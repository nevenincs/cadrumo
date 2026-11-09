//! Lifetime of one admitted manager, independent of the native event loop.
//!
//! The manager runs the local AI server of the engine the person's selection record names,
//! and follows the record. An absent record is automatic placement on the engine the
//! package makes the default: llama.cpp where it carries the llama-server, Ollama
//! otherwise. A stored choice is kept whatever the package carries, and a record that
//! cannot be read runs no server at all. A rewrite of the record is noticed through a watch
//! of the storage root, on Windows, or at a bounded pace elsewhere. A rewrite that names
//! another engine stops the running server before the other engine's starts; one that
//! changes only the placement under llama.cpp reaches the running server's preset, which
//! drains and starts again once it holds no model.

use crate::{
    diagnostics,
    installed::InstalledRuntime,
    local_engine::{LocalEngineSelection, Recorded},
    session::{
        ManagerSession,
        ownership::{BootRecordLocator, Ownership, StartKind},
    },
    startup::{self, Running, Start},
    supervision::{
        local_ai::{LocalAiHost, server_address},
        stop::PlatformStopSignal,
        supervisor::{
            Collaborators, EVENT_QUEUE, Event, Outcome, Request, SessionActivity, SupervisorConfig,
        },
    },
};
use cadrumo_application::{
    diagnostics::{Diagnostics, EventKind, HostStage, lifecycle::LifecycleFact},
    error::application::{ApplicationError, ErrorCode, Operation},
    provisioning::local_ai::LocalEngine,
};
use std::{
    io,
    net::SocketAddr,
    path::{Path, PathBuf},
    sync::Arc,
    time::{Duration, Instant},
};

// A continuously replenished diagnostics queue must yield to native events.
const EVENTS_PER_POLL: usize = 64;
// Pacing: another owner's release and a changed ownership verdict publish no
// notification, so a waiting manager reassesses at this interval.
const OWNERSHIP_PACE: Duration = Duration::from_secs(1);
// Pacing: a full supervisor input queue publishes no notification when it drains.
const CONTROL_RETRY: Duration = Duration::from_millis(100);
// Pacing: where no directory notification exists, the selection record is read again at
// this interval.
#[cfg(not(windows))]
const SELECTION_PACE: Duration = Duration::from_secs(2);

pub struct Background {
    installed: InstalledRuntime,
    ownership: Ownership,
    activity: fn() -> Box<dyn SessionActivity>,
    running: Option<Running>,
    initial: Option<StartKind>,
    blocked: bool,
    quitting: bool,
    suspended: bool,
    session_end: SessionEnd,
    settlement_error_reported: bool,
    diagnostics: Arc<Diagnostics>,
    waiting: Option<LifecycleFact>,
    installation_watch: Option<Box<dyn crate::lifecycle::RemovalObservation>>,
    observation: Observation,
    cutover_pending: bool,
    update_failed: bool,
    reserved: Option<crate::session::claim::StartClaim>,
    designated: Option<crate::successor::InitialPermit>,
    reporter: Option<crate::successor::Reporter>,
    /// Signaled by supervisor observations and successor reports.
    #[cfg(windows)]
    wake: Arc<crate::wake::windows::Event>,
    backlog: bool,
    next_start: Option<Instant>,
    control_retry: Option<Instant>,
    /// A refused uninstall stop is retried at the control pace.
    stop_retry: Option<Instant>,
    /// The selected engine's local AI server, for a package that carries its program.
    local_ai: LocalAi,
}

impl Background {
    pub fn new(
        installed: InstalledRuntime,
        session: ManagerSession,
        activity: fn() -> Box<dyn SessionActivity>,
        diagnostics: Arc<Diagnostics>,
        initial: StartKind,
    ) -> io::Result<Self> {
        let local_ai = LocalAi::start(
            installed.target.package_root(),
            installed.target.storage_root(),
            &diagnostics,
        );
        let ownership = Ownership::new(
            installed.target.storage_root().to_path_buf(),
            session,
            activity(),
            Box::new(BootRecordLocator::new(installed.target.storage_root())),
        );
        Ok(Self {
            installed,
            ownership,
            activity,
            running: None,
            initial: Some(initial),
            blocked: false,
            quitting: false,
            suspended: false,
            session_end: SessionEnd::default(),
            settlement_error_reported: false,
            diagnostics,
            waiting: None,
            installation_watch: None,
            observation: Observation::default(),
            cutover_pending: false,
            update_failed: false,
            reserved: None,
            designated: None,
            reporter: None,
            #[cfg(windows)]
            wake: crate::wake::windows::Event::new()?,
            backlog: false,
            next_start: None,
            control_retry: None,
            stop_retry: None,
            local_ai,
        })
    }

    pub fn designated(
        &mut self,
        permit: crate::successor::InitialPermit,
        reporter: crate::successor::Reporter,
    ) {
        #[cfg(windows)]
        reporter.notify_with(self.wake.notifier());
        self.designated = Some(permit);
        self.reporter = Some(reporter);
    }

