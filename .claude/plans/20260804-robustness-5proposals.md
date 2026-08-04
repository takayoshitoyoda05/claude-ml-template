# 計画・レビュー堅牢化(5提案の一括実装)

参照設計書: `docs/drafts/20260804-plan-review-robustness-proposals.md`
関連コンテキスト: `literature/ai-dev-plan-review-robustness/summary.md` §3 優先候補
(R3 指摘の接地検証 → 提案1・4、P10 計画遵守 → 提案2、R9 不確実性の出口 → 提案4)

## 目的

計画の「中身」を独立コンテキストで攻撃する層と、計画の前提・テストの網羅性・
レビューの判定根拠を機械検証する層が現行パイプラインに無い。
この2つの穴を、既存の思想(機械的強制 > 自己申告 / 独立コンテキスト / opt-in)に
沿った最小の追加で埋める。

## 現状分析

確認済みの事実(すべて実ファイルを読んで裏取り済み):

- **提案1**: `planner.md` 47行は「未確認の前提は『リスク』に『未確認の仮定: 〜』と
  明示する」とだけ規定し、書式も検証義務も無い。`plan-reviewer.md` 25-33行の機械条件は
  7個で、37-52行の報告形式も7個固定。57-58行に「計画の内容自体の良し悪しは判定しない」。
  frontmatter の `tools` に **Bash が既にある**(4行目)ので、コマンド実行に必要な
  ツール追加は不要。
- **提案2**: `.claude/skills/pre-mortem/SKILL.md` の分析観点6つは全て
  コード向け(shape・数値の脆さ・状態依存等)で、8行目に「動いているコードを見て」と
  明記。スキルは呼び出し元のコンテキストで動くため「planner の会話履歴を持たない
  初見コンテキスト」という要件を構造的に満たせない。
  `ml-pipeline.md` は 114-148行が手順3.3、149-163行が手順3.5 で、3.4 は空き番。
  手順3.3 の READY 分岐(124-125行)は「手順3.5へ進む」と書かれている。
- **提案2の適用範囲**: 手順0(65-75行)で **M は planner を省略**するため、手順3
  (計画の作成)に到達するのは L と、NEEDS_REVISION 2回で昇格した M だけ。したがって
  「手順3.3 を通過した全計画に適用」は設計書の「M/L 規模限定」と等価になる。
- **提案3**: `quality_gate.py` は ruff / radon / mypy の3チェック。`run()` の既定
  timeout は 120 秒。`tool_missing()` は **stderr のみ**を見てスキップ判定する
  (この設計は踏襲する)。`CLAUDE_QUALITY_GATE != "1"` で即 exit 0。
  `templates/settings.local.json.template` に全フラグの雛形があり、
  `claude-init.sh` 126-133行 / `claude-init.ps1` 118-124行の `OPTIONAL_FEATURES` が
  導入時の質問リスト。`enable_feature()` は該当キーを **`"1"` に書き換える実装**。
- **提案4**: `evaluator.md` 30-45行の作業手順にベースライン比較は無い
  (goal.baseline との数値比較は 51-82行にあるが、これは実験計画のみ)。
  `.gitignore` に `/.worktrees/` が既にある(並列実装用)。
- **提案5**: `.claude/improvements/feedback.md` は 335行 / 51エントリまで成長済み。
  形式は `## YYYY-MM-DD [entity: 結果]` + `- 指摘内容:` または `- 原因/理由:`。
  **`feedback.md` と `patterns.md` は `.gitignore` 対象**なので、新規導入先には
  存在しない前提が要る。
  `patterns.md` の分析によると、このリポジトリで最も繰り返された失敗は
  「ドキュメントの記述と実装が食い違う(21件)」で、原因は **README と実装が
  別の並列グループで書かれること**。本計画の並列グループ設計はこれを避ける。
- **整合更新が必要な README 箇所**: 12行(mermaid)、242-243行(環境変数表)、
  300-314行(plan-reviewer 7条件表)、524行(手順説明の「7条件」)、
  605-627行(@evaluator)、644-655行(@plan-reviewer)、760行(エージェント一覧表)、
  836行(フック一覧表)、980-990行(3.11 quality-gate 表)、1366行(導入チェックリスト)、
  1429行・1493行(ディレクトリツリー)。
- **エージェント追加にインストーラ変更は不要**: `claude-init.sh` 39行 /
  `claude-update.sh` 26行は `agents` ディレクトリを丸ごとコピーする。
  新しい環境変数だけが雛形とインストーラの変更を要する。
