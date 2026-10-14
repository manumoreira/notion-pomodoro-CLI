"""Command line interface for Notion Pomodoro CLI using Typer and Rich."""

import sys
from datetime import datetime, timezone
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from notion_pomodoro import __version__
from notion_pomodoro.config import load_config, save_config, clean_database_id
from notion_pomodoro.notifier import notify_session_end
from notion_pomodoro.notion import NotionError, NotionLogger
from notion_pomodoro.timer import PomodoroTimer

app = typer.Typer(
    name="pomodoro",
    help="🍅 Lightweight CLI Pomodoro timer with automatic Notion database logging.",
    add_completion=False,
    no_args_is_help=False,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"[bold green]notion-pomodoro-cli[/bold green] version [cyan]{__version__}[/cyan]")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True, help="Show version and exit."
    ),
):
    """Notion Pomodoro CLI - Focus timer with automatic Notion logging."""
    if ctx.invoked_subcommand is None:
        # Default action when invoked without subcommands: show help or start
        console.print(
            Panel(
                "[bold green]🍅 Notion Pomodoro CLI[/bold green]\n"
                "[dim]Run [bold]pomodoro start[/bold] to begin a focus session, "
                "or [bold]pomodoro init[/bold] to configure your Notion database.[/dim]",
                border_style="green",
            )
        )
        # Print help guidance
        console.print(ctx.get_help())


@app.command(name="init")
@app.command(name="config")
def configure_cmd(
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k", help="Notion Integration Token (secret_...)"),
    database_id: Optional[str] = typer.Option(None, "--database-id", "-d", help="Notion Database ID or URL"),
    work_min: Optional[int] = typer.Option(None, "--work", "-w", help="Default work duration in minutes"),
    short_break_min: Optional[int] = typer.Option(None, "--short-break", "-s", help="Default short break minutes"),
    long_break_min: Optional[int] = typer.Option(None, "--long-break", "-l", help="Default long break minutes"),
    cycles: Optional[int] = typer.Option(None, "--cycles", "-c", help="Default number of cycles before long break"),
    use_global: bool = typer.Option(False, "--global", "-g", help="Save to global config ~/.config/notion-pomodoro/.env"),
):
    """Setup and validate Notion credentials and default timer durations."""
    console.print(
        Panel(
            "[bold cyan]⚙️ Notion Pomodoro Configuration Setup[/bold cyan]\n"
            "[dim]Connect your Notion workspace and database to enable automatic session logging.[/dim]",
            border_style="cyan",
        )
    )

    curr_cfg = load_config()

    if not api_key:
        default_prompt = f" [{curr_cfg.api_key[:8]}...]" if curr_cfg.api_key else ""
        api_key = Prompt.ask(
            f"Enter your [bold]Notion API Key[/bold] (starts with secret_ or ntn_){default_prompt}",
            default=curr_cfg.api_key or "",
            password=True,
        )

    if not database_id:
        default_db = f" [{curr_cfg.database_id}]" if curr_cfg.database_id else ""
        database_id = Prompt.ask(
            f"Enter your [bold]Notion Database ID[/bold] (or full Database URL){default_db}",
            default=curr_cfg.database_id or "",
        )

    clean_db = clean_database_id(database_id)
    work = work_min or curr_cfg.work_minutes
    s_break = short_break_min or curr_cfg.short_break_minutes
    l_break = long_break_min or curr_cfg.long_break_minutes
    n_cycles = cycles or curr_cfg.cycles

    console.print("\n[yellow]⏳ Validating credentials with Notion API...[/yellow]")
    logger = NotionLogger(api_key=api_key, database_id=clean_db)
    is_valid, msg, meta = logger.validate_connection()

    if not is_valid:
        console.print(f"\n[bold red]✗ Validation Failed:[/bold red] {msg}\n")
        raise typer.Exit(code=1)

    console.print(f"[bold green]✓ {msg}[/bold green]")
    if "properties" in meta:
        props_list = ", ".join([f"[cyan]{k}[/cyan] ({v})" for k, v in meta["properties"].items()])
        console.print(f"[dim]Detected Database Columns:[/dim] {props_list}")

    # Save to file
    saved_path = save_config(
        api_key=api_key,
        database_id=clean_db,
        work_minutes=work,
        short_break_minutes=s_break,
        long_break_minutes=l_break,
        cycles=n_cycles,
        use_global=use_global,
    )

    console.print(
        Panel(
            f"[bold green]✓ Configuration successfully saved to:[/bold green]\n"
            f"[cyan]{saved_path.resolve()}[/cyan]\n\n"
            f"• Work Duration: [bold]{work} min[/bold]\n"
            f"• Short Break: [bold]{s_break} min[/bold]\n"
            f"• Long Break: [bold]{l_break} min[/bold]\n"
            f"• Cycles: [bold]{n_cycles}[/bold]\n\n"
            f"[bold]You are all set![/bold] Run [bold green]pomodoro start[/bold green] to begin.",
            title="Setup Complete",
            border_style="green",
        )
    )


