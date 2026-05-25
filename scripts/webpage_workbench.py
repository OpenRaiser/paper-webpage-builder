#!/usr/bin/env python3
"""Local visual workbench for paper webpage generation and region repair.

The workbench is intentionally dependency-light:
  - stdlib HTTP server for the UI and JSON API
  - existing repository scripts for scan / validation where possible
  - optional external agent command for applying a saved repair prompt

Default usage:
  python3 scripts/webpage_workbench.py --port 8765

Then open:
  http://127.0.0.1:8765/
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import shutil
import shlex
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = REPO_ROOT / "assets" / "workbench"
SCRIPT_ROOT = REPO_ROOT / "scripts"
DEFAULT_WORK_DIR = ".paper-webpage-builder"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")


@dataclass
class PreviewMount:
    root: Path
    html_path: Path
    project_dir: Path


class WorkbenchState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._mounts: dict[str, PreviewMount] = {}
        self._sessions: dict[str, "ChatSession"] = {}

    def add_mount(self, project_dir: Path, html_path: Path) -> str:
        output_dir = html_path.parent.resolve()
        token_source = f"{project_dir.resolve()}::{output_dir}::{time.time_ns()}"
        token = hashlib.sha1(token_source.encode("utf-8")).hexdigest()[:12]
        with self._lock:
            self._mounts[token] = PreviewMount(
                root=output_dir,
                html_path=html_path.resolve(),
                project_dir=project_dir.resolve(),
            )
        return token

    def get_mount(self, token: str) -> PreviewMount | None:
        with self._lock:
            return self._mounts.get(token)

    def add_session(self, session: "ChatSession") -> None:
        with self._lock:
            self._sessions[session.session_id] = session

    def get_session(self, session_id: str) -> "ChatSession | None":
        with self._lock:
            return self._sessions.get(session_id)


class ChatSession:
    def __init__(self, project_dir: Path, output_dir: Path, filename: str) -> None:
        self.session_id = uuid.uuid4().hex[:12]
        self.project_dir = project_dir.resolve()
        self.output_dir = output_dir.resolve()
        self.filename = filename
        self.created_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        self.messages: list[dict[str, Any]] = []
        self.current_job: AgentJob | None = None
        self.preview_token: str | None = None
        self.html_path: Path | None = None
        self.last_annotation_bundle: dict[str, Any] | None = None

    @property
    def target_html(self) -> Path:
        return self.output_dir / self.filename

    def add_message(self, role: str, content: str, **extra: Any) -> None:
        self.messages.append({
            "role": role,
            "content": content,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            **extra,
        })


class AgentJob:
    def __init__(self, prompt_path: Path, command: list[str], cwd: Path, stdin_text: str) -> None:
        self.job_id = uuid.uuid4().hex[:12]
        self.prompt_path = prompt_path
        self.command = command
        self.cwd = cwd
        self.stdin_text = stdin_text
        self.status = "queued"
        self.stage = "Queued"
        self.progress = 3
        self.returncode: int | None = None
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.logs: list[str] = []
        self.events: list[dict[str, Any]] = []
        self.error: str | None = None
        self._lock = threading.Lock()

    def append_log(self, text: str) -> None:
        text = text.rstrip("\n")
        if not text:
            return
        with self._lock:
            self.logs.append(text)
            if len(self.logs) > 600:
                self.logs = self.logs[-600:]
            self._update_progress_from_text(text)

    def set_progress(self, stage: str, progress: int) -> None:
        with self._lock:
            self.stage = stage
            self.progress = max(self.progress, min(100, progress))
            self.events.append({
                "stage": self.stage,
                "progress": self.progress,
                "at": time.strftime("%H:%M:%S"),
            })
            if len(self.events) > 80:
                self.events = self.events[-80:]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "job_id": self.job_id,
                "status": self.status,
                "stage": self.stage,
                "progress": self.progress,
                "returncode": self.returncode,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "prompt_path": str(self.prompt_path),
                "logs": self.logs[-220:],
                "events": self.events[-50:],
                "error": self.error,
                "cmd": self.command,
            }

    def _update_progress_from_text(self, text: str) -> None:
        lower = text.lower()
        marker = "workbench_progress"
        if marker in lower:
            try:
                payload = json.loads(text[text.index("{"):])
                stage = str(payload.get("stage") or self.stage)
                progress = int(payload.get("percent") or payload.get("progress") or self.progress)
                self.stage = stage
                self.progress = max(self.progress, min(95, progress))
                return
            except Exception:
                pass
        rules = (
            (("inspect", "scan", "inventory", "paper source"), "Inspecting paper", 15),
            (("extract", "citation", "table", "figure"), "Extracting content", 30),
            (("design", "module", "layout", "visual"), "Designing page", 48),
            (("write", "index.html", "implement", "css", "html"), "Implementing webpage", 65),
            (("validate", "screenshot", "check_webpage", "html_sanity"), "Validating output", 82),
            (("final", "done", "complete", "validation"), "Finishing", 92),
        )
        for keys, stage, progress in rules:
            if any(key in lower for key in keys):
                if progress > self.progress:
                    self.stage = stage
                    self.progress = progress
                return


STATE = WorkbenchState()


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("request body must be a JSON object")
    return data


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler: BaseHTTPRequestHandler, status: int, text: str) -> None:
    body = text.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def resolve_existing_dir(path_value: str) -> Path:
    if not path_value:
        raise ValueError("path is required")
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if not path.is_dir():
        raise ValueError(f"not a directory: {path}")
    return path


def safe_child(base: Path, rel: str) -> Path:
    rel_path = Path(unquote(rel.lstrip("/")))
    candidate = (base / rel_path).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise PermissionError("requested path escapes preview root") from exc
    return candidate


def run_command(args: list[str], cwd: Path, timeout: int = 90) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "cmd": args,
        }
    except FileNotFoundError as exc:
        return {"ok": False, "returncode": 127, "stdout": "", "stderr": str(exc), "cmd": args}
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": f"timeout after {timeout}s\n{exc.stderr or ''}",
            "cmd": args,
        }


def default_output_dir(project_dir: Path) -> Path:
    return (project_dir / "webpage").resolve()


def build_agent_command(server: "WorkbenchServer", project_dir: Path) -> list[str]:
    template = str(server.agent_command or "").strip()
    if template:
        return shlex.split(template.replace("{project}", str(project_dir)))
    codex = shutil.which("codex")
    if codex:
        return [
            codex,
            "exec",
            "--cd",
            str(project_dir),
            "--sandbox",
            "danger-full-access",
            "--skip-git-repo-check",
            "--json",
            "-",
        ]
    raise RuntimeError(
        "No agent command is available. Install Codex CLI or start the server with --agent-command."
    )


def parse_agent_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    if not stripped.startswith("{"):
        return stripped
    try:
        event = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped
    event_type = event.get("type") or event.get("event") or "event"
    for key in ("message", "text", "content", "summary", "status"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return f"{event_type}: {value.strip()}"
    if event_type:
        return str(event_type)
    return stripped[:500]


def find_preview_html(project_dir: Path, output_dir: Path, filename: str) -> Path | None:
    candidates = [
        output_dir / filename,
        project_dir / filename,
        project_dir / "webpage" / filename,
        project_dir / "docs" / filename,
        project_dir / "site" / filename,
    ]
    existing = find_existing_html(project_dir)
    if existing:
        candidates.append(existing)
    for candidate in candidates:
        if candidate.is_file() and not is_legacy_placeholder(candidate):
            return candidate.resolve()
    return None


def build_chat_prompt(
    session: ChatSession,
    user_message: str,
    annotation_bundle: dict[str, Any] | None = None,
) -> tuple[str, Path]:
    run_dir = session.project_dir / DEFAULT_WORK_DIR / "agent-runs" / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = run_dir / "prompt.md"

    tex = find_paper_tex(session.project_dir)
    pdf = find_paper_pdf(session.project_dir)
    inventory, scan_result = scan_project(session.project_dir, tex, pdf)
    inventory_path = run_dir / "inventory.json"
    inventory_path.write_text(
        json.dumps({"inventory": inventory, "scan": scan_result}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    recent = session.messages[-8:]
    history = "\n".join(
        f"- {m['role']}: {m['content'][:1200]}" for m in recent if m.get("content")
    )
    annotation_text = ""
    if annotation_bundle:
        prompt_file = annotation_bundle.get("repair_prompt") or annotation_bundle.get("layout_prompt")
        annotation_text = f"""
