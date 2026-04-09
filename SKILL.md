---
name: skill-reader
description: Use this skill when the user wants to list, inspect, find, or delete AI agent skills installed on the system. Triggers include phrases like "show my skills", "what skills do I have", "list skills", "delete skill", "which skills are global", "find duplicate skills", "skill manager", "manage skills", or any question about installed skills for Claude, Windsurf, Kiro, Codex, or Cursor.
source: local
risk: low
---

# Skill Reader

A CLI + TUI tool to manage AI agent skills installed on this machine.

## What it does

- Lists all skills across Claude, Windsurf, Kiro, Codex, and Cursor
- Shows whether each skill is global or project-scoped
- Detects hardlinks (same file shared between tools)
- Allows filtering by tool, scope, or name
- Deletes skills with confirmation, handling hardlinks safely

## Installation

```bash
cd ~/Developer/skill-reader
pipx install -e .
```

Or during development:

```bash
cd ~/Developer/skill-reader
pip install -e .
```

## CLI Usage

```bash
# Launch the interactive TUI
skill-reader ui

# List all skills
skill-reader list

# Filter by tool
skill-reader list --tool claude
skill-reader list --tool windsurf
skill-reader list --tool kiro
skill-reader list --tool codex

# Filter by scope
skill-reader list --scope global
skill-reader list --scope project

# Show skills shared between tools (hardlinks)
skill-reader duplicates

# Inspect a specific skill
skill-reader inspect chef-assistant

# Delete a skill
skill-reader delete chef-assistant
skill-reader delete chef-assistant --tool windsurf   # only from Windsurf
skill-reader delete chef-assistant --yes             # skip confirmation
```

## Global skill paths scanned

| Tool | Path |
|------|------|
| Claude Code | `~/.claude/skills/` |
| Windsurf | `~/.codeium/windsurf/skills/` |
| Kiro | `~/.kiro/skills/` |
| Codex | `~/.codex/skills/` |
| Cursor | `~/.cursor/rules/` |

## Project skill paths scanned (from CWD)

- `.claude/skills/`
- `.windsurf/skills/`
- `.kiro/skills/`
- `.codex/skills/`
- `.cursor/rules/`

## Hardlink detection

Claude and Windsurf share skills via hardlinks (same inode on disk).
Skill Reader detects this and shows all tools a skill belongs to.
When deleting a hardlinked skill, you choose which tools to remove it from.

## When to use this skill

- User asks what skills are installed
- User wants to remove a skill
- User wants to know if a skill is duplicated across tools
- User wants to see which skills belong to which AI agent
- User is auditing their AI tool configuration
