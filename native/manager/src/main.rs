//! Entrypoint of the per-user runtime manager image.
//!
//! The entrypoint accepts only `--version` and starts no runtime.
#![windows_subsystem = "windows"]

use cadrumo_manager::identity;
use std::{
    env,
    io::{self, Write},
    process::ExitCode,
};

const USAGE_ERROR: u8 = 2;

fn main() -> ExitCode {
    let arguments: Vec<_> = env::args_os().skip(1).collect();
    match arguments.as_slice() {
        [] => ExitCode::SUCCESS,
        [flag] if flag == "--version" => {
            match writeln!(
                io::stdout(),
                "{} {}",
                identity::MANAGER_NAME,
                identity::VERSION
            ) {
                Ok(()) => ExitCode::SUCCESS,
                Err(_) => ExitCode::FAILURE,
            }
        }
        _ => {
            // A GUI-subsystem image may have no stderr; the exit code carries the refusal.
            let _ = writeln!(io::stderr(), "usage: cadrumo-manager [--version]");
            ExitCode::from(USAGE_ERROR)
        }
    }
}
