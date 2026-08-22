# 実装計画: 研究データ保護 Phase 3(読み取り遮断・窓口・暗号化・プロファイル)

参照設計書: `docs/active/20260822-data-protection-phase3.md`(R-001〜R-024。R-024 のみ manual)

experiment: false
# 学習・実験を含まない(フック・スクリプト・文書・配布の追加のみ)

```yaml
cost_estimate:
  train_minutes: 0
  epochs: 0
  dataset_gb: 0
  parallel_jobs: 1
```

## 確定事項(リーダー判断・2026-08-22。未確定事項は解消済み)

| 項目 | 決定 | 実装への影響 |
|------|------|-------------|
| OPTIONAL_FEATURES への載せ方 | `claude-init` の OPTIONAL_FEATURES には「`1` で有効化できるフラグ系」だけを載せる。`CLAUDE_DATA_PROFILE`(3値)は載せず、`templates/settings.local.json.template` と config-set / config-explain だけに配線する。`enable_feature()` の3値拡張は行わない | Step 9 は `CLAUDE_DATA_NO_READ` と `CLAUDE_DATA_GATE` の2つだけを OPTIONAL_FEATURES に追加する。installer の共通ロジック(`claude-init.sh:144-154`)は一切変更しない |
| R-014 の配線対象 | `CLAUDE_DATA_PROFILE` / `CLAUDE_DATA_NO_READ` / `CLAUDE_DATA_GATE` の3変数をまとめて配線する。`CLAUDE_DATA_GATE` の未配線は Phase 2 の漏れであり、記述と実装の整合としてこの機会に解消する | Step 8 が3変数を template・config-set の雛形JSONと変数表・config-explain の変数表に追加する |
| 出荷時の既定値 | 3変数とも `""`(空文字列)で出荷する。NO_READ / GATE はプロファイルに解決を委ねる個別変数であり、`.claude/commands/ml-pipeline.md:34` の「自律度レベルで制御したいゲートの個別変数は出荷時に `""`」規約に従う | **確認済み**: `templates/settings.local.json.template` に `CLAUDE_DATA_*` は現在1件も無い(`grep -n DATA` がヒット0)ため、既存値の `"0"` からの変更作業は発生せず**追加のみ**になる |
| 一時解除の時間 | `data_unlock.py --minutes` は既定 30 分・上限 240 分。240 を超える指定はエラーで非0終了し、記録を書かない | Step 4(b) の実装仕様。PC-25 が番人になる |

## 目的

Phase 1・2 が塞げない唯一の経路「エージェントが data/ を読んだ時点で内容が LLM API に
渡る」を、Read/Bash の読み取り遮断と統計量だけを返す窓口スクリプトで構造的に塞ぐ。
あわせてバックアップ境界の暗号化と、全対策を1変数で切り替える機密度プロファイルを足す。

## 現状分析

確認済みの前提(すべてコード・ログを読んで裏取り済み):

- **`"Read"` matcher は前例が無く新設になる**: `.claude/settings.json` の PreToolUse は
  `Edit|Write|NotebookEdit` と `Bash|PowerShell` の2つのみ。SessionStart の
  `compact` / `startup` を含めても Read 系の matcher は存在しない。
