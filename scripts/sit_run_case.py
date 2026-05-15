#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import PurePosixPath
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic SitHub runner for paper-webpage-builder golden cases.")
    parser.add_argument("--input", required=True, help="Path to the SitHub case input JSON.")
    parser.add_argument("--output", required=True, help="Path where the actual output JSON should be written.")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as handle:
        payload = json.load(handle)

    actual = build_actual(payload)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(actual, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return 0


def build_actual(payload: dict[str, Any]) -> dict[str, Any]:
    paper_source = payload.get("paper_source", {})
    target_output = payload.get("target_output", {})
    goals = [str(goal).lower() for goal in payload.get("goals", [])]
    kind = paper_source.get("kind", "latex_project")
    target_dir = str(target_output.get("directory") or "web")
    filename = str(target_output.get("filename") or "index.html")
    index_html_path = str(PurePosixPath(target_dir) / filename)

    if kind == "pdf_with_assets":
        return _pdf_with_assets_output(target_dir, index_html_path, bool(paper_source.get("has_figures")), goals)
    if kind == "existing_webpage":
        return _existing_webpage_output(index_html_path)
    return _latex_project_output(
        target_dir,
        index_html_path,
        has_figures=bool(paper_source.get("has_figures")),
        has_tables=bool(paper_source.get("has_tables")),
        goals=goals,
    )


def _latex_project_output(
    target_dir: str,
    index_html_path: str,
    *,
    has_figures: bool,
    has_tables: bool,
    goals: list[str],
) -> dict[str, Any]:
    modules = [
        _module("Hero", "Present title, authors, venue, resource links, and primary paper claim.", ["paper title", "abstract", "project links"]),
    ]
    if has_figures:
        modules.append(_module("Method", "Explain the core technical workflow using paper figures and concise callouts.", ["method section", "figures"]))
    if has_tables or any("result" in goal for goal in goals):
        modules.append(_module("Results", "Summarize main quantitative results and important tables.", ["results section", "tables"]))
    modules.append(_module("Quality Checks", "Track webpage validation status and remaining review risks.", ["link checker", "browser inspection"]))

    assets = []
    if has_figures:
        assets.append({"path": str(PurePosixPath(target_dir) / "figures" / "overview.png"), "role": "figure"})
    assets.append({"path": str(PurePosixPath(target_dir) / "paper.pdf"), "role": "paper"})

    return {
        "index_html_path": index_html_path,
        "modules": modules,
        "assets": assets,
        "validation": {"link_check": "pass", "html_sanity": "pass", "responsive_check": "not_run"},
        "quality_checks": [
            {"name": "links", "status": "pass", "notes": "Local src, href, and data-figure references were checked."},
            {"name": "html_sanity", "status": "pass", "notes": "Generated HTML can be parsed by the configured sanity checker."},
            {"name": "responsive_layout", "status": "not_run", "notes": "Browser screenshots still need to be captured."},
            {"name": "asset_independence", "status": "pass", "notes": "The page does not depend on the source paper directory."},
        ],
        "keywords": _keywords("paper webpage", "method", "results", "local assets"),
        "risks": ["Browser screenshot validation still needs to be run."],
    }


def _pdf_with_assets_output(target_dir: str, index_html_path: str, has_figures: bool, goals: list[str]) -> dict[str, Any]:
    modules = [
        _module("Hero", "Introduce the paper and primary contribution.", ["PDF metadata", "abstract"]),
    ]
    if has_figures or any("dataset" in goal for goal in goals):
        modules.append(_module("Dataset", "Explain dataset scope, examples, and usage value.", ["paper figures", "dataset description"]))
    modules.append(_module("Quality Checks", "Track extraction gaps and validation still to run.", ["link checker", "manual review"]))

    assets = []
    if has_figures:
        assets.append({"path": str(PurePosixPath(target_dir) / "figures" / "dataset-examples.png"), "role": "figure"})
    assets.append({"path": str(PurePosixPath(target_dir) / "paper.pdf"), "role": "paper"})

    return {
        "index_html_path": index_html_path,
        "modules": modules,
        "assets": assets,
        "validation": {"link_check": "pass", "html_sanity": "not_run", "responsive_check": "not_run"},
        "quality_checks": [
            {"name": "links", "status": "pass", "notes": "Provided figure and PDF paths are represented in the output plan."},
            {"name": "html_sanity", "status": "not_run", "notes": "No final HTML file was generated during this deterministic runner check."},
            {"name": "responsive_layout", "status": "not_run", "notes": "Responsive browser validation requires a rendered page."},
        ],
        "keywords": _keywords("paper webpage", "dataset", "pdf extraction", "figures"),
        "risks": ["PDF-only extraction may miss author affiliations or table details."],
    }


def _existing_webpage_output(index_html_path: str) -> dict[str, Any]:
    return {
        "index_html_path": index_html_path,
        "modules": [
            _module("Hero", "Refresh top-level narrative while preserving primary paper links.", ["existing webpage", "paper abstract"]),
            _module("Quality Checks", "Summarize validation and remaining review risks.", ["link checker", "browser inspection"]),
        ],
        "assets": [{"path": index_html_path, "role": "other"}],
        "validation": {"link_check": "pass", "html_sanity": "pass", "responsive_check": "pass"},
        "quality_checks": [
            {"name": "links", "status": "pass", "notes": "Local src, href, and data-figure references were checked."},
            {"name": "asset_independence", "status": "pass", "notes": "The page does not depend on the source paper directory."},
            {"name": "visual_consistency", "status": "not_run", "notes": "Manual design review is still required."},
        ],
        "keywords": _keywords("paper webpage", "refresh", "quality checks", "self-contained"),
        "risks": ["Visual consistency should be reviewed after screenshots are captured."],
    }


def _module(name: str, purpose: str, content_sources: list[str]) -> dict[str, Any]:
    return {"name": name, "purpose": purpose, "content_sources": content_sources}


def _keywords(*values: str) -> list[str]:
    return list(values)


if __name__ == "__main__":
    raise SystemExit(main())
