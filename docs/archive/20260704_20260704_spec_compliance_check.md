# 設計書適合チェックの仕組み(spec-compliance)

日付: 2026-07-04
状態: draft(design-interview 完了。実装計画待ち)
元ネタ: ideas/20260704-設計書適合チェック-v1.md

## 目的
設計書(docs/active/)通りに実装できているかを、漏れなく機械的に
チェックできる仕組みを claude-ml-template に追加する。
「LLMの自己申告」ではなく、構造(ID・フック・テスト・独立視点)で漏れを塞ぐ。

## 決定事項(design-interview で確定)

| # | 論点 | 決定 | 理由の要点 |
|---|---|---|---|
| Q1 | 要件の機械可読形式 | 設計書内の「## 受け入れ条件」Markdownテーブル | 人間の読み書きと機械パースを1ファイルで両立。二重管理を作らない。標準ライブラリの正規表現でパース可 |
| Q2 | 物理強制の発動条件 | 環境変数 `CLAUDE_SPEC_CHECK=1` のときのみ Stop フックで検査 | 既存の CLAUDE_ENFORCE_EVAL と同じ思想・同じ設定場所。無関係な軽作業を邪魔しない |
| Q3 | manual要件の承認 | 承認ファイル `.claude/spec/approvals.txt` を保護パス化し、ユーザーの `!` 実行(spec_approve.py)でのみ記録 | Claude による承認偽装・勘違い記入を物理的に不可能にする |
| Q4 | auto要件の判定方式 | 二段構え: evaluator の判定ファイル必須 + spec_gate がランダム抽出で再実行 | 実行コストと確実性のバランス。`CLAUDE_SPEC_RECHECK_N=all` で全件再実行に倒せる |
| Q5 | 独立相互検証(D) | spec-auditor エージェント(sonnet)を1体追加 | 証拠検証とスコープ外変更検出を独立コンテキスト1体でカバー。逆生成diffは偽陽性とコストで見送り |
| Q6 | テスト還元(C)の範囲 | 受け入れテスト事前生成 + カバレッジ連動まで。ミューテーション検査は見送り | 「テストはあるが中身が空」を検出。ミューテーションは初版には過剰 |
| Q7 | CIゲート | 必須。claude-init が workflow を自動配置 | セッション外の手動コミット・別マシンからの push もゲートする |

## 受け入れ条件テーブルの仕様(A)

設計書に「## 受け入れ条件」セクションを必須化し、以下の列を持つテーブルで書く。

| 列 | 意味 | 制約 |
|---|---|---|
| ID | R-001 形式の連番 | 設計書内で一意。欠番・重複はパースエラー |
| 要件 | 検証可能な主張1つ | 1行1要件。複合要件は分割する |
| 検証方法 | 実行コマンド(auto)または「(目視)」(manual) | auto は作業スコープ直下で実行可能なこと |
| 期待結果 | exit 0 / 数値条件(例: mean>0.01)/ 人間承認 | spec_gate が機械照合できる形式 |
| 種別 | auto / manual | |
| 対象 | カバレッジ確認する対象モジュール(auto のみ、任意) | 記載時は spec_gate が coverage で実行有無を確認 |

- design-interview / planner は、このテーブルなしの設計書を docs/active/ に進めない。
- 曖昧で検証コマンド化できない要件は design-interview 段階で分割・具体化する。

## コンポーネント構成

### 新規ファイル
| ファイル | 役割 |
|---|---|
| .claude/hooks/spec_gate.py | Stop フック(B)。CLAUDE_SPEC_CHECK=1 のとき: (1)docs/active/ の設計書から受け入れ条件テーブルをパース、(2)evaluator の判定ファイル(.claude/spec/verdict-*.md)が全要件を網羅しPASSかを検査、(3)auto要件からランダムN件(CLAUDE_SPEC_RECHECK_N、既定3、all で全件)を再実行して照合、(4)「対象」列のある要件は coverage で対象モジュールの実行有無を確認、(5)manual要件が approvals.txt で承認済みかを確認、(6)spec-auditor の監査ファイル(.claude/spec/audit-*.md)が存在し全件OKかを確認。1つでも欠ければ exit 2 |
| .claude/hooks/spec_approve.py | ユーザーが `! uv run python .claude/hooks/spec_approve.py R-003` で実行し、approvals.txt に「設計書名 要件ID 日時」を追記する。Claude 経由の書き込みは保護パスでブロックされる |
| .claude/agents/spec-auditor.md | 監査エージェント(D、sonnet)。実装の経緯を知らない独立コンテキストで、(1)要件ごとに判定ファイルの証拠(実行ログ・file:line)を検証、(2)diff を設計書と突き合わせてスコープ外変更を列挙、(3)結果を .claude/spec/audit-*.md に機械可読テーブルで出力 |
| templates/spec-gate.yml.template | GitHub Actions workflow 雛形。PR 時に spec_gate.py --ci を実行(CIモード: docs/active/ の全設計書について auto要件を全件再実行、manual は承認済み確認、判定・監査ファイルの網羅確認) |

