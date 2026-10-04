use super::*;
use super::{
    frame::{Decoded, Frame, decode},
    session::size,
};
use cadrumo_application::error::application::{ApplicationError, Operation};
use std::{
    str::FromStr,
    sync::atomic::{AtomicBool, AtomicUsize, Ordering},
};
use tauri::{
    WebviewWindowBuilder,
    ipc::{InvokeResponseBody, JavaScriptChannelId},
    test::{MockRuntime, mock_builder, mock_context, noop_assets},
};

#[test]
fn dimensions_are_bounded() {
    assert!(size(1, 24).is_err());
    assert!(size(80, 1001).is_err());
    assert!(size(2, 2).is_ok());
    assert!(size(1000, 1000).is_ok());
}

/// A registry entry whose settlement outcome the test controls.
struct Scripted {
    live: bool,
    settles: Arc<AtomicBool>,
    attempts: Arc<AtomicUsize>,
}

impl Settle for Scripted {
    fn live(&self) -> bool {
        self.live
    }
    fn request_stop(&mut self) {
        self.live = false;
    }
    fn await_stop(&mut self, _deadline: Instant) -> Result<()> {
        self.attempts.fetch_add(1, Ordering::SeqCst);
        if self.settles.load(Ordering::SeqCst) {
            Ok(())
        } else {
            Err(failure(ErrorCode::CleanupFailed))
        }
    }
}

fn scripted(
    settles: &Arc<AtomicBool>,
    attempts: &Arc<AtomicUsize>,
) -> impl FnOnce() -> Result<Scripted> {
    let (settles, attempts) = (settles.clone(), attempts.clone());
    move || {
        Ok(Scripted {
            live: true,
            settles,
            attempts,
        })
    }
}

#[test]
fn a_live_kind_is_refused_and_an_exited_one_replaced() {
    let settles = Arc::new(AtomicBool::new(true));
    let attempts = Arc::new(AtomicUsize::new(0));
    let mut registry = Registry::default();
    let first = registry
        .open(Kind::Python, scripted(&settles, &attempts))
        .unwrap();
    let refused = registry
        .open(Kind::Python, scripted(&settles, &attempts))
        .unwrap_err();
    assert_eq!(refused.code, ErrorCode::SessionUnavailable);
    // Other kinds are independent.
    let tui = registry
        .open(Kind::Tui, scripted(&settles, &attempts))
        .unwrap();
    assert_ne!(first, tui);
    // The child exits; the next open settles and replaces it.
    registry.session(first).unwrap().live = false;
    let second = registry
        .open(Kind::Python, scripted(&settles, &attempts))
        .unwrap();
    assert!(second > first);
    assert_eq!(attempts.load(Ordering::SeqCst), 1);
    assert_eq!(
        registry.session(first).err().map(|e| e.code),
        Some(ErrorCode::SessionUnavailable),
        "a replaced session must not be addressable"
    );
    registry.close(second).unwrap();
    assert_eq!(
        registry.close(second).unwrap_err().code,
        ErrorCode::SessionUnavailable
    );
    assert_eq!(registry.occupied(), [Kind::Tui]);
}

#[test]
fn closing_all_attempts_every_kind_when_one_fails() {
    let settles = Arc::new(AtomicBool::new(true));
    let stuck = Arc::new(AtomicBool::new(false));
    let attempts = Arc::new(AtomicUsize::new(0));
    let mut registry = Registry::default();
    let console = registry
        .open(Kind::Console, scripted(&stuck, &attempts))
        .unwrap();
    registry
        .open(Kind::Python, scripted(&settles, &attempts))
        .unwrap();
    registry
        .open(Kind::Tui, scripted(&settles, &attempts))
        .unwrap();
    let failures = registry.close_all();
    assert_eq!(
        attempts.load(Ordering::SeqCst),
        3,
        "every kind was attempted"
    );
    assert_eq!(failures.len(), 1);
    assert_eq!(failures[0].code, ErrorCode::CleanupFailed);
    // The failed session stays owned and is retried, not forgotten.
    assert_eq!(registry.occupied(), [Kind::Console]);
    assert!(registry.session(console).is_ok());
    assert_eq!(
        registry
            .open(Kind::Console, scripted(&settles, &attempts))
            .unwrap_err()
            .code,
        ErrorCode::CleanupFailed
    );
    stuck.store(true, Ordering::SeqCst);
    assert!(registry.close_all().is_empty());
    assert!(registry.occupied().is_empty());
}

#[test]
fn a_page_load_settles_every_session_and_later_opens_replace_them() {
    let settles = Arc::new(AtomicBool::new(true));
    let attempts = Arc::new(AtomicUsize::new(0));
    let mut registry = Registry::default();
    let ids: Vec<u64> = Kind::ALL
        .into_iter()
        .map(|kind| registry.open(kind, scripted(&settles, &attempts)).unwrap())
        .collect();
    assert!(registry.close_all().is_empty());
    for id in &ids {
        assert!(registry.session(*id).is_err());
    }
    let reopened = registry
        .open(Kind::Python, scripted(&settles, &attempts))
        .unwrap();
    assert!(ids.iter().all(|id| *id < reopened));
}

