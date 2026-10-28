//! Component setup through this window's own engine: status reads, full
//! checks, setup with its plan review, and cancellation, each run by the
//! component engine in this process (`components`). Riding the held person
//! session but apart from setup, the profile's Google account: its stored
//! sign-in, sign-in and sign-out (`google`). The window names items and
//! choices only, and words every code the snapshot carries from its own
//! catalogue. Engine progress and the session's cues each push the typed
//! snapshot on the window's channel. Nothing polls.
//!
//! The local AI is provisioned from the person's selection of models, which only
//! this host reads: before each engine command it asks the agent service for the
//! per-role selection and the catalogue's download sizes (`admission`).
//!
//! The window words an `unavailable` refusal and every host failure by a code alone.
//! The cause behind each is recorded in diagnostics (`reports`), where the Logs
//! console shows it.
pub mod admission;
pub mod components;
pub mod google;
pub mod reports;
pub mod review;
pub mod wire;

use super::sign_in::{Presence, SignIn, wire::SignInStatus};
use crate::agent::{
    AgentHost,
    person::{HeldPerson, PersonEvent},
};
use admission::Admission;
use cadrumo_application::diagnostics::Diagnostics;
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use cadrumo_application::provisioning::items::ItemId;
use components::Components;
use google::{Act, Relay, Tracker};
use reports::Reports;
use serde::Serialize;
use serde_json::Value;
use std::sync::{
    Arc, Mutex,
    atomic::{AtomicBool, Ordering},
};
use tauri::{State, ipc::Channel};
use wire::{Action, CommandFailure, Google, Refusal, Snapshot, Stop};

/// The setup host could not carry on, for the stable `reason` named.
fn failed(reason: &'static str) -> ApplicationError {
    ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli).with_reason(reason)
}

/// The snapshot the window would be given has a value outside its closed sets.
fn snapshot_invalid() -> ApplicationError {
    ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
        .with_reason("setup_snapshot_invalid")
}

/// What the signed-in status lets a setup command do.
enum Standing {
    /// Nobody is signed in.
    SignedOut,
    /// A profile is signed in and its runtime does not answer.
    Unready,
    /// The signed-in profile, whose runtime answers.
    Ready(String),
}

fn standing(status: &SignInStatus) -> Result<Standing> {
    if status.state != Presence::Present {
        if status.supported && status.state == Presence::Unknown {
            return Err(failed("setup_presence_unknown"));
        }
        return Ok(Standing::SignedOut);
    }
    let profile = status
        .active_profile
        .clone()
        .ok_or_else(|| failed("setup_profile_missing"))?;
    Ok(if status.runtime_ready() {
        Standing::Ready(profile)
    } else {
        Standing::Unready
    })
}

/// Whether `status` still shows the answering runtime of the signed-in `profile`.
fn unchanged(status: &SignInStatus, profile: &str) -> bool {
    status.state == Presence::Present
        && status.runtime_ready()
        && status.active_profile.as_deref() == Some(profile)
}

fn lock<T>(value: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    value.lock().unwrap_or_else(|error| error.into_inner())
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Availability {
    SignedOut,
    Unavailable,
    Ready,
}

/// What every setup command answers and the observe channel carries.
#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct DesktopSetup {
    revision: u64,
    state: Availability,
    snapshot: Option<Snapshot>,
}

struct Current {
    value: DesktopSetup,
    listener: Option<Channel<DesktopSetup>>,
}

impl Current {
    fn unobserve(&mut self, subscription: u32) {
        if self
            .listener
            .as_ref()
            .is_some_and(|channel| channel.id() == subscription)
        {
            self.listener = None;
        }
    }

    /// Publish a changed state with the next revision; an unchanged one keeps its revision.
    fn update(&mut self, state: Availability, snapshot: Option<Snapshot>) -> DesktopSetup {
        if self.value.state != state || self.value.snapshot != snapshot {
            self.value = DesktopSetup {
                revision: self.value.revision.saturating_add(1),
                state,
                snapshot,
            };
            if self
                .listener
                .as_ref()
                .is_some_and(|channel| channel.send(self.value.clone()).is_err())
            {
                self.listener = None;
            }
        }
        self.value.clone()
    }
}

