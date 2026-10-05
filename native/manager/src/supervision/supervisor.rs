//! The supervision state machine for one storage root.
//!
//! It launches the runtime, awaits `ready` while the process lives, pings on an interval and
//! escalates a stale heartbeat (`stop`, then the drain and watchdog bound, then termination,
//! with effects left UNKNOWN), classifies every exit and restarts with exponential backoff on
//! monotonic time up to a crash-loop ceiling. On OWNER_BUSY it adopts a runtime only by
//! identity and reports a foreign one without ever stopping it.

use super::adoption::{ForeignReason, InstalledVersions, assess};
use super::boot_record::{BootRecordUnavailable, read_boot_record};
use super::exit::{ExitReason, RuntimeExit};
use super::launch::LaunchTarget;
use super::process::{InspectError, OpenedProcess, RuntimeProcess, current_session, open_process};
use super::protocol::{
    Announcement, Command, Heartbeat, LineFraming, LineRefusal, Ready, decode_announcement,
};
use super::restart::{RestartClass, RestartHistory, RestartPolicy};
use super::stop::{StopSignal, StopSignalError};
use crate::session::ownership::{
    BootRecordLocator, Role, StartPermit, WaitReason, reserve_restart,
};
use std::io::{ErrorKind, Read, Write};
use std::process::{ChildStdin, ChildStdout};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Receiver, RecvTimeoutError, Sender, SyncSender, TrySendError};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

const COMMAND_QUEUE: usize = 16;
const READ_CHUNK_BYTES: usize = 4096;

/// Timing bounds of the supervision core.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SupervisorConfig {
    /// How long a live runtime may take to report `ready`, including first-run scanning.
    pub readiness_ceiling: Duration,
    /// Interval between pings once the runtime is ready.
    pub heartbeat_interval: Duration,
    /// How long without a fresh heartbeat before the runtime counts as hung.
    pub heartbeat_staleness: Duration,
    /// A heartbeat whose accept-loop tick is older than this is not fresh.
    pub accept_tick_ceiling: Duration,
    /// How long a stop may take: the runtime's drain plus its own watchdog, with margin.
    pub drain_bound: Duration,
    /// Deadline for the runtime's ordered session-end settlement before containment.
    pub session_end_bound: Duration,
    /// How long to wait for a terminated process to be reported ended.
    pub termination_bound: Duration,
    /// Upper bound of one wait between exit polls.
    pub poll_interval: Duration,
    pub restart: RestartPolicy,
}

impl Default for SupervisorConfig {
    fn default() -> Self {
        Self {
            readiness_ceiling: Duration::from_secs(180),
            heartbeat_interval: Duration::from_secs(5),
            heartbeat_staleness: Duration::from_secs(30),
            accept_tick_ceiling: Duration::from_secs(30),
            // The runtime drains for 15 s and its watchdog forces an exit 2 s later.
            drain_bound: Duration::from_secs(25),
            session_end_bound: Duration::from_secs(3),
            termination_bound: Duration::from_secs(5),
            poll_interval: Duration::from_millis(100),
            restart: RestartPolicy::default(),
        }
    }
}

/// Whether the manager's own session is active, not locked away or disconnected.
pub trait SessionActivity: Send {
    fn is_active(&self) -> bool;
}

/// Re-reads the installed runtime's version after a VERSION_MISMATCH.
pub trait VersionProbe: Send {
    /// The version the runtime now reports, or `None` when it cannot be probed.
    fn reprobe(&mut self) -> Option<String>;
}

/// What the core consults but does not own.
pub struct Collaborators {
    pub session: Box<dyn SessionActivity>,
    pub probe: Box<dyn VersionProbe>,
    pub versions: Box<dyn InstalledVersions>,
    pub stop_signal: Box<dyn StopSignal>,
}

/// A request from the manager's own surfaces.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Request {
    /// Stop the runtime and end supervision.
    Stop,
    /// Stop the runtime only if no operation is in flight; otherwise keep supervising.
    StopIfIdle,
    /// Settle an ending OS session and permanently suppress this supervisor's restarts.
    SessionEnd,
}

/// Whether in-flight effects settled, or remain for reconciliation.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Effects {
    Settled,
    Unknown,
}

/// A configuration refusal the manager must not retry.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StandDownReason {
    RootMismatch,
    ElevatedTokenRefused,
    /// The runtime still reported VERSION_MISMATCH after one re-probe and relaunch.
    VersionMismatch,
}