- **テストの流儀**: フックの回帰は `verify-hooks.sh` / `.ps1`(`test_hook` は
  exit コード、`test_hook_msg` は exit + stderr パターン、`test_plan_gate` は
  一時 git リポジトリを作って cd して実行)。ロジックの単体テストは
  `tests/test_plan_gate.py`(`subprocess.run([sys.executable, <絶対パス>])` で
  CLI 起動)。**pyproject.toml は無い**。

## 変更対象

| ファイル | 対象 | 変更内容 |
|---|---|---|
| `.claude/agents/planner.md` | 計画フォーマット表「リスク」行、47行 | 未確認の仮定に検証コマンドを添える固定書式を義務化 |
| `.claude/agents/plan-reviewer.md` | 条件表、報告形式、重要なルール | 条件8の追加、検証コマンド実行規約の新設 |
| `.claude/agents/plan-premortem.md` | 新規 | 計画専用の敵対的レビュー(独立コンテキスト・sonnet) |
| `.claude/commands/ml-pipeline.md` | 手順3.3 の遷移先、手順3.4(新設)、手順6 | プレモーテム工程の挿入と feedback.md 還流 |
| `.claude/hooks/quality_gate.py` | docstring、main、新規ヘルパー | 変更行カバレッジ検査(opt-in)を4番目のチェックとして追加 |
| `tests/test_quality_gate.py` | 新規 | 閾値パースと有効/無効経路の受け入れテスト |
| `verify-hooks.sh` / `verify-hooks.ps1` | quality_gate ブロック | 回帰テスト2件を両方に追加 |
| `templates/settings.local.json.template` | env | `CLAUDE_DIFF_COVERAGE` / `CLAUDE_DIFF_COVERAGE_MIN` を追加 |
| `claude-init.sh` / `claude-init.ps1` | OPTIONAL_FEATURES | 新フラグを任意機能の質問に追加 |
| `.claude/agents/evaluator.md` | 作業手順、レポート形式 | 手順4.5 ベースライン比較実行を新設 |
| `README.md` | 上記12箇所 | 実装の実物に合わせた整合更新 |
| `CHANGELOG.md` | [Unreleased] | Added エントリ1件 |

## 実装手順

| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 1 | 「未確認の仮定」に読み取り専用の検証コマンドを添える固定書式を義務化する(P-1 対応) | `.claude/agents/planner.md` | なし | A |
| 2 | 自動承認条件8と「検証コマンドの実行規約」を追加する(P-1 対応) | `.claude/agents/plan-reviewer.md` | Step 1 | A |
| 3 | 計画専用の敵対的レビューエージェントを新設する(P-2 対応) | `.claude/agents/plan-premortem.md` | なし | B |
| 4 | 手順3.4 を新設し、手順3.3 の遷移先を修正し、手順6 に feedback.md 注入を追加する(P-2 / P-5 対応) | `.claude/commands/ml-pipeline.md` | Step 3 | B |
| 5 | 変更行カバレッジ検査の受け入れテストを**実装前に**書く(RED を確認する)(P-3 対応) | `tests/test_quality_gate.py` | なし | C |
| 6 | 変更行カバレッジ検査を quality_gate に追加する(P-3 対応) | `.claude/hooks/quality_gate.py` | Step 5 | C |
| 7 | 新フラグを設定雛形とインストーラの任意機能に追加する(P-3 対応) | `templates/settings.local.json.template`, `claude-init.sh`, `claude-init.ps1` | Step 6 | C |
| 8 | verify-hooks に回帰テスト2件を sh / ps1 の両方へ追加する(P-3 対応) | `verify-hooks.sh`, `verify-hooks.ps1` | Step 6 | C |
| 9 | 手順4.5「ベースライン比較実行」とレポート表を追加する(P-4 対応) | `.claude/agents/evaluator.md` | なし | D |
| 10 | README / CHANGELOG を**実装済みの実物を grep で確認してから**更新する(P-1〜P-5 全対応) | `README.md`, `CHANGELOG.md` | Step 1〜9 すべて | E |

### 各ステップの補足

**Step 1**(`planner.md`)
計画フォーマット表の「リスク」セルに、次の固定書式を1つだけ定義する。

```
- 未確認の仮定: <内容> / 検証: `<読み取り専用の単一コマンド>` / 期待: <期待する出力・終了状態>
```

