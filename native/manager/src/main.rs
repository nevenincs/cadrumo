//! Entrypoint of the per-user runtime manager image.
//!
//! Native admission precedes package probing, ownership and runtime supervision.
#![windows_subsystem = "windows"]

use cadrumo_manager::identity;
use std::{
    env,
    io::{self, Write},
    process::ExitCode,
};

const USAGE_ERROR: u8 = 2;
const STARTUP_FAILED: u8 = 69;
#[cfg(windows)]
const ADMISSION_REFUSED: u8 = 77;

fn start(breakaway_attempted: bool) -> ExitCode {
    #[cfg(windows)]
    if let Err(refusal) = cadrumo_manager::admission::require_current() {
        let _ = writeln!(io::stderr(), "{}", refusal.code());
        return ExitCode::from(ADMISSION_REFUSED);
    }
    #[cfg(windows)]
    match run_windows(breakaway_attempted) {
        Ok(()) => ExitCode::SUCCESS,
        Err(_) => {
            let _ = writeln!(io::stderr(), "manager_startup_failed");
            cadrumo_manager::windows_lifecycle::show_startup_failure();
            ExitCode::from(STARTUP_FAILED)
        }
    }
    #[cfg(not(windows))]
    {
        let _ = breakaway_attempted;
        let _ = writeln!(io::stderr(), "manager_platform_unavailable");
        ExitCode::from(STARTUP_FAILED)
    }
}

#[cfg(windows)]
fn run_windows(breakaway_attempted: bool) -> io::Result<()> {
    use cadrumo_manager::{
        background::Background,
        installed::InstalledRuntime,
        session::{ManagerSession, instance::claim_session},
        supervision::environment::ManagedLocations,
        windows_lifecycle,
    };
    if windows_lifecycle::escape_job(breakaway_attempted)? {
        return Ok(());
    }
    let Some(_session_lock) = claim_session(identity::MANAGER_ID, std::time::Duration::ZERO)?
    else {
        return Ok(());
    };
    let locations = ManagedLocations::resolve(&env::current_exe()?)?;
    let installed = InstalledRuntime::inspect(&locations)?;
    let background = Background::new(
        installed,
        ManagerSession::current()?,
        windows_lifecycle::activity,
    );
    windows_lifecycle::run(background)
}

fn main() -> ExitCode {
    let arguments: Vec<_> = env::args_os().skip(1).collect();
    match arguments.as_slice() {
        [] => start(false),
        [flag] if flag == "--breakaway-attempt" => start(true),
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
