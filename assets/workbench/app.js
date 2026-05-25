const state = {
  sessionId: null,
  token: null,
  previewUrl: null,
  htmlPath: null,
  marking: false,
  dragStart: null,
  selection: null,
  elements: [],
  annotationBundle: null,
  pollTimer: null,
  lastJobStatus: null,
  zoom: 1,
  frameScrollHandler: null,
  frameMouseMoveHandler: null,
  frameMouseUpHandler: null,
  frameKeydownHandler: null,
  canvasMode: false,
  canvasModules: [],
  canvasEdits: new Map(),
  canvasHistory: [],
  canvasRedo: [],
  selectedCanvasModule: null,
  canvasGesture: null,
  canvasResources: new Map()
};

const els = {
  status: document.getElementById("status"),
  projectPath: document.getElementById("projectPath"),
  browseBtn: document.getElementById("browseBtn"),
  browserPanel: document.getElementById("browserPanel"),
  browserRoots: document.getElementById("browserRoots"),
  browserPath: document.getElementById("browserPath"),
  browserList: document.getElementById("browserList"),
  parentDirBtn: document.getElementById("parentDirBtn"),
  useFolderBtn: document.getElementById("useFolderBtn"),
  outputDir: document.getElementById("outputDir"),
  newSessionBtn: document.getElementById("newSessionBtn"),
  inspectBtn: document.getElementById("inspectBtn"),
  stageLabel: document.getElementById("stageLabel"),
  progressNumber: document.getElementById("progressNumber"),
  progressBar: document.getElementById("progressBar"),
  messages: document.getElementById("messages"),
  chatForm: document.getElementById("chatForm"),
  chatInput: document.getElementById("chatInput"),
  includeAnnotation: document.getElementById("includeAnnotation"),
  sendBtn: document.getElementById("sendBtn"),
  agentLog: document.getElementById("agentLog"),
  previewLabel: document.getElementById("previewLabel"),
  coordLabel: document.getElementById("coordLabel"),
  zoomOutBtn: document.getElementById("zoomOutBtn"),
  zoomInBtn: document.getElementById("zoomInBtn"),
  zoomLabel: document.getElementById("zoomLabel"),
  canvasBtn: document.getElementById("canvasBtn"),
  stashBtn: document.getElementById("stashBtn"),
  undoBtn: document.getElementById("undoBtn"),
  redoBtn: document.getElementById("redoBtn"),
  saveLayoutBtn: document.getElementById("saveLayoutBtn"),
  markBtn: document.getElementById("markBtn"),
  validateBtn: document.getElementById("validateBtn"),
  previewWrap: document.getElementById("previewWrap"),
  previewFrame: document.getElementById("previewFrame"),
  overlay: document.getElementById("overlay"),
  selectionBox: document.getElementById("selectionBox"),
  resourceShelf: document.getElementById("resourceShelf"),
  resourceCount: document.getElementById("resourceCount"),
  resourceList: document.getElementById("resourceList")
};

function setStatus(message, tone = "") {
  els.status.textContent = message;
  els.status.className = `status ${tone}`.trim();
}

async function api(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {})
  });
  const payload = await response.json();
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

async function getJson(path) {
  const response = await fetch(path);
  const payload = await response.json();
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

function requireProjectPath() {
  const path = els.projectPath.value.trim();
  if (!path) {
    throw new Error("Enter a paper project folder first.");
  }
  return path;
}

async function browsePath(path) {
  setStatus("Reading folders...", "busy");
  const query = path ? `?path=${encodeURIComponent(path)}` : "";
  const payload = await getJson(`/api/browse${query}`);
  renderBrowser(payload.browse);
  els.browserPanel.hidden = false;
  setStatus("Choose a folder");
}

function renderBrowser(browse) {
  els.browserPath.textContent = browse.current;
  els.parentDirBtn.disabled = !browse.parent;
  els.parentDirBtn.dataset.path = browse.parent || "";
  els.useFolderBtn.dataset.path = browse.current;

  els.browserRoots.innerHTML = "";
  for (const root of browse.roots || []) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = root.label;
    button.title = root.path;
    button.addEventListener("click", () => browsePath(root.path).catch(error => setStatus(error.message, "error")));
    els.browserRoots.appendChild(button);
  }

  els.browserList.innerHTML = "";
  for (const entry of browse.entries || []) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "browser-entry";
    row.disabled = !entry.readable;
    const badges = [];
    if (entry.has_tex) badges.push("TeX");
    if (entry.has_pdf) badges.push("PDF");
    if (entry.has_html) badges.push("HTML");
    row.innerHTML = `<span>${entry.name}</span><small>${badges.join(" ")}</small>`;
    row.addEventListener("click", () => browsePath(entry.path).catch(error => setStatus(error.message, "error")));
    els.browserList.appendChild(row);
  }
}

function chooseCurrentFolder() {
  const path = els.useFolderBtn.dataset.path;
  if (!path) {
    return;
  }
  els.projectPath.value = path;
  els.browserPanel.hidden = true;
  setStatus("Folder selected");
}

function addMessage(role, content) {
  const node = document.createElement("div");
  node.className = `message ${role}`;
  const label = document.createElement("div");
  label.className = "role";
  label.textContent = role === "user" ? "You" : role === "agent" ? "Agent" : "System";
  const body = document.createElement("div");
  body.className = "content";
  body.textContent = content;
  node.append(label, body);
  els.messages.appendChild(node);
  els.messages.scrollTop = els.messages.scrollHeight;
}

function renderMessages(messages) {
  els.messages.innerHTML = "";
  for (const message of messages || []) {
    addMessage(message.role, message.content);
  }
}

function updateProgress(job) {
  const progress = job ? Math.max(0, Math.min(100, job.progress || 0)) : 0;
  els.stageLabel.textContent = job ? `${job.stage} (${job.status})` : "No active job";
  els.progressNumber.textContent = `${progress}%`;
  els.progressBar.style.width = `${progress}%`;
  els.agentLog.textContent = job && job.logs ? job.logs.join("\n") : "";
  if (job && job.logs) {
    els.agentLog.scrollTop = els.agentLog.scrollHeight;
  }
}

function updatePreview(session) {
  state.token = session.preview_token;
  state.previewUrl = session.preview_url;
  state.htmlPath = session.html_path;
  if (session.preview_url && els.previewFrame.getAttribute("src") !== session.preview_url) {
    els.previewFrame.src = session.preview_url;
  }
  els.previewLabel.textContent = session.html_path || "No preview loaded";
  const hasPreview = Boolean(session.preview_url);
  els.markBtn.disabled = !hasPreview;
  els.validateBtn.disabled = !hasPreview;
  els.zoomOutBtn.disabled = !hasPreview;
  els.zoomInBtn.disabled = !hasPreview;
  els.canvasBtn.disabled = !hasPreview;
  els.stashBtn.disabled = !hasPreview || !state.canvasMode || !state.selectedCanvasModule;
  els.saveLayoutBtn.disabled = !hasPreview || state.canvasEdits.size === 0;
  updateHistoryButtons();
}

function applySession(session) {
  state.sessionId = session.session_id;
  renderMessages(session.messages);
  updateProgress(session.job);
  updatePreview(session);
  state.annotationBundle = session.annotation_bundle || state.annotationBundle;
  els.chatInput.disabled = false;
  els.sendBtn.disabled = session.job && ["queued", "running"].includes(session.job.status);
  els.includeAnnotation.disabled = !state.annotationBundle;
  els.includeAnnotation.checked = Boolean(state.annotationBundle);
  if (session.job) {
    state.lastJobStatus = session.job.status;
    const tone = session.job.status === "failed" ? "error" : session.job.status === "running" ? "busy" : "";
    setStatus(session.job.stage || session.job.status, tone);
  } else {
    setStatus("Session ready");
  }
}

function startPolling() {
  if (state.pollTimer) {
    clearInterval(state.pollTimer);
  }
  state.pollTimer = setInterval(async () => {
    if (!state.sessionId) {
      return;
    }
    try {
      const payload = await getJson(`/api/session?id=${encodeURIComponent(state.sessionId)}`);
      applySession(payload.session);
      const job = payload.session.job;
      if (job && ["completed", "failed"].includes(job.status)) {
        els.sendBtn.disabled = false;
      }
    } catch (error) {
      setStatus(error.message, "error");
    }
  }, 1200);
}

async function createSession() {
  setStatus("Creating session...", "busy");
  const payload = await api("/api/session", {
    path: requireProjectPath(),
    output_dir: els.outputDir.value.trim() || "webpage",
    filename: "index.html"
  });
  applySession(payload.session);
  startPolling();
  setStatus("Session ready");
}

async function inspectProject() {
  setStatus("Inspecting...", "busy");
  const payload = await api("/api/project", { path: requireProjectPath() });
  addMessage("system", JSON.stringify(payload.project, null, 2));
  setStatus("Project inspected");
}