## Visual Annotation Context

The user selected or adjusted content in the current preview. Use this as local repair context:

- Annotation JSON: `{annotation_bundle.get("annotation_json")}`
- Layout edits JSON: `{annotation_bundle.get("layout_json")}`
- DOM context: `{annotation_bundle.get("context_html")}`
- Repair/layout prompt: `{prompt_file}`
- Screenshot: `{annotation_bundle.get("screenshot") or "not captured"}`
"""

    prompt = f"""# Paper Webpage Builder Agent Session

You are the agent behind a browser-based workbench. The user is chatting with you to create or repair an academic paper webpage.

## User Message

{user_message}

## Project

- Paper project directory: `{session.project_dir}`
- Target output directory: `{session.output_dir}`
- Target HTML: `{session.target_html}`
- Paper-webpage-builder skill repo: `{REPO_ROOT}`
- Skill instructions: `{REPO_ROOT / "SKILL.md"}`
- Workbench visual repair docs: `{REPO_ROOT / "references" / "visual_workbench.md"}`
- Inventory snapshot: `{inventory_path}`

## Conversation History

{history or "(no previous messages)"}
{annotation_text}

## Required Behavior

- Treat this as the normal `paper-webpage-builder` skill workflow, not a toy template.
- If the user asks to build a webpage, run the full skill process: inspect the source, extract content/tables/citation, prepare assets, design paper-specific modules, write the final `index.html`, and validate it.
- Tables must be fully readable as static content in the first rendered page. Do not hide, crop, fade, mask, vertically clip, or horizontally scroll table rows/cells inside a smaller white container. If a table is wide, split/group columns while preserving all values, use multiple full sub-tables, reduce density while staying readable, or redesign the module so the table and its white/card container fit together.
- If the user asks for a local visual fix, use the visual annotation context and make the smallest targeted change.
- Preserve academic meaning, figures, tables, captions, links, labels, and citations.
- Do not generate a generic placeholder page.
- Use the repository scripts under `{REPO_ROOT / "scripts"}` when useful.
- Write final webpage files to `{session.output_dir}` unless the user explicitly says otherwise.
- Emit occasional progress markers as plain lines in this exact shape:
  `WORKBENCH_PROGRESS {{"stage":"Inspecting paper","percent":15}}`

