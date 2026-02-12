# ORBIT (MVP)

n8n ライクなワークフロー実行エンジン（MVP）。YAML でワークフローを定義し、手動実行またはスケジュール実行できます。DB なし・ローカル駆動で、実行ログは JSONL で保存されます。

## できること

- **ビジュアルエディタ**: ノードをドラッグ＆ドロップで直感的にワークフロー作成
- **AI フロー自動構築**: 自然言語でワークフローを自動生成
- **YAML 定義**: manual / schedule トリガーで柔軟なワークフロー定義
- **ステップ実行**: 順番に実行し、結果を context に格納して次ステップで参照可能
- **テンプレート機能**: Jinja2 でパラメータを動的に展開
- **スケジュール実行**: APScheduler による cron スケジュール実行
- **実行履歴**: 実行ログを JSONL に記録・UI で参照・フィルタリング
- **条件分岐**: when 条件でステップをスキップ可能
- **AI 統合**: Gemini によるテキスト生成・判定・Web検索
- **データ連携**: Excel/Google Sheets/Notion の読み書き
- **ファイル操作**: 読み書き、コピー、移動、削除、リネーム
- **判定アクション**: 完全一致、部分一致、正規表現、数値比較
- **サブワークフロー**: ワークフローの再利用と呼び出し
- **インポート/エクスポート**: ワークフローの YAML ファイル入出力
- **バックアップ**: 自動バックアップ機能（最大10世代保持）

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

## Docker / Docker Compose で起動

Windows + Docker Desktop 前提で、そのまま起動できます。

```bash
# 1) .env を作成（未作成の場合）
copy .env.example .env

# 2) ビルドして起動（バックグラウンド）
docker compose up -d --build

# 3) ログ確認
docker compose logs -f
```

ブラウザで `http://localhost:8000` にアクセスしてください。

### 停止

```bash
docker compose down
```

### 主なマウント先（永続化）

- `./workflows` -> `/app/workflows`
- `./runs` -> `/app/runs`
- `./secrets` -> `/app/secrets`
- `./backups` -> `/app/backups`

### Docker 単体で起動

```bash
# 1) イメージ作成
docker build -t orbit:latest .

# 2) コンテナ起動
docker run -d --name orbit-app -p 8000:8000 --env-file .env -v "${PWD}/workflows:/app/workflows" -v "${PWD}/runs:/app/runs" -v "${PWD}/secrets:/app/secrets" -v "${PWD}/backups:/app/backups" orbit:latest
```

停止・削除:

```bash
docker stop orbit-app
docker rm orbit-app
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
| `excel_list_sheets` | Excel シート一覧取得 |

### Google Sheets

| アクション名 | 説明 |
|------------|------|
| `sheets_read` | スプレッドシート読み込み |
| `sheets_write` | スプレッドシート書き込み |
| `sheets_append` | スプレッドシート追記 |
| `sheets_list` | スプレッドシートのシート一覧取得 |

### Notion

| アクション名 | 説明 |
|------------|------|
| `notion_query_database` | Notion データベース検索 |
| `notion_create_page` | Notion ページ作成 |
| `notion_update_page` | Notion ページ更新 |

### AI

| アクション名 | 説明 |
|------------|------|
| `ai_generate` | AI によるテキスト生成（Gemini）、Web検索対応 |
| `ai_judge` | AI による yes/no 判定（Gemini） |

### 判定（非AI）

| アクション名 | 説明 |
|------------|------|
| `judge_equals` | 完全一致判定 |
| `judge_contains` | 部分一致判定 |
| `judge_regex` | 正規表現判定（プリセット対応） |
| `judge_numeric` | 数値範囲判定 |

### 制御フロー

| アクション名 | 説明 |
|------------|------|
| `subworkflow` | 他のワークフローを呼び出して実行 |

#### サブワークフロー

他のワークフローを呼び出して実行します。再利用可能なワークフローモジュールを作成できます。

```yaml
steps:
  - id: prepare_data
    type: log
    params:
      message: "Preparing data"
  
  - id: call_subworkflow
    type: subworkflow
    params:
      workflow_name: data_processing
      input_data: "{{ prepare_data.result }}"
  
  - id: use_result
    type: log
    params:
      message: "Result: {{ call_subworkflow.results.step_1.output }}"
