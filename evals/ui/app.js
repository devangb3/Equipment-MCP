const byId = (id) => document.getElementById(id);
const ui = Object.fromEntries(
  ["refresh", "files", "file-count", "file-head", "filename", "file-meta", "message",
    "raw-toggle", "raw", "raw-text", "file-body", "cases", "case-count", "search",
    "filter", "record"].map((id) => [id, byId(id)]),
);

const state = { files: [], name: null, records: [], selected: null, raw: false, request: 0 };
const labels = { passed: "Passed", failed: "Failed", error: "Error" };

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function badge(status) {
  return element("span", `badge ${status}`, labels[status]);
}

function button(title, className, onClick) {
  const node = element("button", className);
  node.type = "button";
  node.append(element("span", "row-title", title));
  node.addEventListener("click", onClick);
  return node;
}

function sizeLabel(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  const [value, unit] = bytes < 1024 ** 2
    ? [bytes / 1024, "KB"]
    : [bytes / 1024 ** 2, "MB"];
  return `${value.toFixed(1)} ${unit}`;
}

function runId(filename) {
  const dot = filename.lastIndexOf(".");
  return dot > 0 ? filename.slice(0, dot) : filename;
}

function copyRunButton(id) {
  const node = element("button", "copy-run");
  node.type = "button";
  node.setAttribute("aria-label", `Copy run id ${id}`);
  node.title = "Copy run id";
  node.textContent = "Copy";
  node.addEventListener("click", async (event) => {
    event.stopPropagation();
    const label = node.textContent;
    try {
      await navigator.clipboard.writeText(id);
      node.textContent = "Copied";
    } catch {
      node.textContent = "Failed";
    }
    window.setTimeout(() => {
      node.textContent = label;
    }, 1200);
  });
  return node;
}

