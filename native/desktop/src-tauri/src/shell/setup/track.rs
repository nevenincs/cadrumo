//! The checks and setup this window started, and the profile's Google account,
//! followed through the held person session's generic relay. The hold names no
//! setup item and words nothing: this host submits the product's registered
//! `dependencies.*` operations, and its `config.google.status`,
//! `config.google.login` and `config.google.logout` operations, by definition
//! id, observes them, and builds the window's snapshot from the words the
//! operations themselves return in the profile's language. The Google account
//! is not a setup item: it is the profile's, read and changed on its own, and
//! only travels in the same snapshot because it rides the same session. What
//! only this window knows stays here: which check and setup it started, how far
//! it read their events, the plan it approved, and the plan it saw
//! interrupted, whose unchanged digest lets Resume apply without a second
//! dialog.
use super::wire::{
    Action, BlockedReason, Check, CheckKind, CheckMode, CheckStage, Decision, Failure, Google,
    GoogleStage, GoogleState, ItemKind, ItemProgress, ItemResult, Outcome, PlanEntry, PlanPart,
    Recovery, Refusal, Retry, Review, Row, Run, RunStage, Snapshot, StaleReason, State, Step,
    is_hex64, is_item_id,
};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation};
use serde::Deserialize;
use serde::de::DeserializeOwned;
use serde_json::{Value, json};

pub const STATUS: &str = "dependencies.status";
pub const VERIFY: &str = "dependencies.verify";
pub const SETUP: &str = "dependencies.setup";
pub const SUBJECT: &str = "dependencies:installation";
const PLAN_PHASE: &str = "dependencies.setup.plan";
const SETUP_PREFIX: &str = "dependencies.setup.";
/// The product's registered Google sign-in; the person's click starts it and
/// Google's own consent page is the approval, so its review is answered here.
pub const GOOGLE_SIGN_IN: &str = "config.google.login";
/// The product's registered sign-out, which removes the profile's stored sign-in.
pub const GOOGLE_SIGN_OUT: &str = "config.google.logout";
/// The product's read of the profile's stored sign-in; it contacts nothing.
pub const GOOGLE_STATUS: &str = "config.google.status";
const MAX_ITEMS: usize = 16;
const EVENT_PAGES: usize = 16;

/// One exchange on the held person bridge; the bridge has checked the reply's
/// request, connection, profile and session identity.
pub trait Relay {
    fn call(&mut self, request: Value) -> Result<Value, ApplicationError>;
}

/// Why an action stopped: a closed refusal the window words, or a host failure.
#[derive(Debug)]
pub enum Stop {
    Refused(Refusal),
    Host(ApplicationError),
}

impl From<ApplicationError> for Stop {
    fn from(error: ApplicationError) -> Self {
        Self::Host(error)
    }
}

impl From<Refusal> for Stop {
    fn from(code: Refusal) -> Self {
        Self::Refused(code)
    }
}

fn protocol() -> ApplicationError {
    ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli).with_reason("setup_reply_shape")
}

fn parse<T: DeserializeOwned>(value: &Value) -> Result<T, Stop> {
    serde_json::from_value(value.clone()).map_err(|_| Stop::Host(protocol()))
}

// ── The product's documents ─────────────────────────────────────────────────

#[derive(Clone, Debug, Deserialize)]
struct ItemName {
    item_id: String,
    name: String,
}

#[derive(Clone, Debug, Deserialize)]
struct RowWords {
    item_id: String,
    name: String,
    sentence: String,
    note: Option<String>,
    action: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
struct FailureWords {
    category: Failure,
    sentence: String,
}

/// What a setup result or review says, already in the profile's language.
#[derive(Clone, Debug, Deserialize)]
struct Wording {
    names: Vec<ItemName>,
    rows: Vec<RowWords>,
    failures: Vec<FailureWords>,
    retry: String,
    details: String,
}

impl Wording {
    fn failure(&self, category: Failure) -> Option<String> {
        self.failures
            .iter()
            .find(|words| words.category == category)
            .map(|words| words.sentence.clone())
    }

