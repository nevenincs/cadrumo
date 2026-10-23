//! The desktop Ledger page's channel to the ledger family's registered
//! operations, over the held person's relay. The window names one admitted
//! definition and a JSON object; the runtime decodes it against the
//! definition's registered contract, which this host does not restate. The
//! host fills the profile, keeps paths and secrets away from the window, and
//! bounds the request. It keeps no ledger data: a result is passed on and
//! dropped. It remembers only which operations this window submitted, so the
//! window can follow, answer and cancel those and no other.
mod admitted;

use super::relay::{self, Failure, Relayed, Result, lock, protocol};
use super::user_profile::ProfileHost;
use crate::agent::person::{self, HeldPerson, PersonEvent};
use admitted::{Definition, admitted};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value, json};
use std::{
    collections::VecDeque,
    sync::{Arc, Mutex},
};
use tauri::State;
use tokio::sync::broadcast::Receiver;

/// The relay ends the held session for a payload over its own bound, so the
/// host refuses one well before it: number spellings can differ between the
/// two JSON encoders by a character or two.
const PAYLOAD_HEADROOM: usize = 256;
/// The longest payload, in characters of compact JSON, the host sends.
pub(crate) const PAYLOAD_LIMIT: usize = 12_288 - PAYLOAD_HEADROOM;
/// How many submitted operations the window may still follow.
const TRACKED_LIMIT: usize = 64;

/// Fields the host fills itself. The window never names a profile or a
/// directory.
const HOST_FIELDS: [&str; 2] = ["profile_id", "source_directory"];
/// Fields that name a local file, by definition.
const PATH_FIELDS: [(&str, &str); 6] = [
    ("ledger.evidence.add", "source_path"),
    ("ledger.evidence.batch", "sources"),
    ("ledger.export", "output_path"),
    ("ledger.import", "files"),
    ("ledger.import", "verify_source"),
    ("ledger.invoice.import", "source_path"),
];
/// An own account's number and bank block: private input that travels only
/// in a raw request body.
const OWN_ACCOUNT_SECRETS: [&str; 6] = [
    "iban",
    "swift_bic",
    "bank_name",
    "bank_address",
    "bank_city",
    "bank_country_code",
];
const OWN_ACCOUNT: &str = "ledger.own_account";

fn failure(code: &'static str) -> Failure {
    Failure::new(code)
}

/// Where an operation the window submitted stands. A refusal the runtime
/// settled carries its closed code and, where the definition declares one,
/// its detail document.
#[derive(Debug, PartialEq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Outcome {
    Settled {
        operation_id: String,
        revision: u64,
        result: Value,
    },
    Refused {
        operation_id: String,
        revision: u64,
        reason: Option<String>,
        detail: Option<Value>,
    },
    /// Paused until the person answers the review it shows.
    Review {
        operation_id: String,
        revision: u64,
        cancellable: bool,
    },
    Running {
        operation_id: String,
        revision: u64,
        cancellable: bool,
    },
}

/// The review a paused operation shows, with the digest an answer must name.
#[derive(Debug, Serialize)]
pub struct ReviewDocument {
    operation_id: String,
    revision: u64,
    review_digest: String,
    expires_at: Option<String>,
    review: Value,
}

#[derive(Clone, Copy, Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Decision {
    Apply,
    Reject,
}

/// What a projection says to do next.
#[derive(Debug, PartialEq)]
enum Phase {
    Succeeded,
    /// Settled without changing anything: refused, failed or cancelled.
    Stopped(Option<String>),
    /// Settled with an effect the projection does not name.
    Unknown,
    Review,
    Running,
}
fn phase(p: &Value) -> Phase {
    if p["lifecycle"] == "terminal" {
        if p["terminal_condition"] == "succeeded" {
            Phase::Succeeded
        } else if p["effect"] != "none" {
            Phase::Unknown
        } else {
            Phase::Stopped(
                p["refusal_ref"]
                    .as_str()
                    .or_else(|| p["failure_error_code"].as_str())
                    .map(str::to_owned),
            )
        }
    } else if p["pending_interaction"]["disposition"] == "review_available" {
        Phase::Review
    } else {
        Phase::Running
    }
}
/// Whether following can stop before settlement: the person must act.
fn waits_on_person(p: &Value) -> bool {
    !matches!(
        p["pending_interaction"]["disposition"].as_str(),
        Some("none") | None
    )
}

