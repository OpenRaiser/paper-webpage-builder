#!/usr/bin/env python3
"""Browser-level table fit check for generated paper webpages.

This check catches visual failures that static HTML lint cannot see:
- table boxes spilling outside their white/card visual container;
- table/cell content clipped by overflow hidden/clip;
- tables that require horizontal scrolling.

Tables should be statically and completely visible in the rendered page.
Use larger responsive table sections, grouped/split full-value tables, or
readable density reductions instead of horizontal scrolling. Hidden clipping
is treated as an error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse


def to_url(target: str) -> str:
    parsed = urlparse(target)
    if parsed.scheme in {"http", "https", "file"}:
        return target
    path = Path(target).resolve()
    if not path.exists():
        raise FileNotFoundError(target)
    return path.as_uri()


def have_playwright() -> bool:
    try:
        import playwright  # noqa: F401
    except Exception:
        return False
    return True


CHECK_JS = r"""
() => {
  const tolerance = 3;
  const clipValues = new Set(["hidden", "clip"]);
  const scrollValues = new Set(["auto", "scroll"]);
  const transparent = new Set(["transparent", "rgba(0, 0, 0, 0)"]);

  function rectObject(rect) {
    return {
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      right: Math.round(rect.right),
      bottom: Math.round(rect.bottom)
    };
  }

  function selectorFor(el) {
    if (!el) return "";
    if (el.id) return "#" + el.id;
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 5) {
      let part = node.localName;
      if (node.classList && node.classList.length) {
        part += "." + Array.from(node.classList).slice(0, 3).join(".");
      }
      const parent = node.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(child => child.localName === node.localName);
        if (siblings.length > 1) {
          part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
        }
      }
      parts.unshift(part);
      node = parent;
    }
    return parts.join(" > ");
  }

  function hasVisibleBox(el) {
    const cs = getComputedStyle(el);
    const bg = cs.backgroundColor || "";
    const hasBg = bg && !transparent.has(bg);
    const hasBorder = ["Top", "Right", "Bottom", "Left"].some(side => {
      return (parseFloat(cs[`border${side}Width`]) || 0) > 0 && cs[`border${side}Style`] !== "none";
    });
    const hasPadding = ["Top", "Right", "Bottom", "Left"].some(side => {
      return (parseFloat(cs[`padding${side}`]) || 0) >= 8;
    });
    const hasShadow = cs.boxShadow && cs.boxShadow !== "none";
    const name = `${el.className || ""} ${el.id || ""}`.toLowerCase();
    const tableLike = /(table|card|result|metric|module|surface|panel|wrap)/.test(name);
    return hasBg || hasBorder || hasPadding || hasShadow || tableLike;
  }

  function nearestVisualContainer(table) {
    let node = table.parentElement;
    while (node && node !== document.body && node !== document.documentElement) {
      if (hasVisibleBox(node)) return node;
      node = node.parentElement;
    }
    return null;
  }

  function nearestScrollContainer(table) {
    let node = table.parentElement;
    while (node && node !== document.body && node !== document.documentElement) {
      const cs = getComputedStyle(node);
      if (scrollValues.has(cs.overflowX) && node.scrollWidth > node.clientWidth + tolerance) {
        return node;
      }
      node = node.parentElement;
    }
    return null;
  }

  function clippedByAncestor(table) {
    const tableRect = table.getBoundingClientRect();
    const hits = [];
    let node = table.parentElement;
    while (node && node !== document.body && node !== document.documentElement) {
      const cs = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      const xClipped = clipValues.has(cs.overflowX) && (
        tableRect.left < rect.left - tolerance || tableRect.right > rect.right + tolerance
      );
      const yClipped = clipValues.has(cs.overflowY) && (
        tableRect.top < rect.top - tolerance || tableRect.bottom > rect.bottom + tolerance
      );
      if (xClipped || yClipped) {
        hits.push({
          selector: selectorFor(node),
          overflowX: cs.overflowX,
          overflowY: cs.overflowY,
          rect: rectObject(rect),
          axis: `${xClipped ? "x" : ""}${yClipped ? "y" : ""}`
        });
      }
      node = node.parentElement;
    }
    return hits;
  }

  function clippedCells(table) {
    const cells = Array.from(table.querySelectorAll("th,td"));
    return cells.filter(cell => {
      const cs = getComputedStyle(cell);
      const clipsX = clipValues.has(cs.overflowX) || clipValues.has(cs.overflow);
      const clipsY = clipValues.has(cs.overflowY) || clipValues.has(cs.overflow);
      return (
        (clipsX && cell.scrollWidth > cell.clientWidth + tolerance)
        || (clipsY && cell.scrollHeight > cell.clientHeight + tolerance)
      );
    }).slice(0, 6).map(cell => ({
      selector: selectorFor(cell),
      text: (cell.innerText || cell.textContent || "").trim().replace(/\s+/g, " ").slice(0, 100),
      clientWidth: cell.clientWidth,
      scrollWidth: cell.scrollWidth,
      clientHeight: cell.clientHeight,
      scrollHeight: cell.scrollHeight
    }));
  }

  const tables = Array.from(document.querySelectorAll("table"));
  const issues = [];
  const tableReports = [];
  for (const table of tables) {
    const tableRect = table.getBoundingClientRect();
    if (tableRect.width < 2 || tableRect.height < 2) continue;
    const visual = nearestVisualContainer(table);
    const scroller = nearestScrollContainer(table);
    const clippedAncestors = clippedByAncestor(table);
    const cellClips = clippedCells(table);
    const report = {
      selector: selectorFor(table),
      label: table.getAttribute("data-tex-label") || table.closest("[data-tex-label]")?.getAttribute("data-tex-label") || "",
      rect: rectObject(tableRect),
      scrollWidth: table.scrollWidth,
      clientWidth: table.clientWidth,
      visualContainer: visual ? selectorFor(visual) : "",
      visualRect: visual ? rectObject(visual.getBoundingClientRect()) : null,
      scrollContainer: scroller ? selectorFor(scroller) : "",
      clippedAncestors,
      clippedCells: cellClips
    };
    tableReports.push(report);

    if (clippedAncestors.length) {
      issues.push({
        kind: "table_clipped_by_container",
        severity: "error",
        table: report.selector,
        label: report.label,
        ancestors: clippedAncestors
      });
    }
    if (cellClips.length) {
      issues.push({
        kind: "table_cell_text_clipped",
        severity: "error",
        table: report.selector,
        label: report.label,
        cells: cellClips
      });
    }
    if (scroller) {
      issues.push({
        kind: "table_requires_horizontal_scroll",
        severity: "error",
        table: report.selector,
        label: report.label,
        scrollContainer: report.scrollContainer,
        tableRect: report.rect,
        note: "Do not use horizontal table scrolling. Redesign as a static full table, split/group columns, or allocate a wider responsive module."
      });
    }
    if (visual) {
      const vr = visual.getBoundingClientRect();
      const spills = (
        tableRect.left < vr.left - tolerance
        || tableRect.right > vr.right + tolerance
        || tableRect.top < vr.top - tolerance
        || tableRect.bottom > vr.bottom + tolerance
      );
      if (spills) {
        issues.push({
          kind: "table_spills_outside_visual_container",
          severity: "error",
          table: report.selector,
          label: report.label,
          visualContainer: report.visualContainer,
          tableRect: report.rect,
          visualRect: report.visualRect,
          note: "Resize the table container, split/group columns, use multiple full sub-tables, or reduce table density without dropping values."
        });
      }
    }
  }
  return {
    url: location.href,
    tables: tableReports,
    issues,
    summary: {
      tables: tableReports.length,
      errors: issues.filter(issue => issue.severity === "error").length,
      warnings: issues.filter(issue => issue.severity === "warning").length
    }
  };
}
"""


def run_playwright(url: str) -> dict:
    from playwright.sync_api import sync_playwright  # type: ignore

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(url, wait_until="networkidle")
        report = page.evaluate(CHECK_JS)
        browser.close()
    report["backend"] = "playwright"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", help="Path to index.html or http(s)/file URL.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        url = to_url(args.html)
    except FileNotFoundError as exc:
        print(f"error: not found: {exc}", file=sys.stderr)
        return 2

    if not have_playwright():
        report = {
            "ok": True,
            "status": "skipped",
            "reason": "playwright is not installed; table visual fit was not checked",
            "summary": {"tables": 0, "errors": 0, "warnings": 0},
            "issues": [],
        }
    else:
        report = run_playwright(url)
        report["ok"] = report["summary"]["errors"] == 0
        report["status"] = "pass" if report["ok"] else "fail"

    if args.json:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        if report.get("ok"):
            print(f"table fit check {report.get('status', 'pass')}: {args.html}")
        else:
            print(f"table fit check FAILED: {args.html}")
            for issue in report.get("issues", []):
                print(f"  - [{issue['severity']}] {issue['kind']}: {issue.get('table', '')}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
