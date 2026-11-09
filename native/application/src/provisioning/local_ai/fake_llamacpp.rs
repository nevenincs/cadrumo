//! A fake llama-server in router mode for the tests: the part of the program's HTTP API
//! the engine speaks, answered from in-memory state on a real loopback socket.
//!
//! It runs in the test process, or as the engine's child: the test binary itself started
//! in the [`serve_helper`] mode, where it binds the `--host` and `--port` of its command
//! line as the program does, announces itself on standard error as the program does, and
//! exits once its standard input closes, so it cannot outlive the engine that started it.
//!
//! The routes are `GET /health`, `GET /props`, `GET /models`, `POST /models/load`,
//! `POST /models/unload` and `POST /v1/completions`, which generates one token with a
//! loaded model, plus `GET /fake/environment`, `GET /fake/arguments` and
//! `POST /fake/exit` for a test to look into, or end, the helper child. A test scripts
//! the rest through [`FakeState`]: readiness, the models and their statuses, a scripted
//! answer or a hang-up for any path.
//!
//! It answers a load as the router does: `200` at once, whatever then becomes of the model,
//! and `400` that the model is already running when it is held. A load that fails shows only
//! in the model's entry in the list, as `unloaded` with `failed` and an exit code, never in
//! an answer body. A load that another caller's load evicts shows there as `unloaded` with
//! no `failed` flag.

use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    io::{BufRead, BufReader, Read, Write},
    net::{SocketAddr, TcpListener, TcpStream},
    path::PathBuf,
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    thread::JoinHandle,
};

/// The environment variable that selects the helper mode in a child test binary.
pub(crate) const HELPER_MODE: &str = "CADRUMO_FAKE_LLAMACPP";
/// A file the stand-in waits for before it announces that it listens, so a test can
/// observe a start that has begun and not finished.
pub(crate) const HELPER_GATE: &str = "CADRUMO_FAKE_LLAMACPP_GATE";
/// A file whose absence makes `/health` answer that a model is loading, so a test can
/// observe a server that listens and is not ready.
pub(crate) const HELPER_READY_GATE: &str = "CADRUMO_FAKE_LLAMACPP_READY_GATE";
/// The build the helper reports in `/props`.
pub(crate) const HELPER_BUILD: &str = "CADRUMO_FAKE_LLAMACPP_BUILD";
/// The model ids the helper lists, comma separated, each unloaded at first.
pub(crate) const HELPER_MODELS: &str = "CADRUMO_FAKE_LLAMACPP_MODELS";
/// A file the helper appends every request line and body to, for a test to read after
/// the helper has ended.
pub(crate) const HELPER_LOG: &str = "CADRUMO_FAKE_LLAMACPP_LOG";
/// The line the helper announces itself with, `{address}` standing for where it listens.
/// An empty value announces nothing, as a server that is silent; unset is the program's
/// own line.
pub(crate) const HELPER_BANNER: &str = "CADRUMO_FAKE_LLAMACPP_BANNER";
/// A file the helper appends a line to each time it starts, shared with the fake Ollama,
/// so a test counts the servers of each kind that were ever started.
pub(crate) const HELPER_LAUNCHES: &str = "CADRUMO_FAKE_LLAMACPP_LAUNCHES";
/// The line the helper appends to [`HELPER_LAUNCHES`].
pub(crate) const LAUNCHED: &str = "llama-server";
/// The arguments that run only the helper in a child test binary; the program's own
/// arguments follow them after `--`, where the test harness takes them for name filters
/// that match nothing.
pub(crate) const HELPER_ARGUMENTS: [&str; 4] = [
    "--exact",
    "provisioning::local_ai::fake_llamacpp::serve_helper",
    "--nocapture",
    "--test-threads=1",
];

/// The line the program prints once it listens; `{address}` is `host:port`.
const BANNER: &str = "main: server is listening on http://{address} - starting the main loop";

