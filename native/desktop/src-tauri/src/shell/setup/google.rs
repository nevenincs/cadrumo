//! The profile's Google account, followed through the held person session's
//! generic relay. The account is not a setup item: it is the profile's own
//! sign-in, read and changed through the product's registered
//! `config.google.status`, `config.google.login` and `config.google.logout`
//! operations, and it travels in the setup snapshot only because the window
//! shows them together. What only this window knows stays here: the sign-in
//! or sign-out it started, the consent review it answered, and the stored
//! sign-in as last read.
use super::wire::{Failure, Google, GoogleStage, GoogleState, Refusal, Stop, is_hex64};
use cadrumo_application::error::application::{
    ApplicationError, ChildRefusal, ErrorCode, Operation,
};
use serde::Deserialize;
use serde::de::DeserializeOwned;
use serde_json::{Value, json};

/// The product's registered Google sign-in; the person's click starts it and
/// Google's own consent page is the approval, so its review is answered here.
pub const GOOGLE_SIGN_IN: &str = "config.google.login";
/// The product's registered sign-out, which removes the profile's stored sign-in.
pub const GOOGLE_SIGN_OUT: &str = "config.google.logout";
/// The product's read of the profile's stored sign-in; it contacts nothing.
pub const GOOGLE_STATUS: &str = "config.google.status";
pub const GOOGLE_FOLDER: &str = "config.google.folder.view";

/// One exchange on the held person bridge; the bridge has checked the reply's
/// request, connection, profile and session identity.
pub trait Relay {
    fn call(&mut self, request: Value) -> Result<Value, ApplicationError>;
}

/// What the window asked of the account.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Act {
    Observe,
    SignIn,
    SignOut,
}

fn protocol() -> ApplicationError {
    ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli).with_reason("setup_reply_shape")
}

fn parse<T: DeserializeOwned>(value: &Value) -> Result<T, Stop> {
    serde_json::from_value(value.clone()).map_err(|error| Stop::Host(protocol().caused_by(error)))
}

/// The relay's refusal code as a cause: the code is the runtime's, never the person's.
fn refusal_of(code: &str) -> ChildRefusal {
    ChildRefusal::answered(&json!({"code": code}))
}

// ── The runtime's generic documents ─────────────────────────────────────────

#[derive(Clone, Debug, Deserialize)]
struct Pending {
    disposition: String,
    interaction_id: Option<String>,
    revision: Option<u64>,
}

#[derive(Clone, Debug, Deserialize)]
struct Projection {
    operation_id: String,
    definition_id: String,
    subject_ref: String,
    lifecycle: String,
    terminal_condition: Option<String>,
    pending_interaction: Pending,
}

#[derive(Clone, Debug, Deserialize)]
struct Observation {
    projection: Projection,
}

impl Projection {
    fn terminal(&self) -> bool {
        self.lifecycle == "terminal"
    }

    fn condition(&self) -> Option<&str> {
        self.terminal_condition.as_deref()
    }
}

// ── Relay exchanges ─────────────────────────────────────────────────────────

enum Relayed {
    Reply(Value),
    Refused {
        code: String,
        holder: Option<String>,
    },
}

fn relay(bridge: &mut dyn Relay, request: Value, expected: &str) -> Result<Relayed, Stop> {
    let reply = bridge.call(request)?;
    match reply["kind"].as_str() {
        Some("operation_refused") => Ok(Relayed::Refused {
            code: reply["code"].as_str().ok_or_else(protocol)?.to_owned(),
            holder: reply["holder_operation_id"].as_str().map(str::to_owned),
        }),
        Some(kind) if kind == expected => Ok(Relayed::Reply(reply)),
        _ => Err(Stop::Host(protocol())),
    }
}

/// A reply, or the window's `unavailable` for any refusal it has no closer word for.
fn replied(relayed: Relayed) -> Result<Value, Stop> {
    match relayed {
        Relayed::Reply(reply) => Ok(reply),
        Relayed::Refused { code, .. } => {
            Err(Stop::unavailable("setup_google_relay_refused").because(refusal_of(&code)))
        }
    }
}

