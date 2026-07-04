#!/usr/bin/env python3
"""PreToolUse: 危険な Bash コマンド・大容量/秘密情報ファイルの git add・
ファイル変更コマンド/リダイレクト/tee による秘密情報ファイル・フック設定への
書き込み・コミットメッセージ規約をチェックする。

コミットメッセージ規約(ステップ番号必須)は CLAUDE_COMMIT_STEP_RULE=1 の
ときのみ有効(ml-pipeline実行時を想定。通常の手動コミットを妨げないため)。

注意(多層防御としての限界):
このガードは cp/mv/sed/rm 等の「よく使う直接的な変更手段」と
リダイレクト/tee を塞ぐが、`python -c "open(...,'w')"` のような任意
コード実行や、名前指定の find -delete までは原理的に検知できない。
保護パスの本当の防壁は「ユーザーが手動編集する運用」であり、これは
事故と単純な逸脱を止める補助線と位置づける。
"""
import json
import os
import re
import sys

from _common import (
    ARTIFACT_EXTENSIONS,
    BLOCKED_EXTENSIONS,
    BLOCKED_FILENAMES,
    PROTECTED_PATH_PATTERNS,
    SECRET_CONTENT_PATTERNS,
)

DANGER_PATTERNS = [
    r"git\s+reset\s+--hard",
    r"git\s+push\s+.*--force",
    r"git\s+push\s+-f\b",
    r"git\s+push\s+\S+\s+\+\S+",  # 強制pushの別記法(+refspec)
    r":\(\)\{.*\}:",
    r"mkfs\.",
    r"dd\s+if=.*of=/dev/",
]

BLOCKED_ADD_EXT = sorted(ARTIFACT_EXTENSIONS | BLOCKED_EXTENSIONS)

# ファイルを変更・削除しうるコマンド名(セグメント先頭に来たとき、
# その引数に保護パスが現れたらブロック)。読み取り(cat/grep/diff)や
# 実行(python/uv run python)は含めない。git は rm サブコマンドのみ対象。
FILE_MUTATING_CMDS = {
    "cp", "mv", "rm", "sed", "install", "truncate", "ln",
    "dd", "tee", "chmod", "chown", "shred", "rsync",
}

# セグメント先頭に来ても実際のコマンドではない前置き(読み飛ばす)
_PREFIX_CMDS = {"sudo", "nohup", "time", "env", "nice", "xargs", "command", "builtin"}
_ENV_ASSIGN = re.compile(r"^\w+=")
_SEGMENT_SPLIT = re.compile(r"[;&|\n]+")


def is_dangerous_rm(cmd):
    """再帰かつ強制の rm が絶対パス・~・$HOME を対象にしていたら True。

    -rf / -fr / -r -f のような表記ゆれをフラグ解析で吸収する。
    対象は /、~、$HOME(${HOME} 等の波括弧展開含む)を先頭に持つもの。
    """
    for m in re.finditer(r"\brm\s+([^|;&]+)", cmd):
        args = m.group(1).split()
        flags = "".join(a.lstrip("-") for a in args if a.startswith("-")).lower()
        targets = [a.strip("\"'") for a in args if not a.startswith("-")]
        if "r" in flags and "f" in flags:
            for t in targets:
                if t.startswith(("/", "~")) or re.match(r"\$\{?HOME", t):
                    return True
    return False


def write_targets(cmd):
    """リダイレクト(> / >> / >| / 1> / 2>>)と tee の書き込み先を列挙する。

    先頭のファイルディスクリプタ番号(1> 2>)と noclobber 強制(>|)にも対応する。
    """
    targets = re.findall(r"\d*>{1,2}\|?\s*(\S+)", cmd)
    targets += re.findall(r"\btee\s+(?:-[a-zA-Z]+\s+)*(\S+)", cmd)
    # 稀に target が `|` や `>` だけになるケースを除外
    return [t.strip("\"'") for t in targets if t.strip("\"'") not in ("|", ">", "")]


def _segment_mutating_targets(segment):
    """1セグメントが変更コマンドなら、その引数(パス候補)を返す。

    先頭の環境変数代入(FOO=bar)や sudo 等の前置きは読み飛ばす。
    git は `git rm` のみ対象(add/commit/diff はファイル内容を変えないので除外)。
    `dd of=path` のような `key=value` 形式は value 側もパス候補に含める。
    """
    tokens = segment.strip().split()
    while tokens and (_ENV_ASSIGN.match(tokens[0]) or
                      os.path.basename(tokens[0].strip("\"'")) in _PREFIX_CMDS):
        tokens = tokens[1:]
    if not tokens:
        return []

    name = os.path.basename(tokens[0].strip("\"'"))
    rest = tokens[1:]
    if name == "git":
        if rest and rest[0] == "rm":
            rest = rest[1:]
        else:
            return []
    elif name not in FILE_MUTATING_CMDS:
        return []

    candidates = []
    for t in rest:
        t = t.strip("\"'")
        if not t or t.startswith("-"):
            continue
        candidates.append(t)
        if "=" in t:
            candidates.append(t.split("=", 1)[1])  # of=path 等の value 側
    return candidates


