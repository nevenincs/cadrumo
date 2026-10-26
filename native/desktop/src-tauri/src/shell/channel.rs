use cadrumo_application::{
    diagnostics::Diagnostics,
    error::application::{ApplicationError, ErrorCode, Operation},
};
use std::{
    collections::BTreeSet,
    sync::{Arc, Mutex},
};
use tauri::{
    Manager, Runtime, Webview,
    ipc::{CallbackFn, InvokeResponseBody},
};

/// Channels whose frames could not be delivered to their webview.
///
/// The interceptor consumes every frame, so a channel's `send` succeeds even
/// when evaluating the frame in the webview failed. A failure is recorded here
/// under the webview label and the channel's callback id, which is
/// `Channel::id()` on the Rust side. The shell plugin manages one instance;
/// any thread can query it.
#[derive(Default)]
pub struct Deliveries {
    failed: Mutex<BTreeSet<(String, u32)>>,
}

impl Deliveries {
    fn failed_set(&self) -> std::sync::MutexGuard<'_, BTreeSet<(String, u32)>> {
        self.failed.lock().unwrap_or_else(|e| e.into_inner())
    }

    pub(crate) fn record(&self, webview: &str, callback: u32) {
        self.failed_set().insert((webview.to_owned(), callback));
    }

    /// Whether a frame for channel `callback` of webview `webview` failed to
    /// be delivered since the previous query for that channel. The query
    /// clears the mark, so a channel's owner asks once per check.
    pub fn failed(&self, webview: &str, callback: u32) -> bool {
        self.failed_set().remove(&(webview.to_owned(), callback))
    }
}

/// Delivers every channel frame by evaluating it in the shell document.
///
/// Tauri otherwise parks large frames in a per-webview queue that any frame of
/// the webview can drain with the ACL-exempt channel fetch command, using
/// sequential ids. Consuming every frame here keeps that queue empty, even
/// when evaluation fails: such a frame is reported to diagnostics and marked
/// in the managed [`Deliveries`] rather than parked for a fetch.
pub fn interceptor<R: Runtime>(
    diagnostics: Arc<Diagnostics>,
) -> impl Fn(&Webview<R>, CallbackFn, usize, &InvokeResponseBody) -> bool + Send + Sync + 'static {
    move |webview, callback, index, body| {
        deliver(
            webview.try_state::<Deliveries>().as_deref(),
            &diagnostics,
            webview.label(),
            callback,
            index,
            body,
            |script| webview.eval(script),
        );
        true
    }
}

/// Evaluates one frame's script and records a failure against its channel.
fn deliver<E: std::error::Error + Send + Sync + 'static>(
    deliveries: Option<&Deliveries>,
    diagnostics: &Diagnostics,
    webview: &str,
    callback: CallbackFn,
    index: usize,
    body: &InvokeResponseBody,
    evaluate: impl FnOnce(String) -> Result<(), E>,
) {
    let delivered = script(callback, index, body)
        .map_err(|e| failure().caused_by(e))
        .and_then(|script| evaluate(script).map_err(|e| failure().caused_by(e)));
    if let Err(error) = delivered {
        if let Some(deliveries) = deliveries {
            deliveries.record(webview, callback.0);
        }
        diagnostics.failure(error);
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

    #[test]
    fn a_failed_evaluation_marks_its_channel_once_and_is_reported() {
        let diagnostics = Diagnostics::default();
        let deliveries = Deliveries::default();
        let body = InvokeResponseBody::Raw(vec![1]);
        let mut evaluated = None;
        deliver(
            Some(&deliveries),
            &diagnostics,
            "main",
            CallbackFn(9),
            2,
            &body,
            |script| {
                evaluated = Some(script);
                Err(std::io::Error::other("the webview is gone"))
            },
        );
        assert_eq!(
            evaluated.as_deref(),
            Some(script(CallbackFn(9), 2, &body).unwrap().as_str())
        );
        assert_eq!(diagnostics.snapshot(0).events.len(), 1);
        assert!(!deliveries.failed("main", 8));
        assert!(!deliveries.failed("other", 9));
        assert!(deliveries.failed("main", 9));
        assert!(!deliveries.failed("main", 9), "the query clears the mark");
        // A delivered frame marks nothing and reports nothing.
        deliver(
            Some(&deliveries),
            &diagnostics,
            "main",
            CallbackFn(9),
            3,
            &body,
            |_| Ok::<(), std::io::Error>(()),
        );
        assert!(!deliveries.failed("main", 9));
        assert_eq!(diagnostics.snapshot(0).events.len(), 1);
        // Without a managed record the failure still reaches diagnostics.
        deliver(None, &diagnostics, "main", CallbackFn(9), 4, &body, |_| {
            Err(std::io::Error::other("the webview is gone"))
        });
        assert_eq!(diagnostics.snapshot(0).events.len(), 2);
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
