mod cli;
mod profiles;

use anyhow::Result;

fn main() -> Result<()> {
    cli::run()
}
