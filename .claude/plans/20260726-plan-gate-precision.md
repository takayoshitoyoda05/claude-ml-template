# 計画: plan_gate の検査精度向上(fail-closed 化・検査対象の明示化)

- 設計書: `docs/drafts/control-patterns-spec.md`(本計画の Step 1 で「セクション12」として改訂する。`docs/active/` へは移動しない。理由は現状分析を参照)
- ブランチ: `pipeline/20260726-plan-gate-precision`
- 作業スコープ: `/home/toyod/claude-ml-template`(リポジトリ直下)
- 申し送り元: `docs/reports/20260726-031643/report.md` 5節(e)(f)・7節の残件6件

experiment: false
(本実装はフック・テスト・ドキュメントの変更のみで学習・実験を伴わないため、plan_gate の
チェック対象外であることを行頭で宣言する。箇条書きにしたり行末に説明を続けたりすると
正規表現 `^\s*experiment\s*:\s*false\s*(?:#.*)?$` に一致しないので、必ず独立した行に書く。
理由を添えるときは `# ` のコメントにする)

## 目的

前パイプラインが「既知の制約」として意図的に残した plan_gate の6件を解消する。
中心は2つ: (1) 読めない見積もりを通す fail-open をやめる、(2) 検査対象の計画を
mtime ではなくブランチ名から明示的に決める。あわせてブロック側の回帰テストを整える。

## 現状分析

すべて本機(WSL / Python 3.12.7 / git 2.53.0 / uv)で実測して確認した。

- 確認済み: `.claude/hooks/plan_gate.py` の現行実装(112行)は
  `limit is not None and est is not None` の条件で比較するため、`1e3` / `-5` / `"120"` /
  `1.2.3` のように読めない値は**検査そのものがスキップ**される(fail-open)。
- 確認済み: goal のキー検査は `re.search(rf"^\s*{key}\s*:", plan, re.MULTILINE)` で
  **文書全体**を見ている。プロトタイプで確認したとおり、`goal:` ブロックの外
  (散文や別の YAML ブロック)にある `target:` でも通過する。
- 確認済み: エラーメッセージは `guard_metrics` を要求しているが実装は検査していない。
  `direction` の値域(minimize / maximize)も未検査。
- 確認済み: 検査対象は `.claude/plans/*.md` の mtime 最新。`.claude/plans/` には
  過去計画が9件あり、`git checkout` や無関係な過去計画の閲覧・編集で入れ替わる。
- 確認済み: `git symbolic-ref --short HEAD` は (a) 本リポジトリで
  `pipeline/20260726-plan-gate-precision`、(b) `.worktrees/group-B` で
  `pipeline/20260725-control-patterns-group-B`、(c) コミットが1つも無い
  `git init -b <名前>` 直後のリポジトリでも `<名前>` を返す。
  `git rev-parse --abbrev-ref HEAD` は (c) で exit 128 になる(テスト用フィクスチャを
  コミットなしで組めるかどうかの差)。→ **symbolic-ref を採用する**。
- 確認済み: 既存の計画9件はすべて「ブランチ名の最終セグメント == 計画ファイル名の stem」に
  なっている(例: `pipeline/20260725-control-patterns` ⇔ `20260725-control-patterns.md`)。
  worktree のブランチは親ブランチ名 + `-group-<英字>`。
- 確認済み: YAML ブロックのスコープ抽出は正規表現で実装できる。プロトタイプで
  `cost_estimate:` / `goal:` / invariants の `resources:` の3ブロックを実データから
  正しく切り出し、ブロック外の `target: 999` を拾わないことを確認した
  (ブロック終端は「インデントがキー行以下の非空行」。空行では終端しない。
  コードフェンス行はインデント0なので終端になる)。
- 確認済み: guard_scope は `.claude/hooks/plan_gate.py` への Edit/Write を exit 2 で
  ブロックする。`tests/test_plan_gate.py` / `verify-hooks.sh` / `verify-hooks.ps1` /
  `.claude/agents/planner.md` / `README.md` / `_staging_plan_gate_precision.py` /
  `docs/drafts/control-patterns-spec.md` はいずれも exit 0(書き込み可)。
  → **generator は plan_gate.py を書けない。ユーザー手動適用にする**(前回踏襲)。
- 確認済み: guard_bash は `git add .claude/hooks/plan_gate.py` /
  `git checkout <sha> -- .claude/hooks/plan_gate.py` /
  `uv run python _staging_plan_gate_precision.py` / `--revert` をいずれも exit 0 で通す。
  一方、保護パス名を**リテラルで含むリダイレクト**は一時ディレクトリ配下でもブロックされる
  (実測)。テスト・検証でフィクスチャを作るときはパスを変数に分けて組み立てる。
- 確認済み: 現行のスキップ判定 `^\s*experiment\s*:\s*false` は**行末を見ていない**ため、
  `experiment: falsehood` や `experiment: false は書かない` のような行でもスキップが成立する
  (数値パースで直したのと同じ「ゆるい正規表現」の問題がスキップ判定側に残っている)。