## Completion Criteria

When finished:

- Ensure `{session.target_html}` exists, or clearly explain why it could not be produced.
- Run practical validation checks where possible, including table visual fit (`scripts/check_table_fit.py`) whenever tables are present.
- Summarize generated files, modules, assets, validation, and residual risks.
"""
    prompt_path.write_text(prompt, encoding="utf-8")
    return prompt, prompt_path


def run_agent_job(session: ChatSession, job: AgentJob, server: "WorkbenchServer") -> None:
    job.status = "running"
    job.started_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    job.set_progress("Starting agent", 6)
    try:
        proc = subprocess.Popen(
            job.command,
            cwd=str(job.cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdin is not None
        proc.stdin.write(job.stdin_text)
        proc.stdin.close()
        assert proc.stdout is not None
        for line in proc.stdout:
            parsed = parse_agent_line(line)
            if parsed:
                job.append_log(parsed)
        job.returncode = proc.wait()
        if job.returncode == 0:
            html_path = find_preview_html(session.project_dir, session.output_dir, session.filename)
            if html_path:
                token = STATE.add_mount(session.project_dir, html_path)
                session.preview_token = token
                session.html_path = html_path
                job.set_progress("Preview ready", 100)
                job.status = "completed"
                session.add_message("agent", f"完成。已生成并挂载预览：{html_path}")
            else:
                job.set_progress("Agent finished, HTML missing", 96)
                job.status = "failed"
                job.error = f"Agent completed but {session.target_html} was not found."
                session.add_message("agent", job.error)
        else:
            job.status = "failed"
            job.error = f"Agent command exited with code {job.returncode}."
            session.add_message("agent", job.error)
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        session.add_message("agent", f"执行失败：{exc}")
    finally:
        job.finished_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")


def find_paper_tex(project_dir: Path) -> Path | None:
    preferred = ("main.tex", "paper.tex", "ms.tex", "article.tex")
    for name in preferred:
        candidate = project_dir / name
        if candidate.is_file():
            return candidate
    tex_files = [
        p for p in project_dir.rglob("*.tex")
        if DEFAULT_WORK_DIR not in p.parts and not p.name.startswith("._")
    ]
    return sorted(tex_files, key=lambda p: (len(p.parts), p.name))[0] if tex_files else None


def find_paper_pdf(project_dir: Path) -> Path | None:
    pdfs = [
        p for p in project_dir.rglob("*.pdf")
        if DEFAULT_WORK_DIR not in p.parts and not p.name.startswith("._")
    ]
    return sorted(pdfs, key=lambda p: (len(p.parts), p.name))[0] if pdfs else None


def find_existing_html(project_dir: Path) -> Path | None:
    preferred = (project_dir / "index.html", project_dir / "webpage" / "index.html")
    for candidate in preferred:
        if candidate.is_file():
            return candidate
    excluded_parts = {DEFAULT_WORK_DIR, "reports", ".git", "__pycache__"}
    html_files = [
        p for p in project_dir.rglob("index.html")
        if not any(part in excluded_parts for part in p.parts)
        and p.parts[-3:] != ("assets", "workbench", "index.html")
        and not p.name.startswith("._")
    ]
    return sorted(html_files, key=lambda p: (len(p.parts), p.name))[0] if html_files else None


def is_legacy_placeholder(html_path: Path) -> bool:
    try:
        text = html_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    markers = (
        "Generated by paper-webpage-builder workbench. Treat this as a repairable preview",
        "Extracted Evidence Map",
        "No directly reusable raster/SVG figures were copied",
    )
    return any(marker in text for marker in markers)


def parse_inventory(scan_text: str) -> dict[str, Any]:
    inventory: dict[str, Any] = {
        "title": "",
        "authors": [],
        "abstract": "",
        "sections": [],
        "figures": [],
        "captions": [],
        "tables": [],
        "links": [],
    }
    current: str | None = None
    abstract_lines: list[str] = []
    for raw_line in scan_text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("Title:"):
            inventory["title"] = line.partition(":")[2].strip()
            current = None
            continue
        if line in {"Authors:", "Sections:", "Figures:", "Captions:", "Tables:", "Links:"}:
            current = line[:-1].lower()
            continue
        if line == "Abstract:":
            current = "abstract"
            abstract_lines = []
            continue
        if current == "abstract":
            if not line.strip():
                if abstract_lines:
                    inventory["abstract"] = " ".join(abstract_lines).strip()
                    current = None
                continue
            abstract_lines.append(line.strip())
            continue
        if line.startswith("- ") and current:
            value = line[2:].strip()
            if current == "authors":
                inventory["authors"].append(value)
            elif current == "sections":
                inventory["sections"].append(value)
            elif current == "figures":
                inventory["figures"].append(value)
            elif current == "captions":
                inventory["captions"].append(value)
            elif current == "tables":
                inventory["tables"].append(value)
            elif current == "links":
                inventory["links"].append(value)
    if abstract_lines and not inventory["abstract"]:
        inventory["abstract"] = " ".join(abstract_lines).strip()
    return inventory


def inspect_project(project_dir: Path) -> dict[str, Any]:
    tex = find_paper_tex(project_dir)
    pdf = find_paper_pdf(project_dir)
    html_path = find_existing_html(project_dir)
    figures = [
        str(p.relative_to(project_dir))
        for p in project_dir.rglob("*")
        if p.is_file()
        and p.suffix.lower() in IMAGE_EXTENSIONS
        and DEFAULT_WORK_DIR not in p.parts
        and not p.name.startswith("._")
    ][:80]
    return {
        "project_dir": str(project_dir),
        "paper_tex": str(tex) if tex else None,
        "paper_pdf": str(pdf) if pdf else None,
        "existing_html": str(html_path) if html_path else None,
        "figure_count": len(figures),
        "figures_sample": figures[:20],
    }


def browse_directory(path_value: str | None) -> dict[str, Any]:
    roots = [
        {"label": "Home", "path": str(Path.home())},
        {"label": "Skill Repo", "path": str(REPO_ROOT)},
    ]
    volumes = Path("/Volumes")
    if volumes.is_dir():
        roots.append({"label": "Volumes", "path": str(volumes)})
        for child in sorted(volumes.iterdir(), key=lambda p: p.name.lower()):
            if child.is_dir() and not child.name.startswith("."):
                roots.append({"label": child.name, "path": str(child)})

    if path_value:
        current = Path(path_value).expanduser()
    else:
        current = Path.home()
    if not current.is_absolute():
        current = (Path.cwd() / current)
    current = current.resolve()
    if not current.is_dir():
        raise ValueError(f"not a directory: {current}")

    entries: list[dict[str, Any]] = []
    try:
        iterator = list(current.iterdir())
    except OSError as exc:
        raise ValueError(f"cannot read directory: {current}: {exc}") from exc

    for child in sorted(iterator, key=lambda p: (not p.is_dir(), p.name.lower())):
        if child.name.startswith(".") or child.name.startswith("._"):
            continue
        if not child.is_dir():
            continue
        try:
            has_tex = any((child / name).is_file() for name in ("main.tex", "paper.tex", "ms.tex", "article.tex"))
            has_pdf = any(p.suffix.lower() == ".pdf" for p in child.iterdir() if p.is_file())
            has_html = (child / "index.html").is_file() or (child / "webpage" / "index.html").is_file()
            readable = True
        except OSError:
            has_tex = has_pdf = has_html = False
            readable = False
        entries.append({
            "name": child.name,
            "path": str(child),
            "readable": readable,
            "has_tex": has_tex,
            "has_pdf": has_pdf,
            "has_html": has_html,
        })

    parent = str(current.parent) if current.parent != current else None
    current_files = []
    try:
        current_files = [p.name for p in current.iterdir() if p.is_file()]
    except OSError:
        current_files = []

    return {
        "current": str(current),
        "parent": parent,
        "roots": roots,
        "entries": entries,
        "current_flags": {
            "has_tex": any(name in current_files for name in ("main.tex", "paper.tex", "ms.tex", "article.tex")),
            "has_pdf": any(name.lower().endswith(".pdf") for name in current_files),
            "has_html": "index.html" in current_files or (current / "webpage" / "index.html").is_file(),
        },
    }


def scan_project(project_dir: Path, tex: Path | None, pdf: Path | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if tex:
        result = run_command([sys.executable, str(SCRIPT_ROOT / "scan_paper.py"), str(tex)], REPO_ROOT)
        return parse_inventory(result["stdout"] if result["ok"] else ""), result
    if pdf:
        result = run_command([sys.executable, str(SCRIPT_ROOT / "scan_pdf.py"), str(pdf)], REPO_ROOT)
        return parse_inventory(result["stdout"] if result["ok"] else ""), result
    return {}, {"ok": False, "stdout": "", "stderr": "no paper.tex or PDF found", "cmd": []}


def create_generation_bundle(
    project_dir: Path,
    output_dir: Path,
    inventory: dict[str, Any],
    scan_result: dict[str, Any],
    filename: str = "index.html",
) -> dict[str, str]:
    run_root = project_dir / DEFAULT_WORK_DIR / "generation-runs"
    run_dir = run_root / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    input_payload = {
        "paper_source": {
            "path": str(project_dir),
            "kind": "latex_project" if find_paper_tex(project_dir) else ("pdf_with_assets" if find_paper_pdf(project_dir) else "existing_webpage"),
            "has_figures": bool(inspect_project(project_dir)["figure_count"]),
            "has_tables": bool(inventory.get("tables")),
        },
        "target_output": {
            "directory": str(output_dir),
            "filename": filename,
        },
        "goals": [
            "Build a polished single-page academic project webpage with the same quality bar as the paper-webpage-builder skill workflow.",
            "Use visual assets and central paper evidence; do not replace the skill workflow with a generic scaffold.",
            "Produce an index.html that can be previewed and repaired through the visual workbench.",
        ],
        "constraints": [
            "Preserve academic meaning and central figures/tables.",
            "Do not silently drop important results tables or paper objects.",
            "Run the standard validation scripts after generation when available.",
        ],
    }
    input_path = run_dir / "input.json"
    input_path.write_text(json.dumps(input_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    inventory_path = run_dir / "inventory.json"
    inventory_path.write_text(
        json.dumps({"inventory": inventory, "scan": scan_result}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    prompt = f"""# Full Paper Webpage Generation Request

