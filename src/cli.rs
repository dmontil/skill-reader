use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::{Args, Parser, Subcommand, ValueEnum};

use crate::profiles::{
    add_asset_to_profile, apply_profile, create_profile, delete_profile, list_profiles,
    load_profile, remove_asset_from_profile, AssetKind, ProfileTool,
};

#[derive(Parser)]
#[command(name = "skill-reader")]
#[command(about = "Manage reusable AI skill profiles", version)]
pub struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Profile(ProfileCommand),
}

#[derive(Args)]
struct ProfileCommand {
    #[command(subcommand)]
    command: ProfileSubcommand,
}

#[derive(Subcommand)]
enum ProfileSubcommand {
    List,
    Inspect {
        name: String,
    },
    Create {
        name: String,
        #[arg(short, long, default_value = "")]
        description: String,
    },
    AddAsset {
        name: String,
        #[arg(long)]
        kind: AssetKindArg,
        #[arg(long = "id")]
        asset_id: String,
    },
    RemoveAsset {
        name: String,
        #[arg(long)]
        kind: AssetKindArg,
        #[arg(long = "id")]
        asset_id: String,
    },
    Apply {
        name: String,
        #[arg(short, long)]
        tool: Option<ToolArg>,
        #[arg(long)]
        all: bool,
        #[arg(short, long)]
        cwd: PathBuf,
    },
    Delete {
        name: String,
        #[arg(short, long)]
        yes: bool,
    },
}

#[derive(Clone, Copy, Debug, ValueEnum)]
enum AssetKindArg {
    Skill,
    Rule,
    Agents,
}

#[derive(Clone, Copy, Debug, ValueEnum)]
enum ToolArg {
    Codex,
    Claude,
    Cursor,
    Windsurf,
    Opencode,
}

impl From<AssetKindArg> for AssetKind {
    fn from(value: AssetKindArg) -> Self {
        match value {
            AssetKindArg::Skill => AssetKind::Skill,
            AssetKindArg::Rule => AssetKind::Rule,
            AssetKindArg::Agents => AssetKind::Agents,
        }
    }
}

impl From<ToolArg> for ProfileTool {
    fn from(value: ToolArg) -> Self {
        match value {
            ToolArg::Codex => ProfileTool::Codex,
            ToolArg::Claude => ProfileTool::Claude,
            ToolArg::Cursor => ProfileTool::Cursor,
            ToolArg::Windsurf => ProfileTool::Windsurf,
            ToolArg::Opencode => ProfileTool::Opencode,
        }
    }
}

pub fn run() -> Result<()> {
    let cli = Cli::parse();
    for line in execute(cli)? {
        println!("{line}");
    }
    Ok(())
}

fn execute(cli: Cli) -> Result<Vec<String>> {
    match cli.command {
        Commands::Profile(cmd) => run_profile(cmd.command),
    }
}

fn run_profile(command: ProfileSubcommand) -> Result<Vec<String>> {
    let mut lines = Vec::new();
    match command {
        ProfileSubcommand::List => {
            let profiles = list_profiles()?;
            if profiles.is_empty() {
                lines.push("No profiles found.".to_string());
                return Ok(lines);
            }
            for profile in profiles {
                lines.push(format!(
                    "{}\tassets={}\ttargets={}\t{}",
                    profile.name,
                    profile.assets.len(),
                    profile
                        .targets
                        .keys()
                        .cloned()
                        .collect::<Vec<_>>()
                        .join(","),
                    profile.description
                ));
            }
        }
        ProfileSubcommand::Inspect { name } => {
            let profile = load_profile(&name)?;
            lines.push(format!("name: {}", profile.name));
            lines.push(format!(
                "description: {}",
                if profile.description.is_empty() {
                    "—"
                } else {
                    &profile.description
                }
            ));
            lines.push(format!(
                "targets: {}",
                profile
                    .targets
                    .keys()
                    .cloned()
                    .collect::<Vec<_>>()
                    .join(", ")
            ));
            if profile.assets.is_empty() {
                lines.push("assets: none".to_string());
            } else {
                lines.push("assets:".to_string());
                for asset in profile.assets {
                    lines.push(format!("  - {}:{}", asset.kind.as_str(), asset.id));
                }
            }
        }
        ProfileSubcommand::Create { name, description } => {
            let profile = create_profile(&name, &description)?;
            lines.push(format!("Created profile '{}'.", profile.name));
        }
        ProfileSubcommand::AddAsset {
            name,
            kind,
            asset_id,
        } => {
            let profile = add_asset_to_profile(&name, kind.into(), &asset_id)?;
            lines.push(format!(
                "Updated profile '{}' ({} assets).",
                profile.name,
                profile.assets.len()
            ));
        }
        ProfileSubcommand::RemoveAsset {
            name,
            kind,
            asset_id,
        } => {
            let profile = remove_asset_from_profile(&name, kind.into(), &asset_id)?;
            lines.push(format!(
                "Updated profile '{}' ({} assets).",
                profile.name,
                profile.assets.len()
            ));
        }
        ProfileSubcommand::Apply {
            name,
            tool,
            all,
            cwd,
        } => {
            if !all && tool.is_none() {
                anyhow::bail!("Provide --tool or --all.");
            }
            let chosen = if all {
                Vec::new()
            } else {
                vec![tool.expect("checked").into()]
            };
            let manifests = apply_profile(&name, &chosen, &cwd).with_context(|| {
                format!("Failed to apply profile '{}' in {}", name, cwd.display())
            })?;
            lines.push(format!(
                "Applied profile '{}' to {} tool(s).",
                name,
                manifests.len()
            ));
            for manifest in manifests {
                lines.push(format!(
                    "  -> {} ({} updated paths)",
                    manifest.tool.as_str(),
                    manifest.generated_paths.len() + manifest.managed_files.len()
                ));
            }
        }
        ProfileSubcommand::Delete { name, yes } => {
            if !yes {
                anyhow::bail!("Pass --yes to delete the profile.");
            }
            delete_profile(&name)?;
            lines.push(format!("Deleted profile '{}'.", name));
        }
    }
    Ok(lines)
}

