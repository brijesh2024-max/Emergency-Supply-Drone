import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POSTGRES = os.getenv("DATABASE_URL", "")
DEMO = os.getenv("AERIS_DEMO", "1") == "1"
BASE = (34.066, 74.818)
ZONES = {
    "West assembly ground": (34.077, 74.820),
    "North school yard": (34.087, 74.842),
    "East relief camp": (34.071, 74.862),
}
GEOFENCE = (34.055, 74.805, 34.095, 74.875)
# Axis-aligned exercise exclusion areas: south, west, north, east.
BLOCKS = [
    {"name": "Restricted airspace", "bounds": [34.073, 74.834, 34.080, 74.844]},
    {"name": "Damaged bridge", "bounds": [34.067, 74.844, 34.070, 74.849]},
]

def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def ident(prefix):
    return prefix + "-" + secrets.token_hex(3).upper()

def password_digest(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

class DB:
    def __init__(self, conn):
        self.conn = conn

    def run(self, sql, args=()):
        return self.conn.execute(sql.replace("?", "%s") if POSTGRES else sql, tuple(args))

    def rows(self, sql, args=()):
        return [dict(row) for row in self.run(sql, args).fetchall()]

    def one(self, sql, args=()):
        row = self.run(sql, args).fetchone()
        return dict(row) if row else None

@contextmanager
def transaction(write=False):
    if POSTGRES:
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect(POSTGRES, row_factory=dict_row)
    else:
        path = Path(os.getenv("AERIS_DB", str(ROOT.parent / "data" / "exercise.sqlite3")))
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=10)
        conn.row_factory = sqlite3.Row
    try:
        if POSTGRES:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ" if not write else "SELECT pg_advisory_xact_lock(897421)")
        else:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        yield DB(conn)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()

def event(db, kind, message, actor):
    db.run("INSERT INTO events VALUES (?,?,?,?,?)", (ident("EV"), now(), kind, message, actor))

def initialize():
    with transaction(True) as db:
        files = ["schema.sql"] + (["postgis.sql"] if POSTGRES else [])
        for file in files:
            for statement in (ROOT / file).read_text().split(";"):
                if statement.strip():
                    db.run(statement)
        for username in ("operator", "coordinator", "observer"):
            password = os.getenv("AERIS_" + username.upper() + "_PASSWORD")
            if not password and DEMO:
                password = "exercise-" + username
            if not password:
                raise RuntimeError("Set all three AERIS role passwords when demo access is disabled")
            existing = db.one("SELECT * FROM users WHERE username=?", (username,))
            if not existing or password_digest(password, existing["salt"]) != existing["digest"]:
                salt = secrets.token_hex(16)
                db.run("INSERT INTO users VALUES (?,?,?,?) ON CONFLICT(username) DO UPDATE SET salt=excluded.salt,digest=excluded.digest",
                       (username, username, salt, password_digest(password, salt)))
                db.run("DELETE FROM sessions WHERE username=?", (username,))
        if db.one("SELECT id FROM drones LIMIT 1"):
            return
        for drone, model, cap, battery, location, alt, status in [
            ("AX-01","Survey quad",2.4,92,(34.080,74.826),65,"Surveying"),
            ("AX-02","Cargo quad",4.0,98,BASE,0,"Ready"),
            ("AX-03","Survey quad",2.2,87,(34.067,74.853),70,"Surveying"),
            ("AX-04","Cargo quad",5.0,95,BASE,0,"Ready")]:
            db.run("INSERT INTO drones VALUES (?,?,?,?,?,?,?,?,?)", (drone,model,cap,battery,*location,alt,1,status))
        for row in [("medical","First-aid kit",0.65,24),("water","Drinking water",1.0,48),("food","Food ration",0.45,36),("radio","Emergency radio",0.35,12),("blanket","Thermal blanket",0.25,32)]:
            db.run("INSERT INTO inventory VALUES (?,?,?,?)",row)
        for i,(sector, point, priority, status) in enumerate([
            ("Riverside rooftops",(34.074881,74.834845),"High","Pending"),
            ("East embankment",(34.069,74.854),"Medium","Pending"),
            ("School courtyard",(34.086,74.843),"Medium","Verified"),
            ("South approach",(34.064,74.833),"Low","Dismissed")],1):
            evidence={}
            source="Scenario annotation"
            if i==1:
                from vision.pipeline import fixture_report
                frame=fixture_report()["frames"][0]
                evidence={"name":"Exercise aerial camera","frame_index":0,"time_s":0,"bbox":frame["candidates"][0]["bbox"]}
                source="Synthetic camera annotation"
            elif i==2:
                from vision.sos import inspect_placard
                sign=inspect_placard()
                if sign["detected"]:
                    source="Synthetic SOS placard"
                    evidence={"name":"Synthetic placard","asset":sign["asset"],"template_agreement":sign["template_agreement"]}
            db.run("INSERT INTO detections VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   (f"DET-{i:03}",sector,*point,source,None,status,priority,now(),"exercise setup" if status!="Pending" else None,json.dumps(evidence)))
        from .planning import plan
        for mid, drone, zone, name in [("MS-101","AX-01","North school yard","North bank survey"),("MS-102","AX-03","East relief camp","Embankment assessment")]:
            route = plan(zone)
            # Patrol the surveyed end of an approved corridor in both directions.
            path = [route[-2], route[-1], route[-2]]
            start = [a+(b-a)*0.45 for a,b in zip(path[0],path[1])]
            db.run("UPDATE drones SET lat=?,lon=? WHERE id=?",(*start,drone))
            db.run("INSERT INTO missions (id,name,kind,drone,zone,route,progress,status,qty,created_by,approved_by,created,patrol) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (mid,name,"Survey",drone,zone,json.dumps(path),0.45,"Active",0,"exercise setup","exercise setup",now(),1))
        db.run("INSERT INTO alerts VALUES (?,?,?,?,?)",("ALT-01","High","Bridge access blocked","Exercise survey flags the east crossing for ground-team review.",None))
        event(db,"Exercise","Flood response exercise opened in Srinagar","exercise setup")
        event(db,"Fleet","Two survey aircraft assigned to the affected sectors","exercise setup")
        event(db,"Detection","Riverside rooftops queued for operator review","exercise setup")