Use the `paper-webpage-builder` skill from this repository. Do not generate a simplified placeholder page.

## Source Project

`{project_dir}`

## Target Output

Write the final webpage to:

`{output_dir / filename}`

Create or update assets under:

`{output_dir}`

## Required Workflow

Follow the full workflow in `{REPO_ROOT / "SKILL.md"}`:

1. Inspect the paper source/PDF/assets.
2. Build a content map with title, authors, abstract, links, modules, important figures, and central tables.
3. Convert/copy paper figures into web-ready assets.
4. Extract citation information where possible.
5. Design the page around the paper's actual visual language and evidence.
6. Include important tables fully or with an equivalent full static presentation. A table is not acceptable if any row, cell text, or header is clipped by a smaller white/card container, or if the user must scroll horizontally to inspect it. Use column grouping, multiple full sub-tables, readable density reduction, or a larger responsive container instead of `overflow-x:auto`, `overflow:hidden`, fixed-height cards, masks, or partial previews.
7. Validate links, HTML sanity, responsive screenshots, table visual fit, table reconciliation when a ledger exists, and design drift when a figure manifest exists.

## Input Schema Payload

`{input_path}`

## Extracted Inventory Snapshot

`{inventory_path}`

## Quality Bar

The result should match the quality of the pure skill/agent workflow. The workbench is only the UI wrapper for preview and region repair; it must not lower the webpage design quality.

