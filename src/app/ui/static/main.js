/**
 * ORBIT Global Scripts
 */

window.__orbitMainLoaded = true;
if (!window.__orbitPageShowFixAdded) {
  window.__orbitPageShowFixAdded = true;
  window.addEventListener("pageshow", () => {
    document.body.classList.remove("page-transition-loading");
    document.body.classList.add("page-loaded");
    document.body.classList.remove("overflow-hidden");
    ["help-modal", "delete-modal", "run-prompt-modal"].forEach((id) => {
      const modal = document.getElementById(id);
      if (!modal) return;
      modal.classList.add("hidden");
      modal.classList.remove("flex");
    });
    const loader = document.getElementById("global-loader");
    if (loader) {
      loader.classList.add("hidden");
      loader.classList.remove("flex");
    }
  });
}

const initApp = () => {
  initPageLoad();
  initHtmxEvents();
  initToastAutoScroll();
  initGlobalEventListeners();
  initHelpModal();
  initRunDetailsToggle();
  initFolderGroupToggle();
  initDeleteModal();
  initRunPromptModal();
  initImportWorkflow();
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}

/**
 * Page Load Animation
 */
function initPageLoad() {
  document.body.classList.add("page-loaded");

  // Mark Alpine.js elements as loaded
  document.querySelectorAll("[x-data]:not([x-cloak])").forEach((el) => {
    el.classList.add("x-loaded");
  });

  // Smooth transition for navigation links
  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href]:not([target='_blank']):not([download])");
    if (!link || link.getAttribute("href").startsWith("#")) return;

    const url = new URL(link.href);
    if (url.origin !== window.location.origin) return;

    event.preventDefault();
    document.body.classList.add("page-transition-loading");

    setTimeout(() => {
      window.location.href = link.href;
    }, 150);
  });
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

  // Smooth page transitions for htmx navigation
  document.body.addEventListener("htmx:beforeSwap", (evt) => {
    document.body.classList.remove("page-loaded");
  });

  document.body.addEventListener("htmx:afterSwap", () => {
    setTimeout(() => {
      document.body.classList.add("page-loaded");
    }, 50);

    // Mark Alpine.js elements as loaded (for HTMX-inserted content)
    document.querySelectorAll("[x-data]:not([x-cloak])").forEach((el) => {
      el.classList.add("x-loaded");
    });
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
 * Run Prompt Modal
 */
let pendingRunWorkflow = null;
let pendingRunButton = null;

function showRunPromptModal(name) {
  const modal = document.getElementById("run-prompt-modal");
  if (!modal) return;

  pendingRunWorkflow = name;
  pendingRunButton = document.querySelector(
    `[data-workflow-run="${escapeSelector(name)}"]`,
  );

  const promptInput = modal.querySelector("#run-prompt-input");
  if (promptInput) {
    promptInput.value = "";
    promptInput.focus();
  }

  modal.classList.remove("hidden");
  modal.classList.add("flex");
  document.body.classList.add("overflow-hidden");
}

function hideRunPromptModal(modal) {
  if (!modal) return;
  modal.classList.add("hidden");
  modal.classList.remove("flex");
  document.body.classList.remove("overflow-hidden");
}

async function submitRunPrompt({ prompt, skipPrompt }) {
  if (!pendingRunWorkflow) return;

  const modal = document.getElementById("run-prompt-modal");
  const hasModal = !!modal;

  if (hasModal) {
    hideRunPromptModal(modal);
  }

  const submitButton = hasModal
    ? modal.querySelector("[data-run-prompt-submit]")
    : null;
  const skipButton = hasModal
    ? modal.querySelector("[data-run-prompt-skip]")
    : null;
  const buttons = [submitButton, skipButton].filter(Boolean);

  buttons.forEach((btn) => {
    btn.disabled = true;
  });

  if (pendingRunButton) {
    pendingRunButton.disabled = true;
    pendingRunButton.classList.add("htmx-request");
  }

  if (pendingRunWorkflow) {
    updateDashboardBadge(pendingRunWorkflow, "running");
    const stopButton = getStopButton(pendingRunWorkflow);
    if (stopButton) {
      stopButton.classList.remove("hidden");
      stopButton.disabled = false;
      stopButton.textContent = "Stop";
    }
  }

  try {
    const payload = skipPrompt ? {} : { prompt: prompt || "" };
    const response = await fetch(
      `/api/workflows/${encodeURIComponent(pendingRunWorkflow)}/run`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );

    const html = await response.text();
    if (!response.ok) {
      throw new Error("実行に失敗しました");
    }

    const toastContainer = document.getElementById("toast-container");
    if (toastContainer) {
      const fragment = document
        .createRange()
        .createContextualFragment(html);
      toastContainer.appendChild(fragment);
    }
  } catch (error) {
    window.alert(error.message || "実行に失敗しました");
  } finally {
    buttons.forEach((btn) => {
      btn.disabled = false;
    });
    if (pendingRunButton) {
      pendingRunButton.disabled = false;
      pendingRunButton.classList.remove("htmx-request");
    }
    if (pendingRunWorkflow) {
      const stopButton = getStopButton(pendingRunWorkflow);
      if (stopButton) {
        stopButton.classList.add("hidden");
        stopButton.disabled = false;
        stopButton.textContent = "Stop";
      }
    }
    pendingRunWorkflow = null;
    pendingRunButton = null;
  }
}

function initRunPromptModal() {
  const modal = document.getElementById("run-prompt-modal");
  if (!modal) return;

  const overlay = modal.querySelector("[data-run-prompt-overlay]");
  const closeButtons = modal.querySelectorAll("[data-run-prompt-close]");
  const skipButton = modal.querySelector("[data-run-prompt-skip]");
  const submitButton = modal.querySelector("[data-run-prompt-submit]");
  const promptInput = modal.querySelector("#run-prompt-input");

  const closeModal = () => {
    hideRunPromptModal(modal);
    pendingRunWorkflow = null;
    pendingRunButton = null;
  };

  overlay?.addEventListener("click", closeModal);
  closeButtons.forEach((btn) => btn.addEventListener("click", closeModal));

  skipButton?.addEventListener("click", () => {
    submitRunPrompt({ prompt: "", skipPrompt: true });
  });

  submitButton?.addEventListener("click", () => {
    const prompt = (promptInput?.value || "").trim();
    submitRunPrompt({ prompt, skipPrompt: false });
  });

  promptInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      const prompt = (promptInput?.value || "").trim();
      submitRunPrompt({ prompt, skipPrompt: false });
    }
  });

  document.addEventListener("click", (event) => {
    const target =
      event.target instanceof Element
        ? event.target.closest("[data-workflow-run]")
        : null;
    if (!target) return;

    event.preventDefault();
    const name = target.getAttribute("data-workflow-run");
    if (!name) return;

    const promptEnabled =
      target.getAttribute("data-run-prompt-enabled") === "true";

    if (promptEnabled) {
      showRunPromptModal(name);
      return;
    }

    pendingRunWorkflow = name;
    pendingRunButton = target;
    submitRunPrompt({ prompt: "", skipPrompt: true });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("hidden")) {
      closeModal();
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
    event.stopPropagation();
    event.stopImmediatePropagation();

    const runId = target.getAttribute("data-run-details-toggle");
    if (!runId) return;

    const detailsRow = document.getElementById(`details-${runId}`);
    if (!detailsRow) return;

    const computedStyle = window.getComputedStyle(detailsRow);
    const isHidden = computedStyle.display === "none";

    if (isHidden) {
      detailsRow.style.display = "block";
      detailsRow.classList.remove("hidden");
    } else {
      detailsRow.style.display = "none";
      detailsRow.classList.add("hidden");
    }

    target.setAttribute("aria-expanded", isHidden ? "true" : "false");
  });
}

