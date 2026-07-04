# 実装計画: 設計書適合チェック(spec-compliance)

参照した設計書: docs/active/20260704_spec_compliance_check.md
参照ADR: docs/adr/0001-spec-gate-two-stage-verification.md / 0002-human-approval-via-protected-file.md / 0003-mandatory-ci-spec-gate.md
作成日: 2026-07-04

## 目的
設計書(docs/active/)の受け入れ条件テーブルを唯一の要件ソースとし、
Stop フックと CI で「全要件PASS+承認+独立監査」を機械検査する仕組みを追加する。
LLMの自己申告ではなく、ID・フック・テスト・独立視点で実装漏れを構造的に塞ぐ。

## 現状分析
- 確認済み: _common.py の PROTECTED_PATH_PATTERNS は /.claude/hooks/・settings.json・settings.local.json のみ。.claude/agents/・.claude/commands/・.claude/skills/・templates/・verify-hooks.*・claude-init/update.* は保護対象外で Claude が直接編集可能。
- 確認済み: enforce_eval.py は Stop フックの実装パターン(stdin JSON パース → stop_hook_active 早期return → env フラグ判定 → git状態の sha256 キャッシュ → 失敗時 exit 2)を持ち、spec_gate の雛形にできる。
- 確認済み: guard_scope.py は PROTECTED_PATH_PATTERNS を部分一致で判定。approvals.txt をこのリストに足せば Claude 経由の Edit/Write は exit 2 でブロックされる(R-106)。guard_bash.py も同リストでリダイレクト/tee を検査するため bash 経由書き込みも塞がる。
- 確認済み: verify-hooks.sh の test_hook は「stdin に JSON を流し exit code を照合」する形式。spec_gate はフィクスチャ(設計書+verdict+audit+approvals)と env が要るため専用ヘルパが必要。
- 確認済み: settings.json の Stop は enforce_eval のみ配線。spec_gate の Stop 配線追加が必要だが settings.json は保護パス。
- 確認済み: claude-init.sh/.ps1 は .gitignore へ冪等追記する for ループを持つ。.github/workflows/ の配置処理は未実装。
- 確認済み: design-interview の ADR は Q3/Q4/Q7 分を作成済み。planner 側で新規 ADR は不要。
- 確認済み: docs/active/ を新規作成し設計書を移動済み。docs/drafts/ は空。

## 変更対象

### 新規ファイル
| ファイル | 保護 | 内容 |
|---|---|---|
| .claude/hooks/spec_gate.py | 保護(手動配置) | Stop フック。CLAUDE_SPEC_CHECK=1 のとき6検査を実行。--ci モードあり。--docs <dir> / env で対象docsディレクトリ上書き(テスト用) |
| .claude/hooks/spec_approve.py | 保護(手動配置) | 「! uv run python .claude/hooks/spec_approve.py R-003」で approvals.txt に「設計書名 要件ID 日時」を追記 |
| .claude/agents/spec-auditor.md | 可 | 監査エージェント(sonnet)。証拠検証+スコープ外変更列挙→audit-*.md 出力 |
| templates/spec-gate.yml.template | 可 | GitHub Actions 雛形。PR時に spec_gate.py --ci 実行 |

### 既存ファイルの変更
| ファイル | 保護 | 変更 |
|---|---|---|
| .claude/hooks/_common.py | 保護(手動編集) | PROTECTED_PATH_PATTERNS に approvals.txt を追加。受け入れ条件テーブルのパーサ関数を追加(spec_gate と verify-hooks から import) |
| .claude/settings.json | 保護(手動編集) | Stop に spec_gate.py を追加配線(enforce_eval と併存) |
| .claude/skills/design-interview/SKILL.md | 可 | 完了時に受け入れ条件テーブル生成を必須化 |
| .claude/agents/planner.md | 可 | テーブルなし設計書の差し戻し+受け入れテスト事前作成ステップ+要件ID⇔ステップ対応を必須化 |
| .claude/agents/evaluator.md | 可 | verdict-*.md 出力(要件IDごと ID/判定/コマンド/実測値/証拠file:line、全要件にPASS/FAIL/UNVERIFIABLE) |
| .claude/commands/ml-pipeline.md | 可 | spec-auditor を evaluator×2 の後に追加。CLAUDE_SPEC_CHECK の案内 |
| claude-init.ps1 / .sh | 可 | .github/workflows/spec-gate.yml 自動配置。.gitignore に .claude/spec/ 追記 |
| claude-update.ps1 / .sh | 可 | 同上(冪等) |
| verify-hooks.ps1 / .sh | 可 | R-101〜R-109・R-112 の auto テスト追加 |
| templates/settings.local.json.template | 可 | env に CLAUDE_SPEC_CHECK / CLAUDE_SPEC_RECHECK_N 追記 |
| README.md / CHANGELOG.md | 可 | 機能説明・変更履歴の追記 |

