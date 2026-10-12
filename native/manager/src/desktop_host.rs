//! Desktop-owned hosting of the canonical manager core, with installed-owner arbitration.

use crate::{
    background::Background,
    identity,
    installed::InstalledRuntime,
    ipc::{self, Outcome, Request},
    session::{ManagerSession, instance::claim_session, ownership::StartKind},
    supervision::environment::ManagedLocations,
    windows_lifecycle,
};
use cadrumo_application::{
    component::Cancellation,
    diagnostics::{Diagnostics, EventKind, HostStage},
};
use std::{
    io,
    path::{Path, PathBuf},
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
        mpsc,
    },
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};

const POLL: Duration = Duration::from_millis(100);
const CLOSE_BOUND: Duration = Duration::from_secs(35);

enum Command {
    Retry,
    Close,
}

struct Owner {
    background: Background,
    server: ipc::windows::Server,
    _claim: crate::session::instance::SessionLock,
}

/// The worker owns its thread-affine session claim through final runtime settlement.
pub struct DesktopHost {
    commands: mpsc::SyncSender<Command>,
    state: Arc<Mutex<Outcome>>,
    worker: Option<JoinHandle<io::Result<()>>>,
    closed: Arc<AtomicBool>,
    cancellation: Arc<Cancellation>,
}

impl DesktopHost {
    pub fn start(
        package: &Path,
        root: &Path,
        external_manager: Option<PathBuf>,
        diagnostics: Arc<Diagnostics>,
    ) -> io::Result<Self> {
        let locations = ManagedLocations::for_host(&std::env::current_exe()?, package, root)?;
        let (send, receive) = mpsc::sync_channel(16);
        let state = Arc::new(Mutex::new(Outcome::Starting));
        let observed = state.clone();
        let closed = Arc::new(AtomicBool::new(false));
        let stopping = closed.clone();
        let cancellation = Arc::new(Cancellation::default());
        let admission_cancellation = cancellation.clone();
        let worker = thread::Builder::new()
            .name("desktop-manager".into())
            .spawn(move || {
                let mut failures = 0;
                loop {
                    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                        run(
                            &locations,
                            external_manager.as_deref(),
                            diagnostics.clone(),
                            &receive,
                            &stopping,
                            &observed,
                            &admission_cancellation,
                        )
                    }))
                    .unwrap_or_else(|_| Err(io::Error::other("desktop supervisor failed")));
                    if result.is_ok() || stopping.load(Ordering::Acquire) || failures == 3 {
                        if result.is_err() {
                            *observed.lock().unwrap_or_else(|error| error.into_inner()) =
                                Outcome::Unavailable;
                        }
                        return result;
                    }
                    // The failed owner has drained and joined before re-admission.
                    // Retry transient host faults without leaving a cached dead worker.
                    failures += 1;
                    *observed.lock().unwrap_or_else(|error| error.into_inner()) = Outcome::Starting;
                    for _ in 0..10 {
                        if stopping.load(Ordering::Acquire) {
                            return result;
                        }
                        thread::sleep(POLL);
                    }
                }
            })?;
        Ok(Self {
            commands: send,
            state,
            worker: Some(worker),
            closed,
            cancellation,
        })
    }

    pub fn status(&self) -> Outcome {
        *self.state.lock().unwrap_or_else(|error| error.into_inner())
    }

    pub fn finished(&self) -> bool {
        self.worker.as_ref().is_none_or(JoinHandle::is_finished)
    }

    pub fn retry(&self) -> io::Result<()> {
        if self.closed.load(Ordering::Acquire) {
            return Err(io::ErrorKind::BrokenPipe.into());
        }
        self.commands
            .try_send(Command::Retry)
            .map_err(|_| io::ErrorKind::WouldBlock.into())
    }

    pub fn close(mut self) -> io::Result<()> {
        self.close_with_bound(CLOSE_BOUND)
    }

    fn close_with_bound(&mut self, bound: Duration) -> io::Result<()> {
        // A full control queue must not lose the close fence.
        self.closed.store(true, Ordering::Release);
        self.cancellation.cancel();
        let _ = self.commands.try_send(Command::Close);
        self.join_with_bound(bound)
    }

    fn join(&mut self) -> io::Result<()> {
        self.join_with_bound(CLOSE_BOUND)
    }

    fn join_with_bound(&mut self, bound: Duration) -> io::Result<()> {
        let deadline = Instant::now() + bound;
        while self
            .worker
            .as_ref()
            .is_some_and(|worker| !worker.is_finished())
        {
            if Instant::now() >= deadline {
                // The dedicated worker remains a custody anchor: its exact
                // runtime handle and thread-affine claim stay held until death.
                // The host receives a bounded failure and must exit as failed.
                self.worker.take();
                return Err(io::ErrorKind::TimedOut.into());
            }
            thread::sleep(POLL);
        }
        if let Some(worker) = self.worker.take() {
            worker
                .join()
                .map_err(|_| io::Error::other("desktop supervisor panicked"))??;
        }
        Ok(())
    }
}