fn submit(
    bridge: &mut dyn Relay,
    definition_id: &str,
    subject: &str,
    payload: Value,
) -> Result<Result<String, (String, Option<String>)>, Stop> {
    let request = json!({
        "action": "operation_submit",
        "definition_id": definition_id,
        "subject_ref": subject,
        "payload": payload,
    });
    match relay(bridge, request, "operation_submitted")? {
        Relayed::Reply(reply) => {
            let operation_id = reply["operation_id"].as_str().ok_or_else(protocol)?;
            if !is_hex64(operation_id) {
                return Err(Stop::Host(protocol()));
            }
            Ok(Ok(operation_id.to_owned()))
        }
        Relayed::Refused { code, holder } => Ok(Err((code, holder))),
    }
}

fn observe(
    bridge: &mut dyn Relay,
    operation_id: &str,
    definition_id: &str,
    subject: &str,
) -> Result<Projection, Stop> {
    let request =
        json!({"action": "operation_observe", "operation_id": operation_id, "after_cursor": 0});
    let reply = replied(relay(bridge, request, "operation_observed")?)?;
    let observation: Observation = parse(&reply["observation"])?;
    let projection = observation.projection;
    if projection.operation_id != operation_id
        || projection.definition_id != definition_id
        || projection.subject_ref != subject
    {
        return Err(Stop::unavailable("setup_google_operation_mismatch"));
    }
    Ok(projection)
}

fn result<T: DeserializeOwned>(
    bridge: &mut dyn Relay,
    operation_id: &str,
    definition_id: &str,
) -> Result<T, Stop> {
    let request = json!({"action": "operation_result", "operation_id": operation_id});
    let reply = replied(relay(bridge, request, "operation_result")?)?;
    if reply["operation_id"] != operation_id || reply["definition_id"] != definition_id {
        return Err(Stop::Host(protocol()));
    }
    parse(&reply["document"]["projection"])
}

/// The pending review's interaction, revision and digest.
struct PendingReview {
    interaction_id: String,
    revision: u64,
    review_digest: String,
}

fn pending_review(bridge: &mut dyn Relay, operation_id: &str) -> Result<PendingReview, Stop> {
    let request = json!({"action": "operation_review", "operation_id": operation_id});
    let reply = match relay(bridge, request, "operation_review")? {
        Relayed::Reply(reply) => reply,
        Relayed::Refused { code, .. } if code == "not_pending" => {
            return Err(Refusal::NotPending.into());
        }
        Relayed::Refused { code, .. } => {
            return Err(Stop::unavailable("setup_google_review_refused").because(refusal_of(&code)));
        }
    };
    let text = |key: &str| reply[key].as_str().map(str::to_owned);
    let (Some(interaction_id), Some(revision), Some(review_digest)) = (
        text("interaction_id"),
        reply["revision"].as_u64(),
        text("review_digest"),
    ) else {
        return Err(Stop::Host(protocol()));
    };
    if reply["operation_id"] != operation_id || !is_hex64(&review_digest) {
        return Err(Stop::Host(protocol()));
    }
    Ok(PendingReview {
        interaction_id,
        revision,
        review_digest,
    })
}

/// Approve the review exactly as it was read; `false` when it moved on meanwhile.
fn approve(
    bridge: &mut dyn Relay,
    operation_id: &str,
    pending: &PendingReview,
) -> Result<bool, Stop> {
    let request = json!({
        "action": "operation_respond",
        "operation_id": operation_id,
        "interaction_id": pending.interaction_id,
        "revision": pending.revision,
        "review_digest": pending.review_digest,
        "decision": "apply",
    });
    Ok(matches!(
        relay(bridge, request, "operation_responded")?,
        Relayed::Reply(_)
    ))
}

// ── The settled documents ───────────────────────────────────────────────────

/// What a settled Google operation says: its result, or the failure its refusal falls into.
#[derive(Clone, Debug, Deserialize)]
struct GoogleOutcome {
    outcome: String,
    result: Option<GoogleStatusResult>,
    refusal: Option<GoogleRefusal>,
}

/// The stored sign-in `config.google.status` reports; other Google results carry neither field.
#[derive(Clone, Debug, Deserialize)]
struct GoogleStatusResult {
    #[serde(default)]
    session_present: bool,
    #[serde(default)]
    account_email: Option<String>,
    #[serde(default)]
    granted_scopes: Vec<String>,
}

