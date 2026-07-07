---
name: property-test
description: 関数の入力パターンが多い・境界値が複雑なとき、ランダム入力で不変条件を網羅的に検証したいとき、または「プロパティテストして」「hypothesisでテストして」と言われたときに必ず使う。
---

# プロパティベーステスト

tdd(1つの振る舞いを具体的な入力でテストする)とは異なり、
ランダムに生成した大量の入力で「常に成り立つべき性質(不変条件)」を検証する。
入力の組み合わせが多い前処理・データ変換・バッグ処理に特に有効。

## いつ使うか
- 入力の型やshapeのバリエーションが多い関数(前処理、正規化、データ変換)
- 往復の正しさが求められる処理(encode→decode、serialize→deserialize)
- 冪等性が期待される処理(2回適用しても結果が変わらないべき操作)
- tdd の具体的な入力値だけでは見逃す境界値バグを探したいとき

## 進め方
1. 作業スコープ直下に CONTEXT.md があれば先に読む。
2. 対象の関数を特定する。
3. その関数の「有効な入力」をモデル化する。
   - 型: int, float, str, list, ndarray, tensor 等
   - 値域: 正の数のみ、0を含むか、NaN/Inf を含むか
   - shape: 固定か可変か、空を許すか
4. 以下の不変条件から該当するものを選び、テストを書く。

## 代表的な不変条件
| 不変条件 | 説明 | 例 |
|----------|------|-----|
| 往復(roundtrip) | encode→decode で元に戻る | `decode(encode(x)) == x` |
| 冪等性 | 2回適用しても結果が同じ | `f(f(x)) == f(x)` |
| 出力の型・shape保存 | 入力と出力の型やshapeが対応する | `output.shape[0] == input.shape[0]` |
| 単調性 | 入力が増えたら出力も増える(または減らない) | `x <= y → f(x) <= f(y)` |
| 値域の制約 | 出力が常に有効な範囲に収まる | `0 <= normalize(x) <= 1` |
| ゼロ・空入力 | 空リスト、ゼロ行列、空文字列でクラッシュしない | `f([]) → 例外ではなく空の結果` |

## テストの書き方(Hypothesis ライブラリ)
```python
from hypothesis import given, strategies as st

@given(st.lists(st.floats(allow_nan=False, allow_infinity=False), min_size=1))
def test_normalize_output_range(values):
    result = normalize(values)
    assert all(0 <= v <= 1 for v in result)
```

Hypothesis がインストールされていなければ `uv add --dev hypothesis` で追加する。

## テストの保存先
作業スコープ配下の tests/ に保存する(tdd と同じ場所)。
ファイル名は `test_property_<対象モジュール名>.py` とする。

## 注意
- tdd スキルとの使い分け: tdd は「この入力→この出力」の具体的な振る舞いを
  テストする。property-test は「どんな入力でもこの性質が成り立つ」を
  テストする。両方あるのが理想で、どちらかの代替ではない。
- 生成されたテストが既存のバグを「正解」として固定しないよう注意する。
  不変条件が怪しい場合はユーザーに確認する。
