"""Rebuild camera delivery assets from the fixture. Optional build dependency: Pillow."""
import json
from pathlib import Path
from PIL import Image, ImageDraw
root=Path(__file__).resolve().parents[1]/"public"/"scene"
manifest=json.loads((root/"camera.json").read_text())
folder=root/"frames"
folder.mkdir(exist_ok=True)
with Image.open(root/"camera.png") as animation:
    for i, frame in enumerate(manifest["frames"]):
        animation.seek(i)
        image=animation.convert("RGB")
        image.save(folder/f"{i:02}.jpg",quality=88)
        draw=ImageDraw.Draw(image)
        for obj in frame["boxes"]:
            x,y,r,b=obj["xyxy"]
            draw.rectangle((x*image.width,y*image.height,r*image.width,b*image.height),outline="#d5ff7e",width=2)
        image.save(folder/f"{i:02}-boxes.jpg",quality=88)
