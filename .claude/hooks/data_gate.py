#!/usr/bin/env python3
"""PreToolUse: data/ の外部送信(egress)と、NO_READ実効時の読み取りを遮断する。

判定はプロファイル解決(CLAUDE_DATA_PROFILE)と個別変数
(CLAUDE_DATA_NO_READ / CLAUDE_DATA_GATE)の組み合わせで決まる。個別変数が
非空ならプロファイルより優先する。sensitive は読み遮断・egress遮断の両方が
実効、internal は egress遮断のみ、public・空は両方無効。
CLAUDE_DATA_GATE=1 を単独指定した場合(NO_READ・PROFILE空)は Phase 2 と
同じ挙動(egressのみ遮断、読みは通す)を維持する(R-009: オプトイン)。

data/exports/ 配下は正規の持ち出し経路のため egress・読み遮断のいずれの
対象外。data/synthetic/・data/data.lock・data/.backup_stamp も読み遮断の
対象外(data_read_gate.py と同じ除外規約)。窓口 `scripts/data_summary.py` を
実行するセグメントも読み遮断の対象外(全セグメントが窓口実行またはdata/
非参照のときだけ許可)。

`.claude/spec/data_unlock.txt`(CLAUDE_SPEC_DIR配下)に有効期限内の UTC
epoch秒が記録されていれば、読み遮断は一時的に解除される
(`.claude/hooks/data_unlock.py` がユーザー `!` 実行専用で書く)。

コマンド文字列の静的判定であり、変数展開・シェルスクリプト経由の送信は
検知できない(guard_bash.py と同じ既知の限界。多層防御の補助線)。
"""

import json
import os
import re
import sys
import time
from pathlib import Path

from _common import resolve_spec_dir

# アップロード系コマンド(セグメント先頭で判定)
_UPLOAD_CMDS = {
    "curl",
    "wget",
    "scp",
    "rsync",
    "rclone",
    "aws",
    "gcloud",
    "gsutil",
    "az",
    "gh",
}

# guard_bash.py の _SEGMENT_SPLIT と同じ考え方(; & | 改行を区切りとみなし、
# && / || / ; / | を区別せず全て切り出す)
_SEGMENT_SPLIT = re.compile(r"[;&|\n]+")

# data/ 配下パスの検出(引用符は文字クラスに含めないため、部分引用
# "data/raw/x.csv" でもマッチする)
_DATA_PATH = re.compile(r"data/[\w./-]+")

_EXPORTS_PREFIX = "data/exports/"


def _segment_head(segment: str) -> str | None:
    """セグメントの先頭コマンド名を返す。"""
    tokens = segment.strip().split()
    if not tokens:
        return None
    return os.path.basename(tokens[0].strip("\"'")).lower()


def _has_raw_data_ref(cmd: str) -> bool:
    """data/ 配下(data/exports/ を除く)への参照があるかを判定する。"""
    for match in _DATA_PATH.finditer(cmd):
        if not match.group(0).startswith(_EXPORTS_PREFIX):
            return True
    return False


def _has_upload_cmd(cmd: str) -> bool:
    """パイプ・&&・; のいずれで結合されていてもアップロード系コマンドを検出する。"""
    for segment in _SEGMENT_SPLIT.split(cmd):
        if _segment_head(segment) in _UPLOAD_CMDS:
            return True
    return False


# data_read_gate.py にも同じ関数を同梱する(意図的な重複。hooks自己完結原則
# R-022。PC-13 が両者の実効結果の一致を固定する)。
_EXCLUDED_DATA_PREFIXES = ("synthetic/", "exports/")
_EXCLUDED_DATA_FILES = ("data.lock", ".backup_stamp")

# 窓口実行セグメントの検出(scripts/data_summary.py を起動するセグメントは
# 読み遮断の対象外にする)
_WINDOW_SCRIPT = re.compile(r"scripts[/\\]data_summary\.py")


def resolve_no_read_value() -> str:
    """CLAUDE_DATA_NO_READ(個別)を優先し、無ければ CLAUDE_DATA_PROFILE から解決する。

    Returns:
        "" (無効) / "0" (無効) / "1" (data/ 全体) /
        data/ 直下のサブディレクトリ名のカンマ区切り、のいずれか。
    """
    individual = os.environ.get("CLAUDE_DATA_NO_READ", "").strip()
    if individual:
        return individual
    profile = os.environ.get("CLAUDE_DATA_PROFILE", "").strip().lower()
    if profile == "sensitive":
        return "1"
    return ""


