# claude-ml-template

Claude Code用の Planner / Generator / Evaluator 3分離パターンのテンプレート。

---

## 1. 全体像
ユーザー(あなた)
↓ 要件を伝える
Planner (Opus)   … 調査して実装計画を書く。コードは書かない
↓ 計画をユーザーがレビュー・承認
Generator (Sonnet) … 計画に沿って実装、コミット
↓
Evaluator (Sonnet) … 実際にテスト/評価スクリプトを実行して数値で判定
↓
PASS → 完了
NEEDS_REVISION → Generatorに差し戻し(最大3周)
FAIL(3回目)→ Plannerからやり直しを提案
3体に分けている理由は、1体に全部やらせると「計画・実装・自己採点」を同じ視点で行ってしまい、自分の間違いに気づけないため。役割ごとに視点を変えることで問題を検出しやすくする設計。

---

## 2. 各エージェントの役割と設定

| エージェント | ファイル | model | 持てるtools | 役割 |
|---|---|---|---|---|
| planner | `.claude/agents/planner.md` | `opus` | Read, Grep, Glob, Bash | 調査・計画立案のみ。コード変更はしない |
| generator | `.claude/agents/generator.md` | `sonnet` | Read, Write, Edit, Grep, Glob, Bash | 計画に沿って実装。`permissionMode: acceptEdits`で編集を自動承認 |
| evaluator | `.claude/agents/evaluator.md` | `sonnet` | Read, Grep, Glob, Bash | レビュー+評価コマンド実行。コードは書かない |

### なぜこのモデル配分か
- Planner: 設計判断・原因分析など深い推論が必要 → Opus
- Generator: 定型的な実装作業、速度とコストのバランス重視 → Sonnet
- Evaluator: 読解と実行確認が中心、Opusほどの推論力は不要 → Sonnet
- 全部Haikuにすると計画品質が落ちる/全部Opusにするとコストが3〜5倍に跳ねるので、役割ごとに使い分けるのが基本方針

### permissionMode について
Claude Codeがファイル編集やコマンド実行の前にユーザー確認を挟むかどうかの設定。

| 値 | 動作 |
|---|---|
| `default`(未指定) | 破壊的操作は都度確認 |
| `acceptEdits` | ファイル編集だけ自動承認、それ以外は確認あり |
| `bypassPermissions` | ほぼ全操作を確認なしで実行(非推奨) |
| `plan` | 読み取り専用、変更は一切行わない |

Generatorだけ`acceptEdits`にしているのは、計画通りに黙々と実装させたいため。その代わり最終チェックはEvaluatorが必ず行う設計になっている。

---

### スコープ制約(複数プロジェクト同居リポジトリ向け)
Research_materials のように1つのリポジトリに複数プロジェクトや論文・スライドが
同居している場合の暴走防止として、全エージェントに以下の制約を持たせている。

- 作業は指定された作業ディレクトリ配下に限定する。指定がなければ着手前に確認する。
- papers/ slides/ literature/ など他ディレクトリは読み書きしない。
- generator の `git add`、evaluator の `git diff` は作業ディレクトリにパスを限定する
  (例: `git add projects/Deep_MIL/`、`git diff -- projects/Deep_MIL/`)。

これにより、Gitのルートをプロジェクト単位に分割しなくても、
リポジトリ全体を1つのまま安全に運用できる。

## 3. 記事「よくある5つの失敗」への対策一覧

| # | 失敗内容 | 対策の実装場所 | 内容 |
|---|---|---|---|
| 1 | 指示が曖昧でサブエージェントが迷走 | `generator.md` 作業手順 | 実装前に「対象ファイルパス・使用ライブラリ・入出力の型/shape・制約条件」を確認するステップを追加 |
| 2 | 計画が細かすぎてGeneratorの自由度がない | `planner.md` 制約 | 「技術的詳細を詰めすぎない。実装の判断余地はGeneratorに残す」と明記 |
| 3 | Evaluatorが甘い | `evaluator.md` | PASS/FAIL二値判定のチェックリスト形式、「一度出した指摘を取り下げない」「ファイルパス+行番号で根拠を示す」 |
| 4 | フィードバックループが無限に回る | `ml-pipeline.md` | 最大3イテレーションで打ち切り、収束しなければPlannerからやり直し |
| 5 | モデル選択ミス | 各agent.md の `model` | Planner=opus, Generator=sonnet, Evaluator=sonnet |

