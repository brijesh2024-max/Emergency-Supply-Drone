"""Multipart MJPEG replay with frame-matched optional annotations."""
import asyncio
from functools import lru_cache
from .store import ROOT
@lru_cache(maxsize=48)
def jpeg(index,overlays):
    suffix="-boxes" if overlays else ""
    return (ROOT.parent/"public"/"scene"/"frames"/f"{index:02}{suffix}.jpg").read_bytes()

async def frames(overlays=True):
    index=0
    while True:
        data=jpeg(index,overlays)
        yield (b"--exercise\r\nContent-Type: image/jpeg\r\nContent-Length: "+
               str(len(data)).encode()+b"\r\nX-Frame: "+str(index).encode()+b"\r\n\r\n"+data+b"\r\n")
        index=(index+1)%24
        await asyncio.sleep(1/6)
