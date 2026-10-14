//! Keeps one launcher running exactly while the person's sign-in allows it,
//! and publishes where the agent service is.
//!
//! The launcher starts when the canonical sign-in status reads present, with
//! the runtime available and a profile selected. It stops, by closing its
//! standard input, when any of that changes: sign-out, a lock, idle or
//! absolute expiry, an unknown or unreadable status, another active profile,
//! the runtime becoming unavailable, or the window closing. This host keeps no
//! runtime connection, session, password or provider key: the bearer it mints
//! for the gateway is its only secret, held in memory.

use super::launcher::Event;
use super::runner::{self, Signal, Supervised};
use cadrumo_application::{
    diagnostics::Diagnostics,
    error::application::{ApplicationError, ErrorCode, Operation, Result},
};
use serde::Serialize;
use std::{
    fmt::Write as _,
    future::Future,
    pin::Pin,
    process::Command,
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, AtomicU64, Ordering},
    },
    time::{Duration, Instant},
};
use tauri::ipc::Channel;
use tokio::sync::{Notify, mpsc};
use zeroize::Zeroizing;

/// How often the sign-in status is read while the agent is supervised: the
/// cadence of the account menu's own observation.
pub const POLL: Duration = Duration::from_secs(2);
/// Initial retry delay; later failures back off, up to three retries.
pub const RETRY: Duration = Duration::from_secs(30);

pub use cadrumo_application::diagnostics::service::AgentRefusal as Refusal;
use cadrumo_application::diagnostics::service::{AgentStopCause, ServiceFact};

/// Where the agent service of the signed-in profile is.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "state", rename_all = "snake_case")]
pub enum State {
    Stopped,
    Starting,
    Ready { agent_version: String },
    Refused { code: Refusal },
}

/// The published status: its state, and the lane it runs on.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Status {
    #[serde(flatten)]
    pub state: State,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub lane: Option<&'static str>,
}

/// What the sign-in status allows, read from one observation.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Allowed {
    /// Serve the profile with this label.
    Serve(String),
    Refuse(Refusal),
}

/// One sign-in observation, as the supervisor reads it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Observation {
    pub supported: bool,
    pub present: bool,
    pub runtime_available: bool,
    pub refused: bool,
    pub active_profile: Option<String>,
}

/// Anything but a present sign-in on a working runtime with a selected
/// profile stops the agent. A failed read is unknown, and unknown stops it.
pub fn allowed(observed: &Result<Observation>) -> Allowed {
    let Ok(observed) = observed else {
        return Allowed::Refuse(Refusal::RuntimeUnavailable);
    };
    if !observed.supported {
        return Allowed::Refuse(Refusal::ServiceAbsent);
    }
    if !observed.runtime_available || observed.refused {
        return Allowed::Refuse(Refusal::RuntimeUnavailable);
    }
    match (&observed.active_profile, observed.present) {
        (Some(profile), true) => Allowed::Serve(profile.clone()),
        _ => Allowed::Refuse(Refusal::SignedOut),
    }
}

pub type Observe =
    Arc<dyn Fn() -> Pin<Box<dyn Future<Output = Result<Observation>> + Send>> + Send + Sync>;
/// Builds the command for the profile, given the bearer minted for it.
pub type Launch = Arc<dyn Fn(&str, &str) -> Result<Prepared> + Send + Sync>;

/// What one start runs.
pub struct Prepared {
    pub command: Command,
}

/// How the gateway of the running launcher is reached. The bearer goes
/// nowhere but to that loopback gateway.
#[derive(Clone)]
pub struct Gateway {
    pub port: u16,
    pub bearer: Arc<Zeroizing<String>>,
    /// The profile's agent workspace the launcher reported.
    pub workspace_root: String,
    /// Which launcher reported it; a later one is another gateway.
    pub generation: u64,
}

struct Running {
    supervised: Supervised,
    profile: String,
    generation: u64,
    bearer: Arc<Zeroizing<String>>,
}

struct Listener {
    channel: Channel<Status>,
}

struct Shared {
    status: Mutex<Status>,
    listener: Mutex<Option<Listener>>,
    gateway: Mutex<Option<Gateway>>,
    running: Mutex<Option<Running>>,
    closed: AtomicBool,
    started: AtomicBool,
    retry_requested: AtomicBool,
    wake: Notify,
    generation: AtomicU64,
    worker: Mutex<Option<tauri::async_runtime::JoinHandle<()>>>,
    diagnostics: Arc<Diagnostics>,
    grace: Duration,
    poll: Duration,
    retry: Duration,
}

/// The supervision of one host's launcher.
pub struct Supervisor {
    shared: Arc<Shared>,
    observe: Observe,
    launch: Option<Launch>,
}

