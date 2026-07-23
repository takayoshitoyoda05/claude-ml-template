# 実装計画: no-guess 規律と完全トレース(全ログ記録・完全レポート)

参照設計書: `/home/toyod/claude-ml-template/docs/drafts/full-trace-spec.md`
作業ブランチ: `pipeline/20260724-full-trace`(チェックアウト済み)

## 目的
3原則(no-guess=推測禁止 / 完全ログ=記録漏れゼロ / 完全レポート=短縮ゼロ)を、
モデルの善意でなくフック・スクリプト・プロンプト規律として実装する。
既存テンプレートに新規4ファイル+改修12ファイルを追加する。

## 現状分析(確認済みの事実)
- 確認済み: ml-pipeline.md の実手順は **7 結果の集約 / 7.5 spec-auditor(既存・衝突) / 8 イテレーション制限 / 9 マージ確認**。
  → 設計書の「7. 直後 / 8. マージ確認の直前」という記述は実態とズレる。完全レポートは **8.5** として
  `### 8. イテレーション制限`(L350-351)と `### 9. マージ確認`(L353-)の間に挿入する。
  設計書文中の「手順8(マージ確認)」参照は **9** に読み替える。
- 確認済み: `.claude/settings.json` は `_common.PROTECTED_PATH_PATTERNS` の `/.claude/settings.json` に一致し、
  エージェントの Edit/Write/Bash 変更系がブロックされる。→ セクション6は **gitignore 済みの `_staging_*.py`**
  を作成しユーザーに `!` 実行してもらう既存パターンで行う。この変更はローカル設定でありブランチのコミットに入らない。
- 確認済み: 現 settings.json の `PostToolUse`(L43-53)は matcher `Edit|Write|NotebookEdit` の auto_format のみ。
  action_log は matcher が異なるため **matcher 無し(全ツール対象)の新エントリ**として PostToolUse 配列に追加する。
  `SubagentStop` セクションは存在しない → `Stop` と同階層に新規追加する。
- 確認済み: `.gitignore` L6 は `docs/`(ディレクトリ丸ごと無視)。`!docs/reports/` を足しても親除外のため再包含が効かない。
  隔離リポジトリで検証済み: `docs/*` + `!docs/reports/` + `logs/` の形なら docs/reports/ が追跡可能・docs/drafts 等は無視継続。
- 確認済み: リポジトリに pyproject.toml が無く、`uv run python -m pytest` は "No module named pytest" で失敗。
  `uv run --with pytest python -m pytest` は pytest 9.1.1 で成功。→ report_gen.py の pytest 実行行は
  `["uv","run","--with","pytest","python","-m","pytest","tests/","-v"]` に修正する(設計書コードのままでは失敗)。
- 確認済み: 既存フックは stdlib のみ・`json.load(sys.stdin)`・`main()`/`if __name__`・Google風docstring。
  秘密情報パターンは `_common.SECRET_CONTENT_PATTERNS`(guard 用、キャプチャ無し)に一元化。
  → `_mask.py` はマスキング用にキャプチャ群+key=value 置換が必要で構造が異なるため、設計書コード通り独立定義する
  (重複ではなく用途差。DRY より spec 忠実・最小diffを優先)。
- 確認済み: 改修対象のうちガード保護は settings.json のみ。`.claude/rules/`・`agents/`・`skills/`・`commands/`・
  `templates/`・`verify-hooks.*`・README・CHANGELOG・.gitignore は非保護でEdit可能。
- 確認済み: python-style.md の実在パスは `.claude/rules/python-style.md`。
- 確認済み: README のフック表は 3.4 節(L682付近、auto_format 行 L692)、環境変数表は L194-207(末尾 CLAUDE_FINAL_GATE)、
  spec-compliance 節が L211-。新2節はフック表(3.4)の直後に挿入する。
- 確認済み: verify-hooks.sh は `test_hook "名前" 'JSON' "パス" 期待exit`(L5定義)、末尾に集計。
  verify-hooks.ps1 は `Test-Hook` 形式・末尾に集計。両者とも集計ブロックの直前に追加する。

