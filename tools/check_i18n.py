
#!/usr/bin/env python3
"""Audit HTML/JavaScript translation keys against every locale JSON file."""

import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "Webpage_client"
LOCALE_DIR = WEB_ROOT / "locales"

HTML_ATTRIBUTES = {
    "data-i18n",
    "data-i18n-placeholder",
    "data-i18n-title",
    "data-i18n-document-title",
}

JS_CALL_PATTERN = re.compile(
    r"""(?:window\.)?i18n\.t\(\s*(['"])(.*?)\1"""
)


class TranslationHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.keys = set()

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in HTML_ATTRIBUTES and value:
                self.keys.add(value.strip())


def reject_duplicate_keys(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value

    return result


def scan_html():
    keys = set()
    html_files = list(WEB_ROOT.rglob("*.html"))

    for path in html_files:
        parser = TranslationHTMLParser()
        parser.feed(path.read_text(encoding="utf-8"))
        keys.update(parser.keys)

    return keys, html_files


def scan_javascript():
    keys = set()
    js_files = list((WEB_ROOT / "js").rglob("*.js"))

    for path in js_files:
        source = path.read_text(encoding="utf-8")

        for match in JS_CALL_PATTERN.finditer(source):
            keys.add(match.group(2))

    return keys, js_files


def load_locales():
    locales = {}

    if not LOCALE_DIR.is_dir():
        raise FileNotFoundError(f"Locale directory not found: {LOCALE_DIR}")

    files = sorted(LOCALE_DIR.glob("*.json"))

    if not files:
        raise FileNotFoundError("No locale JSON files found.")

    for path in files:
        try:
            data = json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=reject_duplicate_keys,
            )
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError(f"{path.name}: {error}") from error

        if not isinstance(data, dict):
            raise ValueError(f"{path.name}: root must be a JSON object.")

        locales[path.stem] = data

    return locales


def main():
    print("=== LAN-DouDizhu i18n Audit ===")
    print(f"Project: {ROOT}")

    html_keys, html_files = scan_html()
    js_keys, js_files = scan_javascript()
    required_keys = html_keys | js_keys

    print(f"\nHTML files scanned: {len(html_files)}")
    print(f"JavaScript files scanned: {len(js_files)}")
    print(f"HTML translation keys: {len(html_keys)}")
    print(f"JavaScript translation keys: {len(js_keys)}")
    print(f"Total referenced keys: {len(required_keys)}")

    try:
        locales = load_locales()
    except (OSError, ValueError) as error:
        print(f"\n[FAIL] {error}")
        return 1

    print(f"Locale files found: {len(locales)}")

    failed = False

    for locale_name, translations in sorted(locales.items()):
        available_keys = set(translations)
        missing = sorted(required_keys - available_keys)
        unused = sorted(available_keys - required_keys)

        print(f"\n--- {locale_name} ---")
        print(f"Defined keys: {len(available_keys)}")
        print(f"Missing keys: {len(missing)}")
        print(f"Unused keys: {len(unused)}")

        if missing:
            failed = True
            print("[FAIL] Missing translation keys:")

            for key in missing:
                print(f"  - {key}")

        if unused:
            print("[WARN] Unreferenced translation keys:")

            for key in unused:
                print(f"  - {key}")

        if not missing:
            print("[OK] All referenced keys are defined.")

    print("\n=== Audit Result ===")

    if failed:
        print("FAILED: One or more locales have missing keys.")
        return 1

    print("PASSED: Every locale contains all referenced keys.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