「思考結果の計画書への反映ルール」47行は書式を再掲せず「上記の固定書式で書く」と
参照させる(定義の二重化は patterns.md パターン1の再発源になる)。
検証コマンドの制約(単一コマンド・パイプ/リダイレクト/`;`/`&&`/コマンド置換を
含まない・読み取り専用)も planner 側に明記する。**制約を planner 側に書かないと、
plan-reviewer が実行を拒否する書式の計画が量産される**(条件8 が常時 NG になり
自動承認が事実上死ぬ)。

**Step 2**(`plan-reviewer.md`)
- 条件表に8行目を追加: 「未確認の仮定がすべて検証済み」。確認方法は
  「リスク欄から `未確認の仮定:` 行を全件抽出し、添えられた検証コマンドを
  Bash で実行して『期待』と一致するか確認する」。
  **未確認の仮定が0件なら条件8は OK** と明記する(0件を NG にしない)。
- 新設する「### 検証コマンドの実行規約」に、実行してよい先頭コマンドの許可リストを
  固定で書く: `ls` / `cat` / `head` / `tail` / `wc` / `grep` / `rg` / `find` / `test` /
  `git`(`log` `show` `diff` `status` `rev-parse` `ls-files` `branch` のみ)。
  `|` `>` `>>` `;` `&&` `||` `$(` `` ` `` `&` を含む行、および許可リスト外の
  先頭コマンドは**実行せず**「実行不能な書式」として条件8を NG にする。
- 報告形式に `8. 未確認の仮定の検証: N件中 M件 OK → OK/NG` を追加する。
- 「上記7条件は固定」→「上記8条件は固定」に修正する(修正漏れが起きやすい箇所)。
- 「計画の内容自体の良し悪しは判定しない」は**維持**し、条件8は内容の評価ではなく
  事実照合であることを1行で補足する(既存方針との矛盾に見えるため)。

**Step 3**(`plan-premortem.md` 新規)
既存の `.claude/agents/spec-auditor.md` の見出し構成(frontmatter → 導入文 →
スコープ制約 → 基準テーブル → 作業手順 → 出力形式 → 重要なルール)に倣う。
- frontmatter: `model: sonnet`、`tools: Read, Grep, Glob, Bash`。
- 導入文で「planner の会話履歴も検討経緯も一切知らない初見の立場」を明示する。
- 分析観点(pre-mortem スキルの6観点をコードから計画に置き換えたもの):
  前提の誤り / 手順の順序・依存の抜け / 検証方法の非検出性(その検証で本当に
  失敗を検出できるか)/ 影響範囲の見落とし(計画が触らないのに壊れるもの)/
  並列グループの競合 / ロールバック不能性。
- **HIGH の定義を明記する**: 「その要因が起きると、計画どおりに実装しても目的を
  達成できない、または既存の動作を壊す」。定義が無いと HIGH が乱発され
  差し戻しループになる。
- 出力は指摘リストのみ(重大度 + 失敗のシナリオ + 根拠の file:line か
  コマンド出力)。**改善案は書かない**(planner の責務)。良い点も書かない。
  指摘0件なら「失敗要因なし」と明記させる。

**Step 4**(`ml-pipeline.md`)
- 手順3.3 の READY 分岐(124-125行)を「手順3.4へ進む」に修正する。**この1行の
  修正漏れが最も起きやすい**(新工程が到達不能になる。feedback.md に
  同種の事故が記録されている)。
- 手順3.4 を新設: 計画ファイルのパスと作業スコープ**だけ**を plan-premortem に渡す
  (planner の会話・検討経緯を渡さない。渡すと独立性が失われて工程の意味が消える)。
  HIGH が1件以上 → 指摘全文を planner に渡して計画を修正させ、**手順3.3 から**やり直す。
  この差し戻しは1回まで。2回目の HIGH はユーザーに提示して判断を仰ぐ
  (手順6.8 の SEND_BACK の回数規約に倣う)。HIGH 0件なら MEDIUM/LOW を
  「未対応の指摘」として記録して手順3.5 へ。
  手順3.3 の NEEDS_WORK と同じ体裁で feedback.md に記録する。
  適用範囲は「手順3.3 を READY で通過した全計画」とし、手順3 に到達するのが
  L と昇格した M だけであることを注記する。
- 手順6 の冒頭に「過去の失敗パターンの注入(必須。ファイルが無ければスキップ)」を追加:
  `grep -E '^- (指摘内容|原因/理由):' .claude/improvements/feedback.md | tail -30`
  で直近30行を取り、繰り返し現れる類型を**上位3件まで**選んで
  evaluator / evaluator-standards のタスク指示に「過去にこのプロジェクトで
  繰り返された失敗(参考)。今回の diff に同種の問題が無いか特に確認すること」
  として渡す。ファイルが無い / 0件なら注入せず、その旨を手順8.5 のレポートに記す。
  30行・3件の上限はトークン節約のため(feedback.md は既に335行)。

**Step 5**(`tests/test_quality_gate.py` 新規、テストファースト)
`tests/test_plan_gate.py` の書式(モジュール docstring に対象と RED の説明、
`subprocess.run([sys.executable, <絶対パス>], ...)` での CLI 起動、
`_SUBPROCESS_TIMEOUT` 定数)に倣う。実装前に走らせて FAIL することを確認する。
- 閾値パースの表駆動テスト(`_diff_coverage_min` を `importlib.util` で直接読み込む):
  `""` → 80(既定)、`"80"` → 80、`"0"` → 80、`"1e2"` → 80、`"101"` → 80、
  `"abc"` → 80、`" 75 "` → 75。**読めない値で緩めない**(fail-safe 側に倒す)。
- 経路テスト(一時ディレクトリ + 空の git リポジトリで実行、`CLAUDE_WORK_SCOPE` を
  そこに向ける。リポジトリ本体を対象にすると既存コードの lint 結果でテストが揺れる):
  `CLAUDE_QUALITY_GATE` 未設定 → exit 0 / `CLAUDE_QUALITY_GATE=1` かつ
  `CLAUDE_DIFF_COVERAGE` 未設定 → exit 0(カバレッジ検査を呼ばない)/
  `CLAUDE_QUALITY_GATE=1` かつ `CLAUDE_DIFF_COVERAGE=1` でツール未導入 → exit 0(スキップ)。
- 失敗メッセージが**複数同時**に出る場合のテスト: 2件以上の failures を
  与えたときに全件がメッセージに含まれること(1件だけ表示して他を落とす実装を防ぐ)。

**Step 6**(`quality_gate.py`)
- `_diff_coverage_min() -> int` を追加。`CLAUDE_DIFF_COVERAGE_MIN` を
  **行末を固定した正規表現**で1〜100の整数として読み、読めなければ 80 を返す
  (`.claude/rules/python-style.md` の「`1e3` から `1` を拾う誤読」対策)。
- `_check_diff_coverage(scope: str) -> list[str]` を追加(main に直接書くと
  radon の複雑度 C 閾値を自分で踏む。`_validate_goal_ranges` を分離した
  plan_gate と同じ理由)。処理:
  1. `CLAUDE_DIFF_COVERAGE != "1"` なら空リストを返す。
  2. `uv run pytest <scope> --cov=<scope> --cov-report=xml:<一時ファイル> -q` を
     `timeout=600` で実行(既定120秒ではカバレッジ付き実行が高確率でタイムアウトする)。
     `tool_missing(stderr)` が真ならスキップ(空リスト)。
     **テスト自体の失敗はここではブロックしない**(enforce_eval / evaluator の責務。
     二重ブロックは差し戻しの原因を曖昧にする)。
  3. `uv run diff-cover <xml> --compare-branch=main --fail-under=<閾値>` を実行。
     `tool_missing(stderr)` が真ならスキップ。非ゼロ終了なら failures に追加。
  4. 一時ファイルは `tempfile` で作り、`finally` で必ず削除する。
  - `main` が `main` ブランチを持たない環境では diff-cover が非ゼロで落ちるが、
    その stderr は `tool_missing` に該当しない。**比較先ブランチが解決できない場合を
    「違反」と誤判定しないよう**、`git rev-parse --verify main` が失敗したら
    検査自体をスキップする判定を先に入れる。
  - timeout(`run()` が `(-1, "", "timeout")` を返す)は failures に入れず
    スキップ扱いにする(誤ブロック防止)。
- docstring のチェック一覧に「4. diff-cover — 変更行カバレッジが閾値以上
  (`CLAUDE_DIFF_COVERAGE=1` のときのみ)」を追記する。

**Step 7**(雛形とインストーラ)
- `templates/settings.local.json.template` の `CLAUDE_QUALITY_GATE` の直後に
  `"CLAUDE_DIFF_COVERAGE": "0"` と `"CLAUDE_DIFF_COVERAGE_MIN": ""` を追加する。
  `enable_feature()` は該当キーが**雛形に無いと警告して失敗する**ので、
  この追加は必須。
- `claude-init.sh` の `OPTIONAL_FEATURES` と `claude-init.ps1` の同名ハッシュに
  `CLAUDE_DIFF_COVERAGE|変更行カバレッジゲート(pytest-cov + diff-cover。既定閾値80%、CLAUDE_DIFF_COVERAGE_MIN で変更可)`
  を追加する。`CLAUDE_DIFF_COVERAGE_MIN` は質問リストに載せない(`enable_feature` は
  `"1"` を書き込むため、閾値変数を載せると閾値1%になる)。

**Step 8**(`verify-hooks.sh` / `.ps1`)
既存の quality_gate ブロック(sh 193-200行 / ps1 206-213行)の直後に、同じ書式で2件追加する。
- `quality_gate: diff coverage off when CLAUDE_DIFF_COVERAGE is unset (exit 0)`
- `quality_gate: diff coverage skips when tools are missing (exit 0)`
実行は一時ディレクトリ(`mktemp -d` + `git init`)で行い `CLAUDE_WORK_SCOPE` を
そこへ向ける(`test_plan_gate` と同じ隔離方式)。**sh と ps1 の両方に同一の
説明文字列で追加する**(片方だけの追加は `.claude/rules/consistency.md` 違反)。

**Step 9**(`evaluator.md`)
作業手順4と5の間に「4.5. ベースライン比較実行」を挿入する。
- **発火条件: 手順4で検証コマンドが1つでも失敗した場合のみ**(PASS 時は実行しない)。
- 手順: (a) 分岐元を決める(タスク指示に親ブランチがあればそれ、無ければ
  `git merge-base HEAD main`)→ (b)
  `git worktree add --detach <作業スコープ>/.worktrees/baseline <分岐元>`
  (作業スコープ配下に作る理由は guard_scope。手順5 の worktree 規約と同じ)→
  (c) その中で**同じ検証コマンド**を実行し `logs/runs/` に tee で保存 →
  (d) `git worktree remove` で必ず後片付けする。
- 判定への反映: ベースラインでも同じテストが落ちる → **今回の変更が原因ではない**。
  NEEDS_REVISION の根拠にせず「既存の失敗」としてレポートに列挙する。
  ブランチでのみ落ちる → 従来どおり根拠にする。
  ブランチ側で2回実行して結果が一致しない → flaky として記録し根拠にしない。
- worktree が作れない場合(権限確認で拒否・分岐元が特定できない・git worktree が
  使えない)は比較をスキップし、レポートに「ベースライン比較: 実施できず(理由)」と
  **明記する。黙って省略しない**。
- レポート形式に「ベースライン比較」表(テスト名 / ブランチ結果 / ベースライン結果 /
  判定への採否)を追加する。

**Step 10**(README / CHANGELOG)
**このステップの最初に、Step 1〜9 で実際に書かれた内容を grep で確認してから
書く**(README を実装と別グループで書いたことが patterns.md パターン1・21件の
主因。ここは唯一の逐次ステップとして最後に置いている)。更新箇所:
12行(mermaid に plan-premortem ノード)/ 242-243行(環境変数表に2行)/
300-314行(条件表を8行に)/ 524行(「7条件」→「8条件」)/ 605-627行
(@evaluator にベースライン比較)/ 644-655行(@plan-reviewer を8条件に。
既存 spec-auditor の項の書式に倣って @plan-premortem の項を新設)/
760行(エージェント一覧表に plan-premortem 行を追加、plan-reviewer 行を8条件に)/
836行(フック一覧表の quality_gate 行)/ 980-990行(3.11 の表に変更行カバレッジ行)/
1366行(導入チェックリストの quality_gate 行)/ 1429行・1493行(ディレクトリツリー)。
CHANGELOG は `[Unreleased]` に `### Added(2026-08-04)` を1ブロック追加する
(既存 `### Added(2026-07-22)` の粒度・文体に倣う)。

