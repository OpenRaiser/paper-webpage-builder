#!/usr/bin/env python3
"""Capture desktop and mobile screenshots of a generated webpage.

Backends, in order of preference:
  1. Playwright (`pip install playwright && playwright install chromium`).
  2. Pyppeteer (`pip install pyppeteer`) — first run downloads chromium.
  3. Headless system Chromium / Chrome (`--headless=new --screenshot=...`).

The script writes screenshots into <out_dir> as:
  desktop.png   (1280x800, full page)
  mobile.png    (390x844, full page, deviceScaleFactor=2 when supported)
  meta.json     (viewport, page-height, console-error count, backend used)

Skips with exit code 0 and a clear message when no backend exists, so it
can be wired into the SKILL workflow without breaking the pipeline.

Exit codes:
  0  succeeded OR skipped (skipped when no backend found)
  1  backend chosen but the browser failed (timeout, crash)
  2  bad arguments
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse


DESKTOP = {"width": 1280, "height": 800}
MOBILE = {"width": 390, "height": 844, "device_scale_factor": 2,
          "user_agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                         "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")}


def to_url(target: str) -> str:
    parsed = urlparse(target)
    if parsed.scheme in {"http", "https", "file"}:
        return target
    path = Path(target).resolve()
    if not path.exists():
        raise FileNotFoundError(target)
    return path.as_uri()


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def find_chromium() -> str | None:
    for cmd in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        if have(cmd):
            return cmd
    return None


def have_playwright() -> bool:
    try:
        import playwright  # noqa: F401
    except Exception:
        return False
    return True


def have_pyppeteer() -> bool:
    try:
        import pyppeteer  # noqa: F401
    except Exception:
        return False
    return True


def capture_with_playwright(url: str, out_dir: Path) -> dict:
    from playwright.sync_api import sync_playwright  # type: ignore

    errors_desktop: list[str] = []
    errors_mobile: list[str] = []
    page_height = None
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        ctx = browser.new_context(viewport={"width": DESKTOP["width"], "height": DESKTOP["height"]})
        page = ctx.new_page()
        page.on("console", lambda msg: errors_desktop.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors_desktop.append(str(exc)))
        page.goto(url, wait_until="networkidle")
        page.screenshot(path=str(out_dir / "desktop.png"), full_page=True)
        page_height = page.evaluate("document.documentElement.scrollHeight")
        ctx.close()

        ctx = browser.new_context(
            viewport={"width": MOBILE["width"], "height": MOBILE["height"]},
            device_scale_factor=MOBILE["device_scale_factor"],
            user_agent=MOBILE["user_agent"],
            is_mobile=True,
        )
        page = ctx.new_page()
        page.on("console", lambda msg: errors_mobile.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors_mobile.append(str(exc)))
        page.goto(url, wait_until="networkidle")
        page.screenshot(path=str(out_dir / "mobile.png"), full_page=True)
        ctx.close()
        browser.close()

    return {
        "backend": "playwright",
        "page_height": page_height,
        "console_errors": {"desktop": errors_desktop, "mobile": errors_mobile},
    }


def capture_with_pyppeteer(url: str, out_dir: Path) -> dict:
    import asyncio
    from pyppeteer import launch  # type: ignore

    async def _run() -> dict:
        browser = await launch(args=["--no-sandbox"])
        try:
            page = await browser.newPage()
            await page.setViewport({"width": DESKTOP["width"], "height": DESKTOP["height"]})
            errors_desktop: list[str] = []
            page.on("pageerror", lambda exc: errors_desktop.append(str(exc)))
            page.on("console", lambda msg: errors_desktop.append(msg.text) if getattr(msg, "type", "") == "error" else None)
            await page.goto(url, {"waitUntil": "networkidle0"})
            await page.screenshot({"path": str(out_dir / "desktop.png"), "fullPage": True})
            page_height = await page.evaluate("document.documentElement.scrollHeight")

            await page.setViewport({
                "width": MOBILE["width"], "height": MOBILE["height"],
                "deviceScaleFactor": MOBILE["device_scale_factor"],
                "isMobile": True,
            })
            await page.setUserAgent(MOBILE["user_agent"])
            errors_mobile: list[str] = []
            page.on("pageerror", lambda exc: errors_mobile.append(str(exc)))
            await page.goto(url, {"waitUntil": "networkidle0"})
            await page.screenshot({"path": str(out_dir / "mobile.png"), "fullPage": True})
            return {
                "backend": "pyppeteer",
                "page_height": page_height,
                "console_errors": {"desktop": errors_desktop, "mobile": errors_mobile},
            }
        finally:
            await browser.close()

    return asyncio.run(_run())


def capture_with_chromium(url: str, out_dir: Path, binary: str) -> dict:
    base_args = [
        binary,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--virtual-time-budget=8000",
    ]
    with tempfile.TemporaryDirectory() as user_data:
        for label, viewport, extra in (
            ("desktop", DESKTOP, []),
            ("mobile", MOBILE, ["--user-agent=" + MOBILE["user_agent"]]),
        ):
            cmd = base_args + [
                f"--user-data-dir={user_data}/{label}",
                f"--window-size={viewport['width']},{viewport['height']}",
                f"--screenshot={out_dir / (label + '.png')}",
                *extra,
                url,
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.returncode != 0:
                raise RuntimeError(f"{binary} ({label}) failed: {proc.stderr[:400]}")
    return {
        "backend": f"chromium:{binary}",
        "page_height": None,
        "console_errors": {"desktop": [], "mobile": []},
        "notes": "headless Chrome screenshots only; console errors not captured.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", help="Path to index.html or http(s) URL.")
    parser.add_argument("--out-dir", type=Path, default=Path("reports/screenshots"),
                        help="Output directory; created if missing.")
    parser.add_argument("--backend", choices=("playwright", "pyppeteer", "chromium", "auto"),
                        default="auto")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        url = to_url(args.html)
    except FileNotFoundError as exc:
        print(f"error: not found: {exc}", file=sys.stderr)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)

    backend = args.backend
    chromium = find_chromium()
    if backend == "auto":
        if have_playwright():
            backend = "playwright"
        elif have_pyppeteer():
            backend = "pyppeteer"
        elif chromium:
            backend = "chromium"
        else:
            message = (
                "no screenshot backend available "
                "(install playwright / pyppeteer / chromium); skipped."
            )
            print(message)
            (args.out_dir / "meta.json").write_text(
                json.dumps({"status": "skipped", "reason": message}, indent=2) + "\n",
                encoding="utf-8",
            )
            return 0

    started = time.time()
    try:
        if backend == "playwright":
            meta = capture_with_playwright(url, args.out_dir)
        elif backend == "pyppeteer":
            meta = capture_with_pyppeteer(url, args.out_dir)
        else:
            if not chromium:
                print("error: chromium binary not found.", file=sys.stderr)
                return 1
            meta = capture_with_chromium(url, args.out_dir, chromium)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        (args.out_dir / "meta.json").write_text(
            json.dumps({"status": "failed", "backend": backend, "error": str(exc)}, indent=2) + "\n",
            encoding="utf-8",
        )
        return 1

    meta.update({
        "status": "ok",
        "url": url,
        "elapsed_s": round(time.time() - started, 2),
        "viewports": {"desktop": DESKTOP, "mobile": MOBILE},
    })
    (args.out_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if args.json:
        json.dump(meta, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(f"screenshots written to {args.out_dir} ({meta['backend']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
