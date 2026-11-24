# Offline vision and scene review

Run these commands from the project root. The synthetic exercise uses Python's standard library.

```sh
python -m vision.pipeline fixture --output exercise-report.json
python -m unittest vision.test_pipeline
```

The fixture command reads the person annotations for the bundled synthetic camera frames. Each frame has a source-relative timestamp, normalized bounding boxes, and a pending review status. A synthetic annotation has a null confidence. A YOLO prediction carries the score returned by the local model. The same person can appear in successive frames. Detection counts across frames cannot be interpreted as a survivor count.

## Analyze recorded footage

Use a Python environment compatible with the PyTorch build for your machine. Install the optional inference dependencies and supply a trusted, local Ultralytics detection checkpoint with a class named `person`.

```sh
python -m pip install -r vision/requirements.txt
python -m vision.pipeline analyze --video public/scene/camera.avi --weights models/person.pt --sample-seconds 0.5 --output replay-report.json
```

The CLI decodes the recording using OpenCV and applies YOLO to sampled frames. Sampling defaults to one frame per second, up to 300 analyzed frames. Use `--max-frames` and `--min-confidence` to adjust the run. Frame times are computed from the nominal recording frame rate. For variable-frame-rate footage, convert to a constant frame rate before using timestamps for review.

For a recorded thermal clip, pass `--modality thermal` and weights trained and evaluated for that sensor's imagery. The flag records provenance. It does not recolor the image or establish thermal detection accuracy. For either modality, file inputs and weights must already be on disk. Model checkpoints can execute code when loaded. Use weights from a trusted source.

Optional `--assessment-weights models/disaster.pt` accepts a separate, locally trained detector with any of the classes `flooded_area`, `blocked_road`, or `damaged_infrastructure`. Labels containing spaces are accepted. Reported observations include a bounding box and model score. Without that model the footage assessment is `unassessed`. No pretrained disaster or thermal checkpoint is included.

Ultralytics documents the normalized `xyxyn` coordinates, class IDs, and confidence scores used by this adapter. [Detection data reference](https://docs.ultralytics.com/tasks/detect/)

## Report contract

| Field | Meaning |
| --- | --- |
| `schema_version`, `mode` | Version 1, disaster simulation |
| `source.kind`, `source.modality` | Synthetic or prerecorded input, RGB or thermal |
| `created_at` | UTC report creation time |
| `frames[].frame_index`, `time_s` | Source frame number and seconds from recording start |
| `candidates[].bbox` | Left, top, right, bottom in [0, 1], origin at upper left |
| `candidates[].id` | Frame-local observation identifier scoped to this report |
| `candidates[].provenance` | `synthetic_annotation` or `yolo_local_weights` |
| `candidates[].review_status` | Pending until reviewed by the operator |
| `assessment.provenance` | `synthetic_scenario_masks`, `custom_yolo_local_weights`, or `unassessed` |

The fixture also evaluates a separate 96 × 56 exercise sector. Known road and building layers are intersected with synthetic water, debris, and structural-damage masks. The report includes affected area, obstructed road fraction, damaged building count and unobstructed candidate areas for operator review. Severity uses the largest of these three affected fractions, with exercise thresholds of 0.10 and 0.30. These masks represent the scenario sector and do not describe individual camera pixels. They are unsuitable for assessing an actual disaster or selecting real landing sites.

The pipeline emits image-space observations. Map positions in the simulation come from exercise locations supplied by the mission service. No camera-to-ground geolocation is performed.

## Visible SOS placard exercise

`python -m vision.sos` regenerates the separate exercise sign in `public/scene/sos.png` and inspects its decoded grayscale pixels. `vision.sos.inspect_placard()` samples 75 cell centers and reports the fraction agreeing with the fixed SOS pattern. A match of at least 0.96 produces a pending review alert. This is a fixed-size, fixed-position synthetic recognition exercise. General aerial sign detection, rotation, occlusion, and free-form lettering require separate development and evaluation. Run `python -m unittest vision.test_sos` for the bundled sign and blank-frame cases.