## 並列化判定

**並列化可能**(グループ A / B / C / D は対象ファイルが完全に分離しており依存も無い。
グループ E は README という共有ファイル1つだけを扱い、全グループ完了後に逐次実行する)。

## 検証方法

1. **フック回帰(必須)**
   `bash verify-hooks.sh`
   → 「全テストPASS」。新規2件 `quality_gate: diff coverage ...` が OK で表示されること。
2. **単体テスト(必須)**
   `uv run python -m pytest tests/ -q`
   → 全PASS。`tests/test_quality_gate.py` の閾値パース7ケースを含む。
   Step 5 の時点(実装前)では新規テストが FAIL することを確認して報告に含める。
3. **sh / ps1 の1対1対応(consistency.md の標準形)**
   ```
   diff <(grep -oE 'quality_gate: [^"]+' verify-hooks.sh | sort -u) \
        <(grep -oE 'quality_gate: [^"]+' verify-hooks.ps1 | sort -u)
   diff <(grep -oE 'CLAUDE_[A-Z_]+' claude-init.sh | sort -u) \
        <(grep -oE 'CLAUDE_[A-Z_]+' claude-init.ps1 | sort -u)
   ```
   → いずれも差分なし。件数(生・一意)と diff の3点を報告する。
4. **記述と実装の整合(grep)**
   - `grep -rn "7条件" README.md .claude/agents/ .claude/commands/` → **ヒット0件**
   - `grep -rln "CLAUDE_DIFF_COVERAGE" README.md templates/settings.local.json.template claude-init.sh claude-init.ps1 .claude/hooks/quality_gate.py` → **5ファイル全てヒット**
   - `grep -rln "plan-premortem" README.md .claude/commands/ml-pipeline.md .claude/agents/plan-premortem.md` → **3ファイル全てヒット**
   - `grep -n "手順3.4" .claude/commands/ml-pipeline.md` → 手順3.3 の READY 分岐と
     3.4 の見出しの**2箇所以上**にヒット(1箇所しか無ければ遷移先の修正漏れ)