    /// Install the wake before the first drain: earlier observations are queued.
    fn supervise(&mut self, running: Running) {
        #[cfg(windows)]
        running.handle.notify_with(self.wake.notifier());
        self.backlog = true;
        self.running = Some(running);
    }

    /// What the host waits on before the next poll is due: the wake, the
    /// supervising worker's return, and the deadlines of paced observations.
    #[cfg(windows)]
    pub fn readiness<'a>(&'a self, into: &mut crate::wake::windows::Readiness<'a>) {
        use std::os::windows::io::AsHandle;
        into.handle(self.wake.as_handle());
        // While a refused stop waits for its retry, a supervisor that already
        // returned would keep its handle signalled and spin the wait.
        if self.stop_retry.is_none()
            && let Some(settlement) = self.running.as_ref().and_then(Running::settlement)
        {
            into.handle(settlement);
        }
        if !self.quitting
            && let Some(watch) = &self.installation_watch
        {
            watch.readiness(into);
        }
        self.local_ai.changes.readiness(into);
        if let Some(deadline) = self.next_deadline() {
            into.at(deadline);
        }
    }

    /// The nearest moment a poll is due without any notification.
    pub fn next_deadline(&self) -> Option<Instant> {
        let mut deadlines = Vec::with_capacity(4);
        if self.running.is_some() && self.backlog {
            deadlines.push(Instant::now());
        }
        deadlines.extend(self.control_retry);
        deadlines.extend(self.stop_retry);
        // Where no notification says the selection record changed, its paced look is due.
        #[cfg(not(windows))]
        deadlines.push(self.local_ai.changes.next_look);
        if self.running.is_none() && !self.start_withheld() {
            deadlines.push(self.next_start.unwrap_or_else(Instant::now));
        }
        deadlines.into_iter().min()
    }

    fn start_withheld(&self) -> bool {
        self.suspended || self.blocked || self.quitting || self.cutover_pending
    }
    pub fn storage_root(&self) -> &std::path::Path {
        self.installed.target.storage_root()
    }
    pub fn stopping(&self) -> bool {
        self.quitting || self.suspended
    }
    pub fn can_cutover(&self) -> bool {
        !self.quitting
            && !self.suspended
            && self.reporter.is_none()
            && ((self.running.is_some() && self.observation.ready && self.observation.confirmed)
                || (self.running.is_none()
                    && self.blocked
                    && self.observation.pid.is_some_and(|pid| {
                        matches!(
                            crate::supervision::process::open_process(pid),
                            Err(crate::supervision::process::InspectError::NotRunning)
                        )
                    })))
    }
    pub fn begin_cutover(&mut self) -> io::Result<Option<crate::session::claim::StartClaim>> {
        if !self.can_cutover() {
            return Ok(None);
        }
        let Some(claim) =
            crate::session::claim::StartClaim::take(self.storage_root(), Duration::ZERO)?
        else {
            return Ok(None);
        };
        if !(self.activity)().is_active()
            || !matches!(
                crate::session::quit::read_quit_marker(self.storage_root()),
                crate::session::quit::QuitState::Absent
            )
        {
            return Ok(None);
        }
        if let Some(running) = &self.running {
            if !running.handle.request(Request::StopIfIdle) {
                return Err(io::ErrorKind::WouldBlock.into());
            }
        } else {
            use crate::session::ownership::{Located, RuntimeLocator};
            if !matches!(
                BootRecordLocator::new(self.storage_root()).locate(),
                Located::Nothing
            ) {
                return Ok(None);
            }
        }
        self.cutover_pending = true;
        Ok(Some(claim))
    }
    pub fn idle_stopped(&self) -> bool {
        self.cutover_pending && self.running.is_none()
    }
    pub fn retry_idle(&self) {
        if self.cutover_pending
            && let Some(running) = &self.running
        {
            running.handle.request(Request::StopIfIdle);
        }
    }
    pub fn abandon_cutover(&mut self) {
        self.cutover_pending = false;
    }
    pub fn rollback(&mut self, claim: crate::session::claim::StartClaim) {
        self.cutover_pending = false;
        self.update_failed = true;
        self.blocked = false;
        self.reserved = Some(claim);
        self.next_start = None;
    }
    pub fn watch_installation(
        &mut self,
        observation: Box<dyn crate::lifecycle::RemovalObservation>,
    ) {
        self.installation_watch = Some(observation);
    }
    /// Confirmed native registration removal stops only this manager's
    /// owned runtime, without recording a user Quit preference or deleting files.
    fn uninstall(&mut self) -> io::Result<()> {
        if let Some(running) = &self.running
            && !running.handle.request(Request::Stop)
        {
            self.stop_retry = Some(Instant::now() + CONTROL_RETRY);
            return Err(io::ErrorKind::WouldBlock.into());
        }
        self.stop_retry = None;
        self.quitting = true;
        self.suspended = true;
        self.stop_local_ai();
        Ok(())
    }

    /// The local AI server stops with the runtime's supervision and starts nothing
    /// until supervision resumes. Its own thread carries the stop out.
    fn stop_local_ai(&mut self) {
        self.local_ai.stop();
    }

    pub fn poll(&mut self) -> io::Result<()> {
        // Re-armed only if this poll's uninstall is refused again.
        self.stop_retry = None;
        if let Some(result) = self.reporter.as_ref().and_then(|reporter| reporter.poll()) {
            self.reporter = None;
            if matches!(result, crate::successor::ReportResult::Rejected) {
                self.uninstall()?;
            }
        }
        if !self.quitting
            && self
                .installation_watch
                .as_mut()
                .is_some_and(|watch| watch.removed())
        {
            self.uninstall()?;
        }
        self.restore_adopted_control()?;
        if self.quitting || self.suspended {
            self.stop_local_ai();
        }
        self.local_ai
            .follow(&self.diagnostics, self.quitting || self.suspended);
        if let Some(running) = &mut self.running {
            self.backlog = drain_events(
                running,
                &self.diagnostics,
                EVENTS_PER_POLL,
                Some(&mut self.observation),
            );
            self.observation.report(self.reporter.as_ref())?;
            match running.settled() {
                Ok(Some(outcome)) => {
                    drain_events(
                        running,
                        &self.diagnostics,
                        EVENT_QUEUE,
                        Some(&mut self.observation),
                    );
                    self.running = None;
                    diagnostics::supervision_outcome(&self.diagnostics, outcome);
                    match outcome {
                        Outcome::Failed { .. } | Outcome::Foreign(_) | Outcome::StoodDown(_) => {
                            self.blocked = true;
                            return Ok(());
                        }
                        _ => {}
                    }
                }
                Err(error) => {
                    if running.worker_finished() {
                        // Join before discarding a terminal worker error. A
                        // separate cleanup-only supervisor re-admits the exact
                        // boot/image/process identity; it never starts a runtime.
                        let _ = running.join();
                        self.running = None;
                        self.quitting = true;
                        self.suspended = true;
                        if self.observation.pid.is_some() && !self.settlement_error_reported {
                            let cleanup = startup::stop_adopting(
                                self.installed.target.clone(),
                                SupervisorConfig::default(),
                                Collaborators {
                                    session: (self.activity)(),
                                    probe: Box::new(self.installed.clone()),
                                    versions: Box::new(self.installed.clone()),
                                    stop_signal: Box::new(PlatformStopSignal::default()),
                                },
                            )?;
                            self.supervise(cleanup);
                        }
                    }
                    if !self.settlement_error_reported {
                        self.settlement_error_reported = true;
                        return report_failure(&self.diagnostics, Err(error));
                    }
                    return Err(error);
                }
                Ok(None) => return Ok(()),
            }
        }
        if self.start_withheld() {
            return Ok(());
        }
        let initial = self.initial.take();
        // Any outcome but a running supervisor is reassessed at the pace.
        self.next_start = Some(Instant::now() + OWNERSHIP_PACE);
        let collaborators = Collaborators {
            session: (self.activity)(),
            probe: Box::new(self.installed.clone()),
            versions: Box::new(self.installed.clone()),
            stop_signal: Box::new(PlatformStopSignal::default()),
        };
        self.observation = Observation::default();
        let started = if let Some(permit) = self.designated.take() {
            startup::start_designated(
                self.installed.target.clone(),
                SupervisorConfig::default(),
                collaborators,
                permit,
            )
        } else if let Some(claim) = self.reserved.take() {
            startup::start_reserved(
                self.installed.target.clone(),
                SupervisorConfig::default(),
                collaborators,
                claim,
            )
        } else {
            startup::start(
                self.installed.target.clone(),
                SupervisorConfig::default(),
                collaborators,
                &mut self.ownership,
                initial,
            )
        };
        match report_failure(&self.diagnostics, started)? {
            Start::Running(running) => {
                self.diagnostics.lifecycle(
                    EventKind::StageStarted,
                    HostStage::Supervision,
                    LifecycleFact::SupervisorStarted {},
                    None,
                );
                self.waiting = None;
                self.settlement_error_reported = false;
                self.next_start = None;
                self.supervise(running);
            }
            Start::Waiting(role) => {
                let fact = diagnostics::waiting(&role);
                if fact != self.waiting {
                    if let Some(fact) = fact {
                        let failure = match role {
                            crate::session::ownership::Role::Wait(reason) => {
                                diagnostics::wait_failure(reason)
                            }
                            _ => None,
                        };
                        self.diagnostics.lifecycle(
                            EventKind::StageCompleted,
                            HostStage::Supervision,
                            fact,
                            failure,
                        );
                    }
                    self.waiting = fact;
                }
            }
        }
        Ok(())
    }

    /// A client asks only for reassessment; no running process is interrupted.
    pub fn retry(&mut self) -> io::Result<()> {
        if self.quitting || self.suspended {
            return Err(io::ErrorKind::WouldBlock.into());
        }
        crate::failed_versions::FailedVersions::retry(self.installed.target.storage_root())?;
        self.local_ai.retry();
        self.blocked = false;
        self.update_failed = false;
        self.next_start = None;
        self.poll()
    }

    /// Called after the tray's explicit interruption warning. Normal supervisor
    /// stop/drain completes before the next manual ownership assessment.
    pub fn restart(&mut self) -> io::Result<()> {
        if self.quitting || self.suspended {
            return Err(io::ErrorKind::WouldBlock.into());
        }
        if let Some(running) = &self.running
            && !running.handle.request(Request::Stop)
        {
            return Err(io::ErrorKind::WouldBlock.into());
        }
        self.blocked = false;
        self.initial = Some(StartKind::Manual);
        self.next_start = None;
        Ok(())
    }

    /// An adopted survivor has no heartbeat channel. Drain its verified process
    /// before launching a fresh incarnation with the canonical control channel.
    fn restore_adopted_control(&mut self) -> io::Result<()> {
        self.control_retry = None;
        if !self.quitting
            && !self.suspended
            && self.observation.adopted
            && !self.observation.recovery_requested
        {
            if let Err(error) = self.restart() {
                if error.kind() == io::ErrorKind::WouldBlock {
                    self.control_retry = Some(Instant::now() + CONTROL_RETRY);
                    return Ok(());
                }
                return Err(error);
            }
            self.observation.recovery_requested = true;
        }
        Ok(())
    }

    /// Suppress automatic starts before asking only our owned supervisor to stop.
    pub fn quit(&mut self) -> io::Result<()> {
        self.ownership.record_quit()?;
        self.close_host()
    }

    /// Window close drains its owned runtime without persisting a user Quit choice.
    pub fn close_host(&mut self) -> io::Result<()> {
        if self.quitting {
            return Ok(());
        }
        if let Some(running) = &self.running
            && !running.handle.request(Request::Stop)
        {
            return Err(io::ErrorKind::WouldBlock.into());
        }
        self.quitting = true;
        self.suspended = true;
        self.stop_local_ai();
        Ok(())
    }

    pub fn quit_completed(&self) -> bool {
        self.quitting && self.running.is_none()
    }

    pub fn status(&self) -> &'static str {
        if self.quitting || self.suspended {
            return "stopping";
        }
        if self.update_failed {
            return "update_failed";
        }
        if self.blocked {
            return "unavailable";
        }
        if self.waiting.is_some() {
            return "waiting";
        }
        if self.running.is_some() {
            return if self.observation.adopted {
                "adopted"
            } else if self.observation.ready && self.observation.confirmed {
                "running"
            } else {
                "starting"
            };
        }
        "waiting"
    }

    fn suppress_session_end(&mut self) -> bool {
        let begun = self.session_end.begin(&mut self.suspended, || {
            if let Some(running) = &self.running {
                running.handle.request(Request::SessionEnd);
            }
        });
        // After the runtime's request, so its settlement starts first.
        if begun {
            self.stop_local_ai();
        }
        begun
    }

    pub fn begin_session_end(&mut self) {
        if self.suppress_session_end() {
            session_end_requested(&self.diagnostics);
        }
    }

    /// Supervisor/thread custody only, not Effects::Settled. The native host must
    /// also settle its cutover owner; SessionEnd effects remain Unknown.
    pub fn session_end_settled(&self) -> bool {
        self.session_end.requested && self.running.is_none()
    }

    pub fn session_end(&mut self) {
        if !self.suppress_session_end() {
            return;
        }
        if let Some(running) = &mut self.running {
            if wait_session(running, &self.diagnostics, Duration::from_millis(3500)) {
                self.running = None;
            }
        } else {
            session_end_requested(&self.diagnostics);
        }
    }

    pub fn cancel_session_end(&mut self) {
        // A still-settling supervisor must exit before a fresh one may start.
        self.session_end.cancel(&mut self.suspended, self.quitting);
        if !self.quitting {
            self.local_ai.resume(&self.diagnostics);
        }
        self.next_start = None;
        self.diagnostics.lifecycle(
            EventKind::StageCompleted,
            HostStage::Shutdown,
            LifecycleFact::SessionEndCancelled {},
            None,
        );
    }
}

