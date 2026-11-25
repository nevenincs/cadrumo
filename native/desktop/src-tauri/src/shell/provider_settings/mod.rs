//! Provider administration through the dedicated service's authenticated endpoint.
pub(crate) mod wire;
use crate::{
    agent::{AgentHost, supervisor::AdminWait},
    shell::sign_in::wire::Outcome,
};
use cadrumo_application::diagnostics::{
    Diagnostics,
    desktop::{
        BackendReason, DesktopDiagnostic, DesktopDiagnosticCode, DesktopEvent, DiagnosticOrigin,
        RelayFailureCode,
    },
    service::LogLevel,
};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation};
use serde::Serialize;
use serde_json::{Value, json};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tauri::{
    State,
    ipc::{InvokeBody, Request},
};
use wire::{CommandFailure, Entry, Refusal, SignInSnapshot, Status};
use zeroize::Zeroizing;

fn invalid() -> ApplicationError {
    ApplicationError::new(ErrorCode::InvalidArguments, Operation::Cli)
        .with_reason("provider_settings_invalid_arguments")
}

/// The closed word a serialized enum value stands for.
fn word(value: &impl Serialize) -> Option<String> {
    serde_json::to_value(value)
        .ok()?
        .as_str()
        .map(str::to_owned)
}

/// Record why a command failed: the command, the refusal or host code, the
/// closed cause the service named and the reference of the service's own log
/// line for it. Nothing from a payload is recorded.
pub(crate) fn record_failure(
    diagnostics: &Diagnostics,
    command: &'static str,
    failure: &CommandFailure,
) {
    let (code, reason, logger) = match failure {
        CommandFailure::Host(error) => (
            DesktopDiagnosticCode::from(error.code),
            error.reason.as_deref().and_then(BackendReason::parse),
            "provider_settings".to_owned(),
        ),
        CommandFailure::Refused(refused) => {
            let code = word(&refused.code);
            let cause = refused.cause.as_ref().and_then(word);
            (
                DesktopDiagnosticCode::Relay(RelayFailureCode::Refused),
                cause
                    .as_deref()
                    .or(code.as_deref())
                    .and_then(BackendReason::parse),
                format!(
                    "provider_settings refusal={} log_ref={}",
                    code.as_deref().unwrap_or("unknown"),
                    refused.log_ref.as_deref().unwrap_or("none")
                ),
            )
        }
    };
    diagnostics.desktop_diagnostic(DesktopDiagnostic {
        origin: DiagnosticOrigin::Rust,
        logger: Some(logger),
        event: DesktopEvent::CommandRejected,
        level: LogLevel::Warning,
        command: Some(command.to_owned()),
        code: Some(code),
        dropped: 0,
        line: None,
        column: None,
        reason,
        summary: None,
    });
}

