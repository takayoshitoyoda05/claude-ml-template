# 完全レポート: no-guess 規律と完全トレース(pipeline/20260724-full-trace)

生成: 2026-07-24(手順8.5 の初運用。本レポート自身が今回実装した機能の成果物)

## 1. 概要

full-trace-spec.md に基づき、no-guess 規律(推測禁止)・完全ログ(フックによる機械記録)・完全レポート(evidence/ + report.md の2層)を実装した。変更は 19 ファイル([evidence/diff.patch](evidence/diff.patch))で、フック5本の新規 Python と settings.json 配線、エージェント規律の Markdown、手順8.5 を含む。全レビュー(Codex・Spec軸・Standards軸・セキュリティスキャン・Fable 最終ゲート)を通過済み。

## 2. 時系列

コミット単位の正確な履歴は [evidence/commits.txt](evidence/commits.txt)、各段のユーザー発言時刻は [evidence/transcript.jsonl](evidence/transcript.jsonl) に記録されている。

1. **計画**: planner が計画を作成(手順3)。spec-checklist(手順3.3)が「transcript・実行ログがマスキングなしでコミット対象になる」矛盾を検出し NEEDS_WORK → design-interview 限定モードでユーザーが「report_gen で全コピーをマスク」を承認 → READY
2. **計画承認**(手順4): ユーザー「進めていいよ」。スキャンのコスト承諾は依頼文に含まれていた(「スキャンのトークン消費は了解済み」)
3. **並列実装**(手順5): 初の3グループ worktree 並列(A=フック5本+verify-hooks / B=規律MD5件 / C=手順8.5・README等5件)
4. **レビューと差し戻し**(手順5.5〜7): 各グループに Codex+2軸レビュー。B は1回、C は1回、A は2回+磨き1回の差し戻しを経て全グループ両軸 PASS
5. **統合**(手順6.5): 3ブランチを --no-ff マージ、統合テスト(verify-hooks・pytest 7・gitignore・マスキング)全PASS。統合後の Codex レビューでグループ間の不整合2件を検出し修正
6. **配線**(Step 16): ユーザーが `_staging_settings_hooks.py` を実行し、settings.json に PostToolUse/SubagentStop を配線 → コミット。直後から action_log が本セッションで発火開始([evidence/actions.jsonl](evidence/actions.jsonl) の実データがその証拠)
7. **セキュリティスキャン**(手順6.6): 依頼文の承諾により無人実走。候補2件をパネルが 0/3 で棄却、確定0件・verified(CLAUDE-SECURITY-20260724-013511/)
8. **磨き**(手順6.7): グループA の refactor コミット(d83596c: main 分割 C19→A2・prune 共通化)が磨きの実体。保護領域のため追加ステージングは行わない判断
9. **最終ゲート**(手順6.8): final-gate(Fable)が APPROVE
10. **完全レポート**(手順8.5): 本レポート生成

## 3. 各エージェントの判断理由

- **planner**: 設計書の手順番号衝突(7.5)を 8.5 に適応、settings.json のステージング方式、gitignore の negation 方式を事前調査で確定。当初「保護は settings.json のみ」「settings はコミット外」と誤認し、後にレビューで訂正された(§5参照)
- **spec-checklist**: 一貫性次元で evidence の秘密漏洩リスク(MEDIUM)を検出。5次元中4次元は OK
- **Codex クロスレビュー**: 計画7件・B4件・C4件・A5件・統合2件+Blocker(配線)を指摘。全件が evaluator の実測検証を経て解消または根拠つき棄却
- **evaluator(Spec軸)**: A でセッション混入・symlink 越境・evidence 残留・オフバイワンを**実測再現**し、修正後に同一手順で逆確認。B/C は設計書突合と grep 検証
- **evaluator-standards**: A で _mask.py と _common.py のパターンドリフト(_common 自身の docstring が警告する事故)を発見し共通化を主導。main の複雑度悪化(C19)も radon 実測で検出し分割させた
- **final-gate(Fable)**: 「記録の完全性の過大主張がないか」「ステージング手順の健全性」を重点確認して APPROVE

## 4. 人間の承認コンテキスト

時刻は [evidence/transcript.jsonl](evidence/transcript.jsonl)(ユーザー発言)および [evidence/commits.txt](evidence/commits.txt)(コミット日時)を参照。

| 承認・判断 | 内容 |
|---|---|
| スキャンのコスト承諾 | 依頼文に「スキャンのトークン消費は了解済み」を明記(承諾前倒し方式の正規運用) |
| spec-checklist 指摘の解消方針 | 選択肢3案から「report_gen で全コピーをマスク(推奨案)」を選択 |
| 計画承認 | 「進めていいよ」(手動承認。CLAUDE_AUTO_APPROVE 無効) |
| フック配置(3回) | `_staging_place_hooks.py` を3回実行(初回配置・レビュー修正版・磨き版)— 保護領域への書き込みは全てユーザーの手で実施 |
| settings.json 配線 | `_staging_settings_hooks.py` を実行(Step 16) |

## 5. 発生した問題と対処

- **計画の前提誤り2件**: (1)「ガード保護は settings.json のみ」→ 実際は .claude/hooks/ 全体が保護されており、gen-A が着手時に発見。ステージング+ユーザー実行方式に切り替え。(2)「settings 変更はコミット外」→ settings.json は git 追跡対象と判明し、配線をコミットする方針に訂正
- **base64 ステージングの不採用**: 当初案の base64 埋め込みは自動モード分類器にブロックされ、ユーザーが実行前に目視できる素の Python ファイル方式に変更
- **gen-A のセッション上限失陥**: 最終コミット直前にサブスク上限に到達。リーダーが verify-hooks 確認とコミット(d83596c)を代行し、両軸が事後確認
- **統合後の不整合2件**: README.txt が report_gen の事前クリアで消える順序問題/stats.json に無いテスト数の出所 — 統合 Codex レビューで検出し文書修正
- **スキップ・省略**: なし(全工程実行。6.7 は d83596c を実体とする判断を明記)

## 6. 証拠

すべて本ディレクトリの evidence/ 配下(機械生成・マスキング済み・短縮ゼロ)。

| ファイル | 内容 | 統計([evidence/stats.json](evidence/stats.json)) |
|---|---|---|
| [diff.patch](evidence/diff.patch) | 全差分 | changed_files: 19 |
| [commits.txt](evidence/commits.txt) | コミット一覧(--stat) | — |
| [actions.jsonl](evidence/actions.jsonl) | 本セッションのツール実行記録(session_filter: bc4ed4bd) | actions_entries: 90 |
| [agents.jsonl](evidence/agents.jsonl) | サブエージェント委譲記録 | agents_entries: 8 |
| [transcript.jsonl](evidence/transcript.jsonl) | セッション全記録(マスキング済み) | transcript_lines: 5537 |
| [test-output.txt](evidence/test-output.txt) | 最終テスト完全出力 | 7 passed(test-output.txt 末尾より引用) |

注記: actions.jsonl / agents.jsonl は Step 16 の配線以降の記録(それ以前の本パイプラインの行動は transcript.jsonl が完全記録)。transcript の特定は logs/actions のファイル名 session 8桁(bc4ed4bd)の前方一致で一意に成功(曖昧一致なし)。
