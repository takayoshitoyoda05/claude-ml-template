# claude-ml-template ハーネス改修まとめ（2026-08）

ハーネス研究サーベイに基づく改修。Phase 0〜3 まで実装完了。

**判断基準**: 堅牢さ維持 × トークン削減 × 研究用途

---

## Phase 0 — 測る基盤

### ① ペア評価の回帰ベンチ（CI）
- 自作タスク 10〜20 問。スキルあり/なしのペア実行
- PR ごとに成功率とトークン消費を計測
- 根拠: ハーネス差で精度に約6倍の開き（arXiv:2606.25447 が引用する Lee et al. 2026）／測定なしの進化は fix-one-break-one のトレッドミル化（HarnessX, arXiv:2606.14249）
- 評価プロトコル参考: SkillTester (arXiv:2603.28815), CTA (arXiv:2605.11946)

### ② トレース保存規約
- `.harness/runs/<id>/` に trace / score / diff
- retrospective の出力先をここに固定
- 根拠: 生の実行履歴が後段最適化の材料（Meta-Harness, arXiv:2603.28052）

## Phase 1 — 削る

### ③ スキル棚卸し
- ①の結果で効果の出ないスキルを削除
- 根拠: 自己生成スキルは平均で効果なし（SkillsBench, arXiv:2602.12670）

### ④ プロファイル化
- `research`（フル装備）/ `light`（pre-mortem・leakage-check・invariants のみ）
- skills frontmatter に profile タグ＋適用条件を必須化。hook でロード対象をフィルタ
- 根拠: コンテキスト不一致でスキル注入は性能低下（SWE-Skills-Bench, arXiv:2603.15401）／型付きプリミティブ合成（HarnessX）

## Phase 2 — 構造を足す

### ⑤ Digester 段
- Planner 前段に軽量モデルの圧縮サブエージェントを1段
- 根拠: AEGIS の Digester→Planner→Evolver→Critic 構成（HarnessX）

### ⑥ 検証済み状態の外部化（MEA 化）
- タスク状態をコンテキスト外のファイルに保持
- 環境から独立検証された事実のみで状態更新
- Evaluator = read-only 監査役（状態更新権限を保有）／Executor = 毎回新品コンテキスト
- 根拠: LongHorizon-Harness (arXiv:2608.01964)。WeaveBench 51.8%→80.7%（Qwen 3.7-Plus）等

## Phase 3 — 自動化ループ

### ⑦ invariants.md 自動追記＋統合判定
- retrospective 出力を hook で invariants.md に反映
- ゲート: 失敗のクラスタ化 → 高頻度パターンのみ最小編集 → held-in / held-out 両方で回帰テスト
- 無条件追記は禁止（肥大化は④と矛盾）
- 根拠: 恒久修正原則（Hashimoto "My AI Adoption Journey" 2026-02）＋ Self-Harness (arXiv:2606.09498)

### ⑧ トレース→スキル蒸留
- 解決トレースから頻出失敗・有効パターンを構造化スキルへ蒸留
- 採用条件: ①のペア評価で有意にプラスの場合のみ
- 根拠: Socratic-SWE (arXiv:2606.07412)

## 常時 — セキュリティ

### ⑨ security-review の対象拡張
- 外部由来の skill / MCP 定義自体を検査対象に
- 根拠: skills チャネル経由 16.0%・隠し Unicode 25.5% の攻撃成功率（arXiv:2608.16393）

---

## やらないこと

| 項目 | 理由 |
|---|---|
| 自前の文脈圧縮 | Claude Code 本体に5層コンパクションあり（arXiv:2604.14228） |
| RL 共進化（EvoTrainer / Polar 系） | 計算資源に対し過剰 |
| 本格的自動進化（Meta-Harness 級） | metric masking を①なしで検出不能 |

## 運用ルール

- スキル・invariants の追加は①のペア評価を通過したもののみ
- テンプレート変更 PR は成功率＋トークン消費の両指標を必須添付
- 蒸留スキルも自作扱い（＝効果なし前提で検証してから採用）

## 主要参考文献

**サーベイ**
- From Question Answering to Task Completion — arXiv:2606.20683
- Agent Harness for LLM Agents: A Survey — Preprints 202604.0428
- Code as Agent Harness — arXiv:2605.18747

**ランタイム・実行制御**
- LongHorizon-Harness — arXiv:2608.01964（Claude Code 統合あり）
- Dive into Claude Code — arXiv:2604.14228

**自動最適化・自己進化**
- Meta-Harness — arXiv:2603.28052
- HarnessX — arXiv:2606.14249
- Self-Harness — arXiv:2606.09498
- Continual Harness — arXiv:2605.09998

**スキル評価**
- SkillsBench — arXiv:2602.12670
- SWE-Skills-Bench — arXiv:2603.15401
- SkillTester — arXiv:2603.28815
- CTA — arXiv:2605.11946
- Socratic-SWE — arXiv:2606.07412

**セキュリティ**
- DeepSeek Harness インジェクション評価 — arXiv:2608.16393

**産業一次情報**
- Mitchell Hashimoto "My AI Adoption Journey"（2026-02）
- OpenAI "Harness engineering"（2026-02）
- Anthropic "Harness design for long-running application development"（2026-03）
