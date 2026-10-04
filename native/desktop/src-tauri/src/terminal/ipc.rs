use super::{
    Kind, TerminalState,
    session::{INPUT_LIMIT, Sink, failure},
};
use crate::app::Commands;
use cadrumo_application::{
    diagnostics::{Diagnostics, Snapshot},
    error::application::{ErrorCode, Result},
};
use serde::Serialize;
use std::sync::Arc;
use tauri::{
    Runtime, State,
    http::HeaderMap,
    ipc::{Channel, InvokeBody, InvokeResponseBody, Request},
};

/// The session a raw-body `terminal_write` addresses.
pub const SESSION_HEADER: &str = "x-cadrumo-session";

#[derive(Serialize)]
pub struct Opened {
    session: u64,
}

#[derive(Serialize)]
pub struct Settled {}

fn record<T>(diagnostics: &Diagnostics, outcome: Result<T>) -> Result<T> {
    if let Err(error) = &outcome
        && error.code != ErrorCode::QueueFull
    {
        diagnostics.failure(error.clone());
    }
    outcome
}

/// Runs registry work off the async executor: settlement can block for its
/// full bound while it holds the registry.
async fn blocking<T: Send + 'static>(
    state: &State<'_, Arc<TerminalState>>,
    work: impl FnOnce(&TerminalState) -> Result<T> + Send + 'static,
) -> Result<T> {
    let state = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || record(&state.launch.diagnostics, work(&state)))
        .await
        .map_err(|_| failure(ErrorCode::Panic))?
}

/// The session and bytes of a write: a raw body, or the JSON byte array the
/// postMessage transport makes of one, both addressed by header.
pub fn written(body: &InvokeBody, headers: &HeaderMap) -> Result<(u64, Vec<u8>)> {
    let invalid = || failure(ErrorCode::InvalidArguments);
    let session = headers
        .get(SESSION_HEADER)
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.parse().ok())
        .ok_or_else(invalid)?;
    let bytes = match body {
        InvokeBody::Raw(bytes) if bytes.len() <= INPUT_LIMIT => bytes.clone(),
        InvokeBody::Json(serde_json::Value::Array(items)) if items.len() <= INPUT_LIMIT => items
            .iter()
            .map(|item| item.as_u64().and_then(|byte| u8::try_from(byte).ok()))
            .collect::<Option<Vec<u8>>>()
            .ok_or_else(invalid)?,
        _ => return Err(invalid()),
    };
    Ok((session, bytes))
}

#[tauri::command]
pub async fn terminal_open(
    state: State<'_, Arc<TerminalState>>,
    kind: Kind,
    cols: u16,
    rows: u16,
    frames: Channel,
) -> Result<Opened> {
    let sink: Sink = Arc::new(move |frame| {
        frames
            .send(InvokeResponseBody::Raw(frame))
            .map_err(|e| failure(ErrorCode::WriteFailed).caused_by(e))
    });
    blocking(&state, move |state| {
        state
            .open(kind, cols, rows, sink)
            .map(|session| Opened { session })
    })
    .await
}

#[tauri::command]
pub async fn terminal_write(
    state: State<'_, Arc<TerminalState>>,
    request: Request<'_>,
) -> Result<()> {
    let (session, bytes) = record(
        &state.launch.diagnostics,
        written(request.body(), request.headers()),
    )?;
    blocking(&state, move |state| {
        state.with_session(session, |terminal| terminal.write(&bytes))
    })
    .await
}

#[tauri::command]
pub async fn terminal_ack(
    state: State<'_, Arc<TerminalState>>,
    session: u64,
    offset: u64,
) -> Result<()> {
    blocking(&state, move |state| {
        state.with_session(session, |terminal| terminal.acknowledge(offset))
    })
    .await
}

#[tauri::command]
pub async fn terminal_resize(
    state: State<'_, Arc<TerminalState>>,
    session: u64,
    cols: u16,
    rows: u16,
) -> Result<()> {
    blocking(&state, move |state| {
        state.with_session(session, |terminal| terminal.resize(cols, rows))
    })
    .await
}

#[tauri::command]
pub async fn terminal_close(state: State<'_, Arc<TerminalState>>, session: u64) -> Result<Settled> {
    blocking(&state, move |state| {
        state.close(session).map(|()| Settled {})
    })
    .await
}

#[tauri::command]
pub fn diagnostics_snapshot(state: State<'_, Arc<TerminalState>>, after: u64) -> Snapshot {
    state.launch.diagnostics.snapshot(after)
}

pub fn commands<R: Runtime>() -> Commands<R> {
    crate::app::commands![
        terminal_open,
        terminal_write,
        terminal_ack,
        terminal_resize,
        terminal_close,
        diagnostics_snapshot
    ]
}

#[cfg(test)]
mod tests {
    use super::*;
    use tauri::http::HeaderValue;

    fn headers(session: &str) -> HeaderMap {
        let mut headers = HeaderMap::new();
        headers.insert(SESSION_HEADER, HeaderValue::from_str(session).unwrap());
        headers
    }

    #[test]
    fn raw_and_json_bodies_carry_the_same_bytes_and_limit() {
        let bytes: Vec<u8> = (0..=255).cycle().take(INPUT_LIMIT).collect();
        let raw = InvokeBody::Raw(bytes.clone());
        let json = InvokeBody::Json(serde_json::to_value(&bytes).unwrap());
        assert_eq!(written(&raw, &headers("7")).unwrap(), (7, bytes.clone()));
        assert_eq!(written(&json, &headers("7")).unwrap(), (7, bytes.clone()));
        let mut over = bytes;
        over.push(0);
        for body in [
            InvokeBody::Raw(over.clone()),
            InvokeBody::Json(serde_json::to_value(&over).unwrap()),
        ] {
            let error = written(&body, &headers("7")).unwrap_err();
            assert_eq!(error.code, ErrorCode::InvalidArguments);
        }
        assert_eq!(
            written(&InvokeBody::Raw(Vec::new()), &headers("1")).unwrap(),
            (1, Vec::new())
        );
    }

    #[test]
    fn malformed_writes_are_refused() {
        for (body, session) in [
            (InvokeBody::Raw(b"a".to_vec()), None),
            (InvokeBody::Raw(b"a".to_vec()), Some("-1")),
            (InvokeBody::Raw(b"a".to_vec()), Some("x")),
            (InvokeBody::Json(serde_json::json!([256])), Some("1")),
            (InvokeBody::Json(serde_json::json!([-1])), Some("1")),
            (InvokeBody::Json(serde_json::json!([1.5])), Some("1")),
            (InvokeBody::Json(serde_json::json!(["a"])), Some("1")),
            (
                InvokeBody::Json(serde_json::json!({"data": [1]})),
                Some("1"),
            ),
        ] {
            let headers = session.map(headers).unwrap_or_default();
            let error = written(&body, &headers).unwrap_err();
            assert_eq!(error.code, ErrorCode::InvalidArguments);
        }
    }
}