/// The review this window read for an operation: an answer binds to it.
#[derive(Clone, Debug)]
struct Shown {
    interaction_id: Value,
    revision: Value,
    digest: String,
}
#[derive(Clone, Debug)]
struct Tracked {
    operation: String,
    definition: Definition,
    subject: String,
    identity: Value,
    shown: Option<Shown>,
}
impl Tracked {
    fn relayed<'a>(&'a self, person: &'a HeldPerson) -> Relayed<'a> {
        Relayed {
            person,
            operation: self.operation.clone(),
            definition: self.definition.id,
            subject: self.subject.clone(),
        }
    }
}

/// The operations this window submitted, for the session that submitted them.
#[derive(Default)]
struct Operations(Mutex<VecDeque<Tracked>>);
impl Operations {
    fn track(&self, tracked: Tracked) {
        let mut operations = lock(&self.0);
        // A new session's window follows none of the previous session's.
        operations.retain(|other| other.identity == tracked.identity);
        if operations.len() >= TRACKED_LIMIT {
            operations.pop_front();
        }
        operations.push_back(tracked);
    }
    fn find(&self, operation: &str) -> Result<Tracked> {
        lock(&self.0)
            .iter()
            .find(|tracked| tracked.operation == operation)
            .cloned()
            .ok_or_else(|| failure("not_admitted"))
    }
    fn show(&self, operation: &str, shown: Option<Shown>) {
        if let Some(tracked) = lock(&self.0)
            .iter_mut()
            .find(|tracked| tracked.operation == operation)
        {
            tracked.shown = shown;
        }
    }
    fn clear(&self) {
        lock(&self.0).clear();
    }
}

/// Refuses a payload the host must not pass on: one that is not an object,
/// names a field the host fills, names a path, or carries an own account's
/// secret outside its raw body.
fn admit_fields(definition: Definition, payload: &Map<String, Value>) -> Result<()> {
    let refused = HOST_FIELDS.iter().any(|field| payload.contains_key(*field))
        || PATH_FIELDS
            .iter()
            .any(|(id, field)| *id == definition.id && payload.contains_key(*field))
        || (definition.id == OWN_ACCOUNT
            && OWN_ACCOUNT_SECRETS
                .iter()
                .any(|field| payload.contains_key(*field)));
    if refused {
        return Err(failure("invalid"));
    }
    Ok(())
}

/// Refuses a request the relay could not take, before anything is written to
/// it. The window splits a batch that is too large; the host never does.
fn admit_size(document: &Value) -> Result<()> {
    let fits_payload = serde_json::to_string(&document["payload"])
        .is_ok_and(|text| text.chars().count() <= PAYLOAD_LIMIT);
    if !fits_payload || !person::request_fits(document) {
        return Err(failure("too_large"));
    }
    Ok(())
}

