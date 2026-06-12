#!/usr/bin/env python3
"""Detect design drift between the rendered page and the paper's figures.

Seven checks:

1. Palette overlap: sample the dominant colors from each figure listed in
   `figures.manifest.json` and compare against the colors used in the
   page (from CSS `background`, `background-color`, `color`, inline styles,
   and Tailwind hex utilities). Reports the overlap ratio and any obvious
   accent that has no support in the figure palette.

2. Clone signals: look for the heavy-handed indicators called out in
   references/design_principles.md — coordinate grids / dot textures
   (`background-image: url(grid…), linear-gradient(…),` etc.), dark canvas
   sections (very low luminance) repeated multiple times, hero-card
   compositions reused from another generated report (compared via
   class-name/structure signature against `reports/<other>/index.html`).

3. Figure layout risk: flag CSS patterns that commonly create large blank
   areas around paper figures, especially fixed-height/equal-aspect figure
   cards combined with `object-fit: contain`. Zoom modals are ignored.

4. Variable name vs hue: flag CSS custom properties named with a color word
   (green, blue, red, etc.) whose actual hue contradicts the name.

5. Hardcoded color orphans: flag hex colors in non-:root CSS rules that
   don't match any declared custom property within distance threshold.

6. Grid responsive breakpoints: flag grids with >4 columns that lack a
   media query at <=960px to reduce column count.

7. Paired figure alignment: flag paired-figure containers using
   align-items: start instead of stretch.

This script is best-effort:
  - Color sampling needs PyMuPDF (already a project dep) or stdlib for PNG.
  - JPEG samples require Pillow; if unavailable, JPEGs are skipped with a
    note so the score is correctly weighted.
  - When no figure PNG can be sampled at all, the palette check returns
    `status: skipped` rather than failing.

Exit codes:
  0  no drift signal exceeds the configured threshold
  1  drift signal found (palette overlap below threshold OR clone indicator)
  2  bad arguments
"""

from __future__ import annotations

import argparse
import colorsys
import json
import re
import struct
import sys
import zlib
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

HEX_COLOR_RE = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
RGB_FUNC_RE = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})")
TAILWIND_HEX_RE = re.compile(r"\b(?:bg|text|from|via|to|border|ring)-\[#([0-9a-fA-F]{3,8})\]")
GRID_BG_HINT_RE = re.compile(
    r"(?ix)"
    r"(linear|radial)-gradient \( [^)]*\) \s* , \s* (linear|radial)-gradient"
    r"|"
    r"url\( [^)]* (grid|dots|paper|noise|notebook|graph) [^)]* \)"
)
CSS_RULE_RE = re.compile(r"([^{}@][^{}]*)\{([^{}]+)\}", re.S)
FIGURE_SELECTOR_RE = re.compile(
    r"(?ix)"
    r"\b(img|figure|picture)\b"
    r"|figure|image|visual|media|gallery|teaser|hero-card|case-card|case|thumb"
)
MODAL_SELECTOR_RE = re.compile(r"(?i)\b(modal|lightbox|zoom|preview)\b")
ROW_LAYOUT_CLASS_RE = re.compile(
    r"(?i)\b(two-col|three-col|grid|gallery|diagnostic|case-strip|figure-row|image-row|media-row|split)\b"
)
COMPACT_TABLE_CLASS_RE = re.compile(r"(?i)\b(compact|narrow|mini|summary|stats)\b")
FIXED_HEIGHT_RE = re.compile(
    r"(?i)(?<![-])\bheight\s*:\s*(?!\s*(?:auto|fit-content|initial|inherit|unset)\b)([^;]+)"
)
MIN_HEIGHT_RE = re.compile(
    r"(?i)\bmin-height\s*:\s*(?!\s*(?:0|auto|initial|inherit|unset)\b)([^;]+)"
)
ASPECT_RATIO_RE = re.compile(r"(?i)\baspect-ratio\s*:\s*([^;]+)")
OBJECT_FIT_CONTAIN_RE = re.compile(r"(?i)\bobject-fit\s*:\s*contain\b")

DEFAULT_FIGURE_TOP_K = 5
DEFAULT_PAGE_TOP_K = 8
DEFAULT_OVERLAP_THRESHOLD = 0.5
DEFAULT_DARK_LUMINANCE = 0.18
DEFAULT_DARK_REPEAT = 2
DEFAULT_RATIO_ROW_THRESHOLD = 1.25
DEFAULT_NARROW_TABLE_MAX_COLS = 3
DEFAULT_GRID_MIN_ITEM_WIDTH = 180
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

