"""Produce reviewable detections from the built-in fixture or a local video."""

import argparse
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .scenario import assess_exercise_raster


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "public" / "scene" / "camera.json"
VIDEO_SUFFIXES = {".avi", ".mov", ".mp4", ".mkv", ".webm"}
DAMAGE_LABELS = {"flooded_area", "blocked_road", "damaged_infrastructure"}


def report_header(kind, name, modality):
    return {
        "schema_version": 1,
        "mode": "simulation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {"kind": kind, "name": name, "modality": modality},
        "frames": [],
    }


def candidate(frame_index, index, box, confidence, provenance):
    coords = [float(value) for value in box]
    if len(coords) != 4 or not all(math.isfinite(value) for value in coords):
        raise ValueError("Expected four finite bounding box coordinates")
    coords = [min(1.0, max(0.0, value)) for value in coords]
    left, top, right, bottom = coords
    if left >= right or top >= bottom:
        raise ValueError("Bounding box must have positive area")
    if confidence is not None and not 0 <= confidence <= 1:
        raise ValueError("Confidence must be in [0, 1]")
    return {
        "id": f"f{frame_index}-p{index}",
        "label": "person",
        "bbox": coords,
        "confidence": confidence,
        "provenance": provenance,
        "review_status": "pending",
    }


def fixture_report(manifest=MANIFEST):
    """Read the same annotations used to render the synthetic camera replay."""
    source = json.loads(Path(manifest).read_text(encoding="utf-8-sig"))
    if source.get("source") != "synthetic":
        raise ValueError("Expected a synthetic camera manifest")
    report = report_header("synthetic", "Exercise aerial camera", "rgb")
    assessment = assess_exercise_raster()
    for frame in source["frames"]:
        frame_id = int(frame["frame"])
        report["frames"].append({
            "frame_index": frame_id,
            "time_s": float(frame["time_s"]),
            "candidates": [
                candidate(frame_id, i, box["xyxy"], None, "synthetic_annotation")
                for i, box in enumerate(frame["boxes"]) if box["label"] == "person"
            ],
            "assessment": assessment,
        })
    if not report["frames"]:
        raise ValueError("Camera manifest contains no frames")
    return report


def local_file(value, suffixes):
    path = Path(value).resolve(strict=True)
    if not path.is_file() or path.suffix.lower() not in suffixes:
        raise ValueError(f"Select a local file ending in {', '.join(sorted(suffixes))}")
    return path


def class_ids(model, labels):
    names = model.names
    pairs = names.items() if isinstance(names, dict) else enumerate(names)
    return {
        int(index): str(label).strip().lower().replace(" ", "_")
        for index, label in pairs if str(label).strip().lower().replace(" ", "_") in labels
    }


def infer(model, rgb_or_thermal, classes, confidence):
    result = model.predict(
        source=rgb_or_thermal, classes=list(classes), conf=confidence, verbose=False,
    )[0]
    if result.boxes is None:
        return []
    boxes = result.boxes
    return list(zip(
        boxes.xyxyn.detach().cpu().tolist(),
        boxes.conf.detach().cpu().tolist(),
        boxes.cls.int().detach().cpu().tolist(),
    ))


