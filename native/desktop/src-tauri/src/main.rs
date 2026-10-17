#![cfg_attr(windows, windows_subsystem = "windows")]

mod agent;
mod app;
mod docs;
mod environment;
mod launch;
mod logs;
mod manager;
mod shell;
mod startup;
mod startup_logging;
mod terminal;

use cadrumo_application::{
    child::ChildConfiguration,
    diagnostics::{Diagnostics, EventKind, HostOutcome, HostStage, panic},
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
    // Before the window exists, so a panic in any webview callback has a durable sink.
    startup_logging::configure(&parent, &diagnostics);
    if matches!(mode, Ok(launch::Mode::Gui)) {
        #[cfg(windows)]
        contain_application()?;
        return app::run(root, parent, diagnostics);
    }
    diagnostics.host_event(EventKind::StageStarted, HostStage::Environment);
    let launch =
        tauri::async_runtime::block_on(environment::resolve(root, &parent, diagnostics.clone()))
            .inspect_err(|error| {
                diagnostics.host_failure(HostStage::Environment, error.clone());
            })?;
    diagnostics.host_outcome(HostStage::Environment, HostOutcome::Ready);
    // Package libraries may execute unload handlers after main returns. Keep
    // one independent lease until OS resource cleanup; resolve-only tests retain
    // ordinary RAII cleanup instead of accumulating process-lifetime guards.
    if let Some(lease) = launch._publication.as_ref() {
        std::mem::forget(lease.clone());
    }
    match mode? {
        launch::Mode::Gui => unreachable!("GUI starts before environment preparation"),
        launch::Mode::Health { hold_seconds } => {
            tauri::async_runtime::block_on(check_health(&launch, hold_seconds))
        }
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

/// One kill-on-close job for the window and everything it starts: the runtime
/// it hosts, session holders, the agent service, terminals and short calls. The
/// handle lives until the process ends, so however the window ends, nothing it
/// started outlives it. The installed manager is dispatched through Explorer and
/// stays outside.
#[cfg(windows)]
fn contain_application() -> Result<()> {
    static APPLICATION: std::sync::OnceLock<cadrumo_manager::process_job::ProcessJob> =
        std::sync::OnceLock::new();
    let job = cadrumo_manager::process_job::ProcessJob::new()
        .and_then(|job| job.contain_current().map(|()| job))
        .map_err(|cause| {
            ApplicationError::new(ErrorCode::SpawnFailed, Operation::Launch).caused_by(cause)
        })?;
    let _ = APPLICATION.set(job);
    Ok(())
}

async fn check_health(launch: &environment::Launch, hold_seconds: u64) -> Result<i32> {
    let manager = Arc::new(manager::ManagerStart::new(launch));
    let sign_in = Arc::new(shell::sign_in::SignIn::new(launch));
    let outcome = async {
        manager.ensure_ready(&sign_in).await?;
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(hold_seconds);
        let mut lost_since = None;
        loop {
            let supervised = manager.supervision_status()?;
            app::supervision_continues(Ok(supervised), &mut lost_since, std::time::Instant::now())?;
            if std::time::Instant::now() >= deadline {
                // Supervision ready is not authentication. Require a fresh
                // canonical public runtime observation before health succeeds.
                let status = sign_in.read_status().await?;
                if !status.runtime_ready() || !manager.supervision_status()? {
                    return Err(ApplicationError::new(
                        ErrorCode::ManagerUnavailable,
                        Operation::Manager,
                    ));
                }
                return Ok(0);
            }
            tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        }
    }
    .await;
    if let Err(error) = &outcome {
        launch
            .diagnostics
            .host_failure(HostStage::Manager, error.clone());
    }
    let stopped = sign_in.stop().await;
    let supervision = manager.stop_owned().await;
    let closed = manager.close_checked().await;
    complete_health(outcome, [stopped, supervision, closed], &launch.diagnostics)
}

fn complete_health(
    mut outcome: Result<i32>,
    cleanup: [Result<()>; 3],
    diagnostics: &Diagnostics,
) -> Result<i32> {
    for result in cleanup {
        if let Err(error) = result {
            diagnostics.host_failure(HostStage::Shutdown, error.clone());
            if outcome.is_ok() {
                outcome = Err(error);
            }
        }
    }
    outcome
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
    // Every panic, on any thread and including one that cannot unwind, is recorded
    // before unwinding; the record never carries the payload the default hook prints.
    panic::install(diagnostics.clone());
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

#[cfg(test)]
mod health_tests {
    use super::*;

    #[test]
    fn startup_failure_remains_primary_when_each_cleanup_also_fails() {
        let outcome = complete_health(
            Err(ApplicationError::new(
                ErrorCode::TimedOut,
                Operation::Manager,
            )),
            std::array::from_fn(|_| {
                Err(ApplicationError::new(
                    ErrorCode::CleanupFailed,
                    Operation::Shutdown,
                ))
            }),
            &Diagnostics::default(),
        );
        assert_eq!(outcome.unwrap_err().code, ErrorCode::TimedOut);
    }

    #[test]
    fn otherwise_successful_health_rejects_each_cleanup_failure() {
        for failed in 0..3 {
            let outcome = complete_health(
                Ok(0),
                std::array::from_fn(|index| {
                    if index == failed {
                        Err(ApplicationError::new(
                            ErrorCode::CleanupFailed,
                            Operation::Shutdown,
                        ))
                    } else {
                        Ok(())
                    }
                }),
                &Diagnostics::default(),
            );
            assert_eq!(outcome.unwrap_err().code, ErrorCode::CleanupFailed);
        }
        assert_eq!(
            complete_health(Ok(0), [Ok(()), Ok(()), Ok(())], &Diagnostics::default()).unwrap(),
            0
        );
    }
}
