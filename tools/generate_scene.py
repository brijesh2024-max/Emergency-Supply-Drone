"""Rebuild the fictional Srinagar exercise imagery with Python's standard library.

Run from the project root with python tools/generate_scene.py. Camera frames use
an indexed RGB palette so the same raster can be saved as browser APNG and AVI.
No external maps, photographs, models, observations or telemetry are used.
"""
import json
import math
import random
import struct
import zlib
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / "public" / "scene"
W, H = 1500, 900
SOUTH, WEST, NORTH, EAST = 34.055, 74.805, 34.095, 74.875


def rgb(value):
    return tuple(bytes.fromhex(value))


def mix(a, b, t):
    return tuple(round(x * (1 - t) + y * t) for x, y in zip(a, b))


def chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))


class Canvas:
    """Scan-convert projected world geometry to an 8-bit raster."""
    def __init__(self, w, h, extent, camera=False):
        self.w, self.h = w, h
        self.x, self.y, world_w, world_h = extent
        self.sx, self.sy = w / world_w, h / world_h
        self.camera = camera
        self.colors = []
        self.pixels = bytearray(w * h)
        self.color_cache = {}

    def ink(self, value):
        if value not in self.color_cache:
            self.color_cache[value] = len(self.colors)
            self.colors.append(value)
        return self.color_cache[value]

    def project(self, pt):
        return ((pt[0] - self.x) * self.sx, (pt[1] - self.y) * self.sy)

    def polygon(self, pts, color):
        pts = [self.project(p) for p in pts]
        lo = max(0, math.ceil(min(y for _, y in pts)))
        hi = min(self.h, math.ceil(max(y for _, y in pts)))
        if lo >= hi or max(x for x, _ in pts) < 0 or min(x for x, _ in pts) >= self.w:
            return
        edges = list(zip(pts, pts[1:] + pts[:1]))
        ink = bytes([self.ink(color)])
        for row in range(lo, hi):
            scan = row + 0.5
            hits = sorted(x1 + (scan - y1) * (x2 - x1) / (y2 - y1)
                          for (x1, y1), (x2, y2) in edges if (y1 > scan) != (y2 > scan))
            for a, b in zip(hits[::2], hits[1::2]):
                a, b = max(0, round(a)), min(self.w, round(b))
                if b > a:
                    self.pixels[row * self.w + a:row * self.w + b] = ink * (b - a)

    def line(self, pts, width, color):
        for (x1,y1), (x2,y2) in zip(pts, pts[1:]):
            dx, dy = x2-x1, y2-y1
            length = math.hypot(dx, dy)
            if not length:
                continue
            nx, ny = -dy / length * width/2, dx / length * width/2
            self.polygon([(x1+nx,y1+ny),(x2+nx,y2+ny),(x2-nx,y2-ny),(x1-nx,y1-ny)],color)

    def circle(self, x, y, radius, color):
        if (x+radius < self.x or y+radius < self.y or
                x-radius > self.x+self.w/self.sx or y-radius > self.y+self.h/self.sy):
            return
        self.polygon([(x+radius*math.cos(i*math.pi/6), y+radius*math.sin(i*math.pi/6))
                      for i in range(12)], color)

    def texture(self):
        # Per-material luminance variants preserve the palette of the map and feed.
        rng = random.Random(121)
        original = len(self.colors)
        variants = []
        for base in self.colors[:original]:
            variants.append([self.ink(mix(base, (0,0,0), .07)), self.ink(base),
                             self.ink(mix(base,(255,255,255),.035))])
        for i, ink in enumerate(self.pixels):
            self.pixels[i] = variants[ink][rng.randrange(3)]


def center(y):
    return 520 + .33*y + 142*math.sin(y*.008+.6) + 42*math.sin(y*.016)


def radius(y):
    return 42+8*math.sin(y*.016)+5*math.sin(y*.037)


def band(canvas, width, color):
    ys = list(range(-30,H+31,4))
    canvas.polygon([(center(y)-radius(y)-width, y) for y in ys] +
                   [(center(y)+radius(y)+width, y) for y in reversed(ys)], color)


