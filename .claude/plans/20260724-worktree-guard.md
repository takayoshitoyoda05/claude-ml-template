# 計画: worktree 分離違反の再発防止(cwd ベース封じ込め)

- 設計書: なし(ユーザー直接依頼 / リーダー裁定を反映)
- ブランチ: pipeline/20260724-worktree-guard
- 作業スコープ: /home/toyod/claude-ml-template

## 目的
worktree 担当エージェントがメインリポジトリのファイル(事故例: README)へ誤書き込み・
ステージした事故を機械的に止める。guard_scope.py に「ペイロード cwd が worktree 配下なら
書き込み先も同じ worktree 配下に限定する」ゲートを追加し、二重防御(プロンプト+フック)の
フック側を強化する。

## 現状分析
- guard_scope.py の既存スコープ判定(L91-109)は `CLAUDE_WORK_SCOPE`、未設定なら
  `os.getcwd()` の配下だけを許可する。worktree エージェントの作業スコープはメインリポジトリ
  全体に設定されるため、メイン配下の README への書き込みは既存判定を素通りする。これが事故の
  構造的原因(参照=メイン絶対パス / 編集=worktree 相対パスの非対称でパスを誤用しても、
  既存ゲートは「スコープ内」と見なして通してしまう)。
- 確認済み: guard_scope.py は `data = json.load(sys.stdin)` で全ペイロードを読むため
  `data.get("cwd")` でトップレベル cwd を参照できる。test_hook は渡した JSON をそのまま
  stdin に流すので、JSON に `cwd` を含めた決定的テストが書ける。
- 確認済み: `.worktrees/` は .gitignore(L19)にのみ存在し、_common.py の
  ARTIFACT_DIR_PATTERNS / PROTECTED_PATH_PATTERNS には含まれない。よって worktree 配下への
  正当な書き込みはブロックされず、本機能の「同 worktree 内なら許可」が成立する。
- 確認済み: guard_scope.py は PROTECTED_PATH_PATTERNS の `/.claude/hooks/` 配下 →
  エージェントは Edit/Write/リダイレクト等で編集できない。運用は「変更はユーザーが手動」
  (README L735-737)。よって guard_scope.py の変更はユーザー適用ステップにする。
- 確認済み: verify-hooks.sh / verify-hooks.ps1 / README.md / .claude/commands/ml-pipeline.md /
  CHANGELOG.md はいずれも非保護 → エージェントが直接編集できる。
- 確認済み: ml-pipeline 手順5の worktree 注意書きは L143-165、README の並列実装節は L288-292。

## 変更対象
| ファイル | 変更内容 |
|---------|---------|
| .claude/hooks/guard_scope.py | cwd ベースの worktree 封じ込めゲートを追加(末尾 exit 0 前)。cwd は `data.get("cwd") or os.getcwd()` の二段構え。保護パスのためユーザーが手動適用 |
| verify-hooks.sh | 封じ込めの3ケース(同worktree=0 / worktree→メイン=2 / メイン→worktree=0)テストを追加 |
| verify-hooks.ps1 | 同上を Test-Hook 形式で追加(sh と対称) |
| README.md | 3.x フック節または並列実装節(L288-292)に1文追記(cwd 基準で本体書き込みをブロック) |
| .claude/commands/ml-pipeline.md | 手順5の worktree 注意書き(L143-165 付近)に1文追記 |
| CHANGELOG.md | [Unreleased] の Added(2026-07-24)に1項目追加 |

## 実装方式(採用案の要点)
- 追加ヘルパー(Codex採用で強化): worktree 判定は**スコープルート直下**に限定 —
  `os.path.realpath(cwd)` が `<realpath(allowed_root)>/.worktrees/<名前>` 配下のときのみ
  そのルートを返す(任意の場所の .worktrees を worktree と誤認しない)。
  cwd は `data.get("cwd")` が**非空文字列の場合のみ**採用し、それ以外は os.getcwd() に
  フォールバック。ヘルパー全体を try/except で包み、例外時は None(=ゲート不活性・
  誤ブロックしない安全側)。
