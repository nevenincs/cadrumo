//! Exact-profile Censo review over registered runtime operations.
use super::{Failure, HeldPerson, PersonEvent, ProfileHost, Result, lock, protocol};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::sync::Arc;
use tauri::{State, ipc::Channel};

const DEFINITION: &str = "user-profile.censo-review";

#[derive(Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Requirement {
    field: String,
    satisfied: bool,
    reason: String,
    secret: bool,
}
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Readiness {
    pub(crate) provider: String,
    route: String,
    pub(crate) ready: bool,
    requirements: Vec<Requirement>,
}
#[derive(Clone, Serialize)]
pub struct ReviewField {
    path: String,
    current: Option<String>,
    incoming: Option<String>,
    preserve: bool,
}
#[derive(Clone, Serialize)]
pub struct Snapshot {
    operation: String,
    state: &'static str,
    can_cancel: bool,
    review_digest: Option<String>,
    fields: Vec<ReviewField>,
    /// The operator action that sets up what a pull that stopped lacked, as
    /// its recorded verdict names it; an identifier for routing, never shown.
    #[serde(skip_serializing_if = "Option::is_none")]
    recovery_action_id: Option<String>,
}
pub(super) struct Session {
    person: HeldPerson,
    profile: String,
    operation: String,
    effective: Value,
    review: Option<Value>,
    snapshot: Option<Snapshot>,
}

pub(crate) async fn readiness(
    host: &ProfileHost,
    person: &HeldPerson,
    profile: &str,
) -> Result<Readiness> {
    let result = host
        .run(
            person,
            "auth.local-read",
            json!({"profile_id":profile,"kind":"sync_readiness"}),
            false,
        )
        .await?;
    if result["profile_id"] != profile || result["kind"] != "sync_readiness" {
        return Err(protocol());
    }
    let ready: Readiness =
        serde_json::from_value(result["sync_readiness"].clone()).map_err(|_| protocol())?;
    if ready.ready
        != (!ready.requirements.is_empty() && ready.requirements.iter().all(|r| r.satisfied))
    {
        return Err(protocol());
    }
    Ok(ready)
}

