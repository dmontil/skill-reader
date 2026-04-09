from pathlib import Path

import frontmatter


def parse_skill_dir(skill_dir: Path) -> dict:
    """
    Read SKILL.md from a skill directory and return its metadata.
    Supports the format used by Claude, Windsurf, Kiro, Codex, and Open Code.
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return _fallback_metadata(skill_dir.name)

    try:
        post = frontmatter.load(str(skill_md))
        stat = skill_md.stat()
        return {
            "name": post.get("name") or skill_dir.name,
            "description": _truncate(str(post.get("description") or ""), 200),
            "source": post.get("source"),
            "risk": post.get("risk"),
            "date_added": post.get("date_added"),
            "inode": stat.st_ino,
            "size_kb": round(stat.st_size / 1024, 1),
        }
    except Exception:
        return _fallback_metadata(skill_dir.name)


def parse_rule_file(rule_file: Path) -> dict:
    """
    Parse a single-file rule (e.g. .clinerules, AGENTS.md, .rules).
    Extracts name from filename and description from the first paragraph.
    """
    name = rule_file.stem.lstrip(".")  # ".clinerules" → "clinerules"
    if not name:
        name = rule_file.name

    description = ""
    size_kb = 0.0
    inode = 0

    try:
        stat = rule_file.stat()
        size_kb = round(stat.st_size / 1024, 1)
        inode = stat.st_ino

        text = rule_file.read_text(encoding="utf-8", errors="replace")

        # Try frontmatter first
        try:
            post = frontmatter.loads(text)
            fm_desc = post.get("description") or post.get("title") or ""
            if fm_desc:
                description = _truncate(str(fm_desc), 200)
            else:
                description = _first_paragraph(post.content)
        except Exception:
            description = _first_paragraph(text)

    except Exception:
        pass

    return {
        "name": name,
        "description": description,
        "source": None,
        "risk": None,
        "date_added": None,
        "inode": inode,
        "size_kb": size_kb,
    }


def _first_paragraph(text: str) -> str:
    """Extract the first non-empty, non-heading paragraph from markdown text."""
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("---"):
            return _truncate(line, 200)
    return ""


def _fallback_metadata(name: str) -> dict:
    return {
        "name": name,
        "description": "",
        "source": None,
        "risk": None,
        "date_added": None,
        "inode": 0,
        "size_kb": 0.0,
    }


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[:max_len] + "…"
