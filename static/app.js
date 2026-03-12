const state = {
  activeTab: "manual",
  jobId: null,
  jobMode: "server",
  jobStatus: null,
  jobSummary: null,
  clientRows: [],
  page: 1,
  pageSize: 100,
  totalPages: 0,
  settings: null,
};

const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");
const healthBadge = document.getElementById("healthBadge");
const jobBadge = document.getElementById("jobBadge");
const manualForm = document.getElementById("manualForm");
const manualResult = document.getElementById("manualResult");
const batchForm = document.getElementById("batchForm");
const batchSummary = document.getElementById("batchSummary");
const reviewSummary = document.getElementById("reviewSummary");
const rowsBody = document.getElementById("rowsBody");
const pageMeta = document.getElementById("pageMeta");
const exportFormat = document.getElementById("exportFormat");
const downloadBtn = document.getElementById("downloadBtn");
const refreshRowsBtn = document.getElementById("refreshRowsBtn");
const prevPageBtn = document.getElementById("prevPageBtn");
const nextPageBtn = document.getElementById("nextPageBtn");
const pageSizeSelect = document.getElementById("pageSizeSelect");
const bulkCarrierForm = document.getElementById("bulkCarrierForm");
const settingsForm = document.getElementById("settingsForm");
const assetCards = document.getElementById("assetCards");
const assetCardTemplate = document.getElementById("assetCardTemplate");

tabs.forEach((tab) => {
  tab.addEventListener("click", () => switchTab(tab.dataset.tab));
});

manualForm.addEventListener("submit", onManualSubmit);
batchForm.addEventListener("submit", onBatchSubmit);
downloadBtn.addEventListener("click", onDownload);
refreshRowsBtn.addEventListener("click", loadCurrentPage);
prevPageBtn.addEventListener("click", () => changePage(-1));
nextPageBtn.addEventListener("click", () => changePage(1));
pageSizeSelect.addEventListener("change", () => {
  state.pageSize = Number(pageSizeSelect.value);
  state.page = 1;
  loadCurrentPage();
});
bulkCarrierForm.addEventListener("submit", onBulkCarrierSubmit);
settingsForm.addEventListener("submit", onSettingsSubmit);

boot();

async function boot() {
  setJobStatus("idle");
  await Promise.all([loadHealth(), loadSettings()]);
}

function switchTab(tabName) {
  state.activeTab = tabName;
  tabs.forEach((tab) => tab.classList.toggle("is-active", tab.dataset.tab === tabName));
  panels.forEach((panel) => panel.classList.toggle("is-active", panel.dataset.panel === tabName));
}

async function loadHealth() {
  const data = await request("/api/health");
  healthBadge.textContent = `Healthy - ${data.pincodes_loaded.toLocaleString()} pincodes`;
}

async function loadSettings() {
  const data = await request("/api/settings");
  state.settings = data.settings;
  settingsForm.default_export_format.value = data.settings.default_export_format;
  settingsForm.preview_page_size.value = data.settings.preview_page_size;
  settingsForm.sku_cleanup_suffixes.value = data.settings.sku_cleanup_suffixes.join("\n");
  exportFormat.value = data.settings.default_export_format;
  pageSizeSelect.value = String(data.settings.preview_page_size);
  state.pageSize = data.settings.preview_page_size;
  renderAssetCards(data.assets);
}

function renderAssetCards(assets) {
  assetCards.innerHTML = "";
  const labels = {
    price_workbook: "Calculator Workbook",
    dimensions_workbook: "Dimensions Master",
    sku_alias_workbook: "SKU Alias Master",
  };

  Object.entries(assets).forEach(([assetType, info]) => {
    const fragment = assetCardTemplate.content.cloneNode(true);
    const form = fragment.querySelector("form");
    form.dataset.assetType = assetType;
    fragment.querySelector(".asset-title").textContent = labels[assetType];
    fragment.querySelector(".asset-meta").textContent = info.exists
      ? `${info.name} - ${(info.size_bytes / 1024).toFixed(1)} KB`
      : `${info.name} - Missing`;
    fragment.querySelector(".asset-type").value = assetType;
    form.addEventListener("submit", onAssetUpload);
    assetCards.appendChild(fragment);
  });
}