/// The held person bridge as the account tracker's relay.
struct PersonRelay(HeldPerson);

impl Relay for PersonRelay {
    fn call(&mut self, request: Value) -> Result<Value> {
        // Each exchange retains correlation and session authority. Do not hold
        // the bridge across an entire account read: service admission and
        // person activity must be able to run between its independent reads.
        lock(&self.0).exchange(request)
    }
}

/// The window's snapshot: the engine's side and the account beside it, or a
/// host failure when a value falls outside its closed set.
fn compose(engine: components::View, google: Google) -> Option<Snapshot> {
    let snapshot = Snapshot {
        rows: engine.rows,
        rows_mode: engine.rows_mode,
        complete: engine.complete,
        hardware_limited: engine.hardware_limited,
        check: engine.check,
        setup: engine.setup,
        google,
        details: engine.details,
    };
    snapshot.valid().then_some(snapshot)
}

fn item_ids(items: Option<Vec<String>>) -> Option<Vec<ItemId>> {
    items.map(|items| {
        items
            .iter()
            .filter_map(|item| ItemId::parse(item))
            .collect()
    })
}

pub struct SetupHost {
    sign_in: Arc<SignIn>,
    components: Components,
    reports: Reports,
    current: Mutex<Current>,
    /// The account as last read, which the engine's own changes are shown beside.
    google: Mutex<Option<Google>>,
    person: Arc<Mutex<Option<HeldPerson>>>,
    tracker: Arc<Mutex<Option<Tracker>>>,
    operation: tokio::sync::Mutex<()>,
    worker: Mutex<Option<tokio::task::JoinHandle<()>>>,
    closed: AtomicBool,
    wake: tokio::sync::Notify,
}

impl SetupHost {
    pub fn new(sign_in: Arc<SignIn>, agent: Arc<AgentHost>, diagnostics: Arc<Diagnostics>) -> Self {
        Self {
            sign_in,
            components: Components::new(
                components::installation(),
                Arc::new(Admission::new(agent)),
                diagnostics.clone(),
            ),
            reports: Reports::new(diagnostics),
            current: Mutex::new(Current {
                value: DesktopSetup {
                    revision: 0,
                    state: Availability::SignedOut,
                    snapshot: None,
                },
                listener: None,
            }),
            google: Mutex::new(None),
            person: Arc::new(Mutex::new(None)),
            tracker: Arc::new(Mutex::new(None)),
            operation: tokio::sync::Mutex::new(()),
            worker: Mutex::new(None),
            closed: AtomicBool::new(false),
            wake: tokio::sync::Notify::new(),
        }
    }

    fn publish(&self, state: Availability, snapshot: Option<Snapshot>) -> DesktopSetup {
        lock(&self.current).update(state, snapshot)
    }

    /// Publishes what the engine changed beside the account as last read; a
    /// window that shows no setup now has nothing to update.
    fn refresh(&self) {
        let shown = lock(&self.current).value.state == Availability::Ready;
        let google = lock(&self.google).clone();
        if let (true, Some(google)) = (shown, google) {
            match compose(self.components.view(), google) {
                Some(snapshot) => self.publish(Availability::Ready, Some(snapshot)),
                None => {
                    self.reports.read(&Stop::Host(snapshot_invalid()));
                    self.publish(Availability::Unavailable, None)
                }
            };
        }
    }

    /// The engine's part of one window action. A setup waits for its review or
    /// its network check here, apart from the held session, so the session and
    /// a cancel stay free meanwhile.
    async fn act(&self, request: &Action) -> std::result::Result<(), Stop> {
        match request {
            Action::Observe | Action::GoogleSignIn | Action::GoogleSignOut => {
                self.components.observe();
                Ok(())
            }
            Action::Check(mode) => {
                self.components.check(*mode);
                Ok(())
            }
            Action::Verify(items) => {
                self.components
                    .verify(item_ids(items.clone()).unwrap_or_default());
                Ok(())
            }
            Action::Start {
                items,
                resume,
                download,
            } => {
                self.components
                    .start(item_ids(items.clone()), *resume, download.clone())
                    .await
            }
            Action::Answer {
                operation_id,
                plan_digest,
                decision,
            } => self
                .components
                .answer(operation_id, plan_digest, *decision)
                .await
                .map_err(Stop::from),
            Action::Cancel { operation_id } => self.components.cancel(operation_id).await,
            Action::RemoveModel { model } => self.components.remove_model(model).await,
        }
    }

