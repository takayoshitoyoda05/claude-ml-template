# 実装計画: 研究データ保護 Phase 1(規約・台帳・権限検査)

参照設計書: `/home/toyod/claude-ml-template/docs/active/20260821-data-protection-phase1.md`
(docs/drafts/ から docs/active/ へ移動済み)

experiment: false
# 実験・学習を伴わないテンプレート改修のため

```yaml
cost_estimate:
  train_minutes: 0
  epochs: 0
  dataset_gb: 0
  parallel_jobs: 1
```

## 目的

研究データ保全の土台として「正しい状態の定義」(invariants のデータ規律・DATA_LOG 台帳・
data/ ディレクトリ規約)と、その逸脱を検知する最小の機械検査(doctor の両方向権限検査)を置く。
Phase 2 の機械ゲートは本 Phase の規約・台帳を「正」として照合するため、これが先行する。

## 現状分析

- 確認済み: `.claude/improvements/invariants.md` は `_common.py` の `PROTECTED_PATH_PATTERNS`
  (`/.claude/improvements/invariants.md`)に含まれ、エージェントの Edit/Write では書けない。
  よって staging 方式(`_staging_data_protection_p1.py` をエージェントが作成 → ユーザーが
  `!` 実行)を採る。前例: `_staging_session_monitor.py`。`/_staging_*` は .gitignore 済み。
- 確認済み: invariants.md の構造は `# テンプレートの不変条件` →
  `## 絶対に変えてはいけないこと` 配下に `### 役割分離` / `### 安全ガード` /
  `### 人間の介入ポイント` / `### スコープ` が並び、その後に `## 変えてよいこと`。
  データ保護は `### スコープ` の直後・`## 変えてよいこと` の直前に新しい `###` 節として入る。
- 確認済み: `doctor.sh`(107行)は `set -uo pipefail`。`git clone` 失敗時も `set -e` が無いため
  後続処理は継続する。`=== リモート運用(Remote Control)===` 節はテンプレ取得の外側にあり、
  data 検査も同様に「テンプレ取得に依存しない独立ブロック」として置ける。
  `doctor.ps1`(122行)は clone 部が `try/finally` に入っており、data 検査は finally の外に置く。
- 確認済み: `claude-init.sh:201` / `claude-update.sh:124` / `claude-init.ps1:183` は
  `templates/*.template` をグロブで配布する。テンプレート追加でインストーラの変更は不要
  (sh/ps1 の対ファイル規律に抵触しない)。
- 確認済み: `verify-installers.sh` に「作業ツリー版スクリプトの TEMPLATE_REPO を sed で
  `file://$ROOT` に差し替えてサンドボックスで実行する」前例がある。ローカル depth-1 clone は
  実測 2.3MB・体感即時で、ネットワークに出ない。
- 確認済み: `handoff/SKILL.md` は `## 含める内容` / `## 含めないこと` / `## 保存先` /
  `## 次のセッションでの使い方` / `## 自動記録との違い` の構成。
  `paper-writing/SKILL.md` は `## 用途1〜4` + `## 重要なルール`。
- 確認済み: README は `### 3.16 研究ワークフロー` … `### 3.20 自律度レベルと人間のコントロール`
  の後に `## 4. テンプレートの育て方` が来る。data/ 規約は `### 3.21` として新設できる。
  `## 6. ファイル一覧` の `templates/` ブロック(1630-1638行)に雛形が1行ずつ並ぶ。
- 確認済み: テストの前例は `tests/test_session_monitor.py`(subprocess CLI 起動・
  staging 未適用時の `pytest.mark.skipif`・tmp_path fixture)。
- data/ はテンプレートリポジトリに実体が無い。よって出荷物は「規約・雛形・検査」のみ。

## 変更対象

| ファイル | 変更内容 |
|---------|---------|
| tests/test_data_protection_phase1.py | 新規。R-001〜R-013 の受け入れテスト(実装前に作成) |
| _staging_data_protection_p1.py | 新規(gitignore 対象)。invariants.md へデータ保護節を冪等に追記する適用スクリプト |
| templates/DATA_LOG.md.template | 新規。必須7列のデータ台帳雛形 |
| doctor.sh | data 検査ブロックを追加(独立ブロック。3つの警告マーカー) |
| doctor.ps1 | doctor.sh と同一検査項目・同一マーカーの data 検査ブロックを追加 |
| .claude/skills/handoff/SKILL.md | 公開前チェックリスト7点の節を追加 |
| .claude/skills/paper-writing/SKILL.md | 同一文言のチェックリスト7点の節を追加 |
| README.md | 3.21 節(data/ 運用規約)を新設 + 4.5 doctor 節と6章ファイル一覧の追記 |

