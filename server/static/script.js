/* ─────────────────────────────────────────────────────────────
   ClinicalTrialEnv — Frontend Logic
   Communicates with OpenEnv FastAPI server via /api/reset, /api/step
   ───────────────────────────────────────────────────────────── */

const API_URL = "/api";
let sessionId = null;
let currentTask = "easy";
let episodeActive = false;
let currentRecords = [];
let currentAuditLogs = [];
let currentTaskDesc = "";

// ── DOM refs ──────────────────────────────────────────────────
const statusDot  = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const sessionEl  = document.getElementById("session-id");
const expectedEl = document.getElementById("expected-count");
const stepEl     = document.getElementById("step-count");
const taskDescEl = document.getElementById("task-desc-box");
const submitBtn  = document.getElementById("submit-btn");
const resultsEl  = document.getElementById("results-panel");

// ── Status helpers ─────────────────────────────────────────────
function setStatus(state, txt) {
  statusDot.className = `status-dot ${state}`;
  statusText.textContent = txt;
}

// ── Tab switching ──────────────────────────────────────────────
function switchTab(tab) {
  ["records", "rules", "audit"].forEach(t => {
    document.getElementById(`tab-${t}`).classList.toggle("active", t === tab);
    document.getElementById(`panel-${t}`).classList.toggle("active", t === tab);
  });
}

// ── Task selection ─────────────────────────────────────────────
function selectTask(taskId) {
  currentTask = taskId;
  ["easy", "medium", "hard"].forEach(t => {
    document.getElementById(`btn-${t}`).classList.toggle("active", t === taskId);
  });
  resetEpisode();
}

// ── Reset / Start episode ──────────────────────────────────────
async function resetEpisode() {
  setStatus("loading", "Starting episode…");
  resultsEl.classList.add("hidden");
  submitBtn.disabled = true;
  episodeActive = false;
  sessionId = null;

  document.getElementById("records-container").innerHTML = "<p style='color:var(--text-muted);font-size:13px'>Loading…</p>";
  document.getElementById("rules-list").innerHTML = "";
  document.getElementById("audit-container").innerHTML = "";
  document.getElementById("findings-input").value = "";
  document.getElementById("explanation-input").value = "";
  stepEl.textContent = "0";

  try {
    const res = await fetch(`${API_URL}/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: currentTask }),
    });
    const data = await res.json();
    sessionId = data.session_id;
    const obs = data.observation || data;

    renderObservation(obs);
    setStatus("connected", "Environment ready");
    submitBtn.disabled = false;
    episodeActive = true;
    sessionEl.textContent = sessionId ? sessionId.slice(0, 16) + "…" : "—";
    expectedEl.textContent = obs.expected_finding_count ?? "—";
    taskDescEl.textContent = obs.task_description || "Analyze the data and submit your findings.";
  } catch (e) {
    setStatus("disconnected", "Connection failed");
    document.getElementById("records-container").innerHTML =
      "<p style='color:var(--hard);font-size:13px'>⚠ Failed to connect to server. Is it running?</p>";
  }
}

// ── Render observation data ────────────────────────────────────
function renderObservation(obs) {
  currentTaskDesc = obs.task_description || "";
  renderRecords(obs.patient_records || []);
  renderRules(obs.protocol_rules || []);
  currentAuditLogs = obs.audit_logs || [];
  renderAudit(currentAuditLogs);
}

function renderRecords(records) {
  currentRecords = records;
  const container = document.getElementById("records-container");
  if (!records.length) {
    container.innerHTML = "<p style='color:var(--text-muted);font-size:13px'>No records for this task.</p>";
    return;
  }
  container.innerHTML = records.map((rec, i) => {
    const pid = rec.Patient_ID || `Record #${i + 1}`;
    const fields = Object.entries(rec).filter(([k]) => k !== "Patient_ID");
    const hasError = fields.some(([, v]) => v === null || v === undefined || v === "");
    const fieldsHtml = fields.map(([k, v]) => {
      const missing = (v === null || v === undefined || v === "");
      return `<div class="record-field">
        <span class="field-key">${k}</span>
        <span class="field-value ${missing ? 'missing' : ''}">${missing ? 'NULL ⚠' : v}</span>
      </div>`;
    }).join("");
    return `<div class="record-card ${hasError ? 'has-error' : ''}">
      <div class="record-id">${pid}</div>
      <div class="record-fields">${fieldsHtml}</div>
    </div>`;
  }).join("");
}