def touches_protected_via_mutating_cmd(cmd):
    """変更コマンドが保護パスを実引数に取っていれば、そのパスを返す。

    セグメント(; && || | 区切り)ごとに先頭コマンド名を見るため、
    コミットメッセージ本文に "rm" や保護パス名が現れても誤検知しない。
    """
    for segment in _SEGMENT_SPLIT.split(cmd):
        for token in _segment_mutating_targets(segment):
            abs_norm = os.path.abspath(token).replace("\\", "/")
            if any(pat in abs_norm for pat in PROTECTED_PATH_PATTERNS):
                return token
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cmd = data.get("tool_input", {}).get("command", "")
    if not cmd:
        sys.exit(0)

    if is_dangerous_rm(cmd) or any(re.search(p, cmd) for p in DANGER_PATTERNS):
        print(
            f"[guard_bash] BLOCKED: 危険なコマンドを検出しました: {cmd}\n"
            f"本当に必要な場合は Claude Code の外で手動実行してください。",
            file=sys.stderr,
        )
        sys.exit(2)

    for pat in SECRET_CONTENT_PATTERNS:
        if re.search(pat, cmd):
            print(
                "[guard_bash] BLOCKED: コマンドに秘密情報らしき文字列が含まれています。",
                file=sys.stderr,
            )
            sys.exit(2)

    # cp/mv/sed/rm/install/truncate/tee/git rm 等でフック・設定・承認記録を
    # 書き換え/削除するのをブロック(guard_scope は Edit/Write しか見ないため)
    protected_token = touches_protected_via_mutating_cmd(cmd)
    if protected_token is not None:
        print(
            f"[guard_bash] BLOCKED: フック/設定/承認記録({protected_token})を変更する"
            f"コマンドは禁止です。変更が必要な場合はユーザーが手動で編集してください。",
            file=sys.stderr,
        )
        sys.exit(2)

    # リダイレクト/tee で秘密情報ファイルやフック設定へ直接書き込むのをブロック
    for target in write_targets(cmd):
        norm = target.replace("\\", "/")
        base = os.path.basename(norm)
        _, ext = os.path.splitext(base)
        if base in BLOCKED_FILENAMES or ext.lower() in BLOCKED_EXTENSIONS:
            print(
                f"[guard_bash] BLOCKED: 秘密情報ファイル({base})への書き込みは禁止です。",
                file=sys.stderr,
            )
            sys.exit(2)
        abs_norm = os.path.abspath(target).replace("\\", "/")
        if any(pat in abs_norm for pat in PROTECTED_PATH_PATTERNS):
            print(
                f"[guard_bash] BLOCKED: フック/設定({target})への書き込みは禁止です。"
                f"変更が必要な場合はユーザーが手動で編集してください。",
                file=sys.stderr,
            )
            sys.exit(2)

    if re.search(r"git\s+add\b", cmd):
        # 一括ステージは生成物混入の主経路なのでパス限定を促す
        if re.search(r"git\s+add\s+(?:-[A-Za-z]*A[A-Za-z]*|--all|\*|\.(?:/)?(?:\s|$))", cmd):
            print(
                "[guard_bash] BLOCKED: git add の一括ステージ(. / -A / --all / *)は"
                "禁止です。対象パスを明示してください(例: git add src/train.py)。",
                file=sys.stderr,
            )
            sys.exit(2)
        for ext in BLOCKED_ADD_EXT:
            if re.search(re.escape(ext) + r"(?=[\s\"']|$)", cmd):
                print(
                    f"[guard_bash] BLOCKED: 大容量/秘密情報ファイル({ext})の git add は禁止です。"
                    f".gitignore に追加してください。",
                    file=sys.stderr,
                )
                sys.exit(2)
        for name in BLOCKED_FILENAMES:
            if re.search(r"(?:^|[\s/\"'])" + re.escape(name) + r"(?=[\s\"']|$)", cmd):
                print(
                    f"[guard_bash] BLOCKED: 秘密情報ファイル({name})の git add は禁止です。",
                    file=sys.stderr,
                )
                sys.exit(2)

    if os.environ.get("CLAUDE_COMMIT_STEP_RULE", "") == "1" and re.search(
        r"git\s+commit", cmd
    ):
        m = re.search(r"-m\s+[\"']([^\"']*)[\"']", cmd)
        if m and not re.search(r"\d", m.group(1)):
            print(
                f"[guard_bash] BLOCKED: コミットメッセージに計画のステップ番号(数字)が"
                f"含まれていません: {m.group(1)}\n"
                f"例: 'Step 2: fix interpolation formula'",
                file=sys.stderr,
            )
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
