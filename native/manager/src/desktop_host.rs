//! Desktop-owned hosting of the canonical manager core, with installed-owner arbitration.

use crate::{
    background::Background,
    change_watch::ChangeWatch,
    identity,
    installed::InstalledRuntime,
    ipc::{self, Outcome, Request},
    session::{
        ManagerSession,
        instance::{SessionRelease, claim_session},
        ownership::StartKind,
        status_cue::{StatusPublisher, owner_publishes, status_cue_directory},
    },
    supervision::environment::ManagedLocations,
    wake::{
        Notify, NotifyOnDrop, Slot,
        windows::{Event, Readiness, wait_thread},
    },
    windows_lifecycle,
};
use cadrumo_application::{
    component::Cancellation,
    diagnostics::{Diagnostics, EventKind, HostStage},
    error::application::{ApplicationError, ErrorCode, Operation},
};
use std::{
    io,
    os::windows::io::AsHandle,
    path::{Path, PathBuf},
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
        mpsc,
    },
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};

const CLOSE_BOUND: Duration = Duration::from_secs(35);
// Back-off before re-admitting after a transient host fault.
const RESTART_DELAY: Duration = Duration::from_secs(1);
// Pacing: another manager owns the runtime but publishes no status record, as an
// older manager does, so its status is observed at this interval.
const EXTERNAL_PACE: Duration = Duration::from_secs(1);
// Pacing: a full supervisor input queue publishes no notification when it drains.
const CLOSE_RETRY: Duration = Duration::from_millis(100);

enum Command {
    Retry,
    Close,
}

/// The worker's command queue and the event signaled after each command.
struct Inbox {
    commands: mpsc::Receiver<Command>,
    wake: Arc<Event>,
}

struct Owner {
    background: Background,
    server: ipc::windows::Server,
    /// Tells another observing desktop when this owner's status changes.
    status_record: Option<StatusPublisher>,
    _claim: crate::session::instance::SessionLock,
}

/// What wakes a desktop observing another manager: a rewrite of that manager's
/// status record, and the release of its session lock.
struct ExternalOwner {
    changes: ChangeWatch,
    release: Option<SessionRelease>,
}

impl ExternalOwner {
    fn watch(manager_id: &str, storage_root: &Path) -> Self {
        let mut changes = ChangeWatch::default();
        changes.directory(status_cue_directory(storage_root), false);
        Self {
            changes,
            release: SessionRelease::watch(manager_id).ok(),
        }
    }
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

/// The worker owns its thread-affine session claim through final runtime settlement.
pub struct DesktopHost {
    commands: mpsc::SyncSender<Command>,
    /// Signaled after each command, so the worker never polls its queue.
    wake: Arc<Event>,
    state: Arc<Published>,
    worker: Option<JoinHandle<io::Result<()>>>,
    closed: Arc<AtomicBool>,
    cancellation: Arc<Cancellation>,
    diagnostics: Arc<Diagnostics>,
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
        let wake = Event::new()?;
        let inbox = Inbox {
            commands: receive,
            wake: wake.clone(),
        };
        let state = Arc::new(Published::new(Outcome::Starting));
        let observed = state.clone();
        let closed = Arc::new(AtomicBool::new(false));
        let stopping = closed.clone();
        let cancellation = Arc::new(Cancellation::default());
        let admission_cancellation = cancellation.clone();
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
                            external_manager.as_deref(),
                            diagnostics.clone(),
                            &inbox,
                            &stopping,
                            &observed,
                            &admission_cancellation,
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
                    // The failed owner has drained and joined before re-admission.
                    // Retry transient host faults without leaving a cached dead worker.
                    failures += 1;
                    observed.set(Outcome::Starting);
                    let resume = Instant::now() + RESTART_DELAY;
                    while Instant::now() < resume {
                        if stopping.load(Ordering::Acquire) {
                            return result;
                        }
                        // Close signals the wake after publishing `stopping`;
                        // queued retries remain for the next admission.
                        let mut readiness = Readiness::default();
                        readiness.handle(inbox.wake.as_handle());
                        readiness.at(resume);
                        readiness.wait()?;
                    }
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
            cancellation,
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
        self.cancellation.cancel();
        let _ = self.commands.try_send(Command::Close);
        self.wake.set();
        self.join_with_bound(bound)
    }

    fn join(&mut self) -> io::Result<()> {
        self.join_with_bound(CLOSE_BOUND)
    }

    fn join_with_bound(&mut self, bound: Duration) -> io::Result<()> {
        if let Some(worker) = &self.worker
            && !wait_thread(worker, bound)?
        {
            // The dedicated worker remains a custody anchor: its exact
            // runtime handle and thread-affine claim stay held until death.
            // The host receives a bounded failure and must exit as failed.
            self.worker.take();
            return Err(io::ErrorKind::TimedOut.into());
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
            self.wake.set();
            if let Err(error) = self.join() {
                self.diagnostics.host_failure(
                    HostStage::Shutdown,
                    ApplicationError::new(ErrorCode::CleanupFailed, Operation::Manager)
                        .caused_by(error),
                );
            }
        }
    }
}

