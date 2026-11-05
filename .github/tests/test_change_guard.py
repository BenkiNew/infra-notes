"""Синтетичні перевірки guard; файли та програми проєкту не виконуються."""
import importlib.util
from pathlib import Path
import tempfile
import subprocess
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

    def test_top_level_return_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "module.py").write_text("return 42", encoding="utf-8")
            with self.assertRaises(SyntaxError):
                guard.check_file(root, "module.py")

    def test_repeated_yaml_keys_are_rejected(self):
        with self.assertRaises(ValueError):
            guard.check_yaml("with: {a: one}\nwith: {b: two}\n")

    def test_yaml_tags_cannot_construct_objects(self):
        with self.assertRaises(ValueError):
            guard.check_yaml("!!python/object/apply:os.system ['must not execute']")

    def test_type_changed_file_is_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def git(*args, data=None):
                return subprocess.check_output(["git", "-C", str(root), *args], input=data)
            git("init", "-q")
            blob = git("hash-object", "-w", "--stdin", data=b"target").decode().strip()
            git("update-index", "--add", "--cacheinfo", "120000", blob, "module.py")
            git("-c", "user.name=Synthetic", "-c", "user.email=audit@example.invalid", "commit", "-qm", "base")
            before = git("rev-parse", "HEAD").decode().strip()
            (root / "module.py").write_text("return 42\n", encoding="utf-8")
            git("add", "module.py")
            git("-c", "user.name=Synthetic", "-c", "user.email=audit@example.invalid", "commit", "-qm", "type change")
            after = git("rev-parse", "HEAD").decode().strip()
            self.assertEqual(guard.main(root, before, after), 1)