## 変更対象

| ファイル | 種別 | 変更内容 |
|---------|------|---------|
| .claude/hooks/_mask.py | NEW | 秘密情報マスキング共通モジュール(設計書§2コード通り) |
| .claude/hooks/action_log.py | NEW | PostToolUse フック。全ツール実行をJSONL記録(設計書§3) |
| .claude/hooks/agent_log.py | NEW | SubagentStop フック。委譲チェーン記録(設計書§4、複数キー名フォールバック) |
| .claude/hooks/report_gen.py | NEW | evidence機械集約スクリプト(設計書§5、pytest実行行を`--with pytest`に修正) |
| verify-hooks.sh | MOD | action_log/agent_log の空ペイロードexit0テスト2件追加 |
| verify-hooks.ps1 | MOD | 同上(Test-Hook形式、既存書式踏襲) |
| .claude/agents/planner.md | MOD | 「## 制約」末尾に no-guess 規律 |
| .claude/agents/generator.md | MOD | 「## 作業手順」末尾に tee必須、「## コーディングルール」末尾に no-guess |
| .claude/agents/evaluator.md | MOD | 「## 作業手順」の評価コマンド実行(step4)に tee必須 |
| .claude/skills/design-interview/SKILL.md | MOD | 「## 進め方」冒頭(step1直前)に no-guess大原則 |
| .claude/rules/python-style.md | MOD | 末尾に logging 推奨ルール |
| .claude/commands/ml-pipeline.md | MOD | 手順8.5(完全レポート生成)を8と9の間に挿入、手順9提示情報にレポートパス追加 |
| templates/settings.local.json.template | MOD | env に `"CLAUDE_ACTION_LOG": "1"` 追加 |
| .gitignore | MOD | `docs/`→`docs/*`+`!docs/reports/`、`logs/` 追加 |
| README.md | MOD | フック表3行・環境変数1行・新2節(no-guess/完全トレース) |
| CHANGELOG.md | MOD | [Unreleased] Added(2026-07-24)に1項目追加 |
| _staging_settings_hooks.py | NEW(gitignored) | settings.json に action_log/agent_log を追記するステージング。ユーザーが`!`実行 |

## 実装手順

| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 1 | `_mask.py` を設計書§2コード通り新規作成(stdlibのみ、`mask()`公開) | .claude/hooks/_mask.py | なし | A |
| 2 | `action_log.py` を設計書§3コード通り新規作成(CLAUDE_ACTION_LOG=0で無効、_mask利用、OSError握り) | .claude/hooks/action_log.py | Step1 | A |
| 3 | `agent_log.py` を設計書§4コード通り新規作成。**注: 設計書のデバッグdump(json.dump payload)は入れない**(本パイプライン内で発火せず検証不能なため。複数キー名フォールバックは残す) | .claude/hooks/agent_log.py | Step1 | A |
| 4 | `report_gen.py` を設計書§5コード通り新規作成。**変更2点**: (1) pytest実行行を`["uv","run","--with","pytest","python","-m","pytest","tests/","-v"]`に(素のuv runはpytest不在)、(2) spec-checklist承認済み修正 — `--transcript <パス>` 引数を追加し、transcript・runs/各ログ・test-output のコピー/書き込みに `_mask.mask()` を適用(diff/commitsは対象外)。evidence/のコミット安全性を保証 | .claude/hooks/report_gen.py | Step1 | A |
| 5 | 【テスト先行】verify-hooks に空ペイロードexit0テストを2件追加(sh/ps1両方、集計ブロック直前)。sh側は本機で実行確認、ps1は既存Test-Hook書式の最小追加(本機で構文検証不能=受容リスク) | verify-hooks.sh, verify-hooks.ps1 | Step2,3 | A |
| 6 | 「## 制約」末尾に no-guess 規律(設計書§1-1)を追記 | .claude/agents/planner.md | なし | B |
| 7 | 「## 作業手順」末尾に tee必須ルール(§7-1)、「## コーディングルール」基本原則末尾に no-guess(§1-2)を追記 | .claude/agents/generator.md | なし | B |
| 8 | 「## 作業手順」評価コマンド実行step(step4)に tee必須(§7-2)を追記 | .claude/agents/evaluator.md | なし | B |
| 9 | 「## 進め方」冒頭(step1直前)に no-guess大原則(§1-3)を追記 | .claude/skills/design-interview/SKILL.md | なし | B |
| 10 | 末尾に logging 推奨ルール(§7-3)を追記 | .claude/rules/python-style.md | なし | B |
| 11 | 手順**8.5**(完全レポート生成)を`### 8`と`### 9`の間に挿入。設計書§8本文の「手順8(マージ確認)」は「手順9」に読み替え。手順9のユーザー提示リストにレポートパス`docs/reports/<日時>/report.md`を1項目追加(§8(d)) | .claude/commands/ml-pipeline.md | なし | C |
| 12 | env ブロックに `"CLAUDE_ACTION_LOG": "1"` を追記(既存キー不変) | templates/settings.local.json.template | なし | C |
| 13 | L6 `docs/` を `docs/*` + `!docs/reports/` に変更し、`logs/` を追加(§9-2)。`git check-ignore`で検証 | .gitignore | なし | C |
| 14 | フック表に3行、環境変数表に CLAUDE_ACTION_LOG 1行、新2節(no-guess/完全トレース)をフック表3.4直後に追記。§10本文の「手順7.5」は「8.5」に読み替え | README.md | なし | C |
| 15 | [Unreleased] `### Added(2026-07-24)` を新設し、完全トレース+no-guessの1項目を追加 | CHANGELOG.md | なし | C |
| 16 | `_staging_settings_hooks.py`(gitignored)を作成: 現settings.jsonを読み、PostToolUse配列にmatcher無しaction_logエントリ追加+SubagentStopセクション追加してWrite。**ユーザーに `! uv run python _staging_settings_hooks.py` 実行を依頼**。実行後 settings.json がJSON妥当か確認。この変更はローカル設定でコミットに含めない | _staging_settings_hooks.py, (.claude/settings.json はユーザー手動) | Step2,3 | D |

## 並列化判定
**並列化可能**(グループ A / B / C / D)。
- A=Pythonフック4本+verify-hooks(相互import・verifyが4本をテスト。同一の関心事で密結合)
- B=agents/skills/rules の Markdown 追記(相互に独立した別ファイル)
- C=ml-pipeline+template+gitignore+README+CHANGELOG(別ファイル同士、相互依存なし)
- D=settings.json(ガード保護・ユーザー手作業。他グループとファイル非重複)
4グループはファイル集合が完全に分離し、グループ間の実装依存が無い。
比較(実装コスト/リスク/検証しやすさ/変更耐性): 逐次でも総量は中規模で破綻しないが、A(Python検証が重い)と
B/C(Markdown中心で軽い)を並列化すると待ち時間を圧縮できる。整合リスクは低い(README§14がフックを「説明」するが、
文章記述はフック実体の有無に依存しない)。**唯一の統合点は最終検証(section 11 相当)で全グループ合流後に一括実行**するため、
並列化しても検証段で漏れは捕捉できる。保守側の判断として D はユーザー手作業を含むので独立ステップに隔離した。

## 検証方法(設計書§11を既知乖離で修正+fail-fast)
以下を `&&` 連結(fail-fast)で実行し、全て通れば PASS。