## 実装手順

### フェーズ0: パーサとフックの中核(保護パス外で先に作る)
Generator は保護パスに書けないため、保護対象ファイル(spec_gate.py / spec_approve.py / _common.py / settings.json)は作業スコープ直下の spec_staging/ に完成形を出力し、後述フェーズ5でユーザーが手動適用する。

1. **受け入れ条件テーブルパーサを設計**(spec_staging/_common.py に _common.py の完成形として反映)。
   - 関数例: parse_acceptance_table(design_text) -> list[dict]。設計書テキストから「## 受け入れ条件」直下の Markdown テーブルを正規表現で抽出し、ID/要件/検証方法/期待結果/種別/対象 の6列を dict 化。
   - 安全側の異常検知(R-107): 列数不一致・ID重複・ID欠番・テーブル不在は例外(または特別値)を返し、呼び出し側で exit 2 にできること。
   - 既存の PROTECTED_PATH_PATTERNS に /.claude/spec/approvals.txt を追加。
   - 注意: パーサは stdlib(re)のみ。パイプ記号のエスケープ、前後空白 strip、区切り行(|---|)のスキップを実装。
2. **spec_gate.py を実装**(spec_staging/hooks/spec_gate.py)。enforce_eval.py を土台に:
   - stdin JSON パース → stop_hook_active なら exit 0 → CLAUDE_SPEC_CHECK != "1" なら exit 0(R-112)。
   - 対象 docs ディレクトリ決定: --docs <dir> 引数 or 環境変数があればそれ、なければ CLAUDE_WORK_SCOPE 配下の docs/active/、無ければ ./docs/active/(設計書リスク「複数active」対応)。
   - docs/active/ の全設計書をパース。パース異常があれば exit 2(R-107)。
   - 検査(1つでも欠ければ exit 2):
     (a) verdict-*.md が全要件IDを網羅し全て PASS か(欠けID/FAIL があれば落とす。R-102/R-103)。
     (b) auto要件から CLAUDE_SPEC_RECHECK_N(既定3、all で全件)をランダム抽出し検証コマンド再実行→期待結果照合。all 時は全IDを実行ログに出す(R-108)。
     (c) 「対象」列のある要件は coverage で対象モジュールの実行有無を確認。coverage 未インストールなら該当検査をスキップし警告(fail open。R-109 は coverage 前提で exit 2)。
     (d) manual要件が approvals.txt に「設計書名 要件ID」で承認済みか(R-104/R-105)。
     (e) audit-*.md が存在し全件OKか。
   - enforce_eval と同じ git状態 sha256 キャッシュを実装(重いテストの二重実行防止)。マーカーは .claude/spec/last_spec_pass.txt 等。
   - --ci モード: 抽出ではなく auto要件を全件再実行、manual は承認済み確認、verdict/audit の網羅確認。
   - 注意(失敗シナリオ): docs/active/ 不在時に誤って exit 2 で全 Stop をブロックしないこと。CLAUDE_SPEC_CHECK=1 かつ設計書0件なら「対象なし」で exit 0。
3. **spec_approve.py を実装**(spec_staging/hooks/spec_approve.py)。引数の要件ID + docs/active/ の設計書名 + 日時を .claude/spec/approvals.txt に追記(親ディレクトリを mkdir)。ユーザーの「!」実行専用。
4. **settings.json の Stop 配線完成形**を spec_staging/settings.json に出力(enforce_eval と spec_gate の2フックを Stop に併記)。