#[derive(Clone, Debug, Deserialize)]
struct GoogleFolderOutcome {
    outcome: String,
    result: Option<GoogleFolderResult>,
}

#[derive(Clone, Debug, Deserialize)]
struct GoogleFolderResult {
    configured: bool,
    root_folder_id: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
struct GoogleRefusal {
    failure_category: Option<Failure>,
}

// ── Tracking ────────────────────────────────────────────────────────────────

/// The sign-in or sign-out this window started.
#[derive(Clone, Debug)]
struct GoogleTrack {
    stage: GoogleStage,
    failure: Option<Failure>,
    definition_id: &'static str,
    operation_id: Option<String>,
    answered: Option<(String, u64)>,
}

impl GoogleTrack {
    fn idle() -> Self {
        Self {
            stage: GoogleStage::Idle,
            failure: None,
            definition_id: GOOGLE_SIGN_IN,
            operation_id: None,
            answered: None,
        }
    }

    fn acting(&self) -> bool {
        matches!(self.stage, GoogleStage::SigningIn | GoogleStage::SigningOut)
    }
}

/// The profile's sign-in as last read, and the read in flight.
#[derive(Clone, Debug, Default)]
struct GoogleAccount {
    state: Option<GoogleState>,
    email: Option<String>,
    reading: Option<String>,
    stale: bool,
    folder_needed: bool,
    folder_reading: Option<String>,
    drive_folder_id: Option<String>,
}

/// The Google account this window follows on one held person session.
#[derive(Debug)]
pub struct Tracker {
    session: Value,
    google: GoogleTrack,
    account: GoogleAccount,
}

impl Tracker {
    /// A tracker for the held session `session` names, by its session and connection.
    pub fn new(session: Value) -> Self {
        Self {
            session,
            google: GoogleTrack::idle(),
            account: GoogleAccount::default(),
        }
    }

    /// Whether this tracker follows the held session `identity` names; another
    /// session's operations are not this window's to follow.
    pub fn follows(&self, identity: &Value) -> bool {
        [
            "profile_id",
            "session_id",
            "runtime_boot_id",
            "connection_id",
        ]
        .iter()
        .all(|key| self.session[key] == identity[key])
    }

    /// Run one window act and return the account after it.
    pub fn handle(&mut self, bridge: &mut dyn Relay, act: Act) -> Result<Google, Stop> {
        match act {
            Act::Observe => {}
            Act::SignIn => self.start(bridge, GOOGLE_SIGN_IN)?,
            Act::SignOut => self.start(bridge, GOOGLE_SIGN_OUT)?,
        }
        if self.google.acting() {
            self.observe_google(bridge)?;
        }
        self.follow_account(bridge)?;
        self.follow_folder(bridge)?;
        Ok(self.view())
    }

    fn subject(&self) -> Result<String, Stop> {
        let profile = self.session["profile_id"].as_str().ok_or_else(protocol)?;
        Ok(format!("profile:{profile}"))
    }

    /// Submit `definition_id` for the profile, joining one already running.
    fn submit(&self, bridge: &mut dyn Relay, definition_id: &'static str) -> Result<String, Stop> {
        let subject = self.subject()?;
        let payload = json!({"profile_id": self.session["profile_id"]});
        match submit(bridge, definition_id, &subject, payload)? {
            Ok(operation_id) => Ok(operation_id),
            Err((code, Some(holder))) if code == "subject_busy" && is_hex64(&holder) => {
                match observe(bridge, &holder, definition_id, &subject) {
                    Ok(_) => Ok(holder),
                    Err(Stop::Refused(_) | Stop::Unavailable(_)) => Err(Refusal::Busy.into()),
                    Err(error) => Err(error),
                }
            }
            Err((code, _)) => {
                Err(Stop::unavailable("setup_google_submit_refused").because(refusal_of(&code)))
            }
        }
    }

