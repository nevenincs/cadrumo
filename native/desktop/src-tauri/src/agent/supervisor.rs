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

mod admission;
pub(super) mod protocol;
mod retry;
#[cfg(test)]
mod tests;

use self::admission::{AdmissionWork, admit_person, person_failed};
use self::protocol::{
    Allowed, Changed, Gateway, Launch, Observe, Prepared, StartReply, State, Status, allowed,
    service_refusal, start_reply,
};
use self::retry::{RETRY, RetryBudget};
use super::launcher::{Event, Startup};
use super::runner::{self, Signal, Supervised};
use cadrumo_application::diagnostics::service::AgentRefusal as Refusal;
use cadrumo_application::diagnostics::service::{AgentStopCause, ServiceFact};
use cadrumo_application::diagnostics::{Diagnostics, HostStage};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use std::fmt::Write as _;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tauri::ipc::Channel;
use tokio::sync::{Notify, mpsc};
use zeroize::Zeroizing;

/// Last resort for an owner that never reports readiness or terminal completion.
const STARTUP_TIMEOUT: Duration =
    Duration::from_secs(cadrumo_platform::DEFAULT_ORCHESTRATION_TIMEOUT_SECONDS);

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

struct Preparing {
    generation: u64,
    profile: String,
    started: Instant,
    cancelled: Arc<AtomicBool>,
}

struct Admitting {
    generation: u64,
    cancel: Arc<Notify>,
    cancelled: Arc<AtomicBool>,
    ready: Option<Event>,
}

enum Completion {
    Started(u64, Result<Running>),
    Admitted(u64, Result<super::admin::Endpoint>),
}

struct Listener {
    channel: Channel<Status>,
}

/// Called each time the agent becomes ready: for a profile's sign-in, another profile, or
/// a service start or restart.
pub type Ready = Arc<dyn Fn() + Send + Sync>;

