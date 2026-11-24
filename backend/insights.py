"""Explanatory estimates for a synthetic incident. Values are exercise assumptions."""
WEATHER={
    "Calm":{"wind_kph":8,"gust_kph":13,"rain_mm_h":0.0,"risk":"Low","hold":False},
    "Rain":{"wind_kph":16,"gust_kph":23,"rain_mm_h":4.0,"risk":"Moderate","hold":False},
    "Storm":{"wind_kph":34,"gust_kph":52,"rain_mm_h":16.0,"risk":"High","hold":True},
}

def weather(db):
    row=db.one("SELECT value FROM settings WHERE name='weather'")
    profile=row["value"] if row else "Rain"
    return {"profile":profile,**WEATHER[profile]}

def demand(db):
    unserved=db.one("""SELECT COUNT(*) AS n FROM detections d WHERE d.status='Verified' AND NOT EXISTS
       (SELECT 1 FROM missions m WHERE m.candidate=d.id AND
        (m.status IN ('Active','Awaiting receipt') OR m.return_reason='Delivered'))""")["n"]
    # Scenario exercise packs contain one food and one water unit per open request.
    return {"open_requests":unserved,"food_units":unserved,"water_units":unserved,
            "basis":"One food ration and one water unit per verified, unassigned exercise request."}

def priority_hint(d):
    if d["source"]=="Synthetic SOS placard":
        return {"priority":"High","reason":"Visible distress sign in the exercise frame."}
    if "rooftop" in d["sector"].lower():
        return {"priority":"High","reason":"The exercise identifies an isolated rooftop."}
    return {"priority":"Medium","reason":"Location and access need an operator check."}