    fn start(&mut self, bridge: &mut dyn Relay, definition_id: &'static str) -> Result<(), Stop> {
        if self.google.acting() {
            // A second click joins the sign-in or sign-out already running.
            return Ok(());
        }
        let operation_id = self.submit(bridge, definition_id)?;
        self.account.drive_folder_id = None;
        self.account.folder_reading = None;
        self.account.folder_needed = false;
        self.google = GoogleTrack {
            stage: if definition_id == GOOGLE_SIGN_OUT {
                GoogleStage::SigningOut
            } else {
                GoogleStage::SigningIn
            },
            definition_id,
            operation_id: Some(operation_id),
            ..GoogleTrack::idle()
        };
        Ok(())
    }

    fn observe_google(&mut self, bridge: &mut dyn Relay) -> Result<(), Stop> {
        let Some(operation_id) = self.google.operation_id.clone() else {
            return Ok(());
        };
        let definition_id = self.google.definition_id;
        let subject = self.subject()?;
        let projection = observe(bridge, &operation_id, definition_id, &subject)?;
        if projection.terminal() {
            let failure = self.failure(bridge, &operation_id, definition_id, &projection)?;
            // Whatever the act came to, the stored sign-in is read again.
            self.account.stale = true;
            self.google = GoogleTrack {
                stage: if failure.is_none() {
                    GoogleStage::Idle
                } else {
                    GoogleStage::Failed
                },
                failure,
                ..GoogleTrack::idle()
            };
            return Ok(());
        }
        let pending = &projection.pending_interaction;
        let coordinates = pending.interaction_id.clone().zip(pending.revision);
        if definition_id == GOOGLE_SIGN_IN
            && pending.disposition == "review_available"
            && coordinates != self.google.answered
        {
            // The person's click asked for this sign-in; Google's consent page is the approval.
            let read = pending_review(bridge, &operation_id)?;
            if approve(bridge, &operation_id, &read)? {
                self.google.answered = Some((read.interaction_id, read.revision));
            }
        }
        Ok(())
    }

    /// `None` when the act succeeded; otherwise the one failure the window words.
    fn failure(
        &mut self,
        bridge: &mut dyn Relay,
        operation_id: &str,
        definition_id: &'static str,
        projection: &Projection,
    ) -> Result<Option<Failure>, Stop> {
        match projection.condition() {
            Some("succeeded" | "refused") => {}
            Some("cancelled") => return Ok(Some(Failure::Cancelled)),
            Some("interrupted") => return Ok(Some(Failure::Interrupted)),
            _ => return Ok(Some(Failure::Unexpected)),
        }
        let settled: GoogleOutcome = match result(bridge, operation_id, definition_id) {
            Ok(settled) => settled,
            // A refusal that carries no detail has no closer word than unexpected.
            Err(Stop::Refused(_) | Stop::Unavailable(_)) => return Ok(Some(Failure::Unexpected)),
            Err(error) => return Err(error),
        };
        if settled.outcome == "succeeded" && projection.condition() == Some("succeeded") {
            return Ok(None);
        }
        Ok(Some(
            settled
                .refusal
                .and_then(|refusal| refusal.failure_category)
                .unwrap_or(Failure::Unexpected),
        ))
    }

    /// Keep the profile's stored sign-in read: once at first, again after a
    /// sign-in or sign-out settles, and whenever its read settles. A read the
    /// relay will not carry leaves the sign-in unknown rather than failing the
    /// setup snapshot it travels with.
    fn follow_account(&mut self, bridge: &mut dyn Relay) -> Result<(), Stop> {
        if let Some(operation_id) = self.account.reading.clone() {
            let subject = self.subject()?;
            let projection = match observe(bridge, &operation_id, GOOGLE_STATUS, &subject) {
                Ok(projection) => projection,
                Err(Stop::Refused(_) | Stop::Unavailable(_)) => {
                    self.account.reading = None;
                    self.account.state = Some(GoogleState::Unknown);
                    self.account.email = None;
                    self.account.drive_folder_id = None;
                    return Ok(());
                }
                Err(error) => return Err(error),
            };
            if !projection.terminal() {
                return Ok(());
            }
            self.account.reading = None;
            let (state, email, drive) = self.reading(bridge, &operation_id, &projection)?;
            self.account.state = Some(state);
            self.account.email = email;
            self.account.drive_folder_id = None;
            self.account.folder_reading = None;
            self.account.folder_needed = drive;
        }
        if (self.account.state.is_none() || self.account.stale) && !self.google.acting() {
            self.account.stale = false;
            match self.submit(bridge, GOOGLE_STATUS) {
                Ok(operation_id) => {
                    self.account.reading = Some(operation_id);
                    return self.follow_account(bridge);
                }
                Err(Stop::Refused(_) | Stop::Unavailable(_)) => {
                    self.account.state = Some(GoogleState::Unknown);
                    self.account.email = None;
                    self.account.drive_folder_id = None;
                    self.account.folder_needed = false;
                }
                Err(error) => return Err(error),
            }
        }
        Ok(())
    }