async function sendMessage(message) {
  if (!state.sessionId) {
    await createSession();
  }
  addMessage("user", message);
  els.chatInput.value = "";
  els.sendBtn.disabled = true;
  setStatus("Agent running...", "busy");
  const payload = await api("/api/chat", {
    session_id: state.sessionId,
    message,
    include_annotation: els.includeAnnotation.checked
  });
  applySession(payload.session);
  startPolling();
}

function frameDocument() {
  try {
    return els.previewFrame.contentDocument || els.previewFrame.contentWindow.document;
  } catch (error) {
    return null;
  }
}

function frameWindow() {
  try {
    return els.previewFrame.contentWindow;
  } catch (error) {
    return null;
  }
}

function frameScroll() {
  const win = frameWindow();
  return {
    x: win ? win.scrollX : 0,
    y: win ? win.scrollY : 0
  };
}

function applyPreviewZoom() {
  const zoom = state.zoom;
  els.zoomLabel.textContent = `${Math.round(zoom * 100)}%`;
  els.previewFrame.style.width = `${100 / zoom}%`;
  els.previewFrame.style.height = `${100 / zoom}%`;
  els.previewFrame.style.transform = `scale(${zoom})`;
  els.previewFrame.style.transformOrigin = "0 0";
  redrawSelectionBox();
}

function setPreviewZoom(nextZoom) {
  state.zoom = Math.max(0.5, Math.min(2, nextZoom));
  applyPreviewZoom();
}

function selectionFromViewportRect(rect) {
  const scroll = frameScroll();
  return {
    x: rect.x,
    y: rect.y,
    width: rect.width,
    height: rect.height,
    viewport: { ...rect },
    document: {
      x: Math.round(rect.x + scroll.x),
      y: Math.round(rect.y + scroll.y),
      width: rect.width,
      height: rect.height
    },
    scroll: {
      x: Math.round(scroll.x),
      y: Math.round(scroll.y)
    },
    zoom: state.zoom
  };
}

function cssEscape(value) {
  if (window.CSS && CSS.escape) {
    return CSS.escape(value);
  }
  return String(value).replace(/[^a-zA-Z0-9_-]/g, "\\$&");
}

function shortSelector(element) {
  if (!element || element.nodeType !== 1) {
    return "";
  }
  if (element.id) {
    return `#${cssEscape(element.id)}`;
  }
  const parts = [];
  let node = element;
  while (node && node.nodeType === 1 && parts.length < 5) {
    let part = node.localName;
    if (node.classList && node.classList.length) {
      part += "." + Array.from(node.classList).slice(0, 3).map(cssEscape).join(".");
    }
    const parent = node.parentElement;
    if (parent) {
      const siblings = Array.from(parent.children).filter(child => child.localName === node.localName);
      if (siblings.length > 1) {
        part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
      }
    }
    parts.unshift(part);
    if (node.id) {
      break;
    }
    node = parent;
  }
  return parts.join(" > ");
}

function styleSummary(win, element) {
  const computed = win.getComputedStyle(element);
  const keys = [
    "display", "position", "boxSizing", "width", "height", "minWidth", "maxWidth",
    "minHeight", "maxHeight", "marginTop", "marginRight", "marginBottom",
    "marginLeft", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
    "alignItems", "justifyContent", "gridTemplateColumns", "gap", "objectFit",
    "verticalAlign", "overflow", "fontSize", "lineHeight"
  ];
  const result = {};
  for (const key of keys) {
    result[key] = computed[key];
  }
  return result;
}

function rectToObject(rect) {
  const scroll = frameScroll();
  return {
    viewport: {
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      width: Math.round(rect.width),
      height: Math.round(rect.height)
    },
    document: {
      x: Math.round(rect.x + scroll.x),
      y: Math.round(rect.y + scroll.y),
      width: Math.round(rect.width),
      height: Math.round(rect.height)
    }
  };
}

function rectToDocument(rect, scroll = frameScroll()) {
  return {
    left: rect.left + scroll.x,
    top: rect.top + scroll.y,
    right: rect.right + scroll.x,
    bottom: rect.bottom + scroll.y,
    width: rect.width,
    height: rect.height,
    centerX: rect.left + scroll.x + rect.width / 2,
    centerY: rect.top + scroll.y + rect.height / 2
  };
}

function truncate(value, limit) {
  if (!value) {
    return "";
  }
  return value.length > limit ? `${value.slice(0, limit)}...` : value;
}

function collectElements(selection) {
  const doc = frameDocument();
  const win = els.previewFrame.contentWindow;
  if (!doc || !win) {
    return [];
  }
  const viewport = selection.viewport || selection;
  const scroll = frameScroll();
  const points = [
    [viewport.x + viewport.width / 2, viewport.y + viewport.height / 2],
    [viewport.x + 6, viewport.y + 6],
    [viewport.x + viewport.width - 6, viewport.y + 6],
    [viewport.x + 6, viewport.y + viewport.height - 6],
    [viewport.x + viewport.width - 6, viewport.y + viewport.height - 6]
  ];
  const seen = new Set();
  const elements = [];
  for (const [x, y] of points) {
    const stack = doc.elementsFromPoint(x, y);
    for (const element of stack) {
      if (!element || seen.has(element) || ["HTML", "BODY"].includes(element.tagName)) {
        continue;
      }
      seen.add(element);
      const rect = element.getBoundingClientRect();
      elements.push({
        selector: shortSelector(element),
        tag: element.tagName.toLowerCase(),
        text: truncate((element.innerText || element.textContent || "").trim().replace(/\s+/g, " "), 700),
        bbox: {
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          width: Math.round(rect.width),
          height: Math.round(rect.height)
        },
        documentBbox: {
          x: Math.round(rect.x + scroll.x),
          y: Math.round(rect.y + scroll.y),
          width: Math.round(rect.width),
          height: Math.round(rect.height)
        },
        computedStyle: styleSummary(win, element),
        outerHTML: truncate(element.outerHTML, 4000)
      });
      if (elements.length >= 12) {
        return elements;
      }
    }
  }
  return elements;
}

function normalizeRect(start, end) {
  const x = Math.min(start.x, end.x);
  const y = Math.min(start.y, end.y);
  return {
    x: Math.round(x),
    y: Math.round(y),
    width: Math.round(Math.abs(end.x - start.x)),
    height: Math.round(Math.abs(end.y - start.y))
  };
}

function drawViewportSelection(rect) {
  els.selectionBox.hidden = !rect;
  if (!rect) {
    els.coordLabel.textContent = "No selection";
    return;
  }
  Object.assign(els.selectionBox.style, {
    left: `${rect.x * state.zoom}px`,
    top: `${rect.y * state.zoom}px`,
    width: `${rect.width * state.zoom}px`,
    height: `${rect.height * state.zoom}px`
  });
  const scroll = frameScroll();
  els.coordLabel.textContent = `doc ${Math.round(rect.x + scroll.x)},${Math.round(rect.y + scroll.y)} ${rect.width}x${rect.height}`;
}

function redrawSelectionBox() {
  if (!state.selection || !state.selection.document) {
    drawViewportSelection(null);
    return;
  }
  const scroll = frameScroll();
  const docRect = state.selection.document;
  drawViewportSelection({
    x: Math.round(docRect.x - scroll.x),
    y: Math.round(docRect.y - scroll.y),
    width: docRect.width,
    height: docRect.height
  });
}

function overlayPoint(event) {
  const rect = els.overlay.getBoundingClientRect();
  return {
    x: Math.round(Math.max(0, Math.min(rect.width, event.clientX - rect.left)) / state.zoom),
    y: Math.round(Math.max(0, Math.min(rect.height, event.clientY - rect.top)) / state.zoom)
  };
}

function canvasCandidateSelector() {
  return [
    "article", "div", "figure", "table", "thead", "tbody", "tr", "td", "th", "img",
    "h1", "h2", "h3", "p", "ul", "ol", "pre", "blockquote",
    ".card", ".figure-card", ".result-card", ".method-card", ".table-card", ".table-wrap", ".table-wrapper",
    ".table-container", ".module"
  ].join(",");
}

function canvasContainerSelector() {
  return [
    "article", "figure",
    ".card", ".figure-card", ".result-card", ".method-card", ".table-card", ".table-wrap", ".table-wrapper",
    ".table-container", ".module",
    "[class*='card']", "[class*='table']", "[class*='figure']", "[class*='module']", "[class*='visual']"
  ].join(",");
}

function hasVisibleBoxStyle(element) {
  const win = element.ownerDocument.defaultView;
  if (!win) {
    return false;
  }
  const computed = win.getComputedStyle(element);
  const background = computed.backgroundColor || "";
  const hasBackground = background && !["transparent", "rgba(0, 0, 0, 0)"].includes(background);
  const hasBorder = ["Top", "Right", "Bottom", "Left"].some(side => {
    const width = parseFloat(computed[`border${side}Width`]) || 0;
    return width > 0 && computed[`border${side}Style`] !== "none";
  });
  const hasPadding = ["Top", "Right", "Bottom", "Left"].some(side => (parseFloat(computed[`padding${side}`]) || 0) >= 8);
  const hasShadow = computed.boxShadow && computed.boxShadow !== "none";
  return hasBackground || hasBorder || hasPadding || hasShadow;
}

