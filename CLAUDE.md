# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

ORBIT は n8n ライクなワークフロー実行エンジン（MVP）。YAML定義でワークフローを作成し、スケジュール実行または手動実行できる。DB なし、ローカル駆動。

## アーキテクチャ

### コアコンポーネント

```
src/app/core/
├── models.py          # Pydantic: Workflow, Step, Trigger, RunLog 等
├── loader.py          # WorkflowLoader: workflows/ から YAML 読み込み・バリデーション
├── executor.py        # Executor: ステップを順番に実行するエンジン
├── registry.py        # ActionRegistry: action_type -> 実行関数の辞書
├── scheduler.py       # WorkflowScheduler: APScheduler で cron 実行
├── run_logger.py      # RunLogger: 実行ログを JSONL に記録
└── templating.py      # Jinja2 テンプレートレンダリング
```

### 実行フロー

1. **ワークフロー定義**
   - `workflows/*.yaml` で workflow 定義
   - trigger（manual/schedule）と steps を指定

2. **実行エンジン**
   - Executor が各 step を上から順に実行
   - Jinja2 でパラメータをテンプレートレンダリング
   - アクション実行結果を context に格納（次ステップで参照可能）

3. **スケジューリング**
   - WorkflowScheduler が schedule trigger の workflow を APScheduler に登録
   - FastAPI lifespan で起動/停止を管理

4. **ログ記録**
   - 実行結果を RunLogger で JSONL に追記
   - UI から実行履歴を参照

### アクション拡張

新しいアクションを追加する場合：

```python
# src/app/actions/your_action.py
from ..core.registry import register_action

@register_action("your_action_type")
async def your_action_handler(params: dict, context: dict) -> dict:
    """params と context から処理して結果を dict で返す"""
    result = do_something(params["key"])
    return {"your_output": result}
```

`src/app/actions/__init__.py` でインポートすれば自動登録される。

## よく使うコマンド

```bash
# アプリケーション起動（リロード有効）
py -3.13 -m uvicorn src.app.main:app --reload

# アプリケーション起動（本番）
py -3.13 -m uvicorn src.app.main:app --host 0.0.0.0 --port 8000

# テスト用ワークフロー実行（デバッグ用）
py -3.13 -c "from src.app.core.loader import WorkflowLoader; from src.app.core.executor import Executor; import asyncio; from pathlib import Path; loader = WorkflowLoader(Path('workflows')); executor = Executor(Path('.')); workflow, _ = loader.load_workflow('hello_world'); asyncio.run(executor.run(workflow))"
```

## ワークフロー定義（YAML）

```yaml
name: workflow_name
trigger:
  type: manual    # または schedule
  cron: "0 9 * * *"  # schedule の場合のみ
steps:
  - id: step_1
    type: log     # アクション名
    params:
      message: "Hello {{ now }}"  # Jinja2 テンプレート

  - id: step_2
    type: file_write
    params:
      path: "runs/output/{{ run_id }}.txt"
      content: "Result from step_1: {{ step_1.result }}"
```

### テンプレート変数

- `{{ run_id }}`: 実行ID（YYYYMMDD_HHMMSS_xxxx）
- `{{ workflow }}`: ワークフロー名
- `{{ now }}`: ISO8601 タイムスタンプ
- `{{ step_id.key }}`: 前ステップの結果参照（例: `{{ step_1.values }}` など）
- `{{ base_dir }}`: プロジェクトルートパス

## ディレクトリ構成

```
orbit/
├── src/app/
│   ├── main.py                  # FastAPI アプリケーション
│   ├── core/                    # コアロジック
│   │   ├── models.py
│   │   ├── loader.py
│   │   ├── executor.py
│   │   ├── registry.py
│   │   ├── scheduler.py
│   │   ├── run_logger.py
│   │   └── templating.py
│   ├── actions/                 # アクション実装（拡張可能）
│   │   ├── log.py
│   │   └── file_ops.py
│   └── ui/
│       └── templates/           # Jinja2 テンプレート
├── workflows/                   # ワークフロー定義（YAML）
├── runs/                        # 実行ログ / 出力ファイル
│   ├── YYYYMMDD.jsonl          # 日付ごとの実行ログ
│   └── output/                  # ワークフロー出力
├── secrets/                     # API キー等（Git 管理外）
├── .docs/
│   ├── workflow_mvp_plan.md     # MVP 計画書
│   └── update.md                # 開発進捗
└── requirements.txt
```

## 開発時の注意

### 1. アクション追加時
- `ActionRegistry.register_action` デコレータを使用
- 戻り値は `dict` 型（複数の出力を辞書で返す）
- 例外は適切にログして dict に error キーで返す

### 2. UI テンプレート修正時
- Jinja2 テンプレートは `src/app/ui/templates/` に配置
- HTMX で非同期処理（`hx-post`, `hx-target` 等）
- Tailwind CSS CDN を使用（ローカル CSS 不要）

### 3. Workflow 定義追加時
- `workflows/*.yaml` にファイルを追加するだけで自動認識
- YAML バリデーションエラーはダッシュボードに表示

### 4. ログ確認
- stdout: ログレベル INFO 以上が出力
- JSONL ファイル: `runs/YYYYMMDD.jsonl` に実行結果を記録

## APIキー設定

ORBIT は環境変数を優先してAPIキーを読み込みます。

### 設定方法

1. `.env.example` を `.env` にコピー
2. 各APIキーを設定

```bash
cp .env.example .env
# .env を編集
```

### 環境変数一覧

| 環境変数 | 説明 | 必須 |
|---------|------|------|
| `GEMINI_API_KEY` | Gemini API キー | ai_generate アクション使用時 |
| `ARAICHAT_API_KEY` | ARAICHAT 統合APIキー | araichat_send_message アクション使用時 |
| `ARAICHAT_ROOM_ID` | ARAICHAT デフォルトルームID | araichat_send_message アクション使用時 |
| `GOOGLE_APPLICATION_CREDENTIALS` | Google サービスアカウントJSONパス | sheets_* アクション使用時 |

### フォールバック

環境変数が設定されていない場合、以下のファイルから読み込みます：

- Gemini: `secrets/gemini_api_key.txt`
- ARAICHAT: `secrets/araichat_api_key.txt`
- Google Sheets: `secrets/google_service_account.json`

**推奨**: 環境変数での設定を推奨します。

## Cron 式の例

```
# 毎日 9:00
0 9 * * *

# 毎週月曜 10:00
0 10 * * 1

# 毎時間 0 分
0 * * * *

# 毎分
* * * * *

# 毎月初日 0:00
0 0 1 * *
```

## API エンドポイント（デバッグ用）

```
GET  /                                  # ダッシュボード
GET  /workflows/{name}                  # ワークフロー詳細
GET  /runs                              # 実行履歴一覧
POST /api/workflows/{name}/run          # 手動実行
GET  /api/scheduler/jobs                # 登録済みジョブ一覧
POST /api/scheduler/reload              # ワークフロー再読み込み
```

## 次のフェーズ（Day 5 以降）

- Day 5: Google Sheets Read アクション実装
- Day 6: AI アクション実装（Gemini）
- Day 7-8: UI 仕上げ
- Day 9-10: 運用対応（タイムアウト、ログローテーション）
