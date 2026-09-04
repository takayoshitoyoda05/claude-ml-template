# 実装計画: SKILL.state 部分採用(ml-pipeline 構造化実行状態ファイル)

参照した設計書: `docs/active/20260904-skill-state-spec.md`(受け入れ条件 R-001〜R-017 が要件ソース)
関連 ADR: `docs/adr/0018-skill-state-partial-adoption.md`(既存・本計画で新規 ADR は起こさない)
ブランチ: `pipeline/20260904-skill-state`

experiment: false
# コード変更のみ。学習・実験を含まないため cost_estimate / goal は不要。

## 目的

ml-pipeline の再開が「散文サマリと推定手順番号」に依存している現状を、
検証済みの構造化状態ファイル `.claude/state/<slug>.json` を正とする運用に置き換える。
状態はモデルが更新し、フックがスキーマ検証・再注入・鮮度警告を担う。

## 現状分析

- 確認済み: `record_session_state.py`(Stop)は transcript から手順番号を推定するだけで、
  出力ヘッダ自身が「推定・要確認」と断っている(240行目付近)。ゲート通過状況は持たない。
- 確認済み: `reinject_after_compact.py` は `source == "compact"` のときだけ動作し、
  `.claude/checkpoints/latest.md` と注意文を `print` で注入する。`sys.path` 操作は無い
  (フック間 import を足すなら `sys.path.insert` の追加が必要)。
- 確認済み: `resume_session_state.py` は `source == "startup"` のときだけ動作し、
  記録ブランチと現ブランチが一致するときのみ注入する。異常系は無出力・exit 0。
- 確認済み: `plan_gate._slug_from_branch`(plan_gate.py:58)は
  `record_session_state.py:30` が既に import しており、フック間 import は実績がある。
- 確認済み(重要): `_common.PROTECTED_PATH_PATTERNS` に `/.claude/hooks/` と
  `/.claude/settings.json` が含まれ、guard_scope が Write/Edit をブロックする。
  実測: `.claude/hooks/state_gate.py` への Write ペイロードで exit 2
  (「フック/設定(ガード自身)への書き込みは禁止です」)。
  → **新規フックを含むフック5系統と settings.json は、エージェントが直接書けない。**
- 確認済み: 同じ制約を回避する既存の前例が `_staging_data_protection_p3.py`(760行)。
  リポジトリルートの `_staging_*.py` を**冪等な適用スクリプト**として置き、
  ユーザーが `! uv run python _staging_*.py` で手動適用する。`--root` でサンドボックス
  適用ができ、`.gitignore` に `/_staging_*` があるためコミット対象にならない。
- 確認済み: `.claude/state/` と `_staging_skill_state.py` への書き込みは guard_scope で
  ブロックされない(実測 exit 0)。`git check-ignore .claude/state/dummy.json` は現状 exit 1
  (未 ignore)。
- 確認済み: Stop フックの非ブロック警告の書式は `session_monitor.py:231-233`
  (`print(json.dumps({"systemMessage": text}))` + 同文を stderr、exit 0)。
- 確認済み: settings.json の PreToolUse には matcher `"Edit|Write|NotebookEdit"` の
  グループが既にあり(guard_scope・requirements_gate)、そこへ1件追加すれば足りる。
- 確認済み: CONTEXT.md に「SKILL.state」「実行状態ファイル」の用語が既に登録済み
  (追記不要)。ADR-0018 も作成済み。

## 変更対象

| ファイル | 変更内容 | 直接編集可否 |
|---------|---------|-------------|
| `.gitignore` | `.claude/state/` を追加 | 可 |
| `.claude/commands/ml-pipeline.md` | 手順1.5 に初期状態作成、状態更新規約、手順9 に削除 | 可 |
| `.claude/skills/handoff/SKILL.md` | 「## 実行状態スナップショット」節を必須化 | 可 |
| `tests/test_state_gate.py` | state_gate の受け入れテスト(新規) | 可 |
| `tests/test_reinject_state.py` | compact / startup 注入の受け入れテスト(新規) | 可 |
| `tests/test_state_freshness.py` | Stop 鮮度警告の受け入れテスト(新規) | 可 |
| `_staging_skill_state.py` | 下記4フック+settings.json を冪等適用するスクリプト(新規) | 可 |
| `.claude/hooks/state_gate.py` | 新規 PreToolUse フック(スキーマ検証) | **不可**(staging 経由) |
| `.claude/hooks/record_session_state.py` | 鮮度警告の追加 | **不可**(staging 経由) |
| `.claude/hooks/reinject_after_compact.py` | 状態セクション注入 | **不可**(staging 経由) |
| `.claude/hooks/resume_session_state.py` | 状態セクション注入 | **不可**(staging 経由) |
| `.claude/settings.json` | PreToolUse に state_gate を配線 | **不可**(staging 経由) |