function hasOverflowClipping(element) {
  const win = element.ownerDocument.defaultView;
  if (!win) {
    return false;
  }
  const computed = win.getComputedStyle(element);
  return [computed.overflow, computed.overflowX, computed.overflowY].some(value => (
    value && !["visible", "clip"].includes(value)
  ));
}

function classSuggestsModule(element) {
  const value = `${element.className || ""} ${element.id || ""}`.toLowerCase();
  return /(card|module|table|figure|chart|plot|visual|result|method|metric|tile|item|block|surface)/.test(value);
}

function classSuggestsBackground(element) {
  const value = `${element.className || ""} ${element.id || ""}`.toLowerCase();
  return /(background|backdrop|section|container|wrapper|grid|layout|shell|page|hero|panel|surface-area)/.test(value)
    && !/(card|module|table|figure|chart|plot|visual|result|method|metric|tile|item)/.test(value);
}

function isCanvasBackgroundElement(element) {
  if (!element || !element.ownerDocument) {
    return true;
  }
  const tag = element.tagName;
  if (["HTML", "BODY", "MAIN", "SECTION", "HEADER", "FOOTER", "NAV", "ASIDE"].includes(tag)) {
    return true;
  }
  const rect = element.getBoundingClientRect();
  const doc = element.ownerDocument;
  const viewportWidth = doc.documentElement.clientWidth || 1;
  const viewportHeight = doc.documentElement.clientHeight || 1;
  const largePanel = rect.width >= viewportWidth * 0.72 && rect.height >= viewportHeight * 0.28;
  return classSuggestsBackground(element) || (largePanel && !classSuggestsModule(element));
}

function isMovableCanvasModule(element) {
  if (!element || element.id === "pwb-canvas-box" || element.id === "pwb-guide-layer") {
    return false;
  }
  if (element.classList && element.classList.contains("pwb-canvas-placeholder")) {
    return false;
  }
  if (isCanvasBackgroundElement(element)) {
    return false;
  }
  const tag = element.tagName;
  if (["ARTICLE", "FIGURE", "TABLE", "IMG", "H1", "H2", "H3", "P", "UL", "OL", "PRE", "BLOCKQUOTE"].includes(tag)) {
    return true;
  }
  return element.matches(canvasContainerSelector()) || classSuggestsModule(element) || hasVisibleBoxStyle(element);
}

function findVisualModuleWrapper(element, options = {}) {
  if (!element || !element.parentElement) {
    return null;
  }
  const doc = element.ownerDocument;
  const sourceRect = element.getBoundingClientRect();
  let node = element.parentElement;
  let match = null;
  while (node && node !== doc.body && node !== doc.documentElement) {
    if (node.closest("#pwb-canvas-box") || node.closest("#pwb-guide-layer")) {
      return null;
    }
    if (options.skipTableBoxes && ["TABLE", "THEAD", "TBODY", "TR", "TD", "TH"].includes(node.tagName)) {
      node = node.parentElement;
      continue;
    }
    const rect = node.getBoundingClientRect();
    const wrapsElement = rect.width >= sourceRect.width && rect.height >= sourceRect.height;
    const visiblyLarger = rect.width - sourceRect.width >= 12 || rect.height - sourceRect.height >= 12;
    const overflowWrapper = Boolean(options.allowOverflowWrapper)
      && rect.width >= 24
      && rect.height >= 18
      && (hasVisibleBoxStyle(node) || hasOverflowClipping(node) || classSuggestsModule(node));
    const moduleLike = isMovableCanvasModule(node);
    if (moduleLike && ((wrapsElement && visiblyLarger) || overflowWrapper)) {
      match = node;
      if (!options.preferOuter) {
        return match;
      }
    }
    node = node.parentElement;
  }
  return match;
}

function resolveCanvasModule(element) {
  if (!element || element.id === "pwb-canvas-box") {
    return element;
  }
  const tag = element.tagName;
  if (["THEAD", "TBODY", "TR", "TD", "TH"].includes(tag)) {
    const wrapper = findVisualModuleWrapper(element, {
      skipTableBoxes: true,
      preferOuter: true,
      allowOverflowWrapper: true
    });
    if (wrapper) {
      return wrapper;
    }
  }
  if (["TABLE", "IMG"].includes(tag)) {
    const wrapper = findVisualModuleWrapper(element, {
      preferOuter: tag === "TABLE",
      allowOverflowWrapper: tag === "TABLE"
    });
    if (wrapper) {
      return wrapper;
    }
  }
  if (isMovableCanvasModule(element)) {
    return element;
  }
  const container = element.closest(canvasContainerSelector());
  if (
    container
    && container !== element.ownerDocument.body
    && container !== element.ownerDocument.documentElement
    && isMovableCanvasModule(container)
  ) {
    return container;
  }
  const wrapper = findVisualModuleWrapper(element);
  if (wrapper) {
    return wrapper;
  }
  return element;
}

function ensureCanvasStyles(doc) {
  if (doc.getElementById("pwb-canvas-style")) {
    return;
  }
  const style = doc.createElement("style");
  style.id = "pwb-canvas-style";
  style.textContent = `
    html.pwb-canvas-active .pwb-canvas-module {
      outline: 1px dashed rgba(33, 109, 104, 0.65) !important;
      outline-offset: 2px !important;
      cursor: move !important;
    }
    html.pwb-canvas-active .pwb-canvas-module:hover {
      outline-color: rgba(33, 109, 104, 0.95) !important;
    }
    html.pwb-canvas-active .pwb-canvas-selected {
      outline: 2px solid #216d68 !important;
      outline-offset: 3px !important;
    }
    html.pwb-canvas-active .pwb-free-module {
      position: absolute !important;
      box-sizing: border-box !important;
      z-index: 2147483000 !important;
      max-width: none !important;
    }
    .pwb-canvas-placeholder {
      display: block !important;
      visibility: hidden !important;
      pointer-events: none !important;
      box-sizing: border-box !important;
    }
    .pwb-resource-stashed {
      display: none !important;
    }
    #pwb-canvas-box {
      position: absolute;
      z-index: 2147483647;
      border: 2px solid #216d68;
      background: rgba(33, 109, 104, 0.06);
      pointer-events: none;
      box-sizing: border-box;
    }
    #pwb-canvas-box[hidden] { display: none !important; }
    #pwb-guide-layer {
      position: absolute;
      inset: 0;
      z-index: 2147483646;
      pointer-events: none;
    }
    #pwb-guide-layer[hidden] { display: none !important; }
    .pwb-guide-line {
      position: absolute;
      pointer-events: none;
      background: #d97706;
      box-shadow: 0 0 0 1px rgba(255,255,255,.9), 0 0 10px rgba(217,119,6,.32);
    }
    .pwb-guide-line.vertical {
      top: 0;
      width: 1px;
      min-height: 100vh;
    }
    .pwb-guide-line.horizontal {
      left: 0;
      height: 1px;
      min-width: 100vw;
    }
    .pwb-guide-label {
      position: absolute;
      max-width: 180px;
      border: 1px solid rgba(217,119,6,.35);
      border-radius: 4px;
      padding: 2px 5px;
      color: #7c3f00;
      background: rgba(255,251,235,.96);
      box-shadow: 0 2px 8px rgba(31,41,55,.14);
      font: 11px/1.2 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
      white-space: nowrap;
    }
    #pwb-canvas-handle {
      position: absolute;
      right: -7px;
      bottom: -7px;
      width: 14px;
      height: 14px;
      border: 2px solid #fff;
      background: #216d68;
      border-radius: 3px;
      box-shadow: 0 1px 5px rgba(0,0,0,.25);
      cursor: nwse-resize;
      pointer-events: auto;
    }
  `;
  doc.head.appendChild(style);
}

function makeCanvasBox(doc) {
  let box = doc.getElementById("pwb-canvas-box");
  if (box) {
    return box;
  }
  box = doc.createElement("div");
  box.id = "pwb-canvas-box";
  box.hidden = true;
  const handle = doc.createElement("div");
  handle.id = "pwb-canvas-handle";
  handle.addEventListener("mousedown", event => {
    event.preventDefault();
    event.stopPropagation();
    if (state.selectedCanvasModule) {
      beginCanvasGesture(event, state.selectedCanvasModule, "resize");
    }
  });
  box.appendChild(handle);
  doc.body.appendChild(box);
  return box;
}

function makeGuideLayer(doc) {
  let layer = doc.getElementById("pwb-guide-layer");
  if (layer) {
    return layer;
  }
  layer = doc.createElement("div");
  layer.id = "pwb-guide-layer";
  layer.hidden = true;
  doc.body.appendChild(layer);
  return layer;
}