### 既存ファイルの変更
| ファイル | 変更 |
|---|---|
| .claude/hooks/_common.py | PROTECTED_PATH_PATTERNS に approvals.txt を追加(spec_approve.py 経由以外の書き込み禁止)。受け入れ条件テーブルのパーサを共通化して spec_gate と verify-hooks から使う |
| .claude/skills/design-interview/SKILL.md | 完了時に受け入れ条件テーブルの生成を必須化(全決定を検証可能な要件に変換) |
| .claude/agents/planner.md | 設計書受領時: 受け入れ条件テーブルがなければ計画を作らず差し戻し。計画の実装手順に「auto要件の受け入れテストを実装前に書くステップ」(C)と要件ID⇔ステップ対応を必須化 |
| .claude/agents/evaluator.md | 判定を .claude/spec/verdict-*.md に要件IDごとの機械可読テーブルで出力(ID / 判定 / 実行コマンド / 実測値 / 証拠file:line)。全要件に PASS/FAIL/UNVERIFIABLE を必ず記入 |
| .claude/commands/ml-pipeline.md | 手順に spec-auditor を追加(evaluator ×2 の後)。CLAUDE_SPEC_CHECK=1 の案内 |
| claude-init.ps1 / .sh | .github/workflows/spec-gate.yml を自動配置(Q7: 必須)。.claude/spec/ を gitignore に追加(approvals.txt と verdict/audit はローカル運用。CI は再実行で判定するためコミット不要) |
| verify-hooks.ps1 / .sh | spec_gate のテスト追加(受け入れ条件R-101〜参照) |
| templates/settings.local.json.template | CLAUDE_SPEC_CHECK / CLAUDE_SPEC_RECHECK_N を追記 |
| README.md / CHANGELOG.md | 機能説明の追記 |

### 環境変数
| 変数 | 意味 | 既定 |
|---|---|---|
| CLAUDE_SPEC_CHECK | `1` で Stop 時の適合チェックON | OFF |
| CLAUDE_SPEC_RECHECK_N | 抽出再実行の件数。`all` で全件 | 3 |

## 全体フロー
1. brainstorm / design-interview → 設計書に受け入れ条件テーブル(A)
2. planner → 計画に要件ID⇔ステップ対応 + 受け入れテスト事前作成ステップ(A/C)
3. generator → 受け入れテストを先に書き、実装(C)
4. evaluator → 要件IDごとに verdict ファイル出力(B)
5. spec-auditor → 証拠検証 + スコープ外変更列挙 → audit ファイル出力(D)
6. manual要件 → ユーザーが spec_approve.py で承認(B)
7. Stop 時に spec_gate が全件を機械検査。欠けがあれば完了ブロック(B)
8. push 後は CI の spec_gate --ci が最終ゲート(B)

## 受け入れ条件

| ID | 要件 | 検証方法 | 期待結果 | 種別 | 対象 |
|---|---|---|---|---|---|
| R-101 | spec_gate: 全要件PASS+承認済み+監査OKの設計書で通過する | verify-hooks のテストケース | exit 0 | auto | .claude/hooks/spec_gate.py |
| R-102 | spec_gate: FAIL要件が1つでもあれば完了ブロック | verify-hooks のテストケース | exit 2 | auto | .claude/hooks/spec_gate.py |
| R-103 | spec_gate: verdict ファイルに要件IDの欠けがあればブロック | verify-hooks のテストケース | exit 2 | auto | .claude/hooks/spec_gate.py |
| R-104 | spec_gate: manual要件が未承認ならブロック | verify-hooks のテストケース | exit 2 | auto | .claude/hooks/spec_gate.py |
| R-105 | spec_approve 実行後は R-104 のケースが通過する | verify-hooks のテストケース | exit 0 | auto | .claude/hooks/spec_approve.py |
| R-106 | approvals.txt への Claude 経由書き込みは guard_scope がブロック | verify-hooks のテストケース | exit 2 | auto | .claude/hooks/guard_scope.py |
| R-107 | テーブルが崩れている(列不足・ID重複)場合は安全側に倒してブロック | verify-hooks のテストケース | exit 2 | auto | .claude/hooks/_common.py |
| R-108 | CLAUDE_SPEC_RECHECK_N=all で auto要件が全件再実行される | verify-hooks のテストケース | 実行ログに全ID | auto | .claude/hooks/spec_gate.py |
| R-109 | 対象列のある要件で対象モジュールが未実行なら coverage 検査で落ちる | verify-hooks のテストケース | exit 2 | auto | .claude/hooks/spec_gate.py |
| R-110 | claude-init が spec-gate.yml を配置する | init をテンポラリで実行して確認 | ファイル存在 | manual | |
| R-111 | ml-pipeline の手順に spec-auditor が組み込まれている | ml-pipeline.md の目視 | 人間承認 | manual | |
| R-112 | CLAUDE_SPEC_CHECK 未設定なら spec_gate は何もしない(既存動作を壊さない) | verify-hooks のテストケース | exit 0 | auto | .claude/hooks/spec_gate.py |

## リスク・実装上の注意
- **フックの保護パス制約**: .claude/hooks/ は自己書き換え防止で Claude が書けないため、
  spec_gate.py / spec_approve.py の配置はユーザーの手作業(または一時的なガード解除)が必要。
  実装計画にはこの手順を明記すること。
- **coverage 依存**: カバレッジ連動は coverage パッケージ前提。無ければ該当検査を
  スキップして警告(fail open。auto検証自体は落とさない)。
- **検証コマンドの実行コスト**: 重いテストは enforce_eval と同様の状態キャッシュ
  (前回PASS時のリポジトリ状態と一致ならスキップ)を spec_gate にも実装する。
- **spec_gate と enforce_eval の関係**: 併用可。enforce_eval は「評価コマンド1本」、
  spec_gate は「要件単位」のゲートで役割が異なる。
- **設計書が複数 active の場合**: spec_gate は docs/active/ 直下の全設計書を対象にする。
  作業スコープ(CLAUDE_WORK_SCOPE)配下の docs/active/ を優先。
