import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from .pipeline import candidate, class_ids, fixture_report, save_report
from .scenario import assess_exercise_raster


class PipelineTest(unittest.TestCase):
    def test_synthetic_annotation_preserves_box_and_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "camera.json"
            box = [0.1, 0.3, 0.2, 0.8]
            path.write_text(json.dumps({
                "source": "synthetic",
                "frames": [{"frame": 2, "time_s": 1, "boxes": [
                    {"label": "person", "xyxy": box}, {"label": "tree", "xyxy": box},
                ]}],
            }))
            report = fixture_report(path)
            found, = report["frames"][0]["candidates"]
            self.assertEqual(found["bbox"], box)
            self.assertIsNone(found["confidence"])
            self.assertEqual(found["review_status"], "pending")
            self.assertEqual(found["provenance"], "synthetic_annotation")
            output = Path(temporary) / "report.json"
            save_report(report, output)
            self.assertEqual(json.loads(output.read_text()), report)

    def test_input_validation(self):
        for box in ([0, 0, 0, 1], [0, 0, float("nan"), 1], [1, 1]):
            with self.subTest(box=box), self.assertRaises(ValueError):
                candidate(0, 0, box, 0.8, "yolo_local_weights")
        detected = candidate(0, 0, [-0.01, 0, 1, 0.7], 0.8, "yolo_local_weights")
        self.assertEqual(detected["bbox"], [0, 0, 1, 0.7])
        self.assertEqual(detected["confidence"], 0.8)

    def test_model_class_lookup_uses_label_names(self):
        model = SimpleNamespace(names={0: "vehicle", 2: "person", 7: "Blocked Road"})
        self.assertEqual(class_ids(model, {"person"}), {2: "person"})
        self.assertEqual(class_ids(model, {"blocked_road"}), {7: "blocked_road"})

    def test_scenario_assessment_uses_separate_mask_provenance(self):
        assessment = assess_exercise_raster()
        self.assertEqual(assessment["damaged_buildings"], 1)
        self.assertEqual(assessment["reference_buildings"], 3)
        self.assertGreater(assessment["blocked_road_fraction"], 0.2)
        self.assertGreater(assessment["flooded_area_fraction"], 0)
        self.assertEqual(assessment["provenance"], "synthetic_scenario_masks")
        self.assertEqual(assessment["candidate_sites_for_review"], ["west assembly ground"])


if __name__ == "__main__":
    unittest.main()