5. **提案1の実挙動(複数ケース・入れ子ケースを必ず含める)**
   検証用の計画ファイルを `.claude/plans/` に一時作成し `@plan-reviewer` を手動起動する。
   - 未確認の仮定 **0件** → 条件8 が OK
   - 未確認の仮定 **1件**(`grep -c "" README.md` 等、必ず成功する読み取りコマンド)
     → 条件8 が OK
   - 未確認の仮定 **3件**(うち1件は期待と異なる出力を返すコマンド)
     → 条件8 が NG、どの1件が落ちたかが報告に出る
   - 検証コマンドに **パイプを含む**もの、および **`rm` など許可リスト外**のもの
     → 実行されず「実行不能な書式」で NG
   - 検証コマンドが **欠落**した未確認の仮定 → NG
   確認後、一時計画ファイルを削除する。
6. **提案2の実挙動**
   既存の承認済み計画(例 `.claude/plans/20260726-plan-gate-precision.md`)に対して
   `@plan-premortem` を起動 → 出力が定義した形式(重大度 + 失敗シナリオ + 根拠)を
   守り、改善案・良い点が含まれていないこと。指摘0件なら「失敗要因なし」と出ること。
7. **提案3の閾値挙動**
   `CLAUDE_QUALITY_GATE=1 CLAUDE_DIFF_COVERAGE=1 CLAUDE_DIFF_COVERAGE_MIN=1e2 uv run python .claude/hooks/quality_gate.py <<< '{}'`
   → exit 0(ツール未導入でスキップ)かつ、既定80へフォールバックしていることを
   単体テストで確認済みであること(`1e2` から `1` を拾わない)。
