//! Provider administration through the dedicated service's authenticated endpoint.
mod wire;
use crate::{agent::AgentHost, shell::sign_in::wire::Outcome};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation};
use serde_json::{Value, json};
use std::sync::Arc;
use tauri::{
    State,
    ipc::{InvokeBody, Request},
};
use wire::{CommandFailure, Entry, Refusal, SignInSnapshot, Status};
use zeroize::Zeroizing;

fn invalid() -> ApplicationError {
    ApplicationError::new(ErrorCode::InvalidArguments, Operation::Cli)
}
fn target(provider: &str, revision: &str) -> Result<Value, CommandFailure> {
    if !wire::is_provider_id(provider)
        || revision.len() != 64
        || !revision
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        return Err(invalid().into());
    }
    Ok(json!({"provider":provider,"expected_revision":revision}))
}
fn outcome(result: Value) -> Outcome {
    let result = if result["kind"] == "refused"
        || (result
            .as_object()
            .is_some_and(|object| object.len() == 1 && object.contains_key("code")))
    {
        let code = match result["code"].as_str().unwrap_or("unknown") {
            "signed_out" => "not_signed_in",
            "sign_in_unavailable" => "unsupported_flow",
            "service_stopping" => "runtime_unavailable",
            "invalid_request" | "service_failed" => "unknown",
            code => code,
        };
        json!({"refused":code})
    } else if let Some(entry) = result.get("entry") {
        entry.clone()
    } else {
        result
    };
    Outcome::Success {
        result,
        active_profile: None,
    }
}

/// Recheck current profile settings before accepting an agent message. A
/// running gateway remains available for settings even with no usable provider.
pub(crate) fn agent_selection_available(
    host: &AgentHost,
    provider: &str,
    transport: &str,
) -> Result<bool, ApplicationError> {
    let answer = host.administer(json!({"action":"status"}), None)?;
    match wire::status(outcome(answer)) {
        Ok(status) => Ok(status.permits_agent(provider, transport)),
        Err(CommandFailure::Host(error)) => Err(error),
        Err(CommandFailure::Refused(_)) => {
            Err(ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
                .with_reason("provider_settings_unavailable"))
        }
    }
}
async fn execute(
    host: &State<'_, Arc<AgentHost>>,
    request: Value,
    secret: Option<Zeroizing<Vec<u8>>>,
) -> Result<Outcome, CommandFailure> {
    let host = host.inner().clone();
    let result = tauri::async_runtime::spawn_blocking(move || host.administer(request, secret))
        .await
        .map_err(|_| invalid())??;
    Ok(outcome(result))
}
pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        provider_settings_status,
        provider_settings_set,
        provider_settings_remove,
        provider_settings_turn_on,
        provider_settings_reset,
        provider_sign_in_start,
        provider_sign_in_status,
        provider_sign_in_cancel
    ]
}
#[tauri::command]
pub async fn provider_settings_status(
    state: State<'_, Arc<AgentHost>>,
) -> Result<Status, CommandFailure> {
    wire::status(execute(&state, json!({"action":"status"}), None).await?)
}
#[tauri::command]
pub async fn provider_settings_set(
    state: State<'_, Arc<AgentHost>>,
    request: Request<'_>,
) -> Result<Entry, CommandFailure> {
    let header = |name: &str| request.headers().get(name).and_then(|v| v.to_str().ok());
    let provider = header("x-cadrumo-provider").ok_or_else(invalid)?.to_owned();
    let revision = header("x-cadrumo-revision").ok_or_else(invalid)?;
    let mut document = target(&provider, revision)?;
    document["action"] = json!("set");
    match (
        header("x-cadrumo-base-url"),
        header("x-cadrumo-clear-base-url"),
    ) {
        (None, None) => {}
        (None, Some("1")) => document["base_url"] = json!(""),
        (Some(url), None) if url.len() <= 2048 && !url.chars().any(char::is_control) => {
            document["base_url"] = json!(url)
        }
        _ => return Err(Refusal::BaseUrlRejected.into()),
    }
    let InvokeBody::Raw(bytes) = request.body() else {
        return Err(invalid().into());
    };
    if bytes.is_empty() || bytes.len() > 16 * 1024 || std::str::from_utf8(bytes).is_err() {
        return Err(Refusal::InvalidKeyFormat.into());
    }
    let secret = Zeroizing::new(bytes.clone());
    wire::changed(execute(&state, document, Some(secret)).await?, &provider)
}
#[tauri::command]
pub async fn provider_settings_remove(
    state: State<'_, Arc<AgentHost>>,
    provider: String,
    revision: String,
) -> Result<Entry, CommandFailure> {
    change(&state, "remove", &provider, &revision).await
}
/// Turn an off lane back on with what it kept: its stored key, or its
/// provider's own sign-in.
#[tauri::command]
pub async fn provider_settings_turn_on(
    state: State<'_, Arc<AgentHost>>,
    provider: String,
    revision: String,
) -> Result<Entry, CommandFailure> {
    change(&state, "turn_on", &provider, &revision).await
}
#[tauri::command]
pub async fn provider_settings_reset(
    state: State<'_, Arc<AgentHost>>,
    provider: String,
    revision: String,
) -> Result<Entry, CommandFailure> {
    change(&state, "reset", &provider, &revision).await
}

#[tauri::command]
pub async fn provider_sign_in_start(
    state: State<'_, Arc<AgentHost>>,
    provider: String,
    revision: String,
    method: String,
) -> Result<SignInSnapshot, CommandFailure> {
    let mut request = target(&provider, &revision)?;
    let method = wire::SignInMethod::parse(&method).ok_or_else(invalid)?;
    request["action"] = json!("connect");
    request["method"] = json!(method);
    wire::sign_in_snapshot(execute(&state, request, None).await?, Some(&provider), None)
}

#[tauri::command]
pub async fn provider_sign_in_status(
    state: State<'_, Arc<AgentHost>>,
    attempt_id: String,
) -> Result<SignInSnapshot, CommandFailure> {
    if !wire::is_attempt_id(&attempt_id) {
        return Err(invalid().into());
    }
    let request = json!({"action":"connect_status","attempt_id":attempt_id});
    wire::sign_in_snapshot(
        execute(&state, request, None).await?,
        None,
        Some(&attempt_id),
    )
}

#[tauri::command]
pub async fn provider_sign_in_cancel(
    state: State<'_, Arc<AgentHost>>,
    attempt_id: String,
) -> Result<SignInSnapshot, CommandFailure> {
    if !wire::is_attempt_id(&attempt_id) {
        return Err(invalid().into());
    }
    let request = json!({"action":"connect_cancel","attempt_id":attempt_id});
    wire::sign_in_snapshot(
        execute(&state, request, None).await?,
        None,
        Some(&attempt_id),
    )
}

async fn change(
    state: &State<'_, Arc<AgentHost>>,
    action: &str,
    provider: &str,
    revision: &str,
) -> Result<Entry, CommandFailure> {
    let mut request = target(provider, revision)?;
    request["action"] = json!(action);
    wire::changed(execute(state, request, None).await?, provider)
}