/// The outcome a projection settles to, reading the result where there is one.
async fn outcome(relayed: &Relayed<'_>, p: &Value, mutation: bool) -> Result<Outcome> {
    let operation_id = relayed.operation.clone();
    let revision = p["revision"].as_u64().ok_or_else(protocol)?;
    let cancellable = p["cancellable_now"] == true;
    Ok(match phase(p) {
        Phase::Succeeded => {
            let document = relay::result(relayed).await.map_err(|_| {
                failure(if mutation {
                    "saved_unread"
                } else {
                    "unavailable"
                })
            })?;
            let result = document["projection"].clone();
            if !result.is_object() {
                return Err(failure(if mutation {
                    "saved_unread"
                } else {
                    "unavailable"
                }));
            }
            Outcome::Settled {
                operation_id,
                revision,
                result,
            }
        }
        Phase::Unknown => return Err(failure("unknown")),
        Phase::Stopped(reason) => {
            // The relay reads a refusal's detail only where its definition
            // declares one, and refuses the read otherwise.
            let detail = if p["terminal_condition"] == "refused" {
                relay::result(relayed)
                    .await
                    .ok()
                    .map(|document| document["projection"].clone())
                    .filter(Value::is_object)
            } else {
                None
            };
            Outcome::Refused {
                operation_id,
                revision,
                reason,
                detail,
            }
        }
        Phase::Review => Outcome::Review {
            operation_id,
            revision,
            cancellable,
        },
        Phase::Running => Outcome::Running {
            operation_id,
            revision,
            cancellable,
        },
    })
}

/// Follows a submitted or answered operation until it settles or waits on
/// the person, within the relay's bound. An outcome not observed in time is
/// unknown for a mutation, which is never sent again.
async fn settle(
    events: &mut Receiver<PersonEvent>,
    relayed: &Relayed<'_>,
    definition: Definition,
) -> Result<Outcome> {
    let mutation = definition.mutation();
    let settled = tokio::time::timeout(relay::SETTLE_LIMIT, async {
        let p = relay::follow(events, relayed, waits_on_person).await?;
        outcome(relayed, &p, mutation).await
    })
    .await
    .unwrap_or_else(|_| Err(failure(if mutation { "unknown" } else { "unavailable" })));
    settled.map_err(|mut failure| {
        if mutation && failure.code == "unavailable" {
            failure.code = "unknown";
        }
        failure.operation_id = Some(relayed.operation.clone());
        failure
    })
}

/// Submits a payload the host already admitted, for the held profile, and
/// follows it. `events` must be subscribed before this is called.
async fn submit_on(
    operations: &Operations,
    person: &HeldPerson,
    events: &mut Receiver<PersonEvent>,
    definition: Definition,
    mut payload: Map<String, Value>,
) -> Result<Outcome> {
    let identity = relay::identity(person).await?;
    let profile = identity["profile_id"]
        .as_str()
        .ok_or_else(protocol)?
        .to_owned();
    payload.insert("profile_id".into(), json!(profile));
    let subject = relay::subject(&profile);
    let document = json!({"action":"operation_submit", "definition_id":definition.id,
        "subject_ref":subject, "payload":payload});
    admit_size(&document)?;
    let payload = document["payload"].clone();
    let operation = relay::submit(
        person,
        definition.id,
        &subject,
        payload,
        definition.mutation(),
    )
    .await?;
    let tracked = Tracked {
        operation,
        definition,
        subject,
        identity,
        shown: None,
    };
    operations.track(tracked.clone());
    settle(events, &tracked.relayed(person), definition).await
}

async fn observe_on(tracked: &Tracked, person: &HeldPerson) -> Result<Outcome> {
    let relayed = tracked.relayed(person);
    let mutation = tracked.definition.mutation();
    let observed = match relay::observe(&relayed).await {
        Ok(p) => outcome(&relayed, &p, mutation).await,
        Err(failure) => Err(failure),
    };
    observed.map_err(|mut failure| {
        if mutation && failure.code == "unavailable" {
            failure.code = "unknown";
        }
        failure.operation_id = Some(tracked.operation.clone());
        failure
    })
}

fn review_refusal(reply: &Value) -> Failure {
    let mut refused = failure(match reply["code"].as_str() {
        // The review moved on, or its document changed: read it again.
        Some("not_pending" | "review_changed") => "review_changed",
        _ => "refused",
    });
    refused.reason = reply["code"].as_str().map(str::to_owned);
    refused
}