CSS_VAR_DEF_RE = re.compile(r"--([\w-]+)\s*:\s*([^;]+);")
GRID_COLS_RE = re.compile(
    r"grid-template-columns\s*:\s*repeat\(\s*(\d+)"
)
MEDIA_QUERY_RE = re.compile(r"@media[^{]*max-width\s*:\s*(\d+)")
PAIRED_FIGURE_RE = re.compile(
    r"(?i)\b(paired-figures|figure-row|figure-pair|two-figures|image-row|benchmark-figures)\b"
)
ALIGN_ITEMS_RE = re.compile(r"(?i)\balign-items\s*:\s*(\w+)")

HUE_WORD_RANGES: dict[str, tuple[float, float]] = {
    "red": (345, 15),
    "orange": (15, 45),
    "yellow": (45, 70),
    "green": (70, 170),
    "teal": (170, 200),
    "cyan": (170, 200),
    "blue": (200, 260),
    "purple": (260, 310),
    "pink": (310, 345),
}


def _hue_in_range(hue: float, hue_range: tuple[float, float]) -> bool:
    """Check if a hue (0-360) falls in a range that may wrap around 0."""
    lo, hi = hue_range
    if lo <= hi:
        return lo <= hue <= hi
    return hue >= lo or hue <= hi


# --------------------------------------------------------------------------
# Color parsing helpers
# --------------------------------------------------------------------------

def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    if len(hex_str) == 4:
        hex_str = "".join(c * 2 for c in hex_str[:3])
    if len(hex_str) >= 6:
        return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))
    return (0, 0, 0)


