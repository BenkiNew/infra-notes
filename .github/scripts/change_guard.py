"""Перевірка синтаксису змін без імпорту коду чи доступу до production.

Вхід: BASE_SHA/HEAD_SHA GitHub або аргументи main(). Вихід: ненульовий код
за помилки Git, синтаксису чи шляху поза checkout. Не виконує код проєкту.
Повний набір предметних тестів залишається окремим CI-компонентом.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tokenize

import yaml


def run_git(root, *args):
    """Прочитати Git; будь-яка помилка припиняє перевірку."""
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


def safe_path(root, name):
    """Заборонити читання символьного посилання поза checkout."""
    root = root.resolve()
    path = root / name
    if not path.resolve().is_relative_to(root):
        raise ValueError("Шлях поза checkout")
    return path


def check_yaml(text):
    """Прочитати без створення Python-об’єктів; відхилити повторені ключі."""
    node = yaml.compose(text, Loader=yaml.SafeLoader)
    pending = [node] if node is not None else []
    visited = set()
    allowed = {"map", "seq", "str", "int", "float", "bool", "null", "timestamp", "binary", "merge"}
    while pending:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        if current.tag.removeprefix("tag:yaml.org,2002:") not in allowed:
            raise ValueError("Непідтримуваний тег YAML")
        if isinstance(current, yaml.nodes.MappingNode):
            keys = set()
            for key, value in current.value:
                if not isinstance(key, yaml.nodes.ScalarNode):
                    raise ValueError("Складний ключ YAML не підтримується")
                identity = (key.tag, key.value)
                if identity in keys:
                    raise ValueError("Повторений ключ YAML")
                keys.add(identity)
                pending.extend((key, value))
        elif isinstance(current, yaml.nodes.SequenceNode):
            pending.extend(current.value)


def check_file(root, name):
    """Перевірити Python/JS/JSON і YAML конфігурації GitHub без запуску коду."""
    path = safe_path(root, name)
    if not path.is_file():
        raise ValueError("Змінений файл недоступний")
    suffix = path.suffix.lower()
    if suffix == ".py":
        with tokenize.open(path) as stream:
            compile(stream.read(), name, "exec")
    elif suffix in {".js", ".mjs", ".cjs"}:
        subprocess.run(["node", "--check", str(path)], check=True, capture_output=True)
    elif suffix == ".json" and not name.startswith(("tests/fixtures/", "test/fixtures/")):
        json.loads(path.read_text(encoding="utf-8-sig"))
    elif suffix in {".yaml", ".yml"} and (name.startswith(".github/") or name == ".coderabbit.yaml"):
        check_yaml(path.read_text(encoding="utf-8-sig"))


def main(root, base, head):
    """Перевірити точний diff; за відсутності base — поточний знімок."""
    if not re.fullmatch(r"[0-9a-f]{40}", head or ""):
        raise ValueError("Потрібен точний HEAD_SHA")
    if base and base != "0" * 40:
        if not re.fullmatch(r"[0-9a-f]{40}", base):
            raise ValueError("Некоректний BASE_SHA")
        span = base + "..." + head
        run_git(root, "diff", "--check", span, "--")
        raw = run_git(root, "diff", "--name-only", "--diff-filter=ACMRT", "-z", span, "--")
    else:
        run_git(root, "show", "--format=", "--check", head, "--")
        raw = run_git(root, "ls-files", "-z", "--")
    names = [part.decode("utf-8") for part in raw.split(b"\0") if part]
    failed = []
    for name in names:
        try:
            check_file(root, name)
        except (OSError, ValueError, SyntaxError, yaml.YAMLError, subprocess.SubprocessError) as error:
            # Не виводити вміст джерела або повідомлення парсера з його рядками.
            print("Помилка перевірки:", ascii(name), type(error).__name__)
            failed.append(name)
    print("Перевірено змінених файлів:", len(names), "; помилок:", len(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(Path.cwd(), os.environ.get("BASE_SHA", ""), os.environ.get("HEAD_SHA", "")))
