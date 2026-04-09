from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SkillEntry:
    name: str
    tools: list[str]          # ["claude", "windsurf"] — múltiples si hardlink
    scope: str                # "global" | "project"
    project: str | None       # nombre del proyecto si scope=project
    paths: list[Path]         # una por tool (comparten inode si hardlink)
    description: str
    inode: int
    is_hardlinked: bool       # mismo inode en 2+ herramientas
    size_kb: float
    # Metadatos opcionales (Kiro los añade, otros no)
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


TOOL_GLOBAL_PATHS: dict[str, Path] = {
    "claude":   Path.home() / ".claude" / "skills",
    "windsurf": Path.home() / ".codeium" / "windsurf" / "skills",
    "kiro":     Path.home() / ".kiro" / "skills",
    "codex":    Path.home() / ".codex" / "skills",
    "cursor":   Path.home() / ".cursor" / "rules",
}

TOOL_PROJECT_PATHS: dict[str, str] = {
    "claude":   ".claude/skills",
    "windsurf": ".windsurf/skills",
    "kiro":     ".kiro/skills",
    "codex":    ".codex/skills",
    "cursor":   ".cursor/rules",
}
