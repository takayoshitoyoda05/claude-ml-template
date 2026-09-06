# 実装計画: SKILL.state 機構の堅牢化(Codex MEDIUM 6件の修正)

設計書: `docs/active/20260906-skill-state-hardening-spec.md`(受け入れ条件 R-001〜R-011)
関連: ADR-0019 / 親設計書 `docs/active/20260904-skill-state-spec.md`

experiment: false

## 目的

マージ済み SKILL.state 機構の検証の穴(型不一致の fail-open・cwd 依存・読み込み側の未検証)を塞ぎ、
手順書の自己完結性・並列運用規約・導入先 gitignore を揃える。
「検証済み状態を正とする」という宣言を実際に成立させる。

## 現状分析

- 確認済み: `.claude/hooks/state_gate.py:86` `obj["size"] not in _SIZE_ENUM` と `:102` `value not in enum_values` は、
  `size` が list・`gates` の値が dict の場合 `TypeError: unhashable type` を投げ、`main()` の
  `except Exception: pass`(fail-open, PC-5)に飲まれて書き込みが通る。`current_step` 等の
  文字列キーは既存の `isinstance` 検査で捕捉できている(修正不要)。
- 確認済み: `state_gate._expected_state_path()` は `_current_branch()`(プロセス cwd で git 実行)と
  `os.path.abspath(相対パス)`(プロセス cwd 基準)を使う一方、対象パス判定(`:170`)だけが
  ペイロード cwd 基準。両者が食い違うと「対象外」と判定されて検証がスキップされる。
- 確認済み: `_state_common._state_section()` は `json.loads` が通れば "ok" を返し、スキーマ検証をしない。
  スキーマ違反の状態ファイルが「検証済み・これを正とする」見出し付きで注入されうる。
- 確認済み: 検証実装 `def _validate_state` は `.claude/hooks/` 内で `state_gate.py` の1箇所のみ
  (`rg -n 'def _validate_state' .claude/hooks/` の結果1件)。読み込み側から使うには移設が必要。
- 確認済み: `.claude/commands/ml-pipeline.md:146` が「スキーマは docs/active/20260904-skill-state-spec.md §4.5 に従う」と
  外部参照しており、初期 JSON の実例が無い。並列実装節(:314-349)に状態ファイルの記述は無い。
- 確認済み: gitignore 生成部は `claude-init.sh:99` / `claude-update.sh:88` / `claude-init.ps1:91` /
  `claude-update.ps1:91`。init 対は base に `/.worktrees/` を含み update 対は含まない(対内では一致)。
  現在の sh↔ps1 抽出結果は init 対 28/28 件・update 対 27/27 件で diff 0件(実測済み)。
- 確認済み(既存契約): 既存テスト40件(state_gate 24 / reinject 10 / freshness 6)は全て PASS。
  `tests/test_state_gate.py` のペイロードは `cwd` キーを一切持たず(`_run_gate` は
  `subprocess.run(..., cwd=str(tmp_path))` でプロセス cwd を渡すのみ)、`_effective_cwd` は
  `os.getcwd()` にフォールバックする。よって cwd 統一後もプロセス cwd == 実効 cwd となり、
  既存テストのペイロード形と衝突しない。
- 確認済み: `.claude/hooks/` と `.claude/settings.json` は guard_scope が常時ブロックするため
  staging スクリプト経由。`.claude/commands/ml-pipeline.md` と導入スクリプト4本は保護対象外で直接編集可。
- 確認済み: 既存 `_staging_skill_state.py`(gitignore 対象・適用済み)は `state_gate.py` と
  `_state_common.py` を **ファイル全体の内容リテラル**(`STATE_GATE_CONTENT` / `STATE_COMMON_CONTENT`)から
  `_write_if_different` で配置する。内容比較による冪等なので、リテラルを書き換えれば
  再実行で新内容が適用され、2回目以降はバイト不変。

## 変更対象

