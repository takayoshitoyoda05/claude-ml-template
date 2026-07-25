# 計画: Agentic 制御パターンと人間コントロール層

- 設計書: `docs/drafts/control-patterns-spec.md`(design-interview による更新版。docs/active/ へは移動しない。理由は現状分析を参照)
- ブランチ: pipeline/20260725-control-patterns
- 作業スコープ: /home/toyod/claude-ml-template(リポジトリ直下)

experiment: false
(本実装はコード・ドキュメント変更のみで学習・実験を伴わないため、plan_gate の
チェック対象外であることを行頭で宣言する。箇条書きにすると plan_gate の正規表現
`^\s*experiment\s*:\s*false` に一致しないので、必ず独立した行に書く)

## 目的

設計書セクション1〜10 の全機能(リソース上限・goal による三値判定・失敗遷移表・
HITL 必須操作・規模ルータ・自律度レベル L1/L2/L3・permissions ask/deny)を
テンプレートに実装する。人間の統制手段を「全件承認」ではなく強さの階層
(deny > ask > plan_gate > HITL > CLAUDE_CONTROL_LEVEL)として機械化する。

## 現状分析

- 確認済み: 設計書に「## 受け入れ条件」テーブルは無い。代わりにセクション1〜10 が
  追記する markdown 断片・新規 python の全文・JSON 断片まで確定しており、
  セクション11 に機械照合可能な検証コマンド群がある。本計画は
  **セクション番号を要件IDの代用**としてトレーサビリティを取る。
- 確認済み: 設計書を docs/active/ へ移動してはならない。`_common.parse_acceptance_table`
  は「## 受け入れ条件」が無い設計書に対して `AcceptanceTableError` を送出し、
  `spec_gate.py`(L338-345)がそれを受けて exit 2 で全体をブロックする。
  現状 docs/active/ は空で、同種の受け入れ条件なし仕様書(branch-swarm-spec.md /
  full-trace-spec.md)も docs/drafts/ に残置されている。本計画も drafts 据え置きに従う。
- 確認済み: `.gitignore` L6 に `docs/` があり、`git ls-files docs/` の出力は空。設計書
  `docs/drafts/control-patterns-spec.md` も、パイプラインが生成する `docs/reports/<日時>/` も
  **git 管理外**。したがって設計書 L14-15 が指示する
  `git rm docs/drafts/control-patterns-spec.md` は実行できない
  (`fatal: pathspec did not match any files` になる)。
- 確認済み: **手順番号が設計書と現行 ml-pipeline.md でズレている**。設計書は
  「手順4(実装)」「### 6. 結果の集約」と書くが、現行(466行)では
  実装は `### 5. 実装`(L130)、結果の集約は `### 7. 結果の集約`(L373)。
  → **役割で対応付ける**(実装=手順5、結果の集約=手順7)。挿入する本文中の
  「(手順4のステップ承認)」という自己参照も「手順5」に直して書く。
- 確認済み: `.claude/hooks/` と `.claude/settings.json` は `_common.PROTECTED_PATH_PATTERNS`
  の保護対象。実測で guard_scope が exit 2 を返す(`templates/settings.local.json.template`、
  `.claude/agents/router.md`、`verify-hooks.sh`、`README.md`、`.claude/commands/ml-pipeline.md`、
  `.claude/improvements/invariants.md` は exit 0 で書き込み可)。
  → plan_gate.py と settings.json は **generator が書けない**。前例
  (`.claude/plans/20260724-worktree-guard.md` Step 3)に倣いユーザー手動適用にする。
- 確認済み: 設計書セクション9 の注記どおり、素朴にリポジトリ直下で plan_gate.py を
  実行するテストは**不安定どころか確実に失敗する**。設計書のコードをスクラッチに
  写して実測した結果、リポジトリ直下では exit 2(最新計画 `20260724-worktree-guard.md` が
  「学習|実験|train|epoch」を含み goal を持たないため)。空の一時ディレクトリでは exit 0。
  → 既存の `CG_TMP`(L149-159)/ `SPEC_FIXTURE`(L211)方式に倣い、
  一時ディレクトリに cd して実行する形で追加する。