impl Session {
    async fn check(&self, host: &ProfileHost) -> Result<()> {
        let current = host.person(Some(&self.profile)).await?;
        let expected = lock(&self.person).identity.clone();
        if lock(&current).identity != expected {
            return Err(Failure::new("not_signed_in"));
        }
        Ok(())
    }
    async fn observe(&mut self) -> Result<Value> {
        let reply = ProfileHost::call(
            &self.person,
            json!({"action":"operation_observe","operation_id":self.operation,"after_cursor":0}),
        )
        .await?;
        let p = &reply["observation"]["projection"];
        if reply["kind"] != "operation_observed"
            || p["operation_id"] != self.operation
            || p["definition_id"] != DEFINITION
            || p["subject_ref"] != self.profile
        {
            return Err(protocol());
        }
        Ok(p.clone())
    }
    async fn initial_status(&mut self) -> Snapshot {
        match self.status().await {
            Ok(snapshot) => snapshot,
            Err(_) => {
                let snapshot = Snapshot {
                    operation: self.operation.clone(),
                    state: "unknown",
                    can_cancel: false,
                    review_digest: None,
                    fields: vec![],
                    recovery_action_id: None,
                };
                self.snapshot = Some(snapshot.clone());
                snapshot
            }
        }
    }
    /// The setup action a refused pull's recorded verdict names, where its
    /// detail can be read; a pull without one is still shown as failed.
    async fn recovery_action(&self) -> Option<String> {
        let result = ProfileHost::call(
            &self.person,
            json!({"action":"operation_result","operation_id":self.operation}),
        )
        .await
        .ok()?;
        if result["kind"] != "operation_result"
            || result["operation_id"] != self.operation
            || result["definition_id"] != DEFINITION
        {
            return None;
        }
        refused_action(&result["document"]["projection"])
    }
    async fn status(&mut self) -> Result<Snapshot> {
        let p = self.observe().await?;
        let mut snapshot = Snapshot {
            operation: self.operation.clone(),
            state: "reading",
            can_cancel: p["cancellable_now"] == true,
            review_digest: None,
            fields: vec![],
            recovery_action_id: None,
        };
        if p["lifecycle"] == "terminal" {
            snapshot.state = if p["terminal_condition"] == "succeeded" {
                let result = ProfileHost::call(
                    &self.person,
                    json!({"action":"operation_result","operation_id":self.operation}),
                )
                .await?;
                settled_state(&result, &self.operation)?
            } else if p["effect"] == "none" && p["terminal_condition"] == "cancelled" {
                "stopped"
            } else if p["effect"] == "none" {
                if p["terminal_condition"] == "refused" {
                    snapshot.recovery_action_id = self.recovery_action().await;
                }
                "failed"
            } else {
                "unknown"
            };
        } else if p["pending_interaction"]["disposition"] == "review_available" {
            if let (Some(review), Some(previous)) = (&self.review, &self.snapshot)
                && review["revision"] == p["pending_interaction"]["revision"]
                && review["interaction_id"] == p["pending_interaction"]["interaction_id"]
            {
                return Ok(previous.clone());
            }
            let review = ProfileHost::call(
                &self.person,
                json!({"action":"operation_review","operation_id":self.operation}),
            )
            .await?;
            snapshot.fields = review_fields(&review, &self.effective, &self.operation)?;
            snapshot.review_digest = review["review_digest"].as_str().map(str::to_owned);
            snapshot.state = "review";
            self.review = Some(review);
        } else if p["pending_interaction"]["disposition"] == "unsupported" {
            snapshot.state = "unsupported";
        } else if p["phase_code"] == "censo.clave-device-wait" {
            snapshot.state = "device";
        }
        if snapshot.state != "review" {
            self.review = None;
        }
        self.snapshot = Some(snapshot.clone());
        Ok(snapshot)
    }
}
/// The setup action of the engine item an error detail's registered refusal
/// stands for.
fn refused_action(detail: &Value) -> Option<String> {
    super::super::setup::wire::refused_item(detail)
        .map(|item| item.declaration().recovery_action.to_owned())
}
fn settled_state(result: &Value, operation: &str) -> Result<&'static str> {
    if result["kind"] != "operation_result"
        || result["operation_id"] != operation
        || result["definition_id"] != DEFINITION
    {
        return Err(protocol());
    }
    match result["document"]["projection"]["outcome"].as_str() {
        Some("applied") => Ok("done"),
        Some("rejected") => Ok("stopped"),
        _ => Err(protocol()),
    }
}
fn review_fields(review: &Value, effective: &Value, operation: &str) -> Result<Vec<ReviewField>> {
    if review["kind"] != "operation_review"
        || review["operation_id"] != operation
        || review["revision"].as_u64().is_none()
        || review["interaction_id"].as_str().is_none()
        || !review["review_digest"]
            .as_str()
            .is_some_and(super::super::setup::wire::is_hex64)
    {
        return Err(protocol());
    }
    let projection = &review["document"]["projection"];
    if projection["projection_version"] != 1 {
        return Err(protocol());
    }
    let incoming = projection["fields"].as_array().ok_or_else(protocol)?;
    let saved = effective.as_array().ok_or_else(protocol)?;
    if incoming.len() != saved.len() || incoming.is_empty() {
        return Err(protocol());
    }
    incoming
        .iter()
        .zip(saved)
        .map(|(field, current)| {
            let path = field["path"].as_str().ok_or_else(protocol)?;
            if current["path"] != path
                || !matches!(field["intent"].as_str(), Some("adopt" | "preserve"))
            {
                return Err(protocol());
            }
            let value = |v: &Value| -> Result<Option<String>> {
                if v.is_null() {
                    Ok(None)
                } else {
                    v.as_str()
                        .filter(|s| s.len() <= 16384)
                        .map(|s| Some(s.to_owned()))
                        .ok_or_else(protocol)
                }
            };
            Ok(ReviewField {
                path: path.to_owned(),
                current: value(&current["effective_value"])?,
                incoming: value(&field["observed_value"])?,
                preserve: field["intent"] == "preserve",
            })
        })
        .collect()
}
#[tauri::command]
pub async fn profile_censo_readiness(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
) -> Result<Readiness> {
    let _serial = host.operation.lock().await;
    let person = host.person(Some(&profile)).await?;
    let answer = readiness(&host, &person, &profile).await?;
    let current = host.person(Some(&profile)).await?;
    let identity = lock(&person).identity.clone();
    if lock(&current).identity != identity {
        return Err(Failure::new("not_signed_in"));
    }
    Ok(answer)
}
async fn submit(person: &HeldPerson, profile: &str, payload: Value) -> Result<String> {
    super::super::relay::submit(person, DEFINITION, profile, payload, true).await
}
#[tauri::command]
pub async fn profile_censo_start(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
) -> Result<Snapshot> {
    begin(&host, profile).await
}
/// Starts the census session for `profile`, or answers the one still going
/// on: a lost reply must never start a second remote pull. The AEAT sync run
/// starts the same session as its census item.
pub(crate) async fn begin(host: &ProfileHost, profile: String) -> Result<Snapshot> {
    let mut session = host.censo.lock().await;
    let person = host.person(Some(&profile)).await?;
    if let Some(existing) = session.as_mut() {
        let previous_identity = lock(&existing.person).identity.clone();
        let same_session =
            existing.profile == profile && previous_identity == lock(&person).identity;
        if same_session {
            let snapshot = existing.status().await?;
            existing.check(host).await?;
            if !matches!(snapshot.state, "done" | "stopped" | "failed") {
                return Ok(snapshot);
            }
        }
    }
    let _serial = host.operation.lock().await;
    if !readiness(host, &person, &profile).await?.ready {
        return Err(Failure::new("refused"));
    }
    let prepared = host
        .run(
            &person,
            "user-profile.censo-prepare",
            json!({"profile_id":profile}),
            false,
        )
        .await?;
    if prepared["profile_id"] != profile
        || prepared["operation_request"]["baseline"]["profile_id"] != profile
        || !prepared["effective_fields"].is_array()
    {
        return Err(protocol());
    }
    let operation = submit(&person, &profile, prepared["operation_request"].clone()).await?;
    let mut next = Session {
        person,
        profile,
        operation,
        effective: prepared["effective_fields"].clone(),
        review: None,
        snapshot: None,
    };
    let result = next.initial_status().await;
    *session = Some(next);
    session.as_ref().unwrap().check(host).await?;
    Ok(result)
}
/// Where the census session for `profile` stands now.
pub(crate) async fn standing(host: &ProfileHost, profile: &str) -> Result<&'static str> {
    let mut session = host.censo.lock().await;
    let current = session
        .as_mut()
        .filter(|s| s.profile == profile)
        .ok_or_else(protocol)?;
    current.check(host).await?;
    Ok(current.status().await?.state)
}
impl Snapshot {
    pub(crate) fn state(&self) -> &'static str {
        self.state
    }
}
#[tauri::command]
pub async fn profile_censo_status(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
    operation: String,
) -> Result<Snapshot> {
    let mut session = host.censo.lock().await;
    let current = session
        .as_mut()
        .filter(|s| s.profile == profile && s.operation == operation)
        .ok_or_else(protocol)?;
    current.check(&host).await?;
    let result = current.status().await?;
    current.check(&host).await?;
    Ok(result)
}
#[derive(Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Decision {
    Apply,
    Reject,
    Cancel,
}
#[tauri::command]
pub async fn profile_censo_answer(
    host: State<'_, Arc<ProfileHost>>,
    profile: String,
    operation: String,
    review_digest: Option<String>,
    decision: Decision,
) -> Result<Snapshot> {
    let mut session = host.censo.lock().await;
    let current = session
        .as_mut()
        .filter(|s| s.profile == profile && s.operation == operation)
        .ok_or_else(protocol)?;
    current.check(&host).await?;
    let request = match decision {
        Decision::Cancel => {
            let p = current.observe().await?;
            if p["cancellable_now"] != true {
                return Err(Failure::new("refused"));
            }
            json!({"action":"operation_cancel","operation_id":operation,"expected_revision":p["revision"]})
        }
        Decision::Apply | Decision::Reject => {
            let review = current
                .review
                .as_ref()
                .ok_or_else(|| Failure::new("conflict"))?;
            if review_digest.as_deref() != review["review_digest"].as_str()
                || review_digest.is_none()
            {
                return Err(Failure::new("conflict"));
            }
            json!({"action":"operation_respond","operation_id":operation,"interaction_id":review["interaction_id"],"revision":review["revision"],"review_digest":review["review_digest"],"decision":if matches!(decision,Decision::Apply) {"apply"} else {"reject"}})
        }
    };
    let reply = ProfileHost::call(&current.person, request)
        .await
        .map_err(|_| Failure::new("unknown"))?;
    if !matches!(
        reply["kind"].as_str(),
        Some("operation_responded" | "operation_cancel_requested")
    ) {
        return Err(Failure::new("refused"));
    }
    current.review = None;
    let result = current.status().await?;
    current.check(&host).await?;
    Ok(result)
}
pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        profile_censo_readiness,
        profile_censo_start,
        profile_censo_status,
        profile_censo_answer,
        profile_censo_observe,
        profile_censo_unobserve
    ]
}