```bash
test -f .claude/hooks/_mask.py && echo "OK: _mask" && \
test -f .claude/hooks/action_log.py && echo "OK: action_log" && \
test -f .claude/hooks/agent_log.py && echo "OK: agent_log" && \
test -f .claude/hooks/report_gen.py && echo "OK: report_gen" && \
printf 'api_key=sk-abcdefghijklmnopqrstuvwx\n' | uv run python -c "
import sys; sys.path.insert(0, '.claude/hooks')
from _mask import mask
out = mask(sys.stdin.read())
assert 'sk-abcdefghijklmnop' not in out, 'マスキング失敗'
print('OK: masking ->', out.strip())" && \
grep -q "仮定する" .claude/agents/planner.md && echo "OK: planner no-guess" && \
grep -q "勝手に決めることが失敗" .claude/agents/generator.md && echo "OK: generator no-guess" && \
grep -q "8\.5" .claude/commands/ml-pipeline.md && echo "OK: pipeline 8.5" && \
grep -q "report_gen" .claude/commands/ml-pipeline.md && echo "OK: pipeline report_gen" && \
git check-ignore -q docs/drafts/full-trace-spec.md && echo "OK: docs/drafts ignored" && \
( git check-ignore -q docs/reports/x/report.md; test $? -eq 1 ) && echo "OK: docs/reports NOT ignored" && \
git check-ignore -q logs/actions/x.jsonl && echo "OK: logs ignored" && \
./verify-hooks.sh
```
(`sk-abcdefghijklmnopqrstuvwx` は `sk-` + 24桁英数字のダミーキー。マスキング後に元文字列が消えることを assert する)

期待結果: 各 `OK:` 行が出力され、`./verify-hooks.sh` 末尾が「全テストPASS」(exit 0)。

追加スモーク(report_gen が evidence を生成できること):
```bash
uv run python .claude/hooks/report_gen.py 20260724-smoke && \
test -f docs/reports/20260724-smoke/evidence/stats.json && echo "OK: evidence generated"
```
期待結果: `[report_gen] evidence generated: ...` と `OK: evidence generated`。
(スモーク生成物は検証後に手動削除。docs/reports/ は追跡対象なのでコミット前に要否を確認)

settings.json(ユーザー手作業後):
```bash
python -c "import json; json.load(open('.claude/settings.json'))" && echo "OK: settings.json valid"
```
期待結果: `OK: settings.json valid`(JSON妥当。PostToolUseにaction_log、SubagentStopにagent_logが存在)。

