# Skill Reader

Rust CLI for reusable AI profiles built around shared `skills`, `rules`, and `agents` assets.

This repo now treats the Rust CLI as the primary implementation of `skill-reader`. The older Python code remains in the repo only as legacy/reference material and is no longer the main distribution target.

## Install

### Local development

```bash
git clone git@github.com:dmontil/skill-reader.git
cd skill-reader
cargo run -- profile list
```

### Homebrew

A sample formula is included at [homebrew/skill-reader.rb](/Users/monti/Developer/skill-reader-util/skill-reader/homebrew/skill-reader.rb).

Typical release flow:

1. Tag a release such as `v0.1.0`
2. Publish the source tarball
3. Compute the tarball `sha256`
4. Update the formula
5. Publish it in a tap

Then install with:

```bash
brew tap dmontil/tap
brew install skill-reader
```

The formula expects the Rust crate at the repo root and installs with:

```ruby
system "cargo", "install", *std_cargo_args(path: ".")
```

Recommended tap layout:

```text
homebrew-tap/
└── Formula/
    └── skill-reader.rb
```

## Storage format

The CLI uses a shared on-disk format so it can interoperate with the macOS app:

- `~/.skill-reader/profiles/<name>/profile.yaml`
- `~/.skill-reader/library/skills/<id>/...`
- `~/.skill-reader/library/rules/<id>.*`
- `~/.skill-reader/library/agents/<id>.md`

Applying a profile writes project-local materializations and a manifest under:

- `.skill-reader/applied-profiles/<tool>--<profile>.json`

## Commands

```bash
skill-reader profile list
skill-reader profile create frontend-audit --description "Audit stack"
skill-reader profile add-asset frontend-audit --kind skill --id perf-skill
skill-reader profile inspect frontend-audit
skill-reader profile apply frontend-audit --tool codex --cwd ~/Developer/my-project
skill-reader profile delete frontend-audit --yes
```

## Supported targets

Profiles materialize project-local assets for:

- `codex`
- `claude`
- `cursor`
- `windsurf`
- `opencode`

## Parity with the macOS app

The CLI and macOS app share the same profile storage, asset library layout, target set, and project materialization format.

In practice:

- use the CLI for scripted profile creation and automated project setup
- use the macOS app for browsing, profile composition, previews, metadata editing, and library health maintenance

## Test coverage

Local workflow:

```bash
rustup component add llvm-tools-preview
cargo install cargo-llvm-cov
cargo test
cargo llvm-cov --workspace --all-features --fail-under-lines 100 --summary-only
cargo llvm-cov --workspace --all-features --html
open target/llvm-cov/html/index.html
```

CI workflow:

- Defined in `.github/workflows/skill-reader-rust.yml`
- Runs `cargo fmt`, `cargo clippy`, `cargo test`
- Enforces `100%` line coverage with `cargo llvm-cov --fail-under-lines 100`

## Notes

- This repository currently focuses on the Rust profile CLI.
- The native macOS app lives separately at [dmontil/skill-reader-mac](https://github.com/dmontil/skill-reader-mac).
- The Python implementation is not the primary shipping path anymore.

## Tech Stack

| Component | Library |
|-----------|---------|
| CLI | [clap](https://github.com/clap-rs/clap) |
| Data serialization | [serde](https://github.com/serde-rs/serde) |
| YAML / JSON | [serde_yaml](https://docs.rs/serde_yaml/) / [serde_json](https://docs.rs/serde_json/) |
| Errors | [anyhow](https://github.com/dtolnay/anyhow) |

## License

MIT