8. **提案4・5の記述検証**(実行を伴わない工程のため grep で確認)
   - `grep -n "ベースライン比較" .claude/agents/evaluator.md` → 手順とレポート形式の2箇所
   - `grep -n "feedback.md" .claude/commands/ml-pipeline.md` → 手順3.3 / 3.4 / 手順6 / 手順7 にヒット

## リスク

- **既存動作との非互換**: 提案1により、条件8を満たさない計画は
  `CLAUDE_AUTO_APPROVE=1` でも自動承認されなくなる。これは意図した強化だが、
  移行期は自動承認率が下がる。**未確認の仮定0件を OK とする**規定でこれを緩和する。
- **plan-reviewer が計画ファイル経由でコマンドを実行する**新しい攻撃面ができる。
  許可リスト(読み取り専用の先頭コマンドのみ・シェル構文禁止)で塞ぐが、
  guard_bash の防御に加えて plan-reviewer 側でも保守的に倒す必要がある。
- **quality_gate のタイムアウト**: `pytest --cov` は既定120秒を超えうるため 600秒を
  指定するが、大規模プロジェクトではさらに超える可能性がある。超えた場合は
  `run()` が `(-1, "", "timeout")` を返し `tool_missing` に該当しないため、
  **誤ブロックになりうる**。timeout の戻り値は failures に入れずスキップ扱いにする。
- **この計画は plan-reviewer の条件1(ファイル3個以下)と条件7(ステップ5以下)を
  満たさない**ため、自動承認NG になる。ユーザー承認を前提とする。