- 確認済み(既存計画への影響): `.claude/plans/*.md` 9件を走査したところ、
  `experiment:` の宣言行を持つのは `20260725-control-patterns.md`(7行目)と
  本計画(8行目)の2件だけで、**どちらも行末まで固定した新正規表現に一致する**
  (`experiment: false` の裸の1行)。残り7件は宣言行を持たない。
  両ファイルには `` `experiment: false` `` を含む散文行もあるが、いずれも行頭が
  バッククォート等のため新旧どちらの正規表現にも一致しない。
  → **行末固定への変更で既存計画の挙動は変わらない**。
- 確認済み(glob の誤マッチ): `20260726-extra-foo.md` と `20260726-foo.md` を置いて
  `glob("*-foo.md")` を実行すると候補は2件になり、`stem[:8].isdigit() and stem[8] == "-"`
  だけでは2件とも通過する。`stem[9:] == slug` を加えると `20260726-foo` の1件に絞れる。
  → 仕様 A-4 の完全一致条件は必須。
- 確認済み(件数アサーション): 説明文字列6行のモックで生の件数6 / 一意件数6、
  うち1件を重複させたモックで生6 / 一意5 になることを実測。両方を見れば
  「互いに異なる6ケース」を検査できる。
- 確認済み: `.claude/settings.json` の Stop フック配列には plan_gate が既に配線済み
  (enforce_eval → spec_gate → codex_gate → quality_gate → **plan_gate** → notify)。
  **本計画で settings.json は触らない**。
- 確認済み: 既存テストは `uv run --with pytest python -m pytest tests/ -q` で 7 passed
  (`pyproject.toml` は無く、pytest は `--with` で都度注入する運用)。
  `tests/test_env_fingerprint.py` が「スクリプトを import せず subprocess で CLI 起動」の
  前例になっている。同じ方式を使う。
- 確認済み: `docs/` は `.gitignore` 対象で git 管理外。設計書を改訂してもコミットには
  乗らない。`docs/active/` へ移すと `spec_gate.py` が「## 受け入れ条件」テーブルの無い
  設計書に対し `AcceptanceTableError` で全体をブロックするため**移動しない**。
- 確認済み: `/_staging_*.py` は `.gitignore` 対象(コミットされず codex_gate の
  未追跡チェックも塞がない)。

## 新しい plan_gate の仕様(実装の契約)

Step 1 で設計書に「セクション12」として書き、Step 5/6 で実装する内容。
以下がそのまま受け入れ条件になる。

**A. 検査対象の決定(fail-open のまま。「対象が特定できない」ときは通す)**

1. `.claude/plans/` が無ければ exit 0。
2. `git symbolic-ref --short HEAD`(timeout 5秒)でブランチ名を取る。
   失敗(非 git ディレクトリ / detached HEAD / git 不在)なら exit 0。
3. ブランチ名の最後の `/` 以降を取り、末尾の `-group-<英数字>` を1回だけ除去して `slug` とする。
4. `.claude/plans/<slug>.md` があればそれを対象にする。無ければ **glob で**
   `Path(".claude/plans").glob(f"*-{slug}.md")` の候補を集め、各候補の stem が
   **次の4条件すべて**を満たすものだけを残す(= `<8桁数字>-<slug>.md` の形):
   `len(stem) > 9` / `stem[:8].isdigit()` / `stem[8] == "-"` / **`stem[9:] == slug`**。
   残りが**ちょうど1件**なら対象、0件または2件以上なら exit 0。
   **`stem[9:] == slug` の完全一致は必須**。glob の `*` は任意の文字列を吸収するため、
   これが無いと slug=`foo` に対して `20260726-extra-foo.md` が
   (`*` が `20260726-extra` を吸収し、先頭8桁も `-` も条件を満たすため)誤って選ばれる。
   **slug から正規表現を組まないこと**。`feature/v1.2-fix` のように slug に正規表現の
   メタ文字(`.` `+` 等)が入るブランチ名は実在しうるため、エスケープ漏れが誤マッチになる。
   glob のメタ文字(`*` `?` `[`)は git のブランチ名に使えないので、glob で照合すれば
   この問題が原理的に起きない。
5. 対象ファイルが読めない(OSError)なら exit 0。

**B. スキップ判定(現行どおり)**

6. `^\s*experiment\s*:\s*false\s*(?:#.*)?$`(**行末まで固定**。末尾の空白と
   `# コメント` のみ許す)に一致する行があれば exit 0。
   行末を固定しないと `experiment: falsehood` や、説明文の中に現れた同じ書き出しの行でも
   スキップが成立してしまう(現行実装の穴。現状分析を参照)。
7. `cost_estimate|goal\s*:` も `学習|実験|train|epoch` も含まなければ exit 0。

**C. ブロック検査(ここから fail-closed。errors に積み、1件でもあれば exit 2)**

| # | 検査 | ブロック条件 |
|---|------|-------------|
| C1 | cost_estimate ブロック | 存在しない |
| C2 | cost_estimate の4キー(train_minutes / epochs / dataset_gb / parallel_jobs) | いずれかがブロック配下に無い |
| C3 | 上記4キーの値 | 非負の十進数として読めない(`1e3` `-5` `"45"` `1.2.3` `120abc` 等) |
| C4 | goal ブロック | 存在しない |
| C5 | goal の5キー(metric / target / direction / baseline / guard_metrics) | いずれかが **goal ブロック配下に**無い |
| C6 | target / baseline の値 | 非負の十進数として読めない |
| C7 | direction の値 | `minimize` / `maximize` のいずれでもない |
| C8 | guard_metrics | 値が `[]` でなく、かつ配下に `- name:` 行が1件も無い |
| C9 | invariants の `max_*` | `resources:` ブロック内にキーがあるのに値が読めない |
| C10 | 上限比較 | `est > limit` |