function renderRules(rules) {
  const ul = document.getElementById("rules-list");
  const countEl = document.getElementById("protocol-count");
  if (!rules.length) {
    ul.innerHTML = "<li class='empty-rule'>No protocol rules for this task.</li>";
    countEl.textContent = "0 rules";
    return;
  }
  countEl.textContent = `${rules.length} rule${rules.length !== 1 ? 's' : ''}`;
  ul.innerHTML = rules.map((r, i) => `<li class="rule-item" id="rule-${i}">
    <div class="rule-content">
      <span class="rule-number">${i + 1}</span>
      <span class="rule-text" id="rule-text-${i}">${r}</span>
    </div>
    <div class="rule-actions">
      <button class="rule-edit-btn" onclick="startEditRule(${i})" title="Edit rule">✏️</button>
      <button class="rule-delete-btn" onclick="deleteProtocolRule(${i})" title="Delete rule">🗑️</button>
    </div>
  </li>`).join("");
}

// ── Protocol CRUD ─────────────────────────────────────────────
async function loadProtocols() {
  try {
    const res = await fetch(`/api/protocols?task_id=${currentTask}`);
    const data = await res.json();
    renderRules(data.protocols || []);
  } catch (e) {
    console.error("Failed to load protocols:", e);
  }
}

function startEditRule(index) {
  const textEl = document.getElementById(`rule-text-${index}`);
  const ruleItem = document.getElementById(`rule-${index}`);
  const currentText = textEl.textContent;

  ruleItem.classList.add("editing");
  textEl.innerHTML = `<input type="text" class="edit-rule-input" id="edit-input-${index}" value="${currentText.replace(/"/g, '&quot;')}" />`;

  const actionsDiv = ruleItem.querySelector(".rule-actions");
  actionsDiv.innerHTML = `
    <button class="rule-save-btn" onclick="saveEditRule(${index})" title="Save">✅</button>
    <button class="rule-cancel-btn" onclick="cancelEditRule(${index}, '${currentText.replace(/'/g, "\\'")}')" title="Cancel">❌</button>
  `;

  document.getElementById(`edit-input-${index}`).focus();
  document.getElementById(`edit-input-${index}`).addEventListener("keydown", (e) => {
    if (e.key === "Enter") saveEditRule(index);
    if (e.key === "Escape") cancelEditRule(index, currentText);
  });
}

async function saveEditRule(index) {
  const input = document.getElementById(`edit-input-${index}`);
  const newRule = input.value.trim();
  if (!newRule) return;

  try {
    const res = await fetch(`/api/protocols`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: currentTask, index, rule: newRule }),
    });
    const data = await res.json();
    renderRules(data.protocols || []);
  } catch (e) {
    alert("Failed to update rule: " + e.message);
  }
}

function cancelEditRule(index, originalText) {
  loadProtocols();
}

async function deleteProtocolRule(index) {
  if (!confirm("Delete this protocol rule?")) return;
  try {
    const res = await fetch(`/api/protocols`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: currentTask, index }),
    });
    const data = await res.json();
    renderRules(data.protocols || []);
  } catch (e) {
    alert("Failed to delete rule: " + e.message);
  }
}

async function addProtocolRule() {
  const input = document.getElementById("new-rule-input");
  const rule = input.value.trim();
  if (!rule) { input.focus(); return; }

  try {
    const res = await fetch(`/api/protocols`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: currentTask, rule }),
    });
    const data = await res.json();
    renderRules(data.protocols || []);
    input.value = "";
  } catch (e) {
    alert("Failed to add rule: " + e.message);
  }
}

// ── LLM Protocol Extraction ──────────────────────────────────
function toggleExtractModal() {
  const modal = document.getElementById("extract-modal");
  modal.classList.toggle("hidden");
  if (!modal.classList.contains("hidden")) {
    document.getElementById("extract-text-input").focus();
  }
}

