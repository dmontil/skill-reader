import sys
from pathlib import Path

from .models import SkillEntry, TOOL_GLOBAL_PATHS, TOOL_PROJECT_PATHS, TOOL_PROJECT_RULES
from .parser import parse_skill_dir, parse_rule_file


def _file_identity(path: Path) -> int | str:
    """
    Return a hashable identity for a file that works across platforms.

    - macOS/Linux: inode (st_ino). Hardlinks share an inode.
    - Windows: (st_dev, st_ino) on NTFS; resolved path string on FAT32
      where st_ino may be 0.
    """
    stat = path.stat()
    if sys.platform != "win32":
        return stat.st_ino
    if stat.st_ino != 0:
        return (stat.st_dev, stat.st_ino)
    return str(path.resolve())


def scan_all(cwd: Path | None = None) -> list[SkillEntry]:
    """
    Discover all skills and rules on the system:
      - SKILL.md-based: global paths + project paths relative to cwd
      - Rule files: project-level single files (Cline, Zed, Copilot, etc.)
    """
    cwd = (cwd or Path.cwd()).resolve()
    if not cwd.exists():
        raise FileNotFoundError(f"Directory not found: {cwd}")
    entries: list[SkillEntry] = []
    entries.extend(_scan_skills(cwd))
    entries.extend(_scan_rules(cwd))
    return sorted(entries, key=lambda e: e.name.lower())


# ---------------------------------------------------------------------------
# SKILL.md-based scanning
# ---------------------------------------------------------------------------

def _scan_skills(cwd: Path) -> list[SkillEntry]:
    # identity_key → list of (tool, scope, project_name, skill_dir)
    identity_map: dict[int | str, list[tuple[str, str, str | None, Path]]] = {}

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

    return _build_skill_entries(identity_map)


def _build_skill_entries(
    identity_map: dict[int | str, list[tuple[str, str, str | None, Path]]]
) -> list[SkillEntry]:
    entries: list[SkillEntry] = []
    for key, occurrences in identity_map.items():
        first_path = occurrences[0][3]
        meta = parse_skill_dir(first_path)

        tools = list(dict.fromkeys(o[0] for o in occurrences))
        paths = [o[3] for o in occurrences]
        scopes = list(dict.fromkeys(o[1] for o in occurrences))
        scope = scopes[0] if len(scopes) == 1 else "global+project"
        project = next((o[2] for o in occurrences if o[2]), None)
        inode = key if isinstance(key, int) else 0

        entries.append(SkillEntry(
            name=meta["name"],
            tools=tools,
            scope=scope,
            project=project,
            paths=paths,
            description=meta["description"],
            inode=inode,
            is_hardlinked=len(tools) > 1,
            size_kb=meta["size_kb"],
            entry_type="skill",
            source=meta["source"],
            risk=meta["risk"],
            date_added=meta["date_added"],
        ))
    return entries


# ---------------------------------------------------------------------------
# Rule file scanning (single-file tools)
# ---------------------------------------------------------------------------

def _scan_rules(cwd: Path) -> list[SkillEntry]:
    entries: list[SkillEntry] = []
    seen: set[str] = set()  # resolved path strings to avoid duplicates

    for tool, patterns in TOOL_PROJECT_RULES.items():
        for pattern in patterns:
            for rule_file in sorted(cwd.glob(pattern)):
                if not rule_file.is_file():
                    continue
                resolved = str(rule_file.resolve())
                if resolved in seen:
                    continue
                seen.add(resolved)

                meta = parse_rule_file(rule_file)
                inode = meta["inode"]
                project_name = cwd.name

                entries.append(SkillEntry(
                    name=meta["name"],
                    tools=[tool],
                    scope="project",
                    project=project_name,
                    paths=[rule_file],
                    description=meta["description"],
                    inode=inode,
                    is_hardlinked=False,
                    size_kb=meta["size_kb"],
                    entry_type="rule",
                ))
    return entries


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------

def delete_skill(entry: SkillEntry, tools_to_delete: list[str]) -> list[Path]:
    """
    Delete the skill directory (or rule file) for the specified tools.
    Returns the paths that were deleted.
    """
    import shutil

    deleted: list[Path] = []
    # Iterate by index so tools[i] and paths[i] are always in sync.
    for i, tool in enumerate(entry.tools):
        if tool not in tools_to_delete:
            continue
        path = entry.paths[i]
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        deleted.append(path)
    return deleted
