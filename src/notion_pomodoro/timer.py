"""Visual terminal countdown timer with Rich progress bars and interactive controls."""

import sys
import time
from dataclasses import dataclass
from typing import Optional
from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text


@dataclass
class TimerResult:
    """Result returned after running a timer session."""
    completed: bool
    elapsed_seconds: int
    total_seconds: int
    interrupted: bool = False
    action: str = "completed"  # completed, finished_early, skipped, cancelled

    @property
    def elapsed_minutes(self) -> int:
        """Elapsed time in full minutes (minimum 1 minute if at least 30s elapsed)."""
        if self.elapsed_seconds < 30:
            return max(0, self.elapsed_seconds // 60)
        return max(1, round(self.elapsed_seconds / 60))


class PomodoroTimer:
    """Rich-based visual terminal countdown timer."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    @staticmethod
    def _format_time(seconds: int) -> str:
        """Format seconds into MM:SS string."""
        mins, secs = divmod(max(0, seconds), 60)
        return f"{mins:02d}:{secs:02d}"

    def run(
        self,
        duration_minutes: int,
        session_type: str = "Work",
        task_name: Optional[str] = None,
        cycle_num: Optional[int] = None,
        total_cycles: Optional[int] = None,
    ) -> TimerResult:
        """
        Run countdown timer with live progress update.
        
        Supports Ctrl+C interruption with resume / finish early / quit options.
        """
        total_seconds = int(duration_minutes * 60)
        elapsed_seconds = 0
        is_break = "break" in session_type.lower()
        theme_color = "cyan" if "short" in session_type.lower() else ("blue" if "long" in session_type.lower() else "green")
        badge_title = f"[bold {theme_color}]● {session_type.upper()}[/bold {theme_color}]"

        progress = Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn(f"[{theme_color}]{{task.description}}"),
            BarColumn(bar_width=40, complete_style=theme_color, finished_style="bold green"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TextColumn("[dim]{task.fields[remaining]}[/dim]"),
            console=self.console,
            transient=False,
        )

        task_id = progress.add_task(
            description=task_name or session_type,
            total=total_seconds,
            remaining=self._format_time(total_seconds)
        )

        start_time = time.time()

        def make_layout(curr_elapsed: int) -> Panel:
            rem_sec = total_seconds - curr_elapsed
            time_str = self._format_time(rem_sec)

            # Table for meta information
            table = Table.grid(padding=(0, 2))
            table.add_column(justify="left", style="bold white")
            table.add_column(justify="right", style="dim")

            if cycle_num and total_cycles:
                table.add_row(f"🔄 Cycle {cycle_num}/{total_cycles}", f"Target: {duration_minutes}m")
            else:
                table.add_row(f"⏱  Session: {session_type}", f"Target: {duration_minutes}m")

            if task_name and not is_break:
                table.add_row(f"🎯 Task: [bold]{task_name}[/bold]", f"Elapsed: {self._format_time(curr_elapsed)}")

            # Big stylized countdown text
            clock_text = Text(f" {time_str} ", style=f"bold {theme_color} on default", justify="center")

            content = Group(
                Align.center(clock_text),
                Align.center(progress),
                Align.center(table),
                Align.center(Text("[dim]Press Ctrl+C to pause / options[/dim]", style="dim")),
            )

            return Panel(
                content,
                title=badge_title,
                subtitle=f"[dim]Notion Pomodoro CLI[/dim]",
                border_style=theme_color,
                padding=(1, 2)
            )

        with Live(make_layout(0), console=self.console, refresh_per_second=4, screen=False) as live:
            while elapsed_seconds < total_seconds:
                try:
                    time.sleep(0.25)
                    elapsed_seconds = int(time.time() - start_time)
                    if elapsed_seconds > total_seconds:
                        elapsed_seconds = total_seconds

                    rem = total_seconds - elapsed_seconds
                    progress.update(task_id, completed=elapsed_seconds, remaining=self._format_time(rem))
                    live.update(make_layout(elapsed_seconds))

                except KeyboardInterrupt:
                    live.stop()
                    self.console.print("\n[yellow]⏸  Timer Paused.[/yellow]")
                    
                    if is_break:
                        prompt_text = "Choose action: [r]esume, [s]kip break, [q]uit"
                        choices = ["r", "s", "q"]
                    else:
                        prompt_text = "Choose action: [r]esume, [f]inish early & log, [q]uit/cancel"
                        choices = ["r", "f", "q"]

                    choice = Prompt.ask(prompt_text, choices=choices, default="r")

                    if choice == "r":
                        # Adjust start_time to account for paused duration
                        paused_duration = time.time() - (start_time + elapsed_seconds)
                        start_time += paused_duration
                        live.start()
                        continue
                    elif choice == "f":
                        self.console.print(f"[green]✓ Marked session completed early with {round(elapsed_seconds/60, 1)}m elapsed.[/green]")
                        return TimerResult(
                            completed=True,
                            elapsed_seconds=elapsed_seconds,
                            total_seconds=total_seconds,
                            interrupted=True,
                            action="finished_early"
                        )
                    elif choice == "s":
                        self.console.print("[yellow]⏭  Break skipped.[/yellow]")
                        return TimerResult(
                            completed=False,
                            elapsed_seconds=elapsed_seconds,
                            total_seconds=total_seconds,
                            interrupted=True,
                            action="skipped"
                        )
                    else:  # quit
                        self.console.print("[red]✗ Session cancelled.[/red]")
                        return TimerResult(
                            completed=False,
                            elapsed_seconds=elapsed_seconds,
                            total_seconds=total_seconds,
                            interrupted=True,
                            action="cancelled"
                        )

        # Finished naturally
        return TimerResult(
            completed=True,
            elapsed_seconds=total_seconds,
            total_seconds=total_seconds,
            interrupted=False,
            action="completed"
        )