fn lock<T>(mutex: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    mutex
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

fn mint_bearer() -> Result<Zeroizing<String>> {
    let mut bytes = Zeroizing::new([0u8; 32]);
    getrandom::fill(&mut *bytes).map_err(|e| {
        ApplicationError::new(ErrorCode::SpawnFailed, Operation::Cli)
            .caused_by(std::io::Error::other(e.to_string()))
    })?;
    let mut encoded = Zeroizing::new(String::with_capacity(64));
    for byte in bytes.iter() {
        // Writing to a string cannot fail.
        let _ = write!(encoded, "{byte:02x}");
    }
    Ok(encoded)
}

impl Supervisor {
    /// `launch` builds the launcher command; without one this host has no
    /// agent service and says so.
    pub fn new(observe: Observe, launch: Option<Launch>, diagnostics: Arc<Diagnostics>) -> Self {
        Self::with_timing(
            observe,
            launch,
            diagnostics,
            runner::STOP_GRACE,
            POLL,
            RETRY,
        )
    }

    pub fn with_timing(
        observe: Observe,
        launch: Option<Launch>,
        diagnostics: Arc<Diagnostics>,
        grace: Duration,
        poll: Duration,
        retry: Duration,
    ) -> Self {
        let status = if launch.is_some() {
            Status {
                state: State::Stopped,
                lane: Some("development"),
            }
        } else {
            Status {
                state: State::Refused {
                    code: Refusal::ServiceAbsent,
                },
                lane: None,
            }
        };
        Self {
            shared: Arc::new(Shared {
                status: Mutex::new(status),
                listener: Mutex::new(None),
                gateway: Mutex::new(None),
                running: Mutex::new(None),
                closed: AtomicBool::new(false),
                started: AtomicBool::new(false),
                retry_requested: AtomicBool::new(false),
                wake: Notify::new(),
                generation: AtomicU64::new(0),
                worker: Mutex::new(None),
                diagnostics,
                grace,
                poll,
                retry,
            }),
            observe,
            launch,
        }
    }

    /// The status now. The first ask begins supervision.
    pub fn status(&self) -> Status {
        self.begin();
        lock(&self.shared.status).clone()
    }

    /// An explicit user retry starts a new bounded attempt budget. Passive
    /// status reads never reset failures; canonical sign-in still gates launch.
    pub fn retry(&self) {
        self.shared.retry_requested.store(true, Ordering::Release);
        self.shared.wake.notify_one();
        self.begin();
    }

    /// The gateway of the launcher that reported ready, while it serves.
    pub fn gateway(&self) -> Option<Gateway> {
        lock(&self.shared.gateway).clone()
    }

    /// Sends every later status change to `channel`, replacing any earlier
    /// listener, and the current status at once.
    pub fn subscribe(&self, channel: Channel<Status>) -> u32 {
        self.begin();
        let id = channel.id();
        let current = lock(&self.shared.status).clone();
        let mut listener = lock(&self.shared.listener);
        if channel.send(current).is_ok() {
            *listener = Some(Listener { channel });
        }
        id
    }

    /// Removes the listener `subscription`, never a newer one.
    pub fn unsubscribe(&self, subscription: u32) {
        let mut listener = lock(&self.shared.listener);
        if listener
            .as_ref()
            .is_some_and(|held| held.channel.id() == subscription)
        {
            *listener = None;
        }
    }

    fn begin(&self) {
        let Some(launch) = self.launch.clone() else {
            return;
        };
        if self.shared.closed.load(Ordering::Acquire)
            || self.shared.started.swap(true, Ordering::AcqRel)
        {
            return;
        }
        let shared = self.shared.clone();
        let observe = self.observe.clone();
        let worker = tauri::async_runtime::spawn(supervise(shared, observe, launch));
        *lock(&self.shared.worker) = Some(worker);
    }

    /// Stops the launcher and supervision for good, as the window closes.
    pub async fn close(&self) -> Result<()> {
        self.shared.closed.store(true, Ordering::Release);
        self.shared.wake.notify_one();
        let worker = lock(&self.shared.worker).take();
        let stopped = stop_running(&self.shared, None, AgentStopCause::WindowClosing).await;
        if let Some(worker) = worker {
            let _ = worker.await;
        }
        // Supervision may have stored a launcher while this closed; it stops
        // any it holds when it sees the close, and this stops what is left.
        let remaining = stop_running(&self.shared, None, AgentStopCause::WindowClosing).await;
        *lock(&self.shared.listener) = None;
        stopped.and(remaining)
    }
}

fn publish(shared: &Shared, state: State) {
    let status = {
        let mut current = lock(&shared.status);
        if current.state == state {
            return;
        }
        current.state = state;
        current.clone()
    };
    if let State::Refused { code } = status.state {
        shared
            .diagnostics
            .service(None, ServiceFact::AgentRefused { reason: code });
    }
    let mut listener = lock(&shared.listener);
    if listener
        .as_ref()
        .is_some_and(|held| held.channel.send(status).is_err())
    {
        *listener = None;
    }
}

/// Stops the running launcher, if any. With a generation, only that one.
async fn stop_running(
    shared: &Arc<Shared>,
    generation: Option<u64>,
    cause: AgentStopCause,
) -> Result<()> {
    let taken = {
        let mut running = lock(&shared.running);
        if generation.is_some_and(|wanted| running.as_ref().map(|r| r.generation) != Some(wanted)) {
            return Ok(());
        }
        running.take()
    };
    let Some(running) = taken else {
        return Ok(());
    };
    {
        let mut gateway = lock(&shared.gateway);
        if gateway.as_ref().map(|g| g.generation) == Some(running.generation) {
            *gateway = None;
        }
    }
    let process = running.supervised.process_ref();
    shared
        .diagnostics
        .service(Some(process), ServiceFact::AgentStopping { cause });
    let grace = shared.grace;
    let diagnostics = shared.diagnostics.clone();
    let ended = tauri::async_runtime::spawn_blocking(move || running.supervised.stop(grace))
        .await
        .map_err(|_| ApplicationError::new(ErrorCode::Panic, Operation::Cli))
        .and_then(|ended| ended);
    if let Err(error) = &ended {
        diagnostics.failure(error.clone());
    }
    if ended.is_ok() {
        diagnostics.service(Some(process), ServiceFact::AgentStopped { cause });
    }
    ended.map(|_| ())
}

async fn start(
    shared: &Arc<Shared>,
    launch: &Launch,
    profile: String,
    signals: &mpsc::UnboundedSender<(u64, Signal)>,
) -> Result<()> {
    let bearer = Arc::new(mint_bearer()?);
    let Prepared { command } = launch(&bearer, &profile)?;
    let generation = shared.generation.fetch_add(1, Ordering::AcqRel) + 1;
    shared
        .diagnostics
        .service(None, ServiceFact::AgentStarting { generation });
    let sender = signals.clone();
    let diagnostics = shared.diagnostics.clone();
    let secret = bearer.clone();
    let supervised = tauri::async_runtime::spawn_blocking(move || {
        runner::start_child(
            command,
            Some(secret.as_str()),
            move |signal| {
                let _ = sender.send((generation, signal));
            },
            diagnostics,
        )
    })
    .await
    .map_err(|_| ApplicationError::new(ErrorCode::Panic, Operation::Cli))??;
    let refused = {
        let mut running = lock(&shared.running);
        if shared.closed.load(Ordering::Acquire) {
            Some(supervised)
        } else {
            *running = Some(Running {
                supervised,
                profile,
                generation,
                bearer,
            });
            None
        }
    };
    if let Some(supervised) = refused {
        let grace = shared.grace;
        let _ = tauri::async_runtime::spawn_blocking(move || supervised.stop(grace)).await;
    }
    Ok(())
}

/// A failed service gets three automatic retries. The last refusal remains
/// visible until an explicit retry, sign-in/profile change or host reopen.
#[derive(Default)]
struct RetryBudget {
    failures: u32,
    after: Option<Instant>,
    refusal: Option<Refusal>,
}

impl RetryBudget {
    fn waiting(&self) -> bool {
        self.failures >= 4 || self.after.is_some_and(|at| Instant::now() < at)
    }

    fn failed(&mut self, shared: &Shared) {
        if let State::Refused { code } = lock(&shared.status).state {
            self.refusal = Some(code);
        }
        self.failures = self.failures.saturating_add(1);
        if self.failures >= 4 {
            self.after = None;
            shared.diagnostics.service(
                None,
                ServiceFact::AgentRetryExhausted {
                    attempts: self.failures,
                },
            );
        } else {
            let delay = shared.retry.saturating_mul(1 << (self.failures - 1));
            self.after = Some(Instant::now() + delay);
            shared.diagnostics.service(
                None,
                ServiceFact::AgentRetryScheduled {
                    delay_ms: delay.as_millis().try_into().unwrap_or(u64::MAX),
                },
            );
        }
    }
}

async fn supervise(shared: Arc<Shared>, observe: Observe, launch: Launch) {
    let (signals, mut received) = mpsc::unbounded_channel::<(u64, Signal)>();
    let mut retries = RetryBudget::default();
    let mut serving: Option<String> = None;
    'supervision: while !shared.closed.load(Ordering::Acquire) {
        if shared.retry_requested.swap(false, Ordering::AcqRel) {
            retries = RetryBudget::default();
        }
        let wake = shared.wake.notified();
        tokio::pin!(wake);
        wake.as_mut().enable();
        let observation = observe();
        tokio::pin!(observation);
        // CLI status reads can take seconds. Launcher refusal/exit must clear
        // the gateway and publish its cause while that read is still pending.
        let observed = loop {
            tokio::select! {
                biased;
                _ = &mut wake => {
                    if shared.closed.load(Ordering::Acquire) {
                        break 'supervision;
                    }
                    continue 'supervision;
                }
                Some((generation, signal)) = received.recv() => {
                    if handle(&shared, generation, signal).await {
                        retries.failed(&shared);
                    }
                }
                observed = &mut observation => break observed,
            }
        };
        let allowed = allowed(&observed);
        if shared.closed.load(Ordering::Acquire) {
            break;
        }
        let current = lock(&shared.running).as_ref().map(|r| r.profile.clone());
        match (&current, &allowed) {
            (Some(profile), Allowed::Serve(wanted)) if profile == wanted => {}
            (Some(_), _) => {
                let cause = match &allowed {
                    Allowed::Serve(_) => AgentStopCause::ProfileChanged,
                    Allowed::Refuse(Refusal::SignedOut) => AgentStopCause::SignInUnavailable,
                    Allowed::Refuse(_) => AgentStopCause::RuntimeUnavailable,
                };
                let _ = stop_running(&shared, None, cause).await;
                match &allowed {
                    Allowed::Refuse(code) => {
                        if *code == Refusal::SignedOut {
                            retries = RetryBudget::default();
                            serving = None;
                        }
                        publish(&shared, State::Refused { code: *code });
                    }
                    // Another profile: the next round starts its own.
                    Allowed::Serve(_) => {
                        publish(&shared, State::Stopped);
                        retries = RetryBudget::default();
                        continue;
                    }
                }
            }
            (None, Allowed::Refuse(code)) => {
                // A failed observation is not evidence of a new sign-in. Keep
                // the same profile's budget through transient runtime failures.
                if *code == Refusal::SignedOut {
                    retries = RetryBudget::default();
                    serving = None;
                }
                publish(&shared, State::Refused { code: *code });
            }
            (None, Allowed::Serve(profile)) => {
                // A refused start waits before it is tried again, unless the
                // sign-in changed in between.
                if serving.as_deref() != Some(profile.as_str()) {
                    retries = RetryBudget::default();
                }
                if !retries.waiting() {
                    serving = Some(profile.clone());
                    publish(&shared, State::Starting);
                    if let Err(error) = start(&shared, &launch, profile.clone(), &signals).await {
                        shared.diagnostics.host_failure(
                            cadrumo_application::diagnostics::HostStage::Agent,
                            error,
                        );
                        publish(
                            &shared,
                            State::Refused {
                                code: Refusal::ServiceFailed,
                            },
                        );
                        retries.failed(&shared);
                    }
                } else if let Some(code) = retries.refusal {
                    // The runtime recovered, but this service's last failure
                    // still explains why its retry budget is waiting/exhausted.
                    publish(&shared, State::Refused { code });
                }
            }
        }
        let deadline = tokio::time::sleep(shared.poll);
        tokio::pin!(deadline);
        loop {
            tokio::select! {
                _ = &mut wake => break,
                _ = &mut deadline => break,
                Some((generation, signal)) = received.recv() => {
                    if handle(&shared, generation, signal).await {
                        retries.failed(&shared);
                    }
                }
            }
        }
    }
    let _ = stop_running(&shared, None, AgentStopCause::WindowClosing).await;
}