- 確認済み: plan_gate.py のロジックは本機(Python 3.14 / uv 0.11.29)で意図通り動く。
  実測: 計画なし→0、`experiment: false`→0、`train_minutes: 999` vs `max_train_minutes: 120`→2
  (「リソース超過」メッセージ)、goal 未定義+実験語→2、上限内+goal 完備→0。
- 確認済み: `verify-hooks.sh` の末尾は L423-424 で `rm -rf "$SPEC_FIXTURE"` と
  `trap - EXIT` を実行し、EXIT トラップを解除している。新規テストで trap を
  張り直すと既存の後始末規約を壊すため、trap は使わず明示的に削除する。
- 確認済み: README 6節「ファイル一覧」は網羅的ではない(scout-*.md / action_log.py /
  agent_log.py / report_gen.py が未掲載)。設計書も追記を指示していないため、
  本計画では router.md / plan_gate.py をファイル一覧に追加しない(最小diff)。

## 変更対象

| ファイル | 区分 | 変更内容 | 設計書 |
|---|---|---|---|
| .claude/improvements/invariants.md | MOD | 「### 人間の介入ポイント」1行目に L3 / CLAUDE_AUTO_APPROVE の例外を明記(変更1)+ 末尾に「## リソース上限(resources)」と「## 人間の承認が必須の操作(HITL)」を追記(変更2) | S1 |
| .claude/agents/planner.md | MOD | 計画フォーマット表に cost_estimate / goal の2行追加、出力例節の末尾に YAML 例を追記 | S2 |
| .claude/hooks/plan_gate.py | NEW | Stop フック。リソース超過と goal 未定義をブロック(**ユーザー手動適用**) | S3 |
| .claude/settings.json | MOD | Stop フック配列の末尾に plan_gate.py を配線(**ユーザー手動適用**) | S3 |
| .claude/agents/evaluator.md | MOD | 「## goal との突き合わせ(実験計画の場合)」節を追記(既存レポート判定への写像表を含む) | S4 |
| .claude/agents/router.md | NEW | 規模判定の軽量ルータ(haiku) | S5 |
| .claude/commands/ml-pipeline.md | MOD | 手順0(ルーティング)/ 自律度レベル節 / 手順5冒頭の HITL / 手順5末尾のステップ承認 / 手順7末尾の失敗遷移表 | S6 |
| templates/settings.local.json.template | MOD | env に `"CLAUDE_CONTROL_LEVEL": "L2"` を追加 | S8 |
| verify-hooks.sh | MOD | plan_gate テストを一時ディレクトリ方式で追加 | S9 |
| verify-hooks.ps1 | MOD | 同上(Test-Hook + Push-Location 形式) | S9 |
| README.md | MOD | エージェント表 / フック表 / 環境変数表に各1行、3.20 節を新設 | S10 |

## 実装手順

| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| A-1 | 【テスト先行】plan_gate テストを追加(S9 対応)。`ABS_PLAN_GATE="$(pwd)/.claude/hooks/plan_gate.py"` を取り、`PG_TMP=$(mktemp -d)` に `cd` して `test_hook` 相当を実行し `plan_gate: passes when no plans dir` を exit 0 で検査、最後に `rm -rf "$PG_TMP"`。挿入位置は action_log/agent_log テスト(L426-428)の直後、集計ブロック(`echo ""`)の直前。**注意: trap を追加しない**(L424 で EXIT トラップが解除済みのため既存規約を壊す) | verify-hooks.sh | なし | A |
| A-2 | 同一ケースを `Test-Hook` の書式に合わせて追加(S9 対応)。`$AbsPlanGate = Join-Path (Get-Location).Path ".claude\hooks\plan_gate.py"`、`$PgTmp` を作成して `Push-Location`/`Pop-Location`、最後に `Remove-Item -Recurse -Force`。挿入位置は action_log/agent_log テストの直後・集計ブロックの直前。既存 `Test-CodexGate`(L149-163)の書式を踏襲する | verify-hooks.ps1 | なし | A |
| A-3 | plan_gate.py を設計書 L184-280 のコードそのままで新規作成(S3 対応)。**保護パスのため generator は書き込めない**(guard_scope が exit 2)。スクラッチに全文を用意し、**ユーザーが手動適用**する。適用後 `git add .claude/hooks/plan_gate.py`(明示パス指定の add は guard_bash を通る)。UTF-8(BOMなし)/LF/実行属性不要 | .claude/hooks/plan_gate.py | A-1 | A |
| A-4 | Stop フック配列(L62-87)の末尾、notify.py の直後に `uv run python .claude/hooks/plan_gate.py` の command オブジェクト(設計書 L286-289)を追記し、あわせて permissions に ask / deny を追加する(設計書 §7 L483-498。`allow` は既存のまま触らない)(S3・S7 対応)。**保護パスのためユーザーが手動適用**。適用後 `python -c "import json; json.load(open('.claude/settings.json'))"` で JSON 妥当性を確認 | .claude/settings.json | A-3 | A |
| A-5 | `./verify-hooks.sh` を実行し全PASS を確認(S9・S11 対応)。加えて検証方法節の「plan_gate ブロック挙動の一時ディレクトリ検証」を実行する | (実行のみ) | A-1〜A-4, B-1 | A |
| B-1 | (S1 変更1)「### 人間の介入ポイント」の1行目 L20 `- Planner の計画はユーザー承認なしに実装に進めない` を、設計書 L97-99 の3行版(L3 / CLAUDE_AUTO_APPROVE=1 + plan-reviewer 自動承認OK を例外とする)に**書き換える**。(S1 変更2)末尾(L33 の直後)に「## リソース上限(resources)」と「## 人間の承認が必須の操作(HITL)」を設計書 L107-130 のとおり追記。resources は yaml コードブロックで書く(plan_gate が `max_train_minutes` 等を正規表現で読むため、キー名と数値の書式を変えない)。**注意: invariants.md の変更は S1 が定める HITL 必須操作にあたるが、本変更は design-interview Q4 でユーザー承認取得済み。改めての承認は不要** | .claude/improvements/invariants.md | なし | B |
| B-2 | 「## 計画フォーマット」表(L54-62)の末尾に cost_estimate / goal の2行を追加し、「## 計画の実装手順の出力例」節(L90-112)の末尾に設計書 L151-171 の YAML 例と `experiment: false` の説明を追記(S2 対応)。設計書側の外側 ```markdown フェンスは引用のための囲いであり、本文には含めない | .claude/agents/planner.md | なし | B |
| B-3 | 「## goal との突き合わせ(実験計画の場合)」節を設計書 L299-327 のとおり追記(S4 対応)。**「### 既存のレポート判定への写像」小節(写像表 pass→PASS→手順7.5 / fail→FAIL→失敗遷移表「目標未達」/ inconclusive→NEEDS_REVISION→失敗遷移表「inconclusive」、および「verdict の PASS/FAIL/UNVERIFIABLE は変更しない」の一文)を必ず含める**。挿入位置は「## 評価レポート形式」(L41-44)の直後・「## verdict ファイルの出力」(L46)の直前(判定に関する記述をまとめるため)。既存の PASS/NEEDS_REVISION/FAIL 表記と verdict の表記そのものは書き換えない | .claude/agents/evaluator.md | なし | B |
| B-4 | router エージェントを設計書 L337-363 のとおり新規作成(S5 対応)。frontmatter は `name: router` / `tools: Read, Grep, Glob, Bash` / `model: haiku` | .claude/agents/router.md | なし | B |
| C-1 | 「## 手順」(L26)の直前に「## 自律度レベル(CLAUDE_CONTROL_LEVEL)」節(設計書 L398-417)を挿入し、「### 1. 作業スコープの確定」(L27)の直前に「### 0. ルーティング(規模判定)」(設計書 L373-390)を挿入(S6 変更1・2 対応)。**S 経路は「ブランチは手順1.5 に従い常に作成する(main への直接コミットは自律度レベルに関わらず行わない)」**、**M 経路は昇格時に「コミット済みの実装をブランチ上に保持したまま手順3へ進み、planner に `git diff` と evaluator の指摘全文を渡す」**を含める。自律度レベル節には**空文字列の扱い**(「明示的に設定されている」= 値が空文字列でないこと。template は全キーを `""` で出荷するため空文字列は未設定扱い。既存フックの `!= "1"` と同じ規約)を含める。**自律度レベル表の「(手順4のステップ承認)」は「(手順5のステップ承認)」に直す**(現行の手順番号に合わせる) | .claude/commands/ml-pipeline.md | なし | C |
| C-2 | 「### 5. 実装」(L130)の冒頭に HITL 実行前承認(設計書 L465-472)、同節の本文末尾(手順5.5 の直前)にステップ承認(設計書 L425-431)、「### 7. 結果の集約」(L373)の本文末尾(手順7.5 の直前)に失敗遷移表(設計書 L438-457)を追記(S6 変更3・4・5 対応)。**失敗遷移表には表の直後・feedback 記録の一文の直前に「適用範囲」注記(「目標未達」行は goal を持つ実験計画の三値判定 fail / guard_metrics 違反のみに適用。goal の無い計画は既存の「evaluator が FAIL(3回連続)」が適用。再試行回数は手順8の最大3イテレーションの内数)を必ず入れる**。設計書が言う「手順4」=現行の手順5、「手順6の直後/### 6. 結果の集約」=現行の手順7 | .claude/commands/ml-pipeline.md | C-1 | C |
| C-3 | env ブロック末尾(`"CLAUDE_REFACTOR_SWARM": "0"` の後)に `"CLAUDE_CONTROL_LEVEL": "L2"` を追加(S8 対応)。直前行にカンマを付ける。JSON 妥当性を `python -c "import json; json.load(open('templates/settings.local.json.template'))"` で確認 | templates/settings.local.json.template | なし | C |
| D-1 | 3.1 エージェント表(L649-659)に router 行、3.4 フック表(L718-739)に plan_gate.py 行、環境変数テーブル(L193-209)に CLAUDE_CONTROL_LEVEL 行を、設計書 L549 / L555 / L561 のとおり追加(S10 対応) | README.md | なし | D |
| D-2 | 3.19 節(L1084-1130)の直後・「## 4. テンプレートの育て方」(L1134)の直前に「### 3.20 自律度レベルと人間のコントロール」を新設し、設計書 L567-609 の本文(手段の階層表 / 自律度レベル表 / goal / 失敗遷移表 / ルーティング)を入れる(S10 対応)。既存の節番号付き見出し規約に合わせて `3.20` を付ける。data/ 以外のデータディレクトリ名の場合に settings.local.json で追加できる旨(設計書 L508-509)も本節に1行入れる(S7 の README 記載要求) | README.md | D-1 | D |

