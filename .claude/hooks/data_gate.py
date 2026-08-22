#!/usr/bin/env python3
"""PreToolUse: data/ の外部送信を CLAUDE_DATA_GATE=1 のときだけ fail-closed で遮断する。

data/exports/ 配下は正規の持ち出し経路のため対象外。既定は無効で、
CLAUDE_DATA_GATE=1 が明示されたときだけ判定に入る(R-009: オプトイン)。

コマンド文字列の静的判定であり、変数展開・シェルスクリプト経由の送信は
検知できない(guard_bash.py と同じ既知の限界。多層防御の補助線)。
"""

import json
import os
import re
import sys

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


def main() -> None:
    if os.environ.get("CLAUDE_DATA_GATE") != "1":
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cmd = data.get("tool_input", {}).get("command", "")
    if not cmd:
        sys.exit(0)

    # exports/ が同一コマンドラインに同居していても、raw参照がある限り遮断する
    # (exports があるからといって全体を通してはならない)
    if _has_raw_data_ref(cmd) and _has_upload_cmd(cmd):
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