- 数値として読める書式: `120` / `30.5` / `200.` / `.5`、行末の空白と `# コメント` は許す
  (invariants の `max_train_minutes: 120     # ...` を読むために必須)。
  正規表現は現行の `([0-9]+(?:\.[0-9]*)?|\.[0-9]+)` を流用する(前回の回帰修正の成果)。
- invariants.md が存在しない / **読み取りに失敗する(OSError)** / `resources:` ブロックが無い /
  特定の `max_*` キーが無い場合は、**上限比較(C9・C10)のみをスキップ**する
  (C9 は「キーはあるのに値が読めない」場合だけ)。
  計画側の C1〜C8 は invariants の状態に関わらず実施する。
- **フックは例外で終了してはならない**。invariants.md の読み取りは計画ファイルとは別の
  `try` で囲み、`OSError`(不在・権限不足・ディレクトリだった等)を捕捉して
  「上限なし」として扱う。ここを捕捉し損ねると Stop フックが例外終了し、
  全セッションが停止できなくなる。同様に `git` の呼び出しも例外・タイムアウトを捕捉する。
- ブロック抽出の規則: `^(\s*)<キー>\s*:\s*(?:#.*)?$` に一致する**最初の行**をブロック開始とし、
  以降、空行は本文として継続、インデントがキー行以下の非空行に達したら終了。
  ブロック配下のキー検索は `^\s+<キー>\s*:` で行う(必ずブロック開始より深いインデント)。
  `guard_metrics` だけは `guard_metrics: []` の値付き形も受ける。
- エラーメッセージは現行書式(`[plan_gate] 計画がゲートを通過できません:` + 箇条書き)を維持し、
  先頭に**検査対象の計画ファイルパス**を1行加える。C1〜C3 のメッセージには
  「コード変更のみなら `experiment: false` と書く」逃げ道を必ず含める。

## 変更対象

| ファイル | 区分 | 変更内容 | 要件 |
|---|---|---|---|
| docs/drafts/control-patterns-spec.md | MOD | セクション3 冒頭に改訂ポインタ1行 + 末尾に「セクション12: plan_gate 検査精度の改訂(2026-07-26)」と「## 受け入れ条件」テーブル(12行)を追加 | R-001〜R-012 |
| tests/test_plan_gate.py | NEW | 受け入れテスト(subprocess で CLI 起動、一時 git リポジトリ) | R-001〜R-006, R-012 |
| verify-hooks.sh | MOD | plan_gate テストを exit 2 側含む6ケースへ拡張 | R-007 |
| verify-hooks.ps1 | MOD | 同一6ケース(try/finally 保護) | R-007, R-008 |
| _staging_plan_gate_precision.py | NEW | 保護パス適用スクリプト(全文置換 + sha256 検査 + `--revert` + 適用後自動検証) | R-001〜R-006, R-012 |
| .claude/hooks/plan_gate.py | MOD | 上記「実装の契約」の実装(**ユーザー手動適用**) | R-001〜R-006, R-012 |
| .claude/agents/planner.md | MOD | 計画ファイル名とブランチ名の対応・ブロックは1つだけ・必須キーの明記 | R-006, R-010 |
| README.md | MOD | フック表の plan_gate 行と 3.20 節の plan_gate 行を実態に合わせる | R-011 |

## 実装手順

| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 1 | セクション3 の冒頭に「本節の plan_gate 仕様はセクション12 で改訂された(2026-07-26)」を1行挿入し、ファイル末尾に「## セクション12: plan_gate 検査精度の改訂」を新設する。内容は本計画の「新しい plan_gate の仕様(実装の契約)」A/B/C をそのまま移す(表 C1〜C10 を含む)。続けて「## 受け入れ条件」テーブル(ID/要件/検証方法/期待結果/種別/対象 の6列、**R-001〜R-012 の12行**)を本計画のトレーサビリティ表と一致する内容で書く。**セクション3 の既存コード掲載は消さず残す**(履歴として。冒頭ポインタで矛盾を防ぐ)(R-001〜R-009 対応) | docs/drafts/control-patterns-spec.md | なし | A |
| 2 | 【テスト先行】受け入れテストを新規作成する(R-001〜R-006, R-012 対応)。`tests/test_env_fingerprint.py` に倣い、フックを import せず `subprocess.run([sys.executable, <plan_gate 絶対パス>], cwd=<tmp>, input="{}")` で起動する。ヘルパ `_run(tmp_path, branch, plan_name, plan_text, invariants_text=None)` を用意し、`git init -q -b <branch>`(**コミットは不要**。`git symbolic-ref` は unborn branch でもブランチ名を返すことを実測済み)、`.claude/plans/<plan_name>` と invariants フィクスチャを書いてから実行する。invariants はテスト内で組むフィクスチャを使い、**リポジトリ本体のものをコピーしない**(値の変更でテストが揺れるうえ、コピーはガードにも触れる)。パスは `Path` の結合で組み立て、シェルのリダイレクトを使わない。ケース一覧は下の「テストケース一覧」に従う。**この時点では現行実装に対して多数 FAIL するのが正しい(RED)** | tests/test_plan_gate.py | なし | B |
| 3 | plan_gate テスト区間(L431-441)を6ケースに拡張する(R-007 対応)。`mktemp -d` の中で `git init -q -b <branch>` してフィクスチャを書き、`uv run python "$ABS_PLAN_GATE"` の exit を期待値と比較する小さなローカル関数を1つ置く。ケースは (a) plans ディレクトリ無し→0 (b) ブランチに対応する計画が無い→0 (c) `experiment: false`→0 (d) 実験語ありで goal 未定義→2 (e) `train_minutes: 1e3`→2 (f) `train_minutes: 999` が上限120超→2。**注意: trap を張らない**(L425 で EXIT トラップを解除済みのため既存規約を壊す)。後始末は `rm -rf "$PG_TMP"` を明示的に実行する。**注意: invariants フィクスチャの生成は、保護パス名をリテラルで含むリダイレクトにしない**(guard_bash が `./verify-hooks.sh` 実行時ではなく編集・検証時に引っかかる。ディレクトリ部分を変数に分ける)。**説明文字列は `"plan_gate: <説明>"` の形で、1ケースにつき1行・1箇所だけ書き、6ケースすべてを互いに異なる文字列にする**(OK / NG のメッセージは関数内で引数を使って組み立てる)。検証方法3 が `grep -cE '"plan_gate: [^"]+"'` で6件を数えるため、説明文字列を複数箇所に書くと件数が合わなくなる。**現行の `echo "OK: plan_gate: passes when..."` の形(説明が別の文字列に埋め込まれた形)ではこの grep に一致しない**(現行ファイルでの実測値は sh / ps1 とも0件)。呼び出し側で独立した引数として `"plan_gate: ..."` を書くこと。挿入位置は現行の plan_gate 区間をそのまま置き換える形(集計ブロック `echo ""` の直前) | verify-hooks.sh | なし | C |
| 4 | sh 版と**同一の6ケース・同一の説明文字列**を追加する(R-007, R-008 対応)。既存の `try { Push-Location } finally { Pop-Location; Remove-Item }` 構造(L458-471)を維持したまま中身を6ケースに広げる。`$ErrorActionPreference = "Stop"` 下で途中例外が起きても後始末に到達すること。説明文字列は `"plan_gate: <説明>"` の形で sh 版と1文字違わず揃え、**1ケースにつき1行・1箇所だけ・6ケースすべて相異なる**ように書く(Step 9 の照合コマンドが生の件数6・一意件数6・1対1対応の3つを検査する) | verify-hooks.ps1 | Step 3 | C |
| 5 | 保護パス適用スクリプトを作成する(R-001〜R-006, R-012 対応)。仕様: (a) 引数なしで適用、`--revert` で復旧。(b) リポジトリ直下で実行されているか確認。(c) **現行ファイルの sha256 が既知の旧版ハッシュと一致する場合のみ**新版を全文書き込みする(新版ハッシュと一致したら `SKIP: 適用済み`、どちらとも違えば `NG: 想定外の内容` で中止)。全文置換方式のため「置換対象がちょうど1件」の代わりにこのハッシュ一致検査を置く。(d) 適用後に `uv run --with pytest python -m pytest tests/test_plan_gate.py -q` を subprocess で実行し、**1件でも失敗したら旧版を書き戻してから NG 終了**する(Stop フックを壊したまま終わらないため)。旧版・新版の全文はスクリプト内に文字列定数として持つ。**注意: 新版のソースは python-style 規約(型ヒント・Google スタイル docstring・why コメント)に従い、docstring の方針記述を新仕様に書き換える**(「パースできない場合は黙って通す」は誤りになる) | _staging_plan_gate_precision.py | Step 2 | B |
| 6 | 【ユーザー手動】`! uv run python _staging_plan_gate_precision.py` を実行して適用する。generator / リーダーは実行しない(保護パスの適用は人間が行う規約)。適用後 `git add .claude/hooks/plan_gate.py` してコミットする(R-001〜R-006, R-012 対応) | .claude/hooks/plan_gate.py | Step 5 | B |
| 7 | 「## 作業手順」の 5.(L32)に、計画ファイル名を**現在のブランチ名の最終セグメント**(`-group-X` を除く)と一致させる規約を追記する。あわせて「## 計画フォーマット」の cost_estimate / goal 行に「4キー(train_minutes / epochs / dataset_gb / parallel_jobs)をすべて数値で書く」「goal は metric / target / direction / baseline / guard_metrics の5キーを goal ブロック配下に書く。guard_metrics が無い場合は `guard_metrics: []` と明示する」「数値は指数表記・引用符・符号を使わない十進で書く」「cost_estimate / goal ブロックは計画中に1つだけ書く(例示を再掲しない)」を追記する(R-006, R-010 対応。plan_gate が最初のブロックを採用するため)。あわせて「`experiment: false` は独立した行に書き、**行末に説明を続けない**(理由は `# ` コメントにする)」を追記する(R-012 の行末固定に合わせた運用規約)。**検証を grep で固定するため、次の6つの文字列をそのまま含めること**: `ブランチ名の最終セグメント` / `4キーをすべて数値で書く` / `guard_metrics: []` / `指数表記` / `ブロックは計画中に1つだけ` / `行末に説明を続けない`(いずれも現行の planner.md には存在しないことを確認済み) | .claude/agents/planner.md | なし | D |
| 8 | フック表の plan_gate 行(L731)を「**現在のブランチ名に対応する**計画のリソース超過(invariants の resources 比)・goal 未定義・**読めない見積もり**をブロック」に更新し、3.20 節の plan_gate 行(L1146)にも「見積もりが数値として読めない計画もブロックする(fail-closed)」を1文加える(R-011 対応)。**検証を grep で固定するため、`ブランチ名に対応する` と `fail-closed` の2文字列をそのまま含めること**(いずれも現行の README.md には存在しないことを確認済み) | README.md | なし | E |
| 9 | 検証をまとめて実行する(R-007〜R-009 対応)。「検証方法」節の全コマンドを順に流す。Windows 実行(R-009)は本機では不可のため、ユーザーへの申し送りとして結果に明記する | (実行のみ) | Step 1〜8 | B |