async function extractRules() {
  const textInput = document.getElementById("extract-text-input");
  const fileInput = document.getElementById("extract-file-input");
  
  const text = textInput.value.trim();
  const file = fileInput.files[0];
  
  if (!text && !file) {
    alert("Please upload a file or paste text first.");
    return;
  }

  const btn = document.getElementById("extract-submit-btn");
  const originalText = btn.textContent;
  btn.textContent = "Extracting...";
  btn.disabled = true;

  try {
    const formData = new FormData();
    formData.append("task_id", currentTask);
    formData.append("text", text);
    if (file) {
      formData.append("file", file);
    }

    const res = await fetch(`/api/extract-rules`, {
      method: "POST",
      body: formData,
    });
    
    const data = await res.json();
    if (res.ok) {
      // The rules are now extracted but we need to actually add them
      // We can just add them sequentially using the existing API
      for (const rule of data.extracted_rules) {
        await fetch(`/api/protocols`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ task_id: currentTask, rule }),
        });
      }
      
      // Reload and close
      await loadProtocols();
      toggleExtractModal();
      textInput.value = "";
      fileInput.value = "";
      alert(`Successfully added ${data.extracted_rules.length} AI-extracted rules!`);
    } else {
      alert("Extraction failed: " + (data.error || "Unknown error"));
    }
  } catch (e) {
    alert("Extraction failed: " + e.message);
  } finally {
    btn.textContent = originalText;
    btn.disabled = false;
  }
}

function renderAudit(logs) {
  const container = document.getElementById("audit-container");
  if (!logs.length) {
    container.innerHTML = "<p style='color:var(--text-muted);font-size:13px'>No audit logs for this task.</p>";
    return;
  }
  const suspiciousKeywords = ["changed", "modified", "locked", "after"];
  container.innerHTML = logs.map(log => {
    const isSuspicious = suspiciousKeywords.some(kw => log.toLowerCase().includes(kw));
    return `<div class="audit-entry ${isSuspicious ? 'suspicious' : ''}">${log}</div>`;
  }).join("");
}

// ── Submit findings ────────────────────────────────────────────
async function submitFindings() {
  if (!sessionId || !episodeActive) return;

  const rawFindings = document.getElementById("findings-input").value.trim();
  const explanation = document.getElementById("explanation-input").value.trim();

  if (!rawFindings) {
    alert("Please enter at least one finding before submitting.");
    return;
  }

  const findings = rawFindings.split("\n").map(f => f.trim()).filter(f => f.length > 0);

  submitBtn.disabled = true;
  submitBtn.querySelector("#submit-label").textContent = "⟳ Submitting…";
  setStatus("loading", "Grading…");

  try {
    const res = await fetch(`${API_URL}/step`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        task_id: currentTask,
        findings,
        explanation,
      }),
    });
    const data = await res.json();
    const obs = data.observation || data;
    const reward = data.reward ?? 0;

    // Update step count
    stepEl.textContent = "1";
    episodeActive = false;

    // Show results
    showResults(reward, obs.message || "", findings);
    setStatus("connected", "Episode complete");
  } catch (e) {
    setStatus("disconnected", "Step failed");
    submitBtn.disabled = false;
    submitBtn.querySelector("#submit-label").textContent = "⟶ Submit Findings";
  }
}

function showResults(reward, message, findings) {
  resultsEl.classList.remove("hidden");

  const scoreEl = document.getElementById("score-value");
  const barEl = document.getElementById("score-bar");
  const msgEl = document.getElementById("result-message");
  const listEl = document.getElementById("findings-list");

  // Animate score counter
  let current = 0;
  const target = reward;
  const step = target / 30;
  const interval = setInterval(() => {
    current = Math.min(current + step, target);
    scoreEl.textContent = current.toFixed(2);
    if (current >= target) clearInterval(interval);
  }, 20);

  // Colour code score
  if (reward >= 0.9) scoreEl.style.color = "var(--easy)";
  else if (reward >= 0.5) scoreEl.style.color = "var(--medium)";
  else scoreEl.style.color = "var(--hard)";

  // Animate bar
  setTimeout(() => {
    barEl.style.width = `${Math.round(reward * 100)}%`;
  }, 50);

  msgEl.textContent = message;
  listEl.innerHTML = findings.map(f => `<div class="finding-item">${f}</div>`).join("");

  submitBtn.querySelector("#submit-label").textContent = "⟶ Submit Findings";
}

