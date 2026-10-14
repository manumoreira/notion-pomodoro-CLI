"""Unit tests for PomodoroTimer time formatting and TimerResult."""

from notion_pomodoro.timer import PomodoroTimer, TimerResult


def test_timer_format_time():
    assert PomodoroTimer._format_time(0) == "00:00"
    assert PomodoroTimer._format_time(59) == "00:59"
    assert PomodoroTimer._format_time(60) == "01:00"
    assert PomodoroTimer._format_time(1500) == "25:00"
    assert PomodoroTimer._format_time(300) == "05:00"


def test_timer_result_elapsed_minutes():
    res1 = TimerResult(completed=True, elapsed_seconds=1500, total_seconds=1500)
    assert res1.elapsed_minutes == 25

    res2 = TimerResult(completed=True, elapsed_seconds=120, total_seconds=1500)
    assert res2.elapsed_minutes == 2

    res3 = TimerResult(completed=True, elapsed_seconds=45, total_seconds=1500)
    assert res3.elapsed_minutes == 1

    res4 = TimerResult(completed=False, elapsed_seconds=10, total_seconds=1500)
    assert res4.elapsed_minutes == 0


def test_timer_pause_prompts_render_intact():
    import io
    from rich.console import Console

    # Verify that Rich does not eat the initial letters when rendering the prompts
    break_prompt = (
        r"Choose action: [bold cyan]\[r][/bold cyan]esume, "
        r"[bold cyan]\[s][/bold cyan]kip break, "
        r"[bold cyan]\[q][/bold cyan]uit"
    )
    work_prompt = (
        r"Choose action: [bold cyan]\[r][/bold cyan]esume, "
        r"[bold cyan]\[f][/bold cyan]inish early & log, "
        r"[bold cyan]\[q][/bold cyan]uit/cancel"
    )

    out = io.StringIO()
    c = Console(file=out, color_system=None)
    c.print(break_prompt)
    rendered_break = out.getvalue()
    assert "[r]esume" in rendered_break
    assert "[s]kip break" in rendered_break
    assert "[q]uit" in rendered_break
    assert "esume" in rendered_break and not rendered_break.startswith("Choose action: esume")

    out_work = io.StringIO()
    c_work = Console(file=out_work, color_system=None)
    c_work.print(work_prompt)
    rendered_work = out_work.getvalue()
    assert "[r]esume" in rendered_work
    assert "[f]inish early & log" in rendered_work
    assert "[q]uit/cancel" in rendered_work
