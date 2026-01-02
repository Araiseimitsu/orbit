# ORBIT MVP 開発進捗

## 現在の状態
- **Day 4 完了** - 次は Day 5 から再開

## 技術スタック
- Python 3.13
- FastAPI + Uvicorn
- HTMX + TailwindCSS (CDN)
- Gemini API（AI連携）

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

## 次回のタスク: Day 5

### Google Sheets Read
- [ ] Service Account で Sheets read
- [ ] `google_sheet_read` action 実装
- [ ] サンプルワークフローで値を取得 → log に出す

## 現在のファイル構造

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
│       │   └── file_ops.py      # file_write / file_read
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
│   └── test_every_minute.yaml   # テスト用（毎分実行）
├── runs/
│   ├── 20260102.jsonl           # 実行ログ
│   └── output/                  # ワークフロー出力ファイル
├── secrets/
│   └── .gitkeep
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