function hideCanvasGuides() {
  const doc = frameDocument();
  const layer = doc ? doc.getElementById("pwb-guide-layer") : null;
  if (!layer) {
    return;
  }
  layer.hidden = true;
  layer.replaceChildren();
}

function showCanvasGuides(guides) {
  const doc = frameDocument();
  if (!doc) {
    return;
  }
  const layer = makeGuideLayer(doc);
  layer.replaceChildren();
  if (!guides || guides.length === 0) {
    layer.hidden = true;
    return;
  }
  const pageWidth = Math.max(doc.documentElement.scrollWidth, doc.body.scrollWidth, doc.documentElement.clientWidth);
  const pageHeight = Math.max(doc.documentElement.scrollHeight, doc.body.scrollHeight, doc.documentElement.clientHeight);
  for (const guide of guides) {
    const line = doc.createElement("div");
    line.className = `pwb-guide-line ${guide.axis === "x" ? "vertical" : "horizontal"}`;
    if (guide.axis === "x") {
      Object.assign(line.style, {
        left: `${Math.round(guide.value)}px`,
        height: `${pageHeight}px`
      });
    } else {
      Object.assign(line.style, {
        top: `${Math.round(guide.value)}px`,
        width: `${pageWidth}px`
      });
    }
    layer.appendChild(line);
    if (guide.label) {
      const label = doc.createElement("div");
      label.className = "pwb-guide-label";
      label.textContent = guide.label;
      Object.assign(label.style, guide.axis === "x" ? {
        left: `${Math.round(guide.value + 6)}px`,
        top: `${Math.max(8, Math.round((guide.spanStart || 0) + 8))}px`
      } : {
        left: `${Math.max(8, Math.round((guide.spanStart || 0) + 8))}px`,
        top: `${Math.round(guide.value + 6)}px`
      });
      layer.appendChild(label);
    }
  }
  layer.hidden = false;
}

function pushSnapTarget(targets, axis, value, label, priority = 0) {
  if (Number.isFinite(value)) {
    targets.push({ axis, value, label, priority });
  }
}

function canvasSnapTargets(element) {
  const doc = frameDocument();
  const win = frameWindow();
  if (!doc || !win) {
    return [];
  }
  const targets = [];
  const pageWidth = Math.max(doc.documentElement.scrollWidth, doc.body.scrollWidth, doc.documentElement.clientWidth);
  const pageHeight = Math.max(doc.documentElement.scrollHeight, doc.body.scrollHeight, doc.documentElement.clientHeight);
  pushSnapTarget(targets, "x", pageWidth / 2, "page center", 3);
  pushSnapTarget(targets, "y", pageHeight / 2, "page middle", 3);

  const parent = element.parentElement;
  if (parent && parent !== doc.body && parent !== doc.documentElement) {
    const parentRect = rectToDocument(parent.getBoundingClientRect());
    pushSnapTarget(targets, "x", parentRect.left, "parent left", 1);
    pushSnapTarget(targets, "x", parentRect.centerX, "parent center", 3);
    pushSnapTarget(targets, "x", parentRect.right, "parent right", 1);
    pushSnapTarget(targets, "y", parentRect.top, "parent top", 1);
    pushSnapTarget(targets, "y", parentRect.centerY, "parent middle", 3);
    pushSnapTarget(targets, "y", parentRect.bottom, "parent bottom", 1);
  }

  const axes = [
    { axis: "x", center: pageWidth / 2, label: "page mirror" },
    { axis: "y", center: pageHeight / 2, label: "page mirror" }
  ];
  if (parent && parent !== doc.body && parent !== doc.documentElement) {
    const parentRect = rectToDocument(parent.getBoundingClientRect());
    axes.push({ axis: "x", center: parentRect.centerX, label: "parent mirror" });
    axes.push({ axis: "y", center: parentRect.centerY, label: "parent mirror" });
  }

  const modules = state.canvasModules.filter(module => (
    module
    && module.isConnected
    && module !== element
    && !module.contains(element)
    && !element.contains(module)
    && !module.closest("#pwb-canvas-box")
    && !module.closest("#pwb-guide-layer")
  ));
  for (const module of modules) {
    const rect = module.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) {
      continue;
    }
    const docRect = rectToDocument(rect);
    const name = module.dataset.pwbModuleId || module.tagName.toLowerCase();
    pushSnapTarget(targets, "x", docRect.left, `${name} left`, 1);
    pushSnapTarget(targets, "x", docRect.centerX, `${name} center`, 2);
    pushSnapTarget(targets, "x", docRect.right, `${name} right`, 1);
    pushSnapTarget(targets, "y", docRect.top, `${name} top`, 1);
    pushSnapTarget(targets, "y", docRect.centerY, `${name} middle`, 2);
    pushSnapTarget(targets, "y", docRect.bottom, `${name} bottom`, 1);
    for (const axis of axes) {
      const value = axis.center * 2 - (axis.axis === "x" ? docRect.centerX : docRect.centerY);
      pushSnapTarget(targets, axis.axis, value, `${axis.label} ${name}`, 2);
    }
  }
  return targets;
}

function projectedCanvasRect(gesture, dx, dy) {
  return {
    left: gesture.baseDocRect.left + dx,
    top: gesture.baseDocRect.top + dy,
    right: gesture.baseDocRect.right + dx,
    bottom: gesture.baseDocRect.bottom + dy,
    width: gesture.baseDocRect.width,
    height: gesture.baseDocRect.height,
    centerX: gesture.baseDocRect.centerX + dx,
    centerY: gesture.baseDocRect.centerY + dy
  };
}

function closestSnap(deltaA, deltaB) {
  if (!deltaA) {
    return deltaB;
  }
  if (!deltaB) {
    return deltaA;
  }
  const absA = Math.abs(deltaA.delta);
  const absB = Math.abs(deltaB.delta);
  if (absB < absA) {
    return deltaB;
  }
  if (absB === absA && deltaB.priority > deltaA.priority) {
    return deltaB;
  }
  return deltaA;
}

function canvasSnapMove(gesture, dx, dy) {
  const threshold = 7;
  const rect = projectedCanvasRect(gesture, dx, dy);
  const anchors = {
    x: [
      { name: "left", value: rect.left, spanStart: rect.top },
      { name: "center", value: rect.centerX, spanStart: rect.top },
      { name: "right", value: rect.right, spanStart: rect.top }
    ],
    y: [
      { name: "top", value: rect.top, spanStart: rect.left },
      { name: "middle", value: rect.centerY, spanStart: rect.left },
      { name: "bottom", value: rect.bottom, spanStart: rect.left }
    ]
  };
  let bestX = null;
  let bestY = null;
  for (const target of gesture.snapTargets || []) {
    for (const anchor of anchors[target.axis]) {
      const delta = target.value - anchor.value;
      if (Math.abs(delta) <= threshold) {
        const match = {
          axis: target.axis,
          delta,
          value: target.value,
          label: `${anchor.name} -> ${target.label}`,
          anchor: anchor.name,
          priority: target.priority,
          spanStart: anchor.spanStart
        };
        if (target.axis === "x") {
          bestX = closestSnap(bestX, match);
        } else {
          bestY = closestSnap(bestY, match);
        }
      }
    }
  }
  const snappedDx = dx + (bestX ? bestX.delta : 0);
  const snappedDy = dy + (bestY ? bestY.delta : 0);
  const guides = [];
  if (bestX) {
    guides.push({ axis: "x", value: bestX.value, label: bestX.label, anchor: bestX.anchor, spanStart: bestX.spanStart });
  }
  if (bestY) {
    guides.push({ axis: "y", value: bestY.value, label: bestY.label, anchor: bestY.anchor, spanStart: bestY.spanStart });
  }
  return { dx: snappedDx, dy: snappedDy, guides };
}

function actualCanvasAnchor(element, axis, anchor) {
  const rect = rectToDocument(element.getBoundingClientRect());
  if (axis === "x") {
    if (anchor === "left") {
      return rect.left;
    }
    if (anchor === "right") {
      return rect.right;
    }
    return rect.centerX;
  }
  if (anchor === "top") {
    return rect.top;
  }
  if (anchor === "bottom") {
    return rect.bottom;
  }
  return rect.centerY;
}