/// Acts on one launcher signal. True when the launcher ended unasked, which
/// delays the next start.
async fn handle(shared: &Arc<Shared>, generation: u64, signal: Signal) -> bool {
    let (bearer, process) = {
        let running = lock(&shared.running);
        match running.as_ref() {
            Some(running) if running.generation == generation => {
                (running.bearer.clone(), running.supervised.process_ref())
            }
            _ => return false,
        }
    };
    match signal {
        Signal::Event(Event::Ready {
            gateway_port,
            agent_version,
            workspace_root,
        }) => {
            *lock(&shared.gateway) = Some(Gateway {
                port: gateway_port,
                bearer,
                workspace_root,
                generation,
            });
            shared.diagnostics.service(
                Some(process),
                ServiceFact::AgentReady {
                    generation,
                    gateway_port,
                },
            );
            publish(shared, State::Ready { agent_version });
            false
        }
        Signal::Event(Event::Refused { code }) => {
            publish(
                shared,
                State::Refused {
                    code: Refusal::from_launcher(&code),
                },
            );
            let _ = stop_running(shared, Some(generation), AgentStopCause::LauncherRefused).await;
            true
        }
        Signal::Event(Event::Stopped { reason }) => {
            *lock(&shared.gateway) = None;
            publish(
                shared,
                State::Refused {
                    code: Refusal::from_launcher(&reason),
                },
            );
            false
        }
        Signal::Violation => {
            shared
                .diagnostics
                .service(Some(process), ServiceFact::AgentProtocolRefused {});
            publish(
                shared,
                State::Refused {
                    code: Refusal::ServiceFailed,
                },
            );
            let _ = stop_running(shared, Some(generation), AgentStopCause::ProtocolRefused).await;
            true
        }
        Signal::Ended => {
            let unasked = matches!(
                lock(&shared.status).state,
                State::Starting | State::Ready { .. }
            );
            if unasked {
                publish(
                    shared,
                    State::Refused {
                        code: Refusal::ServiceFailed,
                    },
                );
            }
            let _ = stop_running(shared, Some(generation), AgentStopCause::LauncherEnded).await;
            true
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn observed(present: bool, runtime: bool, profile: Option<&str>) -> Result<Observation> {
        Ok(Observation {
            supported: true,
            present,
            runtime_available: runtime,
            refused: false,
            active_profile: profile.map(str::to_owned),
        })
    }

    #[test]
    fn only_a_present_sign_in_on_a_working_runtime_with_a_profile_serves() {
        assert_eq!(
            allowed(&observed(true, true, Some("A"))),
            Allowed::Serve("A".into())
        );
        for (status, refusal) in [
            // Sign-out, a lock, idle or absolute expiry: the sign-in is gone.
            (observed(false, true, Some("A")), Refusal::SignedOut),
            (observed(true, true, None), Refusal::SignedOut),
            (
                observed(true, false, Some("A")),
                Refusal::RuntimeUnavailable,
            ),
            (
                Err(ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)),
                Refusal::RuntimeUnavailable,
            ),
        ] {
            assert_eq!(allowed(&status), Allowed::Refuse(refusal));
        }
        let mut refused = observed(true, true, Some("A")).unwrap();
        refused.refused = true;
        assert_eq!(
            allowed(&Ok(refused.clone())),
            Allowed::Refuse(Refusal::RuntimeUnavailable)
        );
        refused.supported = false;
        assert_eq!(
            allowed(&Ok(refused)),
            Allowed::Refuse(Refusal::ServiceAbsent)
        );
    }

    #[test]
    fn statuses_serialize_as_the_column_reads_them() {
        let lane = Some("development");
        for (state, expected) in [
            (
                State::Stopped,
                serde_json::json!({"state": "stopped", "lane": "development"}),
            ),
            (
                State::Starting,
                serde_json::json!({"state": "starting", "lane": "development"}),
            ),
            (
                State::Ready {
                    agent_version: "0.4.1".into(),
                },
                serde_json::json!({"state": "ready", "agent_version": "0.4.1", "lane": "development"}),
            ),
            (
                State::Refused {
                    code: Refusal::ProviderCredentialMissing,
                },
                serde_json::json!({"state": "refused", "code": "agent_provider_credential_missing", "lane": "development"}),
            ),
        ] {
            assert_eq!(
                serde_json::to_value(Status { state, lane }).unwrap(),
                expected
            );
        }
        assert_eq!(
            serde_json::to_value(Status {
                state: State::Refused {
                    code: Refusal::ServiceAbsent
                },
                lane: None
            })
            .unwrap(),
            serde_json::json!({"state": "refused", "code": "agent_service_absent"})
        );
        // Preserve the launcher's actionable root-admission refusal.
        assert_eq!(
            Refusal::from_launcher("agent_root_unmarked"),
            Refusal::RootUnmarked
        );
        assert_eq!(
            Refusal::from_launcher("agent_signed_out"),
            Refusal::SignedOut
        );
    }

    #[test]
    fn the_bearer_is_fresh_hex_each_time() {
        let first = mint_bearer().unwrap();
        let second = mint_bearer().unwrap();
        assert_eq!(first.len(), 64);
        assert!(first.bytes().all(|b| b.is_ascii_hexdigit()));
        assert_ne!(*first, *second);
    }

    #[tokio::test]
    async fn repeated_start_failures_exhaust_retries_and_profile_change_resets_them() {
        let source = Arc::new(Mutex::new(observed(true, true, Some("A"))));
        let current = source.clone();
        let observe: Observe = Arc::new(move || {
            let result = lock(&current).clone();
            Box::pin(async move { result })
        });
        let attempts = Arc::new(AtomicU64::new(0));
        let count = attempts.clone();
        let launch: Launch = Arc::new(move |_, _| {
            count.fetch_add(1, Ordering::SeqCst);
            Err(ApplicationError::new(
                ErrorCode::SpawnFailed,
                Operation::Cli,
            ))
        });
        let diagnostics = Arc::new(Diagnostics::default());
        let supervisor = Supervisor::with_timing(
            observe,
            Some(launch),
            diagnostics.clone(),
            Duration::from_millis(1),
            Duration::from_millis(1),
            Duration::from_millis(2),
        );
        supervisor.status();
        tokio::time::timeout(Duration::from_secs(5), async {
            while attempts.load(Ordering::SeqCst) < 4 {
                tokio::time::sleep(Duration::from_millis(5)).await;
            }
        })
        .await
        .unwrap();
        tokio::time::sleep(Duration::from_millis(50)).await;
        assert_eq!(attempts.load(Ordering::SeqCst), 4);
        assert_eq!(
            supervisor.status().state,
            State::Refused {
                code: Refusal::ServiceFailed
            }
        );
        let facts: Vec<_> = diagnostics
            .snapshot(u64::MAX)
            .events
            .into_iter()
            .filter_map(|event| event.service)
            .collect();
        let delays: Vec<_> = facts
            .iter()
            .filter_map(|fact| match fact {
                ServiceFact::AgentRetryScheduled { delay_ms } => Some(*delay_ms),
                _ => None,
            })
            .collect();
        assert_eq!(delays, [2, 4, 8]);
        assert!(
            facts
                .iter()
                .any(|fact| matches!(fact, ServiceFact::AgentRetryExhausted { attempts: 4 }))
        );
        // Neither a failed read nor an unavailable runtime creates a new
        // authorization epoch or replenishes an exhausted attempt budget.
        for unavailable in [
            Err(ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)),
            observed(true, false, Some("A")),
        ] {
            *lock(&source) = unavailable;
            tokio::time::timeout(Duration::from_secs(5), async {
                while supervisor.status().state
                    != (State::Refused {
                        code: Refusal::RuntimeUnavailable,
                    })
                {
                    tokio::time::sleep(Duration::from_millis(2)).await;
                }
            })
            .await
            .unwrap();
            *lock(&source) = observed(true, true, Some("A"));
            tokio::time::timeout(Duration::from_secs(5), async {
                while supervisor.status().state
                    != (State::Refused {
                        code: Refusal::ServiceFailed,
                    })
                {
                    tokio::time::sleep(Duration::from_millis(2)).await;
                }
            })
            .await
            .unwrap();
            tokio::time::sleep(Duration::from_millis(30)).await;
            assert_eq!(attempts.load(Ordering::SeqCst), 4);
        }
        supervisor.retry();
        tokio::time::timeout(Duration::from_secs(5), async {
            while attempts.load(Ordering::SeqCst) < 8 {
                tokio::time::sleep(Duration::from_millis(5)).await;
            }
        })
        .await
        .unwrap();
        tokio::time::sleep(Duration::from_millis(50)).await;
        assert_eq!(attempts.load(Ordering::SeqCst), 8);
        *lock(&source) = observed(true, true, Some("B"));
        tokio::time::timeout(Duration::from_secs(5), async {
            while attempts.load(Ordering::SeqCst) < 12 {
                tokio::time::sleep(Duration::from_millis(5)).await;
            }
        })
        .await
        .unwrap();
        supervisor.close().await.unwrap();
        assert_eq!(attempts.load(Ordering::SeqCst), 12);
    }

    #[tokio::test]
    async fn explicit_retry_still_requires_canonical_sign_in() {
        let calls = Arc::new(AtomicU64::new(0));
        let count = calls.clone();
        let observe: Observe = Arc::new(move || {
            count.fetch_add(1, Ordering::SeqCst);
            Box::pin(async { observed(false, true, Some("A")) })
        });
        let launch: Launch = Arc::new(|_, _| panic!("retry cannot authorize a signed-out profile"));
        let supervisor = Supervisor::with_timing(
            observe,
            Some(launch),
            Arc::new(Diagnostics::default()),
            Duration::from_millis(1),
            Duration::from_secs(60),
            Duration::from_millis(1),
        );
        supervisor.status();
        tokio::time::timeout(Duration::from_secs(5), async {
            while supervisor.status().state
                != (State::Refused {
                    code: Refusal::SignedOut,
                })
            {
                tokio::task::yield_now().await;
            }
        })
        .await
        .unwrap();
        let before = calls.load(Ordering::SeqCst);
        supervisor.retry();
        tokio::time::timeout(Duration::from_secs(5), async {
            while calls.load(Ordering::SeqCst) == before {
                tokio::task::yield_now().await;
            }
        })
        .await
        .unwrap();
        assert_eq!(
            supervisor.status().state,
            State::Refused {
                code: Refusal::SignedOut
            }
        );
        supervisor.close().await.unwrap();
    }

    #[tokio::test]
    async fn closing_does_not_wait_for_a_pending_status_read() {
        let entered = Arc::new(Notify::new());
        let notify = entered.clone();
        let observe: Observe = Arc::new(move || {
            let notify = notify.clone();
            Box::pin(async move {
                notify.notify_one();
                std::future::pending().await
            })
        });
        let launch: Launch = Arc::new(|_, _| panic!("pending status cannot authorize launch"));
        let supervisor = Supervisor::new(observe, Some(launch), Arc::new(Diagnostics::default()));
        supervisor.status();
        entered.notified().await;
        tokio::time::timeout(Duration::from_secs(1), supervisor.close())
            .await
            .unwrap()
            .unwrap();
    }

    #[cfg(windows)]
    mod live {
        use super::*;
        use crate::agent::runner::tests::{alive, launcher_script, powershell, reported};
        use tauri::ipc::InvokeResponseBody;

        #[tokio::test(flavor = "multi_thread")]
        async fn launcher_refusal_is_handled_while_status_read_is_pending() {
            let calls = Arc::new(AtomicU64::new(0));
            let count = calls.clone();
            let observe: Observe = Arc::new(move || {
                let first = count.fetch_add(1, Ordering::SeqCst) == 0;
                Box::pin(async move {
                    if first {
                        observed(true, true, Some("A"))
                    } else {
                        std::future::pending().await
                    }
                })
            });
            let launch: Launch = Arc::new(|_, _| {
                Ok(Prepared {
                    command: powershell(
                        "$null = [Console]::In.ReadLine(); Start-Sleep -Milliseconds 500; [Console]::Out.WriteLine('{\"event\":\"agent_refused\",\"code\":\"agent_root_unmarked\"}'); exit 3",
                    ),
                })
            });
            let supervisor = Supervisor::with_timing(
                observe,
                Some(launch),
                Arc::new(Diagnostics::default()),
                Duration::from_secs(5),
                Duration::from_millis(5),
                Duration::from_secs(60),
            );
            supervisor.status();
            tokio::time::timeout(Duration::from_secs(20), async {
                loop {
                    if supervisor.status().state
                        == (State::Refused {
                            code: Refusal::RootUnmarked,
                        })
                        && lock(&supervisor.shared.running).is_none()
                    {
                        break;
                    }
                    tokio::time::sleep(Duration::from_millis(10)).await;
                }
            })
            .await
            .unwrap();
            assert!(
                calls.load(Ordering::SeqCst) >= 2,
                "the second status read is still pending"
            );
            assert!(supervisor.gateway().is_none());
            supervisor.close().await.unwrap();
        }

        struct Rig {
            supervisor: Supervisor,
            observation: Arc<Mutex<Result<Observation>>>,
            statuses: Arc<Mutex<Vec<serde_json::Value>>>,
            diagnostics: Arc<Diagnostics>,
        }

        fn rig(ignore_end: bool) -> Rig {
            let observation = Arc::new(Mutex::new(observed(true, true, Some("A"))));
            let source = observation.clone();
            let observe: Observe = Arc::new(move || {
                let current = lock(&source).clone();
                Box::pin(async move { current })
            });
            let launch: Launch = Arc::new(move |_, _| {
                Ok(Prepared {
                    command: powershell(&launcher_script(ignore_end)),
                })
            });
            let diagnostics = Arc::new(Diagnostics::default());
            let supervisor = Supervisor::with_timing(
                observe,
                Some(launch),
                diagnostics.clone(),
                Duration::from_millis(if ignore_end { 500 } else { 10_000 }),
                Duration::from_millis(100),
                Duration::from_secs(60),
            );
            let statuses = Arc::new(Mutex::new(Vec::new()));
            let sink = statuses.clone();
            supervisor.subscribe(Channel::new(move |body| {
                let InvokeResponseBody::Json(body) = body else {
                    panic!("expected a JSON status")
                };
                sink.lock()
                    .unwrap()
                    .push(serde_json::from_str(&body).unwrap());
                Ok(())
            }));
            Rig {
                supervisor,
                observation,
                statuses,
                diagnostics,
            }
        }

        /// The first status in `state` published at or after index `from`.
        async fn until(rig: &Rig, from: usize, state: &str) -> serde_json::Value {
            let deadline = Instant::now() + Duration::from_secs(40);
            loop {
                let found = {
                    let statuses = rig.statuses.lock().unwrap();
                    statuses[from.min(statuses.len())..]
                        .iter()
                        .find(|status| status["state"] == state)
                        .cloned()
                };
                if let Some(status) = found {
                    return status;
                }
                assert!(
                    Instant::now() < deadline,
                    "never {state}: {:?}",
                    rig.statuses.lock().unwrap()
                );
                tokio::time::sleep(Duration::from_millis(50)).await;
            }
        }

        /// The grandchild the running launcher reported, and its launcher.
        async fn serving(rig: &Rig, from: usize) -> (u32, u32) {
            let ready = until(rig, from, "ready").await;
            let (grandchild, length) = reported(ready["agent_version"].as_str().unwrap());
            assert_eq!(length, "64", "the launcher read the minted bearer");
            let gateway = rig.supervisor.gateway().unwrap();
            assert_eq!(gateway.port, 4000);
            let snapshot = rig.diagnostics.snapshot(u64::MAX);
            let ready = snapshot
                .events
                .iter()
                .rev()
                .find(|event| {
                    matches!(
                        event.service,
                        Some(ServiceFact::AgentReady {
                            gateway_port: 4000,
                            ..
                        })
                    )
                })
                .unwrap();
            let process = ready.status.as_ref().unwrap();
            assert_eq!(
                process.role,
                cadrumo_application::process::status::ProcessRole::AgentLauncher
            );
            assert!(process.pid > 0);
            assert!(
                !serde_json::to_string(&snapshot.events)
                    .unwrap()
                    .contains(gateway.bearer.as_str())
            );
            assert_eq!(gateway.workspace_root, r"C:\lane\ws");
            assert_eq!(gateway.bearer.len(), 64);
            let launcher = lock(&rig.supervisor.shared.running)
                .as_ref()
                .unwrap()
                .supervised
                .id();
            (launcher, grandchild)
        }

        async fn gone(pids: (u32, u32)) {
            let deadline = Instant::now() + Duration::from_secs(20);
            while alive(pids.0) || alive(pids.1) {
                assert!(Instant::now() < deadline, "a started process survived");
                tokio::time::sleep(Duration::from_millis(50)).await;
            }
        }

        #[tokio::test(flavor = "multi_thread")]
        async fn each_sign_in_trigger_stops_the_launcher_and_its_tree() {
            for (trigger, observation, published) in [
                (
                    "sign-out, lock or expiry",
                    observed(false, true, Some("A")),
                    "refused",
                ),
                (
                    "runtime unavailable",
                    observed(true, false, Some("A")),
                    "refused",
                ),
                (
                    "unreadable status",
                    Err(ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)),
                    "refused",
                ),
                ("another profile", observed(true, true, Some("B")), "ready"),
            ] {
                let rig = rig(false);
                assert_eq!(rig.supervisor.status().lane, Some("development"));
                let first = serving(&rig, 0).await;
                let changed = rig.statuses.lock().unwrap().len();
                *rig.observation.lock().unwrap() = observation;
                gone(first).await;
                assert!(
                    rig.supervisor.gateway().is_none_or(|g| g.generation > 1),
                    "{trigger}: the old gateway is forgotten"
                );
                let after = until(&rig, changed, published).await;
                if published == "ready" {
                    // The new profile is served by a new launcher with a new bearer.
                    let second = serving(&rig, changed).await;
                    assert_ne!(second, first);
                    let states: Vec<_> = rig
                        .statuses
                        .lock()
                        .unwrap()
                        .iter()
                        .map(|s| s["state"].clone())
                        .collect();
                    assert!(
                        states
                            .windows(2)
                            .any(|w| w[0] == "stopped" && w[1] == "starting"),
                        "{states:?}"
                    );
                } else {
                    assert_eq!(
                        after["code"],
                        if trigger.starts_with("sign-out") {
                            "agent_signed_out"
                        } else {
                            "agent_runtime_unavailable"
                        },
                        "{trigger}"
                    );
                }
                rig.supervisor.close().await.unwrap();
                assert!(lock(&rig.supervisor.shared.running).is_none());
            }
        }

        #[tokio::test(flavor = "multi_thread")]
        async fn window_close_stops_the_launcher_even_when_it_ignores_its_input() {
            let rig = rig(true);
            rig.supervisor.status();
            let pids = serving(&rig, 0).await;
            let closing = Instant::now();
            rig.supervisor.close().await.unwrap();
            assert!(closing.elapsed() < Duration::from_secs(15));
            gone(pids).await;
            assert!(rig.supervisor.gateway().is_none());
            // Closed for good: nothing starts again.
            rig.supervisor.status();
            tokio::time::sleep(Duration::from_millis(400)).await;
            assert!(lock(&rig.supervisor.shared.running).is_none());
        }

        #[tokio::test(flavor = "multi_thread")]
        async fn a_launcher_that_ends_unasked_is_a_failed_service_and_is_not_restarted_at_once() {
            let observation = Arc::new(Mutex::new(observed(true, true, Some("A"))));
            let source = observation.clone();
            let observe: Observe = Arc::new(move || {
                let current = lock(&source).clone();
                Box::pin(async move { current })
            });
            let starts = Arc::new(AtomicU64::new(0));
            let counted = starts.clone();
            let launch: Launch = Arc::new(move |_, _| {
                counted.fetch_add(1, Ordering::AcqRel);
                Ok(Prepared {
                    command: powershell(
                        "$null = [Console]::In.ReadLine(); [Console]::Out.WriteLine('{\"event\":\"agent_refused\",\"code\":\"agent_root_unmarked\"}'); exit 3",
                    ),
                })
            });
            let supervisor = Supervisor::with_timing(
                observe,
                Some(launch),
                Arc::new(Diagnostics::default()),
                Duration::from_secs(5),
                Duration::from_millis(100),
                Duration::from_secs(60),
            );
            supervisor.status();
            let deadline = Instant::now() + Duration::from_secs(30);
            while supervisor.status().state
                != (State::Refused {
                    code: Refusal::RootUnmarked,
                })
            {
                assert!(Instant::now() < deadline);
                tokio::time::sleep(Duration::from_millis(50)).await;
            }
            tokio::time::sleep(Duration::from_millis(800)).await;
            assert_eq!(starts.load(Ordering::Acquire), 1);
            assert!(lock(&supervisor.shared.running).is_none());
            // A changed sign-in is a new start.
            *observation.lock().unwrap() = observed(false, true, Some("A"));
            tokio::time::sleep(Duration::from_millis(400)).await;
            *observation.lock().unwrap() = observed(true, true, Some("A"));
            let deadline = Instant::now() + Duration::from_secs(10);
            while starts.load(Ordering::Acquire) < 2 {
                assert!(Instant::now() < deadline);
                tokio::time::sleep(Duration::from_millis(50)).await;
            }
            supervisor.close().await.unwrap();
        }
    }
}