## 並列化判定

**並列化可能**(グループ A / B / C / D。編集ファイルがグループ間で完全に分離しているため)。

- グループ A(plan_gate 本体・配線・テスト): `.claude/hooks/plan_gate.py`, `.claude/settings.json`,
  `verify-hooks.sh`, `verify-hooks.ps1`
- グループ B(エージェント定義・不変条件): `.claude/improvements/invariants.md`,
  `.claude/agents/planner.md`, `.claude/agents/evaluator.md`, `.claude/agents/router.md`
- グループ C(フロー制御・テンプレート): `.claude/commands/ml-pipeline.md`,
  `templates/settings.local.json.template`
- グループ D(ドキュメント): `README.md`

**重要な実行上の制約**: グループ A は保護パス(`.claude/hooks/` と `.claude/settings.json`)を
含み、guard_scope が Edit/Write を物理ブロックする(実測 exit 2)。worktree の
チームメイトに出さず、**統合ブランチ上のメインリポジトリで、ユーザー手動適用を挟んで実行する**。
B / C / D は worktree で並列実装してよい。A-5(検証)は B-1(invariants の resources)が
マージされた後に実行する。

## 検証方法

設計書セクション11 の検証コマンド群(push を除く)を実行する。

```bash
# 1. 新規ファイルの存在確認 → 両方 OK が出れば PASS
test -f .claude/agents/router.md && echo "OK: router"
test -f .claude/hooks/plan_gate.py && echo "OK: plan_gate"

# 2. 各ファイルへの追記確認 → 各行がファイル名を出力すれば PASS
grep -l "model: haiku" .claude/agents/router.md
grep -l "max_train_minutes" .claude/improvements/invariants.md
grep -l "guard_metrics" .claude/agents/planner.md
grep -l "CLAUDE_CONTROL_LEVEL" .claude/commands/ml-pipeline.md
grep -l "失敗遷移表" .claude/commands/ml-pipeline.md
grep -l "ルーティング" .claude/commands/ml-pipeline.md
grep -l "ステップ承認" .claude/commands/ml-pipeline.md
grep -l "実行前承認" .claude/commands/ml-pipeline.md
grep -l "設定行為自体がユーザーの事前承認" .claude/improvements/invariants.md
grep -l "inconclusive" .claude/agents/evaluator.md
grep -l "CLAUDE_CONTROL_LEVEL" templates/settings.local.json.template
grep -l "CLAUDE_CONTROL_LEVEL" README.md

# 3. permissions の ask / deny → "OK: permissions ask/deny" が出れば PASS
python -c "
import json
s = json.load(open('.claude/settings.json'))
assert 'ask' in s['permissions'], 'ask がない'
assert 'deny' in s['permissions'], 'deny がない'
assert any('rm -rf' in d for d in s['permissions']['deny']), 'rm -rf の deny がない'
print('OK: permissions ask/deny')
"

# 4. JSON 妥当性 → 例外が出なければ PASS
python -c "import json; json.load(open('.claude/settings.json'))"
python -c "import json; json.load(open('templates/settings.local.json.template'))"

# 5. plan_gate が Stop に配線されたか → "OK: wired" が出れば PASS
python -c "
import json
s = json.load(open('.claude/settings.json'))
cmds = [h['command'] for g in s['hooks']['Stop'] for h in g['hooks']]
assert any('plan_gate.py' in c for c in cmds), 'plan_gate が未配線'
print('OK: wired')
"

# 6. フックテスト → 最終行が「全テストPASS」なら PASS
./verify-hooks.sh
```