## 事後条件(postconditions)

| ID | 対象 | 入力 | 満たすべき条件 | R-ID |
|----|------|------|--------------|------|
| PC-1 | 適用後の `.claude/improvements/invariants.md` | ファイル本文 | データ三原則の3項目(raw 不可侵 / 前処理はスクリプト / DATA_LOG が来歴の唯一の真実)がいずれも本文中に現れる | R-001 |
| PC-2 | 同上 | ファイル本文 | 持ち出し規制(外部に出してよいのは集計値・図・ハッシュのみ)が記載される | R-002 |
| PC-3 | 同上 | 追記した各データ規律の行 | 各規律に対応する機械検査名(doctor の検査マーカー、または Phase 2 のゲート名)が併記され、検査名の無い規律が0件 | R-003 |
| PC-4 | `templates/DATA_LOG.md.template` | ファイル本文 | Markdown 表のヘッダ行に7列(データセット名/入手元/入手日/ライセンス/sha256/前処理コマンド/識別子列)が過不足なく含まれる | R-004 |
| PC-5 | `doctor.sh` | `data/raw` が存在し書き込み可の作業ディレクトリ | 標準出力に raw 書き込み可の警告マーカーが1回以上出る | R-005 |
| PC-6 | `doctor.sh` | `data/processed` が存在し書き込み不可の作業ディレクトリ | 標準出力に processed 保護過剰の警告マーカーが1回以上出る | R-006 |
| PC-7 | `doctor.sh` | `data/` があり `DATA_LOG.md` が無い作業ディレクトリ | 標準出力に台帳不在の警告マーカーが1回以上出る | R-007 |
| PC-8 | `doctor.sh` | `data/` が存在しない作業ディレクトリ | 標準出力に data 検査の警告マーカーが1つも出ず、終了コードが 0 | R-008 |
| PC-9 | `doctor.sh` と `doctor.ps1` | 両ファイル本文 | data 検査マーカーの一意集合が完全一致し、かつマーカー数が3以上 | R-009 |
| PC-10 | `.claude/skills/handoff/SKILL.md` | ファイル本文 | 公開前チェックリストの7項目(git 履歴/notebook 出力/テスト fixture/ログ/レポート・evidence/MLflow/exports 予定物)がすべて現れる | R-010 |
| PC-11 | `.claude/skills/paper-writing/SKILL.md` | ファイル本文 | handoff 側と同一の7項目キーワードがすべて現れる(2ファイル間で集合一致) | R-011 |
| PC-12 | `README.md` | ファイル本文 | raw/processed/synthetic/exports の4語と各役割の説明、および raw 更新手順(chmod +w → 更新 → DATA_LOG 追記 → chmod -w)が記載される | R-012 |
| PC-13 | `_staging_data_protection_p1.py` | invariants.md の複製を置いた一時ディレクトリ(`--root`) | 2回連続適用したときのファイル内容が1回目適用後と完全一致(バイト一致)し、2回目は `SKIP` を報告する | R-013 |
| PC-14 | `tests/` 全体 | 既存テスト一式 | `uv run --with pytest python -m pytest tests/ -q` が exit 0 | R-014 |

## 実装手順

| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 1 | auto 要件(R-001〜R-013)の受け入れテストを実装前に作成する。`tests/test_session_monitor.py` の様式に倣う(冒頭 docstring・`_ROOT` 定数・subprocess 起動・`pytest.mark.skipif`)。テスト関数名は設計書の `-k` キーワードと一致させる(`invariants_principles` / `invariants_egress` / `invariants_check_mapping` / `datalog_template` / `doctor_raw_writable` / `doctor_processed_readonly` / `doctor_datalog_missing` / `doctor_no_data_dir` / `doctor_parity` / `handoff_checklist` / `paper_checklist` / `readme_data_convention` / `staging_idempotent`)。invariants 依存の3ケースは staging 未適用の間だけ skip、それ以外は未実装時に FAIL すること。注意: doctor 実行系は root(euid 0)では chmod が効かず検査が空振りするため `os.geteuid() == 0` を skip 条件に入れる。`uv`・`git` 不在時も skip する | tests/test_data_protection_phase1.py | なし | A |
| 2 | 全テストを実行し、doctor/テンプレ/スキル/README 系が **FAIL**、invariants 系3件が **skip** になることを確認する(テストの検出力の証明。ここで PASS するテストがあれば書き方が誤っている) | (実行のみ) | Step 1 | A |
| 3 | DATA_LOG 台帳の雛形を作成する。必須7列の Markdown 表 + 記入例1行 + 「識別子列は Phase 2 の辞書半自動生成の入力になる」旨の注記。既存の `templates/design-doc.md.template` の書式(見出し + 表 + 注釈コメント)に倣う | templates/DATA_LOG.md.template | Step 1 | B |
| 4 | invariants.md へデータ保護節を追記する staging スクリプトを作成する。`_staging_session_monitor.py` の構成(モジュール docstring・`--root` 引数・適用済みマーカーによる冪等判定・アンカー件数が1でなければ警告のみで無変更・`APPLIED`/`SKIP` 報告)に倣う。追記内容は `### 研究データ保護` 節として `## 変えてよいこと` の直前に挿入し、データ三原則+持ち出し規制の各行に対応する機械検査名(doctor の検査マーカー名 / Phase 2 のゲート名)を併記する。注意: 検査できない精神論を書かない(検査名を併記できない文言は入れない) | _staging_data_protection_p1.py | Step 1 | C |
| 5 | doctor.sh に data 検査ブロックを追加する。テンプレ取得(clone)の成否に依存しない独立ブロックとし、`=== リモート運用 ===` 節と同じ様式(見出し行 + 個別チェック)で置く。警告文言に機械照合用マーカーを含める。**マーカーの正式名は次の3つで確定**(Step 1 のテストもこの文字列を assert する。premortem MEDIUM の反映): `[DATA-RAW-WRITABLE]`(raw 書き込み可)/ `[DATA-PROCESSED-READONLY]`(processed 書き込み不可)/ `[DATA-LOG-MISSING]`(台帳不在)。`data/` が無い場合は何も出力しない。注意: 既存の `diff_count` 集計・終了コードに影響を与えない(警告のみ) | doctor.sh | Step 1 | D |
| 6 | doctor.ps1 に同一検査項目・同一マーカーのブロックを追加する。判定手段は Windows 実態に合わせる(ReadOnly 属性 / ACL)。判定手段が Unix と厳密には一致しないことをコメントで明記する。clone 部の `try/finally` の外側に置く | doctor.ps1 | Step 5 | D |
| 7 | handoff スキルに公開前チェックリスト7点の節を追加する。既存の `## 含めないこと` 等と同じ見出し階層・箇条書き様式に倣う。文言に Phase 依存(「Phase 2 で機械化」等)を書かない | .claude/skills/handoff/SKILL.md | Step 1 | E |
| 8 | paper-writing スキルに **同一文言** のチェックリスト節を追加する。既存の `## 重要なルール` の並びに合わせて配置する | .claude/skills/paper-writing/SKILL.md | Step 7 | E |
| 9 | README に `### 3.21` として data/ 運用規約を新設する(3.20 の直後・`## 4.` の直前)。raw/processed/synthetic/exports の役割表と raw 更新手順を、既存の環境変数表・フック表と同じ表様式で書く。あわせて整合のため 4.5 doctor 節に data 検査を1行追記し、6章 `templates/` 一覧に `DATA_LOG.md.template` の行を追加する | README.md | Step 1 | F |
| 10 | 全テストを実行し、invariants 系3件が skip・他が PASS になることを確認する。あわせてユーザーに `! uv run python _staging_data_protection_p1.py` の実行(= invariants 変更の承認、R-015)を依頼し、適用後に invariants 系3件が PASS へ変わることを完了報告に含める | (実行のみ) | Step 3-9 | A |