function correctCanvasSnap(element, guides) {
  if (!guides || guides.length === 0) {
    return;
  }
  for (let pass = 0; pass < 2; pass += 1) {
    let changed = false;
    for (const guide of guides) {
      const current = actualCanvasAnchor(element, guide.axis, guide.anchor);
      const delta = guide.value - current;
      if (!Number.isFinite(delta) || Math.abs(delta) < 0.5) {
        continue;
      }
      if (guide.axis === "x") {
        if (element.dataset.pwbFree === "true") {
          const left = parseFloat(element.style.left || "0") || 0;
          element.style.left = `${Math.round(left + delta)}px`;
        } else {
          const marginLeft = parseFloat(element.style.marginLeft || "0") || 0;
          element.style.marginLeft = `${Math.round(marginLeft + delta)}px`;
        }
        element.dataset.pwbFlowX = String(Math.round(Number(element.dataset.pwbFlowX || 0) + delta));
      } else {
        if (element.dataset.pwbFree === "true") {
          const top = parseFloat(element.style.top || "0") || 0;
          element.style.top = `${Math.round(top + delta)}px`;
        } else {
          const marginTop = parseFloat(element.style.marginTop || "0") || 0;
          element.style.marginTop = `${Math.round(marginTop + delta)}px`;
        }
        element.dataset.pwbFlowY = String(Math.round(Number(element.dataset.pwbFlowY || 0) + delta));
      }
      changed = true;
    }
    if (!changed) {
      break;
    }
  }
}

function canvasModuleTitle(element) {
  const text = (element.innerText || element.alt || element.textContent || "")
    .trim()
    .replace(/\s+/g, " ");
  return truncate(text || element.id || element.tagName.toLowerCase(), 54);
}

function removeCanvasPlaceholder(element) {
  const placeholder = element._pwbPlaceholder;
  if (placeholder && placeholder.parentElement) {
    placeholder.remove();
  }
  element._pwbPlaceholder = null;
}

function makeCanvasPlaceholder(element, rect, computed) {
  const doc = element.ownerDocument;
  const placeholder = doc.createElement("div");
  placeholder.className = "pwb-canvas-placeholder";
  placeholder.dataset.pwbPlaceholderFor = element.dataset.pwbModuleId;
  Object.assign(placeholder.style, {
    width: `${Math.round(rect.width)}px`,
    height: `${Math.round(rect.height)}px`,
    minHeight: `${Math.round(rect.height)}px`,
    marginTop: computed ? computed.marginTop : "",
    marginRight: computed ? computed.marginRight : "",
    marginBottom: computed ? computed.marginBottom : "",
    marginLeft: computed ? computed.marginLeft : ""
  });
  return placeholder;
}

function ensureFreeCanvasModule(element) {
  if (element.dataset.pwbFree === "true") {
    return;
  }
  const doc = frameDocument();
  const win = frameWindow();
  if (!doc || !win || !element.parentElement) {
    return;
  }
  const rect = element.getBoundingClientRect();
  const docRect = rectToDocument(rect);
  const computed = win.getComputedStyle(element);
  const placeholder = makeCanvasPlaceholder(element, rect, computed);
  element.parentElement.insertBefore(placeholder, element);
  element._pwbPlaceholder = placeholder;
  doc.body.appendChild(element);
  element.dataset.pwbFree = "true";
  element.classList.add("pwb-free-module");
  Object.assign(element.style, {
    position: "absolute",
    left: `${Math.round(docRect.left)}px`,
    top: `${Math.round(docRect.top)}px`,
    width: `${Math.round(rect.width)}px`,
    minHeight: `${Math.round(rect.height)}px`,
    maxWidth: "none",
    margin: "0",
    zIndex: "2147483000",
    boxSizing: "border-box"
  });
  if (element.tagName === "IMG") {
    element.style.height = `${Math.round(rect.height)}px`;
    element.style.objectFit = "contain";
  }
}

function restoreCanvasPlaceholder(element, snapshot) {
  if (!snapshot.placeholderParent) {
    return;
  }
  let placeholder = element._pwbPlaceholder;
  if (!placeholder || !placeholder.isConnected) {
    placeholder = element.ownerDocument.createElement("div");
    placeholder.className = "pwb-canvas-placeholder";
    placeholder.dataset.pwbPlaceholderFor = element.dataset.pwbModuleId;
    element._pwbPlaceholder = placeholder;
  }
  placeholder.setAttribute("style", snapshot.placeholderStyle || "");
  if (placeholder.parentElement !== snapshot.placeholderParent) {
    if (snapshot.placeholderNextSibling && snapshot.placeholderNextSibling.parentElement === snapshot.placeholderParent) {
      snapshot.placeholderParent.insertBefore(placeholder, snapshot.placeholderNextSibling);
    } else {
      snapshot.placeholderParent.appendChild(placeholder);
    }
  }
}

function canvasResourceFor(element) {
  const id = element.dataset.pwbModuleId;
  if (!state.canvasResources.has(id)) {
    state.canvasResources.set(id, {
      id,
      element,
      title: canvasModuleTitle(element),
      tag: element.tagName.toLowerCase()
    });
  }
  return state.canvasResources.get(id);
}

function canvasResourceStatus(element) {
  if (element.dataset.pwbStashed === "true" || element.classList.contains("pwb-resource-stashed")) {
    return "stashed";
  }
  if (element.dataset.pwbFree === "true") {
    return "free";
  }
  return "on page";
}

function renderResourceShelf() {
  if (!els.resourceShelf || !els.resourceList) {
    return;
  }
  els.resourceShelf.hidden = !state.canvasMode;
  els.resourceCount.textContent = String(state.canvasResources.size);
  els.resourceList.innerHTML = "";
  for (const resource of state.canvasResources.values()) {
    const element = resource.element;
    if (!element || !element.isConnected) {
      continue;
    }
    const item = document.createElement("div");
    item.className = `resource-item${element === state.selectedCanvasModule ? " selected" : ""}`;
    const status = canvasResourceStatus(element);
    const title = document.createElement("div");
    title.className = "resource-title";
    title.textContent = resource.title;
    const meta = document.createElement("div");
    meta.className = "resource-meta";
    meta.innerHTML = `<span>${resource.tag}</span><span>${status}</span>`;
    const actions = document.createElement("div");
    actions.className = "resource-actions";
    const selectBtn = document.createElement("button");
    selectBtn.type = "button";
    selectBtn.textContent = "Select";
    selectBtn.addEventListener("click", () => {
      if (canvasResourceStatus(element) === "stashed") {
        placeCanvasResource(element);
      } else {
        selectCanvasModule(element);
      }
    });
    const stashBtn = document.createElement("button");
    stashBtn.type = "button";
    stashBtn.textContent = status === "stashed" ? "Place" : "Stash";
    stashBtn.addEventListener("click", () => {
      if (canvasResourceStatus(element) === "stashed") {
        placeCanvasResource(element);
      } else {
        stashCanvasModule(element);
      }
    });
    actions.append(selectBtn, stashBtn);
    item.append(title, meta, actions);
    els.resourceList.appendChild(item);
  }
}

function moduleSelector(element) {
  return shortSelector(element);
}

function moduleSnapshot(element) {
  const rect = element.getBoundingClientRect();
  const coords = rectToObject(rect);
  const win = frameWindow();
  return {
    id: element.dataset.pwbModuleId,
    selector: moduleSelector(element),
    tag: element.tagName.toLowerCase(),
    text: truncate((element.innerText || element.alt || element.textContent || "").trim().replace(/\s+/g, " "), 500),
    bbox: coords.viewport,
    documentBbox: coords.document,
    computedStyle: win ? styleSummary(win, element) : {},
    outerHTML: truncate(element.outerHTML, 3000)
  };
}

function captureCanvasState(element) {
  const placeholder = element._pwbPlaceholder;
  return {
    style: element.getAttribute("style") || "",
    flowX: element.dataset.pwbFlowX || "",
    flowY: element.dataset.pwbFlowY || "",
    free: element.dataset.pwbFree || "",
    stashed: element.dataset.pwbStashed || "",
    classes: element.getAttribute("class") || "",
    parent: element.parentElement,
    nextSibling: element.nextElementSibling,
    placeholder,
    placeholderParent: placeholder ? placeholder.parentElement : null,
    placeholderNextSibling: placeholder ? placeholder.nextElementSibling : null,
    placeholderStyle: placeholder ? placeholder.getAttribute("style") || "" : "",
    bbox: rectToObject(element.getBoundingClientRect())
  };
}

function applyCanvasState(element, snapshot) {
  if (snapshot.placeholderParent) {
    restoreCanvasPlaceholder(element, snapshot);
  } else {
    removeCanvasPlaceholder(element);
  }
  if (snapshot.parent && element.parentElement !== snapshot.parent) {
    if (snapshot.nextSibling && snapshot.nextSibling.parentElement === snapshot.parent) {
      snapshot.parent.insertBefore(element, snapshot.nextSibling);
    } else {
      snapshot.parent.appendChild(element);
    }
  } else if (
    snapshot.parent
    && snapshot.nextSibling
    && snapshot.nextSibling.parentElement === snapshot.parent
    && element.nextElementSibling !== snapshot.nextSibling
  ) {
    snapshot.parent.insertBefore(element, snapshot.nextSibling);
  }
  if (snapshot.style) {
    element.setAttribute("style", snapshot.style);
  } else {
    element.removeAttribute("style");
  }
  if (snapshot.flowX) {
    element.dataset.pwbFlowX = snapshot.flowX;
  } else {
    delete element.dataset.pwbFlowX;
  }
  if (snapshot.flowY) {
    element.dataset.pwbFlowY = snapshot.flowY;
  } else {
    delete element.dataset.pwbFlowY;
  }
  if (snapshot.free) {
    element.dataset.pwbFree = snapshot.free;
  } else {
    delete element.dataset.pwbFree;
  }
  if (snapshot.stashed) {
    element.dataset.pwbStashed = snapshot.stashed;
  } else {
    delete element.dataset.pwbStashed;
  }
  element.setAttribute("class", snapshot.classes || "");
}

