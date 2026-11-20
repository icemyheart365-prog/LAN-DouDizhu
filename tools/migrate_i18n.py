
#!/usr/bin/env python3
"""Conservative i18n migration tool. Preview by default; use --apply to write."""

import argparse
import ast
import difflib
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "Webpage_client"
LOCALE = WEB / "locales" / "zh-CN.json"

HTML_FILES = [WEB / "index.html"]
JS_DIR = WEB / "js"

HTML_TEXT = re.compile(
    r"<(?P<tag>[A-Za-z][\w-]*)(?P<attrs>\s[^<>]*?)?>"
    r"(?P<text>[^<>]+)"
    r"</(?P=tag)\s*>",
    re.DOTALL,
)

JS_ASSIGNMENT = re.compile(
    r"(?P<prefix>\.(?:textContent|placeholder|title)\s*=\s*)"
    r"(?P<quote>['\"])(?P<text>(?:\\.|[^\\])*?)"
    r"(?P=quote)"
)

SKIP_TAGS = {"script", "style", "code", "pre", "textarea"}


def load_dictionary():
    data = json.loads(LOCALE.read_text(encoding="utf-8"))
    reverse = defaultdict(list)

    for key, value in data.items():
        if isinstance(value, str):
            reverse[value].append(key)

    unique = {
        text: keys[0]
        for text, keys in reverse.items()
        if len(keys) == 1
    }
    ambiguous = {
        text: keys
        for text, keys in reverse.items()
        if len(keys) > 1
    }
    return unique, ambiguous


def migrate_html(source, mapping):
    def replace(match):
        tag = match.group("tag")
        attrs = match.group("attrs") or ""
        text = match.group("text")
        stripped = text.strip()

        if tag.lower() in SKIP_TAGS:
            return match.group(0)

        if "data-i18n" in attrs:
            return match.group(0)

        key = mapping.get(stripped)
        if not key:
            return match.group(0)

        leading = text[:len(text) - len(text.lstrip())]
        trailing = text[len(text.rstrip()):]
        new_attrs = attrs + f' data-i18n="{key}"'

        return (
            f"<{tag}{new_attrs}>"
            f"{leading}{trailing}"
            f"</{tag}>"
        )

    return HTML_TEXT.sub(replace, source)


def migrate_javascript(source, mapping):
    def replace(match):
        raw = match.group("quote") + match.group("text") + match.group("quote")

        try:
            value = ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            return match.group(0)

        key = mapping.get(value)
        if not key:
            return match.group(0)

        return match.group("prefix") + f'i18n.t("{key}")'

    return JS_ASSIGNMENT.sub(replace, source)


def process_file(path, mapping, apply):
    original = path.read_text(encoding="utf-8")

    if path.suffix == ".html":
        updated = migrate_html(original, mapping)
    else:
        updated = migrate_javascript(original, mapping)

    if updated == original:
        return 0

    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=str(path.relative_to(ROOT)),
        tofile=str(path.relative_to(ROOT)) + " (i18n)",
    )

    print("".join(diff))

    if apply:
        backup = path.with_name(path.name + ".i18n.bak")
        if not backup.exists():
            shutil.copy2(path, backup)

        path.write_text(updated, encoding="utf-8")
        print(f"[APPLIED] {path.relative_to(ROOT)}")
    else:
        print(f"[PREVIEW] {path.relative_to(ROOT)}")

    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes after creating backups.",
    )
    args = parser.parse_args()

    if not LOCALE.is_file():
        print(f"[FAIL] Missing locale file: {LOCALE}")
        return 1

    mapping, ambiguous = load_dictionary()

    print("=== LAN-DouDizhu i18n Migration ===")
    print(f"Mode: {'APPLY' if args.apply else 'PREVIEW'}")
    print(f"Unique Chinese strings: {len(mapping)}")
    print(f"Ambiguous Chinese strings: {len(ambiguous)}")

    for value, keys in ambiguous.items():
        print(f"[SKIP: ambiguous] {value!r} -> {', '.join(keys)}")

    files = [path for path in HTML_FILES if path.is_file()]
    files.extend(sorted(JS_DIR.rglob("*.js")))

    changed = 0

    for path in files:
        changed += process_file(path, mapping, args.apply)

    print(f"\nFiles with proposed changes: {changed}")

    if not args.apply:
        print("Preview only. Run with --apply to write changes.")
    else:
        print("Migration applied. Review the backups and git diff.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