/// How supervision ended.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Outcome {
    /// Ownership must be reassessed before another launch is attempted.
    RestartDeferred(WaitReason),
    /// A live runtime appeared before this manager reserved its restart.
    OwnershipChanged,
    /// A requested stop completed.
    Stopped {
        effects: Effects,
    },
    StoodDown(StandDownReason),
    /// Another runtime owns the root and was not adopted; it was not stopped.
    Foreign(ForeignReason),
    /// The login witness was lost while the manager's session is not active.
    AwaitingActiveSession,
    /// The crash-loop ceiling was reached.
    Failed {
        last: RestartClass,
    },
}

/// Why the core began a stop.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum StopCause {
    /// The runtime announced an identity other than the one launched.
    Defect,
    /// No readiness within the ceiling, or a stale heartbeat.
    Hang,
    /// The runtime accepted a `stop-if-idle`.
    IdleRequested,
    /// The manager asked to stop.
    Requested,
    /// Session teardown outranks every ordinary drain or restart reason.
    SessionEnd,
}

/// How a stop reached the runtime.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StopPath {
    Channel,
    Signal,
    Undelivered(StopSignalError),
}

/// What the core observed, in order; later Steps log and display these.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Event {
    RestartDeferred(WaitReason),
    OwnershipChanged,
    Launched {
        pid: u32,
        version: String,
    },
    LaunchFailed {
        kind: ErrorKind,
    },
    Ready {
        pid: u32,
        boot_id: String,
    },
    /// The boot record names this boot, pid, creation time, version and admission.
    BootRecordConfirmed {
        pid: u32,
    },
    BootRecordMismatch {
        pid: u32,
    },
    /// The runtime wrote a line outside the grammar.
    AnnouncementRefused(LineRefusal),
    /// The runtime refused one of the manager's lines.
    CommandRefused(LineRefusal),
    ChannelClosed {
        pid: u32,
    },
    Busy {
        pid: u32,
    },
    /// The runtime has no protocol channel, so an idle-only stop cannot be asked.
    IdleStopUnavailable {
        pid: u32,
    },
    HangDetected {
        pid: u32,
        ready: bool,
    },
    StopRequested {
        pid: u32,
        cause: StopCause,
        path: StopPath,
    },
    Terminated {
        pid: u32,
    },
    EffectsUnknown {
        pid: u32,
    },
    Exited {
        pid: u32,
        exit: RuntimeExit,
        announced: Option<ExitReason>,
    },
    VersionReprobed {
        version: String,
    },
    RestartScheduled {
        class: RestartClass,
        delay: Duration,
    },
    Adopted {
        pid: u32,
        version: String,
    },
    Foreign(ForeignReason),
    StoodDown(StandDownReason),
    AwaitingActiveSession,
    Failed {
        last: RestartClass,
    },
}

enum Input {
    Line {
        generation: u64,
        line: Result<Announcement, LineRefusal>,
    },
    Closed {
        generation: u64,
    },
    Control(Request),
}

/// Sends requests to a running supervisor from another thread.
#[derive(Clone)]
pub struct SupervisorHandle(Sender<Input>, Arc<AtomicBool>, Arc<Mutex<()>>);

impl SupervisorHandle {
    /// Queue `request`; false once the supervisor is gone.
    pub fn request(&self, request: Request) -> bool {
        if request == Request::SessionEnd {
            let _launch = self.2.lock().unwrap_or_else(|error| error.into_inner());
            // Publish before queueing: a concurrent exit/backoff must not relaunch
            // while the control message is behind old channel announcements.
            self.1.store(true, Ordering::SeqCst);
        }
        self.0.send(Input::Control(request)).is_ok()
    }
}

/// How one supervised process ended.
struct Ended {
    pid: u32,
    exit: RuntimeExit,
    cause: Option<StopCause>,
    terminated: bool,
}

impl Ended {
    fn effects(&self) -> Effects {
        if self.cause == Some(StopCause::SessionEnd) {
            // The closed supervisor grammar reports an exit reason, not exact
            // worker settlement or lease outcomes. Those remain runtime-owned.
            return Effects::Unknown;
        }
        let drained = matches!(
            self.exit,
            RuntimeExit::Reason(
                ExitReason::SupervisorStop | ExitReason::SignalStop | ExitReason::SessionEndSettle
            ) | RuntimeExit::Zero
                | RuntimeExit::ControlC
        );
        if drained && !self.terminated && self.cause != Some(StopCause::Hang) {
            Effects::Settled
        } else {
            Effects::Unknown
        }
    }
}

/// What the core does after one runtime ended.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Decision {
    Stopped,
    Restart(RestartClass),
    Adopt,
    StandDown(StandDownReason),
    VersionMismatch,
    WitnessLoss,
}

