# 研究データの漏洩防止 発散 v1

日付: 2026-08-21
文脈: テンプレートの研究用プロジェクト化にあたり、データが git・外部サービス
(LLM API・Codex・MLflow・クラウド)・ログ類へ漏れる経路を塞ぎたい。
姉妹メモ: ideas/20260821-data-maintainability-v1.md(保全・来歴の軸)。
絞り込みは design-interview で行う。

## 漏洩経路の棚卸し(現状)
- git コミット: .gitignore 頼み(パスベースのみ)。notebook 出力・fixture・
  evidence 内の diff/テスト出力は無検査
- LLM API: エージェントが data/ を Read すると内容が API に渡る。guard_scope は
  書き込みのみブロックで、読み取りは無防備
- Codex cross-review / claude-security: diff をそのまま外部送信
- MLflow / クラウド: トラッキング先・artifacts に制約なし
- logs/runs・transcript・report_gen evidence: _mask.py は API キー等のみマスク。
  データ識別子は素通し

## 発散した案

### G1: git 混入防止系
1. 内容ベース pre-commit 検知(拡張子・サイズ・エントロピー・PII パターン。
   パス移し替え事故も捕まえる)
2. nbstripout 必須化+テストは必ず合成データ+ログは shape/hash/統計量のみ
   (python-standards に規約追加)
3. git 履歴全体の定期漏洩監査+除去手順(BFG / filter-repo)の事前文書化

### G2: 外部送信ゲート系
4. 外部送出前の diff 検疫: cross-review / claude-security 起動前にデータ
   パターンをスキャンし、検知時は送信停止または該当ハンク除外
5. guard_bash の egress 制御: data/ パス × アップロード系コマンド
   (curl・scp・rclone・gh・aws)の組み合わせブロック
6. data_egress_gate フック(requirements/session_monitor と同じ様式):
   「data/ を読んで外部コマンドへパイプ」する Bash をブロック
7. MLflow ローカル限定既定(file:./mlruns)+リモート URI・データ形式
   artifacts への警告(mlflow-log スキル側)

### G3: マスキング・sanitize 系
8. データ識別子辞書(患者ID・サンプルID・座標等の正規表現。プロジェクトごと
   定義)によるスキャナ(gitleaks のデータ版)
9. _mask.py の辞書拡張: 秘密語に加えデータ識別子をマスク
   (logs・transcript・evidence に自動で効く)
10. report_gen の sanitize パス: evidence(diff.patch・test-output.txt)の
    データ行検知→伏せ字

### G4: 構造的隔離系
11. **data/ の読み取り遮断**(CLAUDE_DATA_NO_READ=1): Read/cat 等による
    data/ 読み取り自体をブロック。**LLM API へ内容が渡る経路を構造的に
    塞げる唯一の案**
12. 持ち出し規制の invariants 化: 「外部に出てよいのは集計値・図・ハッシュのみ。
    個票・生データ禁止」を invariants.md に明文化(全レベル有効)
13. クリーンルーム運用: データ処理はネットワーク遮断環境で実行する手順書
14. data/ の暗号化保管(age / git-crypt。誤 push しても暗号文)

### G5: 運用チェック系
15. 公開・共有前チェックリスト(git 履歴・notebook 出力・fixtures・ログ・
    レポート・MLflow)を paper-writing / handoff に追加

## 軽い評価

| グループ | 新規性 | 実現性 | インパクト | 検証しやすさ |
|---|---|---|---|---|
| G1 git 混入防止 | 中 | 高 | 高(公開リポジトリなら最重要) | 高 |
| G2 外部送信ゲート | 高 | 高(フック前例あり) | 高(Codex/スキャン経路は現在無防備) | 高 |
| G3 マスキング拡張 | 中 | 高(_mask.py の延長) | 中(辞書の網羅性に依存) | 中 |
| G4 構造的隔離 | 高 | 11・12は高/13・14は中 | 最高(API 経路は G4-11 のみが塞ぐ) | 高 |
| G5 チェックリスト | 低 | 極高 | 低〜中 | 高 |

## 重要な非対称
G1〜G3・G5 は「写り込み・持ち出しの検知と抑止」。エージェント自身が data/ を
読んだ時点で内容が LLM API に渡る経路だけは G4-11(読み取り遮断)でしか
塞げない。機密度の高いデータなら G4-11+G4-12 が土台、その上に G1・G2 を
重ねる構造が素直。

## 次のステップ
方向性を選んだら design-interview で仕様を固める(データ識別子辞書の定義方法・
遮断の粒度(raw のみ/全 data/)・許可リスト(集計スクリプトの出力は可、等)・
既存 guard/_mask との責務分担)。
