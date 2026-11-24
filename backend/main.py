import asyncio
import contextlib
import hashlib
import hmac
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from . import operations as ops
from .store import DEMO, ROOT, event, initialize, password_digest, transaction

@asynccontextmanager
async def lifespan(app):
    initialize()
    async def simulation():
        while True:
            await asyncio.sleep(2)
            await asyncio.to_thread(ops.tick)
    task=asyncio.create_task(simulation())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

app=FastAPI(title="Aeris · Rescue simulation",version="1.0",lifespan=lifespan)
def session(token):
    if not token:
        return None
    with transaction() as db:
        return db.one("SELECT u.username,u.role FROM sessions s JOIN users u ON s.username=u.username WHERE s.digest=? AND s.expires>?",
                      (hashlib.sha256(token.encode()).hexdigest(),time.time()))

def who(req:Request):
    return session(req.cookies.get("aeris_session"))

def permitted(*roles):
    def check(user=Depends(who)):
        if not user:
            raise HTTPException(401,"Sign in to perform this action")
        if user["role"] not in roles:
            raise HTTPException(403,"Your role cannot authorize this action")
        return user["username"]
    return check

def same_origin(origin,host):
    return not origin or urlsplit(origin).netloc==host

@app.middleware("http")
async def origin_check(request, call_next):
    if request.method not in ("GET","HEAD","OPTIONS") and not same_origin(request.headers.get("origin"),request.headers.get("host")):
        return Response("Cross-origin submission refused",403)
    response=await call_next(request)
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"]="no-store"
    return response

class Login(BaseModel):
    username:str=Field(max_length=40)
    password:str=Field(max_length=200)

class Mission(BaseModel):
    name:str=Field(min_length=3,max_length=70)
    kind:Literal["Survey","Delivery"]
    zone:str
    drone:str
    item:str|None=None
    candidate:str|None=None
    qty:int=Field(default=0,ge=0,le=100)
    @field_validator("name")
    @classmethod
    def meaningful_name(cls,v):
        if len(v.strip())<3:
            raise ValueError("Enter a mission name of at least three characters")
        return v.strip()

class Decision(BaseModel):
    status:Literal["Verified","Dismissed"]
    priority:Literal["High","Medium","Low"]

class Observation(BaseModel):
    bbox:tuple[float,float,float,float]
    confidence:float|None=Field(default=None,ge=0,le=1)
    provenance:Literal["synthetic_annotation","yolo_local_weights"]

    @field_validator("bbox")
    @classmethod
    def normalized(cls, box):
        x,y,r,b=box
        if not (0<=x<r<=1 and 0<=y<b<=1):
            raise ValueError("Invalid normalized image coordinates")
        return box

class FrameImport(BaseModel):
    zone:str=Field(max_length=80)
    source:str=Field(min_length=1,max_length=160)
    frame_index:int=Field(ge=0)
    time_s:float=Field(ge=0,allow_inf_nan=False)
    candidates:list[Observation]=Field(min_length=1,max_length=150)

@app.post("/api/vision/import")
def import_frame(data:FrameImport,actor=Depends(permitted("operator","coordinator"))):
    from .store import ZONES, now
    if data.zone not in ZONES:
        raise HTTPException(422,"Unknown exercise sector")
    with transaction(True) as db:
        inserted=0
        for c in data.candidates:
            if (c.confidence is None)!=(c.provenance=="synthetic_annotation"):
                raise HTTPException(422,"Confidence must match observation provenance")
            evidence={"name":data.source,"time_s":data.time_s,"frame_index":data.frame_index,"bbox":c.bbox}
            unique=json.dumps([data.zone,evidence,c.provenance],sort_keys=True)
            key="OBS-"+hashlib.sha256(unique.encode()).hexdigest()[:16]
            cur=db.run("INSERT INTO detections VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING",
                (key,data.zone,*ZONES[data.zone],c.provenance,c.confidence,"Pending","Medium",now(),None,json.dumps(evidence)))
            inserted+=cur.rowcount
        if inserted:
            event(db,"Vision",f"{inserted} frame observations queued at {data.zone}",actor)
    return {"inserted":inserted}

@app.get("/api/health")
def health():
    return {"status":"ok","mode":"simulation"}

@app.get("/api/session")
def profile(user=Depends(who)):
    return {"user":user,"demo":DEMO}