    fn retry(&self, attempt: u32, delay_s: u32) -> String {
        self.retry
            .replace("{attempt}", &attempt.to_string())
            .replace("{seconds}", &delay_s.to_string())
    }
}

#[derive(Clone, Debug, Deserialize)]
struct StatusRow {
    item_id: String,
    kind: ItemKind,
    mode: CheckMode,
    state: State,
    stale_reason: Option<StaleReason>,
    blocked_reason: Option<BlockedReason>,
    failure_category: Option<Failure>,
    recovery: Option<Recovery>,
    recovery_action_id: Option<String>,
    version: Option<String>,
    size_estimate_bytes: Option<u64>,
}

#[derive(Clone, Debug, Deserialize)]
struct StatusResult {
    mode: CheckMode,
    rows: Vec<StatusRow>,
    complete: bool,
    hardware_limited: bool,
    wording: Wording,
}

#[derive(Clone, Debug, Deserialize)]
struct SetupItemResult {
    item_id: String,
    changed: bool,
    failure_category: Option<Failure>,
    transferred_bytes: u64,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
enum SetupOutcome {
    Completed,
    NothingToDo,
    Rejected,
    PlanChanged,
    NotEnoughSpace,
    Interrupted,
    Cancelled,
}

impl SetupOutcome {
    fn outcome(self) -> Outcome {
        match self {
            Self::Completed => Outcome::Completed,
            Self::NothingToDo => Outcome::NothingToDo,
            Self::Rejected => Outcome::Rejected,
            Self::PlanChanged => Outcome::PlanChanged,
            Self::NotEnoughSpace => Outcome::NotEnoughSpace,
            Self::Interrupted => Outcome::Interrupted,
            Self::Cancelled => Outcome::Cancelled,
        }
    }
}

#[derive(Clone, Debug, Deserialize)]
struct SetupResult {
    outcome: SetupOutcome,
    plan_digest: Option<String>,
    items: Vec<SetupItemResult>,
    rows: Vec<StatusRow>,
    complete: bool,
    wording: Wording,
}

#[derive(Clone, Debug, Deserialize)]
struct PlannedEntry {
    item_id: String,
    download_bytes: Option<u64>,
    source_hosts: Vec<String>,
    installs_outside_program: bool,
    advisories: Vec<super::wire::Advisory>,
}

#[derive(Clone, Debug, Deserialize)]
struct PartView {
    part_id: String,
    name: String,
    download_bytes: Option<u64>,
}

#[derive(Clone, Debug, Deserialize)]
struct EntryView {
    entry: PlannedEntry,
    destination_path: Option<String>,
    shares_download_with: Option<String>,
    licence_notice: Option<String>,
    parts: Vec<PartView>,
}

#[derive(Clone, Debug, Deserialize)]
struct Space {
    free_bytes: Option<u64>,
    required_bytes: u64,
}

#[derive(Clone, Debug, Deserialize)]
struct PlanReview {
    plan_digest: String,
    entries: Vec<EntryView>,
    known_download_bytes: u64,
    has_unknown_size: bool,
    installs_outside_program: bool,
    space: Space,
    space_sufficient: bool,
    wording: Wording,
}

// ── The runtime's generic documents ─────────────────────────────────────────

#[derive(Clone, Debug, Deserialize)]
struct Progress {
    completed: u64,
    total: u64,
    subject_code: Option<String>,
}

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
    revision: u64,
    lifecycle: String,
    terminal_condition: Option<String>,
    phase_code: Option<String>,
    progress: Option<Progress>,
    cancellable_now: bool,
    cancellation_requested: bool,
    pending_interaction: Pending,
}

#[derive(Clone, Debug, Deserialize)]
struct Event {
    kind: String,
    phase_code: Option<String>,
    notice_code: Option<String>,
    subject_code: Option<String>,
    completed: Option<u64>,
    total: Option<u64>,
}

#[derive(Clone, Debug, Deserialize)]
struct EventPage {
    status: String,
    events: Vec<Event>,
    next_cursor: u64,
    anchor_cursor: u64,
}

#[derive(Clone, Debug, Deserialize)]
struct Observation {
    projection: Projection,
    event_page: EventPage,
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
        Relayed::Refused { .. } => Err(Refusal::Unavailable.into()),
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
    after_cursor: u64,
    definition_id: &str,
) -> Result<Observation, Stop> {
    observe_subject(bridge, operation_id, after_cursor, definition_id, SUBJECT)
}

fn observe_subject(
    bridge: &mut dyn Relay,
    operation_id: &str,
    after_cursor: u64,
    definition_id: &str,
    subject: &str,
) -> Result<Observation, Stop> {
    let request = json!({"action": "operation_observe", "operation_id": operation_id, "after_cursor": after_cursor});
    let reply = replied(relay(bridge, request, "operation_observed")?)?;
    let observation: Observation = parse(&reply["observation"])?;
    let projection = &observation.projection;
    if projection.operation_id != operation_id
        || projection.definition_id != definition_id
        || projection.subject_ref != subject
    {
        return Err(Refusal::Unavailable.into());
    }
    Ok(observation)
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

/// The plan awaiting the person's answer, as the relay read it.
#[derive(Clone, Debug)]
struct ReviewRead {
    interaction_id: String,
    revision: u64,
    expires_at: Option<String>,
    review_digest: String,
    plan: PlanReview,
}

/// The pending review's interaction, revision and digest, and the reply that showed it.
struct PendingReview {
    interaction_id: String,
    revision: u64,
    expires_at: Option<String>,
    review_digest: String,
    reply: Value,
}

fn pending_review(bridge: &mut dyn Relay, operation_id: &str) -> Result<PendingReview, Stop> {
    let request = json!({"action": "operation_review", "operation_id": operation_id});
    let reply = match relay(bridge, request, "operation_review")? {
        Relayed::Reply(reply) => reply,
        Relayed::Refused { code, .. } if code == "not_pending" => {
            return Err(Refusal::NotPending.into());
        }
        Relayed::Refused { .. } => return Err(Refusal::Unavailable.into()),
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
        expires_at: text("expires_at"),
        review_digest,
        reply,
    })
}

fn review(bridge: &mut dyn Relay, operation_id: &str) -> Result<ReviewRead, Stop> {
    let pending = pending_review(bridge, operation_id)?;
    Ok(ReviewRead {
        plan: parse(&pending.reply["document"]["projection"])?,
        interaction_id: pending.interaction_id,
        revision: pending.revision,
        expires_at: pending.expires_at,
        review_digest: pending.review_digest,
    })
}

/// Answer the review exactly as it was read; `false` when it moved on meanwhile.
fn respond_to(
    bridge: &mut dyn Relay,
    operation_id: &str,
    pending: &PendingReview,
    decision: Decision,
) -> Result<bool, Stop> {
    let request = json!({
        "action": "operation_respond",
        "operation_id": operation_id,
        "interaction_id": pending.interaction_id,
        "revision": pending.revision,
        "review_digest": pending.review_digest,
        "decision": decision,
    });
    Ok(matches!(
        relay(bridge, request, "operation_responded")?,
        Relayed::Reply(_)
    ))
}

/// `(item, step)` of a `dependencies.setup.<item>.<step>` phase code.
fn setup_phase(code: &str) -> Option<(&str, Step)> {
    let (item, step) = code.strip_prefix(SETUP_PREFIX)?.rsplit_once('.')?;
    let step = match step {
        "plan" => Step::Plan,
        "preflight" => Step::Preflight,
        "download" => Step::Download,
        "install" => Step::Install,
        "verify" => Step::Verify,
        "cleanup" => Step::Cleanup,
        _ => return None,
    };
    is_item_id(item).then_some((item, step))
}

/// `(item, attempt, seconds)` of a `dependencies.setup.<item>.retry.<attempt>.<seconds>` notice.
fn retry_notice(code: &str) -> Option<(&str, u32, u32)> {
    let (item, tail) = code.strip_prefix(SETUP_PREFIX)?.rsplit_once(".retry.")?;
    let (attempt, seconds) = tail.split_once('.')?;
    let (attempt, seconds) = (attempt.parse().ok()?, seconds.parse().ok()?);
    (is_item_id(item) && attempt >= 2).then_some((item, attempt, u32::max(1, seconds)))
}

// ── Tracking ────────────────────────────────────────────────────────────────

#[derive(Clone, Debug, Default)]
struct ItemTrack {
    step: Option<Step>,
    progress: Option<(u64, u64)>,
    retry: Option<(u32, u32)>,
}

#[derive(Clone, Debug)]
struct CheckTrack {
    operation_id: String,
    definition_id: &'static str,
    kind: CheckKind,
    stage: CheckStage,
}

#[derive(Clone, Debug)]
struct SetupTrack {
    operation_id: String,
    resume_digest: Option<String>,
    cursor: u64,
    revision: u64,
    stage: RunStage,
    review: Option<ReviewRead>,
    items: Vec<(String, ItemTrack)>,
    cancellable: bool,
    cancel_requested: bool,
    result: Option<SetupResult>,
    failed: bool,
    approved_digest: Option<String>,
}

impl SetupTrack {
    fn new(operation_id: String, resume_digest: Option<String>) -> Self {
        Self {
            operation_id,
            resume_digest,
            cursor: 0,
            revision: 0,
            stage: RunStage::Planning,
            review: None,
            items: Vec::new(),
            cancellable: false,
            cancel_requested: false,
            result: None,
            failed: false,
            approved_digest: None,
        }
    }

