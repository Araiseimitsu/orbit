(() => {
  const configEl = document.getElementById("flow-editor-config");
  if (!configEl) {
    return;
  }

  const config = JSON.parse(configEl.textContent || "{}");
  const state = {
    workflow: config.workflow || {
      name: "",
      description: "",
      trigger: { type: "manual" },
      steps: [],
    },
    actions: config.actions || [],
    metadata: {},
    ACTION_GUIDES: {},
    selectedId: null,
  };

  const buildActionGuides = (metadata) => {
    const guides = {};
    for (const [type, meta] of Object.entries(metadata)) {
      guides[type] = {
        title: meta.title,
        description: meta.description,
        params: (meta.params || []).map((p) => ({
          key: p.key,
          desc: p.description,
          example: p.example,
        })),
        outputs: (meta.outputs || []).map((o) => ({
          key: o.key,
          desc: o.description,
        })),
      };
    }
    return guides;
  };

  const nameInput = document.getElementById("workflow-name");
  const triggerSelect = document.getElementById("trigger-type");
  const cronField = document.getElementById("cron-field");
  const cronInput = document.getElementById("trigger-cron");
  const cronPreset = document.getElementById("cron-preset");
  const cronPreview = document.getElementById("cron-preview");
  const cronError = document.getElementById("cron-error");
  const statusEl = document.getElementById("editor-status");
  const enabledInput = document.getElementById("workflow-enabled");
  const saveButton = document.getElementById("save-workflow");
  const actionListEl = document.getElementById("action-list");
  const canvasEl = document.getElementById("flow-canvas");
  const inspectorEl = document.getElementById("inspector");
  const aiPromptInput = document.getElementById("ai-flow-prompt");
  const aiModeSelect = document.getElementById("ai-flow-mode");
  const aiSearchToggle = document.getElementById("ai-flow-search");
  const aiGenerateButton = document.getElementById("ai-flow-generate");
  const aiClearButton = document.getElementById("ai-flow-clear");
  const aiStatusEl = document.getElementById("ai-flow-status");

  const REQUIRED_PARAMS = {
    ai_generate: ["prompt"],
  };

  const DEFAULT_PARAMS = {
    ai_generate: { prompt: "" },
  };

  const buildActionGroups = (actions) => {
    const categoryMap = new Map();

    actions.forEach((action) => {
      const meta = state.metadata[action];
      const category = meta?.category || "その他";
      if (!categoryMap.has(category)) {
        categoryMap.set(category, []);
      }
      categoryMap.get(category).push(action);
    });

    const groups = [];
    categoryMap.forEach((actionList, category) => {
      groups.push({ label: category, actions: actionList });
    });

    return groups;
  };

  const getDefaultParams = (type) => ({ ...(DEFAULT_PARAMS[type] || {}) });

  const setStatus = (message, isError = false) => {
    if (!statusEl) {
      return;
    }
    statusEl.textContent = message;
    statusEl.style.color = isError ? "#b91c1c" : "#475569";
  };

  const setAiStatus = (message, tone = null) => {
    if (!aiStatusEl) {
      return;
    }
    aiStatusEl.textContent = message || "";
    aiStatusEl.classList.remove("error", "success");
    if (tone === "error") {
      aiStatusEl.classList.add("error");
    } else if (tone === "success") {
      aiStatusEl.classList.add("success");
    }
  };

  const copyToClipboard = async (text) => {
    if (!text) {
      return false;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch (error) {
        // フォールバックへ
      }
    }
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    let copied = false;
    try {
      copied = document.execCommand("copy");
    } catch (error) {
      copied = false;
    }
    textarea.remove();
    return copied;
  };

  const markCopyFeedback = (el, success) => {
    if (!el) {
      return;
    }
    el.classList.remove("copied", "copy-failed");
    el.classList.add(success ? "copied" : "copy-failed");
    if (el.__copyTimer) {
      clearTimeout(el.__copyTimer);
    }
    el.__copyTimer = setTimeout(() => {
      el.classList.remove("copied", "copy-failed");
    }, 1200);
  };

  const uniqueId = (base) => {
    const safeBase = (base || "step").replace(/[^a-zA-Z0-9_]+/g, "_");
    let index = 1;
    let candidate = `${safeBase}_${index}`;
    const ids = new Set(state.workflow.steps.map((step) => step.id));
    while (ids.has(candidate)) {
      index += 1;
      candidate = `${safeBase}_${index}`;
    }
    return candidate;
  };

  const sanitizeStepId = (value) => {
    const text = String(value || "step");
    const sanitized = text.replace(/[^a-zA-Z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
    return sanitized || "step";
  };

  const ensureUniqueId = (base, used) => {
    let candidate = sanitizeStepId(base);
    let index = 1;
    while (used.has(candidate)) {
      index += 1;
      candidate = `${sanitizeStepId(base)}_${index}`;
    }
    used.add(candidate);
    return candidate;
  };

  const getSelectedStep = () =>
    state.workflow.steps.find((step) => step.id === state.selectedId);

  const selectStep = (id) => {
    state.selectedId = id;
    renderCanvas();
    renderInspector();
    const firstInput = inspectorEl.querySelector("input");
    if (firstInput) {
      firstInput.focus();
    }
  };

  const addStep = (type) => {
    const stepType = type || state.actions[0] || "log";
    const newStep = {
      id: uniqueId(stepType),
      type: stepType,
      params: getDefaultParams(stepType),
      position: {
        x: 80,
        y: 80 + state.workflow.steps.length * 80,
      },
    };
    state.workflow.steps.push(newStep);
    selectStep(newStep.id);
  };

  const removeStep = (id) => {
    const index = state.workflow.steps.findIndex((step) => step.id === id);
    if (index >= 0) {
      state.workflow.steps.splice(index, 1);
      state.selectedId = null;
      renderCanvas();
      renderInspector();
    }
  };

  const renderActionList = () => {
    actionListEl.innerHTML = "";
    const actions = state.actions.length ? state.actions : ["log"];
    const groups = buildActionGroups(actions);
    groups.forEach((group) => {
      const groupWrap = document.createElement("div");
      groupWrap.className = "action-group";

      const groupTitle = document.createElement("div");
      groupTitle.className = "action-group-title";
      groupTitle.textContent = group.label;
      groupWrap.appendChild(groupTitle);

      const groupItems = document.createElement("div");
      groupItems.className = "action-group-items";

      group.actions.forEach((action) => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "action-item";

        // メタデータから表示名を取得
        const meta = state.metadata[action];
        const displayName = meta?.title || action;
        const description = meta?.description || "";

        item.innerHTML = `
          <div class="action-item-name">${displayName}</div>
          <div class="action-item-desc">${description}</div>
        `;
        item.title = description;

        item.addEventListener("click", () => addStep(action));
        groupItems.appendChild(item);
      });

      groupWrap.appendChild(groupItems);
      actionListEl.appendChild(groupWrap);
    });
  };

  const refreshActions = async () => {
    try {
      const response = await fetch("/api/actions");
      if (response.ok) {
        const data = await response.json();
        if (Array.isArray(data.actions)) {
          state.actions = data.actions;
        }
        // メタデータを保存
        if (data.metadata) {
          state.metadata = data.metadata;
          state.ACTION_GUIDES = buildActionGuides(data.metadata);
        }
      }
    } catch (error) {
      // フェイルセーフ: 失敗しても UI は続行
    }
    renderActionList();
    renderInspector();
  };

  const renderCanvas = () => {
    canvasEl.innerHTML = "";
    const orderMap = new Map(
      [...state.workflow.steps]
        .sort(
          (a, b) => a.position.y - b.position.y || a.position.x - b.position.x,
        )
        .map((step, index) => [step.id, index + 1]),
    );
    state.workflow.steps.forEach((step) => {
      const node = document.createElement("div");
      node.className =
        "flow-node" + (step.id === state.selectedId ? " selected" : "");
      node.dataset.id = step.id;
      node.style.left = `${step.position.x}px`;
      node.style.top = `${step.position.y}px`;
      node.addEventListener("click", (event) => {
        event.stopPropagation();
        selectStep(step.id);
      });

      const orderBadge = document.createElement("div");
      orderBadge.className = "flow-node-order";
      orderBadge.textContent = `#${orderMap.get(step.id) || 0}`;

      const title = document.createElement("div");
      title.className = "flow-node-title";
      title.textContent = step.type;

      const label = document.createElement("div");
      label.className = "flow-node-id";
      label.textContent = step.id;

      node.appendChild(orderBadge);
      node.appendChild(title);
      node.appendChild(label);
      canvasEl.appendChild(node);
    });
  };

  const buildParamRow = (key, value, availableKeys) => {
    const row = document.createElement("div");
    row.className = "param-row";

    const keyWrap = document.createElement("div");
    keyWrap.className = "param-key";

    const keySelect = document.createElement("select");
    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = "入力パラメータを選択";
    keySelect.appendChild(defaultOption);

    (availableKeys || []).forEach((paramKey) => {
      const opt = document.createElement("option");
      opt.value = paramKey;
      opt.textContent = paramKey;
      keySelect.appendChild(opt);
    });

    const customOption = document.createElement("option");
    customOption.value = "__custom__";
    customOption.textContent = "カスタム入力...";
    keySelect.appendChild(customOption);

    const keyInput = document.createElement("input");
    keyInput.type = "text";
    keyInput.value = key || "";
    keyInput.placeholder = "例: prompt";
    keyInput.style.display = "none";
    keyInput.className = "param-key-input";

    const setKeyMode = (selectedValue) => {
      if (
        selectedValue === "__custom__" ||
        (!selectedValue && keyInput.value)
      ) {
        keyInput.style.display = "block";
      } else {
        keyInput.style.display = "none";
        if (selectedValue) {
          keyInput.value = selectedValue;
        }
      }
    };

    if (key && (availableKeys || []).includes(key)) {
      keySelect.value = key;
      setKeyMode(key);
    } else if (key) {
      keySelect.value = "__custom__";
      setKeyMode("__custom__");
    } else {
      keySelect.value = "";
      setKeyMode("");
    }

    keySelect.addEventListener("change", () => {
      setKeyMode(keySelect.value);
    });

    keyWrap.appendChild(keySelect);
    keyWrap.appendChild(keyInput);

    const valueInput = document.createElement("textarea");
    valueInput.value = value || "";
    valueInput.placeholder = "例: {{ step_1.text }}";
    valueInput.className = "param-value";

    const valueWrap = document.createElement("div");
    valueWrap.className = "param-value-wrap";
    valueWrap.appendChild(valueInput);

    const aiButton = document.createElement("button");
    aiButton.type = "button";
    aiButton.className = "ai-expression-button";
    aiButton.textContent = "🤖 AI";
    aiButton.title = "AIで式を構築";
    valueWrap.appendChild(aiButton);

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.textContent = "削除";

    row.appendChild(keyWrap);
    row.appendChild(valueWrap);
    row.appendChild(removeButton);

    return { row, keyInput, keySelect, valueInput, removeButton, aiButton };
  };

  const openExpressionBuilder = (targetInput, step) => {
    const paramRow = targetInput.closest(".param-row");
    const keyInput = paramRow.querySelector(".param-key input");
    const keySelect = paramRow.querySelector(".param-key select");
    const paramKey = keyInput?.value || keySelect?.value || "";

    const modal = document.createElement("div");
    modal.className = "expression-builder-modal";
    modal.innerHTML = `
      <div class="modal-overlay"></div>
      <div class="modal-content">
        <div class="modal-header">
          <h3>AIで式を構築</h3>
          <button class="modal-close">×</button>
        </div>
        <div class="modal-body">
          <div class="expression-context">
            <p><strong>パラメータ:</strong> ${paramKey || "カスタム"}</p>
            <p><strong>ステップタイプ:</strong> ${step.type}</p>
          </div>
          <div class="expression-chat">
            <div class="messages" id="expression-messages"></div>
            <div class="input-area">
              <textarea id="expression-prompt" placeholder="例: 今日の日付の日部分だけ（先頭0なし）を取得したい"></textarea>
              <button id="expression-send">送信</button>
            </div>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    const messagesEl = modal.querySelector("#expression-messages");
    const promptInput = modal.querySelector("#expression-prompt");
    const sendButton = modal.querySelector("#expression-send");
    const closeButton = modal.querySelector(".modal-close");
    const overlay = modal.querySelector(".modal-overlay");

    const closeModal = () => {
      modal.remove();
    };

    closeButton.addEventListener("click", closeModal);
    overlay.addEventListener("click", closeModal);

    const addMessage = (container, type, text) => {
      const msg = document.createElement("div");
      msg.className = `message message-${type}`;
      msg.textContent = text;
      container.appendChild(msg);
      container.scrollTop = container.scrollHeight;
    };

    const sendMessage = async () => {
      const prompt = promptInput.value.trim();
      if (!prompt) return;

      addMessage(messagesEl, "user", prompt);
      promptInput.value = "";
      sendButton.disabled = true;
      sendButton.textContent = "送信中...";

      try {
        const response = await fetch("/api/ai/expression", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt,
            param_key: paramKey,
            step_type: step.type,
            context: {
              available_vars: [
                "run_id",
                "now",
                "today",
                "yesterday",
                "tomorrow",
                "today_ymd",
                "now_ymd_hms",
                "workflow",
                "base_dir",
              ],
              step_outputs: Object.keys(step.params || {}),
            },
          }),
        });

        if (!response.ok) {
          throw new Error("API エラー");
        }

        const data = await response.json();
        const expression = data.expression || "";

        if (expression) {
          addMessage(messagesEl, "assistant", `生成された式: ${expression}`);

          const applyButton = document.createElement("button");
          applyButton.textContent = "この式を適用";
          applyButton.className = "apply-expression-button";
          applyButton.addEventListener("click", () => {
            targetInput.value = expression;
            targetInput.dispatchEvent(new Event("input"));
            closeModal();
          });
          messagesEl.appendChild(applyButton);
        } else {
          addMessage(messagesEl, "error", "式を生成できませんでした");
        }
      } catch (error) {
        console.error("Expression generation error:", error);
        addMessage(messagesEl, "error", "エラーが発生しました");
      } finally {
        sendButton.disabled = false;
        sendButton.textContent = "送信";
      }
    };

    sendButton.addEventListener("click", sendMessage);
    promptInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        sendMessage();
      }
    });
  };

  const renderInspector = () => {
    inspectorEl.innerHTML = "";
    const step = getSelectedStep();
    if (!step) {
      const hint = document.createElement("div");
      hint.textContent = "ノードを選択してください。";
      hint.style.color = "#64748b";
      inspectorEl.appendChild(hint);
      return;
    }

    const orderedSteps = [...state.workflow.steps].sort(
      (a, b) => a.position.y - b.position.y || a.position.x - b.position.x,
    );
    const orderIndex = orderedSteps.findIndex((item) => item.id === step.id);

    const orderRow = document.createElement("div");
    orderRow.className = "inspector-row";
    const orderLabel = document.createElement("label");
    orderLabel.textContent = "実行順";
    const orderValue = document.createElement("div");
    orderValue.className = "inspector-order";
    orderValue.textContent =
      orderIndex >= 0 ? `${orderIndex + 1} / ${orderedSteps.length}` : "-";
    orderRow.appendChild(orderLabel);
    orderRow.appendChild(orderValue);

    const idRow = document.createElement("div");
    idRow.className = "inspector-row";
    const idLabel = document.createElement("label");
    idLabel.textContent = "ID";
    const idInput = document.createElement("input");
    idInput.type = "text";
    idInput.value = step.id;
    idRow.appendChild(idLabel);
    idRow.appendChild(idInput);

    const typeRow = document.createElement("div");
    typeRow.className = "inspector-row";
    const typeLabel = document.createElement("label");
    typeLabel.textContent = "タイプ";
    const typeSelect = document.createElement("select");
    const actions = state.actions.length ? state.actions : ["log"];
    actions.forEach((action) => {
      const opt = document.createElement("option");
      opt.value = action;
      opt.textContent = action;
      if (action === step.type) {
        opt.selected = true;
      }
      typeSelect.appendChild(opt);
    });
    typeRow.appendChild(typeLabel);
    typeRow.appendChild(typeSelect);

    const buildGuide = (stepType, stepId) => {
      const guide = state.ACTION_GUIDES[stepType];
      if (!guide) {
        return null;
      }

      const guideWrap = document.createElement("div");
      guideWrap.className = "inspector-guide";

      const guideTitle = document.createElement("div");
      guideTitle.className = "guide-title";
      guideTitle.textContent = `${guide.title} の設定ガイド`;
      guideWrap.appendChild(guideTitle);

      const guideDesc = document.createElement("div");
      guideDesc.className = "guide-desc";
      guideDesc.textContent = guide.description;
      guideWrap.appendChild(guideDesc);

      const guideHint = document.createElement("div");
      guideHint.className = "guide-hint";
      guideHint.textContent = "例のコードはクリックでコピーできます。";
      guideWrap.appendChild(guideHint);

      const exampleStepId = stepId || "step_id";

      const buildExampleChip = (example) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "guide-example";
        chip.textContent = example;
        chip.title = "クリックでコピー";
        chip.addEventListener("click", async () => {
          const ok = await copyToClipboard(example);
          markCopyFeedback(chip, ok);
        });
        chip.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            chip.click();
          }
        });
        return chip;
      };

      const buildSection = (label, items, withExamples, sectionClass) => {
        if (!items || items.length === 0) {
          return null;
        }
        const section = document.createElement("div");
        section.className = sectionClass
          ? `guide-section ${sectionClass}`
          : "guide-section";

        const sectionLabel = document.createElement("div");
        sectionLabel.className = "guide-label";
        sectionLabel.textContent = label;
        section.appendChild(sectionLabel);

        items.forEach((item) => {
          const line = document.createElement("div");
          line.className = "guide-item";
          const text = document.createElement("span");
          text.className = "guide-text";
          text.textContent = `${item.key}: ${item.desc}`;
          line.appendChild(text);

          if (withExamples && item.example) {
            const exampleLabel = document.createElement("span");
            exampleLabel.className = "guide-example-label";
            exampleLabel.textContent = "例:";
            line.appendChild(exampleLabel);
            line.appendChild(buildExampleChip(item.example));
          }
          section.appendChild(line);
        });

        return section;
      };

      const paramsSection = buildSection(
        "入力パラメータ（このステップに渡す）",
        guide.params,
        true,
        "input",
      );
      if (paramsSection) {
        guideWrap.appendChild(paramsSection);
      }

      const outputs = (guide.outputs || []).map((item) => ({
        ...item,
        example: item.example || `{{ ${exampleStepId}.${item.key} }}`,
      }));
      const outputsSection = buildSection(
        "出力の参照例（次のステップで使う）",
        outputs,
        true,
        "output",
      );
      if (outputsSection) {
        guideWrap.appendChild(outputsSection);
      }

      const commonVars = document.createElement("div");
      commonVars.className = "guide-section";
      const commonLabel = document.createElement("div");
      commonLabel.className = "guide-label";
      commonLabel.textContent =
        "共通テンプレート変数（どのステップでも利用可）";
      commonVars.appendChild(commonLabel);
      const commonLine = document.createElement("div");
      commonLine.className = "guide-item";
      [
        "{{ run_id }}",
        "{{ now }}",
        "{{ today }}",
        "{{ yesterday }}",
        "{{ tomorrow }}",
        "{{ today_ymd }}",
        "{{ now_ymd_hms }}",
        "{{ workflow }}",
        "{{ base_dir }}",
      ].forEach(
        (value) => {
          commonLine.appendChild(buildExampleChip(value));
        },
      );
      commonVars.appendChild(commonLine);
      guideWrap.appendChild(commonVars);

      return guideWrap;
    };

    const paramsRow = document.createElement("div");
    paramsRow.className = "inspector-row";
    const paramsLabel = document.createElement("label");
    paramsLabel.textContent = "入力パラメータ（ここに入力）";
    paramsRow.appendChild(paramsLabel);

    const paramsList = document.createElement("div");
    const entries = Object.entries(step.params || {});
    const availableKeys = (state.ACTION_GUIDES[step.type]?.params || []).map(
      (item) => item.key,
    );
    if (entries.length === 0) {
      entries.push(["", ""]);
    }

    const updateParamsFromUI = () => {
      const rows = Array.from(paramsList.querySelectorAll(".param-row"));
      const nextParams = {};
      rows.forEach((row) => {
        const keyInputEl = row.querySelector(".param-key input");
        const valueInputEl = row.querySelector(".param-value");
        const key = (keyInputEl?.value || "").trim();
        const value = valueInputEl?.value || "";
        if (key) {
          nextParams[key] = value;
        }
      });
      step.params = nextParams;
    };

    const appendParamRow = (key, value) => {
      const { row, keyInput, keySelect, valueInput, removeButton, aiButton } =
        buildParamRow(key, value, availableKeys);
      paramsList.appendChild(row);
      removeButton.addEventListener("click", () => {
        row.remove();
        updateParamsFromUI();
      });
      keyInput.addEventListener("input", updateParamsFromUI);
      keySelect.addEventListener("change", updateParamsFromUI);
      valueInput.addEventListener("input", updateParamsFromUI);
      aiButton.addEventListener("click", () => {
        openExpressionBuilder(valueInput, step);
      });
      return { row, keyInput, valueInput };
    };

    entries.forEach(([key, value]) => {
      appendParamRow(key, value);
    });
    paramsRow.appendChild(paramsList);

    const paramsHelp = document.createElement("div");
    paramsHelp.className = "param-help";
    paramsHelp.textContent =
      "ヒント: 出力は {{ step_id.キー }} の形で次のステップで参照できます。";
    paramsRow.appendChild(paramsHelp);

    const addParamButton = document.createElement("button");
    addParamButton.type = "button";
    addParamButton.className = "ghost-button";
    addParamButton.textContent = "+ 追加";
    addParamButton.addEventListener("click", () => {
      appendParamRow("", "");
    });
    paramsRow.appendChild(addParamButton);

    const guide = buildGuide(step.type, step.id);

    const whenRow = document.createElement("div");
    whenRow.className = "inspector-row";
    const whenLabel = document.createElement("label");
    whenLabel.textContent = "実行条件（任意）";
    whenRow.appendChild(whenLabel);

    const whenToggleLabel = document.createElement("label");
    whenToggleLabel.className = "condition-toggle";
    const whenToggle = document.createElement("input");
    whenToggle.type = "checkbox";
    whenToggle.checked = !!step.when;
    whenToggleLabel.appendChild(whenToggle);
    whenToggleLabel.appendChild(document.createTextNode("条件を使う"));
    whenRow.appendChild(whenToggleLabel);

    const whenFields = document.createElement("div");
    whenFields.className = "condition-fields";

    const whenStepInput = document.createElement("input");
    whenStepInput.type = "text";
    whenStepInput.placeholder = "判定ステップID (例: judge)";
    whenStepInput.value = step.when?.step || "";

    const whenFieldInput = document.createElement("input");
    whenFieldInput.type = "text";
    whenFieldInput.placeholder = "出力キー (例: text)";
    whenFieldInput.value = step.when?.field || "text";

    const whenMatchSelect = document.createElement("select");
    const matchOptions = [
      { value: "equals", label: "一致" },
      { value: "contains", label: "含む" },
    ];
    matchOptions.forEach((option) => {
      const opt = document.createElement("option");
      opt.value = option.value;
      opt.textContent = option.label;
      whenMatchSelect.appendChild(opt);
    });
    whenMatchSelect.value = step.when?.match || "equals";

    const whenEqualsInput = document.createElement("input");
    whenEqualsInput.type = "text";
    whenEqualsInput.placeholder = "一致値 (例: Yes)";
    whenEqualsInput.value =
      step.when && step.when.equals !== undefined && step.when.equals !== null
        ? step.when.equals
        : "";

    whenFields.appendChild(whenStepInput);
    whenFields.appendChild(whenFieldInput);
    whenFields.appendChild(whenMatchSelect);
    whenFields.appendChild(whenEqualsInput);
    whenRow.appendChild(whenFields);

    const whenHelp = document.createElement("div");
    whenHelp.className = "condition-help";
    whenHelp.textContent =
      "一致/含む で判定します（前後空白と大文字小文字は無視）。";
    whenRow.appendChild(whenHelp);

    const whenOptions = {
      trim: step.when?.trim,
      case_insensitive: step.when?.case_insensitive,
    };

    const syncWhen = () => {
      if (!whenToggle.checked) {
        step.when = null;
        whenFields.style.display = "none";
        whenHelp.style.display = "none";
        return;
      }
      whenFields.style.display = "grid";
      whenHelp.style.display = "block";
      const nextWhen = {
        step: whenStepInput.value.trim(),
        field: (whenFieldInput.value || "text").trim() || "text",
        equals: whenEqualsInput.value,
        match: whenMatchSelect.value,
      };
      if (whenOptions.trim === false) {
        nextWhen.trim = false;
      }
      if (whenOptions.case_insensitive === false) {
        nextWhen.case_insensitive = false;
      }
      step.when = nextWhen;
    };

    whenToggle.addEventListener("change", syncWhen);
    whenStepInput.addEventListener("input", syncWhen);
    whenFieldInput.addEventListener("input", syncWhen);
    whenMatchSelect.addEventListener("change", syncWhen);
    whenEqualsInput.addEventListener("input", syncWhen);
    syncWhen();

    const actionsRow = document.createElement("div");
    actionsRow.className = "inspector-actions";
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "danger-button";
    deleteButton.textContent = "削除";
    deleteButton.addEventListener("click", () => removeStep(step.id));
    actionsRow.appendChild(deleteButton);

    inspectorEl.appendChild(orderRow);
    inspectorEl.appendChild(idRow);
    inspectorEl.appendChild(typeRow);
    if (guide) {
      inspectorEl.appendChild(guide);
    }
    inspectorEl.appendChild(paramsRow);
    inspectorEl.appendChild(whenRow);
    inspectorEl.appendChild(actionsRow);

    const updateId = () => {
      const nextId = idInput.value.trim();
      if (!nextId) {
        setStatus("IDは必須です", true);
        return;
      }
      const duplicate = state.workflow.steps.some(
        (item) => item.id === nextId && item !== step,
      );
      if (duplicate) {
        setStatus("IDが重複しています", true);
        return;
      }
      step.id = nextId;
      setStatus("");
      renderCanvas();
    };

    const updateType = () => {
      step.type = typeSelect.value;
      if (!step.params || Object.keys(step.params).length === 0) {
        step.params = getDefaultParams(step.type);
      }
      renderCanvas();
      renderInspector();
    };

    idInput.addEventListener("blur", updateId);
    idInput.addEventListener("input", updateId);
    typeSelect.addEventListener("change", updateType);
  };

  const updateTriggerVisibility = () => {
    const isSchedule = triggerSelect.value === "schedule";
    cronField.style.display = isSchedule ? "grid" : "none";
  };

  let cronPreviewTimer = null;
  const setCronPreviewMessage = (message) => {
    if (cronPreview) {
      cronPreview.textContent = message || "";
    }
  };
  const setCronErrorMessage = (message) => {
    if (cronError) {
      cronError.textContent = message || "";
    }
  };

  const formatJst = (iso) => {
    if (!iso) {
      return "";
    }
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) {
      return iso;
    }
    return date.toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" });
  };

  const updateCronPreview = () => {
    if (!cronInput || triggerSelect.value !== "schedule") {
      setCronPreviewMessage("");
      setCronErrorMessage("");
      return;
    }
    const cron = cronInput.value.trim();
    if (!cron) {
      setCronPreviewMessage("");
      setCronErrorMessage("cron を入力してください");
      return;
    }
    setCronErrorMessage("");
    setCronPreviewMessage("次回実行を確認中...");
    fetch("/api/scheduler/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cron }),
    })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.detail || "cron の解析に失敗しました");
        }
        const nextRuns = Array.isArray(data.next_runs) ? data.next_runs : [];
        if (nextRuns.length === 0) {
          setCronPreviewMessage("次回実行: -");
        } else {
          const previewText = nextRuns.map(formatJst).join(" / ");
          setCronPreviewMessage(`次回実行: ${previewText}`);
        }
        setCronErrorMessage("");
      })
      .catch((error) => {
        setCronPreviewMessage("");
        setCronErrorMessage(error.message || "cron の解析に失敗しました");
      });
  };

  const scheduleCronPreview = () => {
    if (cronPreviewTimer) {
      clearTimeout(cronPreviewTimer);
    }
    cronPreviewTimer = setTimeout(updateCronPreview, 350);
  };

  const buildPayload = () => {
    const steps = [...state.workflow.steps]
      .sort(
        (a, b) => a.position.y - b.position.y || a.position.x - b.position.x,
      )
      .map((step) => {
        const payloadStep = {
          id: step.id,
          type: step.type,
          params: step.params || {},
          position: step.position,
        };
        if (step.when) {
          payloadStep.when = step.when;
        }
        return payloadStep;
      });

    const trigger = { type: triggerSelect.value };
    if (trigger.type === "schedule") {
      trigger.cron = cronInput.value.trim();
    }

    return {
      name: (nameInput.value || "").trim(),
      description: state.workflow.description || "",
      enabled: enabledInput ? !!enabledInput.checked : true,
      trigger,
      steps,
    };
  };

  const normalizeIncomingWhen = (raw) => {
    if (!raw || typeof raw !== "object") {
      return null;
    }
    const step = typeof raw.step === "string" ? raw.step.trim() : "";
    const equals = raw.equals;
    if (
      !step ||
      equals === undefined ||
      equals === null ||
      (typeof equals === "string" && equals.trim() === "")
    ) {
      return null;
    }
    const field =
      typeof raw.field === "string" && raw.field.trim() ? raw.field.trim() : "text";
    const matchRaw =
      typeof raw.match === "string" ? raw.match.trim().toLowerCase() : "equals";
    const matchValue =
      matchRaw === "contains" || matchRaw === "equals" ? matchRaw : "equals";
    const when = { step, field, equals, match: matchValue };
    if (typeof raw.trim === "boolean") {
      when.trim = raw.trim;
    }
    if (typeof raw.case_insensitive === "boolean") {
      when.case_insensitive = raw.case_insensitive;
    }
    return when;
  };

  const normalizeIncomingSteps = (rawSteps, usedIds, offsetIndex = 0) => {
    if (!Array.isArray(rawSteps)) {
      return [];
    }
    const normalized = [];
    rawSteps.forEach((raw, index) => {
      if (!raw || typeof raw !== "object") {
        return;
      }
      const type =
        typeof raw.type === "string" && raw.type.trim()
          ? raw.type.trim()
          : state.actions[0] || "log";
      const params = raw.params && typeof raw.params === "object" ? raw.params : {};
      const when = normalizeIncomingWhen(raw.when);
      const baseId = raw.id || type;
      const id = ensureUniqueId(baseId, usedIds);
      const baseIndex = offsetIndex + index;
      const x = 80;
      const y = 80 + baseIndex * 120;
      const step = { id, type, params, position: { x, y } };
      if (when) {
        step.when = when;
      }
      normalized.push(step);
    });
    return normalized;
  };

  const buildAiContext = () => {
    const payload = buildPayload();
    const steps = (payload.steps || []).map((step) => ({
      id: step.id,
      type: step.type,
      params: step.params || {},
      when: step.when || null,
    }));
    return { ...payload, steps };
  };

  const applyAiWorkflow = (workflow, mode) => {
    if (!workflow || !Array.isArray(workflow.steps)) {
      setAiStatus("AI の応答形式が不正です", "error");
      return false;
    }
    const usedIds =
      mode === "append"
        ? new Set(state.workflow.steps.map((step) => step.id))
        : new Set();
    const offsetIndex = mode === "append" ? state.workflow.steps.length : 0;
    const normalizedSteps = normalizeIncomingSteps(
      workflow.steps,
      usedIds,
      offsetIndex,
    );
    if (normalizedSteps.length === 0) {
      setAiStatus("有効なステップがありませんでした", "error");
      return false;
    }

    if (mode === "replace") {
      state.workflow.steps = normalizedSteps;
      if (workflow.name) {
        state.workflow.name = workflow.name;
      }
      if (workflow.description !== undefined) {
        state.workflow.description = workflow.description || "";
      }
      if (workflow.trigger) {
        state.workflow.trigger = workflow.trigger;
      }
      if (typeof workflow.enabled === "boolean") {
        state.workflow.enabled = workflow.enabled;
      }
    } else {
      normalizedSteps.forEach((step) => state.workflow.steps.push(step));
    }

    nameInput.value = state.workflow.name || "";
    triggerSelect.value = state.workflow.trigger?.type || "manual";
    cronInput.value = state.workflow.trigger?.cron || "";
    if (enabledInput) {
      enabledInput.checked = state.workflow.enabled !== false;
    }
    updateTriggerVisibility();
    scheduleCronPreview();
    selectStep(normalizedSteps[0].id);
    return true;
  };

  const requestAiFlow = async () => {
    if (!aiPromptInput || !aiGenerateButton) {
      return;
    }
    const prompt = aiPromptInput.value.trim();
    if (!prompt) {
      setAiStatus("指示を入力してください", "error");
      return;
    }
    const mode = aiModeSelect ? aiModeSelect.value : "replace";
    if (mode === "replace" && state.workflow.steps.length > 0) {
      const ok = window.confirm("現在のフローを置き換えますか？");
      if (!ok) {
        return;
      }
    }

    const originalLabel = aiGenerateButton.textContent;
    aiGenerateButton.disabled = true;
    aiGenerateButton.textContent = "生成中...";
    setAiStatus("AI に問い合わせ中...");

    try {
      const response = await fetch(config.aiUrl || "/api/ai/flow", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          mode,
          current_workflow: buildAiContext(),
          use_search: aiSearchToggle ? !!aiSearchToggle.checked : true,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "AI 生成に失敗しました");
      }

      const applied = applyAiWorkflow(data.workflow, mode);
      if (!applied) {
        return;
      }
      if (Array.isArray(data.warnings) && data.warnings.length > 0) {
        setAiStatus(`生成完了（注意: ${data.warnings.join(" / ")}）`, "success");
      } else {
        setAiStatus("生成完了", "success");
      }
    } catch (error) {
      setAiStatus(error.message || "AI 生成に失敗しました", "error");
    } finally {
      aiGenerateButton.disabled = false;
      aiGenerateButton.textContent = originalLabel || "AIで構築";
    }
  };

  const validateRequiredParams = (payload) => {
    for (const step of payload.steps) {
      const required = REQUIRED_PARAMS[step.type];
      if (required) {
        for (const key of required) {
          const value = step.params ? step.params[key] : undefined;
          if (typeof value !== "string" || value.trim() === "") {
            setStatus(`"${step.id}" の ${key} が必要です`, true);
            return false;
          }
        }
      }
      if (step.when) {
        const whenStep = (step.when.step || "").trim();
        const whenEquals = step.when.equals;
        if (!whenStep) {
          setStatus(`"${step.id}" の条件ステップIDが必要です`, true);
          return false;
        }
        if (
          whenEquals === undefined ||
          whenEquals === null ||
          (typeof whenEquals === "string" && whenEquals.trim() === "")
        ) {
          setStatus(`"${step.id}" の条件の一致値が必要です`, true);
          return false;
        }
        if (!step.when.field || step.when.field.trim() === "") {
          step.when.field = "text";
        }
      }
    }
    return true;
  };

  const saveWorkflow = async () => {
    setStatus("保存中...");
    saveButton.disabled = true;
    try {
      const payload = buildPayload();
      if (!payload.name) {
        setStatus("ワークフロー名が必要です", true);
        return;
      }
      if (payload.steps.length === 0) {
        setStatus("ステップを追加してください", true);
        return;
      }
      if (!validateRequiredParams(payload)) {
        return;
      }
      const response = await fetch(config.saveUrl || "/api/workflows/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail || "保存に失敗しました");
      }
      const result = await response.json();
      setStatus("保存しました");
      if (result.name && window.location.pathname.indexOf("/edit") === -1) {
        window.location.href = `/workflows/${result.name}/edit`;
      }
    } catch (error) {
      setStatus(error.message || "保存に失敗しました", true);
    } finally {
      saveButton.disabled = false;
    }
  };

  let dragState = null;
  const onPointerMove = (event) => {
    if (!dragState) {
      return;
    }
    const step = state.workflow.steps.find((item) => item.id === dragState.id);
    if (!step) {
      return;
    }
    const dx = event.clientX - dragState.startX;
    const dy = event.clientY - dragState.startY;
    step.position.x = Math.max(0, dragState.originX + dx);
    step.position.y = Math.max(0, dragState.originY + dy);
    renderCanvas();
  };

  const onPointerUp = () => {
    if (!dragState) {
      return;
    }
    if (dragState.pointerId !== null) {
      canvasEl.releasePointerCapture(dragState.pointerId);
    }
    dragState = null;
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
  };

  canvasEl.addEventListener("pointerdown", (event) => {
    const target =
      event.target instanceof Element
        ? event.target
        : event.target.parentElement;
    const nodeEl = target ? target.closest(".flow-node") : null;
    if (!nodeEl) {
      return;
    }
    event.preventDefault();
    const id = nodeEl.dataset.id;
    selectStep(id);
    const step = state.workflow.steps.find((item) => item.id === id);
    if (!step) {
      return;
    }
    dragState = {
      id,
      startX: event.clientX,
      startY: event.clientY,
      originX: step.position.x,
      originY: step.position.y,
      pointerId: event.pointerId,
    };
    canvasEl.setPointerCapture(event.pointerId);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
  });

  saveButton.addEventListener("click", saveWorkflow);
  if (aiGenerateButton) {
    aiGenerateButton.addEventListener("click", requestAiFlow);
  }
  if (aiClearButton && aiPromptInput) {
    aiClearButton.addEventListener("click", () => {
      aiPromptInput.value = "";
      setAiStatus("");
      aiPromptInput.focus();
    });
  }
  if (aiPromptInput) {
    aiPromptInput.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        requestAiFlow();
      }
    });
  }
  triggerSelect.addEventListener("change", updateTriggerVisibility);
  if (cronPreset) {
    cronPreset.addEventListener("change", () => {
      if (cronPreset.value) {
        cronInput.value = cronPreset.value;
      }
      scheduleCronPreview();
    });
  }
  if (cronInput) {
    cronInput.addEventListener("input", scheduleCronPreview);
    cronInput.addEventListener("blur", updateCronPreview);
  }

  nameInput.value = state.workflow.name || "";
  triggerSelect.value = state.workflow.trigger?.type || "manual";
  cronInput.value = state.workflow.trigger?.cron || "";
  if (enabledInput) {
    enabledInput.checked = state.workflow.enabled !== false;
  }
  updateTriggerVisibility();
  scheduleCronPreview();

  refreshActions();
  renderCanvas();
  renderInspector();
})();