## 事後条件(postconditions)

| ID | 対象 | 入力 | 満たすべき条件 | R-ID |
|----|------|------|---------------|------|
| PC-1 | state_gate.py | 設計書 4.5 のスキーマに完全準拠した状態 JSON の Write ペイロード(file_path が `.claude/state/<slug>.json`) | exit 0・ブロックメッセージを出さない | R-003 |
| PC-2 | state_gate.py | 必須キー欠落 / 型不一致(例: `current_step` が数値)/ enum 外(例: `gates.evaluator` が `"OK"`)の各ペイロード | いずれも exit 2、stderr に違反したキー名を含む理由 | R-004 |
| PC-3 | state_gate.py | スキーマ外のキーを1つ追加したペイロード | exit 2、stderr に当該キー名を含む | R-005 |
| PC-4 | state_gate.py | `notes` が 501 字 / 500 字 のペイロード | 501 字は exit 2、500 字は exit 0(境界を含む) | R-006 |
| PC-5 | state_gate.py | 検証処理内部で予期せぬ例外が発生する状況(壊れた stdin ペイロード等) | exit 0(fail-open)、ブロックしない | R-007 |
| PC-6 | state_gate.py | `.claude/state/` 配下でないパス、または `.json` 以外への Write/Edit | 内容を問わず exit 0 | R-003 |
| PC-7 | state_gate.py | Edit ツールのペイロード。適用結果がスキーマ違反になる場合 / 準拠する場合 | 違反は exit 2、準拠は exit 0。`old_string` が一意に特定できない等で適用結果を再現できない場合は exit 0(fail-open) | R-004 |
| PC-8 | reinject_after_compact.py | `source="compact"` + 有効な状態ファイル | stdout に `## 現在の実行状態(検証済み・これを正とする)` を含み、その見出しが `## 直前のチェックポイント` より**前**に出る | R-008, R-017 |
| PC-9 | resume_session_state.py | `source="startup"` + 有効な状態ファイル(ブランチ一致) | stdout に同じ見出しの節と状態 JSON を含む | R-009 |
| PC-10 | 両注入フック | 状態ファイルが存在しない / JSON として壊れている | stdout に状態セクション見出しを**含まず**、「状態ファイルが読めない」旨の1行を含む。exit 0 | R-010 |
| PC-11 | record_session_state.py | 状態ファイルの `updated_at` が現在時刻の31分前 / 29分前 | 31分前は警告(systemMessage)を出力し exit 0(ブロックなし)、29分前は警告を出さない。状態ファイルが無ければ何も出さない | R-011 |
| PC-12 | `.gitignore` | `git check-ignore .claude/state/dummy.json` | exit 0 | R-015 |
| PC-13 | `_staging_skill_state.py` | 同一 `--root` に対して2回連続実行 | 1回目と2回目で適用先ファイル群がバイト単位で同一(冪等) | R-016 |
| PC-14 | `.claude/settings.json` | 適用後のファイル | 有効な JSON であり、`state_gate` を含むフックエントリがちょうど1件、PreToolUse の Edit/Write を含む matcher に属する | R-016 |
| PC-15 | `.claude/hooks/state_gate.py`・`reinject_after_compact.py`・`resume_session_state.py` | 適用後のソース | ブランチ名から状態ファイルパスを導出する処理は3ファイルとも `from plan_gate import _slug_from_branch` の import で行い、いずれも `-group-` を含む正規表現リテラルを**含まない**(複製禁止。premortem MEDIUM 反映: 注入フック側での独自複製もテストで検出する) | R-014 |
| PC-16 | `.claude/commands/ml-pipeline.md` | ファイル本文 | 手順1.5 節に `.claude/state/` の初期作成指示、`current_step` を含む状態更新規約、手順9 節に状態ファイル削除の指示がある | R-001, R-002, R-013 |
| PC-17 | `.claude/skills/handoff/SKILL.md` | ファイル本文 | `## 実行状態スナップショット` の見出しと、別マシンでの復元手順がある | R-012 |

