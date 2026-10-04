use cadrumo_application::{
    diagnostics::Diagnostics,
    error::application::{ApplicationError, ErrorCode, Operation},
};
use std::sync::Arc;
use tauri::{
    Runtime, Webview,
    ipc::{CallbackFn, InvokeResponseBody},
};

/// Delivers every channel frame by evaluating it in the shell document.
///
/// Tauri otherwise parks large frames in a per-webview queue that any frame of
/// the webview can drain with the ACL-exempt channel fetch command, using
/// sequential ids. Consuming every frame here keeps that queue empty.
pub fn interceptor<R: Runtime>(
    diagnostics: Arc<Diagnostics>,
) -> impl Fn(&Webview<R>, CallbackFn, usize, &InvokeResponseBody) -> bool + Send + Sync + 'static {
    move |webview, callback, index, body| {
        let delivered = script(callback, index, body)
            .map_err(|e| failure().caused_by(e))
            .and_then(|script| webview.eval(script).map_err(|e| failure().caused_by(e)));
        if let Err(error) = delivered {
            diagnostics.failure(error);
        }
        true
    }
}

fn failure() -> ApplicationError {
    ApplicationError::new(ErrorCode::WriteFailed, Operation::Webview)
}

/// The callback invocation Tauri itself evaluates for a directly delivered frame.
fn script(
    callback: CallbackFn,
    index: usize,
    body: &InvokeResponseBody,
) -> serde_json::Result<String> {
    let message = match body {
        InvokeResponseBody::Json(json) => json.clone(),
        InvokeResponseBody::Raw(bytes) => {
            format!("new Uint8Array({}).buffer", serde_json::to_string(bytes)?)
        }
    };
    Ok(format!(
        "window.__TAURI_INTERNALS__.runCallback({}, {{ message: {message}, index: {index} }})",
        callback.0
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::str::FromStr;
    use tauri::{
        WebviewWindowBuilder,
        ipc::{JavaScriptChannelId, Response},
        test::{
            INVOKE_KEY, MockRuntime, get_ipc_response, mock_builder, mock_context, noop_assets,
        },
        webview::InvokeRequest,
    };

    #[test]
    fn frames_become_callback_invocations() {
        assert_eq!(
            script(CallbackFn(7), 3, &InvokeResponseBody::Raw(vec![0, 255])).unwrap(),
            "window.__TAURI_INTERNALS__.runCallback(7, { message: new Uint8Array([0,255]).buffer, index: 3 })"
        );
        assert_eq!(
            script(
                CallbackFn(7),
                4,
                &InvokeResponseBody::Json("{\"a\":1}".into())
            )
            .unwrap(),
            "window.__TAURI_INTERNALS__.runCallback(7, { message: {\"a\":1}, index: 4 })"
        );
    }

    fn fetch_first_queued(builder: tauri::Builder<MockRuntime>) -> Result<(), serde_json::Value> {
        let app = builder.build(mock_context(noop_assets())).unwrap();
        let window = WebviewWindowBuilder::new(&app, "main", Default::default())
            .build()
            .unwrap();
        let webview: &Webview<MockRuntime> = window.as_ref();
        let channel = JavaScriptChannelId::from_str("__CHANNEL__:7")
            .unwrap()
            .channel_on::<MockRuntime, Response>(webview.clone());
        // Larger than every size Tauri delivers directly, so without an
        // interceptor the frame waits in the fetch queue.
        channel.send(Response::new(vec![0x5a; 65536])).unwrap();
        let mut headers = tauri::http::HeaderMap::new();
        headers.insert(
            "Tauri-Channel-Id",
            tauri::http::HeaderValue::from_static("0"),
        );
        get_ipc_response(
            &window,
            InvokeRequest {
                cmd: "plugin:__TAURI_CHANNEL__|fetch".into(),
                callback: CallbackFn(0),
                error: CallbackFn(1),
                url: if cfg!(windows) {
                    "http://tauri.localhost"
                } else {
                    "tauri://localhost"
                }
                .parse()
                .unwrap(),
                body: Default::default(),
                headers,
                invoke_key: INVOKE_KEY.to_owned(),
            },
        )
        .map(|_| ())
    }

    #[test]
    fn intercepted_frames_never_reach_the_fetch_queue() {
        let diagnostics = Arc::new(Diagnostics::default());
        let intercepted = fetch_first_queued(
            mock_builder().channel_interceptor(interceptor(diagnostics.clone())),
        );
        assert_eq!(intercepted, Err(serde_json::Value::from("data not found")));
        assert!(diagnostics.snapshot(0).events.is_empty());
        // Control: the same frame without the interceptor is fetchable.
        assert_eq!(fetch_first_queued(mock_builder()), Ok(()));
    }
}