- 検討した代替案と不採用理由:
  - 提案1を手順3.3(spec-checklist)側に置く案 — spec-checklist はスキルで
    リーダーのコンテキスト内で走るため、独立性とコマンド実行の責務が曖昧になる。
    plan-reviewer は既に Bash を持ち機械条件の担当なので追加コストが最小。
  - 提案1で許可リストを設けず全コマンドを実行する案 — 計画ファイル経由の
    任意コマンド実行になり、テンプレートのガード設計と正面から衝突する。
  - 提案2で既存 pre-mortem スキルを再利用する案 — スキルは呼び出し元の
    コンテキストで動くため「planner の会話履歴を持たない初見視点」を満たせない。
    分析観点6つもコード向けで計画には転用できない。
  - 提案3で `CLAUDE_DIFF_COVERAGE` に閾値そのものを入れる1変数案 —
    `claude-init` の `enable_feature()` が該当キーに `"1"` を書き込む実装なので、
    導入時に有効化すると閾値1%になり「有効に見えるが素通りするゲート」になる。
    二値フラグ + 別閾値変数に分けた。
  - 提案3に mutation gate(`CLAUDE_MUTATION_GATE=1`)を同時導入する案 — **不採用**。
    `run()` の既定タイムアウトは120秒、mutmut はモジュールあたり数分〜数十分で
    Stop フックでの実行はタイムアウトが常態化する。加えてテンプレート本体に
    pyproject.toml が無く mutmut の設定を置く場所がない。mutation-test は
    従来どおり手動スキルのまま残す。
  - 提案4を常時実行する案 — PASS 時にもテストを2回走らせる時間の無駄が大きい。
    失敗時限定で目的(誤判定の防止)は達成できる。
  - 提案5で `patterns.md`(retrospective の集計済み出力)を注入する案 —
    安価だが retrospective が回っていないプロジェクトでは空になる。設計書の
    指定どおり feedback.md を一次ソースにし、抽出を grep 30行に制限した。
- 未確認の仮定(提案1で導入する固定書式で記載):
  - 未確認の仮定: この環境に `diff-cover` / `pytest-cov` は未導入で、新規の
    カバレッジ検査はスキップ経路しか通らない /
    検証: `uv run diff-cover --version` /
    期待: 非ゼロ終了し stderr に `Failed to spawn` 等の未導入を示す文言が出る
  - 未確認の仮定: `verify-hooks.ps1` は Linux 上で構文検証できないため、
    Step 8 の ps1 側は目視の書式一致でしか担保できない /
    検証: `grep -n "全 .ps1 は Linux 上で構文検証できていない" README.md` /
    期待: 1件ヒットする
  - 未確認の仮定: `git worktree add` は settings の allow に無いため、
    提案4の実行時にユーザーへの権限確認が出る /
    検証: `grep -c "git worktree" .claude/settings.json` /
    期待: `0` が返る
  - 未確認の仮定: `docs/` は `.gitignore` 対象のため、参照設計書
    `docs/drafts/20260804-plan-review-robustness-proposals.md` はコミットされず、
    `docs/active/` への移動も履歴に残らない /
    検証: `grep -n "^docs/$" .gitignore` /
    期待: 1件ヒットする

## トレーサビリティ

参照設計書に「## 受け入れ条件」テーブルが無いため、設計書の「## 提案(優先度順)」
テーブルの提案番号 #1〜#5 を P-1〜P-5 として対応づける。

| ID | 提案 | 対応ステップ | 検証方法 |
|---|---|---|---|
| P-1 | 仮定の機械検証 | Step 1, 2, 10 | 検証方法5(0件/1件/3件/パイプ/許可リスト外/欠落の6ケース)+ `grep -rn "7条件"` が0件 |
| P-2 | 計画プレモーテム | Step 3, 4, 10 | 検証方法6 + `grep -n "手順3.4" .claude/commands/ml-pipeline.md` が2箇所以上 |
| P-3 | diff カバレッジゲート | Step 5, 6, 7, 8, 10 | `bash verify-hooks.sh` が全PASS + `uv run python -m pytest tests/ -q` が全PASS + 検証方法3の diff が空 |
| P-4 | ベースライン比較実行 | Step 9, 10 | `grep -n "ベースライン比較" .claude/agents/evaluator.md` が2箇所 |
| P-5 | feedback.md 還流 | Step 4, 10 | `grep -n "feedback.md" .claude/commands/ml-pipeline.md` が手順6にヒット |

対応ステップの無い P-ID は無い。Step 10 はどの提案にも単独では属さないが、
`.claude/rules/consistency.md` の「記述と実装の整合」を満たすために全提案に対応する。

## コスト見積もり

学習ジョブ・実験を含まないコード/定義ファイルのみの変更のため、plan_gate の
検査対象外とする。

