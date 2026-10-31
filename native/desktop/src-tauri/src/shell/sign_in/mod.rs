//! The window's sign-in: the selected profile signs in on the window's own
//! runtime connection, which then holds the person's session; profile
//! creation and listing run canonical CLI invocations; one pushed status
//! observation follows every change.
mod observation;
#[cfg(all(test, windows))]
mod opening_tests;
mod password;
mod profiles;
mod watch;
// The child runner and the envelope decoder are also the provider settings'
// channel: one set of lanes, one deadline, one output bound, one settlement.
pub(crate) mod process;
pub(crate) mod wire;
use observation::{
    __cmd__sign_in_subscribe, __cmd__sign_in_unsubscribe, __tauri_command_name_sign_in_subscribe,
    __tauri_command_name_sign_in_unsubscribe, sign_in_subscribe, sign_in_unsubscribe,
};
use password::{
    __cmd__profile_password_change, __tauri_command_name_profile_password_change,
    profile_password_change,
};
use profiles::{
    __cmd__profile_delete, __cmd__profile_delete_review, __tauri_command_name_profile_delete,
    __tauri_command_name_profile_delete_review, profile_delete, profile_delete_review,
};

use crate::agent::recovery::Custody;
use crate::environment::Launch;
use cadrumo_application::{
    binary::{self, BinaryExpectation},
    child::ChildConfiguration,
    diagnostics::helper::{HelperExecutable, HelperIdentity},
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    package::PackageManifest,
    role::Role,
    value::RelativePath,
};
use serde::Deserialize;
use std::{collections::BTreeMap, sync::Arc};
use tauri::{
    State,
    http::HeaderMap,
    ipc::{InvokeBody, Request},
};
use zeroize::Zeroizing;

use process::Children;
pub(crate) use wire::Presence;
use wire::{ProfileCreateResult, ProfileList, SignInResult, SignInStatus, SignOutResult};

/// Why the window could not sign in on its own connection.
enum NativeSignIn {
    /// The runtime refused the sign-in itself, as the command line would report it.
    Refused(wire::Refusal),
    /// No native session is possible here: the runtime does not admit the
    /// window as the holder, or cannot be reached natively.
    Unavailable(ApplicationError),
}

impl NativeSignIn {
    /// Reads the runtime's answer to a sign-in it did not admit. Among the
    /// refusals that are not its own: the runtime does not admit this process
    /// as the desktop holder.
    fn from_refusal(refusal: cadrumo_application::runtime_client::Refusal) -> Self {
        use cadrumo_application::runtime_client::Refusal;

        match refusal {
            Refusal::Timeout => Self::Refused(wire::Refusal {
                code: "RUNTIME_TIMEOUT".into(),
                retry_after_seconds: None,
            }),
            refusal @ Refusal::Denied { .. } if refusal.code() != "runtime_peer_untrusted" => {
                match wire::sign_in_refusal(
                    refusal.code(),
                    refusal.sign_in_reason(),
                    refusal.remaining_seconds(),
                ) {
                    Ok(refusal) => Self::Refused(refusal),
                    Err(error) => Self::Unavailable(error),
                }
            }
            refusal => Self::Unavailable(
                failure(ErrorCode::SessionUnavailable)
                    .with_reason("native_sign_in_unavailable")
                    .caused_by(refusal),
            ),
        }
    }
}

/// The public acknowledgement of a sign-in the window holds for `active`.
fn signed_in(active: String) -> SignInResult {
    SignInResult::SignedIn {
        status: SignInStatus {
            supported: true,
            state: Presence::Present,
            active_profile: Some(active),
            runtime_available: true,
            reconnecting: None,
            refusal: None,
        },
    }
}

/// The header that names a profile by its label, percent-encoded as UTF-8:
/// a header carries no other text, and the body is the password alone.
const PROFILE_HEADER: &str = "x-cadrumo-profile";
/// The product's own bound on a profile label, in characters.
const LABEL_LIMIT: usize = 160;
/// Characters the product's command line rewrites in an argument on Windows,
/// after the option terminator too: it expands environment variables and
/// file-name patterns before it reads its arguments. Asked directly, a
/// package created `%USERNAME% y Cia` as the user's name followed by "y Cia"
/// and `Taller [2025]` as the name of a file beside it. A label holding one
/// would name another profile, so it is not passed at all.
pub(crate) const REWRITTEN: [char; 5] = ['*', '?', '[', '%', '$'];

/// One command under `config`: its words, the name its answer must carry,
/// whether it only reads, its owning image, and its enrollment deadline.
struct Call {
    words: &'static [&'static str],
    leaf: &'static str,
    reads: bool,
    runtime: bool,
    slow: bool,
    command: &'static str,
}
#[cfg(test)]
const LOGIN: Call = Call {
    words: &["login"],
    leaf: "login",
    command: "config.login",
    reads: false,
    runtime: false,
    slow: false,
};
const LOGOUT: Call = Call {
    words: &["logout"],
    leaf: "logout",
    command: "config.logout",
    reads: false,
    runtime: false,
    slow: false,
};
const LIST: Call = Call {
    words: &["profile", "list"],
    leaf: "profile.list",
    command: "config.profile.list",
    reads: true,
    runtime: false,
    slow: false,
};
const CREATE: Call = Call {
    words: &["profile", "create", "--quiet"],
    leaf: "profile.create",
    command: "config.profile.create",
    reads: false,
    runtime: false,
    slow: true,
};

fn failure(code: ErrorCode) -> ApplicationError {
    ApplicationError::new(code, Operation::Cli)
}

#[derive(Deserialize)]
struct Contract {
    layout: Layout,
}
#[derive(Deserialize)]
struct Layout {
    paths: Paths,
    files: Files,
    entrypoints: BTreeMap<String, String>,
    entrypoint_suffix: String,
}
#[derive(Deserialize)]
struct Paths {
    native: RelativePath,
}
#[derive(Deserialize)]
struct Files {
    package_manifest: RelativePath,
}