@app.command(name="start")
@app.command(name="work")
def start_cmd(
    task: Optional[str] = typer.Option(None, "--task", "-t", help="Task name or focus description"),
    tag: Optional[str] = typer.Option(None, "--tag", "-g", help="Project / Client category"),
    work_min: Optional[int] = typer.Option(None, "--work", "-w", help="Work session duration in minutes"),
    short_break_min: Optional[int] = typer.Option(None, "--short-break", "-s", help="Short break duration in minutes"),
    long_break_min: Optional[int] = typer.Option(None, "--long-break", "-l", help="Long break duration in minutes"),
    cycles: Optional[int] = typer.Option(None, "--cycles", "-c", help="Number of Pomodoro cycles to run"),
    auto_break: bool = typer.Option(True, "--auto-break/--prompt-break", help="Automatically transition into break timers"),
    no_log: bool = typer.Option(False, "--no-log", help="Do not log completed sessions to Notion"),
    silent: bool = typer.Option(False, "--silent", help="Disable audio and terminal notifications"),
    os_notify: bool = typer.Option(False, "--os-notify", help="Also push desktop/OS notifications (disabled by default)"),
):
    """Start a Pomodoro focus session with visual timer and automatic Notion task incrementing."""
    cfg = load_config()
    work_duration = work_min or cfg.work_minutes
    s_break_duration = short_break_min or cfg.short_break_minutes
    l_break_duration = long_break_min or cfg.long_break_minutes
    total_cycles = cycles or cfg.cycles

    if not no_log and not cfg.is_configured:
        console.print(
            "[yellow]⚠️  Notion credentials are not configured yet.[/yellow]\n"
            "Run [bold cyan]pomodoro init[/bold cyan] to connect your Notion database, "
            "or use [bold]--no-log[/bold] to run offline.\n"
        )
        if Confirm.ask("Would you like to configure Notion now?", default=True):
            configure_cmd()
            cfg = load_config()
        else:
            console.print("[dim]Continuing session without Notion logging...[/dim]\n")
            no_log = True

    timer = PomodoroTimer(console=console)
    current_task = task
    current_tag = tag
    current_page_id: Optional[str] = None
    notion_logger: Optional[NotionLogger] = None

    if not no_log and cfg.is_configured:
        notion_logger = NotionLogger(api_key=cfg.api_key, database_id=cfg.database_id)

    for cycle in range(1, total_cycles + 1):
        if not current_task:
            # Interactive task selection from Notion
            if notion_logger:
                with console.status("[cyan]Fetching active tasks from Notion...[/cyan]"):
                    recent_tasks = notion_logger.fetch_recent_tasks(limit=8)

                if recent_tasks:
                    table = Table(title="Select an active task from Notion or enter a new one", border_style="cyan")
                    table.add_column("#", justify="center", style="bold cyan", width=4)
                    table.add_column("Task", style="bold white")
                    table.add_column("Project / Client", style="magenta")
                    table.add_column("🍅", justify="center", style="green")
                    table.add_column("Time", justify="right", style="yellow")
                    table.add_column("Status", style="blue")

                    for idx, t in enumerate(recent_tasks, 1):
                        poms_str = str(t['pomodoros']) if t['pomodoros'] else "-"
                        time_str = f"{t['time_spent']}m" if t['time_spent'] else "-"
                        table.add_row(
                            str(idx),
                            t["title"],
                            t["project"] or "[dim]-[/dim]",
                            poms_str,
                            time_str,
                            t["status"] or "[dim]-[/dim]"
                        )

                    console.print(table)
                    user_input = Prompt.ask(
                        f"[bold green]🍅 Cycle {cycle}/{total_cycles}[/bold green] - Enter number [1-{len(recent_tasks)}] or new task name",
                        default="1"
                    ).strip()

                    if user_input.isdigit() and 1 <= int(user_input) <= len(recent_tasks):
                        selected = recent_tasks[int(user_input) - 1]
                        current_task = selected["title"]
                        current_page_id = selected["id"]
                        current_tag = selected["project"] or current_tag
                    else:
                        current_task = user_input
                        current_page_id = None
                else:
                    current_task = Prompt.ask(
                        f"[bold green]🍅 Cycle {cycle}/{total_cycles}[/bold green] - What are you focusing on?",
                        default="Deep Work",
                    )
            else:
                current_task = Prompt.ask(
                    f"[bold green]🍅 Cycle {cycle}/{total_cycles}[/bold green] - What are you focusing on?",
                    default="Deep Work",
                )

        console.print(f"\n[bold green]▶ Starting Pomodoro Cycle {cycle}/{total_cycles} on '[bold]{current_task}[/bold]'[/bold green]")
        started_at = datetime.now(timezone.utc)

        # Run Work Timer
        result = timer.run(
            duration_minutes=work_duration,
            session_type="Work",
            task_name=current_task,
            cycle_num=cycle,
            total_cycles=total_cycles,
        )

        completed_at = datetime.now(timezone.utc)

        if not silent and result.completed:
            notify_session_end("work", task_name=current_task, console=console, os_notify=os_notify)

        if result.action == "cancelled":
            console.print("[red]Focus session aborted.[/red]")
            break

        # Log / Increment in Notion
        if result.completed and not no_log and notion_logger:
            actual_duration = result.elapsed_minutes if result.interrupted else work_duration
            if actual_duration <= 0:
                actual_duration = 1

            # Check if task was completed
            is_done = Confirm.ask(f"Did you finish '{current_task}'? (Mark status as Done in Notion)", default=False)

            with console.status("[cyan]Updating task in Notion database...[/cyan]"):
                try:
                    res = notion_logger.record_or_increment_task(
                        task_name=current_task,
                        page_id=current_page_id,
                        duration_minutes=actual_duration,
                        pomodoros_count=1,
                        project_client=current_tag,
                        mark_completed=is_done,
                        completed_at=completed_at
                    )
                    action_str = "Created new task" if res["action"] == "created" else "Updated task"
                    console.print(
                        Panel(
                            f"[bold green]✓ {action_str} in Notion![/bold green]\n\n"
                            f"• Task: [bold]{current_task}[/bold]\n"
                            f"• Total Pomodoros: [bold green]🍅 {res['pomodoros']}[/bold green] (+1)\n"
                            f"• Total Time Spent: [bold yellow]{res['time_spent']} min[/bold yellow] (+{actual_duration}m)\n"
                            f"• Status: [bold]{'Done' if is_done else 'In Progress'}[/bold]\n"
                            f"• Link: [link={res['url']}]{res['url']}[/link]",
                            border_style="green",
                        )
                    )
                except NotionError as e:
                    console.print(f"[bold red]✗ Failed to update Notion:[/bold red] {e}")

        # Break handling
        if cycle < total_cycles:
            is_long_break = (cycle % cfg.cycles == 0)
            break_duration = l_break_duration if is_long_break else s_break_duration
            break_type = "Long Break" if is_long_break else "Short Break"

            if not auto_break:
                should_break = Confirm.ask(
                    f"\nReady for {break_type} ({break_duration} min)?",
                    default=True,
                )
                if not should_break:
                    console.print("[dim]Skipping break...[/dim]")
                    continue

            console.print(f"\n[bold cyan]☕ Starting {break_type} ({break_duration} min)...[/bold cyan]")
            break_res = timer.run(
                duration_minutes=break_duration,
                session_type="Long Break" if is_long_break else "Short Break",
                cycle_num=cycle,
                total_cycles=total_cycles,
            )

            if not silent and break_res.completed:
                notify_session_end("long_break" if is_long_break else "short_break", console=console, os_notify=os_notify)

            if break_res.action == "cancelled":
                console.print("[red]Session loop cancelled.[/red]")
                break

            # Prompt for next cycle if not continuous
            if not auto_break:
                ready = Confirm.ask(
                    f"\nReady to begin Cycle {cycle + 1}/{total_cycles}?",
                    default=True,
                )
                if not ready:
                    console.print("[yellow]Pomodoro session ended early.[/yellow]")
                    break

            # Clear task selection for next cycle
            current_task = None
            current_page_id = None

    console.print(
        Panel(
            f"[bold green]🎉 Great job! Completed {total_cycles} Pomodoro cycle(s).[/bold green]\n"
            f"[dim]Time to rest and celebrate your progress![/dim]",
            border_style="green",
        )
    )


