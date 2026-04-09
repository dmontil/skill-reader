from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
)

from ..models import SkillEntry, TOOL_ICONS
from ..scanner import delete_skill, scan_all

TOOL_COLORS = {
    "claude":   "bright_blue",
    "windsurf": "bright_green",
    "kiro":     "bright_yellow",
    "codex":    "bright_magenta",
    "cursor":   "bright_cyan",
    "opencode": "bright_white",
    "cline":    "cyan",
    "zed":      "green",
    "amp":      "yellow",
    "copilot":  "blue",
    "amazonq":  "dark_orange",
    "aider":    "magenta",
    "continue": "white",
}


class DeleteModal(ModalScreen[list[str] | None]):
    """Deletion confirmation modal with per-tool selection."""

    DEFAULT_CSS = """
    DeleteModal {
        align: center middle;
    }
    DeleteModal > Vertical {
        width: 60;
        height: auto;
        border: thick $error;
        background: $surface;
        padding: 1 2;
    }
    DeleteModal .modal-title {
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }
    DeleteModal .path-label {
        color: $text-muted;
        margin-left: 2;
    }
    DeleteModal .buttons {
        margin-top: 1;
        align: right middle;
    }
    """

    def __init__(self, entry: SkillEntry) -> None:
        super().__init__()
        self.entry = entry

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Delete skill: {self.entry.name}", classes="modal-title")
            if self.entry.is_hardlinked:
                yield Label("This skill is shared across multiple tools.")
                yield Label("Select which tools to remove it from:")
                for tool, path in zip(self.entry.tools, self.entry.paths):
                    yield Checkbox(
                        f"{TOOL_ICONS.get(tool, tool.upper())}  {tool}",
                        id=f"chk_{tool}",
                        value=True,
                    )
                    yield Label(f"  {path}", classes="path-label")
            else:
                tool = self.entry.tools[0]
                yield Label(f"Tool: {tool}")
                yield Label(f"Path: {self.entry.primary_path}", classes="path-label")
            with Horizontal(classes="buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Delete", variant="error", id="confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        else:
            if self.entry.is_hardlinked:
                selected = [
                    tool
                    for tool in self.entry.tools
                    if self.query_one(f"#chk_{tool}", Checkbox).value
                ]
            else:
                selected = self.entry.tools[:]
            self.dismiss(selected if selected else None)


class DetailPanel(Static):
    """Side panel showing the selected skill's details."""

    DEFAULT_CSS = """
    DetailPanel {
        width: 40;
        border-left: solid $panel;
        padding: 1 2;
        overflow-y: auto;
    }
    DetailPanel .detail-name {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    DetailPanel .detail-label {
        color: $text-muted;
        text-style: italic;
    }
    DetailPanel .detail-value {
        margin-bottom: 1;
    }
    """

    entry: reactive[SkillEntry | None] = reactive(None)

    def render_entry(self, entry: SkillEntry | None) -> str:
        if entry is None:
            return "Select a skill to see its details."

        lines = [
            f"[bold accent]{entry.name}[/]",
            "",
            "[dim]Tools[/]",
            f"  {', '.join(entry.tools)}",
            "",
            "[dim]Scope[/]",
            f"  {entry.scope}",
        ]
        if entry.project:
            lines += ["", "[dim]Project[/]", f"  {entry.project}"]
        if entry.source:
            lines += ["", "[dim]Source[/]", f"  {entry.source}"]
        if entry.risk:
            lines += ["", "[dim]Risk[/]", f"  {entry.risk}"]
        if entry.date_added:
            lines += ["", "[dim]Added[/]", f"  {entry.date_added}"]
        lines += [
            "",
            "[dim]Size[/]",
            f"  {entry.size_kb} KB",
            "",
            "[dim]Hardlinked[/]",
            f"  {'Yes ⬡' if entry.is_hardlinked else 'No'}",
            "",
            "[dim]Description[/]",
            f"  {entry.description or '—'}",
            "",
            "[dim]Paths[/]",
        ]
        for tool, path in zip(entry.tools, entry.paths):
            lines.append(f"  [{TOOL_COLORS.get(tool, 'white')}]{TOOL_ICONS.get(tool, '?')}[/] {path}")

        return "\n".join(lines)

    def watch_entry(self, entry: SkillEntry | None) -> None:
        self.update(self.render_entry(entry))


class SkillReaderApp(App):
    """Skill Reader TUI."""

    TITLE = "Skill Reader"
    SUB_TITLE = "Manage your AI agent skills"
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("d", "delete", "Delete"),
        Binding("f", "focus_filter", "Filter"),
        Binding("escape", "clear_filter", "Clear filter"),
    ]
    DEFAULT_CSS = """
    Screen {
        layout: vertical;
    }
    #toolbar {
        height: 3;
        padding: 0 1;
        background: $panel;
        align: left middle;
    }
    #filter-input {
        width: 30;
        margin-right: 2;
    }
    #scope-select {
        width: 20;
        margin-right: 2;
    }
    #tool-select {
        width: 20;
    }
    #main {
        layout: horizontal;
    }
    #table-container {
        width: 1fr;
    }
    DataTable {
        height: 1fr;
    }
    #stats {
        height: 1;
        background: $panel;
        padding: 0 1;
        color: $text-muted;
    }
    """

    filter_text: reactive[str] = reactive("")
    filter_scope: reactive[str] = reactive("all")
    filter_tool: reactive[str] = reactive("all")
    filter_type: reactive[str] = reactive("all")

    def __init__(self, cwd: Path | None = None) -> None:
        super().__init__()
        self.cwd = cwd or Path.cwd()
        self.all_entries: list[SkillEntry] = []
        self.filtered_entries: list[SkillEntry] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="toolbar"):
            yield Input(placeholder="Filter by name…", id="filter-input")
            yield Select(
                [("All scopes", "all"), ("Global", "global"), ("Project", "project")],
                id="scope-select",
                value="all",
            )
            yield Select(
                [
                    ("All tools", "all"),
                    ("Claude", "claude"),
                    ("Windsurf", "windsurf"),
                    ("Kiro", "kiro"),
                    ("Codex", "codex"),
                    ("Cursor", "cursor"),
                    ("Open Code", "opencode"),
                    ("Cline", "cline"),
                    ("Zed", "zed"),
                    ("Amp", "amp"),
                    ("Copilot", "copilot"),
                    ("Amazon Q", "amazonq"),
                    ("Aider", "aider"),
                ],
                id="tool-select",
                value="all",
            )
            yield Select(
                [("Skills + Rules", "all"), ("Skills", "skill"), ("Rules", "rule")],
                id="type-select",
                value="all",
            )
        with Horizontal(id="main"):
            with Vertical(id="table-container"):
                yield DataTable(id="table", cursor_type="row")
            yield DetailPanel(id="detail")
        yield Static("", id="stats")
        yield Footer()

    def on_mount(self) -> None:
        self._load_skills()
        self._setup_table()
        self._refresh_table()

    def _load_skills(self) -> None:
        self.all_entries = scan_all(self.cwd)

    def _setup_table(self) -> None:
        table = self.query_one("#table", DataTable)
        table.add_columns("Name", "Type", "Tools", "Scope", "Project", "Description")

    def _refresh_table(self) -> None:
        table = self.query_one("#table", DataTable)
        table.clear()

        self.filtered_entries = self._apply_filters()

        for entry in self.filtered_entries:
            tools_str = self._render_tools(entry)
            desc = entry.description[:50] + "…" if len(entry.description) > 50 else entry.description
            type_label = "skill" if entry.entry_type == "skill" else "rule"
            table.add_row(
                ("⬡ " if entry.is_hardlinked else "  ") + entry.name,
                type_label,
                tools_str,
                entry.scope,
                entry.project_display,
                desc,
            )

        self._update_stats()

    def _render_tools(self, entry: SkillEntry) -> str:
        return " ".join(TOOL_ICONS.get(t, t[0].upper()) for t in entry.tools)

    def _apply_filters(self) -> list[SkillEntry]:
        result = self.all_entries

        if self.filter_text:
            txt = self.filter_text.lower()
            result = [e for e in result if txt in e.name.lower() or txt in e.description.lower()]

        if self.filter_scope != "all":
            result = [e for e in result if self.filter_scope in e.scope]

        if self.filter_tool != "all":
            result = [e for e in result if self.filter_tool in e.tools]

        if self.filter_type != "all":
            result = [e for e in result if e.entry_type == self.filter_type]

        return result

    def _update_stats(self) -> None:
        total = len(self.all_entries)
        shown = len(self.filtered_entries)
        hardlinked = sum(1 for e in self.all_entries if e.is_hardlinked)
        tools = {}
        for e in self.all_entries:
            for t in e.tools:
                tools[t] = tools.get(t, 0) + 1
        tool_str = "  ".join(f"{TOOL_ICONS.get(t, t)}:{n}" for t, n in sorted(tools.items()))
        self.query_one("#stats", Static).update(
            f"Showing {shown}/{total} skills  |  Hardlinked: {hardlinked}  |  {tool_str}"
        )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        idx = event.cursor_row
        if 0 <= idx < len(self.filtered_entries):
            detail = self.query_one("#detail", DetailPanel)
            detail.entry = self.filtered_entries[idx]

    def on_input_changed(self, event: Input.Changed) -> None:
        self.filter_text = event.value
        self._refresh_table()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "scope-select":
            self.filter_scope = str(event.value)
        elif event.select.id == "tool-select":
            self.filter_tool = str(event.value)
        elif event.select.id == "type-select":
            self.filter_type = str(event.value)
        self._refresh_table()

    def action_refresh(self) -> None:
        self._load_skills()
        self._refresh_table()

    def action_focus_filter(self) -> None:
        self.query_one("#filter-input", Input).focus()

    def action_clear_filter(self) -> None:
        inp = self.query_one("#filter-input", Input)
        inp.value = ""
        self.query_one("#table", DataTable).focus()

    def action_delete(self) -> None:
        table = self.query_one("#table", DataTable)
        idx = table.cursor_row
        if not (0 <= idx < len(self.filtered_entries)):
            return
        entry = self.filtered_entries[idx]
        self.push_screen(DeleteModal(entry), callback=self._on_delete_confirmed)

    def _on_delete_confirmed(self, tools_to_delete: list[str] | None) -> None:
        if not tools_to_delete:
            return
        table = self.query_one("#table", DataTable)
        idx = table.cursor_row
        if not (0 <= idx < len(self.filtered_entries)):
            return
        entry = self.filtered_entries[idx]
        deleted = delete_skill(entry, tools_to_delete)
        if deleted:
            self._load_skills()
            self._refresh_table()