- main() 内: 既存スコープ判定を通過した後、worktree ルートを求める。ルートがあれば、
  書き込み先も **os.path.realpath で解決してから**(symlink 迂回を塞ぐ。Codex採用)
  同ルート配下かを末尾スラッシュ付き前方一致で検査し、外れていれば既存と同形式の
  `[guard_scope] BLOCKED: ...` を stderr に出して exit 2。
  cwd が worktree 外(メイン)のときはゲート不活性 → 現状維持。
- 二段構えの根拠: ペイロード cwd を優先し、無い/空なら os.getcwd() にフォールバックする。
  これによりペイロードに cwd が来るか否かに関わらず誤ブロックしない安全側に倒れる
  (この防御は補助線であり完全性は主張しない。secret-safety.md の既存原則と同位置づけ)。

## 実装手順
| # | 内容 | 対象ファイル | 依存 | 並列グループ |
|---|------|-------------|------|-------------|
| 1 | 封じ込め3ケースのテストを追加(下記ケース表)。この時点では未実装なので同worktree/メイン→worktree は誤ってPASS・worktree→メインはFAILしうる=テスト先行で失敗を可視化 | verify-hooks.sh | なし | A |
| 2 | 同一3ケースを Test-Hook 形式で追加(sh と対称) | verify-hooks.ps1 | なし | A |
| 3 | worktree 封じ込めゲートを追加(ヘルパー+main末尾)。**保護パスのためエージェントは編集不可** → generator は新内容をスクラッチに用意し**ユーザーが手動適用**(エディタ or ユーザー実行の `!` コマンド)。適用後 `git add .claude/hooks/guard_scope.py`(明示パス指定の add は guard_bash の変更系コマンド検知に当たらず通る)でステージ | .claude/hooks/guard_scope.py | Step 1,2(テストで挙動確認するため) | A |
| 4 | `bash verify-hooks.sh` を実行し全PASS(既存テスト含む)を確認。既存の cwd 無しテストが新ロジックで誤ブロックされないことを併せて確認 | (実行のみ) | Step 3 | A |
| 5 | 並列実装節に1文追記(worktree 担当の本体書き込みは cwd 基準でガードがブロック) | README.md | なし | B |
| 6 | 手順5 の worktree 注意書きに同1文を追記 | .claude/commands/ml-pipeline.md | なし | B |
| 7 | Added(2026-07-24)に1項目追加 | CHANGELOG.md | なし | B |

テストケース表(Step 1/2、$RP はリポジトリ絶対パス。Codex採用で6ケースに拡充):
| ケース | cwd | file_path | 期待 exit |
|-------|-----|-----------|----------|
| 同 worktree 内 | $RP/.worktrees/group-A | $RP/.worktrees/group-A/src/foo.py | 0 |
| worktree→メイン | $RP/.worktrees/group-A | $RP/src/train.py | 2 |
| メイン→worktree(現状維持) | $RP | $RP/.worktrees/group-A/src/foo.py | 0 |
| 前方一致の隣接名 | $RP/.worktrees/group-A | $RP/.worktrees/group-AB/src/foo.py | 2 |
| worktree 内サブディレクトリ cwd | $RP/.worktrees/group-A/src | $RP/src/train.py | 2 |
| 不正 cwd 型(数値) | 12345(JSON数値) | $RP/src/train.py | 0(フォールバック・誤ブロックしない) |
(symlink ケースは環境依存のため verify-hooks には含めず、realpath 解決の実装で対処
 — 除外理由をここに記録)

注(Step 3 の失敗シナリオ対策):
- ゲートは必ず既存スコープ判定の「後」に置く。前に置くと worktree ルート算出前に
  scope で弾かれる/通される順序依存が生じる。
- 比較は既存 L98-103 と同じく末尾スラッシュ付き・Windows は lower() で揃える。前方一致の
  誤許可(`.worktrees/group-A` が `.worktrees/group-AB` を通す)を防ぐため。
