import sys
import os
import shutil
import tempfile
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


# ---------------------------------------------------------------------------
# Creation / install
# ---------------------------------------------------------------------------

SKILL_TOOLS = tuple(TOOL_PROJECT_PATHS.keys())


def install_skill(
    *,
    name: str,
    tools: list[str],
    scope: str = "global",
    cwd: Path | None = None,
    description: str = "",
    content: str = "",
    source_dir: Path | None = None,
    source: str | None = None,
    risk: str | None = None,
    date_added: str | None = None,
    overwrite: bool = False,
    link_mode: str = "hardlink",
) -> list[Path]:
    """
    Create/install a skill directory (with SKILL.md) for one or more tools.

    If source_dir is provided, that directory is copied/linked.
    Otherwise, a SKILL.md file is generated using the provided metadata/content.
    """
    cleaned_name = name.strip()
    if not cleaned_name:
        raise ValueError("Skill name cannot be empty.")
    if not tools:
        raise ValueError("At least one tool must be provided.")
    if scope not in {"global", "project"}:
        raise ValueError("scope must be 'global' or 'project'.")
    if link_mode not in {"copy", "hardlink"}:
        raise ValueError("link_mode must be 'copy' or 'hardlink'.")

    unknown = [t for t in tools if t not in SKILL_TOOLS]
    if unknown:
        raise ValueError(
            f"Unsupported tool(s): {', '.join(unknown)}. "
            f"Supported: {', '.join(SKILL_TOOLS)}"
        )

    cwd = (cwd or Path.cwd()).resolve()
    if scope == "project" and not cwd.exists():
        raise ValueError(f"Project directory not found: {cwd}")

    unique_tools = list(dict.fromkeys(tools))
    dest_dirs = [_skill_dest_dir(t, scope=scope, cwd=cwd, skill_name=cleaned_name) for t in unique_tools]

    for dest in dest_dirs:
        if dest.exists():
            if not overwrite:
                raise FileExistsError(f"Destination already exists: {dest}")
            shutil.rmtree(dest)

    for dest in dest_dirs:
        dest.parent.mkdir(parents=True, exist_ok=True)

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    try:
        if source_dir is not None:
            source_skill_dir = source_dir.resolve()
            if not source_skill_dir.is_dir():
                raise ValueError(f"source_dir is not a directory: {source_dir}")
            skill_md = source_skill_dir / "SKILL.md"
            if not skill_md.exists():
                raise ValueError(f"source_dir does not contain SKILL.md: {source_skill_dir}")
        else:
            temp_dir = tempfile.TemporaryDirectory(prefix="skill-reader-")
            source_skill_dir = Path(temp_dir.name) / cleaned_name
            source_skill_dir.mkdir(parents=True, exist_ok=True)
            generated = _render_skill_md(
                name=cleaned_name,
                description=description,
                content=content,
                source=source,
                risk=risk,
                date_added=date_added,
            )
            (source_skill_dir / "SKILL.md").write_text(generated, encoding="utf-8")

        created: list[Path] = []
        shutil.copytree(source_skill_dir, dest_dirs[0], copy_function=shutil.copy2, dirs_exist_ok=False)
        created.append(dest_dirs[0])

        for dest in dest_dirs[1:]:
            if link_mode == "hardlink":
                try:
                    shutil.copytree(source_skill_dir, dest, copy_function=os.link, dirs_exist_ok=False)
                except OSError:
                    shutil.copytree(source_skill_dir, dest, copy_function=shutil.copy2, dirs_exist_ok=False)
            else:
                shutil.copytree(source_skill_dir, dest, copy_function=shutil.copy2, dirs_exist_ok=False)
            created.append(dest)

        return created
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def _skill_dest_dir(tool: str, *, scope: str, cwd: Path, skill_name: str) -> Path:
    if scope == "global":
        base = TOOL_GLOBAL_PATHS[tool]
    else:
        base = cwd / TOOL_PROJECT_PATHS[tool]
    return base / skill_name


def _yaml_line(key: str, value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).replace("\n", " ").strip()
    if not cleaned:
        return None
    escaped = cleaned.replace("\\", "\\\\").replace('"', '\\"')
    return f'{key}: "{escaped}"'


def _render_skill_md(
    *,
    name: str,
    description: str,
    content: str,
    source: str | None,
    risk: str | None,
    date_added: str | None,
) -> str:
    template_body = (
        "## Purpose\n"
        "Explain what this skill does and the outcome it should produce.\n\n"
        "## When To Use\n"
        "- Trigger phrase 1\n"
        "- Trigger phrase 2\n\n"
        "## Inputs\n"
        "- Input A\n"
        "- Input B\n\n"
        "## Steps\n"
        "1. Step one.\n"
        "2. Step two.\n"
        "3. Step three.\n\n"
        "## Output\n"
        "Describe the expected output format and quality bar.\n"
    )

    lines: list[str] = ["---"]
    lines.append(_yaml_line("name", name) or 'name: "unnamed-skill"')
    lines.append(_yaml_line("description", description) or 'description: ""')
    extra = [
        _yaml_line("source", source),
        _yaml_line("risk", risk),
        _yaml_line("date_added", date_added),
    ]
    lines.extend([line for line in extra if line is not None])
    lines.append("---")
    lines.append("")
    lines.append(f"# {name}")
    lines.append("")
    body = content.strip()
    lines.append(body if body else template_body)
    lines.append("")
    return "\n".join(lines)