**plan_gate ブロック挙動の一時ディレクトリ検証**(A-5。リポジトリ直下の
`.claude/plans/` の内容に依存させないため一時ディレクトリで実施する):

```bash
T=$(mktemp -d); mkdir -p "$T/.claude/plans" "$T/.claude/improvements"
cp .claude/improvements/invariants.md "$T/.claude/improvements/"
PG="$(pwd)/.claude/hooks/plan_gate.py"
# (a) experiment: false はスキップ → 期待 exit 0
printf 'experiment: false\n学習と実験の計画\n' > "$T/.claude/plans/p.md"
(cd "$T" && echo '{}' | uv run python "$PG"); echo "a=$?"
# (b) 実験語ありで goal 未定義 → 期待 exit 2(stderr に「goal が未定義」)
printf '学習ジョブを epoch 30 で回す\n' > "$T/.claude/plans/p.md"
(cd "$T" && echo '{}' | uv run python "$PG"); echo "b=$?"
# (c) goal 完備でもリソース超過 → 期待 exit 2(stderr に「リソース超過」)
printf 'cost_estimate:\n  train_minutes: 999\ngoal:\n  metric: rmse\n  target: 0.15\n  direction: minimize\n  baseline: 0.21\n' > "$T/.claude/plans/p.md"
(cd "$T" && echo '{}' | uv run python "$PG"); echo "c=$?"
rm -rf "$T"
```

期待結果: `a=0` / `b=2` / `c=2`、かつ (c) の stderr に
`リソース超過: train_minutes=999.0 が上限 max_train_minutes=120.0` が出る
(= B-1 で追記した invariants の resources を実際に読めている証拠)。

