import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SkillEntry:
    name: str
    tools: list[str]          # e.g. ["claude", "windsurf"] when hardlinked
    scope: str                # "global" | "project" | "global+project"
    project: str | None       # project name when scope=project
    paths: list[Path]         # one path per tool occurrence
    description: str
    inode: int
    is_hardlinked: bool       # same inode across 2+ tools
    size_kb: float
    entry_type: str = "skill" # "skill" | "rule"
    # Optional metadata (Kiro adds these; others may not)
    source: str | None = None
    risk: str | None = None
    date_added: str | None = None

    @property
    def primary_path(self) -> Path:
        return self.paths[0]

    @property
    def tools_display(self) -> str:
        icons = TOOL_ICONS
        return " ".join(icons.get(t, t[0].upper()) for t in self.tools)

    @property
    def project_display(self) -> str:
        return self.project or "—"


TOOL_ICONS: dict[str, str] = {
    "claude":   "C",
    "windsurf": "W",
    "kiro":     "K",
    "codex":    "X",
    "cursor":   "U",
    "opencode": "O",
    "cline":    "L",
    "zed":      "Z",
    "amp":      "A",
    "copilot":  "G",
    "amazonq":  "Q",
    "aider":    "D",
}


def _win_appdata(key: str = "APPDATA") -> Path:
    val = os.environ.get(key)
    return Path(val) if val else Path.home()


def _xdg_config() -> Path:
    """Return $XDG_CONFIG_HOME or ~/.config on Linux/macOS."""
    val = os.environ.get("XDG_CONFIG_HOME")
    return Path(val) if val else Path.home() / ".config"


def _resolve_tool_global_paths() -> dict[str, list[Path]]:
    """
    Candidate global skill paths per tool, ordered most-likely first.
    Only SKILL.md-based tools are listed here (Open Code shares the format).
    """
    home = Path.home()
    is_win = sys.platform == "win32"

    if is_win:
        appdata = _win_appdata("APPDATA")
        local = _win_appdata("LOCALAPPDATA")
        return {
            "claude": [home / ".claude" / "skills"],
            "windsurf": [
                local / "Codeium" / "windsurf" / "skills",
                appdata / "Codeium" / "windsurf" / "skills",
                home / ".codeium" / "windsurf" / "skills",
            ],
            "kiro": [home / ".kiro" / "skills"],
            "codex": [home / ".codex" / "skills"],
            "cursor": [
                appdata / "Cursor" / "User" / "rules",
                home / ".cursor" / "rules",
            ],
            "opencode": [appdata / "opencode" / "skills"],
        }
    else:
        cfg = _xdg_config()
        return {
            "claude":   [home / ".claude" / "skills"],
            "windsurf": [home / ".codeium" / "windsurf" / "skills"],
            "kiro":     [home / ".kiro" / "skills"],
            "codex":    [home / ".codex" / "skills"],
            "cursor":   [home / ".cursor" / "rules"],
            # Open Code uses XDG_CONFIG_HOME on Linux/macOS
            "opencode": [cfg / "opencode" / "skills"],
        }


def _build_global_paths() -> dict[str, Path]:
    result: dict[str, Path] = {}
    for tool, candidates in _resolve_tool_global_paths().items():
        for c in candidates:
            if c.exists():
                result[tool] = c
                break
        else:
            result[tool] = candidates[0]
    return result


# SKILL.md-based: directories containing a SKILL.md file
TOOL_GLOBAL_PATHS: dict[str, Path] = _build_global_paths()

TOOL_PROJECT_PATHS: dict[str, str] = {
    "claude":   ".claude/skills",
    "windsurf": ".windsurf/skills",
    "kiro":     ".kiro/skills",
    "codex":    ".codex/skills",
    "cursor":   ".cursor/rules",
    "opencode": ".opencode/skills",
}

# Rule files: single files or glob patterns relative to project root.
# These tools don't use SKILL.md directories — they use one file per project.
# Value: list of glob patterns relative to CWD.
TOOL_PROJECT_RULES: dict[str, list[str]] = {
    "cline":   [".clinerules", ".clinerules/*.md"],
    "zed":     [".rules"],
    "amp":     ["AGENTS.md"],
    "copilot": [
        ".github/copilot-instructions.md",
        ".github/instructions/*.instructions.md",
    ],
    "amazonq": [".amazonq/rules/*.md"],
    "aider":   ["CONVENTIONS.md"],
}
