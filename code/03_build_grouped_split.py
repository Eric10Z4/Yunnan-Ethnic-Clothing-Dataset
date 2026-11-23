#!/usr/bin/env python3
"""New group-aware split planning, or exact replay of a frozen manifest.

This implementation was added after publication. It is not evidence that the
published dataset was produced by this algorithm. No image is copied or moved.
"""

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import csv
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import urlsplit, urlunsplit
import html


SPLITS = ("train", "val", "test")
METADATA_FIELDS = (
    "image_id", "path", "ethnicity", "garment_type", "split", "source_url",
    "publisher", "collected_at", "license", "processing", "source_page_url",
    "group_id", "source_path",
)


class PlanError(ValueError):
    pass


def text(value, field, required=False):
    if value is None or value == "":
        if required:
            raise PlanError("Missing " + field)
        return ""
    if not isinstance(value, str) or not value.strip():
        raise PlanError(field + " must be a nonempty string")
    if value != value.strip() or any(ord(c) < 32 for c in value):
        raise PlanError(field + " contains surrounding whitespace or control characters")
    return value


def page_key(value):
    """Conservative URL equality: retain path/query, drop only the fragment."""
    if not value:
        return ""
    value = html.unescape(value)
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            raise ValueError("not an HTTP(S) source page")
        if parsed.username or parsed.password:
            raise ValueError("credentials are not allowed in source pages")
        port = parsed.port
        host = parsed.hostname.lower()
        if ":" in host:
            host = "[" + host + "]"
        if port and not ((parsed.scheme.lower() == "https" and port == 443)
                         or (parsed.scheme.lower() == "http" and port == 80)):
            host += ":" + str(port)
        return urlunsplit((parsed.scheme.lower(), host, parsed.path or "/", parsed.query, ""))
    except ValueError as exc:
        raise PlanError("Invalid source_page_url: " + str(exc)) from exc


def read_records(path):
    data = path.read_bytes()
    source = data.decode("utf-8-sig")
    if path.suffix.lower() == ".csv":
        records = list(csv.DictReader(io.StringIO(source)))
    elif path.suffix.lower() == ".jsonl":
        records = [json.loads(line) for line in source.splitlines() if line.strip()]
    else:
        records = json.loads(source)
    if not isinstance(records, list) or not records:
        raise PlanError("Input must contain a nonempty record list")
    if not all(isinstance(row, dict) for row in records):
        raise PlanError("Every record must be an object")
    return records, data


def prepare(records, input_base, compute_sha256=False, frozen=False):
    prepared = []
    seen = set()
    for original in records:
        row = deepcopy(original)
        image_id = text(row.get("image_id"), "image_id", True)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", image_id):
            raise PlanError("image_id must be a safe filename identifier")
        if image_id in seen:
            raise PlanError("Duplicate image_id: " + image_id)
        seen.add(image_id)
        ethnicity = text(row.get("ethnicity"), "ethnicity", True)
        meta = row.get("meta", {})
        if not isinstance(meta, dict):
            raise PlanError("meta must be an object")
        top_page = text(row.get("source_page_url"), "source_page_url")
        nested_page = text(meta.get("source_page_url"), "meta.source_page_url")
        if top_page and nested_page and page_key(top_page) != page_key(nested_page):
            raise PlanError("Conflicting source pages on " + image_id)
        page = top_page or nested_page
        canonical_page = page_key(page)
        shoot = text(row.get("shoot_group_id"), "shoot_group_id")
        hashes = [text(row.get(key), key).lower() for key in
                  ("sha256", "image_sha256", "content_sha256") if row.get(key) not in (None, "")]
        if any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes):
            raise PlanError("SHA256 must contain 64 hexadecimal characters on " + image_id)
        if len(set(hashes)) > 1:
            raise PlanError("Conflicting SHA256 values on " + image_id)
        sha = hashes[0] if hashes else ""
        source_path = next((text(value, "source_path") for value in
                            (row.get("source_path"), row.get("raw_path"), row.get("path"), meta.get("local_path"))
                            if value not in (None, "")), "")
        if not frozen and not source_path:
            raise PlanError("A source_path, raw_path, or path is required on " + image_id)
        if compute_sha256:
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", source_path):
                raise PlanError("--compute-sha256 only reads local source files")
            source = Path(source_path)
            if not source.is_absolute():
                source = input_base / source
            digest = hashlib.sha256()
            with source.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            computed = digest.hexdigest()
            if sha and computed != sha:
                raise PlanError("Provided SHA256 does not match source file on " + image_id)
            sha = computed
        phash = text(row.get("phash"), "phash").lower()
        if phash and not re.fullmatch(r"[0-9a-f]{16}", phash):
            raise PlanError("phash must contain exactly 16 hexadecimal characters")
        if frozen:
            group = text(row.get("group_id"), "group_id", True)
            split = text(row.get("split"), "split", True)
            path = text(row.get("path"), "path", True)
            parts = PurePosixPath(path).parts
            if (split not in SPLITS or "\\" in path or len(parts) != 3
                    or parts[0] != "images" or parts[1] != split
                    or PurePosixPath(path).stem != image_id):
                raise PlanError("Frozen path/split/image_id mismatch on " + image_id)
        prepared.append({"record": row, "id": image_id, "ethnicity": ethnicity,
                         "page": canonical_page, "source_page": page, "shoot": shoot,
                         "sha": sha, "phash": int(phash, 16) if phash else None,
                         "source_path": source_path})
    # Only exact content hashes imply a label contradiction. A page may validly
    # discuss multiple ethnic groups; a photo session may also contain them.
    hash_labels = defaultdict(set)
    for row in prepared:
        if row["sha"]:
            hash_labels[row["sha"]].add(row["ethnicity"])
    if any(len(labels) > 1 for labels in hash_labels.values()):
        raise PlanError("The same SHA256 has conflicting ethnicity labels; resolve it before planning")
    return prepared


