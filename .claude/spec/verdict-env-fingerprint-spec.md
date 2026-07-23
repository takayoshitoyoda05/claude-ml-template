# verdict: env-fingerprint-spec

参照設計書: `docs/active/env-fingerprint-spec.md`
参照計画: `.claude/plans/20260723-env-fingerprint.md`
評価日: 2026-07-23
総合判定: NEEDS_REVISION

| ID | 判定 | 実行コマンド | 実測値 | 証拠(file:line) |
|---|---|---|---|---|
| R-001 | PASS | `uv run python scripts/env_fingerprint.py; echo $?` | exit=0, JSON1行出力 | scripts/env_fingerprint.py:110-118 |
| R-002 | PASS | `uv run python scripts/env_fingerprint.py \| python3 -c "import json,sys; json.load(sys.stdin)"` | exit=0 | scripts/env_fingerprint.py:117 |
| R-003 | PASS | `uv run python scripts/env_fingerprint.py \| python3 -c "...list(d)==[...]"` | exit=0, キー順一致 | scripts/env_fingerprint.py:100-107 |
| R-004 | PASS | 空の一時ディレクトリで `uv run --project ... python .../env_fingerprint.py \| ...assert uv_lock_sha256 is None and git_commit is None` | exit=0 | scripts/env_fingerprint.py:42-58,61-73 |
| R-005 | PASS | `grep -nE "^\s*(import \|from )" scripts/env_fingerprint.py` | トップレベル import は hashlib/json/platform/subprocess/sys/pathlib のみ。torch は84行目で関数内try-import | scripts/env_fingerprint.py:10-15,84 |
| R-006 | PASS | `grep -q env_fingerprint README.md` | exit=0 | README.md:940-945 |
| R-007 | PASS | `grep -q env_fingerprint CHANGELOG.md` | exit=0 | CHANGELOG.md:49-51 |
| R-008 | PASS | `bash ./verify-hooks.sh` | exit=0, 全テストPASS | verify-hooks.sh 出力: "全テストPASS" |
| R-009 | PASS | torch import可否と出力null/非nullの自己整合スクリプト | exit=0(本環境はtorch未導入、両者null一致) | scripts/env_fingerprint.py:76-88 |
| R-010 | PASS | 一時ディレクトリでuv.lockに"test"を書きSHA-256照合 | exit=0, 期待ハッシュと一致 | scripts/env_fingerprint.py:61-73 |
| R-011 | PASS | `git_commit` 出力と `git rev-parse HEAD` を比較 | exit=0, 一致(5f6d1494bffdb957e0f8990b3a89ce4f16e9340f) | scripts/env_fingerprint.py:42-58 |

補足: 全auto要件(R-001〜R-004, R-006〜R-011)は実測でexit 0。ただし EARS要件7
「いかなる収集失敗でも exit code 0」については、main() (scripts/env_fingerprint.py:110-118)
が json.dumps/print を try/except で囲んでいないため、収集値が非JSON直列化可能な
場合に exit 1 で落ちることを実測で再現した(下記レポート参照)。この失敗モードは
現行の R-001〜R-011 の auto コマンドではテストされないため各IDはPASSのままだが、
設計書が明言する無条件exit 0という契約を完全には満たしていない実装上のギャップが
存在する。総合判定はこの点を理由に NEEDS_REVISION とする。
