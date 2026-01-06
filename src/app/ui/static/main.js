/**
 * ORBIT Global Scripts
 */

window.__orbitMainLoaded = true;

const initApp = () => {
  initHtmxEvents();
  initToastAutoScroll();
  initGlobalEventListeners();
  initHelpModal();
  initRunDetailsToggle();
  initDeleteModal();
  initImportWorkflow();
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}

/**
 * HTMX Event Handlers
 */
function initHtmxEvents() {
  // Show global loader on specific htmx requests
  document.body.addEventListener("htmx:beforeRequest", (evt) => {
    const target = evt.detail?.elt || evt.target;
    if (target instanceof Element && target.matches('button[data-workflow-run]')) {
      target.disabled = true;

      const workflowName = target.getAttribute("data-workflow-run");
      if (workflowName) {
        updateDashboardBadge(workflowName, "running");
        const stopButton = getStopButton(workflowName);
        if (stopButton) {
          stopButton.classList.remove("hidden");
          stopButton.disabled = false;
          stopButton.textContent = "Stop";
        }
      }
    }
  });

  document.body.addEventListener("htmx:afterRequest", (evt) => {
    const target = evt.detail?.elt || evt.target;
    if (!(target instanceof Element) || !target.matches('button[data-workflow-run]')) {
      return;
    }

    target.disabled = false;

    const workflowName = target.getAttribute("data-workflow-run");
    if (workflowName) {
      const stopButton = getStopButton(workflowName);
      if (stopButton) {
        stopButton.classList.add("hidden");
        stopButton.disabled = false;
        stopButton.textContent = "Stop";
      }
    }
  });
}

/**
 * Toast Management
 */
const BADGE_CLASSES = [
  "badge-success",
  "badge-error",
  "badge-neutral",
  "badge-pending",
];

function escapeSelector(value) {
  if (window.CSS && CSS.escape) return CSS.escape(value);
  return String(value).replace(/["\\]/g, "\\$&");
}

function getStopButton(workflowName) {
  if (!workflowName) return null;
  const selector = `[data-workflow-stop="${escapeSelector(workflowName)}"]`;
  return document.querySelector(selector);
}

function updateDashboardBadge(workflowName, runStatus) {
  if (!workflowName || !runStatus) return;
  const selector = `[data-workflow-status="${escapeSelector(workflowName)}"]`;
  const badge = document.querySelector(selector);
  if (!badge) return;

  const statusMap = {
    success: { label: "成功", className: "badge-success" },
    failed: { label: "失敗", className: "badge-error" },
    running: { label: "実行中", className: "badge-neutral" },
    stopped: { label: "停止", className: "badge-pending" },
  };
  const next = statusMap[runStatus] || {
    label: runStatus,
    className: "badge-neutral",
  };

  badge.textContent = next.label;
  BADGE_CLASSES.forEach((name) => badge.classList.remove(name));
  badge.classList.add(next.className);
}

function registerToast(toast) {
  if (!toast || toast.dataset.toastInitialized === "true") return;
  toast.dataset.toastInitialized = "true";

  const duration = Number.parseInt(toast.dataset.toastDuration || "5000", 10);
  const workflowName = toast.dataset.workflowName;
  const runStatus = toast.dataset.runStatus;

  updateDashboardBadge(workflowName, runStatus);

  if (Number.isFinite(duration) && duration > 0) {
    setTimeout(() => {
      toast.style.transform = "translateX(100%)";
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }
}

function initToastAutoScroll() {
  const toastContainer = document.getElementById("toast-container");
  if (toastContainer) {
    toastContainer.querySelectorAll(".toast-item").forEach(registerToast);
    const observer = new MutationObserver((mutations) => {
      toastContainer.scrollTop = toastContainer.scrollHeight;
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (!(node instanceof Element)) return;
          if (node.matches(".toast-item")) {
            registerToast(node);
            return;
          }
          node.querySelectorAll(".toast-item").forEach(registerToast);
        });
      });
    });
    observer.observe(toastContainer, { childList: true, subtree: true });
  }
}

/**
 * Global Interactivity
 */
function initGlobalEventListeners() {
  // Toast close handler
  document.addEventListener("click", (event) => {
    const target =
      event.target instanceof Element
        ? event.target.closest("[data-toast-close]")
        : null;
    if (!target) return;

    event.preventDefault();
    const toast = target.closest(".toast-item");
    if (toast) {
      toast.remove();
    }
  });

  // Delete workflow handler (モーダルを表示)
  document.addEventListener("click", (event) => {
    const target =
      event.target instanceof Element
        ? event.target.closest("[data-delete-workflow]")
        : null;
    if (!target) return;

    event.preventDefault();
    const name = target.getAttribute("data-delete-workflow");
    const cron = target.getAttribute("data-cron") || null;
    if (!name) return;

    showDeleteModal(name, cron);
  });

  // Toggle workflow handler
  document.addEventListener("click", async (event) => {
    const target =
      event.target instanceof Element
        ? event.target.closest("[data-toggle-workflow]")
        : null;
    if (!target) return;

    event.preventDefault();
    const name = target.getAttribute("data-toggle-workflow");
    const current = target.getAttribute("data-enabled") === "true";
    if (!name) return;

    const label = !current ? "有効化" : "停止";
    const confirmed = window.confirm(`「${name}」を${label}しますか？`);
    if (!confirmed) return;

    try {
      const response = await fetch(
        `/api/workflows/${encodeURIComponent(name)}/toggle`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: !current }),
        },
      );
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail || "更新に失敗しました");
      }
      window.location.reload();
    } catch (error) {
      window.alert(error.message || "更新に失敗しました");
    }
  });

  // Stop workflow handler
  document.addEventListener("click", async (event) => {
    const target =
      event.target instanceof Element
        ? event.target.closest("[data-workflow-stop]")
        : null;
    if (!target) return;

    event.preventDefault();
    const name = target.getAttribute("data-workflow-stop");
    if (!name) return;

    const originalLabel = target.textContent || "Stop";
    target.disabled = true;
    target.textContent = "Stopping...";

    try {
      const response = await fetch(
        `/api/workflows/${encodeURIComponent(name)}/stop`,
        { method: "POST" },
      );
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || "停止に失敗しました");
      }
    } catch (error) {
      window.alert(error.message || "停止に失敗しました");
      target.disabled = false;
      target.textContent = originalLabel;
    }
  });
}

