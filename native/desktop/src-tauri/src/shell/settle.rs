//! Following an operation a window submitted over the held person's relay,
//! until it settles or waits on the person: the outcome the window is told,
//! the review it reads and answers by digest, cancellation at an observed
//! revision, and the bounded record of which operations this window may still
//! follow. Shared by the host families; no family's meaning lives here: a
//! caller names the definition, says whether it may write, which result
//! fields name a file, and which folders its payload put files from.
use super::relay::{self, Failure, Relayed, Result, lock, protocol};
use super::user_profile::ProfileHost;
use crate::agent::person::{HeldPerson, PersonEvent};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{collections::VecDeque, sync::Mutex};
use tokio::sync::broadcast::Receiver;

/// How many submitted operations the window may still follow.
const TRACKED_LIMIT: usize = 64;

fn failure(code: &'static str) -> Failure {
    Failure::new(code)
}

/// What the settle loop needs to know of one admitted definition.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) struct Settling {
    pub(super) id: &'static str,
    /// May change records: an outcome that was not observed is unknown.
    pub(super) mutation: bool,
    /// Result fields that name a file the worker read or wrote.
    pub(super) result_paths: &'static [&'static str],
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
impl Outcome {
    fn operation_id(&self) -> &str {
        match self {
            Self::Settled { operation_id, .. }
            | Self::Refused { operation_id, .. }
            | Self::Review { operation_id, .. }
            | Self::Running { operation_id, .. } => operation_id,
        }
    }
}