| ファイル | 関数・箇所 | 変更内容 |
|---|---|---|
| `_staging_skill_state.py` | `STATE_COMMON_CONTENT` | `_validate_state` を移設(型検証を enum 判定前に追加)、`_current_branch(cwd)` 対応、`_state_section` にスキーマ検証を追加 |
| `_staging_skill_state.py` | `STATE_GATE_CONTENT` | `_validate_state` 定義を削除し `_state_common` から import、ブランチ取得・パス導出・対象判定を実効 cwd 基準に統一 |
| `.claude/hooks/_state_common.py` | (staging 適用の結果) | 上記が反映される |
| `.claude/hooks/state_gate.py` | (staging 適用の結果) | 上記が反映される |
| `tests/test_state_gate.py` | 末尾に追加 | 型不一致テスト(`type_mismatch`)・cwd 分離テスト(`cwd`)を追加 |
| `tests/test_reinject_state.py` | 末尾に追加 | スキーマ違反注入テスト(`schema_invalid`)を追加 |
| `.claude/commands/ml-pipeline.md` | 手順1.5(:143-147) | 完全な初期状態 JSON 実例を埋め込み、`docs/active/...` 参照を削除 |
| `.claude/commands/ml-pipeline.md` | 並列実装節(:330-347) | 状態ファイルはリーダーのみ更新する規約を追記 |
| `claude-init.sh` / `claude-update.sh` | `IGNORE_ENTRIES` 基本リスト | `.claude/state/` を追加 |
| `claude-init.ps1` / `claude-update.ps1` | `$ignoreEntries` 基本リスト | `.claude/state/` を追加 |

## 事後条件(postconditions)

| ID | 対象 | 入力 | 満たすべき条件 | 対応 R-ID |
|----|------|------|----------------|-----------|
| PC-1 | `state_gate.py`(CLI) | Write ペイロード、状態 JSON の `size` が `["S"]` | exit 2・stderr に `size` を含む・Traceback を含まない | R-001 |
| PC-2 | `state_gate.py`(CLI) | Write ペイロード、`gates.evaluator` が `{"v": "PASS"}` | exit 2・stderr に `evaluator` を含む・Traceback を含まない | R-001 |
| PC-3 | `state_gate.py`(CLI) | プロセス cwd = 別ディレクトリ、ペイロード `cwd` = 状態ファイルのあるリポジトリroot、スキーマ違反の状態 JSON への Write | exit 2(検証がスキップされない) | R-002 |
| PC-4 | `state_gate.py`(CLI) | 同上の cwd 分離で、スキーマ準拠の状態 JSON への Write | exit 0・stderr に `BLOCKED` を含まない | R-002 |
| PC-5 | `reinject_after_compact.py` / `resume_session_state.py`(CLI) | 現ブランチ slug の状態ファイルが JSON として読めるがスキーマ違反(必須キー欠落・enum 違反) | stdout に見出し `## 現在の実行状態(検証済み・これを正とする)` を含まず、状態ファイルが読めない旨の1行を含む | R-003 |
| PC-6 | `reinject_after_compact.py` / `resume_session_state.py`(CLI) | スキーマ準拠の状態ファイル | stdout に上記見出しと状態 JSON 本文を含む(回帰) | R-004 |
| PC-7 | `.claude/hooks/` 配下 | `grep -rn 'def _validate_state' .claude/hooks/` | ヒット1件のみ(`_state_common.py`) | R-005 |
| PC-8 | `.claude/commands/ml-pipeline.md` 手順1.5節 | 節本文 | `schema_version` を含む JSON コードブロックが存在し、`docs/active` の文字列を含まない | R-006 |
| PC-9 | `.claude/commands/ml-pipeline.md` 並列実装節 | 節本文 | 「状態ファイル」「リーダー」を含む規約行が存在する | R-007 |
| PC-10 | `claude-init.sh` / `claude-update.sh` / `claude-init.ps1` / `claude-update.ps1` | gitignore 生成部 | 4ファイルすべてが `.claude/state/` を基本リスト(GITIGNORE_ALL 条件の外)に含む | R-008 |
| PC-11 | 導入スクリプト sh/ps1 対 | 検証方法の抽出コマンド | init 対・update 対とも 生件数一致・一意件数一致・diff 0件 | R-009 |
| PC-12 | `tests/` 全体 | `uv run --with pytest python -m pytest tests/ -q` | exit 0(新規 FAIL 無し) | R-010 |
| PC-13 | `_staging_skill_state.py` | 同一 `--root` へ2回連続適用 | 適用先ファイル群がバイト単位で同一・settings.json の state_gate 登録が1件 | R-011 |

## 実装手順

| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 1 | 型不一致テスト(関数名に `type_mismatch` を含む)を追加。`size` が list / `gates` の値が dict / `open_findings` が str / `artifacts.plan` が数値 等を parametrize し、exit 2・stderr にキー名・`Traceback` 非出力を検証(R-001 / PC-1, PC-2)。書式は同ファイル既存の `test_pc6_...` の parametrize に倣う | `tests/test_state_gate.py` | なし | A |
| 2 | cwd 分離テスト(関数名に `cwd` を含む)を追加。`tmp_path/repo` を `_init_repo` し、`subprocess.run(cwd=tmp_path/"elsewhere")`(git リポジトリでない別ディレクトリ)+ ペイロード `"cwd": str(repo)` で、違反 JSON は exit 2、準拠 JSON は exit 0 を検証(R-002 / PC-3, PC-4)。注意: `file_path` は相対のまま渡し、実効 cwd 基準で解決されることを確かめる | `tests/test_state_gate.py` | Step 1 | A |
| 3 | スキーマ違反注入テスト(関数名に `schema_invalid` を含む)を追加。JSON としては妥当だがスキーマ違反(必須キー欠落・`gates.evaluator` が不正 enum)の状態ファイルを置き、compact 経路と startup 経路の双方で見出し不在+1行通知を検証(R-003 / PC-5)。書式は既存 `test_broken_state_invalid_json_shows_notice_only` に倣う | `tests/test_reinject_state.py` | なし | A |
| 4 | **不具合を再現するケース**(`size` が list・`gates` の値が dict の型不一致、cwd 分離での検証スキップ、スキーマ違反ファイルの注入)が RED(FAIL)であることを確認して記録する。既存動作の回帰確認ケース(`open_findings` が str・`artifacts.plan` が数値など既存 isinstance 検査で捕捉済みのもの、cwd 分離の正常系 exit 0)は修正前でも GREEN で正しい(Codex レビュー指摘: 全ケース RED 要求は回帰テストを歪める)。不具合再現ケースが GREEN の場合のみ検出力が無いとして書き直す | (実行のみ) | Step 1,2,3 | A |
| 5 | `STATE_COMMON_CONTENT` を改修: (a) `state_gate.py` の `_validate_state` とその定数群(`_REQUIRED_KEYS` / `_GATES_ENUM` / `_ARTIFACT_KEYS` / `_SIZE_ENUM` / `NOTES_MAX_CHARS`)を移設し、`size` は `isinstance(str)` を確認してから enum 判定、`gates` の各値は `None` または `str` を確認してから enum 判定に変える(R-001 / PC-1, PC-2)。(b) `_current_branch(cwd: str \| None = None)` に拡張し `subprocess.run(..., cwd=cwd)` を渡す(既定 None = 現行挙動を保持。reinject/resume は引数なし呼び出しのまま)(R-002)。(c) `_state_section` で `json.loads` 後に `_validate_state` を呼び、違反なら `"broken"` を返す(R-003 / PC-5)。注意: 通知文言(「状態ファイルが読めないため…」)は両フック側にあり marker 適用済みのため変更しない | `_staging_skill_state.py` | Step 4 | A |
| 6 | `STATE_GATE_CONTENT` を改修: `_validate_state` と関連定数の定義を削除し `from _state_common import _current_branch, _validate_state` に変更(R-005 / PC-7)。`_expected_state_path(effective_cwd)` へ引数を追加して `_current_branch(effective_cwd)` と `os.path.join(effective_cwd, ".claude", "state", ...)` を使い、`_run()` で実効 cwd を先に決めてから渡す(R-002 / PC-3, PC-4)。モジュール docstring の検証規則・cwd 規約の記述も実装に合わせて更新する | `_staging_skill_state.py` | Step 5 | A |
| 7 | ユーザーに `! uv run python _staging_skill_state.py` の実行を依頼して適用する(保護パスのため自動適用不可)。適用後に `.claude/hooks/state_gate.py` と `_state_common.py` が更新されたことを確認 | `.claude/hooks/state_gate.py`, `.claude/hooks/_state_common.py` | Step 6 | A |
| 8 | 検証方法のコマンドを全て実行し GREEN を確認する(R-001〜R-005, R-010, R-011 / PC-1〜PC-7, PC-12, PC-13)。既存40件に新規 FAIL が無いことも同時に確認 | (実行のみ) | Step 7 | A |
| 9 | 手順1.5 の状態ファイル作成手順に、11キーすべてを含む完全な初期状態 JSON 実例(```json ブロック)を埋め込み、`docs/active/20260904-skill-state-spec.md §4.5` への参照文を削除する(R-006 / PC-8)。実例の値は `schema_version: 1`・`current_step: "1"`・`gates` 全キー null・`open_findings: []`・`artifacts` 3キー null・`updated_at` は ISO 8601 の例。既存の手順1.5 内のコードブロック(`git checkout -b`)と同じ体裁に倣う | `.claude/commands/ml-pipeline.md` | なし | B |
| 10 | 並列実装節「各チームメイトへの指示に含めること」の直後の注意リストに、「`.claude/state/<slug>.json` は統合ブランチ上のリーダー(ml-pipeline 実行者)のみが更新し、worktree 内の generator は読み書きしない(1ファイル1書き手)」を1項目として追記する(R-007 / PC-9)。既存の注意リスト(`- ` 始まり)の書式に倣う | `.claude/commands/ml-pipeline.md` | Step 9 | B |
| 11 | `IGNORE_ENTRIES` の基本リスト(GITIGNORE_ALL 条件の外側)に `".claude/state/"` を追加する。init は `/.worktrees/` の後ろ、update は `**/.claude/spec/` の後ろに置く(R-008 / PC-10) | `claude-init.sh`, `claude-update.sh` | なし | C |
| 12 | `$ignoreEntries` の基本リストに `".claude/state/"` を sh 版と同じ位置に追加する(R-008, R-009 / PC-10, PC-11)。注意: 対の位置がずれても `sort -u` 後の diff は通るが、可読性のため sh 版と同順に置く | `claude-init.ps1`, `claude-update.ps1` | Step 11 | C |

並列化判定: 並列化可能(グループ A / B / C。A はフック+テスト+staging、B は `ml-pipeline.md`、C は導入スクリプト4本で、対象ファイルが完全に分離しており依存も無いため)。
ただし**グループ A は worktree に出さず、統合ブランチ上でリーダー(または統合ブランチ上の generator)が直接実行する**
(Codex レビュー指摘: `_staging_skill_state.py` は Git 管理外(`.gitignore:19` の `/_staging_*`)のため worktree に存在せず、
Step 7 の適用先フックも統合側リポジトリの `.claude/hooks/` であるため)。worktree 並列にしてよいのは B・C のみ。
また A の Step 7 はユーザーの `!` 実行を挟むため、A は途中で待ちが入る。

## 検証方法

すべてリポジトリルートで実行する。

1. R-001: `uv run --with pytest python -m pytest tests/test_state_gate.py -q -k type_mismatch`
   → exit 0 かつ「N passed」の N ≥ 1(`no tests ran` は不可)
2. R-002: `uv run --with pytest python -m pytest tests/test_state_gate.py -q -k cwd`
   → exit 0 かつ N ≥ 1
3. R-003: `uv run --with pytest python -m pytest tests/test_reinject_state.py -q -k schema_invalid`
   → exit 0 かつ N ≥ 1
4. R-004: `uv run --with pytest python -m pytest tests/test_reinject_state.py -q` → exit 0
5. R-005: `grep -rn 'def _validate_state' .claude/hooks/` → ヒット1件のみ(`_state_common.py`)。
   `__pycache__` のバイナリ一致が報告された場合は `--include='*.py'` を付けて再確認する
6. R-006: `grep -n '20260904-skill-state-spec' .claude/commands/ml-pipeline.md` → 0件
   (手順1.5 節の参照は親設計書ファイル名を含む唯一の行のため、ファイル全体 grep で機械判定できる。
   `docs/active` 自体は他節に無関係な既存ヒットが3行あり件数判定に使えない — premortem 指摘)。
   加えて `grep -n 'schema_version' .claude/commands/ml-pipeline.md` が手順1.5 節でヒットする
7. R-007: `grep -n '状態ファイル' .claude/commands/ml-pipeline.md` → 並列実装節(現行 :314-349 相当)でヒット
8. R-008: `grep -l '\.claude/state/' claude-init.sh claude-update.sh claude-init.ps1 claude-update.ps1` → 4ファイル全て
9. R-009(consistency.md 標準形。init 対・update 対の2回実行し、生件数・一意件数・diff の3点を報告):

   ```bash
   diff <(sed -n '/^ *IGNORE_ENTRIES=(/,/^ *fi$/p' claude-init.sh | grep -oE '"[^"]+"' | grep -vE 'CLAUDE_TEMPLATE_GITIGNORE_ALL|^"1"$' | sort -u) \
        <(sed -n '/\$ignoreEntries = @(/,/^ *}$/p' claude-init.ps1 | grep -oE '"[^"]+"' | grep -vE '^"1"$' | sort -u)
   ```

   同じ形で `claude-update.sh` / `claude-update.ps1` も比較する。
   期待: diff 0件、生件数 init 対 29/29・update 対 28/28(現状 28/28・27/27 に `.claude/state/` が1件加わる)
10. R-010: `uv run --with pytest python -m pytest tests/ -q` → exit 0(基準: 変更前は state 系40件 PASS を実測済み)
11. R-011: `uv run --with pytest python -m pytest tests/test_state_gate.py -q -k idempotent` → exit 0 かつ N ≥ 1

複数・入れ子ケースの検証(取りこぼし防止):

- 型不一致は1キーだけでなく、**複数キーが同時に不正**な状態(例: `size` が list かつ `gates.evaluator` が dict)でも
  exit 2 かつ Traceback 非出力であることを確認する
- **入れ子の型不一致**(`gates` の値が dict、`artifacts.plan` が list、`open_findings` の要素が dict)を
  それぞれ個別ケースとして検証する(トップレベルのみの検査で素通りしないことの確認)
- gitignore 生成部は**基本リストと GITIGNORE_ALL 追加リストの2ブロック**があるため、抽出コマンドが
  両ブロックを拾っていること(件数が 29 / 28 になること)を件数で確認する

## リスク

- **既存契約(確認済み)**: `tests/test_state_gate.py` の全ペイロードは `cwd` キーを持たず、
  `_effective_cwd` が `os.getcwd()` にフォールバックするため、cwd 統一後も実効 cwd = プロセス cwd = `tmp_path` で
  既存24件の前提は変わらない。`_current_branch` の引数追加は既定値 None で現行挙動を保持するため
  reinject/resume の10件にも影響しない(実測: 変更前 40件 PASS)。
- **staging スクリプトの選択**: 既存 `_staging_skill_state.py` を更新する案を採用。
  代替案(新規 `_staging_skill_state_hardening.py`)は不採用 — 両スクリプトが `state_gate.py` を
  ファイル丸ごと配置するため、旧スクリプトを後から再実行すると堅牢化前の内容へ巻き戻る競合が生じる。
- **通知文言の据え置き**: スキーマ違反を既存の `"broken"` 分岐に合流させる案を採用。
  代替案(`"schema_invalid"` 分岐を新設し文言を分ける)は不採用 — 文言は reinject/resume の
  両フック側にあり、staging の marker 判定(`_RESUME_SHARED_MARKER`)が既に適用済みを返すため
  文言差し替えには marker 設計のやり直しが必要で、R-003 の受け入れ条件(注入しない+1行通知)は
  合流案で満たせる。
- **検証の集約先**: `_validate_state` を `_state_common.py` へ移す案を採用。代替案(state_gate に残して
  `_state_common` から import)は循環 import(state_gate → _state_common → state_gate)になるため不採用。
- **副作用**: 導入スクリプトの変更は導入先の `.gitignore` に1行増える。既存導入先は
  `claude-update` 再実行時に追記される(冪等な `grep -qxF` 判定のため重複しない)。
- 未確認の仮定: `_state_common.py` に `_validate_state` を移しても state_gate 以外の import 経路に影響が無い / 検証: `rg -n 'from state_gate import' .` / 期待: ヒット0件
- 未確認の仮定: 手順1.5 の初期 JSON 実例が `.claude/commands/ml-pipeline.md` 以外で二重管理になっていない / 検証: `rg -ln 'schema_version' .claude/commands` / 期待: ヒット0件(変更前時点)

## トレーサビリティ

| ID | 対応ステップ | 検証方法 |
|--------|------------|---------|
| R-001 | Step 1, 4, 5, 8 | `uv run --with pytest python -m pytest tests/test_state_gate.py -q -k type_mismatch` |
| R-002 | Step 2, 4, 6, 8 | `uv run --with pytest python -m pytest tests/test_state_gate.py -q -k cwd` |
| R-003 | Step 3, 4, 5, 8 | `uv run --with pytest python -m pytest tests/test_reinject_state.py -q -k schema_invalid` |
| R-004 | Step 5, 8 | `uv run --with pytest python -m pytest tests/test_reinject_state.py -q` |
| R-005 | Step 5, 6, 8 | `grep -rn 'def _validate_state' .claude/hooks/` |
| R-006 | Step 9 | `grep -n '20260904-skill-state-spec' .claude/commands/ml-pipeline.md`(0件)+ `schema_version` の JSON ブロック確認 |
| R-007 | Step 10 | `grep -n '状態ファイル' .claude/commands/ml-pipeline.md`(並列実装節でヒット) |
| R-008 | Step 11, 12 | `grep -l '\.claude/state/' claude-init.sh claude-update.sh claude-init.ps1 claude-update.ps1` |
| R-009 | Step 11, 12 | 検証方法9(consistency.md 標準形 diff、init 対・update 対) |
| R-010 | Step 8 | `uv run --with pytest python -m pytest tests/ -q` |
| R-011 | Step 7, 8 | `uv run --with pytest python -m pytest tests/test_state_gate.py -q -k idempotent` |
