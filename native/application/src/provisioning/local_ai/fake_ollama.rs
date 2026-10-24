//! A fake local AI program for the tests: the part of the program's HTTP API the engine
//! speaks, answered from in-memory state on a real loopback socket.
//!
//! It runs in the test process, or as the engine's child: the test binary itself started
//! in the [`serve_helper`] mode, where it binds `OLLAMA_HOST`, announces itself on
//! standard error as the program does, and exits once its standard input closes, so it
//! cannot outlive the engine that started it.

use serde_json::{Value, json};
use std::{
    collections::BTreeMap,
    io::{BufRead, BufReader, Read, Write},
    net::{TcpListener, TcpStream},
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
};

/// The environment variable that selects the helper mode in a child test binary.
pub(crate) const HELPER_MODE: &str = "CADRUMO_FAKE_OLLAMA";
/// The version the helper reports.
pub(crate) const HELPER_VERSION: &str = "CADRUMO_FAKE_OLLAMA_VERSION";
/// The arguments that run only the helper in a child test binary.
pub(crate) const HELPER_ARGUMENTS: [&str; 4] = [
    "--exact",
    "provisioning::local_ai::fake_ollama::serve_helper",
    "--nocapture",
    "--test-threads=1",
];

/// What the fake knows and has been asked.
#[derive(Default)]
pub(crate) struct FakeState {
    pub version: String,
    /// Loaded model names.
    pub loaded: Vec<String>,
    /// Every request line, in order.
    pub requests: Vec<String>,
    /// The environment the program was started with, as the helper saw it.
    pub environment: BTreeMap<String, String>,
    /// Where the helper also appends every request line, for a test to read after the
    /// helper has ended.
    pub log: Option<std::path::PathBuf>,
}

pub(crate) type Shared = Arc<Mutex<FakeState>>;

struct Request {
    line: String,
    body: Vec<u8>,
}

fn read_request(stream: &TcpStream) -> std::io::Result<Request> {
    let mut reader = BufReader::new(stream);
    let mut line = String::new();
    reader.read_line(&mut line)?;
    let mut length = 0usize;
    loop {
        let mut header = String::new();
        if reader.read_line(&mut header)? == 0 || header.trim().is_empty() {
            break;
        }
        if let Some((name, value)) = header.split_once(':')
            && name.trim().eq_ignore_ascii_case("content-length")
        {
            length = value.trim().parse().unwrap_or(0);
        }
    }
    let mut body = vec![0; length];
    reader.read_exact(&mut body)?;
    Ok(Request {
        line: line.trim_end().to_owned(),
        body,
    })
}

pub(crate) fn respond(stream: &mut TcpStream, status: &str, body: &Value) {
    let body = body.to_string();
    let _ = write!(
        stream,
        "HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let _ = stream.flush();
}

fn answer(state: &Shared, mut stream: TcpStream) {
    let Ok(request) = read_request(&stream) else {
        return;
    };
    let mut guard = state.lock().unwrap();
    guard.requests.push(request.line.clone());
    if let Some(log) = &guard.log {
        let mut file = std::fs::File::options()
            .create(true)
            .append(true)
            .open(log)
            .unwrap();
        writeln!(
            file,
            "{} {}",
            request.line,
            String::from_utf8_lossy(&request.body)
        )
        .unwrap();
    }
    let body: Value = serde_json::from_slice(&request.body).unwrap_or(Value::Null);
    let target = request
        .line
        .split(' ')
        .nth(1)
        .unwrap_or_default()
        .to_owned();
    match (
        request.line.split(' ').next().unwrap_or_default(),
        target.as_str(),
    ) {
        ("GET", "/api/version") => {
            let version = guard.version.clone();
            drop(guard);
            respond(&mut stream, "200 OK", &json!({ "version": version }));
        }
        ("GET", "/api/ps") => {
            let models: Vec<Value> = guard
                .loaded
                .iter()
                .map(|name| json!({ "name": name, "model": name }))
                .collect();
            drop(guard);
            respond(&mut stream, "200 OK", &json!({ "models": models }));
        }
        ("GET", "/fake/environment") => {
            let environment = json!(guard.environment);
            drop(guard);
            respond(&mut stream, "200 OK", &environment);
        }
        ("POST", "/api/generate") => {
            let model = body["model"].as_str().unwrap_or_default().to_owned();
            if body["keep_alive"] == json!(0) {
                guard.loaded.retain(|name| *name != model);
                drop(guard);
                respond(
                    &mut stream,
                    "200 OK",
                    &json!({ "model": model, "response": "", "done": true, "done_reason": "unload" }),
                );
            } else {
                if !guard.loaded.contains(&model) {
                    guard.loaded.push(model.clone());
                }
                drop(guard);
                respond(
                    &mut stream,
                    "200 OK",
                    &json!({ "model": model, "response": "ok", "done": true }),
                );
            }
        }
        _ => {
            drop(guard);
            respond(
                &mut stream,
                "404 Not Found",
                &json!({ "error": "not found" }),
            );
        }
    }
}

/// Answers each connection on its own thread, joining them all before returning.
fn accept_until(listener: &TcpListener, state: &Shared, stop: &AtomicBool) {
    let mut workers = Vec::new();
    for stream in listener.incoming() {
        if stop.load(Ordering::Acquire) {
            break;
        }
        let Ok(stream) = stream else { continue };
        let state = state.clone();
        workers.push(std::thread::spawn(move || answer(&state, stream)));
    }
    for worker in workers {
        let _ = worker.join();
    }
}

/// The child-process mode: the test binary stands in for the program's `serve`.
#[test]
fn serve_helper() {
    if std::env::var_os(HELPER_MODE).is_none() {
        return;
    }
    let host = std::env::var("OLLAMA_HOST").unwrap();
    let listener = TcpListener::bind(&host).unwrap();
    let state: Shared = Arc::new(Mutex::new(FakeState {
        version: std::env::var(HELPER_VERSION).unwrap(),
        environment: std::env::vars().collect(),
        log: Some(
            std::path::Path::new(&std::env::var("OLLAMA_HOME").unwrap()).join("requests.log"),
        ),
        ..FakeState::default()
    }));
    // The program's own announcement, which the engine waits for.
    eprintln!(
        "time=2026-01-01T00:00:00.000Z level=INFO source=routes.go:1 msg=\"Listening on {} (version {})\"",
        listener.local_addr().unwrap(),
        state.lock().unwrap().version
    );
    std::thread::spawn(|| {
        let mut sink = Vec::new();
        let _ = std::io::stdin().read_to_end(&mut sink);
        std::process::exit(0);
    });
    accept_until(&listener, &state, &AtomicBool::new(false));
}