- **Read の PreToolUse 発火とペイロード形は公式ドキュメントで確認済み**
  (https://code.claude.com/docs/en/hooks.md 、確認日 2026-08-22): matcher `"Read"` は
  有効、`tool_input` は `file_path` を持つ(相対/絶対の明示は無い)、exit 2 で Read が
  中断され stderr が Claude に表示される。**相対/絶対が明示されていない**ため、
  `guard_scope.py:117-127` の「ペイロード cwd 優先」方式による相対解決を維持する。
- **実測でも入力キーは `file_path`(絶対パス)**: `logs/actions/20260726-7808005c.jsonl`
  の Read エントリの `input` が `{"file_path": "/home/toyod/claude-ml-template/docs/..."}`
  (PostToolUse 側の記録。PreToolUse 実機での最終確認は Step 10 で行う)。
- **ユーザー `!` 実行専用スクリプトのブロック方式の実体**: `guard_bash.py:270-310` は、
  コマンド文字列に当該スクリプト名が含まれ、かつ全セグメントの先頭コマンドが
  読み取り専用コマンド集合(`guard_bash.py:113-123` の grep/rg/cat/head/tail/wc/diff/echo/git)に
  収まらない場合に exit 2 する。`data_unlock` も同じ形にする(実行・複製だけを止め、
  grep/cat での参照は通す)。
- **保護パスの定義箇所**: `.claude/hooks/_common.py:63-81` の `PROTECTED_PATH_PATTERNS`
  (`/.claude/spec/approvals.txt` 等の**ファイル単位**の前例あり)。`matched_protected_pattern`
  は realpath も照合して symlink 迂回を塞ぐ。
- **data_gate は先頭でオプトイン判定**: `data_gate.py:66` の
  `if os.environ.get("CLAUDE_DATA_GATE") != "1": sys.exit(0)`。ここをプロファイル解決に
  置き換える(既定 OFF は維持)。コマンド分割は `_SEGMENT_SPLIT` / `_segment_head`。
- **doctor の `[DATA-*]` マーカーは現在7種**: RAW-WRITABLE / PROCESSED-READONLY /
  LOG-MISSING / LOCK-MISMATCH / BACKUP-UNKNOWN / BACKUP-STALE / PRECOMMIT-OFF
  (`doctor.sh:133-203` / `doctor.ps1:155-222`)。3種追加で10種になり R-020 と一致する。
- **既存 parity テストは「7固定」であり、追加すると必ず落ちる**:
  `tests/test_data_protection_phase2.py:924` が `assert len(sh_markers) == 7`。
  Phase 1 側(`test_data_protection_phase1.py:324-326`)は `>= 3` と部分集合なので不変。
  → Phase 2 テストの数値を 10 に更新するステップを計画に入れる(Step 6)。
- **`CLAUDE_DATA_GATE` は config 系に未配線**: `grep -rn CLAUDE_DATA_GATE .claude/commands/
  templates/ .claude/skills/` はヒット0(出現は README・data_gate.py・tests・plans のみ)。
  `templates/settings.local.json.template` にも `CLAUDE_DATA_*` は1件も無い。Phase 2 の
  配線漏れであり、Step 8 でまとめて解消する。
- **doctor の scripts 差分検査は追加作業不要**: `doctor.sh:64-77` / `doctor.ps1:72-86` は
  配布元 `$TMP/scripts` を `find` で全走査する実装なので、新規2本は自動的に対象になる。
  R-019 の「doctor 差分検査対象に追加」は**テストで確認するだけ**で足りる。
- **installer の scripts 配布は個別ファイル名の列挙**: `claude-init.sh:107-109`(IGNORE_ENTRIES)
  と `claude-init.sh:266-300`(配置ループ)、`claude-update.ps1:99-101` / `192-215` 等、
  sh/ps1 4本 + IGNORE_ENTRIES 2箇所(`claude-init.sh:107` / `claude-update.sh:92`)。
  MARKER によるユーザー独自ファイル保持もこのループ内にある。
- **OPTIONAL_FEATURES の値の書き込みは `"1"` 固定**: `claude-init.sh:144-154` の
  `enable_feature()` が `sed` で `"$var": "1"` に置換する。3値を取る変数は載せられない
  (確定事項の Q1=A の根拠)。
- **機能有効化の仕組みは claude-init 専用**: `claude-init.sh:128-140` の `OPTIONAL_FEATURES`
  配列 + `enable_feature()`、`claude-init.ps1:120-176` の `$OptionalFeatures` +
  `Enable-Feature`(識別子名が sh/ps1 で異なる)。**`claude-update.sh` / `claude-update.ps1`
  には該当する仕組みが1つも無い**(`grep -n -i "optional|feature|enable_feature"` がヒット0)。
  更新時に機能を有効化するのは既存設計の役割分担外であり、本計画でも新設しない。
- **README の既存 data_gate 段落**: `README.md:1489-1493` の
  `#### data_gate(送信経路の静的ゲート)` が `CLAUDE_DATA_GATE=1` 前提の説明のまま。
  プロファイル解決を入れると新旧の説明が併存するため、Step 7 で更新する。
- **age は本環境に未導入**(`command -v age` が空)。よって暗号化経路のテストは
  age 実在時のみ走る条件付きになり、本環境では不在経路が常に検証される。
- **staging 前例**: `.claude/plans/20260821-data-protection-p2.md` の Step 7(全操作を冪等・
  `--root [dir]` 引数)と `tests/test_data_protection_phase2.py:1067` の2回適用バイト比較。
  `/_staging_*` は `.gitignore:17` で除外済み。
- **テスト様式**: `tests/test_data_protection_phase2.py`(冒頭 docstring で契約固定・`_ROOT`
  定数・subprocess 起動・`pytestmark_staging` による skip・doctor は `place_installers` 方式で
  `TEMPLATE_REPO` を `file://[repo]` に sed 差し替え。同ファイル 252-295 行)。
- **状態ディレクトリの解決**: `_common.resolve_spec_dir()` は `CLAUDE_SPEC_DIR` で上書きできる
  (テストから解除記録の置き場所を差し替えられる)。

## 設計判断(本計画で確定)

| 項目 | 決定 | 理由 |
|------|------|------|
| 窓口スクリプトの保護(設計書8節の保留) | `scripts/data_summary.py` を `PROTECTED_PATH_PATTERNS` に追加する | 窓口を通す許可を data_gate に入れる以上、窓口自体を書き換えられると読み取り遮断が丸ごとバイパスされる(Edit で個票出力を足せる)。配布・更新は installer の cp(ユーザーのシェル)で行われ、保護パスの影響を受けない。テンプレート側の以後の修正が staging 経由になるコストは受け入れる(ADR-0010 に記録) |
| プロファイル解決の置き場所 | 解決関数を `data_gate.py` と `data_read_gate.py` の**両方に同梱**(重複を許容) | hooks 自己完結原則(R-022)。共有モジュールを増やすより、PC-13 で両者の解決結果の全組み合わせ一致をテストで固定する方が壊れにくい(Phase 2 の ADR-0007 と同じ整理) |
| data/ 判定 | パスを `/` 正規化したうえで `/data/` セグメントを含むかで判定(`_common.PROTECTED_PATH_PATTERNS` の `/data/` と同じ考え方) | プロジェクトルート推定に依存せず、worktree・サンドボックスでも同じ結果になる。`metadata/` のような部分一致はセグメント境界で弾く |
| `.claude/backup_recipients.txt` | 配布リスト・IGNORE_ENTRIES のどちらにも追加しない | 中身は公開鍵のみでユーザー個別の資産。テンプレートが配る種類のファイルではなく、リポジトリに載せても危険ではない(設計書8節の整理どおり) |

## 変更対象

| ファイル | 変更内容 |
|---------|---------|
| `tests/test_data_protection_phase3.py` | 新規。PC-1〜PC-25 の受け入れテスト |
| `scripts/data_summary.py` | 新規。統計量のみを出す窓口(標準ライブラリのみ・MARKER 行つき) |
| `scripts/backup_encrypt.py` | 新規。data/(exports/除く)を tar + age 2鍵で暗号化(MARKER 行つき) |
| `_staging_data_protection_p3.py` | 新規(untracked)。保護パスへの6変更をすべて冪等に適用 |
| `.claude/hooks/data_read_gate.py` | 新規(staging が配置)。Read 遮断 |
| `.claude/hooks/data_unlock.py` | 新規(staging が配置)。ユーザー `!` 実行専用の一時解除(既定30分・上限240分) |
| `.claude/hooks/data_gate.py` | staging が拡張。プロファイル解決 + Bash 読み遮断 + 窓口許可 + 解除判定 |
| `.claude/hooks/guard_bash.py` | staging が拡張。`data_unlock` の実行・複製ブロック |
| `.claude/hooks/_common.py` | staging が拡張。PROTECTED に `/.claude/spec/data_unlock.txt` と `/scripts/data_summary.py` |
| `.claude/settings.json` | staging が拡張。PreToolUse に matcher `"Read"` を新設し data_read_gate を登録 |
| `doctor.sh` / `doctor.ps1` | `[DATA-KEY-RECIPIENTS-MISSING]` / `[DATA-AGE-MISSING]` / `[DATA-PROFILE-UNSET]` を追加 |
| `tests/test_data_protection_phase2.py` | マーカー数の期待値 7 → 10(1行) |
| `README.md` | synthetic 規約・復号手順・Grep の既知の限界・一時解除手順・環境変数表・ファイルツリー |
| `templates/settings.local.json.template` | `CLAUDE_DATA_PROFILE` / `CLAUDE_DATA_NO_READ` / `CLAUDE_DATA_GATE` を既定 `""` で追加 |
| `.claude/skills/config-set/SKILL.md` / `config-explain/SKILL.md` | 雛形JSONと変数表に同3変数を追加 |
| `claude-init.sh` / `claude-init.ps1` | 新 scripts 2本を配布リスト + IGNORE_ENTRIES に追加。**加えて** OPTIONAL_FEATURES(sh: `OPTIONAL_FEATURES` 配列 / ps1: `$OptionalFeatures`)にフラグ系2変数を追加 |
| `claude-update.sh` / `claude-update.ps1` | 新 scripts 2本を配布リスト + IGNORE_ENTRIES に追加**のみ**。機能有効化プロンプトは新設しない(update 側に該当の仕組みが無い) |

## 事後条件(postconditions)

期待値は設計書の受け入れ条件と上記「確定事項」から導いた。実装前に Step 1 でテスト化する。

| ID | 対象 | 入力 | 満たすべき条件 | R-ID |
|----|------|------|---------------|------|
| PC-1 | `.claude/hooks/data_read_gate.py` | env `CLAUDE_DATA_NO_READ=1`、stdin の `tool_input.file_path` が サンドボックス配下の `data/raw/x.csv` | exit 2。stderr が `data_summary` と `data_unlock` の両方の文字列(=次の行動)を含む | R-001 |
| PC-2 | 同上 | 同 env、`data/synthetic/a.csv` / `data/exports/a.csv` / `data/data.lock` / `data/.backup_stamp` の4入力 | すべて exit 0、stderr は空 | R-002 |
| PC-3 | 同上 | env `CLAUDE_DATA_NO_READ=raw` | `data/raw/x.csv` は exit 2、`data/processed/x.csv` は exit 0 | R-003 |
| PC-4 | 同上 | env 未設定 / `CLAUDE_DATA_NO_READ=0`(PROFILE も空) | `data/raw/x.csv` で exit 0 | R-004 |
| PC-5 | 同上 | 非JSON の stdin / `tool_input` 欠落 / `file_path` が `src/train.py` / `file_path` が `metadata/x.csv` | すべて exit 0(過剰ブロックなし) | R-005 |
| PC-6 | `.claude/hooks/data_gate.py` | env `CLAUDE_DATA_NO_READ=1`、cmd `cat data/raw/x.csv` / `head -5 data/raw/x.csv` / `tail data/raw/x.csv` / `less data/raw/x.csv` / python のワンライナーで同ファイルを開くコマンド | すべて exit 2。同じ cmd を env `CLAUDE_DATA_GATE=1` のみ(NO_READ・PROFILE 空)で与えると exit 0(Phase 2 の挙動不変) | R-006 |
| PC-7 | 同上 | env `CLAUDE_DATA_NO_READ=1`、cmd `uv run python scripts/data_summary.py data/raw/x.csv` | exit 0 | R-007 |
| PC-8 | `data_read_gate.py` と `data_gate.py` | `CLAUDE_SPEC_DIR` 配下の `data_unlock.txt` に (a) 未来の UTC epoch (b) 過去の epoch (c) 非整数の文字列 (d) 空ファイル、の4状態で遮断対象の入力 | (a) 両方 exit 0 かつ stderr に解除中である旨を含む。(b)(c)(d) いずれも両方 exit 2(壊れた記録は「解除されていない」として fail-closed。spec-checklist LOW の反映) | R-008 |
| PC-9 | `.claude/hooks/guard_bash.py` | cmd `uv run python .claude/hooks/data_unlock.py --minutes 30` / `cp .claude/hooks/data_unlock.py /tmp/x.py` / `grep -n minutes .claude/hooks/data_unlock.py` | 前2つは exit 2(stderr に `!` 実行の案内)、grep は exit 0 | R-009 |
| PC-10 | `.claude/hooks/guard_scope.py` | Write の `file_path` がサンドボックス配下の `.claude/spec/data_unlock.txt` | exit 2 | R-009 |
| PC-11 | `scripts/data_summary.py` | 3列(数値2列・文字列1列)×4行、欠損1件を含む csv / tsv / json / jsonl | exit 0。stdout に 行数・列数・全列名・列ごとの型・欠損数・数値列の min/max/mean/std・12桁の16進ハッシュが現れる | R-010 |
| PC-12 | 同上 | 全セルに一意な既知の値(例 `ZZTOPSECRET1` 等)を埋めた上記4形式 | stdout・stderr のどこにもセル値が1件も現れない(列名は除く) | R-011 |
| PC-13 | 両フックのプロファイル解決 | `CLAUDE_DATA_PROFILE` が sensitive / internal / public / 空 × 個別変数が空、の全組み合わせ | sensitive→(NO_READ 有効, GATE 有効)、internal→(無効, 有効)、public・空→(無効, 無効)。**両フックの実効結果が全組み合わせで一致する** | R-012 |
| PC-14 | 同上 | `CLAUDE_DATA_NO_READ=0` + `CLAUDE_DATA_PROFILE=sensitive` / `CLAUDE_DATA_GATE=0` + 同 profile | 前者は `data/raw/x.csv` の Read が exit 0、後者は data/raw を curl で送信するコマンドが exit 0(個別変数が優先) | R-013 |
| PC-15 | `templates/settings.local.json.template`・`config-set/SKILL.md`・`config-explain/SKILL.md`・`claude-init.sh`/`.ps1` | ファイル内容 | `CLAUDE_DATA_PROFILE` / `CLAUDE_DATA_NO_READ` / `CLAUDE_DATA_GATE` の3変数が template・config-set(雛形JSONと変数表)・config-explain(変数表)のすべてに現れる。template は `json.loads` でパースでき、3変数の値がいずれも `""`、かつ既存キーが1つも消えていない。`claude-init.sh` / `.ps1` の OPTIONAL_FEATURES(sh: `OPTIONAL_FEATURES` / ps1: `$OptionalFeatures`)には `CLAUDE_DATA_NO_READ` と `CLAUDE_DATA_GATE` だけが現れ、`CLAUDE_DATA_PROFILE` は現れない。`claude-update.sh` / `.ps1` には3変数のいずれも現れない(機能有効化プロンプトを新設していないこと) | R-014 |
| PC-16 | `scripts/backup_encrypt.py` | age を含まない PATH で実行 | 非0終了。stderr に age の導入案内。実行前後で data/ 配下のファイル一覧と各 sha256 が不変、出力先ファイルが生成されていない。age 実在時のみ追加検証: recipient 2件で出力ファイルが生成され、先頭に age 形式の識別子を含む | R-015 |
| PC-17 | `doctor.sh`(サンドボックス実行) | recipients ファイル無し / 鍵1本だけ / age 不在 PATH | それぞれ `[DATA-KEY-RECIPIENTS-MISSING]`(前2者)・`[DATA-AGE-MISSING]` を出力し、**終了コードは警告なしの場合と同じ** | R-016 |
| PC-18 | 同上 | `data/DATA_LOG.md` にデータ行1行以上 + プロファイル無効 / 同 + `CLAUDE_DATA_PROFILE=sensitive` | 前者のみ `[DATA-PROFILE-UNSET]` を出力。終了コードは不変 | R-017 |
| PC-19 | `README.md` | ファイル内容 | (a) data/synthetic の役割詳細、(b) age 復号手順、(c) Grep/Glob が遮断対象外である既知の限界、(d) 一時解除の `!` 実行手順、の4トピックがいずれも記載されている。加えて (e) 既存の `#### data_gate(送信経路の静的ゲート)` 段落にプロファイル(`CLAUDE_DATA_PROFILE`)への言及があり、`CLAUDE_DATA_GATE=1` だけを前提とした説明が残っていない | R-018 |
| PC-20 | installer 4本 + サンドボックス配布 | `claude-init.sh` / `.ps1` / `claude-update.sh` / `.ps1` の scripts 名の集合、IGNORE_ENTRIES 2箇所、E2E 配布 | 4本の scripts 名集合が一致し `data_summary.py`・`backup_encrypt.py` を含む。IGNORE_ENTRIES 2箇所にも両方。E2E 配布後に両ファイルが実在する | R-019 |
| PC-21 | `doctor.sh` / `doctor.ps1` | `[DATA-...]` 形式のマーカーの抽出集合 | sh と ps1 が一致し、要素数がちょうど10。新3マーカーを含む | R-020 |
| PC-22 | `_staging_data_protection_p3.py --root [dir]` | 同一サンドボックスに2回適用 | 2回目適用後の `settings.json` / `data_gate.py` / `guard_bash.py` / `_common.py` が1回目適用後とバイト単位で一致。2回目も exit 0。`settings.json` の PreToolUse に matcher `"Read"` がちょうど1つ、data_read_gate 登録もちょうど1つ | R-021 |
| PC-23 | `.claude/hooks/*.py` | 全ファイルの内容 | `import scripts` / `from scripts` に相当する記述が0件 | R-022 |
| PC-24 | `tests/` 全体 | `uv run --with pytest python -m pytest tests/ -q` | 失敗0(staging 未適用の間は該当ケースが skip でよい) | R-023 |
| PC-25 | `.claude/hooks/data_unlock.py`(`CLAUDE_SPEC_DIR` をサンドボックスに向けて直接実行) | `--minutes` 省略 / `--minutes 240` / `--minutes 241` / `--minutes 0` / `--minutes -5` | 省略時は現在時刻+30分(±60秒)の UTC epoch が `data_unlock.txt` に1行だけ記録され exit 0。240 は同様に成功。241・0・-5 はいずれも非0終了し、**記録ファイルが作られない・既存の記録が書き換わらない** | R-008 |

## 実装手順

| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 1 | **テストファースト**: PC-1〜PC-25 を受け入れテストとして書き、全件 RED(または skip)を確認する。`tests/test_data_protection_phase2.py` の様式に倣う(冒頭 docstring で契約明記・`_ROOT` 定数・subprocess 起動・`pytestmark_staging` 相当の skip・doctor は同ファイル 252-295 行の `place_installers` 方式)。テスト名は設計書の `-k` キーワード(`read_gate_blocks` 等)にそのまま一致させる(PC-25 は `unlock_window` を含む名前にして `-k unlock_window` で拾えるようにする)。**ここで固定する契約**: (a) 解除記録 `.claude/spec/data_unlock.txt` の形式 = UTC epoch 秒の整数1行、(b) `CLAUDE_DATA_NO_READ` の値の形 = `1` または data/ 直下のサブディレクトリ名のカンマ区切り、(c) プロファイル解決の戻り値 = (NO_READ 有効, GATE 有効) の2値、(d) `--minutes` の既定30・上限240。Step 2〜9 が別グループで並列実装されるため、ここで固定しないと食い違う。staging 依存のケース(PC-1〜PC-10・PC-13・PC-14・PC-22・PC-25)は `_staging_data_protection_p3.py` または `.claude/hooks/data_read_gate.py` が無ければ skip する。**注意**: age 不在経路のテストで PATH を空にすると python 自体が起動できなくなるので、`sys.executable` の絶対パスで起動しつつ PATH だけを空ディレクトリに差し替える (R-001〜R-023 対応) | `tests/test_data_protection_phase3.py` | なし | A |
| 2 | 窓口スクリプトを実装する。csv/tsv/json/jsonl を標準ライブラリのみで読み、shape・列名と型・欠損数・数値列の min/max/mean/std・sha256 先頭12桁を出力する。**個票の値を出力する経路を一切持たせない**(ユニーク値一覧・サンプル行・例外メッセージへの行内容の埋め込みも禁止。例外時もファイル名と行番号だけを出す)。既存 `scripts/data_scan.py` の CLI 様式と MARKER 行の入れ方に倣う (R-010, R-011 対応) | `scripts/data_summary.py` | Step 1 | B |
| 3 | バックアップ暗号化を実装する。data/(exports/ 除く)を tar にまとめ、`.claude/backup_recipients.txt` の公開鍵2件を recipient 指定して age で暗号化する。鍵が2件未満・age 未導入はいずれも**データを一切変更せず**案内を出して非0終了する(出力先の書きかけファイルも残さない)。`scripts/export_check.py` の引数・終了コードの様式に倣う (R-015 対応) | `scripts/backup_encrypt.py` | Step 1 | B |
| 4 | staging スクリプトを1本作る。適用内容は (a) `data_read_gate.py` の配置、(b) `data_unlock.py` の配置(`--minutes` 既定30・上限240。上限超過・0以下はエラーで非0終了し記録を書かない。記録は UTC epoch 秒の整数1行で上書き)、(c) `data_gate.py` の拡張、(d) `guard_bash.py` に data_unlock の実行・複製ブロック追加、(e) `_common.py` の PROTECTED に2件追加、(f) `settings.json` の PreToolUse に matcher `"Read"` を新設して data_read_gate を登録。**6操作すべてを冪等にする**(適用済みか判定してから書く。settings.json は配列・オブジェクト追加、他は行挿入なので素朴に書くと2回目で重複する。PC-22)。`--root [dir]` を受ける。**注意1**: (c) は `data_gate.py:66` の先頭オプトイン分岐をプロファイル解決に置き換えるが、`CLAUDE_DATA_GATE=1` のみが与えられたときの挙動(egress だけ遮断・読みは通す)を変えてはならない(既存 Phase 2 テストが退行する。PC-6 後半)。**注意2**: (d) は `guard_bash.py:270-310` の既存ブロック実装と同じ構造にし、読み取り専用コマンド集合の例外も同じく効かせる。**注意3**: (f) の Read matcher 追加で他の matcher 配列を書き換えないこと (R-001〜R-009・R-012・R-013・R-021 対応) | `_staging_data_protection_p3.py` | Step 1 | C |
| 5 | doctor に3マーカーを追加する。`[DATA-KEY-RECIPIENTS-MISSING]`(`.claude/backup_recipients.txt` が無い/鍵が2未満)・`[DATA-AGE-MISSING]`(age 未導入)・`[DATA-PROFILE-UNSET]`(DATA_LOG にデータ行があるのにプロファイル実効が無効)。既存 `doctor.sh:180-203` / `doctor.ps1:196-222` の節の書式・警告文の言い回しに倣い、**終了コードを変えない**。sh と ps1 に対称に入れる (R-016, R-017, R-020 対応) | `doctor.sh`, `doctor.ps1` | Step 1 | D |
| 6 | 既存 parity テストの期待値を 7 から 10 に更新する(`tests/test_data_protection_phase2.py:924` の1行のみ。他は触らない)。Step 5 と同時に入れないと Phase 2 テストが赤になる (R-020, R-023 対応) | `tests/test_data_protection_phase2.py` | Step 5 | D |
| 7 | README を追記する。3.21 節に (a) data/synthetic の役割詳細(実データと同スキーマの合成サンプル・遮断対象外・テストとデバッグはここで行う)、(b) 読み取り遮断とプロファイルの説明(3変数の関係と解決規約)、(c) 一時解除の `!` 実行手順(既定30分・上限240分)、(d) age 復号の手動手順と秘密鍵は環境外管理である旨、(e) Grep/Glob は遮断対象外という既知の限界。**既存の `#### data_gate(送信経路の静的ゲート)` 段落(`README.md:1489-1493`)を、プロファイル解決を踏まえた説明に更新する**(`CLAUDE_DATA_GATE=1` 前提の記述と新しいプロファイルの説明が併存しないようにする。PC-19 (e))。あわせて環境変数表(263行付近。既存の `CLAUDE_DATA_GATE` 行の既定表記を、出荷時 `""` かつプロファイル解決に委ねる旨に整える)・4.5 節の doctor マーカー一覧・ファイルツリーの scripts/ 一覧に新規分を追記する。既存 3.21 節の小見出し(`#### バックアップ記録(data/.backup_stamp)` 等)の粒度に倣う (R-018 対応) | `README.md` | Step 1 | E |
| 8 | 設定の配線。`templates/settings.local.json.template` に `CLAUDE_DATA_PROFILE` / `CLAUDE_DATA_NO_READ` / `CLAUDE_DATA_GATE` を**いずれも既定 `""`** で追加し(現状これらのキーは1件も無いため追加のみ)、`config-set` の雛形 JSON と変数表、`config-explain` の変数表に同じ3変数を追加する。既存の `CLAUDE_SESSION_MONITOR` の並び・説明文の書式に倣う。変数表にはプロファイル解決規約(個別変数が非空なら優先)を1行で書く。template は JSON として妥当なまま保つ (R-014 対応) | `templates/settings.local.json.template`, `.claude/skills/config-set/SKILL.md`, `.claude/skills/config-explain/SKILL.md` | Step 1 | E |
| 9 | 配布の配線。`claude-init.sh` / `claude-init.ps1` / `claude-update.sh` / `claude-update.ps1` の scripts 配布リストに `data_summary.py` と `backup_encrypt.py` を追加し、`claude-init.sh:107-109` と `claude-update.sh:92` 相当の IGNORE_ENTRIES にも追加する(sh/ps1 で1対1)。あわせて OPTIONAL_FEATURES には**フラグ系の `CLAUDE_DATA_NO_READ` と `CLAUDE_DATA_GATE` の2つだけ**を追加する(`CLAUDE_DATA_PROFILE` は3値のため載せない。`enable_feature()` / `Enable-Feature` のロジックは変更しない)。**OPTIONAL_FEATURES への追加先は `claude-init.sh`(`OPTIONAL_FEATURES` 配列)と `claude-init.ps1`(`$OptionalFeatures`)だけ**であり、`claude-update.sh` / `.ps1` は**配布リストと IGNORE_ENTRIES のみ**を変更する(update 側には機能有効化の仕組みが無く、本計画でも新設しない。確認済み)。**注意**: doctor の scripts 差分検査は `find` による全走査なので追加変更は不要(現状分析の裏取り済み)。既存 `scripts/data_scan.py` の記載箇所と同じ並びに足す (R-014, R-019 対応) | `claude-init.sh`, `claude-init.ps1`, `claude-update.sh`, `claude-update.ps1` | Step 1 | F |
| 10 | ユーザーに `! uv run python _staging_data_protection_p3.py` の実行を依頼し、適用後に skip していたケースが PASS することを確認する。**注意**: Step 4 の (e) で `scripts/data_summary.py` が保護パスになるため、適用後は Step 2 の成果物を Edit で直せない。適用前に Step 2 のテストが緑であることを確認してから依頼する (R-024, R-023 対応) | (なし) | Step 2〜9 すべて | A |

並列化判定: **並列化可能**(グループ B・C・D・E・F。Step 1 を先に完了させたうえで、
B=scripts 新規2本 / C=staging 1本 / D=doctor 2本+Phase2 テスト1行 / E=文書と設定雛形 /
F=installer 4本 と、対象ファイルが完全に分離しているため。Step 10 は全グループ合流後の
逐次ステップ)

## 検証方法

| 何を | コマンド | PASS 条件 |
|------|---------|----------|
| Phase 3 受け入れ | `uv run --with pytest python -m pytest tests/test_data_protection_phase3.py -q` | 失敗0(staging 未適用のケースは skip でよい) |
| 全体退行 | `uv run --with pytest python -m pytest tests/ -q` | 失敗0 |
| 複数ある場合(入力の形の網羅) | `uv run --with pytest python -m pytest tests/test_data_protection_phase3.py -q -k "read_gate or bash_read"` | data/ 参照が**1つの場合**(`cat data/raw/a.csv`)・**複数ある場合**(`cat data/raw/a.csv data/processed/b.csv`)・**除外と非除外の混在**(`cat data/exports/ok.csv data/raw/a.csv` は遮断)・**窓口と生読みの混在**(窓口実行の後段に `cat data/raw/a.csv` を連結したコマンドは遮断)のすべてで期待どおり |
| 入れ子・多段の場合 | 同上 | パイプ・`&&`・`;` で連結したコマンド、`data/raw/sub/dir/x.csv` のような深い階層、`./data/raw/x.csv` のような相対表記でも判定が変わらない |
| 一時解除の境界値 | `uv run --with pytest python -m pytest tests/test_data_protection_phase3.py -q -k unlock_window` | 既定30分・240分は成功、241分・0・負値はエラーかつ記録が変わらない(PC-25) |
| staging 冪等 | `uv run --with pytest python -m pytest tests/test_data_protection_phase3.py -q -k staging_idempotent_p3` | 2回適用後もバイト一致・exit 0 |
| フック単体 | `./verify-hooks.sh` | 既存の全ケース PASS |
| installer 配布 | `./verify-installers.sh` | 既存の全ケース PASS |
| 記述と実装の整合 | doctor.sh と doctor.ps1 から `[DATA-...]` マーカーを `grep -oE` で抽出して `sort -u` し `diff` で比較する(`.claude/rules/consistency.md` の標準形) | 差分なし(件数は生・一意の両方を報告する) |

## リスク

- **既存 Phase 2 テストの期待値を書き換える**: `len(sh_markers) == 7` を 10 にする。
  マーカーを増やす以上は不可避で、Step 5 と Step 6 を同じグループに置いて同時に更新する。
  数値以外(sh/ps1 一致・新マーカーの部分集合)の検査は緩めない。
- **data_gate の拡張が Phase 2 の挙動を変えうる**: `CLAUDE_DATA_GATE=1` だけを設定していた
  既存利用者にとって、cat/head が突然ブロックされると運用が壊れる。読み遮断は
  NO_READ 実効有効時のみに限定する(PC-6 後半がこの契約の番人)。
- **窓口許可の判定が緩いと素通りする**: 窓口スクリプト名を echo するだけのセグメントと
  生読みセグメントを連結した文字列で許可してはならない。セグメント単位で判定し、
  「全セグメントが窓口実行または data/ 非参照」のときだけ許可する。
- **Read 遮断の過剰ブロック**: `/data/` の部分一致で `metadata/` 等を巻き込むと、
  data/ と無関係な作業まで止まる(PC-5 が検知)。
- **解除記録の読み取り失敗**: 記録が壊れている・読めないときに「解除中」と誤読すると
  遮断が無効化する。読めない・解釈できない場合はすべて「解除されていない」として扱う
  (遮断の目的上、ここだけは fail-closed 側に倒す)。
- **template への3変数追加が既存利用者の設定を上書きしない**: `settings.local.json` は
  IGNORE_ENTRIES に入っており installer は既存ファイルを尊重する。追加した変数が
  既存プロジェクトに現れないケースは想定内で、フック側は未設定=空として扱う。
- 検討した代替案と不採用理由:
  - **案A: settings.json の permissions.deny に data/ の Read 拒否を足すだけにする** —
    実装は最小だが、パス粒度指定・プロファイル・一時解除・行動つきブロック文言・
    監査痕跡のいずれも作れない。不採用。
  - **案B: data_read_gate を作らず data_gate に統合し、`tool_name` で分岐する** —
    フックは1本で済むが、Read のたびに egress 用の判定まで読み込むことになり責務も混ざる。
    設計書の「Read 毎に走るため 100ms 級」に反する方向。不採用。
  - **案C: 窓口 `scripts/data_summary.py` を保護パスに入れない** — 保守は楽だが、
    窓口を Edit で書き換えれば読み取り遮断を丸ごとバイパスできる。不採用(ADR-0010)。
  - **案D: プロファイル解決を共有モジュール化する** — 重複は消えるが、hooks 自己完結
    原則(R-022)と衝突し、共有先が壊れると両ゲートが同時に死ぬ。不採用。
  - **案E: `enable_feature()` を「変数名|説明|設定値」形式に拡張して 3値のプロファイルも
    OPTIONAL_FEATURES に載せる** — 対話で機密度まで選べるが、installer 4本の共通ロジック
    変更となり既存11機能すべての回帰確認が要る。不採用(確定事項 Q1=A)。
- 確認済み(公式ドキュメント https://code.claude.com/docs/en/hooks.md 、確認日 2026-08-22): matcher `"Read"` の PreToolUse は有効、`tool_input` は `file_path` を持ち、exit 2 で Read が中断され stderr が Claude に表示される。相対/絶対の明示が無いため相対解決は維持する。実機での最終確認は Step 10 で行う(価値が残るため手順として存置)
- 未確認の仮定: age は本環境の PATH に存在しない(暗号化経路のテストは条件付き実行になる) / 検証: `command -v age` / 期待: 何も出力せず終了コードが1
- Phase 2 と同じ既知のトレードオフ: staging 適用(Step 10)まで新規テストの一部は skip

## トレーサビリティ

| ID | 対応ステップ | 検証方法 |
|--------|------------|---------|
| R-001 | Step 1, 4 | `uv run --with pytest python -m pytest tests/test_data_protection_phase3.py -q -k read_gate_blocks` |
| R-002 | Step 1, 4 | 同 `-k read_gate_allows_excluded` |
| R-003 | Step 1, 4 | 同 `-k read_gate_granular` |
| R-004 | Step 1, 4 | 同 `-k read_gate_off` |
| R-005 | Step 1, 4 | 同 `-k read_gate_fail_open_input` |
| R-006 | Step 1, 4 | 同 `-k bash_read_blocked` |
| R-007 | Step 1, 2, 4 | 同 `-k bash_read_allows_summary` |
| R-008 | Step 1, 4 | 同 `-k unlock_window`(PC-8 の期限判定と PC-25 の既定30分・上限240分を含む) |
| R-009 | Step 1, 4 | 同 `-k unlock_agent_blocked` |
| R-010 | Step 1, 2 | 同 `-k summary_outputs` |
| R-011 | Step 1, 2 | 同 `-k summary_no_row_values` |
| R-012 | Step 1, 4 | 同 `-k profile_resolution` |
| R-013 | Step 1, 4 | 同 `-k profile_individual_override` |
| R-014 | Step 1, 8, 9 | 同 `-k profile_wiring_docs` |
| R-015 | Step 1, 3 | 同 `-k backup_encrypt` |
| R-016 | Step 1, 5 | 同 `-k doctor_key_checks` |
| R-017 | Step 1, 5 | 同 `-k doctor_profile_unset` |
| R-018 | Step 1, 7 | 同 `-k docs_phase3` |
| R-019 | Step 1, 9 | 同 `-k scripts_distributed_p3` |
| R-020 | Step 1, 5, 6 | 同 `-k doctor_parity_p3` |
| R-021 | Step 1, 4 | 同 `-k staging_idempotent_p3` |
| R-022 | Step 1, 4 | 同 `-k hooks_selfcontained_p3` |
| R-023 | Step 6, 10 | `uv run --with pytest python -m pytest tests/ -q` |
| R-024 | Step 10 | (目視) ユーザーの `!` 実行後、staging 依存のテストが skip から PASS に変わる |
