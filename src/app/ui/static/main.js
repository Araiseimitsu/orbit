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
    const target = evt.target;
    if (target.matches('button[hx-post*="/run"]')) {
      const loader = document.getElementById("global-loader");
      if (loader) {
        loader.classList.remove("hidden");
        loader.classList.add("flex");
      }
      target.disabled = true;
    }
  });

  document.body.addEventListener("htmx:afterRequest", (evt) => {
    const loader = document.getElementById("global-loader");
    if (loader) {
      loader.classList.add("hidden");
      loader.classList.remove("flex");
    }
    const buttons = document.querySelectorAll('button[hx-post*="/run"]');
    buttons.forEach((btn) => (btn.disabled = false));
  });
}

/**
 * Toast Management
 */
const BADGE_CLASSES = ["badge-success", "badge-error", "badge-neutral"];

function escapeSelector(value) {
  if (window.CSS && CSS.escape) return CSS.escape(value);
  return String(value).replace(/["\\]/g, "\\$&");
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
  document.addEventListener("click", async (event) => {
    const target =
      event.target instanceof Element
        ? event.target.closest("[data-delete-workflow]")
        : null;
    if (!target) return;

    event.preventDefault();
    const name = target.getAttribute("data-delete-workflow");
    if (!name) return;

    const confirmed = window.confirm(
      `「${name}」を削除しますか？この操作は取り消せません。`,
    );
    if (!confirmed) return;

    try {
      const response = await fetch(
        `/api/workflows/${encodeURIComponent(name)}/delete`,
        { method: "POST" },
      );
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail || "削除に失敗しました");
      }
      if (window.location.pathname.startsWith(`/workflows/${name}`)) {
        window.location.href = "/";
      } else {
        window.location.reload();
      }
    } catch (error) {
      window.alert(error.message || "削除に失敗しました");
    }
  });

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
