"""Синтетичні Git-історії: жодних справжніх ключів чи даних осіб."""
import os
import hashlib
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
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE).decode().strip()

    def commit(self, root):
        self.git(root, "add", ".")
        self.git(root, "-c", "user.name=Synthetic", "-c", "user.email=audit@example.invalid", "commit", "-qm", "synthetic")
        return self.git(root, "rev-parse", "HEAD")

    def initialize(self, root):
        self.git(root, "init", "-qb", "main")
        (root / "README.md").write_text("Synthetic repository\n", encoding="utf-8")
        return self.commit(root)

    def fake_secret(self):
        # AUDIT_EXAMPLE: синтетичний рядок лише у тимчасовому тестовому Git.
        return "ghp_" + hashlib.sha256(b"synthetic audit value").hexdigest()[:36]

    def scan(self, root, span):
        result = subprocess.run([BINARY, "git", "--config=" + CONFIG,
            "--gitleaks-ignore-path=" + IGNORE, "--ignore-gitleaks-allow", "--redact=100",
            "--no-banner", "--exit-code=1", "--log-opts=--diff-merges=first-parent " + span,
            str(root)], capture_output=True, timeout=30)
        return result.returncode

    def test_secret_removed_in_later_commit_is_still_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.initialize(root)
            (root / "secret.txt").write_text(self.fake_secret(), encoding="utf-8")
            self.commit(root)
            (root / "secret.txt").unlink()
            head = self.commit(root)
            self.assertEqual(self.scan(root, head), 1)

    def test_merge_secret_cannot_hide_with_pr_configuration_or_allow_comment(self):
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
            head = self.commit(root)
            self.assertEqual(self.scan(root, base + ".." + head), 1)