---

## 4. 使い方(新プロジェクトで導入)

### 4-1. プロジェクトのルートで展開

PowerShell:Invoke-WebRequest -Uri "https://raw.githubusercontent.com/takayoshitoyoda05/claude-ml-template/main/claude-init.ps1" -OutFile "claude-init.ps1"
.\claude-init.ps1

bash(WSL/Linux/Git Bash):Invoke-WebRequest -Uri "https://raw.githubusercontent.com/takayoshitoyoda05/claude-ml-template/main/claude-init.ps1" -OutFile "claude-init.ps1"
.\claude-init.ps1

展開されると .claude/agents/, .claude/commands/, CLAUDE.md が作られる。

### 4-2. 動作確認
claude
セッション内で:
/agents
planner / generator / evaluator の3体が表示されればOK。

### 4-3. 実行
/ml-pipeline <作業ディレクトリ> <やりたいこと>

作業ディレクトリを冒頭で指定することで、その配下だけを対象に3エージェントが動く。
複数プロジェクトが1つのリポジトリに同居している場合でも、他プロジェクトや
papers/ slides/ などを誤って触らないようにするための仕組み。

例:
/ml-pipeline projects/Deep_MIL attention可視化のバグを直したい。
outputs/に出る画像が真っ黒になる問題を解消したい

作業ディレクトリを指定しなかった場合、エージェントは着手前に
「どのプロジェクトディレクトリで作業するか」を確認する。

### 4-4. 個別に呼び出したい場合
@planner この関数の設計を考えて
@generator この計画通りに実装して
@evaluator 直近の変更をレビューして

---

## 5. 運用サイクル(育て方)

1. 実プロジェクトで /ml-pipeline を使う
2. 「Plannerの指示がずれていた」「Generatorが暴走した」「Evaluatorが甘かった」など気づきが出る
3. 気づきを このテンプレートリポジトリ側 の該当 .md に反映して commit・push
4. 次の新規プロジェクトでは改善版がすぐ使える

プロジェクト固有の調整(そのプロジェクトだけの特殊事情)は、展開後のローカル .claude/ だけを直接編集し、テンプレート側には戻さない。テンプレートに戻すのは「他のプロジェクトでも共通して使える改善」のみ、と切り分けるのがコツ。

---

## 6. コスト感覚

- 3エージェント構成は単一実行より確実にトークン消費が増える(数倍〜十数倍になり得る)
- 向いているタスク: 結果の正しさが重要、複数バージョン間のdiscrepancy解消、実験の再現性がかかった変更
- 向いていないタスク: 単発のリファクタ、文献確認、ドキュメント編集など軽い調査タスク → メインセッションだけで十分

判断に迷ったら「これが間違っていたら困るか?」を基準にする。困るなら3エージェント、困らないなら単発でOK。

---

## 7. トラブルシューティング

### 文字化け
原因: エディタ(nvim)のファイルエンコーディング設定がUTF-8になっていない。

対策:
- 編集前に必ず :set fileencoding=utf-8 と :set fileformat=unix を実行
- 既に化けたファイルを開いても正しく直らないので、一度PowerShellの Out-File -Encoding utf8 または [System.IO.File]::WriteAllText(...) で書き直す方が確実
- .sh ファイルはBOM付きUTF-8だとシェバン(#!/bin/bash)が壊れて実行できなくなるので、BOMなしUTF-8で保存する

### PowerShellで mkdir -p a b c のようなbash構文がエラーになる
PowerShellの mkdir は複数パスを一度に取れない。代わりに:
New-Item -ItemType Directory -Path "a", "b", "c" -Force

### git pushでブランチ名がmasterのままになる
git branch -M main
で明示的にmainへ変更してからpush。

---

## 8. ファイル一覧
claude-ml-template/
├── .claude/
│   ├── agents/
│   │   ├── planner.md      Opus / 計画立案専任
│   │   ├── generator.md    Sonnet / 実装専任、acceptEdits
│   │   └── evaluator.md    Sonnet / レビュー・数値検証専任
│   └── commands/
│       └── ml-pipeline.md  3エージェントを繋ぐフロー制御
├── templates/
│   └── CLAUDE.md.template  プロジェクト展開時に埋められる雛形
├── claude-init.sh          Linux/WSL/Git Bash用セットアップ
├── claude-init.ps1         Windows PowerShell用セットアップ
└── README.md