pub struct SignIn {
    child: Result<ChildConfiguration>,
    runtime: Result<ChildConfiguration>,
    /// What the window's own runtime connections are made from.
    native: Result<watch::Native>,
    service: Result<ChildConfiguration>,
    pub children: Arc<Children>,
    observation: observation::Observer,
    watch: watch::Watch,
    // The one person session this window holds; each consumer keeps it alive
    // only while it uses it.
    person: std::sync::Mutex<std::sync::Weak<std::sync::Mutex<crate::agent::person::Person>>>,
    // The session the window's own sign-in opened, kept until a resumed
    // session replaces it or the person signs out, so none is resumed twice.
    signed_in: std::sync::Mutex<Option<crate::agent::person::HeldPerson>>,
    // What every person session of this window was pushed, whichever is held.
    person_events: crate::agent::person::PersonEvents,
    // Whether the session held waits for a fresh proof after the profile's
    // worker was lost, as the connection that holds it reports it.
    custody: Custody,
    closed: std::sync::atomic::AtomicBool,
    lifecycle: std::sync::Mutex<()>,
    signing_in: std::sync::Mutex<Option<Arc<PendingSignIn>>>,
    openings: std::sync::Mutex<
        Vec<std::sync::Weak<cadrumo_application::runtime_client::OpenCancellation>>,
    >,
}

struct PendingSignIn {
    password: std::sync::Mutex<Zeroizing<Vec<u8>>>,
    complete: std::sync::Mutex<bool>,
    settled: std::sync::Condvar,
}

impl PendingSignIn {
    fn wait(&self) {
        let mut complete = self.complete.lock().unwrap_or_else(|e| e.into_inner());
        while !*complete {
            complete = self
                .settled
                .wait(complete)
                .unwrap_or_else(|e| e.into_inner());
        }
    }
}

struct SigningIn<'a>(
    &'a std::sync::Mutex<Option<Arc<PendingSignIn>>>,
    Arc<PendingSignIn>,
);

impl Drop for SigningIn<'_> {
    fn drop(&mut self) {
        *self.1.complete.lock().unwrap_or_else(|e| e.into_inner()) = true;
        self.1.settled.notify_all();
        self.0
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .take();
    }
}

impl SignIn {
    pub fn new(launch: &Launch) -> Self {
        let runtime = resolve_image(launch, "cadrumo-runtime");
        let native = native_runtime(launch);
        Self {
            child: resolve_cli(launch),
            watch: watch::Watch::new(native.clone()),
            native,
            runtime,
            service: resolve_image(launch, "cadrumo-agent-service"),
            children: Arc::new(Children::new(launch.diagnostics.clone())),
            observation: observation::Observer::default(),
            person: std::sync::Mutex::new(std::sync::Weak::new()),
            signed_in: std::sync::Mutex::new(None),
            person_events: tokio::sync::broadcast::channel(16).0,
            custody: Custody::default(),
            closed: std::sync::atomic::AtomicBool::new(false),
            lifecycle: std::sync::Mutex::new(()),
            signing_in: std::sync::Mutex::new(None),
            openings: std::sync::Mutex::new(Vec::new()),
        }
    }

    /// What keeps a session this window holds through a loss of the profile's
    /// worker: the stored sign-in it presents once, and the standing it reports.
    fn recovery(&self) -> Result<crate::agent::recovery::rebind::Recovery> {
        use crate::agent::recovery::rebind::{Recovery, StoredReceipt};

        let native = self.native.as_ref().map_err(Clone::clone)?;
        Ok(Recovery {
            custody: self.custody.clone(),
            proof: Arc::new(StoredReceipt {
                storage_root: native.storage_root.clone(),
            }),
        })
    }