並列化判定: 並列化可能(グループ B / C / D / E / F。対象ファイルが完全に分離しており、
互いに依存しない。グループ A は前後の検証ステップで、Step 1 が全グループの前提、
Step 10 が合流点。doctor.sh / .ps1 は別ファイルだが1対1の整合が必要なため同一グループ D、
handoff / paper-writing も同一文言を保つ必要があるため同一グループ E にまとめた)

## 検証方法

| 検証 | コマンド | PASS 条件 |
|------|---------|----------|
| 実装前(検出力) | `uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q` | doctor/テンプレ/スキル/README/staging 系が FAIL、invariants 系3件が skip |
| 実装後(staging 未適用) | `uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q` | invariants 系3件が skip、残り全件 PASS、exit 0 |
| 実装後(staging 適用後) | `uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q` | 全件 PASS(skip 0 件)、exit 0 |
| 全体退行 | `uv run --with pytest python -m pytest tests/ -q` | exit 0 |
| doctor 複数ケース(data/ あり・raw のみ・processed のみ・両方・data/ 無し・DATA_LOG あり/なし の各組み合わせ) | 上記テスト内の doctor ケース(tmp_path に data/ 構成を作り分けて実行) | 各組み合わせで期待するマーカーだけが出て、期待しないマーカーが出ない |
| doctor の警告が入れ子/複数同時でも取りこぼさない | raw 書き込み可 + processed 書き込み不可 + DATA_LOG 無し を同時に満たす tmp_path | 3マーカーすべてが同一実行の出力に現れる |
| sh/ps1 の1対1(consistency.md 標準形) | `diff <(grep -oE '\[DATA-[A-Z-]+\]' doctor.sh \| sort -u) <(grep -oE '\[DATA-[A-Z-]+\]' doctor.ps1 \| sort -u)` | 差分なし。生の件数・一意件数・diff の3点を完了報告に書く |
| 冪等性 | 上記テストの `staging_idempotent` ケース(tmp_path に invariants.md を複製し2回適用) | 1回目適用後と2回目適用後がバイト一致、2回目は SKIP 報告 |
| 承認(R-015) | ユーザーが `! uv run python _staging_data_protection_p1.py` を実行 | `APPLIED` が報告され、invariants 系テストが PASS に変わる |

doctor テストの実行方式(設計判断): **作業ツリーの doctor.sh をサンドボックスへコピーし、
`TEMPLATE_REPO` 行を sed で `file://<リポジトリルート>` に差し替えて実行する**
(`verify-installers.sh` の `place_installers` と同じ前例)。理由:
(1) doctor.sh 本体にテスト専用の分岐・環境変数を足さずに済む(出荷物を汚さない)、
(2) 実運用と同じ経路(clone → 差分 → data 検査)を丸ごと通せる、
(3) ネットワークに出ない(ローカル depth-1 clone は実測 2.3MB)。
不採用: (a) `CLAUDE_DOCTOR_*` でテンプレ取得をスキップする環境変数 — 出荷スクリプトに
テスト専用スイッチが残り、検査を丸ごと飛ばす抜け道にもなる。(b) data 検査を別スクリプトへ
切り出して doctor から呼ぶ — 新規ファイルが sh/ps1 の対で2つ増え、インストーラの配布対象
(root script distribution, ADR-0005)にも波及する。

## リスク

- invariants.md は保護パスかつ HITL 対象。staging スクリプトのユーザー `!` 実行が承認行為を
  兼ねる(R-015)。エージェントは invariants.md を直接編集しない。計画承認の時点で
  「invariants.md を変更する計画である」ことを承認対象に含める。
- doctor の権限検査は Unix パーミッション前提。ps1 側は ReadOnly 属性 / ACL による判定で
  厳密には同一でない。検査項目とマーカー文言の1対1は保ち、判定手段の差はコードコメントに残す
  (設計書8節に記録済み)。
- テストを root(euid 0)で実行すると chmod による書き込み不可が再現できず、R-006 が
  偽 PASS になりうる。Step 1 の注意書きのとおり skip 条件で塞ぐ。
- 代替案1: invariants への追記を staging ではなく「ユーザーへの手順提示(手動編集依頼)」に
  する — 冪等性(R-013)を機械検証できず、文言のブレも起きるため不採用。
- 代替案2: data 検査を doctor ではなく新規フック(PreToolUse)で行う — フックは
  invariants の「フックのロジック変更は却下」に触れ、Phase 2 の data_gate と役割が重複する。
  Phase 1 は「検知のみ」に留めるため不採用。