function canvasStateChanged(before, after) {
  return (
    before.style !== after.style
    || before.flowX !== after.flowX
    || before.flowY !== after.flowY
    || before.free !== after.free
    || before.stashed !== after.stashed
    || before.classes !== after.classes
    || before.parent !== after.parent
    || before.nextSibling !== after.nextSibling
    || before.placeholderParent !== after.placeholderParent
  );
}

function currentCanvasBox(element) {
  const rect = element.getBoundingClientRect();
  return rectToObject(rect);
}

function updateCanvasBox() {
  const doc = frameDocument();
  if (!doc) {
    return;
  }
  const box = doc.getElementById("pwb-canvas-box");
  if (!box || !state.selectedCanvasModule || !state.canvasMode) {
    if (box) {
      box.hidden = true;
    }
    return;
  }
  const docRect = currentCanvasBox(state.selectedCanvasModule).document;
  Object.assign(box.style, {
    left: `${docRect.x}px`,
    top: `${docRect.y}px`,
    width: `${docRect.width}px`,
    height: `${docRect.height}px`
  });
  box.hidden = false;
}

function selectCanvasModule(element) {
  if (!element || element.dataset.pwbStashed === "true") {
    return;
  }
  if (state.selectedCanvasModule) {
    state.selectedCanvasModule.classList.remove("pwb-canvas-selected");
  }
  state.selectedCanvasModule = element;
  element.classList.add("pwb-canvas-selected");
  canvasResourceFor(element);
  const snap = moduleSnapshot(element);
  els.coordLabel.textContent = `module ${snap.documentBbox.x},${snap.documentBbox.y} ${snap.documentBbox.width}x${snap.documentBbox.height}`;
  els.stashBtn.disabled = false;
  renderResourceShelf();
  updateCanvasBox();
}

function installCanvasModules() {
  const doc = frameDocument();
  if (!doc) {
    return;
  }
  ensureCanvasStyles(doc);
  makeCanvasBox(doc);
  makeGuideLayer(doc);
  doc.documentElement.classList.add("pwb-canvas-active");
  if (!doc._pwbCanvasClickBlocker) {
    doc._pwbCanvasClickBlocker = event => {
      if (!state.canvasMode) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
    };
    doc.addEventListener("click", doc._pwbCanvasClickBlocker, true);
    doc.addEventListener("dblclick", doc._pwbCanvasClickBlocker, true);
  }
  const seenModules = new Set();
  const candidates = [];
  for (const rawElement of Array.from(doc.querySelectorAll(canvasCandidateSelector()))) {
    if (
      rawElement.closest("#pwb-canvas-box")
      || rawElement.closest("#pwb-guide-layer")
      || rawElement.classList.contains("pwb-canvas-placeholder")
    ) {
      continue;
    }
    const element = resolveCanvasModule(rawElement);
    if (!element || seenModules.has(element) || !isMovableCanvasModule(element)) {
      continue;
    }
    const rect = element.getBoundingClientRect();
    if (rect.width >= 24 && rect.height >= 18 && rect.width * rect.height >= 1200) {
      seenModules.add(element);
      candidates.push(element);
    }
  }
  state.canvasModules = candidates;
  candidates.forEach((element, index) => {
    if (!element.dataset.pwbModuleId) {
      element.dataset.pwbModuleId = `m${index + 1}`;
      element.dataset.pwbOriginalStyle = element.getAttribute("style") || "";
      element.dataset.pwbBaseWidth = String(Math.round(element.getBoundingClientRect().width));
      element.dataset.pwbBaseHeight = String(Math.round(element.getBoundingClientRect().height));
    }
    canvasResourceFor(element);
    element.classList.add("pwb-canvas-module");
    if (!element._pwbCanvasDown) {
      element._pwbCanvasDown = event => {
        if (!state.canvasMode) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        const module = resolveCanvasModule(element);
        selectCanvasModule(module);
        beginCanvasGesture(event, module, "move");
      };
      element.addEventListener("mousedown", element._pwbCanvasDown);
    }
  });
  renderResourceShelf();
  setStatus(`Canvas mode: ${candidates.length} modules`);
}

function uninstallCanvasModules() {
  const doc = frameDocument();
  if (!doc) {
    return;
  }
  doc.documentElement.classList.remove("pwb-canvas-active");
  for (const element of state.canvasModules) {
    element.classList.remove("pwb-canvas-module", "pwb-canvas-selected");
  }
  const box = doc.getElementById("pwb-canvas-box");
  if (box) {
    box.hidden = true;
  }
  hideCanvasGuides();
  if (els.resourceShelf) {
    els.resourceShelf.hidden = true;
  }
  els.stashBtn.disabled = true;
  state.selectedCanvasModule = null;
  state.canvasModules = [];
}

function buildCanvasEdit(element, action) {
  const id = element.dataset.pwbModuleId;
  const before = {
    selector: moduleSelector(element),
    originalStyle: element.dataset.pwbOriginalStyle || "",
    baseWidth: Number(element.dataset.pwbBaseWidth || 0),
    baseHeight: Number(element.dataset.pwbBaseHeight || 0)
  };
  const after = moduleSnapshot(element);
  return {
    id,
    action,
    selector: before.selector,
    originalStyle: before.originalStyle,
    before,
    after,
    layout: {
      position: element.style.position || "",
      left: element.style.left || "",
      top: element.style.top || "",
      marginLeft: element.style.marginLeft || "",
      marginTop: element.style.marginTop || "",
      width: element.style.width || "",
      minHeight: element.style.minHeight || "",
      height: element.style.height || "",
      maxWidth: element.style.maxWidth || "",
      objectFit: element.style.objectFit || "",
      freeCanvas: element.dataset.pwbFree === "true",
      stashed: element.dataset.pwbStashed === "true"
    },
    transform: {
      x: Number(element.dataset.pwbFlowX || 0),
      y: Number(element.dataset.pwbFlowY || 0),
      width: element.style.width || "",
      minHeight: element.style.minHeight || "",
      transform: element.style.transform || "",
      note: "Canvas mode now uses flow-affecting margin/size edits; transform is recorded only if present from source or prior edits."
    }
  };
}

function rebuildCanvasEdits() {
  state.canvasEdits.clear();
  for (const entry of state.canvasHistory) {
    if (entry.element && entry.element.isConnected) {
      state.canvasEdits.set(entry.element.dataset.pwbModuleId, buildCanvasEdit(entry.element, entry.action));
    }
  }
  updateHistoryButtons();
}

function updateHistoryButtons() {
  els.saveLayoutBtn.disabled = state.canvasEdits.size === 0;
  els.undoBtn.disabled = state.canvasHistory.length === 0;
  els.redoBtn.disabled = state.canvasRedo.length === 0;
  els.stashBtn.disabled = !state.canvasMode || !state.selectedCanvasModule;
  els.includeAnnotation.disabled = state.canvasEdits.size === 0 && !state.annotationBundle;
  els.coordLabel.textContent = `${state.canvasEdits.size} layout edit${state.canvasEdits.size === 1 ? "" : "s"}`;
  renderResourceShelf();
}

function beginCanvasGesture(event, element, mode) {
  const beforeState = captureCanvasState(element);
  if (mode === "move") {
    ensureFreeCanvasModule(element);
  }
  const rect = element.getBoundingClientRect();
  const baseDocRect = rectToDocument(rect);
  const win = frameWindow();
  const computed = win ? win.getComputedStyle(element) : null;
  state.canvasGesture = {
    mode,
    element,
    startX: event.clientX,
    startY: event.clientY,
    baseX: Number(element.dataset.pwbFlowX || 0),
    baseY: Number(element.dataset.pwbFlowY || 0),
    baseMarginLeft: computed ? parseFloat(computed.marginLeft) || 0 : 0,
    baseMarginTop: computed ? parseFloat(computed.marginTop) || 0 : 0,
    baseMarginRight: computed ? parseFloat(computed.marginRight) || 0 : 0,
    baseMarginBottom: computed ? parseFloat(computed.marginBottom) || 0 : 0,
    baseWidth: rect.width,
    baseHeight: rect.height,
    baseDocRect,
    preserveMoveWidth: mode === "move" && computed && computed.width && computed.width !== "auto",
    snapTargets: mode === "move" ? canvasSnapTargets(element) : [],
    beforeState,
    lastClientX: event.clientX,
    lastClientY: event.clientY,
    view: event.view || frameWindow()
  };
}

