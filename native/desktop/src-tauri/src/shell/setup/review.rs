//! Explicit response-only review of a known registered setup operation.
//! Native in-process setup remains on its existing engine path.
use super::{SetupHost, failed, lock};
use crate::shell::sign_in::Presence;
use cadrumo_application::error::application::ApplicationError;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Coordinates {
    operation_id: String,
    interaction_id: String,
    revision: u64,
    review_digest: String,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Decision {
    Apply,
    Reject,
}

pub enum Action {
    Read { operation_id: String },
    Claim(Coordinates),
    Answer(Coordinates, Decision),
}

#[derive(Debug, Serialize)]
pub struct Failure {
    code: String,
}

impl From<ApplicationError> for Failure {
    fn from(_: ApplicationError) -> Self {
        Self {
            code: "unavailable".into(),
        }
    }
}

fn refused(code: &str) -> Failure {
    Failure { code: code.into() }
}

fn checked(reply: Value) -> Result<Value, Failure> {
    if reply["kind"] == "operation_refused" {
        return Err(refused(reply["code"].as_str().unwrap_or("unavailable")));
    }
    Ok(reply)
}

pub async fn exchange(host: &SetupHost, action: Action) -> Result<Value, Failure> {
    let before = host.sign_in.read_status().await?;
    let label = before
        .active_profile
        .clone()
        .ok_or_else(|| refused("not_signed_in"))?;
    if before.state != Presence::Present || !before.runtime_ready() {
        return Err(refused("not_signed_in"));
    }
    let sign_in = host.sign_in.clone();
    let active_label = label.clone();
    let result = tauri::async_runtime::spawn_blocking(move || {
        // Resolve the exact admitted profile and person, never a frontend boolean.
        let profile_id = sign_in.profile_id(&active_label)?;
        let person = sign_in.person(&profile_id)?;
        let mut held = lock(&person);
        let operation_id = match &action {
            Action::Read { operation_id } => operation_id,
            Action::Claim(review) | Action::Answer(review, _) => &review.operation_id,
        };
        let observed = checked(held.exchange(json!({
            "action": "operation_observe", "operation_id": operation_id, "after_cursor": 0,
        }))?)?;
        if observed["observation"]["projection"]["definition_id"] != "config.provision.setup" {
            return Err(refused("not_pending"));
        }
        let request = match action {
            Action::Read { operation_id } => json!({"action": "operation_review", "operation_id": operation_id}),
            Action::Claim(review) => json!({
                "action": "operation_review_claim", "operation_id": review.operation_id,
                "interaction_id": review.interaction_id, "revision": review.revision, "review_digest": review.review_digest,
            }),
            Action::Answer(review, decision) => json!({
                "action": "operation_respond", "operation_id": review.operation_id,
                "interaction_id": review.interaction_id, "revision": review.revision, "review_digest": review.review_digest,
                "decision": decision,
            }),
        };
        checked(held.exchange(request)?)
    }).await.map_err(|_| Failure::from(failed()))?;
    let after = host.sign_in.read_status().await?;
    if after.state != Presence::Present
        || !after.runtime_ready()
        || after.active_profile.as_deref() != Some(&label)
    {
        return Err(refused("not_signed_in"));
    }
    result
}