#[test]
fn frames_travel_as_raw_channel_bodies_in_send_order() {
    let delivered = Arc::new(Mutex::new(Vec::new()));
    let seen = delivered.clone();
    let app = mock_builder()
        .channel_interceptor(move |_, _, index, body| {
            if let InvokeResponseBody::Raw(bytes) = body {
                seen.lock().unwrap().push((index, bytes.clone()));
            }
            true
        })
        .build(mock_context(noop_assets()))
        .unwrap();
    let window = WebviewWindowBuilder::new(&app, "main", Default::default())
        .build()
        .unwrap();
    let webview: &tauri::Webview<MockRuntime> = window.as_ref();
    let channel = JavaScriptChannelId::from_str("__CHANNEL__:3")
        .unwrap()
        .channel_on::<MockRuntime, InvokeResponseBody>(webview.clone());
    let sink: Sink = Arc::new(move |frame| {
        channel
            .send(InvokeResponseBody::Raw(frame))
            .map_err(|e| failure(ErrorCode::WriteFailed).caused_by(e))
    });
    let error = ApplicationError::new(ErrorCode::ReadFailed, Operation::Terminal);
    for frame in [
        Frame::Started { pid: 9 },
        Frame::Data(b"one"),
        Frame::Data(&[0; 8192]),
        Frame::Failed(&error),
        Frame::Exited { code: Some(0) },
    ] {
        sink(frame.encode().unwrap()).unwrap();
    }
    let delivered = delivered.lock().unwrap();
    assert_eq!(
        delivered
            .iter()
            .map(|(index, _)| *index)
            .collect::<Vec<_>>(),
        [0, 1, 2, 3, 4]
    );
    let decoded: Vec<Decoded> = delivered
        .iter()
        .map(|(_, bytes)| decode(bytes).unwrap())
        .collect();
    assert_eq!(decoded[0], Decoded::Started { pid: 9 });
    assert_eq!(decoded[1], Decoded::Data(b"one".to_vec()));
    assert_eq!(decoded[2], Decoded::Data(vec![0; 8192]));
    assert!(matches!(decoded[3], Decoded::Failed(_)));
    assert_eq!(decoded[4], Decoded::Exited { code: Some(0) });
}

/// The production interceptor consumes a terminal-sized flood: every frame
/// becomes a script for the top document and none waits in the fetch queue.
/// The mock runtime discards the scripts, so this measures the host side only.
#[test]
fn the_channel_interceptor_consumes_a_terminal_flood_without_queueing() {
    use cadrumo_application::diagnostics::Diagnostics;
    use tauri::{
        http::{HeaderMap, HeaderValue},
        ipc::CallbackFn,
        test::{INVOKE_KEY, get_ipc_response},
        webview::InvokeRequest,
    };
    let diagnostics = Arc::new(Diagnostics::default());
    let app = mock_builder()
        .channel_interceptor(crate::shell::channel::interceptor(diagnostics.clone()))
        .build(mock_context(noop_assets()))
        .unwrap();
    let window = WebviewWindowBuilder::new(&app, "main", Default::default())
        .build()
        .unwrap();
    let webview: &tauri::Webview<MockRuntime> = window.as_ref();
    let channel = JavaScriptChannelId::from_str("__CHANNEL__:5")
        .unwrap()
        .channel_on::<MockRuntime, InvokeResponseBody>(webview.clone());
    let payload: Vec<u8> = (0..session::CHUNK).map(|i| (i % 256) as u8).collect();
    let frame = Frame::Data(&payload).encode().unwrap();
    let frames = 1280;
    let began = Instant::now();
    for _ in 0..frames {
        channel
            .send(InvokeResponseBody::Raw(frame.clone()))
            .unwrap();
    }
    let elapsed = began.elapsed();
    let bytes = (frames * session::CHUNK) as f64;
    eprintln!(
        "interceptor host side: {} MiB in {elapsed:.2?} ({:.1} MB/s)",
        frames * session::CHUNK / (1024 * 1024),
        bytes / elapsed.as_secs_f64() / 1e6
    );
    assert!(diagnostics.snapshot(0).events.is_empty(), "a frame failed");
    for id in [0, 1, frames - 1, frames] {
        let mut headers = HeaderMap::new();
        headers.insert(
            "Tauri-Channel-Id",
            HeaderValue::from_str(&id.to_string()).unwrap(),
        );
        let fetched = get_ipc_response(
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
        );
        assert_eq!(
            fetched.err(),
            Some(serde_json::Value::from("data not found")),
            "frame {id} was left in the fetch queue"
        );
    }
}

#[cfg(feature = "live-package-tests")]
mod live;
