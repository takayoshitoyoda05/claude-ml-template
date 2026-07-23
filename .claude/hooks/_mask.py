#!/usr/bin/env python3
"""ログ書き込み前の秘密情報マスキング。

エージェントのトレースにはプロンプト・ツール引数・コマンド出力が含まれ、
秘密情報が混入しうる。ログに書く前に既知パターンを伏せ字にする。
"""

import re

# guard_bash.py の検知パターンと同じ系統。マスキング用に再定義
_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9_\-]{16,})"),  # OpenAI/Anthropic系APIキー
    re.compile(r"(ghp_[A-Za-z0-9]{20,})"),  # GitHub PAT
    re.compile(r"(gho_[A-Za-z0-9]{20,})"),  # GitHub OAuth
    re.compile(r"(AKIA[0-9A-Z]{16})"),  # AWS Access Key
    re.compile(r"(xox[baprs]-[A-Za-z0-9\-]{10,})"),  # Slack token
    re.compile(
        r"((?:api[_-]?key|token|secret|password|passwd)\s*[=:]\s*)"
        r"(['\"]?)([^\s'\"]{8,})(\2)",
        re.IGNORECASE,
    ),  # key=value 形式
]


def mask(text: str) -> str:
    """既知の秘密情報パターンを [MASKED] に置換して返す。"""
    if not text:
        return text
    masked = text
    for pat in _PATTERNS[:5]:
        masked = pat.sub("[MASKED]", masked)
    # key=value 形式は値だけマスクする
    masked = _PATTERNS[5].sub(r"\1\2[MASKED]\4", masked)
    return masked