function initFolderGroupToggle() {
  const STORAGE_PREFIX = "orbit.dashboard.folder:";
  const getStorageKey = (target, panelId) => {
    const rawKey = target.getAttribute("data-folder-key") || panelId || "";
    return `${STORAGE_PREFIX}${rawKey}`;
  };
  const setExpandedState = (target, panel, expanded) => {
    panel.classList.toggle("hidden", !expanded);
    target.setAttribute("aria-expanded", expanded ? "true" : "false");
    const icon = target.querySelector("[data-folder-toggle-icon]");
    if (icon) {
      icon.classList.toggle("rotate-180", expanded);
    }
  };

  document.querySelectorAll("[data-folder-toggle]").forEach((target) => {
    const panelId = target.getAttribute("data-folder-toggle");
    if (!panelId) return;
    const panel = document.getElementById(panelId);
    if (!panel) return;

    const stored = localStorage.getItem(getStorageKey(target, panelId));
    if (stored === "collapsed") {
      setExpandedState(target, panel, false);
    } else {
      setExpandedState(target, panel, true);
    }
  });

  document.addEventListener("click", (event) => {
    const target =
      event.target instanceof Element
        ? event.target.closest("[data-folder-toggle]")
        : null;
    if (!target) return;

    event.preventDefault();

    const panelId = target.getAttribute("data-folder-toggle");
    if (!panelId) return;

    const panel = document.getElementById(panelId);
    if (!panel) return;

    const isHidden = panel.classList.contains("hidden");
    const nextExpanded = isHidden;
    setExpandedState(target, panel, nextExpanded);
    localStorage.setItem(
      getStorageKey(target, panelId),
      nextExpanded ? "expanded" : "collapsed",
    );
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
