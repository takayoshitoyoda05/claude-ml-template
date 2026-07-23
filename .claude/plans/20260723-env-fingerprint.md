# 実装計画: 環境フィンガープリント(env_fingerprint.py)

参照設計書: `/home/toyod/claude-ml-template/docs/active/env-fingerprint-spec.md`
(計画作成時に `docs/drafts/` から `docs/active/` へ移動済み)

## 目的

実験の再現に必要な実行環境(Python版数・プラットフォーム・git commit・
uv.lock ハッシュ・torch/CUDA版数)を1コマンドで機械可読な JSON として固定し、
MLflow や実験ログに添付できるようにする。

## 現状分析

- 確認済み: `scripts/` ディレクトリは存在しない(新規作成が必要)。
- 確認済み: リポジトリ直下に `pyproject.toml` も `uv.lock` も存在しない
  (本リポジトリはテンプレート配布物であり Python プロジェクトではない)。
  → 受け入れ条件 R-004 の「uv.lock が無い場所」条件は現状どこでも成立し、
    正常系として null が返る。
- 確認済み: `uv 0.11.29` は pyproject.toml が無くても `uv run python ...` および
  `uv run --project <dir> python ...` を実行できる(実測)。よって受け入れ条件の
  検証コマンド(R-001〜R-004)は現状のリポジトリでそのまま成立する。
- 確認済み: `README.md` にスクリプト説明の専用節は無い。スキル一覧(3.2)・
  研究ワークフロー(3.15)・ファイル一覧(6章)が実在の構成。
- 確認済み: `CHANGELOG.md` の `[Unreleased]` 内 `### Added(2026-07-23)` 節の
  末尾は 45〜48 行目(`### Changed(2026-07-22)` の直前)。既存慣習は
  種別ごと日付昇順・箇条書き。
- 確認済み: `verify-hooks.sh` はリポジトリ直下に実在(R-008 の検証対象)。
- 確認済み: `docs/active/`・`docs/archive/` はプランナー手順に従い作成済み。

## 変更対象

| ファイル | 種別 | 変更内容 |
|---|---|---|
| `scripts/env_fingerprint.py` | 新規 | 環境情報を収集し単一 JSON を標準出力へ。stdlib のみ、torch は try-import、常に exit 0 |
| `README.md` | 変更 | 研究ワークフロー節(3.15)に env_fingerprint の説明を追記。ファイル一覧(6章)に `scripts/env_fingerprint.py` を追加 |
| `CHANGELOG.md` | 変更 | `[Unreleased]` の `### Added(2026-07-23)` 末尾に1項目追加 |

## 実装方針(python-standards 適合)

- 型ヒント必須(公開関数 `collect_fingerprint() -> dict[str, str | None]` 等)。
  Python 3.10+ 構文(`str | None`)を使う。
- Google スタイル docstring を公開関数に付ける。
- import は標準ライブラリのみ(`json` / `sys` / `platform` / `hashlib` /
  `subprocess` / `pathlib`)。torch は関数内 try/except import で任意依存化。
- 収集項目は個別の小関数に分け、各収集を try/except で囲み、失敗時は当該キーを
  null にして継続(いかなる失敗でも exit 0)。
- 出力キーは固定順の dict:
  `python_version` / `platform` / `git_commit` / `uv_lock_sha256` /
  `torch_version` / `cuda_version`。
- `uv.lock` は「カレントディレクトリ」(`pathlib.Path("uv.lock")`)を見る
  (設計の EARS「カレントディレクトリに存在するとき」に忠実に。R-004 は cwd 依存)。
- git commit は `subprocess.run(["git","rev-parse","HEAD"])` を capture、
  非0終了/例外なら null。
- uv 非依存: `python3 scripts/env_fingerprint.py` 単体で動くこと(設計リスク欄)。
  → 注意: shebang `#!/usr/bin/env python3` を付けるが、実行は python 経由前提で可。

## 実装手順

| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 1 | (auto要件 R-001〜R-004, R-009〜R-011 / テストファースト)受け入れ検証コマンドを実装前に実行し、まず失敗することを確認 | (検証コマンド。恒久ファイルは作らず設計書の検証方法をそのまま使う) | なし | A |
| 2 | env_fingerprint.py 本体を実装(stdlib のみ・torch try-import・全キー固定・常に exit 0) | scripts/env_fingerprint.py | Step 1 | A |
| 3 | README 3.15 に env_fingerprint 説明を追記、6章ファイル一覧に scripts/env_fingerprint.py を追加 | README.md | なし | B |
| 4 | CHANGELOG の Added(2026-07-23) 末尾に1項目追加 | CHANGELOG.md | なし | C |

補足:
- Step 1 は「実装前に auto 要件テストを書く」プランナー必須ステップの充足。
  本タスクは tests/ 配下の pytest ではなく受け入れ条件が CLI 検証(auto要件
  R-001〜R-004, R-009〜R-011)で構成されるため、恒久テストファイルは新設せず、下記「検証方法」の
  コマンド群を Step 2 実装前に実行し全て失敗(スクリプト未存在)することを
  先に確認する形でテストファーストを担保する。
- Step 2 の注意(自己批判由来): (a) uv.lock を script のディレクトリ基準で
  読むと R-004 が cwd を変えても常に repo の uv.lock を見て失敗しうる → cwd 基準で
  読む。(b) torch import 失敗を握りつぶす except を広く取りすぎると他の
  ImportError も飲む → `except Exception` で当該収集のみに閉じる。(c) git 収集で
  subprocess が git 未導入時に FileNotFoundError → これも捕捉して null。

## 並列化判定

並列化可能(グループ A / B / C)。
理由: Step 3(README)・Step 4(CHANGELOG)・Step 1-2(scripts/)は
互いに異なるファイルのみを触り依存が無い。A 内(Step 1→2)のみ逐次。
ただし規模が小さく(1スクリプト+ドキュメント2箇所)、並列化の
オーケストレーションコストが上回るため、実運用は逐次実行でも可
(判定上は「並列化可能」だが必須ではない)。

## 検証方法

以下を順に実行し、全て PASS であること(R-ID 対応は下表)。

```
# R-001 exit 0
uv run python scripts/env_fingerprint.py; echo "exit=$?"     # exit=0

# R-002 有効なJSON
uv run python scripts/env_fingerprint.py | python3 -c "import json,sys; json.load(sys.stdin)"; echo "exit=$?"  # exit=0

# R-003 キーが固定6個・固定順(過不足なし)
uv run python scripts/env_fingerprint.py | python3 -c "import json,sys; d=json.load(sys.stdin); assert list(d) == ['python_version','platform','git_commit','uv_lock_sha256','torch_version','cuda_version']"; echo "exit=$?"  # exit=0

# R-004 空の一時ディレクトリ(uv.lock無し・git外)では両方 null
T=$(mktemp -d) && cd "$T" && uv run --project /home/toyod/claude-ml-template python /home/toyod/claude-ml-template/scripts/env_fingerprint.py | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['uv_lock_sha256'] is None and d['git_commit'] is None"; echo "exit=$?"; cd - >/dev/null  # exit=0

# R-009 torch の import 可否と出力の null/非null が一致(自己整合)
uv run python scripts/env_fingerprint.py | uv run python -c "
import json,sys
d=json.load(sys.stdin)
try:
    import torch; e=torch.__version__
except Exception:
    e=None
assert d['torch_version']==e"; echo "exit=$?"  # exit=0

# R-010 uv.lock があるとき正しい SHA-256
T=$(mktemp -d) && printf test > "$T/uv.lock" && cd "$T" && uv run --project /home/toyod/claude-ml-template python /home/toyod/claude-ml-template/scripts/env_fingerprint.py | python3 -c "import json,sys,hashlib; assert json.load(sys.stdin)['uv_lock_sha256'] == hashlib.sha256(b'test').hexdigest()"; echo "exit=$?"; cd - >/dev/null  # exit=0

# R-011 git リポジトリ内では現在の HEAD と一致
[ "$(uv run python scripts/env_fingerprint.py | python3 -c "import json,sys; print(json.load(sys.stdin)['git_commit'])")" = "$(git rev-parse HEAD)" ]; echo "exit=$?"  # exit=0

# R-005 標準ライブラリのみ(目視/manual): 関数内含む全 import 行を確認
grep -nE "^\s*(import |from )" /home/toyod/claude-ml-template/scripts/env_fingerprint.py
#   → 期待: json/sys/platform/hashlib/subprocess/pathlib のみ。torch は関数内 try-import で、
#     トップレベル import に torch が無いことを人間が承認する

# R-006 README に説明
grep -q "env_fingerprint" README.md; echo "exit=$?"          # exit=0

# R-007 CHANGELOG に記載
grep -q "env_fingerprint" CHANGELOG.md; echo "exit=$?"        # exit=0

# R-008 フック無変更(全PASS)
bash ./verify-hooks.sh; echo "exit=$?"                        # exit=0(全PASS)
```

