//! The closed shapes of the window's setup snapshot and the setup actions the
//! window may ask for. The host builds each snapshot from the product's own
//! worded documents; a value outside a closed set or a bound exceeded is a
//! protocol failure, never passed on.
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

const MAX_ITEMS: usize = 16;
const MAX_HOSTS: usize = 8;
const NAME_LIMIT: usize = 256;
const SENTENCE_LIMIT: usize = 1024;
const VERSION_LIMIT: usize = 128;
const PATH_LIMIT: usize = 4096;
const DETAILS_LIMIT: usize = 16 * 1024;
const MODEL_LIMIT: usize = 128;

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
    pub name: String,
    pub sentence: String,
    pub note: Option<String>,
    pub action_label: Option<String>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Check {
    pub operation_id: String,
    pub kind: CheckKind,
    pub stage: CheckStage,
}

/// One part of an item planned in parts: the local AI program, or one role's model.
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct PlanPart {
    pub part: String,
    pub name: String,
    pub download_bytes: Option<u64>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct PlanEntry {
    pub item: String,
    pub name: String,
    pub download_bytes: Option<u64>,
    pub source_hosts: Vec<String>,
    pub destination: Option<String>,
    pub installs_outside_program: bool,
    pub shares_download_with: Option<String>,
    /// Empty except on a local model's entry; the plan digest binds it.
    pub advisories: Vec<Advisory>,
    /// A model's licence notice, already in the profile's language; the plan digest binds it.
    pub licence_notice: Option<String>,
    /// The parts of the local AI, in the order setup carries them out; empty
    /// for any other item.
    pub parts: Vec<PlanPart>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Review {
    pub plan_digest: String,
    pub expires_at: Option<String>,
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
    pub sentence: String,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ItemResult {
    pub changed: bool,
    pub failure: Option<Failure>,
    pub sentence: Option<String>,
    pub transferred_bytes: u64,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ItemProgress {
    pub item: String,
    pub name: String,
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
    pub failure_sentence: Option<String>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Google {
    /// `None` until the profile's sign-in has been read.
    pub state: Option<GoogleState>,
    /// The signed-in account's address; present only when signed in.
    pub email: Option<String>,
    pub stage: GoogleStage,
    pub failure: Option<Failure>,
    pub sentence: Option<String>,
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

/// A part of an item's plan: `program`, or the catalogue role a model serves.
fn is_part_id(text: &str) -> bool {
    text.len() <= 64
        && text.bytes().next().is_some_and(|b| b.is_ascii_lowercase())
        && text
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_')
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

/// A catalogue model name, as `dependencies.setup` accepts one.
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
            && plain(&self.name, NAME_LIMIT)
            && plain(&self.sentence, SENTENCE_LIMIT)
            && plain_option(self.note.as_ref(), SENTENCE_LIMIT)
            && plain_option(self.action_label.as_ref(), NAME_LIMIT)
            && plain_option(self.version.as_ref(), VERSION_LIMIT)
            && self.recovery.is_some() == self.action_label.is_some()
            && self.recovery.is_some() == self.recovery_action_id.is_some()
            && self.recovery_action_id.as_deref().is_none_or(is_action_id)
            && reasons.iter().filter(|present| **present).count() <= 1
            && (self.stale_reason.is_none() || self.state == State::Stale)
            && (self.blocked_reason.is_none() || self.state == State::Blocked)
            && (self.failure.is_none() || self.state == State::Failed)
    }
}

impl Review {
    fn valid(&self) -> bool {
        is_hex64(&self.plan_digest)
            && plain_option(self.expires_at.as_ref(), 64)
            && !self.entries.is_empty()
            && self.entries.len() <= MAX_ITEMS
            && unique(self.entries.iter().map(|entry| &entry.item))
            && self.entries.iter().all(|entry| {
                is_item_id(&entry.item)
                    && plain(&entry.name, NAME_LIMIT)
                    && !entry.source_hosts.is_empty()
                    && entry.source_hosts.len() <= MAX_HOSTS
                    && entry.source_hosts.iter().all(|host| is_host(host))
                    && unique(&entry.source_hosts)
                    && plain_option(entry.destination.as_ref(), PATH_LIMIT)
                    && plain_option(entry.licence_notice.as_ref(), SENTENCE_LIMIT)
                    && (entry.advisories.is_empty() || entry.item == "local_ai")
                    && (entry.parts.is_empty() || entry.item == "local_ai")
                    && entry.parts.len() <= MAX_ITEMS
                    && unique(entry.parts.iter().map(|part| &part.part))
                    && entry
                        .parts
                        .iter()
                        .all(|part| is_part_id(&part.part) && plain(&part.name, NAME_LIMIT))
                    && entry.advisories.iter().collect::<BTreeSet<_>>().len()
                        == entry.advisories.len()
                    && entry.licence_notice.is_some()
                        == entry
                            .advisories
                            .contains(&Advisory::LicenceCommercialUseBarred)
                    && entry
                        .shares_download_with
                        .as_deref()
                        .is_none_or(|other| is_item_id(other) && other != entry.item)
            })
            && self.space_sufficient
                == self
                    .free_bytes
                    .is_some_and(|free| free >= self.required_bytes)
    }
}

impl ItemProgress {
    fn valid(&self) -> bool {
        is_item_id(&self.item)
            && plain(&self.name, NAME_LIMIT)
            && self.completed.is_some() == self.total.is_some()
            && self
                .completed
                .zip(self.total)
                .is_none_or(|(completed, total)| total > 0 && completed <= total)
            && self.retry.as_ref().is_none_or(|retry| {
                retry.attempt >= 2 && retry.delay_s >= 1 && plain(&retry.sentence, SENTENCE_LIMIT)
            })
            && self.result.as_ref().is_none_or(|result| {
                result.failure.is_some() == result.sentence.is_some()
                    && plain_option(result.sentence.as_ref(), SENTENCE_LIMIT)
            })
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
            && (self.outcome == Some(Outcome::Failed)) == self.failure_sentence.is_some()
            && plain_option(self.failure_sentence.as_ref(), SENTENCE_LIMIT)
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
            && self.google.failure.is_some() == self.google.sentence.is_some()
            && plain_option(self.google.sentence.as_ref(), SENTENCE_LIMIT)
            && (self.google.email.is_none() || self.google.state == Some(GoogleState::SignedIn))
            && plain_option(self.google.email.as_ref(), NAME_LIMIT)
            && self.details.len() <= DETAILS_LIMIT
            && !self.details.chars().any(|c| c.is_control() && c != '\n')
    }
}

/// One setup action the window asked for, in its closed form.
#[derive(Clone, Debug, PartialEq)]
pub enum Action {
    Observe,
    Check(CheckMode),
    Verify(Option<Vec<String>>),
    Start {
        items: Option<Vec<String>>,
        model: Option<String>,
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

/// Setup of `items`, or of every item not ready, planned first.
pub fn start_request(
    selected: Option<Vec<String>>,
    model: Option<String>,
    resume: bool,
) -> Result<Action, ApplicationError> {
    if model.as_deref().is_some_and(|model| !is_model_name(model)) {
        return Err(invalid());
    }
    Ok(Action::Start {
        items: items(selected)?,
        model,
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
            "version": null, "size_bytes": 180000000,
            "name": "Browser for the tax agency website", "sentence": "Not set up yet.",
            "note": null, "action_label": "Set up",
        })
    }

    fn review() -> Value {
        json!({
            "plan_digest": "a".repeat(64), "expires_at": "2026-10-18T10:00:00+00:00",
            "entries": [{
                "item": "browser", "name": "Browser for the tax agency website",
                "download_bytes": 100, "source_hosts": ["cdn.playwright.dev"],
                "destination": "C:\\Cadrumo\\components\\playwright",
                "installs_outside_program": false, "shares_download_with": null,
                "advisories": [], "licence_notice": null, "parts": [],
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
                "item": "browser", "name": "Browser for the tax agency website",
                "step": "download", "completed": 40, "total": 100,
                "retry": {"attempt": 2, "delay_s": 4, "sentence": "Trying again in 4 seconds."},
                "result": null,
            }],
            "cancellable": stage == "running", "cancel_requested": false,
            "outcome": if stage == "settled" { json!("completed") } else { Value::Null },
            "failure_sentence": null,
        })
    }

    fn snapshot() -> Value {
        json!({
            "rows": [row()], "rows_mode": "quick", "complete": false, "hardware_limited": false,
            "check": {"operation_id": "c".repeat(64), "kind": "status_quick", "stage": "done"},
            "setup": run("review"),
            "google": {"state": "signed_out", "email": null, "stage": "idle", "failure": null, "sentence": null},
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
    fn a_value_outside_a_closed_set_or_a_bound_is_a_protocol_failure() {
        let cases: [Case; 20] = [
            ("unknown state", |s| s["rows"][0]["state"] = json!("broken")),
            ("unknown field", |s| s["rows"][0]["path"] = json!("C:\\")),
            ("bad item", |s| s["rows"][0]["item"] = json!("printer")),
            ("label without recovery", |s| {
                s["rows"][0]["recovery"] = Value::Null
            }),
            ("reason on another state", |s| {
                s["rows"][0]["failure"] = json!("offline")
            }),
            ("control text", |s| {
                s["rows"][0]["sentence"] = json!("a\u{7}b")
            }),
            ("empty sentence", |s| s["rows"][0]["sentence"] = json!("")),
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
            (
                "google failure without sentence",
                |s| s["google"] = json!({"state": "signed_out", "email": null, "stage": "failed", "failure": "offline", "sentence": null}),
            ),
            ("google address while signed out", |s| {
                s["google"]["email"] = json!("person@example.com")
            }),
            ("part outside the local AI", |s| {
                s["setup"]["review"]["entries"][0]["parts"] =
                    json!([{"part": "program", "name": "Program", "download_bytes": null}])
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
    fn a_settled_run_carries_its_outcome_and_a_failed_one_its_sentence() {
        let mut settled = snapshot();
        settled["setup"] = run("settled");
        settled["setup"]["outcome"] = json!("failed");
        assert!(parsed(settled.clone()).is_none());
        settled["setup"]["failure_sentence"] = json!("Something unexpected happened.");
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
            start_request(Some(vec!["local_ai".into()]), Some("qwen3:4b".into()), true).unwrap(),
            Action::Start {
                items: Some(vec!["local_ai".into()]),
                model: Some("qwen3:4b".into()),
                resume: true,
            }
        );
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
        for model in ["", "-x", "a b", "a\\b", &"m".repeat(129)] {
            assert!(
                start_request(None, Some(model.to_owned()), false).is_err(),
                "{model}"
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
            {"part": "program", "name": "The program that runs the models", "download_bytes": null},
            {"part": "text_extraction", "name": "Model for document text", "download_bytes": 100},
        ]);
        entry["advisories"] = json!(["licence_commercial_use_barred", "fit_unverified"]);
        entry["licence_notice"] = json!("This model may be used for non-commercial purposes only.");
        licensed
    }

    #[test]
    fn a_model_entry_carries_its_closed_advisories_and_licence_notice() {
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
            ("notice without the barred advisory", |e| {
                e["advisories"] = json!(["licence_unverified"])
            }),
            ("barred advisory without notice", |e| {
                e["licence_notice"] = Value::Null
            }),
            ("control text", |e| e["licence_notice"] = json!("a	b")),
            ("empty notice", |e| e["licence_notice"] = json!("")),
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
