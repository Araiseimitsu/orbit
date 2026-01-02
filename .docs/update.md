# ORBIT MVP 開発進捗

## 現在の状態
- **Day 7-8 完了** - UI 仕上げ完了

## 更新履歴
- 2026-01-02: フローエディタでドラッグ順序が分かるよう、ノードに実行順バッジと詳細パネルの順序表示を追加。

## 技術スタック
- Python 3.13
- FastAPI + Uvicorn
- HTMX + Alpine.js + TailwindCSS (CDN)
- Gemini API / OpenAI API（AI連携）
- Google Sheets API

## 完了タスク

### Day 1: 土台づくり
- FastAPIプロジェクト作成
- HTMX + Tailwind CDN を base.html に適用
- ルーティング: `/`, `/workflows/{name}`, `/runs`
- workflowsディレクトリ読込（一覧表示）

### Day 2: Workflow Loader & Validation
- Pydanticモデル（Workflow, Step, Trigger, WorkflowInfo, RunLog）
- YAMLローダー（PyYAML + バリデーション）
- 不正なworkflowはUIでエラー表示

### Day 3: Executor（直列実行）+ ログ（JSONL）
- ActionRegistry（アクション登録辞書）
- log / file_write / file_read アクション
- Executor（直列実行エンジン）+ Jinja2テンプレート展開
- RunLogger（JSONL追記）
- API エンドポイント POST /api/workflows/{name}/run
- UIでRun結果をトースト表示（HTMX）

### Day 4: Scheduler（cron）
- APScheduler導入（AsyncIOScheduler）
- WorkflowScheduler クラス作成（scheduler.py）
- FastAPI lifespan でスケジューラー起動/停止
- workflow.trigger = schedule のワークフロー自動登録
- 次回実行予定の UI 表示
- デバッグ用 API エンドポイント追加（/api/scheduler/jobs, /api/scheduler/reload）

### Day 5: Google Sheets 連携
- google-api-python-client / google-auth 導入
- `sheets_read` アクション実装（ヘッダー行処理対応）
- `sheets_list` アクション実装（シート一覧取得）
- サービスアカウント認証（secrets/google_service_account.json）

### Day 6: AI アクション
- `ai_generate` アクション実装（Gemini/OpenAI対応）
- `ai_summarize` アクション実装（要約ショートカット）
- openai パッケージ追加
- テストワークフロー作成（ai_test, ai_summarize_test, ai_openai_test）

### Day 7-8: UI 仕上げ
- Alpine.js 導入（トースト通知の展開機能）
- グローバルローディングオーバーレイ追加
- ボタン内スピナー表示（htmx-indicator）
- トースト通知の詳細展開（成功/失敗時）
- 実行履歴詳細画面（runs.html）の拡張
  - ステップ結果の表示
  - エラー詳細の展開
  - 完全な JSON デバッグ表示
- ワークフロー詳細画面の実行履歴強化
- エラーハンドリング強化（try-except で予期しないエラーもキャッチ）

## 次回のタスク: Day 9-10

### 運用対応
- [ ] タイムアウト処理の実装
- [ ] ログローテーション
- [ ] 実行中ワークフローのキャンセル機能
- [ ] リソース使用状況の監視

## 現在のファイル構成

```
orbit/
├── src/
│   ├── __init__.py
│   └── app/
│       ├── __init__.py
│       ├── main.py              # FastAPIエントリーポイント
│       ├── core/
│       │   ├── __init__.py
│       │   ├── models.py        # Pydanticスキーマ
│       │   ├── loader.py        # YAMLローダー
│       │   ├── registry.py      # ActionRegistry
│       │   ├── executor.py      # Executor（直列実行）
│       │   ├── run_logger.py    # JSONL記録
│       │   ├── templating.py    # Jinja2テンプレレンダ
│       │   └── scheduler.py     # APScheduler（cron実行）
│       ├── actions/
│       │   ├── __init__.py
│       │   ├── log.py           # logアクション
│       │   ├── file_ops.py      # file_write / file_read
│       │   ├── google_sheets.py # sheets_read / sheets_list
│       │   └── ai.py            # ai_generate / ai_summarize
│       └── ui/
│           ├── __init__.py
│           └── templates/
│               ├── base.html
│               ├── dashboard.html
│               ├── workflow_detail.html
│               ├── runs.html
│               └── partials/
│                   └── run_result.html
├── workflows/
│   ├── hello_world.yaml
│   ├── sample_daily_summary.yaml
│   ├── test_every_minute.yaml   # テスト用（毎分実行）
│   ├── ai_test.yaml             # AIテスト
│   ├── ai_summarize_test.yaml   # 要約テスト
│   └── ai_openai_test.yaml      # OpenAIテスト
├── runs/
│   └── output/                  # ワークフロー出力ファイル
├── secrets/
│   └── .gitkeep                 # APIキー配置用
├── .docs/
│   ├── workflow_mvp_plan.md     # MVP計画書
│   └── update.md                # この進捗ファイル
├── requirements.txt
├── .env.example
└── .gitignore
```

## 起動コマンド
```bash
py -3.13 -m uvicorn src.app.main:app --reload
```

## 動作確認済み
- ダッシュボード（ワークフロー一覧）
- ワークフロー詳細画面
- 実行履歴一覧
- 手動Run（HTMX）→ トースト通知
- JSONL実行ログ記録
- スケジュール実行（APScheduler）
- 次回実行予定の表示

## 参照ファイル
- MVP計画書: `.docs/workflow_mvp_plan.md`

## 更新履歴

### 2026/01/02
- 新規ワークフロー作成のUI導線を追加（ダッシュボード/ナビ）
- 新規作成ガイドページ（/workflows/new）を追加
- `.docs/AGENTS.md` / `.docs/CLAUDE.md` / `.docs/copilot-instructions.md` を作成
- ビジュアルエディタ（/workflows/new/visual, /workflows/{name}/edit）を追加
- アクション追加・ドラッグ移動・詳細編集のUIを実装
- ワークフロー保存API（/api/workflows/save）とアクション一覧APIを追加
- UI用の静的ファイル（/static）を追加
- ビジュアルエディタの詳細設定にアクション別の設定ガイドと出力参照例を追加