/// Notices a rewrite of the selection record in the storage root.
struct SelectionChanges {
    /// The storage root, whose entries' names and writes the watch reports. A notification
    /// says only that something changed; the record is read again.
    #[cfg(windows)]
    watch: crate::change_watch::ChangeWatch,
    #[cfg(not(windows))]
    next_look: Instant,
    /// A change was noticed that has not been acted on yet.
    dirty: bool,
}

impl SelectionChanges {
    fn new(root: &Path) -> Self {
        #[cfg(windows)]
        let watch = {
            let mut watch = crate::change_watch::ChangeWatch::default();
            watch.directory(root.to_path_buf(), false);
            watch
        };
        #[cfg(not(windows))]
        let _ = root;
        Self {
            #[cfg(windows)]
            watch,
            #[cfg(not(windows))]
            next_look: Instant::now() + SELECTION_PACE,
            dirty: false,
        }
    }

    /// Takes what the watch noticed since the last call.
    #[cfg(windows)]
    fn look(&mut self) {
        self.dirty |= self.watch.take();
    }

    /// Takes the pace's due look, since nothing here notices a rewrite.
    #[cfg(not(windows))]
    fn look(&mut self) {
        if Instant::now() >= self.next_look {
            self.next_look = Instant::now() + SELECTION_PACE;
            self.dirty = true;
        }
    }

