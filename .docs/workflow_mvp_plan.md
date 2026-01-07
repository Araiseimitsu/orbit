# Project Name **ORBIT** MVP 計画書（最小構成）

作成日: 2026-01-02  
対象: **n8nライク**なワークフロー実行アプリ（最小構成）  
目的: **スケジュール / Google Spreadsheet / AI 連携**を「直列ワークフロー」で動かすMVPを、**DBなし・ローカル駆動**で完成させる。

---

## 0. MVPの定義（今回つくる“できること”）

### できること（MVP）
- **スケジュールトリガー（cron）**でワークフローを実行できる
- **workflow.yaml**（またはworkflow.json）で、直列のステップを定義できる
- 実行ログを**ローカルファイル**に記録できる（JSONL）
- UIで以下ができる（HTMX + Tailwind CDN）
  - ワークフロー一覧表示（ローカルディレクトリから読み込み）
  - 1件のワークフロー詳細表示（YAML内容 / 最終実行結果）
  - 手動実行ボタン（Run）
  - 実行履歴表示（直近N件、ファイル読み取り）

### MVPでは“やらないこと”（スコープ外）
- 分岐（if）、ループ、並列、再試行ポリシーの高度化
- DB永続化、ユーザー認証、マルチテナント
- 複雑なノード編集UI（ドラッグ＆ドロップ）
- 大規模なプラグインマーケット風管理

---

## 1. 技術スタック（指定）

- Python 3.13+
- FastAPI
- Uvicorn
- HTMX
- TailwindCSS（CDN）
- （推奨）Pydantic / PyYAML / APScheduler（またはschedule + asyncio）

---

## 2. 画面要件（Jobs級 “simple, beautiful and intelligent”）

### UI方針（デザイン原則）
- **1画面1メッセージ**: 何をすれば良いか迷わせない
- **余白 > 装飾**: 情報密度より可読性
- **操作は最小**: 主要操作は「Run」だけに寄せる
- **状態が語る**: 成功/失敗/実行中が一目でわかる

### 画面一覧
1. **Dashboard（/）**
   - ワークフロー一覧（カード）
   - ステータス（最終実行: 成功/失敗/未実行、最終実行時刻）
   - 「Run」ボタン（HTMXで非同期実行）
2. **Workflow Detail（/workflows/{name}）**
   - YAML内容（折りたたみ可）
   - 直近実行履歴（最新5〜20件）
   - 「Run」ボタン
3. **Runs（/runs）**
   - 全ワークフローの実行履歴（フィルタ: workflow名）

---

## 3. データ/永続化（DBなし）

### ファイル構成（ローカル）
- `./workflows/` : ワークフロー定義（YAML）
- `./runs/` : 実行ログ（JSONL）
- `./secrets/` : APIキーなど（dotenv等、Git管理外）

### 実行ログフォーマット（JSONL 例）
- 1行1実行（追記のみ）
- 例:
```json
{"run_id":"20260102_083000_ab12","workflow":"daily_sheet_summary","status":"success","started_at":"2026-01-02T08:30:00+09:00","ended_at":"2026-01-02T08:30:08+09:00","steps":[{"id":"fetch","status":"success"},{"id":"ai","status":"success"}],"error":null}
```

---

## 4. ワークフロー定義（最小スキーマ）

### 4.1 形式（YAML推奨）
- 例: `workflows/daily_sheet_summary.yaml`
```yaml
name: daily_sheet_summary
trigger:
  type: schedule
  cron: "0 9 * * *"   # 毎日9:00
steps:
  - id: fetch_sheet
    type: google_sheet_read
    params:
      spreadsheet_id: "xxxx"
      range: "Sheet1!A1:D50"

  - id: summarize
    type: ai
    params:
      provider: "openai"
      model: "gpt-4o-mini"
      prompt: |
        次の表を要約して、重要トピックを3つ挙げてください:
        {{ fetch_sheet.values }}

  - id: save_text
    type: file_write
    params:
      path: "runs/output/{{ run_id }}.md"
      content: |
        # Summary
        {{ summarize.text }}
```

### 4.2 変数（テンプレ）
- `{{ run_id }}`: 実行ID
- `{{ step_id.output_key }}`: 直前の結果参照（例: `{{ fetch_sheet.values }}`）

※ MVPではテンプレは **Jinja2 1本**に統一が最も楽。

---

## 5. 実行エンジン（最小アーキテクチャ）

### 5.1 コンポーネント
- **Loader**: workflows/ からYAML読み込み、バリデーション
- **Scheduler**: cron→実行キュー投入
- **Executor**: stepsを上から順に実行
- **Action Registry**: `type` → 実行関数の辞書
- **Logger**: run JSONL追記 + stdout

### 5.2 実行フロー
1. スケジュール or 手動実行で run を作成
2. `context` に `run_id`, `workflow`, `now` を入れる
3. 各 step:
   - paramsをテンプレレンダリング
   - actionを呼ぶ
   - resultを `context[step_id] = result` に格納
4. 成否をrunログとして追記
5. UIへ結果返却（HTMX partial）

---

## 6. アクション（最低限）

### MVPに入れるアクション
1. `google_sheet_read`
   - Google Sheets API（Service Account推奨）
   - rangeを読む→`values`を返す
2. `ai`
   - OpenAI/Gemini等（どれか1つに絞ってOK）
   - promptを投げる→`text`を返す
3. `http_request`（任意、AI以外の連携拡張用）
4. `file_write`（結果保存）
5. `log`（デバッグ）

### アクションの戻り値（例）
- google_sheet_read: `{"values": [...], "rows": n}`
- ai: `{"text": "...", "raw": {...}}`