### フェーズ1: エージェント/スキル/コマンド(保護パス外・Generator が直接編集)
5. evaluator.md: 完了時に verdict-*.md を出力する手順を追加(要件IDごとの機械可読テーブル、全要件に判定必須)。
6. spec-auditor.md 新規作成(sonnet)。独立コンテキストで証拠検証+diff とのスコープ外変更列挙→audit-*.md 出力。
7. planner.md: 設計書受領時に受け入れ条件テーブルが無ければ差し戻す旨、計画に「auto要件の受け入れテストを実装前に書くステップ」と要件ID⇔実装ステップ対応を必須化。
8. design-interview/SKILL.md: 完了手順(手順8付近)に受け入れ条件テーブル生成の必須化を追記。
9. ml-pipeline.md: 手順にspec-auditor(evaluator×2の後)と CLAUDE_SPEC_CHECK の案内を追加。

### フェーズ2: テンプレ・配置スクリプト(Generator が直接編集)
10. templates/spec-gate.yml.template 新規作成。
11. templates/settings.local.json.template の env に CLAUDE_SPEC_CHECK / CLAUDE_SPEC_RECHECK_N 追記。
12. claude-init.sh/.ps1・claude-update.sh/.ps1: .github/workflows/spec-gate.yml を配置(既存なら保持)、.gitignore の for ループ対象に .claude/spec/ を追加(R-110)。

### フェーズ3: テスト(Generator が直接編集)
13. verify-hooks.sh/.ps1 に spec_gate 用ヘルパを追加。フィクスチャ(mktemp のテンポラリdir)に最小設計書+verdict+audit+approvals を書き、CLAUDE_SPEC_CHECK=1 + --docs <fixture> で {} を stdin 供給し exit code を照合。auto要件の検証コマンドは決定的な簡易コマンド(例: python で sys.exit(0))を使う。R-101〜R-109・R-112 を追加(R-109 は coverage 未導入環境ではスキップ表示)。テスト後にフィクスチャを掃除。bash/PowerShell 両方を同内容で保守。

### フェーズ4: ドキュメント(Generator が直接編集)
14. README.md に spec-compliance の使い方(env設定・全体フロー・spec_approve の「!」実行)を追記。CHANGELOG.md [Unreleased] に Added として追記。

### フェーズ5: ユーザーによる保護パス適用(手動・計画に明記が必須)
Generator 完了後、ユーザーが手動で以下を実行して保護ファイルを反映する(ガードは有効なまま)。
- spec_staging/hooks/spec_gate.py を .claude/hooks/spec_gate.py へコピー
- spec_staging/hooks/spec_approve.py を .claude/hooks/spec_approve.py へコピー
- spec_staging/_common.py を .claude/hooks/_common.py へコピー
- spec_staging/settings.json を .claude/settings.json へコピー
- 適用後 spec_staging/ ディレクトリを削除
適用後、下記「検証方法」を実行する。代替として一時的にガードを外す運用もあるが、自己書き換え防止の観点から staging+手動コピーを推奨(不採用理由はリスク欄)。

## 検証方法
すべて作業スコープ直下で実行。PASS 条件を併記。

1. **フック単体テスト(R-101〜R-109・R-112)**
   - bash verify-hooks.sh → 期待: 末尾「全テストPASS」、exit 0。
   - pwsh -File verify-hooks.ps1 → 期待: 同上。
   - 内訳の期待 exit code(spec_gate.py へ {} を stdin、env/fixture 指定):
     - R-101 全要件PASS+承認済み+監査OK → exit 0
     - R-102 FAIL要件あり → exit 2
     - R-103 verdict にID欠け → exit 2
     - R-104 manual未承認 → exit 2
     - R-105 spec_approve 実行後の R-104 ケース → exit 0
     - R-106 approvals.txt への Claude 書き込み(guard_scope.py に file_path=.claude/spec/approvals.txt の Write JSON)→ exit 2
     - R-107 テーブル列不足/ID重複 → exit 2
     - R-108 CLAUDE_SPEC_RECHECK_N=all で実行ログに全ID出現(ログ grep でアサート)
     - R-109 対象列ありで対象モジュール未実行(coverage 導入時)→ exit 2 / 未導入時はスキップ表示
     - R-112 CLAUDE_SPEC_CHECK 未設定 → exit 0