    #[cfg(windows)]
    fn readiness<'a>(&'a self, into: &mut crate::wake::windows::Readiness<'a>) {
        self.watch.readiness(into);
    }
}

/// The local AI server the person's selection names, and the reading of the record it was
/// started from.
struct LocalAi {
    package: Option<PathBuf>,
    storage_root: PathBuf,
    /// The server of the applied selection: none for a package that carries no program of
    /// the selected engine, and none while the record cannot be read.
    host: Option<LocalAiHost>,
    applied: Recorded,
    changes: SelectionChanges,
    /// The loopback address each engine's server listens on: the package's declared one,
    /// and in a test one the system has just assigned.
    address: fn(LocalEngine) -> Option<SocketAddr>,
}

impl LocalAi {
    /// Reads the selection record and starts the server it names. The watch is set before
    /// the first read, so a rewrite in between is noticed.
    fn start(package: Option<&Path>, storage_root: &Path, diagnostics: &Diagnostics) -> Self {
        Self::start_at(package, storage_root, diagnostics, server_address)
    }

    /// [`Self::start`] with each engine's server on the address `address` gives.
    fn start_at(
        package: Option<&Path>,
        storage_root: &Path,
        diagnostics: &Diagnostics,
        address: fn(LocalEngine) -> Option<SocketAddr>,
    ) -> Self {
        let changes = SelectionChanges::new(storage_root);
        let applied = LocalEngineSelection::read(storage_root);
        let mut local_ai = Self {
            package: package.map(Path::to_path_buf),
            storage_root: storage_root.to_path_buf(),
            host: None,
            applied,
            changes,
            address,
        };
        local_ai.host = local_ai.build(applied, diagnostics);
        local_ai
    }

