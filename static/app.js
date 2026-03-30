const statusGrid = document.querySelector("#status-grid");
const jobHighlights = document.querySelector("#job-highlights");
const jobState = document.querySelector("#job-state");
const toast = document.querySelector("#toast");
const statusPill = document.querySelector("#status-pill");
const progressLabel = document.querySelector("#progress-label");
const progressValue = document.querySelector("#progress-value");
const progressFill = document.querySelector("#progress-fill");

async function request(path, payload = null) {
  const response = await fetch(path, {
    method: payload ? "POST" : "GET",
    headers: payload ? { "Content-Type": "application/json" } : undefined,
    body: payload ? JSON.stringify(payload) : undefined,
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }
  return data;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function flash(message, isError = false) {
  toast.textContent = message;
  toast.hidden = false;
  toast.dataset.variant = isError ? "error" : "success";
  clearTimeout(flash.timer);
  flash.timer = setTimeout(() => {
    toast.hidden = true;
  }, 3500);
}

function maskPhone(phone) {
  if (!phone) {
    return "Not saved";
  }
  if (phone.length <= 5) {
    return phone;
  }
  return `${phone.slice(0, 4)}•••${phone.slice(-2)}`;
}

function buildCard(label, value, tone = "default") {
  return `
    <article class="status-card" data-tone="${tone}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </article>
  `;
}

function renderProgress(job) {
  const processedPdfs = job.downloaded_count + job.skipped_count + job.failed_count;
  const ratio = job.discovered_pdfs > 0 ? Math.round((processedPdfs / job.discovered_pdfs) * 100) : 0;

  statusPill.textContent = job.status || "idle";
  statusPill.dataset.status = job.status || "idle";

  if (job.status === "running") {
    progressLabel.textContent = `Processing ${processedPdfs} of ${job.discovered_pdfs || 0} discovered PDFs`;
    progressValue.textContent = `${Math.min(ratio, 100)}%`;
    progressFill.style.width = `${Math.min(ratio, 100)}%`;
    return;
  }

  if (job.status === "completed") {
    progressLabel.textContent = "Archive completed";
    progressValue.textContent = "100%";
    progressFill.style.width = "100%";
    return;
  }

  if (job.status === "failed") {
    progressLabel.textContent = job.error || "The job failed";
    progressValue.textContent = "Stopped";
    progressFill.style.width = "100%";
    return;
  }

  progressLabel.textContent = "Waiting for a job";
  progressValue.textContent = "0%";
  progressFill.style.width = "0%";
}

function renderHighlights(job) {
  const highlights = [
    ["Source", job.source || "Not set"],
    ["Output", job.output_dir || "Not set"],
    ["Started", job.started_at || "Not started"],
    ["Finished", job.finished_at || "Not finished"],
    ["Last file", job.last_file || "No file yet"],
    ["Error", job.error || "None"],
  ];

  jobHighlights.innerHTML = highlights
    .map(
      ([label, value]) => `
        <article class="highlight-card">
          <span>${escapeHtml(label)}</span>
          <strong title="${escapeHtml(value)}">${escapeHtml(value)}</strong>
        </article>
      `,
    )
    .join("");
}

function renderStatus(status) {
  const cards = [
    ["API ID", status.config.api_id_set ? "Saved" : "Missing", status.config.api_id_set ? "good" : "warn"],
    ["API hash", status.config.api_hash_set ? "Saved" : "Missing", status.config.api_hash_set ? "good" : "warn"],
    ["Phone", maskPhone(status.config.phone), status.config.phone ? "default" : "warn"],
    ["Authorized", status.auth.authorized ? "Yes" : "No", status.auth.authorized ? "good" : "warn"],
    ["2FA pending", status.auth.pending_password ? "Yes" : "No", status.auth.pending_password ? "warn" : "default"],
    ["Messages scanned", String(status.job.scanned_messages || 0), "default"],
    ["PDFs found", String(status.job.discovered_pdfs || 0), "default"],
    ["Saved", String(status.job.downloaded_count || 0), "good"],
    ["Skipped", String(status.job.skipped_count || 0), "default"],
    ["Failed", String(status.job.failed_count || 0), status.job.failed_count ? "danger" : "default"],
  ];

  statusGrid.innerHTML = cards.map(([label, value, tone]) => buildCard(label, value, tone)).join("");
  renderProgress(status.job);
  renderHighlights(status.job);
  jobState.textContent = JSON.stringify(status.job, null, 2);
}

async function refreshStatus() {
  try {
    const status = await request("/api/status");
    renderStatus(status);
  } catch (error) {
    flash(error.message, true);
  }
}

document.querySelector("#config-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  try {
    await request("/api/config", Object.fromEntries(formData.entries()));
    flash("Local config saved.");
    refreshStatus();
  } catch (error) {
    flash(error.message, true);
  }
});

document.querySelector("#send-code").addEventListener("click", async () => {
  try {
    const result = await request("/api/auth/send-code", {});
    flash(result.message);
    refreshStatus();
  } catch (error) {
    flash(error.message, true);
  }
});

document.querySelector("#verify-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  try {
    const result = await request("/api/auth/verify", Object.fromEntries(formData.entries()));
    flash(result.message);
    refreshStatus();
  } catch (error) {
    flash(error.message, true);
  }
});

document.querySelector("#download-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  try {
    const result = await request("/api/downloads/start", Object.fromEntries(formData.entries()));
    flash(result.message);
    refreshStatus();
  } catch (error) {
    flash(error.message, true);
  }
});

refreshStatus();
setInterval(refreshStatus, 2500);
