#!/usr/bin/env python3
"""Substitute `{{NAME}}` placeholders in an HTML template.

Default behaviour:
  render_template.py <template.html> <values.json> -o <out.html>

`values.json` is a flat object mapping placeholder names to strings.
Required placeholders for the bundled `single-page-template.html`:
  LANG, TITLE, DESCRIPTION, CANONICAL_URL, OG_IMAGE, JSONLD

Unknown placeholders raise an error unless `--allow-missing` is passed.

`--inplace <existing.html>` mode:
  Skip the body and only update the metadata block (everything inside <head>
  whose tags carry an attribute matching one of LANG/CANONICAL_URL/OG_IMAGE/
  TITLE/DESCRIPTION). Useful when the page was hand-edited but the LLM wants
  to refresh canonical/social metadata before publishing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Z][A-Z0-9_]*)\s*\}\}")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _comment_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in COMMENT_RE.finditer(text)]


def _in_comment(span: tuple[int, int], comments: list[tuple[int, int]]) -> bool:
    start, end = span
    for c_start, c_end in comments:
        if c_start <= start and end <= c_end:
            return True
    return False


def substitute(text: str, values: dict[str, str], allow_missing: bool) -> tuple[str, list[str]]:
    missing: list[str] = []
    comments = _comment_spans(text)

    def repl(match: re.Match[str]) -> str:
        if _in_comment(match.span(), comments):
            return match.group(0)
        name = match.group(1)
        if name in values:
            return values[name]
        missing.append(name)
        return match.group(0) if allow_missing else ""

    rendered = PLACEHOLDER_RE.sub(repl, text)
    return rendered, missing


def update_inplace(html: str, values: dict[str, str]) -> tuple[str, list[str]]:
    """Refresh head-block metadata without disturbing the rest of the page."""
    updates: list[str] = []

    def replace_attr(pattern: str, attr: str, new_value: str) -> str:
        nonlocal html
        regex = re.compile(pattern, re.IGNORECASE | re.DOTALL)
        match = regex.search(html)
        if match:
            html = html[: match.start(1)] + new_value + html[match.end(1):]
            updates.append(attr)
        return html

    if "LANG" in values:
        html = replace_attr(
            r"<html\b[^>]*\blang=\"([^\"]*)\"", "html[lang]", values["LANG"]
        )
    if "TITLE" in values:
        html = replace_attr(
            r"<title>([^<]*)</title>", "title", values["TITLE"]
        )
        for attr_name, key in (("og:title", "TITLE"), ("twitter:title", "TITLE")):
            html = replace_attr(
                rf"<meta\s+(?:property|name)=\"{re.escape(attr_name)}\"\s+content=\"([^\"]*)\"",
                f"meta[{attr_name}]", values[key],
            )
    if "DESCRIPTION" in values:
        for attr_name, prefix in (("description", "name"), ("og:description", "property"),
                                  ("twitter:description", "name")):
            html = replace_attr(
                rf"<meta\s+{prefix}=\"{re.escape(attr_name)}\"\s+content=\"([^\"]*)\"",
                f"meta[{attr_name}]", values["DESCRIPTION"],
            )
    if "CANONICAL_URL" in values:
        html = replace_attr(
            r"<link\s+rel=\"canonical\"\s+href=\"([^\"]*)\"",
            "link[canonical]", values["CANONICAL_URL"],
        )
        for attr_name in ("og:url",):
            html = replace_attr(
                rf"<meta\s+property=\"{re.escape(attr_name)}\"\s+content=\"([^\"]*)\"",
                f"meta[{attr_name}]", values["CANONICAL_URL"],
            )
    if "OG_IMAGE" in values:
        for attr_name, prefix in (("og:image", "property"), ("twitter:image", "name")):
            html = replace_attr(
                rf"<meta\s+{prefix}=\"{re.escape(attr_name)}\"\s+content=\"([^\"]*)\"",
                f"meta[{attr_name}]", values["OG_IMAGE"],
            )
    if "JSONLD" in values:
        regex = re.compile(
            r"(<script\s+type=\"application/ld\+json\">)(.*?)(</script>)",
            re.IGNORECASE | re.DOTALL,
        )
        match = regex.search(html)
        if match:
            html = html[: match.end(1)] + values["JSONLD"] + html[match.start(3):]
            updates.append("script[ld+json]")
    return html, updates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", type=Path,
                        help="Template HTML (or existing HTML when --inplace).")
    parser.add_argument("values", type=Path, nargs="?",
                        help="JSON file mapping placeholder names to strings. "
                             "Optional when --values-stdin is used.")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Output path. Defaults to stdout when omitted.")
    parser.add_argument("--allow-missing", action="store_true",
                        help="Leave unknown {{PLACEHOLDERS}} untouched.")
    parser.add_argument("--inplace", action="store_true",
                        help="Refresh metadata only on an existing index.html.")
    parser.add_argument("--values-stdin", action="store_true",
                        help="Read JSON values from stdin instead of a file.")
    args = parser.parse_args()

    if not args.template.is_file():
        print(f"error: not a file: {args.template}", file=sys.stderr)
        return 2

    if args.values_stdin:
        values = json.load(sys.stdin)
    else:
        if not args.values or not args.values.is_file():
            print("error: missing values file (or use --values-stdin)", file=sys.stderr)
            return 2
        values = json.loads(args.values.read_text(encoding="utf-8"))

    if not isinstance(values, dict):
        print("error: values must be a JSON object", file=sys.stderr)
        return 2

    text = args.template.read_text(encoding="utf-8")

    if args.inplace:
        rendered, updates = update_inplace(text, {k: str(v) for k, v in values.items()})
        if not updates:
            print("warning: no metadata fields matched; nothing changed.", file=sys.stderr)
        else:
            print(f"updated: {', '.join(updates)}", file=sys.stderr)
        rendered, missing = rendered, []
    else:
        rendered, missing = substitute(text, {k: str(v) for k, v in values.items()},
                                       args.allow_missing)
        if missing and not args.allow_missing:
            print(f"error: unresolved placeholders: {', '.join(sorted(set(missing)))}",
                  file=sys.stderr)
            return 1
        if missing:
            print(f"warning: unresolved placeholders kept verbatim: "
                  f"{', '.join(sorted(set(missing)))}", file=sys.stderr)

    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
