# 実装計画: session_monitor(コンテキスト重量化の handoff 推奨モニタ)

参照設計書: `/home/toyod/claude-ml-template/docs/active/20260820-session-monitor.md`
(受け入れ条件 R-001〜R-015。手順0.5 でユーザー承認済み)

experiment: false  # 学習・実験を含まないコード変更のみの計画

## 目的
セッションのコンテキスト使用量が重くなったことに、画面を見ていなくても気づけるようにする。
Stop フックが transcript の usage 実測値と auto-compact 回数から handoff を推奨する。
既存フック(checkpoint/reinject/record_session_state)の責務は変えず「気づき」だけを足す。

## 現状分析
- 確認済み: Stop フックの登録は `.claude/settings.json` の `hooks.Stop[0].hooks` 配列。
  現在 record_session_state / enforce_eval / spec_gate / codex_gate / quality_gate /
  plan_gate / notify の7件が並ぶ。
- 確認済み: `notify.py` の docstring に「配置は Stop フックの末尾」と明記されている
  (`.claude/hooks/notify.py` 冒頭)。したがって新フックは **notify.py の直前** に挿入する。
- 確認済み: `.claude/hooks/checkpoint_before_compact.py` は PreCompact ペイロードから
  `trigger`("manual"/"auto")と `transcript_path` を読んでいる(行35-36)。auto-compact
  回数の加算はこの既存の `trigger` 判定を使って追記できる。
- 確認済み: ペイロードの `session_id` は既存フックで使用実績がある
  (`action_log.py:39`, `agent_log.py:30` が `payload.get("session_id", "unknown")`)。
- 確認済み: `.claude/hooks/` と `.claude/settings.json` はガードによりエージェント書き込み
  不可。直近の前例は requirements_gate(コミット f3d78cf・ce1b971)で、staging スクリプトを
  ユーザーが `!` 実行して適用している。
- 確認済み: `.gitignore:17` に `/_staging_*` があり staging スクリプトはコミットされない。
  過去の staging スクリプトは適用後に削除済みで、リポジトリ内に現存しない。
- 確認済み: テストの前例 `tests/test_requirements_gate.py` は、フック本体が未適用の間
  `pytestmark = pytest.mark.skipif(not HOOK_PATH.exists(), ...)` で全件 skip し、
  適用後は subprocess で最小 env を渡して CLI 起動する。
- 確認済み: `verify-hooks.sh` / `.ps1` は guard 系のみを対象にしており、requirements_gate も
  含まれていない(`grep -n "requirements_gate" verify-hooks.sh` が 0 件)。よって本件でも
  verify-hooks は変更しない(最小diff)。
- 確認済み: 任意機能の配線先は `claude-init.sh:125-136` の `OPTIONAL_FEATURES` 配列と
  `claude-init.ps1:117-128` の `$OptionalFeatures` ordered dict。雛形の含有 assert の前例は
  `verify-installers.sh:92`。
- 確認済み: 雛形は `templates/settings.local.json.template` の `env` オブジェクト
  (`"CLAUDE_REQUIREMENTS_GATE": "0"` と同じ様式)。
- 確認済み: ドキュメントの整合先は README.md の環境変数表(244行付近)・フック一覧表
  (918-927行付近)・構成ツリー(1609行付近)、`.claude/skills/config-explain/SKILL.md` の
  変数表(21行付近)、`.claude/skills/config-set/SKILL.md` の雛形(28行付近)と変数表(54行付近)。

## 変更対象