```yaml
experiment: false
```

参考値(学習ジョブが無いため全て0。並列実装のグループ数は
`cost_estimate.parallel_jobs`(学習ジョブの並列度)とは別概念):

```yaml
cost_estimate:
  train_minutes: 0
  epochs: 0
  dataset_gb: 0
  parallel_jobs: 0
```

## 作業ログ(グループA: Step 1, 2)

- 2026-08-04: Step 1(`planner.md`)完了。「思考結果の計画書への反映ルール」47行の
  「未確認の仮定: 〜」書式の再掲を削除し、「計画フォーマット」のリスク欄で一度だけ
  定義する形に統一。リスク欄セルに「(固定書式は下記)」と付記し、表直後に固定書式
  ```
  - 未確認の仮定: <内容> / 検証: `<読み取り専用の単一コマンド>` / 期待: <期待する出力・終了状態>
  ```
  と、検証コマンドの制約(単一コマンド・パイプ/リダイレクト/`;`/`&&`/コマンド置換
  禁止・読み取り専用)を追加した。
- 2026-08-04: Step 2(`plan-reviewer.md`)完了。自動承認条件表に条件8
  「未確認の仮定がすべて検証済み」(0件なら OK)を追加し、新設した
  「### 検証コマンドの実行規約」に許可リスト(ls/cat/head/tail/wc/grep/rg/find/test/
  git の log/show/diff/status/rev-parse/ls-files/branch のみ)と禁止構文
  (`|` `>` `>>` `;` `&&` `||` `$(` `` ` `` `&`)を固定で記載。報告形式に条件8の行を
  追加し、「上記7条件は固定」を「上記8条件は固定」に修正。「計画の内容自体の
  良し悪しは判定しない」は維持しつつ、条件8は事実照合であり方針と矛盾しない旨を
  1行補足した。
- 検証: `grep -n "7条件" .claude/agents/plan-reviewer.md` → ヒット0件。
  `grep -n "未確認の仮定:" .claude/agents/planner.md` と
  `grep -n "「期待」\|検証コマンド" .claude/agents/plan-reviewer.md` で
  両ファイルの書式表現(未確認の仮定: / 検証: / 期待:)の突き合わせを確認済み。
- コミット: `09860dc`
  `feat(step 1-2): 未確認の仮定の固定書式と plan-reviewer の機械検証を義務化`

### 差し戻し修正(evaluator-standards 指摘対応)

- 2026-08-04: evaluator-standards の指摘3点(HIGH 1件・MEDIUM 2件)に対応。
  1. 条件表8行目が3物理行にまたがりGFMの1行1レコード規則に違反していた点を、
     セル内容を要約して1物理行に収め修正(詳細は表外の節に残す)。
  2. 新設見出し「### 検証コマンドの実行規約」が見出し連番(### 1/2/3)を崩していた点を、
     既存の `evaluator.md` 48行・`evaluator-standards.md` 49行の
     `#### 問題点`・`#### 指摘事項`(`###` の子節として `####` を使う慣行)に倣い、
     `#### 検証コマンドの実行規約` として `### 2. 自動承認条件のチェック` の子節に位置づけた。
  3. 許可リストの先頭コマンドが通っても破壊的なフラグ(`find -delete`/`-exec`/`-ok`/
     `-fprint`/`-fprintf`、`git branch` の `-D`/`-d`/`-m`/`-f`)を実行してしまう穴を、
     「禁止フラグ」として明記し実行不能な書式に含めた。
- 検証: markdown-it-py(`MarkdownIt("gfm-like")`)で実レンダリングし、条件表が
  `<table>` 1個・`<tr>` 9個(ヘッダー+条件1〜8)で正しく生成され、以降の見出し・
  箇条書きが壊れていないことを確認。`awk 'NR>=25&&NR<=34' ... | grep -vc '^|'` → `0`
  (表領域10行が全行 `|` 始まり)。`grep -n "7条件" .claude/agents/plan-reviewer.md` →
  ヒット0件。`grep -n "8条件" .claude/agents/plan-reviewer.md` → 「上記8条件は固定」
  1件ヒット、維持を確認。`grep -n "未確認の仮定" .claude/agents/planner.md
  .claude/agents/plan-reviewer.md` で両ファイルの `未確認の仮定:` 書式表現の
  整合を再確認(今回の修正で書式定義自体には触れていない)。
- コミット: `3d810c0`
  `fix(step 2): 条件表の行分断・見出し階層・破壊フラグの許可漏れを修正`