#[tauri::command]
fn profile_censo_observe(host: State<'_, Arc<ProfileHost>>, updates: Channel<()>) -> u32 {
    let mut events = host.sign_in.person_events();
    host.censo_observer
        .observe(host.is_closed(), updates, |updates| async move {
            loop {
                match events.recv().await {
                    Ok(PersonEvent::OperationChanged | PersonEvent::Retired)
                    | Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => {
                        if updates.send(()).is_err() {
                            break;
                        }
                    }
                    Err(tokio::sync::broadcast::error::RecvError::Closed) => break,
                    _ => {}
                }
            }
        })
}
#[tauri::command]
fn profile_censo_unobserve(host: State<'_, Arc<ProfileHost>>, subscription: u32) {
    host.censo_observer.unobserve(subscription);
}

#[cfg(test)]
mod tests {
    use super::*;
    #[cfg(windows)]
    #[tokio::test]
    async fn submission_and_review_bind_the_bare_profile_and_settle() {
        use super::super::super::scripted::{OPERATION, PROFILE, holder, observed, resulted, step};
        let held = holder(|_| {
            vec![
                step(
                    "operation_submit",
                    json!([
                        ["definition_id", DEFINITION],
                        ["subject_ref", PROFILE],
                        ["payload.baseline.profile_id", PROFILE]
                    ]),
                    json!({"kind":"operation_submitted","operation_id":OPERATION}),
                    false,
                ),
                step(
                    "operation_observe",
                    json!([["operation_id", OPERATION]]),
                    observed(
                        DEFINITION,
                        PROFILE,
                        "running",
                        json!({"pending_interaction":{"disposition":"review_available","revision":1,"interaction_id":"i"}}),
                    ),
                    false,
                ),
                step(
                    "operation_review",
                    json!([["operation_id", OPERATION]]),
                    json!({"kind":"operation_review","operation_id":OPERATION,"interaction_id":"i","revision":1,"review_digest":"b".repeat(64),"document":{"projection":{"projection_version":1,"fields":[{"path":"contact.postcode","intent":"adopt","observed_value":"29001"}]}}}),
                    false,
                ),
                step(
                    "operation_observe",
                    json!([["operation_id", OPERATION]]),
                    observed(
                        DEFINITION,
                        PROFILE,
                        "terminal",
                        json!({"terminal_condition":"succeeded"}),
                    ),
                    false,
                ),
                step(
                    "operation_result",
                    json!([["operation_id", OPERATION]]),
                    resulted(DEFINITION, json!({"outcome":"applied"})),
                    false,
                ),
            ]
        });
        let operation = submit(
            &held.person,
            PROFILE,
            json!({"baseline":{"profile_id":PROFILE}}),
        )
        .await
        .unwrap();
        let mut session = Session {
            person: held.person,
            profile: PROFILE.into(),
            operation,
            effective: json!([{"path":"contact.postcode","effective_value":"29005"}]),
            review: None,
            snapshot: None,
        };
        let review = session.status().await.unwrap();
        assert_eq!(review.state, "review");
        assert_eq!(review.fields[0].incoming.as_deref(), Some("29001"));
        assert_eq!(session.status().await.unwrap().state, "done");
    }