## 実装手順

テストファースト。Step 2〜4 の auto 要件テストを、実装(Step 5 の staging スクリプト)より
先に書く。Step 5 の前は対象フックが存在しないため RED になるのが正しい状態
(`tests/test_session_resume.py` の docstring と同じ扱い方に倣う)。

| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 1 | `.claude/state/` を gitignore に追加(`.claude/checkpoints/` の近くに、用途が分かる1行コメント付きで)(R-015 対応) | `.gitignore` | なし | D |
| 2 | state_gate の受け入れテストを先に書く。`-k` で `valid` / `invalid` / `unknown_key` / `notes_limit` / `fail_open` が選択できるテスト名にする。PC-1〜PC-7・PC-15 を固定。書式は `tests/test_session_resume.py`(`subprocess.run([sys.executable, <絶対パス>], ...)`・`_SUBPROCESS_TIMEOUT`)に倣う(R-003〜R-007, R-014 対応) | `tests/test_state_gate.py` | なし | A |
| 3 | 注入側の受け入れテストを先に書く。`-k` で `compact` / `startup` / `broken` が選択できるテスト名にする。PC-8〜PC-10 を固定。見出しの**出現順**(状態セクションが先)まで検査する(R-008〜R-010 対応) | `tests/test_reinject_state.py` | なし | A |
| 4 | 鮮度警告の受け入れテストを先に書く。PC-11 を固定。`updated_at` は naive(`2026-09-04T10:00:00`)と aware(`+09:00` 付き)の両形式で31分前・29分前を検査する。注意: 片方だけだと `datetime` の naive/aware 比較で `TypeError` になり、fail-open に飲まれて警告が永久に出ない事故を検出できない(R-011 対応) | `tests/test_state_freshness.py` | なし | A |
| 5 | 保護パス配下の変更をまとめて適用する冪等スクリプトを書く。`_staging_data_protection_p3.py` の構成(モジュール docstring に適用内容の一覧、内容を文字列定数として保持、`--root` 引数、`_write_if_different` 相当、適用済み判定のマーカー)に倣う。適用内容: (a) `.claude/hooks/state_gate.py` の新規配置、(b) `record_session_state.py` への鮮度警告、(c) `reinject_after_compact.py` への状態注入、(d) `resume_session_state.py` への状態注入、(e) `.claude/settings.json` の PreToolUse(matcher `Edit\|Write\|NotebookEdit`)への state_gate 追加。注意: (e) は同一コマンド文字列が既にあれば追加しない(二重登録でフックが2回走るのを防ぐ)。(c)(d) の注入フックが現ブランチの状態ファイルパスを特定する処理は、`_slug_from_branch` の import で行う(独自の正規表現複製は PC-15 で禁止)(R-003〜R-011, R-014, R-016 対応) | `_staging_skill_state.py` | Step 2, 3, 4 | A |
| 6 | ml-pipeline.md に (i) 手順1.5 の末尾へ初期状態ファイル作成、(ii) 手順の節に状態更新規約(各手順完了時に `current_step`・`gates`・`updated_at`・`next_action` を更新)、(iii) 手順9 に状態ファイル削除、を追記する。既存の手順見出し(`### N. タイトル`)と箇条書きの書式に倣い、新設の節は作らない(R-001, R-002, R-013 対応) | `.claude/commands/ml-pipeline.md` | なし | B |
| 7 | handoff/SKILL.md の「## 含める内容」の後に「## 実行状態スナップショット」節を追加し、状態 JSON の埋め込みを必須と明記、別マシンでの復元手順(`.claude/state/<slug>.json` に書き戻す)を書く。既存節の語り口(短い箇条書き)に倣い、「## 自動記録との違い」節にも状態ファイルとの関係を1〜2行で追記する(R-012 対応) | `.claude/skills/handoff/SKILL.md` | なし | C |
| 8 | ユーザーへ `_staging_skill_state.py` の適用を依頼する(`! uv run python _staging_skill_state.py`)。適用内容の要約(変更5ファイル)と、適用前は Step 2〜4 のテストが RED であることを併せて伝える。エージェントは自分で適用しない | (ユーザー操作) | Step 5 | A |
| 9 | 適用後に全テストと grep 系検証を実行し、下記「検証方法」の全項目が PASS することを確認する。R-017(注入文面の優先順位)はユーザーに目視確認を依頼する | (検証のみ) | Step 1, 6, 7, 8 | A |

