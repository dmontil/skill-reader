from pathlib import Path

import frontmatter


def parse_skill_dir(skill_dir: Path) -> dict:
    """
    Lee el SKILL.md de un directorio de skill y devuelve sus metadatos.
    Soporta el formato de Claude, Windsurf, Kiro y Codex.
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return _fallback_metadata(skill_dir)

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
        return _fallback_metadata(skill_dir)


def _fallback_metadata(skill_dir: Path) -> dict:
    return {
        "name": skill_dir.name,
        "description": "",
        "source": None,
        "risk": None,
        "date_added": None,
        "inode": 0,
        "size_kb": 0.0,
    }


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[:max_len] + "…"