def analyze(video, weights, modality="rgb", sample_seconds=1.0, max_frames=300,
            min_confidence=0.35, assessment_weights=None):
    """Use only local, prerecorded video and explicitly supplied model files."""
    source = local_file(video, VIDEO_SUFFIXES)
    model_path = local_file(weights, {".pt"})
    damage_path = local_file(assessment_weights, {".pt"}) if assessment_weights else None
    if not math.isfinite(sample_seconds) or sample_seconds <= 0 or not 1 <= max_frames <= 10000:
        raise ValueError("Sample interval must be positive and frame limit must be 1 to 10000")
    if modality not in {"rgb", "thermal"} or not 0 < min_confidence < 1:
        raise ValueError("Invalid modality or confidence threshold")

    os.environ["YOLO_OFFLINE"] = "true"
    os.environ["YOLO_AUTOINSTALL"] = "false"
    try:
        import cv2
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Install vision/requirements.txt in the vision environment") from exc

    people = YOLO(str(model_path), task="detect")
    people_classes = class_ids(people, {"person"})
    if not people_classes:
        raise ValueError("Person model must declare a 'person' class")
    hazards = YOLO(str(damage_path), task="detect") if damage_path else None
    hazard_classes = class_ids(hazards, DAMAGE_LABELS) if hazards is not None else {}
    if hazards is not None and not hazard_classes:
        raise ValueError("Assessment model must declare at least one supported damage class")

    report = report_header("prerecorded", source.name, modality)
    report["source"]["person_model"] = model_path.name
    report["source"]["assessment_model"] = damage_path.name if damage_path else None
    report["source"]["confidence_threshold"] = min_confidence
    capture = cv2.VideoCapture(str(source))
    try:
        if not capture.isOpened():
            raise ValueError("OpenCV could not open this video")
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("Replay requires a video with a known frame rate")
        interval = max(1, round(fps * sample_seconds))
        frame_index = 0
        while len(report["frames"]) < max_frames and capture.grab():
            if frame_index % interval == 0:
                ok, image = capture.retrieve()
                if not ok or image is None:
                    raise ValueError(f"Cannot decode frame {frame_index}")
                detections = infer(people, image, people_classes, min_confidence)
                observations = []
                if hazards is not None:
                    for box, score, label in infer(hazards, image, hazard_classes, min_confidence):
                        observations.append({"label": hazard_classes[label], "bbox": box, "confidence": score})
                report["frames"].append({
                    "frame_index": frame_index,
                    "time_s": round(frame_index / fps, 6),
                    "candidates": [
                        candidate(frame_index, i, box, score, "yolo_local_weights")
                        for i, (box, score, _) in enumerate(detections)
                    ],
                    "assessment": {
                        "provenance": "custom_yolo_local_weights" if hazards is not None else "unassessed",
                        "observations": observations,
                        "review_status": "pending",
                    },
                })
            frame_index += 1
    finally:
        capture.release()
    if not report["frames"]:
        raise ValueError("No decodable frames in the recording")
    return report


def save_report(report, destination):
    target = Path(destination).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(report, output, indent=2, allow_nan=False)
            output.write("\n")
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="command", required=True)
    fixture = modes.add_parser("fixture", help="Read the synthetic replay annotations")
    fixture.add_argument("--manifest", type=Path, default=MANIFEST)
    recorded = modes.add_parser("analyze", help="Run YOLO on a local recording")
    recorded.add_argument("--video", type=Path, required=True)
    recorded.add_argument("--weights", type=Path, required=True)
    recorded.add_argument("--modality", choices=("rgb", "thermal"), default="rgb")
    recorded.add_argument("--assessment-weights", type=Path)
    recorded.add_argument("--sample-seconds", type=float, default=1.0)
    recorded.add_argument("--max-frames", type=int, default=300)
    recorded.add_argument("--min-confidence", type=float, default=0.35)
    for mode in (fixture, recorded):
        mode.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "fixture":
            result = fixture_report(args.manifest)
            inputs = [args.manifest]
        else:
            result = analyze(args.video, args.weights, args.modality, args.sample_seconds,
                             args.max_frames, args.min_confidence, args.assessment_weights)
            inputs = [p for p in (args.video, args.weights, args.assessment_weights) if p]
        if any(path.resolve() == args.output.resolve() for path in inputs):
            raise ValueError("Choose an output path separate from the input files")
        save_report(result, args.output)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        parser.exit(2, f"Vision analysis failed: {exc}\n")
    print(f"Saved {len(result['frames'])} frames to {args.output}")


if __name__ == "__main__":
    main()