fn run(
    locations: &ManagedLocations,
    external_manager: Option<&Path>,
    diagnostics: Arc<Diagnostics>,
    inbox: &Inbox,
    closed: &AtomicBool,
    state: &Published,
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
    let mut close_refused = false;
    let mut terminal_error = None;
    let storage_root = installed.target.storage_root().to_path_buf();
    let session = ManagerSession::current()?.session;
    let mut external: Option<ExternalOwner> = None;
    // Due at once when another owner is first found; afterwards only when it
    // publishes no status record or its lock cannot be watched.
    let mut next_external = Some(Instant::now());
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
            background,
            server,
            status_record,
            ..
        }) = &mut owner
        {
            let polled = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                close_refused = false;
                if closing {
                    if let Err(error) = background.close_host() {
                        if error.kind() != io::ErrorKind::WouldBlock {
                            return Err(error);
                        }
                        close_refused = true;
                    }
                } else if retry {
                    background.retry()?;
                }
                background.poll()?;
                if let Some(record) = status_record {
                    record.publish(background.status());
                }
                if !closing {
                    server.poll(|request| match request {
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
        } else if closing {
            // An externally owned manager and runtime are never stopped by this host.
            return Ok(());
        } else if !external_due(
            &mut external,
            &manager_id,
            &storage_root,
            retry,
            next_external,
        ) {
            // Woken by nothing that concerns the external owner.
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
            )?;
            diagnostics.host_event(EventKind::StageCompleted, HostStage::Admission);
            external = None;
            owner = Some(Owner {
                background,
                server,
                status_record: StatusPublisher::new(&storage_root, &session).ok(),
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
            state.set(response.map_or(Outcome::Waiting, |reply| reply.outcome));
            let signalled = external
                .as_ref()
                .is_some_and(|watch| watch.release.is_some())
                && owner_publishes(&storage_root, &session);
            next_external = (!signalled).then(|| Instant::now() + EXTERNAL_PACE);
        }
        let mut readiness = Readiness::default();
        readiness.handle(inbox.wake.as_handle());
        match &owner {
            Some(Owner {
                background, server, ..
            }) => {
                background.readiness(&mut readiness);
                // A closing owner no longer serves its pipe; a completed
                // operation it leaves unpolled stays signaled.
                if !closing {
                    server.readiness(&mut readiness);
                }
                if close_refused {
                    readiness.after(CLOSE_RETRY);
                }
            }
            None => {
                if let Some(watch) = &external {
                    watch.changes.readiness(&mut readiness);
                    if let Some(release) = &watch.release {
                        readiness.handle(release.handle());
                    }
                }
                if let Some(at) = next_external {
                    readiness.at(at);
                }
            }
        }
        readiness.wait()?;
    }
}

/// Whether another owner needs observing now: asked to retry, its lock was
/// released, its status record changed, or its paced observation is due.
fn external_due(
    external: &mut Option<ExternalOwner>,
    manager_id: &str,
    storage_root: &Path,
    retry: bool,
    next_external: Option<Instant>,
) -> bool {
    let watch = external.get_or_insert_with(|| ExternalOwner::watch(manager_id, storage_root));
    // Both are taken every pass, so neither leaves a signaled handle behind.
    let released = watch.release.as_ref().is_some_and(SessionRelease::take);
    let changed = watch.changes.take();
    retry || released || changed || next_external.is_some_and(|at| Instant::now() >= at)
}

#[cfg(test)]
mod tests {
    use super::*;

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
        assert_eq!(published.get(), Outcome::Running);
        let ended = published.changed.clone();
        thread::spawn(move || {
            let _ended = NotifyOnDrop(ended);
        })
        .join()
        .unwrap();
        assert_eq!(count.load(Ordering::SeqCst), 2);
    }
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
            wake: Event::new().unwrap(),
            state: Arc::new(Published::new(Outcome::Stopping)),
            worker: Some(worker),
            closed: closed.clone(),
            cancellation,
            diagnostics: Arc::new(Diagnostics::default()),
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

    /// Wait as the host does for an external owner, bounded by `bound`, then
    /// answer whether that owner needs observing.
    fn woken_for_external(
        external: &mut Option<ExternalOwner>,
        manager_id: &str,
        root: &Path,
        bound: Duration,
    ) -> bool {
        if let Some(watch) = external.as_ref() {
            let mut readiness = Readiness::default();
            watch.changes.readiness(&mut readiness);
            if let Some(release) = &watch.release {
                readiness.handle(release.handle());
            }
            readiness.after(bound);
            readiness.wait().unwrap();
        }
        external_due(external, manager_id, root, false, None)
    }

    #[test]
    fn another_owners_status_change_and_release_each_wake_the_observer_and_nothing_else_does() {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let manager_id = format!("test.desktop.external.{}.{nanos}", std::process::id());
        let root =
            std::env::temp_dir().join(format!("desktop-external-{}-{nanos}", std::process::id()));
        crate::custody::ensure_local_directory(&root).unwrap();
        let session = ManagerSession::current().unwrap().session;
        let (claimed, ready) = mpsc::channel();
        let (step, steps) = mpsc::channel::<&'static str>();
        let owner_id = manager_id.clone();
        let owner_root = root.clone();
        let owner_session = session.clone();
        // Another manager: holds the session lock and publishes its status.
        let other = thread::spawn(move || {
            let _claim = claim_session(&owner_id, Duration::ZERO).unwrap().unwrap();
            let mut record = StatusPublisher::new(&owner_root, &owner_session).unwrap();
            record.publish("starting");
            claimed.send(()).unwrap();
            while let Ok(status) = steps.recv() {
                if status == "release" {
                    return;
                }
                record.publish(status);
            }
        });
        ready.recv_timeout(Duration::from_secs(5)).unwrap();
        assert!(owner_publishes(&root, &session));
        let mut external = None;
        // Finding the owner arms the watches; nothing has happened since.
        assert!(!external_due(
            &mut external,
            &manager_id,
            &root,
            false,
            None
        ));
        assert!(external.as_ref().unwrap().release.is_some());
        let started = Instant::now();
        assert!(!woken_for_external(
            &mut external,
            &manager_id,
            &root,
            Duration::from_millis(400)
        ));
        assert!(started.elapsed() >= Duration::from_millis(350));
        step.send("running").unwrap();
        assert!(woken_for_external(
            &mut external,
            &manager_id,
            &root,
            Duration::from_secs(5)
        ));
        while woken_for_external(
            &mut external,
            &manager_id,
            &root,
            Duration::from_millis(200),
        ) {}
        assert!(
            claim_session(&manager_id, Duration::ZERO)
                .unwrap()
                .is_none(),
            "the observer holds no acquisition of a held lock"
        );
        step.send("release").unwrap();
        other.join().unwrap();
        assert!(woken_for_external(
            &mut external,
            &manager_id,
            &root,
            Duration::from_secs(5)
        ));
        // The observer gave its acquisition back, so its claim decides the takeover.
        drop(external);
        assert!(
            claim_session(&manager_id, Duration::ZERO)
                .unwrap()
                .is_some()
        );
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn terminal_worker_failure_is_joined_and_never_reported_as_clean_close() {
        let (commands, _unread) = mpsc::sync_channel(0);
        let worker = thread::spawn(|| Err(io::Error::from_raw_os_error(47)));
        let mut host = DesktopHost {
            commands,
            wake: Event::new().unwrap(),
            state: Arc::new(Published::new(Outcome::Unavailable)),
            worker: Some(worker),
            closed: Arc::new(AtomicBool::new(false)),
            cancellation: Arc::new(Cancellation::default()),
            diagnostics: Arc::new(Diagnostics::default()),
        };
        assert_eq!(
            host.close_with_bound(Duration::from_secs(1))
                .unwrap_err()
                .raw_os_error(),
            Some(47)
        );
        assert!(host.worker.is_none());
    }

    #[test]
    fn commands_wake_a_waiting_worker_and_close_returns_when_it_does() {
        // Each latency is far below the former 100 ms poll; the fastest of
        // several runs tolerates an occasional scheduling delay.
        let mut retries = Vec::new();
        let mut closes = Vec::new();
        for _ in 0..5 {
            let (commands, receive) = mpsc::sync_channel(16);
            let wake = Event::new().unwrap();
            let woken = wake.clone();
            let (observed, retried) = mpsc::channel();
            let worker = thread::spawn(move || -> io::Result<()> {
                loop {
                    let mut readiness = Readiness::default();
                    readiness.handle(woken.as_handle());
                    readiness.after(Duration::from_secs(5));
                    readiness.wait()?;
                    for command in receive.try_iter() {
                        match command {
                            Command::Retry => observed.send(Instant::now()).unwrap(),
                            Command::Close => return Ok(()),
                        }
                    }
                }
            });
            let mut host = DesktopHost {
                commands,
                wake,
                state: Arc::new(Published::new(Outcome::Starting)),
                worker: Some(worker),
                closed: Arc::new(AtomicBool::new(false)),
                cancellation: Arc::new(Cancellation::default()),
                diagnostics: Arc::new(Diagnostics::default()),
            };
            thread::sleep(Duration::from_millis(20));
            let requested = Instant::now();
            host.retry().unwrap();
            let seen = retried.recv_timeout(Duration::from_secs(5)).unwrap();
            retries.push(seen.saturating_duration_since(requested));
            let closing = Instant::now();
            host.close_with_bound(Duration::from_secs(5)).unwrap();
            closes.push(closing.elapsed());
            assert!(host.worker.is_none());
        }
        let fastest = |latencies: &[Duration]| latencies.iter().min().copied().unwrap();
        assert!(fastest(&retries) < Duration::from_millis(50), "{retries:?}");
        assert!(fastest(&closes) < Duration::from_millis(50), "{closes:?}");
    }
}