    #[cfg(windows)]
    #[tokio::test]
    async fn initial_observation_failure_keeps_operation_for_recovery() {
        use super::super::super::scripted::{OPERATION, PROFILE, holder, observed, step};
        let held = holder(|_| {
            vec![
                step(
                    "operation_observe",
                    json!([["operation_id", OPERATION]]),
                    json!({"kind":"operation_refused", "code":"unavailable"}),
                    false,
                ),
                step(
                    "operation_observe",
                    json!([["operation_id", OPERATION]]),
                    observed(DEFINITION, PROFILE, "running", json!({})),
                    false,
                ),
            ]
        });
        let mut session = Session {
            person: held.person,
            profile: PROFILE.into(),
            operation: OPERATION.into(),
            effective: json!([]),
            review: None,
            snapshot: None,
        };
        let first = session.initial_status().await;
        assert_eq!(first.state, "unknown");
        assert_eq!(first.operation, OPERATION);
        assert_eq!(session.status().await.unwrap().state, "reading");
    }

    #[cfg(windows)]
    #[tokio::test]
    async fn failed_no_effect_is_distinct_from_cancellation() {
        use super::super::super::scripted::{OPERATION, PROFILE, holder, observed, step};
        let held = holder(|_| {
            vec![
                step(
                    "operation_observe",
                    json!([]),
                    observed(
                        DEFINITION,
                        PROFILE,
                        "terminal",
                        json!({"terminal_condition":"failed", "effect":"none"}),
                    ),
                    false,
                ),
                step(
                    "operation_observe",
                    json!([]),
                    observed(
                        DEFINITION,
                        PROFILE,
                        "terminal",
                        json!({"terminal_condition":"cancelled", "effect":"none"}),
                    ),
                    false,
                ),
            ]
        });
        let mut session = Session {
            person: held.person,
            profile: PROFILE.into(),
            operation: OPERATION.into(),
            effective: json!([]),
            review: None,
            snapshot: None,
        };
        assert_eq!(session.status().await.unwrap().state, "failed");
        assert_eq!(session.status().await.unwrap().state, "stopped");
    }