    fn item(&mut self, item_id: &str) -> Result<&mut ItemTrack, Stop> {
        if let Some(index) = self.items.iter().position(|(id, _)| id == item_id) {
            return Ok(&mut self.items[index].1);
        }
        if !is_item_id(item_id) || self.items.len() >= MAX_ITEMS {
            return Err(Refusal::Unavailable.into());
        }
        self.items.push((item_id.to_owned(), ItemTrack::default()));
        Ok(&mut self.items.last_mut().expect("just pushed").1)
    }
}

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
}

#[derive(Clone, Debug, Deserialize)]
struct GoogleRefusal {
    failure_category: Option<Failure>,
}

/// The profile's sign-in as last read, and the read in flight.
#[derive(Clone, Debug, Default)]
struct GoogleAccount {
    state: Option<GoogleState>,
    email: Option<String>,
    reading: Option<String>,
    stale: bool,
}

/// The setup state this window follows on one held person session.
#[derive(Debug)]
pub struct Tracker {
    session: Value,
    rows: Option<StatusResult>,
    rows_from_setup: Option<SetupResult>,
    check: Option<CheckTrack>,
    setup: Option<SetupTrack>,
    last_interrupted_digest: Option<String>,
    google: GoogleTrack,
    account: GoogleAccount,
    refresh_rows: bool,
    wording: Option<Wording>,
    names: Vec<(String, String)>,
    locale: Option<Option<String>>,
}