    /// The window's person session for `profile_id`, shared by every consumer
    /// so one person holds one runtime session. A closed session or another
    /// profile's is replaced by resuming the stored sign-in on a fresh
    /// connection of the window's own.
    pub(crate) fn person(&self, profile_id: &str) -> Result<crate::agent::person::HeldPerson> {
        if self.closed.load(std::sync::atomic::Ordering::Acquire) {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        let mut cached = self.person.lock().unwrap_or_else(|e| e.into_inner());
        if let Some(held) = cached.upgrade() {
            let mut person = held.lock().unwrap_or_else(|e| e.into_inner());
            if person.identity["profile_id"] == profile_id && person.is_open() {
                drop(person);
                let _lifecycle = self.lifecycle.lock().unwrap_or_else(|e| e.into_inner());
                if self.closed.load(std::sync::atomic::Ordering::Acquire) {
                    return Err(failure(ErrorCode::SessionUnavailable));
                }
                return Ok(held);
            }
        }
        let mut person = self.resume(profile_id)?;
        let _lifecycle = self.lifecycle.lock().unwrap_or_else(|e| e.into_inner());
        if self.closed.load(std::sync::atomic::Ordering::Acquire) {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        person.observe_events(self.person_events.clone())?;
        let held = Arc::new(std::sync::Mutex::new(person));
        *cached = Arc::downgrade(&held);
        *self.signed_in.lock().unwrap_or_else(|e| e.into_inner()) = None;
        Ok(held)
    }

    /// Signs the selected profile in on the window's own connection, storing
    /// the sign-in for the TUI and the command line, and keeps that session as
    /// the window's person session. Named profiles are resolved by the runtime,
    /// even before this window has received its first status observation.
    fn sign_in(&self, label: Option<&str>, password: Zeroizing<Vec<u8>>) -> Result<SignInResult> {
        use cadrumo_application::runtime_client::TimeoutWait;

        let waiting = TimeoutWait::new();
        if self.closed.load(std::sync::atomic::Ordering::Acquire) {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        macro_rules! native {
            ($exchange:expr) => {
                match $exchange {
                    Ok(value) => value,
                    Err(refusal) => {
                        return match NativeSignIn::from_refusal(refusal) {
                            NativeSignIn::Refused(refusal) => Ok(SignInResult::Refused { refusal }),
                            NativeSignIn::Unavailable(error) => Err(error),
                        };
                    }
                }
            };
        }
        let pending_sign_in = Arc::new(PendingSignIn {
            password: std::sync::Mutex::new(password),
            complete: std::sync::Mutex::new(false),
            settled: std::sync::Condvar::new(),
        });
        {
            let mut pending = self
                .signing_in
                .lock()
                .unwrap_or_else(|error| error.into_inner());
            if self.closed.load(std::sync::atomic::Ordering::Acquire) || pending.is_some() {
                return Err(failure(ErrorCode::CliBusy).with_reason("sign_in_in_progress"));
            }
            *pending = Some(pending_sign_in.clone());
        }
        let _signing_in = SigningIn(&self.signing_in, pending_sign_in.clone());
        let connection = native!(self.connect(waiting.deadline()));
        let target = match label {
            Some(label) => label.to_owned(),
            None => native!(connection.active_profile(false, waiting.deadline()))
                .selected_profile_id
                .ok_or_else(|| {
                    failure(ErrorCode::ReadFailed).with_reason("profile_identity_absent")
                })?,
        };
        let (profile_id, active) = native!(connection.login_target(&target, waiting.deadline()))
            .ok_or_else(|| failure(ErrorCode::ReadFailed).with_reason("profile_identity_absent"))?;
        let _mutation = self.watch.mutation();
        let password = pending_sign_in
            .password
            .lock()
            .unwrap_or_else(|error| error.into_inner());
        if self.closed.load(std::sync::atomic::Ordering::Acquire) {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        if let Some(rebound) = self.rebind_held(&profile_id, &password) {
            let _lifecycle = self.lifecycle.lock().unwrap_or_else(|e| e.into_inner());
            if self.closed.load(std::sync::atomic::Ordering::Acquire) {
                return Err(failure(ErrorCode::SessionUnavailable));
            }
            return match rebound {
                Ok(()) => Ok(signed_in(active)),
                Err(NativeSignIn::Refused(refusal)) => Ok(SignInResult::Refused { refusal }),
                Err(NativeSignIn::Unavailable(error)) => Err(error),
            };
        }
        let mut person =
            match self.native_sign_in(&profile_id, &password, connection, waiting.deadline()) {
                Ok(person) => person,
                Err(NativeSignIn::Refused(refusal)) => {
                    return Ok(SignInResult::Refused { refusal });
                }
                Err(NativeSignIn::Unavailable(error)) => return Err(error),
            };
        if !person.session_persisted() {
            // As the command line answers it: a sign-in no other frontend can
            // resume is refused, and dropping the session here ends it.
            return Ok(SignInResult::Refused {
                refusal: wire::Refusal {
                    code: "session_not_persisted".into(),
                    retry_after_seconds: None,
                },
            });
        }
        person.observe_events(self.person_events.clone())?;
        let held = Arc::new(std::sync::Mutex::new(person));
        let mut cached = self.person.lock().unwrap_or_else(|e| e.into_inner());
        let _lifecycle = self.lifecycle.lock().unwrap_or_else(|e| e.into_inner());
        if self.closed.load(std::sync::atomic::Ordering::Acquire) {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        *cached = Arc::downgrade(&held);
        *self.signed_in.lock().unwrap_or_else(|e| e.into_inner()) = Some(held);
        Ok(signed_in(active))
    }

    /// Brings the session this window holds for `profile_id` back by its
    /// password, on the connection that holds it, while the runtime keeps it
    /// suspended: a password typed on any other connection would sign in
    /// under a new session instead. `None` when no held session waits for
    /// one, and the password signs in afresh.
    fn rebind_held(
        &self,
        profile_id: &str,
        password: &[u8],
    ) -> Option<std::result::Result<(), NativeSignIn>> {
        self.custody.reconnecting()?;
        let held = self
            .person
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .upgrade()?;
        let mut person = held.lock().unwrap_or_else(|e| e.into_inner());
        if person.identity["profile_id"] != profile_id {
            return None;
        }
        Some(
            person
                .rebind_password(password)
                .map_err(NativeSignIn::from_refusal),
        )
    }

    /// Every later push to whichever person session this window holds.
    pub(crate) fn person_events(
        &self,
    ) -> tokio::sync::broadcast::Receiver<crate::agent::person::PersonEvent> {
        self.person_events.subscribe()
    }

    /// Resolves at the next sign-in observation after this call; create it
    /// before reading the status, so an observation meanwhile is not missed.
    pub(crate) fn observation_changed(&self) -> impl Future<Output = ()> + Send + 'static {
        let (watched, waiting) = (self.watch.changed(), self.custody.changed());
        async move {
            tokio::select! {
                () = watched => {},
                () = waiting => {},
            }
        }
    }

    pub(crate) fn runtime(&self) -> Result<ChildConfiguration> {
        self.runtime.clone()
    }
    pub(crate) fn service(&self) -> Result<ChildConfiguration> {
        self.service.clone()
    }

    /// The private identity of the profile `label` names, from the current
    /// observation; another selected profile or a stale observation names none.
    pub(crate) fn profile_id(&self, label: &str) -> Result<String> {
        let observed = self.watch.latest()?;
        if observed.status.active_profile.as_deref() != Some(label) {
            return Err(
                failure(ErrorCode::ReadFailed).with_reason("profile_identity_other_profile")
            );
        }
        observed
            .profile_id
            .ok_or_else(|| failure(ErrorCode::ReadFailed).with_reason("profile_identity_absent"))
    }

    /// The current status if one is already known and fresh; never waits.
    pub(crate) fn current_observation(&self) -> Result<SignInStatus> {
        Ok(self.shown(self.watch.latest()?.status))
    }

    pub(crate) async fn read_status(self: &Arc<Self>) -> Result<SignInStatus> {
        if !supported() {
            return Ok(SignInStatus::unsupported());
        }
        Ok(self.shown(self.watch.current().await?.status))
    }

    /// `status` with what this window knows that the runtime's stored sign-in
    /// does not say: that its own session waits for a fresh proof.
    fn shown(&self, mut status: SignInStatus) -> SignInStatus {
        status.reconnecting = self.custody.reconnecting();
        status
    }

    /// Signal every opening before shutdown joins any dependent owner.
    pub(crate) fn request_stop(&self) {
        {
            let _lifecycle = self.lifecycle.lock().unwrap_or_else(|e| e.into_inner());
            self.closed
                .store(true, std::sync::atomic::Ordering::Release);
        }
        self.watch.request_close();
        for opening in self
            .openings
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .drain(..)
            .filter_map(|owner| owner.upgrade())
        {
            opening.cancel();
        }
        if let Some(pending) = self
            .signing_in
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .as_ref()
            .cloned()
        {
            zeroize::Zeroize::zeroize(
                &mut **pending.password.lock().unwrap_or_else(|e| e.into_inner()),
            );
        }
    }

    pub async fn stop(&self) -> Result<()> {
        self.request_stop();
        self.observation.close();
        let pending = self
            .signing_in
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .as_ref()
            .cloned();
        let children = self.children.clone();
        let result = super::blocking(move || {
            if let Some(pending) = pending {
                pending.wait();
            }
            children.stop()
        })
        .await;
        let joined = self.observation.join().await;
        let watch = self.watch.clone();
        let signed_in = self
            .signed_in
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .take();
        super::blocking(move || {
            // Closing the window's connection ends the session it holds.
            drop(signed_in);
            watch.close();
            Ok(())
        })
        .await?;
        result?;
        joined
    }

    /// The runtime this window's connections reach, and the release it expects there.
    pub(crate) fn runtime_target(
        &self,
    ) -> std::result::Result<
        (
            cadrumo_application::runtime_client::Endpoint,
            cadrumo_application::runtime_client::Cohort,
        ),
        cadrumo_application::runtime_client::Refusal,
    > {
        use cadrumo_application::runtime_client::{Cohort, Endpoint, Refusal};

        let native = self.native.as_ref().map_err(|_| Refusal::Unavailable)?;
        let endpoint = Endpoint::of(&native.storage_root)?;
        let cohort = Cohort {
            product_version: native.product_version.clone(),
            authority_generation: None,
        };
        Ok((endpoint, cohort))
    }

    /// A connection of the window's own to its runtime.
    fn connect(
        &self,
        deadline: std::time::Instant,
    ) -> std::result::Result<
        Arc<cadrumo_application::runtime_client::Connection>,
        cadrumo_application::runtime_client::Refusal,
    > {
        use cadrumo_application::runtime_client::{Connection, OpenCancellation, Refusal};
        let opening = Arc::new(OpenCancellation::new().map_err(Refusal::Io)?);
        {
            let mut owners = self.openings.lock().unwrap_or_else(|e| e.into_inner());
            if self.closed.load(std::sync::atomic::Ordering::Acquire) {
                return Err(Refusal::ConnectionClosed);
            }
            owners.retain(|owner| owner.upgrade().is_some_and(|opening| !opening.cancelled()));
            owners.push(Arc::downgrade(&opening));
        }
        let (endpoint, cohort) = self.runtime_target()?;
        let connection = Arc::new(Connection::open_cancellable(
            &endpoint, &cohort, deadline, opening,
        )?);
        if self.closed.load(std::sync::atomic::Ordering::Acquire) {
            connection.close();
            return Err(Refusal::ConnectionClosed);
        }
        Ok(connection)
    }

    /// Signs `profile_id` in on a connection of the window's own, storing the
    /// sign-in for the other frontends, and holds the session it admits.
    fn native_sign_in(
        &self,
        profile_id: &str,
        password: &[u8],
        connection: Arc<cadrumo_application::runtime_client::Connection>,
        deadline: std::time::Instant,
    ) -> std::result::Result<crate::agent::person::Person, NativeSignIn> {
        use cadrumo_application::runtime_client::Frontend;
        let recovery = self.recovery().map_err(NativeSignIn::Unavailable)?;
        // Subscribed first: a push between the sign-in's reply and the
        // session's router still reaches it.
        let pushed = connection.subscribe_scoped();
        let admitted = connection
            .login_password(profile_id, Frontend::Desktop, password, true, deadline)
            .map_err(NativeSignIn::from_refusal)?;
        let persisted = admitted.session_persisted == Some(true);
        crate::agent::person::Person::native(
            connection,
            pushed,
            admitted,
            Some(persisted),
            recovery,
        )
        .map_err(NativeSignIn::Unavailable)
    }

    /// Resumes the stored sign-in of `profile_id` on a fresh connection of the
    /// window's own, as the desktop frontend, and holds the session it admits.
    fn resume(&self, profile_id: &str) -> Result<crate::agent::person::Person> {
        use cadrumo_application::runtime_client::Frontend;
        let waiting = cadrumo_application::runtime_client::TimeoutWait::new();

        let native = self.native.as_ref().map_err(Clone::clone)?;
        let recovery = self.recovery()?;
        let connection = self.connect(waiting.deadline()).map_err(|refusal| {
            failure(ErrorCode::SessionUnavailable)
                .with_reason("person_resume_unavailable")
                .caused_by(refusal)
        })?;
        let pushed = connection.subscribe_scoped();
        let admitted = connection
            .resume_receipt(
                &native.storage_root,
                profile_id,
                Frontend::Desktop,
                waiting.deadline(),
            )
            .map_err(|refusal| {
                failure(ErrorCode::SessionUnavailable)
                    .with_reason("person_resume_refused")
                    .caused_by(refusal)
            })?;
        crate::agent::person::Person::native(connection, pushed, admitted, None, recovery)
    }

    /// Notes the person's input through the session this window holds, so a
    /// report starts no process and never waits on the credential lanes.
    fn record_activity(&self) -> Result<()> {
        let profile_id =
            self.watch.latest()?.profile_id.ok_or_else(|| {
                failure(ErrorCode::ReadFailed).with_reason("activity_profile_absent")
            })?;
        let held = self.person(&profile_id)?;
        let mut person = held.lock().unwrap_or_else(|e| e.into_inner());
        person.exchange(serde_json::json!({"action": "activity"}))?;
        Ok(())
    }

    /// Signs the person out through the session this window holds or resumes,
    /// or `None` when it can hold none and the command line signs out instead.
    fn window_sign_out(&self) -> Option<SignOutResult> {
        let profile_id = self.watch.latest().ok()?.profile_id?;
        let held = self.person(&profile_id).ok()?;
        let out = held
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .sign_out()
            .ok()?;
        Some(SignOutResult::remaining(
            out.automation_enabled,
            out.automation_access_remains,
        ))
    }

    fn run(
        &self,
        call: &Call,
        label: Option<&str>,
        secret: Option<Zeroizing<Vec<u8>>>,
    ) -> Result<wire::Outcome> {
        wire::decode(call.leaf, &self.output(call, label, secret)?)
    }

    fn output(
        &self,
        call: &Call,
        label: Option<&str>,
        secret: Option<Zeroizing<Vec<u8>>>,
    ) -> Result<process::Output> {
        self.output_with_options(call, label, secret, &[])
    }

    fn output_with_options(
        &self,
        call: &Call,
        label: Option<&str>,
        secret: Option<Zeroizing<Vec<u8>>>,
        options: &[String],
    ) -> Result<process::Output> {
        let _mutation = (!call.reads).then(|| self.watch.mutation());
        let image = if call.runtime {
            &self.runtime
        } else {
            &self.child
        };
        let mut command = image.as_ref().map_err(Clone::clone)?.command();
        command.args(arguments(call, None, secret.is_some()));
        command.args(options);
        if let Some(label) = label {
            command.args(["--", label]);
        }
        let identity = HelperIdentity {
            command: call.command,
            executable: if call.runtime {
                HelperExecutable::Runtime
            } else {
                HelperExecutable::Cli
            },
        };
        if call.reads {
            self.children.read(identity, command)
        } else if call.slow {
            self.children
                .run_within(identity, command, secret, process::TIMEOUT)
        } else {
            self.children.run(identity, command, secret)
        }
    }
}

/// The arguments of one call. A label is the person's own text: it follows
/// the option terminator, so that none of it is read as an option.
fn arguments(call: &Call, label: Option<&str>, secret: bool) -> Vec<String> {
    let mut arguments: Vec<String> = ["--format", "json", "config"]
        .iter()
        .chain(call.words)
        .map(|word| (*word).to_owned())
        .collect();
    if secret {
        arguments.push("--secrets-stdin".to_owned());
    }
    if let Some(label) = label {
        arguments.push("--".to_owned());
        arguments.push(label.to_owned());
    }
    arguments
}

fn resolve_cli(launch: &Launch) -> Result<ChildConfiguration> {
    resolve_image(launch, "aeat")
}

/// What the window's own runtime connection is made from: the storage root it
/// serves and the installed product version the package manifest states.
fn native_runtime(launch: &Launch) -> Result<watch::Native> {
    let contract: Contract =
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json")))
            .map_err(|_| failure(ErrorCode::PackageUnavailable))?;
    let manifest = PackageManifest::read(
        &launch.package_root,
        &contract.layout.files.package_manifest,
    )
    .map_err(|_| failure(ErrorCode::PackageUnavailable))?;
    let product_version = manifest
        .distributions
        .get("cadrumo")
        .filter(|version| !version.is_empty())
        .ok_or_else(|| failure(ErrorCode::PackageUnavailable))?;
    Ok(watch::Native {
        storage_root: launch.working_directory.clone(),
        product_version: product_version.clone(),
    })
}

fn resolve_image(launch: &Launch, entrypoint: &str) -> Result<ChildConfiguration> {
    let contract: Contract =
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json")))
            .map_err(|_| failure(ErrorCode::PackageUnavailable))?;
    let layout = contract.layout;
    if !layout.entrypoints.contains_key(entrypoint) {
        return Err(failure(ErrorCode::PackageUnavailable));
    }
    // The desktop runs a console script that a role hosts as that role of its own
    // binary, so the helper stays in the window's process tree.
    let role = Role::hosting(entrypoint).filter(|_| cfg!(windows));
    let relative = match role {
        Some(_) => RelativePath::new(format!("cadrumo{}", std::env::consts::EXE_SUFFIX)),
        None => RelativePath::new(format!(
            "{}/{}{}",
            layout.paths.native.as_str(),
            entrypoint,
            layout.entrypoint_suffix
        )),
    }
    .map_err(|_| failure(ErrorCode::PackageUnavailable))?;
    let manifest = PackageManifest::read(&launch.package_root, &layout.files.package_manifest)
        .map_err(|_| failure(ErrorCode::PackageUnavailable))?;
    let digest = manifest
        .files
        .get(&relative)
        .ok_or_else(|| failure(ErrorCode::PackageUnavailable))?;
    let executable = relative.under(&launch.package_root);
    binary::verify(
        &executable,
        digest,
        BinaryExpectation::host().map_err(|_| failure(ErrorCode::PackageUnavailable))?,
    )
    .map_err(|_| failure(ErrorCode::PackageUnavailable))?;
    let child = ChildConfiguration::new(
        executable,
        launch.working_directory.clone(),
        launch.child.environment().clone(),
    )
    .map_err(|_| failure(ErrorCode::EnvironmentFailed))?;
    Ok(match role {
        Some(role) => child.in_role(role),
        None => child,
    })
}

// A host whose runtime the native client cannot reach yet must not claim a
// positively observed sign-in.
fn supported() -> bool {
    cfg!(any(windows, target_os = "macos"))
}

pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        sign_in_status,
        sign_in_activity,
        sign_in_subscribe,
        sign_in_unsubscribe,
        sign_in_submit,
        sign_out,
        profile_list,
        profile_create,
        profile_delete_review,
        profile_delete,
        profile_password_change
    ]
}

#[tauri::command]
pub async fn sign_in_activity(
    state: State<'_, Arc<SignIn>>,
) -> std::result::Result<(), wire::CommandFailure> {
    if !supported() {
        return Err(failure(ErrorCode::UnsupportedPlatform).into());
    }
    let state = state.inner().clone();
    super::blocking(move || state.record_activity()).await?;
    Ok(())
}

#[tauri::command]
pub async fn sign_in_status(
    state: State<'_, Arc<SignIn>>,
    manager: State<'_, Arc<crate::manager::ManagerStart>>,
) -> Result<SignInStatus> {
    if !supported() {
        return Ok(SignInStatus::unsupported());
    }
    // Dispatch completion is not runtime readiness. The canonical CLI below
    // remains the only authority on availability and authentication.
    let started = manager.start(false).await;
    status_after_manager(started, state.inner().read_status().await)
}

fn status_after_manager(
    started: Result<crate::manager::StartOutcome>,
    observed: Result<SignInStatus>,
) -> Result<SignInStatus> {
    let status = observed?;
    // A working runtime remains authoritative even if manager dispatch failed.
    // When it is unavailable, retain the preceding startup failure as the cause.
    if !status.runtime_available {
        started?;
    }
    Ok(status)
}

#[tauri::command]
pub async fn sign_in_submit(
    state: State<'_, Arc<SignIn>>,
    request: Request<'_>,
) -> Result<SignInResult> {
    if !supported() {
        return Err(failure(ErrorCode::UnsupportedPlatform));
    }
    // Named, the profile is the one signed in to; unnamed, the product's
    // selected one is.
    let profile = label(request.headers())?;
    let password = password(request.body())?;
    let state = state.inner().clone();
    super::blocking(move || state.sign_in(profile.as_deref(), password)).await
}

/// The profiles on this computer, by label. It needs no password, session or
/// runtime, and it changes nothing.
#[tauri::command]
pub async fn profile_list(
    state: State<'_, Arc<SignIn>>,
) -> std::result::Result<ProfileList, wire::CommandFailure> {
    if !supported() {
        return Err(failure(ErrorCode::UnsupportedPlatform).into());
    }
    let state = state.inner().clone();
    // The sign-in watch lists the profiles with every observation; the command
    // line answers only while no current observation does.
    if let Some(listed) = state
        .watch
        .latest()
        .ok()
        .and_then(|observed| observed.profiles)
    {
        return Ok(listed);
    }
    let output = super::blocking(move || state.output(&LIST, None, None)).await?;
    wire::profiles(&output)
}

/// Creates a profile under the label in the header, with the password in the
/// raw body. One attempt: nothing is retried, and the new profile is left
/// signed out, as the product leaves it.
#[tauri::command]
pub async fn profile_create(
    state: State<'_, Arc<SignIn>>,
    request: Request<'_>,
) -> Result<ProfileCreateResult> {
    if !supported() {
        return Err(failure(ErrorCode::UnsupportedPlatform));
    }
    let name = label(request.headers())?.ok_or_else(|| failure(ErrorCode::InvalidArguments))?;
    let secret = confirmed_secret(request.body())?;
    let state = state.inner().clone();
    super::blocking(move || wire::created(state.run(&CREATE, Some(&name), Some(secret))?)).await
}

#[tauri::command]
pub async fn sign_out(
    state: State<'_, Arc<SignIn>>,
) -> std::result::Result<SignOutResult, wire::CommandFailure> {
    if !supported() {
        return Err(failure(ErrorCode::UnsupportedPlatform).into());
    }
    let state = state.inner().clone();
    let outcome = super::blocking(move || {
        let signed_out = state.window_sign_out();
        *state.signed_in.lock().unwrap_or_else(|e| e.into_inner()) = None;
        if let Some(result) = signed_out {
            return Ok(Err(result));
        }
        state.run(&LOGOUT, None, None).map(Ok)
    })
    .await?;
    match outcome {
        Err(result) => Ok(result),
        Ok(outcome) => wire::logout(outcome),
    }
}

/// The label a call names, or none. Refused unless it is text the product
/// could hold as a label and its command line would read as written: within
/// the bound, without surrounding space or control characters, not led by a
/// hyphen, which is read as an option, nor by a tilde, which is read as a
/// home directory, and free of the characters the command line rewrites.
fn label(headers: &HeaderMap) -> Result<Option<String>> {
    let invalid = || failure(ErrorCode::InvalidArguments);
    let Some(value) = headers.get(PROFILE_HEADER) else {
        return Ok(None);
    };
    let mut rest = value.to_str().map_err(|_| invalid())?.as_bytes();
    let mut bytes = Vec::with_capacity(rest.len());
    while let [first, tail @ ..] = rest {
        if *first == b'%' {
            let [high, low, after @ ..] = tail else {
                return Err(invalid());
            };
            let digit = |byte: u8| char::from(byte).to_digit(16).ok_or_else(invalid);
            bytes.push(u8::try_from(digit(*high)? * 16 + digit(*low)?).map_err(|_| invalid())?);
            rest = after;
        } else {
            bytes.push(*first);
            rest = tail;
        }
    }
    let label = String::from_utf8(bytes).map_err(|_| invalid())?;
    let length = label.chars().count();
    if length == 0
        || length > LABEL_LIMIT
        || label != label.trim()
        || label.starts_with('-')
        || label.starts_with('~')
        || label
            .chars()
            .any(|c| c.is_control() || REWRITTEN.contains(&c))
    {
        return Err(invalid());
    }
    Ok(Some(label))
}

/// The password a sign-in carries, as the person typed it, for a person hold's frame.
fn password(body: &InvokeBody) -> Result<Zeroizing<Vec<u8>>> {
    let InvokeBody::Raw(bytes) = body else {
        return Err(failure(ErrorCode::InvalidArguments));
    };
    if bytes.len() > 8192 || std::str::from_utf8(bytes).is_err() {
        return Err(failure(ErrorCode::InvalidArguments));
    }
    Ok(Zeroizing::new(bytes.clone()))
}

/// The command line's sign-in secret for a body, as the tests drive it.
#[cfg(test)]
fn secret(body: &InvokeBody) -> Result<Zeroizing<Vec<u8>>> {
    encoded(body, false)
}

/// The secret of a creation: the one password the person confirmed in the
/// window, as the password and its confirmation.
fn confirmed_secret(body: &InvokeBody) -> Result<Zeroizing<Vec<u8>>> {
    encoded(body, true)
}

fn encoded(body: &InvokeBody, confirmed: bool) -> Result<Zeroizing<Vec<u8>>> {
    let InvokeBody::Raw(bytes) = body else {
        return Err(failure(ErrorCode::InvalidArguments));
    };
    encoded_bytes(bytes, confirmed)
}

fn encoded_bytes(bytes: &[u8], confirmed: bool) -> Result<Zeroizing<Vec<u8>>> {
    if bytes.len() > 8192 {
        return Err(failure(ErrorCode::InvalidArguments));
    }
    let password = std::str::from_utf8(bytes).map_err(|_| failure(ErrorCode::InvalidArguments))?;
    // Serialize borrowed text directly into the one owned, wipe-on-drop buffer.
    // The transport-owned Request bytes remain Tauri's unwipeable copy.
    #[derive(serde::Serialize)]
    struct Payload<'a> {
        passphrase: &'a str,
        #[serde(skip_serializing_if = "Option::is_none")]
        passphrase_confirmation: Option<&'a str>,
    }
    let mut encoded = Zeroizing::new(Vec::with_capacity(8192 * 12 + 64));
    serde_json::to_writer(
        &mut *encoded,
        &Payload {
            passphrase: password,
            passphrase_confirmation: confirmed.then_some(password),
        },
    )
    .map_err(|_| failure(ErrorCode::InvalidArguments))?;
    if encoded.len() > 8192 {
        return Err(failure(ErrorCode::InvalidArguments));
    }
    Ok(encoded)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn status_observation(available: bool) -> Result<SignInStatus> {
        Ok(SignInStatus {
            supported: true,
            state: if available {
                wire::Presence::Absent
            } else {
                wire::Presence::Unknown
            },
            active_profile: Some("Test profile".into()),
            runtime_available: available,
            reconnecting: None,
            refusal: (!available).then(|| wire::Refusal {
                code: "runtime_unavailable".into(),
                retry_after_seconds: None,
            }),
        })
    }

    #[test]
    fn unavailable_runtime_preserves_the_preceding_manager_failure_and_safe_context() {
        let denied = if cfg!(windows) { 5 } else { 13 };
        let error = ApplicationError::new(ErrorCode::ManagerDispatchFailed, Operation::Manager)
            .caused_by(std::io::Error::from_raw_os_error(denied));
        let failure = status_after_manager(Err(error), status_observation(false)).unwrap_err();
        let document = serde_json::to_value(failure).unwrap();
        assert_eq!(document["code"], "manager_dispatch_failed");
        assert_eq!(document["operation"], "manager");
        assert_eq!(document["ioKind"], "PermissionDenied");
        assert_eq!(document["osCode"], denied);

        let private = ApplicationError::new(ErrorCode::PackageUnavailable, Operation::Manager)
            .caused_by(std::io::Error::new(
                std::io::ErrorKind::NotFound,
                "private installation path and exception payload",
            ));
        let failure = status_after_manager(Err(private), status_observation(false)).unwrap_err();
        let document = serde_json::to_value(failure).unwrap();
        assert_eq!(document["code"], "package_unavailable");
        assert_eq!(document["operation"], "manager");
        assert_eq!(document["ioKind"], "NotFound");
        assert!(!document.to_string().contains("private"));
    }

    #[test]
    fn a_working_runtime_remains_available_after_a_manager_dispatch_failure() {
        let failure = ApplicationError::new(ErrorCode::PackageUnavailable, Operation::Manager);
        let status = status_after_manager(Err(failure), status_observation(true)).unwrap();
        assert!(status.runtime_available);
        assert_eq!(status.state, wire::Presence::Absent);
        assert_eq!(status.active_profile.as_deref(), Some("Test profile"));
        assert!(status.refusal.is_none());
    }

    #[test]
    fn successful_or_unsupported_dispatch_never_claims_runtime_readiness() {
        fn check(outcome: crate::manager::StartOutcome) {
            let status = status_after_manager(Ok(outcome), status_observation(false)).unwrap();
            assert!(!status.runtime_available);
            assert_eq!(status.refusal.unwrap().code, "runtime_unavailable");
        }
        check(crate::manager::StartOutcome::Dispatched);
        #[cfg(not(any(windows, target_os = "macos")))]
        check(crate::manager::StartOutcome::Unsupported);
    }

    #[test]
    fn an_unreadable_cli_status_retains_its_own_failure() {
        let manager = ApplicationError::new(ErrorCode::PackageUnavailable, Operation::Manager);
        let cli = ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli);
        let failure = status_after_manager(Err(manager), Err(cli)).unwrap_err();
        assert_eq!(failure.code, ErrorCode::ReadFailed);
        assert_eq!(failure.operation, Operation::Cli);
    }