### テストケース一覧(Step 2)

**特記が無いケースは、cost_estimate 4キー・goal 5キーを完備し上限内に収まる計画を使う**
(「exit 0 を期待しているのに他の必須キーが欠けている」テストを書かないため。
exit 2 を期待するケースも、表に書いた1点だけが不備で他は完備した計画にする)。

| # | 要件 | 入力 | 期待 |
|---|------|------|------|
| T-01 | R-006 | `.claude/plans/` 自体が無い | exit 0 |
| T-02 | R-006 | 非 git ディレクトリ(plans あり・goal 無しの実験計画あり) | exit 0 |
| T-03 | R-006 | ブランチ `pipeline/20260726-foo`、計画は `20260726-bar.md` のみ | exit 0 |
| T-04 | R-006 | ブランチ `pipeline/20260726-foo`、計画 `20260726-foo.md`(実験語あり・goal 無し) | exit 2 |
| T-05 | R-006 | ブランチ `pipeline/20260726-foo-group-B`、計画 `20260726-foo.md`(同上) | exit 2 |
| T-06 | R-006 | ブランチ `feature/foo`、計画 `20260726-foo.md`(同上) | exit 2(日付つき形のマッチ) |
| T-07 | R-006 | ブランチ `feature/foo`、計画 `20260726-foo.md` と `20260725-foo.md` の2件 | exit 0(曖昧なので検査しない) |
| T-08 | 既存 | 対象計画に `experiment: false` | exit 0 |
| T-09 | R-001 | 実験語あり・goal 完備・cost_estimate ブロック無し | exit 2 |
| T-10 | R-001 | cost_estimate に train_minutes が無い(他3キーはある) | exit 2 |
| T-11 | R-002 | `train_minutes: 1e3` | exit 2 かつ stderr に読めない旨 |
| T-12 | R-002 | `train_minutes` が `-5` / `"45"` / `1.2.3`(3ケース) | いずれも exit 2 |
| T-13 | R-002 | `train_minutes: 100.` と `dataset_gb: .5` | exit 0(正当な小数表記の回帰防止) |
| T-14 | R-003 | invariants の `max_train_minutes: 1e3` | exit 2 |
| T-15 | R-003 | invariants に `resources:` ブロックが無い(計画は完備) | exit 0 |
| T-16 | R-003 | `train_minutes: 999` vs 上限 120 | exit 2 かつ stderr に「リソース超過」 |
| T-17 | R-004 | `goal:` ブロックの外に metric / target / direction / baseline を書き、goal ブロック配下は空 | exit 2 |
| T-18 | R-004 | 完備した goal ブロック + 散文に `target: 999` | exit 0(ブロック外を拾わない) |
| T-19 | R-005 | goal に `guard_metrics` が無い | exit 2 |
| T-20 | R-005 | `guard_metrics: []` | exit 0 |
| T-21 | R-005 | `guard_metrics:` の配下に `- name: train_val_gap` が1件 | exit 0 |
| T-22 | R-005 | `direction: down` | exit 2 |
| T-23 | R-012 | 実験計画の本文に `experiment: falsehood` の行がある(goal 無し) | exit 2(行末固定でスキップしない) |
| T-24 | R-012 | `experiment: false   # コード変更のみ` | exit 0 |
| T-25 | R-003 | invariants.md が**読めない**(同名のディレクトリを作って OSError にする)+ 計画は完備 | exit 0(例外終了しないこと) |
| T-26 | R-003 | 同上 + 計画の goal が欠落 | exit 2(計画側の検査は実施される) |
| T-27 | R-006 | ブランチ `pipeline/20260726-foo`、計画は `20260726-extra-foo.md` のみ | exit 0(glob の `*` による誤マッチを弾く) |

T-25 / T-26 の「読めない」状態は、`.claude/improvements/invariants.md` と同名の
**ディレクトリ**を作ることで再現する(`read_text` が `IsADirectoryError`(OSError の
サブクラス)を送出することを本機で実測済み。Windows では `PermissionError` になるが、
これも `OSError` のサブクラスなので扱いは同じ)。
この形が環境依存で不安定な場合に限り、`invariants.md` を**置かない**ケースで代用し、
テストの docstring にその旨を書く。

