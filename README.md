# Skill Reader

A CLI + TUI tool to manage AI agent skills installed on your machine — across Claude, Windsurf, Kiro, Codex, and Cursor.

## The Problem

As you install skills from the internet, you quickly lose track of:
- Which skills you actually have installed
- Whether a skill is global or tied to a specific project
- Which AI tool each skill belongs to
- Skills duplicated (or hardlinked) between tools like Claude and Windsurf

Skill Reader gives you a single place to see, filter, inspect, and delete all your skills.

## Features

- **Multi-tool scanning** — discovers skills from Claude, Windsurf, Kiro, Codex, and Cursor in one pass
- **Global + project scope** — scans both `~/.<tool>/skills/` and `./<tool>/skills/` relative to your working directory
- **Hardlink detection** — identifies when the same file is shared between tools (e.g. Claude ↔ Windsurf share skills via hardlinks), and warns you before deleting
- **Interactive TUI** — filterable table with a detail panel and deletion modal
- **CLI commands** — scriptable `list`, `inspect`, `duplicates`, `delete`

## Installation

Requires Python 3.11+.

```bash
pipx install git+https://github.com/dmontil/skill-reader.git
```

Or clone and install in editable mode for development:

```bash
git clone https://github.com/dmontil/skill-reader.git
cd skill-reader
pipx install -e .
```

## Usage

### Interactive TUI

```bash
skill-reader ui
```

The TUI opens a full-screen interface with:
- A filterable table of all your skills
- A detail panel on the right showing metadata, description, and paths
- A deletion modal that handles hardlinked skills safely

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| `f` | Focus the filter input |
| `Esc` | Clear filter / return to table |
| `d` | Delete selected skill |
| `r` | Refresh (re-scan) |
| `q` | Quit |

### CLI Commands

**List all skills:**
```bash
skill-reader list
```

**Filter by tool:**
```bash
skill-reader list --tool claude
skill-reader list --tool windsurf
skill-reader list --tool kiro
skill-reader list --tool codex
skill-reader list --tool cursor
```

**Filter by scope:**
```bash
skill-reader list --scope global
skill-reader list --scope project
```

**Show skills shared between tools (hardlinks or copies):**
```bash
skill-reader duplicates
```

**Inspect a specific skill:**
```bash
skill-reader inspect chef-assistant
```

**Delete a skill:**
```bash
# Interactive confirmation
skill-reader delete chef-assistant

# Delete only from one tool (if hardlinked)
skill-reader delete chef-assistant --tool windsurf

# Skip confirmation prompt
skill-reader delete chef-assistant --yes
```

**Scan a specific project directory:**
```bash
skill-reader list --cwd ~/Developer/my-project
skill-reader ui --cwd ~/Developer/my-project
```

## Platform Support

| Platform | Status |
|----------|--------|
| macOS | Fully supported |
| Linux | Fully supported |
| Windows | Supported — hardlink detection is best-effort (NTFS reliable, FAT32 falls back to path comparison) |

## Scanned Paths

### Global (always scanned)

Paths are resolved at runtime based on the current platform.

| Tool | macOS / Linux | Windows |
|------|--------------|---------|
| Claude Code | `~/.claude/skills/` | `~/.claude/skills/` |
| Windsurf | `~/.codeium/windsurf/skills/` | `%LOCALAPPDATA%\Codeium\windsurf\skills\` |
| Kiro | `~/.kiro/skills/` | `~/.kiro/skills/` |
| Codex | `~/.codex/skills/` | `~/.codex/skills/` |
| Cursor | `~/.cursor/rules/` | `%APPDATA%\Cursor\User\rules\` |

### Project (relative to CWD or `--cwd`)

Same on all platforms:

| Tool | Path |
|------|------|
| Claude Code | `.claude/skills/` |
| Windsurf | `.windsurf/skills/` |
| Kiro | `.kiro/skills/` |
| Codex | `.codex/skills/` |
| Cursor | `.cursor/rules/` |

## Hardlink Detection

Claude Code and Windsurf share skills via filesystem hardlinks — the same `SKILL.md` inode exists under both `~/.claude/skills/` and `~/.codeium/windsurf/skills/`. Skill Reader detects this by comparing inodes across all scanned paths and groups them into a single entry showing all tools the skill belongs to.

On Windows, inode-based detection works on NTFS. On FAT32 volumes, Skill Reader falls back to path comparison (no false positives, but hardlinks won't be grouped).

When you try to delete a hardlinked skill, Skill Reader shows a modal letting you choose which tools to remove it from:

```
Delete skill: chef-assistant
This skill is shared across multiple tools.
Select which tools to remove it from:

[x] C  claude   ~/.claude/skills/chef-assistant
[x] W  windsurf ~/.codeium/windsurf/skills/chef-assistant

[Cancel]  [Delete]
```

## Skill Format

Skill Reader supports the standard `SKILL.md` format used by Claude Code, Windsurf, Kiro, and Codex:

```markdown
---
name: my-skill
description: "Trigger description for the agent..."
source: community     # optional (Kiro)
risk: low             # optional (Kiro)
date_added: "2026-01-01"  # optional (Kiro)
---

# My Skill

Skill content here...
```

Each skill lives in its own directory:

```
~/.claude/skills/
└── my-skill/
    ├── SKILL.md
    └── resources/   # optional
```

## Using as an AI Agent Skill

Skill Reader ships with its own `SKILL.md` so that Claude, Kiro, Windsurf, and other agents can invoke it automatically when you ask about your skills.

Install the skill globally:

```bash
# Claude
mkdir -p ~/.claude/skills/skill-reader
cp SKILL.md ~/.claude/skills/skill-reader/SKILL.md

# Windsurf (hardlink to keep in sync with Claude)
mkdir -p ~/.codeium/windsurf/skills/skill-reader
ln ~/.claude/skills/skill-reader/SKILL.md ~/.codeium/windsurf/skills/skill-reader/SKILL.md

# Kiro
mkdir -p ~/.kiro/skills/skill-reader
cp SKILL.md ~/.kiro/skills/skill-reader/SKILL.md
```

Once installed, agents will suggest using `skill-reader` when you say things like:
- "show my skills"
- "what skills do I have installed?"
- "delete the chef-assistant skill"
- "which skills are duplicated?"

## Tech Stack

| Component | Library |
|-----------|---------|
| TUI | [Textual](https://github.com/Textualize/textual) |
| CLI | [Typer](https://typer.tiangolo.com/) |
| Frontmatter parsing | [python-frontmatter](https://github.com/eyeseast/python-frontmatter) |
| Terminal output | [Rich](https://github.com/Textualize/rich) |

## License

MIT
