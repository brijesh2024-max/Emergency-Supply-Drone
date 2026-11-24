"""Shortest path on a fixed exercise graph. Coordinates represent synthetic scenario sites."""
import heapq
import math
from .store import BASE, BLOCKS, GEOFENCE, ZONES

NODES = [BASE, (34.064,74.833), (34.064,74.852), (34.070,74.823),
         (34.082,74.825), *ZONES.values(), (34.084,74.853)]
EDGES = [(0,1),(1,2),(2,7),(0,3),(3,5),(3,4),(5,4),(4,6),(6,8),(7,8),
         (0,6),(1,6),(3,7)]
def intersects(a,b,rect):
    lo,hi=0.0,1.0
    for x,y,mn,mx in zip(a,b,rect[:2],rect[2:]):
        delta=y-x
        if delta==0:
            if x<mn or x>mx:
                return False
        else:
            t,u=sorted(((mn-x)/delta,(mx-x)/delta))
            lo,hi=max(lo,t),min(hi,u)
            if lo>hi:
                return False
    return True

def clear(a,b):
    s,w,n,e=GEOFENCE
    return all(s<=p[0]<=n and w<=p[1]<=e for p in (a,b)) and not any(intersects(a,b,x["bounds"]) for x in BLOCKS)

def distance(a,b):
    return 111.2 * math.hypot(a[0]-b[0], (a[1]-b[1])*math.cos(math.radians(34.075)))

def plan(zone):
    target=NODES.index(ZONES[zone])
    queue=[(0,0,[0])]
    visited=set()
    while queue:
        cost,node,path=heapq.heappop(queue)
        if node==target:
            return [NODES[i] for i in path]
        if node in visited:
            continue
        visited.add(node)
        for left,right in EDGES:
            if node not in (left,right):
                continue
            nxt=right if node==left else left
            if nxt not in visited and clear(NODES[node],NODES[nxt]):
                heapq.heappush(queue,(cost+distance(NODES[node],NODES[nxt]),nxt,path+[nxt]))
    raise ValueError("No clear exercise corridor reaches this zone")