impl Tracker {
    /// A tracker for the held session `session` names, by its session and connection.
    pub fn new(session: Value) -> Self {
        Self {
            session,
            rows: None,
            rows_from_setup: None,
            check: None,
            setup: None,
            last_interrupted_digest: None,
            google: GoogleTrack::idle(),
            account: GoogleAccount::default(),
            refresh_rows: false,
            wording: None,
            names: Vec::new(),
            locale: None,
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

    /// Run one window action and return the snapshot after it.
    pub fn handle(&mut self, bridge: &mut dyn Relay, action: Action) -> Result<Snapshot, Stop> {
        self.locale = None;
        match action {
            Action::Observe => {}
            Action::Check(mode) => {
                let kind = if mode == CheckMode::Quick {
                    CheckKind::StatusQuick
                } else {
                    CheckKind::StatusFull
                };
                let payload = json!({"mode": mode, "locale": self.language(bridge)?});
                self.start_check(bridge, STATUS, payload, kind)?;
            }
            Action::Verify(items) => {
                let payload = json!({"item_ids": items, "locale": self.language(bridge)?});
                self.start_check(bridge, VERIFY, payload, CheckKind::Verify)?;
            }
            Action::Start {
                items,
                model,
                resume,
            } => self.start_setup(bridge, items, model, resume)?,
            Action::Answer {
                operation_id,
                plan_digest,
                decision,
            } => self.answer(bridge, &operation_id, &plan_digest, decision)?,
            Action::Cancel { operation_id } => self.cancel(bridge, &operation_id)?,
            Action::GoogleSignIn => self.start_google(bridge, GOOGLE_SIGN_IN)?,
            Action::GoogleSignOut => self.start_google(bridge, GOOGLE_SIGN_OUT)?,
        }
        self.snapshot(bridge)
    }

    fn language(&mut self, bridge: &mut dyn Relay) -> Result<Option<String>, Stop> {
        if let Some(language) = &self.locale {
            return Ok(language.clone());
        }
        let reply = bridge.call(json!({"action": "language_observe"}))?;
        let language = reply["language"].as_str().map(str::to_owned);
        self.locale = Some(language.clone());
        Ok(language)
    }

    fn snapshot(&mut self, bridge: &mut dyn Relay) -> Result<Snapshot, Stop> {
        if self
            .check
            .as_ref()
            .is_some_and(|check| check.stage == CheckStage::Running)
        {
            self.observe_check(bridge)?;
        }
        if let Some(mut track) = self.setup.take() {
            let observed = if track.stage == RunStage::Settled {
                Ok(())
            } else {
                self.observe_setup(bridge, &mut track)
            };
            self.setup = Some(track);
            observed?;
        }
        if self.google.acting() {
            self.observe_google(bridge)?;
        }
        self.follow_account(bridge)?;
        let unread = (self.rows.is_none() && self.rows_from_setup.is_none()) || self.refresh_rows;
        let checking = self
            .check
            .as_ref()
            .is_some_and(|check| check.stage == CheckStage::Running);
        if unread && !checking {
            self.refresh_rows = false;
            let payload = json!({"mode": CheckMode::Quick, "locale": self.language(bridge)?});
            self.start_check(bridge, STATUS, payload, CheckKind::StatusQuick)?;
        }
        self.render()
    }

    fn learn(&mut self, wording: &Wording) {
        for name in &wording.names {
            match self
                .names
                .iter_mut()
                .find(|(item, _)| *item == name.item_id)
            {
                Some(known) => known.1.clone_from(&name.name),
                None => self.names.push((name.item_id.clone(), name.name.clone())),
            }
        }
        self.wording = Some(wording.clone());
    }

    // ── Checks ──────────────────────────────────────────────────────────────

    fn start_check(
        &mut self,
        bridge: &mut dyn Relay,
        definition_id: &'static str,
        payload: Value,
        kind: CheckKind,
    ) -> Result<(), Stop> {
        if self
            .check
            .as_ref()
            .is_some_and(|check| check.stage == CheckStage::Running)
        {
            return Ok(());
        }
        let operation_id = submit(bridge, definition_id, SUBJECT, payload)?
            .map_err(|_| Stop::Refused(Refusal::Unavailable))?;
        self.check = Some(CheckTrack {
            operation_id,
            definition_id,
            kind,
            stage: CheckStage::Running,
        });
        self.observe_check(bridge)
    }

    fn observe_check(&mut self, bridge: &mut dyn Relay) -> Result<(), Stop> {
        let Some(check) = self.check.clone() else {
            return Ok(());
        };
        let projection = observe(bridge, &check.operation_id, 0, check.definition_id)?.projection;
        if !projection.terminal() {
            return Ok(());
        }
        let stage = if projection.condition() == Some("succeeded") {
            let status: StatusResult = result(bridge, &check.operation_id, check.definition_id)?;
            self.learn(&status.wording);
            self.rows = Some(status);
            self.rows_from_setup = None;
            CheckStage::Done
        } else {
            CheckStage::Failed
        };
        if let Some(current) = self.check.as_mut() {
            current.stage = stage;
        }
        Ok(())
    }

    // ── Setup ───────────────────────────────────────────────────────────────

    fn start_setup(
        &mut self,
        bridge: &mut dyn Relay,
        items: Option<Vec<String>>,
        model: Option<String>,
        resume: bool,
    ) -> Result<(), Stop> {
        if self
            .setup
            .as_ref()
            .is_some_and(|track| track.stage != RunStage::Settled)
        {
            // One setup at a time: a second start joins the running one.
            return Ok(());
        }
        let payload =
            json!({"item_ids": items, "model_name": model, "locale": self.language(bridge)?});
        let operation_id = match submit(bridge, SETUP, SUBJECT, payload)? {
            Ok(operation_id) => operation_id,
            Err((code, Some(holder))) if code == "subject_busy" && is_hex64(&holder) => {
                // Another frontend's setup holds the items unless this session can follow it.
                match observe(bridge, &holder, 0, SETUP) {
                    Ok(_) => holder,
                    Err(Stop::Refused(_)) => return Err(Refusal::Busy.into()),
                    Err(error) => return Err(error),
                }
            }
            Err(_) => return Err(Refusal::Unavailable.into()),
        };
        let resume_digest = if resume {
            self.last_interrupted_digest.clone()
        } else {
            None
        };
        let mut track = SetupTrack::new(operation_id, resume_digest);
        let observed = self.observe_setup(bridge, &mut track);
        self.setup = Some(track);
        observed
    }

    fn observe_setup(
        &mut self,
        bridge: &mut dyn Relay,
        track: &mut SetupTrack,
    ) -> Result<(), Stop> {
        let mut observation = observe(bridge, &track.operation_id, track.cursor, SETUP)?;
        for _ in 0..EVENT_PAGES {
            let page = &observation.event_page;
            for event in &page.events {
                Self::take_event(track, event)?;
            }
            track.cursor = page.next_cursor;
            if page.status != "page" || track.cursor >= page.anchor_cursor {
                break;
            }
            observation = observe(bridge, &track.operation_id, track.cursor, SETUP)?;
        }
        let projection = observation.projection;
        track.revision = projection.revision;
        track.cancellable = projection.cancellable_now;
        track.cancel_requested = projection.cancellation_requested;
        if let Some(progress) = &projection.progress
            && let Some(subject) = &progress.subject_code
            && progress.total > 0
        {
            track.item(subject)?.progress = Some((progress.completed, progress.total));
        }
        if projection.terminal() {
            return self.settle(bridge, track, &projection);
        }
        let pending = &projection.pending_interaction;
        if pending.disposition == "review_available" {
            let known = track
                .review
                .as_ref()
                .map(|read| (&read.interaction_id, read.revision));
            if known != pending.interaction_id.as_ref().zip(pending.revision) {
                let read = review(bridge, &track.operation_id)?;
                for entry in &read.plan.entries {
                    track.item(&entry.entry.item_id)?;
                }
                self.learn(&read.plan.wording);
                track.review = Some(read);
            }
            track.stage = RunStage::Review;
            let digest = track
                .review
                .as_ref()
                .map(|read| read.plan.plan_digest.clone());
            if track.resume_digest.is_some() && track.resume_digest == digest {
                // A Resume click of the plan this window approved and saw interrupted is the person's act.
                track.resume_digest = None;
                self.respond(bridge, track, Decision::Apply)?;
            }
            return Ok(());
        }
        track.review = None;
        track.stage = if track.approved_digest.is_none()
            && projection.phase_code.as_deref() == Some(PLAN_PHASE)
        {
            RunStage::Planning
        } else {
            RunStage::Running
        };
        Ok(())
    }

    fn take_event(track: &mut SetupTrack, event: &Event) -> Result<(), Stop> {
        match event.kind.as_str() {
            "phase" => {
                if let Some((item, step)) = event.phase_code.as_deref().and_then(setup_phase) {
                    let item = track.item(item)?;
                    item.step = Some(step);
                    item.retry = None;
                }
            }
            "progress" => {
                if let (Some(subject), Some(completed), Some(total)) =
                    (event.subject_code.as_deref(), event.completed, event.total)
                    && is_item_id(subject)
                    && total > 0
                {
                    track.item(subject)?.progress = Some((completed.min(total), total));
                }
            }
            "notice" => {
                if let Some((item, attempt, seconds)) =
                    event.notice_code.as_deref().and_then(retry_notice)
                {
                    track.item(item)?.retry = Some((attempt, seconds));
                }
            }
            _ => {}
        }
        Ok(())
    }

    fn settle(
        &mut self,
        bridge: &mut dyn Relay,
        track: &mut SetupTrack,
        projection: &Projection,
    ) -> Result<(), Stop> {
        track.stage = RunStage::Settled;
        track.review = None;
        track.cancellable = false;
        if projection.condition() == Some("succeeded") {
            let settled: SetupResult = result(bridge, &track.operation_id, SETUP)?;
            for item in &settled.items {
                track.item(&item.item_id)?;
            }
            let interrupted = settled.outcome == SetupOutcome::Interrupted
                || settled
                    .items
                    .iter()
                    .any(|item| item.failure_category == Some(Failure::Interrupted));
            self.last_interrupted_digest = if interrupted {
                settled.plan_digest.clone()
            } else {
                None
            };
            self.learn(&settled.wording);
            self.rows_from_setup = Some(settled.clone());
            track.result = Some(settled);
        } else {
            track.failed = projection.condition() != Some("cancelled");
            self.last_interrupted_digest = if projection.condition() == Some("interrupted") {
                track.approved_digest.clone()
            } else {
                None
            };
            self.refresh_rows = true;
        }
        Ok(())
    }

    fn answer(
        &mut self,
        bridge: &mut dyn Relay,
        operation_id: &str,
        plan_digest: &str,
        decision: Decision,
    ) -> Result<(), Stop> {
        let Some(mut track) = self
            .setup
            .take_if(|track| track.operation_id == operation_id)
        else {
            return Err(Refusal::NotPending.into());
        };
        let answered = self.answer_track(bridge, &mut track, plan_digest, decision);
        self.setup = Some(track);
        answered
    }

    fn answer_track(
        &mut self,
        bridge: &mut dyn Relay,
        track: &mut SetupTrack,
        plan_digest: &str,
        decision: Decision,
    ) -> Result<(), Stop> {
        self.observe_setup(bridge, track)?;
        if track.stage != RunStage::Review || track.review.is_none() {
            return Err(Refusal::NotPending.into());
        }
        // Read the plan again: an answer approves exactly the plan the person saw.
        let current = review(bridge, &track.operation_id)?;
        let changed = current.plan.plan_digest != plan_digest;
        self.learn(&current.plan.wording);
        track.review = Some(current);
        if changed {
            return Err(Refusal::PlanChanged.into());
        }
        self.respond(bridge, track, decision)
    }

    fn respond(
        &mut self,
        bridge: &mut dyn Relay,
        track: &mut SetupTrack,
        decision: Decision,
    ) -> Result<(), Stop> {
        let Some(read) = track.review.clone() else {
            return Err(Refusal::NotPending.into());
        };
        let request = json!({
            "action": "operation_respond",
            "operation_id": track.operation_id,
            "interaction_id": read.interaction_id,
            "revision": read.revision,
            "review_digest": read.review_digest,
            "decision": decision,
        });
        match relay(bridge, request, "operation_responded")? {
            Relayed::Reply(_) => {}
            Relayed::Refused { code, .. } if code == "review_changed" => {
                return Err(Refusal::PlanChanged.into());
            }
            Relayed::Refused { .. } => return Err(Refusal::NotPending.into()),
        }
        if decision == Decision::Apply {
            track.approved_digest = Some(read.plan.plan_digest);
        }
        track.review = None;
        track.stage = RunStage::Running;
        self.observe_setup(bridge, track)
    }

    fn cancel(&mut self, bridge: &mut dyn Relay, operation_id: &str) -> Result<(), Stop> {
        let Some(mut track) = self.setup.take_if(|track| {
            track.operation_id == operation_id && track.stage != RunStage::Settled
        }) else {
            return Err(Refusal::NotPending.into());
        };
        let cancelled = self.cancel_track(bridge, &mut track);
        self.setup = Some(track);
        cancelled
    }

    fn cancel_track(&mut self, bridge: &mut dyn Relay, track: &mut SetupTrack) -> Result<(), Stop> {
        for _ in 0..2 {
            self.observe_setup(bridge, track)?;
            if track.stage == RunStage::Settled || !track.cancellable {
                return Err(Refusal::NotCancellable.into());
            }
            let request = json!({
                "action": "operation_cancel",
                "operation_id": track.operation_id,
                "expected_revision": track.revision,
            });
            match relay(bridge, request, "operation_cancel_requested")? {
                Relayed::Reply(_) => {
                    track.cancel_requested = true;
                    return self.observe_setup(bridge, track);
                }
                // The operation moved on since it was read; read it again once.
                Relayed::Refused { code, .. } if code == "stale_operation_revision" => {}
                Relayed::Refused { .. } => return Err(Refusal::NotCancellable.into()),
            }
        }
        Err(Refusal::NotCancellable.into())
    }

    // ── Google ──────────────────────────────────────────────────────────────

    fn google_subject(&self) -> Result<String, Stop> {
        let profile = self.session["profile_id"].as_str().ok_or_else(protocol)?;
        Ok(format!("profile:{profile}"))
    }

    /// Submit `definition_id` for the profile, joining one already running.
    fn submit_google(
        &self,
        bridge: &mut dyn Relay,
        definition_id: &'static str,
    ) -> Result<String, Stop> {
        let subject = self.google_subject()?;
        let payload = json!({"profile_id": self.session["profile_id"]});
        match submit(bridge, definition_id, &subject, payload)? {
            Ok(operation_id) => Ok(operation_id),
            Err((code, Some(holder))) if code == "subject_busy" && is_hex64(&holder) => {
                match observe_subject(bridge, &holder, 0, definition_id, &subject) {
                    Ok(_) => Ok(holder),
                    Err(Stop::Refused(_)) => Err(Refusal::Busy.into()),
                    Err(error) => Err(error),
                }
            }
            Err(_) => Err(Refusal::Unavailable.into()),
        }
    }

    fn start_google(
        &mut self,
        bridge: &mut dyn Relay,
        definition_id: &'static str,
    ) -> Result<(), Stop> {
        if self.google.acting() {
            // A second click joins the sign-in or sign-out already running.
            return Ok(());
        }
        let operation_id = self.submit_google(bridge, definition_id)?;
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
        self.observe_google(bridge)
    }

    fn observe_google(&mut self, bridge: &mut dyn Relay) -> Result<(), Stop> {
        let Some(operation_id) = self.google.operation_id.clone() else {
            return Ok(());
        };
        let definition_id = self.google.definition_id;
        let subject = self.google_subject()?;
        let projection =
            observe_subject(bridge, &operation_id, 0, definition_id, &subject)?.projection;
        if projection.terminal() {
            let failure = self.google_failure(bridge, &operation_id, definition_id, &projection)?;
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
            if respond_to(bridge, &operation_id, &read, Decision::Apply)? {
                self.google.answered = Some((read.interaction_id, read.revision));
            }
        }
        Ok(())
    }

    /// `None` when the act succeeded; otherwise the one failure the window words.
    fn google_failure(
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
            Err(Stop::Refused(_)) => return Ok(Some(Failure::Unexpected)),
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
            let subject = self.google_subject()?;
            let projection =
                match observe_subject(bridge, &operation_id, 0, GOOGLE_STATUS, &subject) {
                    Ok(observation) => observation.projection,
                    Err(Stop::Refused(_)) => {
                        self.account.reading = None;
                        self.account.state = Some(GoogleState::Unknown);
                        self.account.email = None;
                        return Ok(());
                    }
                    Err(error) => return Err(error),
                };
            if !projection.terminal() {
                return Ok(());
            }
            self.account.reading = None;
            let (state, email) = self.account_reading(bridge, &operation_id, &projection)?;
            self.account.state = Some(state);
            self.account.email = email;
        }
        if (self.account.state.is_none() || self.account.stale) && !self.google.acting() {
            self.account.stale = false;
            match self.submit_google(bridge, GOOGLE_STATUS) {
                Ok(operation_id) => {
                    self.account.reading = Some(operation_id);
                    return self.follow_account(bridge);
                }
                Err(Stop::Refused(_)) => {
                    self.account.state = Some(GoogleState::Unknown);
                    self.account.email = None;
                }
                Err(error) => return Err(error),
            }
        }
        Ok(())
    }

    fn account_reading(
        &mut self,
        bridge: &mut dyn Relay,
        operation_id: &str,
        projection: &Projection,
    ) -> Result<(GoogleState, Option<String>), Stop> {
        let unknown = Ok((GoogleState::Unknown, None));
        if !matches!(projection.condition(), Some("succeeded" | "refused")) {
            return unknown;
        }
        let settled: GoogleOutcome = match result(bridge, operation_id, GOOGLE_STATUS) {
            Ok(settled) => settled,
            Err(Stop::Refused(_)) => return unknown,
            Err(error) => return Err(error),
        };
        if settled.outcome == "succeeded" {
            return Ok(match settled.result {
                Some(read) if read.session_present => (GoogleState::SignedIn, read.account_email),
                Some(_) => (GoogleState::SignedOut, None),
                None => (GoogleState::Unknown, None),
            });
        }
        Ok(
            match settled.refusal.and_then(|refusal| refusal.failure_category) {
                Some(Failure::NotInThisBuild) => (GoogleState::NotInThisBuild, None),
                // A sign-in made for another installation, or one that has ended.
                Some(Failure::NeedsSignIn) => (GoogleState::SignedOut, None),
                _ => (GoogleState::Unknown, None),
            },
        )
    }

    // ── Rendering ───────────────────────────────────────────────────────────

    fn name(&self, item_id: &str) -> String {
        self.names
            .iter()
            .find(|(item, _)| item == item_id)
            .map_or_else(|| item_id.to_owned(), |(_, name)| name.clone())
    }

    fn failure_sentence(&self, failure: Failure) -> Result<String, Stop> {
        self.wording
            .as_ref()
            .and_then(|wording| wording.failure(failure))
            .ok_or(Stop::Host(protocol()))
    }

    fn render_rows(rows: &[StatusRow], wording: &Wording) -> Vec<Row> {
        rows.iter()
            .filter_map(|row| {
                let words = wording
                    .rows
                    .iter()
                    .find(|words| words.item_id == row.item_id)?;
                Some(Row {
                    item: row.item_id.clone(),
                    kind: row.kind,
                    mode: row.mode,
                    state: row.state,
                    stale_reason: row.stale_reason,
                    blocked_reason: row.blocked_reason,
                    failure: row.failure_category,
                    recovery: row.recovery,
                    recovery_action_id: row.recovery_action_id.clone(),
                    version: row.version.clone(),
                    size_bytes: row.size_estimate_bytes,
                    name: words.name.clone(),
                    sentence: words.sentence.clone(),
                    note: words.note.clone(),
                    action_label: words.action.clone(),
                })
            })
            .collect()
    }

    fn render_review(&self, read: &ReviewRead) -> Review {
        let plan = &read.plan;
        Review {
            plan_digest: plan.plan_digest.clone(),
            expires_at: read.expires_at.clone(),
            entries: plan
                .entries
                .iter()
                .map(|view| PlanEntry {
                    item: view.entry.item_id.clone(),
                    name: self.name(&view.entry.item_id),
                    download_bytes: view.entry.download_bytes,
                    source_hosts: view.entry.source_hosts.clone(),
                    destination: view.destination_path.clone(),
                    installs_outside_program: view.entry.installs_outside_program,
                    shares_download_with: view.shares_download_with.clone(),
                    advisories: view.entry.advisories.clone(),
                    licence_notice: view.licence_notice.clone(),
                    parts: view
                        .parts
                        .iter()
                        .map(|part| PlanPart {
                            part: part.part_id.clone(),
                            name: part.name.clone(),
                            download_bytes: part.download_bytes,
                        })
                        .collect(),
                })
                .collect(),
            known_download_bytes: plan.known_download_bytes,
            has_unknown_size: plan.has_unknown_size,
            installs_outside_program: plan.installs_outside_program,
            required_bytes: plan.space.required_bytes,
            free_bytes: plan.space.free_bytes,
            space_sufficient: plan.space_sufficient,
        }
    }

    fn render_setup(&self, track: &SetupTrack) -> Result<Run, Stop> {
        let settled = track.stage == RunStage::Settled;
        let mut items = Vec::with_capacity(track.items.len());
        for (item_id, item) in &track.items {
            let result = track
                .result
                .as_ref()
                .and_then(|result| result.items.iter().find(|done| done.item_id == *item_id));
            let retry = match (item.retry, &self.wording) {
                (Some((attempt, delay_s)), Some(wording)) if !settled => Some(Retry {
                    attempt,
                    delay_s,
                    sentence: wording.retry(attempt, delay_s),
                }),
                _ => None,
            };
            let result = match result {
                None => None,
                Some(done) => Some(ItemResult {
                    changed: done.changed,
                    failure: done.failure_category,
                    sentence: done
                        .failure_category
                        .map(|failure| self.failure_sentence(failure))
                        .transpose()?,
                    transferred_bytes: done.transferred_bytes,
                }),
            };
            items.push(ItemProgress {
                item: item_id.clone(),
                name: self.name(item_id),
                step: item.step,
                completed: item.progress.map(|(completed, _)| completed),
                total: item.progress.map(|(_, total)| total),
                retry,
                result,
            });
        }
        let outcome = settled.then(|| match &track.result {
            Some(result) => result.outcome.outcome(),
            None if track.failed => Outcome::Failed,
            None => Outcome::Cancelled,
        });
        Ok(Run {
            operation_id: track.operation_id.clone(),
            stage: track.stage,
            review: match (&track.review, track.stage) {
                (Some(read), RunStage::Review) => Some(self.render_review(read)),
                _ => None,
            },
            items,
            cancellable: track.cancellable,
            cancel_requested: track.cancel_requested,
            outcome,
            failure_sentence: if outcome == Some(Outcome::Failed) {
                Some(self.failure_sentence(Failure::Unexpected)?)
            } else {
                None
            },
        })
    }

    fn render(&self) -> Result<Snapshot, Stop> {
        let from_setup = self.rows_from_setup.as_ref().filter(|_| {
            self.setup
                .as_ref()
                .is_some_and(|track| track.result.is_some())
        });
        let (rows, rows_mode, complete, hardware_limited) = match (from_setup, &self.rows) {
            (Some(settled), _) => (
                Self::render_rows(&settled.rows, &settled.wording),
                Some(CheckMode::Quick),
                Some(settled.complete),
                self.rows.as_ref().map(|status| status.hardware_limited),
            ),
            (None, Some(status)) => (
                Self::render_rows(&status.rows, &status.wording),
                Some(status.mode),
                Some(status.complete),
                Some(status.hardware_limited),
            ),
            (None, None) => (Vec::new(), None, None, None),
        };
        let snapshot = Snapshot {
            rows,
            rows_mode,
            complete,
            hardware_limited,
            check: self.check.as_ref().map(|check| Check {
                operation_id: check.operation_id.clone(),
                kind: check.kind,
                stage: check.stage,
            }),
            setup: self
                .setup
                .as_ref()
                .map(|track| self.render_setup(track))
                .transpose()?,
            google: Google {
                state: self.account.state,
                email: self
                    .account
                    .email
                    .clone()
                    .filter(|_| self.account.state == Some(GoogleState::SignedIn)),
                stage: self.google.stage,
                failure: self.google.failure,
                sentence: self
                    .google
                    .failure
                    .map(|failure| self.failure_sentence(failure))
                    .transpose()?,
            },
            details: self
                .wording
                .as_ref()
                .map(|wording| wording.details.clone())
                .unwrap_or_default(),
        };
        if !snapshot.valid() {
            return Err(Stop::Host(protocol()));
        }
        Ok(snapshot)
    }
}

#[cfg(test)]
#[path = "track_tests.rs"]
mod tests;
