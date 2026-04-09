import sys
from pathlib import Path

from .models import SkillEntry, TOOL_GLOBAL_PATHS, TOOL_PROJECT_PATHS
from .parser import parse_skill_dir


def _file_identity(path: Path) -> int | str:
    """
    Return a hashable identity key for a file that works across platforms.

    - On macOS/Linux: use the inode number (st_ino). Hardlinks share an inode.
    - On Windows: st_ino is unreliable (may be 0 on FAT32, or non-unique).
      Fall back to the resolved absolute path as a string so that at minimum
      the same path from two tools is deduplicated. True hardlink detection
      on Windows requires the win32 API and is left as a future improvement.
    """
    stat = path.stat()
    if sys.platform != "win32":
        return stat.st_ino
    # Windows: use (volume serial, file index) when available, else resolved path
    file_index = getattr(stat, "st_file_attributes", 0)
    if stat.st_ino != 0:
        return (stat.st_dev, stat.st_ino)
    return str(path.resolve())


def scan_all(cwd: Path | None = None) -> list[SkillEntry]:
    """
    Discover all skills on the system:
      - Fixed global paths per tool (platform-aware)
      - Project paths relative to cwd (or Path.cwd())

    Groups by file identity to detect hardlinks between tools.
    """
    cwd = cwd or Path.cwd()

    # identity_key → list of (tool, scope, project_name, path)
    identity_map: dict[int | str, list[tuple[str, str, str | None, Path]]] = {}

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
            key = _file_identity(skill_md)
            identity_map.setdefault(key, []).append((tool, "global", None, skill_dir))

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
            key = _file_identity(skill_md)
            identity_map.setdefault(key, []).append(
                (tool, "project", project_name, skill_dir)
            )

    return _build_entries(identity_map)


def _build_entries(
    identity_map: dict[int | str, list[tuple[str, str, str | None, Path]]]
) -> list[SkillEntry]:
    entries: list[SkillEntry] = []

    for key, occurrences in identity_map.items():
        first_path = occurrences[0][3]
        meta = parse_skill_dir(first_path)

        tools = list(dict.fromkeys(o[0] for o in occurrences))  # ordered, no duplicates
        paths = [o[3] for o in occurrences]

        # scope: if both global and project exist, show both
        scopes = list(dict.fromkeys(o[1] for o in occurrences))
        scope = scopes[0] if len(scopes) == 1 else "global+project"

        project = next((o[2] for o in occurrences if o[2]), None)

        # inode for display — use 0 on Windows when unavailable
        inode = key if isinstance(key, int) else 0

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