`verify-hooks.ps1` は本機(WSL、pwsh 未導入)で実行検証できない。既存
`Test-Hook` / `Test-CodexGate` の書式を踏襲した最小追加に留め、sh 版との
1対1対応を目視で確認する(既存前例と同じ受容リスク)。

## リスク

- **判定語彙の重複(解消済み)**: 設計書が追加する三値(pass / fail / inconclusive)は、
  evaluator の既存レポート判定(PASS / NEEDS_REVISION / FAIL)および verdict の
  (PASS / FAIL / UNVERIFIABLE)と併存する。design-interview により
  **S4 の写像表(pass→PASS / fail→FAIL / inconclusive→NEEDS_REVISION、verdict は不変)**で
  対応付けが確定した(B-3 で実装)。既存表記そのものは置換しない
  (置換すると ml-pipeline 手順7 の分岐と spec_gate の verdict 検査が壊れるため)。
- **検討した代替案1(不採用)**: 設計書を docs/active/ へ移動してから実装する
  (planner の標準手順)。→ 受け入れ条件テーブルが無いため、CLAUDE_SPEC_CHECK=1 の
  環境で spec_gate が AcceptanceTableError により全体をブロックする。drafts 据え置きを採用。
- **検討した代替案2(不採用)**: verify-hooks の plan_gate テストを設計書どおり
  リポジトリ直下で実行する。→ 実測で exit 2 となりテストが常時 NG。一時ディレクトリ方式を採用。
- **検討した代替案3(不採用)**: plan_gate.py / settings.json を generator が直接編集する。
  → guard_scope が保護パスとして物理ブロック(実測 exit 2)。ユーザー手動適用を採用。
- **検討した代替案4(不採用)**: verify-hooks にブロック側(exit 2)のテストも追加する。
  → 設計書が指定したテストは1件のみ。最小diff規律に従い verify-hooks への追加は1件とし、
  ブロック挙動は上記の一時ディレクトリ検証(計画の検証方法)で証拠を残す。
- **permissions.deny の副作用**: `Bash(curl *)` / `Bash(wget *)` / `Bash(rm -rf *)` の
  deny は allow より優先される。本テンプレートの既存 allow には該当コマンドが無く、
  verify-hooks は `rm -rf "$CG_TMP"` 等を**フック内ではなくスクリプト内**で実行するため
  影響を受けない(deny は Claude の Bash ツール呼び出しに効くもので、
  スクリプト内部のコマンドには効かない)。ただし今後エージェントが
  一時ディレクトリを `rm -rf` できなくなる運用上の制約が生じる。設計どおり採用する。
- **CLAUDE_CONTROL_LEVEL の未実装部分**: 本計画で追加するのはプロンプト(ml-pipeline.md)
  上の分岐定義であり、フックによる機械強制は伴わない。L1 のステップ承認は
  generator の遵守に依存する(設計書もその設計)。
- **README ファイル一覧(6節)への追記は行わない**: 既存一覧が scout-*.md /
  action_log.py 等を含まず網羅的でないことを確認済みで、設計書も指示していないため。
  網羅性を上げたい場合は別タスクにする。
- **未確認の仮定**: なし(手順番号・行番号・保護パス・plan_gate の挙動・
  spec_gate の挙動はいずれも実測で確認済み)。

## トレーサビリティ