| ファイル | 対象 | 変更内容 |
|---|---|---|
| tests/test_session_monitor.py | 新規 | R-001〜R-012 の受け入れテスト(未適用時は skip) |
| _staging_session_monitor.py | 新規(gitignore・非コミット) | session_monitor.py の設置 + settings.json 登録 + checkpoint_before_compact.py への追記。冪等 |
| .claude/hooks/session_monitor.py | 新規(staging 経由で設置) | Stop フック本体 |
| .claude/settings.json | hooks.Stop[0].hooks | notify.py の直前に session_monitor を挿入(staging 経由) |
| .claude/hooks/checkpoint_before_compact.py | main() | trigger=="auto" のとき session 別 compact 回数を加算(staging 経由) |
| claude-init.sh | OPTIONAL_FEATURES(125-136) | `CLAUDE_SESSION_MONITOR\|説明` を1行追加 |
| claude-init.ps1 | $OptionalFeatures(117-128) | 同じ説明文で1行追加 |
| verify-installers.sh | 92行付近 | 雛形に `"CLAUDE_SESSION_MONITOR": "0"` が含まれる assert を既存様式で追加 |
| templates/settings.local.json.template | env | `"CLAUDE_SESSION_MONITOR": "0"` を追加 |
| README.md | 環境変数表・フック一覧表・構成ツリー | session_monitor の行を追加 |
| .claude/skills/config-explain/SKILL.md | 変数表 | `CLAUDE_SESSION_MONITOR \| 同上` を追加 |
| .claude/skills/config-set/SKILL.md | 雛形・変数表 | 既定 `"0"` と説明行を追加 |

## 事後条件(postconditions)

| ID | 対象 | 入力 | 満たすべき条件 | R-ID |
|---|---|---|---|---|
| PC-1 | `.claude/hooks/session_monitor.py`(CLI) | `CLAUDE_SESSION_MONITOR` 未設定 or `0`、任意の stdin | 標準出力・標準エラーに警告文言を出さず exit 0 | R-001 |
| PC-2 | 同上 | monitor=1、末尾 usage 合計 100,000 の transcript | 警告文言を出さず exit 0 | R-002 |
| PC-3 | 同上 | monitor=1、末尾 usage 合計 150,000 の transcript | 出力(stdout+stderr)に "handoff" を含む警告があり exit 0 | R-003 |
| PC-4 | 同上 | monitor=1、末尾 usage 合計 180,000 の transcript | 出力に high 水準を示す語("high")を含み exit 0 | R-004 |
| PC-5 | 同上 | 150,000 で警告後、同一 session_id・使用量 160,000 で再実行 | 2回目は警告文言を出さない(exit 0) | R-005 |
| PC-6 | 同上 | 150,000 で警告後、同一 session_id・使用量 170,000 で再実行 | 2回目も警告文言を出す(exit 0) | R-006 |
| PC-7 | 同上 | monitor=1、使用量 10,000、状態ファイルの compact 回数 2 | 警告文言を出し exit 0。同条件の3回目実行では警告しない | R-007 |
| PC-8 | 同上 | transcript_path 不在 / 読取不能 / usage キー無し / 空 JSONL の4入力 | いずれも警告文言なしで exit 0 | R-008 |
| PC-9 | 同上 | `CLAUDE_MONITOR_WARN_TOKENS=1000` / `CLAUDE_MONITOR_HIGH_TOKENS=2000`、使用量 1,500 | warn 相当の警告を出し high 語を含まない。exit 0 | R-009 |
| PC-10 | 同上 | 非JSON stdin / 空 stdin / usage が文字列の transcript | returncode が 2 でない(全て 0) | R-010 |
| PC-11 | `.claude/hooks/checkpoint_before_compact.py`(CLI) | `trigger:"auto"` の PreCompact ペイロードを2回 | 状態ファイルの当該 session の compact 回数が 2 になる。`trigger:"manual"` では増えない | R-011 |
| PC-12 | `_staging_session_monitor.py --root <tmp>` | 既存フック・settings.json を複製した tmp ディレクトリ | 1回目適用後と2回目適用後で対象ファイル群のバイト列が一致する | R-012 |
| PC-13 | `templates/settings.local.json.template` | - | `"CLAUDE_SESSION_MONITOR": "0"` を含み、JSON としてパースできる | R-014 |
| PC-14 | `claude-init.sh` / `claude-init.ps1` | - | 抽出した変数名集合が完全一致し、両方に `CLAUDE_SESSION_MONITOR` を含む | R-013 |

