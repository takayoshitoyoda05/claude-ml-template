# Changelog

このプロジェクトの主な変更点を記録する。形式は [Keep a Changelog](https://keepachangelog.com/) に緩く準拠。

## [Unreleased]
### Security
- spec-compliance の3つの迂回経路を修正(セルフ監査での指摘対応)
  - guard_bash: エージェントの Bash/PowerShell 経由での `spec_approve.py` 実行をブロック
    (承認はユーザーの `!` 手動実行のみ。`!` は PreToolUse を通らないため影響しない)
  - `_common.py`: `.claude/spec/last_spec_pass.txt`(spec_gate のキャッシュマーカー)と
    `.claude/spec/design_hashes.txt` を PROTECTED_PATH_PATTERNS に追加
    (決定的な署名計算によるキャッシュ偽装・承認記録偽装を防止)
  - spec_gate/spec_approve: 計画承認時に設計書のハッシュを `design_hashes.txt` に記録し、
    Stop 時に照合。「唯一の要件ソース」である設計書(docs/active/)自体の改変・
    検証コマンドの無害化を検知してブロック(`--design <設計書名>` で再承認)

### Added
- spec-compliance(設計書適合チェック): 設計書(docs/active/)の「## 受け入れ条件」テーブルを
  唯一の要件ソースとして、Stop フックと CI で全要件PASS・承認・独立監査を機械検査する仕組みを追加
  - `.claude/hooks/spec_gate.py`: `CLAUDE_SPEC_CHECK=1` のとき、verdict/audit/approvals
    を検査し欠けがあれば完了をブロック。`--ci` でCIモード、`--docs`/`--spec-dir` でテスト用の
    ディレクトリ上書きに対応
  - `.claude/hooks/spec_approve.py`: ユーザーの `!` 実行でmanual要件を
    `.claude/spec/approvals.txt` に承認記録(Claude 経由の書き込みは保護パスでブロック)
  - `.claude/agents/spec-auditor.md` 新規: evaluator の判定を独立コンテキストで再検証し、
    スコープ外変更を列挙する監査エージェント
  - evaluator.md: 完了時に `.claude/spec/verdict-*.md`(要件IDごとの機械可読判定)を出力
  - planner.md: 受け入れ条件テーブルの無い設計書を差し戻し、テストファーストのステップと
    要件ID⇔実装ステップ対応を必須化
  - design-interview/SKILL.md: 完了時に受け入れ条件テーブル生成を必須化
  - ml-pipeline.md: spec-auditor を evaluator×2 の後に追加、CLAUDE_SPEC_CHECK を案内
  - `templates/spec-gate.yml.template`: PR/push時に `spec_gate.py --ci` を実行するCIワークフロー雛形
  - claude-init/update: `.github/workflows/spec-gate.yml` の自動配置、`.claude/spec/` の
    .gitignore追加
  - verify-hooks: spec-compliance のテストケース(R-101〜R-109, R-112)を追加
- regression-suite スキル: 実装後に影響範囲を広くカバーするテストを任意生成
- config-explain スキル: スコープ・評価強制設定の可視化
- GitHub Actions CI: push/PR時に verify-hooks を自動実行
- LICENSE(MIT)
- doctor.ps1 / doctor.sh: テンプレートとの差分検知(sync-check)
- examples/toy-project: パイプラインお試し用のサンプルプロジェクト
- スキル設計のリファクタ: 全スキルの description をトリガー条件のみに絞り、Claudeがdescriptionだけで行動する誤動作を減らした
- スキル間の連鎖強制: design-interview / planner がトレードオフを伴う決定を解消したら、adr スキルの使用を必須化
- 設計書からの知識自動スタック: design-interview と planner が、設計書・計画に含まれる用語をCONTEXT.md、設計判断をdocs/adr/、実験再現条件をEXPERIMENT_LOG.mdに自動追記

### Fixed
- spec_gate `--ci` が verdict/audit/approvals(gitignore対象でCIに存在しない)まで要求し、
  設計書があるとCIが必ず失敗する問題を修正。CIモードは auto要件の全件再実行+coverage検査のみで判定
- spec_gate のキャッシュがマーカーファイル自身を署名に含めていて毎回失効していた問題を修正
- `.claude/spec/` の .gitignore パターンを `**/.claude/spec/` に変更
  (CLAUDE_WORK_SCOPE 設定時に使われる作業スコープ配下の `.claude/spec/` も除外されるように)
- evaluator / spec-auditor に Write/Edit ツールを追加(verdict/audit ファイルの出力を
  Bash リダイレクト頼みにしない)。verdict/audit の出力先が作業スコープ配下であることを明記
- ml-pipeline.md が README の存在しない節(7.5)を参照し、環境変数の設定方法として
  古いシェル方式を案内していたのを settings.local.json 方式に修正
- repo_state_signature の重複実装(enforce_eval.py / spec_gate.py)を _common.py に一元化

### Security
- ガードの自己書き換え防止を強化: これまで Edit/Write とリダイレクト/tee しか塞げず、
  `cp`/`mv`/`sed -i`/`install`/`truncate`/単純 `rm`/`git rm` 等で保護パス(フック・設定・
  承認記録)を書き換え/削除できる穴があったのを塞いだ。リダイレクト検出を `>\|`(noclobber強制)や
  `1>`/`2>>`(fd指定)にも対応、危険 rm の対象判定を `${HOME}` 等の展開形にも拡張。
  併せて、これらが任意コード実行(`python -c`)を封じる完全な境界ではなく多層防御である旨を
  README に明記
- ガードの自己書き換え防止: .claude/hooks/ と settings.json / settings.local.json への Edit/Write・リダイレクト・tee をブロック(PROTECTED_PATH_PATTERNS)
- guard_scope のスコープ判定を修正: 前方一致による兄弟ディレクトリ(例: proj と proj-evil)の誤許可を解消、Windows の大文字小文字差異にも対応
- guard_bash の rm 検知をフラグ解析に変更: -fr / -r -f 等の表記ゆれも検知
- git push の強制push別記法(+refspec)をブロック
- git add の一括ステージ(. / -A / --all / *)をブロックし、パス限定を促す。拡張子・ファイル名の検知を境界一致にして誤検知(例: foo.key.md)を解消
- フックの matcher を拡張: PowerShell / NotebookEdit も guard 対象に
- checkpoint のバックアップ(会話ログ含む)を直近10世代のみ保持するよう掃除を追加

### Changed
- トークン節約: 全スキルの description を圧縮(全セッション常駐分)、planner.md をルール維持のまま文言圧縮

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
