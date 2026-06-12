#!/usr/bin/env python3
"""Check local asset references and (optionally) lint the webpage.

Default mode (`--mode links`): scan `src` / `href` / `data-figure` for missing
local files, exactly like the original behaviour.

Full mode (`--mode full`, alias `--full`): additionally check
- CSS `url(...)` references inside `<style>` and inline `style=` attributes,
- `srcset` candidate URLs (responsive images),
- `<source src>` (`<picture>`/`<video>`/`<audio>`) and `<video poster>`,
- `<link rel="preload" as="image|font|style|...">`,
- `<link rel="canonical">`, `<link rel="icon">`, `<link rel="manifest">`,
- `<meta property="og:image">` and `<meta name="twitter:image">`,
- internal `#fragment` references whose target id does not exist,
- duplicate ids in the document,
- `<img>` / `<iframe>` / `<input type="image">` missing accessible text.

Outputs human-readable lines by default, or JSON via `--json`.

Exit codes (both modes):
  0  no problems found
  1  at least one problem
  2  invalid argument or input
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ATTR_RE = re.compile(r"""(?:src|href|data-figure)=["']([^"']+)["']""")
CSS_URL_RE = re.compile(r"""url\(\s*['"]?([^'"\)]+)['"]?\s*\)""")
SRCSET_TOKEN_RE = re.compile(r"\s+\d+(?:\.\d+)?[wx]\s*$")


def is_local(value: str) -> bool:
    if not value:
        return False
    if value.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return False
    if value.startswith("#"):
        return False
    parsed = urlparse(value)
    return not parsed.scheme and not parsed.netloc


def strip_query_fragment(value: str) -> str:
    return unquote(value.split("#", 1)[0].split("?", 1)[0])


class WebpageInspector(HTMLParser):
    """Collect attributes, ids, fragments, and inline styles in a single pass."""

    REL_AS_FILE = {"image", "font", "style", "script", "fetch"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.local_assets: list[tuple[str, str, str]] = []  # (path, attr, tag)
        self.fragment_refs: list[str] = []  # ids referenced via #foo
        self.ids: list[str] = []  # collected id values (with line for duplicates)
        self.id_lines: dict[str, list[int]] = {}
        self.style_blocks: list[str] = []
        self.inline_styles: list[str] = []
        self.missing_alt: list[tuple[str, int]] = []
        self.external_urls: list[tuple[str, str, bool]] = []  # (url, tag, unverified)
        self.in_style = False
        self.style_buf: list[str] = []
        self.has_canonical = False
        self.has_og_image = False
        self.has_lang = False
        self.html_lang_value = ""
        self.title_present = False
        self._in_title = False

    def _line(self) -> int:
        return self.getpos()[0]

    def _record_attr(self, raw: str, attr: str, tag: str) -> None:
        self.local_assets.append((raw, attr, tag))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag == "html":
            self.has_lang = "lang" in attr_dict and bool(attr_dict["lang"])
            self.html_lang_value = attr_dict.get("lang", "")
        if tag == "title":
            self._in_title = True

        # IDs
        if "id" in attr_dict and attr_dict["id"]:
            ident = attr_dict["id"].strip()
            self.ids.append(ident)
            self.id_lines.setdefault(ident, []).append(self._line())

        # Inline styles
        if "style" in attr_dict and attr_dict["style"]:
            self.inline_styles.append(attr_dict["style"])

        # Fragment hrefs and other hrefs
        if "href" in attr_dict:
            href = attr_dict["href"]
            if href.startswith("#") and len(href) > 1:
                self.fragment_refs.append(href[1:])
            elif tag == "link":
                # <link> is handled below so it can split icon/canonical/preload
                # into specific buckets without duplicating the generic href.
                pass
            elif is_local(href):
                self._record_attr(href, "href", tag)
            # Collect external URLs for optional reachability check
            parsed_href = urlparse(href)
            if parsed_href.scheme in ("http", "https") and parsed_href.netloc:
                unverified = "data-unverified" in attr_dict
                self.external_urls.append((href, tag, unverified))
            if tag == "link":
                rel = attr_dict.get("rel", "").lower().split()
                if "canonical" in rel:
                    self.has_canonical = True
                if "preload" in rel and attr_dict.get("as", "").lower() in self.REL_AS_FILE:
                    if is_local(href):
                        self._record_attr(href, "href[preload]", tag)
                elif rel and any(r in rel for r in ("icon", "manifest", "stylesheet", "apple-touch-icon")):
                    if is_local(href):
                        self._record_attr(href, f"href[{rel[0]}]", tag)

        # Generic local src
        if "src" in attr_dict and attr_dict["src"]:
            src = attr_dict["src"]
            if is_local(src):
                self._record_attr(src, "src", tag)
            else:
                parsed_src = urlparse(src)
                if parsed_src.scheme in ("http", "https") and parsed_src.netloc:
                    unverified = "data-unverified" in attr_dict
                    self.external_urls.append((src, tag, unverified))

        # Video poster
        if "poster" in attr_dict and attr_dict["poster"] and is_local(attr_dict["poster"]):
            self._record_attr(attr_dict["poster"], "poster", tag)

        # data-figure (custom convention from this skill)
        if "data-figure" in attr_dict and attr_dict["data-figure"]:
            value = attr_dict["data-figure"]
            if is_local(value):
                self._record_attr(value, "data-figure", tag)

        # srcset (img / source)
        if "srcset" in attr_dict and attr_dict["srcset"]:
            for chunk in attr_dict["srcset"].split(","):
                token = chunk.strip()
                if not token:
                    continue
                token = SRCSET_TOKEN_RE.sub("", token).strip()
                if is_local(token):
                    self._record_attr(token, "srcset", tag)

        # og:image / twitter:image
        if tag == "meta":
            prop = (attr_dict.get("property") or "").lower()
            name = (attr_dict.get("name") or "").lower()
            content = attr_dict.get("content", "")
            if prop in {"og:image", "og:image:secure_url"} or name in {"twitter:image"}:
                if content:
                    self.has_og_image = True
                    if is_local(content):
                        self._record_attr(content, prop or name, tag)

        # Accessible text on common visual tags
        if tag == "img":
            alt = attr_dict.get("alt")
            if alt is None or not alt.strip():
                # role="presentation" or aria-hidden="true" exempts the alt requirement
                if (attr_dict.get("role", "").lower() != "presentation"
                        and attr_dict.get("aria-hidden", "").lower() != "true"):
                    self.missing_alt.append(("img", self._line()))
        elif tag == "iframe":
            if not attr_dict.get("title", "").strip():
                self.missing_alt.append(("iframe", self._line()))
        elif tag == "input" and attr_dict.get("type", "").lower() == "image":
            if not attr_dict.get("alt", "").strip():
                self.missing_alt.append(("input[image]", self._line()))

        if tag == "style":
            self.in_style = True
            self.style_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "style" and self.in_style:
            self.style_blocks.append("".join(self.style_buf))
            self.style_buf = []
            self.in_style = False
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_style:
            self.style_buf.append(data)
        if self._in_title and data.strip():
            self.title_present = True


def collect_css_assets(blocks: list[str]) -> list[str]:
    found: list[str] = []
    for block in blocks:
        for match in CSS_URL_RE.findall(block):
            ref = match.strip()
            if not ref or ref.startswith("data:") or not is_local(ref):
                continue
            found.append(ref)
    return found


def resolve_local(root: Path, raw: str) -> tuple[str, Path | None]:
    """Return (status, path).

    status is one of:
      - "ok":       path is inside root (caller still checks existence)
      - "escape":   path resolves outside root (path-traversal via .. or /abs)
      - "empty":    raw was empty after stripping query/fragment
    """
    path_part = strip_query_fragment(raw)
    if not path_part:
        return ("empty", None)
    target = (root / path_part).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return ("escape", target)
    return ("ok", target)


def lint_html(html_path: Path, full: bool, check_external: bool = False) -> dict:
    text = html_path.read_text(encoding="utf-8", errors="ignore")
    inspector = WebpageInspector()
    inspector.feed(text)
    inspector.close()

    root = html_path.parent.resolve()

    issues: list[dict] = []

    # --- 1. local asset existence (always on) ----------------------------------
    seen: set[tuple[str, str]] = set()
    for raw, attr, tag in inspector.local_assets:
        if "${" in raw:
            continue
        key = (raw, attr)
        if key in seen:
            continue
        seen.add(key)
        status, target = resolve_local(root, raw)
        if status == "escape":
            issues.append(
                {"kind": "path_escape", "ref": raw, "attr": attr, "tag": tag,
                 "resolved": str(target), "severity": "warning"}
            )
            continue
        if status == "empty":
            continue
        if target is None or not target.exists():
            issues.append(
                {"kind": "missing_asset", "ref": raw, "attr": attr, "tag": tag,
                 "severity": "error"}
            )

    # Legacy ATTR_RE fallback so callers relying on the old behaviour (text
    # inside non-element contexts, e.g. JS template strings) still get
    # the same coverage. Skip refs already reported by the structured pass.
    already_missing = {item["ref"] for item in issues if item["kind"] == "missing_asset"}
    already_escaped = {item["ref"] for item in issues if item["kind"] == "path_escape"}
    for raw in sorted(set(ATTR_RE.findall(text))):
        if "${" in raw or not is_local(raw) or raw.startswith("#"):
            continue
        if raw in already_missing or raw in already_escaped:
            continue
        if raw in {item[0] for item in inspector.local_assets}:
            continue
        status, target = resolve_local(root, raw)
        if status == "escape":
            issues.append(
                {"kind": "path_escape", "ref": raw, "attr": "src/href/data-figure",
                 "tag": "?", "resolved": str(target), "severity": "warning"}
            )
            already_escaped.add(raw)
            continue
        if status == "empty":
            continue
        if target is None or not target.exists():
            issues.append(
                {"kind": "missing_asset", "ref": raw, "attr": "src/href/data-figure",
                 "tag": "?", "severity": "error"}
            )
            already_missing.add(raw)

    if not full:
        return _summarize(issues, html_path)

    # --- 2. CSS url(...) inside <style> blocks --------------------------------
    for ref in collect_css_assets(inspector.style_blocks):
        status, target = resolve_local(root, ref)
        if status == "escape":
            issues.append(
                {"kind": "path_escape", "ref": ref, "attr": "css.url",
                 "tag": "style", "resolved": str(target), "severity": "warning"}
            )
            continue
        if status == "empty":
            continue
        if target is None or not target.exists():
            issues.append(
                {"kind": "missing_asset", "ref": ref, "attr": "css.url",
                 "tag": "style", "severity": "error"}
            )

    # --- 3. inline style= url(...) --------------------------------------------
    for ref in collect_css_assets(inspector.inline_styles):
        status, target = resolve_local(root, ref)
        if status == "escape":
            issues.append(
                {"kind": "path_escape", "ref": ref, "attr": "style.url",
                 "tag": "(inline)", "resolved": str(target), "severity": "warning"}
            )
            continue
        if status == "empty":
            continue
        if target is None or not target.exists():
            issues.append(
                {"kind": "missing_asset", "ref": ref, "attr": "style.url",
                 "tag": "(inline)", "severity": "error"}
            )

    # --- 4. fragment ref → id existence ---------------------------------------
    id_set = set(inspector.ids)
    for frag in sorted(set(inspector.fragment_refs)):
        if frag in id_set:
            continue
        # Allow common reserved fragments (top-of-page).
        if frag.lower() in {"top", "main", "content"} and frag in id_set:
            continue
        issues.append(
            {"kind": "broken_fragment", "ref": f"#{frag}", "severity": "error"}
        )

    # --- 5. duplicate ids -----------------------------------------------------
    for ident, lines in inspector.id_lines.items():
        if len(lines) > 1:
            issues.append(
                {"kind": "duplicate_id", "id": ident, "lines": lines,
                 "severity": "error"}
            )

    # --- 6. accessibility heads-up --------------------------------------------
    for tag, line in inspector.missing_alt:
        issues.append(
            {"kind": "missing_accessible_text", "tag": tag, "line": line,
             "severity": "warning"}
        )

    # --- 7. document-level metadata reminders ---------------------------------
    if not inspector.title_present:
        issues.append({"kind": "missing_title", "severity": "warning"})
    if not inspector.has_lang:
        issues.append({"kind": "missing_html_lang", "severity": "warning"})
    if not inspector.has_canonical:
        issues.append(
            {"kind": "missing_canonical", "severity": "info",
             "note": "<link rel=\"canonical\"> is recommended for project pages"}
        )
    if not inspector.has_og_image:
        issues.append(
            {"kind": "missing_og_image", "severity": "info",
             "note": "no og:image / twitter:image found; social previews will be blank"}
        )

    # --- 8. external URL reachability (optional) ------------------------------
    if check_external and inspector.external_urls:
        issues.extend(check_external_urls(inspector.external_urls))

    return _summarize(issues, html_path, lang=inspector.html_lang_value)


def check_external_urls(
    urls: list[tuple[str, str, bool]], timeout: float = 5.0, max_requests: int = 20
) -> list[dict]:
    """HEAD-request external URLs and report failures.

    Returns a list of issue dicts for unreachable or unverified URLs.
    Deduplicates by URL before requesting. Caps at max_requests to avoid
    blocking the validation pipeline on slow networks.
    """
    issues: list[dict] = []
    seen: set[str] = set()
    request_count = 0
    for url, tag, unverified in urls:
        if url in seen:
            continue
        seen.add(url)
        if unverified:
            issues.append({
                "kind": "unverified_external_url",
                "ref": url,
                "tag": tag,
                "severity": "warning",
                "note": "URL marked data-unverified; confirm reachability before publishing.",
            })
            continue
        if request_count >= max_requests:
            issues.append({
                "kind": "external_check_limit",
                "severity": "info",
                "note": f"Stopped after {max_requests} external requests; remaining URLs unchecked.",
            })
            break
        request_count += 1
        try:
            req = Request(url, method="HEAD", headers={"User-Agent": "paper-webpage-builder/0.6"})
            resp = urlopen(req, timeout=timeout)
            code = resp.status
            if code >= 400:
                issues.append({
                    "kind": "external_url_error",
                    "ref": url,
                    "tag": tag,
                    "status": code,
                    "severity": "error",
                })
        except HTTPError as exc:
            issues.append({
                "kind": "external_url_error",
                "ref": url,
                "tag": tag,
                "status": exc.code,
                "severity": "error" if exc.code < 500 else "warning",
            })
        except (URLError, OSError, TimeoutError):
            issues.append({
                "kind": "external_url_timeout",
                "ref": url,
                "tag": tag,
                "severity": "warning",
                "note": "Connection failed or timed out.",
            })
    return issues


def _summarize(issues: list[dict], html_path: Path, lang: str = "") -> dict:
    error_count = sum(1 for i in issues if i.get("severity") == "error")
    warning_count = sum(1 for i in issues if i.get("severity") == "warning")
    info_count = sum(1 for i in issues if i.get("severity") == "info")
    return {
        "html": str(html_path),
        "lang": lang,
        "issues": issues,
        "summary": {
            "errors": error_count,
            "warnings": warning_count,
            "info": info_count,
        },
    }


def render_text(report: dict, mode: str) -> str:
    lines: list[str] = []
    if mode == "links":
        missing = [i for i in report["issues"] if i["kind"] == "missing_asset"]
        if not missing:
            return "All local assets referenced by src/href/data-figure exist.\n"
        lines.append("Missing local assets:")
        for item in missing:
            lines.append(f"- {item['ref']}")
        return "\n".join(lines) + "\n"

    if not report["issues"]:
        return f"No problems found in {report['html']}.\n"
    grouped: dict[str, list[dict]] = {}
    for item in report["issues"]:
        grouped.setdefault(item["kind"], []).append(item)
    for kind, items in grouped.items():
        lines.append(f"[{kind}] ({len(items)})")
        for item in items:
            severity = item.get("severity", "?")
            ref = item.get("ref") or item.get("id") or item.get("tag") or item.get("note") or ""
            extra = ""
            if "lines" in item:
                extra = f" lines={item['lines']}"
            elif "line" in item:
                extra = f" line={item['line']}"
            lines.append(f"  - [{severity}] {ref}{extra}")
    s = report["summary"]
    lines.append(f"summary: errors={s['errors']} warnings={s['warnings']} info={s['info']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument(
        "--mode",
        choices=("links", "full"),
        default="links",
        help="links: original asset existence check; full: links + accessibility + metadata + fragments.",
    )
    parser.add_argument("--full", action="store_true",
                        help="Alias for --mode full.")
    parser.add_argument("--json", action="store_true",
                        help="Emit a JSON report instead of text.")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as failures (exit 1 on any warning).")
    parser.add_argument("--check-external", action="store_true",
                        help="HEAD-request external URLs to verify reachability (max 20, 5s timeout).")
    args = parser.parse_args()

    if not args.html.is_file():
        print(f"error: not a file: {args.html}", file=sys.stderr)
        return 2

    mode = "full" if args.full else args.mode
    report = lint_html(args.html, full=(mode == "full"), check_external=args.check_external)

    if args.json:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_text(report, mode))

    s = report["summary"]
    if s["errors"] > 0:
        return 1
    if args.strict and s["warnings"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
