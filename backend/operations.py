"""Transactional exercise workflow. All aircraft state lives in the exercise database."""
import json
import math
from fastapi import HTTPException
from .planning import distance, plan
from .insights import weather, demand, priority_hint
from .store import BASE, BLOCKS, DEMO, GEOFENCE, ZONES, event, ident, now, transaction

def reject(message, code=409):
    raise HTTPException(code, message)

def fetch(db, table, key):
    row=db.one(f"SELECT * FROM {table} WHERE id=?", (key,))
    if not row:
        reject("Record not found",404)
    return row

def snapshot(full_history=False):
    with transaction() as db:
        missions=db.rows("SELECT * FROM missions ORDER BY created DESC,id")
        for m in missions:
            m["route"]=json.loads(m["route"])
        detections=db.rows("""SELECT * FROM detections ORDER BY
            CASE status WHEN 'Pending' THEN 0 WHEN 'Verified' THEN 1 ELSE 2 END,
            CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END,
            observed DESC,id""")
        for d in detections:
            d["evidence"]=json.loads(d["evidence"])
            d["hint"]=priority_hint(d)
        return {"mode":"Simulation","time":now(),"demo":DEMO,"drones":db.rows("SELECT * FROM drones ORDER BY id"),
                "missions":missions,"detections":detections,"inventory":db.rows("SELECT * FROM inventory ORDER BY name"),
                "events":db.rows("SELECT * FROM events ORDER BY time DESC,id"+("" if full_history else " LIMIT 150")),
                "alerts":db.rows("SELECT * FROM alerts ORDER BY id DESC"),"zones":ZONES,"base":BASE,
                "blocks":BLOCKS,"bounds":GEOFENCE,"plans":{zone:plan(zone) for zone in ZONES},
                "weather":weather(db),"demand":demand(db)}

def check_load(db, drone, zone, kind, item, qty, candidate):
    if weather(db)["hold"]:
        reject("Dispatch is on hold under the simulated storm profile")
    if zone not in ZONES:
        reject("Select an exercise zone",422)
    if drone["status"]!="Ready" or not drone["link"]:
        reject("Aircraft must be connected and ready")
    route=plan(zone)
    length=sum(distance(a,b) for a,b in zip(route,route[1:]))
    if drone["battery"] < 25+length*4:
        reject("Battery reserve is too low for this corridor")
    if kind=="Delivery":
        supply=fetch(db,"inventory",item)
        if qty<1 or qty>supply["available"]:
            reject("Quantity exceeds available stock")
        if qty*supply["mass"]>drone["capacity"]+1e-9:
            reject("Load exceeds aircraft payload capacity")
        if fetch(db,"detections",candidate)["status"]!="Verified":
            reject("Delivery requires a verified assistance request")
        if db.one("SELECT id FROM missions WHERE candidate=? AND (status IN ('Active','Awaiting receipt','Returning') OR return_reason='Delivered')", (candidate,)):
            reject("This request already has an assigned or completed delivery")
    return route

def create_mission(db, data, actor):
    drone=fetch(db,"drones",data.drone)
    route=check_load(db,drone,data.zone,data.kind,data.item,data.qty,data.candidate)
    key=ident("MS")
    delivery=data.kind=="Delivery"
    db.run("INSERT INTO missions (id,name,kind,drone,zone,route,status,item,qty,candidate,created_by,created) VALUES (?,?,?,?,?,?,'Proposed',?,?,?,?,?)",
           (key,data.name.strip(),data.kind,data.drone,data.zone,json.dumps(route),data.item if delivery else None,
            data.qty if delivery else 0,data.candidate if delivery else None,actor,now()))
    event(db,"Mission",f"{key} · {data.name.strip()} submitted for approval",actor)
    return key

def return_route(db, m, drone, reason):
    original=json.loads(m["route"])
    index=min(int(m["progress"]),len(original)-1)
    route=[[drone["lat"],drone["lon"]],*reversed(original[:index+1])]
    if m["patrol"]:
        # Patrol endpoints lie on the prechecked outbound route.
        outbound=plan(m["zone"])
        join=outbound.index(tuple(original[0]))
        route.extend(reversed(outbound[:join]))
    if tuple(route[-1])!=BASE:
        reject("Return corridor unavailable")
    db.run("UPDATE missions SET status='Returning',progress=0,route=?,return_reason=?,patrol=0 WHERE id=?",
           (json.dumps(route),reason,m["id"]))
    db.run("UPDATE drones SET status='Returning' WHERE id=?",(drone["id"],))

def restore(db,m):
    if m["reserved"]:
        db.run("UPDATE inventory SET available=available+? WHERE id=?",(m["qty"],m["item"]))
        db.run("UPDATE missions SET reserved=0 WHERE id=?",(m["id"],))