function autoScrollFrameDuringDrag(event) {
  const win = frameWindow();
  if (!win || event.view !== win) {
    return;
  }
  const edge = 56;
  let scrollY = 0;
  let scrollX = 0;
  if (event.clientY > win.innerHeight - edge) {
    scrollY = Math.min(34, edge - (win.innerHeight - event.clientY));
  } else if (event.clientY < edge) {
    scrollY = -Math.min(34, edge - event.clientY);
  }
  if (event.clientX > win.innerWidth - edge) {
    scrollX = Math.min(28, edge - (win.innerWidth - event.clientX));
  } else if (event.clientX < edge) {
    scrollX = -Math.min(28, edge - event.clientX);
  }
  if (scrollX || scrollY) {
    win.scrollBy(scrollX, scrollY);
  }
}

function updateCanvasGesture(event) {
  const gesture = state.canvasGesture;
  if (!gesture) {
    return;
  }
  gesture.lastClientX = event.clientX;
  gesture.lastClientY = event.clientY;
  gesture.view = event.view || frameWindow();
  autoScrollFrameDuringDrag(event);
  const dx = (event.clientX - gesture.startX) / state.zoom;
  const dy = (event.clientY - gesture.startY) / state.zoom;
  const element = gesture.element;
  if (gesture.mode === "move") {
    const snapped = canvasSnapMove(gesture, dx, dy);
    const effectiveDx = snapped.dx;
    const effectiveDy = snapped.dy;
    const nextX = Math.round(gesture.baseX + effectiveDx);
    const nextY = Math.round(gesture.baseY + effectiveDy);
    element.dataset.pwbFlowX = String(nextX);
    element.dataset.pwbFlowY = String(nextY);
    if (gesture.preserveMoveWidth) {
      element.style.width = `${Math.round(gesture.baseWidth)}px`;
      element.style.maxWidth = "none";
    }
    if (element.dataset.pwbFree === "true") {
      element.style.position = "absolute";
      element.style.left = `${Math.round(gesture.baseDocRect.left + effectiveDx)}px`;
      element.style.top = `${Math.round(gesture.baseDocRect.top + effectiveDy)}px`;
      element.style.margin = "0";
      element.style.zIndex = "2147483000";
    } else {
      element.style.marginLeft = `${Math.round(gesture.baseMarginLeft + effectiveDx)}px`;
      element.style.marginTop = `${Math.round(gesture.baseMarginTop + effectiveDy)}px`;
      if (effectiveDx > 0) {
        element.style.marginRight = `${Math.round(Math.max(0, gesture.baseMarginRight - effectiveDx))}px`;
      }
      if (effectiveDy > 0) {
        element.style.marginBottom = `${Math.round(Math.max(0, gesture.baseMarginBottom - effectiveDy))}px`;
      }
    }
    correctCanvasSnap(element, snapped.guides);
    showCanvasGuides(snapped.guides);
  } else {
    hideCanvasGuides();
    const nextWidth = Math.max(24, Math.round(gesture.baseWidth + dx));
    const nextHeight = Math.max(18, Math.round(gesture.baseHeight + dy));
    element.style.width = `${nextWidth}px`;
    element.style.maxWidth = "none";
    element.style.minHeight = `${nextHeight}px`;
    if (element.tagName === "IMG") {
      element.style.height = `${nextHeight}px`;
      element.style.objectFit = "contain";
    }
  }
  updateCanvasBox();
}

function resetMoveMarginsToGestureBase(element, gesture) {
  element.style.marginLeft = `${Math.round(gesture.baseMarginLeft)}px`;
  element.style.marginTop = `${Math.round(gesture.baseMarginTop)}px`;
  element.style.marginRight = `${Math.round(gesture.baseMarginRight)}px`;
  element.style.marginBottom = `${Math.round(gesture.baseMarginBottom)}px`;
  element.dataset.pwbFlowX = "0";
  element.dataset.pwbFlowY = "0";
}

function findCanvasDropTarget(gesture) {
  const doc = frameDocument();
  const win = frameWindow();
  if (!doc || !win || gesture.view !== win) {
    return null;
  }
  const x = Math.max(0, Math.min(win.innerWidth - 1, gesture.lastClientX));
  const y = Math.max(0, Math.min(win.innerHeight - 1, gesture.lastClientY));
  const stack = doc.elementsFromPoint(x, y);
  for (const candidate of stack) {
    if (!candidate || candidate === gesture.element || candidate.closest("#pwb-canvas-box")) {
      continue;
    }
    const module = resolveCanvasModule(candidate);
    if (
      module
      && module !== gesture.element
      && !gesture.element.contains(module)
      && !module.contains(gesture.element)
      && doc.body.contains(module)
    ) {
      return module;
    }
  }
  return null;
}

function applyCanvasDropReorder(gesture) {
  if (gesture.mode !== "move" || gesture.element.dataset.pwbFree === "true") {
    return false;
  }
  const target = findCanvasDropTarget(gesture);
  if (!target || !target.parentElement) {
    return false;
  }
  const targetRect = target.getBoundingClientRect();
  const after = gesture.lastClientY > targetRect.top + targetRect.height / 2;
  const parent = target.parentElement;
  const element = gesture.element;
  resetMoveMarginsToGestureBase(element, gesture);
  if (after) {
    parent.insertBefore(element, target.nextSibling);
  } else {
    parent.insertBefore(element, target);
  }
  if (!state.canvasModules.includes(element)) {
    state.canvasModules.push(element);
  }
  selectCanvasModule(element);
  return true;
}

function finishCanvasGesture() {
  if (!state.canvasGesture) {
    return;
  }
  hideCanvasGuides();
  const gesture = state.canvasGesture;
  const reordered = applyCanvasDropReorder(gesture);
  const afterState = captureCanvasState(gesture.element);
  if (canvasStateChanged(gesture.beforeState, afterState)) {
    state.canvasHistory.push({
      element: gesture.element,
      action: reordered ? "reorder" : gesture.mode,
      beforeState: gesture.beforeState,
      afterState
    });
    state.canvasRedo = [];
    rebuildCanvasEdits();
  }
  state.canvasGesture = null;
}

function undoCanvasEdit() {
  const entry = state.canvasHistory.pop();
  if (!entry) {
    return;
  }
  applyCanvasState(entry.element, entry.beforeState);
  state.canvasRedo.push(entry);
  if (state.selectedCanvasModule === entry.element) {
    updateCanvasBox();
  }
  rebuildCanvasEdits();
  setStatus("Undo");
}

function redoCanvasEdit() {
  const entry = state.canvasRedo.pop();
  if (!entry) {
    return;
  }
  applyCanvasState(entry.element, entry.afterState);
  state.canvasHistory.push(entry);
  if (state.selectedCanvasModule === entry.element) {
    updateCanvasBox();
  }
  rebuildCanvasEdits();
  setStatus("Redo");
}

function commitCanvasAction(element, action, beforeState) {
  const afterState = captureCanvasState(element);
  if (canvasStateChanged(beforeState, afterState)) {
    state.canvasHistory.push({ element, action, beforeState, afterState });
    state.canvasRedo = [];
    rebuildCanvasEdits();
  }
}

function stashCanvasModule(element = state.selectedCanvasModule) {
  if (!element || !state.canvasMode) {
    return;
  }
  const beforeState = captureCanvasState(element);
  canvasResourceFor(element);
  element.classList.remove("pwb-canvas-selected");
  element.classList.add("pwb-resource-stashed");
  element.dataset.pwbStashed = "true";
  if (element === state.selectedCanvasModule) {
    state.selectedCanvasModule = null;
  }
  removeCanvasPlaceholder(element);
  updateCanvasBox();
  commitCanvasAction(element, "stash", beforeState);
  renderResourceShelf();
  els.stashBtn.disabled = true;
  setStatus("Module stashed");
}

function placeCanvasResource(element) {
  if (!element || !state.canvasMode) {
    return;
  }
  const beforeState = captureCanvasState(element);
  element.classList.remove("pwb-resource-stashed");
  delete element.dataset.pwbStashed;
  ensureFreeCanvasModule(element);
  removeCanvasPlaceholder(element);
  const win = frameWindow();
  const rect = element.getBoundingClientRect();
  const x = win ? win.scrollX + Math.max(24, (win.innerWidth - rect.width) / 2) : 24;
  const y = win ? win.scrollY + Math.max(24, (win.innerHeight - rect.height) / 2) : 24;
  Object.assign(element.style, {
    display: "",
    position: "absolute",
    left: `${Math.round(x)}px`,
    top: `${Math.round(y)}px`,
    width: `${Math.max(24, Math.round(rect.width || Number(element.dataset.pwbBaseWidth || 240)))}px`,
    minHeight: `${Math.max(18, Math.round(rect.height || Number(element.dataset.pwbBaseHeight || 120)))}px`,
    maxWidth: "none",
    margin: "0",
    zIndex: "2147483000"
  });
  selectCanvasModule(element);
  commitCanvasAction(element, "place", beforeState);
  renderResourceShelf();
  setStatus("Module placed");
}