// ── CSV Upload ────────────────────────────────────────────────
async function handleCSVUpload(input) {
  const file = input.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  const dropzone = document.getElementById("csv-dropzone");
  dropzone.querySelector(".dropzone-text").textContent = "Uploading…";

  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();

    if (res.ok) {
      // Show file info
      document.getElementById("csv-file-info").classList.remove("hidden");
      document.getElementById("csv-file-name").textContent = `📄 ${data.message}`;
      document.getElementById("csv-file-stats").textContent = `${data.row_count} rows · ${data.columns.length} columns`;
      dropzone.classList.add("hidden");

      // Display the uploaded records in the main panel
      renderRecords(data.records || []);
      switchTab("records");
    } else {
      alert(data.error || "Upload failed");
      dropzone.querySelector(".dropzone-text").textContent = "Click or drag CSV file here";
    }
  } catch (e) {
    alert("Upload failed: " + e.message);
    dropzone.querySelector(".dropzone-text").textContent = "Click or drag CSV file here";
  }

  input.value = "";
}

function clearCSVData() {
  document.getElementById("csv-file-info").classList.add("hidden");
  document.getElementById("csv-dropzone").classList.remove("hidden");
  document.getElementById("csv-dropzone").querySelector(".dropzone-text").textContent = "Click or drag CSV file here";
  resetEpisode();
}

// ── Drag and drop support ─────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  const dropzone = document.getElementById("csv-dropzone");
  if (dropzone) {
    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("dragover");
    });
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      const file = e.dataTransfer.files[0];
      if (file && file.name.endsWith(".csv")) {
        const input = document.getElementById("csv-file-input");
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
        handleCSVUpload(input);
      } else {
        alert("Please drop a .csv file");
      }
    });
  }
});

// ── Init ───────────────────────────────────────────────────────
resetEpisode();

// ── Auto Validate (LLM) ───────────────────────────────────────────────
async function autoValidate() {
  if (!currentRecords || currentRecords.length === 0) {
    alert("No records available to validate!");
    return;
  }

  const btn = document.getElementById("auto-validate-btn");
  const originalText = btn.innerHTML;
  btn.innerHTML = "⏳ Validating...";
  btn.disabled = true;

  try {
    // 1. Fetch the exact current protocols
    const rulesRes = await fetch(`/api/protocols?task_id=${currentTask}`);
    const rulesData = await rulesRes.json();
    const rules = rulesData.protocols || [];

    // 2. Ask backend to auto-validate using Llama 3.1
    const res = await fetch(`/api/auto-validate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task_id: currentTask,
        task_description: currentTaskDesc,
        records: currentRecords,
        protocol_rules: rules,
        audit_logs: currentAuditLogs
      })
    });
    const data = await res.json();

    if (res.ok) {
      // 3. Populate UI
      const findingsOutput = (data.findings || []).join("\n");
      document.getElementById("findings-input").value = findingsOutput;
      document.getElementById("explanation-input").value = data.explanation || "";
      
      // Flash the background of the textareas to indicate they were auto-filled
      const finInput = document.getElementById("findings-input");
      finInput.style.transition = "background-color 0.5s ease";
      finInput.style.backgroundColor = "rgba(56, 236, 182, 0.2)";
      setTimeout(() => finInput.style.backgroundColor = "var(--bg-surface)", 600);
      
      submitBtn.disabled = false;
      
      // Automatically submit the findings to get the reward!
      setTimeout(() => {
        if (!submitBtn.disabled && document.getElementById("findings-input").value.trim() !== "") {
          submitFindings();
        }
      }, 800);
    } else {
      alert("Auto-validation failed: " + (data.error || "Unknown error"));
    }
  } catch (e) {
    alert("Warning: Auto-validation failed: " + e.message);
  } finally {
    btn.innerHTML = originalText;
    btn.disabled = false;
  }
}
