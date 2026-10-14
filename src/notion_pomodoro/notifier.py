"""Audio and system notification utilities for session completion."""

import platform
import subprocess
import sys
from typing import Optional


from rich.console import Console
from rich.panel import Panel


def ring_bell() -> None:
    """Emit an audio alert via terminal bell."""
    try:
        sys.stdout.write("\a")
        sys.stdout.flush()
    except Exception:
        pass


def send_system_notification(title: str, message: str, sound_name: str = "Glass") -> bool:
    """
    Send a native desktop notification.
    
    Supports:
      - macOS (via AppleScript osascript)
      - Linux (via notify-send if installed)
      - Windows (via PowerShell / basic fallback)
    """
    current_os = platform.system().lower()

    if current_os == "darwin":  # macOS
        # Escape quotes in title and message
        safe_title = title.replace('"', '\\"')
        safe_msg = message.replace('"', '\\"')
        apple_script = f'display notification "{safe_msg}" with title "{safe_title}" sound name "{sound_name}"'
        try:
            subprocess.run(
                ["osascript", "-e", apple_script],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            return False

    elif current_os == "linux":
        try:
            subprocess.run(
                ["notify-send", title, message],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            return False

    elif current_os == "windows":
        try:
            ps_script = (
                f'[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; '
                f'$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); '
                f'$textNodes = $template.GetElementsByTagName("text"); '
                f'$textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) > $null; '
                f'$textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) > $null; '
                f'$toast = [Windows.UI.Notifications.ToastNotification]::new($template); '
                f'[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Notion Pomodoro").Show($toast);'
            )
            subprocess.run(
                ["powershell", "-Command", ps_script],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            return False

    return False


def notify_session_end(
    session_type: str,
    task_name: Optional[str] = None,
    console: Optional[Console] = None,
    os_notify: bool = False,
) -> None:
    """Notify user of session completion via terminal bell and visual banner."""
    ring_bell()

    c = console or Console()

    if session_type.lower() == "work":
        title = "🍅 Pomodoro Completed!"
        if task_name:
            msg = f"Finished focus block on: [bold]{task_name}[/bold]. Time for a break!"
        else:
            msg = "Focus session completed. Time for a break!"
        border_style = "green"
        sound = "Hero"
    elif session_type.lower() == "short_break":
        title = "☕ Short Break Ended!"
        msg = "Break is over. Ready to start your next focus session?"
        border_style = "cyan"
        sound = "Glass"
    else:  # Long break
        title = "🌴 Long Break Ended!"
        msg = "Fully recharged? Let's dive back into focus!"
        border_style = "magenta"
        sound = "Ping"

    c.print(
        Panel(
            f"[bold {border_style}]🔔 {title}[/bold {border_style}]\n{msg}",
            border_style=border_style,
            padding=(0, 2),
        )
    )

    if os_notify:
        send_system_notification(title, msg, sound_name=sound)