## 実装手順

| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 1 | auto要件の受け入れテストを実装前に作成する。PC-1〜PC-12 を網羅し、テスト関数名に設計書の `-k` キーワード(gate_off / below_warn / warn_level / high_level / dedup_silent / dedup_rewarns / compact_count / fail_open / threshold_env / never_blocks / compact_counter_hook / staging_idempotent)を必ず含める。`tests/test_requirements_gate.py` の様式に倣い、モジュール先頭で `pytest.mark.skipif(not HOOK_PATH.exists())` により未適用時 skip。警告有無の判定は **stdout と stderr を連結した文字列**に対して行う(出力先が systemMessage か stderr かの実装判断に影響されないようにするため)。作成後、この時点で「全件 skip」になることを確認する(FAIL/skip 確認) | tests/test_session_monitor.py | なし | A |
| 2 | staging スクリプトを作成する。(a) `HOOK_SOURCE` 定数に session_monitor.py の全文、(b) `apply(root)` で フック設置 + settings.json 登録 + checkpoint_before_compact.py への文字列置換、(c) `smoke()`、(d) `--smoke-only` と `--root <dir>`(既定はスクリプトのあるディレクトリ)。settings.json は `json.loads` → `hooks.Stop[0].hooks` に挿入 → `json.dumps(indent=2, ensure_ascii=False)` + 末尾改行。**挿入位置は notify.py エントリの直前**(notify.py は末尾である必要があるため)。既に同じ command があれば挿入しない。checkpoint への追記は `REPLACEMENTS = [(OLD, NEW, 説明)]` 方式で、OLD の一意性を検査し、適用済みなら何もしない | _staging_session_monitor.py | Step 1 | A |
| 3 | session_monitor.py 本体の仕様を staging の HOOK_SOURCE 内に実装する。オプトイン判定 → stdin JSON 読み → `stop_hook_active` なら終了 → transcript を**行単位ストリーム**で走査し最後に見つかった assistant の `message.usage` から `input_tokens + cache_read_input_tokens + cache_creation_input_tokens` を合算 → 状態ファイル `.claude/checkpoints/session_monitor_state.json`(キー: session_id。Stop/PreCompact とも `payload.get("session_id", "unknown")` でフォールバック)と突き合わせ、warn/high 判定と 10% 重複排除、compact 回数2以上ならセッション中1回だけ警告 → 警告は JSON の `systemMessage` で出力(表示されない場合は stderr にフォールバック)。読み取りの例外は `(OSError, UnicodeError, ValueError)` を捕捉(`json.JSONDecodeError` は ValueError のサブクラス。並行セッションの read-modify-write で状態ファイルが破損しうるため、破損時は状態を空として初期化し続行)し、**全経路 exit 0**(premortem MEDIUM 1・2 の反映) | _staging_session_monitor.py | Step 2 | A |
| 4 | ユーザーに `! uv run python _staging_session_monitor.py` の実行を依頼し、適用後に Step 1 のテストが skip から実行に変わり全 PASS することを確認する。FAIL があれば Step 2-3 を修正して再適用(冪等なので上書き可) | (ユーザー実行) | Step 3 | A |
| 5 | 任意機能メニューに `CLAUDE_SESSION_MONITOR` を追加する。sh/ps1 の説明文は**同一文言**にし、追加後に1対1対応を diff で機械検証する | claude-init.sh, claude-init.ps1 | なし | B |
| 6 | 雛形に `"CLAUDE_SESSION_MONITOR": "0"` を追加し、verify-installers.sh に含有 assert を 92行の様式で追加する | templates/settings.local.json.template, verify-installers.sh | Step 5 | B |
| 7 | README の環境変数表・フック一覧表・構成ツリーに session_monitor を追記する(既存の record_session_state.py 行の書式に倣う) | README.md | なし | C |
| 8 | config-explain の変数表、config-set の雛形と変数表に CLAUDE_SESSION_MONITOR を追記する(CLAUDE_REQUIREMENTS_GATE の行の書式に倣う) | .claude/skills/config-explain/SKILL.md, .claude/skills/config-set/SKILL.md | なし | C |
| 9 | 全テスト・インストーラ検証を実行し、R-013〜R-015 の検証コマンドを通す。さらに記述と実装の整合を grep で機械照合する: `grep -n "150" README.md .claude/skills/config-set/SKILL.md`(閾値既定値)と `grep -rn "CLAUDE_MONITOR_WARN_TOKENS\|CLAUDE_MONITOR_HIGH_TOKENS\|CLAUDE_SESSION_MONITOR" README.md .claude/skills/config-explain/SKILL.md .claude/skills/config-set/SKILL.md` の結果が実装(HOOK_SOURCE 内の既定値・変数名)と一致すること(premortem MEDIUM 3 の反映) | (検証のみ) | Step 4, 6, 8 | A |