    /// Carry one setup action to the engine and the account's part of it to
    /// the held session of the signed-in profile, then publish the snapshot
    /// after it. Signed out, an action is refused and a read answers the
    /// signed-out state. Whatever lay behind an `unavailable` refusal or a host
    /// failure the window is told, diagnostics are told as well.
    async fn exchange(
        &self,
        request: Action,
        action: bool,
    ) -> std::result::Result<DesktopSetup, CommandFailure> {
        match self.carry(request, action).await {
            Ok(value) => Ok(value),
            Err(stop) => {
                if action {
                    self.reports.command(&stop);
                } else {
                    self.reports.read(&stop);
                }
                Err(stop.into())
            }
        }
    }

    /// A read the window is told of by the state it is shown rather than by an error,
    /// which only a command is answered with.
    fn shown(&self, action: bool, stop: Stop) -> std::result::Result<DesktopSetup, Stop> {
        if action {
            return Err(stop);
        }
        self.reports.read(&stop);
        Ok(lock(&self.current).value.clone())
    }

    async fn carry(
        &self,
        request: Action,
        action: bool,
    ) -> std::result::Result<DesktopSetup, Stop> {
        if self.closed.load(Ordering::Acquire) {
            return Err(failed("setup_host_closed").into());
        }
        let status = self.sign_in.read_status().await?;
        let profile = match standing(&status)? {
            Standing::SignedOut => {
                self.release_person().await?;
                let value = self.publish(Availability::SignedOut, None);
                self.reports.recovered();
                return if action {
                    Err(Refusal::NotSignedIn.into())
                } else {
                    Ok(value)
                };
            }
            Standing::Unready => {
                self.publish(Availability::Unavailable, None);
                return self.shown(action, Stop::unavailable("setup_runtime_not_ready"));
            }
            Standing::Ready(profile) => profile,
        };
        let refused = self.act(&request).await.err();
        let account = match request {
            Action::GoogleSignIn => Act::SignIn,
            Action::GoogleSignOut => Act::SignOut,
            _ => Act::Observe,
        };
        let _operation = self.operation.lock().await;
        if self.closed.load(Ordering::Acquire) {
            return Err(failed("setup_host_closed").into());
        }
        let sign_in = self.sign_in.clone();
        let bridge = self.person.clone();
        let tracker = self.tracker.clone();
        let label = profile.clone();
        let exchanged = super::blocking(move || {
            let profile_id = sign_in.profile_id(&label)?;
            let mut held = lock(&bridge);
            // Replacing, not clearing first: the session stays held while it is shared.
            let person = sign_in.person(&profile_id)?;
            *held = Some(person.clone());
            let identity = lock(&person).identity.clone();
            let mut followed = lock(&tracker);
            // Another held session's account is not this window's to follow.
            let tracked = match followed.take() {
                Some(tracked) if tracked.follows(&identity) => tracked,
                _ => Tracker::new(identity),
            };
            let tracked = followed.insert(tracked);
            let answered = tracked.handle(&mut PersonRelay(person.clone()), account);
            if matches!(answered, Err(Stop::Host(_))) && !lock(&person).is_open() {
                *held = None;
            }
            Ok(answered)
        })
        .await;
        let answered = match exchanged {
            Ok(answered) => answered,
            Err(error) => Err(Stop::Host(error)),
        };
        let after = self.sign_in.read_status().await?;
        if !unchanged(&after, &profile) {
            self.release_person().await?;
            self.publish(Availability::Unavailable, None);
            return Err(failed("setup_session_changed").into());
        }
        let google = match answered {
            Ok(google) => google,
            Err(Stop::Host(error)) => {
                // A lost bridge keeps no setup on display as if it were current.
                *lock(&self.google) = None;
                self.publish(Availability::Unavailable, None);
                return self.shown(action, Stop::Host(error));
            }
            Err(stop) => return Err(stop),
        };
        *lock(&self.google) = Some(google.clone());
        let Some(snapshot) = compose(self.components.view(), google) else {
            self.publish(Availability::Unavailable, None);
            return self.shown(action, Stop::Host(snapshot_invalid()));
        };
        let value = self.publish(Availability::Ready, Some(snapshot));
        self.reports.recovered();
        match refused {
            Some(stop) => Err(stop),
            None => Ok(value),
        }
    }

