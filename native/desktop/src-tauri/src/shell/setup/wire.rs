//! The closed shapes of the window's setup snapshot and the setup actions the
//! window may ask for. The snapshot carries codes and locale-neutral facts
//! only: item ids, states and their reasons, step and failure codes, byte
//! counts, hosts, folders and versions. The window words every one of them
//! from its own catalogue. A value outside a closed set or a bound exceeded is
//! a host failure, never passed on.
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

const MAX_ITEMS: usize = 16;
const MAX_HOSTS: usize = 8;
const NAME_LIMIT: usize = 256;
const VERSION_LIMIT: usize = 128;
const PATH_LIMIT: usize = 4096;
const DETAILS_LIMIT: usize = 16 * 1024;
const MODEL_LIMIT: usize = 128;

/// The parts a local AI plan is made of: its program, then the model each
/// catalogue role reads with.
pub const PARTS: [&str; 5] = [
    "program",
    "vision_transcription",
    "text_extraction",
    "column_role_mapping",
    "supply_nature_proposal",
];

fn invalid() -> ApplicationError {
    ApplicationError::new(ErrorCode::InvalidArguments, Operation::Cli)
}

/// Why a setup command was refused, as the stable code the window words.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Refusal {
    NotSignedIn,
    Busy,
    PlanChanged,
    NotPending,
    NotCancellable,
    Unavailable,
}

/// What a command refuses with. Only the code crosses to the window.
#[derive(Debug, Serialize)]
pub struct Refused {
    pub code: Refusal,
}