並列化判定: 並列化可能(グループ A / B / C / D。B は ml-pipeline.md のみ、C は handoff/SKILL.md のみ、
D は .gitignore のみを触り、A のテスト・staging スクリプトとファイルが完全に分離しているため。
A 内部は Step 2〜4 → 5 → 8 → 9 の順に依存があるので逐次)

## 検証方法

適用(Step 8)後に、リポジトリルートで実行する。

| 検証 | コマンド | PASS 条件 |
|------|---------|----------|
| state_gate 全体 | `uv run python -m pytest tests/test_state_gate.py -q` | exit 0 |
| 正常系 | `uv run python -m pytest tests/test_state_gate.py -q -k valid` | exit 0・1件以上実行(deselect 0件でない) |
| 異常系 | `uv run python -m pytest tests/test_state_gate.py -q -k invalid` | exit 0・1件以上実行 |
| 未知キー | `uv run python -m pytest tests/test_state_gate.py -q -k unknown_key` | exit 0・1件以上実行 |
| notes 上限 | `uv run python -m pytest tests/test_state_gate.py -q -k notes_limit` | exit 0・1件以上実行 |
| fail-open | `uv run python -m pytest tests/test_state_gate.py -q -k fail_open` | exit 0・1件以上実行 |
| compact 注入 | `uv run python -m pytest tests/test_reinject_state.py -q -k compact` | exit 0・1件以上実行 |
| startup 注入 | `uv run python -m pytest tests/test_reinject_state.py -q -k startup` | exit 0・1件以上実行 |
| 欠損・破損 | `uv run python -m pytest tests/test_reinject_state.py -q -k broken` | exit 0・1件以上実行 |
| 鮮度警告 | `uv run python -m pytest tests/test_state_freshness.py -q` | exit 0 |
| 回帰 | `uv run python -m pytest tests/ -q` | exit 0(既存テストの新規 FAIL なし) |
| gitignore | `git check-ignore .claude/state/dummy.json` | exit 0 |
| slug 複製禁止 | `grep -l 'from plan_gate import _slug_from_branch' .claude/hooks/state_gate.py .claude/hooks/reinject_after_compact.py .claude/hooks/resume_session_state.py` | 状態ファイルパスをブランチ名から導出する全ファイルがヒット。かつ `grep -n '\-group\-' <同3ファイル>` が正規表現リテラルとして0件 |
| 配線 | `grep -c 'state_gate' .claude/settings.json` | 1(2件以上なら二重登録) |
| settings.json 妥当性 | `uv run python -m json.tool .claude/settings.json` | exit 0 |
| ml-pipeline | `grep -n 'state/' .claude/commands/ml-pipeline.md` | 手順1.5 節と手順9 節の両方にヒット |
| 状態更新規約 | `grep -c 'current_step' .claude/commands/ml-pipeline.md` | 1 以上 |
| handoff | `grep -n '実行状態スナップショット' .claude/skills/handoff/SKILL.md` | 1件以上ヒット |
| 冪等性 | `uv run python -m pytest tests/test_state_gate.py -q -k idempotent` | exit 0(2回適用で差分なし) |
| R-017(目視) | 注入文面をユーザーに提示 | 状態セクションが散文サマリより優先される指示文になっている、と承認 |

入力形状のバリエーション(取りこぼし防止のため必ず検査する):

- `gates` の5キーがすべて null / 一部が enum 値 / 1つだけ enum 外、の3ケース
- `open_findings` が空リスト / 複数要素 / 要素が文字列でない(型不一致)、の3ケース
- `artifacts` の3キーが null / 文字列 / キー欠落 / 未知のサブキー追加(入れ子の未知キー)
- Write ペイロードと Edit ペイロードの両方(PC-7)

## リスク

- **保護パス経由の適用漏れ**: フック5系統は staging スクリプト適用まで反映されない。
  適用前は Step 2〜4 のテストが RED になる(想定どおり)。Step 9 の検証は必ず適用後に行う。