コミット案(各ステップ完了ごと。作業ブランチ pipeline/20260724-full-trace 上):
1-4: `feat(step 1..4): <各フック名>`  / 5: `test(step 5): 新フックの空ペイロードexit0テスト`
6-11,14,15: `docs(step N): <要約>`  / 12,13: `feat(step 12/13): <要約>`
16: コミットなし(ローカル設定。ステージング副産物 `_staging_*.py` は gitignore 済み)
最終: `git push` と設計書削除は**ユーザー明示指示まで行わない**(タスク指示#7)。

## リスク
- **SubagentStop/PostToolUse の stdin フィールド名がバージョン依存**: 新フックは settings.json 変更+セッション再読込後
  にしか発火せず、本パイプライン内で実ペイロードを確認できない。→ 防御的実装(設計書コードの複数キー名フォールバック)
  で進め、「初回実走時にフィールド名を確認する」を残課題として README トラブルシューティング(または本計画末尾)に明記。
  デバッグdumpは検証不能かつ副作用があるため入れない。
- **ps1 の構文を本機で検証不能**: 既存 Test-Hook 行の書式を踏襲した最小追加のみとし、受容リスクとする(設計書§6注記と同旨)。
- **未確認の仮定**: agent_log.py の `resolvedModel`/`agent_name` 等の実キー名。実走前は不明のためフォールバック順で吸収。
- **代替案1(settings.json を直接Edit)**: ガードにブロックされ不可 → 不採用。ステージング+ユーザー`!`実行が唯一成立する経路。
- **代替案2(.gitignore を `!docs/reports/` だけ追記)**: 親 `docs/` 除外のため再包含が効かず docs/reports/ を追跡できない
  (隔離リポジトリで確認)→ 不採用。`docs/*` 形式に変更する案を採用。
- **代替案3(_mask.py を _common.SECRET_CONTENT_PATTERNS で共通化)**: guard 用パターンはキャプチャ群を持たず値マスクに使えず、
  構造改修が必要で minimal-diff に反する → 不採用。設計書コードの独立定義を採用。
- **report_gen のスモーク生成物**: docs/reports/ が追跡対象になったため、検証で作った `20260724-smoke/` を誤コミットしないよう
  検証後に削除する(検証方法の注記に反映済み)。
- 並列実装時の整合: README(C)がフック(A)を説明するが文章はフック実体に非依存。統合点は最終検証のみで漏れは捕捉可能。

## トレーサビリティ(設計書セクション→実装ステップ→検証)
設計書に「## 受け入れ条件」R-ID テーブルは無いため、セクション番号で対応付ける。

| 設計書セクション | 対応ステップ | 検証方法 |
|-----------------|------------|---------|
| §1-1 planner no-guess | Step 6 | `grep -q "仮定する" .claude/agents/planner.md` |
| §1-2 generator no-guess | Step 7 | `grep -q "勝手に決めることが失敗" .claude/agents/generator.md` |
| §1-3 design-interview no-guess | Step 9 | `grep -q "no-guess" .claude/skills/design-interview/SKILL.md` |
| §2 _mask.py | Step 1 | 存在確認 + マスキング単体(sk-...が消える) |
| §3 action_log.py | Step 2, 5 | 存在確認 + `test_hook '{}' action_log.py 0`(verify-hooks) |
| §4 agent_log.py | Step 3, 5 | 存在確認 + `test_hook '{}' agent_log.py 0`(verify-hooks) |
| §5 report_gen.py | Step 4 | 存在確認 + スモーク(evidence/stats.json 生成)+ マスク適用確認(ダミー秘密入りrunログがevidence/でマスクされる) |
| §6 settings.json フック追記 | Step 16 | `python -c json.load` でJSON妥当・両フック存在(ユーザー手作業後) |
| §7-1 generator tee | Step 7 | `grep -q "tee logs/runs" .claude/agents/generator.md` |
| §7-2 evaluator tee | Step 8 | `grep -q "logs/runs" .claude/agents/evaluator.md` |
| §7-3 python-style logging | Step 10 | `grep -q "logging" .claude/rules/python-style.md` |
| §8 ml-pipeline 手順8.5 | Step 11 | `grep -q "8\.5"` かつ `grep -q "report_gen"` |
| §9-1 template CLAUDE_ACTION_LOG | Step 12 | `grep -q "CLAUDE_ACTION_LOG" templates/settings.local.json.template` |
| §9-2 gitignore | Step 13 | `git check-ignore` で reports=非無視・drafts/logs=無視 |
| §9-3 verify-hooks | Step 5 | `./verify-hooks.sh` が「全テストPASS」 |
| §10 README 追記 | Step 14 | `grep -q "action_log" README.md` かつ `grep -q "no-guess 規律" README.md` |
| §11 検証・後始末 | 検証方法(本計画) | 上記 fail-fast チェーンが全 OK |
| (慣習) CHANGELOG | Step 15 | `grep -q "2026-07-24" CHANGELOG.md` |

全セクションに対応ステップと検証がある。対応の無いステップは無い。

## 残課題(実装完了後・初回実走時にユーザーへ引き継ぐ)
- 新フック(action_log/agent_log)は settings.json 反映+セッション再読込後の初回実走で
  初めて発火する。その初回に `logs/actions/*.jsonl` `logs/agents/*.jsonl` を1件開き、
  `tool`/`agent`/`model`/`duration_ms` 等が実ペイロードのキー名と合っているか確認する。
  ズレていればフォールバックのキー名を実キーに合わせて調整する。

## 知識の自動スタック確認結果
- (a) CONTEXT.md: 作業スコープ直下(リポジトリルート)に CONTEXT.md は存在しない(テンプレートのため)。追記先が無く N/A。
- (b) ADR: 設計判断はほぼ設計書に固定済み。唯一のローカル選択(gitignore を `docs/*`+negation にする)は
  制約由来の機械的修正で「後から変更しづらい」性質は弱く、本計画のリスク欄に代替案と不採用理由を記録済み。新規ADRは作成しない。
- (c) EXPERIMENT_LOG: 数値・シード・データセット・重みパスは無い。N/A。
