//! Provider administration through the dedicated service's authenticated endpoint.
pub(crate) mod wire;
use crate::{agent::AgentHost, shell::sign_in::wire::Outcome};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation};
use serde_json::{Value, json};
use std::sync::Arc;
use std::time::Duration;
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
        #[cfg(test)]
        active_profile: None,
    }
}

/// Recheck current profile settings before accepting an agent message. A
/// running gateway remains available for settings even with no usable provider.
pub(crate) fn agent_selection_available(
    host: &AgentHost,
    provider: &str,
    transport: &str,
) -> Result<bool, CommandFailure> {
    read_status(
        || host.administer(json!({"action":"status"}), None),
        Duration::from_millis(250),
    )
    .map(|status| status.permits_agent(provider, transport))
}

/// A cold sign-in probe outlives the service's bounded status exchange. Its
/// work continues after `busy`, and the next read collects that result.
/// Retry only this read and only that explicit response, never a mutation
/// or an exchange whose outcome is unknown.
pub(crate) fn read_status(
    mut request: impl FnMut() -> Result<Value, ApplicationError>,
    pause: Duration,
) -> Result<Status, CommandFailure> {
    for attempt in 0..4 {
        match wire::status(outcome(request()?)) {
            Err(CommandFailure::Refused(wire::Refused {
                code: Refusal::Busy,
            })) if attempt < 3 => {
                std::thread::sleep(pause);
            }
            result => return result,
        }
    }
    unreachable!("the last attempt returns its result")
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
        provider_sign_in_cancel,
        provider_sign_in_submit_code
    ]
}
#[tauri::command]
pub async fn provider_settings_status(
    state: State<'_, Arc<AgentHost>>,
) -> Result<Status, CommandFailure> {
    let host = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        read_status(
            || host.administer(json!({"action":"status"}), None),
            Duration::from_millis(250),
        )
    })
    .await
    .map_err(|_| invalid())?
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

fn code_submission(attempt_id: &str, bytes: &[u8]) -> Result<Value, CommandFailure> {
    if !wire::is_attempt_id(attempt_id)
        || bytes.is_empty()
        || bytes.len() > 2048
        || !bytes.iter().all(|byte| (33..=126).contains(byte))
    {
        return Err(invalid().into());
    }
    Ok(json!({"action":"connect_submit_code","attempt_id":attempt_id}))
}

#[tauri::command]
pub async fn provider_sign_in_submit_code(
    state: State<'_, Arc<AgentHost>>,
    request: Request<'_>,
) -> Result<SignInSnapshot, CommandFailure> {
    let attempt_id = request
        .headers()
        .get("x-cadrumo-attempt-id")
        .and_then(|value| value.to_str().ok())
        .ok_or_else(invalid)?;
    let InvokeBody::Raw(bytes) = request.body() else {
        return Err(invalid().into());
    };
    let document = code_submission(attempt_id, bytes)?;
    let secret = Zeroizing::new(bytes.clone());
    wire::sign_in_snapshot(
        execute(&state, document, Some(secret)).await?,
        None,
        Some(attempt_id),
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn code_submission_requires_a_bounded_printable_code_and_attempt() {
        let id = "123e4567-e89b-42d3-a456-426614174000";
        let document = code_submission(id, b"one-time-code").unwrap();
        assert_eq!(
            document,
            json!({"action":"connect_submit_code","attempt_id":id})
        );
        for bytes in [
            Vec::new(),
            vec![b'x'; 2049],
            b"space bad".to_vec(),
            vec![0x80],
        ] {
            assert!(code_submission(id, &bytes).is_err());
        }
        assert!(code_submission("stale-id", b"code").is_err());
        assert!(code_submission(id, &vec![b'!'; 2048]).is_ok());
    }

    #[test]
    fn a_slow_status_read_is_collected_without_restarting_its_work() {
        let mut calls = 0;
        let status = read_status(
            || {
                calls += 1;
                Ok(if calls < 3 {
                    json!({"kind":"refused","code":"busy"})
                } else {
                    json!({"development":false,"providers":[]})
                })
            },
            Duration::ZERO,
        )
        .unwrap();
        assert_eq!(calls, 3);
        assert!(status.providers.is_empty());
    }

    #[test]
    fn status_retries_are_bounded_and_preserve_the_refusal() {
        let mut calls = 0;
        let result = read_status(
            || {
                calls += 1;
                Ok(json!({"kind":"refused","code":"busy"}))
            },
            Duration::ZERO,
        );
        assert_eq!(calls, 4);
        assert!(matches!(
            result,
            Err(CommandFailure::Refused(wire::Refused {
                code: Refusal::Busy
            }))
        ));
        for code in ["signed_out", "profile_locked", "catalog_unavailable"] {
            calls = 0;
            let result = read_status(
                || {
                    calls += 1;
                    Ok(json!({"kind":"refused","code":code}))
                },
                Duration::ZERO,
            );
            assert!(result.is_err());
            assert_eq!(calls, 1);
        }
    }

    #[test]
    fn a_failed_status_exchange_is_not_replayed() {
        let mut calls = 0;
        let result = read_status(
            || {
                calls += 1;
                Err(ApplicationError::new(ErrorCode::TimedOut, Operation::Cli))
            },
            Duration::ZERO,
        );
        assert!(matches!(result, Err(CommandFailure::Host(_))));
        assert_eq!(calls, 1);
    }
}