fn decide(exit: RuntimeExit, cause: Option<StopCause>) -> Decision {
    match cause {
        Some(StopCause::Requested | StopCause::IdleRequested | StopCause::SessionEnd) => {
            return Decision::Stopped;
        }
        Some(StopCause::Hang) => return Decision::Restart(RestartClass::Hang),
        Some(StopCause::Defect) => return Decision::Restart(RestartClass::Unexpected),
        None => {}
    }
    match exit {
        RuntimeExit::Reason(ExitReason::SignalStop) | RuntimeExit::Zero | RuntimeExit::ControlC => {
            Decision::Restart(RestartClass::OutsideStop)
        }
        RuntimeExit::Reason(ExitReason::OwnerBusy) => Decision::Adopt,
        RuntimeExit::Reason(ExitReason::RootMismatch) => {
            Decision::StandDown(StandDownReason::RootMismatch)
        }
        RuntimeExit::Reason(ExitReason::ElevatedTokenRefused) => {
            Decision::StandDown(StandDownReason::ElevatedTokenRefused)
        }
        RuntimeExit::Reason(ExitReason::VersionMismatch) => Decision::VersionMismatch,
        RuntimeExit::Reason(ExitReason::LoginWitnessLoss) => Decision::WitnessLoss,
        RuntimeExit::LaunchFailure(_) => Decision::Restart(RestartClass::LaunchFailure),
        RuntimeExit::Reason(
            ExitReason::SupervisorStop
            | ExitReason::SessionEndSettle
            | ExitReason::DrainWatchdog
            | ExitReason::UnexpectedFailure,
        )
        | RuntimeExit::Crash(_)
        | RuntimeExit::Terminated
        | RuntimeExit::Unknown => Decision::Restart(RestartClass::Unexpected),
    }
}

/// Writes commands on its own thread, so a runtime that stops reading never blocks the core.
struct CommandWriter {
    queue: SyncSender<Vec<u8>>,
    broken: Arc<AtomicBool>,
}

impl CommandWriter {
    fn spawn(mut stdin: ChildStdin) -> Self {
        let (queue, lines) = mpsc::sync_channel::<Vec<u8>>(COMMAND_QUEUE);
        let broken = Arc::new(AtomicBool::new(false));
        let flag = Arc::clone(&broken);
        thread::spawn(move || {
            for line in lines {
                if stdin.write_all(&line).and_then(|()| stdin.flush()).is_err() {
                    flag.store(true, Ordering::SeqCst);
                    return;
                }
            }
        });
        Self { queue, broken }
    }

    fn usable(&self) -> bool {
        !self.broken.load(Ordering::SeqCst)
    }

    fn send(&self, command: Command) -> bool {
        match self.queue.try_send(command.encode()) {
            Ok(()) => self.usable(),
            Err(TrySendError::Full(_) | TrySendError::Disconnected(_)) => false,
        }
    }
}

fn spawn_reader(mut stdout: ChildStdout, generation: u64, inputs: Sender<Input>) {
    thread::spawn(move || {
        let mut framing = LineFraming::default();
        let mut chunk = [0_u8; READ_CHUNK_BYTES];
        loop {
            let read = match stdout.read(&mut chunk) {
                Ok(0) => break,
                Ok(read) => read,
                Err(error) if error.kind() == ErrorKind::Interrupted => continue,
                Err(_) => break,
            };
            for line in framing.feed(&chunk[..read]) {
                let line = line.and_then(|line| decode_announcement(&line));
                if inputs.send(Input::Line { generation, line }).is_err() {
                    return;
                }
            }
        }
        let _ = inputs.send(Input::Closed { generation });
    });
}

enum Phase {
    Starting {
        deadline: Instant,
    },
    Ready {
        sent: u64,
        acknowledged: u64,
        last_fresh: Instant,
        next_ping: Instant,
    },
    /// An adopted runtime: no channel, so no readiness or heartbeat.
    Unmonitored,
}

/// The protocol channel of a launched runtime.
struct Channel {
    commands: Option<CommandWriter>,
    announcements_open: bool,
}

impl Channel {
    fn usable(&self) -> bool {
        self.announcements_open && self.commands.as_ref().is_some_and(CommandWriter::usable)
    }

    fn send(&self, command: Command) -> bool {
        self.usable()
            && self
                .commands
                .as_ref()
                .is_some_and(|writer| writer.send(command))
    }
}

/// One supervised process and the stop in progress against it.
struct Watch {
    pid: u32,
    runtime: RuntimeProcess,
    channel: Option<Channel>,
    phase: Phase,
    cause: Option<StopCause>,
    idle_pending: bool,
    stop_deadline: Option<Instant>,
    announced: Option<ExitReason>,
}