async fn review_on(
    operations: &Operations,
    tracked: &Tracked,
    person: &HeldPerson,
) -> Result<ReviewDocument> {
    let reply = relay::call(
        person,
        json!({"action":"operation_review", "operation_id":tracked.operation}),
    )
    .await?;
    if reply["kind"] == "operation_refused" {
        operations.show(&tracked.operation, None);
        return Err(review_refusal(&reply));
    }
    let digest = reply["review_digest"]
        .as_str()
        .filter(|digest| super::setup::wire::is_hex64(digest));
    let revision = reply["revision"].as_u64();
    let review = &reply["document"]["projection"];
    let (Some(digest), Some(revision), true, true, true) = (
        digest,
        revision,
        reply["kind"] == "operation_review" && reply["operation_id"] == tracked.operation,
        reply["interaction_id"].is_string(),
        review.is_object(),
    ) else {
        return Err(protocol());
    };
    operations.show(
        &tracked.operation,
        Some(Shown {
            interaction_id: reply["interaction_id"].clone(),
            revision: reply["revision"].clone(),
            digest: digest.to_owned(),
        }),
    );
    Ok(ReviewDocument {
        operation_id: tracked.operation.clone(),
        revision,
        review_digest: digest.to_owned(),
        expires_at: reply["expires_at"].as_str().map(str::to_owned),
        review: review.clone(),
    })
}

/// Answers the review the window read, bound to the digest it showed. The
/// relay reads the review again and refuses an answer to a changed one.
async fn answer_on(
    operations: &Operations,
    tracked: &Tracked,
    person: &HeldPerson,
    events: &mut Receiver<PersonEvent>,
    review_digest: &str,
    decision: Decision,
) -> Result<Outcome> {
    let shown = tracked
        .shown
        .as_ref()
        .filter(|shown| shown.digest == review_digest)
        .ok_or_else(|| failure("review_changed"))?;
    let unknown = || {
        let mut unknown = failure("unknown");
        unknown.operation_id = Some(tracked.operation.clone());
        unknown
    };
    let reply = relay::call(
        person,
        json!({"action":"operation_respond", "operation_id":tracked.operation,
            "interaction_id":shown.interaction_id, "revision":shown.revision,
            "review_digest":shown.digest,
            "decision": match decision { Decision::Apply => "apply", Decision::Reject => "reject" }}),
    )
    .await
    .map_err(|_| unknown())?;
    operations.show(&tracked.operation, None);
    if reply["kind"] == "operation_refused" {
        return Err(review_refusal(&reply));
    }
    if reply["kind"] != "operation_responded" || reply["operation_id"] != tracked.operation {
        return Err(unknown());
    }
    settle(events, &tracked.relayed(person), tracked.definition).await
}

/// Asks the runtime to cancel at the revision the window observed, then
/// reports where the operation stands.
async fn cancel_on(tracked: &Tracked, person: &HeldPerson, revision: u64) -> Result<Outcome> {
    let reply = relay::call(
        person,
        json!({"action":"operation_cancel", "operation_id":tracked.operation,
            "expected_revision":revision}),
    )
    .await
    .map_err(|_| {
        let mut unknown = failure("unknown");
        unknown.operation_id = Some(tracked.operation.clone());
        unknown
    })?;
    if reply["kind"] == "operation_refused" {
        let mut refused = failure("refused");
        refused.reason = reply["code"].as_str().map(str::to_owned);
        refused.operation_id = Some(tracked.operation.clone());
        return Err(refused);
    }
    observe_on(tracked, person).await
}