/// The review a paused operation shows, with the digest an answer must name.
#[derive(Debug, Serialize)]
pub struct ReviewDocument {
    operation_id: String,
    revision: u64,
    pub(super) review_digest: String,
    expires_at: Option<String>,
    pub(super) review: Value,
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
pub(super) struct Shown {
    interaction_id: Value,
    revision: Value,
    digest: String,
}
/// One operation this window submitted, for the session that submitted it.
#[derive(Clone, Debug)]
pub(super) struct Tracked {
    pub(super) operation: String,
    pub(super) definition: Settling,
    pub(super) subject: String,
    pub(super) identity: Value,
    pub(super) shown: Option<Shown>,
    /// The folders of the files the host put in its payload.
    folders: Vec<String>,
}
impl Tracked {
    pub(super) fn new(
        operation: String,
        definition: Settling,
        subject: String,
        identity: Value,
        folders: Vec<String>,
    ) -> Self {
        Self {
            operation,
            definition,
            subject,
            identity,
            shown: None,
            folders,
        }
    }
    fn relayed<'a>(&'a self, person: &'a HeldPerson) -> Relayed<'a> {
        Relayed {
            person,
            operation: self.operation.clone(),
            definition: self.definition.id,
            subject: self.subject.clone(),
        }
    }
    /// What the window is shown of a document the runtime answered for it.
    fn reduced(&self, document: &Value) -> Value {
        reduced(document, self.definition.result_paths, &self.folders)
    }
}

/// The operations this window submitted, for the session that submitted them.
#[derive(Default)]
pub(super) struct Operations(Mutex<VecDeque<Tracked>>);
impl Operations {
    pub(super) fn track(&self, tracked: Tracked) {
        let mut operations = lock(&self.0);
        // A new session's window follows none of the previous session's.
        operations.retain(|other| other.identity == tracked.identity);
        if operations.len() >= TRACKED_LIMIT {
            operations.pop_front();
        }
        operations.push_back(tracked);
    }
    pub(super) fn find(&self, operation: &str) -> Result<Tracked> {
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
    pub(super) fn clear(&self) {
        lock(&self.0).clear();
    }
}

/// Reduces every absolute path a result names under one of `keys` to its
/// file name. The window names files and never holds where they are, and a
/// folder can carry the person's own name.
fn file_names(value: &mut Value, keys: &[&str]) {
    // Split on both separators: the worker's platform decides the spelling,
    // not the host's.
    fn named(text: &mut String) {
        let bytes = text.as_bytes();
        let drive = bytes.len() > 2
            && bytes[0].is_ascii_alphabetic()
            && bytes[1] == b':'
            && matches!(bytes[2], b'\\' | b'/');
        // A local attachment's locator can also be a file URI.
        let uri = text
            .get(..5)
            .is_some_and(|scheme| scheme.eq_ignore_ascii_case("file:"));
        if drive || uri || text.starts_with(['/', '\\']) {
            let name = text
                .rsplit(['/', '\\'])
                .next()
                .unwrap_or_default()
                .to_owned();
            *text = name;
        }
    }
    match value {
        Value::Object(fields) => {
            for (key, field) in fields.iter_mut() {
                match field {
                    Value::String(text) if keys.contains(&key.as_str()) => named(text),
                    Value::Array(items) if keys.contains(&key.as_str()) => {
                        for item in items.iter_mut() {
                            match item {
                                Value::String(text) => named(text),
                                other => file_names(other, keys),
                            }
                        }
                    }
                    other => file_names(other, keys),
                }
            }
        }
        Value::Array(items) => items.iter_mut().for_each(|item| file_names(item, keys)),
        _ => {}
    }
}

/// What the window is shown of a document the runtime answered for an
/// operation: every path reduced to its file name, wherever the worker
/// quoted it, as in a message, a review line or a row's source.
fn reduced(document: &Value, keys: &[&str], folders: &[String]) -> Value {
    fn strip(value: &mut Value, folders: &[(String, String)]) {
        match value {
            Value::String(text) => {
                for (folder, name) in folders {
                    if text.contains(folder.as_str()) {
                        *text = text
                            .replace(&format!("{folder}\\"), "")
                            .replace(&format!("{folder}/"), "")
                            .replace(folder.as_str(), name);
                    }
                }
            }
            Value::Array(items) => items.iter_mut().for_each(|item| strip(item, folders)),
            Value::Object(fields) => fields.values_mut().for_each(|field| strip(field, folders)),
            _ => {}
        }
    }
    let mut document = document.clone();
    file_names(&mut document, keys);
    // The worker may spell a folder with either separator; the deepest
    // folder goes first so a nested one is not cut at its parent.
    let mut spellings: Vec<(String, String)> = folders
        .iter()
        .flat_map(|folder| {
            let name = folder
                .rsplit(['/', '\\'])
                .next()
                .unwrap_or_default()
                .to_owned();
            [
                (folder.clone(), name.clone()),
                (folder.replace('\\', "/"), name),
            ]
        })
        .collect();
    spellings.sort_by_key(|(folder, _)| std::cmp::Reverse(folder.len()));
    spellings.dedup();
    strip(&mut document, &spellings);
    document
}

/// The outcome a projection settles to, reading the result where there is one.
async fn outcome(relayed: &Relayed<'_>, p: &Value, tracked: &Tracked) -> Result<Outcome> {
    let mutation = tracked.definition.mutation;
    let operation_id = relayed.operation.clone();
    let revision = p["revision"].as_u64().ok_or_else(protocol)?;
    let cancellable = p["cancellable_now"] == true;
    Ok(match phase(p) {
        Phase::Succeeded => {
            let unread = || {
                failure(if mutation {
                    "saved_unread"
                } else {
                    "unavailable"
                })
            };
            let document = relay::result(relayed).await.map_err(|_| unread())?;
            let result = tracked.reduced(&document["projection"]);
            if !result.is_object() {
                return Err(unread());
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
                    .map(|document| tracked.reduced(&document["projection"]))
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

/// A lost answer is unknown for a mutation, and names its operation.
fn attributed(mut failure: Failure, tracked: &Tracked) -> Failure {
    if tracked.definition.mutation && failure.code == "unavailable" {
        failure.code = "unknown";
    }
    failure.operation_id = Some(tracked.operation.clone());
    failure
}

/// Follows a submitted or answered operation until it settles or waits on
/// the person, within the relay's bound. An outcome not observed in time is
/// unknown for a mutation, which is never sent again.
pub(super) async fn settle(
    events: &mut Receiver<PersonEvent>,
    tracked: &Tracked,
    person: &HeldPerson,
) -> Result<Outcome> {
    let relayed = tracked.relayed(person);
    let mutation = tracked.definition.mutation;
    let settled = tokio::time::timeout(relay::SETTLE_LIMIT, async {
        let p = relay::follow(events, &relayed, waits_on_person).await?;
        outcome(&relayed, &p, tracked).await
    })
    .await
    .unwrap_or_else(|_| Err(failure(if mutation { "unknown" } else { "unavailable" })));
    settled.map_err(|failure| attributed(failure, tracked))
}

/// Where a tracked operation stands now, without waiting.
pub(super) async fn observe_on(tracked: &Tracked, person: &HeldPerson) -> Result<Outcome> {
    let relayed = tracked.relayed(person);
    let observed = match relay::observe(&relayed).await {
        Ok(p) => outcome(&relayed, &p, tracked).await,
        Err(failure) => Err(failure),
    };
    observed.map_err(|failure| attributed(failure, tracked))
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

/// Reads the review a tracked operation shows and remembers its digest, the
/// one an answer must name.
pub(super) async fn review_on(
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
        review: tracked.reduced(review),
    })
}

/// Answers the review the window read, bound to the digest it showed. The
/// relay reads the review again and refuses an answer to a changed one.
pub(super) async fn answer_on(
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
        // The relay answers "unavailable" when the runtime's reply was lost
        // after the answer may have been taken.
        if reply["code"] == "unavailable" {
            return Err(unknown());
        }
        return Err(review_refusal(&reply));
    }
    if reply["kind"] != "operation_responded" || reply["operation_id"] != tracked.operation {
        return Err(unknown());
    }
    settle(events, tracked, person).await
}

/// Asks the runtime to cancel at the revision the window observed, then
/// reports where the operation stands.
pub(super) async fn cancel_on(
    tracked: &Tracked,
    person: &HeldPerson,
    revision: u64,
) -> Result<Outcome> {
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

/// The held person, only while it is the session that submitted `tracked`.
pub(super) async fn holding(profile: &ProfileHost, tracked: &Tracked) -> Result<HeldPerson> {
    let person = profile
        .person(tracked.identity["profile_id"].as_str())
        .await?;
    if relay::identity(&person).await? != tracked.identity {
        return Err(failure("not_signed_in"));
    }
    Ok(person)
}

/// Rejects an answer read while the window's account changed underneath.
pub(super) async fn still_holding(profile: &ProfileHost, person: &HeldPerson) -> Result<()> {
    let identity = relay::identity(person).await?;
    let current = profile.person(identity["profile_id"].as_str()).await?;
    if relay::identity(&current).await? != identity {
        return Err(failure("not_signed_in"));
    }
    Ok(())
}

/// The outcome of an operation submitted for `person`, while that is still
/// the session the window holds. An account that changed after a write was
/// sent leaves the write unknown, never "not sent": it may have committed.
pub(super) async fn still_held(
    profile: &ProfileHost,
    person: &HeldPerson,
    outcome: Outcome,
    mutation: bool,
) -> Result<Outcome> {
    if let Err(changed) = still_holding(profile, person).await {
        if !mutation {
            return Err(changed);
        }
        let mut unknown = failure("unknown");
        unknown.operation_id = Some(outcome.operation_id().to_owned());
        return Err(unknown);
    }
    Ok(outcome)
}

#[cfg(test)]
mod tests {
    use super::*;

    const PATHS: &[&str] = &[
        "files",
        "output_path",
        "path",
        "provider_locator",
        "source_name",
        "source_path",
    ];
    const READ: Settling = Settling {
        id: "family.example-read",
        mutation: false,
        result_paths: PATHS,
    };
    const REVIEWED: Settling = Settling {
        id: "family.example-review",
        mutation: true,
        result_paths: PATHS,
    };

    #[test]
    fn results_name_files_and_never_where_they_are() {
        let mut result = json!({
            "sources": [{"path": r"C:\Users\alba\AEAT\justificante.pdf", "sha256": "ab"}],
            "rows": [{"source_path": "/home/alba/modelos/303.txt", "holder": r"C:\Users\alba"}],
            "output_path": r"\\server\share\modelo-303.txt",
            "files": [r"D:\export\a.ofx", "b.ofx"],
            "review": {"path": "casillas[0].value"},
            "queue": [
                {"provider_locator": r"C:\Users\alba\Facturas\gasolina.pdf"},
                {"provider_locator": "file:///home/alba/facturas/luz.pdf"},
                {"provider_locator": "drive:1AbCdEf"},
            ],
        });
        file_names(&mut result, PATHS);
        assert_eq!(result["sources"][0]["path"], "justificante.pdf");
        assert_eq!(result["sources"][0]["sha256"], "ab");
        assert_eq!(result["rows"][0]["source_path"], "303.txt");
        assert_eq!(result["rows"][0]["holder"], r"C:\Users\alba");
        assert_eq!(result["output_path"], "modelo-303.txt");
        assert_eq!(result["files"], json!(["a.ofx", "b.ofx"]));
        assert_eq!(result["review"]["path"], "casillas[0].value");
        assert_eq!(result["queue"][0]["provider_locator"], "gasolina.pdf");
        assert_eq!(result["queue"][1]["provider_locator"], "luz.pdf");
        assert_eq!(result["queue"][2]["provider_locator"], "drive:1AbCdEf");
    }

    #[test]
    fn a_folder_the_host_filled_in_is_never_shown_wherever_the_worker_quotes_it() {
        let folders = [
            r"C:\Users\alba\Bancos".to_owned(),
            r"C:\Users\alba\Bancos\2026".to_owned(),
        ];
        let document = json!({
            "unresolved": [{"source_name": r"C:\Users\alba\Bancos\2026\n26.csv", "reason": "duplicate"}],
            "message": r"could not read C:/Users/alba/Bancos/ing.csv",
            "context": [{"value": r"in C:\Users\alba\Bancos"}],
            "lines": [r"C:\Users\alba\Bancos\2026\abril\bbva.csv: 3 rows"],
            "supplier": "C:\\Users\\albacete",
            "amount": 12,
        });
        let shown = reduced(&document, PATHS, &folders);
        assert_eq!(shown["unresolved"][0]["source_name"], "n26.csv");
        assert_eq!(shown["unresolved"][0]["reason"], "duplicate");
        assert_eq!(shown["message"], "could not read ing.csv");
        assert_eq!(shown["context"][0]["value"], "in Bancos");
        assert_eq!(shown["lines"][0], r"abril\bbva.csv: 3 rows");
        assert_eq!(shown["supplier"], "C:\\Users\\albacete");
        assert_eq!(shown["amount"], 12);
        assert!(!shown.to_string().contains("alba\\"));
    }

    fn projection(lifecycle: &str) -> Value {
        json!({"lifecycle":lifecycle, "terminal_condition":null, "effect":"none",
            "refusal_ref":null, "failure_error_code":null, "revision":3, "cancellable_now":false,
            "pending_interaction":{"disposition":"none"}})
    }

    #[test]
    fn only_a_settled_no_effect_stop_is_a_refusal_and_any_other_effect_is_unknown() {
        let mut p = projection("terminal");
        p["terminal_condition"] = json!("succeeded");
        p["effect"] = json!("updated");
        assert_eq!(phase(&p), Phase::Succeeded);
        p["terminal_condition"] = json!("refused");
        p["effect"] = json!("none");
        p["refusal_ref"] = json!("REFUSED_CLI_VALIDATION_BOUNDARY");
        assert_eq!(
            phase(&p),
            Phase::Stopped(Some("REFUSED_CLI_VALIDATION_BOUNDARY".into()))
        );
        p["terminal_condition"] = json!("failed");
        p["refusal_ref"] = Value::Null;
        p["failure_error_code"] = json!("FAIL_EXAMPLE");
        assert_eq!(phase(&p), Phase::Stopped(Some("FAIL_EXAMPLE".into())));
        for effect in ["unknown", "partial", "updated"] {
            p["effect"] = json!(effect);
            assert_eq!(phase(&p), Phase::Unknown, "{effect}");
        }
        let mut paused = projection("running");
        assert_eq!(phase(&paused), Phase::Running);
        assert!(!waits_on_person(&paused));
        paused["pending_interaction"] = json!({"disposition":"review_available"});
        assert_eq!(phase(&paused), Phase::Review);
        assert!(waits_on_person(&paused));
        // An input or choice the window cannot answer still stops following.
        paused["pending_interaction"] = json!({"disposition":"unsupported"});
        assert_eq!(phase(&paused), Phase::Running);
        assert!(waits_on_person(&paused));
    }

    #[test]
    fn a_window_follows_only_its_own_sessions_operations() {
        let operations = Operations::default();
        let tracked = |operation: &str, session: &str| {
            Tracked::new(
                operation.into(),
                READ,
                "profile:p".into(),
                json!({"profile_id":"p","session_id":session}),
                Vec::new(),
            )
        };
        operations.track(tracked("a", "one"));
        assert!(operations.find("a").is_ok());
        assert_eq!(operations.find("b").unwrap_err().code, "not_admitted");
        operations.track(tracked("b", "two"));
        assert!(
            operations.find("a").is_err(),
            "a new session forgets the last"
        );
        for at in 0..TRACKED_LIMIT {
            operations.track(tracked(&format!("n{at}"), "two"));
        }
        assert!(
            operations.find("b").is_err(),
            "the oldest is forgotten first"
        );
        assert!(operations.find(&format!("n{}", TRACKED_LIMIT - 1)).is_ok());
        operations.clear();
        assert!(operations.find("n0").is_err());
    }

    #[test]
    fn outcomes_and_failures_reach_the_window_in_the_contracts_shape() {
        let settled = Outcome::Settled {
            operation_id: "op".into(),
            revision: 4,
            result: json!({"rows":[]}),
        };
        assert_eq!(
            serde_json::to_value(&settled).unwrap(),
            json!({"kind":"settled","operation_id":"op","revision":4,"result":{"rows":[]}})
        );
        let running = Outcome::Running {
            operation_id: "op".into(),
            revision: 2,
            cancellable: true,
        };
        assert_eq!(
            serde_json::to_value(&running).unwrap(),
            json!({"kind":"running","operation_id":"op","revision":2,"cancellable":true})
        );
        let review = Outcome::Review {
            operation_id: "op".into(),
            revision: 2,
            cancellable: false,
        };
        assert_eq!(serde_json::to_value(&review).unwrap()["kind"], "review");
        let mut failure = Failure::new("refused");
        assert_eq!(
            serde_json::to_value(&failure).unwrap(),
            json!({"code":"refused","operation_id":null}),
            "a failure without a reason keeps the profile pages' shape"
        );
        failure.reason = Some("subject_busy".into());
        assert_eq!(
            serde_json::to_value(&failure).unwrap()["reason"],
            "subject_busy"
        );
        assert_eq!(
            review_refusal(&json!({"kind":"operation_refused","code":"not_pending"})).code,
            "review_changed"
        );
        assert_eq!(
            review_refusal(&json!({"kind":"operation_refused","code":"unavailable"})).code,
            "refused"
        );
        let lost = attributed(
            Failure::new("unavailable"),
            &Tracked::new("op".into(), REVIEWED, "s".into(), json!({}), Vec::new()),
        );
        assert_eq!(
            (lost.code, lost.operation_id.as_deref()),
            ("unknown", Some("op")),
            "a lost answer to a mutation is unknown, never unavailable"
        );
        let read = attributed(
            Failure::new("unavailable"),
            &Tracked::new("op".into(), READ, "s".into(), json!({}), Vec::new()),
        );
        assert_eq!(read.code, "unavailable");
    }

    #[cfg(windows)]
    mod relayed {
        use super::super::super::scripted::{OPERATION, PROFILE, holder, observed, resulted, step};
        use super::*;

        fn subject() -> String {
            relay::subject(PROFILE)
        }
        fn tracked(definition: Settling, identity: &Value) -> Tracked {
            Tracked::new(
                OPERATION.into(),
                definition,
                subject(),
                identity.clone(),
                Vec::new(),
            )
        }
        fn review(digest: &str, projection: Value) -> Value {
            json!({"kind":"operation_review","operation_id":OPERATION,
                "interaction_id":"i-1","revision":5,"expires_at":null,
                "review_digest":digest, "document":{"projection":projection}})
        }

        #[tokio::test]
        async fn a_settled_effect_the_projection_does_not_name_is_unknown() {
            let held = holder(|_| {
                vec![step(
                    "operation_observe",
                    json!([["operation_id", OPERATION]]),
                    observed(
                        REVIEWED.id,
                        &subject(),
                        "terminal",
                        json!({"terminal_condition":"failed","effect":"partial"}),
                    ),
                    false,
                )]
            });
            let mut events = held.events.subscribe();
            let lost = settle(
                &mut events,
                &tracked(REVIEWED, &held.identity),
                &held.person,
            )
            .await
            .unwrap_err();
            assert_eq!(lost.code, "unknown");
            assert_eq!(lost.operation_id.as_deref(), Some(OPERATION));
        }

        #[tokio::test]
        async fn a_pending_input_stops_following_as_running() {
            let held = holder(|_| {
                vec![step(
                    "operation_observe",
                    json!([]),
                    observed(
                        REVIEWED.id,
                        &subject(),
                        "running",
                        json!({"pending_interaction":{"disposition":"unsupported"},
                            "revision":4, "cancellable_now":true}),
                    ),
                    false,
                )]
            });
            let mut events = held.events.subscribe();
            let outcome = settle(
                &mut events,
                &tracked(REVIEWED, &held.identity),
                &held.person,
            )
            .await
            .unwrap();
            assert_eq!(
                outcome,
                Outcome::Running {
                    operation_id: OPERATION.into(),
                    revision: 4,
                    cancellable: true,
                }
            );
        }

        #[tokio::test]
        async fn a_settled_refusal_carries_its_code_and_declared_detail() {
            let detail = json!({"detail_version":1,"kind":"registered_error",
                "error_code":"REFUSED_CLI_VALIDATION_BOUNDARY","context":[],
                "source_path": r"C:\Users\alba\justificante.pdf"});
            let held = holder(|_| {
                vec![
                    step(
                        "operation_observe",
                        json!([]),
                        observed(
                            READ.id,
                            &subject(),
                            "terminal",
                            json!({"terminal_condition":"refused",
                                "refusal_ref":"REFUSED_CLI_VALIDATION_BOUNDARY"}),
                        ),
                        false,
                    ),
                    step(
                        "operation_result",
                        json!([]),
                        resulted(READ.id, detail.clone()),
                        false,
                    ),
                ]
            });
            let mut events = held.events.subscribe();
            let outcome = settle(&mut events, &tracked(READ, &held.identity), &held.person)
                .await
                .unwrap();
            let Outcome::Refused { reason, detail, .. } = outcome else {
                panic!("the refusal settled");
            };
            assert_eq!(reason.as_deref(), Some("REFUSED_CLI_VALIDATION_BOUNDARY"));
            assert_eq!(detail.unwrap()["source_path"], "justificante.pdf");
        }

        #[tokio::test]
        async fn a_review_is_answered_only_with_the_digest_the_window_was_shown() {
            let digest = "c".repeat(64);
            let held = holder(|_| {
                vec![
                    step(
                        "operation_review",
                        json!([["operation_id", OPERATION]]),
                        review(
                            &"c".repeat(64),
                            json!({"proposal":{"value":"1"},
                                "source_path": r"C:\Users\alba\303.txt"}),
                        ),
                        false,
                    ),
                    step(
                        "operation_respond",
                        json!([
                            ["interaction_id", "i-1"],
                            ["revision", 5],
                            ["review_digest", "c".repeat(64)],
                            ["decision", "apply"]
                        ]),
                        json!({"kind":"operation_responded","operation_id":OPERATION,"decision":"apply"}),
                        true,
                    ),
                    step(
                        "operation_observe",
                        json!([]),
                        observed(
                            REVIEWED.id,
                            &subject(),
                            "terminal",
                            json!({"terminal_condition":"succeeded","effect":"updated","revision":7}),
                        ),
                        false,
                    ),
                    step(
                        "operation_result",
                        json!([]),
                        resulted(REVIEWED.id, json!({"outcome":"applied"})),
                        false,
                    ),
                ]
            });
            let operations = Operations::default();
            operations.track(tracked(REVIEWED, &held.identity));
            let mut events = held.events.subscribe();
            let unshown = operations.find(OPERATION).unwrap();
            assert_eq!(
                answer_on(
                    &operations,
                    &unshown,
                    &held.person,
                    &mut events,
                    &digest,
                    Decision::Apply
                )
                .await
                .unwrap_err()
                .code,
                "review_changed",
                "nothing was shown yet: no answer is sent"
            );
            let shown = review_on(&operations, &unshown, &held.person)
                .await
                .unwrap();
            assert_eq!(shown.review_digest, digest);
            assert_eq!(
                shown.review["source_path"], "303.txt",
                "a review names files and never where they are"
            );
            let tracked = operations.find(OPERATION).unwrap();
            assert_eq!(
                answer_on(
                    &operations,
                    &tracked,
                    &held.person,
                    &mut events,
                    &"d".repeat(64),
                    Decision::Apply
                )
                .await
                .unwrap_err()
                .code,
                "review_changed",
                "another digest is refused here, without an exchange"
            );
            let settled = answer_on(
                &operations,
                &tracked,
                &held.person,
                &mut events,
                &digest,
                Decision::Apply,
            )
            .await
            .unwrap();
            assert_eq!(
                settled,
                Outcome::Settled {
                    operation_id: OPERATION.into(),
                    revision: 7,
                    result: json!({"outcome":"applied"}),
                }
            );
            assert!(operations.find(OPERATION).unwrap().shown.is_none());
        }

        #[tokio::test]
        async fn an_answer_is_unknown_when_its_reply_was_lost_and_changed_when_refused_so() {
            for (code, expected) in [
                ("unavailable", "unknown"),
                ("review_changed", "review_changed"),
            ] {
                let held = holder(|_| {
                    vec![
                        step(
                            "operation_review",
                            json!([]),
                            review(&"c".repeat(64), json!({"proposal":{}})),
                            false,
                        ),
                        step(
                            "operation_respond",
                            json!([]),
                            json!({"kind":"operation_refused","code":code,"holder_operation_id":null}),
                            false,
                        ),
                    ]
                });
                let operations = Operations::default();
                operations.track(tracked(REVIEWED, &held.identity));
                let tracked = operations.find(OPERATION).unwrap();
                review_on(&operations, &tracked, &held.person)
                    .await
                    .unwrap();
                let tracked = operations.find(OPERATION).unwrap();
                let mut events = held.events.subscribe();
                let failed = answer_on(
                    &operations,
                    &tracked,
                    &held.person,
                    &mut events,
                    &"c".repeat(64),
                    Decision::Reject,
                )
                .await
                .unwrap_err();
                assert_eq!(failed.code, expected, "{code}");
                if expected == "unknown" {
                    assert_eq!(failed.operation_id.as_deref(), Some(OPERATION));
                }
                assert!(operations.find(OPERATION).unwrap().shown.is_none());
            }
        }

        #[tokio::test]
        async fn a_cancel_names_the_observed_revision_and_a_refusal_keeps_its_code() {
            let held = holder(|_| {
                vec![step(
                    "operation_cancel",
                    json!([["operation_id", OPERATION], ["expected_revision", 9]]),
                    json!({"kind":"operation_refused","code":"cancellation_unsupported",
                        "holder_operation_id":null}),
                    false,
                )]
            });
            let refused = cancel_on(&tracked(REVIEWED, &held.identity), &held.person, 9)
                .await
                .unwrap_err();
            assert_eq!(refused.code, "refused");
            assert_eq!(refused.reason.as_deref(), Some("cancellation_unsupported"));
            assert_eq!(refused.operation_id.as_deref(), Some(OPERATION));
        }
    }
}