When done, report:

- generated `index.html` path
- modules included
- important figures/tables included
- table visual fit status; any clipped table is a blocker, not a cosmetic issue
- validation results
- remaining risks
"""
    prompt_path = run_dir / "generation_prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    return {
        "run_dir": str(run_dir),
        "input_json": str(input_path),
        "inventory_json": str(inventory_path),
        "generation_prompt": str(prompt_path),
        "target_html": str(output_dir / filename),
    }


def build_repair_prompt(annotation_dir: Path, annotation: dict[str, Any], mount: PreviewMount) -> str:
    prompt = f"""# Region Repair Request

You are editing an academic project webpage generated from a paper folder.

## User Instruction

{annotation.get("instruction") or "(no instruction provided)"}

## Target Files

- Project directory: `{mount.project_dir}`
- HTML file: `{mount.html_path}`
- Annotation JSON: `{annotation_dir / "annotation.json"}`
- DOM context: `{annotation_dir / "context.html"}`

## Repair Constraints

- Make the smallest local HTML/CSS/JS change that resolves the marked issue.
- Use the selected DOM elements and bounding boxes to identify the region.
- Do not rewrite unrelated page sections.
- Do not delete figures, tables, captions, links, labels, or citations to make layout easier.
- Do not fix table layout by clipping rows, hiding overflow, adding horizontal scroll, shrinking text below readability, or showing only a partial preview. Tables must be completely readable as static content; wide tables should use grouped full-value layouts, multiple full sub-tables, or larger responsive modules.
- Prefer responsive layout fixes over fixed pixel hacks.
- After editing, rerun link/html sanity checks, table visual fit, and capture screenshots when available.

## Selection Summary

```json
{json.dumps(annotation.get("selection", {}), ensure_ascii=False, indent=2)}
```

## Viewport

```json
{json.dumps(annotation.get("viewport", {}), ensure_ascii=False, indent=2)}
```

## Candidate DOM Elements

```json
{json.dumps(annotation.get("elements", []), ensure_ascii=False, indent=2)[:12000]}
```
"""
    path = annotation_dir / "repair_prompt.md"
    path.write_text(prompt, encoding="utf-8")
    return str(path)


def build_layout_prompt(layout_dir: Path, layout: dict[str, Any], mount: PreviewMount) -> str:
    prompt = f"""# Canvas Layout Edit Request

The user adjusted webpage modules in the visual canvas. Treat these edits as layout intent, not as a request to preserve absolute positioning.

## Target Files

- Project directory: `{mount.project_dir}`
- HTML file: `{mount.html_path}`
- Layout edits JSON: `{layout_dir / "layout_edits.json"}`

## Required Behavior

- Translate the canvas edits into maintainable, responsive HTML/CSS changes.
- Prefer grid/flex/layout rules, width constraints, spacing, and figure/table composition fixes.
- Canvas movement is recorded as flow-affecting margin/size edits so containers and siblings can reflow in the preview.
- Do not blindly copy temporary margins, `transform`, absolute positioning, or fixed pixel values unless they are genuinely appropriate; infer the intended alignment/spacing/composition and encode it cleanly.
- Preserve academic meaning, figures, tables, captions, links, labels, and citations.
- If a canvas edit involves a table, preserve the full table and keep it completely readable as static content. Do not let table content spill outside a white/card container, require horizontal scrolling, or be hidden by fixed-height/overflow clipping.
- Keep changes scoped to the edited modules and nearby layout containers.
- Re-run link/html sanity checks, table visual fit, and screenshots after editing when available.

## Canvas Edits Summary