pub struct LedgerHost {
    profile: Arc<ProfileHost>,
    operations: Operations,
}
impl LedgerHost {
    pub fn new(profile: Arc<ProfileHost>) -> Self {
        Self {
            profile,
            operations: Operations::default(),
        }
    }
    pub fn close(&self) {
        self.operations.clear();
    }
    /// The held person, only while it is the session that submitted `tracked`.
    async fn holding(&self, tracked: &Tracked) -> Result<HeldPerson> {
        let person = self
            .profile
            .person(tracked.identity["profile_id"].as_str())
            .await?;
        if relay::identity(&person).await? != tracked.identity {
            return Err(failure("not_signed_in"));
        }
        Ok(person)
    }
    /// Rejects an answer read while the window's account changed underneath.
    async fn still_holding(&self, person: &HeldPerson) -> Result<()> {
        let identity = relay::identity(person).await?;
        let current = self.profile.person(identity["profile_id"].as_str()).await?;
        if relay::identity(&current).await? != identity {
            return Err(failure("not_signed_in"));
        }
        Ok(())
    }
    async fn submit(&self, definition: &str, payload: Value) -> Result<Outcome> {
        let definition = admitted(definition).ok_or_else(|| failure("not_admitted"))?;
        let Value::Object(payload) = payload else {
            return Err(failure("invalid"));
        };
        admit_fields(definition, &payload)?;
        self.relay(definition, payload).await
    }
    /// Submits an admitted payload for the window's signed-in profile.
    async fn relay(&self, definition: Definition, payload: Map<String, Value>) -> Result<Outcome> {
        if self.profile.is_closed() {
            return Err(protocol());
        }
        let _serial = self.profile.serial().await;
        let person = self.profile.person(None).await?;
        let mut events = self.profile.sign_in().person_events();
        let outcome =
            submit_on(&self.operations, &person, &mut events, definition, payload).await?;
        self.still_holding(&person).await?;
        Ok(outcome)
    }
    async fn observe(&self, operation: &str) -> Result<Outcome> {
        let tracked = self.operations.find(operation)?;
        let person = self.holding(&tracked).await?;
        observe_on(&tracked, &person).await
    }
    async fn review(&self, operation: &str) -> Result<ReviewDocument> {
        let tracked = self.operations.find(operation)?;
        let person = self.holding(&tracked).await?;
        let document = review_on(&self.operations, &tracked, &person).await?;
        self.still_holding(&person).await?;
        Ok(document)
    }
    async fn answer(
        &self,
        operation: &str,
        review_digest: &str,
        decision: Decision,
    ) -> Result<Outcome> {
        let _serial = self.profile.serial().await;
        let tracked = self.operations.find(operation)?;
        let person = self.holding(&tracked).await?;
        let mut events = self.profile.sign_in().person_events();
        answer_on(
            &self.operations,
            &tracked,
            &person,
            &mut events,
            review_digest,
            decision,
        )
        .await
    }
    async fn cancel(&self, operation: &str, revision: u64) -> Result<Outcome> {
        let _serial = self.profile.serial().await;
        let tracked = self.operations.find(operation)?;
        let person = self.holding(&tracked).await?;
        cancel_on(&tracked, &person, revision).await
    }
}

/// Submits one admitted ledger operation with `payload`, a JSON object of its
/// registered request without the profile, and follows it until it settles
/// or waits on the person. One attempt: nothing is retried.
#[tauri::command]
async fn ledger_submit(
    host: State<'_, Arc<LedgerHost>>,
    definition: String,
    payload: Value,
) -> Result<Outcome> {
    host.submit(&definition, payload).await
}
/// Where an operation this window submitted stands now, without waiting.
#[tauri::command]
async fn ledger_observe(host: State<'_, Arc<LedgerHost>>, operation: String) -> Result<Outcome> {
    host.observe(&operation).await
}
#[tauri::command]
async fn ledger_review(
    host: State<'_, Arc<LedgerHost>>,
    operation: String,
) -> Result<ReviewDocument> {
    host.review(&operation).await
}
#[tauri::command]
async fn ledger_answer(
    host: State<'_, Arc<LedgerHost>>,
    operation: String,
    review_digest: String,
    decision: Decision,
) -> Result<Outcome> {
    host.answer(&operation, &review_digest, decision).await
}
#[tauri::command]
async fn ledger_cancel(
    host: State<'_, Arc<LedgerHost>>,
    operation: String,
    revision: u64,
) -> Result<Outcome> {
    host.cancel(&operation, revision).await
}

pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        ledger_submit,
        ledger_observe,
        ledger_review,
        ledger_answer,
        ledger_cancel
    ]
}

#[cfg(test)]
mod tests;
