# 領域1: 計画の堅牢化(採用11件)

各項目の形式: 書誌情報 / 1行要約 / 要点 / 本パイプラインとの関係 / 確認レベル
(確認レベル: abstract_only = アブストラクトのみ, page_read = 本文ページ確認済み)

## P1. 自然言語計画の LTL モデル検査
- 書誌: Ramani, Tawosi, Alamir, Borrajo (J.P. Morgan AI Research), 2025. https://arxiv.org/abs/2510.03469
- 要約: 自然言語計画を Kripke 構造+LTL 式に変換しモデル検査器で機械検証する。
- 要点: LLM は形式表現への翻訳のみ担当し、合否はモデル検査が出す。PlanBench 簡約版で GPT-5 が F1 96.3%。
- 関係: plan-reviewer と plan_gate の間に手順順序・前提充足の形式検査レイヤを追加できる。受け入れ条件テーブルを LTL 性質の源泉にできる。既存は LLM 判定+正規表現検査のみで時相論理は未カバー。
- 確認レベル: abstract_only

## P2. LLM-Modulo(外部批評器バンク+自動再計画ループ)
- 書誌: Kambhampati et al., ICML 2024. https://arxiv.org/abs/2402.01817
- 要約: LLM は生成器に徹し、役割別の外部検証器バンクが合否と理由を返して再計画させる反復構成。
- 要点: 硬い制約・スタイル等の批評器を分離。Blocks World で15ラウンド反復により82%到達。
- 関係: 現状の spec-checklist→plan-reviewer→plan_gate は一方向。不合格理由を構造化して planner に自動差し戻す反復プロトコル化が新規要素。
- 確認レベル: abstract_only

## P3. SpecFix(要求文の曖昧性を分布計測で機械修復)
- 書誌: Jia, Morris, Ye, Sarro, Mechtaev, 2025. https://arxiv.org/abs/2505.07270
- 要約: 要求文が誘導する生成プログラムの分布の割れを曖昧性とみなし、要求文自体を修復する。
- 要点: LLM に「曖昧か」と直接聞くより一貫した編集が得られ、ベンチ全体で +4.09%。
- 関係: planner 前段で要求文から実装スケッチを k 個安価に生成し、挙動が割れた箇所を検出して受け入れ条件を修復してから計画に進む形で導入可能。
- 確認レベル: page_read

## P4. EVPI による明確化質問の価値定量化(SAGE-Agent)
- 書誌: Suri et al., 2025. https://arxiv.org/abs/2511.08798
- 要約: 各明確化質問の価値を Expected Value of Perfect Information で定量化し「聞くべき質問だけ」を選ぶ。
- 要点: 曖昧タスクでカバレッジ +7〜39%、冗長質問を削減。
- 関係: design-interview / planner の未確定事項リストに「その質問で計画のどの分岐が消えるか」の優先度を付け、上位 n 問だけ人間に出す選別として導入可能。
- 確認レベル: page_read

## P5. Ambig-SWE(過少仕様の入口判別ゲート)
- 書誌: Vijayvargiya, Zhou, Yerukola, Sap, Neubig, 2025(ICLR 2026 採択). https://arxiv.org/abs/2502.13069
- 要約: 「仕様が不完全だと認識→質問→回答を反映」の3段階を評価するベンチと知見。
- 要点: 対話ありで非対話比最大 +74%。ただし SOTA でも明確/曖昧の判別自体が弱い。
- 関係: 手順0に「この要件は underspecified か」の判別を置き、曖昧判定時のみ design-interview を強制発火するトリガに使える。判別プロンプトの設計知見あり。
- 確認レベル: page_read

## P6. WebDreamer(世界モデルによる計画の順方向シミュレーション)
- 書誌: Gu et al., 2024. https://arxiv.org/abs/2411.06559
- 要約: 各ステップの「実行後に何が起きるか」を LLM に自然言語でシミュレートさせ整合を検査する。
- 要点: 木探索と同等の性能を 4-5 倍の効率で達成。
- 関係: 計画の各ステップに「実行後の状態予測」を付記させ、前ステップの出力が次の入力を満たすか(データ依存の破れ)を plan-reviewer が検査する形で導入可能。プレモーテム(失敗列挙)と直交。
- 確認レベル: abstract_only

