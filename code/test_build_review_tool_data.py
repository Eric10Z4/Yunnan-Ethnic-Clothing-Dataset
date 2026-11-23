"""Synthetic fixtures only; never edits the published dataset."""
import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from build_review_tool_data import INPUTS, PUBLIC_ITEM_KEYS, build_payload, public_source_url, write_index


class ReviewIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="yecid_review_fixture_")
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.rows = [
            {"image_id": "1001", "path": "images/train/1001.jpg", "ethnicity": "Fixture", "split": "train", "caption": "Synthetic fixture, not a dataset annotation.", "source_page_url": "https://example.org/item/1"},
            {"image_id": "1002", "path": "images/test/1002.jpg", "ethnicity": "Fixture", "split": "test", "caption": "Another synthetic fixture.", "source_page_url": "https://example.org/item/2"},
        ]
        self.write_tracks()

    def write_tracks(self, overrides=None):
        overrides = overrides or {}
        for label, relative in INPUTS.items():
            rows = copy.deepcopy(overrides.get(label, self.rows))
            for row in rows:
                row.update({"raw_path": "C:/PRIVATE/DO_NOT_PUBLISH.jpg", "local_dest": "DO_NOT_PUBLISH", "vlm_reason": "DO_NOT_PUBLISH", "authorization": "SYNTHETIC_DO_NOT_PUBLISH"})
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".csv":
                with path.open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                    writer.writeheader(); writer.writerows(rows)
            elif path.suffix == ".jsonl":
                path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            else:
                path.write_text(json.dumps(rows), encoding="utf-8")

    def test_public_deterministic_output_and_read_only_inputs(self):
        before = {relative: (self.root / relative).read_bytes() for relative in INPUTS.values()}
        out = self.root / "audit_tool_v3/data.js"
        first = write_index(self.root, out, 2)
        content = out.read_bytes()
        self.assertEqual(first["record_count"], 2)
        self.assertNotIn(b"DO_NOT_PUBLISH", content)
        info, items = build_payload(self.root, 2)
        self.assertEqual(set(items[0]), PUBLIC_ITEM_KEYS)
        self.assertEqual(items[0]["path"], "images/train/1001.jpg")
        self.assertEqual(info, first)
        write_index(self.root, out, 2)
        self.assertEqual(content, out.read_bytes())
        self.assertEqual(before, {relative: (self.root / relative).read_bytes() for relative in INPUTS.values()})

    def test_cross_track_missing_id_is_rejected(self):
        self.write_tracks({"extended": self.rows[:1]})
        with self.assertRaisesRegex(ValueError, "image_id set"):
            build_payload(self.root, 2)

    def test_duplicate_id_is_rejected(self):
        self.write_tracks({"manifest": [self.rows[0], self.rows[0]]})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_payload(self.root, 2)

    def test_path_or_caption_mismatch_is_rejected(self):
        changed = copy.deepcopy(self.rows); changed[0]["path"] = "../outside.jpg"
        self.write_tracks({"metadata": changed})
        with self.assertRaisesRegex(ValueError, "expected path"):
            build_payload(self.root, 2)
        changed = copy.deepcopy(self.rows); changed[0]["caption"] = "Mismatch"
        self.write_tracks({"merged": changed})
        with self.assertRaisesRegex(ValueError, "merged caption"):
            build_payload(self.root, 2)

    def test_excluded_ids_and_wrong_count_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Expected 1512"):
            build_payload(self.root)
        self.rows[0].update(image_id="0803", path="images/train/0803.jpg")
        self.write_tracks()
        with self.assertRaisesRegex(ValueError, "Excluded"):
            build_payload(self.root, 2)

    def test_output_inside_dataset_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside dataset"):
            write_index(self.root, self.root / "dataset/generated.js", 2)

    def test_credential_or_signed_urls_are_omitted(self):
        for url in ["file:///private/picture.jpg", "https://user:pass@example.org/", "https://example.org/?access_token=synthetic", "https://example.org/?X-Amz-Signature=synthetic", "https://example.org/?sessionid=synthetic"]:
            self.assertEqual(public_source_url(url), "")
        self.assertEqual(public_source_url("https://example.org/item?id=2"), "https://example.org/item?id=2")


if __name__ == "__main__":
    unittest.main()