    /// The server `recorded` names. A record that cannot be read names none, and none runs:
    /// Ollama must never run where llama.cpp may be the selection.
    fn build(&self, recorded: Recorded, diagnostics: &Diagnostics) -> Option<LocalAiHost> {
        let package = self.package.as_deref()?;
        let Some(selection) = recorded.selection(package) else {
            diagnostics::local_ai_selection_unreadable(diagnostics);
            return None;
        };
        LocalAiHost::at(
            package,
            &self.storage_root,
            selection.engine,
            selection.placement,
            (self.address)(selection.engine),
        )
        .inspect_err(|reason| {
            diagnostics::local_ai_unavailable(diagnostics, selection.engine, *reason);
        })
        .ok()
    }

    /// Applies a rewrite of the record that was noticed, unless the manager is stopping,
    /// when it waits for supervision to resume. Whether the selection was applied as a new
    /// server.
    fn follow(&mut self, diagnostics: &Diagnostics, withheld: bool) -> bool {
        self.changes.look();
        if withheld || !self.changes.dirty {
            return false;
        }
        let Some(package) = self.package.clone() else {
            return false;
        };
        self.changes.dirty = false;
        let recorded = LocalEngineSelection::read(&self.storage_root);
        if recorded == self.applied {
            return false;
        }
        let previous = std::mem::replace(&mut self.applied, recorded);
        if let (Some(before), Some(after)) =
            (previous.selection(&package), recorded.selection(&package))
            && before.engine == after.engine
            && let Some(host) = &self.host
        {
            // The same engine keeps its server: a changed placement reaches its preset, which
            // drains and starts again once it holds no model.
            host.set_placement(after.placement);
            return false;
        }
        // Another engine, or none readable, or no server yet: the running server stops
        // before the next one starts.
        drop(self.host.take());
        self.host = self.build(recorded, diagnostics);
        true
    }

    fn stop(&mut self) {
        if let Some(host) = &mut self.host {
            host.stop();
        }
    }

    /// Supervises again after a stop that did not end the manager. A selection rewritten
    /// meanwhile starts its own server instead of the stopped one.
    fn resume(&mut self, diagnostics: &Diagnostics) {
        if self.follow(diagnostics, false) {
            return;
        }
        if let Some(host) = &mut self.host {
            host.resume();
        }
    }

    fn retry(&self) {
        if let Some(host) = &self.host {
            host.retry();
        }
    }
}

#[derive(Default)]
struct SessionEnd {
    requested: bool,
}
impl SessionEnd {
    fn begin(&mut self, suspended: &mut bool, request: impl FnOnce()) -> bool {
        *suspended = true;
        if self.requested {
            return false;
        }
        self.requested = true;
        request();
        true
    }
    fn cancel(&mut self, suspended: &mut bool, quitting: bool) {
        self.requested = false;
        *suspended = quitting;
    }
}