    #[test]
    fn secret_is_raw_utf8_and_bounded_after_json_encoding() {
        let encoded = secret(&InvokeBody::Raw("á\"\n漢".as_bytes().to_vec())).unwrap();
        assert_eq!(
            serde_json::from_slice::<serde_json::Value>(&encoded).unwrap(),
            serde_json::json!({"passphrase":"á\"\n漢"})
        );
        for body in [
            InvokeBody::Json(serde_json::json!([97])),
            InvokeBody::Raw(vec![255]),
            InvokeBody::Raw(vec![b'\n'; 8192]),
        ] {
            assert_eq!(secret(&body).unwrap_err().code, ErrorCode::InvalidArguments);
        }
    }

    #[test]
    fn a_creation_sends_the_one_password_as_itself_and_its_confirmation() {
        let encoded = confirmed_secret(&InvokeBody::Raw("á\"\n漢".as_bytes().to_vec())).unwrap();
        assert_eq!(
            serde_json::from_slice::<serde_json::Value>(&encoded).unwrap(),
            serde_json::json!({"passphrase":"á\"\n漢","passphrase_confirmation":"á\"\n漢"})
        );
        // Twice the text must still fit the product's one bounded read.
        assert_eq!(
            confirmed_secret(&InvokeBody::Raw(vec![b'x'; 4096]))
                .unwrap_err()
                .code,
            ErrorCode::InvalidArguments
        );
        assert!(confirmed_secret(&InvokeBody::Raw(vec![b'x'; 1024])).is_ok());
    }