function label(key) {
  const words = key.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function statusOf(record) {
  const value = record.value;
  const score = value?.grade ?? value;
  if (record.issue !== undefined || value?.error || score?.error) return "error";
  if (score?.passed === true) return "passed";
  if (score?.passed === false) return "failed";
  return "";
}

function parseRecords(filename, source) {
  if (filename.toLowerCase().endsWith(".jsonl")) {
    const records = [];
    source.split(/\r?\n/).forEach((line, index) => {
      if (!line.trim()) return;
      try {
        records.push({ value: JSON.parse(line), line: index + 1 });
      } catch {
        records.push({ issue: line, line: index + 1 });
      }
    });
    return records;
  }
  if (filename.toLowerCase().endsWith(".json")) {
    try {
      const data = JSON.parse(source);
      return (Array.isArray(data) ? data : [data]).map((value) => ({ value }));
    } catch {
      return [{ issue: source }];
    }
  }
  return null;
}

function titleOf(record, index) {
  return record.value?.id || (record.line ? `Line ${record.line}` : `Record ${index + 1}`);
}

async function fetchResult(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response;
}

function showMessage(text) {
  ui.message.hidden = !text;
  ui.message.textContent = text;
}

function renderFiles() {
  ui.files.replaceChildren();
  ui["file-count"].hidden = !state.files.length;
  ui["file-count"].textContent = state.files.length;
  for (const file of state.files) {
    const row = element("div", "file-row");
    row.dataset.name = file.name;
    const open = element("button", "file-open");
    open.type = "button";
    open.append(element("span", "row-title", file.name));
    open.addEventListener("click", () => {
      if (file.name !== state.name || ui["raw-toggle"].hidden) loadFile(file);
    });
    const head = element("div", "file-row-head");
    head.append(open, copyRunButton(runId(file.name)));
    row.append(head, element("span", "row-meta", sizeLabel(file.size)));
    ui.files.append(row);
  }
  if (!state.files.length) {
    ui.files.append(element("p", "empty", "No files found in evals/results."));
  }
  updateFileSelection();
}

function updateFileSelection() {
  for (const row of ui.files.querySelectorAll(".file-row")) {
    row.setAttribute("aria-pressed", row.dataset.name === state.name);
  }
}

async function refreshFiles() {
  const request = ++state.request;
  try {
    const response = await fetchResult("/api/files");
    const files = await response.json();
    if (request !== state.request) return;
    state.files = files;
    renderFiles();
    const file = files.find(({ name }) => name === state.name) ?? files[0];
    if (file) {
      await loadFile(file);
    } else {
      state.name = null;
      ui["file-head"].hidden = ui["file-body"].hidden = ui.raw.hidden = true;
      showMessage("Add a result file to evals/results, then refresh.");
    }
  } catch (error) {
    if (request !== state.request) return;
    if (!state.files.length) ui.files.replaceChildren();
    showMessage(`Couldn't list result files (${error.message}). Try Refresh files.`);
  }
}

async function loadFile(file) {
  const request = ++state.request;
  if (file.name !== state.name) {
    state.selected = null;
    state.raw = false;
    ui.search.value = "";
    ui.filter.value = "all";
  }
  state.name = file.name;
  updateFileSelection();
  ui.filename.textContent = file.name;
  ui["file-meta"].textContent = sizeLabel(file.size);
  ui["file-head"].hidden = false;
  ui["file-body"].hidden = ui.raw.hidden = ui["raw-toggle"].hidden = true;
  showMessage("Loading file…");
  try {
    const response = await fetchResult(`/api/files/${encodeURIComponent(file.name)}`);
    const source = await response.text();
    if (request !== state.request) return;
    state.records = parseRecords(file.name, source);
    ui["raw-text"].textContent = source || "This file is empty.";
    ui.raw.scrollTop = 0;
    renderFileMeta();
    renderCases();
    showMessage("");
    renderMode();
  } catch (error) {
    if (request !== state.request) return;
    showMessage(`Couldn't open this file (${error.message}). Try Refresh files.`);
  }
}

function renderFileMeta() {
  if (!state.records) return;
  const total = state.records.length;
  ui["file-meta"].replaceChildren(element("span", "", `${total} ${total === 1 ? "record" : "records"}`));
  const counts = { passed: 0, failed: 0, error: 0 };
  for (const record of state.records) {
    const status = statusOf(record);
    if (status) counts[status] += 1;
  }
  ui.filter.hidden = !state.records.some(({ value }) => typeof (value?.grade ?? value)?.passed === "boolean");
  if (ui.filter.hidden) ui.filter.value = "all";
  for (const [status, count] of Object.entries(counts)) {
    if (count) {
      const description = status === "error" && count !== 1 ? "errors" : labels[status].toLowerCase();
      ui["file-meta"].append(element("span", `summary ${status}`, `${count} ${description}`));
    }
  }
}

function renderMode() {
  const hasRecords = state.records !== null;
  const raw = state.raw || !hasRecords;
  ui["raw-toggle"].hidden = !hasRecords;
  ui["raw-toggle"].textContent = raw ? "View cases" : "View raw file";
  ui.raw.hidden = !raw;
  ui["file-body"].hidden = raw;
}

function renderCases() {
  if (!state.records) return;
  const query = ui.search.value.trim().toLowerCase();
  const filter = ui.filter.value;
  const matches = [];
  for (const [index, record] of state.records.entries()) {
    const title = titleOf(record, index);
    const status = statusOf(record);
    const request = record.value?.input?.request ?? "";
    if (!`${title} ${request}`.toLowerCase().includes(query)) continue;
    if (filter !== "all" && filter !== status) continue;
    matches.push({ index, title, status });
  }
  if (!matches.some(({ index }) => index === state.selected)) {
    state.selected = matches[0]?.index ?? null;
  }
  ui["case-count"].textContent = matches.length;
  ui.cases.replaceChildren();
  for (const { index, title, status } of matches) {
    const row = button(title, "case-row", () => selectRecord(index));
    row.dataset.index = index;
    if (status) row.append(badge(status));
    ui.cases.append(row);
  }
  if (!matches.length) {
    const text = state.records.length ? "No matching cases." : "This file has no records.";
    ui.cases.append(element("p", "empty", text));
  }
  selectRecord(state.selected);
}

function selectRecord(index) {
  state.selected = index;
  for (const row of ui.cases.querySelectorAll("button")) {
    row.setAttribute("aria-pressed", Number(row.dataset.index) === index);
  }
  ui.record.replaceChildren();
  ui.record.scrollTop = 0;
  if (index === null) return;

  const record = state.records[index];
  const { value, line, issue } = record;
  const score = value?.grade ?? value;
  const heading = element("header", "record-head");
  heading.append(element("h3", "", titleOf(record, index)));
  const status = statusOf(record);
  if (status) heading.append(badge(status));
  ui.record.append(heading);
  if (line || score?.model) {
    const meta = element("p", "record-meta");
    if (line) meta.append(element("span", "", `Line ${line}`));
    if (score?.model) meta.append(element("span", "", `Judge model ${score.model}`));
    ui.record.append(meta);
  }
  if (issue !== undefined) {
    addSection("Invalid JSON", element("pre", "", issue));
    return;
  }
  const isRun = Array.isArray(value?.trace) || Array.isArray(value?.new_requests);
  const isGrade = typeof score?.passed === "boolean";
  if (isRun && value?.error) addSection("Agent error", element("p", "prose error-text", value.error));
  if (score?.error && (!isRun || score.error !== value?.error)) {
    addSection(isGrade ? "Grading error" : "Error", element("p", "prose error-text", score.error));
  }
  if (value?.input?.request) {
    const request = element("div");
    if (value.input.employee_id) {
      request.append(element("p", "employee", `Employee ${value.input.employee_id}`));
    }
    request.append(element("p", "prose", value.input.request));
    addSection("Employee request", request);
  }
  if (value?.final) addSection("Final response", element("p", "prose response", value.final));
  if (score?.verdict) {
    const { case_rubric: rubric, ...shared } = score.verdict;
    addFindings("Judge findings", shared);
    if (rubric) addFindings("Case rubric", rubric);
  }
  if (score?.checks) addFindings("Deterministic checks", score.checks);
  if (Array.isArray(value?.trace)) {
    const trace = element("ol", "trace");
    for (const step of value.trace) trace.append(element("li", "", step));
    addSection("Agent trace", trace);
  }
  if (Array.isArray(value?.new_requests)) {
    addSection("New database requests", value.new_requests.length
      ? jsonBlock(value.new_requests)
      : element("p", "quiet", "No new requests."));
  }
  const json = jsonBlock(value);
  if (isRun || isGrade) {
    const details = element("details", "record-json");
    details.append(element("summary", "", "Record JSON"), json);
    ui.record.append(details);
  } else {
    ui.record.append(json);
  }
}

function addSection(title, content) {
  const section = element("section", "detail");
  section.append(element("h4", "", title), content);
  ui.record.append(section);
}

function jsonBlock(value) {
  return element("pre", "", JSON.stringify(value, null, 2));
}

function addFindings(title, findings) {
  const list = element("ul", "findings");
  for (const [key, finding] of Object.entries(findings)) {
    const item = element("li");
    const header = element("div", "finding-head");
    const passed = typeof finding === "boolean" ? finding : finding?.passed;
    header.append(element("strong", "", label(key)));
    if (typeof passed === "boolean") header.append(badge(passed ? "passed" : "failed"));
    item.append(header);
    if (finding?.evidence) item.append(element("p", "prose", finding.evidence));
    list.append(item);
  }
  if (list.children.length) addSection(title, list);
}

ui.refresh.addEventListener("click", refreshFiles);
ui.search.addEventListener("input", renderCases);
ui.filter.addEventListener("change", renderCases);
ui["raw-toggle"].addEventListener("click", () => {
  state.raw = !state.raw;
  renderMode();
});
refreshFiles();