---

## 7. セキュリティ / 設定（ローカル前提の最小）

- `.env` に APIキーを置く（Git管理外）
- Service Account JSONは `./secrets/` に保存（Git管理外）
- 例:  
  - `OPENAI_API_KEY=...`
  - `GOOGLE_APPLICATION_CREDENTIALS=./secrets/sa.json`

---

## 8. 開発計画（MVPまでのタスク分解）

### ゴール
- 直列ワークフローが、**スケジュール**と**手動Run**の両方で動く
- UIで「一覧/詳細/実行/履歴」が見える

---

## 9. スプリント計画（おすすめ: 5日〜10日）

### Day 1: 土台づくり（起動とUIの骨格）
- [ ] FastAPIプロジェクト作成
- [ ] HTMX + Tailwind CDN を base.html に適用
- [ ] ルーティング: `/`, `/workflows/{name}`, `/runs`
- [ ] workflowsディレクトリ読込（一覧表示）

成果物:
- ブラウザでワークフロー一覧が見える

---

### Day 2: Workflow Loader & Validation
- [ ] YAMLロード（PyYAML）
- [ ] Pydanticモデルでスキーマ検証（name/trigger/steps）
- [ ] Detail画面でYAML表示

成果物:
- 不正なworkflowはUIでエラー表示（壊れた定義を見分けられる）

---

### Day 3: Executor（直列実行） + ログ（JSONL）
- [ ] `ActionRegistry` 追加（まずは `log`, `file_write` だけ）
- [ ] `Executor.run(workflow)` を実装
- [ ] `runs/{date}.jsonl` に追記
- [ ] UIのRunボタン（HTMX）で手動実行→結果表示

成果物:
- “Run”が押せて、実行履歴が残る

---

### Day 4: Scheduler（cron）
- [ ] APScheduler導入（またはCloud Scheduler相当を後で）
- [ ] workflow.trigger= schedule を登録
- [ ] 実行をバックグラウンドタスク化（FastAPI lifespanで開始）

成果物:
- 指定時刻に自動実行され、runログが増える

---

### Day 5: Google Sheets Read
- [ ] service accountでSheets read
- [ ] `google_sheet_read` action実装
- [ ] サンプルworkflowで値を取得→logに出す

成果物:
- Sheets→値を取得できる

---

### Day 6: AI Action（OpenAI or Gemini）
- [ ] AIクライアント1種に絞って実装
- [ ] promptテンプレレンダリング（Jinja2）
- [ ] Sheets→AI要約→file_write まで通す

成果物:
- 要件3つ（schedule / gsheet / ai）が最小で全通

---

### Day 7-8: UI仕上げ（Jobs級の整頓）
- [ ] 最終実行ステータス表示（成功/失敗/未実行）
- [ ] Detailに最新ログ表示（折りたたみ・読みやすい）
- [ ] エラー時の表示（“何が起きたか”を短く明快に）

成果物:
- 「触れる」「迷わない」UI

---

### Day 9-10: 仕上げ（運用に耐える最低限）
- [ ] タイムアウト設定（AI/HTTP）
- [ ] ログの肥大化対策（ローテ）
- [ ] README（起動方法・設定方法）
- [ ] サンプルworkflow 3つ同梱

成果物:
- MVP完了。社内デモできる状態

---

## 10. 受け入れ基準（Doneの定義）

- [ ] `uvicorn app.main:app --reload` で起動できる
- [ ] `workflows/*.yaml` が一覧に表示される
- [ ] 手動Runでワークフローが最後まで走る
- [ ] cronで指定時刻に自動実行される
- [ ] Google Sheets の range が読める
- [ ] AIで要約が生成される
- [ ] 実行ログが JSONL に残り、UIで閲覧できる
- [ ] UIがシンプルで、主要操作は迷わない（Runに集約）

---

## 11. ディレクトリ案（MVP）

```
mvp-workflow/
  app/
    main.py
    ui/
      templates/
        base.html
        dashboard.html
        workflow_detail.html
        runs.html
      static/              # MVPでは最小（必要なら）
    core/
      loader.py            # YAMLロード
      models.py            # Pydanticスキーマ
      executor.py          # 直列実行
      registry.py          # Action登録
      scheduler.py         # cron登録
      logging.py           # JSONL書き込み
      templating.py        # Jinja2レンダ
    actions/
      google_sheets.py
      ai.py
      file_ops.py
      http.py
      log.py
  workflows/
    sample_daily_sheet_summary.yaml
  runs/
    .gitkeep
  secrets/
    .gitkeep
  .env.example
  README.md
```

---

## 12. リスクと対策（MVPで潰す）

- **Google認証が詰まりやすい**
  - 対策: Service Account固定 + 読み取りのみから開始
- **AIのレスポンス遅延/失敗**
  - 対策: タイムアウト + エラーをrunログに必ず残す
- **UIが肥大化しがち**
  - 対策: “Run”中心。編集UIは捨てる（YAML直編集）

---

## 13. MVP後の拡張ロードマップ（次の一手）

- v0.2: Webhookトリガー（Apps Script → HTTP）
- v0.3: if / retry / timeout policy
- v0.4: ノード追加（Slack/Email/Drive）
- v0.5: DB永続化（Runs/Workflows管理）
- v1.0: 権限/監査/チーム運用

---

## 付録A: MVPサンプルユースケース

1. 毎朝9時、Google Sheetsの「前日実績」を取得  
2. AIで「重要ポイント3つ」と「異常値」を要約  
3. Markdownで保存し、必要ならSlack通知（次フェーズ）

---

以上。