## 並列化判定

**並列化可能**(グループ A / B / C / D / E。編集ファイルがグループ間で完全に分離しているため)。

- A: `docs/drafts/control-patterns-spec.md`
- B: `tests/test_plan_gate.py`, `_staging_plan_gate_precision.py`, `.claude/hooks/plan_gate.py`(手動適用)
- C: `verify-hooks.sh`, `verify-hooks.ps1`(1対1対応を保つため同一グループ・逐次)
- D: `.claude/agents/planner.md`
- E: `README.md`

**実行上の制約**: グループ B は保護パスの適用(Step 6)を含むため worktree に出さず、
**統合ブランチ上のメインリポジトリ**で実行する(前回踏襲)。C / D / E は worktree で並列実装してよい。
Step 9(検証)は全グループのマージ後に実行する。

## 検証方法

```bash
# 1. 受け入れテスト → 「N passed」かつ失敗0なら PASS(Step 6 適用前は FAIL するのが正しい)
uv run --with pytest python -m pytest tests/ -q

# 2. フックテスト一式 → 最終行が「全テストPASS」なら PASS
./verify-hooks.sh

# 3. plan_gate テストが sh / ps1 とも「互いに異なる6ケース」で、1対1対応しているか(R-007, R-008)
#    → OK が5行出れば PASS
#    生の件数だけでは同じ説明の重複を見逃し、一意件数だけでは重複ぶんの余剰ケースを
#    見逃すため、両方を検査する(ケースが両方から削除されても「全テストPASS」では通らない)
test "$(grep -cE '"plan_gate: [^"]+"' verify-hooks.sh)"  -eq 6 && echo "OK: sh 6行"
test "$(grep -cE '"plan_gate: [^"]+"' verify-hooks.ps1)" -eq 6 && echo "OK: ps1 6行"
A=$(mktemp); B=$(mktemp)
grep -oE '"plan_gate: [^"]+"' verify-hooks.sh  | sort -u > "$A"
grep -oE '"plan_gate: [^"]+"' verify-hooks.ps1 | sort -u > "$B"
test "$(wc -l < "$A")" -eq 6 && echo "OK: sh 6件(一意)"
test "$(wc -l < "$B")" -eq 6 && echo "OK: ps1 6件(一意)"
diff "$A" "$B" && echo "OK: 1対1対応"; rm -f "$A" "$B"

# 3b. planner.md に規約が入ったか(R-010)→ "OK: planner.md 規約6件" が出れば PASS
grep -q "ブランチ名の最終セグメント" .claude/agents/planner.md \
  && grep -q "4キーをすべて数値で書く" .claude/agents/planner.md \
  && grep -qF "guard_metrics: []" .claude/agents/planner.md \
  && grep -q "指数表記" .claude/agents/planner.md \
  && grep -q "ブロックは計画中に1つだけ" .claude/agents/planner.md \
  && grep -q "行末に説明を続けない" .claude/agents/planner.md \
  && echo "OK: planner.md 規約6件"

# 3c. README が新仕様を反映したか(R-011)→ "OK: README 2件" が出れば PASS
grep -q "ブランチ名に対応する" README.md && grep -q "fail-closed" README.md \
  && echo "OK: README 2件"

# 4. 実運用に近い形でのブロック挙動(一時 git リポジトリ)
#    フィクスチャのパスは変数に分ける(保護パス名をリテラルで含むリダイレクトは
#    一時ディレクトリ配下でも guard_bash にブロックされるため)
T=$(mktemp -d); git -C "$T" init -q -b pipeline/20260726-demo
CL="$T/.claude"; INV="$CL/improvements"; PL="$CL/plans"; N=invariants.md
mkdir -p "$PL" "$INV"
printf 'resources:\n  max_train_minutes: 120\n  max_epochs: 100\n  max_dataset_gb: 10\n  max_parallel_jobs: 1\n' > "$INV/$N"
PG="$(pwd)/.claude/hooks/plan_gate.py"
printf '学習ジョブを epoch 30 で回す\n' > "$PL/20260726-demo.md"
( cd "$T" && echo '{}' | uv run python "$PG" ) >/dev/null 2>&1; echo "b=$?"
printf 'cost_estimate:\n  train_minutes: 1e3\n  epochs: 30\n  dataset_gb: 2.4\n  parallel_jobs: 1\ngoal:\n  metric: rmse\n  target: 0.15\n  direction: minimize\n  baseline: 0.21\n  guard_metrics: []\n' > "$PL/20260726-demo.md"
( cd "$T" && echo '{}' | uv run python "$PG" ) >/dev/null 2>&1; echo "c=$?"
printf 'cost_estimate:\n  train_minutes: 999\n  epochs: 30\n  dataset_gb: 2.4\n  parallel_jobs: 1\ngoal:\n  metric: rmse\n  target: 0.15\n  direction: minimize\n  baseline: 0.21\n  guard_metrics: []\n' > "$PL/20260726-demo.md"
( cd "$T" && echo '{}' | uv run python "$PG" ) >/dev/null 2>&1; echo "d=$?"
rm -rf "$T"

# 5. 本リポジトリ自身の Stop が止まらないことの確認(最重要)
#    → 0 なら PASS(本計画は experiment: false のため必ず通る)
echo '{}' | uv run python .claude/hooks/plan_gate.py; echo "self=$?"
```