@app.command(name="tasks")
@app.command(name="list")
def tasks_cmd(
    limit: int = typer.Option(15, "--limit", "-n", help="Number of tasks to list"),
):
    """List recent tasks from your Notion database with Pomodoros and Time Spent."""
    cfg = load_config()
    if not cfg.is_configured:
        console.print("[bold red]✗ Notion is not configured.[/bold red] Run [cyan]pomodoro init[/cyan] first.")
        raise typer.Exit(code=1)

    logger = NotionLogger(api_key=cfg.api_key, database_id=cfg.database_id)
    with console.status("[cyan]Fetching tasks from Notion...[/cyan]"):
        tasks = logger.fetch_recent_tasks(limit=limit)

    if not tasks:
        console.print("[yellow]No tasks found in the database or could not retrieve tasks.[/yellow]")
        return

    table = Table(title=f"Recent Notion Tasks ({len(tasks)})", border_style="cyan")
    table.add_column("Task", style="bold white")
    table.add_column("Project / Client", style="magenta")
    table.add_column("🍅 Poms", justify="center", style="green")
    table.add_column("Time Spent", justify="right", style="yellow")
    table.add_column("Status", style="blue")

    for t in tasks:
        poms_str = f"🍅 {t['pomodoros']}" if t['pomodoros'] else "-"
        time_str = f"{t['time_spent']}m" if t['time_spent'] else "-"
        table.add_row(
            f"[link={t['url']}]{t['title']}[/link]",
            t["project"] or "[dim]-[/dim]",
            poms_str,
            time_str,
            t["status"] or "[dim]-[/dim]"
        )

    console.print(table)