/// Pass a command's result on after recording its failure.
fn logged<T>(
    host: &AgentHost,
    command: &'static str,
    result: Result<T, CommandFailure>,
) -> Result<T, CommandFailure> {
    if let Err(failure) = &result {
        record_failure(host.diagnostics(), command, failure);
    }
    result
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

/// The refusal an answer from the service stands for. Every code the service
/// serves for a refusal passes through under its own name, so a known failure
/// is never reported as an unknown one; the cause and the log reference it
/// carries pass through with it.
pub(crate) fn outcome(result: Value) -> Outcome {
    let refusal_fields = |object: &serde_json::Map<String, Value>| {
        object.contains_key("code")
            && object
                .keys()
                .all(|key| matches!(key.as_str(), "kind" | "code" | "cause" | "log_ref"))
    };
    let result = if result["kind"] == "refused" || result.as_object().is_some_and(refusal_fields) {
        let code = match result["code"].as_str().unwrap_or("unknown") {
            "signed_out" => "not_signed_in",
            "sign_in_unavailable" => "unsupported_flow",
            "service_stopping" => "runtime_unavailable",
            code => code,
        };
        let mut refused = json!({"refused":code});
        for field in ["cause", "log_ref"] {
            if let Some(value) = result.get(field).filter(|value| value.is_string()) {
                refused[field] = value.clone();
            }
        }
        refused
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
        STATUS_BUSY_PATIENCE,
    )
    .map(|status| status.permits_agent(provider, transport))
}

/// How long a status read answered `busy` is read again. The service answers
/// `busy` while it reads its provider catalog, which probes every lane and took
/// 5.4 s for 13 lanes on a fresh profile, where four reads gave up after one
/// second and left the settings page saying the providers could not be loaded.
/// The bound is on time, not on reads: each exchange can itself take seconds,
/// and 48 such reads kept a window waiting minutes.
pub(crate) const STATUS_BUSY_PATIENCE: Duration = Duration::from_secs(12);

/// The window's own status read asks again after `busy` for less time: it draws
/// the busy answer as the agent starting and reads again when the service
/// publishes the agent ready. It bounds those repeated asks only, never an
/// exchange the service is answering.
const WINDOW_STATUS_PATIENCE: Duration = Duration::from_secs(4);

/// A cold sign-in probe or catalog read outlives the service's bounded status
/// exchange. Its work continues after `busy`, and the next read collects that
/// result. Retry only this read and only that explicit response, never a
/// mutation or an exchange whose outcome is unknown.
pub(crate) fn read_status(
    mut request: impl FnMut() -> Result<Value, ApplicationError>,
    pause: Duration,
    patience: Duration,
) -> Result<Status, CommandFailure> {
    let began = Instant::now();
    loop {
        match wire::status(outcome(request()?)) {
            Err(CommandFailure::Refused(wire::Refused {
                code: Refusal::Busy,
                ..
            })) if began.elapsed() + pause < patience => {
                std::thread::sleep(pause);
            }
            result => return result,
        }
    }
}
/// Settings are read and changed only through an admitted admin endpoint. The
/// window asks for them as soon as the service starts, and admission follows
/// some seconds later, so a call made meanwhile waits for it instead of failing
/// the settings until the window asks again. A service still starting when the
/// bound elapses answers the busy word the window retries; a service that is
/// not starting reaches `call`, which refuses as it always has.
/// The window's status read. It is not waited for while the service starts the agent:
/// the window draws the busy answer at once and reads again when the service publishes
/// the agent ready, which it does only after admission. A `busy` answer is asked again
/// for at most `limit`. An exchange under way is collected within the host's own status
/// exchange bound, never cut at `limit`: the service's status reads only the store and
/// never waits for the agent, so a slow one is a store read under a loaded machine
/// (seconds behind the profile guard), and cutting it answered every read busy and left
/// the settings without lanes, while nothing cued the window to ask for the answer the
/// service still gave.
pub(crate) async fn window_status(
    admitted: impl FnOnce() -> AdminWait + Send + 'static,
    exchange: impl FnMut() -> Result<Value, ApplicationError> + Send + 'static,
    limit: Duration,
) -> Result<Status, CommandFailure> {
    tauri::async_runtime::spawn_blocking(move || {
        when_admitted(admitted, || {
            read_status(exchange, Duration::from_millis(250), limit)
        })
    })
    .await
    .map_err(|_| invalid().with_reason("provider_settings_task_failed"))
    .map_err(CommandFailure::from)
    .and_then(|result| result)
}

pub(crate) fn when_admitted<T>(
    wait: impl FnOnce() -> AdminWait,
    call: impl FnOnce() -> Result<T, CommandFailure>,
) -> Result<T, CommandFailure> {
    match wait() {
        AdminWait::StillStarting => Err(Refusal::Busy.into()),
        AdminWait::Admitted | AdminWait::NotStarting => call(),
    }
}

async fn execute(
    host: &State<'_, Arc<AgentHost>>,
    request: Value,
    secret: Option<Zeroizing<Vec<u8>>>,
) -> Result<Outcome, CommandFailure> {
    let host = host.inner().clone();
    let result = tauri::async_runtime::spawn_blocking(move || {
        when_admitted(
            || host.await_admin(),
            || Ok(host.administer(request, secret)?),
        )
    })
    .await
    .map_err(|_| invalid().with_reason("provider_settings_task_failed"))??;
    Ok(outcome(result))
}
pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        provider_settings_status,
        provider_settings_set,
        provider_settings_remove,
        provider_settings_turn_on,
        provider_settings_reset,
        provider_sign_out,
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
    let read = window_status(
        {
            let host = host.clone();
            move || host.admin_now()
        },
        {
            let host = host.clone();
            move || host.administer(json!({"action":"status"}), None)
        },
        WINDOW_STATUS_PATIENCE,
    )
    .await;
    logged(&host, "provider_settings_status", read)
}
#[tauri::command]
pub async fn provider_settings_set(
    state: State<'_, Arc<AgentHost>>,
    request: Request<'_>,
) -> Result<Entry, CommandFailure> {
    let result = set(&state, &request).await;
    logged(state.inner(), "provider_settings_set", result)
}
async fn set(
    state: &State<'_, Arc<AgentHost>>,
    request: &Request<'_>,
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
    wire::changed(execute(state, document, Some(secret)).await?, &provider)
}
#[tauri::command]
pub async fn provider_settings_remove(
    state: State<'_, Arc<AgentHost>>,
    provider: String,
    revision: String,
) -> Result<Entry, CommandFailure> {
    let result = change(&state, "remove", &provider, &revision).await;
    logged(state.inner(), "provider_settings_remove", result)
}
/// Turn an off lane back on with what it kept: its stored key, or its
/// provider's own sign-in.
#[tauri::command]
pub async fn provider_settings_turn_on(
    state: State<'_, Arc<AgentHost>>,
    provider: String,
    revision: String,
) -> Result<Entry, CommandFailure> {
    let result = change(&state, "turn_on", &provider, &revision).await;
    logged(state.inner(), "provider_settings_turn_on", result)
}
#[tauri::command]
pub async fn provider_settings_reset(
    state: State<'_, Arc<AgentHost>>,
    provider: String,
    revision: String,
) -> Result<Entry, CommandFailure> {
    let result = change(&state, "reset", &provider, &revision).await;
    logged(state.inner(), "provider_settings_reset", result)
}