/// Supervises the runtime of one storage root until an [`Outcome`].
pub struct Supervisor {
    config: SupervisorConfig,
    target: LaunchTarget,
    collaborators: Collaborators,
    events: Sender<Event>,
    inputs: Receiver<Input>,
    sender: Sender<Input>,
    history: RestartHistory,
    generation: u64,
    reprobed: bool,
    restart_permit: Option<StartPermit>,
    session_ending: Arc<AtomicBool>,
    launch_gate: Arc<Mutex<()>>,
}

impl Supervisor {
    pub fn new(
        config: SupervisorConfig,
        target: LaunchTarget,
        collaborators: Collaborators,
        events: Sender<Event>,
    ) -> Self {
        let (sender, inputs) = mpsc::channel();
        Self {
            config,
            target,
            collaborators,
            events,
            inputs,
            sender,
            history: RestartHistory::default(),
            generation: 0,
            reprobed: false,
            restart_permit: None,
            session_ending: Arc::new(AtomicBool::new(false)),
            launch_gate: Arc::new(Mutex::new(())),
        }
    }

    /// A handle that sends requests to this supervisor while it runs.
    pub fn handle(&self) -> SupervisorHandle {
        SupervisorHandle(
            self.sender.clone(),
            Arc::clone(&self.session_ending),
            Arc::clone(&self.launch_gate),
        )
    }

    fn emit(&self, event: Event) {
        let _ = self.events.send(event);
    }

    /// Supervise until a requested stop, a stand-down, a foreign owner or the ceiling.
    pub fn run(&mut self) -> Outcome {
        let outcome = self.run_owned();
        self.restart_permit = None;
        outcome
    }

    /// Transfer the initial ownership claim into the supervisor. This keeps pre-ready
    /// failures and retries under the same claim, without a caller holding a competing
    /// guard while this blocking method runs. The root must be the exact pinned root
    /// for which ownership granted the permit.
    pub fn run_with_permit(&mut self, permit: StartPermit) -> std::io::Result<Outcome> {
        if permit.storage_root() != self.target.storage_root() {
            return Err(std::io::Error::new(
                ErrorKind::InvalidInput,
                "the start permit belongs to another storage root",
            ));
        }
        self.restart_permit = Some(permit);
        Ok(self.run())
    }

    fn run_owned(&mut self) -> Outcome {
        let mut adopting = false;
        let mut prior_effects = Effects::Settled;
        loop {
            if self.session_ending.load(Ordering::SeqCst) {
                return Outcome::Stopped {
                    effects: prior_effects,
                };
            }
            let ended = if adopting {
                adopting = false;
                // Inputs still queued from the launch that reported OWNER_BUSY are stale.
                self.generation += 1;
                match self.adopt() {
                    Ok(opened) => {
                        self.restart_permit = None;
                        self.watch(RuntimeProcess::Adopted(opened), None)
                    }
                    Err(reason) => {
                        self.emit(Event::Foreign(reason));
                        return Outcome::Foreign(reason);
                    }
                }
            } else {
                if let Some(reason) = self
                    .restart_permit
                    .as_ref()
                    .and_then(|permit| permit.refusal(self.collaborators.session.as_ref()))
                {
                    self.emit(Event::RestartDeferred(reason));
                    return Outcome::RestartDeferred(reason);
                }
                match self.launch() {
                    Some(ended) => ended,
                    None => {
                        if let Some(outcome) = self.back_off(RestartClass::LaunchFailure) {
                            return outcome;
                        }
                        continue;
                    }
                }
            };
            if self.session_ending.load(Ordering::SeqCst) {
                // Acceptance may race the process-exit poll before its cause is
                // recorded. The reason code is not a worker settlement receipt.
                self.emit(Event::EffectsUnknown { pid: ended.pid });
                return Outcome::Stopped {
                    effects: Effects::Unknown,
                };
            }
            let effects = ended.effects();
            prior_effects = effects;
            if effects == Effects::Unknown {
                self.emit(Event::EffectsUnknown { pid: ended.pid });
            }
            let class = match decide(ended.exit, ended.cause) {
                Decision::Stopped => return Outcome::Stopped { effects },
                Decision::Adopt => {
                    adopting = true;
                    continue;
                }
                Decision::StandDown(reason) => return self.stand_down(reason),
                Decision::VersionMismatch => {
                    if self.reprobe() {
                        if let Some(outcome) = self.reserve_restart() {
                            return outcome;
                        }
                        continue;
                    }
                    return self.stand_down(StandDownReason::VersionMismatch);
                }
                Decision::WitnessLoss if !self.collaborators.session.is_active() => {
                    self.emit(Event::AwaitingActiveSession);
                    return Outcome::AwaitingActiveSession;
                }
                Decision::WitnessLoss => RestartClass::WitnessLoss,
                Decision::Restart(class) => class,
            };
            if let Some(outcome) = self.back_off(class) {
                return outcome;
            }
        }
    }

