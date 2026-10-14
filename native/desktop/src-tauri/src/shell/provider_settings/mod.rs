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
use wire::{CommandFailure, Entry, Refusal, Status};
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
        provider_settings_reset
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
#[tauri::command]
pub async fn provider_settings_reset(
    state: State<'_, Arc<AgentHost>>,
    provider: String,
    revision: String,
) -> Result<Entry, CommandFailure> {
    change(&state, "reset", &provider, &revision).await
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
