use super::{
    Kind, TerminalState,
    session::{INPUT_LIMIT, Sink, failure},
};
use crate::{app::Commands, shell::channel::Deliveries};
use cadrumo_application::{
    diagnostics::{Diagnostics, Snapshot},
    error::application::{ErrorCode, Result},
};
use serde::Serialize;
use std::sync::Arc;
use tauri::{
    Manager, Runtime, State, Webview,
    http::HeaderMap,
    ipc::{
        Channel, CommandArg, CommandItem, Invoke, InvokeBody, InvokeError, InvokeResponseBody,
        Request,
    },
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

/// The frame sink of one session's channel. A frame the interceptor could
/// not deliver to the webview fails the send, which stops the session.
pub fn frame_sink<R: Runtime>(webview: Webview<R>, frames: Channel) -> Sink {
    Arc::new(move |frame| {
        frames
            .send(InvokeResponseBody::Raw(frame))
            .map_err(|e| failure(ErrorCode::WriteFailed).caused_by(e))?;
        match webview.try_state::<Deliveries>() {
            Some(deliveries) if deliveries.failed(webview.label(), frames.id()) => {
                Err(failure(ErrorCode::WriteFailed))
            }
            _ => Ok(()),
        }
    })
}

const OPEN: &str = "terminal_open";

/// `terminal_open{kind, cols, rows, frames}`. Written against the invoke
/// itself rather than as a command function, because the requesting document
/// must be read when the request arrives: a command function's body, and
/// even its argument parsing, runs later on the async runtime, after a reload
/// could already have replaced that document.
fn terminal_open<R: Runtime>(invoke: Invoke<R>) -> bool {
    let Invoke {
        message,
        resolver,
        acl,
    } = invoke;
    let parsed = (|| -> std::result::Result<_, InvokeError> {
        let argument = |key| CommandItem {
            plugin: None,
            name: OPEN,
            key,
            message: &message,
            acl: &acl,
        };
        let state: State<'_, Arc<TerminalState>> = CommandArg::from_command(argument("state"))?;
        let state = state.inner().clone();
        let document = state.document();
        let kind: Kind = CommandArg::from_command(argument("kind"))?;
        let cols: u16 = CommandArg::from_command(argument("cols"))?;
        let rows: u16 = CommandArg::from_command(argument("rows"))?;
        let frames: Channel = CommandArg::from_command(argument("frames"))?;
        let sink = frame_sink(message.webview(), frames);
        Ok((state, document, kind, cols, rows, sink))
    })();
    match parsed {
        Ok((state, document, kind, cols, rows, sink)) => {
            resolver.respond_async(async move {
                tauri::async_runtime::spawn_blocking(move || {
                    record(
                        &state.launch.diagnostics,
                        state.open(kind, cols, rows, sink, document),
                    )
                })
                .await
                .map_err(|_| failure(ErrorCode::Panic))
                .and_then(|opened| opened)
                .map(|session| Opened { session })
                .map_err(InvokeError::from)
            });
        }
        Err(error) => resolver.invoke_error(error),
    }
    true
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

pub const NAMES: &[&str] = &[
    OPEN,
    "terminal_write",
    "terminal_ack",
    "terminal_resize",
    "terminal_close",
    "diagnostics_snapshot",
];

/// Routes every terminal command, without the shell token check the host
/// composes around it.
pub fn handler<R: Runtime>() -> impl Fn(Invoke<R>) -> bool + Send + Sync + 'static {
    fn typed<R: Runtime>(
        handler: impl Fn(Invoke<R>) -> bool + Send + Sync + 'static,
    ) -> impl Fn(Invoke<R>) -> bool + Send + Sync + 'static {
        handler
    }
    let generated = typed::<R>(tauri::generate_handler![
        terminal_write,
        terminal_ack,
        terminal_resize,
        terminal_close,
        diagnostics_snapshot
    ]);
    move |invoke: Invoke<R>| {
        if invoke.message.command() == OPEN {
            terminal_open(invoke)
        } else {
            generated(invoke)
        }
    }
}

pub fn commands<R: Runtime>() -> Commands<R> {
    Commands::new(NAMES, Box::new(handler()))
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
