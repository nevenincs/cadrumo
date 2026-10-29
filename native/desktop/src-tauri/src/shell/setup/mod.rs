//! Component setup through this window's own engine: status reads, full
//! checks, setup with its plan review, and cancellation, each run by the
//! component engine in this process (`components`). The components are this
//! installation's, not a profile's, so the engine serves them whether or not
//! anyone is signed in. Riding the held person session but apart from setup,
//! the profile's Google account: its stored sign-in, sign-in and sign-out
//! (`google`). The window names items and
//! choices only, and words every code the snapshot carries from its own
//! catalogue. Engine progress and the session's cues each push the typed
//! snapshot on the window's channel. Nothing polls.
//!
//! The local AI is provisioned from the person's selection of models, which only
//! this host reads: before each engine command it asks the agent service for the
//! per-role selection and the catalogue's download sizes (`admission`). The model list
//! is the signed-in person's, so signed out a model download or removal, and a removal
//! of the local AI that takes the listed models with it, is refused as not signed in,
//! as is the Google account.
//!
//! Signed in, the engine does not wait on the profile's runtime either: while that
//! runtime or its held session does not answer, the engine's side is shown beside an
//! account that cannot be read, and only what needs the session (the Google account
//! and what the person's model list admits) is refused as `unavailable`. The window is
//! shown no setup only when the engine's own snapshot cannot be composed.
//!
//! The window words an `unavailable` refusal and every host failure by a code alone.
//! The cause behind each is recorded in diagnostics (`reports`), where the Logs
//! console shows it.
pub mod admission;
pub mod components;
pub mod google;
pub mod reports;
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
use wire::{
    Action, CommandFailure, Google, GoogleStage, GoogleState, Refusal, Removal, Snapshot, Stop,
};

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
    /// A profile is signed in and its runtime does not answer: the engine
    /// still serves what is this installation's.
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

/// Whether the window is shown setup: `Unavailable` until the engine's side is
/// first read and whenever the snapshot cannot be composed, `Ready` with the
/// snapshot otherwise, signed in or not.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Availability {
    Unavailable,
    Ready,
}

/// The account beside the snapshot while nobody is signed in: there is no
/// profile, so no Google sign-in either.
fn no_account() -> Google {
    Google {
        state: Some(GoogleState::SignedOut),
        email: None,
        drive_folder_id: None,
        stage: GoogleStage::Idle,
        failure: None,
    }
}

/// The account beside the snapshot while the signed-in profile's runtime or
/// session does not answer: it is the profile's, but it cannot be read now.
fn unread_account() -> Google {
    Google {
        state: Some(GoogleState::Unknown),
        email: None,
        drive_folder_id: None,
        stage: GoogleStage::Idle,
        failure: None,
    }
}

/// Why setup is shown apart from the held person session.
#[derive(Clone, Copy, Debug)]
enum Apart {
    /// Nobody is signed in: there is no account, and what is a profile's is
    /// refused as not signed in.
    SignedOut,
    /// A profile is signed in but its runtime or held session does not answer,
    /// for the stable `reason` named; what is the profile's is refused as
    /// `unavailable`.
    Unanswered(&'static str),
}

impl Apart {
    fn account(self) -> Google {
        match self {
            Self::SignedOut => no_account(),
            Self::Unanswered(_) => unread_account(),
        }
    }

    /// What a profile's request is refused with.
    fn refusal(self) -> Stop {
        match self {
            Self::SignedOut => Refusal::NotSignedIn.into(),
            Self::Unanswered(reason) => Stop::unavailable(reason),
        }
    }

    /// The failure diagnostics keep while this lasts.
    fn cause(self) -> Option<Stop> {
        match self {
            Self::SignedOut => None,
            Self::Unanswered(reason) => Some(Stop::unavailable(reason)),
        }
    }
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
        runs: engine.runs,
        google,
        details: engine.details,
    };
    snapshot.valid().then_some(snapshot)
}

