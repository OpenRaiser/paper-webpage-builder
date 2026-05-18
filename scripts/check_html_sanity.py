#!/usr/bin/env python3
"""HTML5-aware sanity check for a generated paper webpage.

Backends, in preferred order:
  1. `html5validator` (Java/Vnu) — strictest.
  2. `tidy -e -q` from html-tidy.
  3. `html5lib` Python parser — strict-ish, doesn't require Java.
  4. Fallback: stdlib `html.parser` walking the document and reporting
     unbalanced tags, malformed attributes, and the most common HTML5 mistakes
     that `xmllint --html` would either miss (custom elements, `<main>`,
     `<picture>`, `<dialog>`) or false-flag.

The script prefers an actually installed backend. If only the stdlib
fallback runs the report makes that explicit so the caller knows the check
was best-effort.

Exit codes:
  0  no errors
  1  at least one error reported by the chosen backend
  2  invalid arguments / file missing
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
# A small, permissive HTML5 element list. Custom elements (`my-foo`) pass
# automatically because we only flag known-bad patterns, not unknown tags.
HTML5_OPTIONAL_END_TAGS = {"li", "p", "td", "th", "tr", "thead", "tbody", "tfoot", "option", "optgroup", "dt", "dd"}


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def run_html5validator(path: Path) -> dict:
    proc = subprocess.run(
        ["html5validator", "--ignore", "info", "--also-check-css", "--", str(path)],
        capture_output=True, text=True,
    )
    return {
        "backend": "html5validator",
        "ok": proc.returncode == 0,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def run_tidy(path: Path) -> dict:
    proc = subprocess.run(
        ["tidy", "-quiet", "-errors", "--gnu-emacs", "yes", str(path)],
        capture_output=True, text=True,
    )
    # tidy returns 0 (clean), 1 (warnings) or 2 (errors). Treat 0–1 as ok.
    return {
        "backend": "tidy",
        "ok": proc.returncode <= 1,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def run_html5lib(path: Path) -> dict:
    try:
        import html5lib  # type: ignore
    except Exception:
        return {"backend": "html5lib", "ok": False, "skipped": True,
                "stderr": "html5lib not installed"}
    text = path.read_text(encoding="utf-8", errors="replace")
    parser = html5lib.HTMLParser(strict=False)
    parser.parse(text)
    errors = parser.errors  # list of (line/col, code, datavars)
    if not errors:
        return {"backend": "html5lib", "ok": True, "stdout": ""}
    lines = [
        f"{pos[0]}:{pos[1] if isinstance(pos, tuple) and len(pos) > 1 else 0} {code} {data}"
        for pos, code, data in errors[:50]
    ]
    extra = "" if len(errors) <= 50 else f"\n... and {len(errors) - 50} more"
    return {
        "backend": "html5lib",
        "ok": False,
        "stdout": "\n".join(lines) + extra,
    }


class FallbackParser(HTMLParser):
    """Best-effort parser that flags unbalanced tags and malformed input."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, tuple[int, int]]] = []
        self.errors: list[str] = []
        self.has_doctype = False

    def handle_decl(self, decl: str) -> None:
        if decl.lower().startswith("doctype"):
            self.has_doctype = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in VOID_ELEMENTS:
            return
        self.stack.append((tag, self.getpos()))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # Self-closing on a non-void element is technically fine in HTML5
        # (browsers ignore the slash) so we don't flag it.
        return

    def handle_endtag(self, tag: str) -> None:
        if not self.stack:
            self.errors.append(f"line {self.getpos()[0]}: unmatched </{tag}>")
            return
        # Pop until we find the matching open tag, allowing optional-end tags
        # (li/p/etc.) to auto-close like browsers do.
        for index in range(len(self.stack) - 1, -1, -1):
            top_tag, _ = self.stack[index]
            if top_tag == tag:
                # Auto-close intermediate optional-end tags silently.
                self.stack = self.stack[:index]
                return
            if top_tag in HTML5_OPTIONAL_END_TAGS:
                continue
            # Otherwise the closing tag is mismatched.
            self.errors.append(
                f"line {self.getpos()[0]}: </{tag}> closes <{top_tag}> opened at "
                f"line {self.stack[index][1][0]}"
            )
            self.stack = self.stack[:index]
            return
        self.errors.append(f"line {self.getpos()[0]}: unmatched </{tag}>")

    def error(self, message: str) -> None:  # type: ignore[override]
        # html.parser raises on some malformed input; capture instead.
        self.errors.append(message)


def run_fallback(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    parser = FallbackParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:
        parser.errors.append(f"parse exception: {exc}")
    if not parser.has_doctype:
        parser.errors.insert(0, "missing <!doctype html> declaration")
    leftover = [t for t, _ in parser.stack if t.lower() not in {"html", "body", "head"}]
    if leftover:
        parser.errors.append(f"unclosed tags at end of document: {', '.join(leftover)}")
    return {
        "backend": "stdlib-fallback",
        "ok": not parser.errors,
        "stdout": "\n".join(parser.errors),
        "stderr": (
            "stdlib fallback only flags structural issues; install html5validator, "
            "tidy, or html5lib for stricter HTML5 conformance."
        ),
    }


def pick_backend(force: str | None) -> str:
    if force:
        return force
    if _have("html5validator"):
        return "html5validator"
    if _have("tidy"):
        return "tidy"
    try:
        import html5lib  # noqa: F401
        return "html5lib"
    except Exception:
        return "stdlib-fallback"


def run(path: Path, backend: str) -> dict:
    if backend == "html5validator":
        return run_html5validator(path)
    if backend == "tidy":
        return run_tidy(path)
    if backend == "html5lib":
        return run_html5lib(path)
    return run_fallback(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument(
        "--backend",
        choices=("html5validator", "tidy", "html5lib", "stdlib-fallback"),
        default=None,
        help="Force a specific backend; default is auto-pick.",
    )
    parser.add_argument("--json", action="store_true",
                        help="Emit JSON instead of text.")
    args = parser.parse_args()

    if not args.html.is_file():
        print(f"error: not a file: {args.html}", file=sys.stderr)
        return 2

    backend = pick_backend(args.backend)
    result = run(args.html, backend)

    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        backend_used = result.get("backend", backend)
        if result.get("ok"):
            print(f"sanity check OK ({backend_used})")
        else:
            print(f"sanity check FAILED ({backend_used})")
            if result.get("stdout"):
                print(result["stdout"].rstrip())
            if result.get("stderr"):
                print(result["stderr"].rstrip(), file=sys.stderr)

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
