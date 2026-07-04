# Changelog

このプロジェクトの主な変更点を記録する。形式は [Keep a Changelog](https://keepachangelog.com/) に緩く準拠。

## [Unreleased]
### Security
- ガードの自己書き換え防止: .claude/hooks/ と settings.json / settings.local.json への Edit/Write・リダイレクト・tee をブロック(PROTECTED_PATH_PATTERNS)
- guard_scope のスコープ判定を修正: 前方一致による兄弟ディレクトリ(例: proj と proj-evil)の誤許可を解消、Windows の大文字小文字差異にも対応
- guard_bash の rm 検知をフラグ解析に変更: -fr / -r -f 等の表記ゆれも検知
- git push の強制push別記法(+refspec)をブロック
- git add の一括ステージ(. / -A / --all / *)をブロックし、パス限定を促す。拡張子・ファイル名の検知を境界一致にして誤検知(例: foo.key.md)を解消
- フックの matcher を拡張: PowerShell / NotebookEdit も guard 対象に
- checkpoint のバックアップ(会話ログ含む)を直近10世代のみ保持するよう掃除を追加

### Changed
- トークン節約: 全スキルの description を圧縮(全セッション常駐分)、planner.md をルール維持のまま文言圧縮

### Added
- regression-suite スキル: 実装後に影響範囲を広くカバーするテストを任意生成
- config-explain スキル: スコープ・評価強制設定の可視化
- GitHub Actions CI: push/PR時に verify-hooks を自動実行
- LICENSE(MIT)
- doctor.ps1 / doctor.sh: テンプレートとの差分検知(sync-check)
- examples/toy-project: パイプラインお試し用のサンプルプロジェクト
- スキル設計のリファクタ: 全スキルの description をトリガー条件のみに絞り、Claudeがdescriptionだけで行動する誤動作を減らした
- スキル間の連鎖強制: design-interview / planner がトレードオフを伴う決定を解消したら、adr スキルの使用を必須化
- 設計書からの知識自動スタック: design-interview と planner が、設計書・計画に含まれる用語をCONTEXT.md、設計判断をdocs/adr/、実験再現条件をEXPERIMENT_LOG.mdに自動追記

## 過去の主な変更(遡及記録)
- Planner / Generator / Evaluator の3分離パターンを構築
- evaluator を Spec軸(evaluator) / Standards軸(evaluator-standards) に分割
- スコープ制約とフック(guard_scope, guard_bash)による物理ガードを導入
- design-interview, brainstorm, diagnosing-bugs, tdd, adr, handoff,
  architecture-check の各スキルを追加
- 秘密情報ガード、実験ログ自動記録、Golden Baseline、Explore事前調査を追加
- CONTEXT.md によるドメイン用語共有を導入
- コンテキスト圧縮対策(checkpoint_before_compact, reinject_after_compact)を追加
- claude-update による差分反映、.gitignore自動設定を追加
