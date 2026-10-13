"""Unit tests for CLI commands using CliRunner."""

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
