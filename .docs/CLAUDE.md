# CLAUDE.md

## プロジェクト目的
- ORBIT の MVP を構築し、YAML 定義のワークフローを手動/スケジュール実行できるようにする。

## 目標
- ワークフローの作成・実行・履歴閲覧が UI から行えること。
- ワークフロー拡張（アクション追加）が簡単であること。

## ルール
- UI は HTMX を中心に最小構成で実装。
- ワークフロー定義は `workflows/` 配下の YAML で管理。
- 重要な更新は `.docs/update.md` に追記。

## 活用技術
- Python 3.13
- FastAPI
- HTMX + Tailwind CSS (CDN)
- APScheduler
