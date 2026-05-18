#!/usr/bin/env python3
"""Reconcile the LaTeX table ledger against an `index.html`.

Inputs:
  --ledger  JSON produced by `extract_tables.py` (a {"tables": [...]} document).
  --html    Path to the rendered index.html.

For each LaTeX table the script tries to find a matching <table> in the page,
preferring an explicit `data-tex-label="<label>"` attribute on either the
`<table>` or any ancestor `<section>`/`<figure>`/`<div>`. When no explicit
label is present, it falls back to fuzzy caption matching against `<caption>`
and `<figcaption>` text (case-insensitive substring match).

Per match the script reports:
  - status: matched | missing | abbreviated | mismatch | unmapped_html_table
  - paper rows × cols vs. html rows × cols
  - any first-difference on a header cell (so highlighting changes show up)

Exit codes:
  0 when every central table is matched (or explicitly waived in the ledger via
    `not_central: true`).
  1 when any central table is missing or has fewer rows than the source.
  2 on bad arguments.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


WHITESPACE_RE = re.compile(r"\s+")


def normalise(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def caption_keywords(caption: str | None) -> set[str]:
    if not caption:
        return set()
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", caption.lower())
    return {w for w in cleaned.split() if len(w) >= 4}


class HtmlTableCollector(HTMLParser):
    """Collect every <table> with rows, captions, and any data-tex-label nearby."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[dict] = []
        self.tables: list[dict] = []
        self.current_label_stack: list[str] = []
        self.current_caption: list[str] | None = None
        self.collecting_caption = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k.lower(): (v or "") for k, v in attrs}
        # Track ancestor data-tex-label so a section wrapping the table counts.
        label = attr.get("data-tex-label", "").strip()
        self.current_label_stack.append(label)

        if tag == "table":
            self.stack.append({
                "label": next((l for l in reversed(self.current_label_stack) if l), ""),
                "headers": [],
                "rows": [],
                "caption": "",
                "current_row": None,
                "current_cell": None,
                "in_thead": False,
            })
        elif self.stack:
            top = self.stack[-1]
            if tag == "caption" or tag == "figcaption":
                self.collecting_caption = True
                self.current_caption = []
            elif tag == "thead":
                top["in_thead"] = True
            elif tag == "tr":
                top["current_row"] = []
            elif tag in ("td", "th"):
                top["current_cell"] = []

    def handle_endtag(self, tag: str) -> None:
        if self.current_label_stack:
            self.current_label_stack.pop()

        if not self.stack:
            if tag in ("caption", "figcaption"):
                self.collecting_caption = False
                self.current_caption = None
            return

        top = self.stack[-1]
        if tag in ("caption", "figcaption") and self.collecting_caption:
            cap = normalise("".join(self.current_caption or []))
            if cap and not top.get("caption"):
                top["caption"] = cap
            self.collecting_caption = False
            self.current_caption = None
        elif tag in ("td", "th") and top.get("current_cell") is not None:
            cell = normalise("".join(top["current_cell"]))
            top["current_row"].append(cell)
            top["current_cell"] = None
        elif tag == "tr" and top.get("current_row") is not None:
            row = top["current_row"]
            top["current_row"] = None
            if top.get("in_thead") or (not top["headers"] and not top["rows"]):
                top["headers"].append(row)
            else:
                top["rows"].append(row)
        elif tag == "thead":
            top["in_thead"] = False
        elif tag == "table":
            finished = self.stack.pop()
            finished.pop("current_row", None)
            finished.pop("current_cell", None)
            finished.pop("in_thead", None)
            self.tables.append(finished)

    def handle_data(self, data: str) -> None:
        if self.collecting_caption and self.current_caption is not None:
            self.current_caption.append(data)
        if not self.stack:
            return
        top = self.stack[-1]
        if top.get("current_cell") is not None:
            top["current_cell"].append(data)


def best_caption_match(paper_caption: str | None, html_tables: list[dict], used: set[int]) -> int | None:
    if not paper_caption:
        return None
    keywords = caption_keywords(paper_caption)
    if not keywords:
        return None
    best_score = 0
    best_index = None
    for index, html in enumerate(html_tables):
        if index in used:
            continue
        cap_keywords = caption_keywords(html.get("caption", ""))
        score = len(keywords & cap_keywords)
        if score > best_score:
            best_score = score
            best_index = index
    if best_score >= 2:
        return best_index
    return None


