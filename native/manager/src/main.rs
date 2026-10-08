//! Entrypoint of the per-user runtime manager image.
//!
//! Native admission precedes package probing, ownership and runtime supervision.
#![windows_subsystem = "windows"]

#[cfg(windows)]
use cadrumo_application::diagnostics::{
    DiagnosticSource, Diagnostics, EventKind, HostOutcome, HostStage,
};
use cadrumo_manager::identity;
#[cfg(windows)]
use std::sync::Arc;
use std::{
    env,
    io::{self, Write},
    process::ExitCode,
};

const USAGE_ERROR: u8 = 2;
const STARTUP_FAILED: u8 = 69;
#[cfg(windows)]
const ADMISSION_REFUSED: u8 = 77;

fn start(
    breakaway_attempted: bool,
    sign_in: bool,
    designation: Option<cadrumo_manager::cutover::Designation>,
) -> ExitCode {
    #[cfg(windows)]
    let diagnostics = Arc::new(Diagnostics::new(DiagnosticSource::Manager));
    #[cfg(windows)]
    diagnostics.host_event(EventKind::HostStarted, HostStage::Admission);
    #[cfg(windows)]
    diagnostics.host_event(EventKind::StageStarted, HostStage::Admission);
    #[cfg(windows)]
    if let Err(refusal) = cadrumo_manager::admission::require_current() {
        cadrumo_manager::diagnostics::admission_refused(&diagnostics, refusal);
        diagnostics.host_stopped(i32::from(ADMISSION_REFUSED));
        let _ = writeln!(io::stderr(), "{}", refusal.code());
        return ExitCode::from(ADMISSION_REFUSED);
    }
    #[cfg(windows)]
    diagnostics.host_outcome(HostStage::Admission, HostOutcome::Ready);
    #[cfg(windows)]
    match run_windows(
        breakaway_attempted,
        sign_in,
        designation,
        diagnostics.clone(),
    ) {
        Ok(()) => {
            diagnostics.host_stopped(0);
            ExitCode::SUCCESS
        }
        Err(_) => {
            diagnostics.host_stopped(i32::from(STARTUP_FAILED));
            let _ = writeln!(io::stderr(), "manager_startup_failed");
            cadrumo_manager::windows_lifecycle::show_startup_failure();
            ExitCode::from(STARTUP_FAILED)
        }
    }
    #[cfg(not(windows))]
    {
        let _ = (breakaway_attempted, sign_in, designation);
        let _ = writeln!(io::stderr(), "manager_platform_unavailable");
        ExitCode::from(STARTUP_FAILED)
    }
}

#[cfg(windows)]
fn run_windows(
    breakaway_attempted: bool,
    sign_in: bool,
    designation: Option<cadrumo_manager::cutover::Designation>,
    diagnostics: Arc<Diagnostics>,
) -> io::Result<()> {
    use cadrumo_application::error::application::{ErrorCode, Operation};
    use cadrumo_manager::{
        background::Background,
        diagnostics::{configure, inspection_failed, stage},
        installation::DispatchOutcome,
        installed::InstalledRuntime,
        session::{ManagerSession, instance::claim_session},
        windows_lifecycle,
    };
    if stage(
        &diagnostics,
        HostStage::JobEscape,
        ErrorCode::ManagerUnavailable,
        Operation::Manager,
        || windows_lifecycle::escape_job(breakaway_attempted || designation.is_some(), sign_in),
    )? {
        diagnostics.host_outcome(HostStage::JobEscape, HostOutcome::Dispatched);
        return Ok(());
    }
    let (installation, successor) = if let Some(designation) = designation {
        let admitted = cadrumo_manager::cutover_child::admit(designation)?;
        (
            admitted.installation,
            Some((admitted.permit, admitted.reporter)),
        )
    } else {
        let installation = match stage(
            &diagnostics,
            HostStage::Package,
            ErrorCode::PackageUnavailable,
            Operation::Manager,
            || cadrumo_manager::installation::dispatch_newest(&env::current_exe()?, sign_in),
        )? {
            DispatchOutcome::Dispatched => {
                diagnostics.host_outcome(HostStage::Package, HostOutcome::Dispatched);
                return Ok(());
            }
            DispatchOutcome::Current(installation) => installation,
        };
        (installation, None)
    };
    let Some(session_lock) = stage(
        &diagnostics,
        HostStage::Instance,
        ErrorCode::InstanceLockForeign,
        Operation::Manager,
        || claim_session(identity::MANAGER_ID, std::time::Duration::ZERO),
    )?
    else {
        diagnostics.host_outcome(HostStage::Instance, HostOutcome::AlreadyRunning);
        if successor.is_some() {
            return Err(io::ErrorKind::WouldBlock.into());
        }
        if !sign_in {
            cadrumo_manager::ipc::windows::request(
                &env::current_exe()?,
                &cadrumo_manager::ipc::Request::Reveal { schema: 1 },
            )?;
        }
        return Ok(());
    };
    diagnostics.host_event(EventKind::StageStarted, HostStage::Storage);
    diagnostics.host_event(EventKind::StageCompleted, HostStage::Storage);
    configure(installation.locations(), &diagnostics);
    let preferences =
        cadrumo_manager::preferences::Preferences::read(installation.locations().storage_root())?;
    if sign_in && !preferences.start_at_sign_in {
        return Ok(());
    }
    let tray =
        cadrumo_manager::windows_tray::Configuration::new(installation.locations(), preferences)?;
    let ipc = cadrumo_manager::ipc::windows::Server::bind_installed(
        installation.locations().package_root(),
    )?;
    diagnostics.host_event(EventKind::StageStarted, HostStage::Package);
    let selected = installation.selection().clone();
    let installed = InstalledRuntime::from_admitted(installation)
        .map_err(|error| inspection_failed(&diagnostics, error))?;
    diagnostics.host_outcome(HostStage::Package, HostOutcome::Ready);
    let session = stage(
        &diagnostics,
        HostStage::Session,
        ErrorCode::SessionUnavailable,
        Operation::Manager,
        ManagerSession::current,
    )?;
    let mut background = Background::new(
        installed,
        session,
        windows_lifecycle::activity,
        diagnostics.clone(),
        if sign_in {
            cadrumo_manager::session::ownership::StartKind::SignIn
        } else {
            cadrumo_manager::session::ownership::StartKind::Manual
        },
    );
    if let Some((permit, reporter)) = successor {
        background.designated(permit, reporter);
    }
    background.watch_installation(&selected)?;
    stage(
        &diagnostics,
        HostStage::Window,
        ErrorCode::ManagerUnavailable,
        Operation::Manager,
        || windows_lifecycle::run(background, ipc, tray, selected, session_lock),
    )
}

fn main() -> ExitCode {
    let arguments: Vec<_> = env::args_os().skip(1).collect();
    match arguments.as_slice() {
        [] => start(false, false, None),
        [flag] if flag == "--sign-in" => start(false, true, None),
        [flag] if flag == "--breakaway-attempt" => start(true, false, None),
        [first, second] if first == "--breakaway-attempt" && second == "--sign-in" => {
            start(true, true, None)
        }
        [flag, value] if flag == "--cutover" => {
            match value
                .to_str()
                .and_then(|value| cadrumo_manager::cutover::Designation::parse(value).ok())
            {
                Some(designation) => start(false, false, Some(designation)),
                None => ExitCode::from(USAGE_ERROR),
            }
        }
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
