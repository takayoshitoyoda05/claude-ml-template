# 計画: env_fingerprint 受け入れ検証の pytest 回帰テスト化

- 設計書: なし(ユーザー直接依頼。承諾ゲート新フローの実走テストを兼ねた小実装)
- 参照した既存計画: `.claude/plans/20260723-env-fingerprint.md`(R-ID 定義の出所)
- ブランチ: `pipeline/20260724-env-fp-tests`

## 目的
`scripts/env_fingerprint.py` の受け入れ検証を使い捨て CLI コマンドから
`tests/test_env_fingerprint.py` の pytest 回帰テストへ恒久化し、
将来の変更で仕様が壊れたら CI/ローカルで自動検出できるようにする。

## 現状分析
- 現在この検証は `.claude/plans/20260723-env-fingerprint.md` の「検証方法」に
  ワンライナー群(R-002〜R-004, R-009〜R-011)として書かれているだけで、恒久テストが無い
  (`tests/` ディレクトリ自体が存在しない)。
- 確認済み: リポジトリに `pyproject.toml` も `uv.lock` も無い。それでも
  `uv run --with pytest python -m pytest ...` は動作する(実測: pytest 9.1.1 が起動)。
  → テスト実行の正式コマンドは `uv run --with pytest python -m pytest tests/ -q`。
- 確認済み(実測): 通常実行で有効 JSON・キー6個が固定順で出る。`/tmp` など git 外・
  uv.lock 無しの場所では `git_commit` と `uv_lock_sha256` が両方 null。
  `python3 scripts/env_fingerprint.py | head -c 1` は exit 0(BrokenPipe 耐性あり)。
- 確認済み: このリポジトリの `sys.executable`(/usr/bin/python3, 3.14.4)には torch 未導入。
  よって R-009 は「import 不可 ⇔ torch_version/cuda_version が null」の自己整合を検証する形にする。
- 確認済み: CHANGELOG は `### Added(YYYY-MM-DD)` の日付見出し慣習。最新は 2026-07-23。
  README のツリーは 6章(L1097〜)、`scripts/` 節は L1177、env_fingerprint 小節は 3.15 の L940。

## 変更対象
| ファイル | 変更内容 |
|---------|---------|
| `tests/test_env_fingerprint.py`(新規) | subprocess で `sys.executable scripts/env_fingerprint.py` を CLI 起動し R-002/003/004/009/010/011 + BrokenPipe を検証する pytest |
| `README.md` | 6章ツリーに `tests/` を追記、3.15 env_fingerprint 小節にテスト実行コマンド1行を追記 |
| `CHANGELOG.md` | `[Unreleased]` に `### Added(2026-07-24)` を新設しテスト恒久化を記載 |

## 実装手順
| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 1 | (テストファースト)テストファイルを新規作成し、まず未整備の失敗しうる形で骨組み→全 R-ID 検証を実装。subprocess で `sys.executable` を使い、スクリプトを import せず CLI として起動。R-004 は `tmp_path`(git 外・uv.lock 無し)を cwd に、R-010 は `tmp_path` に既知バイト列の uv.lock を置いて SHA-256 一致、R-011 は `tmp_path` で `git init`+コミットし cwd を移して HEAD 一致、R-009 は別 subprocess で `import torch` 可否を判定し出力の null/非null と突き合わせ、BrokenPipe は stdout を即クローズして exit 0 を確認 | `tests/test_env_fingerprint.py` | なし | A |
| 2 | 6章ツリーに `tests/` 行(`test_env_fingerprint.py  env_fingerprint.py の受け入れ回帰テスト`)を `scripts/` 付近へ追記し、3.15 の env_fingerprint 小節末尾にテスト実行コマンド `uv run --with pytest python -m pytest tests/ -q` を1行追記 | `README.md` | なし | B |
| 3 | `[Unreleased]` 先頭に `### Added(2026-07-24)` を新設し、env_fingerprint の受け入れ検証を pytest 回帰テスト化した旨を1項目で記載 | `CHANGELOG.md` | なし | C |

コミット案(各ステップ完了ごと。step N は本計画内の連番):
- Step 1: `test(step 1): env_fingerprint の受け入れ検証を pytest 回帰テスト化(R-002..R-011+BrokenPipe)`
- Step 2: `docs(step 2): README に tests/ とテスト実行コマンドを追記`
- Step 3: `docs(step 3): CHANGELOG に env_fingerprint テスト恒久化を記録`

補足(Step 1 の失敗回避メモ):
- `git init` 直後のコミットには author/committer 情報が要る。tmp repo 内で
  `git -c user.email=... -c user.name=...` 形式か環境変数(GIT_AUTHOR_NAME 等)で
  ユーザー設定に依存せず自己完結させる。
- torch 検証(R-009)は実値比較にする(Codex指摘の採用): 同一 `sys.executable` の別プロセスで
  `import torch` を試み、可能なら期待値 `str(torch.__version__)` / `str(torch.version.cuda) if torch.version.cuda is not None else None`
  を JSON で取得し、スクリプト出力と**フィールドごとに個別比較**する。import 不可なら両方 None を期待。
  CPU ビルド(torch有り・cuda None)でも正しく PASS する。