並列化判定: 並列化可能(グループ A / B / C。A=フック実体とテスト、B=インストーラと雛形、
C=ドキュメントで、触るファイルが完全に分離しており相互依存が無いため。Step 9 は統合検証で
全グループ完了後に実行する)

## 検証方法

| 検証 | コマンド | PASS 条件 |
|---|---|---|
| 新規テスト(適用前) | `uv run --with pytest python -m pytest tests/test_session_monitor.py -q` | 全件 skip(exit 0)。Step 1 完了時点で1件も PASS しないこと |
| 新規テスト(適用後) | `uv run --with pytest python -m pytest tests/test_session_monitor.py -q` | 全件 PASS、skip 0 |
| 全体退行(R-015) | `uv run --with pytest python -m pytest tests/ -q` | exit 0。既存の156件が退行しない |
| 閾値の複数ケース | `uv run --with pytest python -m pytest tests/test_session_monitor.py -q -k "warn_level or high_level or threshold_env"` | 3ケースとも PASS(境界値ちょうど・上・下の3点を含むこと) |
| transcript が複数行・複数 assistant の場合 | 上記テスト内 `-k warn_level` のフィクスチャに、usage を持つ assistant 行が複数ある JSONL・usage を持たない行が末尾に混ざる JSONL・入れ子の `message.usage` が欠けた行を含める | いずれも「最後に見つかった usage」で判定され PASS |
| 冪等性(R-012) | `uv run --with pytest python -m pytest tests/test_session_monitor.py -q -k staging_idempotent` | PASS(staging 未存在時のみ skip) |
| インストーラ1対1(R-013) | `bash -c "diff <(grep -oE '\"CLAUDE_[A-Z_]+\|' claude-init.sh \| tr -d '\"\|' \| sort -u) <(grep -oE '\"CLAUDE_[A-Z_]+\"' claude-init.ps1 \| tr -d '\"' \| sort -u)"` | 差分なし(exit 0)。件数(生・一意)も報告する |
| 雛形(R-014) | `grep -q '"CLAUDE_SESSION_MONITOR": "0"' templates/settings.local.json.template` | exit 0 |
| インストーラ検証 | `bash verify-installers.sh` | 全 assert PASS |

## リスク
- **代替案A(auto-compact 閾値の調整のみ)**: 不採用。圧縮の劣化が始まったことを人が知る
  手段が無く、設計書の目的(気づき)を満たさない。
- **代替案B(Stop を exit 2 でブロックし handoff を強制)**: 不採用。作業が止まる副作用が
  大きく、設計書の non-goals に明記されている。警告のみとする。