- 代替案3: DATA_LOG を YAML/CSV にする — Phase 2 の data.lock が機械可読な正を持つ予定で、
  Phase 1 の台帳は人間が書く来歴記録。既存 templates/*.md.template の様式に合わせ Markdown 表を採用。
- 未確認の仮定: doctor.sh は `git clone` に失敗しても後続処理を続ける(`set -e` 無し) /
  検証: `grep -n 'set -' /home/toyod/claude-ml-template/doctor.sh` / 期待: `set -uo pipefail` のみが出力され `set -e` は含まれない
- 未確認の仮定: templates/*.template はグロブで配布されるためテンプレート追加でインストーラ変更が不要 /
  検証: `grep -n 'templates/\*.template' /home/toyod/claude-ml-template/claude-init.sh` / 期待: `for f in "$TMP"/templates/*.template; do` を含む行が出力される

## トレーサビリティ

| ID | 対応ステップ | 検証方法 |
|--------|------------|---------|
| R-001 | Step 1, 4, 10 | uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k invariants_principles |
| R-002 | Step 1, 4, 10 | uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k invariants_egress |
| R-003 | Step 1, 4, 10 | uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k invariants_check_mapping |
| R-004 | Step 1, 3 | uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k datalog_template |
| R-005 | Step 1, 5 | uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k doctor_raw_writable |
| R-006 | Step 1, 5 | uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k doctor_processed_readonly |
| R-007 | Step 1, 5 | uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k doctor_datalog_missing |
| R-008 | Step 1, 5 | uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k doctor_no_data_dir |
| R-009 | Step 1, 5, 6 | uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k doctor_parity |
| R-010 | Step 1, 7 | uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k handoff_checklist |
| R-011 | Step 1, 8 | uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k paper_checklist |
| R-012 | Step 1, 9 | uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k readme_data_convention |
| R-013 | Step 1, 4 | uv run --with pytest python -m pytest tests/test_data_protection_phase1.py -q -k staging_idempotent |
| R-014 | Step 2, 10 | uv run --with pytest python -m pytest tests/ -q |
| R-015 | Step 10 | (目視)ユーザーが `! uv run python _staging_data_protection_p1.py` を実行し APPLIED を確認 |

## 作業ログ(リーダー統合・手順6.5後の一括追記)

| 計画ステップ# | 実施内容 | 変更ファイル | 検証コマンドと結果 | コミットID |
|---|---|---|---|---|
| 1-2 | 受け入れテスト14関数作成+RED確認(9 failed/4 skip/1正当PASS) | tests/test_data_protection_phase1.py | pytest → 9 failed, 1 passed, 4 skipped | 1ddf4a2 |
| 3 | DATA_LOG雛形(必須7列+記入例+Phase2注記) | templates/DATA_LOG.md.template | -k datalog_template → 1 passed | 65483a5 |
| 4 | invariants追記のstagingスクリプト(冪等・アンカー検査) | _staging_data_protection_p1.py(gitignore・非コミット) | -k staging_idempotent → 1 passed。差し戻しでdocstring+例外捕捉を追補 | (untracked) |
| 5-6 | doctor sh/ps1にdata検査3マーカー(独立ブロック・警告のみ) | doctor.sh, doctor.ps1 | doctor系6件PASS。マーカー1対1: 生3/一意3/diff差分なし | e7bf0b1, cb08748 |
| 7-8 | handoff/paper-writingに同一文言のチェックリスト7点 | 2つのSKILL.md | -k checklist系 → 2 passed | 71dee7a, fdf9112 |
| 9 | README 3.21新設+4.5・6章追記 | README.md | -k readme_data_convention → 1 passed | 4038428 |
| 10 | ユーザーがstaging適用(R-015承認)→invariants系3件PASS化→B/D/E/Fマージ→統合検証 | .claude/improvements/invariants.md | 全体 192 passed / verify-hooks・installers 全PASS | ac8aa8a+マージ4件 |
| 差し戻し | Standards MEDIUM 2件(docstring・例外捕捉)をstagingに反映 | _staging_data_protection_p1.py | staging_idempotent PASS・ruff PASS | (untracked) |