- **settings.json の二重登録**: 適用スクリプトを2回走らせると state_gate が2回配線され、
  同じブロックが二重に出る。PC-13(冪等性)と検証の `grep -c` = 1 で固定する。
- **naive / aware の日時比較**: `updated_at` の形式次第で `TypeError` が起き、fail-open に
  飲まれて鮮度警告が永久に出ない。Step 4 で両形式を検査する。
- **過剰ブロック**: Edit の適用結果を再現できないケースでブロックすると、正当な部分更新が
  止まる。PC-7 のとおり再現不能時は fail-open にする。
- **ADR-0016 との併存**: 将来 MEA 状態が実装されると状態が2系統になる。優先規則は 0016 側で
  決める(設計書 8 節。本計画では扱わない)。
- 検討した代替案(不採用):
  - 案B: guard_scope を無効化/ユーザーに5ファイルを手編集してもらう →
    不採用。ガード迂回の前例を作る、または5ファイル手編集で誤りやすい。既存の
    `_staging_*` 前例と一貫させる方が安全かつ検証可能。
  - 案C: PostToolUse で事後警告のみ(fail-open) → 不採用。ADR-0018 が PreToolUse ブロックを
    採用済みで、壊れた状態が一度書かれると再注入が汚染される。
  - 案D: `.claude/state/*.json` への Edit を一律ブロックし Write のみ許可 → 不採用。
    要件が Edit も検証対象と明記しており、正当な部分更新まで止める過剰ブロックになる。
- 未確認の仮定: 実装前の時点で `tests/` 全体が PASS しており、本計画で追加する RED テスト以外に新規 FAIL が無い / 検証: `uv run python -m pytest tests/ -q` / 期待: exit 0(失敗0件)

## トレーサビリティ

| ID | 対応ステップ | 検証方法 |
|--------|------------|---------|
| R-001 | Step 6 | `grep -n 'state/' .claude/commands/ml-pipeline.md`(手順1.5 節にヒット) |
| R-002 | Step 6 | `grep -c 'current_step' .claude/commands/ml-pipeline.md`(1 以上) |
| R-003 | Step 2, 5, 8 | `uv run python -m pytest tests/test_state_gate.py -q -k valid` |
| R-004 | Step 2, 5, 8 | `uv run python -m pytest tests/test_state_gate.py -q -k invalid` |
| R-005 | Step 2, 5, 8 | `uv run python -m pytest tests/test_state_gate.py -q -k unknown_key` |
| R-006 | Step 2, 5, 8 | `uv run python -m pytest tests/test_state_gate.py -q -k notes_limit` |
| R-007 | Step 2, 5, 8 | `uv run python -m pytest tests/test_state_gate.py -q -k fail_open` |
| R-008 | Step 3, 5, 8 | `uv run python -m pytest tests/test_reinject_state.py -q -k compact` |
| R-009 | Step 3, 5, 8 | `uv run python -m pytest tests/test_reinject_state.py -q -k startup` |
| R-010 | Step 3, 5, 8 | `uv run python -m pytest tests/test_reinject_state.py -q -k broken` |
| R-011 | Step 4, 5, 8 | `uv run python -m pytest tests/test_state_freshness.py -q` |
| R-012 | Step 7 | `grep -n '実行状態スナップショット' .claude/skills/handoff/SKILL.md` |
| R-013 | Step 6 | `grep -n 'state/' .claude/commands/ml-pipeline.md`(手順9 節にヒット) |
| R-014 | Step 2, 5, 8 | 検証方法「slug 複製禁止」行のとおり(state_gate.py+注入フック2本の3ファイル対象) |
| R-015 | Step 1 | `git check-ignore .claude/state/dummy.json` |
| R-016 | Step 5, 8 | `grep -c 'state_gate' .claude/settings.json`(1) |
| R-017 | Step 9 | (目視)ユーザーが注入文面を確認し承認する |

## 作業ログ(2026-09-04, generator)

### R-010 の解決(ユーザー決定)

