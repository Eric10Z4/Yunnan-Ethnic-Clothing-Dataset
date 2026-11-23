"""Build a public, read-only review index from the five published dataset tracks.

This does not call models, download images, edit annotations, or change splits.
Only the allowlisted public fields below are written to audit_tool_v3/data.js.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qsl, urlsplit

INPUTS = {
    "official": "dataset/annotations/captions.jsonl",
    "extended": "dataset/annotations/extended_fine_grained_attributes.jsonl",
    "merged": "dataset/annotations/captions_merged_full.jsonl",
    "metadata": "dataset/metadata.csv",
    "manifest": "dataset/annotations/dataset_manifest_mapped.json",
}
EXCLUDED_IDS = {"0803", "1166"}
PUBLIC_ITEM_KEYS = {"item_id", "image_id", "path", "ethnicity", "split", "caption", "source_page_url"}
SENSITIVE_QUERY = re.compile(r"token|password|secret|signature|credential|api.?key|access.?key|auth|session|jwt|signed", re.I)


def unique_rows(rows: list[dict], label: str) -> dict[str, dict]:
    indexed = {}
    for row in rows:
        if not isinstance(row, dict) or not re.fullmatch(r"\d{4}", str(row.get("image_id", ""))):
            raise ValueError(f"{label}: every row needs a four-digit string image_id")
        image_id = str(row["image_id"])
        if image_id in indexed:
            raise ValueError(f"{label}: duplicate image_id {image_id}")
        indexed[image_id] = row
    return indexed


def load_tracks(repo_root: Path) -> dict[str, dict[str, dict]]:
    tracks = {}
    for label, relative in INPUTS.items():
        path = repo_root / relative
        if path.suffix == ".csv":
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
        elif path.suffix == ".jsonl":
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        else:
            rows = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(rows, list):
            raise ValueError(f"{label}: expected an array of records")
        tracks[label] = unique_rows(rows, label)
    return tracks


def public_source_url(value: object) -> str:
    """Keep public HTTP(S) page links; omit credentials or signed/token URLs."""
    if not isinstance(value, str) or not value.strip():
        return ""
    value = value.strip()
    try:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            return ""
        if any(SENSITIVE_QUERY.search(key) for key, _ in parse_qsl(parts.query, keep_blank_values=True)):
            return ""
        return value
    except ValueError:
        return ""


def image_path(value: object, image_id: str, split: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{image_id}: missing public image path")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    expected = f"images/{split}/{image_id}.jpg"
    if path.is_absolute() or ".." in path.parts or normalized != expected:
        raise ValueError(f"{image_id}: expected path {expected}, got {normalized!r}")
    return normalized


def build_payload(repo_root: Path, expected_count: int = 1512) -> tuple[dict, list[dict]]:
    tracks = load_tracks(repo_root)
    ids = set(tracks["official"])
    if len(ids) != expected_count:
        raise ValueError(f"Expected {expected_count} official records, found {len(ids)}")
    if ids & EXCLUDED_IDS:
        raise ValueError("Excluded samples 0803 / 1166 must not be in the review entry")
    for label, records in tracks.items():
        if set(records) != ids:
            raise ValueError(f"{label}: image_id set differs from the official track")

    items = []
    for image_id in sorted(ids):
        official = tracks["official"][image_id]
        meta = tracks["metadata"][image_id]
        manifest = tracks["manifest"][image_id]
        split = meta.get("split")
        if split not in {"train", "val", "test"} or manifest.get("split") != split:
            raise ValueError(f"{image_id}: inconsistent split")
        path = image_path(official.get("path"), image_id, split)
        ethnicity = official.get("ethnicity")
        if not isinstance(ethnicity, str) or not ethnicity:
            raise ValueError(f"{image_id}: missing ethnicity")
        for label, records in tracks.items():
            record = records[image_id]
            if record.get("ethnicity") != ethnicity or image_path(record.get("path"), image_id, split) != path:
                raise ValueError(f"{image_id}: inconsistent path / ethnicity in {label}")
        caption = official.get("caption")
        if not isinstance(caption, str) or not caption.strip():
            raise ValueError(f"{image_id}: missing official caption")
        if tracks["merged"][image_id].get("caption") != caption:
            raise ValueError(f"{image_id}: merged caption differs from official caption")
        # Never serialize a raw row: manifest contains local paths and nested logs.
        item = {
            "item_id": image_id,
            "image_id": image_id,
            "path": path,
            "ethnicity": ethnicity,
            "split": split,
            "caption": caption,
            "source_page_url": public_source_url(meta.get("source_page_url")),
        }
        assert set(item) == PUBLIC_ITEM_KEYS
        items.append(item)

    digests = {label: hashlib.sha256((repo_root / relative).read_bytes()).hexdigest() for label, relative in INPUTS.items()}
    fingerprint = hashlib.sha256(json.dumps(digests, sort_keys=True).encode("utf-8")).hexdigest()
    info = {
        "schema_version": 1,
        "record_count": len(items),
        "fingerprint": fingerprint,
        "source_kind": "published-five-track",
        "images_included": False,
    }
    return info, items


def write_index(repo_root: Path, output: Path, expected_count: int = 1512) -> dict:
    dataset = (repo_root / "dataset").resolve()
    output = output.resolve()
    if output == dataset or dataset in output.parents:
        raise ValueError("Output must be outside dataset/; dataset files are read-only")
    info, items = build_payload(repo_root, expected_count)
    # JSON string literals are safe in this external JS file; no executable data.
    content = (
        "// Generated by code/build_review_tool_data.py; public review index only.\n"
        "window.AUDIT_DATASET = " + json.dumps(info, ensure_ascii=False, sort_keys=True) + ";\n"
        "window.AUDIT_ITEMS = [\n" + ",\n".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) for item in items) + "\n];\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="Default: <repo-root>/audit_tool_v3/data.js")
    parser.add_argument("--expected-count", type=int, default=1512, help="Use another count only for an explicit synthetic fixture")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    info = write_index(root, args.output or root / "audit_tool_v3/data.js", args.expected_count)
    print(f"Built {info['record_count']} public review entries; fingerprint {info['fingerprint']}")


if __name__ == "__main__":
    main()
