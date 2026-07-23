#!/usr/bin/env python3
"""Stop フック: CLAUDE_NOTIFY=1 のとき、セッション停止時に
デスクトップ通知を出す。長時間パイプラインの完了・停止を離席中でも把握できる。

Windows: PowerShell のトースト通知
macOS: osascript
Linux: notify-send
いずれも失敗しても exit 0(通知の失敗で作業を止めない)。

配置は Stop フックの末尾。stop_hook_active(他の Stop フックのブロックに
よる自動継続中)のときは通知しない — exit 2 のブロックでは Claude は
停止せず作業を続行するため、「停止しました」という通知は偽報になる。
"""

import json
import os
import platform
import subprocess
import sys


def _sq(text: str) -> str:
    """PowerShell / AppleScript の単一引用符文字列に安全に埋め込む。

    環境変数由来のパスに引用符が含まれるとスクリプトが壊れる
    (任意コマンド注入にもなり得る)ため、最低限のエスケープを行う。
    """
    return text.replace("'", "''")


def notify(title: str, message: str) -> None:
    system = platform.system()
    try:
        if system == "Windows":
            script = (
                "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
                "$t = [Windows.UI.Notifications.ToastTemplateType]::ToastText02;"
                "$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($t);"
                f"$x.GetElementsByTagName('text').Item(0).AppendChild($x.CreateTextNode('{_sq(title)}')) > $null;"
                f"$x.GetElementsByTagName('text').Item(1).AppendChild($x.CreateTextNode('{_sq(message)}')) > $null;"
                "$n = [Windows.UI.Notifications.ToastNotification]::new($x);"
                "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Claude Code').Show($n);"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                timeout=10,
            )
        elif system == "Darwin":
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "{message.replace(chr(34), "")}" '
                    f'with title "{title.replace(chr(34), "")}"',
                ],
                capture_output=True,
                timeout=10,
            )
        else:
            subprocess.run(
                ["notify-send", title, message],
                capture_output=True,
                timeout=10,
            )
    except Exception:
        pass


def main():
    if os.environ.get("CLAUDE_NOTIFY", "") != "1":
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    # ブロック起因の自動継続中は通知しない(停止していないため)
    if data.get("stop_hook_active"):
        sys.exit(0)

    scope = os.environ.get("CLAUDE_WORK_SCOPE", "").strip() or "(scope未設定)"
    notify("Claude Code", f"セッションが停止しました: {scope}")
    sys.exit(0)


if __name__ == "__main__":
    main()