/// Where the router holds a model.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum ModelStatus {
    Loaded,
    Unloaded,
    Loading,
    /// A load that was taken and then failed: listed as `unloaded`, with `failed` set.
    Failed,
}

impl ModelStatus {
    fn as_str(self) -> &'static str {
        match self {
            Self::Loaded => "loaded",
            Self::Unloaded | Self::Failed => "unloaded",
            Self::Loading => "loading",
        }
    }
}

/// A scripted answer: the status line text, such as `500 Internal Server Error`, and the
/// JSON body.
#[derive(Clone)]
pub(crate) struct Scripted {
    pub status: String,
    pub body: Value,
}

/// What the fake knows and has been asked.
#[derive(Default)]
pub(crate) struct FakeState {
    /// The build the program reports in `/props`.
    pub build_info: String,
    /// Whether `/health` answers ready.
    pub ready: bool,
    /// A file whose absence also makes `/health` answer not ready: only in the helper.
    pub ready_file: Option<PathBuf>,
    /// The router's models by id and status.
    pub models: BTreeMap<String, ModelStatus>,
    /// Whether a load leaves its model `loading` instead of `loaded`, as a load that has
    /// begun and not finished.
    pub load_leaves_loading: bool,
    /// Whether a load is taken, answered `200`, and then fails: the model's entry reads
    /// unloaded, failed, with exit code 1, as the router lists a model whose process ended.
    pub load_fails: bool,
    /// Whether a load is taken, answered `200`, and then evicted by another caller's load
    /// into the router's one place: the model's entry reads unloaded with no `failed` flag.
    pub load_evicted: bool,
    /// Every request line, in order.
    pub requests: Vec<String>,
    /// Every request body, in order, `null` when it was none or not JSON.
    pub bodies: Vec<Value>,
    /// The environment the program was started with, as the helper saw it.
    pub environment: BTreeMap<String, String>,
    /// The arguments the program was started with, as the helper saw them.
    pub arguments: Vec<String>,
    /// Where the helper also appends every request line, for a test to read after the
    /// helper has ended.
    pub log: Option<PathBuf>,
    /// What a path answers with instead of its route, by path, until removed.
    pub failures: BTreeMap<String, Scripted>,
    /// The paths whose requests are closed without an answer, as a server that ended or
    /// dropped the request does.
    pub hang_ups: BTreeSet<String>,
    /// Whether `POST /fake/exit` ends the process, as a crash would: only in the helper.
    pub exits_on_request: bool,
    /// Runs as each load is taken, before it is answered, as whatever happens to the
    /// router while a load is on its way.
    pub on_load: Option<Box<dyn FnMut() + Send>>,
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

fn respond(stream: &mut TcpStream, status: &str, body: &Value) {
    let body = body.to_string();
    let _ = write!(
        stream,
        "HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let _ = stream.flush();
}

fn error_body(message: &str) -> Value {
    json!({ "error": { "message": message } })
}

fn answer(state: &Shared, mut stream: TcpStream) {
    let Ok(request) = read_request(&stream) else {
        return;
    };
    let mut guard = state.lock().unwrap();
    guard.requests.push(request.line.clone());
    let mut parts = request.line.split(' ');
    let method = parts.next().unwrap_or_default().to_owned();
    let target = parts
        .next()
        .unwrap_or_default()
        .split('?')
        .next()
        .unwrap_or_default()
        .to_owned();
    // The health answer is decided before the request is logged and is logged with it, so a
    // reader of the log never sees a health request whose answer could still change.
    let ready = guard.ready && guard.ready_file.as_ref().is_none_or(|file| file.exists());
    let health = (method == "GET"
        && target == "/health"
        && !guard.hang_ups.contains(&target)
        && !guard.failures.contains_key(&target))
    .then_some(if ready { 200 } else { 503 });
    if let Some(log) = &guard.log {
        let mut file = std::fs::File::options()
            .create(true)
            .append(true)
            .open(log)
            .unwrap();
        let answered = health
            .map(|status| format!(" answered {status}"))
            .unwrap_or_default();
        writeln!(
            file,
            "{} {}{answered}",
            request.line,
            String::from_utf8_lossy(&request.body)
        )
        .unwrap();
    }
    let body: Value = serde_json::from_slice(&request.body).unwrap_or(Value::Null);
    guard.bodies.push(body.clone());

    // The routes that look into the fake answer whatever is scripted for the others.
    match (method.as_str(), target.as_str()) {
        ("POST", "/fake/exit") if guard.exits_on_request => {
            drop(guard);
            respond(&mut stream, "200 OK", &json!({}));
            std::process::exit(3);
        }
        ("GET", "/fake/environment") => {
            let environment = json!(guard.environment);
            drop(guard);
            respond(&mut stream, "200 OK", &environment);
            return;
        }
        ("GET", "/fake/arguments") => {
            let arguments = json!(guard.arguments);
            drop(guard);
            respond(&mut stream, "200 OK", &arguments);
            return;
        }
        _ => {}
    }
    if guard.hang_ups.contains(&target) {
        drop(guard);
        let _ = stream.shutdown(std::net::Shutdown::Both);
        return;
    }
    if let Some(scripted) = guard.failures.get(&target).cloned() {
        drop(guard);
        respond(&mut stream, &scripted.status, &scripted.body);
        return;
    }
    match (method.as_str(), target.as_str()) {
        ("GET", "/health") => {
            drop(guard);
            if health == Some(200) {
                respond(&mut stream, "200 OK", &json!({ "status": "ok" }));
            } else {
                respond(
                    &mut stream,
                    "503 Service Unavailable",
                    &error_body("Loading model"),
                );
            }
        }
        ("GET", "/props") => {
            let build_info = guard.build_info.clone();
            drop(guard);
            respond(
                &mut stream,
                "200 OK",
                &json!({ "build_info": build_info, "role": "router" }),
            );
        }
        ("GET", "/models") => {
            let data: Vec<Value> = guard
                .models
                .iter()
                .map(|(id, status)| {
                    let mut status_entry = json!({ "value": status.as_str() });
                    if *status == ModelStatus::Failed {
                        status_entry["failed"] = json!(true);
                        status_entry["exit_code"] = json!(1);
                    }
                    json!({
                        "id": id,
                        "object": "model",
                        "status": status_entry,
                    })
                })
                .collect();
            drop(guard);
            respond(
                &mut stream,
                "200 OK",
                &json!({ "object": "list", "data": data }),
            );
        }
        ("POST", "/models/load" | "/models/unload") => {
            let loading = target == "/models/load";
            let leaves_loading = guard.load_leaves_loading;
            let fails = guard.load_fails;
            let evicted = guard.load_evicted;
            let reply = match body["model"].as_str() {
                None => ("400 Bad Request", error_body("the request names no model")),
                Some(model) => match guard.models.get_mut(model) {
                    None => ("404 Not Found", error_body("model not found")),
                    Some(ModelStatus::Loaded | ModelStatus::Loading) if loading => {
                        ("400 Bad Request", error_body("model is already running"))
                    }
                    Some(status) => {
                        *status = match (loading, fails, evicted, leaves_loading) {
                            (true, true, _, _) => ModelStatus::Failed,
                            (true, false, true, _) => ModelStatus::Unloaded,
                            (true, false, false, true) => ModelStatus::Loading,
                            (true, false, false, false) => ModelStatus::Loaded,
                            (false, _, _, _) => ModelStatus::Unloaded,
                        };
                        ("200 OK", json!({ "success": true }))
                    }
                },
            };
            // Whatever happens to the router while a load is on its way happens for a
            // model it knows, whether it started the load or held the model.
            if loading
                && matches!(reply.0, "200 OK" | "400 Bad Request")
                && body["model"]
                    .as_str()
                    .is_some_and(|model| guard.models.contains_key(model))
                && let Some(on_load) = guard.on_load.as_mut()
            {
                on_load();
            }
            drop(guard);
            respond(&mut stream, reply.0, &reply.1);
        }
        ("POST", "/v1/completions") => {
            let reply = match body["model"].as_str().map(|model| guard.models.get(model)) {
                None => ("400 Bad Request", error_body("the request names no model")),
                Some(None) => ("404 Not Found", error_body("model not found")),
                Some(Some(ModelStatus::Unloaded | ModelStatus::Failed)) => {
                    ("400 Bad Request", error_body("model is not loaded"))
                }
                Some(Some(ModelStatus::Loaded | ModelStatus::Loading)) => (
                    "200 OK",
                    json!({
                        "object": "text_completion",
                        "choices": [{ "index": 0, "text": "Ok", "finish_reason": "length" }],
                        "usage": { "prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5 },
                    }),
                ),
            };
            drop(guard);
            respond(&mut stream, reply.0, &reply.1);
        }
        _ => {
            drop(guard);
            respond(&mut stream, "404 Not Found", &error_body("not found"));
        }
    }
}

/// A fake answering on a loopback port of the test process until dropped.
pub(crate) struct FakeLlamaCpp {
    pub state: Shared,
    address: SocketAddr,
    stop: Arc<AtomicBool>,
    accept: Option<JoinHandle<()>>,
}

impl FakeLlamaCpp {
    /// Starts a ready router that reports `build_info` and lists no model.
    pub fn start(build_info: &str) -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let state: Shared = Arc::new(Mutex::new(FakeState {
            build_info: build_info.to_owned(),
            ready: true,
            ..FakeState::default()
        }));
        let address = listener.local_addr().unwrap();
        let stop = Arc::new(AtomicBool::new(false));
        let accept = {
            let state = state.clone();
            let stop = stop.clone();
            std::thread::spawn(move || accept_until(&listener, &state, &stop))
        };
        Self {
            state,
            address,
            stop,
            accept: Some(accept),
        }
    }

    pub fn address(&self) -> SocketAddr {
        self.address
    }
}

impl Drop for FakeLlamaCpp {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Release);
        let _ = TcpStream::connect(self.address);
        if let Some(accept) = self.accept.take() {
            let _ = accept.join();
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

/// The child-process mode: the test binary stands in for the program's router.
#[test]
fn serve_helper() {
    if std::env::var_os(HELPER_MODE).is_none() {
        return;
    }
    let arguments: Vec<String> = std::env::args().collect();
    let option = |name: &str| {
        arguments
            .windows(2)
            .find(|pair| pair[0] == name)
            .map(|pair| pair[1].clone())
    };
    let host = option("--host").unwrap_or_else(|| "127.0.0.1".into());
    let port = option("--port").expect("the router is given its port");
    if let Some(launches) = std::env::var_os(HELPER_LAUNCHES) {
        let mut file = std::fs::File::options()
            .create(true)
            .append(true)
            .open(launches)
            .unwrap();
        writeln!(file, "{LAUNCHED}").unwrap();
    }
    let listener = TcpListener::bind(format!("{host}:{port}")).unwrap();
    let address = listener.local_addr().unwrap();
    let state: Shared = Arc::new(Mutex::new(FakeState {
        build_info: std::env::var(HELPER_BUILD).unwrap(),
        ready: true,
        ready_file: std::env::var_os(HELPER_READY_GATE).map(PathBuf::from),
        models: std::env::var(HELPER_MODELS)
            .unwrap_or_default()
            .split(',')
            .filter(|id| !id.is_empty())
            .map(|id| (id.to_owned(), ModelStatus::Unloaded))
            .collect(),
        environment: std::env::vars().collect(),
        arguments,
        log: std::env::var_os(HELPER_LOG).map(PathBuf::from),
        exits_on_request: true,
        ..FakeState::default()
    }));
    if let Some(gate) = std::env::var_os(HELPER_GATE) {
        while !std::path::Path::new(&gate).exists() {
            std::thread::sleep(std::time::Duration::from_millis(20));
        }
    }
    // The program's own announcement, which the engine waits for.
    let banner = std::env::var(HELPER_BANNER).unwrap_or_else(|_| BANNER.to_owned());
    if !banner.is_empty() {
        eprintln!("{}", banner.replace("{address}", &address.to_string()));
    }
    std::thread::spawn(|| {
        let mut sink = Vec::new();
        let _ = std::io::stdin().read_to_end(&mut sink);
        std::process::exit(0);
    });
    accept_until(&listener, &state, &AtomicBool::new(false));
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::provisioning::local_ai::loopback::Loopback;
    use std::process::{Child, Command, Stdio};

    fn json_of(body: &[u8]) -> Value {
        serde_json::from_slice(body).unwrap()
    }

    fn scripted(status: &str, message: &str) -> Scripted {
        Scripted {
            status: status.to_owned(),
            body: error_body(message),
        }
    }

    #[test]
    fn health_follows_readiness() {
        let fake = FakeLlamaCpp::start("b1");
        let loopback = Loopback::new(fake.address()).unwrap();
        fake.state.lock().unwrap().ready = false;

        let (status, body) = loopback.get("/health").unwrap();
        assert_eq!(status, 503);
        assert_eq!(json_of(&body), error_body("Loading model"));

        fake.state.lock().unwrap().ready = true;
        let (status, body) = loopback.get("/health").unwrap();
        assert_eq!(status, 200);
        assert_eq!(json_of(&body), json!({ "status": "ok" }));
    }

    #[test]
    fn props_report_the_build() {
        let fake = FakeLlamaCpp::start("b7654-abcdef0");
        let loopback = Loopback::new(fake.address()).unwrap();

        let (status, body) = loopback.get("/props").unwrap();

        assert_eq!(status, 200);
        assert_eq!(json_of(&body)["build_info"], "b7654-abcdef0");
    }

    #[test]
    fn models_list_each_status_by_id() {
        let fake = FakeLlamaCpp::start("b1");
        let loopback = Loopback::new(fake.address()).unwrap();
        {
            let mut state = fake.state.lock().unwrap();
            state.models.insert("a".into(), ModelStatus::Loaded);
            state.models.insert("b".into(), ModelStatus::Unloaded);
            state.models.insert("c".into(), ModelStatus::Loading);
        }

        let (status, body) = loopback.get("/models").unwrap();

        assert_eq!(status, 200);
        let listed: Vec<(String, String)> = json_of(&body)["data"]
            .as_array()
            .unwrap()
            .iter()
            .map(|entry| {
                (
                    entry["id"].as_str().unwrap().to_owned(),
                    entry["status"]["value"].as_str().unwrap().to_owned(),
                )
            })
            .collect();
        assert_eq!(
            listed,
            [
                ("a".to_owned(), "loaded".to_owned()),
                ("b".to_owned(), "unloaded".to_owned()),
                ("c".to_owned(), "loading".to_owned()),
            ]
        );
    }

    #[test]
    fn load_and_unload_change_the_status_and_record_what_was_sent() {
        let fake = FakeLlamaCpp::start("b1");
        let loopback = Loopback::new(fake.address()).unwrap();
        fake.state
            .lock()
            .unwrap()
            .models
            .insert("m".into(), ModelStatus::Unloaded);

        let load = json!({ "model": "m", "ctx_size": 4096 });
        let (status, body) = loopback
            .post("/models/load", load.to_string().as_bytes())
            .unwrap();
        assert_eq!((status, json_of(&body)), (200, json!({ "success": true })));
        assert_eq!(fake.state.lock().unwrap().models["m"], ModelStatus::Loaded);

        let unload = json!({ "model": "m" });
        let (status, body) = loopback
            .post("/models/unload", unload.to_string().as_bytes())
            .unwrap();
        assert_eq!((status, json_of(&body)), (200, json!({ "success": true })));
        assert_eq!(
            fake.state.lock().unwrap().models["m"],
            ModelStatus::Unloaded
        );

        fake.state.lock().unwrap().load_leaves_loading = true;
        loopback
            .post("/models/load", load.to_string().as_bytes())
            .unwrap();
        let state = fake.state.lock().unwrap();
        assert_eq!(state.models["m"], ModelStatus::Loading);
        assert_eq!(state.bodies, [load.clone(), unload, load]);
        assert_eq!(state.bodies[0]["ctx_size"], 4096);
        assert_eq!(
            state.requests,
            [
                "POST /models/load HTTP/1.1",
                "POST /models/unload HTTP/1.1",
                "POST /models/load HTTP/1.1"
            ]
        );
    }

    #[test]
    fn a_failed_load_shows_only_in_the_list_and_a_held_model_is_already_running() {
        let fake = FakeLlamaCpp::start("b1");
        let loopback = Loopback::new(fake.address()).unwrap();
        {
            let mut state = fake.state.lock().unwrap();
            state.models.insert("m".into(), ModelStatus::Unloaded);
            state.load_fails = true;
        }

        let (status, body) = loopback.post("/models/load", br#"{"model":"m"}"#).unwrap();
        assert_eq!((status, json_of(&body)), (200, json!({ "success": true })));
        let (_, body) = loopback.get("/models").unwrap();
        assert_eq!(
            json_of(&body)["data"][0]["status"],
            json!({ "value": "unloaded", "failed": true, "exit_code": 1 })
        );
        let (status, _) = loopback
            .post("/v1/completions", br#"{"model":"m","prompt":"x"}"#)
            .unwrap();
        assert_eq!(status, 400, "a model whose load failed generates nothing");

        // The next load can succeed, and a model then held answers a load as running.
        fake.state.lock().unwrap().load_fails = false;
        let (status, _) = loopback.post("/models/load", br#"{"model":"m"}"#).unwrap();
        assert_eq!(status, 200);
        assert_eq!(fake.state.lock().unwrap().models["m"], ModelStatus::Loaded);
        let (status, body) = loopback.post("/models/load", br#"{"model":"m"}"#).unwrap();
        assert_eq!(status, 400);
        assert_eq!(json_of(&body), error_body("model is already running"));
        let (_, body) = loopback.get("/models").unwrap();
        assert_eq!(
            json_of(&body)["data"][0]["status"],
            json!({ "value": "loaded" })
        );
    }

    #[test]
    fn an_evicted_load_is_taken_and_listed_unloaded_with_no_failed_flag() {
        let fake = FakeLlamaCpp::start("b1");
        let loopback = Loopback::new(fake.address()).unwrap();
        {
            let mut state = fake.state.lock().unwrap();
            state.models.insert("m".into(), ModelStatus::Unloaded);
            state.load_evicted = true;
        }

        let (status, body) = loopback.post("/models/load", br#"{"model":"m"}"#).unwrap();
        assert_eq!((status, json_of(&body)), (200, json!({ "success": true })));
        let (_, body) = loopback.get("/models").unwrap();
        assert_eq!(
            json_of(&body)["data"][0]["status"],
            json!({ "value": "unloaded" })
        );
    }

    #[test]
    fn a_completion_generates_with_a_loaded_model_only() {
        let fake = FakeLlamaCpp::start("b1");
        let loopback = Loopback::new(fake.address()).unwrap();
        fake.state
            .lock()
            .unwrap()
            .models
            .insert("m".into(), ModelStatus::Unloaded);
        let request = json!({ "model": "m", "prompt": "Say one word.", "max_tokens": 1 });

        let (status, _) = loopback
            .post("/v1/completions", request.to_string().as_bytes())
            .unwrap();
        assert_eq!(status, 400, "an unloaded model generates nothing");

        loopback.post("/models/load", br#"{"model":"m"}"#).unwrap();
        let (status, body) = loopback
            .post("/v1/completions", request.to_string().as_bytes())
            .unwrap();
        assert_eq!(status, 200);
        assert_eq!(json_of(&body)["usage"]["completion_tokens"], 1);

        let (status, _) = loopback
            .post("/v1/completions", br#"{"model":"other","prompt":"x"}"#)
            .unwrap();
        assert_eq!(status, 404);
    }

    #[test]
    fn a_load_of_an_unknown_or_unnamed_model_is_refused() {
        let fake = FakeLlamaCpp::start("b1");
        let loopback = Loopback::new(fake.address()).unwrap();

        let (status, _) = loopback
            .post("/models/load", br#"{"model":"nope"}"#)
            .unwrap();
        assert_eq!(status, 404);
        let (status, _) = loopback.post("/models/unload", b"{}").unwrap();
        assert_eq!(status, 400);
        let (status, _) = loopback.get("/nowhere").unwrap();
        assert_eq!(status, 404);
    }

    #[test]
    fn a_scripted_failure_replaces_its_route_until_removed() {
        let fake = FakeLlamaCpp::start("b1");
        let loopback = Loopback::new(fake.address()).unwrap();
        {
            let mut state = fake.state.lock().unwrap();
            state.models.insert("m".into(), ModelStatus::Unloaded);
            state.failures.insert(
                "/models/load".into(),
                scripted("500 Internal Server Error", "out of memory"),
            );
        }

        let (status, body) = loopback.post("/models/load", br#"{"model":"m"}"#).unwrap();
        assert_eq!(status, 500);
        assert_eq!(json_of(&body), error_body("out of memory"));
        assert_eq!(
            fake.state.lock().unwrap().models["m"],
            ModelStatus::Unloaded
        );

        fake.state.lock().unwrap().failures.clear();
        let (status, _) = loopback.post("/models/load", br#"{"model":"m"}"#).unwrap();
        assert_eq!(status, 200);
    }

    #[test]
    fn a_hang_up_closes_the_request_without_an_answer() {
        let fake = FakeLlamaCpp::start("b1");
        let loopback = Loopback::new(fake.address()).unwrap();
        fake.state.lock().unwrap().hang_ups.insert("/props".into());

        loopback.get("/props").expect_err("the request is dropped");

        // Only that path is dropped.
        assert_eq!(loopback.get("/health").unwrap().0, 200);
    }

    /// The helper child, ended when it drops.
    struct Helper(Child);

    impl Drop for Helper {
        fn drop(&mut self) {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }

    fn free_port() -> u16 {
        TcpListener::bind("127.0.0.1:0")
            .unwrap()
            .local_addr()
            .unwrap()
            .port()
    }

    /// Starts the helper on `port` with `environment` and waits for its first line of
    /// standard error, its announcement.
    fn start_helper(port: u16, environment: &[(&str, &std::ffi::OsStr)]) -> (Helper, String) {
        let port = port.to_string();
        let mut command = Command::new(std::env::current_exe().unwrap());
        command
            .args(HELPER_ARGUMENTS)
            .args(["--", "--host", "127.0.0.1", "--port", port.as_str()])
            .env(HELPER_MODE, "serve")
            .env(HELPER_BUILD, "b4242")
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::piped());
        for (name, value) in environment {
            command.env(name, value);
        }
        let mut child = command.spawn().unwrap();
        let stderr = child.stderr.take().unwrap();
        let mut helper = Helper(child);
        let mut banner = String::new();
        let mut reader = BufReader::new(stderr);
        if reader.read_line(&mut banner).unwrap() == 0 {
            let _ = helper.0.wait();
            panic!("the helper ended without announcing that it listens");
        }
        // Keep draining so the helper never blocks on a full pipe.
        std::thread::spawn(move || {
            let mut sink = Vec::new();
            let _ = reader.read_to_end(&mut sink);
        });
        (helper, banner)
    }

    #[test]
    fn the_helper_announces_serves_records_and_exits_on_request() {
        let port = free_port();
        let directory = tempfile::tempdir().unwrap();
        let ready = directory.path().join("ready");
        let log = directory.path().join("requests.log");
        let (mut helper, banner) = start_helper(
            port,
            &[
                (HELPER_READY_GATE, ready.as_os_str()),
                (HELPER_MODELS, std::ffi::OsStr::new("m1,m2")),
                (HELPER_LOG, log.as_os_str()),
            ],
        );
        assert!(
            banner.contains(&format!("http://127.0.0.1:{port}")),
            "{banner}"
        );
        let loopback = Loopback::new(SocketAddr::from(([127, 0, 0, 1], port))).unwrap();

        // It listens and is not ready until the file is there.
        assert_eq!(loopback.get("/health").unwrap().0, 503);
        std::fs::write(&ready, b"").unwrap();
        assert_eq!(loopback.get("/health").unwrap().0, 200);
        assert_eq!(
            json_of(&loopback.get("/props").unwrap().1)["build_info"],
            "b4242"
        );

        let (_, body) = loopback.get("/models").unwrap();
        let ids: Vec<String> = json_of(&body)["data"]
            .as_array()
            .unwrap()
            .iter()
            .map(|entry| entry["id"].as_str().unwrap().to_owned())
            .collect();
        assert_eq!(ids, ["m1", "m2"]);
        loopback
            .post("/models/load", br#"{"model":"m1","ctx_size":2048}"#)
            .unwrap();

        // The helper reports how it was started.
        let (_, body) = loopback.get("/fake/environment").unwrap();
        assert_eq!(json_of(&body)[HELPER_BUILD], "b4242");
        assert!(json_of(&body).get("LLAMA_ARG_PORT").is_none());
        let (_, body) = loopback.get("/fake/arguments").unwrap();
        let arguments: Vec<String> = serde_json::from_value(json_of(&body)).unwrap();
        assert!(
            arguments
                .iter()
                .any(|argument| argument == HELPER_ARGUMENTS[1])
        );
        let port_text = port.to_string();
        assert!(
            arguments
                .windows(2)
                .any(|pair| pair[0] == "--port" && pair[1] == port_text),
            "{arguments:?}"
        );

        // Exiting on request ends it as a crash would.
        let (status, _) = loopback.post("/fake/exit", b"{}").unwrap();
        assert_eq!(status, 200);
        assert_eq!(helper.0.wait().unwrap().code(), Some(3));
        let written = std::fs::read_to_string(&log).unwrap();
        assert!(written.contains("GET /health HTTP/1.1"), "{written}");
        assert!(
            written.contains(r#"{"model":"m1","ctx_size":2048}"#),
            "{written}"
        );
    }

    #[test]
    fn the_helper_ends_when_its_standard_input_closes() {
        let port = free_port();
        let (mut helper, _) = start_helper(port, &[]);
        drop(helper.0.stdin.take());

        assert_eq!(helper.0.wait().unwrap().code(), Some(0));
    }

    #[test]
    fn a_banner_can_be_scripted_and_a_gate_delays_it() {
        let port = free_port();
        let directory = tempfile::tempdir().unwrap();
        let gate = directory.path().join("announce");
        let handle = {
            let gate = gate.clone();
            std::thread::spawn(move || {
                start_helper(
                    port,
                    &[
                        (HELPER_GATE, gate.as_os_str()),
                        (HELPER_BANNER, std::ffi::OsStr::new("ready at {address}")),
                    ],
                )
            })
        };
        // The helper has not announced: it waits for the gate.
        std::thread::sleep(std::time::Duration::from_millis(200));
        assert!(!handle.is_finished());
        std::fs::write(&gate, b"").unwrap();
        let (_helper, banner) = handle.join().unwrap();
        assert_eq!(banner.trim_end(), format!("ready at 127.0.0.1:{port}"));
    }
}
