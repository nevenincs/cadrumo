use super::*;
use super::{
    frame::{Decoded, Frame, decode},
    session::size,
};
use crate::shell::channel::Deliveries;
use cadrumo_application::{
    child::ChildConfiguration,
    diagnostics::Diagnostics,
    error::application::{ApplicationError, Operation},
    process::status::{ProcessPhase, ProcessRole},
};
use std::{
    path::PathBuf,
    str::FromStr,
    sync::atomic::{AtomicBool, AtomicUsize, Ordering},
    time::Duration,
};
use tauri::{
    Manager, WebviewWindowBuilder,
    ipc::{CallbackFn, InvokeBody, InvokeResponseBody, JavaScriptChannelId},
    test::{INVOKE_KEY, MockRuntime, get_ipc_response, mock_builder, mock_context, noop_assets},
    webview::InvokeRequest,
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
    use tauri::http::{HeaderMap, HeaderValue};
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

/// A reload that lands while an open is starting its session: the session is
/// settled and the open refused, so the new document can open that kind.
#[test]
fn an_open_for_a_replaced_document_is_refused_and_its_session_settled() {
    let settles = Arc::new(AtomicBool::new(true));
    let attempts = Arc::new(AtomicUsize::new(0));
    let registry = Mutex::new(Registry::default());
    let documents = Documents::default();
    let first = documents.current();

    // The current document opens normally.
    let opened = open_for(
        &registry,
        &documents,
        first,
        Kind::Tui,
        scripted(&settles, &attempts),
    )
    .unwrap();
    registry.lock().unwrap().close(opened).unwrap();
    attempts.store(0, Ordering::SeqCst);

    // The reload begins while the session starts, as a page load's count
    // moves while its settlement waits for the registry this open holds.
    let started = AtomicUsize::new(0);
    let refused = open_for(&registry, &documents, first, Kind::Python, || {
        started.fetch_add(1, Ordering::SeqCst);
        documents.replace();
        scripted(&settles, &attempts)()
    })
    .unwrap_err();
    assert_eq!(refused.code, ErrorCode::SessionUnavailable);
    assert_eq!(started.load(Ordering::SeqCst), 1);
    assert_eq!(
        attempts.load(Ordering::SeqCst),
        1,
        "the session was settled"
    );
    assert!(registry.lock().unwrap().occupied().is_empty());

    // A request stamped before the reload starts nothing.
    let never = || -> Result<Scripted> { panic!("a stale request started a session") };
    let stale = open_for(&registry, &documents, first, Kind::Python, never).unwrap_err();
    assert_eq!(stale.code, ErrorCode::SessionUnavailable);

    // The new document opens the kind the stale request would have held.
    let current = documents.current();
    assert_ne!(current, first);
    open_for(
        &registry,
        &documents,
        current,
        Kind::Python,
        scripted(&settles, &attempts),
    )
    .unwrap();
    assert_eq!(registry.lock().unwrap().occupied(), [Kind::Python]);
}

/// A session that misses its settlement bound stays owned, and the open
/// reports the settlement failure rather than the refusal.
#[test]
fn a_stale_session_that_cannot_settle_stays_owned() {
    let stuck = Arc::new(AtomicBool::new(false));
    let attempts = Arc::new(AtomicUsize::new(0));
    let registry = Mutex::new(Registry::default());
    let documents = Documents::default();
    let first = documents.current();
    let error = open_for(&registry, &documents, first, Kind::Tui, || {
        documents.replace();
        scripted(&stuck, &attempts)()
    })
    .unwrap_err();
    assert_eq!(error.code, ErrorCode::CleanupFailed);
    assert_eq!(registry.lock().unwrap().occupied(), [Kind::Tui]);
    stuck.store(true, Ordering::SeqCst);
    assert!(registry.lock().unwrap().close_all().is_empty());
}

/// A launch whose sessions cannot start: every path is absolute and the
/// interpreter does not exist, so an open that is wrongly admitted fails to
/// spawn rather than starting a process.
fn unit_launch() -> crate::environment::Launch {
    let directory = std::env::temp_dir();
    let executable = directory.join("cadrumo-unit-absent-interpreter.exe");
    assert!(!executable.exists());
    crate::environment::Launch {
        child: ChildConfiguration::new(executable, directory.clone(), Default::default()).unwrap(),
        working_directory: directory.clone(),
        webview: directory.clone(),
        diagnostics: Arc::new(Diagnostics::default()),
        home: directory.clone(),
        package_root: directory.clone(),
        docs_root: directory.clone(),
        docs_manifest: directory.join("manifest.json"),
        log_file: directory.join("cadrumo.log"),
        manager_log_file: directory.join("cadrumo-manager.log"),
        log_format: String::new(),
        output_language: "en".into(),
    }
}

fn open_request(frames: &str) -> InvokeRequest {
    InvokeRequest {
        cmd: "terminal_open".into(),
        callback: CallbackFn(0),
        error: CallbackFn(1),
        url: if cfg!(windows) {
            "http://tauri.localhost"
        } else {
            "tauri://localhost"
        }
        .parse()
        .unwrap(),
        body: InvokeBody::Json(
            serde_json::json!({"kind": "tui", "cols": 80, "rows": 24, "frames": frames}),
        ),
        headers: Default::default(),
        invoke_key: INVOKE_KEY.to_owned(),
    }
}

/// The real `terminal_open` handler reads the requesting document when the
/// request arrives. Its open is held at the registry until the reload has
/// begun, and is then refused without starting anything.
#[test]
fn terminal_open_answers_for_the_document_that_sent_it() {
    let state = Arc::new(TerminalState::new(unit_launch()));
    let (dispatched_out, dispatched) = std::sync::mpsc::channel();
    let dispatched_out = Mutex::new(dispatched_out);
    let handler = ipc::handler();
    let app = mock_builder()
        .manage(state.clone())
        .invoke_handler(move |invoke| {
            let handled = handler(invoke);
            dispatched_out.lock().unwrap().send(()).unwrap();
            handled
        })
        .build(mock_context(noop_assets()))
        .unwrap();
    let window = WebviewWindowBuilder::new(&app, "main", Default::default())
        .build()
        .unwrap();
    let held = state.registry.lock().unwrap();
    let reply = std::thread::scope(|scope| {
        let request = scope.spawn(|| get_ipc_response(&window, open_request("__CHANNEL__:21")));
        dispatched.recv().unwrap();
        state.documents.replace();
        drop(held);
        request.join().unwrap()
    });
    let refused = reply.unwrap_err();
    assert_eq!(refused["code"], "session_unavailable", "{refused}");
    assert!(state.registry.lock().unwrap().occupied().is_empty());
    // Malformed arguments are refused at dispatch.
    let mut malformed = open_request("__CHANNEL__:22");
    malformed.body = InvokeBody::Json(serde_json::json!({"kind": "tui"}));
    assert!(get_ipc_response(&window, malformed).is_err());
    assert!(get_ipc_response(&window, open_request("not a channel")).is_err());
}

/// Only the start of a new top-frame document replaces the current one.
#[test]
fn a_page_load_start_replaces_the_document() {
    let state = TerminalState::new(unit_launch());
    let first = state.document();
    state.page_load(tauri::webview::PageLoadEvent::Finished);
    assert_eq!(state.document(), first);
    state.page_load(tauri::webview::PageLoadEvent::Started);
    let second = state.document();
    assert_ne!(second, first);
    state.page_load(tauri::webview::PageLoadEvent::Started);
    assert_ne!(state.document(), second);
}

/// Every terminal command name reaches a handler: the composed names and the
/// routed commands agree.
#[test]
fn every_terminal_command_name_is_routed() {
    let app = mock_builder()
        .invoke_handler(ipc::handler())
        .build(mock_context(noop_assets()))
        .unwrap();
    let window = WebviewWindowBuilder::new(&app, "main", Default::default())
        .build()
        .unwrap();
    let call = |name: &str| {
        let mut request = open_request("__CHANNEL__:1");
        request.cmd = name.into();
        get_ipc_response(&window, request).unwrap_err().to_string()
    };
    for name in ipc::NAMES {
        let reply = call(name);
        assert!(!reply.contains("not found"), "{name}: {reply}");
    }
    let unknown = call("terminal_unknown");
    assert!(unknown.contains("not found"), "{unknown}");
}

/// A frame the interceptor failed to deliver fails the sink once, through the
/// managed delivery record the interceptor writes.
#[test]
fn the_frame_sink_fails_when_its_channel_was_not_delivered() {
    let app = mock_builder()
        .manage(Deliveries::default())
        .build(mock_context(noop_assets()))
        .unwrap();
    let window = WebviewWindowBuilder::new(&app, "main", Default::default())
        .build()
        .unwrap();
    let webview: &tauri::Webview<MockRuntime> = window.as_ref();
    let frames = JavaScriptChannelId::from_str("__CHANNEL__:31")
        .unwrap()
        .channel_on::<MockRuntime, InvokeResponseBody>(webview.clone());
    let sink = ipc::frame_sink(webview.clone(), frames);
    sink(vec![0, b'a']).unwrap();
    // Failures of another webview or another channel do not concern it.
    app.state::<Deliveries>().record("other", 31);
    app.state::<Deliveries>().record("main", 32);
    sink(vec![0, b'b']).unwrap();
    app.state::<Deliveries>().record("main", 31);
    assert_eq!(
        sink(vec![0, b'c']).unwrap_err().code,
        ErrorCode::WriteFailed
    );
}

/// A system program that keeps writing output until it is stopped.
fn chatty_program() -> Program {
    let environment = std::env::vars_os().collect();
    let directory = std::env::temp_dir();
    let (executable, arguments): (PathBuf, &[&str]) = if cfg!(windows) {
        let root = std::env::var_os("SystemRoot").expect("SystemRoot");
        (
            PathBuf::from(root).join("System32").join("cmd.exe"),
            &["/d", "/c", "ping", "-n", "60", "127.0.0.1"],
        )
    } else {
        (
            PathBuf::from("/bin/sh"),
            &["-c", "while :; do echo output; sleep 1; done"],
        )
    };
    Program {
        executable,
        arguments: arguments.iter().map(OsString::from).collect(),
        directory,
        environment,
        role: ProcessRole::Console,
    }
}

#[test]
fn only_the_dedicated_tui_receives_the_desktop_palette_identity() {
    for role in [ProcessRole::Tui, ProcessRole::Console, ProcessRole::Repl] {
        let mut program = chatty_program();
        program.role = role;
        program.environment.insert(
            "TERM_PROGRAM".into(),
            if role == ProcessRole::Tui {
                "OtherTerminal"
            } else {
                "cadrumo"
            }
            .into(),
        );
        let arguments = if cfg!(windows) {
            vec!["/d", "/c", "set TERM_PROGRAM"]
        } else {
            vec!["-c", "printf '%s' \"$TERM_PROGRAM\""]
        };
        program.arguments = arguments.into_iter().map(OsString::from).collect();
        let captured = Arc::new(Mutex::new(Vec::new()));
        let output = captured.clone();
        let sink: Sink = Arc::new(move |frame| {
            if frame.first() == Some(&0) {
                output.lock().unwrap().extend_from_slice(&frame[1..]);
            }
            Ok(())
        });
        let mut session =
            Session::start(program, 80, 24, sink, Arc::new(Diagnostics::default())).unwrap();
        let began = Instant::now();
        let mut answered = 0;
        while session.live() && began.elapsed() < Duration::from_secs(10) {
            let bytes = captured.lock().unwrap();
            let queries = bytes
                .windows(4)
                .filter(|window| *window == b"\x1b[6n")
                .count();
            session.acknowledge(bytes.len() as u64).unwrap();
            drop(bytes);
            while answered < queries {
                session.write(b"\x1b[1;1R").unwrap();
                answered += 1;
            }
            std::thread::sleep(Duration::from_millis(20));
        }
        assert!(!session.live(), "terminal identity probe did not exit");
        session.stop().unwrap();
        let bytes = captured.lock().unwrap();
        let text = String::from_utf8_lossy(&bytes);
        if role == ProcessRole::Tui {
            assert!(!text.contains("cadrumo-shell"), "{text:?}");
        }
        assert!(
            text.contains(if role == ProcessRole::Tui {
                "cadrumo"
            } else {
                "cadrumo-shell"
            }),
            "{text:?}"
        );
    }
}

/// When frames stop reaching the webview the session stops itself: the child
/// is terminated and every worker joined without anyone closing it.
#[test]
fn a_session_whose_frames_cannot_be_delivered_stops_itself() {
    let diagnostics = Arc::new(Diagnostics::default());
    let attempts = Arc::new(AtomicUsize::new(0));
    let counted = attempts.clone();
    let sink: Sink = Arc::new(move |_| {
        counted.fetch_add(1, Ordering::SeqCst);
        Err(failure(ErrorCode::WriteFailed))
    });
    let mut session = Session::start(chatty_program(), 80, 24, sink, diagnostics.clone()).unwrap();
    let began = Instant::now();
    while session.live() && began.elapsed() < Duration::from_secs(10) {
        std::thread::sleep(Duration::from_millis(20));
    }
    assert!(
        !session.live(),
        "the session kept running without a receiver"
    );
    session.stop().unwrap();
    let snapshot = diagnostics.snapshot(0);
    assert_eq!(snapshot.processes.len(), 1);
    assert_eq!(snapshot.processes[0].phase, ProcessPhase::Terminated);
    let process = &snapshot.processes[0];
    assert!(snapshot.events.iter().any(|event| {
        event.process == Some(process.id)
            && event
                .status
                .as_ref()
                .is_some_and(|status| status.pid == process.pid)
            && event
                .failure
                .as_ref()
                .is_some_and(|error| error.code == ErrorCode::WriteFailed)
    }));
    assert!(snapshot.output.is_empty());
    // The refused started frame ends delivery; later output is discarded.
    assert_eq!(attempts.load(Ordering::SeqCst), 1);
}

#[test]
fn a_failed_terminal_launch_records_its_role_without_private_launch_data() {
    let directory = std::env::temp_dir();
    let diagnostics = Arc::new(Diagnostics::default());
    let program = Program {
        executable: directory.join(format!(
            "synthetic-private-executable-{}",
            std::process::id()
        )),
        arguments: vec!["synthetic-private-argument".into()],
        directory,
        environment: std::collections::BTreeMap::from([(
            "SYNTHETIC_SECRET".into(),
            "synthetic-private-credential".into(),
        )]),
        role: ProcessRole::Repl,
    };
    let error = Session::start(program, 80, 24, Arc::new(|_| Ok(())), diagnostics.clone())
        .err()
        .unwrap();
    assert_eq!(error.code, ErrorCode::SpawnFailed);
    let snapshot = diagnostics.snapshot(0);
    assert!(snapshot.processes.is_empty());
    assert_eq!(snapshot.events.len(), 1);
    assert_eq!(snapshot.events[0].role, Some(ProcessRole::Repl));
    let records = serde_json::to_string(&snapshot.events).unwrap();
    assert!(!records.contains("synthetic-private"));
    assert!(!records.contains("SYNTHETIC_SECRET"));
}

#[cfg(feature = "live-package-tests")]
mod live;
