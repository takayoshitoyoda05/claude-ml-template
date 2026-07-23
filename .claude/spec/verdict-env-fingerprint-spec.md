# verdict: env-fingerprint-spec

参照設計書: `docs/active/env-fingerprint-spec.md`
参照計画: `.claude/plans/20260723-env-fingerprint.md`
評価日: 2026-07-23(最終状態 a8d8a46 再レビュー、対象範囲 `63a9527~1..a8d8a46`)
総合判定: PASS

| ID | 判定 | 実行コマンド | 実測値 | 証拠(file:line) |
|---|---|---|---|---|
| R-001 | PASS | `uv run python scripts/env_fingerprint.py; echo $?` | exit=0, JSON1行出力 | scripts/env_fingerprint.py:117-156 |
| R-002 | PASS | `uv run python scripts/env_fingerprint.py \| python3 -c "import json,sys; json.load(sys.stdin)"` | exit=0 | scripts/env_fingerprint.py:127 |
| R-003 | PASS | `uv run python scripts/env_fingerprint.py \| python3 -c "...list(d)==[...]"` | exit=0, キー順一致 | scripts/env_fingerprint.py:107-114 |
| R-004 | PASS | 空の一時ディレクトリで `uv run --project ... python .../env_fingerprint.py \| ...assert uv_lock_sha256 is None and git_commit is None` | exit=0 | scripts/env_fingerprint.py:45-62,65-77 |
| R-005 | PASS | `grep -nE "^\s*(import \|from )" scripts/env_fingerprint.py` | トップレベル import は hashlib/json/os/platform/subprocess/sys/pathlib のみ。torch は88行目で関数内try-import | scripts/env_fingerprint.py:12-18,88 |
| R-006 | PASS | `grep -q env_fingerprint README.md` | exit=0 | README.md:940-947 |
| R-007 | PASS | `grep -q env_fingerprint CHANGELOG.md` | exit=0 | CHANGELOG.md:49-51 |
| R-008 | PASS | `bash ./verify-hooks.sh` | exit=0, 全テストPASS | verify-hooks.sh 出力: "全テストPASS" |
| R-009 | PASS | torch import可否と出力null/非nullの自己整合スクリプト | exit=0(本環境はtorch未導入、両者null一致) | scripts/env_fingerprint.py:80-95 |
| R-010 | PASS | 一時ディレクトリでuv.lockに"test"を書きSHA-256照合 | exit=0, 期待ハッシュと一致 | scripts/env_fingerprint.py:65-77 |
| R-011 | PASS | `git_commit` 出力と `git rev-parse HEAD` を比較 | exit=0, 一致(a8d8a46596bc9f2fb5bdbf3f332a059ff8982bd6) | scripts/env_fingerprint.py:45-62 |

## 修正履歴のトレース(63a9527 → a3f5397 → a8d8a46)

| # | 指摘 | 対応コミット | 最終検証結果 |
|---|---|---|---|
| 1 | subprocess timeout | 63a9527 (`timeout=5`) | 解決確認: ハングするダミー `git` バイナリで約5.0秒後に打ち切られ `git_commit: null`、exit=0 |
| 2 | torch属性のstr()変換 | 63a9527 | 解決確認: `__version__` が `__repr__` のみのダミーオブジェクトでも `str()` 経由で文字列化されJSON出力・exit=0 |
| 3 | READMEにリポジトリルート実行の前提 | 63a9527 | 解決確認: README.md:946-947 に追記済み |
| 4 | main()のexit 0契約完全化(非直列化可能値) | 63a9527 | 解決確認: fake torch(非JSON直列化オブジェクト・str()失敗オブジェクト)いずれも exit=0 |
| 5 | main()のexit 0契約完全化(BrokenPipe) | a3f5397, a8d8a46 | **解決確認**(今回の再レビューで新規検証)。`print`/`flush` を `except BrokenPipeError` で捕捉し、インタプリタ終了時の自動flushでSIGPIPEが再発しないよう `os.dup2` で stdout を devnull に差し替える実装(scripts/env_fingerprint.py:129-135, 150-155)。以下3通りの再現手順すべてで exit=0 を実測: (a) `uv run python scripts/env_fingerprint.py \| true` → pipestatus=0、(b) `python3 scripts/env_fingerprint.py \| head -c 0` を5回連続実行しすべてpipestatus=0、(c) FIFO経由でreaderが即座に読み取りをクローズするケースでpythonプロセス単独の終了コードを直接取得し0を確認。a8d8a46 のdevnull FD close漏れ修正(`os.close(devnull)` 追加)もFDリークなく動作することを `subprocess.Popen` + 即座の `stdout.close()` で確認(exit=0) |

## 総合所見

R-001〜R-011のauto要件は全件、実際にコマンドを再実行してexit 0を確認した(R-005 manualも
importの実文を確認しstdlibのみ・torchは関数内try-importであることを確認)。前回
(63a9527時点)でNEEDS_REVISIONの唯一の根拠だった「main()自身のdocstringが謳う
無条件exit0(『それすら書き込めない場合も0を返す』)がBrokenPipeErrorのケースで
守られていない」という指摘は、a3f5397のflush+devnull dup2実装、およびa8d8a46の
FD close漏れ修正により、複数の独立した再現手順(パイプの即時終了・reader即クローズ・
FIFO経由の単独終了コード取得)すべてでexit 0が確認でき、解消したと判断する。
EARS要件7件・受け入れ条件R-001〜R-011のすべてが実装と一致しているため、総合判定は
PASS とする。