def _bucket(rgb: tuple[int, int, int], bucket: int = 32) -> tuple[int, int, int]:
    """Round RGB to a coarse grid so 'almost-equal' colors collapse."""
    r, g, b = rgb
    return (r // bucket * bucket, g // bucket * bucket, b // bucket * bucket)


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (c / 255 for c in rgb)
    def lin(x: float) -> float:
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _is_neutral(rgb: tuple[int, int, int], spread: int = 12) -> bool:
    """Whitepoint, near-black, and near-greys should not count toward palette."""
    r, g, b = rgb
    if max(r, g, b) - min(r, g, b) > spread:
        return False
    return True


# --------------------------------------------------------------------------
# PNG sampling
# --------------------------------------------------------------------------

def sample_png(path: Path, max_samples: int = 4096) -> Counter:
    """Return a Counter of bucketed RGB tuples sampled from a PNG.

    Implements just enough PNG to read top-level RGB(A) pixels via stdlib.
    Caller filters by neutrality.
    """
    counter: Counter = Counter()
    try:
        data = path.read_bytes()
    except OSError:
        return counter
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return counter
    width = height = 0
    bit_depth = color_type = 0
    idat_chunks: list[bytes] = []
    pos = 8
    while pos < len(data):
        if pos + 8 > len(data):
            break
        length = int.from_bytes(data[pos:pos + 4], "big")
        tag = data[pos + 4:pos + 8]
        chunk_data = data[pos + 8:pos + 8 + length]
        pos += 8 + length + 4
        if tag == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk_data[:10])
        elif tag == b"IDAT":
            idat_chunks.append(chunk_data)
        elif tag == b"IEND":
            break
    if not (width and height and idat_chunks):
        return counter
    if bit_depth != 8 or color_type not in (2, 6):
        return counter  # 8-bit RGB/RGBA only

    raw = zlib.decompress(b"".join(idat_chunks))
    bpp = 3 if color_type == 2 else 4
    stride = width * bpp + 1
    expected = stride * height
    if len(raw) < expected:
        return counter

    pixels: list[tuple[int, int, int]] = []
    prev_row = bytes(width * bpp)
    for y in range(height):
        row_start = y * stride
        filter_type = raw[row_start]
        scanline = bytearray(raw[row_start + 1:row_start + stride])
        # PNG filter reconstruction (None/Sub/Up/Average/Paeth).
        if filter_type == 0:
            pass
        elif filter_type == 1:  # Sub
            for i in range(bpp, len(scanline)):
                scanline[i] = (scanline[i] + scanline[i - bpp]) & 0xFF
        elif filter_type == 2:  # Up
            for i in range(len(scanline)):
                scanline[i] = (scanline[i] + prev_row[i]) & 0xFF
        elif filter_type == 3:  # Average
            for i in range(len(scanline)):
                left = scanline[i - bpp] if i >= bpp else 0
                up = prev_row[i]
                scanline[i] = (scanline[i] + (left + up) // 2) & 0xFF
        elif filter_type == 4:  # Paeth
            for i in range(len(scanline)):
                a = scanline[i - bpp] if i >= bpp else 0
                b = prev_row[i]
                c = prev_row[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                if pa <= pb and pa <= pc:
                    pr = a
                elif pb <= pc:
                    pr = b
                else:
                    pr = c
                scanline[i] = (scanline[i] + pr) & 0xFF
        else:
            return counter
        prev_row = bytes(scanline)
        # Sample evenly across the row.
        step = max(1, width // 32)
        for x in range(0, width, step):
            offset = x * bpp
            if bpp == 4 and scanline[offset + 3] < 128:
                continue
            pixels.append((scanline[offset], scanline[offset + 1], scanline[offset + 2]))
        if len(pixels) >= max_samples:
            break
    for px in pixels:
        if _is_neutral(px):
            continue
        counter[_bucket(px)] += 1
    return counter


def sample_figures(manifest_path: Path, top_k: int) -> tuple[Counter, list[str]]:
    """Aggregate dominant colors across all PNG outputs in the manifest."""
    overall: Counter = Counter()
    notes: list[str] = []
    if not manifest_path.is_file():
        notes.append(f"manifest not found: {manifest_path}")
        return overall, notes
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for asset in manifest.get("assets", []):
        out = asset.get("output")
        if not out:
            continue
        out_path = Path(out)
        if not out_path.is_absolute():
            out_path = manifest_path.parent / out_path
        if out_path.suffix.lower() != ".png":
            notes.append(f"skip (non-PNG, not sampled): {out_path.name}")
            continue
        figure_counter = sample_png(out_path)
        if not figure_counter:
            notes.append(f"skip (no usable pixels): {out_path.name}")
            continue
        for color, count in figure_counter.most_common(top_k):
            overall[color] += count
    return overall, notes


# --------------------------------------------------------------------------
# Page color extraction
# --------------------------------------------------------------------------

class StyleCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.styles: list[str] = []
        self.classes: list[str] = []
        self.section_backgrounds: list[str] = []
        self.has_grid_hint = False
        self.in_style = False
        self.style_buf: list[str] = []
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k.lower(): (v or "") for k, v in attrs}
        if "class" in attr and attr["class"]:
            self.classes.append(attr["class"])
        if "style" in attr and attr["style"]:
            self.styles.append(attr["style"])
            if tag in ("section", "header", "footer", "main", "div"):
                self.section_backgrounds.append(attr["style"])
        if tag == "style":
            self.in_style = True
            self.style_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "style" and self.in_style:
            block = "".join(self.style_buf)
            self.styles.append(block)
            self.in_style = False

    def handle_data(self, data: str) -> None:
        if self.in_style:
            self.style_buf.append(data)


class LayoutInspector(HTMLParser):
    """Collect lightweight structure for figure-row and table-density checks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = {"tag": "root", "classes": set(), "attrs": {}, "children": []}
        self.stack: list[dict] = [self.root]
        self.label_stack: list[str] = []
        self.tables: list[dict] = []
        self.current_table: dict | None = None
        self.current_row_cols = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k.lower(): (v or "") for k, v in attrs}
        classes = set(attr.get("class", "").split())
        node = {
            "tag": tag,
            "classes": classes,
            "attrs": attr,
            "children": [],
        }
        self.stack[-1]["children"].append(node)
        self.stack.append(node)

        label = attr.get("data-tex-label", "").strip()
        self.label_stack.append(label)

        if tag == "table":
            ancestor_classes = set()
            for item in self.stack:
                ancestor_classes.update(item.get("classes", set()))
            self.current_table = {
                "label": next((x for x in reversed(self.label_stack) if x), ""),
                "classes": ancestor_classes,
                "cols": 0,
            }
        elif tag == "tr" and self.current_table is not None:
            self.current_row_cols = 0
        elif tag in ("td", "th") and self.current_table is not None:
            try:
                colspan = int(attr.get("colspan", "1"))
            except ValueError:
                colspan = 1
            self.current_row_cols += max(1, colspan)

        if tag in VOID_TAGS:
            if self.label_stack:
                self.label_stack.pop()
            if len(self.stack) > 1:
                self.stack.pop()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        before_depth = len(self.stack)
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS and len(self.stack) > before_depth:
            if self.label_stack:
                self.label_stack.pop()
            if len(self.stack) > 1:
                self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        if tag == "tr" and self.current_table is not None:
            self.current_table["cols"] = max(self.current_table["cols"], self.current_row_cols)
            self.current_row_cols = 0
        elif tag == "table" and self.current_table is not None:
            self.tables.append(self.current_table)
            self.current_table = None

        if self.label_stack:
            self.label_stack.pop()
        if len(self.stack) > 1:
            self.stack.pop()


def extract_page_colors(html: str) -> tuple[Counter, list[str], list[str]]:
    parser = StyleCollector()
    parser.feed(html)
    parser.close()

    colors: Counter = Counter()
    for blob in parser.styles + parser.classes:
        for match in HEX_COLOR_RE.findall(blob):
            colors[_bucket(_hex_to_rgb(match))] += 1
        for match in RGB_FUNC_RE.findall(blob):
            try:
                rgb = (int(match[0]), int(match[1]), int(match[2]))
            except ValueError:
                continue
            colors[_bucket(rgb)] += 1
        for match in TAILWIND_HEX_RE.findall(blob):
            colors[_bucket(_hex_to_rgb(match))] += 1
    grid_hits: list[str] = []
    for blob in parser.styles:
        for match in GRID_BG_HINT_RE.findall(blob):
            grid_hits.append(blob[:120])
            break
    dark_sections = [s for s in parser.section_backgrounds
                     if any(_luminance(_hex_to_rgb(m)) < DEFAULT_DARK_LUMINANCE
                             for m in HEX_COLOR_RE.findall(s))]
    return colors, grid_hits, dark_sections


def detect_figure_layout_risks(styles: list[str], limit: int = 8) -> list[dict]:
    """Find CSS rules likely to create empty figure boxes.

    This is intentionally heuristic: it does not try to evaluate layout. The
    goal is to catch the common generated-page pattern where mixed-ratio paper
    figures are forced into a uniform grid box and then rendered with
    `object-fit: contain`, leaving large blank areas inside the container.
    """
    risks: list[dict] = []
    for blob in styles:
        for selector, declarations in CSS_RULE_RE.findall(blob):
            selector_clean = " ".join(selector.split())
            decl_clean = " ".join(declarations.split())
            if not selector_clean or MODAL_SELECTOR_RE.search(selector_clean):
                continue
            figureish = bool(FIGURE_SELECTOR_RE.search(selector_clean))
            fixed_height = FIXED_HEIGHT_RE.search(decl_clean)
            min_height = MIN_HEIGHT_RE.search(decl_clean)
            aspect_ratio = ASPECT_RATIO_RE.search(decl_clean)
            contain = OBJECT_FIT_CONTAIN_RE.search(decl_clean)
            if not figureish and not contain:
                continue
            flags: list[str] = []
            if aspect_ratio:
                flags.append(f"aspect-ratio:{aspect_ratio.group(1).strip()}")
            if fixed_height:
                flags.append(f"height:{fixed_height.group(1).strip()}")
            if min_height:
                flags.append(f"min-height:{min_height.group(1).strip()}")
            if contain:
                flags.append("object-fit:contain")
            if not flags:
                continue
            # A single width-only responsive image rule is fine; the risky
            # cases have at least one vertical/ratio constraint or contain.
            risks.append({
                "selector": selector_clean[:100],
                "flags": flags,
            })
            if len(risks) >= limit:
                return risks
    return risks


def _node_classes(node: dict) -> str:
    return " ".join(sorted(node.get("classes", set())))


def _descendant_image_srcs(node: dict) -> list[str]:
    srcs: list[str] = []
    if node.get("tag") == "img":
        src = node.get("attrs", {}).get("src", "")
        if src:
            srcs.append(src)
    for child in node.get("children", []):
        srcs.extend(_descendant_image_srcs(child))
    return srcs


def _iter_nodes(node: dict):
    yield node
    for child in node.get("children", []):
        yield from _iter_nodes(child)


def png_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        header = path.read_bytes()[:24]
    except OSError:
        return None, None
    if path.suffix.lower() == ".png" and header[:8] == b"\x89PNG\r\n\x1a\n":
        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        return width, height
    return None, None


def load_figure_ratios(manifest_path: Path | None) -> tuple[dict[str, float], list[str]]:
    ratios: dict[str, float] = {}
    notes: list[str] = []
    if not manifest_path or not manifest_path.is_file():
        return ratios, notes
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for asset in manifest.get("assets", []):
        out = asset.get("output")
        if not out:
            continue
        out_path = Path(out)
        if not out_path.is_absolute():
            out_path = manifest_path.parent / out_path
        width = asset.get("width")
        height = asset.get("height")
        if not width or not height:
            width, height = png_dimensions(out_path)
        if width and height:
            ratios[out_path.name] = float(width) / float(height)
        else:
            notes.append(f"skip ratio (dimensions unavailable): {out_path.name}")
    return ratios, notes


def detect_mixed_ratio_figure_rows(root: dict, ratios: dict[str, float],
                                   threshold: float = DEFAULT_RATIO_ROW_THRESHOLD,
                                   limit: int = 8) -> list[dict]:
    risks: list[dict] = []
    if not ratios:
        return risks
    for node in _iter_nodes(root):
        classes = _node_classes(node)
        if not classes or not ROW_LAYOUT_CLASS_RE.search(classes):
            continue
        srcs = _descendant_image_srcs(node)
        if len(srcs) < 2:
            continue
        row_ratios: list[tuple[str, float]] = []
        for src in srcs:
            name = Path(src.split("?", 1)[0]).name
            if name in ratios:
                row_ratios.append((name, ratios[name]))
        if len(row_ratios) < 2:
            continue
        values = [ratio for _, ratio in row_ratios]
        spread = max(values) / max(0.001, min(values))
        if spread > threshold:
            risks.append({
                "classes": classes[:100],
                "spread": round(spread, 3),
                "figures": [{"name": name, "ratio": round(ratio, 3)} for name, ratio in row_ratios[:6]],
            })
            if len(risks) >= limit:
                return risks
    return risks


def detect_overstretched_tables(tables: list[dict], max_cols: int = DEFAULT_NARROW_TABLE_MAX_COLS,
                                limit: int = 8) -> list[dict]:
    risks: list[dict] = []
    for table in tables:
        cols = int(table.get("cols") or 0)
        if cols <= 0 or cols > max_cols:
            continue
        classes = " ".join(sorted(table.get("classes", set())))
        if COMPACT_TABLE_CLASS_RE.search(classes):
            continue
        risks.append({
            "label": table.get("label", ""),
            "cols": cols,
            "classes": classes[:100],
        })
        if len(risks) >= limit:
            return risks
    return risks


# --------------------------------------------------------------------------
# New checks: variable naming, hardcoded colors, grid density, paired figures
# --------------------------------------------------------------------------

def detect_variable_hue_mismatch(styles: list[str], limit: int = 8) -> list[dict]:
    """Flag CSS variables named with a color word whose value contradicts the name."""
    issues: list[dict] = []
    for blob in styles:
        for name, value in CSS_VAR_DEF_RE.findall(blob):
            name_lower = name.lower()
            matched_word = None
            for word in HUE_WORD_RANGES:
                if word in name_lower:
                    matched_word = word
                    break
            if not matched_word:
                continue
            hex_match = HEX_COLOR_RE.search(value)
            rgb_match = RGB_FUNC_RE.search(value)
            if hex_match:
                rgb = _hex_to_rgb(hex_match.group(1))
            elif rgb_match:
                try:
                    rgb = (int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3)))
                except ValueError:
                    continue
            else:
                continue
            if _is_neutral(rgb, spread=20):
                continue
            r, g, b = (c / 255.0 for c in rgb)
            h, _, s = colorsys.rgb_to_hls(r, g, b)
            if s < 0.1:
                continue
            hue_deg = h * 360
            expected_range = HUE_WORD_RANGES[matched_word]
            if not _hue_in_range(hue_deg, expected_range):
                issues.append({
                    "variable": f"--{name}",
                    "value": value.strip()[:40],
                    "named_hue": matched_word,
                    "actual_hue_deg": round(hue_deg, 1),
                })
                if len(issues) >= limit:
                    return issues
    return issues


def detect_hardcoded_color_orphans(
    styles: list[str], limit: int = 12
) -> list[dict]:
    """Find hex colors in non-:root CSS rules that don't match any custom property."""
    declared_colors: list[tuple[int, int, int]] = []
    non_root_colors: list[tuple[str, tuple[int, int, int]]] = []

    for blob in styles:
        for selector, declarations in CSS_RULE_RE.findall(blob):
            sel_clean = selector.strip()
            is_root = sel_clean in (":root", "html", ":root, html")
            for hex_match in HEX_COLOR_RE.finditer(declarations):
                rgb = _hex_to_rgb(hex_match.group(1))
                if _is_neutral(rgb, spread=15):
                    continue
                if is_root:
                    declared_colors.append(_bucket(rgb, 16))
                else:
                    non_root_colors.append((f"#{hex_match.group(1)}", rgb))

    if not declared_colors:
        return []

    issues: list[dict] = []
    seen: set[str] = set()
    for hex_str, rgb in non_root_colors:
        if hex_str in seen:
            continue
        bucketed = _bucket(rgb, 16)
        min_dist = min(
            (sum((a - b) ** 2 for a, b in zip(bucketed, declared)) ** 0.5
             for declared in declared_colors),
            default=999,
        )
        if min_dist > 20:
            seen.add(hex_str)
            issues.append({
                "color": hex_str,
                "nearest_variable_distance": round(min_dist, 1),
            })
            if len(issues) >= limit:
                return issues
    return issues


def detect_grid_missing_breakpoints(styles: list[str], limit: int = 8) -> list[dict]:
    """Flag grid rules with >4 columns that lack a responsive breakpoint at <=960px."""
    issues: list[dict] = []
    full_css = "\n".join(styles)

    breakpoints_present: set[int] = set()
    for bp_match in MEDIA_QUERY_RE.finditer(full_css):
        breakpoints_present.add(int(bp_match.group(1)))

    has_960_or_below = any(bp <= 960 for bp in breakpoints_present)

    for blob in styles:
        for selector, declarations in CSS_RULE_RE.findall(blob):
            cols_match = GRID_COLS_RE.search(declarations)
            if not cols_match:
                continue
            cols = int(cols_match.group(1))
            if cols <= 4:
                continue
            selector_clean = selector.strip()[:80]
            if not has_960_or_below:
                issues.append({
                    "selector": selector_clean,
                    "columns": cols,
                    "note": f"Grid has {cols} columns but no @media breakpoint at <=960px found.",
                })
                if len(issues) >= limit:
                    return issues
    return issues


def detect_paired_figure_alignment(styles: list[str], limit: int = 8) -> list[dict]:
    """Flag paired-figure containers using align-items: start instead of stretch."""
    issues: list[dict] = []
    for blob in styles:
        for selector, declarations in CSS_RULE_RE.findall(blob):
            selector_clean = selector.strip()
            if not PAIRED_FIGURE_RE.search(selector_clean):
                continue
            align_match = ALIGN_ITEMS_RE.search(declarations)
            if align_match and align_match.group(1).lower() in ("start", "flex-start", "baseline"):
                issues.append({
                    "selector": selector_clean[:80],
                    "align_items": align_match.group(1),
                    "note": "Paired figures should use align-items: stretch for equal height alignment.",
                })
                if len(issues) >= limit:
                    return issues
    return issues


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------

def palette_overlap(figure_palette: Counter, page_palette: Counter, fig_top_k: int,
                    page_top_k: int, tolerance: int = 1) -> dict:
    fig_top = [c for c, _ in figure_palette.most_common(fig_top_k) if not _is_neutral(c)]
    page_top = [c for c, _ in page_palette.most_common(page_top_k) if not _is_neutral(c)]
    if not page_top:
        return {"status": "no_page_colors", "overlap": 0.0, "fig_top": fig_top,
                "page_top": page_top, "matched": [], "missing": []}
    if not fig_top:
        return {"status": "no_figure_colors", "overlap": 0.0, "fig_top": fig_top,
                "page_top": page_top, "matched": [], "missing": []}

    matched: list[tuple[tuple[int, int, int], tuple[int, int, int]]] = []
    missing: list[tuple[int, int, int]] = []
    for color in page_top:
        match = _nearest(color, fig_top, max_dist=64 * tolerance)
        if match is not None:
            matched.append((color, match))
        else:
            missing.append(color)
    overlap = len(matched) / len(page_top)
    return {
        "status": "ok",
        "overlap": overlap,
        "fig_top": [_hex(c) for c in fig_top],
        "page_top": [_hex(c) for c in page_top],
        "matched": [(_hex(p), _hex(f)) for p, f in matched],
        "missing": [_hex(c) for c in missing],
    }


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def _nearest(color: tuple[int, int, int], pool: list[tuple[int, int, int]], max_dist: int):
    best = None
    best_d = max_dist + 1
    for cand in pool:
        d = sum((a - b) ** 2 for a, b in zip(color, cand)) ** 0.5
        if d < best_d:
            best = cand
            best_d = d
    return best


def reference_signature(reports_dir: Path) -> list[dict]:
    """Build a class-token signature for any sibling reports/<other>/index.html."""
    if not reports_dir.is_dir():
        return []
    signatures: list[dict] = []
    for candidate in sorted(reports_dir.iterdir()):
        page = candidate / "index.html"
        if not page.is_file():
            continue
        text = page.read_text(encoding="utf-8", errors="ignore")
        parser = StyleCollector()
        parser.feed(text)
        parser.close()
        signatures.append({
            "path": str(page),
            "classes": Counter(token for blob in parser.classes for token in blob.split()),
        })
    return signatures


def class_overlap(page_classes: Counter, ref_signature: dict) -> float:
    page_top = set(c for c, _ in page_classes.most_common(80))
    ref_top = set(c for c, _ in ref_signature["classes"].most_common(80))
    if not page_top or not ref_top:
        return 0.0
    return len(page_top & ref_top) / max(1, len(page_top | ref_top))


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--manifest", type=Path,
                        help="figures.manifest.json. If omitted, palette check is skipped.")
    parser.add_argument("--reports-dir", type=Path,
                        help="Directory with prior reports/<slug>/index.html for clone scoring.")
    parser.add_argument("--threshold", type=float, default=DEFAULT_OVERLAP_THRESHOLD,
                        help="Required palette overlap (0-1). Default 0.5.")
    parser.add_argument("--dark-luminance", type=float, default=DEFAULT_DARK_LUMINANCE,
                        help="Luminance ceiling for 'dark canvas' sections (default 0.18).")
    parser.add_argument("--clone-threshold", type=float, default=0.7,
                        help="Class-token overlap above this flags a clone (default 0.7).")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.html.is_file():
        print(f"error: not a file: {args.html}", file=sys.stderr)
        return 2

    html_text = args.html.read_text(encoding="utf-8", errors="ignore")
    page_colors, grid_hits, dark_sections = extract_page_colors(html_text)
    page_parser = StyleCollector()
    page_parser.feed(html_text)
    page_parser.close()
    figure_layout_risks = detect_figure_layout_risks(page_parser.styles)
    layout_parser = LayoutInspector()
    layout_parser.feed(html_text)
    layout_parser.close()
    page_class_counter: Counter = Counter(
        token for blob in page_parser.classes for token in blob.split()
    )

    palette = {"status": "skipped", "reason": "no manifest"}
    palette_notes: list[str] = []
    figure_ratios: dict[str, float] = {}
    ratio_notes: list[str] = []
    if args.manifest:
        figure_colors, palette_notes = sample_figures(args.manifest, DEFAULT_FIGURE_TOP_K)
        palette = palette_overlap(
            figure_colors, page_colors, DEFAULT_FIGURE_TOP_K, DEFAULT_PAGE_TOP_K
        )
        figure_ratios, ratio_notes = load_figure_ratios(args.manifest)
    mixed_ratio_rows = detect_mixed_ratio_figure_rows(layout_parser.root, figure_ratios)
    narrow_table_risks = detect_overstretched_tables(layout_parser.tables)
    variable_hue_mismatches = detect_variable_hue_mismatch(page_parser.styles)
    hardcoded_orphans = detect_hardcoded_color_orphans(page_parser.styles)
    grid_breakpoint_issues = detect_grid_missing_breakpoints(page_parser.styles)
    paired_figure_issues = detect_paired_figure_alignment(page_parser.styles)

    clone_hits: list[dict] = []
    if args.reports_dir:
        for sig in reference_signature(args.reports_dir):
            score = class_overlap(page_class_counter, sig)
            if score >= args.clone_threshold:
                clone_hits.append({"path": sig["path"], "score": round(score, 3)})

    issues: list[dict] = []
    if palette.get("status") == "ok" and palette["overlap"] < args.threshold:
        issues.append({
            "kind": "palette_drift",
            "severity": "warning",
            "overlap": round(palette["overlap"], 3),
            "threshold": args.threshold,
            "missing_accents": palette["missing"],
        })
    if palette.get("status") in ("no_figure_colors", "no_page_colors"):
        issues.append({
            "kind": "palette_unavailable",
            "severity": "info",
            "reason": palette["status"],
        })
    if grid_hits:
        issues.append({
            "kind": "grid_or_texture_background",
            "severity": "warning",
            "count": len(grid_hits),
            "note": "grid/dots/paper/notebook background detected; verify it is supported by the paper figures.",
        })
    if len(dark_sections) >= DEFAULT_DARK_REPEAT:
        issues.append({
            "kind": "repeated_dark_canvas",
            "severity": "warning",
            "count": len(dark_sections),
            "note": "multiple dark sections; ensure consistent dark canvas system across the page.",
        })
    if figure_layout_risks:
        issues.append({
            "kind": "figure_layout_blank_space_risk",
            "severity": "warning",
            "count": len(figure_layout_risks),
            "samples": figure_layout_risks,
            "note": (
                "paper figures appear to use fixed height/aspect-ratio or "
                "object-fit: contain outside a modal; preserve natural image "
                "height unless the container ratio is known to match the image."
            ),
        })
    if mixed_ratio_rows:
        issues.append({
            "kind": "mixed_ratio_figure_row",
            "severity": "warning",
            "count": len(mixed_ratio_rows),
            "samples": mixed_ratio_rows,
            "note": (
                "side-by-side figure groups have mismatched aspect ratios; "
                "stack them, group compatible ratios, or pair one figure with "
                "text/table content instead of another image."
            ),
        })
    if narrow_table_risks:
        issues.append({
            "kind": "overstretched_low_column_table",
            "severity": "warning",
            "count": len(narrow_table_risks),
            "samples": narrow_table_risks,
            "note": (
                "tables with three or fewer columns should usually use a "
                "compact/narrow treatment instead of filling the full page width."
            ),
        })
    if variable_hue_mismatches:
        issues.append({
            "kind": "variable_name_hue_mismatch",
            "severity": "warning",
            "count": len(variable_hue_mismatches),
            "samples": variable_hue_mismatches,
            "note": (
                "CSS variable names contain a color word that contradicts the "
                "actual hue of the value. Use semantic names (--primary, --accent) "
                "instead of hue-literal names."
            ),
        })
    if hardcoded_orphans:
        issues.append({
            "kind": "hardcoded_color_drift",
            "severity": "warning",
            "count": len(hardcoded_orphans),
            "samples": hardcoded_orphans[:6],
            "note": (
                "Hex colors in CSS rules outside :root do not match any declared "
                "custom property. Replace with var(--...) references for theme consistency."
            ),
        })
    if grid_breakpoint_issues:
        issues.append({
            "kind": "grid_missing_responsive_breakpoint",
            "severity": "warning",
            "count": len(grid_breakpoint_issues),
            "samples": grid_breakpoint_issues,
            "note": (
                "Grids with >4 columns need a @media (max-width: 960px) breakpoint "
                "that reduces columns. Items may be too narrow on medium screens."
            ),
        })
    if paired_figure_issues:
        issues.append({
            "kind": "paired_figure_alignment_risk",
            "severity": "warning",
            "count": len(paired_figure_issues),
            "samples": paired_figure_issues,
            "note": (
                "Paired figure containers use align-items: start/baseline which "
                "causes height misalignment. Use align-items: stretch with inner "
                "flexbox + object-fit: contain."
            ),
        })
    if clone_hits:
        issues.append({
            "kind": "possible_template_clone",
            "severity": "warning",
            "matches": clone_hits,
        })

    report = {
        "html": str(args.html),
        "palette": palette,
        "palette_notes": palette_notes,
        "ratio_notes": ratio_notes,
        "grid_hits": len(grid_hits),
        "dark_sections": len(dark_sections),
        "figure_layout_risks": figure_layout_risks,
        "mixed_ratio_rows": mixed_ratio_rows,
        "narrow_table_risks": narrow_table_risks,
        "variable_hue_mismatches": variable_hue_mismatches,
        "hardcoded_color_orphans": hardcoded_orphans,
        "grid_breakpoint_issues": grid_breakpoint_issues,
        "paired_figure_issues": paired_figure_issues,
        "clone_hits": clone_hits,
        "issues": issues,
        "summary": {
            "errors": sum(1 for i in issues if i["severity"] == "error"),
            "warnings": sum(1 for i in issues if i["severity"] == "warning"),
            "info": sum(1 for i in issues if i["severity"] == "info"),
        },
    }

    if args.json:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        actionable = [i for i in issues if i["severity"] in ("error", "warning")]
        if not actionable:
            print(f"design drift check OK ({args.html})")
            for item in issues:
                print(f"  - [info] {item['kind']}: "
                      f"{json.dumps({k: v for k, v in item.items() if k not in ('severity', 'kind')}, ensure_ascii=False)}")
        else:
            print(f"design drift findings ({args.html}):")
            for item in issues:
                print(f"  - [{item['severity']}] {item['kind']}: "
                      f"{json.dumps({k: v for k, v in item.items() if k not in ('severity', 'kind')}, ensure_ascii=False)}")
        if palette.get("status") == "ok":
            print(f"  palette overlap: {round(palette['overlap'], 3)}  "
                  f"page_top={palette['page_top']} fig_top={palette['fig_top']}")
        for note in palette_notes:
            print(f"  note: {note}")
        for note in ratio_notes:
            print(f"  note: {note}")

    if report["summary"]["errors"] > 0 or report["summary"]["warnings"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
