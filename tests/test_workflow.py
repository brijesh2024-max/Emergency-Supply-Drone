"""Run with python -m unittest discover -s tests after installing httpx."""
import asyncio
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import main, operations
from backend.planning import clear, plan
from backend.store import ZONES, initialize, transaction

class ExerciseTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{"AERIS_DB":str(Path(self.temp.name)/"exercise.sqlite3")})
        self.env.start()
        self.pg=patch("backend.store.POSTGRES","")
        self.pg.start()
        initialize()
        self.client=TestClient(main.app)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.env.stop)
        self.addCleanup(self.pg.stop)
        self.addCleanup(self.client.close)

    def login(self,role="coordinator"):
        response=self.client.post("/api/login",json={"username":role,"password":"exercise-"+role})
        self.assertEqual(response.status_code,200,response.text)

    def mission(self,**changes):
        payload={"name":"Relief exercise","kind":"Delivery","drone":"AX-02",
                 "zone":"North school yard","item":"water","qty":2,"candidate":"DET-003"}
        return self.client.post("/api/missions",json={**payload,**changes})

    def action(self,mid,action):
        return self.client.post(f"/api/missions/{mid}/{action}",json={})

    def stock(self):
        with transaction() as db:
            return db.one("SELECT available FROM inventory WHERE id='water'")["available"]

    def advance(self,mid,status):
        for _ in range(48):
            with transaction() as db:
                if db.one("SELECT status FROM missions WHERE id=?",(mid,))["status"]==status:
                    return
            operations.tick()
        self.fail("Mission never reached "+status)

    def test_role_gates_and_receipt(self):
        self.assertEqual(self.mission().status_code,401)
        self.login("observer")
        self.assertEqual(self.mission().status_code,403)
        self.login("operator")
        self.assertEqual(self.mission(qty=9).status_code,409)
        self.assertEqual(self.mission(candidate="DET-001").status_code,409)
        self.assertEqual(self.client.post("/api/detections/DET-001/review",json={"priority":"High","status":"Verified"}).status_code,200)
        result=self.mission(candidate="DET-001")
        self.assertEqual(result.status_code,201,result.text)
        mid=result.json()["id"]
        self.assertEqual(self.stock(),48)
        self.assertEqual(self.action(mid,"approve").status_code,403)
        self.login()
        self.assertEqual(self.action(mid,"approve").status_code,200)
        self.assertEqual(self.action(mid,"approve").status_code,409)
        self.assertEqual(self.stock(),46)
        self.assertEqual(self.action(mid,"confirm").status_code,409)
        self.advance(mid,"Awaiting receipt")
        self.login("operator")
        self.assertEqual(self.action(mid,"confirm").status_code,200)
        self.assertEqual(self.action(mid,"confirm").status_code,409)
        self.advance(mid,"Completed")
        self.assertEqual(self.stock(),46)
        self.assertEqual(self.mission(candidate="DET-001").status_code,409)
        report=self.client.get("/api/report").json()
        self.assertTrue(any(mid in e["message"] for e in report["events"]))
        initialize()
        self.assertEqual(self.stock(),46)

    def test_simultaneous_approvals_preserve_exclusive_assignment(self):
        self.login()
        ids=[self.mission().json()["id"] for _ in range(2)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda mid:self.action(mid,"approve").status_code,ids))
        self.assertEqual(sorted(results),[200,409])
        self.assertEqual(self.stock(),46)

    def test_link_loss_and_recovery(self):
        self.login()
        mid=self.mission().json()["id"]
        self.action(mid,"approve")
        operations.tick()
        self.client.post("/api/fleet/AX-02/link-loss",json={})
        self.advance(mid,"Returning")
        self.advance(mid,"Recalled")
        self.assertEqual(self.stock(),48)
        self.assertEqual(self.mission().status_code,409)
        self.client.post("/api/fleet/AX-02/restore-link",json={})
        mid=self.mission().json()["id"]
        self.action(mid,"approve")
        self.action(mid,"land")
        self.assertEqual(self.stock(),46)
        self.assertEqual(self.client.post("/api/fleet/AX-02/recover",json={}).status_code,200)
        self.assertEqual(self.stock(),48)

    def test_restrictions_weather_and_battery(self):
        self.assertFalse(clear((34.074,74.83),(34.077,74.85)))
        self.assertFalse(clear((34.4,74.84),(34.077,74.85)))
        for zone in ZONES:
            path=plan(zone)
            self.assertTrue(all(clear(a,b) for a,b in zip(path,path[1:])))
        self.login()
        self.client.post("/api/weather/Storm",json={})
        self.assertEqual(self.mission().status_code,409)
        operations.tick()
        self.advance("MS-101","Recalled")
        self.client.post("/api/weather/Calm",json={})
        with transaction(True) as db:
            db.run("UPDATE drones SET battery=10 WHERE id='AX-02'")
        self.assertEqual(self.mission().status_code,409)

    def test_vision_import_and_duplicate(self):
        self.login("operator")
        payload={"source":"Training clip","zone":"East relief camp","frame_index":3,
                 "time_s":1.5,"candidates":[{"bbox":[.2,.3,.4,.5],"confidence":.78,"provenance":"yolo_local_weights"}]}
        for count in [1,0]:
            response=self.client.post("/api/vision/import",json=payload)
            self.assertEqual(response.json(),{"inserted":count},response.text)
        state=self.client.get("/api/state").json()
        imported=next(d for d in state["detections"] if d["id"].startswith("OBS-"))
        self.assertEqual(imported["confidence"],.78)
        self.assertEqual(imported["status"],"Pending")
        self.assertEqual(imported["evidence"]["frame_index"],3)
        payload["candidates"][0]["bbox"]=[2,0,1,1]
        self.assertEqual(self.client.post("/api/vision/import",json=payload).status_code,422)

    def test_websocket_and_origin(self):
        with self.client.websocket_connect("/api/stream") as ws:
            first=ws.receive_json()
            self.assertEqual(first["mode"],"Simulation")
            operations.tick()
            second=ws.receive_json()
            self.assertNotEqual(first["drones"][0]["lat"],second["drones"][0]["lat"])
        response=self.client.post("/api/logout",json={},headers={"Origin":"https://unrelated.invalid"})
        self.assertEqual(response.status_code,403)

    def test_private_mode_and_logout(self):
        with patch("backend.main.DEMO",False):
            self.assertEqual(self.client.get("/api/state").status_code,401)
            self.assertEqual(self.client.get("/api/assessment").status_code,401)
            self.login("observer")
            self.assertEqual(self.client.get("/api/state").status_code,200)
            self.client.post("/api/logout",json={})
            self.assertEqual(self.client.get("/api/report").status_code,401)

    def test_dashboard_assets(self):
        self.assertEqual(self.client.get("/").status_code,200)
        self.assertIn("Operations overview",self.client.get("/").text)
        for url in ["/vendor/leaflet/leaflet.js","/scene/map.png","/scene/camera.avi","/scene/camera.json"]:
            self.assertEqual(self.client.get(url).status_code,200,url)

    def test_survey_observation_and_low_battery_return(self):
        self.login()
        before=len(self.client.get("/api/state").json()["detections"])
        mid=self.mission(kind="Survey").json()["id"]
        self.assertEqual(self.action(mid,"approve").status_code,200)
        self.advance(mid,"Completed")
        self.assertEqual(len(self.client.get("/api/state").json()["detections"]),before+1)
        mid=self.mission().json()["id"]
        self.action(mid,"approve")
        with transaction(True) as db:
            db.run("UPDATE drones SET battery=22 WHERE id='AX-02'")
        operations.tick()
        self.advance(mid,"Recalled")
        self.assertEqual(self.stock(),48)

    def test_camera_stream_contains_jpeg_frames(self):
        from backend.camera import frames,jpeg
        async def verify():
            replay=frames(True)
            try:
                for i in range(2):
                    packet=await anext(replay)
                    self.assertIn(b"X-Frame: "+str(i).encode(),packet)
                    self.assertIn(jpeg(i,True),packet)
                    self.assertNotEqual(jpeg(i,True),jpeg(i,False))
            finally:
                await replay.aclose()
        asyncio.run(verify())
