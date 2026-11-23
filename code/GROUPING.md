# Group-aware split planning and frozen manifest replay

This entry point was added after the published dataset was assembled. It is a
new implementation, **not evidence of the algorithm or commands used in the
historical run**. It does not claim to recreate the published 1,142 groups or
their assignments. Published image IDs, groups, splits and images remain frozen.

The two workflows have different purposes:

| Command | Purpose | Changes grouping or splits? | Writes images? |
| --- | --- | --- | --- |
| `build` | Plan a **new** dataset from an eligible candidate list | Yes, in a new output plan only | Never |
| `validate` | Check a frozen published manifest | No | Never |
| `replay` | Validate and reproduce the frozen manifest bytes in a separate directory | No | Never |

The implementation and tests use only the Python standard library. The tests
create small synthetic fixtures in temporary directories. They do not load or
repartition the 1,512-image production dataset.

## New-build input

`build` accepts a JSON array, JSONL or CSV. IDs must be nonempty strings containing
letters, numbers, underscores or hyphens; leading zeros are preserved. CSV input
also preserves leading zeros. A minimal synthetic example is:

```json
[
  {
    "image_id": "0001",
    "ethnicity": "Yi",
    "source_path": "eligible/first.jpg",
    "source_page_url": "https://example.org/article/one",
    "shoot_group_id": "session-a"
  },
  {
    "image_id": "0002",
    "ethnicity": "Miao",
    "source_path": "eligible/second.jpg",
    "source_page_url": "https://example.org/article/one"
  }
]
```

Required fields are `image_id`, `ethnicity`, and a source image reference. The
source is taken from `source_path`, then `raw_path`, then the old `path`, then
`meta.local_path`. Explicit `source_path` is recommended when eligible images
are already standardized. No source is fetched, copied, moved or modified.

Optional grouping evidence:

- `source_page_url`, either at the top level or in `meta`. Contradictory values
  are rejected. URL comparison removes fragments, decodes HTML entities and
  normalizes the scheme/host/default port; it retains path and query identity.
- `shoot_group_id`, an explicit globally meaningful photo-session identifier.
  A generated historical `group_id` is not treated as a session identifier.
- `sha256` (or `image_sha256` / `content_sha256`), 64 hexadecimal characters.
  With `--compute-sha256`, local sources are read to compute this value; relative
  paths resolve against the candidate file's directory. Supplied hashes must
  match the computed values. Network fetching is not implemented.
- `phash`, a **precomputed** 64-bit perceptual hash encoded as 16 hexadecimal
  characters. It participates only when `--phash-threshold N` is explicitly
  supplied. The comparison is inclusive: Hamming distance `<= N`.

Each relation adds an edge to a global UnionFind graph. Transitive links are
resolved **before** splitting. Source-page links are not scoped by ethnicity:
one article can validly include several ethnic groups. Such a component keeps
its complete per-class count vector during stratification. However, identical
SHA256 content with contradictory ethnicity labels is rejected for adjudication.

Candidates with no active grouping evidence are rejected by default. A supplied
pHash is not active until a threshold is explicitly enabled. For an intentional
singleton-only inventory, `--allow-ungrouped` permits such records and lists their
IDs in the report. Directory names are never used to infer ethnicity or sessions.

Perceptual similarity is evidence for co-location, not a proof that two images
are duplicates. Optional pHash grouping can create false links; review large
components before accepting a new plan. The tool does not delete duplicate
images, verify ethnic labels, validate redistribution licenses or replace the
image-quality and annotation audit.

## Build a separate plan

By default the command prints a JSON summary and writes nothing:

```sh
python code/03_build_grouped_split.py build --candidates /tmp/candidates.json --seed 2026
```

An explicit output directory enables writing. Its parent must already exist,
and the directory itself must not exist, even if empty:

```sh
python code/03_build_grouped_split.py build --candidates /tmp/candidates.json --seed 2026 --ratios 0.7,0.15,0.15 --output-dir /tmp/new-split-plan
```

Use `--dry-run` to suppress writing even with an output path. A destination
inside any directory named `dataset` or `.git` is rejected. Existing directories,
files and symlinks are refused rather than overlaid. Production images are never
automatically populated or moved.

The new bundle contains:

- `annotations/dataset_manifest_mapped.json`: the downstream mapping shape,
  with preserved IDs and new `build-<digest>` group IDs, split and planned path.
- `metadata_plan.csv`: the ten common metadata fields plus source page, group
  and source path. Missing source fields stay empty; an annotation-derived
  `garment_type` is `unknown` unless supplied. No license or publisher is invented.
- `image_materialization_plan.csv`: source-to-planned-destination references,
  for an independently authorized later materialization step.
- `grouping_report.json`: seed, ratios, evidence coverage, counts and limitations.

These are **plans**. The generated relative image paths will not exist until a
separate, reviewed materialization step creates a new dataset. The currently
published annotation pipeline still reads its configured dataset directory;
this tool does not redirect it or replace that directory. Existing candidate
`split`, `group_id` and `path` assignments are replaced in a new build plan;
an old absolute `local_dest` is removed so it cannot silently target production.

Whole components are allocated using a deterministic greedy objective over
per-class counts and total size, followed by deterministic single-group
improvement. The objective is class-normalized squared target deviation plus
0.25 times total-size deviation. Seeded SHA256 tie ordering and stable ID sorting
make assignments reproducible under input-row permutation. Components remain
indivisible, so small classes or large sessions may make exact 70/15/15 impossible.
The report exposes actual counts instead of claiming exact proportions.

## Validate or replay a frozen mapping

Use these modes for a published manifest; do not use a new build to claim a
reconstruction of historical assignments:

```sh
python code/03_build_grouped_split.py validate --manifest /tmp/frozen.json
python code/03_build_grouped_split.py replay --manifest /tmp/frozen.json --output-dir /tmp/frozen-replay
```

Validation checks unique IDs, path/ID/split agreement, required group assignments,
and group/source-page/session/exact-hash cross-split links. It permits multiple
ethnicities on one page when they stay in the same split. It does not recompute
or merge groups using pHash. `replay` writes the manifest's **original bytes**,
preserving order, IDs, published group IDs, splits, paths and all record content.
The accompanying metadata and materialization files are derived plans.

By default validation is structural and does not require source images to be
present. To additionally check frozen image references without modifying them,
pass `--image-root /tmp/isolated-image-root`; each published `path` must resolve
to an existing file safely below that root. This checks file references, not
image geometry or semantic annotation quality.

## Offline verification

```sh
python -m unittest discover -s code -p test_grouped_split.py -v
```

The behavioral tests cover global mixed-ethnicity page grouping, transitive
session/hash relations, exact-hash label conflicts, optional inclusive pHash
links, deterministic ordering/seed, class balance, indivisible groups, leading
zero IDs, dry-run and output safeguards, exact-byte frozen replay and invalid
frozen references. Every input and destination used by the tests is synthetic.