```

**パラメータ:**

- `workflow_name` (必須): 呼び出すワークフロー名（YAMLファイル名）
- `max_depth` (オプション): 最大呼び出し深度（デフォルト: 5）
- `continue_on_error` (オプション): エラー時も続行するか（デフォルト: false）
- その他の任意のパラメータ: サブワークフローのcontextに渡されます

**出力:**

- `success`: 成功フラグ
- `status`: 実行ステータス (success/failed/skipped)
- `run_id`: サブワークフローの実行ID
- `results`: 各ステップの実行結果 `{step_id: {...}}`
- `error`: エラーメッセージ（失敗時）

**注意点:**

- 循環参照（ワークフローがお互いを呼び出す）は自動的に検出され、エラーになります
- 最大呼び出し深度を超えるとエラーになります
- 親ワークフローのステップ結果はサブワークフローに渡されません（カオスを防ぐため）
- 基本変数（`run_id`, `now`, `today` など）は自動的に引き継がれます

### その他

| アクション名 | 説明 |
|------------|------|
| `araichat_send_message` | ARAICHAT へメッセージ送信 |

## 環境変数

| 環境変数 | 説明 | 必須 |
|---------|------|------|
| `GEMINI_API_KEY` | Gemini API キー | ai_generate / ai_judge 使用時 |
| `ARAICHAT_API_KEY` | ARAICHAT API キー | araichat_send_message 使用時 |
| `ARAICHAT_ROOM_ID` | ARAICHAT デフォルトルームID | araichat_send_message 使用時（オプション） |
| `GOOGLE_APPLICATION_CREDENTIALS` | Google サービスアカウントJSONパス | sheets_* 使用時 |
| `NOTION_API_KEY` | Notion インテグレーショントークン | notion_* 使用時 |

**フォールバック**: 環境変数が設定されていない場合、以下のファイルから読み込みます：
- Gemini: `secrets/gemini_api_key.txt`
- ARAICHAT: `secrets/araichat_api_key.txt`
- Google Sheets: `secrets/google_service_account.json`
- Notion: `secrets/notion_api_key.txt`

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

## 主要 API

### UI エンドポイント

- `GET  /` ダッシュボード
- `GET  /workflows/new` ワークフロー新規作成（テンプレート選択）
- `GET  /workflows/new/visual` ビジュアルエディタ（新規作成）
- `GET  /workflows/{name}` ワークフロー詳細
- `GET  /workflows/{name}/edit` ビジュアルエディタ（編集）
- `GET  /runs` 実行履歴一覧

### API エンドポイント

- `POST /api/workflows/{name}/run` 手動実行
- `POST /api/workflows/{name}/stop` 実行中ワークフローを停止
- `POST /api/workflows/{name}/toggle` ワークフローの有効/無効切り替え
- `POST /api/workflows/{name}/delete` ワークフロー削除
- `POST /api/workflows/save` ワークフロー保存
- `POST /api/workflows/import` YAML ファイルからインポート
- `GET  /api/workflows/{name}/export` YAML ファイルとしてエクスポート
- `GET  /api/workflows` ワークフロー一覧取得
- `GET  /api/actions` 登録済みアクション一覧
- `POST /api/ai/flow` AI でワークフロー案を生成
- `POST /api/ai/expression` AI で Jinja2 テンプレート式を生成
- `POST /api/ai/params` AI でステップパラメータを生成
- `GET  /api/scheduler/jobs` 登録済みスケジュールジョブ一覧
- `POST /api/scheduler/reload` ワークフロー再読み込み
- `POST /api/scheduler/preview` cron の次回実行時刻をプレビュー
- `POST /api/logs/cleanup` ログファイルの手動クリーンアップ
- `GET  /health` ヘルスチェック

## 開発メモ

- 重要な変更は `.docs/update.md` に追記
- 追加ドキュメントは `.docs/` 配下で管理
