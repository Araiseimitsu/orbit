# ORBIT MVP 開発進捗

## 現在の状態
- **Day 7-8 完了** - UI 仕上げ完了

## 更新履歴
- 2026-01-12: ダッシュボードのフォルダトグルを左配置に変更し、開閉状態をローカル保存。
- 2026-01-12: ダッシュボードのフォルダ別グループ表示をトグルで開閉できるようにした。
- 2026-01-12: Runs の実行履歴一覧にワークフローのフォルダ名を表示。
- 2026-01-12: ダッシュボードの最新実行ステータス取得を一括化し、ログ走査のN+1を解消。読み込み時間の詳細ログも追加。
- 2026-01-12: ダッシュボードの検索対象にフォルダ名を追加。
- 2026-01-12: フォルダ入力の初期化順序を修正し、フローエディタでアクション/フローが表示されない不具合を解消。
- 2026-01-12: フローエディタにフォルダ入力欄を追加し、UIからフォルダを設定できるようにした。
- 2026-01-11: ダッシュボードの検索フォームとカードグリッドをモバイル向けに調整し、カードの横はみ出しを防止。
- 2026-01-11: ワークフローに folder メタデータを追加し、ダッシュボードでフォルダ別にグルーピング表示（未分類はフォルダ未設定）を実装。
- 2026-01-08: ワークフローのテンプレート式で `fromjson` / `tojson_utf8` を追加し、単一式は型（list/dict/int等）を保持して返すよう改善。Google Sheets/Excel の `values` 例も `{{ ai_generate_1.text | fromjson }}` に更新し、UIでコピーしやすくした。
- 2026-01-07: アクション/詳細パネルの上部余白をなくし、固定見出しが上端まで覆うようにレイアウトを整理。

- 2026-01-07: アクション/詳細パネルの固定見出しが上部の余白まで覆うようにして、スクロール内容が透けて見える問題を修正。
- 2026-01-07: フローエディタのパネル見出し/ツールバーの背景を不透明に戻し、スクロール内容が背後に透けないよう調整。
- 2026-01-07: フローエディタのアクション/詳細パネルの背景に色味を追加し、見出し背景も強調。
- 2026-01-07: フローエディタのアクション/フロー/詳細パネル内の見出しと中央のツールバーを固定し、ページ上部ヘッダーの固定は解除。
- 2026-01-07: フローエディタのヘッダーを固定表示にして、アクション/フロー/詳細のスクロール時も見失わないように調整。
- 2026-01-07: ページ遷移時のちらつき改善を実装。初期CSSをインライン化、ページフェードインアニメーション、HTMX/Alpine.jsの読み込み最適化。RunsページのView Detailsトグルを直接displayプロパティで制御するように修正し、イベント伝播問題を解決。
- 2026-01-06: ai_generate の同期処理をスレッド実行に切り替え、実行中の停止要求がブロックされないよう改善。
- 2026-01-06: Dashboard の手動Runに停止ボタンを追加し、実行中キャンセル（stoppedステータス）に対応。
- 2026-01-05: 共通テンプレート変数に today / yesterday / tomorrow / today_ymd / now_ymd_hms を追加。
- 2026-01-05: when 条件に match（equals/contains）を追加し、含む判定での条件分岐を可能にした。
- 2026-01-05: ai_generate に Web検索（google_search）対応を追加し、use_search パラメータで切り替え可能にした。
- 2026-01-05: AIフロー自動構築にWeb検索トグルを追加し、Gemini APIのgoogle_searchツール対応を実装。
- 2026-01-05: ビジュアルエディタに AI フロー自動構築パネルを追加し、Gemini を使ったフロー案生成APIを実装。
- 2026-01-05: Runs 画面にワークフローのフィルターUIを追加。ログクリーンアップを毎日実行するようスケジューラーに登録。インポート/トースト/詳細トグルのイベントをJSに集約し、テンプレートのインラインイベントを解消。
- 2026-01-04: ステップ条件（when）を追加し、条件一致時のみ実行・不一致時はスキップに対応。実行履歴の表示もスキップを反映。
- 2026-01-04: ARAICHAT 送信アクション名を `araichat_send_message` に統一し、旧 `araichat_send` の互換対応を削除。
- 2026-01-03: フローエディタの例チップが長いパスでも折り返すように調整。
- 2026-01-03: ARAICHAT 送信の files に単一パス文字列を許可（Windows パス対応）。
- 2026-01-03: トースト処理をmain.jsに移し、手動Run後のステータスバッジ更新と自動削除を安定化。
- 2026-01-03: ARAICHAT のベースURLを固定化（ARAICHAT_URL を廃止）。
- 2026-01-03: ARAICHAT 送信アクション（araichat_send）を追加。
- 2026-01-02: フローエディタでドラッグ順序が分かるよう、ノードに実行順バッジと詳細パネルの順序表示を追加。
- 2026-01-03: ワークフローの有効/無効（アクティブ/停止）切り替えを追加。スケジュール登録は有効時のみ。
- 2026-01-03: ダッシュボードにワークフロー名検索（部分一致）を追加。
- 2026-01-03: AIは `ai_generate` に統一し、要約ショートカット（ai_summarize）を廃止。ワークフロー例とフローエディタの定義を更新。
- 2026-01-03: Google Sheets の追記/上書きアクション（`sheets_append` / `sheets_write`）を追加。書き込み対応スコープに変更。
- 2026-01-03: ローカル Excel 連携（`excel_read` / `excel_write` / `excel_append` / `excel_list_sheets`）を追加。フローエディタのガイドも更新。
- 2026-01-03: フローエディタの設定ガイド内の例をクリックでコピーできるよう改善。
- 2026-01-03: `ai_generate` の `max_tokens` / `temperature` を文字列でも解釈できるよう型変換を追加。
- 2026-01-03: Runs 詳細の開閉を inline onclick から data 属性 + main.js のイベント委譲に切り替え。
- 2026-01-03: main.js の初期化を DOMContentLoaded 依存から即時起動可能にして、イベント未登録を回避。
- 2026-01-03: main.js 未読込時のフォールバックとして Help / Runs 詳細のイベント登録を base.html に追加。
- 2026-01-03: 旧サービスワーカーのキャッシュ影響を避けるため、base.html で Service Worker 解除とキャッシュ削除を実行。
- 2026-01-03: Runs 画面の JSON 出力を HTML エスケープして、AI 出力の HTML/CSS がページを壊す問題を修正。

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
- openai パッケージ追加
- テストワークフロー作成（ai_test, ai_generate_summary_test, ai_openai_test）

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
│       │   └── ai.py            # ai_generate
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
│   ├── ai_generate_summary_test.yaml # 要約テスト
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