class UnionFind:
    def __init__(self, size):
        self.parent = list(range(size))

    def find(self, item):
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left, right):
        left, right = self.find(left), self.find(right)
        if left != right:
            self.parent[right] = left


def form_groups(rows, phash_threshold=None):
    union = UnionFind(len(rows))
    for key in ("page", "shoot", "sha"):
        first = {}
        for index, row in enumerate(rows):
            value = row[key]
            if not value:
                continue
            if value in first:
                union.union(first[value], index)
            else:
                first[value] = index
    if phash_threshold is not None:
        available = [(index, row["phash"]) for index, row in enumerate(rows)
                     if row["phash"] is not None]
        for pos, (left, a) in enumerate(available):
            for right, b in available[pos + 1:]:
                if (a ^ b).bit_count() <= phash_threshold:
                    union.union(left, right)
    grouped = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[union.find(index)].append(row)
    groups = []
    for members in grouped.values():
        members.sort(key=lambda row: row["id"])
        ids = [row["id"] for row in members]
        identity = hashlib.sha256(json.dumps(ids, ensure_ascii=False).encode("utf-8")).hexdigest()
        groups.append({"id": "build-" + identity, "members": members,
                       "counts": Counter(row["ethnicity"] for row in members), "size": len(members)})
    return sorted(groups, key=lambda group: group["id"])


