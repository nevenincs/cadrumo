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
/// How long after a refused or failed start another start is tried.
pub const RETRY: Duration = Duration::from_secs(30);

/// Why the agent service is not serving, as the column's closed vocabulary
/// names it.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum Refusal {
    #[serde(rename = "agent_service_absent")]
    ServiceAbsent,
    #[serde(rename = "agent_service_incompatible")]
    ServiceIncompatible,
    #[serde(rename = "agent_signed_out")]
    SignedOut,
    #[serde(rename = "agent_runtime_unavailable")]
    RuntimeUnavailable,
    #[serde(rename = "agent_provider_credential_missing")]
    ProviderCredentialMissing,
    #[serde(rename = "agent_service_failed")]
    ServiceFailed,
}

impl Refusal {
    /// The column's code for a launcher's. A code the column has no word for,
    /// such as an unmarked root, is a start that failed.
    fn from_launcher(code: &str) -> Self {
        match code {
            "agent_service_absent" => Self::ServiceAbsent,
            "agent_service_incompatible" => Self::ServiceIncompatible,
            "agent_signed_out" => Self::SignedOut,
            "agent_runtime_unavailable" => Self::RuntimeUnavailable,
            "agent_provider_credential_missing" => Self::ProviderCredentialMissing,
            _ => Self::ServiceFailed,
        }
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
pub type Launch = Arc<dyn Fn() -> Result<Command> + Send + Sync>;

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
        let stopped = stop_running(&self.shared, None).await;
        if let Some(worker) = worker {
            let _ = worker.await;
        }
        // Supervision may have stored a launcher while this closed; it stops
        // any it holds when it sees the close, and this stops what is left.
        let remaining = stop_running(&self.shared, None).await;
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
    let mut listener = lock(&shared.listener);
    if listener
        .as_ref()
        .is_some_and(|held| held.channel.send(status).is_err())
    {
        *listener = None;
    }
}

/// Stops the running launcher, if any. With a generation, only that one.
async fn stop_running(shared: &Arc<Shared>, generation: Option<u64>) -> Result<()> {
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
    let grace = shared.grace;
    let diagnostics = shared.diagnostics.clone();
    let ended = tauri::async_runtime::spawn_blocking(move || running.supervised.stop(grace))
        .await
        .map_err(|_| ApplicationError::new(ErrorCode::Panic, Operation::Cli))
        .and_then(|ended| ended);
    if let Err(error) = &ended {
        diagnostics.failure(error.clone());
    }
    ended.map(|_| ())
}

async fn start(
    shared: &Arc<Shared>,
    launch: &Launch,
    profile: String,
    signals: &mpsc::UnboundedSender<(u64, Signal)>,
) -> Result<()> {
    let command = launch()?;
    let bearer = Arc::new(mint_bearer()?);
    let generation = shared.generation.fetch_add(1, Ordering::AcqRel) + 1;
    let sender = signals.clone();
    let diagnostics = shared.diagnostics.clone();
    let secret = bearer.clone();
    let supervised = tauri::async_runtime::spawn_blocking(move || {
        runner::start(
            command,
            &secret,
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

async fn supervise(shared: Arc<Shared>, observe: Observe, launch: Launch) {
    let (signals, mut received) = mpsc::unbounded_channel::<(u64, Signal)>();
    let mut retry_after: Option<Instant> = None;
    let mut serving: Option<String> = None;
    while !shared.closed.load(Ordering::Acquire) {
        let wake = shared.wake.notified();
        tokio::pin!(wake);
        wake.as_mut().enable();
        let allowed = allowed(&observe().await);
        if shared.closed.load(Ordering::Acquire) {
            break;
        }
        let current = lock(&shared.running).as_ref().map(|r| r.profile.clone());
        match (&current, &allowed) {
            (Some(profile), Allowed::Serve(wanted)) if profile == wanted => {}
            (Some(_), _) => {
                let _ = stop_running(&shared, None).await;
                serving = None;
                match &allowed {
                    Allowed::Refuse(code) => publish(&shared, State::Refused { code: *code }),
                    // Another profile: the next round starts its own.
                    Allowed::Serve(_) => {
                        publish(&shared, State::Stopped);
                        retry_after = None;
                        continue;
                    }
                }
            }
            (None, Allowed::Refuse(code)) => {
                retry_after = None;
                serving = None;
                publish(&shared, State::Refused { code: *code });
            }
            (None, Allowed::Serve(profile)) => {
                // A refused start waits before it is tried again, unless the
                // sign-in changed in between.
                let waiting = retry_after.is_some_and(|at| Instant::now() < at)
                    && serving.as_deref() == Some(profile.as_str());
                if !waiting {
                    serving = Some(profile.clone());
                    retry_after = None;
                    publish(&shared, State::Starting);
                    if start(&shared, &launch, profile.clone(), &signals)
                        .await
                        .is_err()
                    {
                        publish(
                            &shared,
                            State::Refused {
                                code: Refusal::ServiceFailed,
                            },
                        );
                        retry_after = Some(Instant::now() + shared.retry);
                    }
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
                        retry_after = Some(Instant::now() + shared.retry);
                    }
                }
            }
        }
    }
    let _ = stop_running(&shared, None).await;
}

/// Acts on one launcher signal. True when the launcher ended unasked, which
/// delays the next start.
async fn handle(shared: &Arc<Shared>, generation: u64, signal: Signal) -> bool {
    let bearer = {
        let running = lock(&shared.running);
        match running.as_ref() {
            Some(running) if running.generation == generation => running.bearer.clone(),
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
            let _ = stop_running(shared, Some(generation)).await;
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
            publish(
                shared,
                State::Refused {
                    code: Refusal::ServiceFailed,
                },
            );
            let _ = stop_running(shared, Some(generation)).await;
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
            let _ = stop_running(shared, Some(generation)).await;
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
        // A launcher code the column has no word for is a failed start.
        assert_eq!(
            Refusal::from_launcher("agent_root_unmarked"),
            Refusal::ServiceFailed
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

    #[cfg(windows)]
    mod live {
        use super::*;
        use crate::agent::runner::tests::{alive, launcher_script, powershell, reported};
        use tauri::ipc::InvokeResponseBody;

        struct Rig {
            supervisor: Supervisor,
            observation: Arc<Mutex<Result<Observation>>>,
            statuses: Arc<Mutex<Vec<serde_json::Value>>>,
        }

        fn rig(ignore_end: bool) -> Rig {
            let observation = Arc::new(Mutex::new(observed(true, true, Some("A"))));
            let source = observation.clone();
            let observe: Observe = Arc::new(move || {
                let current = lock(&source).clone();
                Box::pin(async move { current })
            });
            let launch: Launch = Arc::new(move || Ok(powershell(&launcher_script(ignore_end))));
            let supervisor = Supervisor::with_timing(
                observe,
                Some(launch),
                Arc::new(Diagnostics::default()),
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
            let launch: Launch = Arc::new(move || {
                counted.fetch_add(1, Ordering::AcqRel);
                Ok(powershell(
                    "$null = [Console]::In.ReadLine(); [Console]::Out.WriteLine('{\"event\":\"agent_refused\",\"code\":\"agent_root_unmarked\"}'); exit 3",
                ))
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
                    code: Refusal::ServiceFailed,
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