#[cfg(test)]
mod tests {
    use std::{env, fs};

    use super::*;
    use crate::profiles::skill_reader_test_lock;
    use tempfile::TempDir;

    fn with_test_home<T>(f: impl FnOnce(&TempDir) -> Result<T>) -> Result<T> {
        let _guard = skill_reader_test_lock().lock().expect("test env lock");
        let temp = TempDir::new()?;
        let previous = env::var_os("SKILL_READER_HOME");
        env::set_var("SKILL_READER_HOME", temp.path().join(".skill-reader"));
        let result = f(&temp);
        if let Some(previous) = previous {
            env::set_var("SKILL_READER_HOME", previous);
        } else {
            env::remove_var("SKILL_READER_HOME");
        }
        result
    }

    fn seed_home(root: &TempDir) {
        let home = root.path().join(".skill-reader");
        fs::create_dir_all(home.join("library/skills/perf-skill")).unwrap();
        fs::write(
            home.join("library/skills/perf-skill/SKILL.md"),
            "---\nname: perf-skill\ndescription: Improve performance\n---\n\nUse perf guidance.\n",
        )
        .unwrap();
        fs::create_dir_all(home.join("library/rules")).unwrap();
        fs::write(
            home.join("library/rules/frontend-guide.md"),
            "---\ndescription: Frontend constraints\n---\n\nAlways test mobile.\n",
        )
        .unwrap();
        fs::create_dir_all(home.join("library/agents")).unwrap();
        fs::write(
            home.join("library/agents/team-playbook.md"),
            "# Team playbook\n\nShip carefully.\n",
        )
        .unwrap();
    }

    #[test]
    fn cli_parse_create_command() {
        with_test_home(|_| {
            let cli = Cli::try_parse_from(["skill-reader", "profile", "create", "frontend-audit"])?;
            let lines = execute(cli)?;
            assert_eq!(lines[0], "Created profile 'frontend-audit'.");
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn cli_execute_full_profile_flow() -> Result<()> {
        with_test_home(|temp| {
            seed_home(temp);
            let project = temp.path().join("project");
            fs::create_dir_all(&project)?;

            let lines = execute(Cli::try_parse_from([
                "skill-reader",
                "profile",
                "create",
                "frontend-audit",
                "--description",
                "Audit stack",
            ])?)?;
            assert_eq!(lines[0], "Created profile 'frontend-audit'.");

            execute(Cli::try_parse_from([
                "skill-reader",
                "profile",
                "add-asset",
                "frontend-audit",
                "--kind",
                "skill",
                "--id",
                "perf-skill",
            ])?)?;
            execute(Cli::try_parse_from([
                "skill-reader",
                "profile",
                "add-asset",
                "frontend-audit",
                "--kind",
                "rule",
                "--id",
                "frontend-guide",
            ])?)?;
            execute(Cli::try_parse_from([
                "skill-reader",
                "profile",
                "add-asset",
                "frontend-audit",
                "--kind",
                "agents",
                "--id",
                "team-playbook",
            ])?)?;

            let inspect = execute(Cli::try_parse_from([
                "skill-reader",
                "profile",
                "inspect",
                "frontend-audit",
            ])?)?;
            assert!(inspect.iter().any(|line| line.contains("skill:perf-skill")));

            let apply = execute(Cli::try_parse_from([
                "skill-reader",
                "profile",
                "apply",
                "frontend-audit",
                "--tool",
                "codex",
                "--cwd",
                project.to_str().unwrap(),
            ])?)?;
            assert!(apply[0].contains("Applied profile 'frontend-audit'"));

            let list = execute(Cli::try_parse_from(["skill-reader", "profile", "list"])?)?;
            assert!(list[0].contains("frontend-audit"));

            let remove = execute(Cli::try_parse_from([
                "skill-reader",
                "profile",
                "remove-asset",
                "frontend-audit",
                "--kind",
                "rule",
                "--id",
                "frontend-guide",
            ])?)?;
            assert!(remove[0].contains("Updated profile 'frontend-audit'"));

            let delete = execute(Cli::try_parse_from([
                "skill-reader",
                "profile",
                "delete",
                "frontend-audit",
                "--yes",
            ])?)?;
            assert_eq!(delete[0], "Deleted profile 'frontend-audit'.");
            Ok(())
        })
    }

    #[test]
    fn cli_apply_requires_tool_or_all() -> Result<()> {
        let temp = TempDir::new()?;
        let project = temp.path().join("project");
        fs::create_dir_all(&project)?;
        let err = execute(Cli::try_parse_from([
            "skill-reader",
            "profile",
            "apply",
            "frontend-audit",
            "--cwd",
            project.to_str().unwrap(),
        ])?)
        .unwrap_err();
        assert!(err.to_string().contains("Provide --tool or --all"));
        Ok(())
    }

    #[test]
    fn cli_delete_requires_yes() -> Result<()> {
        let err = execute(Cli::try_parse_from([
            "skill-reader",
            "profile",
            "delete",
            "frontend-audit",
        ])?)
        .unwrap_err();
        assert!(err.to_string().contains("Pass --yes"));
        Ok(())
    }
}
