"""session_monitor.py と checkpoint_before_compact.py 追記分の受け入れテスト。

`tests/test_requirements_gate.py` に倣い、フックを import せず subprocess で
CLI 起動する(実運用の Stop/PreCompact フックと同じ経路で検証するため)。

フック本体・checkpoint_before_compact.py への追記・staging スクリプトは
ユーザーが `! uv run python _staging_session_monitor.py` で適用するまで
存在しないため、未適用の間は関連ケースを個別に skip する。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = _ROOT / ".claude" / "hooks" / "session_monitor.py"
CHECKPOINT_HOOK_PATH = _ROOT / ".claude" / "hooks" / "checkpoint_before_compact.py"
STAGING_PATH = _ROOT / "_staging_session_monitor.py"
_SUBPROCESS_TIMEOUT = 30

# session_monitor.py 本体が無い間は PC-1〜PC-10 が全て skip になる
# (未適用時は「全件skip」であることが検出力の証明になる)
pytestmark = pytest.mark.skipif(
    not HOOK_PATH.exists(),
    reason="_staging_session_monitor.py 未適用(ユーザーの ! 実行待ち)",
)


def _run_monitor(
    payload_text: str, cwd: Path, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "CLAUDE_SESSION_MONITOR": "1",
    }
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=payload_text,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=_SUBPROCESS_TIMEOUT,
        env=env,
    )


def _run_checkpoint(payload_text: str, cwd: Path) -> subprocess.CompletedProcess:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
    }
    return subprocess.run(
        [sys.executable, str(CHECKPOINT_HOOK_PATH)],
        input=payload_text,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=_SUBPROCESS_TIMEOUT,
        env=env,
    )


def _assistant_line(
    input_tokens: int, cache_read: int = 0, cache_creation: int = 0
) -> str:
    entry = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "usage": {
                "input_tokens": input_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_creation,
            },
        },
    }
    return json.dumps(entry, ensure_ascii=False)


def _transcript(
    tmp_path: Path, lines: list[str], name: str = "transcript.jsonl"
) -> Path:
    path = tmp_path / name
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def _payload(
    transcript_path: str, session_id: str = "sess-1", stop_hook_active: bool = False
) -> str:
    return json.dumps(
        {
            "transcript_path": transcript_path,
            "session_id": session_id,
            "stop_hook_active": stop_hook_active,
        },
        ensure_ascii=False,
    )


def _output(result: subprocess.CompletedProcess) -> str:
    # 出力先が systemMessage(stdout の JSON)か stderr かの実装判断に
    # 依存しないよう、判定は常に stdout+stderr の連結文字列に対して行う
    return result.stdout + result.stderr


# --- PC-1: gate_off ---


def test_gate_off_no_warning(tmp_path: Path) -> None:
    transcript = _transcript(tmp_path, [_assistant_line(200_000)])
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=_payload(str(transcript)),
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=_SUBPROCESS_TIMEOUT,
        env={
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
            # CLAUDE_SESSION_MONITOR を意図的に付けない(未設定 == gate off)
        },
    )
    assert result.returncode == 0
    assert "handoff" not in _output(result)


def test_gate_zero_no_warning(tmp_path: Path) -> None:
    transcript = _transcript(tmp_path, [_assistant_line(200_000)])
    result = _run_monitor(
        _payload(str(transcript)), tmp_path, {"CLAUDE_SESSION_MONITOR": "0"}
    )
    assert result.returncode == 0
    assert "handoff" not in _output(result)


# --- PC-2: below_warn ---


def test_below_warn_threshold_silent(tmp_path: Path) -> None:
    transcript = _transcript(tmp_path, [_assistant_line(100_000)])
    result = _run_monitor(_payload(str(transcript)), tmp_path)
    assert result.returncode == 0
    assert "handoff" not in _output(result)


# --- PC-3: warn_level(境界値 150,000 ちょうど) ---


def test_warn_level_at_boundary_warns(tmp_path: Path) -> None:
    transcript = _transcript(tmp_path, [_assistant_line(150_000)])
    result = _run_monitor(_payload(str(transcript), session_id="sess-warn"), tmp_path)
    assert result.returncode == 0
    assert "handoff" in _output(result)


def test_warn_level_multiple_assistant_lines_uses_last(tmp_path: Path) -> None:
    # usage を持つ assistant 行が複数 → usage を持たない行が末尾に混在 →
    # message.usage が欠けた行、の順で並べても「最後に見つかった usage」で判定される
    lines = [
        _assistant_line(50_000),
        _assistant_line(150_000),
        json.dumps(
            {"type": "assistant", "message": {"role": "assistant"}}, ensure_ascii=False
        ),
        json.dumps({"type": "user", "message": {"role": "user"}}, ensure_ascii=False),
    ]
    transcript = _transcript(tmp_path, lines)
    result = _run_monitor(
        _payload(str(transcript), session_id="sess-warn-multi"), tmp_path
    )
    assert result.returncode == 0
    assert "handoff" in _output(result)


# --- PC-4: high_level(境界値 180,000 ちょうど) ---


def test_high_level_at_boundary_warns_with_high_word(tmp_path: Path) -> None:
    transcript = _transcript(tmp_path, [_assistant_line(180_000)])
    result = _run_monitor(_payload(str(transcript), session_id="sess-high"), tmp_path)
    assert result.returncode == 0
    output = _output(result)
    assert "handoff" in output
    assert "high" in output


# --- PC-5: dedup_silent(前回警告時から10%未満の増加) ---


def test_dedup_silent_below_ten_percent(tmp_path: Path) -> None:
    session_id = "sess-dedup-silent"
    transcript1 = _transcript(tmp_path, [_assistant_line(150_000)], "t1.jsonl")
    first = _run_monitor(_payload(str(transcript1), session_id=session_id), tmp_path)
    assert "handoff" in _output(first)

    # 150,000 -> 160,000 は +6.7% で 10% 未満 → 再警告しない
    transcript2 = _transcript(tmp_path, [_assistant_line(160_000)], "t2.jsonl")
    second = _run_monitor(_payload(str(transcript2), session_id=session_id), tmp_path)
    assert second.returncode == 0
    assert "handoff" not in _output(second)


# --- PC-6: dedup_rewarns(前回警告時から10%以上の増加) ---


def test_dedup_rewarns_above_ten_percent(tmp_path: Path) -> None:
    session_id = "sess-dedup-rewarn"
    transcript1 = _transcript(tmp_path, [_assistant_line(150_000)], "t1.jsonl")
    first = _run_monitor(_payload(str(transcript1), session_id=session_id), tmp_path)
    assert "handoff" in _output(first)

    # 150,000 -> 170,000 は +13.3% で 10% 以上 → 再警告する
    transcript2 = _transcript(tmp_path, [_assistant_line(170_000)], "t2.jsonl")
    second = _run_monitor(_payload(str(transcript2), session_id=session_id), tmp_path)
    assert second.returncode == 0
    assert "handoff" in _output(second)


# --- PC-7: compact_count ---


def test_compact_count_warns_once_then_silent(tmp_path: Path) -> None:
    session_id = "sess-compact"
    state_dir = tmp_path / ".claude" / "checkpoints"
    state_dir.mkdir(parents=True)
    state_path = state_dir / "session_monitor_state.json"
    state_path.write_text(
        json.dumps({session_id: {"compact_count": 2}}), encoding="utf-8"
    )
    transcript = _transcript(tmp_path, [_assistant_line(10_000)])

    first = _run_monitor(_payload(str(transcript), session_id=session_id), tmp_path)
    assert first.returncode == 0
    assert "handoff" in _output(first)

    second = _run_monitor(_payload(str(transcript), session_id=session_id), tmp_path)
    assert second.returncode == 0
    assert "handoff" not in _output(second)

    third = _run_monitor(_payload(str(transcript), session_id=session_id), tmp_path)
    assert third.returncode == 0
    assert "handoff" not in _output(third)


# --- PC-8: fail_open ---


def test_fail_open_missing_transcript_path(tmp_path: Path) -> None:
    payload = json.dumps(
        {"transcript_path": "", "session_id": "sess-missing"}, ensure_ascii=False
    )
    result = _run_monitor(payload, tmp_path)
    assert result.returncode == 0
    assert "handoff" not in _output(result)


def test_fail_open_unreadable_transcript_path(tmp_path: Path) -> None:
    payload = json.dumps(
        {
            "transcript_path": str(tmp_path / "does-not-exist.jsonl"),
            "session_id": "sess-unreadable",
        },
        ensure_ascii=False,
    )
    result = _run_monitor(payload, tmp_path)
    assert result.returncode == 0
    assert "handoff" not in _output(result)


def test_fail_open_no_usage_key(tmp_path: Path) -> None:
    lines = [
        json.dumps(
            {"type": "assistant", "message": {"role": "assistant"}}, ensure_ascii=False
        )
    ]
    transcript = _transcript(tmp_path, lines)
    result = _run_monitor(
        _payload(str(transcript), session_id="sess-no-usage"), tmp_path
    )
    assert result.returncode == 0
    assert "handoff" not in _output(result)


def test_fail_open_empty_jsonl(tmp_path: Path) -> None:
    transcript = _transcript(tmp_path, [])
    result = _run_monitor(_payload(str(transcript), session_id="sess-empty"), tmp_path)
    assert result.returncode == 0
    assert "handoff" not in _output(result)


# --- PC-9: threshold_env ---


def test_threshold_env_override(tmp_path: Path) -> None:
    transcript = _transcript(tmp_path, [_assistant_line(1_500)])
    result = _run_monitor(
        _payload(str(transcript), session_id="sess-threshold-env"),
        tmp_path,
        {"CLAUDE_MONITOR_WARN_TOKENS": "1000", "CLAUDE_MONITOR_HIGH_TOKENS": "2000"},
    )
    assert result.returncode == 0
    output = _output(result)
    assert "handoff" in output
    assert "high" not in output


# --- PC-10: never_blocks ---


def test_never_blocks_malformed_json_stdin(tmp_path: Path) -> None:
    result = _run_monitor("これはJSONではない", tmp_path)
    assert result.returncode == 0


def test_never_blocks_empty_stdin(tmp_path: Path) -> None:
    result = _run_monitor("", tmp_path)
    assert result.returncode == 0


def test_never_blocks_usage_as_string(tmp_path: Path) -> None:
    lines = [
        json.dumps(
            {
                "type": "assistant",
                "message": {"role": "assistant", "usage": "not-a-dict"},
            },
            ensure_ascii=False,
        )
    ]
    transcript = _transcript(tmp_path, lines)
    result = _run_monitor(
        _payload(str(transcript), session_id="sess-usage-string"), tmp_path
    )
    assert result.returncode == 0


# --- PC-11: compact_counter_hook(checkpoint_before_compact.py 側) ---

pytestmark_compact = pytest.mark.skipif(
    not CHECKPOINT_HOOK_PATH.exists()
    or "compact_count" not in CHECKPOINT_HOOK_PATH.read_text(encoding="utf-8"),
    reason="checkpoint_before_compact.py 未適用(session_monitor 追記待ち)",
)


@pytestmark_compact
def test_compact_counter_hook_increments_on_auto(tmp_path: Path) -> None:
    session_id = "sess-auto-compact"
    payload = json.dumps(
        {"trigger": "auto", "transcript_path": "", "session_id": session_id},
        ensure_ascii=False,
    )
    first = _run_checkpoint(payload, tmp_path)
    assert first.returncode == 0
    second = _run_checkpoint(payload, tmp_path)
    assert second.returncode == 0

    state_path = tmp_path / ".claude" / "checkpoints" / "session_monitor_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state[session_id]["compact_count"] == 2


@pytestmark_compact
def test_compact_counter_hook_ignores_manual(tmp_path: Path) -> None:
    session_id = "sess-manual-compact"
    payload = json.dumps(
        {"trigger": "manual", "transcript_path": "", "session_id": session_id},
        ensure_ascii=False,
    )
    result = _run_checkpoint(payload, tmp_path)
    assert result.returncode == 0

    state_path = tmp_path / ".claude" / "checkpoints" / "session_monitor_state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state.get(session_id, {}).get("compact_count", 0) == 0


# --- PC-12: staging_idempotent(_staging_session_monitor.py 側) ---

pytestmark_staging = pytest.mark.skipif(
    not STAGING_PATH.exists(),
    reason="_staging_session_monitor.py が存在しない(未作成 or 既に削除済み)",
)


@pytestmark_staging
def test_staging_idempotent_apply_twice(tmp_path: Path) -> None:
    # 実リポジトリの保護ファイル(.claude/hooks/・.claude/settings.json)は
    # ガードで書き込めないため、--root で複製した一時ディレクトリに適用する
    root = tmp_path / "fake_root"
    hooks_dir = root / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)

    checkpoint_src = CHECKPOINT_HOOK_PATH.read_text(encoding="utf-8")
    (hooks_dir / "checkpoint_before_compact.py").write_text(
        checkpoint_src, encoding="utf-8"
    )

    settings_src = json.loads(
        (_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    (root / ".claude" / "settings.json").write_text(
        json.dumps(settings_src, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
    }
    result1 = subprocess.run(
        [sys.executable, str(STAGING_PATH), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
        env=env,
    )
    assert result1.returncode == 0

    snapshot = {
        p: p.read_bytes()
        for p in [
            hooks_dir / "session_monitor.py",
            root / ".claude" / "settings.json",
            hooks_dir / "checkpoint_before_compact.py",
        ]
    }

    result2 = subprocess.run(
        [sys.executable, str(STAGING_PATH), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
        env=env,
    )
    assert result2.returncode == 0

    for path, before in snapshot.items():
        assert path.read_bytes() == before