async function onManualSubmit(event) {
  event.preventDefault();
  const formData = new FormData(manualForm);
  const payload = {
    weight: Number(formData.get("weight")),
    pincode: Number(formData.get("pincode")),
  };
  const data = await request("/api/calculate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  renderManualResult(data);
}

function renderManualResult(data) {
  const cards = [
    card("Best Carrier", data.best_carrier || "N/A"),
    card("Best Rate", data.best_price ?? "N/A"),
    card("Delhivery Zone", data.zones?.delhivery_zone || "-"),
    card("Bluedart Zone", data.zones?.bluedart_zone || "-"),
    card("Affinity Zone", data.zones?.affinity_zone || "-"),
  ];
  manualResult.innerHTML = cards.join("");
}

async function onBatchSubmit(event) {
  event.preventDefault();
  const files = document.getElementById("batchFiles").files;
  if (!files.length) {
    return;
  }

  const formData = new FormData();
  Array.from(files).forEach((file) => formData.append("files", file));

  const data = await request("/api/jobs", { method: "POST", body: formData });
  state.jobId = data.job_id || null;
  state.jobMode = data.job_mode || "server";
  state.jobStatus = data.status;
  state.jobSummary = data.summary;
  state.clientRows = data.rows || [];
  state.page = 1;

  setJobStatus(data.status, data.summary, data.error);
  renderSummary(batchSummary, data.summary);
  renderSummary(reviewSummary, data.summary);
  switchTab("review");

  if (state.jobMode === "client") {
    await loadCurrentPage();
    return;
  }

  renderRows([]);
  state.totalPages = 1;
  pageMeta.textContent = "Processing batch...";
  await pollJobUntilReady();
}

async function loadCurrentPage() {
  if (state.jobMode === "client") {
    const page = getClientPage();
    renderRows(page.rows);
    state.totalPages = page.totalPages;
    pageMeta.textContent = `Page ${page.page} / ${page.totalPages}`;
    return;
  }

  if (!state.jobId || state.jobStatus !== "completed") {
    return;
  }

  const data = await request(`/api/jobs/${state.jobId}/rows?page=${state.page}&page_size=${state.pageSize}`);
  state.jobStatus = data.status;
  renderRows(data.rows);
  state.totalPages = data.total_pages;
  pageMeta.textContent = `Page ${data.page} / ${data.total_pages}`;
}

async function refreshSummary() {
  if (state.jobMode === "client") {
    const summary = calculateClientSummary();
    state.jobSummary = summary;
    setJobStatus("completed", summary);
    renderSummary(reviewSummary, summary);
    renderSummary(batchSummary, summary);
    return;
  }

  if (!state.jobId) {
    return;
  }

  const data = await request(`/api/jobs/${state.jobId}`);
  state.jobStatus = data.status;
  state.jobSummary = data.summary;
  setJobStatus(data.status, data.summary, data.error);
  renderSummary(reviewSummary, data.summary);
  renderSummary(batchSummary, data.summary);
}

function renderRows(rows) {
  rowsBody.innerHTML = rows
    .map((row) => {
      const carrierOptions = Object.entries(row.carrier_prices || {})
        .filter(([, value]) => value !== null)
        .map(
          ([carrier]) =>
            `<option value="${escapeHtml(carrier)}" ${row.best_carrier === carrier ? "selected" : ""}>${escapeHtml(
              carrier
            )}</option>`
        )
        .join("");

      return `
        <tr>
          <td>${escapeHtml(row.source_platform)}</td>
          <td>${escapeHtml(row.order_id || row.order_item_id)}</td>
          <td>${escapeHtml(row.sku)}</td>
          <td>${escapeHtml(row.resolved_mtp_sku || "-")}</td>
          <td>${escapeHtml(row.product_name)}</td>
          <td>${escapeHtml(String(row.quantity))}</td>
          <td>${escapeHtml(row.pincode || "-")}</td>
          <td><input data-row-id="${row.row_id}" data-field="weight" type="number" min="0.1" step="0.1" value="${
            row.resolved_weight_kg || ""
          }" /></td>
          <td>
            <select data-row-id="${row.row_id}" data-field="carrier" ${carrierOptions ? "" : "disabled"}>
              ${carrierOptions || "<option>No carriers</option>"}
            </select>
          </td>
          <td>${row.best_rate ?? "-"}</td>
          <td>${escapeHtml(row.zone || "-")}</td>
          <td class="${row.exception_reason ? "issue" : "ok"}">${escapeHtml(row.exception_reason || "Ready")}</td>
          <td>
            <button type="button" data-row-id="${row.row_id}" class="save-row">Save</button>
            ${
              row.resolved_mtp_sku
                ? `<button type="button" data-mtp-sku="${escapeHtml(row.resolved_mtp_sku)}" data-carrier="${escapeHtml(
                    row.best_carrier || ""
                  )}" class="apply-same">Apply Same SKU</button>`
                : ""
            }
          </td>
        </tr>
      `;
    })
    .join("");

  rowsBody.querySelectorAll(".save-row").forEach((button) => button.addEventListener("click", onSaveRow));
  rowsBody.querySelectorAll(".apply-same").forEach((button) => button.addEventListener("click", onApplySameSku));
}

async function onSaveRow(event) {
  const rowId = Number(event.currentTarget.dataset.rowId);
  const weightInput = rowsBody.querySelector(`input[data-row-id="${rowId}"][data-field="weight"]`);
  const carrierSelect = rowsBody.querySelector(`select[data-row-id="${rowId}"][data-field="carrier"]`);
  const payload = {
    weight_kg: weightInput.value ? Number(weightInput.value) : null,
    carrier: carrierSelect && !carrierSelect.disabled ? carrierSelect.value : null,
  };

  if (state.jobMode === "client") {
    const currentRow = state.clientRows.find((row) => row.row_id === rowId);
    if (!currentRow) {
      return;
    }

    const updated = await request("/api/rows/recalculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ row: currentRow, ...payload }),
    });
    replaceClientRow(updated);
    await Promise.all([loadCurrentPage(), refreshSummary()]);
    return;
  }

  await request(`/api/jobs/${state.jobId}/rows/${rowId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await Promise.all([loadCurrentPage(), refreshSummary()]);
}

async function onApplySameSku(event) {
  const mtpSku = event.currentTarget.dataset.mtpSku;
  const carrier = event.currentTarget.dataset.carrier;
  if (!mtpSku || !carrier) {
    return;
  }
  document.getElementById("bulkMtpSku").value = mtpSku;
  document.getElementById("bulkCarrier").value = carrier;
  await applyBulkCarrier(mtpSku, carrier);
}

async function onBulkCarrierSubmit(event) {
  event.preventDefault();
  const mtpSku = document.getElementById("bulkMtpSku").value.trim();
  const carrier = document.getElementById("bulkCarrier").value;
  await applyBulkCarrier(mtpSku, carrier);
}

async function applyBulkCarrier(mtpSku, carrier) {
  if (!mtpSku || !carrier) {
    return;
  }

  if (state.jobMode === "client") {
    let updatedRows = 0;
    state.clientRows = state.clientRows.map((row) => {
      if (row.resolved_mtp_sku !== mtpSku) {
        return row;
      }
      updatedRows += 1;
      return applyCarrierSelection({ ...row }, carrier);
    });
    if (updatedRows) {
      await Promise.all([loadCurrentPage(), refreshSummary()]);
    }
    return;
  }

  if (!state.jobId) {
    return;
  }

  await request(`/api/jobs/${state.jobId}/bulk-carrier`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mtp_sku: mtpSku, carrier }),
  });
  await Promise.all([loadCurrentPage(), refreshSummary()]);
}