def geo(x,y):
    return [round(SOUTH+(NORTH-SOUTH)*(1-y/H),6),round(WEST+(EAST-WEST)*x/W,6)]


CAM_Y = 451
CAM_X = center(CAM_Y)+radius(CAM_Y)+14
CAM_W, CAM_H = 102, 57.375
CAM_EXTENT = (CAM_X-48,CAM_Y-27,CAM_W,CAM_H)


def scene(c):
    rng = random.Random(51121)
    cam = c.camera
    def color(dark, light):
        return rgb(light if cam else dark)
    ground = color("1a292b","847e68")
    c.pixels[:] = bytes([c.ink(ground)]) * len(c.pixels)
    def local(u,v):
        return (.9759*u-.2182*v+580,.2182*u+.9759*v+310)
    def roof(cx,cy,w,h,angle,material):
        cos, sin = math.cos(angle), math.sin(angle)
        def p(x,y):
            return cx+x*cos-y*sin,cy+x*sin+y*cos
        corners = [p(-w/2,-h/2),p(w/2,-h/2),p(w/2,h/2),p(-w/2,h/2)]
        c.polygon([(x+1.4,y+1.9) for x,y in corners],color("112021","514d42"))
        c.polygon(corners,material)
        c.polygon([p(-w/2,-h/2),p(w/2,-h/2),p(w/2,-.13*h),p(-w/2,.08*h)],
                  mix(material,(231,225,206),.15))
        if cam:
            for i in range(1,math.ceil(w/.55)):
                x=-w/2+i*.55
                c.line([p(x,-h/2),p(x,h/2)],.085,mix(material,(25,34,32),.14))
            c.line([p(-w/2,0),p(w/2,0)],.22,mix(material,(246,235,205),.43))
            c.line([p(-w/2,h/2),p(w/2,h/2)],.22,rgb("78796c"))
            if int(cx+cy)%3==1:
                c.polygon([p(-w*.29,-h*.2),p(-w*.13,-h*.2),p(-w*.13,-h*.02),
                           p(-w*.29,-h*.02)],rgb("657573"))
    dry = [color("223235","8d8b74"),color("263638","969179"),color("203238","858979"),
           color("223638","9c9982"),color("293a39","8d846d")]
    roofs = [color("435454","93968b"),color("3f4e50","a8a497"),color("354748","9c8880"),
             color("465452","a3a28a"),color("3b504f","708a8e"),color("485553","bfa18b")]
    treeshadow = color("152824","424b37")
    trees = [color("263e33","64744c"),color("2b4036","728457"),color("30453a","77865e")]
    roads = []
    for i in range(-22,24):
        u = i*48
        pts = [local(u+.95*math.sin(v/47+i),v) for v in range(-850,1051,20)]
        roads.append((pts,1.95 if i%4 else 3.5))
    for j in range(-24,27):
        v=j*36
        pts=[local(u,v+1.8*math.sin(u/57+j)) for u in range(-900,1451,20)]
        roads.append((pts,1.8 if j%4 else 3))
    for i in range(-22,24):
        for j in range(-24,27):
            u,v=i*48,j*36
            c.polygon([local(u+1,v+1),local(u+47,v+1),local(u+47,v+35),local(u+1,v+35)], rng.choice(dry))
            garden = rng.random()<.24
            for a in range(5):
                for b in range(3):
                    x,y=local(u+5.6+a*9+rng.uniform(-1.6,1.6), v+6+b*10+rng.uniform(-2,2))
                    if x < -12 or x > W+12 or y < -12 or y > H+12:
                        continue
                    w, h = rng.uniform(4.4,8.1),rng.uniform(4.4,8.2)
                    if rng.random() < (.83 if garden else .14):
                        r=rng.uniform(1.7,3.5)
                        c.circle(x+.9,y+1.2,r,treeshadow)
                        leaf=rng.choice(trees)
                        c.circle(x,y,r,leaf)
                        if cam and c.x-5<x<c.x+CAM_W+5 and c.y-5<y<c.y+CAM_H+5:
                            crown=random.Random(round(x*512+y*23))
                            for _ in range(13):
                                theta=crown.uniform(0,2*math.pi)
                                off=r*crown.uniform(.15,.82)
                                c.circle(x+off*math.cos(theta),y+off*math.sin(theta),
                                         r*crown.uniform(.23,.45),crown.choice(trees))
                    else:
                        roof(x,y,w,h,.22+rng.uniform(-.07,.07),rng.choice(roofs))
    for pts,width in roads:
        c.line(pts,width+.65,color("16272a","747564"))
        c.line(pts,width,color("51615e","aaa793"))
    # A contoured wooded ridge beyond the outer streets.
    if not cam:
        ridge = [(1135,-5),(1088,26),(1054,73),(1106,128),(1156,143),(1176,194),
                 (1254,251),(1317,287),(1380,366),(1441,379),(1505,410),(1505,-5)]
        c.polygon(ridge,rgb("263d33"))
        for k in range(3,126,4):
            c.line([(x+k*2.2+3*math.sin(k+y/22),y-k*.65) for x,y in ridge[:-2]],
                   .9, rgb("365043") if k%3 else rgb("405548"))
    # Parked light vehicles, skylights and individual foliage clusters resolve
    # only in the closer survey view. Visual detail does not encode detections.
    if cam:
        detail_rng=random.Random(663)
        for i in range(-22,24):
            for j in range(-24,27):
                px,py=local(i*48,j*36)
                if not (c.x-10 < px < c.x+CAM_W+10 and c.y-10 < py < c.y+CAM_H+10):
                    continue
                for offset in (8.5,15,33):
                    vx,vy=local(i*48+offset,j*36+.9)
                    if detail_rng.random()>.5:
                        c.line([(vx-1.1,vy-.25),(vx+1.1,vy+.25)],1.02,color("384344","474c48"))
                        c.line([(vx-.8,vy-.23),(vx+.8,vy+.16)],.86,color("526260","b5b9ac"))
                        c.line([(vx-.22,vy-.11),(vx+.35,vy+.03)],.68,color("405356","708383"))
    band(c,9,color("30443a","667656"))
    band(c,5.2,color("4c5246","a39772"))
    band(c,2.4,color("354747","968c6e"))
    band(c,0,color("193d49","5c7771"))
    # Narrow current traces follow the simulated watercourse.
    for _ in range(3400):
        y=rng.uniform(-12,H+8)
        x=center(y)+rng.uniform(-radius(y)+2,radius(y)-2)
        length=rng.uniform(.6,5)
        c.line([(x,y),(x+center(y+length)-center(y),y+length)],rng.uniform(.13,.65),
               color("25505a","788e81") if rng.random()>.4 else color("1a424c","536f69"))
    # A winding arterial and two bridges are part of the illustrative plan.
    highway=[(-20,570),(136,529),(281,475),(417,463),(529,403),(620,370),
             (731,352),(809,336),(948,298),(1112,300),(1250,268),(1520,210)]
    crossing=[(-20,813),(195,756),(315,737),(480,702),(620,717),(757,704),
              (891,681),(1033,643),(1220,602),(1520,551)]
    for road in (highway,crossing):
        c.line(road,7.3,color("18282b","5e6258"))
        c.line(road,5.5,color("75807a","b2ac97"))
        c.line(road,3.25,color("566461","8c8c7e"))
        c.line(road,.7,color("a39b7b","d2bf94"))
    # A flooded cluster and its elevated shelter, shared by both projections.
    x,y=CAM_X,CAM_Y
    flood=[(x-31,y-15),(x-18,y-15),(x-13,y-12),(x-9,y-11),(x-6,y-8),(x-1,y-7),
           (x+1,y-6),(x-2,y-3),(x-3,y+4),(x+3,y+7),(x+7,y+8),(x+10,y+12),
           (x+8,y+16),(x+8,y+21),(x+4,y+20),(x+1,y+18),(x-5,y+16),
           (x-12,y+12),(x-19,y+10),(x-22,y+11),(x-30,y+9)]
    c.polygon(flood,color("2a4a4e","72877a"))
    if cam:
        for a,b in zip(flood[:16],flood[1:17]):
            c.line([a,b],.26,rgb("90967d"))
    roof(x,y,15.8,9.5,.22,color("63706a","aca595"))
    roof(x+20,y-4.8,12,7.5,.2,color("4e6060","96998b"))
    roof(x+23,y+7,8.8,6,.2,color("4d5959","a58b7b"))
    if cam:
        for sx,sy in [(x-5,y-1),(x+19,y-4.5),(x+22,y+8.5)]:
            c.polygon([(sx,sy),(sx+1.6,sy+.3),(sx+1.5,sy+1.6),(sx-.3,sy+1.35)],rgb("68716a"))
        for z in range(100):
            px=rng.uniform(x-42,x-20)
            py=rng.uniform(y-24,y+24)
            if abs(px-center(py))<radius(py)-2:
                c.line([(px,py),(px+.55,py+.4)],.14,rgb("91a092"))
    c.texture()