    fn stand_down(&self, reason: StandDownReason) -> Outcome {
        self.emit(Event::StoodDown(reason));
        Outcome::StoodDown(reason)
    }

    fn reserve_restart(&mut self) -> Option<Outcome> {
        if self.restart_permit.is_some() {
            return None;
        }
        let root = self.target.storage_root();
        match reserve_restart(
            root,
            self.collaborators.session.as_ref(),
            &mut BootRecordLocator::new(root),
        ) {
            Role::Start(permit) => {
                self.restart_permit = Some(permit);
                None
            }
            Role::Wait(reason) => {
                self.emit(Event::RestartDeferred(reason));
                Some(Outcome::RestartDeferred(reason))
            }
            Role::OwnSession { .. } | Role::Observe(_) => {
                self.emit(Event::OwnershipChanged);
                Some(Outcome::OwnershipChanged)
            }
        }
    }

    /// Re-probe once per mismatch run and retarget the launch; false when already tried.
    fn reprobe(&mut self) -> bool {
        if self.reprobed {
            return false;
        }
        self.reprobed = true;
        let Some(version) = self.collaborators.probe.reprobe() else {
            return false;
        };
        if self.target.set_expected_version(version.clone()).is_err() {
            return false;
        }
        self.emit(Event::VersionReprobed { version });
        true
    }

    /// Wait the admitted backoff while honouring requests; `Some` ends supervision.
    fn back_off(&mut self, class: RestartClass) -> Option<Outcome> {
        if self.session_ending.load(Ordering::SeqCst) {
            return Some(Outcome::Stopped {
                effects: Effects::Unknown,
            });
        }
        if let Some(outcome) = self.reserve_restart() {
            return Some(outcome);
        }
        let Some(delay) = self.history.admit(&self.config.restart, Instant::now()) else {
            self.emit(Event::Failed { last: class });
            return Some(Outcome::Failed { last: class });
        };
        self.emit(Event::RestartScheduled { class, delay });
        let deadline = Instant::now() + delay;
        loop {
            let remaining = deadline.saturating_duration_since(Instant::now());
            if remaining.is_zero() {
                return None;
            }
            match self.inputs.recv_timeout(remaining) {
                // A session-end request must not erase the failed process's
                // unresolved effects merely because no process is running now.
                Ok(Input::Control(Request::SessionEnd)) => {
                    return Some(Outcome::Stopped {
                        effects: Effects::Unknown,
                    });
                }
                // Nothing runs, so an ordinary stop is complete at once.
                Ok(Input::Control(_)) => {
                    return Some(Outcome::Stopped {
                        effects: Effects::Settled,
                    });
                }
                Ok(_) => {}
                Err(RecvTimeoutError::Timeout | RecvTimeoutError::Disconnected) => return None,
            }
        }
    }

    /// Launch and watch one runtime; `None` when the image could not be started.
    fn launch(&mut self) -> Option<Ended> {
        let launched = {
            // Linearize launch with SessionEnd acceptance. A request accepted
            // before this gate cannot be followed by a new child process.
            let _launch = self
                .launch_gate
                .lock()
                .unwrap_or_else(|error| error.into_inner());
            if self.session_ending.load(Ordering::SeqCst) {
                return None;
            }
            self.target.spawn()
        };
        let mut child = match launched {
            Ok(child) => child,
            Err(error) => {
                self.emit(Event::LaunchFailed { kind: error.kind() });
                return None;
            }
        };
        self.generation += 1;
        let pid = child.id();
        self.emit(Event::Launched {
            pid,
            version: self.target.expected_version().to_owned(),
        });
        let commands = child.stdin.take().map(CommandWriter::spawn);
        let announcements_open = match child.stdout.take() {
            Some(stdout) => {
                spawn_reader(stdout, self.generation, self.sender.clone());
                true
            }
            None => false,
        };
        let channel = Channel {
            commands,
            announcements_open,
        };
        Some(self.watch(RuntimeProcess::Launched(child), Some(channel)))
    }