@app.command(name="break")
def break_cmd(
    minutes: Optional[int] = typer.Option(None, "--minutes", "-m", help="Break duration in minutes"),
    long_break: bool = typer.Option(False, "--long", "-l", help="Run long break duration"),
    silent: bool = typer.Option(False, "--silent", help="Disable audio and terminal notifications"),
    os_notify: bool = typer.Option(False, "--os-notify", help="Also push desktop/OS notifications (disabled by default)"),
):
    """Run an independent break countdown timer."""
    cfg = load_config()
    if minutes is not None:
        duration = minutes
        b_type = "Break"
    elif long_break:
        duration = cfg.long_break_minutes
        b_type = "Long Break"
    else:
        duration = cfg.short_break_minutes
        b_type = "Short Break"

    console.print(f"\n[bold cyan]☕ Starting {b_type} ({duration} min)...[/bold cyan]")
    timer = PomodoroTimer(console=console)
    result = timer.run(duration_minutes=duration, session_type=b_type)

    if not silent and result.completed:
        notify_session_end("long_break" if long_break else "short_break", console=console, os_notify=os_notify)

    if result.completed:
        console.print(f"[bold green]✓ {b_type} finished! Feeling refreshed?[/bold green]")


@app.command(name="log")
def log_cmd(
    task: str = typer.Option(..., "--task", "-t", prompt="Task Name", help="Name of task to log/increment"),
    duration: int = typer.Option(25, "--duration", "-d", help="Duration in minutes to add"),
    pomodoros: int = typer.Option(1, "--pomodoros", "-p", help="Number of Pomodoros to add"),
    tag: Optional[str] = typer.Option(None, "--tag", "-g", help="Project / Client category"),
    status: Optional[str] = typer.Option(None, "--status", help="Session status (e.g. In Progress, Done)"),
    done: bool = typer.Option(False, "--done", help="Mark task status as Done / Completed"),
):
    """Directly log or increment Pomodoros on a task in your Notion database."""
    cfg = load_config()
    if not cfg.is_configured:
        console.print("[bold red]✗ Notion is not configured.[/bold red] Run [cyan]pomodoro init[/cyan] first.")
        raise typer.Exit(code=1)

    logger = NotionLogger(api_key=cfg.api_key, database_id=cfg.database_id)
    with console.status("[cyan]Saving progress to Notion...[/cyan]"):
        try:
            res = logger.record_or_increment_task(
                task_name=task,
                duration_minutes=duration,
                pomodoros_count=pomodoros,
                project_client=tag,
                status=status,
                mark_completed=done,
                completed_at=datetime.now(timezone.utc),
            )
            action_str = "Created new task" if res["action"] == "created" else "Updated task"
            console.print(
                Panel(
                    f"[bold green]✓ {action_str} in Notion![/bold green]\n\n"
                    f"• Task: [bold]{task}[/bold]\n"
                    f"• Total Pomodoros: [bold green]🍅 {res['pomodoros']}[/bold green] (+{pomodoros})\n"
                    f"• Total Time Spent: [bold yellow]{res['time_spent']} min[/bold yellow] (+{duration}m)\n"
                    + (f"• Project/Client: [bold]{tag}[/bold]\n" if tag else "")
                    + f"• Link: [link={res['url']}]{res['url']}[/link]",
                    border_style="green",
                )
            )
        except NotionError as e:
            console.print(f"[bold red]✗ Failed to log session:[/bold red] {e}")
            raise typer.Exit(code=1)