def resolve_gate_enabled() -> bool:
    """CLAUDE_DATA_GATE(個別)を優先し、無ければ CLAUDE_DATA_PROFILE から解決する。"""
    individual = os.environ.get("CLAUDE_DATA_GATE", "").strip()
    if individual:
        return individual == "1"
    profile = os.environ.get("CLAUDE_DATA_PROFILE", "").strip().lower()
    return profile in ("sensitive", "internal")


def _unlock_active() -> bool:
    """一時解除の記録(CLAUDE_SPEC_DIR配下 data_unlock.txt)が有効期限内なら True。

    読めない・解釈できない・期限切れの記録はすべて「解除されていない」として
    扱う(遮断の目的上、ここだけはfail-closed側に倒す)。
    """
    spec_dir = resolve_spec_dir()
    unlock_file = Path(spec_dir) / "data_unlock.txt"
    if not unlock_file.exists():
        return False
    try:
        content = unlock_file.read_text(encoding="utf-8").strip()
        expiry = int(content)
    except (OSError, UnicodeError, ValueError):
        return False
    return expiry > int(time.time())


def _rel_after_data(match_text: str) -> str:
    """`_DATA_PATH` がマッチした文字列("data/..." )から "data/" を除いた残りを返す。"""
    return match_text[len("data/") :]


def _is_excluded_data_rel(rel: str) -> bool:
    """data_read_gate.py と同じ除外規約(synthetic/・exports/・data.lock・.backup_stamp)。"""
    if rel.startswith(_EXCLUDED_DATA_PREFIXES):
        return True
    return rel in _EXCLUDED_DATA_FILES


def _segment_has_blocked_data_ref(segment: str, no_read_value: str) -> bool:
    """1セグメントに NO_READ 実効値で遮断対象になる data/ 参照があれば True。"""
    for match in _DATA_PATH.finditer(segment):
        rel = _rel_after_data(match.group(0))
        if _is_excluded_data_rel(rel):
            continue
        if no_read_value == "1":
            return True
        subdirs = {s.strip() for s in no_read_value.split(",") if s.strip()}
        if rel.split("/", 1)[0] in subdirs:
            return True
    return False


def _no_read_blocks_cmd(cmd: str, no_read_value: str) -> bool:
    """NO_READ実効時、コマンドが遮断対象の data/ 読み取りを含むなら True。

    窓口 `scripts/data_summary.py` を実行するセグメントは対象外にする
    (全セグメントが窓口実行またはdata/非参照のときだけ許可)。アップロード系
    コマンド(_UPLOAD_CMDS)は egress側(GATE)の管轄であり、ここでは対象外にする
    (CLAUDE_DATA_GATE=0 の個別上書きがNO_READ経由で骨抜きにならないようにする)。
    """
    if no_read_value in ("", "0"):
        return False
    for segment in _SEGMENT_SPLIT.split(cmd):
        if _WINDOW_SCRIPT.search(segment):
            continue
        if _segment_head(segment) in _UPLOAD_CMDS:
            continue
        if _segment_has_blocked_data_ref(segment, no_read_value):
            return True
    return False


def main() -> None:
    no_read_value = resolve_no_read_value()
    gate_enabled = resolve_gate_enabled()
    if not gate_enabled and no_read_value in ("", "0"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cmd = data.get("tool_input", {}).get("command", "")
    if not cmd:
        sys.exit(0)

    if _no_read_blocks_cmd(cmd, no_read_value):
        if _unlock_active():
            print(
                "[data_gate] 一時解除が有効なため data/ の読み取りを許可します"
                "(期限内)。",
                file=sys.stderr,
            )
        else:
            print(
                "[data_gate] BLOCKED: data/ 配下(除外パスを除く)を読み取ろうとする"
                "コマンドを検出しました。統計量だけが必要なら"
                " `uv run python scripts/data_summary.py <path>`(窓口)を使って"
                "ください。個票が必要な場合はユーザーに"
                " `! uv run python .claude/hooks/data_unlock.py [--minutes N]` "
                "の実行を依頼してください(既定30分・上限240分)。",
                file=sys.stderr,
            )
            sys.exit(2)

    # exports/ が同一コマンドラインに同居していても、raw参照がある限り遮断する
    # (exports があるからといって全体を通してはならない)
    if gate_enabled and _has_raw_data_ref(cmd) and _has_upload_cmd(cmd):
        print(
            "[data_gate] BLOCKED: data/ 配下(data/exports/ を除く)を外部へ"
            "送信しようとするコマンドを検出しました。"
            "exports/ に集計値として置いてから、そちらを送信してください。"
            "(静的なコマンド文字列判定であり補助線です。変数展開・"
            "スクリプト経由の送信までは検知できません)",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
