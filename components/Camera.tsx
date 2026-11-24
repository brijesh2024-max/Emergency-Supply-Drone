"use client";
import { useEffect, useState } from "react";
import {
  Radio,
  Video,
  Pause,
  Play,
  ScanLine,
  Camera as Capture,
} from "lucide-react";
type Frame = { boxes: { xyxy: number[] }[] };
export default function Camera({ wide = false }: { wide?: boolean }) {
  const [playing, setPlaying] = useState(true),
    [boxes, setBoxes] = useState(true),
    [frames, setFrames] = useState<Frame[]>([]),
    [frame, setFrame] = useState(0),
    [stream, setStream] = useState(false);
  useEffect(() => {
    fetch("/scene/camera.json")
      .then((r) => r.json())
      .then((m) => setFrames(m.frames))
      .catch(() => {});
  }, []);
  useEffect(() => {
    if (!playing || stream || !frames.length) return;
    const id = setInterval(
      () => setFrame((i) => (i + 1) % frames.length),
      1000 / 6,
    );
    return () => clearInterval(id);
  }, [playing, frames, stream]);
  return (
    <section className={"panel camera-panel " + (wide ? "wide-cam" : "")}>
      <div className="panel-title compact">
        <div className="section-title">
          <Video size={17} />
          <h2>Aircraft camera</h2>
        </div>
        <span className="chip amber">
          <i />
          Synthetic
        </span>
      </div>
      <div className="feed-wrap">
        <div className="feed-image">
          <img
            src={
              stream
                ? "/api/camera/stream?overlays=" + boxes
                : "/scene/frames/" + String(frame).padStart(2, "0") + ".jpg"
            }
            alt="Synthetic overhead replay of illustrated people on a rooftop beside floodwater"
          />
          {!stream &&
            boxes &&
            frames[frame]?.boxes.map((b, i) => {
              const [x, y, r, bottom] = b.xyxy;
              return (
                <span
                  key={i}
                  className="bbox"
                  style={{
                    left: x * 100 + "%",
                    top: y * 100 + "%",
                    width: (r - x) * 100 + "%",
                    height: (bottom - y) * 100 + "%",
                  }}
                />
              );
            })}
          <span className="feed-corners" />
          <span className="cam-id">
            <i />
            {stream ? "STREAM" : playing ? "REPLAY" : "PAUSED"} &nbsp; / &nbsp;
            CAM 01
          </span>
          <span className="cam-time">
            {stream ? "6 FPS" : "00:0" + Math.floor(frame / 6) + " / 00:04"}
          </span>
          <span className="cam-sector">RIVERSIDE ROOFTOPS</span>
        </div>
      </div>
      <div className="camera-tools">
        <button
          onClick={() => {
            if (stream) {
              setStream(false);
              setPlaying(false);
            } else setPlaying(!playing);
          }}
          aria-label={playing ? "Pause replay" : "Play replay"}
        >
          {playing ? <Pause size={14} /> : <Play size={14} />}{" "}
          {playing ? "Pause" : "Play"}
        </button>
        <button
          aria-pressed={boxes}
          onClick={() => setBoxes(!boxes)}
          className={boxes ? "enabled" : ""}
        >
          <ScanLine size={14} /> Overlays
        </button>
        <button
          aria-pressed={stream}
          className={stream ? "enabled" : ""}
          onClick={() => {
            setPlaying(true);
            setStream(!stream);
          }}
        >
          <Radio size={14} /> Stream
        </button>
        <a
          href={
            stream
              ? "/scene/camera-still.png"
              : "/scene/frames/" + String(frame).padStart(2, "0") + ".jpg"
          }
          download={
            stream ? "aeris-synthetic-poster.png" : "aeris-synthetic-frame.jpg"
          }
          aria-label="Download synthetic still frame"
        >
          <Capture size={16} />
        </a>
      </div>
    </section>
  );
}