#[derive(Default)]
struct Observation {
    pid: Option<u32>,
    ready: bool,
    confirmed: bool,
    reported_launch: bool,
    reported_ready: bool,
    adopted: bool,
    recovery_requested: bool,
}
impl Observation {
    fn observe(&mut self, event: &Event) {
        match event {
            Event::Launched { pid, .. } => {
                *self = Self {
                    pid: Some(*pid),
                    ..Self::default()
                };
            }
            Event::Ready { pid, .. } if self.pid == Some(*pid) => self.ready = true,
            Event::BootRecordConfirmed { pid } if self.pid == Some(*pid) => self.confirmed = true,
            Event::Adopted { pid, .. } => {
                *self = Self {
                    pid: Some(*pid),
                    adopted: true,
                    ..Self::default()
                };
            }
            Event::ChannelClosed { .. } | Event::HangDetected { .. } | Event::Exited { .. } => {
                self.ready = false;
            }
            _ => {}
        }
    }
    fn report(&mut self, reporter: Option<&crate::successor::Reporter>) -> io::Result<()> {
        if let Some(reporter) = reporter
            && let Some(pid) = self.pid
        {
            if !self.reported_launch {
                reporter.launched(pid)?;
                self.reported_launch = true;
            }
            if self.ready && self.confirmed && !self.reported_ready {
                reporter.ready(pid)?;
                self.reported_ready = true;
            }
        }
        Ok(())
    }
}

/// Publish restart suppression and settle before any diagnostic file I/O.
/// False retains the running supervisor so cleanup ownership survives the bound.
pub fn settle_session(running: &mut Running, diagnostics: &Diagnostics, bound: Duration) -> bool {
    running.handle.request(Request::SessionEnd);
    wait_session(running, diagnostics, bound)
}

fn session_end_requested(diagnostics: &Diagnostics) {
    diagnostics.lifecycle(
        EventKind::StageStarted,
        HostStage::Shutdown,
        LifecycleFact::SessionEndRequested {},
        None,
    );
}

fn wait_session(running: &mut Running, diagnostics: &Diagnostics, bound: Duration) -> bool {
    let result = running.wait_settled(bound);
    session_end_requested(diagnostics);
    match result {
        Ok(Some(outcome)) => {
            drain_events(running, diagnostics, EVENT_QUEUE, None);
            diagnostics::supervision_outcome(diagnostics, outcome);
            true
        }
        Err(error) => {
            let _ = report_failure::<()>(diagnostics, Err(error));
            false
        }
        Ok(None) => {
            drain_events(running, diagnostics, EVENTS_PER_POLL, None);
            false
        }
    }
}

/// True when the limit was reached, so further observations may be queued.
fn drain_events(
    running: &Running,
    diagnostics: &Diagnostics,
    limit: usize,
    mut observation: Option<&mut Observation>,
) -> bool {
    let mut drained = 0;
    for event in running.events.try_iter().take(limit) {
        drained += 1;
        if let Some(observation) = &mut observation {
            observation.observe(&event);
        }
        diagnostics::supervision_event(diagnostics, &event);
    }
    let count = running.handle.take_dropped_events();
    if count > 0 {
        diagnostics.lifecycle(
            EventKind::Failure,
            HostStage::Supervision,
            LifecycleFact::EventsDropped { count },
            Some(ApplicationError::new(
                ErrorCode::OutputLimit,
                Operation::Manager,
            )),
        );
    }
    drained == limit
}

#[cfg(test)]
fn record_events(
    events: &std::sync::mpsc::Receiver<Event>,
    diagnostics: &Diagnostics,
    limit: usize,
) {
    for event in events.try_iter().take(limit) {
        diagnostics::supervision_event(diagnostics, &event);
    }
}

