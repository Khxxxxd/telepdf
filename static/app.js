const statusGrid = document.querySelector("#status-grid");
const jobHighlights = document.querySelector("#job-highlights");
const jobState = document.querySelector("#job-state");
const toast = document.querySelector("#toast");
const statusPill = document.querySelector("#status-pill");
const progressLabel = document.querySelector("#progress-label");
const progressValue = document.querySelector("#progress-value");
const progressFill = document.querySelector("#progress-fill");
const stopDownloadButton = document.querySelector("#stop-download");
const logoutButton = document.querySelector("#logout-button");
const clearStorageButton = document.querySelector("#clear-storage-button");

function translateJobStatus(value) {
  const mapping = {
    idle: "جاهز",
    running: "قيد التشغيل",
    stopping: "جارِ الإيقاف",
    stopped: "متوقف",
    completed: "مكتمل",
    failed: "فشل",
  };
  return mapping[value] || value || "جاهز";
}

async function request(path, payload = null) {
  const response = await fetch(path, {
    method: payload ? "POST" : "GET",
    headers: payload ? { "Content-Type": "application/json" } : undefined,
    body: payload ? JSON.stringify(payload) : undefined,
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "فشل الطلب.");
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
    return "غير محفوظ";
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

  statusPill.textContent = translateJobStatus(job.status);
  statusPill.dataset.status = job.status || "idle";

  if (job.status === "running") {
    if (job.discovered_pdfs > 0) {
      progressLabel.textContent = `تمت معالجة ${processedPdfs} من ${job.discovered_pdfs} ملف PDF`;
      progressValue.textContent = `${Math.min(ratio, 100)}%`;
      progressFill.style.width = `${Math.min(ratio, 100)}%`;
    } else {
      progressLabel.textContent = "جارِ فحص الرسائل واكتشاف الملفات...";
      progressValue.textContent = `${job.scanned_messages || 0} رسالة`;
      progressFill.style.width = "8%";
    }
    return;
  }

  if (job.status === "stopping") {
    progressLabel.textContent = "جارِ إيقاف المهمة بعد إنهاء الملف الحالي...";
    progressValue.textContent = "انتظر";
    progressFill.style.width = "100%";
    return;
  }

  if (job.status === "stopped") {
    progressLabel.textContent = "تم إيقاف المهمة";
    progressValue.textContent = "متوقف";
    progressFill.style.width = "100%";
    return;
  }

  if (job.status === "completed") {
    progressLabel.textContent = "اكتملت المهمة";
    progressValue.textContent = "100%";
    progressFill.style.width = "100%";
    return;
  }

  if (job.status === "failed") {
    progressLabel.textContent = job.error || "توقفت المهمة";
    progressValue.textContent = "متوقف";
    progressFill.style.width = "100%";
    return;
  }

  progressLabel.textContent = "بانتظار بدء المهمة";
  progressValue.textContent = "0%";
  progressFill.style.width = "0%";
}

function renderHighlights(job) {
  const highlights = [
    ["المصدر", job.source || "غير محدد"],
    ["مجلد الحفظ", job.output_dir || "غير محدد"],
    ["وقت البدء", job.started_at || "لم تبدأ بعد"],
    ["وقت الانتهاء", job.finished_at || "لم تنتهِ بعد"],
    ["آخر ملف", job.last_file || "لا يوجد بعد"],
    ["الخطأ", job.error || "لا يوجد"],
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
    ["API ID", status.config.api_id_set ? "محفوظ" : "غير محفوظ", status.config.api_id_set ? "good" : "warn"],
    ["API Hash", status.config.api_hash_set ? "محفوظ" : "غير محفوظ", status.config.api_hash_set ? "good" : "warn"],
    ["رقم الهاتف", maskPhone(status.config.phone), status.config.phone ? "default" : "warn"],
    ["مسجل الدخول", status.auth.authorized ? "نعم" : "لا", status.auth.authorized ? "good" : "warn"],
    ["بانتظار 2FA", status.auth.pending_password ? "نعم" : "لا", status.auth.pending_password ? "warn" : "default"],
    ["الرسائل المفحوصة", String(status.job.scanned_messages || 0), "default"],
    ["ملفات PDF المكتشفة", String(status.job.discovered_pdfs || 0), "default"],
    ["الملفات المحفوظة", String(status.job.downloaded_count || 0), "good"],
    ["الملفات المتجاوزة", String(status.job.skipped_count || 0), "default"],
    ["الملفات الفاشلة", String(status.job.failed_count || 0), status.job.failed_count ? "danger" : "default"],
  ];

  statusGrid.innerHTML = cards.map(([label, value, tone]) => buildCard(label, value, tone)).join("");
  renderProgress(status.job);
  renderHighlights(status.job);
  jobState.textContent = JSON.stringify(status.job, null, 2);
  stopDownloadButton.disabled = !["running", "stopping"].includes(status.job.status);
  stopDownloadButton.textContent = status.job.status === "stopping" ? "جارِ الإيقاف..." : "إيقاف التنزيل";
  logoutButton.disabled = ["running", "stopping"].includes(status.job.status);
  clearStorageButton.disabled = ["running", "stopping"].includes(status.job.status);
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
    flash("تم حفظ الإعدادات محلياً.");
    refreshStatus();
  } catch (error) {
    flash(error.message, true);
  }
});

document.querySelector("#send-code").addEventListener("click", async () => {
  try {
    await request("/api/auth/send-code", {});
    flash("تم إرسال كود تيليجرام.");
    refreshStatus();
  } catch (error) {
    flash(error.message, true);
  }
});

document.querySelector("#verify-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  try {
    await request("/api/auth/verify", Object.fromEntries(formData.entries()));
    flash("تم تسجيل الدخول بنجاح.");
    refreshStatus();
  } catch (error) {
    flash(error.message, true);
  }
});

document.querySelector("#download-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  try {
    await request("/api/downloads/start", Object.fromEntries(formData.entries()));
    flash("بدأت مهمة التنزيل.");
    refreshStatus();
  } catch (error) {
    flash(error.message, true);
  }
});

stopDownloadButton.addEventListener("click", async () => {
  try {
    const result = await request("/api/downloads/stop", {});
    flash(result.message);
    refreshStatus();
  } catch (error) {
    flash(error.message, true);
  }
});

logoutButton.addEventListener("click", async () => {
  if (!window.confirm("سيتم حذف جلسة تيليجرام المحلية من هذا الجهاز. هل تريد المتابعة؟")) {
    return;
  }
  try {
    const result = await request("/api/auth/logout", {});
    flash(result.message);
    refreshStatus();
  } catch (error) {
    flash(error.message, true);
  }
});

clearStorageButton.addEventListener("click", async () => {
  if (!window.confirm("سيتم حذف الإعدادات والجلسة والسجل المحلي من TelePDF فقط. ملفات PDF التي نزلتها لن تُحذف. هل تريد المتابعة؟")) {
    return;
  }
  try {
    const result = await request("/api/storage/clear", {});
    flash(result.message);
    document.querySelector("#config-form").reset();
    document.querySelector("#verify-form").reset();
    refreshStatus();
  } catch (error) {
    flash(error.message, true);
  }
});

refreshStatus();
setInterval(refreshStatus, 2500);