def image_payload(pixels,w,h):
    return zlib.compress(b"".join(b"\0"+pixels[r*w:(r+1)*w] for r in range(h)),8)


def png_header(canvas):
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR",struct.pack(">IIBBBBB",canvas.w,canvas.h,8,3,0,0,0)) +
            chunk(b"PLTE",b"".join(bytes(col) for col in canvas.colors)))


def save_png(path,canvas):
    path.write_bytes(png_header(canvas)+chunk(b"IDAT",image_payload(canvas.pixels,canvas.w,canvas.h))+
                     chunk(b"IEND",b""))


def paint_people(c,t):
    boxes=[]
    for x,y,shirt,phase in [(CAM_X+1.8,CAM_Y-.8,"bb774e",0),(CAM_X-1.2,CAM_Y+1.15,"899daa",1.4)]:
        x+=.23*math.sin(t+phase)
        y+=.12*math.cos(t+phase)
        c.circle(x+.26,y+.62,.52,rgb("666657"))
        c.line([(x-.18,y+.12),(x-.2,y+.9)],.27,rgb("414740"))
        c.line([(x+.13,y+.12),(x+.24,y+.8)],.26,rgb("414740"))
        c.circle(x,y,.49,rgb(shirt))
        c.line([(x-.28,y),(x-.62,y-.25+.2*math.sin(2*t+phase))],.23,rgb(shirt))
        c.circle(x+.04,y-.48,.28,rgb("655f51"))
        a,b=c.project((x-.76,y-.8))
        d,e=c.project((x+.62,y+1.06))
        boxes.append({"label":"person","xyxy":[round(a/c.w,5),round(b/c.h,5),round(d/c.w,5),round(e/c.h,5)]})
    return boxes