    fn reading(
        &mut self,
        bridge: &mut dyn Relay,
        operation_id: &str,
        projection: &Projection,
    ) -> Result<(GoogleState, Option<String>, bool), Stop> {
        let unknown = Ok((GoogleState::Unknown, None, false));
        if !matches!(projection.condition(), Some("succeeded" | "refused")) {
            return unknown;
        }
        let settled: GoogleOutcome = match result(bridge, operation_id, GOOGLE_STATUS) {
            Ok(settled) => settled,
            Err(Stop::Refused(_) | Stop::Unavailable(_)) => return unknown,
            Err(error) => return Err(error),
        };
        if settled.outcome == "succeeded" {
            return Ok(match settled.result {
                Some(read) if read.session_present => (
                    GoogleState::SignedIn,
                    read.account_email,
                    read.granted_scopes
                        .iter()
                        .any(|scope| scope == "https://www.googleapis.com/auth/drive.file"),
                ),
                Some(_) => (GoogleState::SignedOut, None, false),
                None => (GoogleState::Unknown, None, false),
            });
        }
        Ok(
            match settled.refusal.and_then(|refusal| refusal.failure_category) {
                Some(Failure::NotInThisBuild) => (GoogleState::NotInThisBuild, None, false),
                // A sign-in made for another installation, or one that has ended.
                Some(Failure::NeedsSignIn) => (GoogleState::SignedOut, None, false),
                _ => (GoogleState::Unknown, None, false),
            },
        )
    }

    fn follow_folder(&mut self, bridge: &mut dyn Relay) -> Result<(), Stop> {
        if self.google.acting() || self.account.stale || self.account.reading.is_some() {
            return Ok(());
        }
        if self.account.folder_needed {
            self.account.folder_needed = false;
            match self.submit(bridge, GOOGLE_FOLDER) {
                Ok(id) => self.account.folder_reading = Some(id),
                Err(Stop::Refused(_) | Stop::Unavailable(_)) => return Ok(()),
                Err(error) => return Err(error),
            }
        }
        let Some(id) = self.account.folder_reading.clone() else {
            return Ok(());
        };
        let subject = self.subject()?;
        let projection = match observe(bridge, &id, GOOGLE_FOLDER, &subject) {
            Ok(projection) => projection,
            Err(Stop::Refused(_) | Stop::Unavailable(_)) => {
                self.account.folder_reading = None;
                return Ok(());
            }
            Err(error) => return Err(error),
        };
        if !projection.terminal() {
            return Ok(());
        }
        self.account.folder_reading = None;
        if projection.condition() != Some("succeeded") {
            return Ok(());
        }
        let settled: GoogleFolderOutcome = match result(bridge, &id, GOOGLE_FOLDER) {
            Ok(settled) => settled,
            Err(Stop::Refused(_) | Stop::Unavailable(_)) => return Ok(()),
            Err(error) => return Err(error),
        };
        if settled.outcome == "succeeded" {
            self.account.drive_folder_id = settled
                .result
                .filter(|folder| folder.configured)
                .and_then(|folder| folder.root_folder_id)
                .filter(|id| super::wire::is_drive_folder_id(id));
        }
        Ok(())
    }

    fn view(&self) -> Google {
        Google {
            state: self.account.state,
            drive_folder_id: self
                .account
                .drive_folder_id
                .clone()
                .filter(|_| !self.google.acting() && !self.account.stale),
            email: self
                .account
                .email
                .clone()
                .filter(|_| self.account.state == Some(GoogleState::SignedIn)),
            stage: self.google.stage,
            failure: self.google.failure,
        }
    }
}

#[cfg(test)]
#[path = "google_tests.rs"]
mod tests;