@app.post("/api/login")
def login(data:Login,response:Response):
    with transaction(True) as db:
        user=db.one("SELECT * FROM users WHERE username=?",(data.username,))
        digest=password_digest(data.password,user["salt"] if user else "00"*16)
        if not user or not hmac.compare_digest(user["digest"],digest):
            raise HTTPException(401,"Incorrect username or password")
        token=secrets.token_urlsafe(32)
        db.run("DELETE FROM sessions WHERE expires<?",(time.time(),))
        db.run("INSERT INTO sessions VALUES (?,?,?)",(hashlib.sha256(token.encode()).hexdigest(),user["username"],time.time()+8*3600))
    response.set_cookie("aeris_session",token,httponly=True,samesite="strict",secure=os.getenv("AERIS_SECURE_COOKIE")=="1",max_age=28800)
    return {"username":user["username"],"role":user["role"]}

@app.post("/api/logout")
def logout(req:Request,response:Response):
    token=req.cookies.get("aeris_session","")
    with transaction(True) as db:
        db.run("DELETE FROM sessions WHERE digest=?",(hashlib.sha256(token.encode()).hexdigest(),))
    response.delete_cookie("aeris_session")
    return {"ok":True}

@app.get("/api/state")
def state(user=Depends(who)):
    if not DEMO and not user:
        raise HTTPException(401,"Sign in to view the exercise")
    return ops.snapshot()

@app.get("/api/camera/stream")
def camera_stream(overlays:bool=True,user=Depends(who)):
    if not DEMO and not user:
        raise HTTPException(401,"Sign in to view the replay")
    from .camera import frames
    return StreamingResponse(frames(overlays),media_type="multipart/x-mixed-replace; boundary=exercise")

@app.get("/api/assessment")
def assessment(user=Depends(who)):
    if not DEMO and not user:
        raise HTTPException(401,"Sign in to view the exercise")
    from vision.scenario import assess_exercise_raster
    from vision.sos import inspect_placard
    return {**assess_exercise_raster(),"sos":inspect_placard()}

@app.post("/api/weather/{profile}")
def set_weather(profile:Literal["Calm","Rain","Storm"],actor=Depends(permitted("coordinator"))):
    with transaction(True) as db:
        db.run("INSERT INTO settings VALUES ('weather',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(profile,))
        event(db,"Weather",profile+" exercise weather profile selected",actor)
    return {"ok":True}

@app.websocket("/api/stream")
async def stream(ws:WebSocket):
    if not same_origin(ws.headers.get("origin"),ws.headers.get("host")):
        await ws.close(code=1008)
        return
    token=ws.cookies.get("aeris_session")
    if not DEMO and not await asyncio.to_thread(session,token):
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        while True:
            if not DEMO and not await asyncio.to_thread(session,token):
                await ws.close(code=1008)
                return
            await ws.send_json(await asyncio.to_thread(ops.snapshot))
            await asyncio.sleep(2)
    except (WebSocketDisconnect,RuntimeError,OSError):
        pass

@app.post("/api/missions",status_code=201)
def new(data:Mission,actor=Depends(permitted("operator","coordinator"))):
    with transaction(True) as db:
        return {"id":ops.create_mission(db,data,actor)}

@app.post("/api/missions/{key}/{action}")
def mission_action(key:str,action:Literal["approve","confirm","cancel","return","land"],user=Depends(permitted("operator","coordinator"))):
    if action in ("approve","return","land") and user!="coordinator":
        raise HTTPException(403,"Coordinator authorization required")
    with transaction(True) as db:
        ops.act(db,key,action,user)
    return {"ok":True}

@app.post("/api/detections/{key}/review")
def review(key:str,data:Decision,actor=Depends(permitted("operator","coordinator"))):
    with transaction(True) as db:
        ops.review(db,key,data.status,data.priority,actor)
    return {"ok":True}

@app.post("/api/fleet/{key}/{action}")
def fleet(key:str,action:Literal["link-loss","restore-link","recover"],actor=Depends(permitted("coordinator"))):
    with transaction(True) as db:
        if action=="recover":
            ops.recover(db,key,actor)
        else:
            ops.fetch(db,"drones",key)
            db.run("UPDATE drones SET link=? WHERE id=?",(int(action=="restore-link"),key))
            event(db,"Fleet",key+" · "+action,actor)
    return {"ok":True}

@app.post("/api/alerts/{key}/acknowledge")
def acknowledge(key:str,actor=Depends(permitted("operator","coordinator"))):
    with transaction(True) as db:
        ops.fetch(db,"alerts",key)
        db.run("UPDATE alerts SET acknowledged_by=? WHERE id=? AND acknowledged_by IS NULL",(actor,key))
    return {"ok":True}

@app.get("/api/report")
def report(user=Depends(permitted("observer","operator","coordinator"))):
    result=ops.snapshot(full_history=True)
    result["assessment"]=assessment({"username":user})
    return Response(json.dumps(result,indent=2),media_type="application/json",headers={"Content-Disposition":"attachment; filename=aeris-exercise-report.json"})

site=ROOT.parent/"out"
if site.is_dir():
    app.mount("/",StaticFiles(directory=site,html=True),name="dashboard")
