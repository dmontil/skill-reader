from pathlib import Path
from typing import Optional
import os
import subprocess

import typer
from rich.console import Console
from rich.table import Table
from rich import box

from .scanner import scan_all, delete_skill, install_skill
from .models import SkillEntry, TOOL_GLOBAL_PATHS, TOOL_PROJECT_PATHS


def _validate_cwd(cwd: Path | None) -> None:
    if cwd is not None and not cwd.exists():
        console.print(f"[red]Error: directory not found: {cwd}[/red]")
        raise typer.Exit(1)

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
    _validate_cwd(cwd)
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
    _validate_cwd(cwd)
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
    _validate_cwd(cwd)
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
    _validate_cwd(cwd)
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
    _validate_cwd(cwd)
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


@app.command("add")
def add_cmd(
    name: str = typer.Argument(..., help="Skill name (directory name)"),
    tool: list[str] = typer.Option(
        ...,
        "--tool",
        "-t",
        help="Target tool(s). Repeat flag for multiple tools.",
    ),
    scope: str = typer.Option("global", "--scope", "-s", help="Install scope: global|project"),
    description: str = typer.Option("", "--description", "-d", help="Frontmatter description"),
    content: str = typer.Option("", "--content", help="Body content to write in SKILL.md"),
    content_file: Optional[Path] = typer.Option(None, "--content-file", help="Read skill body content from file"),
    source_dir: Optional[Path] = typer.Option(None, "--from-dir", help="Copy/import from an existing skill directory"),
    link_mode: str = typer.Option("hardlink", "--link-mode", help="copy|hardlink when installing to multiple tools"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing skill directory"),
    source: Optional[str] = typer.Option(None, "--source", help="Optional metadata field"),
    risk: Optional[str] = typer.Option(None, "--risk", help="Optional metadata field"),
    date_added: Optional[str] = typer.Option(None, "--date-added", help="Optional metadata field"),
    cwd: Optional[Path] = typer.Option(None, "--cwd", "-c", help="Project directory for project scope"),
):
    """Create or import a skill and install it to one or more tools."""
    _validate_cwd(cwd)
    chosen_cwd = (cwd or Path.cwd()).resolve()

    if scope not in {"global", "project"}:
        console.print("[red]Error: --scope must be 'global' or 'project'.[/red]")
        raise typer.Exit(1)
    if link_mode not in {"copy", "hardlink"}:
        console.print("[red]Error: --link-mode must be 'copy' or 'hardlink'.[/red]")
        raise typer.Exit(1)
    if source_dir and (content or content_file):
        console.print("[red]Error: --from-dir cannot be used with --content or --content-file.[/red]")
        raise typer.Exit(1)

    body = content
    if content_file is not None:
        if not content_file.exists():
            console.print(f"[red]Error: content file not found: {content_file}[/red]")
            raise typer.Exit(1)
        try:
            body = content_file.read_text(encoding="utf-8", errors="replace")
        except Exception as ex:
            console.print(f"[red]Error reading content file: {ex}[/red]")
            raise typer.Exit(1)

    try:
        created = install_skill(
            name=name,
            tools=tool,
            scope=scope,
            cwd=chosen_cwd,
            description=description,
            content=body,
            source_dir=source_dir,
            source=source,
            risk=risk,
            date_added=date_added,
            overwrite=overwrite,
            link_mode=link_mode,
        )
    except Exception as ex:
        console.print(f"[red]Error: {ex}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Installed skill '{name}' to {len(created)} location(s):[/green]")
    for path in created:
        console.print(f"  [green]→[/green] {path}")


@app.command("init")
def init_cmd(
    name: str = typer.Argument(..., help="Skill name"),
    tool: str = typer.Option("codex", "--tool", "-t", help="Target tool"),
    description: str = typer.Option("", "--description", "-d"),
    cwd: Optional[Path] = typer.Option(None, "--cwd", "-c", help="Project directory"),
):
    """Quick-start: create a project skill with default template and open editor."""
    _validate_cwd(cwd)
    chosen_cwd = (cwd or Path.cwd()).resolve()
    try:
        created = install_skill(
            name=name,
            tools=[tool],
            scope="project",
            cwd=chosen_cwd,
            description=description,
            content="",
            overwrite=False,
            link_mode="copy",
        )
    except Exception as ex:
        console.print(f"[red]Error: {ex}[/red]")
        raise typer.Exit(1)

    skill_md = created[0] / "SKILL.md"
    console.print(f"[green]Created:[/green] {skill_md}")
    _open_in_editor(skill_md)


@app.command("edit")
def edit_cmd(
    name: str = typer.Argument(..., help="Skill name"),
    cwd: Optional[Path] = typer.Option(None, "--cwd", "-c"),
):
    """Open SKILL.md for the selected skill in $EDITOR."""
    _validate_cwd(cwd)
    entries = scan_all(cwd)
    matches = [e for e in entries if e.name.lower() == name.lower()]
    if not matches:
        console.print(f"[red]Skill '{name}' not found.[/red]")
        raise typer.Exit(1)
    content_path = _resolve_content_path(matches[0])
    if content_path is None:
        console.print(f"[red]No editable content found for '{name}'.[/red]")
        raise typer.Exit(1)
    _open_in_editor(content_path)


def _open_in_editor(path: Path) -> None:
    editor = os.environ.get("EDITOR")
    if editor:
        cmd = [editor, str(path)]
        try:
            subprocess.run(cmd, check=False)
        except Exception as ex:
            console.print(f"[yellow]Could not launch $EDITOR ({editor}): {ex}[/yellow]")
    else:
        console.print(f"[dim]Set $EDITOR to open automatically. File: {path}[/dim]")


@app.command("doctor")
def doctor_cmd(
    cwd: Optional[Path] = typer.Option(None, "--cwd", "-c", help="Project directory for project-scope checks"),
):
    """Check skill paths, existence, and write access."""
    _validate_cwd(cwd)
    chosen_cwd = (cwd or Path.cwd()).resolve()

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    table.add_column("Tool", min_width=10)
    table.add_column("Scope", min_width=8)
    table.add_column("Path")
    table.add_column("Exists")
    table.add_column("Writable")

    def _writable(path: Path) -> bool:
        target = path if path.exists() else path.parent
        return os.access(target, os.W_OK)

    for tool, path in TOOL_GLOBAL_PATHS.items():
        table.add_row(
            tool,
            "global",
            str(path),
            "yes" if path.exists() else "no",
            "yes" if _writable(path) else "no",
        )

    for tool, rel in TOOL_PROJECT_PATHS.items():
        path = chosen_cwd / rel
        table.add_row(
            tool,
            "project",
            str(path),
            "yes" if path.exists() else "no",
            "yes" if _writable(path) else "no",
        )

    console.print(table)


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