| 設計書セクション | 内容 | 対応ステップ | 検証方法 |
|---|---|---|---|
| S1 | invariants の介入ポイント例外(変更1)+ resources / HITL(変更2) | B-1 | `grep -l "設定行為自体がユーザーの事前承認" .claude/improvements/invariants.md` / `grep -l "max_train_minutes" .claude/improvements/invariants.md` |
| S2 | planner に cost_estimate / goal | B-2 | `grep -l "guard_metrics" .claude/agents/planner.md` |
| S3 | plan_gate.py 新規 + settings.json 配線 | A-3, A-4 | plan_gate ブロック挙動の一時ディレクトリ検証(a=0/b=2/c=2)+ 配線確認スクリプト |
| S4 | evaluator の三値判定 + 既存レポート判定への写像 | B-3 | `grep -l "inconclusive" .claude/agents/evaluator.md` / `grep -l "既存のレポート判定への写像" .claude/agents/evaluator.md` |
| S5 | router エージェント | B-4 | `test -f .claude/agents/router.md` / `grep -l "model: haiku" .claude/agents/router.md` |
| S6 | ml-pipeline の手順0・自律度・ステップ承認・失敗遷移表・HITL | C-1, C-2 | `grep -l "ルーティング" / "CLAUDE_CONTROL_LEVEL" / "失敗遷移表" / "ステップ承認" / "実行前承認" .claude/commands/ml-pipeline.md` |
| S7 | settings.json の ask / deny | A-4 | `python -c "..."` で ask / deny / rm -rf を assert |
| S8 | settings.local.json.template | C-3 | `grep -l "CLAUDE_CONTROL_LEVEL" templates/settings.local.json.template` + JSON パース |
| S9 | verify-hooks へのテスト追加 | A-1, A-2, A-5 | `./verify-hooks.sh` が「全テストPASS」 |
| S10 | README への追記 | D-1, D-2 | `grep -l "CLAUDE_CONTROL_LEVEL" README.md` + 3.20 節の目視 |
| S11 | 検証と後始末 | A-5 + 下記「完了後のユーザー操作」 | 検証方法の全コマンド |

すべてのセクションに対応ステップがある。どのセクションにも対応しないステップは無い。

## 完了後のユーザー操作(本計画では実行しない)

設計書セクション11 の後半はユーザーの承認事項のため、計画の実装範囲に含めない。

- `git push`: ml-pipeline 手順9 のマージ判断でユーザーが決める(permissions.ask 追加後は
  `Bash(git push *)` が毎回確認対象にもなる)。
- **仕様書ファイル(`docs/drafts/control-patterns-spec.md`)の削除は計画に含めない**。
  理由1: 設計書 L14-15 が削除の前提を「verify-hooks 全PASS **かつ git push まで完了**」と
  定めており、push がユーザー承認事項である以上、削除もその後のユーザー操作になるため。
  理由2: 確認済みのとおり `docs/` は `.gitignore` 対象で `git ls-files docs/` は空。
  設計書 L14-15 の `git rm docs/drafts/control-patterns-spec.md` は**実行できない**
  (git 管理外のため `fatal: pathspec did not match any files`)。削除したい場合は
  通常の `rm docs/drafts/control-patterns-spec.md` であり、**コミットも push も発生しない**。
  同じ理由で、パイプラインが生成する `docs/reports/<日時>/` もローカル成果物であり
  リポジトリには入らない。

## 未確定事項(回答があれば計画に反映する。無ければ上記の既定の扱いで進行可能)

(旧1「evaluator の判定語彙の対応付け」は design-interview で確定し、設計書 S4 の
写像表として明文化されたため削除した。)

1. **`data/` 以外のデータディレクトリ名**: 設計書 L508-509 は「README に記載する」と
   だけ指示している。本計画は D-2(3.20 節)に1行入れる扱いにした。
   1節セットアップ側にも書くべきなら指示がほしい。

## 知識の自動スタック(確認結果)

- (a) CONTEXT.md: リポジトリ直下に CONTEXT.md は存在しない(テンプレート本体のため)。追記対象なし。
- (b) ADR: **作成済み** — `docs/adr/0003-control-level-and-failure-transitions.md`
  (design-interview で解消した5件の衝突(自律度レベルと不変条件、goal 三値と既存判定、
  失敗遷移表と既存イテレーション制限、S 経路とブランチ規律、環境変数の空文字列規約)の
  決定を記録)。計画側の判断(drafts 据え置き・保護ファイルのユーザー手動適用・
  一時ディレクトリ方式)は既存前例の踏襲のため追加 ADR は作らない。
- (c) EXPERIMENT_LOG: 本実装はコード・ドキュメント変更のみで学習・実験を伴わない
  (`experiment: false`)。追記対象なし。