    /// A failure of the host itself, recorded as it is returned.
    fn lost(&self, error: ApplicationError) -> ApplicationError {
        self.reports.error(&error);
        error
    }

    async fn release_person(&self) -> Result<()> {
        let bridge = self.person.clone();
        super::blocking(move || {
            *lock(&bridge) = None;
            Ok(())
        })
        .await
    }

    fn observe(self: &Arc<Self>, updates: Channel<DesktopSetup>) -> Result<u32> {
        let mut worker = lock(&self.worker);
        if self.closed.load(Ordering::Acquire) {
            return Err(self.lost(failed("setup_host_closed")));
        }
        let subscription = updates.id();
        let mut current = lock(&self.current);
        updates
            .send(current.value.clone())
            .map_err(|_| self.lost(failed("setup_observer_closed")))?;
        current.listener = Some(updates);
        drop(current);
        if worker.is_none() {
            let owner = self.clone();
            *worker = Some(tokio::spawn(async move {
                let mut events = owner.sign_in.person_events();
                let mut changes = owner.components.changes();
                let mut read = true;
                loop {
                    // Register every wake before reading, so none arriving meanwhile is lost.
                    let wake = owner.wake.notified();
                    tokio::pin!(wake);
                    wake.as_mut().enable();
                    let signed_in = owner.sign_in.observation_changed();
                    tokio::pin!(signed_in);
                    if owner.closed.load(Ordering::Acquire) {
                        break;
                    }
                    if read && lock(&owner.current).listener.is_some() {
                        // A failed read has recorded its cause and published the unavailable
                        // state; the next cue reads again.
                        let _ = owner.exchange(Action::Observe, false).await;
                    }
                    read = true;
                    tokio::select! {
                        _ = &mut wake => {},
                        () = &mut signed_in => {},
                        () = setup_pushed(&mut events) => {},
                        () = engine_changed(&mut changes) => {
                            // The engine moved on: its part is shown again without a session read.
                            owner.refresh();
                            read = false;
                        },
                    }
                }
            }));
        } else {
            self.wake.notify_one();
        }
        Ok(subscription)
    }

    pub async fn close(&self) -> Result<()> {
        self.closed.store(true, Ordering::Release);
        lock(&self.current).listener = None;
        self.wake.notify_one();
        let worker = lock(&self.worker).take();
        if let Some(worker) = worker {
            worker
                .await
                .map_err(|error| self.lost(failed("setup_worker_join").caused_by(error)))?;
        }
        self.components.close().await;
        let _operation = self.operation.lock().await;
        self.release_person().await
    }
}

/// Resolves when the engine changed what the window shows.
async fn engine_changed(changes: &mut tokio::sync::watch::Receiver<u64>) {
    if changes.changed().await.is_err() {
        // The engine is gone with its host; nothing more will change.
        std::future::pending::<()>().await;
    }
}

/// Resolves when the held person session hears that an operation it relayed,
/// a Google sign-in included, may have changed, or ended; other pushes are
/// not this host's.
async fn setup_pushed(events: &mut tokio::sync::broadcast::Receiver<PersonEvent>) {
    use tokio::sync::broadcast::error::RecvError;
    loop {
        match events.recv().await {
            Ok(PersonEvent::OperationChanged | PersonEvent::Retired)
            | Err(RecvError::Lagged(_)) => {
                return;
            }
            Ok(
                PersonEvent::LanguageChanged
                | PersonEvent::RecordsChanged
                | PersonEvent::AttendanceChanged,
            ) => {}
            // The window is closing; nothing more will be pushed.
            Err(RecvError::Closed) => std::future::pending::<()>().await,
        }
    }
}

pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        desktop_setup_review_pending,
        desktop_setup_review_claim,
        desktop_setup_review_answer,
        desktop_setup_read,
        desktop_setup_check,
        desktop_setup_verify,
        desktop_setup_start,
        desktop_setup_answer,
        desktop_setup_cancel,
        desktop_setup_remove_model,
        desktop_google_sign_in,
        desktop_google_sign_out,
        desktop_setup_observe,
        desktop_setup_unobserve
    ]
}

#[tauri::command]
async fn desktop_setup_review_pending(
    host: State<'_, Arc<SetupHost>>,
) -> std::result::Result<Value, review::Failure> {
    review::exchange(&host, review::Action::Pending).await
}

#[tauri::command]
async fn desktop_setup_review_claim(
    host: State<'_, Arc<SetupHost>>,
    review: review::Coordinates,
) -> std::result::Result<Value, review::Failure> {
    review::exchange(&host, review::Action::Claim(review)).await
}

#[tauri::command]
async fn desktop_setup_review_answer(
    host: State<'_, Arc<SetupHost>>,
    review: review::Coordinates,
    decision: review::Decision,
) -> std::result::Result<Value, review::Failure> {
    review::exchange(&host, review::Action::Answer(review, decision)).await
}

#[tauri::command]
async fn desktop_setup_read(
    host: State<'_, Arc<SetupHost>>,
) -> std::result::Result<DesktopSetup, CommandFailure> {
    host.exchange(Action::Observe, false).await
}

#[tauri::command]
async fn desktop_setup_check(
    host: State<'_, Arc<SetupHost>>,
    mode: String,
) -> std::result::Result<DesktopSetup, CommandFailure> {
    host.exchange(wire::check_request(&mode)?, true).await
}

#[tauri::command]
async fn desktop_setup_verify(
    host: State<'_, Arc<SetupHost>>,
    items: Option<Vec<String>>,
) -> std::result::Result<DesktopSetup, CommandFailure> {
    host.exchange(wire::verify_request(items)?, true).await
}

#[tauri::command]
async fn desktop_setup_start(
    host: State<'_, Arc<SetupHost>>,
    items: Option<Vec<String>>,
    resume: bool,
    download: Option<wire::ModelDownload>,
) -> std::result::Result<DesktopSetup, CommandFailure> {
    host.exchange(wire::start_request(items, resume, download)?, true)
        .await
}

#[tauri::command]
async fn desktop_setup_answer(
    host: State<'_, Arc<SetupHost>>,
    operation_id: String,
    plan_digest: String,
    decision: String,
) -> std::result::Result<DesktopSetup, CommandFailure> {
    host.exchange(
        wire::answer_request(&operation_id, &plan_digest, &decision)?,
        true,
    )
    .await
}

#[tauri::command]
async fn desktop_setup_cancel(
    host: State<'_, Arc<SetupHost>>,
    operation_id: String,
) -> std::result::Result<DesktopSetup, CommandFailure> {
    host.exchange(wire::cancel_request(&operation_id)?, true)
        .await
}

/// Removes one local model the person picked, once no role selects it.
#[tauri::command]
async fn desktop_setup_remove_model(
    host: State<'_, Arc<SetupHost>>,
    model: String,
) -> std::result::Result<DesktopSetup, CommandFailure> {
    host.exchange(wire::remove_model_request(&model)?, true)
        .await
}

/// Signs the profile into Google: Google's own consent page is the approval.
#[tauri::command]
async fn desktop_google_sign_in(
    host: State<'_, Arc<SetupHost>>,
) -> std::result::Result<DesktopSetup, CommandFailure> {
    host.exchange(Action::GoogleSignIn, true).await
}

/// Removes the profile's stored Google sign-in.
#[tauri::command]
async fn desktop_google_sign_out(
    host: State<'_, Arc<SetupHost>>,
) -> std::result::Result<DesktopSetup, CommandFailure> {
    host.exchange(Action::GoogleSignOut, true).await
}