/**
 * Delete Modal Management
 */
let pendingDeleteWorkflow = null;

function showDeleteModal(name, cron = null) {
  const modal = document.getElementById("delete-modal");
  if (!modal) return;

  pendingDeleteWorkflow = name;

  document.getElementById("delete-modal-workflow-name").textContent = name;

  const scheduleInfo = document.getElementById("delete-modal-schedule-info");
  const cronEl = document.getElementById("delete-modal-cron");
  if (cron) {
    cronEl.textContent = cron;
    scheduleInfo.classList.remove("hidden");
  } else {
    scheduleInfo.classList.add("hidden");
  }

  modal.classList.remove("hidden");
  modal.classList.add("flex");
  document.body.classList.add("overflow-hidden");
}

function initDeleteModal() {
  const modal = document.getElementById("delete-modal");
  if (!modal) return;

  const overlay = modal.querySelector("[data-delete-overlay]");
  const cancelBtn = modal.querySelector("[data-delete-cancel]");
  const confirmBtn = modal.querySelector("[data-delete-confirm]");

  const closeModal = () => {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
    document.body.classList.remove("overflow-hidden");
    pendingDeleteWorkflow = null;
  };

  overlay?.addEventListener("click", closeModal);
  cancelBtn?.addEventListener("click", closeModal);

  confirmBtn?.addEventListener("click", async () => {
    if (!pendingDeleteWorkflow) return;

    confirmBtn.disabled = true;
    confirmBtn.textContent = "削除中...";

    try {
      const response = await fetch(
        `/api/workflows/${encodeURIComponent(pendingDeleteWorkflow)}/delete`,
        { method: "POST" },
      );
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail || "削除に失敗しました");
      }

      closeModal();

      if (
        window.location.pathname.startsWith(
          `/workflows/${pendingDeleteWorkflow}`,
        )
      ) {
        window.location.href = "/";
      } else {
        window.location.reload();
      }
    } catch (error) {
      window.alert(error.message || "削除に失敗しました");
      confirmBtn.disabled = false;
      confirmBtn.textContent = "削除する";
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("hidden")) {
      closeModal();
    }
  });
}

/**
 * Help Modal
 */
function initHelpModal() {
  const modal = document.getElementById("help-modal");
  if (!modal) return;

  const openButtons = document.querySelectorAll("[data-help-open]");
  const closeButtons = modal.querySelectorAll("[data-help-close]");
  const overlay = modal.querySelector("[data-help-overlay]");

  const openModal = () => {
    modal.classList.remove("hidden");
    modal.classList.add("flex");
    document.body.classList.add("overflow-hidden");
    openButtons.forEach((btn) => btn.setAttribute("aria-expanded", "true"));
  };

  const closeModal = () => {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
    document.body.classList.remove("overflow-hidden");
    openButtons.forEach((btn) => btn.setAttribute("aria-expanded", "false"));
  };

  openButtons.forEach((btn) => btn.addEventListener("click", openModal));
  closeButtons.forEach((btn) => btn.addEventListener("click", closeModal));
  if (overlay) {
    overlay.addEventListener("click", closeModal);
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("hidden")) {
      closeModal();
    }
  });
}

function initRunDetailsToggle() {
  document.addEventListener("click", (event) => {
    const target =
      event.target instanceof Element
        ? event.target.closest("[data-run-details-toggle]")
        : null;
    if (!target) return;

    event.preventDefault();
    const runId = target.getAttribute("data-run-details-toggle");
    if (!runId) return;

    const detailsRow = document.getElementById(`details-${runId}`);
    if (!detailsRow) return;

    const isHidden = detailsRow.classList.contains("hidden");
    if (isHidden) {
      detailsRow.classList.remove("hidden");
      detailsRow.classList.add(
        "animate-in",
        "fade-in",
        "slide-in-from-top-2",
        "duration-300",
      );
    } else {
      detailsRow.classList.add("hidden");
    }

    target.setAttribute("aria-expanded", isHidden ? "true" : "false");
  });
}

function initImportWorkflow() {
  const input = document.querySelector("[data-import-input]");
  const triggerButtons = document.querySelectorAll("[data-import-trigger]");
  if (!input || triggerButtons.length === 0) return;

  triggerButtons.forEach((button) => {
    button.addEventListener("click", () => input.click());
  });

  input.addEventListener("change", () => importWorkflow(input));
}

/**
 * Workflow Import
 */
async function importWorkflow(input) {
  const file = input.files?.[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("/api/workflows/import", {
      method: "POST",
      body: formData,
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "インポートに失敗しました");
    }

    window.alert(`ワークフロー「${result.name}」をインポートしました`);
    window.location.reload();
  } catch (error) {
    window.alert(error.message || "インポートに失敗しました");
  } finally {
    input.value = "";
  }
}