@app.command(name="schema")
@app.command(name="status")
def status_cmd():
    """Inspect current configuration and Notion database property mapping."""
    cfg = load_config()

    table = Table(title="Notion Pomodoro CLI Configuration", border_style="cyan")
    table.add_column("Setting", style="bold white")
    table.add_column("Value", style="cyan")

    table.add_row("Config File", str(cfg.config_source))
    table.add_row("Notion API Key", f"{cfg.api_key[:8]}... (configured)" if cfg.api_key else "[red]Not configured[/red]")
    table.add_row("Database ID", cfg.database_id or "[red]Not configured[/red]")
    table.add_row("Work Duration", f"{cfg.work_minutes} min")
    table.add_row("Short Break", f"{cfg.short_break_minutes} min")
    table.add_row("Long Break", f"{cfg.long_break_minutes} min")
    table.add_row("Default Cycles", f"{cfg.cycles}")

    console.print(table)

    if not cfg.is_configured:
        console.print("\n[yellow]Run [bold]pomodoro init[/bold] to configure your Notion credentials.[/yellow]")
        return

    console.print("\n[yellow]⏳ Testing connection and querying database schema...[/yellow]")
    logger = NotionLogger(api_key=cfg.api_key, database_id=cfg.database_id)
    is_valid, msg, meta = logger.validate_connection()

    if not is_valid:
        console.print(f"[bold red]✗ Connection Error:[/bold red] {msg}")
        return

    console.print(f"[bold green]✓ {msg}[/bold green]\n")

    schema_table = Table(title=f"Database Columns for '{meta.get('title')}'", border_style="green")
    schema_table.add_column("Property Name", style="bold white")
    schema_table.add_column("Type", style="magenta")
    schema_table.add_column("CLI Role", style="green")

    mapping = logger._resolve_property_mapping(meta.get("raw_properties", {}))
    role_by_prop = {}
    for role, prop_info in mapping.items():
        if prop_info:
            role_by_prop[prop_info[0]] = role.replace("_", " ").title()

    for prop_name, prop_type in meta.get("properties", {}).items():
        role = role_by_prop.get(prop_name, "[dim]Ignored / Preserved[/dim]")
        schema_table.add_row(prop_name, prop_type, role)

    console.print(schema_table)


def main():
    """Main entrypoint function."""
    app()


if __name__ == "__main__":
    main()