async function onDownload() {
  if (state.jobStatus !== "completed") {
    return;
  }

  if (state.jobMode === "client") {
    await downloadClientExport();
    return;
  }

  if (!state.jobId) {
    return;
  }

  window.location.href = `/api/jobs/${state.jobId}/export?export_format=${exportFormat.value}`;
}

async function changePage(direction) {
  if (state.jobStatus !== "completed") {
    return;
  }
  const nextPage = state.page + direction;
  if (nextPage < 1 || nextPage > state.totalPages) {
    return;
  }
  state.page = nextPage;
  await loadCurrentPage();
}

async function onSettingsSubmit(event) {
  event.preventDefault();
  const formData = new FormData(settingsForm);
  const payload = {
    default_export_format: formData.get("default_export_format"),
    preview_page_size: Number(formData.get("preview_page_size")),
    sku_cleanup_suffixes: String(formData.get("sku_cleanup_suffixes"))
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean),
  };
  await request("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await loadSettings();
}

async function onAssetUpload(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const fileInput = form.querySelector(".asset-input");
  if (!fileInput.files.length) {
    return;
  }
  const formData = new FormData();
  formData.append("asset_type", form.dataset.assetType);
  formData.append("file", fileInput.files[0]);
  await request("/api/settings/assets", { method: "POST", body: formData });
  fileInput.value = "";
  await Promise.all([loadHealth(), loadSettings()]);
}

async function pollJobUntilReady() {
  while (state.jobId && state.jobStatus === "processing") {
    await delay(1200);
    const data = await request(`/api/jobs/${state.jobId}`);
    state.jobStatus = data.status;
    state.jobSummary = data.summary;
    setJobStatus(data.status, data.summary, data.error);
    renderSummary(reviewSummary, data.summary);
    renderSummary(batchSummary, data.summary);

    if (data.status === "completed") {
      state.page = 1;
      await loadCurrentPage();
      return;
    }

    if (data.status === "failed") {
      rowsBody.innerHTML = "";
      pageMeta.textContent = data.error || "Batch failed.";
      return;
    }
  }
}