fn report_failure<T>(diagnostics: &Diagnostics, result: io::Result<T>) -> io::Result<T> {
    result.map_err(|error| {
        let safe = ApplicationError::new(ErrorCode::ManagerUnavailable, Operation::Manager)
            .caused_by(error);
        diagnostics.host_failure(HostStage::Supervision, safe.clone());
        io::Error::other(safe)
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use cadrumo_application::{
        diagnostics::{
            DiagnosticSource,
            lifecycle::{LocalAiEngine, LocalAiUnavailable},
        },
        provisioning::{
            local_ai::{LocalEngine, Placement},
            pins::Platform,
        },
    };
    use std::sync::mpsc;

    #[test]
    fn readiness_requires_current_launch_and_boot_record_and_is_retired_on_channel_loss() {
        let mut observed = Observation::default();
        observed.observe(&Event::Launched {
            pid: 7,
            version: "1".into(),
        });
        observed.observe(&Event::Ready {
            pid: 8,
            boot_id: "stale".into(),
        });
        assert!(!observed.ready);
        observed.observe(&Event::Ready {
            pid: 7,
            boot_id: "current".into(),
        });
        assert!(observed.ready && !observed.confirmed);
        observed.observe(&Event::BootRecordConfirmed { pid: 7 });
        assert!(observed.ready && observed.confirmed);
        observed.observe(&Event::ChannelClosed { pid: 7 });
        assert!(!observed.ready);
        observed.observe(&Event::Adopted {
            pid: 7,
            version: "1".into(),
        });
        assert!(observed.adopted && !observed.ready && !observed.confirmed);
        observed.observe(&Event::Launched {
            pid: 9,
            version: "1".into(),
        });
        assert!(!observed.adopted && !observed.ready && !observed.confirmed);
    }

    #[test]
    fn session_end_is_idempotent_and_cancellation_preserves_user_quit() {
        let mut state = SessionEnd::default();
        let mut suspended = false;
        let (send, receive) = mpsc::channel();
        assert!(state.begin(&mut suspended, || send.send(()).unwrap()));
        assert!(suspended && state.requested);
        assert!(!state.begin(&mut suspended, || send.send(()).unwrap()));
        assert_eq!(receive.try_iter().count(), 1);
        state.cancel(&mut suspended, false);
        assert!(!suspended && !state.requested);
        assert!(state.begin(&mut suspended, || send.send(()).unwrap()));
        assert_eq!(receive.try_iter().count(), 1);
        state.cancel(&mut suspended, true);
        assert!(suspended && !state.requested);
    }

    #[test]
    fn polling_leaves_backlog_for_later_messages_and_final_drain_finishes_it() {
        let (send, receive) = mpsc::sync_channel(EVENT_QUEUE);
        for pid in 1..=512 {
            send.try_send(Event::Ready {
                pid,
                boot_id: "opaque-boot".into(),
            })
            .unwrap();
        }
        let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
        record_events(&receive, &diagnostics, EVENTS_PER_POLL);
        let first = diagnostics.snapshot(u64::MAX);
        assert_eq!(first.events.len(), 64);
        assert_eq!(
            first.events.last().unwrap().lifecycle,
            Some(LifecycleFact::Ready { pid: 64 })
        );

        // A producer can replenish the queue; a second poll still yields.
        for pid in 513..=576 {
            send.try_send(Event::Ready {
                pid,
                boot_id: "opaque-boot".into(),
            })
            .unwrap();
        }
        record_events(&receive, &diagnostics, EVENTS_PER_POLL);
        assert_eq!(diagnostics.snapshot(u64::MAX).events.len(), 128);
        drop(send);
        record_events(&receive, &diagnostics, EVENT_QUEUE);
        assert!(matches!(
            receive.try_recv(),
            Err(mpsc::TryRecvError::Disconnected)
        ));
        let final_events = diagnostics.snapshot(u64::MAX).events;
        assert_eq!(
            final_events.last().unwrap().lifecycle,
            Some(LifecycleFact::Ready { pid: 576 })
        );
    }

    /// The storage root and package of one local AI test, removed when dropped.
    struct LocalAiScratch(PathBuf);

    impl LocalAiScratch {
        fn new(name: &str) -> Self {
            let path = std::env::temp_dir().join(format!(
                "cadrumo-manager-selection-{name}-{}",
                std::process::id()
            ));
            let _ = std::fs::remove_dir_all(&path);
            std::fs::create_dir_all(path.join("package")).unwrap();
            std::fs::create_dir_all(path.join("state")).unwrap();
            Self(path)
        }

        fn package(&self) -> PathBuf {
            self.0.join("package")
        }

        fn state(&self) -> PathBuf {
            self.0.join("state")
        }

        /// Puts a llama-server in the package that cannot get as far as listening.
        fn carry_llama_server(&self) {
            #[cfg(windows)]
            const EXECUTABLE: &str = "llama-server.exe";
            #[cfg(not(windows))]
            const EXECUTABLE: &str = "llama-server";
            let folder = self.package().join(crate::contract::LLAMA_SERVER);
            std::fs::create_dir_all(&folder).unwrap();
            let program = folder.join(EXECUTABLE);
            std::fs::write(&program, b"#!/bin/sh\nexit 3\n").unwrap();
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                std::fs::set_permissions(&program, std::fs::Permissions::from_mode(0o755)).unwrap();
            }
        }

        fn choose(&self, engine: LocalEngine, placement: Placement) {
            LocalEngineSelection::new(engine, placement)
                .store(&self.state())
                .unwrap();
        }

        fn start(&self, diagnostics: &Diagnostics) -> LocalAi {
            LocalAi::start_at(
                Some(self.package().as_path()),
                &self.state(),
                diagnostics,
                crate::supervision::local_ai::free_loopback,
            )
        }
    }

    impl Drop for LocalAiScratch {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    /// Every local AI server the manager recorded it could not run.
    fn unavailable(diagnostics: &Diagnostics) -> Vec<(LocalAiEngine, LocalAiUnavailable)> {
        diagnostics
            .snapshot(0)
            .events
            .iter()
            .filter_map(|event| match event.lifecycle {
                Some(LifecycleFact::LocalAiUnavailable { engine, reason }) => {
                    Some((engine, reason))
                }
                _ => None,
            })
            .collect()
    }

    /// What a package without Ollama's pins reports for Ollama.
    fn ollama_unpinned() -> LocalAiUnavailable {
        if Platform::current().is_some() {
            LocalAiUnavailable::OllamaNotPinned
        } else {
            LocalAiUnavailable::Platform
        }
    }

    /// Whether the server the manager runs is the llama-server: only its host takes a
    /// placement.
    fn runs_llama_server(local_ai: &LocalAi) -> bool {
        local_ai
            .host
            .as_ref()
            .is_some_and(|host| host.set_placement(Placement::Auto))
    }

    #[test]
    fn with_no_record_a_package_that_carries_the_llama_server_runs_it() {
        let scratch = LocalAiScratch::new("absent-llama");
        scratch.carry_llama_server();
        let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
        let local_ai = scratch.start(&diagnostics);
        assert_eq!(local_ai.applied, Recorded::Absent);
        assert!(runs_llama_server(&local_ai));
        assert_eq!(unavailable(&diagnostics), []);
    }

    #[test]
    fn with_no_record_a_package_without_the_llama_server_chooses_ollama() {
        let scratch = LocalAiScratch::new("absent-ollama");
        let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
        let local_ai = scratch.start(&diagnostics);
        // The package pins no Ollama either, so nothing runs, and Ollama says why.
        assert!(local_ai.host.is_none());
        assert_eq!(
            unavailable(&diagnostics),
            [(LocalAiEngine::Ollama, ollama_unpinned())]
        );
    }

    #[test]
    fn a_stored_llama_cpp_choice_on_a_package_without_it_is_refused_and_never_ollama() {
        let scratch = LocalAiScratch::new("chosen-llama");
        scratch.choose(LocalEngine::LlamaCpp, Placement::Auto);
        let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
        let local_ai = scratch.start(&diagnostics);
        assert!(local_ai.host.is_none());
        assert_eq!(
            unavailable(&diagnostics),
            [(
                LocalAiEngine::LlamaCpp,
                LocalAiUnavailable::LlamaServerNotPackaged
            )]
        );
    }

    #[test]
    fn a_stored_ollama_choice_is_kept_beside_a_packaged_llama_server() {
        let scratch = LocalAiScratch::new("chosen-ollama");
        scratch.carry_llama_server();
        scratch.choose(LocalEngine::Ollama, Placement::CpuOnly);
        let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
        let local_ai = scratch.start(&diagnostics);
        assert!(!runs_llama_server(&local_ai));
        assert_eq!(
            unavailable(&diagnostics),
            [(LocalAiEngine::Ollama, ollama_unpinned())]
        );
    }

    #[test]
    fn an_unreadable_record_runs_no_server_and_says_no_engine_was_selected() {
        let scratch = LocalAiScratch::new("unreadable");
        scratch.carry_llama_server();
        std::fs::write(
            scratch
                .state()
                .join(crate::contract::LOCAL_ENGINE_SELECTION),
            b"{",
        )
        .unwrap();
        let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
        let local_ai = scratch.start(&diagnostics);
        assert_eq!(local_ai.applied, Recorded::Unreadable);
        assert!(local_ai.host.is_none(), "neither engine runs");
        assert_eq!(
            unavailable(&diagnostics),
            [(
                LocalAiEngine::Unselected,
                LocalAiUnavailable::SelectionUnreadable
            )]
        );
    }

    #[test]
    fn a_rewritten_record_is_followed_by_engine_and_by_placement() {
        let scratch = LocalAiScratch::new("follow");
        scratch.carry_llama_server();
        scratch.choose(LocalEngine::Ollama, Placement::Auto);
        let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
        let mut local_ai = scratch.start(&diagnostics);
        assert!(!runs_llama_server(&local_ai));

        // A noticed rewrite is not applied while the manager is stopping.
        scratch.choose(LocalEngine::LlamaCpp, Placement::Auto);
        local_ai.changes.dirty = true;
        assert!(!local_ai.follow(&diagnostics, true));
        assert!(!runs_llama_server(&local_ai));

        // Another engine: the running server is replaced by the other engine's.
        assert!(local_ai.follow(&diagnostics, false));
        assert!(runs_llama_server(&local_ai));

        // The same engine with another placement keeps its server and passes it on.
        scratch.choose(LocalEngine::LlamaCpp, Placement::CpuOnly);
        local_ai.changes.dirty = true;
        assert!(!local_ai.follow(&diagnostics, false));
        assert_eq!(
            local_ai.applied,
            Recorded::Selected(LocalEngineSelection::new(
                LocalEngine::LlamaCpp,
                Placement::CpuOnly
            ))
        );
        assert!(runs_llama_server(&local_ai));

        // A record that can no longer be read stops the server and runs none.
        std::fs::write(
            scratch
                .state()
                .join(crate::contract::LOCAL_ENGINE_SELECTION),
            b"{",
        )
        .unwrap();
        local_ai.changes.dirty = true;
        assert!(local_ai.follow(&diagnostics, false));
        assert!(local_ai.host.is_none());
        assert_eq!(
            unavailable(&diagnostics).last(),
            Some(&(
                LocalAiEngine::Unselected,
                LocalAiUnavailable::SelectionUnreadable
            ))
        );
    }
}