    #[cfg(windows)]
    #[tokio::test]
    async fn a_pull_refused_for_a_missing_component_names_its_setup_action() {
        use super::super::super::scripted::{OPERATION, PROFILE, holder, observed, resulted, step};
        let refusal = |code: &str| {
            json!({"detail_version":1,"kind":"registered_error","error_code":code,"message_key":null,
                "context":[],"context_entries_omitted":0,"precondition_verdict_json":null})
        };
        let refused = || {
            observed(
                DEFINITION,
                PROFILE,
                "terminal",
                json!({"terminal_condition":"refused", "effect":"none"}),
            )
        };
        let held = holder(|_| {
            vec![
                step("operation_observe", json!([]), refused(), false),
                step(
                    "operation_result",
                    json!([["operation_id", OPERATION]]),
                    resulted(DEFINITION, refusal("REFUSED_BROWSER_NOT_READY")),
                    false,
                ),
                step("operation_observe", json!([]), refused(), false),
                step(
                    "operation_result",
                    json!([["operation_id", OPERATION]]),
                    resulted(DEFINITION, refusal("REFUSED_PROFILE_LOCKED")),
                    false,
                ),
            ]
        });
        let mut session = Session {
            person: held.person,
            profile: PROFILE.into(),
            operation: OPERATION.into(),
            effective: json!([]),
            review: None,
            snapshot: None,
        };
        let stopped = session.status().await.unwrap();
        assert_eq!(stopped.state, "failed");
        assert_eq!(
            stopped.recovery_action_id.as_deref(),
            Some("operator.provision.browser")
        );
        // A refusal that stands for no component names no setup.
        let other = session.status().await.unwrap();
        assert_eq!(other.state, "failed");
        assert_eq!(other.recovery_action_id, None);
    }

