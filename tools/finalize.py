
#!/usr/bin/env python3
"""Validate the LAN-DouDizhu project, then commit and push if every check passes."""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMIT_MESSAGE = "Complete frontend i18n"
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache",
}
SENSITIVE_NAMES = re.compile(
    r"(^|/)(\.env($|\.)|.*\.(pem|key|p12|pfx)$|"
    r"id_rsa|id_ed25519|credentials\.json|secrets?\.json)",
    re.IGNORECASE,
)

os.chdir(ROOT)


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print("\n$", " ".join(command), flush=True)
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, command)
    return result


def git(*args: str, check: bool = True) -> str:
    result = run(["git", *args], check=check)
    return result.stdout.strip()


def fail(message: str) -> None:
    print(f"\nFAILED: {message}")
    sys.exit(1)


def files_with_suffix(*suffixes: str) -> list[Path]:
    return [
        p for p in ROOT.rglob("*")
        if p.is_file()
        and p.suffix.lower() in suffixes
        and not any(part in EXCLUDED_DIRS for part in p.parts)
    ]


class HTMLCheck(HTMLParser):
    pass


def main() -> None:
    print("=== LAN-DouDizhu Final Validation ===")
    print(f"Project: {ROOT}")

    if not (ROOT / ".git").exists():
        fail("Project root is not a Git repository.")

    # 1. Required tools
    for tool in ("python3", "node", "git"):
        if subprocess.call(
            ["bash", "-lc", f"command -v {tool} >/dev/null 2>&1"]
        ) != 0:
            fail(f"Required tool not found: {tool}")

    # 2. Python syntax
    py_files = files_with_suffix(".py")
    for path in py_files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:
            fail(f"Python syntax error in {path.relative_to(ROOT)}: {exc}")
    print(f"PASS: Python syntax ({len(py_files)} files)")

    # 3. JavaScript syntax
    js_files = files_with_suffix(".js", ".mjs", ".cjs")
    for path in js_files:
        result = run(["node", "--check", str(path)], check=False)
        if result.returncode:
            fail(f"JavaScript syntax error: {path.relative_to(ROOT)}")
    print(f"PASS: JavaScript syntax ({len(js_files)} files)")

    # 4. JSON syntax
    json_files = files_with_suffix(".json")
    for path in json_files:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            fail(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}")
    print(f"PASS: JSON syntax ({len(json_files)} files)")

    # 5. Locale checks
    locale_dir = ROOT / "Webpage_client" / "locales"
    required_locales = ("zh-CN.json", "en-CA.json")
    for name in required_locales:
        path = locale_dir / name
        if not path.is_file():
            fail(f"Missing locale file: {path.relative_to(ROOT)}")

    locale_data = {
        name: json.loads((locale_dir / name).read_text(encoding="utf-8"))
        for name in required_locales
    }
    if locale_data["zh-CN.json"].keys() != locale_data["en-CA.json"].keys():
        fail("Locale files have different top-level keys.")
    print("PASS: Locale files exist and have matching top-level keys")

    checker = ROOT / "tools" / "check_i18n.py"
    if checker.is_file():
        result = run(["python3", str(checker)], check=False)
        if result.returncode:
            fail("i18n audit failed.")
        print("PASS: i18n audit")
    else:
        fail("tools/check_i18n.py is missing.")

    # 6. HTML parsing
    html_files = files_with_suffix(".html")
    for path in html_files:
        try:
            parser = HTMLCheck()
            parser.feed(path.read_text(encoding="utf-8"))
            parser.close()
        except Exception as exc:
            fail(f"HTML parsing error in {path.relative_to(ROOT)}: {exc}")
    print(f"PASS: HTML parsing ({len(html_files)} files)")

    # 7. Critical game.js sanity check
    game_js = ROOT / "Webpage_client" / "js" / "game.js"
    if not game_js.is_file():
        fail("Web client game.js is missing.")
    game_text = game_js.read_text(encoding="utf-8")
    if "let selectedCards = new Set();" not in game_text:
        fail("game.js does not contain the expected game logic entry.")
    if "function renderGame(" not in game_text:
        fail("game.js is missing renderGame().")
    print("PASS: game.js sanity check")

    # 8. Python unit tests, if present
    tests_dir = ROOT / "tests"
    if tests_dir.is_dir():
        result = run(
            ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
            check=False,
        )
        if result.returncode:
            fail("Python unit tests failed.")
        print("PASS: Python unit tests")
    else:
        print("INFO: No tests/ directory; unit tests skipped.")

    # 9. Git whitespace checks
    for args in (["diff", "--check"], ["diff", "--cached", "--check"]):
        result = run(["git", *args], check=False)
        if result.returncode:
            fail("Git diff whitespace check failed.")
    print("PASS: git diff --check")

    # 10. Check branch and remote
    branch = git("branch", "--show-current")
    if not branch:
        fail("Detached HEAD; refusing to commit.")

    remotes = git("remote")
    if "origin" not in remotes.split():
        fail("Git remote 'origin' is missing.")

    # Refuse likely secrets before staging.
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    tracked_changes = git(
        "diff", "--name-only", "HEAD"
    ).splitlines()
    candidates = set(untracked + tracked_changes)
    suspicious = [name for name in candidates if SENSITIVE_NAMES.search(name)]
    if suspicious:
        fail("Potential secret files detected:\n  " + "\n  ".join(suspicious))

    # 11. Stage all non-ignored project changes
    run(["git", "add", "-A"])

    staged = git("diff", "--cached", "--name-only")
    if not staged:
        print("\nNothing to commit. No push performed.")
        return

    # Check staged content too.
    result = run(["git", "diff", "--cached", "--check"], check=False)
    if result.returncode:
        fail("Staged diff check failed.")

    print("\n=== Staged changes ===")
    run(["git", "diff", "--cached", "--stat"])
    run(["git", "status", "-s"])

    # 12. Fetch and refuse non-fast-forward situations
    run(["git", "fetch", "origin"])
    upstream = f"origin/{branch}"
    run(["git", "rev-parse", "--verify", upstream], check=False)
    counts = git("rev-list", "--left-right", "--count", f"HEAD...{upstream}")
    ahead, behind = map(int, counts.split())
    if behind:
        fail(
            f"Local branch is behind {upstream} by {behind} commit(s). "
            "Pull/reconcile first; no commit or push was attempted."
        )

    # 13. Commit
    run(["git", "commit", "-m", COMMIT_MESSAGE])

    # 14. Push
    run(["git", "push", "origin", branch])

    print("\n=== FINAL AUDIT ===")
    run(["git", "status", "-sb"])
    run(["git", "log", "-1", "--oneline"])
    print("\nSUCCESS: Validation passed, commit created, and push completed.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        fail(f"Command failed with exit code {exc.returncode}: {exc.cmd}")
