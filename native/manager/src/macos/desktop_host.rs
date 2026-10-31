//! Desktop-owned hosting of the canonical manager core on macOS, with arbitration
//! against a manager that already owns the session for the same storage root.
//!
//! The desktop claims the same per-session lock the installed manager claims for its
//! root, so a manager or desktop on another root is never consulted. While
//! another process holds it, that owner keeps the runtime: the desktop observes its
//! status over the authenticated manager socket and claims again at a steady pace,
//! taking over once the owner releases the lock. While the desktop holds it, it runs
//! the shared supervisor and serves the same socket. Closing drains only a
//! supervisor this desktop owns; another owner is never started, stopped or
//! signalled.

use crate::{
    background::Background,
    installed::InstalledRuntime,
    ipc::{self, Outcome, Request},
    macos::{activity, ipc::Server},
    session::{
        ManagerSession,
        instance::{SessionLock, claim_session, manager_id},
        ownership::StartKind,
    },
    supervision::environment::ManagedLocations,
    wake::{Notify, NotifyOnDrop, Slot},
};
use cadrumo_application::{
    diagnostics::{Diagnostics, EventKind, HostStage},
    error::application::{ApplicationError, ErrorCode, Operation},
};
use std::{
    io,
    path::{Path, PathBuf},
    sync::{
        Arc, Condvar, Mutex,
        atomic::{AtomicBool, Ordering},
        mpsc,
    },
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};

const CLOSE_BOUND: Duration = Duration::from_secs(35);
// Back-off before re-admitting after a transient host fault.
const RESTART_DELAY: Duration = Duration::from_secs(1);
// Pacing: how often another owner's status is read and the lock claimed again.
const EXTERNAL_PACE: Duration = Duration::from_secs(1);
// Pacing: the owned supervisor and its socket are polled at the manager's own
// interval, since neither offers a waitable readiness here.
const OWNER_PACE: Duration = Duration::from_millis(50);

enum Command {
    Retry,
    Close,
}

/// Wakes the worker before its next paced pass.
#[derive(Default)]
struct Wake {
    pending: Mutex<bool>,
    changed: Condvar,
}

impl Wake {
    fn set(&self) {
        *self
            .pending
            .lock()
            .unwrap_or_else(|error| error.into_inner()) = true;
        self.changed.notify_all();
    }

    /// Waits until woken or `deadline`, consuming the wake.
    fn wait_until(&self, deadline: Instant) {
        let mut pending = self
            .pending
            .lock()
            .unwrap_or_else(|error| error.into_inner());
        while !*pending {
            let Some(remaining) = deadline.checked_duration_since(Instant::now()) else {
                break;
            };
            pending = self
                .changed
                .wait_timeout(pending, remaining)
                .unwrap_or_else(|error| error.into_inner())
                .0;
        }
        *pending = false;
    }
}

struct Inbox {
    commands: mpsc::Receiver<Command>,
    wake: Arc<Wake>,
}

struct Owner {
    background: Background,
    server: Server,
    _claim: SessionLock,
}

/// The worker's latest outcome; every change, and the worker's end, is notified.
struct Published {
    outcome: Mutex<Outcome>,
    changed: Slot,
}

impl Published {
    fn new(outcome: Outcome) -> Self {
        Self {
            outcome: Mutex::new(outcome),
            changed: Slot::default(),
        }
    }

    fn get(&self) -> Outcome {
        *self
            .outcome
            .lock()
            .unwrap_or_else(|error| error.into_inner())
    }

    fn set(&self, outcome: Outcome) {
        let mut current = self
            .outcome
            .lock()
            .unwrap_or_else(|error| error.into_inner());
        if *current != outcome {
            *current = outcome;
            drop(current);
            self.changed.notify();
        }
    }
}

/// The desktop's supervision: its own hosted core, or its observation of another owner.
pub struct DesktopHost {
    commands: mpsc::SyncSender<Command>,
    wake: Arc<Wake>,
    state: Arc<Published>,
    worker: Option<JoinHandle<io::Result<()>>>,
    closed: Arc<AtomicBool>,
    diagnostics: Arc<Diagnostics>,
}