#[tauri::command]
async fn desktop_setup_observe(
    host: State<'_, Arc<SetupHost>>,
    updates: Channel<DesktopSetup>,
) -> Result<u32> {
    host.inner().observe(updates)
}

#[tauri::command]
fn desktop_setup_unobserve(host: State<'_, Arc<SetupHost>>, subscription: u32) {
    lock(&host.current).unobserve(subscription);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(windows)]
    #[test]
    fn setup_relay_releases_the_person_between_requests() {
        use crate::agent::person::{Person, request_id};
        let profile = request_id().unwrap();
        let identity = serde_json::json!({
            "kind": "session_held", "profile_id": profile,
            "session_id": request_id().unwrap(), "runtime_boot_id": request_id().unwrap(),
            "connection_id": request_id().unwrap(),
        });
        let reply = serde_json::json!({
            "kind": "profile_language", "profile_id": profile,
            "session_id": identity["session_id"], "request_id": "",
            "runtime_boot_id": identity["runtime_boot_id"],
            "connection_id": identity["connection_id"],
            "language": "en", "record_revision": 1,
        });
        let script = format!(
            "& {{ [Console]::Out.WriteLine('{identity}'); [Console]::Out.Flush(); \
             for ($i = 0; $i -lt 2; $i++) {{ \
             $request = [Console]::In.ReadLine() | ConvertFrom-Json; \
             $reply = '{reply}' | ConvertFrom-Json; $reply.request_id = $request.request_id; \
             [Console]::Out.WriteLine(($reply | ConvertTo-Json -Compress)); [Console]::Out.Flush(); \
             }}; [Console]::In.ReadLine() | Out-Null }}"
        );
        let mut command = std::process::Command::new("powershell.exe");
        command.args([
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            &script,
        ]);
        let held = Arc::new(Mutex::new(Person::scripted(command, &profile).unwrap()));
        let mut relay = PersonRelay(held.clone());
        relay
            .call(serde_json::json!({"action":"language_observe"}))
            .unwrap();
        // Another consumer can acquire and exchange while the setup relay is
        // still alive; the snapshot no longer monopolizes the bridge.
        let mut other = held
            .try_lock()
            .expect("setup retained the shared person lock");
        assert_eq!(
            other
                .exchange(serde_json::json!({"action":"language_observe"}))
                .unwrap()["language"],
            "en"
        );
    }
    use serde_json::json;

    fn snapshot(details: &str) -> Snapshot {
        serde_json::from_value(json!({
            "rows": [], "rows_mode": null, "complete": null, "hardware_limited": null,
            "check": null, "setup": null,
            "google": {"state": null, "email": null, "drive_folder_id": null, "stage": "idle", "failure": null},
            "details": details,
        }))
        .unwrap()
    }

    fn current(listener: Option<Channel<DesktopSetup>>) -> Current {
        Current {
            value: DesktopSetup {
                revision: 0,
                state: Availability::SignedOut,
                snapshot: None,
            },
            listener,
        }
    }

    #[test]
    fn revisions_follow_changes_only() {
        let mut current = current(None);
        assert_eq!(current.update(Availability::SignedOut, None).revision, 0);
        let ready = current.update(Availability::Ready, Some(snapshot("a")));
        assert_eq!((ready.revision, ready.state), (1, Availability::Ready));
        assert_eq!(
            current
                .update(Availability::Ready, Some(snapshot("a")))
                .revision,
            1
        );
        assert_eq!(
            current
                .update(Availability::Ready, Some(snapshot("b")))
                .revision,
            2
        );
        let lost = current.update(Availability::Unavailable, None);
        assert_eq!((lost.revision, lost.snapshot), (3, None));
    }

    #[test]
    fn the_channel_carries_each_change_as_the_window_reads_it_until_unobserved() {
        let frames = Arc::new(Mutex::new(Vec::new()));
        let capture = frames.clone();
        let channel = Channel::new(move |body| {
            let tauri::ipc::InvokeResponseBody::Json(body) = body else {
                panic!("setup is JSON")
            };
            lock(&capture).push(serde_json::from_str::<Value>(&body).unwrap());
            Ok(())
        });
        let id = channel.id();
        let mut current = current(Some(channel));
        current.update(Availability::Ready, Some(snapshot("a")));
        current.update(Availability::Ready, Some(snapshot("a")));
        assert_eq!(lock(&frames).len(), 1);
        let frame = lock(&frames)[0].clone();
        assert_eq!(frame["revision"], 1);
        assert_eq!(frame["state"], "ready");
        assert_eq!(frame["snapshot"]["google"]["stage"], "idle");
        current.unobserve(id + 1);
        assert!(current.listener.is_some());
        current.unobserve(id);
        current.update(Availability::SignedOut, None);
        assert_eq!(lock(&frames).len(), 1);
    }

    #[tokio::test]
    async fn only_an_operation_cue_or_retirement_wakes_the_observer() {
        let (sender, mut events) = tokio::sync::broadcast::channel(4);
        sender.send(PersonEvent::LanguageChanged).unwrap();
        sender.send(PersonEvent::AttendanceChanged).unwrap();
        let pending = tokio::time::timeout(
            std::time::Duration::from_millis(50),
            setup_pushed(&mut events),
        )
        .await;
        assert!(pending.is_err());
        sender.send(PersonEvent::OperationChanged).unwrap();
        setup_pushed(&mut events).await;
        sender.send(PersonEvent::Retired).unwrap();
        setup_pushed(&mut events).await;
    }

    fn status(state: Presence, profile: Option<&str>, runtime: bool) -> SignInStatus {
        SignInStatus {
            supported: true,
            state,
            active_profile: profile.map(str::to_owned),
            runtime_available: runtime,
            reconnecting: None,
            refusal: None,
        }
    }

    #[test]
    fn a_status_says_what_a_command_may_do_or_names_why_it_may_not() {
        assert!(matches!(
            standing(&status(Presence::Absent, None, true)),
            Ok(Standing::SignedOut)
        ));
        assert!(matches!(
            standing(&SignInStatus::unsupported()),
            Ok(Standing::SignedOut)
        ));
        assert!(matches!(
            standing(&status(Presence::Present, Some("one"), true)),
            Ok(Standing::Ready(profile)) if profile == "one"
        ));
        assert!(matches!(
            standing(&status(Presence::Present, Some("one"), false)),
            Ok(Standing::Unready)
        ));
        for (name, status, reason) in [
            (
                "a presence the runtime could not read",
                status(Presence::Unknown, None, true),
                "setup_presence_unknown",
            ),
            (
                "a signed-in profile with no name",
                status(Presence::Present, None, true),
                "setup_profile_missing",
            ),
        ] {
            let error = standing(&status).err().expect(name);
            assert_eq!(error.reason.as_deref(), Some(reason), "{name}");
            assert_eq!(error.code, ErrorCode::SessionUnavailable, "{name}");
        }
    }

    #[test]
    fn a_session_is_unchanged_only_while_the_same_profiles_runtime_answers() {
        assert!(unchanged(
            &status(Presence::Present, Some("one"), true),
            "one"
        ));
        assert!(!unchanged(
            &status(Presence::Present, Some("two"), true),
            "one"
        ));
        assert!(!unchanged(
            &status(Presence::Present, Some("one"), false),
            "one"
        ));
        assert!(!unchanged(
            &status(Presence::Absent, Some("one"), true),
            "one"
        ));
        assert!(!unchanged(&status(Presence::Present, None, true), "one"));
    }

    #[test]
    fn a_snapshot_outside_its_closed_sets_is_not_composed() {
        let view = || components::View {
            rows: Vec::new(),
            rows_mode: None,
            complete: None,
            hardware_limited: None,
            check: None,
            setup: None,
            details: "Cadrumo setup details\n".into(),
        };
        let unread = || Google {
            state: None,
            email: None,
            drive_folder_id: None,
            stage: wire::GoogleStage::Idle,
            failure: None,
        };
        assert!(compose(view(), unread()).is_some());
        let mut failed = unread();
        failed.failure = Some(wire::Failure::Unexpected);
        assert!(compose(view(), failed).is_none());
    }
}
