# verdict: env-fingerprint-spec

参照設計書: `docs/active/env-fingerprint-spec.md`
参照計画: `.claude/plans/20260723-env-fingerprint.md`
評価日: 2026-07-23(修正コミット 63a9527 再レビュー)
総合判定: NEEDS_REVISION

| ID | 判定 | 実行コマンド | 実測値 | 証拠(file:line) |
|---|---|---|---|---|
| R-001 | PASS | `uv run python scripts/env_fingerprint.py; echo $?` | exit=0, JSON1行出力 | scripts/env_fingerprint.py:116-142 |
| R-002 | PASS | `uv run python scripts/env_fingerprint.py \| python3 -c "import json,sys; json.load(sys.stdin)"` | exit=0 | scripts/env_fingerprint.py:126 |
| R-003 | PASS | `uv run python scripts/env_fingerprint.py \| python3 -c "...list(d)==[...]"` | exit=0, キー順一致 | scripts/env_fingerprint.py:106-113 |
| R-004 | PASS | 空の一時ディレクトリで `uv run --project ... python .../env_fingerprint.py \| ...assert uv_lock_sha256 is None and git_commit is None` | exit=0 | scripts/env_fingerprint.py:44-61,64-76 |
| R-005 | PASS | `grep -nE "^\s*(import \|from )" scripts/env_fingerprint.py` | トップレベル import は hashlib/json/platform/subprocess/sys/pathlib のみ。torch は87行目で関数内try-import | scripts/env_fingerprint.py:12-17,87 |
| R-006 | PASS | `grep -q env_fingerprint README.md` | exit=0 | README.md:940-947 |
| R-007 | PASS | `grep -q env_fingerprint CHANGELOG.md` | exit=0 | CHANGELOG.md:49-51 |
| R-008 | PASS | `bash ./verify-hooks.sh` | exit=0, 全テストPASS | verify-hooks.sh 出力: "全テストPASS" |
| R-009 | PASS | torch import可否と出力null/非nullの自己整合スクリプト | exit=0(本環境はtorch未導入、両者null一致) | scripts/env_fingerprint.py:79-94 |
| R-010 | PASS | 一時ディレクトリでuv.lockに"test"を書きSHA-256照合 | exit=0, 期待ハッシュと一致 | scripts/env_fingerprint.py:64-76 |
| R-011 | PASS | `git_commit` 出力と `git rev-parse HEAD` を比較 | exit=0, 一致(63a95272c9e4a2605b14eb40e13f54e4107e07af) | scripts/env_fingerprint.py:44-61 |

## 63a9527 再レビュー結果(team-lead 依頼の4点)

| # | 依頼内容 | 判定 | 実測 |
|---|---|---|---|
| 1 | main() の try/except 化で exit 0 契約が完全化(fake torch / BrokenPipe) | **一部未解決** | fake torch(非JSON直列化オブジェクト・str()失敗オブジェクト)は exit=0 で修正確認。ただしダウンストリームが早期に読み取りを止めるケース(`env_fingerprint.py \| head -c 0`)では、main() 自体は 0 を return するが、CPython のインタプリタ終了時の stdout 自動flushで `BrokenPipeError` が発生し、プロセス自身の終了コードは **120**(FIFO経由で python プロセス単独の終了コードを直接確認、再現性あり)。scripts/env_fingerprint.py:119-122 のdocstringは「それすら書き込めない場合は何も出力せずに0を返す」と明言しているが、この経路は main() の外(atexitのstdout flush)で発生するため保護されておらず、docstringの主張と実挙動が一致しない |
| 2 | subprocess timeout=5 | **解決確認** | scripts/env_fingerprint.py:57。`git` をハングさせるダミーバイナリで実測: 約5.0秒で打ち切られ `git_commit: null`、exit=0 |
| 3 | torch 属性の str() 変換 | **解決確認** | scripts/env_fingerprint.py:89-92。`__version__`が非文字列(`__repr__`しか持たないダミーオブジェクト)でも `str()` 経由で "<Weird>" のような文字列に変換されJSON出力・exit=0 |
| 4 | README にリポジトリルート実行の前提1文 | **解決確認** | README.md:946-947「uv.lock はカレントディレクトリ基準で探索するため、リポジトリルート(uv.lockのある場所)で実行すること。」を追記済み |

補足: 全auto要件(R-001〜R-011)は今回も実測でexit 0。前回指摘した「非JSON直列化可能な収集値でexit 1」というシナリオは修正済みを確認した。ただし今回の再検証で
新たに、ダウンストリームの早期切断(BrokenPipeError)による exit 120 のケースを
実測で発見した。これはEARS要件7の文言(「収集失敗でも」)の狭義解釈では対象外の
可能性があるが、本コミットの docstring 自身が「常に0」「それすら書き込めない
場合も0を返す」と明言しているため、実装がその自己申告した契約を満たしていない。
このため総合判定は NEEDS_REVISION を維持する。
