#!/usr/bin/env python3
"""Convert paper figures into web-ready files with a stable manifest.

Improvements over the original `convert_figures.sh`:
  * Multi-page PDFs produce one PNG per page (`name-p1.png`, `name-p2.png`)
    so subfigure-pack PDFs are not silently truncated to page 1.
  * `.eps` is rasterised through Ghostscript when available.
  * `.svg` is copied as-is (browsers render SVG natively).
  * `.png` / `.jpg` / `.jpeg` / `.webp` / `.gif` pass through with renaming.
  * Filenames are slugified ASCII; CJK / accented names get a deterministic
    8-char hash suffix so distinct sources never collide on the same slug.
  * A `figures.manifest.json` is written next to the converted assets,
    mapping each output file to its source path, page index, dimensions
    when known, and a placeholder `alt` ready for the LLM to fill in.

Usage:
  convert_figures.py <source_images_dir> <target_figures_dir> [--dpi 180]
                     [--manifest <name>] [--no-multipage]

Exit codes:
  0  conversions ran (manifest may still list per-file errors)
  2  bad arguments / source dir missing
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

RASTER_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
VECTOR_PASSTHROUGH_EXTS = {".svg"}
PDF_EXTS = {".pdf"}
EPS_EXTS = {".eps", ".ps"}


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def slugify(name: str) -> tuple[str, bool]:
    """Return (slug, hashed). hashed=True if non-ASCII content was lost."""
    original = name
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_only).strip("-").lower()
    hashed = False
    if not slug or slug != re.sub(r"[^A-Za-z0-9]+", "-", original).strip("-").lower():
        digest = hashlib.sha1(original.encode("utf-8")).hexdigest()[:8]
        slug = (slug or "figure")
        slug = f"{slug}-{digest}"
        hashed = True
    return slug, hashed


@dataclass
class ConvertedAsset:
    source: str
    output: str
    kind: str
    page: int | None = None
    width: int | None = None
    height: int | None = None
    alt: str = ""
    notes: list[str] = field(default_factory=list)


def gather_sources(src_dir: Path) -> list[Path]:
    sources: list[Path] = []
    for path in sorted(src_dir.iterdir()):
        if not path.is_file() or path.name.startswith("._") or path.name.startswith("."):
            continue
        ext = path.suffix.lower()
        if ext in RASTER_EXTS | VECTOR_PASSTHROUGH_EXTS | PDF_EXTS | EPS_EXTS:
            sources.append(path)
    return sources


def rasterize_pdf_with_pymupdf(
    src: Path, dst_dir: Path, slug: str, dpi: int, multipage: bool
) -> tuple[list[Path], list[ConvertedAsset]]:
    import fitz  # type: ignore

    outputs: list[Path] = []
    assets: list[ConvertedAsset] = []
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(src) as doc:
        page_count = doc.page_count
        pages = range(page_count) if multipage else range(min(1, page_count))
        for index in pages:
            page = doc[index]
            pix = page.get_pixmap(matrix=matrix, alpha=True)
            if page_count > 1 and multipage:
                out = unique_path(dst_dir, f"{slug}-p{index + 1}.png")
            else:
                out = unique_path(dst_dir, f"{slug}.png")
            pix.save(out)
            outputs.append(out)
            assets.append(
                ConvertedAsset(
                    source=str(src),
                    output=str(out),
                    kind="raster-from-pdf",
                    page=index + 1 if page_count > 1 else None,
                    width=pix.width,
                    height=pix.height,
                )
            )
    return outputs, assets


def rasterize_pdf_with_gs(
    src: Path, dst_dir: Path, slug: str, dpi: int, multipage: bool
) -> tuple[list[Path], list[ConvertedAsset]]:
    if not have("gs"):
        raise RuntimeError("Ghostscript missing; cannot rasterize PDF without pymupdf either.")
    page_count = 1
    if have("pdfinfo"):
        try:
            info = subprocess.run(
                ["pdfinfo", str(src)], check=True, capture_output=True, text=True
            ).stdout
            for line in info.splitlines():
                if line.lower().startswith("pages:"):
                    page_count = int(line.split(":")[1].strip())
                    break
        except Exception:
            page_count = 1
    last_page = page_count if multipage else 1
    outputs: list[Path] = []
    assets: list[ConvertedAsset] = []

    if page_count == 1 or not multipage:
        out = unique_path(dst_dir, f"{slug}.png")
        cmd = [
            "gs", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pngalpha",
            f"-r{dpi}", "-dFirstPage=1", "-dLastPage=1",
            f"-sOutputFile={out}", str(src),
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0 and out.exists():
            outputs.append(out)
            assets.append(ConvertedAsset(source=str(src), output=str(out), kind="raster-from-pdf"))
        return outputs, assets

    pattern_out = unique_path(dst_dir, f"{slug}-p%d.png")
    cmd = [
        "gs", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pngalpha",
        f"-r{dpi}", "-dFirstPage=1", f"-dLastPage={last_page}",
        f"-sOutputFile={pattern_out}", str(src),
    ]
    subprocess.run(cmd, capture_output=True)
    for index in range(1, last_page + 1):
        out = pattern_out.with_name(pattern_out.name.replace("%d", str(index)))
        if out.exists():
            outputs.append(out)
            assets.append(
                ConvertedAsset(
                    source=str(src), output=str(out), kind="raster-from-pdf",
                    page=index,
                )
            )
    return outputs, assets


def rasterize_eps(src: Path, dst_dir: Path, slug: str, dpi: int) -> tuple[list[Path], list[ConvertedAsset]]:
    if not have("gs"):
        return [], [ConvertedAsset(
            source=str(src), output="", kind="eps",
            notes=["skipped: ghostscript missing"],
        )]
    out = unique_path(dst_dir, f"{slug}.png")
    cmd = [
        "gs", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-dEPSCrop",
        "-sDEVICE=pngalpha", f"-r{dpi}", f"-sOutputFile={out}", str(src),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0 or not out.exists():
        return [], [ConvertedAsset(
            source=str(src), output="", kind="eps",
            notes=[f"ghostscript failed: {result.stderr.decode('utf-8', 'replace')[:200]}"],
        )]
    return [out], [ConvertedAsset(source=str(src), output=str(out), kind="raster-from-eps")]


def passthrough(src: Path, dst_dir: Path, slug: str, kind: str) -> tuple[list[Path], list[ConvertedAsset]]:
    out = unique_path(dst_dir, f"{slug}{src.suffix.lower()}")
    shutil.copy2(src, out)
    width, height = (None, None)
    if src.suffix.lower() in RASTER_EXTS:
        width, height = read_raster_dims(out)
    return [out], [ConvertedAsset(
        source=str(src), output=str(out), kind=kind,
        width=width, height=height,
    )]


def read_raster_dims(path: Path) -> tuple[int | None, int | None]:
    try:
        import fitz  # type: ignore
        doc = fitz.open(path)
        try:
            pix = doc[0].get_pixmap(alpha=False)
            return pix.width, pix.height
        finally:
            doc.close()
    except Exception:
        pass
    # PNG header probe (no extra deps)
    try:
        with path.open("rb") as fh:
            header = fh.read(24)
        if path.suffix.lower() == ".png" and header[:8] == b"\x89PNG\r\n\x1a\n":
            width = int.from_bytes(header[16:20], "big")
            height = int.from_bytes(header[20:24], "big")
            return width, height
    except Exception:
        return None, None
    return None, None


def unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        candidate = directory / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def convert_one(
    src: Path, dst_dir: Path, dpi: int, multipage: bool
) -> list[ConvertedAsset]:
    slug, hashed = slugify(src.stem)
    ext = src.suffix.lower()
    notes: list[str] = []
    if hashed:
        notes.append("non-ASCII source name; appended sha1 suffix to keep filenames stable")

    try:
        if ext in PDF_EXTS:
            try:
                import fitz  # noqa: F401
                outputs, assets = rasterize_pdf_with_pymupdf(src, dst_dir, slug, dpi, multipage)
            except Exception:
                outputs, assets = rasterize_pdf_with_gs(src, dst_dir, slug, dpi, multipage)
        elif ext in EPS_EXTS:
            outputs, assets = rasterize_eps(src, dst_dir, slug, dpi)
        elif ext in VECTOR_PASSTHROUGH_EXTS:
            outputs, assets = passthrough(src, dst_dir, slug, "vector")
        elif ext in RASTER_EXTS:
            outputs, assets = passthrough(src, dst_dir, slug, "raster")
        else:
            return [ConvertedAsset(
                source=str(src), output="", kind="unsupported",
                notes=notes + [f"unsupported extension {ext}"],
            )]
    except Exception as exc:
        return [ConvertedAsset(
            source=str(src), output="", kind=ext.lstrip("."),
            notes=notes + [f"conversion failed: {exc}"],
        )]
    for asset in assets:
        asset.notes.extend(notes)
    return assets


def write_manifest(target_dir: Path, name: str, assets: Iterable[ConvertedAsset]) -> Path:
    asset_list = []
    for asset in assets:
        d = asdict(asset)
        if d.get("width") and d.get("height") and d["height"] > 0:
            d["aspect_ratio"] = round(d["width"] / d["height"], 4)
        asset_list.append(d)
    payload = {
        "version": 1,
        "directory": str(target_dir.resolve()),
        "assets": asset_list,
    }
    out = target_dir / name
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("target_dir", type=Path)
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--manifest", default="figures.manifest.json")
    parser.add_argument(
        "--no-multipage",
        action="store_true",
        help="Only export the first page from multi-page PDFs (legacy behaviour).",
    )
    args = parser.parse_args()

    if not args.source_dir.is_dir():
        print(f"error: not a directory: {args.source_dir}", file=sys.stderr)
        return 2
    args.target_dir.mkdir(parents=True, exist_ok=True)

    sources = gather_sources(args.source_dir)
    if not sources:
        print(f"warning: no convertible figures found in {args.source_dir}", file=sys.stderr)

    multipage = not args.no_multipage
    all_assets: list[ConvertedAsset] = []
    for src in sources:
        assets = convert_one(src, args.target_dir, args.dpi, multipage)
        for asset in assets:
            if asset.output:
                print(asset.output)
            else:
                print(
                    f"warning: failed to convert {asset.source}: {'; '.join(asset.notes) or 'no output'}",
                    file=sys.stderr,
                )
            all_assets.append(asset)

    manifest_path = write_manifest(args.target_dir, args.manifest, all_assets)
    print(f"manifest: {manifest_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
