"""Unit tests for notifier module."""

from unittest.mock import patch
import io
from rich.console import Console
from notion_pomodoro.notifier import ring_bell, notify_session_end


def test_ring_bell():
    with patch("sys.stdout.write") as mock_write, patch("sys.stdout.flush") as mock_flush:
        ring_bell()
        mock_write.assert_called_once_with("\a")
        mock_flush.assert_called_once()


def test_notify_session_end_terminal_only():
    out = io.StringIO()
    c = Console(file=out, color_system=None)

    with patch("notion_pomodoro.notifier.send_system_notification") as mock_os_notify:
        notify_session_end("work", task_name="Refactor API", console=c, os_notify=False)
        mock_os_notify.assert_not_called()

    rendered = out.getvalue()
    assert "Pomodoro Completed!" in rendered
    assert "Refactor API" in rendered


def test_notify_session_end_with_os_notify():
    out = io.StringIO()
    c = Console(file=out, color_system=None)

    with patch("notion_pomodoro.notifier.send_system_notification") as mock_os_notify:
        notify_session_end("short_break", console=c, os_notify=True)
        mock_os_notify.assert_called_once()
        args = mock_os_notify.call_args[0]
        assert "Short Break Ended!" in args[0]

    rendered = out.getvalue()
    assert "Short Break Ended!" in rendered


def test_notify_session_end_long_break():
    out = io.StringIO()
    c = Console(file=out, color_system=None)

    with patch("notion_pomodoro.notifier.send_system_notification") as mock_os_notify:
        notify_session_end("long_break", console=c, os_notify=False)
        mock_os_notify.assert_not_called()

    rendered = out.getvalue()
    assert "Long Break Ended!" in rendered
