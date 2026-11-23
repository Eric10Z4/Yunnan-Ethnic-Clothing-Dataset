"""Offline behavioral checks using only temporary synthetic candidate records."""

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("03_build_grouped_split.py")


class GroupedSplitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="grouped-split-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def row(self, identifier, ethnicity="Yi", **fields):
        return {"image_id": identifier, "ethnicity": ethnicity,
                "source_path": "synthetic/" + identifier + ".jpg",
                "source_page_url": "https://example.org/item/" + identifier, **fields}

    def save(self, rows, name="input.json"):
        path = self.root / name
        if path.suffix == ".csv":
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        elif path.suffix == ".jsonl":
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        else:
            path.write_text(json.dumps(rows), encoding="utf-8")
        return path

    def run_cli(self, *args, ok=True):
        completed = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                                   capture_output=True, text=True, encoding="utf-8")
        if ok:
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return json.loads(completed.stdout)
        self.assertNotEqual(completed.returncode, 0)
        self.assertTrue(completed.stderr.strip())
        return completed

    def build(self, rows, directory="plan", *extra):
        source = self.save(rows)
        output = self.root / directory
        report = self.run_cli("build", "--candidates", source, "--output-dir", output, *extra)
        mapping = json.loads((output / "annotations/dataset_manifest_mapped.json").read_text(encoding="utf-8"))
        return report, mapping, output

    def test_transitive_global_page_session_and_hash_links(self):
        rows = [
            self.row("0001", source_page_url="https://EXAMPLE.org:443/shared#one"),
            self.row("0002", "Miao", source_page_url="https://example.org/shared#two", shoot_group_id="session-A"),
            self.row("0003", shoot_group_id="session-A", sha256="a" * 64),
            self.row("0004", sha256="a" * 64),
            self.row("0005"), self.row("0006"),
        ]
        report, mapping, output = self.build(rows)
        by_id = {row["image_id"]: row for row in mapping}
        self.assertEqual(len({by_id[key]["group_id"] for key in ["0001", "0002", "0003", "0004"]}), 1)
        self.assertEqual(len({by_id[key]["split"] for key in ["0001", "0002", "0003", "0004"]}), 1)
        self.assertEqual(report["groups"], 3)
        self.assertEqual(by_id["0002"]["ethnicity"], "Miao")
        self.assertEqual(by_id["0001"]["source_path"], rows[0]["source_path"])
        self.assertFalse((output / "images").exists())
        self.assertEqual({p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()},
                         {"annotations/dataset_manifest_mapped.json", "metadata_plan.csv",
                          "image_materialization_plan.csv", "grouping_report.json"})

    def test_same_exact_hash_conflicting_ethnicity_is_rejected(self):
        source = self.save([self.row("1", sha256="a" * 64), self.row("2", "Miao", sha256="a" * 64)])
        out = self.root / "must-not-exist"
        result = self.run_cli("build", "--candidates", source, "--output-dir", out, ok=False)
        self.assertIn("conflicting ethnicity", result.stderr)
        self.assertFalse(out.exists())

    def test_missing_grouping_evidence_requires_explicit_opt_in(self):
        source = self.save([self.row("1", source_page_url="")])
        self.run_cli("build", "--candidates", source, ok=False)
        report = self.run_cli("build", "--candidates", source, "--allow-ungrouped")
        self.assertEqual(report["ungrouped_image_ids"], ["1"])
        source = self.save([self.row("2", source_page_url="", phash="0123456789abcdef")])
        self.run_cli("build", "--candidates", source, ok=False)
        report = self.run_cli("build", "--candidates", source, "--phash-threshold", 0)
        self.assertEqual(report["ungrouped_image_ids"], [])

    def test_metadata_retains_nested_garment_type_and_publisher(self):
        _, _, output = self.build([self.row("1", meta={"garment_type": "accessories", "publisher": "Synthetic museum"})])
        with (output / "metadata_plan.csv").open(encoding="utf-8", newline="") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["garment_type"], "accessories")
        self.assertEqual(row["publisher"], "Synthetic museum")

    def test_phash_threshold_is_optional_inclusive_and_transitive(self):
        rows = [self.row("1", phash="0000000000000000"),
                self.row("2", "Miao", phash="000000000000000f"),
                self.row("3", phash="00000000000000ff")]
        _, plain, _ = self.build(rows, "plain")
        self.assertEqual(len({x["group_id"] for x in plain}), 3)
        _, grouped, _ = self.build(rows, "grouped", "--phash-threshold", 4)
        self.assertEqual(len({x["group_id"] for x in grouped}), 1)
        _, separated, _ = self.build(rows, "separated", "--phash-threshold", 3)
        self.assertEqual(len({x["group_id"] for x in separated}), 3)

    def test_seed_and_order_reproducibility_and_class_balance(self):
        rows = [self.row("%s%03d" % (label, number), label) for label in ["Yi", "Miao", "Dai"]
                for number in range(20)]
        report, first, _ = self.build(rows, "first", "--seed", 71)
        _, second, _ = self.build(list(reversed(rows)), "second", "--seed", 71)
        self.assertEqual(first, second)
        for counts in report["class_split_counts"].values():
            self.assertLessEqual(abs(counts["train"] - 14), 1)
            self.assertLessEqual(abs(counts["val"] - 3), 1)
            self.assertLessEqual(abs(counts["test"] - 3), 1)
        self.assertEqual(sum(report["split_counts"].values()), 60)

    def test_large_group_is_not_cut_to_force_ratios(self):
        rows = [self.row(str(i), shoot_group_id="one-shoot") for i in range(15)]
        report, mapping, _ = self.build(rows)
        self.assertEqual(len({row["split"] for row in mapping}), 1)
        self.assertFalse(report["exact_ratios_guaranteed"])

    def test_default_dry_run_does_not_create_or_change_files(self):
        source = self.save([self.row("0007"), self.row("0042")])
        before = source.read_bytes()
        report = self.run_cli("build", "--candidates", source)
        self.assertTrue(report["dry_run"])
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [source.name])
        self.assertEqual(source.read_bytes(), before)
        out = self.root / "dry-plan"
        self.run_cli("build", "--candidates", source, "--output-dir", out, "--dry-run")
        self.assertFalse(out.exists())

    def test_csv_and_jsonl_keep_leading_zero_identifiers(self):
        for extension in ["csv", "jsonl"]:
            source = self.save([self.row("0007"), self.row("0042")], "input." + extension)
            out = self.root / ("plan-" + extension)
            self.run_cli("build", "--candidates", source, "--output-dir", out)
            mapping = json.loads((out / "annotations/dataset_manifest_mapped.json").read_text())
            self.assertEqual([x["image_id"] for x in mapping], ["0007", "0042"])

    def test_existing_output_and_dataset_destination_are_refused(self):
        source = self.save([self.row("1")])
        existing = self.root / "existing"
        existing.mkdir()
        self.run_cli("build", "--candidates", source, "--output-dir", existing, ok=False)
        self.assertEqual(list(existing.iterdir()), [])
        sentinel = existing / "keep.txt"
        sentinel.write_bytes(b"keep me")
        self.run_cli("build", "--candidates", source, "--output-dir", existing, ok=False)
        self.assertEqual(sentinel.read_bytes(), b"keep me")
        protected = self.root / "dataset"
        protected.mkdir()
        out = protected / "new-plan"
        self.run_cli("build", "--candidates", source, "--output-dir", out, ok=False)
        self.assertFalse(out.exists())

    def test_compute_hashes_reads_only_synthetic_sources(self):
        for name in ["a.jpg", "b.jpg"]:
            (self.root / name).write_bytes(b"synthetic same file bytes")
        rows = [self.row("1", source_path="a.jpg"), self.row("2", source_path="b.jpg")]
        _, mapping, _ = self.build(rows, "hashed", "--compute-sha256")
        self.assertEqual(mapping[0]["group_id"], mapping[1]["group_id"])
        self.assertEqual(mapping[0]["sha256"], hashlib.sha256(b"synthetic same file bytes").hexdigest())
        self.assertEqual((self.root / "a.jpg").read_bytes(), b"synthetic same file bytes")
        bad = self.save([self.row("3", source_path="a.jpg", sha256="0" * 64)])
        self.run_cli("build", "--candidates", bad, "--compute-sha256", ok=False)

    def frozen(self):
        return [{"image_id": "0900", "ethnicity": "Yi", "group_id": "published-z",
                 "split": "test", "path": "images/test/0900.jpg", "source_page_url": "https://example.org/z"},
                {"image_id": "0001", "ethnicity": "Miao", "group_id": "published-a",
                 "split": "train", "path": "images/train/0001.jpg", "source_page_url": "https://example.org/a"}]

    def test_frozen_replay_preserves_raw_bytes_ids_groups_and_order(self):
        source = self.root / "frozen.json"
        original = json.dumps(self.frozen(), indent=3).replace("\n", "\r\n").encode("utf-8")
        source.write_bytes(original)
        out = self.root / "replay"
        report = self.run_cli("replay", "--manifest", source, "--output-dir", out)
        self.assertEqual((out / "annotations/dataset_manifest_mapped.json").read_bytes(), original)
        self.assertFalse(report["repartitioned"])
        self.assertFalse(report["phash_regrouping_performed"])
        validated = self.run_cli("validate", "--manifest", source)
        self.assertTrue(validated["dry_run"])
        self.assertEqual(source.read_bytes(), original)

    def test_frozen_cross_split_group_and_page_are_rejected(self):
        rows = self.frozen()
        rows[1]["group_id"] = rows[0]["group_id"]
        source = self.save(rows)
        self.run_cli("replay", "--manifest", source, ok=False)
        rows = self.frozen()
        rows[1]["source_page_url"] = rows[0]["source_page_url"]
        source = self.save(rows)
        self.run_cli("validate", "--manifest", source, ok=False)

    def test_frozen_page_can_span_ethnicities_when_split_is_same(self):
        rows = self.frozen()
        rows[1].update(split="test", path="images/test/0001.jpg",
                       source_page_url=rows[0]["source_page_url"])
        report = self.run_cli("validate", "--manifest", self.save(rows))
        self.assertEqual(report["records"], 2)

    def test_frozen_optional_image_root_checks_only_explicit_references(self):
        source = self.save(self.frozen())
        image_root = self.root / "isolated-image-root"
        image_root.mkdir()
        self.run_cli("validate", "--manifest", source, "--image-root", image_root, ok=False)
        for row in self.frozen():
            target = image_root / row["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"synthetic image reference")
        report = self.run_cli("validate", "--manifest", source, "--image-root", image_root)
        self.assertEqual(report["physical_image_references_checked"], 2)
        self.assertFalse(report["image_materialization_required"])
        for row in self.frozen():
            self.assertEqual((image_root / row["path"]).read_bytes(), b"synthetic image reference")

    def test_malformed_identifiers_hashes_ratios_and_frozen_paths_rejected(self):
        for rows in [[self.row("1"), self.row("1")], [self.row("../1")],
                     [self.row("1", sha256="bad")], [self.row("1", phash="abc")]]:
            self.run_cli("build", "--candidates", self.save(rows), ok=False)
        source = self.save([self.row("1")])
        for ratios in ["0.7,0.15,0.14", "nan,0.1,0.9", "1,0,0"]:
            self.run_cli("build", "--candidates", source, "--ratios", ratios, ok=False)
        rows = self.frozen()
        rows[0]["path"] = "images/train/0900.jpg"
        self.run_cli("validate", "--manifest", self.save(rows), ok=False)


if __name__ == "__main__":
    unittest.main()