    fn named(value: &str) -> HeaderMap {
        let mut headers = HeaderMap::new();
        headers.insert(PROFILE_HEADER, value.parse().unwrap());
        headers
    }

    #[test]
    fn a_label_is_percent_encoded_utf8_and_absent_when_unnamed() {
        assert_eq!(label(&HeaderMap::new()).unwrap(), None);
        for (sent, read) in [
            ("Demo%20profile", "Demo profile"),
            ("Taller%20Ribera%2C%20S.L.", "Taller Ribera, S.L."),
            ("%E6%BC%A2%C3%A1", "漢á"),
            ("Ana-Maria", "Ana-Maria"),
            (
                "Ana%7EMaria%20%26%20Hijos%20%282025%29",
                "Ana~Maria & Hijos (2025)",
            ),
        ] {
            assert_eq!(
                label(&named(sent)).unwrap().as_deref(),
                Some(read),
                "{sent}"
            );
        }
        let longest = "x".repeat(LABEL_LIMIT);
        assert_eq!(label(&named(&longest)).unwrap().as_deref(), Some(&*longest));
    }

    #[test]
    fn a_label_the_product_could_not_hold_or_would_read_as_an_option_is_refused() {
        let long = "x".repeat(LABEL_LIMIT + 1);
        for sent in [
            "",
            "%20",
            "%20Ana",
            "Ana%20",
            "-Ana",
            "--help",
            "%2D%2Dquiet",
            "Ana%0ASoler",
            "Ana%00",
            "%",
            "%4",
            "%zz",
            "%FF",
            "%E6%BC",
            long.as_str(),
            // What the command line would rewrite into another label.
            "%25USERNAME%25%20y%20Cia",
            "Rebajas%2050%25",
            "Caja%20%24USERNAME",
            "Taller%20%5B2025%5D",
            "Todo%2A",
            "Cu%C3%A1l%3F",
            "~",
            "%7Eana",
        ] {
            assert_eq!(
                label(&named(sent)).unwrap_err().code,
                ErrorCode::InvalidArguments,
                "{sent:?}"
            );
        }
    }