2. **CIワークフロー(R-110・Q7)**
   - テンポラリで init を実行(mktemp した空dirで git init 後 claude-init.sh を実行)し、.github/workflows/spec-gate.yml が存在し中身に「spec_gate.py --ci」を含むこと → PASS。
   - .gitignore に .claude/spec/ が入っていること → PASS。
3. **spec-auditor 組み込み(R-111・目視)**
   - .claude/commands/ml-pipeline.md の手順に spec-auditor が evaluator×2 の後に記載 → 目視で確認、ユーザー承認。
4. **回帰(既存動作の非破壊)**
   - bash verify-hooks.sh の既存23ケースが全て PASS のまま(R-112 と合わせ既存 Stop 動作を壊さない)。

## リスク
- **未確認の仮定**: spec_gate のテスト容易性のため --docs <dir> / 上書き env を新設する前提。設計書に明記は無いが、フィクスチャで docs/active/ を差し替えられないと verify-hooks が書けないため必須と判断。Generator はこの上書き口を必ず実装すること。
- **保護パスの適用漏れ**: フェーズ5 の手動コピーをユーザーが忘れると spec_gate/spec_approve が未配置で機能しない。検証手順1の実行自体が適用確認を兼ねる(未配置ならテストが失敗する)。
- **fail open の副作用**: coverage 未導入で R-109 検査をスキップするため、対象列の検査が実質無効化されるケースがある。CI 側(spec-gate.yml)で coverage を導入することで本番ゲートは有効に保つ。
- **設計書0件・docs/active 不在での過剰ブロック**: CLAUDE_SPEC_CHECK=1 でも対象設計書0件なら exit 0 とする(過剰ブロック回避)。実装手順2に注意書き済み。
- 検討した代替案と不採用理由(ADR に既決、要点のみ):
  - 要件の機械可読形式に別JSONファイルを持つ案 → 二重管理を生むため不採用。設計書内 Markdown テーブル1本に統一(Q1)。
  - auto要件を毎回全件再実行する案 → 実行コスト過大。ランダム抽出+all 逃げ道で妥協(ADR-0001/Q4)。
  - 独立検証を逆生成diffで行う案 → 偽陽性とコスト大。spec-auditor 1体に集約(Q5)。
  - 保護ファイルをガード一時解除で編集する案 → 自己書き換え防止を弱めるため非推奨。staging+手動コピーを採用。

## 作業ログ(Generator)

### フェーズ0(手順1-4): 完了
- `spec_staging/_common.py`: `PROTECTED_PATH_PATTERNS` に `/.claude/spec/approvals.txt` を追加。
  `AcceptanceTableError` / `split_table_row` / `is_separator_row` / `parse_acceptance_table` を実装
  (テーブル不在・列数不一致・列名不正・ID形式不正・ID重複・ID欠番を検知)。
- `spec_staging/hooks/spec_gate.py`: Stop / `--ci` 両対応。`--docs`・`--spec-dir`(独自追加。env
  `CLAUDE_SPEC_DOCS` / `CLAUDE_SPEC_DIR`)でテスト用ディレクトリ上書き。verdict網羅+PASS判定・
  auto要件のランダム/全件再実行・coverage連動(fail open)・manual承認確認・audit網羅確認の5検査。
  git状態+specディレクトリ内容のsha256キャッシュで再実行をスキップ(--ci時は無効)。
- `spec_staging/hooks/spec_approve.py`: `<要件ID>` 引数を受け取り、docs内の該当設計書を特定して
  approvals.txt に `設計書名 要件ID 日時` を追記。