/// Sign a signed-in app lane's provider out through the logout the agent
/// declares for it, answering with the lane's refreshed entry. The service
/// refuses a lane whose agent declares no logout.
#[tauri::command]
pub async fn provider_sign_out(
    state: State<'_, Arc<AgentHost>>,
    provider: String,
    revision: String,
) -> Result<Entry, CommandFailure> {
    let result = change(&state, "sign_out", &provider, &revision).await;
    logged(state.inner(), "provider_sign_out", result)
}

#[tauri::command]
pub async fn provider_sign_in_start(
    state: State<'_, Arc<AgentHost>>,
    provider: String,
    revision: String,
    method: String,
) -> Result<SignInSnapshot, CommandFailure> {
    let result = sign_in_start(&state, &provider, &revision, &method).await;
    logged(state.inner(), "provider_sign_in_start", result)
}
async fn sign_in_start(
    state: &State<'_, Arc<AgentHost>>,
    provider: &str,
    revision: &str,
    method: &str,
) -> Result<SignInSnapshot, CommandFailure> {
    let mut request = target(provider, revision)?;
    let method = wire::SignInMethod::parse(method).ok_or_else(invalid)?;
    request["action"] = json!("connect");
    request["method"] = json!(method);
    wire::sign_in_snapshot(execute(state, request, None).await?, Some(provider), None)
}

#[tauri::command]
pub async fn provider_sign_in_status(
    state: State<'_, Arc<AgentHost>>,
    attempt_id: String,
) -> Result<SignInSnapshot, CommandFailure> {
    let result = attempt_request(&state, "connect_status", &attempt_id).await;
    logged(state.inner(), "provider_sign_in_status", result)
}