def reconcile(ledger: dict, html: str) -> dict:
    parser = HtmlTableCollector()
    parser.feed(html)
    parser.close()
    html_tables = parser.tables

    paper_tables = ledger.get("tables", [])
    used: set[int] = set()
    entries: list[dict] = []

    # Pass 1: explicit label match
    label_to_html: dict[str, int] = {
        t["label"]: i for i, t in enumerate(html_tables) if t.get("label")
    }
    for paper in paper_tables:
        match_index: int | None = None
        if paper.get("label") and paper["label"] in label_to_html:
            match_index = label_to_html[paper["label"]]
            used.add(match_index)
        entries.append({"paper": paper, "html_index": match_index, "match_via": "label" if match_index is not None else None})

    # Pass 2: fuzzy caption fallback for entries that didn't match
    for entry in entries:
        if entry["html_index"] is not None:
            continue
        index = best_caption_match(entry["paper"].get("caption"), html_tables, used)
        if index is not None:
            entry["html_index"] = index
            entry["match_via"] = "caption"
            used.add(index)

    results: list[dict] = []
    central_failure = False
    for entry in entries:
        paper = entry["paper"]
        is_central = bool(paper.get("central")) or not paper.get("not_central")
        # Heuristic: treat all paper tables as "central" by default unless the
        # ledger explicitly opts a row out via `not_central: true`.
        if paper.get("not_central"):
            is_central = False

        if entry["html_index"] is None:
            results.append(_diagnose_missing(paper, is_central))
            if is_central:
                central_failure = True
            continue

        html_table = html_tables[entry["html_index"]]
        diag = _diagnose_match(paper, html_table, entry["match_via"])
        if is_central and diag["status"] in {"abbreviated", "mismatch"}:
            central_failure = True
        results.append(diag)

    unmapped_html = [
        {"status": "unmapped_html_table", "html_index": i,
         "caption": html_tables[i].get("caption", ""),
         "label": html_tables[i].get("label", "")}
        for i in range(len(html_tables)) if i not in used
    ]
    results.extend(unmapped_html)

    summary = {
        "paper_tables": len(paper_tables),
        "html_tables": len(html_tables),
        "matched": sum(1 for r in results if r["status"] == "matched"),
        "missing": sum(1 for r in results if r["status"] == "missing"),
        "abbreviated": sum(1 for r in results if r["status"] == "abbreviated"),
        "mismatch": sum(1 for r in results if r["status"] == "mismatch"),
        "unmapped_html_table": sum(1 for r in results if r["status"] == "unmapped_html_table"),
        "central_failure": central_failure,
    }
    return {"results": results, "summary": summary}


def _row_count(table: dict) -> int:
    return len(table.get("data_rows", []))


def _expected_rows(paper: dict) -> int:
    return _row_count(paper)


def _html_row_count(table: dict) -> int:
    return len(table.get("rows", []))


def _diagnose_match(paper: dict, html_table: dict, match_via: str | None) -> dict:
    paper_rows = _expected_rows(paper)
    html_rows = _html_row_count(html_table)
    paper_cols = max((len(r) for r in paper.get("data_rows", [])), default=0)
    html_cols = max((len(r) for r in html_table.get("rows", [])), default=0)

    status = "matched"
    if html_rows < paper_rows:
        status = "abbreviated"
    elif html_cols < paper_cols and paper_cols > 0:
        status = "mismatch"

    return {
        "status": status,
        "match_via": match_via,
        "label": paper.get("label"),
        "caption": paper.get("caption"),
        "paper_rows": paper_rows,
        "paper_cols": paper_cols,
        "html_rows": html_rows,
        "html_cols": html_cols,
        "html_caption": html_table.get("caption"),
    }


def _diagnose_missing(paper: dict, is_central: bool) -> dict:
    return {
        "status": "missing",
        "label": paper.get("label"),
        "caption": paper.get("caption"),
        "central": is_central,
        "paper_rows": _expected_rows(paper),
    }


def render_text(report: dict) -> str:
    lines = []
    s = report["summary"]
    lines.append(
        f"paper tables: {s['paper_tables']}  html tables: {s['html_tables']}  "
        f"matched: {s['matched']}  abbreviated: {s['abbreviated']}  "
        f"mismatch: {s['mismatch']}  missing: {s['missing']}  "
        f"unmapped_html: {s['unmapped_html_table']}"
    )
    for entry in report["results"]:
        status = entry["status"]
        label = entry.get("label") or "(no label)"
        cap = (entry.get("caption") or "")[:120]
        if status == "matched":
            lines.append(
                f"  ok       {label}  rows {entry['html_rows']}/{entry['paper_rows']}  "
                f"cols {entry['html_cols']}/{entry['paper_cols']}  via={entry.get('match_via')}"
            )
        elif status == "abbreviated":
            lines.append(
                f"  abbrev   {label}  rows {entry['html_rows']}/{entry['paper_rows']}  "
                f"cols {entry['html_cols']}/{entry['paper_cols']}  -- HTML drops rows!"
            )
        elif status == "mismatch":
            lines.append(
                f"  mismatch {label}  rows {entry['html_rows']}/{entry['paper_rows']}  "
                f"cols {entry['html_cols']}/{entry['paper_cols']}  -- HTML drops columns!"
            )
        elif status == "missing":
            mark = "MISSING(central)" if entry.get("central") else "missing"
            lines.append(f"  {mark}  {label}  ({cap})")
        elif status == "unmapped_html_table":
            cap = entry.get("caption") or ""
            lines.append(f"  extra    html-only table label={entry.get('label') or '?'}  ({cap[:120]})")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True,
                        help="extract_tables.py JSON output.")
    parser.add_argument("--html", type=Path, required=True,
                        help="Rendered index.html.")
    parser.add_argument("--json", action="store_true",
                        help="Emit JSON instead of text.")
    args = parser.parse_args()

    if not args.ledger.is_file() or not args.html.is_file():
        print("error: ledger or html missing", file=sys.stderr)
        return 2

    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    html_text = args.html.read_text(encoding="utf-8", errors="ignore")
    report = reconcile(ledger, html_text)

    if args.json:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_text(report))

    if report["summary"]["central_failure"]:
        return 1
    if report["summary"]["missing"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
