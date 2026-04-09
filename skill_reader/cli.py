from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import box

from .scanner import scan_all, delete_skill
from .models import SkillEntry

app = typer.Typer(
    name="skill-reader",
    help="Manage AI agent skills (Claude, Windsurf, Kiro, Codex).",
    add_completion=False,
)
console = Console()

TOOL_COLORS = {
    "claude":   "blue",
    "windsurf": "green",
    "kiro":     "yellow",
    "codex":    "magenta",
    "cursor":   "cyan",
}
TOOL_ICONS = {"claude": "C", "windsurf": "W", "kiro": "K", "codex": "X", "cursor": "U"}


def _colored_tools(entry: SkillEntry) -> str:
    parts = []
    for t in entry.tools:
        color = TOOL_COLORS.get(t, "white")
        icon = TOOL_ICONS.get(t, t[0].upper())
        parts.append(f"[{color}]{icon}[/{color}]")
    prefix = "⬡ " if entry.is_hardlinked else "  "
    return prefix + " ".join(parts)


@app.command("ui")
def launch_ui(
    cwd: Optional[Path] = typer.Option(None, "--cwd", "-c", help="Project directory to scan"),
):
    """Launch the interactive TUI."""
    from .tui.app import SkillReaderApp
    SkillReaderApp(cwd=cwd).run()


@app.command("list")
def list_skills(
    tool: Optional[str] = typer.Option(None, "--tool", "-t", help="Filter by tool (claude|windsurf|kiro|codex|cursor)"),
    scope: Optional[str] = typer.Option(None, "--scope", "-s", help="Filter by scope (global|project)"),
    cwd: Optional[Path] = typer.Option(None, "--cwd", "-c", help="Project directory to scan"),
):
    """List all skills found on the system."""
    entries = scan_all(cwd)

    if tool:
        entries = [e for e in entries if tool in e.tools]
    if scope:
        entries = [e for e in entries if scope in e.scope]

    if not entries:
        console.print("[dim]No skills found.[/dim]")
        raise typer.Exit()

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    table.add_column("Name", style="bold", min_width=20)
    table.add_column("Tools", min_width=8)
    table.add_column("Scope", min_width=8)
    table.add_column("Project", min_width=12)
    table.add_column("Description")

    for e in entries:
        desc = e.description[:60] + "…" if len(e.description) > 60 else e.description
        table.add_row(
            e.name,
            _colored_tools(e),
            e.scope,
            e.project_display,
            f"[dim]{desc}[/dim]",
        )

    console.print(table)
    _print_summary(entries)


@app.command("inspect")
def inspect_skill(
    name: str = typer.Argument(..., help="Skill name"),
    cwd: Optional[Path] = typer.Option(None, "--cwd", "-c"),
):
    """Show full details of a skill."""
    entries = scan_all(cwd)
    matches = [e for e in entries if e.name.lower() == name.lower()]

    if not matches:
        console.print(f"[red]Skill '{name}' not found.[/red]")
        raise typer.Exit(1)

    e = matches[0]
    console.print(f"\n[bold accent]{e.name}[/bold accent]")
    console.print(f"  Tools        : {', '.join(e.tools)}")
    console.print(f"  Scope        : {e.scope}")
    if e.project:
        console.print(f"  Project      : {e.project}")
    if e.source:
        console.print(f"  Source       : {e.source}")
    if e.risk:
        console.print(f"  Risk         : {e.risk}")
    if e.date_added:
        console.print(f"  Added        : {e.date_added}")
    console.print(f"  Size         : {e.size_kb} KB")
    console.print(f"  Hardlinked   : {'Yes ⬡' if e.is_hardlinked else 'No'}")
    console.print(f"\n  Description:\n  {e.description}")
    console.print("\n  Paths:")
    for tool, path in zip(e.tools, e.paths):
        color = TOOL_COLORS.get(tool, "white")
        console.print(f"    [{color}]{TOOL_ICONS.get(tool, '?')}[/{color}] {path}")


@app.command("duplicates")
def show_duplicates(
    cwd: Optional[Path] = typer.Option(None, "--cwd", "-c"),
):
    """Show skills that appear in more than one tool (hardlinked or copied)."""
    entries = scan_all(cwd)
    dups = [e for e in entries if len(e.tools) > 1]

    if not dups:
        console.print("[green]No skills shared between tools.[/green]")
        raise typer.Exit()

    console.print(f"[bold]{len(dups)} skills shared between tools:[/bold]\n")
    for e in dups:
        console.print(f"  [bold]{e.name}[/bold]  {_colored_tools(e)}")
        for tool, path in zip(e.tools, e.paths):
            color = TOOL_COLORS.get(tool, "white")
            console.print(f"    [{color}]→[/{color}] {path}")
        console.print()


@app.command("delete")
def delete_cmd(
    name: str = typer.Argument(..., help="Skill name to delete"),
    tool: Optional[str] = typer.Option(None, "--tool", "-t", help="Delete only from this tool"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    cwd: Optional[Path] = typer.Option(None, "--cwd", "-c"),
):
    """Delete a skill from the system."""
    entries = scan_all(cwd)
    matches = [e for e in entries if e.name.lower() == name.lower()]

    if not matches:
        console.print(f"[red]Skill '{name}' not found.[/red]")
        raise typer.Exit(1)

    e = matches[0]
    tools_to_delete = [tool] if tool else e.tools

    invalid = [t for t in tools_to_delete if t not in e.tools]
    if invalid:
        console.print(f"[red]Skill '{name}' is not installed in: {', '.join(invalid)}[/red]")
        raise typer.Exit(1)

    console.print(f"\nWill delete [bold]{e.name}[/bold] from: {', '.join(tools_to_delete)}")
    for t in tools_to_delete:
        idx = e.tools.index(t)
        console.print(f"  [red]→[/red] {e.paths[idx]}")

    if not yes:
        typer.confirm("\nConfirm?", abort=True)

    deleted = delete_skill(e, tools_to_delete)
    for p in deleted:
        console.print(f"[green]Deleted:[/green] {p}")


def _print_summary(entries: list[SkillEntry]) -> None:
    total = len(entries)
    hardlinked = sum(1 for e in entries if e.is_hardlinked)
    tools: dict[str, int] = {}
    for e in entries:
        for t in e.tools:
            tools[t] = tools.get(t, 0) + 1
    tool_str = "  ".join(
        f"[{TOOL_COLORS.get(t, 'white')}]{TOOL_ICONS.get(t, t)}:{n}[/{TOOL_COLORS.get(t, 'white')}]"
        for t, n in sorted(tools.items())
    )
    console.print(f"\n[dim]Total: {total}  |  Hardlinked: {hardlinked}  |  {tool_str}[/dim]")


if __name__ == "__main__":
    app()
