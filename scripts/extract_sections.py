#!/usr/bin/env python3
"""Extract per-section body prose from a LaTeX paper for deep reading.

`scan_paper.py` produces the skeleton (title, captions, table metadata) but
never emits the body text of each section. Without that text the builder agent
can only paraphrase the abstract and invent section headings, which is the
main cause of shallow, generic project pages.

This script segments the paper by `\\section`/`\\subsection`, cleans the prose
(removing float/equation noise while preserving citations as `[cite]` and
keeping `itemize`/`enumerate` contribution lists in full), and prints readable
body text per section. The builder agent reads this to understand the paper's
actual argument before designing the page.

Multi-file projects are supported via the same `\\input`/`\\include` following
as `scan_paper.py`.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

INPUT_RE = re.compile(r"\\(?:input|include|subfile)\{([^{}]+)\}")
MAX_INCLUDE_DEPTH = 6
DEFAULT_MAX_CHARS = 2600

# Float / display environments whose raw bodies are noise for prose reading.
# Their captions are already covered by scan_paper.py / extract_tables.py.
DROP_ENVIRONMENTS = (
    "figure", "figure*", "table", "table*", "tabular", "tabularx", "array",
    "wraptable", "wrapfigure", "align", "align*", "equation", "equation*",
    "gather", "gather*", "multline", "multline*", "tikzpicture", "lstlisting",
    "verbatim", "minted",
)


def strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("%"):
            continue
        lines.append(re.sub(r"(?<!\\)%.*", "", line))
    return "\n".join(lines)


def read_text_with_warning(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        for encoding in ("utf-8-sig", "gb18030", "shift_jis", "euc-kr"):
            try:
                text = path.read_text(encoding=encoding)
                print(
                    f"warning: {path} decoded with fallback encoding `{encoding}` "
                    f"(not UTF-8). Re-save the file as UTF-8 to silence this.",
                    file=sys.stderr,
                )
                return text
            except (UnicodeDecodeError, LookupError):
                continue
        text = path.read_text(encoding="latin-1", errors="replace")
        print(
            f"warning: {path} could not be decoded as UTF-8 nor common CJK "
            f"encodings; fell back to latin-1 with replacement.",
            file=sys.stderr,
        )
        return text


def read_with_inputs(root: Path) -> str:
    visited: set[Path] = set()
    chunks: list[str] = []

    def load(path: Path, depth: int) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if resolved in visited or depth > MAX_INCLUDE_DEPTH or not resolved.is_file():
            return
        visited.add(resolved)
        text = strip_comments(read_text_with_warning(resolved))
        chunks.append(text)
        for match in INPUT_RE.finditer(text):
            ref = match.group(1).strip()
            if not ref:
                continue
            candidate = resolved.parent / ref
            if candidate.suffix == "":
                candidate = candidate.with_suffix(".tex")
            load(candidate, depth + 1)

    load(root, 0)
    return "\n\n".join(chunks)
def drop_environments(text: str) -> str:
    """Remove float/display environment bodies, but keep list environments."""
    for env in DROP_ENVIRONMENTS:
        pattern = re.compile(
            r"\\begin\{" + re.escape(env) + r"\}.*?\\end\{" + re.escape(env) + r"\}",
            re.S,
        )
        text = pattern.sub(" ", text)
    return text


def clean_prose(text: str) -> str:
    """Turn LaTeX body text into readable prose while keeping list structure."""
    text = drop_environments(text)

    # Drop \input/\include lines: their target paths (e.g. Tables/foo) would
    # otherwise leak in as stray prose tokens.
    text = re.sub(r"\\(?:input|include|subfile)\{[^{}]*\}", " ", text)

    # Spacing commands with a length arg leave fragments like "-2pt"/"-1mm"
    # once the command name is stripped; remove the whole command+arg first.
    text = re.sub(
        r"\\(?:v|h)space\*?\{[^{}]*\}|\\(?:setlength|addvspace|vskip|hskip)\b[^\n]*",
        " ",
        text,
    )
    text = re.sub(r"\\(?:smallskip|medskip|bigskip|noindent|centering|par)\b", " ", text)

    # Preserve itemize/enumerate items as bullet lines (contribution lists,
    # which are high-signal for the page's "contributions" framing).
    text = re.sub(r"\\begin\{(itemize|enumerate|description)\}(?:\[[^\]]*\])?", "\n", text)
    text = re.sub(r"\\end\{(itemize|enumerate|description)\}", "\n", text)
    text = re.sub(r"\\item\s*(?:\[[^\]]*\])?", "\n- ", text)

    # Inline emphasis: keep the visible text, drop the wrapper.
    for cmd in ("textbf", "textit", "emph", "textsc", "texttt", "underline"):
        text = re.sub(r"\\" + cmd + r"\{([^{}]*)\}", r"\1", text)

    # Citations / refs collapse to compact placeholders so sentences stay intact.
    text = re.sub(r"\\(?:cite|citep|citet|citeauthor)\{[^{}]*\}", "[cite]", text)
    text = re.sub(r"\\(?:ref|cref|Cref|autoref|eqref)\{[^{}]*\}", "[ref]", text)
    text = re.sub(r"\\(?:label)\{[^{}]*\}", "", text)
    text = re.sub(r"\\footnote\{[^{}]*\}", "", text)

    # Inline math: replace with a marker rather than dumping TeX tokens.
    text = re.sub(r"\$[^$]*\$", "[math]", text)

    # Resolve remaining `\cmd{...}` from the inside out so nested wrappers like
    # `\textbf{Source-layer (\texttt{.tex})}` keep their full visible text. A
    # single pass would skip the outer command once it sees an inner brace.
    one_arg = re.compile(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}")
    for _ in range(6):
        new_text = one_arg.sub(r"\1", text)
        if new_text == text:
            break
        text = new_text

    # Remaining bare commands -> drop.
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)
    text = text.replace("\\&", "&").replace("~", " ")
    text = text.replace("{", "").replace("}", "")

    # Collapse whitespace but keep paragraph + bullet breaks.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    # Merge consecutive [math]/[cite]/[ref] noise.
    text = re.sub(r"(?:\[(?:math|cite|ref)\]\s*){3,}", "[...] ", text)
    return text.strip()


SECTION_RE = re.compile(r"\\(section|subsection|subsubsection)\*?\{([^{}]+)\}")


def clean_heading(value: str) -> str:
    value = re.sub(r"\\[a-zA-Z]+\*?", "", value)
    value = value.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", value).strip()


def segment_sections(text: str) -> list[tuple[str, str, str]]:
    """Return [(level, heading, body)] in document order."""
    matches = list(SECTION_RE.finditer(text))
    sections: list[tuple[str, str, str]] = []
    for i, match in enumerate(matches):
        level = match.group(1)
        heading = clean_heading(match.group(2))
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = clean_prose(text[start:end])
        sections.append((level, heading, body))
    return sections


def first_paragraphs(body: str, max_chars: int) -> str:
    if len(body) <= max_chars:
        return body
    truncated = body[:max_chars]
    # Cut at the last sentence boundary for readability.
    cut = max(truncated.rfind(". "), truncated.rfind(".\n"))
    if cut > max_chars * 0.6:
        truncated = truncated[: cut + 1]
    return truncated.rstrip() + " […truncated]"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paper_tex", type=Path)
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help="Max characters of body text printed per section (default 2600).",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Print full section bodies without truncation.",
    )
    args = parser.parse_args()

    if not args.paper_tex.is_file():
        print(f"error: not a file: {args.paper_tex}", file=sys.stderr)
        return 2

    text = read_with_inputs(args.paper_tex)
    sections = segment_sections(text)

    print("# Section Prose\n")
    print(
        "Use this to understand the paper's actual argument before designing "
        "the page. Build a Paper Brief from this content; do not paraphrase the "
        "abstract or invent section meanings. See references/paper_reading.md.\n"
    )

    if not sections:
        print("(no \\section commands found; this may be a PDF-only project)")
        return 0

    for level, heading, body in sections:
        prefix = "##" if level == "section" else "###"
        print(f"{prefix} {heading}")
        if not body:
            print("(no body prose — likely a float-only or list-only section)\n")
            continue
        shown = body if args.full else first_paragraphs(body, args.max_chars)
        print(shown)
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())