struct Shared {
    status: Mutex<Status>,
    listener: Mutex<Option<Listener>>,
    ready: Mutex<Option<Ready>>,
    gateway: Mutex<Option<Gateway>>,
    admin: Mutex<Option<super::admin::Endpoint>>,
    running: Mutex<Option<Running>>,
    preparing: Mutex<Option<Preparing>>,
    admitting: Mutex<Option<Admitting>>,
    completions: mpsc::UnboundedSender<Completion>,
    completed: Mutex<Option<mpsc::UnboundedReceiver<Completion>>>,
    tasks: Mutex<Vec<tauri::async_runtime::JoinHandle<()>>>,
    closed: AtomicBool,
    started: AtomicBool,
    retry_requested: AtomicBool,
    wake: Notify,
    generation: AtomicU64,
    worker: Mutex<Option<tauri::async_runtime::JoinHandle<()>>>,
    diagnostics: Arc<Diagnostics>,
    grace: Duration,
    retry: Duration,
    startup_timeout: Duration,
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
    /// A host without a runnable service publishes its reason without observing
    /// sign-in or starting a supervision task.
    #[cfg(any(not(windows), test))]
    pub fn unavailable(
        observe: Observe,
        changed: Changed,
        reason: Refusal,
        diagnostics: Arc<Diagnostics>,
    ) -> Self {
        let supervisor = Self::new(observe, changed, None, diagnostics);
        *lock(&supervisor.shared.status) = Status {
            state: State::Refused { code: reason },
            lane: None,
        };
        supervisor
    }

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
        let (completions, completed) = mpsc::unbounded_channel();
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
                ready: Mutex::new(None),
                gateway: Mutex::new(None),
                admin: Mutex::new(None),
                running: Mutex::new(None),
                preparing: Mutex::new(None),
                admitting: Mutex::new(None),
                completions,
                completed: Mutex::new(Some(completed)),
                tasks: Mutex::new(Vec::new()),
                closed: AtomicBool::new(false),
                started: AtomicBool::new(false),
                retry_requested: AtomicBool::new(false),
                wake: Notify::new(),
                generation: AtomicU64::new(0),
                worker: Mutex::new(None),
                diagnostics,
                grace,
                retry,
                startup_timeout: STARTUP_TIMEOUT,
            }),
            observe,
            changed,
            launch,
        }
    }

    /// A fixture launcher's speed is not under test; it gets `limit` to report
    /// its service instead of the product's start limit.
    #[cfg(test)]
    fn timeout_within(mut self, limit: Duration) -> Self {
        Arc::get_mut(&mut self.shared)
            .expect("timing is set before supervision begins")
            .startup_timeout = limit;
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
        if self.launch.is_none() {
            return;
        }
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

    /// The admitted service identity for a sequence of related administration reads.
    pub fn admin_generation(&self) -> Result<u64> {
        self.begin();
        lock(&self.shared.admin)
            .as_ref()
            .map(|endpoint| endpoint.generation)
            .ok_or_else(|| {
                ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
                    .with_reason("agent_admin_unavailable")
            })
    }

    /// Exchange with the same admitted service, rejecting retirement or replacement.
    pub fn administer_generation(
        &self,
        request: serde_json::Value,
        generation: u64,
    ) -> Result<serde_json::Value> {
        let changed = || {
            ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
                .with_reason("agent_admin_generation_changed")
        };
        let endpoint = lock(&self.shared.admin)
            .as_ref()
            .filter(|endpoint| endpoint.generation == generation)
            .cloned()
            .ok_or_else(changed)?;
        let answer = endpoint.exchange(request, None)?;
        if lock(&self.shared.admin)
            .as_ref()
            .is_none_or(|endpoint| endpoint.generation != generation)
        {
            return Err(changed());
        }
        Ok(answer)
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

    /// Calls `ready` each later time the agent becomes ready, replacing any earlier one.
    pub fn on_ready(&self, ready: Ready) {
        *lock(&self.shared.ready) = Some(ready);
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
    if matches!(status.state, State::Ready { .. }) {
        let ready = lock(&shared.ready).clone();
        if let Some(ready) = ready {
            ready();
        }
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
    if let Some(preparing) = lock(&shared.preparing).as_ref()
        && generation.is_none_or(|wanted| wanted == preparing.generation)
    {
        preparing.cancelled.store(true, Ordering::Release);
    }
    {
        let mut admitting = lock(&shared.admitting);
        if admitting
            .as_ref()
            .is_some_and(|pending| generation.is_none_or(|wanted| wanted == pending.generation))
            && let Some(pending) = admitting.take()
        {
            pending.cancelled.store(true, Ordering::Release);
            pending.cancel.notify_one();
        }
    }
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

async fn prepare_start(
    shared: &Arc<Shared>,
    launch: &Launch,
    profile: String,
    signals: &mpsc::UnboundedSender<(u64, Signal)>,
    generation: u64,
    cancelled: Arc<AtomicBool>,
    preparation_started: Instant,
) -> Result<Running> {
    let bearer = Arc::new(mint_bearer()?);
    let gateway_bearer = Arc::new(mint_bearer()?);
    let launch = launch.clone();
    let prepare_bearer = bearer.clone();
    let prepare_profile = profile.clone();
    // Include held-person acquisition (which can wait on another consumer)
    // in the visible startup interval, not just the child launch afterwards.
    shared
        .diagnostics
        .service(None, ServiceFact::AgentStarting { generation });
    let (
        Prepared {
            command,
            person,
            local_engine_default,
        },
        person_failure,
    ) = tauri::async_runtime::spawn_blocking(move || {
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
    if cancelled.load(Ordering::Acquire) || shared.closed.load(Ordering::Acquire) {
        return Err(
            ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
                .with_reason("agent_start_cancelled"),
        );
    }
    let sender = signals.clone();
    let diagnostics = shared.diagnostics.clone();
    let secret = bearer.clone();
    let gateway_secret = gateway_bearer.clone();
    let supervised = tauri::async_runtime::spawn_blocking(move || {
        runner::start_child(
            command,
            Some(Startup {
                bearer: secret.as_str(),
                gateway_bearer: gateway_secret.as_str(),
                local_engine_default,
            }),
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
    if cancelled.load(Ordering::Acquire) || shared.closed.load(Ordering::Acquire) {
        let grace = shared.grace;
        tauri::async_runtime::spawn_blocking(move || supervised.stop(grace))
            .await
            .map_err(|_| ApplicationError::new(ErrorCode::Panic, Operation::Cli))??;
        return Err(
            ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
                .with_reason("agent_start_cancelled"),
        );
    }
    Ok(Running {
        supervised,
        profile,
        generation,
        bearer,
        gateway_bearer,
        person,
        person_failure,
        started: preparation_started,
    })
}

fn start(
    shared: &Arc<Shared>,
    launch: &Launch,
    profile: String,
    signals: &mpsc::UnboundedSender<(u64, Signal)>,
) {
    let generation = shared.generation.fetch_add(1, Ordering::AcqRel) + 1;
    let cancelled = Arc::new(AtomicBool::new(false));
    let started = Instant::now();
    *lock(&shared.preparing) = Some(Preparing {
        generation,
        profile: profile.clone(),
        started,
        cancelled: cancelled.clone(),
    });
    let (owner, launch, signals) = (shared.clone(), launch.clone(), signals.clone());
    let task = tauri::async_runtime::spawn(async move {
        let result = prepare_start(
            &owner, &launch, profile, &signals, generation, cancelled, started,
        )
        .await;
        if let Err(failed) = owner
            .completions
            .send(Completion::Started(generation, result))
            && let Completion::Started(_, Ok(running)) = failed.0
        {
            let grace = owner.grace;
            let _ =
                tauri::async_runtime::spawn_blocking(move || running.supervised.stop(grace)).await;
        }
    });
    let mut tasks = lock(&shared.tasks);
    tasks.retain(|task| !task.inner().is_finished());
    tasks.push(task);
}

async fn supervise(shared: Arc<Shared>, observe: Observe, changed: Changed, launch: Launch) {
    let (signals, mut received) = mpsc::unbounded_channel::<(u64, Signal)>();
    let mut completed = lock(&shared.completed)
        .take()
        .expect("one supervision owner");
    let mut completions = std::collections::VecDeque::new();
    let mut early = Vec::new();
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
        let startup_timeout = async {
            match startup_due(&shared) {
                Some(deadline) => tokio::time::sleep_until(deadline.into()).await,
                None => std::future::pending::<()>().await,
            }
        };
        tokio::pin!(startup_timeout);
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
                    if lock(&shared.running).is_none() && lock(&shared.preparing).as_ref().is_some_and(|p| p.generation == generation) {
                        early.push((generation, signal));
                        continue;
                    }
                    if handle(&shared, generation, signal).await {
                        retries.failed(&shared);
                    }
                }
                Some(completion) = completed.recv() => {
                    match completion {
                        Completion::Started(generation, result) => {
                            // Keeping a privately owned child needs no new
                            // authority observation. Readiness/admission still
                            // cannot publish an endpoint until the exact
                            // canonical profile is observed below. Process
                            // exit/refusal must remain observable meanwhile.
                            let pending = {
                                let mut preparing = lock(&shared.preparing);
                                if preparing.as_ref().is_some_and(|pending| pending.generation == generation) {
                                    preparing.take()
                                } else {
                                    None
                                }
                            };
                            let valid = pending.as_ref().is_some_and(|pending| !pending.cancelled.load(Ordering::Acquire));
                            match result {
                                Ok(running) if valid => {
                                    *lock(&shared.running) = Some(running);
                                    for (epoch, signal) in early.drain(..) {
                                        if epoch == generation && handle(&shared, epoch, signal).await {
                                            retries.failed(&shared);
                                        }
                                    }
                                }
                                Ok(running) => {
                                    let grace = shared.grace;
                                    let _ = tauri::async_runtime::spawn_blocking(move || running.supervised.stop(grace)).await;
                                    early.retain(|(epoch, _)| *epoch != generation);
                                }
                                Err(error) if valid => {
                                    shared.diagnostics.host_failure(HostStage::Agent, error);
                                    publish(&shared, State::Refused { code: Refusal::ServiceFailed });
                                    retries.failed(&shared);
                                }
                                Err(_) => early.retain(|(epoch, _)| *epoch != generation),
                            }
                        }
                        completion @ Completion::Admitted(..) => {
                            completions.push_back(completion);
                            continue 'supervision;
                        }
                    }
                }
                () = &mut startup_timeout => {
                    retries.timeout();
                    let _ = stop_running(&shared, None, AgentStopCause::ProtocolRefused).await;
                    publish(&shared, State::Refused { code: Refusal::Timeout });
                    continue 'supervision;
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
        if let Some(preparing) = lock(&shared.preparing).as_ref()
            && !matches!(&allowed, Allowed::Serve(profile) if *profile == preparing.profile)
        {
            preparing.cancelled.store(true, Ordering::Release);
        }
        while let Some(completion) = completions.pop_front() {
            match completion {
                Completion::Started(generation, result) => {
                    let preparing = {
                        let mut held = lock(&shared.preparing);
                        if held
                            .as_ref()
                            .is_some_and(|pending| pending.generation == generation)
                        {
                            held.take()
                        } else {
                            None
                        }
                    };
                    let valid = preparing.as_ref().is_some_and(|pending| {
                        !pending.cancelled.load(Ordering::Acquire)
                            && matches!(&allowed, Allowed::Serve(profile) if *profile == pending.profile)
                    });
                    match result {
                        Ok(running) if valid => {
                            *lock(&shared.running) = Some(running);
                            for (epoch, signal) in early.drain(..) {
                                if epoch == generation && handle(&shared, epoch, signal).await {
                                    retries.failed(&shared);
                                }
                            }
                        }
                        Ok(running) => {
                            let grace = shared.grace;
                            let _ = tauri::async_runtime::spawn_blocking(move || {
                                running.supervised.stop(grace)
                            })
                            .await;
                            early.retain(|(epoch, _)| *epoch != generation);
                        }
                        Err(error) if valid => {
                            shared.diagnostics.host_failure(HostStage::Agent, error);
                            publish(
                                &shared,
                                State::Refused {
                                    code: Refusal::ServiceFailed,
                                },
                            );
                            retries.failed(&shared);
                        }
                        Err(_) => {
                            early.retain(|(epoch, _)| *epoch != generation);
                        }
                    }
                }
                Completion::Admitted(generation, result) => {
                    let pending = {
                        let mut held = lock(&shared.admitting);
                        if held
                            .as_ref()
                            .is_some_and(|pending| pending.generation == generation)
                        {
                            held.take()
                        } else {
                            None
                        }
                    };
                    let current = lock(&shared.running).as_ref().is_some_and(|running| {
                        running.generation == generation
                            && matches!(&allowed, Allowed::Serve(profile) if *profile == running.profile)
                    });
                    if let Some(pending) = pending
                        && current
                        && !pending.cancelled.load(Ordering::Acquire)
                    {
                        match result {
                            Ok(endpoint) => {
                                *lock(&shared.admin) = Some(endpoint);
                                if let Some(ready) = pending.ready {
                                    let _ = handle(&shared, generation, Signal::Event(ready)).await;
                                }
                            }
                            Err(error) => {
                                let timeout = error.reason.as_deref() == Some("agent_timeout");
                                shared.diagnostics.host_failure(HostStage::Agent, error);
                                publish(
                                    &shared,
                                    State::Refused {
                                        code: if timeout {
                                            Refusal::Timeout
                                        } else {
                                            Refusal::ServiceFailed
                                        },
                                    },
                                );
                                let _ = stop_running(
                                    &shared,
                                    Some(generation),
                                    AgentStopCause::ProtocolRefused,
                                )
                                .await;
                                if timeout {
                                    retries.timeout();
                                } else {
                                    retries.failed(&shared);
                                }
                            }
                        }
                    }
                }
            }
        }
        let preparation_expired = lock(&shared.preparing).as_ref().is_some_and(|pending| {
            !pending.cancelled.load(Ordering::Acquire)
                && pending.started.elapsed() >= shared.startup_timeout
        });
        if preparation_expired {
            if let Some(pending) = lock(&shared.preparing).as_ref() {
                pending.cancelled.store(true, Ordering::Release);
            }
            publish(
                &shared,
                State::Refused {
                    code: Refusal::Timeout,
                },
            );
            retries.timeout();
        }
        let starting_expired = lock(&shared.running).as_ref().is_some_and(|running| {
            lock(&shared.admin).is_none() && running.started.elapsed() >= shared.startup_timeout
        });
        if starting_expired {
            publish(
                &shared,
                State::Refused {
                    code: Refusal::Timeout,
                },
            );
            let _ = stop_running(&shared, None, AgentStopCause::ProtocolRefused).await;
            retries.timeout();
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
                if !retries.waiting() && lock(&shared.preparing).is_none() {
                    serving = Some(profile.clone());
                    publish(&shared, State::Starting);
                    start(&shared, &launch, profile.clone(), &signals);
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
                    if lock(&shared.running).is_none() && lock(&shared.preparing).as_ref().is_some_and(|p| p.generation == generation) {
                        early.push((generation, signal));
                        continue;
                    }
                    if handle(&shared, generation, signal).await {
                        retries.failed(&shared);
                        break;
                    }
                }
                Some(completion) = completed.recv() => {
                    match completion {
                        started @ Completion::Started(..) => {
                            // The observation loop above installs private child
                            // ownership even if its observation stays pending.
                            let _ = shared.completions.send(started);
                        }
                        admitted => completions.push_back(admitted),
                    }
                    break;
                }
            }
        }
    }
    let _ = stop_running(&shared, None, AgentStopCause::WindowClosing).await;
    let tasks = std::mem::take(&mut *lock(&shared.tasks));
    for task in tasks {
        let _ = task.await;
    }
    while let Ok(completion) = completed.try_recv() {
        if let Completion::Started(_, Ok(running)) = completion {
            let grace = shared.grace;
            let _ =
                tauri::async_runtime::spawn_blocking(move || running.supervised.stop(grace)).await;
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
    retry.into_iter().chain(startup_due(shared)).min()
}

fn startup_due(shared: &Shared) -> Option<Instant> {
    let starting = lock(&shared.running).as_ref().and_then(|running| {
        lock(&shared.admin)
            .is_none()
            .then_some(running.started + shared.startup_timeout)
    });
    let preparation = lock(&shared.preparing).as_ref().and_then(|pending| {
        (!pending.cancelled.load(Ordering::Acquire))
            .then_some(pending.started + shared.startup_timeout)
    });
    starting.into_iter().chain(preparation).min()
}

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
            if lock(&shared.admitting).is_some() {
                return false;
            }
            let cancelled = Arc::new(AtomicBool::new(false));
            let cancel = Arc::new(Notify::new());
            *lock(&shared.admitting) = Some(Admitting {
                generation,
                cancel: cancel.clone(),
                cancelled: cancelled.clone(),
                ready: None,
            });
            let deadline = lock(&shared.running).as_ref().unwrap().started + shared.startup_timeout;
            let owner = shared.clone();
            let endpoint = super::admin::Endpoint {
                port: admin_port,
                bearer,
                generation,
                gate: Default::default(),
            };
            let task = tauri::async_runtime::spawn(async move {
                let result = admit_person(AdmissionWork {
                    person,
                    boot: runtime_boot_id,
                    profile: profile_id,
                    recipient: connection_id,
                    service: service_id,
                    deadline,
                    cancelled,
                    cancel,
                })
                .await
                .map(|()| endpoint);
                let _ = owner
                    .completions
                    .send(Completion::Admitted(generation, result));
            });
            lock(&shared.tasks).push(task);
            false
        }
        Signal::Event(Event::Ready {
            gateway_port,
            agent_version,
            workspace_root,
        }) => {
            {
                let mut admitting = lock(&shared.admitting);
                if let Some(pending) = admitting
                    .as_mut()
                    .filter(|pending| pending.generation == generation)
                {
                    pending.ready = Some(Event::Ready {
                        gateway_port,
                        agent_version,
                        workspace_root,
                    });
                    return false;
                }
            }
            if lock(&shared.admin)
                .as_ref()
                .is_none_or(|endpoint| endpoint.generation != generation)
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
            if let Some(pending) = lock(&shared.admitting).as_mut() {
                pending.ready = None;
            }
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
            if let Some(pending) = lock(&shared.admitting).as_mut() {
                pending.ready = None;
            }
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
