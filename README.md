# ORBIT (MVP)

n8n ライクなワークフロー実行エンジン（MVP）。YAML でワークフローを定義し、手動実行またはスケジュール実行できます。DB なし・ローカル駆動で、実行ログは JSONL で保存されます。

## できること

- YAML でワークフロー定義（manual / schedule トリガー）
- ステップを順番に実行し、結果を context に格納
- Jinja2 テンプレートでパラメータを動的に展開
- APScheduler による cron スケジュール実行
- 実行ログを JSONL に記録・UI で参照
- UI からワークフローの参照・編集・実行
- AI（Gemini）によるテキスト生成・判定
- Excel/Google Sheets の読み書き
- ファイル操作（読み書き、コピー、移動、削除、リネーム）
- AIを使わない判定アクション（完全一致、部分一致、正規表現、数値比較）

## 動作環境

- Python 3.13+（python install manager 前提）
- Windows を想定（`py -3.??` 形式で起動）

## セットアップ

```bash
# 1) 仮想環境作成（未作成の場合）
py -3.13 -m venv .venv

# 2) 仮想環境有効化（PowerShell）
.\.venv\Scripts\Activate.ps1

# 3) 依存関係インストール
pip install -r requirements.txt
```

環境変数は `.env` または `.env.example` を参照してください。

## 起動

```bash
# 開発起動（ホットリロード）
py -3.13 -m uvicorn src.app.main:app --reload

# 本番起動
py -3.13 -m uvicorn src.app.main:app --host 0.0.0.0 --port 8000
```

## ディレクトリ構成

```
orbit/
├── src/app/                 # アプリケーション本体
│   ├── main.py              # FastAPI エントリ
│   ├── core/                # 実行エンジン/スケジューラ等
│   ├── actions/             # アクション実装
│   └── ui/                  # UI テンプレート/静的ファイル
├── workflows/               # ワークフロー定義（YAML）
├── runs/                    # 実行ログ / 出力
├── secrets/                 # API キー等（Git 管理外）
├── .docs/                   # ドキュメント運用
└── requirements.txt
```

## ワークフロー定義（YAML）

```yaml
name: hello_world
trigger:
  type: manual
steps:
  - id: step_1
    type: log
    params:
      message: "Hello {{ now }}"

  - id: step_2
    type: file_write
    params:
      path: "runs/output/{{ run_id }}.txt"
      content: "Result from step_1: {{ step_1.result }}"
```

### 条件付きステップ（when）

`when` を指定すると、条件に一致した場合だけステップを実行します。
（一致しない場合はスキップ）

```yaml
steps:
  - id: judge_error
    type: ai_judge
    params:
      target: "{{ step_1.text }}"
      question: "このテキストにエラーが含まれているか"

  - id: on_error
    type: log
    when:
      step: judge_error
      field: result
      equals: "yes"
    params:
      message: "エラーが検出されました"
```

※ 文字列比較はデフォルトで **前後空白の除去 + 大文字小文字を無視** します。

### テンプレート変数

- `{{ run_id }}`: 実行ID（YYYYMMDD_HHMMSS_xxxx）
- `{{ workflow }}`: ワークフロー名
- `{{ now }}`: ISO8601 タイムスタンプ（JST）
- `{{ today }}`: 当日の日付（YYYY-MM-DD, JST）
- `{{ yesterday }}`: 前日の日付（YYYY-MM-DD, JST）
- `{{ tomorrow }}`: 翌日の日付（YYYY-MM-DD, JST）
- `{{ today_ymd }}`: 当日の日付（YYYYMMDD, JST）
- `{{ now_ymd_hms }}`: 実行時刻（YYYYMMDD_HHMMSS, JST）
- `{{ step_id.key }}`: 前ステップの結果参照（例: `{{ step_1.values }}`）
- `{{ base_dir }}`: プロジェクトルートパス

## 利用可能なアクション

### ログ

| アクション名 | 説明 |
|------------|------|
| `log` | ログ出力 |

### ファイル

| アクション名 | 説明 |
|------------|------|
| `file_read` | ファイル読み込み |
| `file_write` | ファイル書き込み |
| `file_copy` | ファイルコピー |
| `file_move` | ファイル移動 |
| `file_delete` | ファイル削除 |
| `file_rename` | ファイル名変更 |

### Excel

| アクション名 | 説明 |
|------------|------|
| `excel_read` | Excel ファイル読み込み |
| `excel_write` | Excel ファイル書き込み |
| `excel_append` | Excel ファイル追記 |
| `excel_create` | 新規 Excel ファイル作成 |

### Google Sheets

| アクション名 | 説明 |
|------------|------|
| `sheets_read` | スプレッドシート読み込み |
| `sheets_write` | スプレッドシート書き込み |
| `sheets_append` | スプレッドシート追記 |
| `sheets_create` | 新規スプレッドシート作成 |

### AI

| アクション名 | 説明 |
|------------|------|
| `ai_generate` | AI によるテキスト生成（Gemini） |
| `ai_judge` | AI による yes/no 判定（Gemini） |

### 判定（非AI）

| アクション名 | 説明 |
|------------|------|
| `judge_equals` | 完全一致判定 |
| `judge_contains` | 部分一致判定 |
| `judge_regex` | 正規表現判定（プリセット対応） |
| `judge_numeric` | 数値範囲判定 |

### その他

| アクション名 | 説明 |
|------------|------|
| `araichat_send_message` | ARAICHAT へメッセージ送信 |

## 環境変数

| 環境変数 | 説明 | 必須 |
|---------|------|------|
| `GEMINI_API_KEY` | Gemini API キー | ai_generate / ai_judge 使用時 |
| `ARAICHAT_API_KEY` | ARAICHAT API キー | araichat_send_message 使用時 |
| `GOOGLE_APPLICATION_CREDENTIALS` | Google サービスアカウントJSONパス | sheets_* 使用時 |

## アクション拡張

`src/app/actions/` に実装し、`__init__.py` で import すると自動登録されます。

```python
from ..core.registry import register_action

@register_action("your_action_type")
async def your_action_handler(params: dict, context: dict) -> dict:
    result = do_something(params["key"])
    return {"your_output": result}
```

## 実行ログ

- 実行ログは `runs/YYYYMMDD.jsonl` に追記
- UI の「実行履歴」から参照可能

## 主要 API（デバッグ用）

- `GET  /` ダッシュボード
- `GET  /workflows/{name}` ワークフロー詳細
- `GET  /runs` 実行履歴一覧
- `POST /api/workflows/{name}/run` 手動実行
- `GET  /api/scheduler/jobs` 登録済みジョブ一覧
- `POST /api/scheduler/reload` ワークフロー再読み込み

## 開発メモ

- 重要な変更は `.docs/update.md` に追記
- 追加ドキュメントは `.docs/` 配下で管理