- ケース表の file_path は全てリポジトリ配下の絶対パスにする。既存スコープ判定(scope=リポジトリ
  or getcwd)を先に通し、封じ込めゲート単独の合否を検証するため(メイン→worktree ケースが
  ARTIFACT/PROTECTED に当たらないよう `.md`/`src/*.py` を使う)。

コミット案(CLAUDE_COMMIT_STEP_RULE 対応で step 番号入り):
- `test(step 1): worktree封じ込めのverify-hooksテストを追加(sh/ps1)`
- `feat(step 2): guard_scopeにcwdベースのworktree封じ込めを追加`
- `docs(step 3): worktree封じ込めをREADME/ml-pipeline/CHANGELOGに反映`
（Step 番号は実装単位でまとめる。guard_scope はユーザー手動適用後にステージ→コミット）

## 並列化判定
並列化可能(グループ A=フック+テスト+検証、グループ B=文書3ファイル)。
理由: A と B は対象ファイルが完全に分離し依存が無い。B の文書は挙動の説明のみでコード実行に
依存しない。A 内(Step 1→2→3→4)は「テストで挙動を確認しながら実装」する論理依存があるため
逐次。保守的に、A 内は分割しない。

## 検証方法(fail-fast)
1. `bash verify-hooks.sh` → 最終行「全テストPASS」かつ exit 0。新規3ケースが OK 表示。
   (Step 3 未適用の状態で走らせると worktree→メインの新規ケースが NG になり、実装が
   入っていないことを検出できる=fail-fast の担保)
2. Windows 環境がある場合のみ `pwsh verify-hooks.ps1` → 同様に全PASS。無い場合は sh と
   同一ケースを目視で対称に追加したことを diff で確認。
3. 既存テスト(cwd フィールド無し)が全て従来どおりの exit を維持していることを 1 の出力で確認。

## リスク
- 誤ブロックの失敗シナリオ1: メイン作業のつもりでもユーザーが手動で worktree に cd し、その
  cwd がペイロードに載ると、worktree 外への書き込みが封じ込められる。→ 設計意図どおり(worktree に
  いるなら封じ込める)。許容。
- 誤ブロックの失敗シナリオ2: ペイロードに cwd が無く、かつフックプロセスの os.getcwd() が
  worktree 配下のとき、cwd 無しの書き込みが封じ込め対象になりうる。→ verify-hooks はリポジトリ
  ルートから実行するため既存テストは影響を受けない(検証方法3で担保)。実運用でメインエージェントの
  os.getcwd() が worktree になる状況は想定しない。
- (更新: Codex指摘採用済み)シンボリックリンク迂回は、cwd・書き込み先とも
  os.path.realpath 解決後に比較する実装で対処する(実装方式の節を参照)。
  realpath でも解決できない特殊経路(バインドマウント等)は補助線の限界として受容。
- 検討した代替案A(os.getcwd() だけで判定/ペイロード cwd を使わない): 既存 L95 と同経路で単純だが、
  フックプロセスの cwd がエージェントの worktree を反映する保証を静的に確認できず、反映されない場合に
  無防備。→ 不採用(二段構えの方が安全側)。
- 検討した代替案B(scope チェック自体を worktree 対応に書き換える): 既存の scope 意味論を変えると
  リーダー/メイン作業の従来挙動に非互換が出る。→ 不採用(独立ゲート追加の方が最小 diff・非互換なし)。
- スコープ限定: `.sandbox-worktrees/`(.gitignore L20)は今回対象外。事故・設計はいずれも
  `.worktrees` を対象としており、対象拡大は要求外のため含めない。
- 未確認の仮定: 実際の worktree 担当エージェントの PreToolUse ペイロードが cwd に worktree パスを
  載せるか否かを、リポジトリ内の記録(action_log は cwd を保存しない)からは確定できなかった。
  公式フック入力仕様上 PreToolUse は cwd を含むが、実機ログでの裏取りは未。二段構えにより
  「載る場合は封じ込めが効く / 載らない場合はフォールバックで誤ブロックしない」ため、この不確実性が
  あっても安全側に倒れる設計になっている(効力の上限がこの仮定に依存する点は明示する)。
