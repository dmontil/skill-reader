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
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()

from .models import TOOL_ICONS

TOOL_COLORS = {
    "claude":   "blue",
    "windsurf": "green",
    "kiro":     "yellow",
    "codex":    "magenta",
    "cursor":   "cyan",
    "opencode": "white",
    "cline":    "cyan",
    "zed":      "green",
    "amp":      "yellow",
    "copilot":  "blue",
    "amazonq":  "bright_red",
    "aider":    "magenta",
    "continue": "white",
}


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
    tool: Optional[str] = typer.Option(None, "--tool", "-t", help="Filter by tool (claude|windsurf|kiro|codex|cursor|opencode|cline|zed|amp|copilot|amazonq|aider)"),
    scope: Optional[str] = typer.Option(None, "--scope", "-s", help="Filter by scope (global|project)"),
    type_filter: Optional[str] = typer.Option(None, "--type", help="Filter by type (skill|rule)"),
    cwd: Optional[Path] = typer.Option(None, "--cwd", "-c", help="Project directory to scan"),
):
    """List all skills and rules found on the system."""
    entries = scan_all(cwd)

    if tool:
        entries = [e for e in entries if tool in e.tools]
    if scope:
        entries = [e for e in entries if scope in e.scope]
    if type_filter:
        entries = [e for e in entries if e.entry_type == type_filter]

    if not entries:
        console.print("[dim]No skills or rules found.[/dim]")
        raise typer.Exit()

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    table.add_column("Name", style="bold", min_width=20)
    table.add_column("Type", min_width=5)
    table.add_column("Tools", min_width=8)
    table.add_column("Scope", min_width=8)
    table.add_column("Project", min_width=12)
    table.add_column("Description")

    for e in entries:
        desc = e.description[:60] + "…" if len(e.description) > 60 else e.description
        type_label = "[dim]skill[/dim]" if e.entry_type == "skill" else "[yellow]rule[/yellow]"
        table.add_row(
            e.name,
            type_label,
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
    no_content: bool = typer.Option(False, "--no-content", help="Skip printing file content"),
    cwd: Optional[Path] = typer.Option(None, "--cwd", "-c"),
):
    """Show full metadata and content of a skill or rule file."""
    entries = scan_all(cwd)
    matches = [e for e in entries if e.name.lower() == name.lower()]

    if not matches:
        console.print(f"[red]Skill '{name}' not found.[/red]")
        raise typer.Exit(1)

    e = matches[0]

    # --- Metadata block ---
    console.print(f"\n[bold]{e.name}[/bold]  [dim]{e.entry_type}[/dim]")
    console.rule(style="dim")
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
    console.print("\n  Paths:")
    for tool, path in zip(e.tools, e.paths):
        color = TOOL_COLORS.get(tool, "white")
        console.print(f"    [{color}]{TOOL_ICONS.get(tool, '?')}[/{color}] {path}")

    if no_content:
        return

    # --- File content ---
    content_path = _resolve_content_path(e)
    if content_path is None or not content_path.exists():
        return

    try:
        text = content_path.read_text(encoding="utf-8", errors="replace")
    except Exception as ex:
        console.print(f"\n[red]Could not read file: {ex}[/red]")
        return

    console.print()
    console.rule("[dim]Content[/dim]", style="dim")
    # Use Rich Markdown rendering for .md files
    if content_path.suffix.lower() in (".md", ".markdown", ""):
        from rich.markdown import Markdown
        console.print(Markdown(text))
    else:
        console.print(text)
    console.rule(style="dim")


def _resolve_content_path(e: "SkillEntry") -> "Path | None":
    """Return the file to display for inspect: SKILL.md for skills, the file itself for rules."""
    path = e.primary_path
    if e.entry_type == "skill":
        skill_md = path / "SKILL.md"
        return skill_md if skill_md.exists() else None
    # rule: path is the file itself
    return path if path.is_file() else None


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
    skills = sum(1 for e in entries if e.entry_type == "skill")
    rules = sum(1 for e in entries if e.entry_type == "rule")
    hardlinked = sum(1 for e in entries if e.is_hardlinked)
    tools: dict[str, int] = {}
    for e in entries:
        for t in e.tools:
            tools[t] = tools.get(t, 0) + 1
    tool_str = "  ".join(
        f"[{TOOL_COLORS.get(t, 'white')}]{TOOL_ICONS.get(t, t)}:{n}[/{TOOL_COLORS.get(t, 'white')}]"
        for t, n in sorted(tools.items())
    )
    console.print(f"\n[dim]Skills: {skills}  Rules: {rules}  |  Hardlinked: {hardlinked}  |  {tool_str}[/dim]")


if __name__ == "__main__":
    app()