impl DesktopHost {
    /// Starts supervision for the package and storage root this desktop runs from.
    /// An external manager image is not consulted: the session's owner is reached
    /// only at an exact image of this package.
    pub fn start(
        package: &Path,
        root: &Path,
        _external_manager: Option<PathBuf>,
        diagnostics: Arc<Diagnostics>,
    ) -> io::Result<Self> {
        let locations = ManagedLocations::for_host(&std::env::current_exe()?, package, root)?;
        let (send, receive) = mpsc::sync_channel(16);
        let wake = Arc::new(Wake::default());
        let inbox = Inbox {
            commands: receive,
            wake: wake.clone(),
        };
        let state = Arc::new(Published::new(Outcome::Starting));
        let observed = state.clone();
        let closed = Arc::new(AtomicBool::new(false));
        let stopping = closed.clone();
        let recorded = diagnostics.clone();
        let worker = thread::Builder::new()
            .name("desktop-manager".into())
            .spawn(move || {
                // A finished worker is a status change the host observes too.
                let _ended = NotifyOnDrop(observed.changed.clone());
                let mut failures = 0;
                loop {
                    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                        run(
                            &locations,
                            diagnostics.clone(),
                            &inbox,
                            &stopping,
                            &observed,
                        )
                    }))
                    .unwrap_or_else(|_| {
                        diagnostics
                            .contained_panic(Some(HostStage::Supervision), Operation::Manager);
                        Err(io::Error::other("desktop supervisor failed"))
                    });
                    if result.is_ok() || stopping.load(Ordering::Acquire) || failures == 3 {
                        if result.is_err() {
                            observed.set(Outcome::Unavailable);
                        }
                        return result;
                    }
                    // The failed owner has drained before re-admission.
                    failures += 1;
                    observed.set(Outcome::Starting);
                    inbox.wake.wait_until(Instant::now() + RESTART_DELAY);
                    if stopping.load(Ordering::Acquire) {
                        return result;
                    }
                }
            })?;
        Ok(Self {
            commands: send,
            wake,
            state,
            worker: Some(worker),
            closed,
            diagnostics: recorded,
        })
    }

    pub fn status(&self) -> Outcome {
        self.state.get()
    }

    /// Notify on every status change and when the worker finishes. Changes
    /// before installation are not delivered, so read the status after it.
    pub fn notify_with(&self, notify: Notify) {
        self.state.changed.install(notify);
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
            .map_err(|_| io::Error::from(io::ErrorKind::WouldBlock))?;
        self.wake.set();
        Ok(())
    }

    pub fn close(mut self) -> io::Result<()> {
        self.close_with_bound(CLOSE_BOUND)
    }

    fn close_with_bound(&mut self, bound: Duration) -> io::Result<()> {
        // A full control queue must not lose the close fence.
        self.closed.store(true, Ordering::Release);
        let _ = self.commands.try_send(Command::Close);
        self.wake.set();
        self.join_with_bound(bound)
    }

    fn join_with_bound(&mut self, bound: Duration) -> io::Result<()> {
        let deadline = Instant::now() + bound;
        while self
            .worker
            .as_ref()
            .is_some_and(|worker| !worker.is_finished())
        {
            if Instant::now() >= deadline {
                // The worker keeps its runtime custody and session claim until it
                // ends; the host receives a bounded failure and exits as failed.
                self.worker.take();
                return Err(io::ErrorKind::TimedOut.into());
            }
            thread::sleep(Duration::from_millis(10));
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
        if self.worker.is_some()
            && let Err(error) = self.close_with_bound(CLOSE_BOUND)
        {
            self.diagnostics.host_failure(
                HostStage::Shutdown,
                ApplicationError::new(ErrorCode::CleanupFailed, Operation::Manager)
                    .caused_by(error),
            );
        }
    }
}

