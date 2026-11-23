"""Offline checks: optional generators must not overwrite published artifacts."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from generator_cli import validate_output


CODE_DIR = Path(__file__).resolve().parent
SCRIPTS = ("build_report_docx.py", "generate_report_charts.py", "build_slides_pptx.py")


class GeneratorSafetyTests(unittest.TestCase):
    def test_imports_do_not_require_generation_libraries_or_write_files(self):
        for name in SCRIPTS:
            with self.subTest(script=name):
                spec = importlib.util.spec_from_file_location("safe_" + name[:-3], CODE_DIR / name)
                module = importlib.util.module_from_spec(spec)
                with patch.dict(sys.modules, {"docx": None, "pptx": None, "matplotlib": None}):
                    with patch.object(Path, "mkdir", side_effect=AssertionError("import wrote a directory")):
                        spec.loader.exec_module(module)
                self.assertTrue(callable(module.main))

    def test_help_is_offline_and_does_not_generate(self):
        for name in SCRIPTS:
            with self.subTest(script=name):
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
                result = subprocess.run([sys.executable, str(CODE_DIR / name), "--help"],
                                        capture_output=True, text=True, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("--project-root", result.stdout)

    def test_explicit_output_is_required(self):
        for name in SCRIPTS:
            with self.subTest(script=name):
                result = subprocess.run([sys.executable, str(CODE_DIR / name)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)

    def test_published_trees_are_protected_even_with_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            for relative in ("dataset/captions.docx", "report/draft.docx", "report/slides/draft.pptx"):
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    validate_output(root, root / relative, force=True)

    def test_project_and_ancestor_are_not_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            for target in (root, root.parent):
                with self.subTest(target=target), self.assertRaises(ValueError):
                    validate_output(root, target, force=True, directory=True)

    def test_existing_draft_is_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            draft = Path(tmp) / "draft.docx"
            draft.write_bytes(b"keep this draft")
            with self.assertRaises(ValueError):
                validate_output(root, draft, suffix=".docx")
            self.assertEqual(draft.read_bytes(), b"keep this draft")

    def test_new_external_draft_path_is_accepted_without_creating_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            draft = Path(tmp) / "drafts" / "report.docx"
            self.assertEqual(validate_output(root, draft, suffix=".docx"), draft.resolve())
            self.assertFalse(draft.parent.exists())


if __name__ == "__main__":
    unittest.main()
