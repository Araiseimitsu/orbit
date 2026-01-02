(() => {
    const configEl = document.getElementById('flow-editor-config');
    if (!configEl) {
        return;
    }

    const config = JSON.parse(configEl.textContent || '{}');
    const state = {
        workflow: config.workflow || { name: '', description: '', trigger: { type: 'manual' }, steps: [] },
        actions: config.actions || [],
        selectedId: null
    };

    const ACTION_GUIDES = {
        log: {
            title: 'ログ出力',
            description: '指定メッセージをログに出力します。テンプレートで前のステップ結果を参照できます。',
            params: [
                { key: 'message', desc: '出力メッセージ（必須）', example: 'Hello {{ step_1.text }}' },
                { key: 'level', desc: 'debug / info / warning / error', example: 'info' }
            ],
            outputs: [
                { key: 'logged', desc: '出力成功フラグ' },
                { key: 'message', desc: '出力したメッセージ' }
            ]
        },
        file_write: {
            title: 'ファイル書き込み',
            description: '指定パスへ内容を書き込みます（相対パスはプロジェクトルート基準）。',
            params: [
                { key: 'path', desc: '出力先パス（必須）', example: 'runs/output/{{ run_id }}.txt' },
                { key: 'content', desc: '書き込む内容（必須）', example: '結果: {{ step_1.text }}' },
                { key: 'encoding', desc: '文字コード（任意）', example: 'utf-8' }
            ],
            outputs: [
                { key: 'written', desc: '書き込み成功フラグ' },
                { key: 'path', desc: '書き込んだパス' },
                { key: 'size', desc: 'ファイルサイズ（bytes）' }
            ]
        },
        file_read: {
            title: 'ファイル読み込み',
            description: '指定パスの内容を読み込みます（相対パスはプロジェクトルート基準）。',
            params: [
                { key: 'path', desc: '読み込み元パス（必須）', example: 'runs/output/{{ run_id }}.txt' },
                { key: 'encoding', desc: '文字コード（任意）', example: 'utf-8' }
            ],
            outputs: [
                { key: 'content', desc: 'ファイル内容' },
                { key: 'path', desc: '読み込んだパス' },
                { key: 'size', desc: 'ファイルサイズ（bytes）' }
            ]
        },
        sheets_read: {
            title: 'Google Sheets 読み取り',
            description: 'スプレッドシートから指定範囲のデータを取得します。',
            params: [
                { key: 'spreadsheet_id', desc: 'スプレッドシートID（必須）', example: '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms' },
                { key: 'range', desc: '取得範囲（必須）', example: 'Sheet1!A1:D10' },
                { key: 'header_row', desc: '1行目をヘッダーとして扱う', example: 'true' },
                { key: 'credentials_file', desc: '認証JSONのパス', example: 'secrets/google_service_account.json' }
            ],
            outputs: [
                { key: 'headers', desc: 'ヘッダー配列' },
                { key: 'rows', desc: 'ヘッダー付き行データ' },
                { key: 'raw', desc: '生データ（2次元配列）' },
                { key: 'row_count', desc: '行数' },
                { key: 'col_count', desc: '列数' }
            ]
        },
        sheets_list: {
            title: 'Google Sheets シート一覧',
            description: 'スプレッドシート内のシート情報を取得します。',
            params: [
                { key: 'spreadsheet_id', desc: 'スプレッドシートID（必須）', example: '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms' },
                { key: 'credentials_file', desc: '認証JSONのパス', example: 'secrets/google_service_account.json' }
            ],
            outputs: [
                { key: 'sheets', desc: 'シート一覧（id/title/index）' },
                { key: 'title', desc: 'スプレッドシート名' }
            ]
        },
        ai_generate: {
            title: 'AI 生成',
            description: 'プロンプトをAIに渡してテキストを生成します。',
            params: [
                { key: 'prompt', desc: '生成指示（必須）', example: '次を要約: {{ step_1.text }}' },
                { key: 'system', desc: 'システムプロンプト', example: 'あなたは優秀なアシスタントです' },
                { key: 'provider', desc: 'gemini', example: 'gemini' },
                { key: 'model', desc: 'モデル名', example: 'gemini-2.5-flash-lite' },
                { key: 'max_tokens', desc: '最大出力トークン数', example: '1000' },
                { key: 'temperature', desc: '0.0〜1.0', example: '0.7' },
                { key: 'api_key_file', desc: 'APIキーのファイルパス', example: 'secrets/gemini_api_key.txt' }
            ],
            outputs: [
                { key: 'text', desc: '生成テキスト' },
                { key: 'model', desc: '使用モデル' },
                { key: 'provider', desc: 'gemini' },
                { key: 'finish_reason', desc: '完了理由' },
                { key: 'prompt_tokens', desc: '入力トークン数' },
                { key: 'completion_tokens', desc: '出力トークン数' },
                { key: 'total_tokens', desc: '合計トークン数' }
            ]
        },
        ai_summarize: {
            title: 'AI 要約',
            description: 'テキストを要約するショートカットアクションです。',
            params: [
                { key: 'text', desc: '要約対象テキスト（必須）', example: '{{ step_1.text }}' },
                { key: 'max_length', desc: '最大文字数', example: '200' },
                { key: 'provider', desc: 'gemini', example: 'gemini' },
                { key: 'language', desc: '出力言語', example: 'japanese' },
                { key: 'model', desc: 'モデル名（任意）', example: 'gemini-2.5-flash-lite' },
                { key: 'api_key_file', desc: 'APIキーのファイルパス', example: 'secrets/gemini_api_key.txt' }
            ],
            outputs: [
                { key: 'summary', desc: '要約結果' },
                { key: 'text', desc: '生成テキスト' },
                { key: 'original_length', desc: '元テキスト長' }
            ]
        }
    };

    const nameInput = document.getElementById('workflow-name');
    const triggerSelect = document.getElementById('trigger-type');
    const cronField = document.getElementById('cron-field');
    const cronInput = document.getElementById('trigger-cron');
    const statusEl = document.getElementById('editor-status');
    const saveButton = document.getElementById('save-workflow');
    const actionListEl = document.getElementById('action-list');
    const canvasEl = document.getElementById('flow-canvas');
    const inspectorEl = document.getElementById('inspector');
    const addNodeButton = document.getElementById('add-node');

    const REQUIRED_PARAMS = {
        ai_generate: ['prompt'],
        ai_summarize: ['text']
    };

    const DEFAULT_PARAMS = {
        ai_generate: { prompt: '' },
        ai_summarize: { text: '' }
    };

    const getDefaultParams = (type) => ({ ...(DEFAULT_PARAMS[type] || {}) });

    const setStatus = (message, isError = false) => {
        if (!statusEl) {
            return;
        }
        statusEl.textContent = message;
        statusEl.style.color = isError ? '#b91c1c' : '#475569';
    };

    const uniqueId = (base) => {
        const safeBase = (base || 'step').replace(/[^a-zA-Z0-9_]+/g, '_');
        let index = 1;
        let candidate = `${safeBase}_${index}`;
        const ids = new Set(state.workflow.steps.map((step) => step.id));
        while (ids.has(candidate)) {
            index += 1;
            candidate = `${safeBase}_${index}`;
        }
        return candidate;
    };

    const getSelectedStep = () => state.workflow.steps.find((step) => step.id === state.selectedId);

    const selectStep = (id) => {
        state.selectedId = id;
        renderCanvas();
        renderInspector();
        const firstInput = inspectorEl.querySelector('input');
        if (firstInput) {
            firstInput.focus();
        }
    };

    const addStep = (type) => {
        const stepType = type || state.actions[0] || 'log';
        const newStep = {
            id: uniqueId(stepType),
            type: stepType,
            params: getDefaultParams(stepType),
            position: {
                x: 80 + state.workflow.steps.length * 20,
                y: 80 + state.workflow.steps.length * 80
            }
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
        actionListEl.innerHTML = '';
        const actions = state.actions.length ? state.actions : ['log'];
        actions.forEach((action) => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'action-item';
            item.textContent = action;
            item.addEventListener('click', () => addStep(action));
            actionListEl.appendChild(item);
        });
    };

    const refreshActions = async () => {
        if (state.actions.length > 0) {
            renderActionList();
            return;
        }
        try {
            const response = await fetch('/api/actions');
            if (response.ok) {
                const data = await response.json();
                if (Array.isArray(data.actions)) {
                    state.actions = data.actions;
                }
            }
        } catch (error) {
            // フェイルセーフ: 失敗しても UI は続行
        }
        renderActionList();
        renderInspector();
    };

    const renderCanvas = () => {
        canvasEl.innerHTML = '';
        const orderMap = new Map(
            [...state.workflow.steps]
                .sort((a, b) => (a.position.y - b.position.y) || (a.position.x - b.position.x))
                .map((step, index) => [step.id, index + 1])
        );
        state.workflow.steps.forEach((step) => {
            const node = document.createElement('div');
            node.className = 'flow-node' + (step.id === state.selectedId ? ' selected' : '');
            node.dataset.id = step.id;
            node.style.left = `${step.position.x}px`;
            node.style.top = `${step.position.y}px`;
            node.addEventListener('click', (event) => {
                event.stopPropagation();
                selectStep(step.id);
            });

            const orderBadge = document.createElement('div');
            orderBadge.className = 'flow-node-order';
            orderBadge.textContent = `#${orderMap.get(step.id) || 0}`;

            const title = document.createElement('div');
            title.className = 'flow-node-title';
            title.textContent = step.type;

            const label = document.createElement('div');
            label.className = 'flow-node-id';
            label.textContent = step.id;

            node.appendChild(orderBadge);
            node.appendChild(title);
            node.appendChild(label);
            canvasEl.appendChild(node);
        });
    };

    const buildParamRow = (key, value, availableKeys) => {
        const row = document.createElement('div');
        row.className = 'param-row';

        const keyWrap = document.createElement('div');
        keyWrap.className = 'param-key';

        const keySelect = document.createElement('select');
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = '入力パラメータを選択';
        keySelect.appendChild(defaultOption);

        (availableKeys || []).forEach((paramKey) => {
            const opt = document.createElement('option');
            opt.value = paramKey;
            opt.textContent = paramKey;
            keySelect.appendChild(opt);
        });

        const customOption = document.createElement('option');
        customOption.value = '__custom__';
        customOption.textContent = 'カスタム入力...';
        keySelect.appendChild(customOption);

        const keyInput = document.createElement('input');
        keyInput.type = 'text';
        keyInput.value = key || '';
        keyInput.placeholder = '例: prompt';
        keyInput.style.display = 'none';

        const setKeyMode = (selectedValue) => {
            if (selectedValue === '__custom__' || (!selectedValue && keyInput.value)) {
                keyInput.style.display = 'block';
            } else {
                keyInput.style.display = 'none';
                if (selectedValue) {
                    keyInput.value = selectedValue;
                }
            }
        };

        if (key && (availableKeys || []).includes(key)) {
            keySelect.value = key;
            setKeyMode(key);
        } else if (key) {
            keySelect.value = '__custom__';
            setKeyMode('__custom__');
        } else {
            keySelect.value = '';
            setKeyMode('');
        }

        keySelect.addEventListener('change', () => {
            setKeyMode(keySelect.value);
        });

        keyWrap.appendChild(keySelect);
        keyWrap.appendChild(keyInput);

        const valueInput = document.createElement('input');
        valueInput.type = 'text';
        valueInput.value = value || '';
        valueInput.placeholder = '例: {{ step_1.text }}';

        const removeButton = document.createElement('button');
        removeButton.type = 'button';
        removeButton.textContent = '削除';

        row.appendChild(keyWrap);
        row.appendChild(valueInput);
        row.appendChild(removeButton);

        return { row, keyInput, keySelect, valueInput, removeButton };
    };

    const renderInspector = () => {
        inspectorEl.innerHTML = '';
        const step = getSelectedStep();
        if (!step) {
            const hint = document.createElement('div');
            hint.textContent = 'ノードを選択してください。';
            hint.style.color = '#64748b';
            inspectorEl.appendChild(hint);
            return;
        }

        const orderedSteps = [...state.workflow.steps]
            .sort((a, b) => (a.position.y - b.position.y) || (a.position.x - b.position.x));
        const orderIndex = orderedSteps.findIndex((item) => item.id === step.id);

        const orderRow = document.createElement('div');
        orderRow.className = 'inspector-row';
        const orderLabel = document.createElement('label');
        orderLabel.textContent = '実行順';
        const orderValue = document.createElement('div');
        orderValue.className = 'inspector-order';
        orderValue.textContent = orderIndex >= 0 ? `${orderIndex + 1} / ${orderedSteps.length}` : '-';
        orderRow.appendChild(orderLabel);
        orderRow.appendChild(orderValue);

        const idRow = document.createElement('div');
        idRow.className = 'inspector-row';
        const idLabel = document.createElement('label');
        idLabel.textContent = 'ID';
        const idInput = document.createElement('input');
        idInput.type = 'text';
        idInput.value = step.id;
        idRow.appendChild(idLabel);
        idRow.appendChild(idInput);

        const typeRow = document.createElement('div');
        typeRow.className = 'inspector-row';
        const typeLabel = document.createElement('label');
        typeLabel.textContent = 'タイプ';
        const typeSelect = document.createElement('select');
        const actions = state.actions.length ? state.actions : ['log'];
        actions.forEach((action) => {
            const opt = document.createElement('option');
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
            const guide = ACTION_GUIDES[stepType];
            if (!guide) {
                return null;
            }

            const guideWrap = document.createElement('div');
            guideWrap.className = 'inspector-guide';

            const guideTitle = document.createElement('div');
            guideTitle.className = 'guide-title';
            guideTitle.textContent = `${guide.title} の設定ガイド`;
            guideWrap.appendChild(guideTitle);

            const guideDesc = document.createElement('div');
            guideDesc.className = 'guide-desc';
            guideDesc.textContent = guide.description;
            guideWrap.appendChild(guideDesc);

            const exampleStepId = stepId || 'step_id';

            const buildSection = (label, items, withExamples, sectionClass) => {
                if (!items || items.length === 0) {
                    return null;
                }
                const section = document.createElement('div');
                section.className = sectionClass ? `guide-section ${sectionClass}` : 'guide-section';

                const sectionLabel = document.createElement('div');
                sectionLabel.className = 'guide-label';
                sectionLabel.textContent = label;
                section.appendChild(sectionLabel);

                items.forEach((item) => {
                    const line = document.createElement('div');
                    line.className = 'guide-item';
                    let text = `${item.key}: ${item.desc}`;
                    if (withExamples && item.example) {
                        text += `（例: ${item.example}）`;
                    }
                    line.textContent = text;
                    section.appendChild(line);
                });

                return section;
            };

            const paramsSection = buildSection('入力パラメータ（このステップに渡す）', guide.params, true, 'input');
            if (paramsSection) {
                guideWrap.appendChild(paramsSection);
            }

            const outputs = (guide.outputs || []).map((item) => ({
                ...item,
                example: item.example || `{{ ${exampleStepId}.${item.key} }}`
            }));
            const outputsSection = buildSection('出力の参照例（次のステップで使う）', outputs, true, 'output');
            if (outputsSection) {
                guideWrap.appendChild(outputsSection);
            }

            const commonVars = document.createElement('div');
            commonVars.className = 'guide-section';
            const commonLabel = document.createElement('div');
            commonLabel.className = 'guide-label';
            commonLabel.textContent = '共通テンプレート変数（どのステップでも利用可）';
            commonVars.appendChild(commonLabel);
            const commonLine = document.createElement('div');
            commonLine.className = 'guide-item';
            commonLine.textContent = '{{ run_id }}, {{ now }}, {{ workflow }}, {{ base_dir }}';
            commonVars.appendChild(commonLine);
            guideWrap.appendChild(commonVars);

            return guideWrap;
        };

        const paramsRow = document.createElement('div');
        paramsRow.className = 'inspector-row';
        const paramsLabel = document.createElement('label');
        paramsLabel.textContent = '入力パラメータ（ここに入力）';
        paramsRow.appendChild(paramsLabel);

        const paramsList = document.createElement('div');
        const entries = Object.entries(step.params || {});
        const availableKeys = (ACTION_GUIDES[step.type]?.params || []).map((item) => item.key);
        if (entries.length === 0) {
            entries.push(['', '']);
        }

        const updateParamsFromUI = () => {
            const rows = Array.from(paramsList.querySelectorAll('.param-row'));
            const nextParams = {};
            rows.forEach((row) => {
                const inputs = row.querySelectorAll('input');
                const key = (inputs[0]?.value || '').trim();
                const value = inputs[1]?.value || '';
                if (key) {
                    nextParams[key] = value;
                }
            });
            step.params = nextParams;
        };

        const appendParamRow = (key, value) => {
            const { row, keyInput, keySelect, valueInput, removeButton } = buildParamRow(key, value, availableKeys);
            paramsList.appendChild(row);
            removeButton.addEventListener('click', () => {
                row.remove();
                updateParamsFromUI();
            });
            keyInput.addEventListener('input', updateParamsFromUI);
            keySelect.addEventListener('change', updateParamsFromUI);
            valueInput.addEventListener('input', updateParamsFromUI);
            return { row, keyInput, valueInput };
        };

        entries.forEach(([key, value]) => {
            appendParamRow(key, value);
        });
        paramsRow.appendChild(paramsList);

        const paramsHelp = document.createElement('div');
        paramsHelp.className = 'param-help';
        paramsHelp.textContent = 'ヒント: 出力は {{ step_id.キー }} の形で次のステップで参照できます。';
        paramsRow.appendChild(paramsHelp);

        const addParamButton = document.createElement('button');
        addParamButton.type = 'button';
        addParamButton.className = 'ghost-button';
        addParamButton.textContent = '+ 追加';
        addParamButton.addEventListener('click', () => {
            appendParamRow('', '');
        });
        paramsRow.appendChild(addParamButton);

        const guide = buildGuide(step.type, step.id);

        const actionsRow = document.createElement('div');
        actionsRow.className = 'inspector-actions';
        const deleteButton = document.createElement('button');
        deleteButton.type = 'button';
        deleteButton.className = 'danger-button';
        deleteButton.textContent = '削除';
        deleteButton.addEventListener('click', () => removeStep(step.id));
        actionsRow.appendChild(deleteButton);

        inspectorEl.appendChild(orderRow);
        inspectorEl.appendChild(idRow);
        inspectorEl.appendChild(typeRow);
        if (guide) {
            inspectorEl.appendChild(guide);
        }
        inspectorEl.appendChild(paramsRow);
        inspectorEl.appendChild(actionsRow);

        const updateId = () => {
            const nextId = idInput.value.trim();
            if (!nextId) {
                setStatus('IDは必須です', true);
                return;
            }
            const duplicate = state.workflow.steps.some((item) => item.id === nextId && item !== step);
            if (duplicate) {
                setStatus('IDが重複しています', true);
                return;
            }
            step.id = nextId;
            setStatus('');
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

        idInput.addEventListener('blur', updateId);
        idInput.addEventListener('input', updateId);
        typeSelect.addEventListener('change', updateType);
    };

    const updateTriggerVisibility = () => {
        const isSchedule = triggerSelect.value === 'schedule';
        cronField.style.display = isSchedule ? 'block' : 'none';
    };

    const buildPayload = () => {
        const steps = [...state.workflow.steps]
            .sort((a, b) => (a.position.y - b.position.y) || (a.position.x - b.position.x))
            .map((step) => ({
                id: step.id,
                type: step.type,
                params: step.params || {},
                position: step.position
            }));

        const trigger = { type: triggerSelect.value };
        if (trigger.type === 'schedule') {
            trigger.cron = cronInput.value.trim();
        }

        return {
            name: (nameInput.value || '').trim(),
            description: state.workflow.description || '',
            trigger,
            steps
        };
    };

    const validateRequiredParams = (payload) => {
        for (const step of payload.steps) {
            const required = REQUIRED_PARAMS[step.type];
            if (!required) {
                continue;
            }
            for (const key of required) {
                const value = step.params ? step.params[key] : undefined;
                if (typeof value !== 'string' || value.trim() === '') {
                    setStatus(`"${step.id}" の ${key} が必要です`, true);
                    return false;
                }
            }
        }
        return true;
    };

    const saveWorkflow = async () => {
        setStatus('保存中...');
        saveButton.disabled = true;
        try {
            const payload = buildPayload();
            if (!payload.name) {
                setStatus('ワークフロー名が必要です', true);
                return;
            }
            if (payload.steps.length === 0) {
                setStatus('ステップを追加してください', true);
                return;
            }
            if (!validateRequiredParams(payload)) {
                return;
            }
            const response = await fetch(config.saveUrl || '/api/workflows/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!response.ok) {
                const body = await response.json();
                throw new Error(body.detail || '保存に失敗しました');
            }
            const result = await response.json();
            setStatus('保存しました');
            if (result.name && window.location.pathname.indexOf('/edit') === -1) {
                window.location.href = `/workflows/${result.name}/edit`;
            }
        } catch (error) {
            setStatus(error.message || '保存に失敗しました', true);
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
        window.removeEventListener('pointermove', onPointerMove);
        window.removeEventListener('pointerup', onPointerUp);
    };

    canvasEl.addEventListener('pointerdown', (event) => {
        const target = event.target instanceof Element ? event.target : event.target.parentElement;
        const nodeEl = target ? target.closest('.flow-node') : null;
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
            pointerId: event.pointerId
        };
        canvasEl.setPointerCapture(event.pointerId);
        window.addEventListener('pointermove', onPointerMove);
        window.addEventListener('pointerup', onPointerUp);
    });

    addNodeButton.addEventListener('click', () => addStep());
    saveButton.addEventListener('click', saveWorkflow);
    triggerSelect.addEventListener('change', updateTriggerVisibility);

    nameInput.value = state.workflow.name || '';
    triggerSelect.value = state.workflow.trigger?.type || 'manual';
    cronInput.value = state.workflow.trigger?.cron || '';
    updateTriggerVisibility();

    refreshActions();
    renderCanvas();
    renderInspector();
})();