    #[test]
    fn a_label_follows_the_option_terminator_and_fixed_words_precede_it() {
        assert_eq!(
            arguments(&LOGIN, Some("Demo profile"), true),
            [
                "--format",
                "json",
                "config",
                "login",
                "--secrets-stdin",
                "--",
                "Demo profile"
            ]
        );
        assert_eq!(
            arguments(&LOGIN, None, true),
            ["--format", "json", "config", "login", "--secrets-stdin"]
        );
        assert_eq!(
            arguments(&CREATE, Some("Ana"), true),
            [
                "--format",
                "json",
                "config",
                "profile",
                "create",
                "--quiet",
                "--secrets-stdin",
                "--",
                "Ana"
            ]
        );
        assert_eq!(
            arguments(&LIST, None, false),
            ["--format", "json", "config", "profile", "list"]
        );
        assert_eq!(
            arguments(&LOGOUT, None, false),
            ["--format", "json", "config", "logout"]
        );
    }

    // What the fixtures assert of the product's models, asked of a real
    // package: its command line lists, creates and refuses as the window
    // expects. The profiles go to storage of this test's own, under the
    // run's, so no other live test meets them.
    #[cfg(feature = "live-package-tests")]
    #[tokio::test]
    async fn a_real_package_lists_creates_and_refuses_profiles_as_the_window_expects() {
        use crate::environment::{Parent, resolve};
        use cadrumo_application::diagnostics::Diagnostics;
        use std::path::PathBuf;

        let root = PathBuf::from(
            std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT").expect("select real package"),
        );
        let mut parent = Parent::current().unwrap();
        let shared = resolve(root.clone(), &parent, Arc::new(Diagnostics::default()))
            .await
            .unwrap()
            .working_directory;
        let own = shared.join(format!("sign-in-profiles-{}", std::process::id()));
        std::fs::create_dir_all(&own).unwrap();
        let mut pinned = 0;
        for (_, value) in &mut parent.environment {
            if std::path::Path::new(&*value) == shared {
                *value = own.clone().into_os_string();
                pinned += 1;
            }
        }
        assert_eq!(pinned, 1, "the run names its storage root once");
        let launch = resolve(root, &parent, Arc::new(Diagnostics::default()))
            .await
            .unwrap();
        assert_eq!(launch.working_directory, own);
        let state = SignIn::new(&launch);

        let listed = |state: &SignIn| {
            serde_json::to_value(
                wire::profiles(&state.output(&LIST, None, None).unwrap())
                    .ok()
                    .unwrap(),
            )
            .unwrap()
        };
        let password =
            || confirmed_secret(&InvokeBody::Raw(b"Live-test-password-1".to_vec())).unwrap();
        let create = |state: &SignIn, name: &str| {
            serde_json::to_value(
                wire::created(state.run(&CREATE, Some(name), Some(password())).unwrap()).unwrap(),
            )
            .unwrap()
        };

        assert_eq!(
            listed(&state),
            serde_json::json!({"profiles": [], "complete": true})
        );
        let first = "Perfil de prueba á漢";
        assert_eq!(
            create(&state, first),
            serde_json::json!({"kind": "created", "name": first})
        );
        assert_eq!(
            listed(&state),
            serde_json::json!({"profiles": [{"name": first, "active": true}], "complete": true})
        );
        // The same label in another case is the same label to the product.
        assert_eq!(
            create(&state, "PERFIL de prueba á漢"),
            serde_json::json!({
                "kind": "refused", "code": "profile_already_exists", "retryAfterSeconds": null
            })
        );
        // A second profile is the one selected once it exists. Its label
        // holds what a command line is most often wrong about: quotes,
        // spaces, an ampersand, and a backslash at its very end.
        let second = r#"Segundo "el nuevo" & Cía (2026) \"#;
        assert_eq!(
            create(&state, second),
            serde_json::json!({"kind": "created", "name": second})
        );
        assert_eq!(
            listed(&state),
            serde_json::json!({
                "profiles": [
                    {"name": first, "active": false},
                    {"name": second, "active": true}
                ],
                "complete": true
            })
        );
        // A sign-in that names a profile reaches the product's login for
        // that label: with no runtime behind this storage it is refused for
        // that, and not as a call the command line could not read.
        let login = serde_json::to_value(
            wire::login(
                state
                    .run(
                        &LOGIN,
                        Some(first),
                        Some(secret(&InvokeBody::Raw(b"Live-test-password-1".to_vec())).unwrap()),
                    )
                    .unwrap(),
            )
            .unwrap(),
        )
        .unwrap();
        assert_eq!(
            login,
            serde_json::json!({
                "kind": "refused", "code": "runtime_unavailable", "retryAfterSeconds": null
            })
        );
        // Signing in did not happen, so the selection is where creation left it.
        assert_eq!(listed(&state)["profiles"][1]["active"], true);
    }
}
