#!/usr/bin/env python3
"""Build SEO + Schema.org metadata for a paper webpage.

Inputs (any subset; all optional except --title):
  --title          page title (paper title is fine)
  --description    one-line summary (≤ 200 chars recommended)
  --canonical      absolute canonical URL
  --og-image       absolute or root-relative URL to the social card
  --lang           BCP-47 tag, defaults to "en"
  --author         repeatable, one author per flag
  --published      ISO date (YYYY-MM-DD) for datePublished
  --doi            optional DOI
  --arxiv          arXiv id (e.g. 2401.12345); auto-fills ScholarlyArticle.url
  --paper-pdf      absolute or root-relative URL to the paper PDF
  --keyword        repeatable, one keyword per flag

Outputs (default `--format render-values`, JSON for render_template.py):
  TITLE, DESCRIPTION, CANONICAL_URL, OG_IMAGE, LANG, JSONLD

Other formats:
  --format meta-block    raw <meta>/<link>/<script> block to drop into <head>
  --format jsonld        only the JSON-LD object

`--inplace <existing.html>` mode runs render_template.py-style head updates
and the ScholarlyArticle block in one shot, so the LLM does not need a
two-step rendering for refresh-only tasks.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def build_jsonld(args: argparse.Namespace) -> dict:
    payload: dict = {
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "headline": args.title,
    }
    if args.description:
        payload["abstract"] = args.description
    if args.author:
        payload["author"] = [{"@type": "Person", "name": name} for name in args.author]
    if args.published:
        payload["datePublished"] = args.published
    if args.canonical:
        payload["url"] = args.canonical
    if args.og_image:
        payload["image"] = args.og_image
    if args.doi:
        payload["sameAs"] = payload.get("sameAs", []) + [f"https://doi.org/{args.doi}"]
        payload["identifier"] = {"@type": "PropertyValue", "propertyID": "doi",
                                 "value": args.doi}
    if args.arxiv:
        payload["sameAs"] = payload.get("sameAs", []) + [f"https://arxiv.org/abs/{args.arxiv}"]
        payload.setdefault("identifier", {"@type": "PropertyValue", "propertyID": "arxiv",
                                          "value": args.arxiv})
    if args.paper_pdf:
        payload["associatedMedia"] = [{
            "@type": "MediaObject",
            "contentUrl": args.paper_pdf,
            "encodingFormat": "application/pdf",
        }]
    if args.keyword:
        payload["keywords"] = ", ".join(args.keyword)
    return payload


def build_meta_block(args: argparse.Namespace, jsonld: dict) -> str:
    """Return a head fragment ready for copy-paste."""
    def esc(value: str) -> str:
        return (value.replace("&", "&amp;").replace("\"", "&quot;")
                     .replace("<", "&lt;").replace(">", "&gt;"))

    lines: list[str] = [f'<title>{esc(args.title)}</title>']
    if args.description:
        lines.append(f'<meta name="description" content="{esc(args.description)}" />')
    if args.canonical:
        lines.append(f'<link rel="canonical" href="{esc(args.canonical)}" />')
    lines.append('<meta property="og:type" content="article" />')
    lines.append(f'<meta property="og:title" content="{esc(args.title)}" />')
    if args.description:
        lines.append(f'<meta property="og:description" content="{esc(args.description)}" />')
    if args.og_image:
        lines.append(f'<meta property="og:image" content="{esc(args.og_image)}" />')
    if args.canonical:
        lines.append(f'<meta property="og:url" content="{esc(args.canonical)}" />')
    lines.append('<meta name="twitter:card" content="summary_large_image" />')
    lines.append(f'<meta name="twitter:title" content="{esc(args.title)}" />')
    if args.description:
        lines.append(f'<meta name="twitter:description" content="{esc(args.description)}" />')
    if args.og_image:
        lines.append(f'<meta name="twitter:image" content="{esc(args.og_image)}" />')
    lines.append(
        '<script type="application/ld+json">'
        + json.dumps(jsonld, ensure_ascii=False) + '</script>'
    )
    return "\n".join(lines) + "\n"


def render_values(args: argparse.Namespace, jsonld: dict) -> dict:
    return {
        "LANG": args.lang or "en",
        "TITLE": args.title,
        "DESCRIPTION": args.description or "",
        "CANONICAL_URL": args.canonical or "",
        "OG_IMAGE": args.og_image or "",
        "JSONLD": json.dumps(jsonld, ensure_ascii=False),
    }


def run_inplace(html_path: Path, values: dict, render_template: Path) -> int:
    if not render_template.is_file():
        print(f"error: render_template.py not found at {render_template}", file=sys.stderr)
        return 2
    proc = subprocess.run(
        [sys.executable, str(render_template), str(html_path), "--inplace",
         "--values-stdin", "-o", str(html_path)],
        input=json.dumps(values), capture_output=True, text=True,
    )
    sys.stderr.write(proc.stderr)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--canonical", default="")
    parser.add_argument("--og-image", default="")
    parser.add_argument("--lang", default="en")
    parser.add_argument("--author", action="append", default=[])
    parser.add_argument("--published", default="")
    parser.add_argument("--doi", default="")
    parser.add_argument("--arxiv", default="")
    parser.add_argument("--paper-pdf", default="")
    parser.add_argument("--keyword", action="append", default=[])
    parser.add_argument(
        "--format",
        choices=("render-values", "meta-block", "jsonld"),
        default="render-values",
    )
    parser.add_argument("--inplace", type=Path, default=None,
                        help="Refresh metadata in-place on an existing index.html.")
    parser.add_argument("--render-template", type=Path,
                        default=Path(__file__).parent / "render_template.py",
                        help="Path to render_template.py (used by --inplace).")
    args = parser.parse_args()

    jsonld = build_jsonld(args)
    values = render_values(args, jsonld)

    if args.inplace:
        if not args.inplace.is_file():
            print(f"error: not a file: {args.inplace}", file=sys.stderr)
            return 2
        return run_inplace(args.inplace, values, args.render_template)

    if args.format == "render-values":
        json.dump(values, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    elif args.format == "meta-block":
        sys.stdout.write(build_meta_block(args, jsonld))
    else:
        json.dump(jsonld, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
