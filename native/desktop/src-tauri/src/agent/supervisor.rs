//! Keeps one launcher running exactly while the person's sign-in allows it,
//! and publishes where the agent service is.
//!
//! The launcher starts when the canonical sign-in status reads present, with
//! the runtime available and a profile selected. It stops, by closing its
//! standard input, when any of that changes: sign-out, a lock, idle or
//! absolute expiry, an unknown or unreadable status, another active profile,
//! the runtime becoming unavailable, or the window closing. A verified installed
//! runtime child holds the exact person session; this host retains its pipe and
//! nonsecret identity. Provider keys cross only a bounded service exchange.

use super::launcher::Event;
use super::runner::{self, Signal, Supervised};
use cadrumo_application::{
    diagnostics::{Diagnostics, HostStage},
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

/// Initial retry delay; later failures back off, up to three retries.
pub const RETRY: Duration = Duration::from_secs(30);
/// Includes the runtime handshake, its 120-second registration exchange and
/// headroom for cold interpreter startup before the service can report ready.
const START_LIMIT: Duration = Duration::from_secs(180);

pub use cadrumo_application::diagnostics::service::AgentRefusal as Refusal;
use cadrumo_application::diagnostics::service::{AgentStopCause, ServiceFact};

fn service_refusal(code: &str) -> Refusal {
    match code {
        "signed_out" => Refusal::SignedOut,
        "credentials_unavailable" | "credentials_invalid" => Refusal::ProviderCredentialMissing,
        "agent_incompatible" | "stores_newer" => Refusal::ServiceIncompatible,
        _ => Refusal::from_launcher(code),
    }
}

/// What the service answered a start request.
#[derive(Debug, PartialEq, Eq)]
enum StartReply {
    Starting,
    /// Other tree work holds the service; the agent it serves is unchanged.
    Busy,
    Refused(Refusal),
}

fn start_reply(reply: &serde_json::Value) -> Result<StartReply> {
    match (reply["kind"].as_str(), reply["code"].as_str()) {
        (Some("starting"), _) => Ok(StartReply::Starting),
        (Some("refused"), Some("busy")) => Ok(StartReply::Busy),
        (Some("refused"), code) => Ok(StartReply::Refused(service_refusal(
            code.unwrap_or("service_failed"),
        ))),
        _ => Err(ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
            .with_reason("agent_start_reply_unexpected")),
    }
}

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
    /// A local sign-in change fences authority until its fresh observation.
    Pending,
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
    if let Err(error) = observed
        && error.code == ErrorCode::SessionUnavailable
        && error.reason.as_deref() == Some("sign_in_mutation_in_progress")
    {
        return Allowed::Pending;
    }
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
/// Resolves at the next sign-in observation after it is called; supervision
/// looks again then, and never on a timer of its own.
pub type Changed = Arc<dyn Fn() -> Pin<Box<dyn Future<Output = ()> + Send>> + Send + Sync>;
/// Builds the command for the profile, given the bearer minted for it.
pub type Launch = Arc<dyn Fn(&str, &str) -> Result<Prepared> + Send + Sync>;

/// What one start runs.
pub struct Prepared {
    pub command: Command,
    pub person: Option<super::person::HeldPerson>,
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
    /// A controller can replace its gateway without replacing the launcher.
    /// Retained observations must not authorize that replacement, even if its
    /// port is reused.
    instance: Arc<()>,
}

impl Gateway {
    pub fn same_instance(&self, other: &Self) -> bool {
        Arc::ptr_eq(&self.instance, &other.instance)
    }
}

struct Running {
    supervised: Supervised,
    profile: String,
    generation: u64,
    bearer: Arc<Zeroizing<String>>,
    gateway_bearer: Arc<Zeroizing<String>>,
    person: Option<super::person::HeldPerson>,
    person_failure: Option<tokio::sync::watch::Receiver<Option<ApplicationError>>>,
    started: Instant,
}

struct Listener {
    channel: Channel<Status>,
}

struct Shared {
    status: Mutex<Status>,
    listener: Mutex<Option<Listener>>,
    gateway: Mutex<Option<Gateway>>,
    admin: Mutex<Option<super::admin::Endpoint>>,
    running: Mutex<Option<Running>>,
    closed: AtomicBool,
    started: AtomicBool,
    retry_requested: AtomicBool,
    wake: Notify,
    generation: AtomicU64,
    worker: Mutex<Option<tauri::async_runtime::JoinHandle<()>>>,
    diagnostics: Arc<Diagnostics>,
    grace: Duration,
    retry: Duration,
    start_limit: Duration,
}

/// The supervision of one host's launcher.
pub struct Supervisor {
    shared: Arc<Shared>,
    observe: Observe,
    changed: Changed,
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
    pub fn new(
        observe: Observe,
        changed: Changed,
        launch: Option<Launch>,
        diagnostics: Arc<Diagnostics>,
    ) -> Self {
        Self::with_timing(
            observe,
            changed,
            launch,
            diagnostics,
            runner::STOP_GRACE,
            RETRY,
        )
    }

    pub fn with_timing(
        observe: Observe,
        changed: Changed,
        launch: Option<Launch>,
        diagnostics: Arc<Diagnostics>,
        grace: Duration,
        retry: Duration,
    ) -> Self {
        let status = if launch.is_some() {
            Status {
                state: State::Stopped,
                lane: None,
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
                admin: Mutex::new(None),
                running: Mutex::new(None),
                closed: AtomicBool::new(false),
                started: AtomicBool::new(false),
                retry_requested: AtomicBool::new(false),
                wake: Notify::new(),
                generation: AtomicU64::new(0),
                worker: Mutex::new(None),
                diagnostics,
                grace,
                retry,
                start_limit: START_LIMIT,
            }),
            observe,
            changed,
            launch,
        }
    }

    /// A fixture launcher's speed is not under test; it gets `limit` to report
    /// its service instead of the product's start limit.
    #[cfg(test)]
    fn starting_within(mut self, limit: Duration) -> Self {
        Arc::get_mut(&mut self.shared)
            .expect("timing is set before supervision begins")
            .start_limit = limit;
        self
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

    pub fn restart_agent(&self) -> Result<()> {
        if lock(&self.shared.admin).is_some() {
            self.person_request(serde_json::json!({"action":"status"}))?;
            let reply = self.administer(serde_json::json!({"action":"start"}), None)?;
            match start_reply(&reply)? {
                StartReply::Starting => {}
                // The service is busy with other tree work, such as a provider
                // sign-in, and keeps the agent as it is: nothing it serves changed.
                StartReply::Busy => {
                    return Err(ApplicationError::new(
                        ErrorCode::SessionUnavailable,
                        Operation::Cli,
                    )
                    .with_reason("agent_service_busy"));
                }
                StartReply::Refused(code) => publish(&self.shared, State::Refused { code }),
            }
        } else {
            self.retry();
        }
        Ok(())
    }

    /// The gateway of the launcher that reported ready, while it serves.
    pub fn gateway(&self) -> Option<Gateway> {
        lock(&self.shared.gateway).clone()
    }

    pub fn administer(
        &self,
        request: serde_json::Value,
        secret: Option<Zeroizing<Vec<u8>>>,
    ) -> Result<serde_json::Value> {
        self.begin();
        let endpoint = lock(&self.shared.admin).clone().ok_or_else(|| {
            ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
                .with_reason("agent_admin_unavailable")
        })?;
        endpoint.exchange(request, secret)
    }

    pub fn person_request(&self, request: serde_json::Value) -> Result<serde_json::Value> {
        self.begin();
        let person = lock(&self.shared.running)
            .as_ref()
            .and_then(|running| running.person.clone())
            .ok_or_else(|| {
                ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
                    .with_reason("agent_service_unavailable")
            })?;
        lock(&person).exchange(request)
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
        let changed = self.changed.clone();
        let worker = tauri::async_runtime::spawn(supervise(shared, observe, changed, launch));
        *lock(&self.shared.worker) = Some(worker);
    }

    /// Stops the launcher and supervision for good, as the window closes.
    pub async fn close(&self) -> Result<()> {
        self.shared.closed.store(true, Ordering::Release);
        self.shared.wake.notify_one();
        let worker = lock(&self.shared.worker).take();
        let stopped = stop_running(&self.shared, None, AgentStopCause::WindowClosing).await;
        if let Some(worker) = worker
            && worker.await.is_err()
        {
            self.shared
                .diagnostics
                .contained_panic(Some(HostStage::Agent), Operation::Cli);
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
        let mut admin = lock(&shared.admin);
        if admin
            .as_ref()
            .is_some_and(|endpoint| endpoint.generation == running.generation)
        {
            *admin = None;
        }
    }
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
    let gateway_bearer = Arc::new(mint_bearer()?);
    let launch = launch.clone();
    let prepare_bearer = bearer.clone();
    let prepare_profile = profile.clone();
    let preparation_started = Instant::now();
    // Include held-person acquisition (which can wait on another consumer)
    // in the visible startup interval, not just the child launch afterwards.
    let generation = shared.generation.fetch_add(1, Ordering::AcqRel) + 1;
    shared
        .diagnostics
        .service(None, ServiceFact::AgentStarting { generation });
    let (Prepared { command, person }, person_failure) =
        tauri::async_runtime::spawn_blocking(move || {
            let prepared = launch(&prepare_bearer, &prepare_profile)?;
            let failure = prepared
                .person
                .as_ref()
                .map(|person| lock(person).failures());
            Ok::<_, ApplicationError>((prepared, failure))
        })
        .await
        .map_err(|_| ApplicationError::new(ErrorCode::Panic, Operation::Cli))??;
    let prepared_at = Instant::now();
    let sender = signals.clone();
    let diagnostics = shared.diagnostics.clone();
    let secret = bearer.clone();
    let gateway_secret = gateway_bearer.clone();
    let supervised = tauri::async_runtime::spawn_blocking(move || {
        runner::start_child(
            command,
            Some((secret.as_str(), gateway_secret.as_str())),
            move |signal| {
                let _ = sender.send((generation, signal));
            },
            diagnostics,
        )
    })
    .await
    .map_err(|_| ApplicationError::new(ErrorCode::Panic, Operation::Cli))??;
    shared.diagnostics.service(
        None,
        ServiceFact::AgentStartupTiming {
            generation,
            prepare_ms: prepared_at
                .duration_since(preparation_started)
                .as_millis()
                .try_into()
                .unwrap_or(u64::MAX),
            spawn_ms: prepared_at
                .elapsed()
                .as_millis()
                .try_into()
                .unwrap_or(u64::MAX),
        },
    );
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
                gateway_bearer,
                person,
                person_failure,
                started: Instant::now(),
            });
            None
        }
    };
    if let Some(supervised) = refused {
        let grace = shared.grace;
        match tauri::async_runtime::spawn_blocking(move || supervised.stop(grace)).await {
            Ok(Ok(_)) => {}
            Ok(Err(error)) => shared.diagnostics.host_failure(HostStage::Agent, error),
            Err(_) => shared
                .diagnostics
                .contained_panic(Some(HostStage::Agent), Operation::Cli),
        }
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

async fn supervise(shared: Arc<Shared>, observe: Observe, changed: Changed, launch: Launch) {
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
        // Created before observing, so an observation arriving meanwhile still wakes this round.
        let changed = changed();
        tokio::pin!(changed);
        let observation = observe();
        tokio::pin!(observation);
        let failed_person = person_failed(&shared);
        tokio::pin!(failed_person);
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
                (generation, error) = &mut failed_person => {
                    if retire_failed_person(&shared, generation, error).await {
                        retries.failed(&shared);
                    }
                    continue 'supervision;
                }
                observed = &mut observation => break observed,
            }
        };
        let allowed = allowed(&observed);
        if shared.closed.load(Ordering::Acquire) {
            break;
        }
        let starting_expired = lock(&shared.running).as_ref().is_some_and(|running| {
            lock(&shared.admin).is_none() && running.started.elapsed() >= shared.start_limit
        });
        if starting_expired {
            publish(
                &shared,
                State::Refused {
                    code: Refusal::ServiceFailed,
                },
            );
            let _ = stop_running(&shared, None, AgentStopCause::ProtocolRefused).await;
            retries.failed(&shared);
        }
        let current = lock(&shared.running).as_ref().map(|r| r.profile.clone());
        match (&current, &allowed) {
            (Some(profile), Allowed::Serve(wanted)) if profile == wanted => {}
            (Some(_), _) => {
                let cause = match &allowed {
                    Allowed::Serve(_) => AgentStopCause::ProfileChanged,
                    Allowed::Pending => AgentStopCause::SignInUnavailable,
                    Allowed::Refuse(Refusal::SignedOut) => AgentStopCause::SignInUnavailable,
                    Allowed::Refuse(_) => AgentStopCause::RuntimeUnavailable,
                };
                let _ = stop_running(&shared, None, cause).await;
                match &allowed {
                    Allowed::Pending => publish(&shared, State::Stopped),
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
            (None, Allowed::Pending) => publish(&shared, State::Stopped),
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
        // Nothing is read on a timer: the next round starts at a new sign-in
        // observation, an explicit wake, a launcher failure, or the one
        // deadline this round set (a retry, or a start that must have finished).
        let due = next_due(&shared, &retries);
        // Starting this round may have installed a different held session.
        let failed_person = person_failed(&shared);
        tokio::pin!(failed_person);
        let deadline = async move {
            match due {
                Some(at) => tokio::time::sleep_until(at.into()).await,
                None => std::future::pending::<()>().await,
            }
        };
        tokio::pin!(deadline);
        loop {
            tokio::select! {
                _ = &mut wake => break,
                () = &mut changed => break,
                () = &mut deadline => break,
                (generation, error) = &mut failed_person => {
                    if retire_failed_person(&shared, generation, error).await {
                        retries.failed(&shared);
                    }
                    break;
                }
                Some((generation, signal)) = received.recv() => {
                    if handle(&shared, generation, signal).await {
                        retries.failed(&shared);
                        break;
                    }
                }
            }
        }
    }
    let _ = stop_running(&shared, None, AgentStopCause::WindowClosing).await;
}

/// A failed shared profile read must retire the service it admitted promptly,
/// without waiting for the busy bridge child or another sign-in observation.
async fn person_failed(shared: &Shared) -> (u64, ApplicationError) {
    let held = lock(&shared.running).as_ref().and_then(|running| {
        running
            .person_failure
            .clone()
            .map(|failure| (running.generation, failure))
    });
    let Some((generation, mut failure)) = held else {
        return std::future::pending().await;
    };
    loop {
        if let Some(error) = failure.borrow_and_update().clone() {
            return (generation, error);
        }
        if failure.changed().await.is_err() {
            return std::future::pending().await;
        }
    }
}

async fn retire_failed_person(
    shared: &Arc<Shared>,
    generation: u64,
    error: ApplicationError,
) -> bool {
    if lock(&shared.running)
        .as_ref()
        .map(|running| running.generation)
        != Some(generation)
    {
        return false;
    }
    let retired = error.reason.as_deref() == Some("person_session_retired");
    if !retired {
        shared.diagnostics.host_failure(HostStage::Agent, error);
    }
    publish(
        shared,
        State::Refused {
            code: if retired {
                Refusal::SignedOut
            } else {
                Refusal::ServiceFailed
            },
        },
    );
    let cause = if retired {
        AgentStopCause::SignInUnavailable
    } else {
        AgentStopCause::ProtocolRefused
    };
    let _ = stop_running(shared, Some(generation), cause).await;
    // A revoked session needs a fresh authority observation, not a service
    // failure retry. Transport faults retain the bounded retry policy.
    !retired
}

/// The one moment this round must look again without a new observation: when
/// a refused start may be retried, or when a starting launcher has had its time.
fn next_due(shared: &Shared, retries: &RetryBudget) -> Option<Instant> {
    let retry = retries.after.filter(|at| *at > Instant::now());
    let starting = lock(&shared.running).as_ref().and_then(|running| {
        lock(&shared.admin)
            .is_none()
            .then_some(running.started + shared.start_limit)
    });
    retry.into_iter().chain(starting).min()
}

/// Acts on one launcher signal. True when the launcher ended unasked, which
/// delays the next start.
async fn handle(shared: &Arc<Shared>, generation: u64, signal: Signal) -> bool {
    let (bearer, gateway_bearer, process) = {
        let running = lock(&shared.running);
        match running.as_ref() {
            Some(running) if running.generation == generation => (
                running.bearer.clone(),
                running.gateway_bearer.clone(),
                running.supervised.process_ref(),
            ),
            _ => return false,
        }
    };
    match signal {
        Signal::Event(Event::ServiceReady {
            admin_port,
            runtime_boot_id,
            connection_id,
            profile_id,
            service_id,
        }) => {
            if lock(&shared.admin).is_some() {
                let _ =
                    stop_running(shared, Some(generation), AgentStopCause::ProtocolRefused).await;
                return true;
            }
            let person = lock(&shared.running)
                .as_ref()
                .and_then(|running| running.person.clone());
            let Some(person) = person else {
                let _ =
                    stop_running(shared, Some(generation), AgentStopCause::ProtocolRefused).await;
                return true;
            };
            let admitted = tauri::async_runtime::spawn_blocking(move || {
                let mut person = lock(&person);
                if person.identity["runtime_boot_id"] != runtime_boot_id || person.identity["profile_id"] != profile_id {
                    return Err(ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
                        .with_reason("service_ready_identity_mismatch"));
                }
                let reply = person.exchange(serde_json::json!({"action":"service_admission", "recipient_connection_id":connection_id, "service_id":service_id}))?;
                if reply["kind"] == "service_connected" {
                    Ok(())
                } else {
                    Err(ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
                        .with_reason("service_admission_reply_unexpected"))
                }
            }).await.unwrap_or_else(|_| {
                shared.diagnostics.contained_panic(Some(HostStage::Agent), Operation::Cli);
                Err(ApplicationError::new(ErrorCode::Panic, Operation::Cli))
            });
            let admitted = match admitted {
                Ok(()) => true,
                Err(error) => {
                    shared.diagnostics.host_failure(HostStage::Agent, error);
                    false
                }
            };
            if !admitted {
                let _ =
                    stop_running(shared, Some(generation), AgentStopCause::ProtocolRefused).await;
                publish(
                    shared,
                    State::Refused {
                        code: Refusal::ServiceFailed,
                    },
                );
                return true;
            }
            *lock(&shared.admin) = Some(super::admin::Endpoint {
                port: admin_port,
                bearer,
                generation,
                gate: Default::default(),
            });
            false
        }
        Signal::Event(Event::Ready {
            gateway_port,
            agent_version,
            workspace_root,
        }) => {
            if !lock(&shared.admin)
                .as_ref()
                .is_some_and(|endpoint| endpoint.generation == generation)
            {
                let _ =
                    stop_running(shared, Some(generation), AgentStopCause::ProtocolRefused).await;
                return true;
            }
            *lock(&shared.gateway) = Some(Gateway {
                port: gateway_port,
                bearer: gateway_bearer,
                workspace_root,
                generation,
                instance: Arc::new(()),
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
        // A start the service declined because other tree work, such as a
        // provider sign-in, holds it: the agent it serves, if any, is unchanged.
        Signal::Event(Event::Refused { code }) if code == "busy" => false,
        Signal::Event(Event::Refused { code }) => {
            publish(
                shared,
                State::Refused {
                    code: service_refusal(&code),
                },
            );
            *lock(&shared.gateway) = None;
            false
        }
        Signal::Event(Event::Stopped { reason }) => {
            *lock(&shared.gateway) = None;
            if reason == "agent_retired" {
                // The hosted controller was retired for an operation such as
                // provider sign-in. The service process and its authenticated
                // admin endpoint remain owned, so this is a neutral stopped
                // state rather than a service refusal.
                publish(shared, State::Stopped);
            } else {
                publish(
                    shared,
                    State::Refused {
                        code: service_refusal(&reason),
                    },
                );
            }
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
                State::Starting | State::Ready { .. } | State::Stopped
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

    #[test]
    fn replacing_a_gateway_in_the_same_launcher_invalidates_its_admission() {
        let first = Gateway {
            port: 12345,
            bearer: Arc::new(Zeroizing::new("test-bearer".to_owned())),
            workspace_root: "workspace".to_owned(),
            generation: 1,
            instance: Arc::new(()),
        };
        assert!(first.same_instance(&first.clone()));
        let replacement = Gateway {
            instance: Arc::new(()),
            ..first.clone()
        };
        assert!(!first.same_instance(&replacement));
    }

    #[test]
    fn native_drops_keep_paths_private_and_claim_them_once_for_the_observing_gateway() {
        use crate::agent::dropping::Drops;
        use tauri::{DragDropEvent, PhysicalPosition, ipc::InvokeResponseBody};
        let gateway = Gateway {
            port: 12345,
            bearer: Arc::new(Zeroizing::new("test-bearer".to_owned())),
            workspace_root: "workspace".to_owned(),
            generation: 1,
            instance: Arc::new(()),
        };
        let replacement = Gateway {
            instance: Arc::new(()),
            ..gateway.clone()
        };
        let signals = Arc::new(Mutex::new(Vec::<serde_json::Value>::new()));
        let received = signals.clone();
        let channel = Channel::new(move |body| {
            let InvokeResponseBody::Json(body) = body else {
                panic!("Expected a drop signal");
            };
            lock(&received).push(serde_json::from_str(&body).unwrap());
            Ok(())
        });
        let drops = Drops::default();
        let first = drops.observe(channel.clone(), gateway.clone());
        let paths = vec![std::path::PathBuf::from("private/invoice.pdf")];
        let position = PhysicalPosition::new(240.0, 360.0);
        drops.event(
            &DragDropEvent::Enter {
                paths: paths.clone(),
                position,
            },
            2.0,
        );
        drops.event(
            &DragDropEvent::Drop {
                paths: paths.clone(),
                position,
            },
            2.0,
        );
        let held = lock(&signals);
        assert_eq!(held[0]["x"], 120.0);
        assert_eq!(held[0]["y"], 180.0);
        assert_eq!(held[0]["count"], 1);
        let id = held[1]["drop_id"].as_str().unwrap().to_owned();
        assert!(!serde_json::to_string(&*held).unwrap().contains("private"));
        assert!(
            !serde_json::to_string(&*held)
                .unwrap()
                .contains("invoice.pdf")
        );
        drop(held);
        assert!(drops.take(&id, &replacement).is_err());
        assert!(drops.take("invented", &gateway).is_err());
        assert_eq!(drops.take(&id, &gateway).unwrap(), paths);
        assert!(drops.take(&id, &gateway).is_err());
        let received = signals.clone();
        let second = drops.observe(
            Channel::new(move |body| {
                let InvokeResponseBody::Json(body) = body else {
                    panic!("Expected a drop signal");
                };
                lock(&received).push(serde_json::from_str(&body).unwrap());
                Ok(())
            }),
            gateway.clone(),
        );
        drops.clear(Some(first));
        // A retired observer cannot clear its replacement.
        assert_ne!(first, second);
        drops.event(
            &DragDropEvent::Drop {
                paths: paths.clone(),
                position,
            },
            2.0,
        );
        let id = lock(&signals)[2]["drop_id"].as_str().unwrap().to_owned();
        assert_eq!(drops.take(&id, &gateway).unwrap(), paths);
        drops.event(&DragDropEvent::Drop { paths, position }, 2.0);
        let id = lock(&signals)[3]["drop_id"].as_str().unwrap().to_owned();
        drops.clear(Some(second));
        assert!(drops.take(&id, &gateway).is_err());
    }

    /// Stands in for new sign-in observations: the test's source is read again every `period`.
    fn every(period: Duration) -> Changed {
        Arc::new(move || Box::pin(tokio::time::sleep(period)))
    }

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
            (
                Err(ApplicationError::new(
                    ErrorCode::SessionUnavailable,
                    Operation::Cli,
                )),
                Refusal::RuntimeUnavailable,
            ),
        ] {
            assert_eq!(allowed(&status), Allowed::Refuse(refusal));
        }
        assert_eq!(
            allowed(&Err(ApplicationError::new(
                ErrorCode::SessionUnavailable,
                Operation::Cli
            )
            .with_reason("sign_in_mutation_in_progress"))),
            Allowed::Pending
        );
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

    #[test]
    fn a_busy_start_is_not_a_refusal_of_the_agent() {
        use serde_json::json;
        assert_eq!(
            start_reply(&json!({"kind": "starting"})).unwrap(),
            StartReply::Starting
        );
        assert_eq!(
            start_reply(&json!({"kind": "refused", "code": "busy"})).unwrap(),
            StartReply::Busy
        );
        assert_eq!(
            start_reply(&json!({"kind": "refused", "code": "signed_out"})).unwrap(),
            StartReply::Refused(Refusal::SignedOut)
        );
        assert_eq!(
            start_reply(&json!({"kind": "refused"})).unwrap(),
            StartReply::Refused(Refusal::ServiceFailed)
        );
        for reply in [json!({}), json!({"kind": "ready"}), json!({"code": "busy"})] {
            let error = start_reply(&reply).unwrap_err();
            assert_eq!(
                error.reason.as_deref(),
                Some("agent_start_reply_unexpected")
            );
        }
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
            every(Duration::from_millis(1)),
            Some(launch),
            diagnostics.clone(),
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
            every(Duration::from_secs(60)),
            Some(launch),
            Arc::new(Diagnostics::default()),
            Duration::from_millis(1),
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
        let supervisor = Supervisor::new(
            observe,
            every(Duration::from_millis(1)),
            Some(launch),
            Arc::new(Diagnostics::default()),
        );
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
        use crate::shell::sign_in::process::tests::{Gate, HANG_GUARD};
        use tauri::ipc::InvokeResponseBody;
        use tokio::sync::watch;

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
                    person: None,
                    command: powershell(
                        "$null = [Console]::In.ReadLine(); Start-Sleep -Milliseconds 500; [Console]::Out.WriteLine('{\"event\":\"agent_refused\",\"code\":\"agent_service_incompatible\"}'); exit 3",
                    ),
                })
            });
            let supervisor = Supervisor::with_timing(
                observe,
                every(Duration::from_millis(5)),
                Some(launch),
                Arc::new(Diagnostics::default()),
                Duration::from_secs(5),
                Duration::from_secs(60),
            );
            supervisor.status();
            tokio::time::timeout(Duration::from_secs(20), async {
                loop {
                    if supervisor.status().state
                        == (State::Refused {
                            code: Refusal::ServiceIncompatible,
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
            holders: Arc<Mutex<Vec<HolderFixture>>>,
            /// Moves on at each published status and each recorded diagnostic.
            recorded: Arc<watch::Sender<u64>>,
            /// Holds a retiring launcher at each step the test inspects.
            gate: Option<Gate>,
        }

        impl Rig {
            /// Lets the launcher go on once it has reached `point`.
            fn release(&mut self, point: &str) {
                let gate = self.gate.as_mut().expect("this launcher waits at a gate");
                tokio::task::block_in_place(|| {
                    gate.reached(point);
                    gate.go();
                });
            }
        }

        struct HolderFixture {
            pid: u32,
            identity: serde_json::Value,
        }

        /// Controlled holder-protocol evidence over real child pipes, not an
        /// installed runtime or a proof of native person authentication.
        fn held_protocol_fixture(
            profile: &str,
            ignore_end: bool,
            retire_at_gate: Option<&str>,
            service_at_gate: Option<&str>,
        ) -> (Prepared, HolderFixture) {
            let profile_id = match profile {
                "A" => "11111111-1111-4111-8111-111111111111",
                "B" => "22222222-2222-4222-8222-222222222222",
                _ => panic!("unexpected fixture profile"),
            };
            let identity = serde_json::json!({
                "kind": "session_held",
                "profile_id": profile_id,
                "session_id": super::super::super::person::request_id().unwrap(),
                "runtime_boot_id": super::super::super::person::request_id().unwrap(),
                "connection_id": super::super::super::person::request_id().unwrap(),
            });
            let recipient = super::super::super::person::request_id().unwrap();
            let reply = serde_json::json!({
                "kind": "service_connected",
                "request_id": super::super::super::person::request_id().unwrap(),
                "runtime_boot_id": identity["runtime_boot_id"],
                "connection_id": identity["connection_id"],
                "profile_id": profile_id,
                "service_id": "cadrumo-agent-service",
                "lease": {
                    "lease_id": super::super::super::person::request_id().unwrap(),
                    "session_id": super::super::super::person::request_id().unwrap(),
                    "parent_session_id": identity["session_id"],
                    "profile_id": profile_id,
                    "runtime_boot_id": identity["runtime_boot_id"],
                    "connection_id": recipient,
                    "service_id": "cadrumo-agent-service",
                    "descriptor_digest": "a".repeat(64),
                },
            });
            let holder_script = format!(
                "& {{ [Console]::Out.WriteLine('{identity}'); [Console]::Out.Flush(); \
                 while (($line = [Console]::In.ReadLine()) -ne $null) {{ \
                     $request = $line | ConvertFrom-Json; \
                     if ($request.action -ne 'service_admission' -or \
                         $request.recipient_connection_id -ne '{recipient}' -or \
                         $request.service_id -ne 'cadrumo-agent-service' -or \
                         $request.psobject.Properties.Name.Count -ne 4) {{ exit 7 }}; \
                     $reply = '{reply}' | ConvertFrom-Json; \
                     $reply.request_id = $request.request_id; \
                     [Console]::Out.WriteLine(($reply | ConvertTo-Json -Compress -Depth 8)); \
                     [Console]::Out.Flush(); \
                 }} }}"
            );
            let person = crate::agent::person::Person::hold_answering_within(
                powershell(&holder_script),
                profile_id,
                HANG_GUARD,
            )
            .unwrap();
            assert_eq!(person.identity, identity);
            let witness = HolderFixture {
                pid: person.child_id(),
                identity,
            };
            let ready = serde_json::json!({
                "event": "service_ready",
                "protocol": 1,
                "admin_port": 4001,
                "runtime_boot_id": witness.identity["runtime_boot_id"],
                "connection_id": recipient,
                "profile_id": profile_id,
                "service_id": "cadrumo-agent-service",
            });
            // The existing launcher first reads and checks both independently
            // minted startup credentials. Add only the service readiness frame
            // before its existing agent-ready frame and child-tree behavior.
            let mut script = launcher_script(ignore_end);
            if let Some(gate) = retire_at_gate {
                let normal_exit = r#"$null = [Console]::In.ReadToEnd(); [Console]::Out.WriteLine('{"event":"agent_stopped","reason":"agent_host_closed"}'); exit 0"#;
                assert!(script.contains(normal_exit));
                // Each step waits for the test, never for an amount of time.
                script = script.replace(
                    normal_exit,
                    &format!(
                        r#"{gate}Wait-Gate 'ready'; [Console]::Out.WriteLine('{{"event":"agent_stopped","reason":"agent_retired"}}'); [Console]::Out.Flush(); Wait-Gate 'retired'; exit 3"#
                    ),
                );
            }
            let marker = "$grandchild = ";
            assert_eq!(script.matches(marker).count(), 1);
            let service_gate = service_at_gate
                .map(|gate| format!("{gate}Wait-Gate 'service'; "))
                .unwrap_or_default();
            let script = script.replacen(
                marker,
                &format!("{service_gate}[Console]::Out.WriteLine('{ready}'); [Console]::Out.Flush(); {marker}"),
                1,
            );
            (
                Prepared {
                    person: Some(Arc::new(Mutex::new(person))),
                    command: powershell(&script),
                },
                witness,
            )
        }

        fn rig(ignore_end: bool, retire_after_ready: bool) -> Rig {
            rig_with_service_gate(ignore_end, retire_after_ready, false)
        }

        fn rig_with_service_gate(
            ignore_end: bool,
            retire_after_ready: bool,
            wait_for_service: bool,
        ) -> Rig {
            let observation = Arc::new(Mutex::new(observed(true, true, Some("A"))));
            let source = observation.clone();
            let observe: Observe = Arc::new(move || {
                let current = lock(&source).clone();
                Box::pin(async move { current })
            });
            let holders = Arc::new(Mutex::new(Vec::new()));
            let witnesses = holders.clone();
            let gate = (retire_after_ready || wait_for_service).then(Gate::new);
            let gate_script = gate
                .as_ref()
                .filter(|_| retire_after_ready)
                .map(Gate::script);
            let service_gate = gate.as_ref().filter(|_| wait_for_service).map(Gate::script);
            let launch: Launch = Arc::new(move |_, profile| {
                let (prepared, witness) = held_protocol_fixture(
                    profile,
                    ignore_end,
                    gate_script.as_deref(),
                    service_gate.as_deref(),
                );
                lock(&witnesses).push(witness);
                Ok(prepared)
            });
            let recorded = Arc::new(watch::Sender::new(0u64));
            let diagnostics = Arc::new(Diagnostics::default());
            let moved = recorded.clone();
            diagnostics.on_recorded(Arc::new(move || moved.send_modify(|count| *count += 1)));
            let supervisor = Supervisor::with_timing(
                observe,
                every(Duration::from_millis(100)),
                Some(launch),
                diagnostics.clone(),
                Duration::from_millis(if ignore_end { 500 } else { 10_000 }),
                Duration::from_secs(60),
            );
            let supervisor = if wait_for_service {
                supervisor
            } else {
                supervisor.starting_within(HANG_GUARD)
            };
            let statuses = Arc::new(Mutex::new(Vec::new()));
            let sink = statuses.clone();
            let moved = recorded.clone();
            supervisor.subscribe(Channel::new(move |body| {
                let InvokeResponseBody::Json(body) = body else {
                    panic!("expected a JSON status")
                };
                sink.lock()
                    .unwrap()
                    .push(serde_json::from_str(&body).unwrap());
                moved.send_modify(|count| *count += 1);
                Ok(())
            }));
            Rig {
                supervisor,
                observation,
                statuses,
                diagnostics,
                holders,
                recorded,
                gate,
            }
        }

        #[tokio::test(flavor = "multi_thread")]
        async fn cold_service_registration_can_finish_after_the_runtime_exchange_window() {
            let mut rig = rig_with_service_gate(false, false, true);
            service_waiting(&mut rig).await;
            // Account for a ten-second handshake and a 120-second registration
            // without spending that time asleep in a process fixture.
            lock(&rig.supervisor.shared.running)
                .as_mut()
                .unwrap()
                .started = Instant::now() - Duration::from_secs(131);
            let due = next_due(&rig.supervisor.shared, &RetryBudget::default()).unwrap();
            assert!(due > Instant::now(), "a valid registration still has time");
            rig.gate.as_mut().unwrap().go();
            until_seen(&rig, "cold service ready", || {
                matches!(rig.supervisor.status().state, State::Ready { .. }).then_some(())
            })
            .await;
            assert_eq!(lock(&rig.holders).len(), 1, "no launch was retried");
            rig.supervisor.close().await.unwrap();
        }

        #[tokio::test(flavor = "multi_thread")]
        async fn a_service_that_never_registers_still_exhausts_its_start_deadline() {
            let mut rig = rig_with_service_gate(false, false, true);
            service_waiting(&mut rig).await;
            lock(&rig.supervisor.shared.running)
                .as_mut()
                .unwrap()
                .started = Instant::now() - Duration::from_secs(181);
            rig.supervisor.shared.wake.notify_one();
            until_seen(&rig, "unregistered service stopped", || {
                (matches!(
                    rig.supervisor.status().state,
                    State::Refused {
                        code: Refusal::ServiceFailed
                    }
                ) && lock(&rig.supervisor.shared.running).is_none())
                .then_some(())
            })
            .await;
            assert!(rig.supervisor.gateway().is_none());
            assert!(lock(&rig.supervisor.shared.admin).is_none());
            rig.supervisor.close().await.unwrap();
        }

        async fn service_waiting(rig: &mut Rig) {
            tokio::task::block_in_place(|| rig.gate.as_mut().unwrap().reached("service"));
            // The child can reach its gate before start_child returns to the
            // supervisor that records ownership of it.
            tokio::time::timeout(HANG_GUARD, async {
                while lock(&rig.supervisor.shared.running).is_none() {
                    tokio::task::yield_now().await;
                }
            })
            .await
            .unwrap();
        }

        /// What `seen` finds once a published status or recorded diagnostic
        /// makes it true. The guard bounds only a supervisor that hangs.
        async fn until_seen<T>(rig: &Rig, what: &str, mut seen: impl FnMut() -> Option<T>) -> T {
            let mut recorded = rig.recorded.subscribe();
            tokio::time::timeout(HANG_GUARD, async {
                loop {
                    if let Some(found) = seen() {
                        return found;
                    }
                    recorded.changed().await.unwrap();
                }
            })
            .await
            .unwrap_or_else(|_| panic!("{what}: {:?}", rig.statuses.lock().unwrap()))
        }

        /// The first status in `state` published at or after index `from`.
        async fn until(rig: &Rig, from: usize, state: &str) -> serde_json::Value {
            until_seen(rig, &format!("never {state}"), || {
                let statuses = rig.statuses.lock().unwrap();
                statuses[from.min(statuses.len())..]
                    .iter()
                    .find(|status| status["state"] == state)
                    .cloned()
            })
            .await
        }

        /// The launcher, its reported grandchild, and its real held-protocol child.
        async fn serving(rig: &Rig, from: usize) -> (u32, u32, u32) {
            let ready = until(rig, from, "ready").await;
            let (grandchild, length) = reported(ready["agent_version"].as_str().unwrap());
            assert_eq!(length, "64", "the launcher read the minted bearer");
            let gateway = rig.supervisor.gateway().unwrap();
            assert_eq!(gateway.port, 4000);
            let admin_bearer = {
                let admin = lock(&rig.supervisor.shared.admin);
                let endpoint = admin
                    .as_ref()
                    .expect("service admitted before agent readiness");
                assert_eq!(endpoint.port, 4001);
                assert_eq!(endpoint.generation, gateway.generation);
                assert_eq!(endpoint.bearer.len(), 64);
                assert_ne!(endpoint.bearer.as_str(), gateway.bearer.as_str());
                endpoint.bearer.clone()
            };
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
            assert!(
                !serde_json::to_string(&snapshot.events)
                    .unwrap()
                    .contains(admin_bearer.as_str())
            );
            assert_eq!(gateway.workspace_root, r"C:\lane\ws");
            assert_eq!(gateway.bearer.len(), 64);
            let (launcher, person) = {
                let running = lock(&rig.supervisor.shared.running);
                let running = running.as_ref().unwrap();
                (running.supervised.id(), running.person.clone().unwrap())
            };
            let person = lock(&person);
            let holders = lock(&rig.holders);
            let witness = holders
                .iter()
                .find(|holder| holder.pid == person.child_id())
                .unwrap();
            assert_eq!(person.identity, witness.identity);
            assert!(
                alive(witness.pid),
                "the original held-protocol child is retained"
            );
            (launcher, grandchild, witness.pid)
        }

        /// The running processes among `pids`, each as its pid and start time:
        /// once a process ends, another process can be given its pid.
        fn instances(pids: (u32, u32, u32)) -> Vec<String> {
            let output = powershell(&format!(
                "foreach ($id in {},{},{}) {{ \
                     $p = Get-Process -Id $id -ErrorAction SilentlyContinue; \
                     if ($p) {{ [Console]::Out.WriteLine(\"$id@$($p.StartTime.Ticks)\") }} }}; \
                 exit 0",
                pids.0, pids.1, pids.2
            ))
            .output()
            .unwrap();
            assert!(output.status.success());
            String::from_utf8(output.stdout)
                .unwrap()
                .lines()
                .map(str::to_owned)
                .collect()
        }

        /// Every one of the launcher's processes, while it serves.
        fn started(pids: (u32, u32, u32)) -> Vec<String> {
            let started = instances(pids);
            assert!(
                started.len() == 3 && started.iter().all(|process| !process.ends_with('@')),
                "every started process runs: {started:?}"
            );
            started
        }

        /// Once the supervisor has finished stopping them, none of the started
        /// processes remains: the job is empty and the holder reaped.
        fn gone(pids: (u32, u32, u32), started: &[String]) {
            let running = instances(pids);
            assert!(
                started.iter().all(|process| !running.contains(process)),
                "a started process survived: {running:?}"
            );
        }

        #[tokio::test(flavor = "multi_thread")]
        async fn a_shared_person_failure_retires_a_ready_service_and_allows_a_fresh_start() {
            let rig = rig(false, false);
            serving(&rig, 0).await;
            let original = rig.supervisor.gateway().unwrap();
            let person = lock(&rig.supervisor.shared.running)
                .as_ref()
                .unwrap()
                .person
                .clone()
                .unwrap();
            // This holder deliberately cannot answer a background language
            // request. Its launcher stays alive until the supervisor stops it.
            let error = tauri::async_runtime::spawn_blocking(move || {
                lock(&person)
                    .exchange(serde_json::json!({"action":"language_read"}))
                    .unwrap_err()
            })
            .await
            .unwrap();
            until(&rig, 0, "refused").await;
            until_seen(&rig, "failed service not retired", || {
                let stopped = lock(&rig.supervisor.shared.running).is_none();
                stopped.then_some(())
            })
            .await;
            assert!(rig.supervisor.gateway().is_none());
            assert!(
                rig.diagnostics
                    .snapshot(u64::MAX)
                    .events
                    .iter()
                    .any(|event| {
                        event
                            .failure
                            .as_ref()
                            .is_some_and(|failure| failure.reason == error.reason)
                    })
            );
            // A new start gets its own admitted session. It does not retry
            // the background request that lost the old one.
            let from = lock(&rig.statuses).len();
            rig.supervisor.retry();
            serving(&rig, from).await;
            assert!(!original.same_instance(&rig.supervisor.gateway().unwrap()));
            rig.supervisor.close().await.unwrap();
        }

        #[tokio::test(flavor = "multi_thread")]
        async fn a_retired_person_stops_the_service_without_a_service_failure_retry() {
            let rig = rig(false, false);
            serving(&rig, 0).await;
            let generation = rig.supervisor.gateway().unwrap().generation;
            // Keep the next authority observation retired as well.
            *rig.observation.lock().unwrap() = observed(false, true, Some("A"));
            let from = lock(&rig.statuses).len();
            let retry = retire_failed_person(
                &rig.supervisor.shared,
                generation,
                ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
                    .with_reason("person_session_retired"),
            )
            .await;
            assert!(!retry);
            let refused = until(&rig, from, "refused").await;
            assert_eq!(refused["code"], "agent_signed_out");
            assert!(rig.supervisor.gateway().is_none());
            assert!(lock(&rig.supervisor.shared.running).is_none());
            assert!(
                !rig.diagnostics
                    .snapshot(u64::MAX)
                    .events
                    .iter()
                    .any(|event| {
                        event.failure.is_some()
                            || matches!(
                                event.service,
                                Some(ServiceFact::AgentRetryScheduled { .. })
                            )
                    })
            );
            rig.supervisor.close().await.unwrap();
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
                (
                    "local sign-in mutation in progress",
                    Err(
                        ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
                            .with_reason("sign_in_mutation_in_progress"),
                    ),
                    "stopped",
                ),
                ("another profile", observed(true, true, Some("B")), "ready"),
            ] {
                let rig = rig(false, false);
                assert_eq!(
                    rig.supervisor.status().lane,
                    None,
                    "the service reports no invented lane"
                );
                let first = serving(&rig, 0).await;
                let processes = started(first);
                let changed = rig.statuses.lock().unwrap().len();
                *rig.observation.lock().unwrap() = observation;
                // Each outcome is published only after the launcher is stopped.
                let settled = if published == "ready" {
                    "stopped"
                } else {
                    published
                };
                let after = until(&rig, changed, settled).await;
                gone(first, &processes);
                assert!(
                    rig.supervisor.gateway().is_none_or(|g| g.generation > 1),
                    "{trigger}: the old gateway is forgotten"
                );
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
                } else if published == "refused" {
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
            let rig = rig(true, false);
            rig.supervisor.status();
            let pids = serving(&rig, 0).await;
            let processes = started(pids);
            let closing = Instant::now();
            rig.supervisor.close().await.unwrap();
            assert!(closing.elapsed() < Duration::from_secs(15));
            gone(pids, &processes);
            assert!(rig.supervisor.gateway().is_none());
            // Closed for good: nothing starts again.
            rig.supervisor.status();
            tokio::time::sleep(Duration::from_millis(400)).await;
            assert!(lock(&rig.supervisor.shared.running).is_none());
        }

        #[tokio::test(flavor = "multi_thread")]
        async fn controller_retirement_is_neutral_but_owned_service_exit_is_failed_and_retried() {
            let mut rig = rig(false, true);
            rig.supervisor.status();
            serving(&rig, 0).await;
            let generation = rig.supervisor.gateway().unwrap().generation;
            let after_ready = rig.statuses.lock().unwrap().len();
            rig.release("ready");

            // The launcher now waits at its gate: its service is still running.
            until(&rig, after_ready, "stopped").await;
            assert!(rig.supervisor.gateway().is_none());
            assert!(
                lock(&rig.supervisor.shared.admin)
                    .as_ref()
                    .is_some_and(|endpoint| endpoint.generation == generation)
            );
            assert!(
                !rig.diagnostics
                    .snapshot(u64::MAX)
                    .events
                    .iter()
                    .any(|event| matches!(event.service, Some(ServiceFact::AgentRefused { .. })))
            );

            let after_retirement = rig.statuses.lock().unwrap().len();
            rig.release("retired");
            let refused = until(&rig, after_retirement, "refused").await;
            assert_eq!(refused["code"], "agent_service_failed");
            // Refusal is published before process cleanup and retry scheduling.
            // Observe the completed transition before inspecting its facts.
            until_seen(
                &rig,
                "service exit must finish cleanup and schedule its retry",
                || {
                    rig.diagnostics
                        .snapshot(u64::MAX)
                        .events
                        .iter()
                        .any(|event| {
                            matches!(
                                event.service,
                                Some(ServiceFact::AgentRetryScheduled { delay_ms: 60_000 })
                            )
                        })
                        .then_some(())
                },
            )
            .await;
            assert!(lock(&rig.supervisor.shared.admin).is_none());

            let facts: Vec<_> = rig
                .diagnostics
                .snapshot(u64::MAX)
                .events
                .into_iter()
                .filter_map(|event| event.service)
                .collect();
            assert!(facts.iter().any(|fact| matches!(
                fact,
                ServiceFact::AgentRefused {
                    reason: Refusal::ServiceFailed
                }
            )));
            assert!(
                facts.iter().any(|fact| matches!(
                    fact,
                    ServiceFact::AgentRetryScheduled { delay_ms: 60_000 }
                ))
            );
            rig.supervisor.close().await.unwrap();
        }

        #[tokio::test(flavor = "multi_thread")]
        async fn a_retired_agent_is_stopped_until_its_replacement_reports_ready() {
            let rig = rig(false, false);
            rig.supervisor.status();
            serving(&rig, 0).await;
            let generation = rig.supervisor.gateway().unwrap().generation;
            let retired = rig.supervisor.gateway().unwrap();

            // The service retires the superseded tree first: nothing serves.
            assert!(
                !handle(
                    &rig.supervisor.shared,
                    generation,
                    Signal::Event(Event::Stopped {
                        reason: "agent_retired".into(),
                    }),
                )
                .await
            );
            assert_eq!(rig.supervisor.status().state, State::Stopped);
            assert!(rig.supervisor.gateway().is_none());

            // A start declined as busy changes nothing it serves.
            assert!(
                !handle(
                    &rig.supervisor.shared,
                    generation,
                    Signal::Event(Event::Refused {
                        code: "busy".into(),
                    }),
                )
                .await
            );
            assert_eq!(rig.supervisor.status().state, State::Stopped);

            // The replacement's ready line serves it, through a new gateway.
            assert!(
                !handle(
                    &rig.supervisor.shared,
                    generation,
                    Signal::Event(Event::Ready {
                        gateway_port: 4001,
                        agent_version: "replacement".into(),
                        workspace_root: r"C:\lane\workspace".into(),
                    }),
                )
                .await
            );
            assert_eq!(
                rig.supervisor.status().state,
                State::Ready {
                    agent_version: "replacement".into()
                }
            );
            let replacement = rig.supervisor.gateway().unwrap();
            assert_eq!(replacement.port, 4001);
            assert!(!replacement.same_instance(&retired));
            rig.supervisor.close().await.unwrap();
        }

        #[tokio::test(flavor = "multi_thread")]
        async fn a_busy_start_leaves_the_serving_agent_ready() {
            let rig = rig(false, false);
            rig.supervisor.status();
            serving(&rig, 0).await;
            let generation = rig.supervisor.gateway().unwrap().generation;
            let before = rig.supervisor.status().state;
            assert!(
                !handle(
                    &rig.supervisor.shared,
                    generation,
                    Signal::Event(Event::Refused {
                        code: "busy".into(),
                    }),
                )
                .await
            );
            assert_eq!(rig.supervisor.status().state, before);
            assert!(rig.supervisor.gateway().is_some());
            rig.supervisor.close().await.unwrap();
        }

        #[tokio::test(flavor = "multi_thread")]
        async fn stopped_reasons_other_than_controller_retirement_remain_refusals() {
            let rig = rig(false, false);
            rig.supervisor.status();
            serving(&rig, 0).await;
            let generation = rig.supervisor.gateway().unwrap().generation;

            assert!(
                !handle(
                    &rig.supervisor.shared,
                    generation,
                    Signal::Event(Event::Stopped {
                        reason: "agent_signed_out".into(),
                    }),
                )
                .await
            );
            assert_eq!(
                rig.supervisor.status().state,
                State::Refused {
                    code: Refusal::SignedOut
                }
            );
            assert!(rig.supervisor.gateway().is_none());
            assert!(
                lock(&rig.supervisor.shared.admin)
                    .as_ref()
                    .is_some_and(|endpoint| endpoint.generation == generation)
            );
            rig.supervisor.close().await.unwrap();
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
                    person: None,
                    command: powershell(
                        "$null = [Console]::In.ReadLine(); [Console]::Out.WriteLine('{\"event\":\"agent_refused\",\"code\":\"agent_service_incompatible\"}'); exit 3",
                    ),
                })
            });
            let supervisor = Supervisor::with_timing(
                observe,
                every(Duration::from_millis(100)),
                Some(launch),
                Arc::new(Diagnostics::default()),
                Duration::from_secs(5),
                Duration::from_secs(60),
            );
            supervisor.status();
            let deadline = Instant::now() + Duration::from_secs(30);
            while supervisor.status().state
                != (State::Refused {
                    code: Refusal::ServiceIncompatible,
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