    #[cfg(windows)]
    #[tokio::test]
    async fn submission_keeps_refusal_reason_and_lost_admission_uncertain() {
        use super::super::super::scripted::{PROFILE, holder, step};
        for (reply, code, reason) in [
            (
                json!({"kind":"operation_refused","code":"profile_mismatch"}),
                "refused",
                Some("profile_mismatch"),
            ),
            (
                json!({"kind":"operation_refused","code":"unavailable"}),
                "unknown",
                None,
            ),
        ] {
            let held = holder(|_| {
                vec![step(
                    "operation_submit",
                    json!([["subject_ref", PROFILE]]),
                    reply.clone(),
                    false,
                )]
            });
            let error = submit(
                &held.person,
                PROFILE,
                json!({"baseline":{"profile_id":PROFILE}}),
            )
            .await
            .unwrap_err();
            assert_eq!(error.code, code);
            assert_eq!(error.reason.as_deref(), reason);
        }
    }

    #[test]
    fn successful_rejection_is_not_presented_as_a_saved_profile() {
        let mut result = json!({"kind":"operation_result","operation_id":"op","definition_id":DEFINITION,"document":{"projection":{"outcome":"rejected"}}});
        assert_eq!(settled_state(&result, "op").unwrap(), "stopped");
        result["document"]["projection"]["outcome"] = json!("applied");
        assert_eq!(settled_state(&result, "op").unwrap(), "done");
        assert!(settled_state(&result, "wrong").is_err());
        result["document"]["projection"]["outcome"] = json!("unknown");
        assert!(settled_state(&result, "op").is_err());
    }

    #[test]
    fn review_rejects_unbound_or_extra_fields_and_preserves_manual_answers() {
        let saved = json!([{"path":"contact.postcode","state":"value","effective_value":"29005"}]);
        let review = json!({"kind":"operation_review","operation_id":"op","interaction_id":"i","revision":3,"review_digest":"b".repeat(64),"document":{"projection":{"projection_version":1,"fields":[{"path":"contact.postcode","intent":"preserve","observed_value":"29001"}]}}});
        let fields = review_fields(&review, &saved, "op").unwrap();
        assert!(fields[0].preserve);
        assert_eq!(fields[0].current.as_deref(), Some("29005"));
        assert_eq!(fields[0].incoming.as_deref(), Some("29001"));
        assert!(review_fields(&review, &saved, "another operation").is_err());
        let mut wrong = review.clone();
        wrong["document"]["projection"]["fields"][0]["path"] = json!("auth.password");
        assert!(review_fields(&wrong, &saved, "op").is_err());
        let mut changed = review.clone();
        changed["review_digest"] = json!("invalid");
        assert!(review_fields(&changed, &saved, "op").is_err());
        let mut invented = review.clone();
        invented["document"]["projection"]["fields"][0]["intent"] = json!("overwrite");
        assert!(review_fields(&invented, &saved, "op").is_err());
    }
}