#[tauri::command]
pub async fn provider_sign_in_cancel(
    state: State<'_, Arc<AgentHost>>,
    attempt_id: String,
) -> Result<SignInSnapshot, CommandFailure> {
    let result = attempt_request(&state, "connect_cancel", &attempt_id).await;
    logged(state.inner(), "provider_sign_in_cancel", result)
}
async fn attempt_request(
    state: &State<'_, Arc<AgentHost>>,
    action: &str,
    attempt_id: &str,
) -> Result<SignInSnapshot, CommandFailure> {
    if !wire::is_attempt_id(attempt_id) {
        return Err(invalid().into());
    }
    let request = json!({"action":action,"attempt_id":attempt_id});
    wire::sign_in_snapshot(execute(state, request, None).await?, None, Some(attempt_id))
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
    let result = submit_code(&state, &request).await;
    logged(state.inner(), "provider_sign_in_submit_code", result)
}
async fn submit_code(
    state: &State<'_, Arc<AgentHost>>,
    request: &Request<'_>,
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
        execute(state, document, Some(secret)).await?,
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
    let request = change_request(action, provider, revision)?;
    wire::changed(execute(state, request, None).await?, provider)
}

/// The administration document of a guarded change to one lane.
fn change_request(action: &str, provider: &str, revision: &str) -> Result<Value, CommandFailure> {
    let mut request = target(provider, revision)?;
    request["action"] = json!(action);
    Ok(request)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test(flavor = "multi_thread")]
    async fn a_status_exchange_slower_than_the_windows_patience_is_collected_with_its_lanes() {
        // A store read behind a loaded profile guard took seconds; cutting it
        // at the window's patience answered busy and showed no lanes.
        let limit = Duration::from_millis(200);
        let read = window_status(
            || AdminWait::Admitted,
            || {
                std::thread::sleep(Duration::from_millis(800));
                Ok(json!({"providers":[signed_out_lane()],"reads_pending":false}))
            },
            limit,
        )
        .await
        .expect("a slow exchange answers with its status");
        assert_eq!(read.providers.len(), 1);
    }

    #[tokio::test(flavor = "multi_thread")]
    async fn a_window_read_answered_busy_asks_again_only_within_its_patience() {
        let limit = Duration::from_millis(600);
        let began = Instant::now();
        let read = window_status(
            || AdminWait::Admitted,
            || Ok(json!({"kind":"refused","code":"busy"})),
            limit,
        )
        .await;
        assert!(
            began.elapsed() < limit + Duration::from_millis(600),
            "answered after {:?}",
            began.elapsed()
        );
        assert!(matches!(
            read,
            Err(CommandFailure::Refused(wire::Refused {
                code: Refusal::Busy,
                ..
            }))
        ));
    }

    #[tokio::test(flavor = "multi_thread")]
    async fn a_window_read_while_the_service_starts_answers_busy_without_an_exchange() {
        let read = window_status(
            || AdminWait::StillStarting,
            || -> Result<Value, ApplicationError> {
                panic!("no exchange is made before admission")
            },
            WINDOW_STATUS_PATIENCE,
        )
        .await;
        assert!(matches!(
            read,
            Err(CommandFailure::Refused(wire::Refused {
                code: Refusal::Busy,
                ..
            }))
        ));
    }

    fn sign_out_answer(served: Value) -> Result<Entry, CommandFailure> {
        wire::changed(outcome(served), "beta_cli")
    }

    fn signed_out_lane() -> Value {
        json!({
            "id": "beta_cli", "provider": "beta", "display_name": "Beta CLI", "transport": "cli",
            "reads_off_host": true, "auth_kind": "provider_sign_in_only", "consumers": ["assistant"],
            "mode": "provider_sign_in", "credential_saved": false, "available": false,
            "source": "none", "readiness": "sign_in_required",
            "reason": "sign_in_with_provider_tool", "cli_state": "installed_signed_out",
            "sign_out_available": false, "revision": "0".repeat(64)
        })
    }

    #[test]
    fn a_sign_out_maps_through_as_a_turn_on_does() {
        let revision = "0".repeat(64);
        for action in ["turn_on", "sign_out"] {
            assert_eq!(
                change_request(action, "beta_cli", &revision).unwrap(),
                json!({"action": action, "provider": "beta_cli", "expected_revision": revision})
            );
            assert!(change_request(action, "beta_cli", "stale").is_err());
            assert!(change_request(action, "../beta", &revision).is_err());
        }
        let entry = sign_out_answer(json!({"entry": signed_out_lane()})).unwrap();
        assert_eq!(entry.id, "beta_cli");
        assert!(!entry.sign_out_available);
        for (served, refused) in [
            ("signed_out", "not_signed_in"),
            ("sign_in_unavailable", "unsupported_flow"),
            ("busy", "busy"),
            ("revision_conflict", "revision_conflict"),
            ("service_failed", "service_failed"),
        ] {
            let failure = refusal_of_entry(sign_out_answer(json!({
                "kind": "refused", "code": served, "cause": "lane_not_signable",
                "log_ref": "123e4567-e89b-42d3-a456-426614174000"
            })));
            assert_eq!(
                serde_json::to_value(failure).unwrap(),
                json!({
                    "code": refused, "cause": "lane_not_signable",
                    "log_ref": "123e4567-e89b-42d3-a456-426614174000"
                }),
                "{served}"
            );
        }
    }

    fn refusal_of_entry(result: Result<Entry, CommandFailure>) -> CommandFailure {
        match result {
            Err(failure) => failure,
            Ok(_) => panic!("expected a failure"),
        }
    }

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
                    json!({"providers":[],"reads_pending":false})
                })
            },
            Duration::ZERO,
            STATUS_BUSY_PATIENCE,
        )
        .unwrap();
        assert_eq!(calls, 3);
        assert!(status.providers.is_empty());
    }

    #[test]
    fn a_status_read_outlasting_a_catalog_read_is_collected() {
        // A catalog read answered `busy` for seconds; twenty reads span five.
        let mut calls = 0;
        let status = read_status(
            || {
                calls += 1;
                Ok(if calls <= 20 {
                    json!({"kind":"refused","code":"busy"})
                } else {
                    json!({"providers":[],"reads_pending":false})
                })
            },
            Duration::ZERO,
            STATUS_BUSY_PATIENCE,
        )
        .unwrap();
        assert_eq!(calls, 21);
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
            STATUS_BUSY_PATIENCE,
        );
        assert!(calls > 1);
        assert!(matches!(
            result,
            Err(CommandFailure::Refused(wire::Refused {
                code: Refusal::Busy,
                ..
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
                STATUS_BUSY_PATIENCE,
            );
            assert!(result.is_err());
            assert_eq!(calls, 1);
        }
    }

    #[test]
    fn a_status_read_whose_exchanges_are_slow_stops_at_its_patience() {
        // Each exchange took seconds while the service recomputed a busy
        // status; counted reads let one window read wait minutes.
        let began = Instant::now();
        let mut calls = 0;
        let result = read_status(
            || {
                calls += 1;
                std::thread::sleep(Duration::from_millis(200));
                Ok(json!({"kind":"refused","code":"busy"}))
            },
            Duration::from_millis(10),
            Duration::from_millis(500),
        );
        assert!(began.elapsed() < Duration::from_millis(1500));
        assert!((2..=4).contains(&calls));
        assert!(matches!(
            result,
            Err(CommandFailure::Refused(wire::Refused {
                code: Refusal::Busy,
                ..
            }))
        ));
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
            STATUS_BUSY_PATIENCE,
        );
        assert!(matches!(result, Err(CommandFailure::Host(_))));
        assert_eq!(calls, 1);
    }

    #[test]
    fn every_refusal_code_the_service_serves_passes_through_under_its_own_name() {
        for (served, passed) in [
            ("signed_out", "not_signed_in"),
            ("sign_in_unavailable", "unsupported_flow"),
            ("service_stopping", "runtime_unavailable"),
            ("invalid_request", "invalid_request"),
            ("service_failed", "service_failed"),
            ("busy", "busy"),
            ("revision_conflict", "revision_conflict"),
        ] {
            let Outcome::Success { result, .. } = outcome(json!({"kind":"refused","code":served}))
            else {
                panic!("a refusal is carried as a result");
            };
            assert_eq!(result, json!({"refused": passed}), "{served}");
        }
    }

    #[test]
    fn a_served_cause_and_log_reference_pass_through_a_refusal_with_or_without_a_kind() {
        let expected =
            json!({"refused":"busy","cause":"sign_in_in_progress","log_ref":"0a1b2c3d4e5f"});
        for served in [
            json!({"kind":"refused","code":"busy","cause":"sign_in_in_progress","log_ref":"0a1b2c3d4e5f"}),
            json!({"code":"busy","cause":"sign_in_in_progress","log_ref":"0a1b2c3d4e5f"}),
        ] {
            let Outcome::Success { result, .. } = outcome(served) else {
                panic!("a refusal is carried as a result");
            };
            assert_eq!(result, expected);
        }
        // A cause that is not text is not forwarded.
        let Outcome::Success { result, .. } =
            outcome(json!({"kind":"refused","code":"busy","cause":{"raw":"output"}}))
        else {
            panic!("a refusal is carried as a result");
        };
        assert_eq!(result, json!({"refused":"busy"}));
        // An answer that merely has a code field among others is not a refusal.
        let Outcome::Success { result, .. } = outcome(json!({"code":"x","entry_count":1})) else {
            panic!("an answer is carried as a result");
        };
        assert_eq!(result, json!({"code":"x","entry_count":1}));
    }

    #[test]
    fn a_refusal_through_the_wire_keeps_cause_and_reference_to_the_window() {
        let failure = refusal_of(wire::sign_in_snapshot(
            outcome(
                json!({"kind":"refused","code":"busy","cause":"sign_in_owner_held","log_ref":"0a1b2c3d4e5f"}),
            ),
            None,
            None,
        ));
        assert_eq!(
            serde_json::to_value(failure).unwrap(),
            json!({"code":"busy","cause":"sign_in_owner_held","log_ref":"0a1b2c3d4e5f"})
        );
        let failure = refusal_of(wire::sign_in_snapshot(
            outcome(json!({"kind":"refused","code":"invalid_request"})),
            None,
            None,
        ));
        assert_eq!(
            serde_json::to_value(failure).unwrap(),
            json!({"code":"invalid_request"})
        );
    }

    fn refusal_of(result: Result<SignInSnapshot, CommandFailure>) -> CommandFailure {
        match result {
            Err(failure) => failure,
            Ok(_) => panic!("expected a failure"),
        }
    }

    fn recorded(failure: &CommandFailure, command: &'static str) -> DesktopDiagnostic {
        let diagnostics = Diagnostics::default();
        record_failure(&diagnostics, command, failure);
        diagnostics
            .snapshot(u64::MAX)
            .events
            .iter()
            .find_map(|event| event.desktop_diagnostic.clone())
            .expect("the failure is recorded")
    }

    #[test]
    fn a_refusal_is_recorded_with_its_command_code_cause_and_log_reference() {
        let failure = refusal_of(wire::sign_in_snapshot(
            outcome(
                json!({"kind":"refused","code":"busy","cause":"sign_in_owner_held","log_ref":"0a1b2c3d4e5f"}),
            ),
            None,
            None,
        ));
        let fact = recorded(&failure, "provider_sign_in_start");
        assert_eq!(fact.command.as_deref(), Some("provider_sign_in_start"));
        assert_eq!(
            fact.logger.as_deref(),
            Some("provider_settings refusal=busy log_ref=0a1b2c3d4e5f")
        );
        assert_eq!(
            fact.reason.as_ref().map(BackendReason::as_str),
            Some("sign_in_owner_held")
        );
        assert!(matches!(fact.level, LogLevel::Warning));
    }

    #[test]
    fn a_host_failure_is_recorded_with_the_check_that_refused_it() {
        let failure = refusal_of(wire::sign_in_snapshot(
            success_of(json!({"event": 7})),
            None,
            None,
        ));
        let fact = recorded(&failure, "provider_sign_in_status");
        assert_eq!(fact.command.as_deref(), Some("provider_sign_in_status"));
        assert_eq!(
            fact.reason.as_ref().map(BackendReason::as_str),
            Some("sign_in_snapshot_unreadable")
        );
        let invalid: CommandFailure = invalid().into();
        assert_eq!(
            recorded(&invalid, "provider_settings_set")
                .reason
                .as_ref()
                .map(BackendReason::as_str),
            Some("provider_settings_invalid_arguments")
        );
    }

    fn success_of(result: Value) -> Outcome {
        Outcome::Success {
            result,
            active_profile: None,
        }
    }
}