- BrokenPipe テストは `subprocess.Popen(stdout=PIPE)` で子の stdout を即 `close()` し、
  `wait()` の returncode が 0 であることを確認(親側で全読みしない)。移植性のため
  SIGPIPE ではなく returncode==0 を判定基準にする。
- サブプロセスの cwd を tmp_path にしても、スクリプトのパスは絶対パスで渡す。
- R-004 の「git 外」保証(Codex指摘の採用): `tmp_path` がリポジトリ配下に作られる環境でも
  親探索で本リポジトリを拾わないよう、サブプロセス環境変数に
  `GIT_CEILING_DIRECTORIES=<tmp_pathの親>` を設定して探索境界を固定する。

## 並列化判定
並列化可能(グループ A, B, C)。3ステップが `tests/test_env_fingerprint.py` /
`README.md` / `CHANGELOG.md` と完全に別ファイルで、内容上の依存も無いため。
ドキュメントに書くコマンド形はすでに実測で確定しており、テスト実装の完了を待つ必要がない。

## 検証方法
1. テスト全 PASS:
   `uv run --with pytest python -m pytest tests/ -q`
   → 期待: 全テスト PASS(exit 0)。
2. ミューテーションでの検出力確認(恒久ファイルは変更しない。ワークツリーで一時的に壊して戻す):
   - 前提確認(Codex指摘の採用): 改変前に `git status --porcelain scripts/env_fingerprint.py` が
     空(クリーン)であることを確認する(未コミット変更の巻き添え破棄を防ぐ)。
   - 例: `scripts/env_fingerprint.py` の `collect_fingerprint` のキー名を1つ改変
     (例 `"platform"` → `"platfrm"`)して 1 の pytest を実行 → 期待: R-003(キー固定)が FAIL。
   - 実行後、必ず `git checkout -- scripts/env_fingerprint.py` で原状復帰し、
     再度 1 を実行して全 PASS に戻ることを確認。
3. ドキュメント整合(目視):
   - `grep -n "tests/" README.md` で 6章ツリーに tests/ 行が存在。
   - 3.15 節に `pytest tests/ -q` を含む行が存在。
   - `CHANGELOG.md` 冒頭に `### Added(2026-07-24)` が存在。

## リスク
- 未確認の仮定: R-010/R-011 の tmp_path 経路と GIT_CEILING_DIRECTORIES の効き(いずれも
  テスト実装時の初回実行で確認する)。それ以外の主要挙動は実測済み。
- torch 依存: 検証環境に torch が入る/入らないで R-009 の期待値が変わるが、
  同一インタプリタで期待値を動的取得しフィールド個別比較する設計のため、
  torch なし・torch あり(CUDA/CPUビルドとも)のどの環境でも正しく PASS/FAIL 判定できる。
- 代替案1(スクリプトを import して関数を直接テスト): 実装コストは低いが、
  実運用(CLI 起動)と経路が異なり BrokenPipe / exit code / stdout 直列化の
  検証ができない → 不採用。ユーザー要件「import せず CLI として検証」にも反する。
- 代替案2(検証を bash スクリプト化して残す): 恒久化はできるが pytest の
  fixture(tmp_path)や CI 連携・可読性で劣る → 不採用。
- 代替案3(pyproject.toml を新設して pytest を dev 依存に固定): 実行の再現性は
  上がるが、本タスクの範囲(テスト恒久化)を超える構成変更で minimal-diff に反する。
  `uv run --with pytest` で実行可能なことを実測済みのため今回は追加しない → 不採用。
- 副作用: `tests/` を新設するが既存動作への影響なし。README/CHANGELOG は追記のみ。

## トレーサビリティ
| ID | 要件 | 対応ステップ | 検証方法 |
|----|------|------------|---------|
| R-002 | 出力が有効 JSON | Step 1 | `pytest tests/ -q` で該当テスト PASS(`json.loads` 成功+exit 0) |
| R-003 | キーが固定6個・固定順 | Step 1 | 同上(`list(d) == [...]` 一致)。ミューテーション2で FAIL することも確認 |
| R-004 | uv.lock 無し・git 外で両方 null | Step 1 | 同上(tmp_path 実行で `git_commit`/`uv_lock_sha256` が None) |
| R-009 | torch の実値一致(import 不可なら両方 None、CPUビルドは cuda のみ None) | Step 1 | 同上(同一インタプリタで期待値を取得しフィールド個別比較) |
| R-010 | 既知内容の uv.lock で SHA-256 一致 | Step 1 | 同上(tmp_path に既知バイト列を置き `hashlib.sha256` 期待値一致) |
| R-011 | git 内で HEAD 一致 | Step 1 | 同上(tmp repo の `git rev-parse HEAD` と一致) |
| (追加) | BrokenPipe 耐性(exit 0) | Step 1 | 同上(子 stdout を即 close して returncode==0) |
| (ドキュメント) | README/CHANGELOG 同期 | Step 2, 3 | 検証方法3(grep/目視) |

本計画で回帰テスト化する全 R-ID(R-002〜004, 009〜011)を網羅(R-001/005〜008 は使い捨て検証・manual・ドキュメント系のため対象外)。Step 2/3 はドキュメント同期タスクのため R-ID 非対応。
