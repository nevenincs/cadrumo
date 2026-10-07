#![cfg_attr(windows, windows_subsystem = "windows")]

mod app;
mod docs;
mod environment;
mod launch;
mod logs;
mod manager;
mod shell;
mod startup_logging;
mod terminal;

use cadrumo_application::{
    child::ChildConfiguration,
    diagnostics::{Diagnostics, EventKind, HostOutcome, HostStage},
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    process,
};
use std::{
    ffi::OsString,
    path::PathBuf,
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
};

const CLI_ENTRYPOINT: &str = include_str!("python/cli.py");

fn run(diagnostics: Arc<Diagnostics>) -> Result<i32> {
    let arguments = std::env::args_os().skip(1).collect();
    let mode = launch::select(arguments, launch::desktop_available());
    diagnostics.event(EventKind::HostStarted, None, None);
    diagnostics.host_event(EventKind::StageStarted, HostStage::Admission);
    // The GUI claims the per-user instance before any per-user state opens.
    let _instance = match &mode {
        Ok(mode) => match shell::single_instance::admit(mode)? {
            shell::single_instance::Admission::Activated => {
                diagnostics.host_outcome(HostStage::Admission, HostOutcome::AlreadyRunning);
                return Ok(0);
            }
            shell::single_instance::Admission::Primary(primary) => Some(primary),
            shell::single_instance::Admission::Headless => None,
        },
        Err(_) => None,
    };
    diagnostics.host_outcome(HostStage::Admission, HostOutcome::Ready);
    let root = match std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT").filter(|v| !v.is_empty()) {
        Some(path) => PathBuf::from(path),
        None => std::env::current_exe()
            .map_err(|e| launch_error().caused_by(e))?
            .parent()
            .ok_or_else(launch_error)?
            .to_owned(),
    };
    let parent = environment::Parent::current()?;
    startup_logging::configure(&parent, &diagnostics);
    diagnostics.host_event(EventKind::StageStarted, HostStage::Environment);
    let launch =
        tauri::async_runtime::block_on(environment::resolve(root, &parent, diagnostics.clone()))
            .inspect_err(|error| {
                diagnostics.host_failure(HostStage::Environment, error.clone());
            })?;
    diagnostics.host_outcome(HostStage::Environment, HostOutcome::Ready);
    match mode? {
        launch::Mode::Gui => app::run(launch),
        launch::Mode::Cli(arguments) => {
            diagnostics.event(EventKind::HeadlessSelected, None, None);
            let configuration = headless(&launch, parent.working_directory)?;
            let mut forwarded: Vec<OsString> =
                vec!["-u".into(), "-c".into(), CLI_ENTRYPOINT.into()];
            forwarded.extend(arguments);
            let cancelled = Arc::new(AtomicBool::new(false));
            let interrupted = cancelled.clone();
            ctrlc::set_handler(move || interrupted.store(true, Ordering::Release))
                .map_err(|e| launch_error().caused_by(e))?;
            process::passthrough(&configuration, &forwarded, diagnostics, cancelled)
        }
    }
}
/// The CLI passthrough keeps the caller's directory; the pinned storage root in
/// the child environment keeps its storage independent of that directory.
fn headless(launch: &environment::Launch, directory: PathBuf) -> Result<ChildConfiguration> {
    ChildConfiguration::new(
        launch.child.executable().to_owned(),
        directory,
        launch.child.environment().clone(),
    )
    .map_err(|e| launch_error().caused_by(e))
}
fn launch_error() -> ApplicationError {
    ApplicationError::new(ErrorCode::EnvironmentFailed, Operation::Launch)
}

fn main() {
    // A GUI launch never allocates a console. CLI callers may already have one;
    // attach before Rust initializes its standard streams, preserving redirection.
    #[cfg(windows)]
    cadrumo_platform::desktop::attach_parent_console();
    let diagnostics = Arc::new(Diagnostics::default());
    // Report after unwinding: hooks run before locks held by the panicking code release.
    // Suppress Rust's default hook, which can expose private payloads on stderr.
    std::panic::set_hook(Box::new(|_| {}));
    let outcome =
        std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| run(diagnostics.clone())))
            .unwrap_or_else(|_| Err(ApplicationError::new(ErrorCode::Panic, Operation::Launch)));
    let code = match outcome {
        Ok(code) => code,
        Err(error) => {
            diagnostics.failure(error.clone());
            eprintln!(
                "{}",
                serde_json::to_string(&error).unwrap_or_else(|_| "application_error".into())
            );
            match error.code {
                ErrorCode::InvalidArguments => 64,
                ErrorCode::DesktopUnavailable => 69,
                ErrorCode::InstanceLockForeign => 77,
                _ => 1,
            }
        }
    };
    diagnostics.host_stopped(code);
    std::process::exit(code);
}