function setJobStatus(status, summary = null, error = "") {
  state.jobStatus = status;
  const rows = summary ? summary.total_rows : 0;
  const isCompleted = status === "completed";

  downloadBtn.disabled = !isCompleted;
  refreshRowsBtn.disabled = !isCompleted;
  prevPageBtn.disabled = !isCompleted;
  nextPageBtn.disabled = !isCompleted;

  if (status === "processing") {
    jobBadge.textContent = "Batch processing in background";
    pageMeta.textContent = "Processing batch...";
    return;
  }

  if (status === "failed") {
    jobBadge.textContent = "Batch failed";
    pageMeta.textContent = error || "Batch failed.";
    return;
  }

  if (status !== "completed") {
    jobBadge.textContent = "No active batch";
    pageMeta.textContent = "Page 0 / 0";
    return;
  }

  jobBadge.textContent = `Active batch - ${rows} rows`;
}

function renderSummary(target, summary) {
  target.innerHTML = [
    summaryCard("Rows", summary.total_rows),
    summaryCard("Success", summary.successful_rows),
    summaryCard("Exceptions", summary.exception_rows),
    summaryCard("Duplicates Skipped", summary.duplicate_rows_skipped),
  ].join("");
}

function summaryCard(label, value) {
  return `<div class="summary-card"><span class="label">${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></div>`;
}

function card(label, value) {
  return `<div class="card"><span class="label">${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></div>`;
}

function getClientPage() {
  const totalRows = state.clientRows.length;
  const totalPages = Math.max(Math.ceil(totalRows / state.pageSize), 1);
  const start = Math.max(state.page - 1, 0) * state.pageSize;
  const end = start + state.pageSize;
  return {
    rows: state.clientRows.slice(start, end),
    page: state.page,
    totalPages,
  };
}

function calculateClientSummary() {
  const baseSummary = state.jobSummary || {
    total_files: 0,
    duplicate_rows_skipped: 0,
    files: [],
  };
  return {
    total_files: baseSummary.total_files || 0,
    total_rows: state.clientRows.length,
    duplicate_rows_skipped: baseSummary.duplicate_rows_skipped || 0,
    exception_rows: state.clientRows.filter((row) => row.exception_reason).length,
    successful_rows: state.clientRows.filter((row) => !row.exception_reason).length,
    files: baseSummary.files || [],
  };
}

function replaceClientRow(updatedRow) {
  state.clientRows = state.clientRows.map((row) => (row.row_id === updatedRow.row_id ? updatedRow : row));
}

function applyCarrierSelection(row, carrier) {
  const rates = row.carrier_prices || {};
  const availableCarriers = Object.entries(rates).filter(([, value]) => value !== null);
  if (!availableCarriers.length) {
    row.selected_carrier = "";
    row.best_carrier = "";
    row.best_rate = null;
    row.zone = "";
    return row;
  }

  let selectedCarrier = carrier;
  if (!selectedCarrier || rates[selectedCarrier] === null || rates[selectedCarrier] === undefined) {
    selectedCarrier = availableCarriers.reduce((best, [name, value]) => {
      if (best === null) {
        return name;
      }
      return value < rates[best] ? name : best;
    }, null);
  }

  row.selected_carrier = selectedCarrier;
  row.best_carrier = selectedCarrier;
  row.best_rate = rates[selectedCarrier];
  row.zone = selectedZoneForCarrier(selectedCarrier, row.zones || {});
  return row;
}

function selectedZoneForCarrier(carrier, zones) {
  if (carrier === "Affinity") {
    return zones.affinity_zone || "";
  }
  if (carrier === "Bluedart") {
    return zones.bluedart_zone || "";
  }
  return zones.delhivery_zone || "";
}

async function downloadClientExport() {
  const response = await fetch("/api/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      rows: state.clientRows,
      export_format: exportFormat.value,
    }),
  });

  if (!response.ok) {
    let detail = "Request failed";
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch (error) {
      detail = response.statusText || detail;
    }
    alert(detail);
    throw new Error(detail);
  }

  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const fileNameMatch = disposition.match(/filename="([^"]+)"/);
  const fileName = fileNameMatch ? fileNameMatch[1] : `shipping-allocation.${exportFormat.value}`;
  downloadBlob(blob, fileName);
}

function downloadBlob(blob, fileName) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

function delay(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = "Request failed";
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch (error) {
      detail = response.statusText || detail;
    }
    alert(detail);
    throw new Error(detail);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