#[derive(Debug, Serialize)]
#[serde(untagged)]
pub enum CommandFailure {
    Host(ApplicationError),
    Refused(Refused),
}
impl From<ApplicationError> for CommandFailure {
    fn from(error: ApplicationError) -> Self {
        Self::Host(error)
    }
}
impl From<Refusal> for CommandFailure {
    fn from(code: Refusal) -> Self {
        Self::Refused(Refused { code })
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ItemKind {
    Browser,
    LocalAi,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum State {
    Absent,
    Provisioning,
    Verifying,
    Ready,
    Stale,
    Failed,
    Blocked,
    Unknown,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum BlockedReason {
    Offline,
    NeedsPerson,
    Hardware,
    NotInThisBuild,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum StaleReason {
    OlderRevision,
    DifferentModelVersion,
    ProgramTooOld,
}

/// A secondary fact a usable item can carry without changing its state.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Note {
    DownloadedNotLoaded,
    OwnNetworkSettings,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Failure {
    Offline,
    HostUnreachable,
    SecureConnectionFailed,
    BlockedByNetwork,
    DiskFull,
    NoPermission,
    DamagedDownload,
    NotEnoughMemory,
    MemoryBusy,
    ProgramMissing,
    ProgramNotRunning,
    Interrupted,
    NeedsSignIn,
    NotInThisBuild,
    Cancelled,
    Unexpected,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Recovery {
    SetUp,
    Update,
    TryAgain,
    Resume,
    CheckAgain,
}

/// Why a model's plan entry is worth telling the person about.
#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Advisory {
    LicenceCommercialUseBarred,
    LicenceUnverified,
    OverrideNotInCatalogue,
    OverrideBelowContextFloor,
    FitExceedsMeasuredHeadroom,
    FitUnverified,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CheckMode {
    Quick,
    Full,
}

impl CheckMode {
    pub fn parse(text: &str) -> Option<Self> {
        match text {
            "quick" => Some(Self::Quick),
            "full" => Some(Self::Full),
            _ => None,
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Step {
    Plan,
    Preflight,
    Download,
    Install,
    Verify,
    Cleanup,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CheckKind {
    StatusQuick,
    StatusFull,
    Verify,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CheckStage {
    Running,
    Done,
    Failed,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RunStage {
    Planning,
    Review,
    Running,
    Settled,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Outcome {
    Completed,
    NothingToDo,
    Rejected,
    PlanChanged,
    NotEnoughSpace,
    Interrupted,
    Cancelled,
    Failed,
}

/// What the profile's Google sign-in reads as, from the product's own status
/// read. The account is the profile's, not a setup item.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum GoogleState {
    SignedIn,
    SignedOut,
    NotInThisBuild,
    Unknown,
}

/// The sign-in or sign-out this window started, while it runs or after it failed.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum GoogleStage {
    Idle,
    SigningIn,
    SigningOut,
    Failed,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Decision {
    Apply,
    Reject,
}

impl Decision {
    pub fn parse(text: &str) -> Option<Self> {
        match text {
            "apply" => Some(Self::Apply),
            "reject" => Some(Self::Reject),
            _ => None,
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Row {
    pub item: String,
    pub kind: ItemKind,
    pub mode: CheckMode,
    pub state: State,
    pub stale_reason: Option<StaleReason>,
    pub blocked_reason: Option<BlockedReason>,
    pub failure: Option<Failure>,
    pub recovery: Option<Recovery>,
    /// The operator action that offers `recovery`, such as
    /// `operator.provision.browser`; present exactly when `recovery` is.
    pub recovery_action_id: Option<String>,
    pub version: Option<String>,
    pub size_bytes: Option<u64>,
    pub note: Option<Note>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Check {
    pub operation_id: String,
    pub kind: CheckKind,
    pub stage: CheckStage,
}

/// One part of the local AI's plan: its program, or the model one role reads
/// with. A part sharing an earlier part's download has size 0.
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct PlanPart {
    pub part: String,
    pub download_bytes: Option<u64>,
}

/// A planned model whose licence bars commercial use: the model and the
/// licence the window names in its notice.
#[derive(Clone, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Licence {
    pub model: String,
    pub licence: String,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct PlanEntry {
    pub item: String,
    pub download_bytes: Option<u64>,
    pub source_hosts: Vec<String>,
    pub destination: Option<String>,
    pub installs_outside_program: bool,
    pub shares_download_with: Option<String>,
    /// Empty except on the local AI's entry; the plan digest binds it.
    pub advisories: Vec<Advisory>,
    /// The planned models whose licence bars commercial use; present exactly
    /// when `advisories` names that bar. The plan digest binds them.
    pub licences: Vec<Licence>,
    /// The parts of the local AI, in the order setup carries them out; empty
    /// for any other item.
    pub parts: Vec<PlanPart>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Review {
    pub plan_digest: String,
    pub entries: Vec<PlanEntry>,
    pub known_download_bytes: u64,
    pub has_unknown_size: bool,
    pub installs_outside_program: bool,
    pub required_bytes: u64,
    pub free_bytes: Option<u64>,
    pub space_sufficient: bool,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Retry {
    pub attempt: u32,
    pub delay_s: u32,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ItemResult {
    pub changed: bool,
    pub failure: Option<Failure>,
    pub transferred_bytes: u64,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ItemProgress {
    pub item: String,
    pub step: Option<Step>,
    pub completed: Option<u64>,
    pub total: Option<u64>,
    pub retry: Option<Retry>,
    pub result: Option<ItemResult>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Run {
    pub operation_id: String,
    pub stage: RunStage,
    pub review: Option<Review>,
    pub items: Vec<ItemProgress>,
    pub cancellable: bool,
    pub cancel_requested: bool,
    pub outcome: Option<Outcome>,
    /// Why the setup failed; present exactly when `outcome` is `failed`.
    pub failure: Option<Failure>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Google {
    /// `None` until the profile's sign-in has been read.
    pub state: Option<GoogleState>,
    /// The signed-in account's address; present only when signed in.
    pub email: Option<String>,
    /// The profile's saved folder, only with a stored Drive grant.
    pub drive_folder_id: Option<String>,
    pub stage: GoogleStage,
    /// Why the sign-in or sign-out failed; present exactly when `stage` is
    /// `failed`.
    pub failure: Option<Failure>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Snapshot {
    pub rows: Vec<Row>,
    pub rows_mode: Option<CheckMode>,
    pub complete: Option<bool>,
    pub hardware_limited: Option<bool>,
    pub check: Option<Check>,
    pub setup: Option<Run>,
    pub google: Google,
    pub details: String,
}

/// `browser` or `local_ai`.
pub fn is_item_id(text: &str) -> bool {
    matches!(text, "browser" | "local_ai")
}

pub fn is_hex64(text: &str) -> bool {
    text.len() == 64
        && text
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

fn is_host(text: &str) -> bool {
    let labels: Vec<&str> = text.split('.').collect();
    text.len() <= 253
        && labels.len() >= 2
        && labels.iter().all(|label| {
            !label.is_empty()
                && label.len() <= 63
                && !label.starts_with('-')
                && !label.ends_with('-')
                && label
                    .bytes()
                    .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'-')
        })
}

fn plain(text: &str, limit: usize) -> bool {
    !text.is_empty() && text.len() <= limit && !text.chars().any(char::is_control)
}

fn plain_option(text: Option<&String>, limit: usize) -> bool {
    text.is_none_or(|text| plain(text, limit))
}

/// A catalogue model name.
pub fn is_model_name(text: &str) -> bool {
    text.len() <= MODEL_LIMIT
        && text
            .bytes()
            .next()
            .is_some_and(|b| b.is_ascii_alphanumeric())
        && text
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b".-_:/".contains(&b))
}

/// An operator action's identifier: `operator.` and dotted lower-case words.
pub fn is_action_id(text: &str) -> bool {
    text.len() <= 64
        && text.strip_prefix("operator.").is_some_and(|rest| {
            rest.split('.').all(|word| {
                word.bytes().next().is_some_and(|b| b.is_ascii_lowercase())
                    && word
                        .bytes()
                        .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_')
            })
        })
}

fn unique<'a>(values: impl IntoIterator<Item = &'a String>) -> bool {
    let mut seen = BTreeSet::new();
    values.into_iter().all(|value| seen.insert(value.as_str()))
}

impl Row {
    fn valid(&self) -> bool {
        let reasons = [
            self.stale_reason.is_some(),
            self.blocked_reason.is_some(),
            self.failure.is_some(),
        ];
        is_item_id(&self.item)
            && plain_option(self.version.as_ref(), VERSION_LIMIT)
            && self.recovery.is_some() == self.recovery_action_id.is_some()
            && self.recovery_action_id.as_deref().is_none_or(is_action_id)
            && reasons.iter().filter(|present| **present).count() <= 1
            && (self.stale_reason.is_none() || self.state == State::Stale)
            && (self.blocked_reason.is_none() || self.state == State::Blocked)
            && (self.failure.is_none() || self.state == State::Failed)
            && (self.note.is_none() || matches!(self.state, State::Ready | State::Stale))
    }
}

impl PlanEntry {
    fn valid(&self) -> bool {
        let barred = self
            .advisories
            .contains(&Advisory::LicenceCommercialUseBarred);
        is_item_id(&self.item)
            && !self.source_hosts.is_empty()
            && self.source_hosts.len() <= MAX_HOSTS
            && self.source_hosts.iter().all(|host| is_host(host))
            && unique(&self.source_hosts)
            && plain_option(self.destination.as_ref(), PATH_LIMIT)
            && (self.advisories.is_empty() || self.item == "local_ai")
            && (self.parts.is_empty() || self.item == "local_ai")
            && self.parts.len() <= PARTS.len()
            && unique(self.parts.iter().map(|part| &part.part))
            && self
                .parts
                .iter()
                .all(|part| PARTS.contains(&part.part.as_str()))
            && self.advisories.iter().collect::<BTreeSet<_>>().len() == self.advisories.len()
            && barred != self.licences.is_empty()
            && self.licences.len() <= PARTS.len()
            && self.licences.iter().collect::<BTreeSet<_>>().len() == self.licences.len()
            && self
                .licences
                .iter()
                .all(|licence| is_model_name(&licence.model) && plain(&licence.licence, NAME_LIMIT))
            && self
                .shares_download_with
                .as_deref()
                .is_none_or(|other| is_item_id(other) && other != self.item)
    }
}

impl Review {
    fn valid(&self) -> bool {
        is_hex64(&self.plan_digest)
            && !self.entries.is_empty()
            && self.entries.len() <= MAX_ITEMS
            && unique(self.entries.iter().map(|entry| &entry.item))
            && self.entries.iter().all(PlanEntry::valid)
            && self.space_sufficient
                == self
                    .free_bytes
                    .is_some_and(|free| free >= self.required_bytes)
    }
}

impl ItemProgress {
    fn valid(&self) -> bool {
        is_item_id(&self.item)
            && self.completed.is_some() == self.total.is_some()
            && self
                .completed
                .zip(self.total)
                .is_none_or(|(completed, total)| total > 0 && completed <= total)
            && self
                .retry
                .as_ref()
                .is_none_or(|retry| retry.attempt >= 2 && retry.delay_s >= 1)
    }
}

impl Run {
    fn valid(&self) -> bool {
        let settled = self.stage == RunStage::Settled;
        is_hex64(&self.operation_id)
            && (self.stage == RunStage::Review) == self.review.is_some()
            && self.review.as_ref().is_none_or(Review::valid)
            && self.items.len() <= MAX_ITEMS
            && unique(self.items.iter().map(|item| &item.item))
            && self.items.iter().all(ItemProgress::valid)
            && settled == self.outcome.is_some()
            && (self.outcome == Some(Outcome::Failed)) == self.failure.is_some()
            && !(settled && self.cancellable)
    }
}

impl Snapshot {
    /// Whether every value is inside its closed set and bound.
    pub fn valid(&self) -> bool {
        let read = self.rows_mode.is_some();
        self.rows.len() <= MAX_ITEMS
            && unique(self.rows.iter().map(|row| &row.item))
            && self.rows.iter().all(Row::valid)
            && read == self.complete.is_some()
            && (read || self.rows.is_empty())
            && self
                .check
                .as_ref()
                .is_none_or(|check| is_hex64(&check.operation_id))
            && self.setup.as_ref().is_none_or(Run::valid)
            && (self.google.stage == GoogleStage::Failed) == self.google.failure.is_some()
            && (self.google.email.is_none() || self.google.state == Some(GoogleState::SignedIn))
            && plain_option(self.google.email.as_ref(), NAME_LIMIT)
            && self.google.drive_folder_id.as_ref().is_none_or(|id| {
                self.google.state == Some(GoogleState::SignedIn)
                    && !matches!(
                        self.google.stage,
                        GoogleStage::SigningIn | GoogleStage::SigningOut
                    )
                    && is_drive_folder_id(id)
            })
            && self.details.len() <= DETAILS_LIMIT
            && !self.details.chars().any(|c| c.is_control() && c != '\n')
    }
}

pub(super) fn is_drive_folder_id(id: &str) -> bool {
    !id.is_empty()
        && id.len() <= 256
        && id
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || c == b'_' || c == b'-')
}

/// One setup action the window asked for, in its closed form.
#[derive(Clone, Debug, PartialEq)]
pub enum Action {
    Observe,
    Check(CheckMode),
    Verify(Option<Vec<String>>),
    Start {
        items: Option<Vec<String>>,
        resume: bool,
    },
    Answer {
        operation_id: String,
        plan_digest: String,
        decision: Decision,
    },
    Cancel {
        operation_id: String,
    },
    GoogleSignIn,
    GoogleSignOut,
}

fn items(items: Option<Vec<String>>) -> Result<Option<Vec<String>>, ApplicationError> {
    match items {
        None => Ok(None),
        Some(items)
            if !items.is_empty()
                && items.len() <= MAX_ITEMS
                && items.iter().all(|item| is_item_id(item))
                && unique(&items) =>
        {
            Ok(Some(items))
        }
        Some(_) => Err(invalid()),
    }
}

/// A status read.
pub fn check_request(mode: &str) -> Result<Action, ApplicationError> {
    Ok(Action::Check(CheckMode::parse(mode).ok_or_else(invalid)?))
}

/// A full check of `items`, or of every item.
pub fn verify_request(selected: Option<Vec<String>>) -> Result<Action, ApplicationError> {
    Ok(Action::Verify(items(selected)?))
}

/// Setup of `items`, or of every item not ready, planned first. Every role's
/// model is the one this build pins, so a setup names no model of its own.
pub fn start_request(
    selected: Option<Vec<String>>,
    model: Option<String>,
    resume: bool,
) -> Result<Action, ApplicationError> {
    if model.is_some() {
        return Err(invalid());
    }
    Ok(Action::Start {
        items: items(selected)?,
        resume,
    })
}

/// The answer to the plan whose digest the window showed.
pub fn answer_request(
    operation_id: &str,
    plan_digest: &str,
    decision: &str,
) -> Result<Action, ApplicationError> {
    let decision = Decision::parse(decision).ok_or_else(invalid)?;
    if !is_hex64(operation_id) || !is_hex64(plan_digest) {
        return Err(invalid());
    }
    Ok(Action::Answer {
        operation_id: operation_id.to_owned(),
        plan_digest: plan_digest.to_owned(),
        decision,
    })
}

/// Cancelling the setup this window started.
pub fn cancel_request(operation_id: &str) -> Result<Action, ApplicationError> {
    if !is_hex64(operation_id) {
        return Err(invalid());
    }
    Ok(Action::Cancel {
        operation_id: operation_id.to_owned(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{Value, json};

    /// The snapshot a document describes, when every value is inside its bounds.
    fn parsed(snapshot: Value) -> Option<Snapshot> {
        serde_json::from_value::<Snapshot>(snapshot)
            .ok()
            .filter(Snapshot::valid)
    }

    fn row() -> Value {
        json!({
            "item": "browser", "kind": "browser", "mode": "quick", "state": "absent",
            "stale_reason": null, "blocked_reason": null, "failure": null, "recovery": "set_up",
            "recovery_action_id": "operator.provision.browser",
            "version": null, "size_bytes": 180000000, "note": null,
        })
    }

    fn review() -> Value {
        json!({
            "plan_digest": "a".repeat(64),
            "entries": [{
                "item": "browser", "download_bytes": 100, "source_hosts": ["cdn.playwright.dev"],
                "destination": "C:\\Cadrumo\\components\\playwright",
                "installs_outside_program": false, "shares_download_with": null,
                "advisories": [], "licences": [], "parts": [],
            }],
            "known_download_bytes": 100, "has_unknown_size": false,
            "installs_outside_program": false, "required_bytes": 1073741944,
            "free_bytes": 2000000000, "space_sufficient": true,
        })
    }

    fn run(stage: &str) -> Value {
        json!({
            "operation_id": "b".repeat(64), "stage": stage,
            "review": if stage == "review" { review() } else { Value::Null },
            "items": [{
                "item": "browser", "step": "download", "completed": 40, "total": 100,
                "retry": {"attempt": 2, "delay_s": 4}, "result": null,
            }],
            "cancellable": stage == "running", "cancel_requested": false,
            "outcome": if stage == "settled" { json!("completed") } else { Value::Null },
            "failure": null,
        })
    }

    fn snapshot() -> Value {
        json!({
            "rows": [row()], "rows_mode": "quick", "complete": false, "hardware_limited": false,
            "check": {"operation_id": "c".repeat(64), "kind": "status_quick", "stage": "done"},
            "setup": run("review"),
            "google": {"state": "signed_out", "email": null, "drive_folder_id": null, "stage": "idle", "failure": null},
            "details": "Cadrumo setup details\nitem: browser; state: absent; check: quick\n",
        })
    }

    /// A named change to a valid document.
    type Case = (&'static str, fn(&mut Value));

    #[test]
    fn a_snapshot_parses_into_the_closed_shapes_and_serializes_as_the_window_reads_it() {
        let shown = parsed(snapshot()).expect("a valid snapshot");
        assert_eq!(serde_json::to_value(&shown).unwrap(), snapshot());
        assert_eq!(shown.setup.as_ref().unwrap().stage, RunStage::Review);
        for stage in ["planning", "running", "settled"] {
            let mut next = snapshot();
            next["setup"] = run(stage);
            assert!(parsed(next).is_some(), "{stage}");
        }
    }

    #[test]
    fn a_value_outside_a_closed_set_or_a_bound_is_a_host_failure() {
        let cases: [Case; 20] = [
            ("unknown state", |s| s["rows"][0]["state"] = json!("broken")),
            ("a word", |s| {
                s["rows"][0]["sentence"] = json!("Not set up yet.")
            }),
            ("bad item", |s| s["rows"][0]["item"] = json!("printer")),
            ("action without recovery", |s| {
                s["rows"][0]["recovery"] = Value::Null
            }),
            ("reason on another state", |s| {
                s["rows"][0]["failure"] = json!("offline")
            }),
            ("note on an absent item", |s| {
                s["rows"][0]["note"] = json!("downloaded_not_loaded")
            }),
            ("unknown note", |s| {
                s["rows"][0]["state"] = json!("ready");
                s["rows"][0]["note"] = json!("shiny")
            }),
            ("duplicate rows", |s| {
                let copy = s["rows"][0].clone();
                s["rows"].as_array_mut().unwrap().push(copy)
            }),
            ("bad host", |s| {
                s["setup"]["review"]["entries"][0]["source_hosts"] = json!(["https://x.y"])
            }),
            ("no hosts", |s| {
                s["setup"]["review"]["entries"][0]["source_hosts"] = json!([])
            }),
            ("bad digest", |s| {
                s["setup"]["review"]["plan_digest"] = json!("A".repeat(64))
            }),
            ("space mismatch", |s| {
                s["setup"]["review"]["space_sufficient"] = json!(false)
            }),
            ("review outside review", |s| {
                s["setup"]["stage"] = json!("running")
            }),
            ("progress beyond total", |s| {
                s["setup"]["items"][0]["completed"] = json!(101)
            }),
            ("first attempt retry", |s| {
                s["setup"]["items"][0]["retry"]["attempt"] = json!(1)
            }),
            ("unknown outcome", |s| s["setup"]["outcome"] = json!("done")),
            ("google failure off a failed act", |s| {
                s["google"]["failure"] = json!("offline")
            }),
            ("google address while signed out", |s| {
                s["google"]["email"] = json!("person@example.com")
            }),
            ("part outside the local AI", |s| {
                s["setup"]["review"]["entries"][0]["parts"] =
                    json!([{"part": "program", "download_bytes": null}])
            }),
            ("rows before a read", |s| {
                s["rows_mode"] = Value::Null;
                s["complete"] = Value::Null
            }),
        ];
        for (name, change) in cases {
            let mut changed = snapshot();
            change(&mut changed);
            assert!(parsed(changed).is_none(), "{name}");
        }
    }

    #[test]
    fn a_settled_run_carries_its_outcome_and_a_failed_one_its_failure() {
        let mut settled = snapshot();
        settled["setup"] = run("settled");
        settled["setup"]["outcome"] = json!("failed");
        assert!(parsed(settled.clone()).is_none());
        settled["setup"]["failure"] = json!("unexpected");
        assert!(parsed(settled.clone()).is_some());
        settled["setup"]["cancellable"] = json!(true);
        assert!(parsed(settled).is_none());
    }

    #[test]
    fn actions_name_only_items_and_choices_in_their_closed_forms() {
        assert_eq!(
            check_request("full").unwrap(),
            Action::Check(CheckMode::Full)
        );
        assert!(check_request("deep").is_err());
        assert_eq!(verify_request(None).unwrap(), Action::Verify(None));
        assert_eq!(
            start_request(Some(vec!["local_ai".into()]), None, true).unwrap(),
            Action::Start {
                items: Some(vec!["local_ai".into()]),
                resume: true,
            }
        );
        // Every role's model is pinned by the build: a setup cannot name another.
        assert!(start_request(None, Some("qwen3:4b".into()), false).is_err());
        for selected in [
            vec![],
            vec!["printer".to_owned()],
            vec!["browser".to_owned(), "browser".to_owned()],
            vec!["local_model.text_extraction".to_owned()],
            vec!["google".to_owned()],
        ] {
            assert!(
                verify_request(Some(selected.clone())).is_err(),
                "{selected:?}"
            );
        }
        let digest = "d".repeat(64);
        assert_eq!(
            answer_request(&"e".repeat(64), &digest, "apply").unwrap(),
            Action::Answer {
                operation_id: "e".repeat(64),
                plan_digest: digest.clone(),
                decision: Decision::Apply,
            }
        );
        assert!(answer_request(&"e".repeat(64), &digest, "approve").is_err());
        assert!(answer_request("e", &digest, "reject").is_err());
        assert!(answer_request(&"e".repeat(64), &"D".repeat(64), "reject").is_err());
        assert!(cancel_request(&"e".repeat(63)).is_err());
        assert_eq!(
            cancel_request(&"e".repeat(64)).unwrap(),
            Action::Cancel {
                operation_id: "e".repeat(64)
            }
        );
    }

    fn licensed() -> Value {
        let mut licensed = snapshot();
        let entry = &mut licensed["setup"]["review"]["entries"][0];
        entry["item"] = json!("local_ai");
        entry["parts"] = json!([
            {"part": "program", "download_bytes": null},
            {"part": "text_extraction", "download_bytes": 100},
        ]);
        entry["advisories"] = json!(["licence_commercial_use_barred", "fit_unverified"]);
        entry["licences"] = json!([{"model": "qwen2.5:3b", "licence": "LicenseRef-Qwen-Research"}]);
        licensed
    }

    #[test]
    fn a_model_entry_carries_its_closed_advisories_and_the_licences_they_bar() {
        let shown = parsed(licensed()).expect("a valid snapshot");
        assert_eq!(serde_json::to_value(&shown).unwrap(), licensed());
        let cases: [Case; 7] = [
            ("unknown advisory", |e| {
                e["advisories"] = json!(["licence_free"])
            }),
            ("repeated advisory", |e| {
                e["advisories"] = json!([
                    "licence_commercial_use_barred",
                    "licence_commercial_use_barred"
                ])
            }),
            ("advisory off a model", |e| e["item"] = json!("browser")),
            ("licence without the barred advisory", |e| {
                e["advisories"] = json!(["licence_unverified"])
            }),
            ("barred advisory without licence", |e| {
                e["licences"] = json!([])
            }),
            ("control text", |e| {
                e["licences"][0]["licence"] = json!("a\tb")
            }),
            ("unknown part", |e| e["parts"][1]["part"] = json!("weather")),
        ];
        for (name, change) in cases {
            let mut changed = licensed();
            change(&mut changed["setup"]["review"]["entries"][0]);
            assert!(parsed(changed).is_none(), "{name}");
        }
    }

    #[test]
    fn a_refusal_serializes_as_its_code_only() {
        assert_eq!(
            serde_json::to_value(CommandFailure::from(Refusal::NotCancellable)).unwrap(),
            json!({"code":"not_cancellable"})
        );
    }
}
