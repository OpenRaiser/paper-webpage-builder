#!/usr/bin/env python3
"""Extract a compact content inventory from a paper PDF.

Designed for `kind: pdf_with_assets` inputs where no LaTeX source exists.
The output mirrors `scan_paper.py` so the same downstream workflow applies:
title, authors, abstract, section headings, figures, table regions, links.

Backends, in order:
  1. PyMuPDF (`pip install pymupdf`) — preferred, gives layout + links.
  2. `pdftotext`/`pdfinfo` (poppler) fallback for text and metadata only.

If neither is available the script prints a clear error and exits 2.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

PLACEHOLDER_TITLE_HINTS = ("untitled", "microsoft word", "arxiv template")
SECTION_RE = re.compile(
    r"""^\s*(
        (?:\d+(?:\.\d+){0,3})\.?\s+[A-Z][^\n]{2,120}    # 1. / 1.2 Section Name
        |
        (?:Abstract|Introduction|Related\s+Work|Background|Method(?:ology)?|
           Approach|Experiments?|Results?|Discussion|Conclusion[s]?|
           Limitations?|References|Appendix(?:\s+[A-Z])?)\s*$
    )""",
    re.VERBOSE,
)
ABSTRACT_HEAD_RE = re.compile(r"^\s*Abstract\b[:.\s]*", re.IGNORECASE)
NEXT_HEAD_RE = re.compile(
    r"^(?:1\b|1\.\s+|Introduction|Keywords|Index Terms|CCS Concepts)\b",
    re.IGNORECASE | re.MULTILINE,
)
URL_RE = re.compile(r"https?://[^\s)>\]]+")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
WHITESPACE_RE = re.compile(r"\s+")


def truncate(value: str, limit: int) -> str:
    value = WHITESPACE_RE.sub(" ", value).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def have_pymupdf() -> bool:
    try:
        import fitz  # noqa: F401
    except Exception:
        return False
    return True


def first_page_text_pymupdf(pdf: Path) -> tuple[str, list[str], dict[str, str]]:
    import fitz

    with fitz.open(pdf) as doc:
        meta = {k: v for k, v in (doc.metadata or {}).items() if v}
        first = doc[0].get_text("text") if doc.page_count else ""
        all_text = "\n\n".join(page.get_text("text") for page in doc)
    return first, [all_text], meta


def first_page_text_poppler(pdf: Path) -> tuple[str, list[str], dict[str, str]]:
    if not shutil.which("pdftotext"):
        raise RuntimeError("Neither pymupdf nor pdftotext is available.")
    first = subprocess.run(
        ["pdftotext", "-layout", "-f", "1", "-l", "1", str(pdf), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    full = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    meta: dict[str, str] = {}
    if shutil.which("pdfinfo"):
        info = subprocess.run(
            ["pdfinfo", str(pdf)], check=True, capture_output=True, text=True
        ).stdout
        for line in info.splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                meta[key.strip().lower()] = value.strip()
    return first, [full], meta


def extract_title(first_page: str, meta: dict[str, str]) -> str:
    meta_title = (meta.get("title") or meta.get("Title") or "").strip()
    if meta_title and not any(h in meta_title.lower() for h in PLACEHOLDER_TITLE_HINTS):
        return truncate(meta_title, 240)

    lines = [line.rstrip() for line in first_page.splitlines() if line.strip()]
    if not lines:
        return ""
    # Take consecutive bold-ish-looking lines at the top: skip obvious arxiv/header noise.
    skip_prefixes = ("arxiv:", "preprint", "draft", "under review", "to appear")
    cleaned: list[str] = []
    for line in lines[:10]:
        low = line.strip().lower()
        if any(low.startswith(p) for p in skip_prefixes):
            continue
        if URL_RE.search(line) or EMAIL_RE.search(line):
            continue
        cleaned.append(line.strip())
        if len(cleaned) >= 3:
            break
    return truncate(" ".join(cleaned), 240) if cleaned else truncate(lines[0], 240)


def extract_authors(first_page: str) -> list[str]:
    """Heuristic: lines after the title that look like 'Name, Name, Name'."""
    lines = [line.strip() for line in first_page.splitlines() if line.strip()]
    candidates: list[str] = []
    seen_title = False
    for line in lines[:25]:
        if not seen_title:
            seen_title = True
            continue
        if ABSTRACT_HEAD_RE.match(line):
            break
        # Author rows tend to contain commas or 'and' and at least one capitalised pair.
        if EMAIL_RE.search(line):
            continue
        if "," in line or " and " in line.lower():
            tokens = re.split(r",|\band\b", line, flags=re.IGNORECASE)
            for tok in tokens:
                name = tok.strip(" *0123456789†‡§¶")
                if not name or len(name) > 80:
                    continue
                if name.lower() in {"abstract", "introduction"}:
                    continue
                if not re.search(r"[A-Za-z]", name):
                    continue
                # A name should have at least two letter-runs.
                if len(re.findall(r"[A-Za-zÀ-ɏ][\w'À-ɏ.-]+", name)) >= 2:
                    candidates.append(name)
        if len(candidates) >= 12:
            break
    # de-dup, keep order
    deduped: list[str] = []
    for c in candidates:
        if c not in deduped:
            deduped.append(c)
    return deduped


def extract_abstract(full_text: str) -> str:
    head = ABSTRACT_HEAD_RE.search(full_text)
    if not head:
        return ""
    tail = full_text[head.end():]
    stop = NEXT_HEAD_RE.search(tail)
    body = tail[: stop.start()] if stop else tail[:3000]
    return truncate(body, 1800)


def extract_sections(full_text: str) -> list[str]:
    seen: list[str] = []
    for line in full_text.splitlines():
        if SECTION_RE.match(line):
            cleaned = WHITESPACE_RE.sub(" ", line).strip(" .")
            if cleaned and cleaned not in seen:
                seen.append(cleaned)
    return seen


def extract_links(full_text: str) -> list[str]:
    urls: list[str] = []
    for url in URL_RE.findall(full_text):
        url = url.rstrip(".,);]>")
        if url not in urls:
            urls.append(url)
    return urls


def extract_figure_table_captions(full_text: str) -> tuple[list[str], list[str]]:
    figs: list[str] = []
    tabs: list[str] = []
    cap_re = re.compile(r"^\s*(Figure|Fig\.|Table|Tab\.)\s*([A-Za-z0-9.]+)[:.\s]+(.+)")
    for line in full_text.splitlines():
        match = cap_re.match(line)
        if not match:
            continue
        kind = match.group(1).lower()
        label = match.group(2).strip(".")
        body = truncate(match.group(3), 240)
        entry = f"{label}: {body}"
        if kind.startswith("fig"):
            if entry not in figs:
                figs.append(entry)
        else:
            if entry not in tabs:
                tabs.append(entry)
    return figs, tabs


def extract_image_objects(pdf: Path) -> list[str]:
    if not have_pymupdf():
        return []
    import fitz

    summaries: list[str] = []
    with fitz.open(pdf) as doc:
        for index, page in enumerate(doc, 1):
            for img in page.get_images(full=True):
                xref, _, width, height, *_ = img
                summaries.append(f"page {index}: xref={xref} {width}x{height}")
    return summaries


def emit(label: str, items: Iterable[str]) -> None:
    items = list(items)
    if not items:
        return
    print(f"{label}:")
    for item in items:
        print(f"- {item}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument(
        "--include-image-objects",
        action="store_true",
        help="List embedded raster images detected by PyMuPDF (debug aid).",
    )
    args = parser.parse_args()

    if not args.pdf.is_file():
        print(f"error: not a file: {args.pdf}", file=sys.stderr)
        return 2

    if have_pymupdf():
        first_page, full_pages, meta = first_page_text_pymupdf(args.pdf)
        backend = "pymupdf"
    else:
        try:
            first_page, full_pages, meta = first_page_text_poppler(args.pdf)
            backend = "poppler"
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            print(
                "hint: pip install pymupdf  (or install poppler-utils for pdftotext)",
                file=sys.stderr,
            )
            return 2

    full_text = "\n".join(full_pages)

    print(f"# PDF Inventory (backend: {backend})\n")

    title = extract_title(first_page, meta)
    if title:
        print(f"Title: {title}\n")

    authors = extract_authors(first_page)
    if authors:
        print("Authors:")
        for name in authors:
            print(f"- {name}")
        print()

    abstract = extract_abstract(full_text)
    if abstract:
        print("Abstract:")
        print(abstract)
        print()

    emit("Sections", extract_sections(full_text))
    figs, tabs = extract_figure_table_captions(full_text)
    emit("Figure captions", figs)
    emit("Table captions", tabs)

    emit("Links", extract_links(full_text))

    if args.include_image_objects:
        emit("Embedded images", extract_image_objects(args.pdf))

    if title == "" and not authors and not abstract:
        print(
            "warning: no title/authors/abstract recovered. PDF may be scanned; "
            "consider running OCR (e.g. `ocrmypdf`) before re-scanning.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