    fn adopt(&mut self) -> Result<OpenedProcess, ForeignReason> {
        let record =
            read_boot_record(self.target.storage_root()).map_err(
                |unavailable| match unavailable {
                    BootRecordUnavailable::Absent => ForeignReason::RecordAbsent,
                    BootRecordUnavailable::Unreadable => ForeignReason::RecordUnreadable,
                },
            )?;
        let opened = open_process(record.pid).map_err(|error| match error {
            InspectError::NotRunning => ForeignReason::StaleRecord,
            InspectError::Unsupported | InspectError::Failed(_) => ForeignReason::Uninspectable,
        })?;
        let installed = assess(
            &record,
            &opened.identity,
            current_session(),
            self.collaborators.versions.as_ref(),
        )?;
        self.emit(Event::Adopted {
            pid: opened.identity.pid,
            version: installed.version,
        });
        Ok(opened)
    }

    fn watch(&mut self, runtime: RuntimeProcess, channel: Option<Channel>) -> Ended {
        let phase = if channel.is_some() {
            Phase::Starting {
                deadline: Instant::now() + self.config.readiness_ceiling,
            }
        } else {
            Phase::Unmonitored
        };
        let mut watch = Watch {
            pid: runtime.pid(),
            runtime,
            channel,
            phase,
            cause: None,
            idle_pending: false,
            stop_deadline: None,
            announced: None,
        };
        loop {
            if self.session_ending.load(Ordering::SeqCst) {
                self.begin_stop(&mut watch, StopCause::SessionEnd);
            }
            if let Some(exit) = watch.runtime.try_exit() {
                return self.ended(&watch, exit, false);
            }
            let now = Instant::now();
            if watch.stop_deadline.is_some_and(|deadline| now >= deadline) {
                return self.terminate(watch);
            }
            self.advance(&mut watch, now);
            let wait = self.next_wait(&watch, Instant::now());
            match self.inputs.recv_timeout(wait) {
                Ok(Input::Line { generation, line }) if generation == self.generation => {
                    self.announcement(&mut watch, line);
                }
                Ok(Input::Closed { generation }) if generation == self.generation => {
                    if let Some(channel) = watch.channel.as_mut() {
                        channel.announcements_open = false;
                    }
                    self.emit(Event::ChannelClosed { pid: watch.pid });
                }
                Ok(Input::Control(Request::Stop)) => {
                    self.begin_stop(&mut watch, StopCause::Requested)
                }
                Ok(Input::Control(Request::StopIfIdle)) => self.stop_if_idle(&mut watch),
                Ok(Input::Control(Request::SessionEnd)) => {
                    self.begin_stop(&mut watch, StopCause::SessionEnd)
                }
                Ok(Input::Line { .. } | Input::Closed { .. })
                | Err(RecvTimeoutError::Timeout | RecvTimeoutError::Disconnected) => {}
            }
        }
    }

    /// Readiness ceiling, pings and staleness, unless a stop is already in progress.
    fn advance(&mut self, watch: &mut Watch, now: Instant) {
        if watch.stop_deadline.is_some() {
            return;
        }
        let hung = match &mut watch.phase {
            Phase::Starting { deadline } => (now >= *deadline).then_some(false),
            Phase::Ready {
                sent,
                last_fresh,
                next_ping,
                ..
            } => {
                if now.saturating_duration_since(*last_fresh) >= self.config.heartbeat_staleness {
                    Some(true)
                } else {
                    if now >= *next_ping {
                        *sent += 1;
                        let seq = *sent;
                        *next_ping = now + self.config.heartbeat_interval;
                        if let Some(channel) = &watch.channel {
                            channel.send(Command::Ping { seq });
                        }
                    }
                    None
                }
            }
            Phase::Unmonitored => None,
        };
        if let Some(ready) = hung {
            self.emit(Event::HangDetected {
                pid: watch.pid,
                ready,
            });
            self.begin_stop(watch, StopCause::Hang);
        }
    }

    fn next_wait(&self, watch: &Watch, now: Instant) -> Duration {
        let deadline = match (&watch.phase, watch.stop_deadline) {
            (_, Some(deadline)) => Some(deadline),
            (Phase::Starting { deadline }, None) => Some(*deadline),
            (
                Phase::Ready {
                    last_fresh,
                    next_ping,
                    ..
                },
                None,
            ) => Some((*next_ping).min(*last_fresh + self.config.heartbeat_staleness)),
            (Phase::Unmonitored, None) => None,
        };
        deadline.map_or(self.config.poll_interval, |deadline| {
            deadline
                .saturating_duration_since(now)
                .min(self.config.poll_interval)
        })
    }

