//! The setup reviews an assistant's setup leaves for the desktop person: the
//! runtime names the ones this person may claim, and each is read, claimed
//! and answered through the held person session. Native in-process setup
//! remains on its existing engine path.
use super::{SetupHost, failed, lock};
use crate::agent::person::Person;
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
    Pending,
    Claim(Coordinates),
    Answer(Coordinates, Decision),
}

#[derive(Debug, Serialize)]
pub struct Failure {
    code: String,
    /// What lay behind an `unavailable` the window words without it; diagnostics keep it.
    #[serde(skip)]
    cause: Option<ApplicationError>,
}

impl From<ApplicationError> for Failure {
    fn from(error: ApplicationError) -> Self {
        Self {
            code: "unavailable".into(),
            cause: Some(error),
        }
    }
}

fn refused(code: &str) -> Failure {
    Failure {
        code: code.into(),
        cause: None,
    }
}

fn checked(reply: Value) -> Result<Value, Failure> {
    if reply["kind"] == "operation_refused" {
        return Err(match reply["code"].as_str() {
            Some(code) => refused(code),
            None => failed("setup_review_reply_shape").into(),
        });
    }
    Ok(reply)
}

pub async fn exchange(host: &SetupHost, action: Action) -> Result<Value, Failure> {
    let result = carry(host, action).await;
    if let Err(Failure {
        cause: Some(error), ..
    }) = &result
    {
        host.reports.error(error);
    }
    result
}

/// Only a setup operation's review is offered or answered here.
fn require_setup(held: &mut Person, operation_id: &str) -> Result<(), Failure> {
    let observed = checked(held.exchange(json!({
        "action": "operation_observe", "operation_id": operation_id, "after_cursor": 0,
    }))?)?;
    if observed["observation"]["projection"]["definition_id"] != "config.provision.setup" {
        return Err(refused("not_pending"));
    }
    Ok(())
}

/// Every setup review this person may claim now, each as currently shown.
/// One that moved on between the listing and its read is left out; a
/// runtime or transport failure fails the whole read.
fn pending(held: &mut Person) -> Result<Value, Failure> {
    let listed = checked(held.exchange(json!({"action": "operation_review_claimable"}))?)?;
    let ids = listed["operation_ids"]
        .as_array()
        .ok_or_else(|| Failure::from(failed("setup_review_reply_shape")))?;
    let mut reviews = Vec::with_capacity(ids.len());
    for id in ids {
        let id = id
            .as_str()
            .ok_or_else(|| Failure::from(failed("setup_review_reply_shape")))?;
        let review = require_setup(held, id).and_then(|()| {
            checked(held.exchange(json!({"action": "operation_review", "operation_id": id}))?)
        });
        match review {
            Ok(review) => reviews.push(review),
            Err(Failure { cause: None, .. }) => {}
            Err(failure) => return Err(failure),
        }
    }
    Ok(Value::Array(reviews))
}

async fn carry(host: &SetupHost, action: Action) -> Result<Value, Failure> {
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
        let request = match action {
            Action::Pending => return pending(&mut held),
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
        require_setup(&mut held, request["operation_id"].as_str().unwrap_or_default())?;
        checked(held.exchange(request)?)
    })
    .await
    .map_err(|error| Failure::from(failed("setup_review_join").caused_by(error)))?;
    let after = host.sign_in.read_status().await?;
    if after.state != Presence::Present
        || !after.runtime_ready()
        || after.active_profile.as_deref() != Some(&label)
    {
        return Err(refused("not_signed_in"));
    }
    result
}
