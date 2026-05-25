# Agent Workbench Loop

Use the local workbench as a browser interface for the paper webpage agent. The UI should feel like Codex/Claude for this skill: the user chats naturally, the agent runs the full `paper-webpage-builder` workflow, progress is shown while work is running, and the generated page is previewed for visual repair.

## Start

From this skill directory:

```bash
python3 scripts/webpage_workbench.py --port 8765
```

Open:

```text
http://127.0.0.1:8765/
```

By default the server uses local `codex exec` when available. To route to another agent, start with:

```bash
python3 scripts/webpage_workbench.py --port 8765 --agent-command "<command that reads prompt from stdin>"
```

The command template may include `{project}`.

## Main Loop

1. Enter the paper project folder.
2. Set the output folder, usually `webpage`.
3. Click **Start Session**.
4. Chat naturally, for example:

```text
为这个论文构建一个高质量 project webpage，输出到 webpage/index.html。使用现有 skill 流程，包含主要图表、引用、资源按钮和响应式验证。
```

5. The backend creates a prompt under:

```text
<paper-project>/.paper-webpage-builder/agent-runs/<timestamp>/prompt.md
```

6. The agent runs in the background. The UI shows:
   - stage label
   - progress bar
   - agent log
   - final preview when `index.html` is found

## Agent Contract

For build requests, the agent must use the real skill workflow from `SKILL.md`; it must not generate a generic placeholder page.

Expected behavior:

- Inspect paper source/PDF/assets.
- Extract title, authors, abstract, links, figures, tables, and citation.
- Convert/copy paper figures into web-ready assets.
- Build paper-specific page modules.
- Include central evidence tables fully or with equivalent complete presentation.
- Write final output to the session target, usually `webpage/index.html`.
- Run practical validation checks and report residual risks.

The prompt asks the agent to emit optional progress lines:

```text
WORKBENCH_PROGRESS {"stage":"Inspecting paper","percent":15}
```

The UI also infers progress from ordinary log text, so the marker is helpful but not mandatory.

## Visual Repair Loop

After a preview is available:

1. Use `+` / `-` to zoom the rendered page when needed.
2. Click **Mark Region**.
3. Drag over the visual defect in the iframe preview.
   - The selected rectangle is stored in document coordinates and redrawn from `scrollX`/`scrollY`, so it follows the target while the iframe scrolls.
   - Zoom is visual only; saved coordinates are normalized back to the rendered page's CSS pixel coordinate system.
4. The workbench saves:

```text
<paper-project>/.paper-webpage-builder/annotations/<timestamp>/
```

The bundle contains:

- `annotation.json`: viewport, selected region, DOM selectors, bounding boxes, computed styles, and target paths.
- `context.html`: selected DOM snippets.
- `repair_prompt.md`: local repair prompt.

5. The chat composer enables **Include selected region**.
6. Send a normal repair instruction, such as:

```text
这两个并排图底边没有对齐，只修这个区域，不要重写整页。
```

The next agent prompt includes the saved annotation context.

## Canvas Layout Mode

For stronger visual layout feedback, click **Canvas Mode** after a preview is available.

- The workbench detects common modules: sections, figures, tables, images, headings, paragraphs, lists, and card-like blocks.
- Modules can be dragged in the preview. Dragging uses flow-affecting margin/size edits, not visual-only transforms, so surrounding containers and siblings can reflow while you experiment.
- The selected module has a resize handle in the lower-right corner.
- Use **Undo** / **Redo**, `Cmd/Ctrl+Z`, `Cmd/Ctrl+Shift+Z`, or `Cmd/Ctrl+Y` to move through canvas edit history.
- These edits are preview-only. They are not written directly into the source HTML/CSS.
- Click **Save Layout** to write:

```text
<paper-project>/.paper-webpage-builder/layout-edits/<timestamp>/
```

The bundle contains:

- `layout_edits.json`: selectors, original styles, before/after boxes, transforms, and module snippets.
- `layout_prompt.md`: an agent prompt for converting the canvas intent into maintainable responsive HTML/CSS.

After saving, send a normal chat instruction such as:

```text
按照我刚才在 Canvas Mode 里拖动和缩放的意图，把这些模块排版改好。不要使用脆弱的 absolute 定位，尽量用 grid/flex 和响应式 CSS。
```

The agent should treat canvas edits as layout intent, not as exact absolute coordinates or margin values to copy.

## Coordinate Model

The workbench stores both viewport coordinates and document coordinates:

- `selection.viewport`: coordinates relative to the iframe viewport at selection time.
- `selection.document`: stable coordinates relative to the full rendered document.
- `selection.zoom`: visual zoom used while selecting.
- `elements[].bbox`: candidate element viewport bounding box.
- `elements[].documentBbox`: candidate element document bounding box.

The saved viewport block also includes scroll offsets and device pixel ratio:

```text
document_x = selection.x + viewport.scrollX
document_y = selection.y + viewport.scrollY
```

DOM selectors and bounding boxes are the primary localization signal. Coordinates are supporting evidence.

Direct drag-to-resize layout editing is intentionally not implemented as source mutation. The UI provides coordinateized selection and zoomed inspection; the agent then makes controlled HTML/CSS changes against the selected DOM context. This avoids corrupting semantic structure while still allowing any rendered area to be selected and repaired.
