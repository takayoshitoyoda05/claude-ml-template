# 検索ログ

2026-08-04。WebSearch(arXiv MCP 未接続)。4領域を並列調査。
各領域の実行クエリと WebFetch で本文確認した URL を記録する。

## 領域1: 計画の堅牢化
1. `LLM agent plan verification formal verification of plans arXiv`
2. `LLM ambiguity resolution clarifying questions specification coding agent arXiv`
3. `LLM planner PDDL translation validate plan VAL solver arXiv`
4. `LLM-Modulo framework external verifiers plan critique Kambhampati arXiv`
5. `world model simulation LLM agent plan verification simulated rollout WebDreamer arXiv`
6. `AdaPlanner plan refinement plan repair LLM agent execution feedback arXiv`
7. `SWE-Search Monte Carlo Tree Search software engineering agents arXiv`
8. `Aider architect mode separate planning model editor model implementation pattern`
9. `LLM task decomposition verification subgoal correctness checking arXiv`
10. `OpenHands planning agent plan critic implementation SWE-bench`
11. `LLM calibration uncertainty estimation agent planning confidence abstain arXiv`
12. `PlanCritic plan feedback genetic algorithm constraint arXiv`

## 領域2: レビューの堅牢化
1. `LLM-as-judge reliability bias mitigation code review rubric pairwise arXiv`
2. `chain-of-verification reduce hallucination LLM arXiv Dhuliawala`
3. `CriticGPT OpenAI critique model code bugs LLM critics arXiv`
4. `multi-agent debate code review verification refuter verify LLM review comments false positive arXiv`
5. `LLM uncertainty estimation abstention defer to human code review confidence calibration arXiv`
6. `automated PR review bot empirical study CodeRabbit Copilot code review effectiveness false positives`
7. `agent-as-a-judge evaluate agents trajectory intermediate steps arXiv`
8. `panel of LLM judges PoLL replacing single large judge Cohere arXiv 2404.18796`
9. `detect incorrect patch overfitting patch validation automated program repair LLM plausible patch correctness arXiv`
10. `LLM code review comment resolution hallucinated fix detection verify fix actually resolves issue arXiv`
11. `process reward model code generation step-level verification coding agent trajectory arXiv`
- WebFetch 本文確認: arXiv 2604.19049 / 2604.03196 / 2601.19072

## 領域3: 検証・テストオラクル
1. `metamorphic testing machine learning code test oracle problem survey`
2. `TestGen-LLM Meta automated test improvement LLM assured`
3. `CrossHair Python symbolic execution contracts verification`
4. `jaxtyping beartype runtime tensor shape checking PyTorch`
5. `automated assertion generation neural test oracle TOGA differential testing LLM-generated code`
6. `flaky test detection tool pytest nondeterminism machine learning experiments`
7. `data leakage notebooks static detection ASE 2022 leakage ML pipelines analysis`
8. `torchtest gradient check sanity checks neural network training bugs tool`
9. `CodeT code generation generated tests dual execution agreement verification`
10. `nl2postcond LLM natural language postconditions formal specifications ICSE 2024`
11. `NeuraLint static checking deep learning programs model graph rules`
12. `deal Python design by contract library CrossHair integration`
13. `machine learning experiment reproducibility checker tool determinism torch.use_deterministic_algorithms verification`

## 領域4: 業界プラクティス
1. `GitHub spec-kit spec-driven development toolkit plan review`
2. `AWS Kiro spec-driven development requirements design tasks EARS`
3. `OpenHands SWE-agent critic model verification loop agentic coding`
4. `AI code review risk scoring tiered review gates human review load`
5. `Anthropic Claude Code best practices agentic coding plan verification`
6. `Google large-scale AI code review resolving code review comments ML paper`
7. `policy-as-code OPA Open Policy Agent guardrails AI agent pipeline CI gate`
8. `Devin planning playbooks Factory droids plan review checkpoint design`
9. `shadow mode AI code review rollout evaluate agent suggestions before enforcing`
10. `"merge queue" OR "trunk-based" AI agents automated gates continuous integration best practices 2026`
- WebFetch 本文確認: github.com/github/spec-kit / openhands.dev critic blog / arXiv 2601.04171 / 2604.12147

## スクリーニングの記録
- 採用: 47件(notes/ の4ファイルに記録)
- 領域間重複: 計画遵守(arXiv 2604.12147)が領域1と領域4の両方で検出 → 1件に統合
- 調査エージェント自身が除外条件により見送った近縁項目(記録として保持):
  - OpenHands critic-32b の複数トラジェクトリ生成+選別 → 提案済み「複数生成+judge panel」と同型
  - Aider の architect/editor 分離 → 本パイプラインの planner/generator 分離と同一