    fn announcement(&mut self, watch: &mut Watch, line: Result<Announcement, LineRefusal>) {
        match line {
            Err(refusal) => self.emit(Event::AnnouncementRefused(refusal)),
            Ok(Announcement::Ready(ready)) => self.ready(watch, &ready),
            Ok(Announcement::Heartbeat(heartbeat)) => self.heartbeat(watch, heartbeat),
            Ok(Announcement::Stopping(reason)) => watch.announced = Some(reason),
            Ok(Announcement::Busy) => {
                if watch.idle_pending {
                    watch.idle_pending = false;
                    self.emit(Event::Busy { pid: watch.pid });
                }
            }
            Ok(Announcement::Refused(code)) => self.emit(Event::CommandRefused(code)),
        }
    }

    fn ready(&mut self, watch: &mut Watch, ready: &Ready) {
        if !matches!(watch.phase, Phase::Starting { .. }) || watch.stop_deadline.is_some() {
            return;
        }
        let launched = u64::from(watch.pid) == ready.pid
            && ready.version == self.target.expected_version()
            && ready.storage_identity == self.target.storage_identity();
        if !launched {
            self.begin_stop(watch, StopCause::Defect);
            return;
        }
        let now = Instant::now();
        watch.phase = Phase::Ready {
            sent: 0,
            acknowledged: 0,
            last_fresh: now,
            next_ping: now,
        };
        self.reprobed = false;
        self.restart_permit = None;
        self.emit(Event::Ready {
            pid: watch.pid,
            boot_id: ready.boot_id.clone(),
        });
        let event = if self.boot_record_confirms(watch.pid, ready) {
            Event::BootRecordConfirmed { pid: watch.pid }
        } else {
            Event::BootRecordMismatch { pid: watch.pid }
        };
        self.emit(event);
    }

    /// Whether the published record names this boot of the held process.
    fn boot_record_confirms(&self, pid: u32, ready: &Ready) -> bool {
        let Ok(record) = read_boot_record(self.target.storage_root()) else {
            return false;
        };
        let claimed = record.boot_id == ready.boot_id
            && record.pid == pid
            && record.version == ready.version
            && record.admission == ready.admission;
        // The launched child is held, so this pid still names it.
        claimed
            && open_process(pid)
                .is_ok_and(|opened| opened.identity.created == record.process_created)
    }

    fn heartbeat(&self, watch: &mut Watch, heartbeat: Heartbeat) {
        let Phase::Ready {
            sent,
            acknowledged,
            last_fresh,
            ..
        } = &mut watch.phase
        else {
            return;
        };
        if heartbeat.seq <= *acknowledged || heartbeat.seq > *sent {
            return;
        }
        *acknowledged = heartbeat.seq;
        let ceiling =
            u64::try_from(self.config.accept_tick_ceiling.as_millis()).unwrap_or(u64::MAX);
        if heartbeat.tick_age_ms.is_some_and(|age| age <= ceiling) {
            *last_fresh = Instant::now();
        }
    }

    fn stop_if_idle(&self, watch: &mut Watch) {
        if watch.stop_deadline.is_some() {
            return;
        }
        let sent = watch
            .channel
            .as_ref()
            .is_some_and(|channel| channel.send(Command::StopIfIdle));
        if sent {
            watch.idle_pending = true;
        } else {
            self.emit(Event::IdleStopUnavailable { pid: watch.pid });
        }
    }

    /// Ask for the drain over the channel, else by stop signal, and bound the wait.
    fn begin_stop(&self, watch: &mut Watch, cause: StopCause) {
        let upgrading = cause == StopCause::SessionEnd && watch.cause != Some(cause);
        watch.cause = watch.cause.max(Some(cause));
        if watch.stop_deadline.is_some() && !upgrading {
            return;
        }
        let command = if cause == StopCause::SessionEnd {
            Command::SessionEnd
        } else {
            Command::Stop
        };
        let over_channel = watch
            .channel
            .as_ref()
            .is_some_and(|channel| channel.send(command));
        let path = if over_channel {
            StopPath::Channel
        } else {
            match self.collaborators.stop_signal.deliver(&mut watch.runtime) {
                Ok(()) => StopPath::Signal,
                Err(error) => StopPath::Undelivered(error),
            }
        };
        let bound = if cause == StopCause::SessionEnd {
            self.config.session_end_bound
        } else {
            self.config.drain_bound
        };
        let deadline = Instant::now() + bound;
        watch.stop_deadline = Some(
            watch
                .stop_deadline
                .map_or(deadline, |old| old.min(deadline)),
        );
        self.emit(Event::StopRequested {
            pid: watch.pid,
            cause,
            path,
        });
    }

