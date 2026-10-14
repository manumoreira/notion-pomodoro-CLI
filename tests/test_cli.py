"""Unit tests for CLI commands using CliRunner."""

import io
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from notion_pomodoro.cli import app
from notion_pomodoro.config import Config
from notion_pomodoro.timer import TimerResult

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "notion-pomodoro-cli" in result.stdout


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Pomodoro timer" in result.stdout
    assert "Commands" in result.stdout


def test_cli_status_unconfigured(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with patch("notion_pomodoro.cli.load_config", return_value=Config()):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "Not configured" in result.stdout
        assert "pomodoro init" in result.stdout


def test_cli_tasks_unconfigured():
    with patch("notion_pomodoro.cli.load_config", return_value=Config()):
        result = runner.invoke(app, ["tasks"])
        assert result.exit_code == 1
        assert "Notion is not configured" in result.stdout


def test_cli_log_unconfigured():
    with patch("notion_pomodoro.cli.load_config", return_value=Config()):
        result = runner.invoke(app, ["log", "--task", "Test Task"])
        assert result.exit_code == 1
        assert "Notion is not configured" in result.stdout


def test_cli_break():
    with patch("notion_pomodoro.timer.PomodoroTimer.run") as mock_run:
        mock_run.return_value = TimerResult(completed=True, elapsed_seconds=300, total_seconds=300)
        result = runner.invoke(app, ["break", "-m", "5", "--silent"])
        assert result.exit_code == 0
        assert "finished" in result.stdout
        mock_run.assert_called_once_with(duration_minutes=5, session_type="Break")


def test_cli_status_configured():
    mock_cfg = Config(
        api_key="secret_test_12345678",
        database_id="db123",
        work_minutes=25,
        short_break_minutes=5,
        long_break_minutes=15,
        cycles=4,
    )
    with patch("notion_pomodoro.cli.load_config", return_value=mock_cfg):
        with patch("notion_pomodoro.cli.NotionLogger.validate_connection") as mock_val:
            mock_val.return_value = (
                True,
                "Connected to Notion database 'My Tasks'",
                {
                    "title": "My Tasks",
                    "properties": {"Task": "title", "Status": "status", "Pomodoros": "number"},
                    "raw_properties": {
                        "Task": {"type": "title"},
                        "Status": {"type": "status"},
                        "Pomodoros": {"type": "number"},
                    },
                },
            )
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 0
            assert "Connected to Notion" in result.stdout
            assert "Database Columns" in result.stdout


def test_cli_tasks_configured():
    mock_cfg = Config(
        api_key="secret_test_12345678",
        database_id="db123",
    )
    tasks_sample = [
        {
            "id": "p1",
            "title": "Build Auth",
            "project": "Backend",
            "pomodoros": 2,
            "time_spent": 50,
            "status": "In Progress",
            "url": "https://notion.so/p1",
        }
    ]
    with patch("notion_pomodoro.cli.load_config", return_value=mock_cfg):
        with patch("notion_pomodoro.cli.NotionLogger.fetch_recent_tasks", return_value=tasks_sample):
            result = runner.invoke(app, ["tasks"])
            assert result.exit_code == 0
            assert "Build Auth" in result.stdout
            assert "Backend" in result.stdout


def test_cli_log_configured():
    mock_cfg = Config(
        api_key="secret_test_12345678",
        database_id="db123",
    )
    return_val = {
        "action": "created",
        "id": "p1",
        "url": "https://notion.so/p1",
        "pomodoros": 1,
        "time_spent": 25,
    }
    with patch("notion_pomodoro.cli.load_config", return_value=mock_cfg):
        with patch("notion_pomodoro.cli.NotionLogger.record_or_increment_task", return_value=return_val):
            result = runner.invoke(app, ["log", "--task", "Write Documentation", "--pomodoros", "1", "--duration", "25"])
            assert result.exit_code == 0
            assert "Created new task in Notion!" in result.stdout
            assert "Write Documentation" in result.stdout


def test_handle_unmatched_task_found_in_recent():
    from rich.console import Console
    from notion_pomodoro.cli import _handle_unmatched_task

    mock_logger = MagicMock()
    recent = [{"id": "p1", "title": "Existing Task", "project": "Acme"}]
    c = Console(file=io.StringIO(), color_system=None)

    name, page_id, tag, untracked, cancelled, retry = _handle_unmatched_task(
        task_input="existing task",
        recent_tasks=recent,
        notion_logger=mock_logger,
        console=c,
    )
    assert name == "Existing Task"
    assert page_id == "p1"
    assert tag == "Acme"
    assert not untracked
    assert not cancelled
    assert not retry


def test_handle_unmatched_task_found_in_notion():
    from rich.console import Console
    from notion_pomodoro.cli import _handle_unmatched_task

    mock_logger = MagicMock()
    mock_logger.find_task_by_title.return_value = {
        "id": "p2",
        "title": "Database Optimization",
        "project": "DevOps"
    }
    c = Console(file=io.StringIO(), color_system=None)

    name, page_id, tag, untracked, cancelled, retry = _handle_unmatched_task(
        task_input="Database Optimization",
        recent_tasks=[],
        notion_logger=mock_logger,
        console=c,
    )
    assert name == "Database Optimization"
    assert page_id == "p2"
    assert tag == "DevOps"
    assert not untracked


def test_handle_unmatched_task_not_found_choose_retry():
    from rich.console import Console
    from notion_pomodoro.cli import _handle_unmatched_task

    mock_logger = MagicMock()
    mock_logger.find_task_by_title.return_value = None
    c = Console(file=io.StringIO(), color_system=None)

    with patch("notion_pomodoro.cli.Prompt.ask", return_value="1"):
        name, page_id, tag, untracked, cancelled, retry = _handle_unmatched_task(
            task_input="Nonexistent Task",
            recent_tasks=[],
            notion_logger=mock_logger,
            console=c,
        )
        assert retry is True
        assert not cancelled


def test_handle_unmatched_task_not_found_choose_create():
    from rich.console import Console
    from notion_pomodoro.cli import _handle_unmatched_task

    mock_logger = MagicMock()
    mock_logger.find_task_by_title.return_value = None
    c = Console(file=io.StringIO(), color_system=None)

    with patch("notion_pomodoro.cli.Prompt.ask", return_value="2"):
        name, page_id, tag, untracked, cancelled, retry = _handle_unmatched_task(
            task_input="Brand New Task",
            recent_tasks=[],
            notion_logger=mock_logger,
            console=c,
        )
        assert name == "Brand New Task"
        assert page_id is None
        assert not untracked
        assert not retry
        assert not cancelled


def test_handle_unmatched_task_not_found_choose_untracked():
    from rich.console import Console
    from notion_pomodoro.cli import _handle_unmatched_task

    mock_logger = MagicMock()
    mock_logger.find_task_by_title.return_value = None
    c = Console(file=io.StringIO(), color_system=None)

    with patch("notion_pomodoro.cli.Prompt.ask", return_value="3"):
        name, page_id, tag, untracked, cancelled, retry = _handle_unmatched_task(
            task_input="Local Scratch",
            recent_tasks=[],
            notion_logger=mock_logger,
            console=c,
        )
        assert name == "Local Scratch"
        assert untracked is True
        assert not cancelled


def test_handle_unmatched_task_not_found_choose_cancel():
    from rich.console import Console
    from notion_pomodoro.cli import _handle_unmatched_task

    mock_logger = MagicMock()
    mock_logger.find_task_by_title.return_value = None
    c = Console(file=io.StringIO(), color_system=None)

    with patch("notion_pomodoro.cli.Prompt.ask", return_value="q"):
        name, page_id, tag, untracked, cancelled, retry = _handle_unmatched_task(
            task_input="Never Mind",
            recent_tasks=[],
            notion_logger=mock_logger,
            console=c,
        )
        assert cancelled is True

