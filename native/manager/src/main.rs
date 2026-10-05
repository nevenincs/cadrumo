//! Entrypoint of the per-user runtime manager image.
//!
//! Bare startup checks native admission. Runtime composition is not yet installed.
#![windows_subsystem = "windows"]

use cadrumo_manager::identity;
use std::{
    env,
    io::{self, Write},
    process::ExitCode,
};

const USAGE_ERROR: u8 = 2;
const COMPOSITION_UNAVAILABLE: u8 = 69;
#[cfg(windows)]
const ADMISSION_REFUSED: u8 = 77;

fn start() -> ExitCode {
    #[cfg(windows)]
    if let Err(refusal) = cadrumo_manager::admission::require_current() {
        let _ = writeln!(io::stderr(), "{}", refusal.code());
        return ExitCode::from(ADMISSION_REFUSED);
    }
    // Admission alone does not start or supervise a runtime. Until installed
    // discovery and the session surfaces are composed, never report success.
    let _ = writeln!(io::stderr(), "manager_composition_unavailable");
    ExitCode::from(COMPOSITION_UNAVAILABLE)
}

fn main() -> ExitCode {
    let arguments: Vec<_> = env::args_os().skip(1).collect();
    match arguments.as_slice() {
        [] => start(),
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