def act(db, key, action, actor):
    m=fetch(db,"missions",key)
    drone=fetch(db,"drones",m["drone"])
    status=m["status"]
    if action=="approve" and status=="Proposed":
        check_load(db,drone,m["zone"],m["kind"],m["item"],m["qty"],m["candidate"])
        if m["kind"]=="Delivery":
            db.run("UPDATE inventory SET available=available-? WHERE id=?",(m["qty"],m["item"]))
        db.run("UPDATE missions SET approved_by=?,status='Active',reserved=? WHERE id=?",
               (actor,int(m["kind"]=="Delivery"),key))
        db.run("UPDATE drones SET status=?,altitude=45 WHERE id=?",("Delivering" if m["kind"]=="Delivery" else "Surveying",m["drone"]))
    elif action=="confirm" and status=="Awaiting receipt":
        db.run("UPDATE missions SET reserved=0 WHERE id=?",(key,))
        return_route(db,m,drone,"Delivered")
    elif action=="return" and status in ("Active","Awaiting receipt"):
        return_route(db,m,drone,"Recalled")
    elif action=="land" and status in ("Active","Awaiting receipt","Returning"):
        db.run("UPDATE missions SET status='Landed' WHERE id=?",(key,))
        db.run("UPDATE drones SET status='Grounded',altitude=0 WHERE id=?",(m["drone"],))
        # Reserved cargo stays with a grounded aircraft until simulated recovery.
    elif action=="cancel" and status=="Proposed":
        db.run("UPDATE missions SET status='Cancelled' WHERE id=?",(key,))
    else:
        reject("This action is unavailable in the current mission state")
    event(db,"Mission",f"{key} · {action} confirmed",actor)

def recover(db,drone_id,actor):
    drone=fetch(db,"drones",drone_id)
    if drone["status"]!="Grounded":
        reject("Only a grounded aircraft can be recovered")
    for m in db.rows("SELECT * FROM missions WHERE drone=? AND reserved=1",(drone_id,)):
        restore(db,m)
    db.run("UPDATE drones SET status='Ready',link=1,lat=?,lon=?,altitude=0 WHERE id=?",(*BASE,drone_id))
    event(db,"Fleet",f"{drone_id} recovered at exercise base",actor)

def review(db, key, status, priority, actor):
    if fetch(db,"detections",key)["status"]!="Pending":
        reject("Observation has already been reviewed")
    db.run("UPDATE detections SET status=?,priority=?,reviewed_by=? WHERE id=?",(status,priority,actor,key))
    event(db,"Detection",f"{key} · {status.lower()} with {priority.lower()} priority",actor)

def tick():
    with transaction(True) as db:
        storm=weather(db)["hold"]
        db.run("UPDATE drones SET battery=CASE WHEN battery<99.9 THEN battery+0.08 ELSE 100 END WHERE status='Ready' AND battery<100")
        for m in db.rows("SELECT * FROM missions WHERE status IN ('Active','Awaiting receipt','Returning')"):
            drone=fetch(db,"drones",m["drone"])
            if m["status"]!="Returning" and (drone["battery"]<=23 or not drone["link"] or storm):
                reason="Link lost" if not drone["link"] else "Storm hold" if storm else "Battery reserve"
                return_route(db,m,drone,reason)
                db.run("INSERT INTO alerts VALUES (?,?,?,?,NULL)",(ident("ALT"),"High",reason+" · "+drone["id"],"Simulated aircraft is following its return corridor."))
                event(db,"Failsafe",f'{drone["id"]} · {reason.lower()}, return initiated',"simulator")
                continue
            if m["status"]=="Awaiting receipt":
                continue
            route=json.loads(m["route"])
            progress=m["progress"]+(0.013 if m["patrol"] else 0.35)
            end=progress>=len(route)-1
            if end and m["patrol"]:
                progress=0
                end=False
            progress=min(progress,len(route)-1)
            i=min(int(progress),len(route)-2)
            f=progress-i
            point=[a+(b-a)*f for a,b in zip(route[i],route[i+1])]
            db.run("UPDATE drones SET lat=?,lon=?,battery=CASE WHEN battery>? THEN battery-? ELSE 0 END,altitude=? WHERE id=?",
                   (*point,0.018 if m["patrol"] else 0.22,0.018 if m["patrol"] else 0.22,65 if m["kind"]=="Survey" else 42,drone["id"]))
            db.run("UPDATE missions SET progress=? WHERE id=?",(progress,m["id"]))
            if not end:
                continue
            if m["status"]=="Returning":
                restore(db,m)
                final="Completed" if m["return_reason"] in ("Delivered","Survey complete") else "Recalled"
                db.run("UPDATE missions SET status=? WHERE id=?",(final,m["id"]))
                db.run("UPDATE drones SET status='Ready',altitude=0,lat=?,lon=? WHERE id=?",(*BASE,drone["id"]))
                event(db,"Mission",m["id"]+" · "+final.lower()+" at base","simulator")
            elif m["kind"]=="Delivery":
                db.run("UPDATE missions SET status='Awaiting receipt' WHERE id=?",(m["id"],))
                db.run("UPDATE drones SET status='At relief zone',altitude=0 WHERE id=?",(drone["id"],))
                event(db,"Delivery",m["id"]+" · landed at relief zone, awaiting operator receipt","simulator")
            else:
                key=ident("DET")
                db.run("INSERT INTO detections VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (key,m["zone"],*point,"Exercise survey fixture",None,"Pending","Medium",now(),None,"{}"))
                return_route(db,{**m,"progress":progress},{**drone,"lat":point[0],"lon":point[1]},"Survey complete")
                event(db,"Detection",key+" · survey observation queued for review","simulator")
