"""Синтетичні перевірки guard; файли та програми проєкту не виконуються."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("change_guard", Path(__file__).parents[1] / "scripts/change_guard.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class ChangeGuardTests(unittest.TestCase):
    def test_python_is_parsed_without_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "module.py").write_text("raise RuntimeError('must not execute')", encoding="utf-8")
            guard.check_file(root, "module.py")

    def test_invalid_python_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "module.py").write_text("def invalid(:", encoding="utf-8")
            with self.assertRaises(SyntaxError):
                guard.check_file(root, "module.py")

    def test_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                guard.safe_path(Path(folder), "../outside.py")

    def test_invalid_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config.json").write_text("{", encoding="utf-8")
            with self.assertRaises(ValueError):
                guard.check_file(root, "config.json")

    def test_invalid_revision_cannot_reach_git(self):
        with patch.object(guard, "run_git") as call:
            with self.assertRaises(ValueError):
                guard.main(Path.cwd(), "untrusted-ref", "a" * 40)
            call.assert_not_called()