## P7. SWE-Search(MCTS による計画探索+途中剪定)
- 書誌: Antoniades et al., 2024. https://arxiv.org/abs/2410.20285
- 要約: リポジトリレベル SWE タスクに MCTS+ハイブリッド価値関数を適用し途中評価で枝刈り。
- 要点: SWE-bench で5モデル平均 +23% 相対改善。探索深さで性能がスケール。
- 関係: L 規模限定で planner 内部の複数案並列生成を「価値関数付き逐次展開・バックトラック」に置換するオプション。独立並列+judge とは探索構造が異なる。コスト大。
- 確認レベル: abstract_only

## P8. AdaPlanner(in-plan / out-of-plan の二層プラン修復)
- 書誌: Sun, Zhuang, Kong, Dai, Zhang, NeurIPS 2023. https://arxiv.org/abs/2305.16653
- 要約: 実行時の逸脱を「計画の枠内で吸収可能」と「計画全体の改訂が必要」に分類し後者のみ再計画。
- 要点: ALFWorld / MiniWoB++ で SOTA 超え。
- 関係: 承認後に計画が崩れたときの機械的な復帰規約(in-plan なら generator 続行、out-of-plan なら plan_gate 再検査)として明文化できる。既存機構は計画作成時の検査のみ。
- 確認レベル: abstract_only

## P9. L-ICL(最初の制約違反の局所化+最小修正例の注入)
- 書誌: Kumar, Cohen, 2026. https://arxiv.org/abs/2602.00276
- 要約: 計画の「最初の制約違反」を特定し、その箇所の最小修正例だけを注入して再計画させる。
- 要点: gridworld で妥当計画率 89%(ベースライン 59%)。
- 関係: plan-reviewer / plan_gate 不合格時の差し戻しを「全文」ではなく「違反した最初の条項+修正済みミニ例」にする差し戻しフォーマットとして採用可能。
- 確認レベル: page_read

## P10. 計画遵守の計測と周期的リマインド(領域4と重複検出 → 統合)
- 書誌: Liu, Dehghan, Ganhotra, Hirzel, Jabbarvand, 2026. https://arxiv.org/abs/2604.12147
- 要約: 約1.7万のエージェント軌跡分析。明示計画の定期リマインドが遵守率と成功率を上げる。
- 要点: 計画がないと内在化した不完全な手順にフォールバックする。悪い計画は無計画より悪い。
- 関係: 承認済み計画を generator 実行中に定期再注入し、完了時に「計画ステップごとの実施証跡」対応表を要求して逸脱を機械検出する。既存は事前審査のみで「承認後に計画どおり実行されたか」は空白。
- 確認レベル: page_read

## P11. PlanCritic(人間フィードバックの制約化+形式検証)
- 書誌: Burns, Hughes, Sycara (CMU), 2024. https://arxiv.org/abs/2412.00300
- 要約: 自然言語の選好を計画制約に変換し、遺伝的アルゴリズム+形式検証器で充足を機械判定。
- 要点: 人間フィードバックをオンラインで機械検査可能な制約に変換するニューロシンボリック構成。
- 関係: 手順4の人間差し戻しコメントを「機械検査可能な制約」に変換して plan_gate の検査項目へ蓄積する変換器として応用可能。plan_gate の制約は現状静的定義のみ。
- 確認レベル: abstract_only

## P12. PDDL 化+VAL 検証(依存グラフの充足検査)
- 書誌: Guan, Valmeekam, Sreedharan, Kambhampati, NeurIPS 2023. https://arxiv.org/abs/2305.14909
- 要約: LLM で PDDL 世界モデルを構築し、外部ソルバ+VAL で前提条件・目標充足を機械検証。
- 要点: LLM 単体の計画より高信頼。エラーは差し戻して反復修復。
- 関係: ML 実験計画の依存関係(データ生成→学習→評価)をミニ DAG として書かせ、「各ステップの前提成果物が先行ステップで生成されるか」を plan_gate で検査する。仮定の裏取り(提案済み)とは検査対象が異なる(計画構造 vs 事実)。
- 確認レベル: abstract_only