def stable_tie(seed, *values):
    value = json.dumps([seed] + list(values), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def allocate(groups, ratios, seed):
    """Deterministic grouped stratification using full per-group class vectors.

    Minimize class-normalized squared error plus 0.25 total-size error. Groups
    remain indivisible; exact proportions are not guaranteed. A deterministic
    single-group improvement pass corrects avoidable greedy imbalance.
    """
    totals = sum((group["counts"] for group in groups), Counter())
    total = sum(totals.values())
    counts = {split: Counter() for split in SPLITS}
    sizes = Counter()

    def change_cost(group, split, direction):
        ratio = ratios[SPLITS.index(split)]
        before = sizes[split] - ratio * total
        after = before + direction * group["size"]
        cost = 0.25 * (after * after - before * before) / (total * total)
        for label, amount in group["counts"].items():
            target = ratio * totals[label]
            before = counts[split][label] - target
            after = before + direction * amount
            cost += (after * after - before * before) / (totals[label] ** 2)
        return cost

    def apply(group, split, direction):
        sizes[split] += direction * group["size"]
        for label, amount in group["counts"].items():
            counts[split][label] += direction * amount

    order = sorted(groups, key=lambda group: (-group["size"], stable_tie(seed, group["id"])))
    assigned = {}
    for group in order:
        split = min(SPLITS, key=lambda s: (change_cost(group, s, 1), stable_tie(seed, group["id"], s)))
        assigned[group["id"]] = split
        apply(group, split, 1)
    for _ in range(20):
        improved = False
        for group in order:
            current = assigned[group["id"]]
            options = [(change_cost(group, current, -1) + change_cost(group, split, 1),
                        stable_tie(seed, group["id"], split), split)
                       for split in SPLITS if split != current]
            delta, _, target = min(options)
            if delta < -1e-12:
                apply(group, current, -1)
                apply(group, target, 1)
                assigned[group["id"]] = target
                improved = True
        if not improved:
            break
    return assigned


def summarize(mapping, mode, **extra):
    by_class = defaultdict(Counter)
    splits = Counter()
    for row in mapping:
        splits[row["split"]] += 1
        by_class[row["ethnicity"]][row["split"]] += 1
    return {"mode": mode, "implementation_origin": "post-publication addition; not historical execution evidence",
            "records": len(mapping), "groups": len({row["group_id"] for row in mapping}),
            "split_counts": {split: splits[split] for split in SPLITS},
            "class_split_counts": {key: {s: by_class[key][s] for s in SPLITS} for key in sorted(by_class)},
            "images_copied_or_moved": 0, **extra}


def build_plan(rows, ratios, seed, phash_threshold=None, allow_ungrouped=False):
    ungrouped = [row["id"] for row in rows
                 if not (row["page"] or row["shoot"] or row["sha"]
                         or (phash_threshold is not None and row["phash"] is not None))]
    if ungrouped and not allow_ungrouped:
        raise PlanError("Candidates lack active grouping evidence: " + ", ".join(ungrouped)
                        + "; supply evidence or explicitly use --allow-ungrouped")
    groups = form_groups(rows, phash_threshold)
    assigned = allocate(groups, ratios, seed)
    mapping = []
    for group in groups:
        split = assigned[group["id"]]
        for item in group["members"]:
            row = deepcopy(item["record"])
            # Avoid retaining an old absolute production destination in a new plan.
            row.pop("local_dest", None)
            filename = row.get("orig_filename") or item["source_path"]
            suffix = PurePosixPath(str(filename).replace("\\", "/")).suffix.lower()
            if suffix not in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"):
                suffix = ".jpg"
            row.update({"group_id": group["id"], "split": split,
                        "path": "images/" + split + "/" + item["id"] + suffix,
                        "source_path": item["source_path"]})
            meta = row.setdefault("meta", {})
            if item["source_page"]:
                meta["source_page_url"] = item["source_page"]
            for key in ("image_url", "publisher", "collected_at", "license"):
                if key in row and key not in meta:
                    meta[key] = row[key]
            if item["sha"]:
                row["sha256"] = item["sha"]
            mapping.append(row)
    mapping.sort(key=lambda row: row["image_id"])
    report = summarize(mapping, "new_build", seed=seed, target_ratios=dict(zip(SPLITS, ratios)),
                       phash_threshold=phash_threshold, missing_source_page_ids=[r["id"] for r in rows if not r["page"]],
                       exact_hash_evidence_records=sum(bool(r["sha"]) for r in rows),
                       phash_evidence_records=sum(r["phash"] is not None for r in rows),
                       allow_ungrouped=allow_ungrouped, ungrouped_image_ids=ungrouped,
                       exact_ratios_guaranteed=False, image_materialization_required=True,
                       group_rule="global source page OR shoot_group_id OR exact SHA256 OR optional pHash edge; transitive union")
    return mapping, report


def validate_frozen(rows):
    for key in ("group_id",):
        splits = defaultdict(set)
        for item in rows:
            splits[item["record"][key]].add(item["record"]["split"])
        if any(len(value) > 1 for value in splits.values()):
            raise PlanError("Frozen group_id crosses splits")
    for key in ("page", "shoot", "sha"):
        splits = defaultdict(set)
        for item in rows:
            if item[key]:
                splits[item[key]].add(item["record"]["split"])
        if any(len(value) > 1 for value in splits.values()):
            raise PlanError("Frozen " + key + " relationship crosses splits")
    mapping = [item["record"] for item in rows]
    return mapping, summarize(mapping, "frozen_replay", repartitioned=False,
                              frozen_group_ids_preserved=True, image_materialization_required=True,
                              phash_regrouping_performed=False)


def metadata_row(row):
    meta = row.get("meta", {})
    result = {key: row.get(key) or meta.get(key, "") for key in METADATA_FIELDS}
    result["source_url"] = row.get("source_url") or meta.get("image_url", "")
    result["source_page_url"] = row.get("source_page_url") or meta.get("source_page_url", "")
    # Annotation-derived garment type is not invented by this grouping tool.
    result["garment_type"] = row.get("garment_type") or meta.get("garment_type") or "unknown"
    return result


def csv_bytes(rows, fields):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def safe_output(path):
    requested = path.expanduser()
    path = requested.resolve()
    if any(part.lower() in ("dataset", ".git") for part in requested.parts + path.parts):
        raise PlanError("Output must not be inside any dataset/ or .git/ directory")
    if requested.is_symlink() or requested.exists() or path.exists():
        raise PlanError("Output directory must not already exist (even if empty)")
    if not path.parent.is_dir():
        raise PlanError("Output parent directory must already exist")
    return path


def write_bundle(output, mapping, report, frozen_bytes=None):
    output = safe_output(output)
    encoded_mapping = frozen_bytes if frozen_bytes is not None else (
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    materialization = [{"image_id": row["image_id"], "source_path": row.get("source_path") or row.get("raw_path", ""),
                        "destination_path": row["path"], "group_id": row["group_id"], "split": row["split"]}
                       for row in mapping]
    bundle = {
        "annotations/dataset_manifest_mapped.json": encoded_mapping,
        "metadata_plan.csv": csv_bytes([metadata_row(row) for row in mapping], METADATA_FIELDS),
        "image_materialization_plan.csv": csv_bytes(materialization, ("image_id", "source_path", "destination_path", "group_id", "split")),
        "grouping_report.json": (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    }
    output.mkdir(exist_ok=False)
    (output / "annotations").mkdir()
    for name, data in bundle.items():
        with (output / name).open("xb") as handle:
            handle.write(data)


def parse_ratios(value):
    try:
        ratios = tuple(float(x) for x in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Ratios must be three comma-separated numbers") from exc
    if len(ratios) != 3 or any(not math.isfinite(x) or x <= 0 for x in ratios) or abs(sum(ratios) - 1) > 1e-9:
        raise argparse.ArgumentTypeError("Ratios must be three positive finite values summing to 1")
    return ratios


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Build NEW grouping and split plans; not a historical reconstruction")
    build.add_argument("--candidates", type=Path, required=True)
    build.add_argument("--seed", type=int, default=2026)
    build.add_argument("--ratios", type=parse_ratios, default=(0.7, 0.15, 0.15))
    build.add_argument("--phash-threshold", type=int)
    build.add_argument("--compute-sha256", action="store_true", help="Read local source files to compute exact hashes")
    build.add_argument("--allow-ungrouped", action="store_true", help="Explicitly permit candidates with no active grouping evidence")
    build.add_argument("--output-dir", type=Path)
    build.add_argument("--dry-run", action="store_true")
    replay = sub.add_parser("replay", help="Validate and optionally copy frozen mapping bytes without repartitioning")
    replay.add_argument("--manifest", type=Path, required=True)
    replay.add_argument("--output-dir", type=Path)
    replay.add_argument("--dry-run", action="store_true")
    replay.add_argument("--image-root", type=Path, help="Optionally verify frozen image paths under this existing root; read-only")
    validate = sub.add_parser("validate", help="Read-only validation of a frozen manifest")
    validate.add_argument("--manifest", type=Path, required=True)
    validate.add_argument("--image-root", type=Path, help="Optionally verify frozen image paths under this existing root; read-only")
    args = parser.parse_args(argv)
    try:
        output = getattr(args, "output_dir", None)
        if output is not None:
            safe_output(output)
        if args.command == "build":
            if args.phash_threshold is not None and not 0 <= args.phash_threshold <= 64:
                raise PlanError("pHash threshold must be between 0 and 64")
            records, raw = read_records(args.candidates)
            rows = prepare(records, args.candidates.resolve().parent, args.compute_sha256)
            mapping, report = build_plan(rows, args.ratios, args.seed, args.phash_threshold, args.allow_ungrouped)
            frozen = None
        else:
            records, raw = read_records(args.manifest)
            if args.manifest.suffix.lower() != ".json":
                raise PlanError("Frozen replay/validation requires a JSON array manifest")
            rows = prepare(records, args.manifest.resolve().parent, frozen=True)
            mapping, report = validate_frozen(rows)
            report["physical_image_references_checked"] = 0
            if args.image_root is not None:
                image_root = args.image_root.resolve()
                if not image_root.is_dir():
                    raise PlanError("--image-root must be an existing directory")
                for row in mapping:
                    image_path = (image_root / row["path"]).resolve()
                    if not image_path.is_relative_to(image_root) or not image_path.is_file():
                        raise PlanError("Frozen image reference not found safely under --image-root on " + row["image_id"])
                report["physical_image_references_checked"] = len(mapping)
                report["image_materialization_required"] = False
            frozen = raw
        report["input_sha256"] = hashlib.sha256(raw).hexdigest()
        report["dry_run"] = output is None or getattr(args, "dry_run", False)
        if not report["dry_run"]:
            write_bundle(output, mapping, report, frozen)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (PlanError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
