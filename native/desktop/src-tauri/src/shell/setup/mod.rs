//! Component setup through the held person session: status reads, setup and
//! its plan review and cancellation; and, riding the same session but apart
//! from setup, the profile's Google account: its stored sign-in, sign-in and
//! sign-out. The window names items and choices only. This host submits the product's registered operations
//! through the session's generic relay and keeps what only this window knows
//! (`track`). An observed operation pushes a cue on the bridge; this host then
//! reads the setup again and pushes the typed snapshot on the window's
//! channel. Nothing polls.
pub mod track;
pub mod wire;

use super::sign_in::{Presence, SignIn};
use crate::agent::person::{HeldPerson, PersonEvent};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use serde::Serialize;
use serde_json::Value;
use std::sync::{
    Arc, Mutex,
    atomic::{AtomicBool, Ordering},
};
use tauri::{State, ipc::Channel};
use track::{Relay, Stop, Tracker};
use wire::{Action, CommandFailure, Refusal, Snapshot};

fn failed() -> ApplicationError {
    ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
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

/// The held person bridge as the tracker's relay.
struct PersonRelay(HeldPerson);

impl Relay for PersonRelay {
    fn call(&mut self, request: Value) -> Result<Value> {
        // Each exchange retains correlation and session authority. Do not hold
        // the bridge across an entire setup snapshot: service admission and
        // person activity must be able to run between its independent reads.
        lock(&self.0).exchange(request)
    }
}

pub struct SetupHost {
    sign_in: Arc<SignIn>,
    current: Mutex<Current>,
    person: Arc<Mutex<Option<HeldPerson>>>,
    tracker: Arc<Mutex<Option<Tracker>>>,
    operation: tokio::sync::Mutex<()>,
    worker: Mutex<Option<tokio::task::JoinHandle<()>>>,
    closed: AtomicBool,
    wake: tokio::sync::Notify,
}

impl SetupHost {
    pub fn new(sign_in: Arc<SignIn>) -> Self {
        Self {
            sign_in,
            current: Mutex::new(Current {
                value: DesktopSetup {
                    revision: 0,
                    state: Availability::SignedOut,
                    snapshot: None,
                },
                listener: None,
            }),
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

    /// Carry one setup action to the held session of the signed-in profile and
    /// publish the snapshot after it. Signed out, an action is refused and a
    /// read answers the signed-out state.
    async fn exchange(
        &self,
        request: Action,
        action: bool,
    ) -> std::result::Result<DesktopSetup, CommandFailure> {
        let _operation = self.operation.lock().await;
        if self.closed.load(Ordering::Acquire) {
            return Err(failed().into());
        }
        let status = self.sign_in.read_status().await?;
        if status.state != Presence::Present {
            if status.supported && status.state == Presence::Unknown {
                return Err(failed().into());
            }
            self.release_person().await?;
            let value = self.publish(Availability::SignedOut, None);
            return if action {
                Err(Refusal::NotSignedIn.into())
            } else {
                Ok(value)
            };
        }
        let profile = status.active_profile.clone().ok_or_else(failed)?;
        if !status.runtime_ready() {
            let value = self.publish(Availability::Unavailable, None);
            return if action {
                Err(Refusal::Unavailable.into())
            } else {
                Ok(value)
            };
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
            // Another held session's operations are not this window's to follow.
            let tracked = match followed.take() {
                Some(tracked) if tracked.follows(&identity) => tracked,
                _ => Tracker::new(identity),
            };
            let tracked = followed.insert(tracked);
            let answered = tracked.handle(&mut PersonRelay(person.clone()), request);
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
        if after.state != Presence::Present
            || !after.runtime_ready()
            || after.active_profile.as_deref() != Some(&profile)
        {
            self.release_person().await?;
            self.publish(Availability::Unavailable, None);
            return Err(failed().into());
        }
        match answered {
            Ok(snapshot) => Ok(self.publish(Availability::Ready, Some(snapshot))),
            Err(Stop::Refused(code)) => Err(code.into()),
            Err(Stop::Host(error)) => {
                // A lost bridge keeps no setup on display as if it were current.
                self.publish(Availability::Unavailable, None);
                if action {
                    Err(error.into())
                } else {
                    Ok(lock(&self.current).value.clone())
                }
            }
        }
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
            return Err(failed());
        }
        let subscription = updates.id();
        let mut current = lock(&self.current);
        updates.send(current.value.clone()).map_err(|_| failed())?;
        current.listener = Some(updates);
        drop(current);
        if worker.is_none() {
            let owner = self.clone();
            *worker = Some(tokio::spawn(async move {
                let mut events = owner.sign_in.person_events();
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
                    if lock(&owner.current).listener.is_some() {
                        // A failed read publishes the unavailable state; the next cue reads again.
                        let _ = owner.exchange(Action::Observe, false).await;
                    }
                    tokio::select! {
                        _ = &mut wake => {},
                        () = &mut signed_in => {},
                        () = setup_pushed(&mut events) => {},
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
            worker.await.map_err(|_| failed())?;
        }
        let _operation = self.operation.lock().await;
        self.release_person().await
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
            Ok(PersonEvent::LanguageChanged | PersonEvent::AttendanceChanged) => {}
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
    items: Option<Vec<String>>,
    model: Option<String>,
    resume: bool,
) -> std::result::Result<DesktopSetup, CommandFailure> {
    host.exchange(wire::start_request(items, model, resume)?, true)
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
        let held = Arc::new(Mutex::new(Person::hold(command, &profile).unwrap()));
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
            "google": {"state": null, "email": null, "stage": "idle", "failure": null, "sentence": null},
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
}