def le_chunk(tag,data):
    return tag+struct.pack("<I",len(data))+data+(b"\0" if len(data)%2 else b"")


def save_avi(frames,c,fps):
    # Microsoft RLE8 using literal runs. The first frame is complete; subsequent
    # frames encode each changed scanline with skips (all frames are decodable
    # sequentially). The public APNG uses the same RGB values and frame clock.
    def encode(frame,prev):
        out=bytearray()
        for y in range(c.h-1,-1,-1):
            line=frame[y*c.w:(y+1)*c.w]
            if prev is not None and line == prev[y*c.w:(y+1)*c.w]:
                out.extend(b"\0\0")
                continue
            for off in range(0,len(line),240):
                part=line[off:off+240]
                if len(part)<3:
                    for value in part:
                        out.extend((1,value))
                else:
                    out.extend((0,len(part)))
                    out.extend(part)
                    if len(part)%2:
                        out.append(0)
            out.extend(b"\0\0")
        out.extend(b"\0\1")
        return bytes(out)
    encoded=[encode(f, frames[i-1] if i else None) for i,f in enumerate(frames)]
    avih=struct.pack("<14I",round(1e6/fps),len(encoded[0])*fps,0,16,len(frames),0,1,len(encoded[0]),c.w,c.h,0,0,0,0)
    strh=struct.pack("<4s4sIHH8I4h",b"vids",b"mrle",0,0,0,0,1,fps,0,len(frames),len(encoded[0]),0xffffffff,0,0,0,c.w,c.h)
    palette=b"".join(bytes((b,g,r,0)) for r,g,b in c.colors)
    strf=struct.pack("<IiiHH6I",40,c.w,c.h,1,8,1,len(encoded[0]),0,0,len(c.colors),0)+palette
    hdrl=le_chunk(b"LIST",b"hdrl"+le_chunk(b"avih",avih)+le_chunk(b"LIST",b"strl"+le_chunk(b"strh",strh)+le_chunk(b"strf",strf)))
    movi=bytearray(b"movi")
    index=bytearray()
    for i,f in enumerate(encoded):
        index.extend(struct.pack("<4sIII",b"00dc",16 if i==0 else 0,len(movi),len(f)))
        movi.extend(le_chunk(b"00dc",f))
    (DEST/"camera.avi").write_bytes(le_chunk(b"RIFF",b"AVI "+hdrl+le_chunk(b"LIST",bytes(movi))+le_chunk(b"idx1",bytes(index))))