function handleUndoRedoKey(event) {
  const isModifier = event.metaKey || event.ctrlKey;
  if (!isModifier || event.altKey) {
    return;
  }
  const key = event.key.toLowerCase();
  if (key === "z" && event.shiftKey) {
    event.preventDefault();
    redoCanvasEdit();
  } else if (key === "z") {
    event.preventDefault();
    undoCanvasEdit();
  } else if (key === "y") {
    event.preventDefault();
    redoCanvasEdit();
  }
}

async function saveLayoutEdits() {
  if (state.canvasEdits.size === 0) {
    throw new Error("No canvas layout edits to save.");
  }
  const payload = await api("/api/layout-edits", {
    session_id: state.sessionId,
    token: state.token,
    page: state.previewUrl,
    html_path: state.htmlPath,
    zoom: state.zoom,
    edits: Array.from(state.canvasEdits.values())
  });
  state.annotationBundle = payload.bundle;
  els.includeAnnotation.disabled = false;
  els.includeAnnotation.checked = true;
  addMessage("system", `Canvas layout edits saved: ${payload.bundle.layout_json}`);
  setStatus("Layout edits saved");
}

function toggleCanvasMode() {
  state.canvasMode = !state.canvasMode;
  if (state.canvasMode) {
    state.marking = false;
    els.overlay.hidden = true;
    els.markBtn.textContent = "Mark Region";
    installCanvasModules();
  } else {
    uninstallCanvasModules();
    setStatus("Canvas mode off");
  }
  els.canvasBtn.textContent = state.canvasMode ? "Exit Canvas" : "Canvas Mode";
  els.canvasBtn.setAttribute("aria-pressed", state.canvasMode ? "true" : "false");
  renderResourceShelf();
  updateHistoryButtons();
}

async function saveAnnotation(instruction) {
  const doc = frameDocument();
  const scroll = frameScroll();
  const viewport = {
    width: doc ? doc.documentElement.clientWidth : null,
    height: doc ? doc.documentElement.clientHeight : null,
    scrollX: Math.round(scroll.x),
    scrollY: Math.round(scroll.y),
    devicePixelRatio: els.previewFrame.contentWindow ? els.previewFrame.contentWindow.devicePixelRatio : window.devicePixelRatio
  };
  const payload = await api("/api/annotation", {
    session_id: state.sessionId,
    token: state.token,
    page: state.previewUrl,
    instruction,
    viewport,
    selection: state.selection,
    elements: state.elements
  });
  state.annotationBundle = payload.bundle;
  els.includeAnnotation.disabled = false;
  els.includeAnnotation.checked = true;
  addMessage("system", `Selected region saved: ${payload.bundle.annotation_json}`);
}

async function validatePage() {
  if (!state.token) {
    throw new Error("No preview is loaded.");
  }
  setStatus("Validating...", "busy");
  const payload = await api("/api/validate", { token: state.token });
  addMessage("system", JSON.stringify(payload.checks, null, 2));
  setStatus("Validation complete");
}

els.newSessionBtn.addEventListener("click", () => {
  createSession().catch(error => setStatus(error.message, "error"));
});

els.browseBtn.addEventListener("click", () => {
  const start = els.projectPath.value.trim();
  browsePath(start).catch(error => setStatus(error.message, "error"));
});

els.parentDirBtn.addEventListener("click", () => {
  const path = els.parentDirBtn.dataset.path;
  if (path) {
    browsePath(path).catch(error => setStatus(error.message, "error"));
  }
});

els.useFolderBtn.addEventListener("click", chooseCurrentFolder);

els.inspectBtn.addEventListener("click", () => {
  inspectProject().catch(error => setStatus(error.message, "error"));
});

els.chatForm.addEventListener("submit", event => {
  event.preventDefault();
  const message = els.chatInput.value.trim();
  if (!message) {
    return;
  }
  sendMessage(message).catch(error => {
    setStatus(error.message, "error");
    els.sendBtn.disabled = false;
  });
});

els.markBtn.addEventListener("click", () => {
  state.marking = !state.marking;
  if (state.marking && state.canvasMode) {
    state.canvasMode = false;
    uninstallCanvasModules();
    els.canvasBtn.textContent = "Canvas Mode";
  }
  els.overlay.hidden = !state.marking;
  els.markBtn.textContent = state.marking ? "Cancel Marking" : "Mark Region";
  setStatus(state.marking ? "Drag over the preview" : "Preview ready");
});

els.validateBtn.addEventListener("click", () => {
  validatePage().catch(error => setStatus(error.message, "error"));
});

els.zoomOutBtn.addEventListener("click", () => {
  setPreviewZoom(state.zoom - 0.1);
});

els.zoomInBtn.addEventListener("click", () => {
  setPreviewZoom(state.zoom + 0.1);
});

els.canvasBtn.addEventListener("click", () => {
  toggleCanvasMode();
});

els.stashBtn.addEventListener("click", () => {
  stashCanvasModule();
});

els.undoBtn.addEventListener("click", () => {
  undoCanvasEdit();
});

els.redoBtn.addEventListener("click", () => {
  redoCanvasEdit();
});

els.saveLayoutBtn.addEventListener("click", () => {
  saveLayoutEdits().catch(error => setStatus(error.message, "error"));
});

els.overlay.addEventListener("mousedown", event => {
  if (!state.marking) {
    return;
  }
  state.dragStart = overlayPoint(event);
  state.selection = null;
  drawViewportSelection({ ...state.dragStart, width: 0, height: 0 });
});

els.overlay.addEventListener("mousemove", event => {
  if (!state.dragStart) {
    return;
  }
  drawViewportSelection(normalizeRect(state.dragStart, overlayPoint(event)));
});

window.addEventListener("mouseup", event => {
  if (state.canvasGesture) {
    finishCanvasGesture();
    return;
  }
  if (!state.dragStart) {
    return;
  }
  const rect = normalizeRect(state.dragStart, overlayPoint(event));
  state.dragStart = null;
  if (rect.width < 8 || rect.height < 8) {
    state.selection = null;
    state.elements = [];
    drawViewportSelection(null);
    return;
  }
  state.selection = selectionFromViewportRect(rect);
  state.elements = collectElements(state.selection);
  state.marking = false;
  els.overlay.hidden = true;
  els.markBtn.textContent = "Mark Region";
  redrawSelectionBox();
  saveAnnotation(
    `User selected document region ${state.selection.document.width}x${state.selection.document.height} at ${state.selection.document.x},${state.selection.document.y}.`
  ).catch(error => {
    setStatus(error.message, "error");
  });
  setStatus("Region selected");
});

window.addEventListener("mousemove", event => {
  updateCanvasGesture(event);
});

window.addEventListener("keydown", event => {
  handleUndoRedoKey(event);
});

els.previewFrame.addEventListener("load", () => {
  const win = frameWindow();
  if (state.frameScrollHandler && win) {
    win.removeEventListener("scroll", state.frameScrollHandler);
  }
  if (state.frameMouseMoveHandler && win) {
    win.removeEventListener("mousemove", state.frameMouseMoveHandler);
  }
  if (state.frameMouseUpHandler && win) {
    win.removeEventListener("mouseup", state.frameMouseUpHandler);
  }
  if (state.frameKeydownHandler && win) {
    win.removeEventListener("keydown", state.frameKeydownHandler);
  }
  state.frameScrollHandler = () => redrawSelectionBox();
  state.frameMouseMoveHandler = event => updateCanvasGesture(event);
  state.frameMouseUpHandler = () => finishCanvasGesture();
  state.frameKeydownHandler = event => handleUndoRedoKey(event);
  if (win) {
    win.addEventListener("scroll", state.frameScrollHandler, { passive: true });
    win.addEventListener("mousemove", state.frameMouseMoveHandler);
    win.addEventListener("mouseup", state.frameMouseUpHandler);
    win.addEventListener("keydown", state.frameKeydownHandler);
  }
  state.selection = null;
  state.elements = [];
  state.canvasMode = false;
  state.canvasEdits.clear();
  state.canvasHistory = [];
  state.canvasRedo = [];
  state.canvasModules = [];
  state.canvasResources.clear();
  state.selectedCanvasModule = null;
  state.canvasGesture = null;
  els.canvasBtn.textContent = "Canvas Mode";
  els.canvasBtn.setAttribute("aria-pressed", "false");
  els.stashBtn.disabled = true;
  els.resourceShelf.hidden = true;
  els.saveLayoutBtn.disabled = true;
  updateHistoryButtons();
  applyPreviewZoom();
  drawViewportSelection(null);
});
