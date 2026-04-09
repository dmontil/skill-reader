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
    # Optional metadata (Kiro adds these; others may not)
    source: str | None = None
    risk: str | None = None
    date_added: str | None = None

    @property
    def primary_path(self) -> Path:
        return self.paths[0]

    @property
    def tools_display(self) -> str:
        icons = {"claude": "C", "windsurf": "W", "kiro": "K", "codex": "X", "cursor": "U"}
        return " ".join(icons.get(t, t[0].upper()) for t in self.tools)

    @property
    def project_display(self) -> str:
        return self.project or "—"


def _win_appdata(key: str = "APPDATA") -> Path:
    """Return a Windows %APPDATA% / %LOCALAPPDATA% path, falling back to home."""
    val = os.environ.get(key)
    return Path(val) if val else Path.home()


def _resolve_tool_global_paths() -> dict[str, list[Path]]:
    """
    Return candidate global skill paths per tool for the current platform.
    Each tool gets a list ordered from most-likely to least-likely.
    The scanner tries them all and uses whichever exists.
    """
    home = Path.home()
    is_win = sys.platform == "win32"

    if is_win:
        appdata = _win_appdata("APPDATA")
        local = _win_appdata("LOCALAPPDATA")
        return {
            # Claude Code CLI stores config in ~/.claude on all platforms
            "claude": [
                home / ".claude" / "skills",
            ],
            # Windsurf is an Electron app; uses LOCALAPPDATA on Windows
            "windsurf": [
                local / "Codeium" / "windsurf" / "skills",
                appdata / "Codeium" / "windsurf" / "skills",
                home / ".codeium" / "windsurf" / "skills",  # fallback
            ],
            # Kiro (Amazon) follows dotfile convention on all platforms
            "kiro": [
                home / ".kiro" / "skills",
            ],
            # Codex CLI follows dotfile convention on all platforms
            "codex": [
                home / ".codex" / "skills",
            ],
            # Cursor is VS Code-based; uses APPDATA on Windows
            "cursor": [
                appdata / "Cursor" / "User" / "rules",
                home / ".cursor" / "rules",  # fallback
            ],
        }
    else:
        # macOS and Linux use dotfiles under home
        return {
            "claude":   [home / ".claude" / "skills"],
            "windsurf": [home / ".codeium" / "windsurf" / "skills"],
            "kiro":     [home / ".kiro" / "skills"],
            "codex":    [home / ".codex" / "skills"],
            "cursor":   [home / ".cursor" / "rules"],
        }


# Resolved at import time — one Path per tool (first candidate that exists,
# or the first candidate if none exist yet so new installs are detected later).
def _build_global_paths() -> dict[str, Path]:
    result: dict[str, Path] = {}
    for tool, candidates in _resolve_tool_global_paths().items():
        for c in candidates:
            if c.exists():
                result[tool] = c
                break
        else:
            result[tool] = candidates[0]  # default to first even if absent
    return result


TOOL_GLOBAL_PATHS: dict[str, Path] = _build_global_paths()

TOOL_PROJECT_PATHS: dict[str, str] = {
    "claude":   ".claude/skills",
    "windsurf": ".windsurf/skills",
    "kiro":     ".kiro/skills",
    "codex":    ".codex/skills",
    "cursor":   ".cursor/rules",
}
