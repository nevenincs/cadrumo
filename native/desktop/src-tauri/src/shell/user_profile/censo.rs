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
    /// Whether the pull stopped because its AEAT session ended; read by the
    /// AEAT sync run to pause, never sent to the window.
    #[serde(skip)]
    session_ended: bool,
}
pub(super) struct Session {
    person: HeldPerson,
    profile: String,
    operation: String,
    effective: Value,
    review: Option<Value>,
    snapshot: Option<Snapshot>,
    /// Per-value decisions the answer protocol cannot carry: the operator's
    /// choices wait here while the whole review is rejected and the read the
    /// operator saw is reviewed again with their intents.
    pending: Option<Pending>,
    /// Earlier operations of this session, which the window may still name.
    superseded: Vec<String>,
}
#[derive(Clone, Copy, PartialEq)]
enum Phase {
    /// The first review was rejected; its operation has not settled yet.
    Rejecting,
    /// The stored read is under review again with the decided intents.
    FollowUp,
}
struct Pending {
    phase: Phase,
    /// Each accepted path with the AEAT value the operator saw for it.
    accepted: Vec<(String, String)>,
}
/// What the follow-up review needs from its host: the lock that serialises
/// profile operations and the prepare read.
trait Prepare {
    async fn hold(&self) -> impl Send;
    async fn prepare(&self, person: &HeldPerson, profile: &str) -> Result<Value>;
}
impl Prepare for ProfileHost {
    async fn hold(&self) -> impl Send {
        self.serial().await
    }
    async fn prepare(&self, person: &HeldPerson, profile: &str) -> Result<Value> {
        self.run(
            person,
            "user-profile.censo-prepare",
            json!({"profile_id":profile}),
            false,
        )
        .await
    }
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
    /// Sends one runtime request that answers or cancels the operation.
    async fn send(&mut self, request: Value) -> Result<()> {
        let reply = ProfileHost::call(&self.person, request)
            .await
            .map_err(|_| Failure::new("unknown"))?;
        if !matches!(
            reply["kind"].as_str(),
            Some("operation_responded" | "operation_cancel_requested")
        ) {
            return Err(Failure::new("refused"));
        }
        self.review = None;
        Ok(())
    }
    /// Answers the review `review_digest` names. `accepted` carries the
    /// operator's per-value choice: where it is the review's own adopt set the
    /// answer is the plain one, and otherwise the review is rejected and the
    /// choice is kept for the follow-up review.
    async fn answer_review(
        &mut self,
        review_digest: Option<&str>,
        apply: bool,
        accepted: Option<Vec<String>>,
    ) -> Result<()> {
        let review = self
            .review
            .as_ref()
            .ok_or_else(|| Failure::new("conflict"))?;
        if review_digest.is_none() || review_digest != review["review_digest"].as_str() {
            return Err(Failure::new("conflict"));
        }
        let divert = match accepted {
            None => None,
            Some(_) if !apply => return Err(Failure::new("conflict")),
            Some(paths) => self.divert(&paths)?,
        };
        let request = json!({"action":"operation_respond","operation_id":self.operation,"interaction_id":review["interaction_id"],"revision":review["revision"],"review_digest":review["review_digest"],"decision":if apply && divert.is_none() {"apply"} else {"reject"}});
        self.send(request).await?;
        self.pending = divert;
        Ok(())
    }
    /// The decision to keep while the review is rejected, where `paths` is not
    /// the review's own adopt set; a path that is not a proposed value of
    /// this review is a conflict.
    fn divert(&self, paths: &[String]) -> Result<Option<Pending>> {
        let fields = match &self.snapshot {
            Some(s) if s.state == "review" => &s.fields,
            _ => return Err(Failure::new("conflict")),
        };
        let mut accepted: Vec<(String, String)> = vec![];
        for path in paths {
            let field = fields
                .iter()
                .find(|f| &f.path == path)
                .ok_or_else(|| Failure::new("conflict"))?;
            let incoming = field
                .incoming
                .clone()
                .ok_or_else(|| Failure::new("conflict"))?;
            if accepted.iter().any(|(p, _)| p == path) {
                return Err(Failure::new("conflict"));
            }
            accepted.push((path.clone(), incoming));
        }
        let same = fields
            .iter()
            .filter(|f| !f.preserve && f.incoming.is_some())
            .count()
            == accepted.len()
            && fields
                .iter()
                .filter(|f| !f.preserve && f.incoming.is_some())
                .all(|f| accepted.iter().any(|(p, _)| p == &f.path));
        Ok((!same).then_some(Pending {
            phase: Phase::Rejecting,
            accepted,
        }))
    }
    /// Submits the stored read again with the decided intents, from a fresh
    /// prepare of the same profile; nothing the operator did not see is sent.
    async fn follow_up(&mut self, prepared: &Value) -> Result<()> {
        let accepted = match &self.pending {
            Some(p) if p.phase == Phase::Rejecting => p.accepted.clone(),
            _ => return Err(Failure::new("conflict")),
        };
        let request = follow_up_request(prepared, &self.profile, &accepted)?;
        let operation = submit(&self.person, &self.profile, request).await?;
        self.superseded
            .push(std::mem::replace(&mut self.operation, operation));
        self.effective = prepared["effective_fields"].clone();
        self.review = None;
        self.snapshot = None;
        if let Some(p) = &mut self.pending {
            p.phase = Phase::FollowUp;
        }
        Ok(())
    }
    /// Whether the follow-up review is exactly what the operator decided: each
    /// intent as chosen, and each accepted value the one they saw.
    fn follow_up_matches(&self, review: &Snapshot) -> bool {
        let Some(pending) = &self.pending else {
            return false;
        };
        review.fields.iter().all(|field| {
            let seen = pending.accepted.iter().find(|(p, _)| p == &field.path);
            field.preserve == seen.is_none()
                && seen.is_none_or(|(_, value)| field.incoming.as_ref() == Some(value))
        }) && pending
            .accepted
            .iter()
            .all(|(path, _)| review.fields.iter().any(|f| &f.path == path))
    }
    fn failed(&mut self) -> Snapshot {
        self.pending = None;
        let snapshot = Snapshot {
            operation: self.operation.clone(),
            state: "failed",
            can_cancel: false,
            review_digest: None,
            fields: vec![],
            recovery_action_id: None,
            session_ended: false,
        };
        self.snapshot = Some(snapshot.clone());
        snapshot
    }
    /// Where the operation stands, moving a pending per-value decision one
    /// step on whenever its operation has settled or its review is here.
    async fn drive(&mut self, host: &impl Prepare) -> Result<Snapshot> {
        let mut snapshot = self.status().await?;
        for _ in 0..4 {
            let Some(phase) = self.pending.as_ref().map(|p| p.phase) else {
                break;
            };
            match (phase, snapshot.state) {
                (Phase::Rejecting, "stopped") => {
                    let _serial = host.hold().await;
                    let prepared = host.prepare(&self.person, &self.profile).await;
                    match prepared {
                        Ok(prepared) if self.follow_up(&prepared).await.is_ok() => {}
                        _ => return Ok(self.failed()),
                    }
                    snapshot = self.status().await?;
                }
                (Phase::FollowUp, "review") => {
                    if !self.follow_up_matches(&snapshot) {
                        self.pending = None;
                        break;
                    }
                    let digest = snapshot.review_digest.clone();
                    self.pending = None;
                    self.answer_review(digest.as_deref(), true, None).await?;
                    snapshot = self.status().await?;
                }
                (_, "reading" | "device" | "review") => break,
                _ => {
                    self.pending = None;
                    break;
                }
            }
        }
        Ok(snapshot)
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
                    session_ended: false,
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
            session_ended: false,
        };
        if p["lifecycle"] == "terminal" {
            snapshot.session_ended = crate::shell::aeat_sync::outcome::session_ended(&p);
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
/// The request that reviews the stored read again with the operator's
/// decisions: each path they accepted is adopted and every other one kept.
fn follow_up_request(
    prepared: &Value,
    profile: &str,
    accepted: &[(String, String)],
) -> Result<Value> {
    let captured = prepared["observation"]["captured_at"]
        .as_str()
        .filter(|s| !s.is_empty())
        .ok_or_else(|| Failure::new("conflict"))?;
    let mut request = prepared["operation_request"].clone();
    if prepared["profile_id"] != profile
        || request["baseline"]["profile_id"] != profile
        || !prepared["effective_fields"].is_array()
    {
        return Err(protocol());
    }
    let intents = request["field_intents"]
        .as_array_mut()
        .ok_or_else(protocol)?;
    if accepted
        .iter()
        .any(|(path, _)| !intents.iter().any(|i| i["path"] == *path))
    {
        return Err(Failure::new("conflict"));
    }
    for item in intents.iter_mut() {
        let chosen = accepted.iter().any(|(path, _)| item["path"] == *path);
        item["intent"] = json!(if chosen { "adopt" } else { "preserve" });
    }
    request["stored_observation"] = json!({"captured_at":captured});
    Ok(request)
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
            let snapshot = existing.drive(host).await?;
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
        pending: None,
        superseded: vec![],
    };
    let result = next.initial_status().await;
    *session = Some(next);
    session.as_ref().unwrap().check(host).await?;
    Ok(result)
}
/// Where the census session for `profile` stands now.
pub(crate) async fn standing(host: &ProfileHost, profile: &str) -> Result<Snapshot> {
    let mut session = host.censo.lock().await;
    let current = session
        .as_mut()
        .filter(|s| s.profile == profile)
        .ok_or_else(protocol)?;
    current.check(host).await?;
    current.drive(host).await
}
impl Snapshot {
    pub(crate) fn state(&self) -> &'static str {
        self.state
    }
    pub(crate) fn session_ended(&self) -> bool {
        self.session_ended
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
        .filter(|s| {
            s.profile == profile && (s.operation == operation || s.superseded.contains(&operation))
        })
        .ok_or_else(protocol)?;
    current.check(&host).await?;
    let result = current.drive(&**host).await?;
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
    accepted: Option<Vec<String>>,
) -> Result<Snapshot> {
    let mut session = host.censo.lock().await;
    let current = session
        .as_mut()
        .filter(|s| {
            s.profile == profile && (s.operation == operation || s.superseded.contains(&operation))
        })
        .ok_or_else(protocol)?;
    current.check(&host).await?;
    match decision {
        Decision::Cancel => {
            let p = current.observe().await?;
            if p["cancellable_now"] != true {
                return Err(Failure::new("refused"));
            }
            let request = json!({"action":"operation_cancel","operation_id":current.operation,"expected_revision":p["revision"]});
            current.send(request).await?;
        }
        Decision::Apply | Decision::Reject => {
            current
                .answer_review(
                    review_digest.as_deref(),
                    matches!(decision, Decision::Apply),
                    accepted,
                )
                .await?;
        }
    }
    let result = current.drive(&**host).await?;
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
            pending: None,
            superseded: vec![],
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
            pending: None,
            superseded: vec![],
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
            pending: None,
            superseded: vec![],
        };
        assert_eq!(session.status().await.unwrap().state, "failed");
        assert_eq!(session.status().await.unwrap().state, "stopped");
    }

    #[cfg(windows)]
    #[tokio::test]
    async fn a_pull_that_ended_with_the_aeat_session_says_so_whatever_it_kept() {
        use super::super::super::scripted::{OPERATION, PROFILE, holder, observed, resulted, step};
        use crate::shell::aeat_sync::outcome::SESSION_ENDED;
        let ended = |condition: &str, effect: &str, refusal: Value| {
            step(
                "operation_observe",
                json!([]),
                observed(
                    DEFINITION,
                    PROFILE,
                    "terminal",
                    json!({"terminal_condition":condition, "effect":effect, "refusal_ref":refusal}),
                ),
                false,
            )
        };
        let held = holder(|_| {
            vec![
                ended("refused", "none", json!(SESSION_ENDED)),
                // The refusal's recorded verdict is read for a setup action.
                step(
                    "operation_result",
                    json!([["operation_id", OPERATION]]),
                    resulted(
                        DEFINITION,
                        json!({"detail_version":1,"kind":"registered_error","error_code":SESSION_ENDED,
                            "message_key":null,"context":[],"context_entries_omitted":0,
                            "precondition_verdict_json":null}),
                    ),
                    false,
                ),
                ended("refused", "unknown", json!(SESSION_ENDED)),
                ended("failed", "none", json!("REFUSED_BROWSER_NOT_READY")),
                ended("failed", "none", Value::Null),
            ]
        });
        let mut session = Session {
            person: held.person,
            profile: PROFILE.into(),
            operation: OPERATION.into(),
            effective: json!([]),
            review: None,
            snapshot: None,
            pending: None,
            superseded: vec![],
        };
        let nothing_kept = session.status().await.unwrap();
        assert_eq!(nothing_kept.state, "failed");
        assert!(nothing_kept.session_ended());
        let may_have_kept = session.status().await.unwrap();
        assert_eq!(may_have_kept.state, "unknown");
        assert!(may_have_kept.session_ended());
        for other in 0..2 {
            let snapshot = session.status().await.unwrap();
            assert_eq!(snapshot.state, "failed", "{other}");
            assert!(!snapshot.session_ended(), "{other}");
        }
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
            pending: None,
            superseded: vec![],
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

    #[cfg(windows)]
    mod per_value {
        use super::super::super::super::scripted::{
            OPERATION, PROFILE, holder, observed, resulted, step,
        };
        use super::*;
        const SECOND: &str = "cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd";
        const CAPTURED: &str = "2026-11-19T10:00:00Z";

        struct Fixed(Value);
        impl Prepare for Fixed {
            async fn hold(&self) -> impl Send {}
            async fn prepare(&self, _: &HeldPerson, _: &str) -> Result<Value> {
                Ok(self.0.clone())
            }
        }
        fn prepared() -> Value {
            json!({"profile_id":PROFILE,
                "operation_request":{"baseline":{"profile_id":PROFILE},
                    "field_intents":[{"path":"contact.postcode","intent":"adopt"},
                                     {"path":"contact.phone","intent":"adopt"}]},
                "effective_fields":[{"path":"contact.postcode","effective_value":"29005"},
                                    {"path":"contact.phone","effective_value":"600"}],
                "observation":{"captured_at":CAPTURED}})
        }
        fn review_of(operation: &str, interaction: &str, fields: Value) -> Value {
            json!({"kind":"operation_review","operation_id":operation,"interaction_id":interaction,"revision":1,"review_digest":"b".repeat(64),"document":{"projection":{"projection_version":1,"fields":fields}}})
        }
        fn first_review() -> Value {
            review_of(
                OPERATION,
                "i",
                json!([{"path":"contact.postcode","intent":"adopt","observed_value":"29001"},
                       {"path":"contact.phone","intent":"adopt","observed_value":"611"}]),
            )
        }
        fn of_operation(mut value: Value, operation: &str) -> Value {
            if value["observation"].is_object() {
                value["observation"]["projection"]["operation_id"] = json!(operation);
            } else {
                value["operation_id"] = json!(operation);
            }
            value
        }
        fn waiting(operation: &str, interaction: &str) -> Value {
            of_operation(
                observed(
                    DEFINITION,
                    PROFILE,
                    "running",
                    json!({"pending_interaction":{"disposition":"review_available","revision":1,"interaction_id":interaction}}),
                ),
                operation,
            )
        }
        fn settled(operation: &str, outcome: &str) -> [Value; 2] {
            [
                of_operation(
                    observed(
                        DEFINITION,
                        PROFILE,
                        "terminal",
                        json!({"terminal_condition":"succeeded"}),
                    ),
                    operation,
                ),
                of_operation(resulted(DEFINITION, json!({"outcome":outcome})), operation),
            ]
        }
        fn respond(operation: &str, decision: &str) -> Value {
            step(
                "operation_respond",
                json!([["operation_id", operation], ["decision", decision]]),
                json!({"kind":"operation_responded"}),
                false,
            )
        }
        fn session(held: super::super::super::super::scripted::Holder) -> Session {
            Session {
                person: held.person,
                profile: PROFILE.into(),
                operation: OPERATION.into(),
                effective: json!([{"path":"contact.postcode","effective_value":"29005"},
                                  {"path":"contact.phone","effective_value":"600"}]),
                review: None,
                snapshot: None,
                pending: None,
                superseded: vec![],
            }
        }
        fn first_steps(more: Vec<Value>) -> Vec<Value> {
            let mut steps = vec![
                step(
                    "operation_observe",
                    json!([["operation_id", OPERATION]]),
                    waiting(OPERATION, "i"),
                    false,
                ),
                step(
                    "operation_review",
                    json!([["operation_id", OPERATION]]),
                    first_review(),
                    false,
                ),
            ];
            steps.extend(more);
            steps
        }

        #[tokio::test]
        async fn the_review_own_adopt_set_answers_apply_as_one_response() {
            let held = holder(|_| first_steps(vec![respond(OPERATION, "apply")]));
            let mut session = session(held);
            let review = session.status().await.unwrap();
            assert_eq!(review.state, "review");
            session
                .answer_review(
                    review.review_digest.as_deref(),
                    true,
                    Some(vec!["contact.phone".into(), "contact.postcode".into()]),
                )
                .await
                .unwrap();
            assert!(session.pending.is_none());
        }

        #[tokio::test]
        async fn a_differing_set_rejects_then_reviews_the_stored_read_and_applies_it() {
            let second_review = review_of(
                SECOND,
                "j",
                json!([{"path":"contact.postcode","intent":"adopt","observed_value":"29001"},
                       {"path":"contact.phone","intent":"preserve","observed_value":"611"}]),
            );
            let held = holder(|_| {
                let [stopped, rejected] = settled(OPERATION, "rejected");
                let [ended, applied] = settled(SECOND, "applied");
                first_steps(vec![
                    respond(OPERATION, "reject"),
                    step(
                        "operation_observe",
                        json!([["operation_id", OPERATION]]),
                        stopped,
                        false,
                    ),
                    step(
                        "operation_result",
                        json!([["operation_id", OPERATION]]),
                        rejected,
                        false,
                    ),
                    step(
                        "operation_submit",
                        json!([
                            ["definition_id", DEFINITION],
                            ["payload.stored_observation.captured_at", CAPTURED]
                        ]),
                        json!({"kind":"operation_submitted","operation_id":SECOND}),
                        false,
                    ),
                    step(
                        "operation_observe",
                        json!([["operation_id", SECOND]]),
                        waiting(SECOND, "j"),
                        false,
                    ),
                    step(
                        "operation_review",
                        json!([["operation_id", SECOND]]),
                        second_review.clone(),
                        false,
                    ),
                    respond(SECOND, "apply"),
                    step(
                        "operation_observe",
                        json!([["operation_id", SECOND]]),
                        ended,
                        false,
                    ),
                    step(
                        "operation_result",
                        json!([["operation_id", SECOND]]),
                        applied,
                        false,
                    ),
                ])
            });
            let mut session = session(held);
            let review = session.status().await.unwrap();
            session
                .answer_review(
                    review.review_digest.as_deref(),
                    true,
                    Some(vec!["contact.postcode".into()]),
                )
                .await
                .unwrap();
            assert!(session.pending.is_some());
            let done = session.drive(&Fixed(prepared())).await.unwrap();
            assert_eq!(done.state, "done");
            assert_eq!(done.operation, SECOND);
            assert_eq!(session.superseded, vec![OPERATION.to_owned()]);
            assert!(session.pending.is_none());
        }

        #[tokio::test]
        async fn a_follow_up_review_that_differs_is_presented_and_never_applied() {
            // The AEAT value of the accepted field changed between the two reads.
            let changed = review_of(
                SECOND,
                "j",
                json!([{"path":"contact.postcode","intent":"adopt","observed_value":"29999"},
                       {"path":"contact.phone","intent":"preserve","observed_value":"611"}]),
            );
            let held = holder(|_| {
                let [stopped, rejected] = settled(OPERATION, "rejected");
                first_steps(vec![
                    respond(OPERATION, "reject"),
                    step(
                        "operation_observe",
                        json!([["operation_id", OPERATION]]),
                        stopped,
                        false,
                    ),
                    step(
                        "operation_result",
                        json!([["operation_id", OPERATION]]),
                        rejected,
                        false,
                    ),
                    step(
                        "operation_submit",
                        json!([["definition_id", DEFINITION]]),
                        json!({"kind":"operation_submitted","operation_id":SECOND}),
                        false,
                    ),
                    step(
                        "operation_observe",
                        json!([["operation_id", SECOND]]),
                        waiting(SECOND, "j"),
                        false,
                    ),
                    step(
                        "operation_review",
                        json!([["operation_id", SECOND]]),
                        changed.clone(),
                        false,
                    ),
                ])
            });
            let mut session = session(held);
            let review = session.status().await.unwrap();
            session
                .answer_review(
                    review.review_digest.as_deref(),
                    true,
                    Some(vec!["contact.postcode".into()]),
                )
                .await
                .unwrap();
            let shown = session.drive(&Fixed(prepared())).await.unwrap();
            assert_eq!(shown.state, "review");
            assert_eq!(shown.fields[0].incoming.as_deref(), Some("29999"));
            assert!(session.pending.is_none());
        }

        #[tokio::test]
        async fn a_path_that_is_not_a_proposed_value_of_the_review_is_a_conflict() {
            let held = holder(|_| first_steps(vec![]));
            let mut session = session(held);
            let review = session.status().await.unwrap();
            for accepted in [
                vec!["auth.password".to_owned()],
                vec!["contact.phone".into(), "contact.phone".into()],
            ] {
                let refused = session
                    .answer_review(review.review_digest.as_deref(), true, Some(accepted))
                    .await
                    .unwrap_err();
                assert_eq!(refused.code, "conflict");
            }
            let rejected = session
                .answer_review(review.review_digest.as_deref(), false, Some(vec![]))
                .await
                .unwrap_err();
            assert_eq!(rejected.code, "conflict");
            assert!(session.pending.is_none());
        }

        #[test]
        fn the_follow_up_request_adopts_only_what_was_accepted_and_names_the_stored_read() {
            let accepted = [("contact.phone".to_owned(), "611".to_owned())];
            let request = follow_up_request(&prepared(), PROFILE, &accepted).unwrap();
            assert_eq!(request["field_intents"][0]["intent"], "preserve");
            assert_eq!(request["field_intents"][1]["intent"], "adopt");
            assert_eq!(request["stored_observation"]["captured_at"], CAPTURED);
            let mut absent = prepared();
            absent["observation"] = Value::Null;
            assert_eq!(
                follow_up_request(&absent, PROFILE, &accepted)
                    .unwrap_err()
                    .code,
                "conflict"
            );
            let unknown = [("auth.password".to_owned(), "x".to_owned())];
            assert_eq!(
                follow_up_request(&prepared(), PROFILE, &unknown)
                    .unwrap_err()
                    .code,
                "conflict"
            );
        }
    }
}