fn run(
    locations: &ManagedLocations,
    diagnostics: Arc<Diagnostics>,
    inbox: &Inbox,
    closed: &AtomicBool,
    state: &Published,
) -> io::Result<()> {
    if closed.load(Ordering::Acquire) {
        return Ok(());
    }
    let installed = InstalledRuntime::inspect(locations)
        .map_err(|error| crate::diagnostics::inspection_failed(&diagnostics, error))?;
    let package = locations.package_root().to_path_buf();
    let manager_id = manager_id(locations.storage_root())?;
    let mut owner: Option<Owner> = None;
    let mut closing = false;
    let mut terminal_error = None;
    let mut next_external = Instant::now();
    loop {
        closing |= closed.load(Ordering::Acquire);
        let mut retry = false;
        for command in inbox.commands.try_iter() {
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
                    server.poll(|_, request| match request {
                        Request::Status { .. } => ipc::status(background.status()),
                        other => ipc::respond(other, || background.retry()),
                    })?;
                }
                Ok(())
            }))
            .unwrap_or_else(|_| {
                diagnostics.contained_panic(Some(HostStage::Supervision), Operation::Manager);
                Err(io::Error::other("desktop supervisor poll failed"))
            });
            if let Err(error) = polled {
                closing = true;
                if terminal_error.is_none() {
                    terminal_error = Some(error);
                }
            }
            state.set(ipc::status(background.status()).outcome);
            if closing && background.quit_completed() {
                return terminal_error.map_or(Ok(()), Err);
            }
            inbox.wake.wait_until(Instant::now() + OWNER_PACE);
            continue;
        }
        if closing {
            // An externally owned manager and runtime are never stopped by this host.
            return Ok(());
        }
        if retry || Instant::now() >= next_external {
            if let Some(claim) = claim_session(&manager_id, Duration::ZERO)? {
                diagnostics.host_event(EventKind::StageStarted, HostStage::Admission);
                let server = Server::bind_embedded(&package, &claim)?;
                let background = Background::new(
                    installed.clone(),
                    ManagerSession::current()?,
                    activity::activity,
                    diagnostics.clone(),
                    StartKind::Manual,
                )?;
                diagnostics.host_event(EventKind::StageCompleted, HostStage::Admission);
                owner = Some(Owner {
                    background,
                    server,
                    _claim: claim,
                });
                continue;
            }
            let request = if retry {
                Request::Retry { schema: 1 }
            } else {
                Request::Status { schema: 1 }
            };
            let response = crate::macos::ipc::request_host(&manager_id, &package, &request);
            state.set(response.map_or(Outcome::Waiting, |reply| reply.outcome));
            next_external = Instant::now() + EXTERNAL_PACE;
        }
        inbox.wake.wait_until(next_external);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_wake_ends_a_wait_early_and_is_consumed() {
        let wake = Arc::new(Wake::default());
        let waking = wake.clone();
        let started = Instant::now();
        let waker = thread::spawn(move || {
            thread::sleep(Duration::from_millis(50));
            waking.set();
        });
        wake.wait_until(Instant::now() + Duration::from_secs(10));
        assert!(started.elapsed() < Duration::from_secs(5));
        waker.join().unwrap();
        let started = Instant::now();
        wake.wait_until(Instant::now() + Duration::from_millis(100));
        assert!(started.elapsed() >= Duration::from_millis(90));
    }

    #[test]
    fn only_a_changed_status_and_the_workers_end_reach_the_notify() {
        let published = Arc::new(Published::new(Outcome::Starting));
        let count = Arc::new(std::sync::atomic::AtomicUsize::new(0));
        let counted = count.clone();
        published.changed.install(Arc::new(move || {
            counted.fetch_add(1, Ordering::SeqCst);
        }));
        published.set(Outcome::Starting);
        assert_eq!(count.load(Ordering::SeqCst), 0);
        published.set(Outcome::Running);
        published.set(Outcome::Running);
        assert_eq!(count.load(Ordering::SeqCst), 1);
        let ended = published.changed.clone();
        thread::spawn(move || {
            let _ended = NotifyOnDrop(ended);
        })
        .join()
        .unwrap();
        assert_eq!(count.load(Ordering::SeqCst), 2);
    }
}
