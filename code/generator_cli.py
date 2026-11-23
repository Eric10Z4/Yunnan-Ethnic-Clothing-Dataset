"""Explicit output handling for optional document/chart template generators.

These generators never write to a project's published dataset/ or report/ tree.
Importing the generators is side-effect free; generation requires an explicit CLI
output outside those protected trees.
"""

import argparse
from pathlib import Path


def generation_args(script_path, description, *, directory=False, suffix=None):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--project-root", type=Path,
                        default=Path(script_path).resolve().parent.parent,
                        help="Read-only project inputs (defaults to this checkout).")
    flag = "--output-dir" if directory else "--output"
    parser.add_argument(flag, dest="output", required=True, type=Path,
                        help="Explicit draft destination outside dataset/ and report/.")
    parser.add_argument("--figures-dir", type=Path,
                        help="Optional chart input directory for Word/PPT templates.")
    parser.add_argument("--force", action="store_true",
                        help="Allow replacing draft outputs, never published assets.")
    args = parser.parse_args()
    try:
        args.project_root = args.project_root.resolve()
        args.output = validate_output(args.project_root, args.output,
                                      force=args.force, directory=directory,
                                      suffix=suffix)
        args.figures_dir = (args.figures_dir.resolve() if args.figures_dir else
                            args.project_root / "report" / "figures")
    except ValueError as exc:
        parser.error(str(exc))
    return args


def validate_output(project_root, output, *, force=False, directory=False,
                    suffix=None):
    root = Path(project_root).resolve()
    target = Path(output).resolve()
    for protected in (root / "dataset", root / "report"):
        if target == protected or protected in target.parents:
            raise ValueError("Refusing to write inside published dataset/ or report/.")
    if target == root or target in root.parents:
        raise ValueError("Output must not replace the project or an ancestor.")
    if suffix and target.suffix.lower() != suffix:
        raise ValueError("Output filename must end with " + suffix)
    if target.exists():
        if directory and not target.is_dir():
            raise ValueError("Output directory is an existing file.")
        if not directory and not target.is_file():
            raise ValueError("Output filename is an existing directory.")
        if not force:
            raise ValueError("Output already exists; choose a new draft destination.")
    return target