期待結果: 1 は全 PASS、2 は「全テストPASS」、3 は OK 5行 + 3b / 3c の OK 各1行、4 は `b=2` `c=2` `d=2`
(`c` が 2 になることが fail-closed 化の証拠。旧実装では 0 だった)、5 は `self=0`。

**Windows 機での実行が必要な区間(R-009。本機では実施できない)**:
`verify-hooks.ps1` の plan_gate 区間と notify テストの `CLAUDE_CONTROL_LEVEL` 退避は、
WSL に pwsh が無いため一度も実走できていない。Windows 機で
`.\verify-hooks.ps1` を実行し、**最終行が「全テストPASS」であること**と
**`plan_gate:` で始まる OK 行が6件出ること**を確認する。本機で担保できるのは
上記3(ケース数6・説明の重複なし・sh 版との1対1対応の照合)と、`try` / `finally` による後始末保護の目視確認までである。

## ロールバック手順

`.claude/hooks/plan_gate.py` はこのリポジトリ自身の Stop フックであり、
壊すと全セッションが停止できなくなる。復旧経路を2つ用意する。

1. `! uv run python _staging_plan_gate_precision.py --revert`
   (新版ハッシュを確認してから旧版を書き戻す)
2. 1 が使えない場合: `git checkout 62b118a -- .claude/hooks/plan_gate.py`
   (`62b118a` は現行版が入っているマージコミット。guard_bash が通ることを実測済み)

Step 5 のスクリプトは適用後テストが1件でも失敗したら自動で 1 と同じ書き戻しを行う。
それでも Stop が通らない場合は、`.claude/settings.json` の Stop 配列から plan_gate の
1エントリを外す(保護パスのためユーザー手動。最終手段)。

## リスク

- **検討した代替案1: 検査対象をセンチネルファイル(`.claude/checkpoints/current_plan.txt`)で
  明示する(不採用)**。planner がパスを書き、フックはそれだけを読む。git 非依存で
  テストも容易だが、(a) planner(LLM)が書き忘れると恒久的に無検査になる、
  (b) `.claude/checkpoints/` は gitignore 対象で worktree に伝播しない、
  (c) 古いセンチネルが残ると mtime と同じ「無関係な計画でブロック」を再現する。
  自動的に決まるブランチ名の方が忘却に強いと判断した。
- **検討した代替案2: `git diff --name-only <base>...HEAD -- .claude/plans/` で
  「このブランチが追加した計画」を対象にする(不採用)**。命名規約に依存しない点は
  最も強いが、base ブランチ(main / master / origin/HEAD)の決定が推測になり、
  マージ後や長寿命ブランチで0件・複数件が普通に起きる。テストの組み立ても最も重い。
- **検討した代替案3: 全文置換ではなく箇所ごとの置換(不採用)**。今回は選択ロジック・
  パース・検査の3層をほぼ書き換えるため、部分置換のパターン一致は破綻しやすい。
  「置換対象1件」の代わりに sha256 の完全一致検査を置き、より厳密にした。
- **ブランチ名と計画ファイル名が食い違うと無検査になる(fail-open の残り)**。
  Step 7 で planner.md に命名規約を明記して契約化するが、機械強制はしない。
  「対象が特定できないときは通す」は意図的な設計(全セッションを止めないため)。
  この残余は設計書セクション12 にも明記する。
- **fail-closed 化で計画がブロックされやすくなる**。`学習|実験|train|epoch` を含むだけの
  コード変更計画は、`experiment: false` を書かないと cost_estimate 4キー + goal 5キーを
  要求されるようになる(現行は goal のみ要求)。逃げ道はエラーメッセージに明記する。
  なお、この必須キーは既に planner.md の計画フォーマットが要求している内容であり、
  仕様の新設ではなく「書かれている規約の機械化」である。
- **スキップ判定の行末固定は既存計画の挙動を変えない**(実測。現状分析を参照)。
  ただし今後、`experiment: false` の後ろに理由を直接書いた計画はスキップされなくなる。
  planner.md 側の規約(Step 7)とエラーメッセージで案内する。
- **自己ブロックの危険**。本計画自身は `experiment: false` を冒頭に持つため
  スキップ判定 B で必ず exit 0 になる(検証方法5で確認する)。実装中に別ブランチ
  (`-group-C` 等)から Stop する場合も、同じ計画に解決されるため挙動は同じ。
- **失敗シナリオ1: 適用後に構文エラーで Stop が壊れる** → Step 5 の自動テスト +
  自動書き戻しで防ぐ。手動復旧経路も上記のとおり2つ用意する。
- **失敗シナリオ2: ブロック抽出が実データで期待どおり動かない** → プロトタイプで
  実 invariants.md と計画サンプルに対して検証済み(現状分析)。テスト T-17 / T-18 で固定する。
- **失敗シナリオ3: ps1 版が Windows で構文エラー**(本機で実走できない)→ 既存の
  try / finally 構造を保ったままケースを増やす方針にし、1対1照合(検証方法3)と
  Windows 機での実行(R-009)をユーザーへ申し送る。
