//! Following an operation the window submitted over the held person's relay,
//! until it settles or waits on the person: the outcome the window is told,
//! the review it reads and answers by digest, cancellation at an observed
//! revision, and the bounded record of which operations this window may still
//! follow. No family's meaning lives here: a caller names the definition, says
//! whether it may write, and which result fields name a file.
use super::super::relay::{self, Failure, Relayed, Result, lock, protocol};
use crate::agent::person::{HeldPerson, PersonEvent};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{collections::VecDeque, sync::Mutex};
use tokio::sync::broadcast::Receiver;

/// How many submitted operations the window may still follow.
pub(crate) const TRACKED_LIMIT: usize = 64;

fn failure(code: &'static str) -> Failure {
    Failure::new(code)
}

/// What the settle loop needs to know of one admitted definition.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct Settling {
    pub(crate) id: &'static str,
    /// May change records: an outcome that was not observed is unknown.
    pub(crate) mutation: bool,
    /// Result fields that name a file the worker read or wrote.
    pub(crate) result_paths: &'static [&'static str],
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
/// One operation this window submitted, for the session that submitted it.
#[derive(Clone, Debug)]
pub(crate) struct Tracked {
    pub(crate) operation: String,
    pub(crate) definition: Settling,
    pub(crate) subject: String,
    pub(crate) identity: Value,
    shown: Option<Shown>,
}
impl Tracked {
    pub(crate) fn new(
        operation: String,
        definition: Settling,
        subject: String,
        identity: Value,
    ) -> Self {
        Self {
            operation,
            definition,
            subject,
            identity,
            shown: None,
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
}

/// The operations this window submitted, for the session that submitted them.
#[derive(Default)]
pub(crate) struct Operations(Mutex<VecDeque<Tracked>>);
impl Operations {
    pub(crate) fn track(&self, tracked: Tracked) {
        let mut operations = lock(&self.0);
        // A new session's window follows none of the previous session's.
        operations.retain(|other| other.identity == tracked.identity);
        if operations.len() >= TRACKED_LIMIT {
            operations.pop_front();
        }
        operations.push_back(tracked);
    }
    pub(crate) fn find(&self, operation: &str) -> Result<Tracked> {
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
    pub(crate) fn clear(&self) {
        lock(&self.0).clear();
    }
}

/// Reduces every absolute path a result names under one of `keys` to its
/// file name. The window names files and never holds where they are, and a
/// folder can carry the person's own name.
pub(crate) fn file_names(value: &mut Value, keys: &[&str]) {
    // Split on both separators: the worker's platform decides the spelling,
    // not the host's.
    fn named(text: &mut String) {
        let bytes = text.as_bytes();
        let drive = bytes.len() > 2
            && bytes[0].is_ascii_alphabetic()
            && bytes[1] == b':'
            && matches!(bytes[2], b'\\' | b'/');
        if drive || text.starts_with(['/', '\\']) {
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

/// The outcome a projection settles to, reading the result where there is one.
async fn outcome(relayed: &Relayed<'_>, p: &Value, definition: Settling) -> Result<Outcome> {
    let mutation = definition.mutation;
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
            let mut result = document["projection"].clone();
            file_names(&mut result, definition.result_paths);
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
                    .map(|document| {
                        let mut detail = document["projection"].clone();
                        file_names(&mut detail, definition.result_paths);
                        detail
                    })
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
pub(crate) async fn settle(
    events: &mut Receiver<PersonEvent>,
    tracked: &Tracked,
    person: &HeldPerson,
) -> Result<Outcome> {
    let relayed = tracked.relayed(person);
    let mutation = tracked.definition.mutation;
    let settled = tokio::time::timeout(relay::SETTLE_LIMIT, async {
        let p = relay::follow(events, &relayed, waits_on_person).await?;
        outcome(&relayed, &p, tracked.definition).await
    })
    .await
    .unwrap_or_else(|_| Err(failure(if mutation { "unknown" } else { "unavailable" })));
    settled.map_err(|failure| attributed(failure, tracked))
}

/// Where a tracked operation stands now, without waiting.
pub(crate) async fn observe_on(tracked: &Tracked, person: &HeldPerson) -> Result<Outcome> {
    let relayed = tracked.relayed(person);
    let observed = match relay::observe(&relayed).await {
        Ok(p) => outcome(&relayed, &p, tracked.definition).await,
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
pub(crate) async fn review_on(
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
        .filter(|digest| super::super::setup::wire::is_hex64(digest));
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
pub(crate) async fn answer_on(
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
    settle(events, tracked, person).await
}

/// Asks the runtime to cancel at the revision the window observed, then
/// reports where the operation stands.
pub(crate) async fn cancel_on(
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

#[cfg(test)]
mod tests {
    use super::*;

    const PATHS: &[&str] = &["output_path", "path", "source_path"];
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
            "review": {"path": "casillas[0].value"},
        });
        file_names(&mut result, PATHS);
        assert_eq!(result["sources"][0]["path"], "justificante.pdf");
        assert_eq!(result["sources"][0]["sha256"], "ab");
        assert_eq!(result["rows"][0]["source_path"], "303.txt");
        assert_eq!(result["rows"][0]["holder"], r"C:\Users\alba");
        assert_eq!(result["output_path"], "modelo-303.txt");
        assert_eq!(result["review"]["path"], "casillas[0].value");
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
            &Tracked::new("op".into(), REVIEWED, "s".into(), json!({})),
        );
        assert_eq!(
            (lost.code, lost.operation_id.as_deref()),
            ("unknown", Some("op")),
            "a lost answer to a mutation is unknown, never unavailable"
        );
        let read = attributed(
            Failure::new("unavailable"),
            &Tracked::new("op".into(), READ, "s".into(), json!({})),
        );
        assert_eq!(read.code, "unavailable");
    }

    #[cfg(windows)]
    mod relayed {
        use super::super::super::scripted::{OPERATION, PROFILE, holder, observed, resulted, step};
        use super::*;

        fn subject() -> String {
            format!("profile:{PROFILE}")
        }
        fn tracked(definition: Settling, identity: &Value) -> Tracked {
            Tracked::new(OPERATION.into(), definition, subject(), identity.clone())
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
                        json!({"kind":"operation_review","operation_id":OPERATION,
                            "interaction_id":"i-1","revision":5,"expires_at":null,
                            "review_digest":"c".repeat(64),
                            "document":{"projection":{"proposal":{"value":"1"}}}}),
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