実装中、`resume_session_state.py` の起動時(startup)注入について、設計書 R-010
「状態ファイルが存在しない/破損していれば1行通知」を文字どおり実装すると、
`.claude/state/` を一度も使っていない(非パイプライン)セッションでも毎回
通知が出るようになり、かつ既存 `tests/test_session_resume.py` の
「記録なしなら stdout 空」という不変条件(本計画の変更対象外ファイル)を
壊す実装上の矛盾が判明したため、一旦停止してユーザーに確認した。

ユーザー決定: 状態ファイル不在時は同ブランチの計画ファイル
(`.claude/plans/<slug>.md`)の有無で分岐する3分岐(破損は無条件通知/
不在+計画ありは通知/両方不在は沈黙)を採用。設計書 §4 を更新済み
(`docs/active/20260904-skill-state-spec.md` の該当箇所)。
`tests/test_reinject_state.py` の `-k broken` 選択でこの3分岐を固定した。

### 検証手段の制約

保護パス(`.claude/hooks/`・`.claude/settings.json`)は Bash 経由でも
`cp`/`Write` の宛先・参照元いずれもガードでブロックされるため、
staging スクリプトの適用結果を実ファイルとして書き出して subprocess で
動作確認することができなかった(サンドボックス実行の試みは権限
クラシファイアにブロックされた)。代わりに、`_staging_skill_state.py` 内の
文字列定数をメモリ上で `exec`(実ファイルには一切書き込まない)し、
state_gate.py の全分岐・reinject_after_compact.py の4分岐・
resume_session_state.py の4分岐(既存回帰含む)・settings.json パッチの
冪等性・record_session_state.py の鮮度境界(固定クロック)を個別に検証した
(詳細は完了報告に記載)。Step 9 の実サブプロセス経由の検証は、
ユーザーが Step 8 で staging を適用した後に行う。

### 計画ステップ対応表

| 計画ステップ# | 実施内容 | 変更ファイル | 検証コマンドと結果 | コミットID |
|---|---|---|---|---|
| 1 | `.claude/state/` を gitignore に追加 | `.gitignore` | `git check-ignore .claude/state/dummy.json` → exit 0 | 924e667 |
| 2 | state_gate.py の受け入れテストを先に書く(RED) | `tests/test_state_gate.py` | `pytest tests/test_state_gate.py -q` → 23 failed(RED、想定どおり) | 625c57f, 08542f1(曖昧old_stringの検出力修正) |
| 3 | 注入側の受け入れテストを先に書く(RED)。R-010 の3分岐を反映 | `tests/test_reinject_state.py` | `pytest tests/test_reinject_state.py -q` → 7 failed, 3 passed(RED、想定どおり) | 95f5e6f, d0f6bf0(R-010 3分岐反映) |
| 4 | 鮮度警告の受け入れテストを先に書く(RED)。ちょうど30分境界を固定クロック単体テストで検証 | `tests/test_state_freshness.py` | `pytest tests/test_state_freshness.py -q` → 3 failed, 3 passed(RED、想定どおり) | 7f7d6f3, 38299a8(境界テストのタイミング欠陥修正) |
| 5 | 保護パス配下変更の冪等適用スクリプトを作成。state_gate.py新規・record/reinject/resume拡張・settings.json配線 | `_staging_skill_state.py`(gitignore対象・未コミット) | メモリ上exec検証で全分岐・冪等性・境界値を確認(完了報告参照)。実適用はStep 8待ち | (gitignore対象のためコミットなし) |
| 6 | ml-pipeline.md に手順1.5初期作成・状態更新規約・手順9削除を追記 | `.claude/commands/ml-pipeline.md` | `grep -n 'state/' ...` → 3箇所ヒット(手順1.5/共通規約/手順9)、`grep -c 'current_step'` → 2 | a340c35 |
| 7 | handoff/SKILL.md に実行状態スナップショット節を追加 | `.claude/skills/handoff/SKILL.md` | `grep -n '実行状態スナップショット' ...` → 2件ヒット | e03dc21 |
| 8 | ユーザーへ `_staging_skill_state.py` 適用を依頼 | (ユーザー操作) | 未実施(ユーザー操作待ち) | - |
| 9 | 適用後の全検証実行 | (検証のみ) | 適用前に実施可能な範囲(gitignore・ml-pipeline/handoff grep・新規3ファイルのRED確認・既存回帰の非劣化確認)のみ完了。サブプロセス経由の GREEN 確認・settings.json実配線確認・R-017目視確認はStep 8後に保留 | - |