- **代替案C(状態を持たず毎ターン警告)**: 不採用。実装は最も簡単だが警告が毎ターン出て
  無視されるようになる(狼少年化)。10% 重複排除を採る。
- 副作用: Stop フックが1つ増える。オプトイン(既定 0)かつ fail-open のため、無効時は
  即 exit 0 で実行時間への影響は無視できる。
- 非互換: `checkpoint_before_compact.py` に追記するため、staging 未適用の環境と適用済みの
  環境でファイル内容が分岐する。文字列置換は適用済みマーカーで冪等にし、OLD が一意で
  見つからない場合は何もせず警告を出す(黙って壊さない)。
- staging スクリプトは gitignore 対象でコミットされないため、CI では新規テストが skip
  され続ける(requirements_gate と同じ既知のトレードオフ。設計書 8節に記載済み)。
- 未確認の仮定: Stop フックの stdin ペイロードに `session_id` キーが含まれる / 検証: `grep -rn "session_id" /home/toyod/claude-ml-template/.claude/hooks/action_log.py` / 期待: `payload.get("session_id", "unknown")` を含む行が出力される(既存フックでの使用実績。Stop で欠ける場合に備え実装側は `"unknown"` フォールバックを持つ)
- 未確認の仮定: PreCompact フックの stdin ペイロードにも `session_id` キーが含まれる / 検証: 実装時に checkpoint_before_compact.py 側も `payload.get("session_id", "unknown")` フォールバックとし、テストのペイロードに session_id 欠落ケースを含める / 期待: 欠落時は "unknown" キーに計上され exit 0(premortem MEDIUM 1 の反映)
- 未確認の仮定: Stop フックの `systemMessage` がユーザーに表示される / 検証: `grep -rn "systemMessage" /home/toyod/claude-ml-template/README.md` / 期待: 記載が見つからなければ実機確認が必要(Step 3 で確認し、不可なら stderr フォールバック。どちらでも R-010 は不変)

## トレーサビリティ

| ID | 対応ステップ | 検証方法 |
|--------|------------|---------|
| R-001 | Step 1, 3, 4 | `uv run --with pytest python -m pytest tests/test_session_monitor.py -q -k gate_off` |
| R-002 | Step 1, 3, 4 | 同上 `-k below_warn` |
| R-003 | Step 1, 3, 4 | 同上 `-k warn_level` |
| R-004 | Step 1, 3, 4 | 同上 `-k high_level` |
| R-005 | Step 1, 3, 4 | 同上 `-k dedup_silent` |
| R-006 | Step 1, 3, 4 | 同上 `-k dedup_rewarns` |
| R-007 | Step 1, 3, 4 | 同上 `-k compact_count` |
| R-008 | Step 1, 3, 4 | 同上 `-k fail_open` |
| R-009 | Step 1, 3, 4 | 同上 `-k threshold_env` |
| R-010 | Step 1, 3, 4 | 同上 `-k never_blocks` |
| R-011 | Step 1, 2, 4 | 同上 `-k compact_counter_hook` |
| R-012 | Step 1, 2, 4 | 同上 `-k staging_idempotent` |
| R-013 | Step 5 | 検証方法の表「インストーラ1対1(R-013)」の diff コマンド |
| R-014 | Step 6 | `grep -q '"CLAUDE_SESSION_MONITOR": "0"' templates/settings.local.json.template` |
| R-015 | Step 9 | `uv run --with pytest python -m pytest tests/ -q` |

Step 7・8 はどの R-ID にも直接対応しない。理由: プロジェクト規約
(`.claude/rules/consistency.md` の記述と実装の整合)により、新しい環境変数・フックを
追加したらドキュメント側も同時に更新する必要があるため。

## コスト見積もり(cost_estimate)

```yaml
cost_estimate:
  train_minutes: 0
  epochs: 0
  dataset_gb: 0
  parallel_jobs: 1
```

学習・実験ジョブを含まないため全て 0。goal は `experiment: false` により対象外。
