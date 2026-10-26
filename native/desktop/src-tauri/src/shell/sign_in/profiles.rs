//! Profile deletion relays the canonical CLI and runtime custody transaction.
use super::{Call, SignIn, failure, label, supported, wire};
use cadrumo_application::error::application::{ErrorCode, Result};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tauri::{State, http::HeaderMap};

const REVIEW: Call = Call {
    words: &["profile", "delete"],
    leaf: "profile.delete",
    command: "config.profile.delete",
    reads: true,
    runtime: false,
    slow: false,
};
const DELETE: Call = Call {
    words: &["profile", "delete", "--yes"],
    leaf: "profile.delete",
    command: "config.profile.delete",
    reads: false,
    runtime: false,
    slow: true,
};

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct DeleteReview {
    name: String,
    profile_id: String,
    digest: String,
}

#[derive(Deserialize)]
struct Fingerprint {
    digest: String,
}
#[derive(Deserialize)]
struct DeleteResult {
    profile_id: String,
    display_name: String,
    deleted: bool,
    fingerprint: Fingerprint,
    completed_at: Option<String>,
}

fn checked_name(name: &str) -> Result<()> {
    // Reuse the exact label rules without accepting paths or shell expansion.
    let encoded: String = name
        .as_bytes()
        .iter()
        .map(|byte| format!("%{byte:02X}"))
        .collect();
    let mut headers = HeaderMap::new();
    headers.insert(
        super::PROFILE_HEADER,
        encoded
            .parse()
            .map_err(|_| failure(ErrorCode::InvalidArguments))?,
    );
    label(&headers)?;
    Ok(())
}

fn decoded(
    outcome: wire::Outcome,
    name: &str,
    deleted: bool,
) -> std::result::Result<DeleteResult, wire::CommandFailure> {
    match outcome {
        wire::Outcome::Refused { refusal } => Err(wire::CommandFailure::Refused(refusal)),
        wire::Outcome::Success { result, .. } => {
            let result: DeleteResult =
                serde_json::from_value(result).map_err(|_| failure(ErrorCode::ReadFailed))?;
            if result.display_name != name
                || result.deleted != deleted
                || result.completed_at.is_some() != deleted
            {
                return Err(failure(ErrorCode::ReadFailed).into());
            }
            Ok(result)
        }
    }
}

#[tauri::command]
pub async fn profile_delete_review(
    state: State<'_, Arc<SignIn>>,
    name: String,
) -> std::result::Result<DeleteReview, wire::CommandFailure> {
    if !supported() {
        return Err(failure(ErrorCode::UnsupportedPlatform).into());
    }
    checked_name(&name)?;
    let state = state.inner().clone();
    let requested = name.clone();
    let output = super::super::blocking(move || state.run(&REVIEW, Some(&requested), None)).await?;
    let result = decoded(output, &name, false)?;
    Ok(DeleteReview {
        name,
        profile_id: result.profile_id,
        digest: result.fingerprint.digest,
    })
}

#[tauri::command]
pub async fn profile_delete(
    state: State<'_, Arc<SignIn>>,
    review: DeleteReview,
    confirmation: String,
    acknowledged: bool,
) -> std::result::Result<(), wire::CommandFailure> {
    if !supported() {
        return Err(failure(ErrorCode::UnsupportedPlatform).into());
    }
    checked_name(&review.name)?;
    if !acknowledged
        || confirmation != review.name
        || review.profile_id.len() != 36
        || !review
            .profile_id
            .bytes()
            .all(|b| b.is_ascii_hexdigit() || b == b'-')
        || review.digest.len() != 64
        || !review.digest.bytes().all(|b| b.is_ascii_hexdigit())
    {
        return Err(failure(ErrorCode::InvalidArguments).into());
    }
    let state = state.inner().clone();
    let requested = review.name.clone();
    let id = review.profile_id.clone();
    let digest = review.digest.clone();
    let output = super::super::blocking(move || {
        let options = vec![
            "--expected-profile-id".into(),
            id,
            "--expected-digest".into(),
            digest,
        ];
        wire::decode(
            DELETE.leaf,
            &state.output_with_options(&DELETE, Some(&requested), None, &options)?,
        )
    })
    .await?;
    let result = decoded(output, &review.name, true)?;
    if result.profile_id != review.profile_id || result.fingerprint.digest != review.digest {
        return Err(failure(ErrorCode::ReadFailed).into());
    }
    Ok(())
}