- **未確認の仮定**: なし(git のブランチ取得挙動・ガードの許否・ブロック抽出・
  pytest の起動方法はいずれも実測済み)。ただし `verify-hooks.ps1` の実走のみ
  本機では確認できない(上記のとおり明示的な残件として扱う)。

## トレーサビリティ

Step 1 で設計書に書く「## 受け入れ条件」テーブルと同じ ID を使う。

| ID | 要件 | 対応ステップ | 検証方法 | 種別 |
|---|---|---|---|---|
| R-001 | cost_estimate ブロック・4キーの欠落をブロックする | 1, 2, 5, 6 | `uv run --with pytest python -m pytest tests/test_plan_gate.py -q`(T-09, T-10) | auto |
| R-002 | 見積もりの値が非負十進で読めない場合ブロックする(`1e3` `-5` `"45"` `1.2.3`)。`200.` `.5` は通す | 1, 2, 5, 6 | 同上(T-11〜T-13) | auto |
| R-003 | invariants の `max_*` が読めない場合ブロックし、キー / ブロック不在 / ファイルが読めない場合は上限比較のみスキップして例外終了しない | 1, 2, 5, 6 | 同上(T-14〜T-16, T-25, T-26) | auto |
| R-004 | goal のキー検査を `goal:` ブロック配下に限定する | 1, 2, 5, 6 | 同上(T-17, T-18) | auto |
| R-005 | guard_metrics を実際に検査し、direction の値域を検査する | 1, 2, 5, 6 | 同上(T-19〜T-22) | auto |
| R-006 | 検査対象の計画をブランチ名から決める(`-group-X` 除去・日付つき形の**完全一致**・曖昧なら無検査) | 1, 2, 5, 6, 7 | 同上(T-01〜T-08, T-27) | auto |
| R-007 | verify-hooks に exit 2 側の回帰テストを追加する(sh / ps1 各6ケース、説明は相異なる) | 1, 3, 4, 9 | `./verify-hooks.sh` が「全テストPASS」**かつ**検証方法3 の件数アサーション(生6行・一意6件を sh / ps1 の両方で)が通る | auto |
| R-008 | ps1 版と sh 版の plan_gate テストが1対1対応している | 1, 3, 4, 9 | 検証方法3 の diff が空(一意件数6の確認とセット) | auto |
| R-009 | Windows 機で `verify-hooks.ps1` が全 PASS する | 1, 4, 9 | Windows 機で `.\verify-hooks.ps1` を実行(最終行が「全テストPASS」かつ `plan_gate:` の OK 行が6件) | manual |
| R-010 | planner.md に計画ファイル名とブランチ名の対応規約・cost_estimate 4キー・goal 5キー・十進数表記・ブロックは1つだけ・`experiment: false` の行末規約 が記載されている | 7, 9 | 検証方法3b の grep 6件が通り "OK: planner.md 規約6件" が出る | auto |
| R-011 | README のフック表と 3.20 節が新仕様(ブランチ名対応・fail-closed)を反映している | 8, 9 | 検証方法3c の grep 2件が通り "OK: README 2件" が出る | auto |
| R-012 | `experiment: false` の判定を行末まで固定する(`experiment: falsehood` ではスキップせず、`# コメント` つきならスキップする) | 1, 2, 5, 6, 7 | `uv run --with pytest python -m pytest tests/test_plan_gate.py -q`(T-23, T-24) | auto |

全 R-ID に対応ステップがあり、すべてのステップがいずれかの R-ID に対応する。

## 未確定事項(回答があれば反映する。無ければ下記の既定で進行できる)

いずれも本計画で既定を決めてあり、着手をブロックしない。方針を変えたい場合のみ指示がほしい。

1. **fail-closed の適用範囲(既定: 計画側は厳格・invariants 側は「キーがあるのに読めない」のみ)**。
   選択肢 A: 既定どおり。B: invariants に `resources:` ブロックが無い場合もブロックする
   (下流プロジェクトが resources を消すと全計画が止まる)。C: 計画側も cost_estimate 欠落は
   見逃す(現行に近く、fail-closed 化の効果が半減する)。
2. **実験語だけを含むコード変更計画の扱い(既定: cost_estimate 4キーも必須)**。
   選択肢 A: 既定どおり(`experiment: false` を書けば回避できる)。
   B: goal だけ必須のまま cost_estimate は「ブロックがあるときだけ中身を検査」にする
   (ブロックされにくいが、見積もりを書かない計画が通る)。
3. **検査対象の決定方式(既定: ブランチ名からの導出)**。リスク節の代替案1(センチネル)・
   代替案2(git diff)を選ぶ場合は指示がほしい。

## 知識の自動スタック(確認結果)

- (a) CONTEXT.md: リポジトリ直下に CONTEXT.md は無い(テンプレート本体のため)。追記対象なし。
- (b) ADR: **作成済み** — `docs/adr/0004-plan-gate-target-and-fail-closed.md`
  (検査対象の決定方式と fail-closed の適用範囲は、複数案から1つを選ぶ・後から変えにくい決定のため)。
- (c) EXPERIMENT_LOG: 学習・実験を伴わない(`experiment: false`)。追記対象なし。
