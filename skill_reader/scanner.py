from pathlib import Path

from .models import SkillEntry, TOOL_GLOBAL_PATHS, TOOL_PROJECT_PATHS
from .parser import parse_skill_dir


def scan_all(cwd: Path | None = None) -> list[SkillEntry]:
    """
    Discover all skills on the system:
      - Fixed global paths per tool
      - Project paths relative to cwd (or Path.cwd())

    Groups by inode to detect hardlinks between tools.
    """
    cwd = cwd or Path.cwd()

    # inode → list of (tool, scope, project_name, path)
    inode_map: dict[int, list[tuple[str, str, str | None, Path]]] = {}

    # --- Global paths ---
    for tool, base in TOOL_GLOBAL_PATHS.items():
        if not base.exists():
            continue
        for skill_dir in sorted(base.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            inode = skill_md.stat().st_ino
            inode_map.setdefault(inode, []).append((tool, "global", None, skill_dir))

    # --- Project paths (from cwd) ---
    for tool, rel in TOOL_PROJECT_PATHS.items():
        base = cwd / rel
        if not base.exists():
            continue
        project_name = cwd.name
        for skill_dir in sorted(base.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            inode = skill_md.stat().st_ino
            inode_map.setdefault(inode, []).append(
                (tool, "project", project_name, skill_dir)
            )

    return _build_entries(inode_map)


def _build_entries(
    inode_map: dict[int, list[tuple[str, str, str | None, Path]]]
) -> list[SkillEntry]:
    entries: list[SkillEntry] = []

    for inode, occurrences in inode_map.items():
        # Parsear metadatos desde la primera ocurrencia
        first_path = occurrences[0][3]
        meta = parse_skill_dir(first_path)

        tools = list(dict.fromkeys(o[0] for o in occurrences))  # ordered, no duplicates
        paths = [o[3] for o in occurrences]

        # scope: if both global and project exist, show both
        scopes = list(dict.fromkeys(o[1] for o in occurrences))
        scope = scopes[0] if len(scopes) == 1 else "global+project"

        project = next((o[2] for o in occurrences if o[2]), None)

        entries.append(
            SkillEntry(
                name=meta["name"],
                tools=tools,
                scope=scope,
                project=project,
                paths=paths,
                description=meta["description"],
                inode=inode,
                is_hardlinked=len(tools) > 1,
                size_kb=meta["size_kb"],
                source=meta["source"],
                risk=meta["risk"],
                date_added=meta["date_added"],
            )
        )

    return sorted(entries, key=lambda e: e.name.lower())


def delete_skill(entry: SkillEntry, tools_to_delete: list[str]) -> list[Path]:
    """
    Delete the skill directory for the specified tools.
    Returns the paths that were deleted.
    """
    import shutil

    deleted: list[Path] = []
    for tool, path in zip(
        [t for t in entry.tools if t in tools_to_delete],
        [p for t, p in zip(entry.tools, entry.paths) if t in tools_to_delete],
    ):
        if path.exists():
            shutil.rmtree(path)
            deleted.append(path)
    return deleted