def main():
    DEST.mkdir(exist_ok=True,parents=True)
    atlas=Canvas(W,H,(0,0,W,H))
    scene(atlas)
    save_png(DEST/"map.png",atlas)
    c=Canvas(640,360,CAM_EXTENT,True)
    scene(c)
    base=bytes(c.pixels)
    fps,n=6,24
    frames=[]
    meta={"source":"synthetic","description":"Fictional flood exercise. Art-directed positions and person annotations.",
          "width":c.w,"height":c.h,"fps":fps,"duration_s":n/fps,
          "frame_center_latlon":geo(CAM_EXTENT[0]+CAM_W/2,CAM_EXTENT[1]+CAM_H/2),
          "map_bounds":[[SOUTH,WEST],[NORTH,EAST]],"frames":[]}
    for i in range(n):
        c.pixels[:]=base
        boxes=paint_people(c,2*math.pi*i/n)
        frames.append(bytes(c.pixels))
        meta["frames"].append({"frame":i,"time_s":round(i/fps,4),"boxes":boxes})
    c.pixels[:]=frames[0]
    save_png(DEST/"camera-still.png",c)
    apng=bytearray(png_header(c)+chunk(b"acTL",struct.pack(">II",n,0)))
    seq=0
    for i,frame in enumerate(frames):
        if i:
            diff=[j for j,(p,q) in enumerate(zip(frame,frames[i-1])) if p!=q]
            xs=[j%c.w for j in diff] or [0]
            ys=[j//c.w for j in diff] or [0]
            x,y=min(xs),min(ys)
            w,h=max(xs)-x+1,max(ys)-y+1
            region=b"".join(frame[row*c.w+x:row*c.w+x+w] for row in range(y,y+h))
        else:
            x,y,w,h,region=0,0,c.w,c.h,frame
        apng.extend(chunk(b"fcTL",struct.pack(">IIIIIHHBB",seq,w,h,x,y,1,fps,0,0)))
        seq+=1
        payload=image_payload(region,w,h)
        if i:
            apng.extend(chunk(b"fdAT",struct.pack(">I",seq)+payload))
            seq+=1
        else:
            apng.extend(chunk(b"IDAT",payload))
    (DEST/"camera.png").write_bytes(apng+chunk(b"IEND",b""))
    (DEST/"camera.json").write_text(json.dumps(meta,separators=(",",":")),encoding="utf-8")
    save_avi(frames,c,fps)
    print(f"{W}x{H} simulated map, {n} camera frames, latitude/longitude {geo(CAM_X,CAM_Y)}")


if __name__=="__main__":
    main()