```json
{json.dumps(layout.get("edits", []), ensure_ascii=False, indent=2)[:16000]}
```
"""
    path = layout_dir / "layout_prompt.md"
    path.write_text(prompt, encoding="utf-8")
    return str(path)


def write_annotation(data: dict[str, Any]) -> dict[str, Any]:
    token = str(data.get("token") or "")
    mount = STATE.get_mount(token)
    if not mount:
        raise ValueError("unknown or expired preview token")
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    annotation_root = mount.project_dir / DEFAULT_WORK_DIR / "annotations"
    annotation_dir = annotation_root / timestamp
    annotation_dir.mkdir(parents=True, exist_ok=True)

    annotation = {
        "created_at": timestamp,
        "project_dir": str(mount.project_dir),
        "html_path": str(mount.html_path),
        "preview_root": str(mount.root),
        "page": data.get("page"),
        "instruction": data.get("instruction", ""),
        "viewport": data.get("viewport", {}),
        "selection": data.get("selection", {}),
        "elements": data.get("elements", []),
    }
    (annotation_dir / "annotation.json").write_text(
        json.dumps(annotation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    context_html = "\n\n".join(
        str(item.get("outerHTML", "")) for item in annotation["elements"] if item.get("outerHTML")
    )
    (annotation_dir / "context.html").write_text(context_html, encoding="utf-8")

    screenshot = str(data.get("screenshot") or "")
    screenshot_path = None
    if screenshot.startswith("data:image/"):
        header, _, payload = screenshot.partition(",")
        ext = ".png" if "png" in header else ".jpg"
        screenshot_path = annotation_dir / f"selection{ext}"
        screenshot_path.write_bytes(base64.b64decode(payload))

    prompt_path = build_repair_prompt(annotation_dir, annotation, mount)
    return {
        "annotation_dir": str(annotation_dir),
        "annotation_json": str(annotation_dir / "annotation.json"),
        "context_html": str(annotation_dir / "context.html"),
        "repair_prompt": prompt_path,
        "screenshot": str(screenshot_path) if screenshot_path else None,
    }


def write_layout_edits(data: dict[str, Any]) -> dict[str, Any]:
    token = str(data.get("token") or "")
    mount = STATE.get_mount(token)
    if not mount:
        raise ValueError("unknown or expired preview token")
    edits = data.get("edits")
    if not isinstance(edits, list) or not edits:
        raise ValueError("edits must be a non-empty array")
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    layout_root = mount.project_dir / DEFAULT_WORK_DIR / "layout-edits"
    layout_dir = layout_root / timestamp
    layout_dir.mkdir(parents=True, exist_ok=True)
    layout = {
        "created_at": timestamp,
        "project_dir": str(mount.project_dir),
        "html_path": str(mount.html_path),
        "preview_root": str(mount.root),
        "page": data.get("page"),
        "zoom": data.get("zoom", 1),
        "edits": edits,
    }
    layout_json = layout_dir / "layout_edits.json"
    layout_json.write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")
    prompt_path = build_layout_prompt(layout_dir, layout, mount)
    return {
        "annotation_dir": str(layout_dir),
        "layout_json": str(layout_json),
        "repair_prompt": prompt_path,
        "layout_prompt": prompt_path,
        "kind": "canvas_layout_edits",
    }


def validate_page(html_path: Path) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    checks["links"] = run_command(
        [sys.executable, str(SCRIPT_ROOT / "check_webpage_links.py"), str(html_path), "--full", "--json"],
        REPO_ROOT,
        timeout=60,
    )
    html_sanity = run_command(
        [sys.executable, str(SCRIPT_ROOT / "check_html_sanity.py"), str(html_path), "--json"],
        REPO_ROOT,
        timeout=60,
    )
    if (
        not html_sanity["ok"]
        and "<main> is not recognized" in html_sanity.get("stdout", "") + html_sanity.get("stderr", "")
    ):
        fallback = run_command(
            [
                sys.executable,
                str(SCRIPT_ROOT / "check_html_sanity.py"),
                str(html_path),
                "--backend",
                "stdlib-fallback",
                "--json",
            ],
            REPO_ROOT,
            timeout=60,
        )
        checks["html_sanity"] = {
            "ok": fallback["ok"],
            "primary": html_sanity,
            "fallback": fallback,
            "note": "Primary tidy backend appears to be pre-HTML5; stdlib fallback was used for structural sanity.",
        }
    else:
        checks["html_sanity"] = html_sanity
    checks["table_fit"] = run_command(
        [sys.executable, str(SCRIPT_ROOT / "check_table_fit.py"), str(html_path), "--json"],
        REPO_ROOT,
        timeout=90,
    )
    screenshot_dir = html_path.parent / DEFAULT_WORK_DIR / "screenshots"
    checks["screenshots"] = run_command(
        [sys.executable, str(SCRIPT_ROOT / "capture_screenshots.py"), str(html_path), "--out-dir", str(screenshot_dir), "--json"],
        REPO_ROOT,
        timeout=120,
    )
    return checks


class WorkbenchHandler(BaseHTTPRequestHandler):
    server_version = "PaperWebpageWorkbench/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), format % args))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path in {"/", "/index.html"}:
                return self.serve_file(UI_ROOT / "index.html")
            if parsed.path in {"/styles.css", "/app.js"}:
                return self.serve_file(UI_ROOT / parsed.path.lstrip("/"))
            if parsed.path.startswith("/workbench/"):
                return self.serve_file(safe_child(UI_ROOT, parsed.path.removeprefix("/workbench/")))
            if parsed.path.startswith("/preview/"):
                return self.serve_preview(parsed.path)
            if parsed.path == "/api/health":
                return json_response(self, 200, {"ok": True, "repo_root": str(REPO_ROOT)})
            if parsed.path == "/api/browse":
                query = parse_qs(parsed.query)
                path_value = (query.get("path") or [""])[0] or None
                return json_response(self, 200, {"ok": True, "browse": browse_directory(path_value)})
            if parsed.path == "/api/session":
                query = parse_qs(parsed.query)
                session_id = (query.get("id") or [""])[0]
                return self.handle_session_status(session_id)
            return text_response(self, HTTPStatus.NOT_FOUND, "not found")
        except PermissionError as exc:
            return json_response(self, HTTPStatus.FORBIDDEN, {"ok": False, "error": str(exc)})
        except Exception as exc:
            return json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            data = read_json(self)
            if parsed.path == "/api/project":
                project_dir = resolve_existing_dir(str(data.get("path") or ""))
                return json_response(self, 200, {"ok": True, "project": inspect_project(project_dir)})
            if parsed.path == "/api/session":
                return self.handle_create_session(data)
            if parsed.path == "/api/chat":
                return self.handle_chat(data)
            if parsed.path == "/api/generate":
                return self.handle_generate(data)
            if parsed.path == "/api/annotation":
                bundle = write_annotation(data)
                session_id = str(data.get("session_id") or "")
                session = STATE.get_session(session_id) if session_id else None
                if session:
                    session.last_annotation_bundle = bundle
                return json_response(self, 200, {"ok": True, "bundle": bundle})
            if parsed.path == "/api/layout-edits":
                bundle = write_layout_edits(data)
                session_id = str(data.get("session_id") or "")
                session = STATE.get_session(session_id) if session_id else None
                if session:
                    session.last_annotation_bundle = bundle
                return json_response(self, 200, {"ok": True, "bundle": bundle})
            if parsed.path == "/api/validate":
                return self.handle_validate(data)
            if parsed.path == "/api/run-agent":
                return self.handle_run_agent(data)
            return text_response(self, HTTPStatus.NOT_FOUND, "not found")
        except ValueError as exc:
            return json_response(self, HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        except Exception as exc:
            return json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})

    def serve_file(self, path: Path) -> None:
        if not path.is_file():
            return text_response(self, HTTPStatus.NOT_FOUND, "not found")
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_preview(self, path: str) -> None:
        parts = path.removeprefix("/preview/").split("/", 1)
        token = parts[0]
        rel = parts[1] if len(parts) > 1 and parts[1] else "index.html"
        mount = STATE.get_mount(token)
        if not mount:
            return text_response(self, HTTPStatus.NOT_FOUND, "unknown preview token")
        target = safe_child(mount.root, rel)
        return self.serve_file(target)

    def session_payload(self, session: ChatSession) -> dict[str, Any]:
        job = session.current_job.snapshot() if session.current_job else None
        preview_url = None
        if session.preview_token and session.html_path:
            rel = session.html_path.name
            preview_url = f"/preview/{session.preview_token}/{rel}"
        return {
            "session_id": session.session_id,
            "project_dir": str(session.project_dir),
            "output_dir": str(session.output_dir),
            "filename": session.filename,
            "target_html": str(session.target_html),
            "html_path": str(session.html_path) if session.html_path else None,
            "preview_token": session.preview_token,
            "preview_url": preview_url,
            "messages": session.messages,
            "job": job,
            "annotation_bundle": session.last_annotation_bundle,
        }

    def handle_create_session(self, data: dict[str, Any]) -> None:
        project_dir = resolve_existing_dir(str(data.get("path") or ""))
        output_value = str(data.get("output_dir") or "webpage").strip()
        output_dir = Path(output_value).expanduser()
        if not output_dir.is_absolute():
            output_dir = project_dir / output_dir
        filename = str(data.get("filename") or "index.html").strip() or "index.html"
        session = ChatSession(project_dir, output_dir, filename)
        html_path = find_preview_html(project_dir, output_dir, filename)
        if html_path:
            session.html_path = html_path
            session.preview_token = STATE.add_mount(project_dir, html_path)
        session.add_message(
            "system",
            "会话已创建。你可以直接描述要构建或修复的 paper webpage。",
        )
        STATE.add_session(session)
        return json_response(self, 200, {"ok": True, "session": self.session_payload(session)})

    def handle_session_status(self, session_id: str) -> None:
        session = STATE.get_session(session_id)
        if not session:
            raise ValueError("unknown session_id")
        return json_response(self, 200, {"ok": True, "session": self.session_payload(session)})

    def handle_chat(self, data: dict[str, Any]) -> None:
        session_id = str(data.get("session_id") or "")
        session = STATE.get_session(session_id)
        if not session:
            raise ValueError("unknown session_id")
        if session.current_job and session.current_job.status in {"queued", "running"}:
            raise ValueError("an agent job is already running for this session")
        message = str(data.get("message") or "").strip()
        if not message:
            raise ValueError("message is required")
        annotation_bundle = session.last_annotation_bundle if data.get("include_annotation") else None
        session.add_message("user", message)
        prompt, prompt_path = build_chat_prompt(session, message, annotation_bundle)
        command = build_agent_command(self.server, session.project_dir)  # type: ignore[arg-type]
        job = AgentJob(prompt_path=prompt_path, command=command, cwd=session.project_dir, stdin_text=prompt)
        session.current_job = job
        thread = threading.Thread(target=run_agent_job, args=(session, job, self.server), daemon=True)
        thread.start()
        return json_response(self, 200, {"ok": True, "session": self.session_payload(session)})

    def handle_generate(self, data: dict[str, Any]) -> None:
        project_dir = resolve_existing_dir(str(data.get("path") or ""))
        requested_output = str(data.get("output_dir") or "").strip()
        filename = str(data.get("filename") or "index.html").strip() or "index.html"
        if requested_output:
            output_dir = Path(requested_output).expanduser()
            if not output_dir.is_absolute():
                output_dir = project_dir / output_dir
        else:
            output_dir = project_dir / DEFAULT_WORK_DIR / "webpage"
        output_dir = output_dir.resolve()
        target_html = (output_dir / filename).resolve()

        existing_html = find_existing_html(project_dir)
        reuse_existing = bool(data.get("reuse_existing", True))
        tex = find_paper_tex(project_dir)
        pdf = find_paper_pdf(project_dir)
        inventory, scan_result = scan_project(project_dir, tex, pdf)
        generation_bundle = create_generation_bundle(
            project_dir=project_dir,
            output_dir=output_dir,
            inventory=inventory,
            scan_result=scan_result,
            filename=filename,
        )
        generation_result: dict[str, Any] | None = None
        html_path: Path | None = None
        status = "prompt_saved"

        if reuse_existing and existing_html:
            html_path = existing_html.resolve()
            status = "preview_existing"
        elif target_html.is_file() and not is_legacy_placeholder(target_html):
            html_path = target_html
            status = "preview_generated"
        else:
            command_template = str(self.server.generate_command or "").strip()  # type: ignore[attr-defined]
            if command_template:
                output_dir.mkdir(parents=True, exist_ok=True)
                command = (
                    command_template
                    .replace("{prompt}", generation_bundle["generation_prompt"])
                    .replace("{project}", str(project_dir))
                    .replace("{output}", str(output_dir))
                    .replace("{html}", str(target_html))
                )
                generation_result = run_command(shlex.split(command), project_dir, timeout=1800)
                if target_html.is_file() and not is_legacy_placeholder(target_html):
                    html_path = target_html
                    status = "generated_by_agent"
                else:
                    status = "agent_finished_no_html" if generation_result["ok"] else "agent_failed"

        token = STATE.add_mount(project_dir, html_path) if html_path else None
        return json_response(self, 200, {
            "ok": True,
            "status": status,
            "html_path": str(html_path) if html_path else None,
            "preview_url": f"/preview/{token}/{filename}" if token else None,
            "token": token,
            "reused_existing": bool(reuse_existing and existing_html),
            "inventory": inventory,
            "generation_bundle": generation_bundle,
            "generation_result": generation_result,
            "scan": scan_result,
        })

    def handle_validate(self, data: dict[str, Any]) -> None:
        token = str(data.get("token") or "")
        mount = STATE.get_mount(token)
        if not mount:
            raise ValueError("unknown or expired preview token")
        checks = validate_page(mount.html_path)
        return json_response(self, 200, {"ok": True, "checks": checks})

    def handle_run_agent(self, data: dict[str, Any]) -> None:
        command_template = str(self.server.agent_command or "").strip()  # type: ignore[attr-defined]
        if not command_template:
            return json_response(
                self,
                HTTPStatus.CONFLICT,
                {
                    "ok": False,
                    "error": "server was not started with --agent-command; use the saved repair_prompt.md manually",
                },
            )
        prompt = str(data.get("repair_prompt") or "")
        if not prompt or not Path(prompt).is_file():
            raise ValueError("repair_prompt must point to an existing file")
        prompt_path = Path(prompt).resolve()
        annotation_json = prompt_path.parent / "annotation.json"
        annotation = json.loads(annotation_json.read_text(encoding="utf-8"))
        html_path = Path(annotation["html_path"]).resolve()
        project_dir = Path(annotation["project_dir"]).resolve()
        command = (
            command_template
            .replace("{prompt}", str(prompt_path))
            .replace("{html}", str(html_path))
            .replace("{project}", str(project_dir))
        )
        result = run_command(shlex.split(command), project_dir, timeout=600)
        return json_response(self, 200, {"ok": result["ok"], "result": result})


class WorkbenchServer(ThreadingHTTPServer):
    agent_command: str | None
    generate_command: str | None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--agent-command",
        default=None,
        help=(
            "Optional command template for /api/run-agent. Placeholders: "
            "{prompt}, {html}, {project}. Example: 'codex exec --cd {project} -- \"$(cat {prompt})\"'"
        ),
    )
    parser.add_argument(
        "--generate-command",
        default=None,
        help=(
            "Optional command template used by /api/generate to run the full skill/agent generation. "
            "Placeholders: {prompt}, {project}, {output}, {html}."
        ),
    )
    args = parser.parse_args()

    server = WorkbenchServer((args.host, args.port), WorkbenchHandler)
    server.agent_command = args.agent_command
    server.generate_command = args.generate_command
    print(f"Paper webpage workbench: http://{args.host}:{args.port}/")
    if args.agent_command:
        print(f"Agent command enabled: {args.agent_command}")
    elif shutil.which("codex"):
        print("Agent command: default local codex exec")
    else:
        print("Agent command unavailable; install Codex CLI or restart with --agent-command.")
    if args.generate_command:
        print(f"Legacy /api/generate command enabled: {args.generate_command}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