/// What the profile's held session carries apart from the engine: its Google account.
fn account_act(request: &Action) -> bool {
    matches!(request, Action::GoogleSignIn | Action::GoogleSignOut)
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
        let components = Components::new(
            components::installation(),
            Arc::new(Admission::new(agent)),
            diagnostics.clone(),
        );
        Self::with_components(sign_in, components, diagnostics)
    }

    fn with_components(
        sign_in: Arc<SignIn>,
        components: Components,
        diagnostics: Arc<Diagnostics>,
    ) -> Self {
        Self {
            sign_in,
            components,
            reports: Reports::new(diagnostics),
            current: Mutex::new(Current {
                value: DesktopSetup {
                    revision: 0,
                    state: Availability::Unavailable,
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
                item,
                resume,
                download,
            } => {
                self.components
                    .start(*item, *resume, download.clone())
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
            Action::Remove(removal) => self.components.remove(*removal).await,
        }
    }

    /// Carry one setup action to the engine and the account's part of it to
    /// the held session of the signed-in profile, then publish the snapshot
    /// after it. Signed out, or signed in while the runtime or its session does
    /// not answer, the engine still carries it, and what is a profile's is
    /// refused (`apart`). Whatever lay behind an `unavailable` refusal or a host
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
                return self.apart(&request, action, Apart::SignedOut).await;
            }
            Standing::Unready => {
                return self
                    .apart(
                        &request,
                        action,
                        Apart::Unanswered("setup_runtime_not_ready"),
                    )
                    .await;
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
            // The account read was another session's: the engine's side stays
            // shown, and the next sign-in cue reads the account again.
            self.release_person().await?;
            let apart = match standing(&after) {
                Ok(Standing::SignedOut) => Apart::SignedOut,
                _ => Apart::Unanswered("setup_session_changed"),
            };
            let refused = refused.or_else(|| account_act(&request).then(|| apart.refusal()));
            return self.display(action, apart.account(), refused, apart.cause());
        }
        let google = match answered {
            Ok(google) => google,
            Err(Stop::Host(error)) => {
                // A lost bridge shows no account as if it were current; the
                // engine's side, its live runs included, stays shown.
                let refused =
                    refused.or_else(|| account_act(&request).then(|| Stop::Host(error.clone())));
                return self.display(action, unread_account(), refused, Some(Stop::Host(error)));
            }
            Err(stop) => return Err(stop),
        };
        self.show(action, google, refused)
    }

    /// What a profile is needed for: its Google account, and a model its person's
    /// local model list admits, downloaded or removed, the removal of the local AI
    /// with the listed models included.
    fn profile_bound(&self, request: &Action) -> bool {
        match request {
            Action::GoogleSignIn
            | Action::GoogleSignOut
            | Action::RemoveModel { .. }
            | Action::Remove(Removal::LocalAi) => true,
            Action::Start {
                item,
                resume,
                download,
            } => self.components.downloads(*item, *resume, download.as_ref()),
            Action::Observe
            | Action::Check(_)
            | Action::Verify(_)
            | Action::Answer { .. }
            | Action::Cancel { .. }
            | Action::Remove(Removal::Browser | Removal::LocalAiProgram) => false,
        }
    }

    /// Apart from the held session: the engine carries what is this
    /// installation's and the snapshot is shown beside the account `apart`
    /// names; what is a profile's is refused as `apart` says.
    async fn apart(
        &self,
        request: &Action,
        action: bool,
        apart: Apart,
    ) -> std::result::Result<DesktopSetup, Stop> {
        let refused = if self.profile_bound(request) {
            Some(apart.refusal())
        } else {
            self.act(request).await.err()
        };
        self.display(action, apart.account(), refused, apart.cause())
    }

    /// Publishes the engine's side beside `google`, kept as the account the engine's
    /// own changes are shown beside, and answers with what the engine `refused`.
    fn show(
        &self,
        action: bool,
        google: Google,
        refused: Option<Stop>,
    ) -> std::result::Result<DesktopSetup, Stop> {
        self.display(action, google, refused, None)
    }

    /// As [`SetupHost::show`], while `cause` keeps the account from being read: a
    /// read records it, and nothing ends the run of failures it belongs to.
    fn display(
        &self,
        action: bool,
        google: Google,
        refused: Option<Stop>,
        cause: Option<Stop>,
    ) -> std::result::Result<DesktopSetup, Stop> {
        *lock(&self.google) = Some(google.clone());
        let Some(snapshot) = compose(self.components.view(), google) else {
            self.publish(Availability::Unavailable, None);
            return self.shown(action, Stop::Host(snapshot_invalid()));
        };
        let value = self.publish(Availability::Ready, Some(snapshot));
        match cause {
            None => self.reports.recovered(),
            Some(cause) if !action => self.reports.read(&cause),
            // A command records its own refusal with its answer.
            Some(_) => {}
        }
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
        desktop_setup_read,
        desktop_setup_check,
        desktop_setup_verify,
        desktop_setup_start,
        desktop_setup_answer,
        desktop_setup_cancel,
        desktop_setup_remove_model,
        desktop_setup_remove,
        desktop_google_sign_in,
        desktop_google_sign_out,
        desktop_setup_observe,
        desktop_setup_unobserve
    ]
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
    item: String,
    resume: bool,
    download: Option<wire::ModelDownload>,
) -> std::result::Result<DesktopSetup, CommandFailure> {
    host.exchange(wire::start_request(&item, resume, download)?, true)
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

/// Removes the browser, or the local AI or its program alone, from this computer.
#[tauri::command]
async fn desktop_setup_remove(
    host: State<'_, Arc<SetupHost>>,
    removal: wire::Removal,
) -> std::result::Result<DesktopSetup, CommandFailure> {
    host.exchange(wire::remove_request(removal), true).await
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
            "check": null, "runs": [],
            "google": {"state": null, "email": null, "drive_folder_id": null, "stage": "idle", "failure": null},
            "details": details,
        }))
        .unwrap()
    }

    fn current(listener: Option<Channel<DesktopSetup>>) -> Current {
        Current {
            value: DesktopSetup {
                revision: 0,
                state: Availability::Unavailable,
                snapshot: None,
            },
            listener,
        }
    }

    #[test]
    fn revisions_follow_changes_only() {
        let mut current = current(None);
        assert_eq!(current.update(Availability::Unavailable, None).revision, 0);
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
        current.update(Availability::Unavailable, None);
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
            runs: Vec::new(),
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
        assert!(compose(view(), no_account()).is_some());
        assert!(compose(view(), unread_account()).is_some());
    }

    /// Signed out, or signed in while the runtime does not answer, against a
    /// real engine of a throwaway installation: the window's host is driven
    /// through its branch apart from the session, which reads none, so the
    /// sign-in it is built with is never consulted.
    mod signed_out {
        use super::super::admission::tests::{GB, LOCAL, Replies, VISION, requested};
        use super::super::components::tests::{Fixture, Serving, serving, window};
        use super::*;
        use cadrumo_application::provisioning::test_servers::Released;
        use wire::{Decision, RunStage};

        fn host(components: Components) -> SetupHost {
            SetupHost::with_components(
                Arc::new(SignIn::new(&crate::terminal::tests::unit_launch())),
                components,
                Arc::default(),
            )
        }

        /// Signed in, with a runtime that does not answer.
        const UNANSWERED: Apart = Apart::Unanswered("setup_runtime_not_ready");

        impl SetupHost {
            async fn signed_out(
                &self,
                request: &Action,
                action: bool,
            ) -> std::result::Result<DesktopSetup, Stop> {
                self.apart(request, action, Apart::SignedOut).await
            }
        }

        /// What a read apart from the session shows once `done` holds of its snapshot.
        async fn shown_until(
            host: &SetupHost,
            apart: Apart,
            done: impl Fn(&Snapshot) -> bool,
        ) -> DesktopSetup {
            let mut changes = host.components.changes();
            loop {
                let shown = host
                    .apart(&Action::Observe, false, apart)
                    .await
                    .expect("a read apart from the session is served");
                if shown.snapshot.as_ref().is_some_and(&done) {
                    return shown;
                }
                changes.changed().await.expect("the engine is alive");
            }
        }

        fn browser_run(shown: &DesktopSetup) -> wire::Run {
            shown
                .snapshot
                .as_ref()
                .and_then(|snapshot| snapshot.runs.first())
                .cloned()
                .expect("the browser's setup is shown")
        }

        fn start_browser() -> Action {
            Action::Start {
                item: ItemId::Browser,
                resume: false,
                download: None,
            }
        }

        fn refused(answer: std::result::Result<DesktopSetup, Stop>) -> Option<Refusal> {
            answer.err().and_then(|stop| stop.refusal())
        }

        #[tokio::test]
        async fn the_engine_serves_this_installations_rows_beside_no_account() {
            let fixture = Fixture::new(Serving::Whole);
            let host = host(window(&fixture));
            let shown = shown_until(&host, Apart::SignedOut, |snapshot| {
                !snapshot.rows.is_empty()
            })
            .await;
            assert_eq!(shown.state, Availability::Ready);
            let snapshot = shown.snapshot.expect("a snapshot");
            let items: Vec<&str> = snapshot.rows.iter().map(|row| row.item.as_str()).collect();
            assert_eq!(items, ["browser", "local_ai"]);
            assert_eq!(snapshot.rows[0].recovery, Some(wire::Recovery::SetUp));
            assert_eq!(snapshot.google, no_account());
            // A full check is the installation's too.
            host.signed_out(&Action::Check(wire::CheckMode::Full), true)
                .await
                .expect("a check is served signed out");
            host.close().await.unwrap();
        }

        #[tokio::test]
        async fn the_browser_is_started_answered_and_cancelled_and_a_sign_in_keeps_its_run() {
            let gate = Arc::new(Released::default());
            let fixture = Fixture::new(Serving::Gated(gate.clone()));
            let host = host(window(&fixture));

            // A plan waiting for its answer is declined by a cancel.
            let asked = browser_run(&host.signed_out(&start_browser(), true).await.unwrap());
            assert_eq!(asked.stage, RunStage::Review);
            host.signed_out(
                &Action::Cancel {
                    operation_id: asked.operation_id.clone(),
                },
                true,
            )
            .await
            .unwrap();
            let declined = shown_until(&host, Apart::SignedOut, |snapshot| {
                snapshot
                    .runs
                    .first()
                    .is_some_and(|run| run.stage == RunStage::Settled)
            })
            .await;
            assert_eq!(
                browser_run(&declined).outcome,
                Some(wire::Outcome::Cancelled)
            );
            assert_eq!(fixture.downloads(), 0);

            // Approved, it runs, held at the gate halfway through its archive.
            let asked = browser_run(&host.signed_out(&start_browser(), true).await.unwrap());
            let review = asked.review.clone().expect("a plan under review");
            host.signed_out(
                &Action::Answer {
                    operation_id: asked.operation_id.clone(),
                    plan_digest: review.plan_digest,
                    decision: Decision::Apply,
                },
                true,
            )
            .await
            .unwrap();
            let running = shown_until(&host, Apart::SignedOut, |snapshot| {
                snapshot
                    .runs
                    .first()
                    .is_some_and(|run| run.items.iter().any(|item| item.completed.is_some()))
            })
            .await;
            assert_eq!(browser_run(&running).stage, RunStage::Running);

            // A sign-in shows the same run beside the account, at a later revision.
            let account = Google {
                state: Some(GoogleState::SignedIn),
                email: Some("person@example.com".into()),
                drive_folder_id: None,
                stage: GoogleStage::Idle,
                failure: None,
            };
            let signed_in = host.show(false, account.clone(), None).unwrap();
            assert!(signed_in.revision > running.revision);
            let kept = browser_run(&signed_in);
            assert_eq!(
                (kept.operation_id.as_str(), kept.stage),
                (asked.operation_id.as_str(), RunStage::Running)
            );
            assert_eq!(signed_in.snapshot.as_ref().unwrap().google, account);

            // Signed out again, it is cancelled; the run settles where it was shown.
            host.signed_out(
                &Action::Cancel {
                    operation_id: asked.operation_id.clone(),
                },
                true,
            )
            .await
            .unwrap();
            gate.release();
            let settled = shown_until(&host, Apart::SignedOut, |snapshot| {
                snapshot
                    .runs
                    .first()
                    .is_some_and(|run| run.stage == RunStage::Settled)
            })
            .await;
            assert!(settled.revision > signed_in.revision);
            let run = browser_run(&settled);
            assert_eq!(
                (run.operation_id.as_str(), run.outcome),
                (asked.operation_id.as_str(), Some(wire::Outcome::Cancelled))
            );
            assert_eq!(settled.snapshot.unwrap().google, no_account());
            host.close().await.unwrap();
        }

        #[tokio::test]
        async fn what_the_persons_model_list_admits_is_refused_and_consults_no_service() {
            let fixture = Fixture::new(Serving::Whole);
            // A service that would admit the model: signed out it is never asked.
            let (components, replies) = serving(
                &fixture,
                Replies::serving(&[VISION], &[], &[(VISION, Some(GB))]),
            );
            let host = host(components);
            for (name, request) in [
                (
                    "a model download",
                    Action::Start {
                        item: ItemId::LocalAi,
                        resume: false,
                        download: Some(requested(LOCAL, VISION)),
                    },
                ),
                (
                    "a model removal",
                    Action::RemoveModel {
                        model: VISION.into(),
                    },
                ),
                (
                    "the local AI with its models",
                    Action::Remove(Removal::LocalAi),
                ),
                ("a Google sign-in", Action::GoogleSignIn),
                ("a Google sign-out", Action::GoogleSignOut),
            ] {
                let answer = host.signed_out(&request, true).await;
                assert_eq!(refused(answer), Some(Refusal::NotSignedIn), "{name}");
                let shown = lock(&host.current).value.clone();
                assert_eq!(
                    shown.state,
                    Availability::Ready,
                    "{name}: setup stays shown"
                );
                assert!(
                    shown.snapshot.unwrap().runs.is_empty(),
                    "{name}: nothing runs"
                );
            }
            assert!(replies.asked().is_empty(), "{:?}", replies.asked());
            assert_eq!(fixture.downloads(), 0);
            // A setup of the program alone is the installation's, not the person's.
            assert!(!host.profile_bound(&Action::Start {
                item: ItemId::LocalAi,
                resume: true,
                download: None,
            }));
            assert!(!host.profile_bound(&Action::Remove(Removal::LocalAiProgram)));
            host.close().await.unwrap();
        }

        fn running(snapshot: &Snapshot) -> bool {
            snapshot
                .runs
                .first()
                .is_some_and(|run| run.items.iter().any(|item| item.completed.is_some()))
        }

        #[tokio::test]
        async fn signed_in_with_no_runtime_the_engine_serves_rows_and_runs() {
            let gate = Arc::new(Released::default());
            let fixture = Fixture::new(Serving::Gated(gate.clone()));
            let (components, replies) = serving(
                &fixture,
                Replies::serving(&[VISION], &[], &[(VISION, Some(GB))]),
            );
            let host = host(components);

            let shown = shown_until(&host, UNANSWERED, |snapshot| !snapshot.rows.is_empty()).await;
            assert_eq!(shown.state, Availability::Ready);
            let snapshot = shown.snapshot.clone().expect("a snapshot");
            let items: Vec<&str> = snapshot.rows.iter().map(|row| row.item.as_str()).collect();
            assert_eq!(items, ["browser", "local_ai"]);
            assert_eq!(snapshot.rows[0].recovery, Some(wire::Recovery::SetUp));
            assert_eq!(snapshot.google, unread_account());
            host.apart(&Action::Check(wire::CheckMode::Full), true, UNANSWERED)
                .await
                .expect("a check is served without the runtime");

            // The browser is planned, answered and runs.
            let asked = browser_run(
                &host
                    .apart(&start_browser(), true, UNANSWERED)
                    .await
                    .unwrap(),
            );
            assert_eq!(asked.stage, RunStage::Review);
            let review = asked.review.clone().expect("a plan under review");
            host.apart(
                &Action::Answer {
                    operation_id: asked.operation_id.clone(),
                    plan_digest: review.plan_digest,
                    decision: Decision::Apply,
                },
                true,
                UNANSWERED,
            )
            .await
            .unwrap();
            let underway = shown_until(&host, UNANSWERED, running).await;
            assert_eq!(browser_run(&underway).stage, RunStage::Running);

            // What needs the session is refused as unavailable, asks no service,
            // and leaves the run shown.
            for (name, request) in [
                (
                    "a model download",
                    Action::Start {
                        item: ItemId::LocalAi,
                        resume: false,
                        download: Some(requested(LOCAL, VISION)),
                    },
                ),
                (
                    "a model removal",
                    Action::RemoveModel {
                        model: VISION.into(),
                    },
                ),
                (
                    "the local AI with its models",
                    Action::Remove(Removal::LocalAi),
                ),
                ("a Google sign-in", Action::GoogleSignIn),
                ("a Google sign-out", Action::GoogleSignOut),
            ] {
                let answer = host.apart(&request, true, UNANSWERED).await;
                assert_eq!(refused(answer), Some(Refusal::Unavailable), "{name}");
                let shown = lock(&host.current).value.clone();
                assert_eq!(
                    shown.state,
                    Availability::Ready,
                    "{name}: setup stays shown"
                );
                let kept = browser_run(&shown);
                assert_eq!(
                    (kept.operation_id.as_str(), kept.stage),
                    (asked.operation_id.as_str(), RunStage::Running),
                    "{name}: the run stays shown"
                );
            }
            assert!(replies.asked().is_empty(), "{:?}", replies.asked());

            // The runtime comes back: the account is read beside the same run.
            let account = Google {
                state: Some(GoogleState::SignedIn),
                email: Some("person@example.com".into()),
                drive_folder_id: None,
                stage: GoogleStage::Idle,
                failure: None,
            };
            let back = host.show(false, account.clone(), None).unwrap();
            assert!(back.revision > underway.revision);
            assert_eq!(back.state, Availability::Ready);
            let kept = browser_run(&back);
            assert_eq!(
                (kept.operation_id.as_str(), kept.stage),
                (asked.operation_id.as_str(), RunStage::Running)
            );
            assert_eq!(back.snapshot.as_ref().unwrap().google, account);

            // Lost again, the run is cancelled without the runtime and settles.
            host.apart(
                &Action::Cancel {
                    operation_id: asked.operation_id.clone(),
                },
                true,
                UNANSWERED,
            )
            .await
            .unwrap();
            gate.release();
            let settled = shown_until(&host, UNANSWERED, |snapshot| {
                snapshot
                    .runs
                    .first()
                    .is_some_and(|run| run.stage == RunStage::Settled)
            })
            .await;
            assert!(settled.revision > back.revision);
            let run = browser_run(&settled);
            assert_eq!(
                (run.operation_id.as_str(), run.outcome),
                (asked.operation_id.as_str(), Some(wire::Outcome::Cancelled))
            );
            assert_eq!(settled.snapshot.unwrap().google, unread_account());
            host.close().await.unwrap();
        }
    }
}
