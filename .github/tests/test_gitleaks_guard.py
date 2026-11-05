"""Синтетичні Git-історії: жодних справжніх ключів чи даних осіб."""
import os
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

BINARY = os.environ.get("GITLEAKS_BINARY")
CONFIG = os.environ.get("GITLEAKS_CONFIG_TRUSTED")
IGNORE = os.environ.get("GITLEAKS_IGNORE_TRUSTED")


@unittest.skipUnless(BINARY and CONFIG and IGNORE, "Потрібен перевірений Gitleaks та довірена конфігурація")
class GitleaksGuardTests(unittest.TestCase):
    def git(self, root, *args):
        """Виконати Git у тимчасовій синтетичній теці з явним автором."""
        return subprocess.check_output(["git", "-c", "user.name=Synthetic", "-c", "user.email=audit@example.invalid", "-C", str(root), *args], stderr=subprocess.PIPE).decode().strip()

    def commit(self, root):
        """Записати синтетичну ревізію й повернути її точний SHA."""
        self.git(root, "add", ".")
        self.git(root, "-c", "user.name=Synthetic", "-c", "user.email=audit@example.invalid", "commit", "-qm", "synthetic")
        return self.git(root, "rev-parse", "HEAD")

    def initialize(self, root):
        """Створити чисту синтетичну історію без глобальних Git-налаштувань."""
        self.git(root, "init", "-qb", "main")
        (root / "README.md").write_text("Synthetic repository\n", encoding="utf-8")
        return self.commit(root)

    def fake_secret(self):
        """Побудувати неживий тестовий маркер стандартного формату токена."""
        # AUDIT_EXAMPLE: синтетичний рядок лише у тимчасовому тестовому Git.
        return "ghp_" + hashlib.sha256(b"synthetic audit value").hexdigest()[:36]

    def scan(self, root, span):
        """Повернути код і замасковані знахідки, не плутаючи помилку зі сканом."""
        # Відтворює очищення лише кореневого ignore у тимчасовому checkout.
        (root / ".gitleaksignore").unlink(missing_ok=True)
        report = root.parent / (root.name + "-gitleaks.json")
        result = subprocess.run([BINARY, "git", "--config=" + CONFIG,
            "--gitleaks-ignore-path=" + IGNORE, "--ignore-gitleaks-allow", "--redact=100",
            "--no-banner", "--report-format=json", "--report-path=" + str(report),
            "--exit-code=1", "--log-opts=--diff-merges=first-parent " + span,
            str(root)], capture_output=True, timeout=30)
        findings = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else []
        report.unlink(missing_ok=True)
        return result.returncode, findings

    def assert_secret_found(self, root, span):
        """Вимагати точну знахідку github-pat у synthetic secret.txt."""
        code, findings = self.scan(root, span)
        self.assertEqual(code, 1)
        self.assertTrue(any(item.get("RuleID") == "github-pat" and item.get("File") == "secret.txt"
                            and item.get("Commit") for item in findings), "Немає очікуваної синтетичної знахідки")

    def test_secret_removed_in_later_commit_is_still_detected(self):
        """Історія зберігає виявлення маркера, видаленого наступною ревізією."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.initialize(root)
            (root / "secret.txt").write_text(self.fake_secret(), encoding="utf-8")
            self.commit(root)
            (root / "secret.txt").unlink()
            head = self.commit(root)
            self.assert_secret_found(root, head)

    def test_merge_secret_cannot_hide_with_pr_configuration_or_allow_comment(self):
        """Merge-маркер виявляється попри PR-конфігурацію та allow-коментар."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base = self.initialize(root)
            self.git(root, "checkout", "-qb", "feature")
            (root / "feature.txt").write_text("feature\n", encoding="utf-8")
            self.commit(root)
            self.git(root, "checkout", "-q", "main")
            (root / "main.txt").write_text("main\n", encoding="utf-8")
            self.commit(root)
            self.git(root, "merge", "--no-commit", "--no-ff", "feature")
            (root / "secret.txt").write_text(self.fake_secret() + " # gitleaks:allow", encoding="utf-8")
            (root / ".gitleaks.toml").write_text('[extend]\nuseDefault = true\n[allowlist]\nregexes = [".*"]\n', encoding="utf-8")
            (root / ".gitleaksignore").write_text("secret.txt:github-pat:1\n", encoding="utf-8")
            head = self.commit(root)
            self.assert_secret_found(root, base + ".." + head)

    def test_ignore_directory_is_an_error(self):
        """Каталог замість ignore-файла не може вимкнути захист мовчки."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            head = self.initialize(root)
            (root / ".gitleaksignore").mkdir()
            with self.assertRaises(IsADirectoryError if os.name != "nt" else PermissionError):
                self.scan(root, head)
