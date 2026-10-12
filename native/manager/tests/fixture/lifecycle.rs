//! Debug-only driver of the canonical Background owner against a real package.
//! Fixture root selection never makes the shipping manager eligible for test paths.

#[cfg(windows)]
fn run() -> std::io::Result<()> {
    use cadrumo_application::diagnostics::{
        DiagnosticSource, Diagnostics,
        lifecycle::{Effects, LifecycleFact, SupervisorOutcome},
    };
    use cadrumo_manager::{
        background::Background,
        installed::InstalledRuntime,
        session::{ManagerSession, ownership::StartKind},
        supervision::environment::ManagedLocations,
    };
    use serde_json::json;
    use std::{
        fs, io,
        io::Write,
        path::PathBuf,
        sync::Arc,
        thread,
        time::{Duration, Instant},
    };
    let raw: Vec<_> = std::env::args_os().skip(1).collect();
    let [package, root] = raw.as_slice() else {
        return Err(io::ErrorKind::InvalidInput.into());
    };
    let package = fs::canonicalize(PathBuf::from(package))?;
    let root = cadrumo_platform::storage::validated_absolute_path(&PathBuf::from(root))
        .map_err(io::Error::from)?;
    if fs::read(root.join("lifecycle-owned-root"))? != b"cadrumo-process-lifecycle-v1\n" {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    let locations = ManagedLocations::fixture(package, root.clone())?;
    let started = Instant::now();
    let mut output = fs::File::create(root.join("manager-events.jsonl"))?;
    let mut stage = "package_inspection";
    let mut reason = "driver_io_failure";
    let result = (|| {
        let installed = InstalledRuntime::inspect(&locations).map_err(io::Error::other)?;
        stage = "session_context";
        let diagnostics = Arc::new(Diagnostics::new(DiagnosticSource::Manager));
        let mut background = Background::new(
            installed,
            ManagerSession::current()?,
            cadrumo_manager::windows_lifecycle::activity,
            diagnostics.clone(),
            StartKind::Manual,
        );
        stage = "supervision";
        let mut sequence = 0;
        let mut stopping = false;
        let mut failed = None;
        let mut settled = false;
        loop {
            stopping |= root.join("manager-stop").exists()
                || started.elapsed() > Duration::from_secs(1200)
                || failed.is_some();
            if stopping
                && let Err(error) = background.close_host()
                && error.kind() != io::ErrorKind::WouldBlock
            {
                failed.get_or_insert(error);
            }
            if let Err(error) = background.poll() {
                failed.get_or_insert(error);
            }
            // Observe the actual owner, including automatic adopted-process drain,
            // completion/join and genuine control readiness before replacement.
            // Snapshot retains lifecycle history; its cursor filters only output.
            let after = sequence;
            for event in diagnostics.snapshot(after).events {
                if event.sequence <= after {
                    continue;
                }
                sequence = sequence.max(event.sequence);
                let Some(fact) = event.lifecycle else {
                    continue;
                };
                let (kind, pid) = match fact {
                    LifecycleFact::Launched { pid } => ("launched", Some(pid)),
                    LifecycleFact::Ready { pid } => ("ready", Some(pid)),
                    LifecycleFact::Adopted { pid } => ("adopted", Some(pid)),
                    LifecycleFact::Exited { pid, .. } => ("exited", Some(pid)),
                    LifecycleFact::BootRecordConfirmed { pid } => ("boot_confirmed", Some(pid)),
                    LifecycleFact::RestartScheduled { .. } => ("restart_scheduled", None),
                    LifecycleFact::HangDetected { pid, .. } => ("hang_detected", Some(pid)),
                    LifecycleFact::LaunchFailed {} => ("launch_failed", None),
                    LifecycleFact::SupervisorEnded { result } => {
                        settled = matches!(
                            result,
                            SupervisorOutcome::Stopped {
                                effects: Effects::Settled
                            }
                        );
                        ("supervisor_ended", None)
                    }
                    _ => ("other", None),
                };
                if let Err(error) = writeln!(
                    output,
                    "{}",
                    json!({
                        "kind": kind, "pid": pid, "sequence": event.sequence,
                        "seconds": started.elapsed().as_secs_f64(),
                        "manager_status": background.status()
                    })
                )
                .and_then(|()| output.flush())
                {
                    failed.get_or_insert(error);
                }
            }
            if stopping && background.quit_completed() {
                return failed.map_or_else(
                    || {
                        if settled {
                            Ok(())
                        } else {
                            reason = "effects_unsettled";
                            Err(io::Error::other("manager did not settle"))
                        }
                    },
                    Err,
                );
            }
            thread::sleep(Duration::from_millis(50));
        }
    })();
    if let Err(error) = &result {
        // Keep only public typed facts; Display may contain paths or private data.
        let _ = writeln!(
            output,
            "{}",
            json!({
                "kind": "driver_failed", "pid": null,
                "seconds": started.elapsed().as_secs_f64(), "manager_status": null,
                "error_kind": format!("{:?}", error.kind()), "raw_native_code": error.raw_os_error(),
                "reason": reason, "stage": stage
            })
        )
        .and_then(|()| output.flush());
    }
    result
}

fn main() -> std::process::ExitCode {
    #[cfg(windows)]
    match run() {
        Ok(()) => std::process::ExitCode::SUCCESS,
        Err(_) => {
            eprintln!("lifecycle_manager_failed");
            std::process::ExitCode::from(69)
        }
    }
    #[cfg(not(windows))]
    std::process::ExitCode::from(69)
}