## コミット(feat(step N) 形式。push は明示指示まで行わない)

- Step 2: `feat(step 2): 環境フィンガープリント収集スクリプトを追加`
- Step 3: `feat(step 3): READMEに env_fingerprint の説明とファイル一覧を追記`
- Step 4: `feat(step 4): CHANGELOG に env_fingerprint 追加を記録`

（Step 1 は検証確認のみで成果物なし。まとめて1コミットにする場合は
  `feat(step 2): 環境フィンガープリント(scripts/env_fingerprint.py)を追加` に
  README/CHANGELOG を含めてもよいが、上記の分割を推奨。）

## リスク

- 未確認の仮定: 実行環境に torch が導入されている場合の 5 秒目安
  (非機能要件)。目安であり硬い制約ではない(設計 8 章)。torch 未導入なら
  `torch_version`/`cuda_version` は null で即返る。
- `uv run` の前提: pyproject.toml が無いが uv 0.11.29 で実行可能なことを実測確認済み。
  ただし uv のバージョンが古い環境では `uv run` の挙動が異なる可能性(未確認の仮定)。
  → スクリプト自体は `python3` 単体で動くため、代替検証は `python3 scripts/...` で可能。
- 代替案1(全パッケージ列挙/pip freeze 相当): 情報量は増えるが stdlib のみの
  制約に反し torch/pip 依存を持ち込む。不採用(設計 non-goal)。
- 代替案2(uv.lock を repo ルート固定で探索): R-004 が cwd を変える意図に反し、
  「カレントディレクトリ」という EARS 記述にも反する。不採用(cwd 基準を採用)。
- 副作用: README/CHANGELOG は追記のみで既存記述を変更しない(最小 diff)。
  scripts/ 新規作成は既存フックのスコープ内(作業スコープ=リポジトリ全体)。

## トレーサビリティ

| ID | 対応ステップ | 検証方法 |
|----|------------|---------|
| R-001 | Step 1, 2 | `uv run python scripts/env_fingerprint.py; echo $?` → exit 0 |
| R-002 | Step 1, 2 | 出力を `json.load` で読める → exit 0 |
| R-003 | Step 1, 2 | 固定6キー・固定順に `list(d) ==` で一致 → exit 0 |
| R-004 | Step 1, 2 | 空の一時ディレクトリで `uv_lock_sha256` と `git_commit` が None → exit 0 |
| R-005 | Step 2 | (manual/人間承認)import 行が stdlib+条件付き torch のみ |
| R-006 | Step 3 | `grep -q env_fingerprint README.md` → exit 0 |
| R-007 | Step 4 | `grep -q env_fingerprint CHANGELOG.md` → exit 0 |
| R-008 | Step 2, 3, 4 | `bash ./verify-hooks.sh` → exit 0(全PASS) |
| R-009 | Step 1, 2 | torch の import 可否と出力の null/非null が一致(自己整合) → exit 0 |
| R-010 | Step 1, 2 | 既知内容の uv.lock で SHA-256 が期待値一致 → exit 0 |
| R-011 | Step 1, 2 | `git_commit` が `git rev-parse HEAD` と一致 → exit 0 |

全 R-ID に対応ステップあり(未対応の R-ID なし)。