    fn terminate(&self, mut watch: Watch) -> Ended {
        let _ = watch.runtime.terminate();
        self.emit(Event::Terminated { pid: watch.pid });
        let deadline = Instant::now() + self.config.termination_bound;
        loop {
            if watch.runtime.try_exit().is_some() || Instant::now() >= deadline {
                return self.ended(&watch, RuntimeExit::Terminated, true);
            }
            thread::sleep(self.config.poll_interval.min(Duration::from_millis(10)));
        }
    }

    fn ended(&self, watch: &Watch, exit: RuntimeExit, terminated: bool) -> Ended {
        self.emit(Event::Exited {
            pid: watch.pid,
            exit,
            announced: watch.announced,
        });
        let idle = watch.idle_pending.then_some(StopCause::IdleRequested);
        Ended {
            pid: watch.pid,
            exit,
            cause: watch.cause.max(idle),
            terminated,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::supervision::exit::STATUS_CONTROL_C_EXIT;

    fn code(code: u32) -> RuntimeExit {
        RuntimeExit::from_code(code)
    }

    #[test]
    fn unrequested_stops_restart_as_outside_stops() {
        for exit in [code(65), code(0), code(STATUS_CONTROL_C_EXIT)] {
            assert_eq!(
                decide(exit, None),
                Decision::Restart(RestartClass::OutsideStop),
                "{exit:?}"
            );
        }
    }

    #[test]
    fn any_exit_after_a_requested_stop_ends_supervision() {
        for exit in [code(64), code(65), code(0), code(71), code(0xC000_0005)] {
            assert_eq!(decide(exit, Some(StopCause::Requested)), Decision::Stopped);
            assert_eq!(
                decide(exit, Some(StopCause::IdleRequested)),
                Decision::Stopped
            );
        }
    }

    #[test]
    fn a_hang_restarts_whatever_the_exit_code() {
        for exit in [code(64), RuntimeExit::Terminated, code(71)] {
            assert_eq!(
                decide(exit, Some(StopCause::Hang)),
                Decision::Restart(RestartClass::Hang)
            );
        }
    }

    #[test]
    fn reason_codes_select_their_class() {
        assert_eq!(decide(code(67), None), Decision::Adopt);
        assert_eq!(
            decide(code(68), None),
            Decision::StandDown(StandDownReason::RootMismatch)
        );
        assert_eq!(
            decide(code(72), None),
            Decision::StandDown(StandDownReason::ElevatedTokenRefused)
        );
        assert_eq!(decide(code(69), None), Decision::VersionMismatch);
        assert_eq!(decide(code(70), None), Decision::WitnessLoss);
        for unexpected in [64, 66, 71, 73, 3, 120, 0xC000_0005] {
            assert_eq!(
                decide(code(unexpected), None),
                Decision::Restart(RestartClass::Unexpected),
                "{unexpected}"
            );
        }
        for launch in [1, 2] {
            assert_eq!(
                decide(code(launch), None),
                Decision::Restart(RestartClass::LaunchFailure)
            );
        }
    }

    #[test]
    fn effects_settle_only_after_a_clean_drain() {
        let ended = |exit, cause, terminated| Ended {
            pid: 1,
            exit,
            cause,
            terminated,
        };
        assert_eq!(
            ended(code(64), Some(StopCause::Requested), false).effects(),
            Effects::Settled
        );
        assert_eq!(ended(code(65), None, false).effects(), Effects::Settled);
        assert_eq!(
            ended(code(71), Some(StopCause::Requested), false).effects(),
            Effects::Unknown
        );
        assert_eq!(
            ended(RuntimeExit::Terminated, Some(StopCause::Requested), true).effects(),
            Effects::Unknown
        );
        assert_eq!(
            ended(code(64), Some(StopCause::Hang), false).effects(),
            Effects::Unknown
        );
        assert_eq!(
            ended(code(0xC000_0005), None, false).effects(),
            Effects::Unknown
        );
        assert_eq!(
            ended(code(66), Some(StopCause::SessionEnd), false).effects(),
            Effects::Unknown
        );
        for exit in [code(0), code(64), code(65), code(71)] {
            assert_eq!(
                ended(exit, Some(StopCause::SessionEnd), false).effects(),
                Effects::Unknown
            );
            assert_eq!(decide(exit, Some(StopCause::SessionEnd)), Decision::Stopped);
        }
    }

    #[test]
    fn a_requested_stop_outranks_a_hang_escalation() {
        assert_eq!(
            Some(StopCause::Hang).max(Some(StopCause::Requested)),
            Some(StopCause::Requested)
        );
        assert_eq!(
            Some(StopCause::Requested).max(Some(StopCause::Hang)),
            Some(StopCause::Requested)
        );
    }
}
