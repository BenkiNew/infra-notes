"""Синтетичні перевірки guard; файли та програми проєкту не виконуються."""
import importlib.util
from pathlib import Path
import tempfile
import sys
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("change_guard", Path(__file__).parents[1] / "scripts/change_guard.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class ChangeGuardTests(unittest.TestCase):
    def test_python_is_parsed_without_execution(self):
        """Перевірка приймає синтаксис, не виконуючи інструкцію raise."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "module.py").write_text("raise RuntimeError('must not execute')", encoding="utf-8")
            guard.check_file(root, "module.py")

    def test_invalid_python_is_rejected(self):
        """Некоректний Python має завершитися SyntaxError."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "module.py").write_text("def invalid(:", encoding="utf-8")
            with self.assertRaises(SyntaxError):
                guard.check_file(root, "module.py")

    def test_escape_is_rejected(self):
        """Вихід за межі checkout блокується до читання."""
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                guard.safe_path(Path(folder), "../outside.py")

    def test_invalid_json_is_rejected(self):
        """Пошкоджений JSON не отримує успішного результату."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config.json").write_text("{", encoding="utf-8")
            with self.assertRaises(ValueError):
                guard.check_file(root, "config.json")

    def test_invalid_revision_cannot_reach_git(self):
        """Недовірений ref відхиляється до запуску Git."""
        with patch.object(guard, "run_git") as call:
            with self.assertRaises(ValueError):
                guard.main(Path.cwd(), "untrusted-ref", "a" * 40)
            call.assert_not_called()

    def test_top_level_return_is_rejected(self):
        """Compile виявляє return поза функцією без виконання файла."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "module.py").write_text("return 42", encoding="utf-8")
            with self.assertRaises(SyntaxError):
                guard.check_file(root, "module.py")

    def test_repeated_yaml_keys_are_rejected(self):
        """Повторений ключ не може мовчки переписати налаштування."""
        with self.assertRaises(ValueError):
            guard.check_yaml("with: {a: one}\nwith: {b: two}\n")

    def test_yaml_tags_cannot_construct_objects(self):
        """Python-теги YAML не створюють об’єкти."""
        with self.assertRaises(ValueError):
            guard.check_yaml("!!python/object/apply:os.system ['must not execute']")

    def test_type_changed_file_is_checked(self):
        """Статус T у справжньому Git не обходить перевірку синтаксису."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def git(*args, data=None):
                """Виконати Git у тимчасовій синтетичній теці з явним автором."""
                return subprocess.check_output(["git", "-C", str(root), *args], input=data)
            git("init", "-q")
            blob = git("hash-object", "-w", "--stdin", data=b"target").decode().strip()
            git("update-index", "--add", "--cacheinfo", "120000", blob, "module.py")
            git("-c", "user.name=Synthetic", "-c", "user.email=audit@example.invalid", "commit", "-qm", "base")
            before = git("rev-parse", "HEAD").decode().strip()
            (root / "module.py").write_text("return 42\n", encoding="utf-8", newline="\n")
            git("add", "module.py")
            git("-c", "user.name=Synthetic", "-c", "user.email=audit@example.invalid", "commit", "-qm", "type change")
            after = git("rev-parse", "HEAD").decode().strip()
            self.assertEqual(guard.main(root, before, after), 1)

    def test_isolated_python_does_not_import_candidate_module(self):
        """Кандидат із підробленим json.py не виконується режимом -I."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "json.py").write_text("raise RuntimeError('candidate executed')", encoding="utf-8")
            result = subprocess.run([sys.executable, "-I", "-c", "import json; print(json.dumps({'safe': True}))"],
                                    cwd=root, capture_output=True, text=True, check=True)
            self.assertIn('"safe": true', result.stdout)