- `spec_staging/settings.json`: Stop に `spec_gate.py` を `enforce_eval.py` と併記した完成形。
- フィクスチャ(R-101〜R-104, R-107, R-108, R-112)を作業ディレクトリ内(`spec_staging/fixture_test/`,
  作業後削除)で作成し、`spec_staging/hooks/spec_gate.py` / `spec_approve.py` を直接実行して
  期待exitコードを確認済み(全て一致)。

### フェーズ1(手順5-9): 完了
- `evaluator.md` に verdict ファイル出力手順(ID/判定/実行コマンド/実測値/証拠のテーブル、
  PASS/FAIL/UNVERIFIABLE必須)を追加。
- `spec-auditor.md` を新規作成(sonnet)。証拠検証・auto要件再実行・スコープ外変更列挙・
  audit-*.md出力の手順を明記。
- `planner.md` に受け入れ条件テーブル不在時の差し戻し、テストファーストステップ必須化、
  要件ID⇔ステップ対応の付記を追加。
- `design-interview/SKILL.md` の完了手順(手順8)に受け入れ条件テーブル生成を必須化。
- `ml-pipeline.md` に spec-auditor(evaluator×2の後)と CLAUDE_SPEC_CHECK の案内を追加。

### フェーズ2(手順10-12): 完了
- `templates/spec-gate.yml.template` 新規作成(`spec_gate.py --ci` 実行、未配置ならSKIP)。
- `templates/settings.local.json.template` に `CLAUDE_SPEC_CHECK` / `CLAUDE_SPEC_RECHECK_N` を追記。
- `claude-init.sh/.ps1`・`claude-update.sh/.ps1` に `.github/workflows/spec-gate.yml` の
  自動配置(既存なら保持)と `.gitignore` への `.claude/spec/` 追加を実装。
  ネットワーク経由の実クローンは検証できないため、`.gitignore`/workflow配置ロジックのみを
  ローカルの一時ディレクトリで再現して動作確認(bashスクリプトは `bash -n` で構文確認も実施)。

### フェーズ3(手順13): 完了
- `verify-hooks.sh` / `verify-hooks.ps1` に spec-compliance 用テスト(R-101〜R-109, R-112)を追加。
  `spec_gate.py` / `spec_approve.py` が `.claude/hooks/` に未配置の間は SKIP 表示にして
  既存23ケースを壊さない設計(実行して確認済み: 既存23ケース全PASS + SKIP表示)。
- `spec_staging/` 内のファイルを一時的に指す設定にしたドライラン版スクリプトで、
  R-101・R-102・R-103・R-104・R-105・R-107・R-108・R-112 が bash / PowerShell 両方で
  期待通りPASSすることを確認。R-106(guard_scope経由のapprovals.txt保護)はフェーズ5で
  `_common.py` を適用するまでは意図的にNGになることを確認(未適用時の期待挙動)。
  R-109はcoverage未導入環境のためSKIPパスを確認(coverage導入環境向けの分岐も実装済み)。

### フェーズ4(手順14): 完了
- `README.md` に spec-compliance 節(使い方・env・spec_approveの`!`実行)、
  エージェント表への spec-auditor 追加、フック表への spec_gate/spec_approve 追加、
  ファイル一覧の更新を反映。
- `CHANGELOG.md` の `[Unreleased]` に `### Added` として spec-compliance 一式を追記。

### フェーズ5(ユーザー手動適用): 未実施・ユーザー作業待ち
以下をユーザーが手動で実行する必要がある(Generatorは保護パスへ書き込めないため未実施)。

```
cp spec_staging/hooks/spec_gate.py .claude/hooks/spec_gate.py
cp spec_staging/hooks/spec_approve.py .claude/hooks/spec_approve.py
cp spec_staging/_common.py .claude/hooks/_common.py
cp spec_staging/settings.json .claude/settings.json
rm -rf spec_staging/
```

適用後、`bash verify-hooks.sh` と `pwsh -File verify-hooks.ps1` を実行し、
新規テスト(R-101〜R-109, R-112)が SKIP ではなく OK になること、
既存23ケースを含め「全テストPASS」になることを確認する
(ドライランで動作は確認済みのため、適用後は原則そのままPASSする見込み)。