impl Drop for DesktopHost {
    fn drop(&mut self) {
        if self.worker.is_some() {
            self.closed.store(true, Ordering::Release);
            self.cancellation.cancel();
            let _ = self.commands.try_send(Command::Close);
            let _ = self.join();
        }
    }
}

fn run(
    locations: &ManagedLocations,
    external_manager: Option<&Path>,
    diagnostics: Arc<Diagnostics>,
    commands: &mpsc::Receiver<Command>,
    closed: &AtomicBool,
    state: &Mutex<Outcome>,
    cancellation: &Cancellation,
) -> io::Result<()> {
    if closed.load(Ordering::Acquire) {
        return Ok(());
    }
    let installed = match InstalledRuntime::inspect_for_host(locations, cancellation, &diagnostics)
    {
        Ok(installed) => installed,
        Err(error) if closed.load(Ordering::Acquire) && error.is_cancelled() => return Ok(()),
        Err(error) => return Err(crate::diagnostics::inspection_failed(&diagnostics, error)),
    };
    let manager_id = if locations.is_default_root() {
        identity::MANAGER_ID.to_owned()
    } else {
        format!(
            "{}.root.{}",
            identity::MANAGER_ID,
            installed.target.storage_identity()
        )
    };
    let contract: cadrumo_application::installation::DiscoveryContract =
        serde_json::from_str(crate::contract::INSTALLATION_CONTRACT).map_err(io::Error::other)?;
    let own_manager = contract
        .manager_member()
        .map_err(io::Error::other)?
        .under(locations.package_root());
    let mut owner = None;
    let mut closing = false;
    let mut terminal_error = None;
    loop {
        closing |= closed.load(Ordering::Acquire);
        let mut retry = false;
        for command in commands.try_iter() {
            match command {
                Command::Close => closing = true,
                Command::Retry => retry = true,
            }
        }
        if let Some(Owner {
            background, server, ..
        }) = &mut owner
        {
            let polled = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                if closing {
                    if let Err(error) = background.close_host()
                        && error.kind() != io::ErrorKind::WouldBlock
                    {
                        return Err(error);
                    }
                } else if retry {
                    background.retry()?;
                }
                background.poll()?;
                if !closing {
                    server.poll(|request| match request {
                        Request::Status { .. } => ipc::status(background.status()),
                        other => ipc::respond(other, || background.retry()),
                    })?;
                }
                Ok(())
            }))
            .unwrap_or_else(|_| Err(io::Error::other("desktop supervisor poll failed")));
            if let Err(error) = polled {
                closing = true;
                if terminal_error.is_none() {
                    terminal_error = Some(error);
                }
            }
            *state.lock().unwrap_or_else(|error| error.into_inner()) =
                ipc::status(background.status()).outcome;
            if closing && background.quit_completed() {
                return terminal_error.map_or(Ok(()), Err);
            }
        } else if closing {
            // An externally owned manager and runtime are never stopped by this host.
            return Ok(());
        } else if let Some(claim) = claim_session(&manager_id, Duration::ZERO)? {
            diagnostics.host_event(EventKind::StageStarted, HostStage::Admission);
            let server =
                ipc::windows::Server::bind_embedded_root(locations.package_root(), &manager_id)?;
            let background = Background::new(
                installed.clone(),
                ManagerSession::current()?,
                windows_lifecycle::activity,
                diagnostics.clone(),
                StartKind::Manual,
            );
            diagnostics.host_event(EventKind::StageCompleted, HostStage::Admission);
            owner = Some(Owner {
                background,
                server,
                _claim: claim,
            });
        } else {
            let request = if retry {
                Request::Retry { schema: 1 }
            } else {
                Request::Status { schema: 1 }
            };
            let response = external_manager
                .filter(|_| locations.is_default_root())
                .map_or_else(
                    || ipc::windows::request_host(&manager_id, &own_manager, &request),
                    |manager| {
                        ipc::windows::request_host(&manager_id, manager, &request).or_else(|_| {
                            ipc::windows::request_host(&manager_id, &own_manager, &request)
                        })
                    },
                );
            *state.lock().unwrap_or_else(|error| error.into_inner()) =
                response.map_or(Outcome::Waiting, |reply| reply.outcome);
        }
        thread::sleep(POLL);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn full_control_queue_and_unsettled_worker_fail_bounded_without_releasing_native_claim() {
        let manager_id = format!(
            "test.desktop.{}.{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        );
        let (commands, _unread) = mpsc::sync_channel(0);
        let (claimed, ready) = mpsc::channel();
        let (release, gate) = mpsc::channel();
        let worker_id = manager_id.clone();
        let cancellation = Arc::new(Cancellation::default());
        let worker_cancellation = cancellation.clone();
        let worker = thread::spawn(move || {
            let _claim =
                claim_session(&worker_id, Duration::ZERO)?.ok_or(io::ErrorKind::WouldBlock)?;
            claimed.send(()).unwrap();
            let _ = gate.recv_timeout(Duration::from_secs(5));
            assert!(matches!(
                cadrumo_application::package::PackageManifest::read_cancellable(
                    Path::new("cancelled-admission-must-not-access-disk"),
                    &cadrumo_application::value::RelativePath::new("manifest.json").unwrap(),
                    &worker_cancellation,
                ),
                Err(cadrumo_application::error::Error::Cancelled)
            ));
            Err(io::Error::from_raw_os_error(47))
        });
        ready.recv_timeout(Duration::from_secs(5)).unwrap();
        let closed = Arc::new(AtomicBool::new(false));
        let mut host = DesktopHost {
            commands,
            state: Arc::new(Mutex::new(Outcome::Stopping)),
            worker: Some(worker),
            closed: closed.clone(),
            cancellation,
        };
        let started = Instant::now();
        assert_eq!(
            host.close_with_bound(Duration::from_millis(20))
                .unwrap_err()
                .kind(),
            io::ErrorKind::TimedOut
        );
        assert!(started.elapsed() < Duration::from_secs(1));
        assert!(closed.load(Ordering::Acquire));
        assert!(
            claim_session(&manager_id, Duration::ZERO)
                .unwrap()
                .is_none(),
            "timed-out custody stays with its actual worker"
        );
        release.send(()).unwrap();
        assert!(
            claim_session(&manager_id, Duration::from_secs(5))
                .unwrap()
                .is_some()
        );
    }

    #[test]
    fn terminal_worker_failure_is_joined_and_never_reported_as_clean_close() {
        let (commands, _unread) = mpsc::sync_channel(0);
        let worker = thread::spawn(|| Err(io::Error::from_raw_os_error(47)));
        let mut host = DesktopHost {
            commands,
            state: Arc::new(Mutex::new(Outcome::Unavailable)),
            worker: Some(worker),
            closed: Arc::new(AtomicBool::new(false)),
            cancellation: Arc::new(Cancellation::default()),
        };
        assert_eq!(
            host.close_with_bound(Duration::from_secs(1))
                .unwrap_err()
                .raw_os_error(),
            Some(47)
        );
        assert!(host.worker.is_none());
    }
}
