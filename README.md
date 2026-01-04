# ORBIT (MVP)

n8n ライクなワークフロー実行エンジン（MVP）。YAML でワークフローを定義し、手動実行またはスケジュール実行できます。DB なし・ローカル駆動で、実行ログは JSONL で保存されます。

## できること

- YAML でワークフロー定義（manual / schedule トリガー）
- ステップを順番に実行し、結果を context に格納
- Jinja2 テンプレートでパラメータを動的に展開
- APScheduler による cron スケジュール実行
- 実行ログを JSONL に記録・UI で参照
- UI からワークフローの参照・編集・実行

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
  - id: judge
    type: ai_generate
    params:
      prompt: "次の質問に Yes/No だけで答えてください: ... "

  - id: do_yes
    type: log
    when:
      step: judge
      field: text
      equals: "Yes"
    params:
      message: "Yes のときだけ実行"

  - id: do_no
    type: log
    when:
      step: judge
      field: text
      equals: "No"
    params:
      message: "No のときだけ実行"
```

※ 文字列比較はデフォルトで **前後空白の除去 + 大文字小文字を無視** します。

### テンプレート変数

- `{{ run_id }}`: 実行ID（YYYYMMDD_HHMMSS_xxxx）
- `{{ workflow }}`: ワークフロー名
- `{{ now }}`: ISO8601 タイムスタンプ
- `{{ step_id.key }}`: 前ステップの結果参照（例: `{{ step_1.values }}`）
- `{{ base_dir }}`: プロジェクトルートパス

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

