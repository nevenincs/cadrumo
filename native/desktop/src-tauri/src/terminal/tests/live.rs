//! Live PTY tests against a real package selected by CADRUMO_DESKTOP_PACKAGE_ROOT.
use crate::{
    environment::{self, Launch, Parent},
    terminal::{
        Kind, Program, TerminalState, console,
        credit::PAUSE,
        frame::{Decoded, decode},
        ipc,
        session::{CHUNK, Session, Sink, failure},
    },
};
use cadrumo_application::{
    child::ChildConfiguration,
    diagnostics::Diagnostics,
    error::application::{ErrorCode, Result},
    process::status::{ProcessPhase, ProcessRole, Stream},
};
use std::{
    ffi::OsString,
    fs,
    path::{Path, PathBuf},
    sync::{
        Arc, Mutex,
        mpsc::{self, Receiver, RecvTimeoutError},
    },
    thread,
    time::{Duration, Instant},
};
use tauri::{
    WebviewWindowBuilder,
    http::{HeaderMap, HeaderValue},
    ipc::{CallbackFn, InvokeBody, InvokeResponseBody},
    test::{INVOKE_KEY, get_ipc_response, mock_builder, mock_context, noop_assets},
    webview::{InvokeRequest, PageLoadEvent},
};

const WAIT: Duration = Duration::from_secs(60);
const SETTLE_BOUND: Duration = Duration::from_secs(5);

fn package() -> PathBuf {
    PathBuf::from(std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT").expect("select real package"))
}

/// The projection query has its own 30 s deadline, which a loaded machine can
/// exceed; the terminal behavior under test starts after it, so a timed-out
/// query is repeated rather than failing the terminal test.
async fn launch() -> Launch {
    for _ in 0..2 {
        match environment::resolve(
            package(),
            &Parent::current().unwrap(),
            Arc::new(Diagnostics::default()),
        )
        .await
        {
            Err(error) if error.code == ErrorCode::TimedOut => {
                eprintln!("projection query timed out; repeating it");
            }
            outcome => return outcome.unwrap(),
        }
    }
    environment::resolve(
        package(),
        &Parent::current().unwrap(),
        Arc::new(Diagnostics::default()),
    )
    .await
    .unwrap()
}

fn collector() -> (Sink, Receiver<Vec<u8>>) {
    let (frames, received) = mpsc::channel();
    (
        Arc::new(move |frame| {
            frames
                .send(frame)
                .map_err(|_| failure(ErrorCode::WriteFailed))
        }),
        received,
    )
}

fn same_path(left: &Path, right: &Path) -> bool {
    fs::canonicalize(left).unwrap() == fs::canonicalize(right).unwrap()
}

fn arguments(values: &[&str]) -> Vec<OsString> {
    values.iter().map(OsString::from).collect()
}

/// Removes control sequences so printed text can be matched.
fn printed(raw: &[u8]) -> String {
    let text = String::from_utf8_lossy(raw);
    let mut out = String::with_capacity(text.len());
    let mut chars = text.chars().peekable();
    while let Some(c) = chars.next() {
        if c != '\u{1b}' {
            out.push(c);
            continue;
        }
        match chars.next() {
            Some('[') => {
                for c in chars.by_ref() {
                    if ('@'..='~').contains(&c) {
                        break;
                    }
                }
            }
            Some(']') => {
                while let Some(c) = chars.next() {
                    if c == '\u{7}' || (c == '\u{1b}' && chars.next_if_eq(&'\\').is_some()) {
                        break;
                    }
                }
            }
            _ => {}
        }
    }
    out
}

/// Every `L<7 digits>` line number, in output order.
fn line_numbers(text: &str) -> Vec<u32> {
    text.split(['\r', '\n'])
        .filter_map(|line| line.strip_prefix('L'))
        .filter(|digits| digits.len() == 7)
        .filter_map(|digits| digits.parse().ok())
        .collect()
}

trait Control {
    fn write(&self, bytes: &[u8]) -> Result<()>;
    fn ack(&self, offset: u64) -> Result<()>;
}

impl Control for Session {
    fn write(&self, bytes: &[u8]) -> Result<()> {
        Session::write(self, bytes)
    }
    fn ack(&self, offset: u64) -> Result<()> {
        self.acknowledge(offset)
    }
}

struct Registered<'a>(&'a TerminalState, u64);

impl Control for Registered<'_> {
    fn write(&self, bytes: &[u8]) -> Result<()> {
        self.0.with_session(self.1, |session| session.write(bytes))
    }
    fn ack(&self, offset: u64) -> Result<()> {
        self.0
            .with_session(self.1, |session| session.acknowledge(offset))
    }
}

/// A frontend stand-in: decodes frames in channel order, acknowledges data and
/// answers cursor position queries the way a terminal emulator does.
struct Screen<'a> {
    frames: Receiver<Vec<u8>>,
    control: &'a dyn Control,
    raw: Vec<u8>,
    received: u64,
    acked: u64,
    peak: u64,
    auto_ack: bool,
    started: Option<u32>,
    exited: Option<Option<u32>>,
    mark: usize,
}

impl<'a> Screen<'a> {
    fn new(frames: Receiver<Vec<u8>>, control: &'a dyn Control) -> Self {
        Self {
            frames,
            control,
            raw: Vec::new(),
            received: 0,
            acked: 0,
            peak: 0,
            auto_ack: true,
            started: None,
            exited: None,
            mark: 0,
        }
    }

    fn ack_all(&mut self) {
        self.control.ack(self.received).unwrap();
        self.acked = self.received;
    }

    /// Handles one frame; false when none arrived in time.
    fn pump(&mut self, timeout: Duration) -> bool {
        let frame = match self.frames.recv_timeout(timeout) {
            Ok(frame) => frame,
            Err(RecvTimeoutError::Timeout | RecvTimeoutError::Disconnected) => return false,
        };
        match decode(&frame).expect("well-formed frame") {
            Decoded::Started { pid } => {
                assert!(
                    self.started.is_none() && self.raw.is_empty(),
                    "started is first"
                );
                self.started = Some(pid);
            }
            Decoded::Data(bytes) => {
                assert!(self.started.is_some(), "data before started");
                assert!(self.exited.is_none(), "data after exited");
                assert!(bytes.len() <= CHUNK);
                self.received += bytes.len() as u64;
                self.peak = self.peak.max(self.received - self.acked);
                let from = self.raw.len().saturating_sub(3);
                self.raw.extend(bytes);
                let queries = self.raw[from..]
                    .windows(4)
                    .filter(|window| window == b"\x1b[6n")
                    .count();
                for _ in 0..queries {
                    self.control.write(b"\x1b[1;1R").unwrap();
                }
                if self.auto_ack {
                    self.ack_all();
                }
            }
            Decoded::Exited { code } => {
                assert!(self.exited.is_none(), "one exited frame");
                self.exited = Some(code);
            }
            Decoded::Failed(failure) => panic!("failed frame: {failure:?}"),
        }
        true
    }

    fn drain(&mut self) {
        while self.pump(Duration::ZERO) {}
    }

    fn text(&self) -> String {
        printed(&self.raw)
    }

    /// Waits for printed `needle` after the previous match.
    fn until(&mut self, needle: &str) {
        let deadline = Instant::now() + WAIT;
        loop {
            let text = self.text();
            if let Some(at) = text[self.mark.min(text.len())..].find(needle) {
                self.mark += at + needle.len();
                return;
            }
            assert!(self.exited.is_none(), "exited before {needle:?}: {text}");
            assert!(Instant::now() < deadline, "no {needle:?}: {text}");
            self.pump(Duration::from_millis(50));
        }
    }

    fn until_raw(&mut self, needle: &[u8]) {
        let deadline = Instant::now() + WAIT;
        while !self
            .raw
            .windows(needle.len())
            .any(|window| window == needle)
        {
            assert!(self.exited.is_none(), "exited before {needle:?}");
            assert!(Instant::now() < deadline, "no {needle:?}: {}", self.text());
            self.pump(Duration::from_millis(50));
        }
    }

    /// The rest of the last printed line starting with `key`.
    fn value(&self, key: &str) -> String {
        let text = self.text();
        let at = text
            .rfind(key)
            .unwrap_or_else(|| panic!("no {key}: {text}"));
        text[at + key.len()..]
            .split(['\r', '\n'])
            .next()
            .unwrap()
            .trim_end()
            .to_owned()
    }

    /// Waits for `exited`, then proves nothing follows it.
    fn exit(&mut self, timeout: Duration) -> Option<u32> {
        let deadline = Instant::now() + timeout;
        while self.exited.is_none() {
            assert!(Instant::now() < deadline, "no exit: {}", self.text());
            self.pump(Duration::from_millis(50));
        }
        assert!(
            !self.pump(Duration::from_millis(300)),
            "a frame followed exited"
        );
        self.exited.unwrap()
    }
}

fn python(launch: &Launch, script: &str) -> Program {
    Program {
        arguments: arguments(&["-u", "-c", script]),
        ..Program::for_kind(launch, Kind::Python).unwrap()
    }
}

/// Writes `megabytes` of numbered lines in blocks, then a marker.
fn flood_script(lines: u32, marker: &str) -> String {
    format!(
        "import sys\nw = sys.stdout.write\nfor b in range({blocks}):\n    w(''.join('L%07d\\n' % i for i in range(b * 1000, b * 1000 + 1000)))\nsys.stdout.flush()\nprint('{marker}')",
        blocks = lines / 1000
    )
}

fn assert_no_pty_bytes(diagnostics: &Diagnostics) {
    let snapshot = diagnostics.snapshot(0);
    assert!(
        snapshot
            .output
            .iter()
            .all(|chunk| chunk.stream != Stream::Terminal
                && !chunk.bytes.windows(4).any(|w| w == b"L000")),
        "PTY bytes reached the diagnostics capture"
    );
    assert!(snapshot.processes.iter().all(|p| p.terminal_bytes == 0));
}

#[tokio::test]
async fn python_kind_is_a_repl_in_home_with_the_pinned_storage_root() {
    let launch = launch().await;
    let (home, storage) = (launch.home.clone(), launch.working_directory.clone());
    let state = TerminalState::new(launch);
    let (sink, frames) = collector();
    let id = state
        .open(Kind::Python, 1000, 40, sink, state.document())
        .unwrap();
    let control = Registered(&state, id);
    let mut screen = Screen::new(frames, &control);
    screen.until(">>> ");
    control.write("print(\"á漢\" * 2)\r".as_bytes()).unwrap();
    screen.until("á漢á漢");
    screen.until(">>> ");
    control
        .write(b"import os; print('CW' + 'D=' + os.getcwd())\r")
        .unwrap();
    screen.until("CWD=");
    screen.until(">>> ");
    control
        .write(b"from cadrumo.core.storage_environment import configured_storage_root as r; print('RO' + 'OT=' + str(r()))\r")
        .unwrap();
    screen.until("ROOT=");
    screen.until(">>> ");
    assert!(same_path(Path::new(&screen.value("CWD=")), &home));
    assert!(
        !fs::canonicalize(&home)
            .unwrap()
            .starts_with(fs::canonicalize(&storage).unwrap())
    );
    assert!(same_path(Path::new(&screen.value("ROOT=")), &storage));
    // The packaged interpreter runs without `site`, so the `exit()` helper
    // does not exist; the REPL still leaves on SystemExit.
    control.write(b"raise SystemExit(0)\r").unwrap();
    assert_eq!(screen.exit(WAIT), Some(0));
    let snapshot = state.launch.diagnostics.snapshot(0);
    let process = snapshot
        .processes
        .iter()
        .find(|p| Some(p.pid) == screen.started)
        .unwrap();
    assert_eq!(process.role, ProcessRole::Repl);
    assert_eq!(process.phase, ProcessPhase::Exited);
    state.stop().unwrap();
}

#[tokio::test]
async fn tui_kind_draws_the_alternate_screen_from_the_storage_root() {
    let launch = launch().await;
    let storage = launch.working_directory.clone();
    let state = TerminalState::new(launch);
    let (sink, frames) = collector();
    let id = state
        .open(Kind::Tui, 120, 40, sink, state.document())
        .unwrap();
    let control = Registered(&state, id);
    let mut screen = Screen::new(frames, &control);
    screen.until_raw(b"\x1b[?1049h");
    state
        .with_session(id, |session| session.resize(100, 30))
        .unwrap();
    control.write(b"\x1b[B\t").unwrap();
    let began = Instant::now();
    state.close(id).unwrap();
    assert!(began.elapsed() < SETTLE_BOUND);
    assert_eq!(
        control.ack(0).unwrap_err().code,
        ErrorCode::SessionUnavailable,
        "a closed session must refuse acks"
    );

    // The same launch, probing its working directory and resolved root.
    let program = Program {
        arguments: arguments(&[
            "-u",
            "-c",
            "import os; from cadrumo.core.storage_environment import configured_storage_root as r; print('CWD=' + os.getcwd()); print('ROOT=' + str(r()))",
        ]),
        ..Program::for_kind(&state.launch, Kind::Tui).unwrap()
    };
    let (sink, frames) = collector();
    let probe = Session::start(program, 1000, 40, sink, state.launch.diagnostics.clone()).unwrap();
    let mut screen = Screen::new(frames, &probe);
    assert_eq!(screen.exit(WAIT), Some(0));
    assert!(same_path(Path::new(&screen.value("CWD=")), &storage));
    assert!(same_path(Path::new(&screen.value("ROOT=")), &storage));
}

#[cfg(windows)]
#[tokio::test]
async fn console_kind_is_the_absolute_platform_shell_with_package_bin_first() {
    let launch = launch().await;
    let home = launch.home.clone();
    let bin = console::package_bin(launch.child.executable()).unwrap();
    let program = Program::for_kind(&launch, Kind::Console).unwrap();
    assert!(program.executable.is_absolute() && program.executable.is_file());
    let core = ["ProgramW6432", "ProgramFiles"]
        .iter()
        .filter_map(std::env::var_os)
        .map(|base| PathBuf::from(base).join(r"PowerShell\7\pwsh.exe"))
        .find(|candidate| candidate.is_file());
    match core {
        Some(core) => assert_eq!(program.executable, core),
        None => assert!(
            program
                .executable
                .ends_with(r"WindowsPowerShell\v1.0\powershell.exe")
        ),
    }
    eprintln!("console shell: {}", program.executable.display());
    drop(program);

    let state = TerminalState::new(launch);
    let (sink, frames) = collector();
    let id = state
        .open(Kind::Console, 1000, 40, sink, state.document())
        .unwrap();
    let control = Registered(&state, id);
    let mut screen = Screen::new(frames, &control);
    screen.until("PS ");
    screen.until(">");
    control
        .write(b"$env:PATH.Split([IO.Path]::PathSeparator) | ForEach-Object { 'PE=' + $_ }; Write-Output ('CW' + 'D=' + (Get-Location).Path)\r")
        .unwrap();
    screen.until("CWD=");
    screen.until("PS ");
    assert!(same_path(Path::new(&screen.value("CWD=")), &home));
    // The shell may add its own directories (PowerShell 7 prepends $PSHOME),
    // but package bin precedes every directory the host passed on.
    let text = screen.text();
    let search: Vec<PathBuf> = text
        .split(['\r', '\n'])
        .filter_map(|line| line.strip_prefix("PE="))
        .map(|entry| PathBuf::from(entry.trim_end()))
        .collect();
    let inherited = state
        .launch
        .child
        .environment()
        .iter()
        .find(|(key, _)| key.eq_ignore_ascii_case("PATH"))
        .and_then(|(_, value)| std::env::split_paths(value).find(|p| p.is_dir()))
        .expect("an inherited search path");
    let position = |wanted: &Path| {
        search
            .iter()
            .position(|entry| entry.is_dir() && same_path(entry, wanted))
    };
    let bin_at = position(&bin).expect("package bin on the console search path");
    let inherited_at = position(&inherited).expect("inherited search path kept");
    assert!(bin_at < inherited_at, "{search:?}");
    eprintln!(
        "console search path ahead of package bin: {:?}",
        &search[..bin_at]
    );

    let contract: serde_json::Value =
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json"))).unwrap();
    let suffix = contract["layout"]["entrypoint_suffix"]
        .as_str()
        .unwrap_or("");
    // Every declared console entrypoint resolves by name from package bin.
    let declared: Vec<String> = contract["layout"]["entrypoints"]
        .as_object()
        .unwrap()
        .keys()
        .cloned()
        .collect();
    assert!(!declared.is_empty());
    for name in &declared {
        assert!(
            bin.join(format!("{name}{suffix}")).is_file(),
            "declared entrypoint {name} is missing from {}",
            bin.display()
        );
        control
            .write(
                format!("Write-Output ('EN' + 'TRY=' + (Get-Command {name}).Source)\r").as_bytes(),
            )
            .unwrap();
        screen.until("ENTRY=");
        screen.until("PS ");
        let source = PathBuf::from(screen.value("ENTRY="));
        assert!(
            same_path(source.parent().unwrap(), &bin),
            "{name} resolved to {source:?}"
        );
        eprintln!("console entrypoint {name} resolves to {}", source.display());
    }
    if declared.iter().any(|name| name == "aeat") {
        control
            .write(b"aeat --version; Write-Output ('AEAT' + '-EXIT=' + $LASTEXITCODE)\r")
            .unwrap();
        screen.until("AEAT-EXIT=");
        screen.until("PS ");
        assert_eq!(screen.value("AEAT-EXIT="), "0");
    } else {
        eprintln!("aeat is not a declared entrypoint in this contract");
    }
    control.write(b"exit\r").unwrap();
    assert_eq!(screen.exit(WAIT), Some(0));
    let snapshot = state.launch.diagnostics.snapshot(0);
    assert!(
        snapshot
            .processes
            .iter()
            .any(|p| Some(p.pid) == screen.started && p.role == ProcessRole::Console)
    );
}

#[tokio::test]
async fn a_final_burst_arrives_before_exited_on_one_channel() {
    let launch = launch().await;
    let (sink, frames) = collector();
    // An unbuffered console write keeps at most 12 KiB of one call, so the
    // burst is written in smaller blocks right before the child exits.
    let session = Session::start(
        python(
            &launch,
            "import sys\nfor b in range(30):\n    sys.stdout.write(''.join('L%07d\\n' % i for i in range(b * 1000, b * 1000 + 1000)))\nsys.stdout.write('TAIL\\n')",
        ),
        200,
        50,
        sink,
        launch.diagnostics.clone(),
    )
    .unwrap();
    let mut screen = Screen::new(frames, &session);
    assert_eq!(screen.exit(WAIT), Some(0));
    let text = screen.text();
    let tail = text.rfind("TAIL").unwrap_or_else(|| {
        let end: String = text
            .chars()
            .rev()
            .take(300)
            .collect::<Vec<_>>()
            .into_iter()
            .rev()
            .collect();
        panic!(
            "no final marker after {} lines; output ends {end:?}",
            line_numbers(&text).len()
        )
    });
    let last = text.rfind("L0029999").expect("final line");
    assert!(last < tail, "the final burst arrived out of order");
    assert_eq!(line_numbers(&text), (0..30000).collect::<Vec<_>>());
    assert_eq!(screen.received, session.delivered());
}

#[tokio::test]
async fn a_flood_pauses_on_credit_and_delivers_every_byte() {
    let launch = launch().await;
    let lines = 1_000_000;
    let (sink, frames) = collector();
    let session = Session::start(
        python(&launch, &flood_script(lines, "FLOOD-DONE")),
        200,
        50,
        sink,
        launch.diagnostics.clone(),
    )
    .unwrap();
    let mut screen = Screen::new(frames, &session);
    // Without acknowledgements the reader stops at the window.
    screen.auto_ack = false;
    let deadline = Instant::now() + WAIT;
    while screen.received < PAUSE {
        assert!(Instant::now() < deadline, "flood never filled the window");
        screen.pump(Duration::from_millis(50));
    }
    thread::sleep(Duration::from_secs(1));
    screen.drain();
    assert!(session.paused());
    assert!(
        screen.received < PAUSE + CHUNK as u64,
        "read past the window"
    );
    assert_eq!(screen.received, session.delivered());
    // Acknowledging resumes it; nothing is lost.
    screen.auto_ack = true;
    screen.ack_all();
    let began = Instant::now();
    assert_eq!(screen.exit(Duration::from_secs(300)), Some(0));
    let elapsed = began.elapsed();
    assert_eq!(screen.received, session.delivered());
    assert_eq!(screen.acked, screen.received);
    assert!(
        screen.peak < PAUSE + CHUNK as u64,
        "window overran: {}",
        screen.peak
    );
    let text = screen.text();
    assert!(text.contains("FLOOD-DONE"));
    let numbers = line_numbers(&text);
    assert_eq!(
        numbers.len(),
        lines as usize,
        "lines lost between child and frontend"
    );
    assert!(numbers.iter().enumerate().all(|(i, n)| i as u32 == *n));
    eprintln!(
        "PTY flood: {} bytes in {:.2?} ({:.1} MB/s) through the credit window",
        screen.received,
        elapsed,
        screen.received as f64 / elapsed.as_secs_f64() / 1e6
    );
    assert_no_pty_bytes(&launch.diagnostics);
}

#[tokio::test]
async fn a_paused_session_settles_within_the_bound() {
    let launch = launch().await;
    let (sink, frames) = collector();
    let mut session = Session::start(
        python(
            &launch,
            "import sys\nw = sys.stdout.write\nwhile True:\n    w('L0000000\\n' * 1000)",
        ),
        200,
        50,
        sink,
        launch.diagnostics.clone(),
    )
    .unwrap();
    let mut screen = Screen::new(frames, &session);
    screen.auto_ack = false;
    while !session.paused() {
        screen.pump(Duration::from_millis(50));
    }
    let pid = screen.started.unwrap();
    drop(screen);
    let began = Instant::now();
    session.stop().unwrap();
    let elapsed = began.elapsed();
    eprintln!("paused session settled in {elapsed:.2?}");
    assert!(elapsed < SETTLE_BOUND);
    let snapshot = launch.diagnostics.snapshot(0);
    let process = snapshot.processes.iter().find(|p| p.pid == pid).unwrap();
    assert_eq!(process.phase, ProcessPhase::Terminated);
    assert_no_pty_bytes(&launch.diagnostics);
}

#[tokio::test]
async fn ctrl_c_reaches_a_child_while_its_output_is_paused() {
    let launch = launch().await;
    let (sink, frames) = collector();
    // A process created in a new process group ignores Ctrl+C, and its
    // descendants inherit that; test runners start commands that way. The
    // child restores default handling so the test observes ConPTY delivery.
    let session = Session::start(
        python(
            &launch,
            "import sys\nif sys.platform == 'win32':\n    import ctypes\n    ctypes.windll.kernel32.SetConsoleCtrlHandler(None, False)\ntry:\n    for i in range(200000):\n        print('L%07d' % i)\nexcept KeyboardInterrupt:\n    print('INTER' + 'RUPTED')\n    sys.exit(7)\nprint('FINI' + 'SHED')",
        ),
        200,
        50,
        sink,
        launch.diagnostics.clone(),
    )
    .unwrap();
    let mut screen = Screen::new(frames, &session);
    screen.auto_ack = false;
    let deadline = Instant::now() + WAIT;
    while !session.paused() {
        assert!(Instant::now() < deadline, "never paused");
        screen.pump(Duration::from_millis(50));
    }
    // Input does not wait for output credit.
    session.write(b"\x03").unwrap();
    thread::sleep(Duration::from_millis(500));
    screen.auto_ack = true;
    screen.ack_all();
    assert_eq!(screen.exit(WAIT), Some(7));
    let text = screen.text();
    assert!(text.contains("INTERRUPTED") && !text.contains("FINISHED"));
}

#[tokio::test]
async fn ipc_commands_write_raw_and_json_bodies_ack_resize_and_close() {
    let launch = launch().await;
    let state = Arc::new(TerminalState::new(launch));
    let (frames_out, frames) = mpsc::channel::<(usize, Vec<u8>)>();
    let forward = Mutex::new(frames_out);
    let app = mock_builder()
        .manage(state.clone())
        .invoke_handler(ipc::handler())
        .channel_interceptor(move |_, _, index, body| {
            if let InvokeResponseBody::Raw(bytes) = body {
                forward
                    .lock()
                    .unwrap()
                    .send((index, bytes.clone()))
                    .unwrap();
            }
            true
        })
        .build(mock_context(noop_assets()))
        .unwrap();
    let window = WebviewWindowBuilder::new(&app, "main", Default::default())
        .build()
        .unwrap();
    let call = |cmd: &str, body: InvokeBody, session: Option<u64>| {
        let mut headers = HeaderMap::new();
        if let Some(session) = session {
            headers.insert(
                ipc::SESSION_HEADER,
                HeaderValue::from_str(&session.to_string()).unwrap(),
            );
        }
        get_ipc_response(
            &window,
            InvokeRequest {
                cmd: cmd.into(),
                callback: CallbackFn(0),
                error: CallbackFn(1),
                url: if cfg!(windows) {
                    "http://tauri.localhost"
                } else {
                    "tauri://localhost"
                }
                .parse()
                .unwrap(),
                body,
                headers,
                invoke_key: INVOKE_KEY.to_owned(),
            },
        )
        .map(|body| -> serde_json::Value {
            match body {
                InvokeResponseBody::Json(json) => serde_json::from_str(&json).unwrap(),
                InvokeResponseBody::Raw(bytes) => serde_json::from_slice(&bytes).unwrap(),
            }
        })
    };
    let opened = call(
        "terminal_open",
        InvokeBody::Json(serde_json::json!({"kind": "python", "cols": 1000, "rows": 40, "frames": "__CHANNEL__:11"})),
        None,
    )
    .unwrap();
    let session = opened["session"].as_u64().unwrap();
    let refused = call(
        "terminal_open",
        InvokeBody::Json(serde_json::json!({"kind": "python", "cols": 80, "rows": 24, "frames": "__CHANNEL__:12"})),
        None,
    )
    .unwrap_err();
    assert_eq!(refused["code"], "session_unavailable");

    // Frames arrive with contiguous channel indexes; acks go through IPC.
    let (decoded_out, decoded) = mpsc::channel();
    let done = Arc::new(std::sync::atomic::AtomicBool::new(false));
    let finished = done.clone();
    let pump = thread::spawn(move || {
        let mut next = 0;
        while !finished.load(std::sync::atomic::Ordering::Acquire) {
            let Ok((index, frame)) = frames.recv_timeout(Duration::from_millis(50)) else {
                continue;
            };
            assert_eq!(index, next, "channel order");
            next += 1;
            if decoded_out.send(frame).is_err() {
                break;
            }
        }
    });
    type Reply = std::result::Result<serde_json::Value, serde_json::Value>;
    struct Ipc<'a> {
        call: &'a dyn Fn(&str, InvokeBody, Option<u64>) -> Reply,
        session: u64,
    }
    impl Control for Ipc<'_> {
        fn write(&self, bytes: &[u8]) -> Result<()> {
            (self.call)(
                "terminal_write",
                InvokeBody::Raw(bytes.to_vec()),
                Some(self.session),
            )
            .map(|_| ())
            .map_err(|_| failure(ErrorCode::WriteFailed))
        }
        fn ack(&self, offset: u64) -> Result<()> {
            (self.call)(
                "terminal_ack",
                InvokeBody::Json(serde_json::json!({"session": self.session, "offset": offset})),
                None,
            )
            .map(|_| ())
            .map_err(|_| failure(ErrorCode::InvalidArguments))
        }
    }
    let control = Ipc {
        call: &call,
        session,
    };
    let mut screen = Screen::new(decoded, &control);
    screen.until(">>> ");
    // Raw body.
    control.write(b"print('RA' + 'W=' + 'ok')\r").unwrap();
    screen.until("RAW=ok");
    screen.until(">>> ");
    // The postMessage transport's JSON byte array, same command and headers.
    let json: Vec<u8> = "print('JS' + 'ON=' + 'á')\r".bytes().collect();
    call(
        "terminal_write",
        InvokeBody::Json(serde_json::to_value(&json).unwrap()),
        Some(session),
    )
    .unwrap();
    screen.until("JSON=á");
    screen.until(">>> ");
    let oversized = call(
        "terminal_write",
        InvokeBody::Raw(vec![b' '; 65537]),
        Some(session),
    )
    .unwrap_err();
    assert_eq!(oversized["code"], "invalid_arguments");
    let beyond = call(
        "terminal_ack",
        InvokeBody::Json(serde_json::json!({"session": session, "offset": screen.received + 1})),
        None,
    )
    .unwrap_err();
    assert_eq!(beyond["code"], "invalid_arguments");
    call(
        "terminal_resize",
        InvokeBody::Json(serde_json::json!({"session": session, "cols": 132, "rows": 40})),
        None,
    )
    .unwrap();
    let small = call(
        "terminal_resize",
        InvokeBody::Json(serde_json::json!({"session": session, "cols": 1, "rows": 40})),
        None,
    )
    .unwrap_err();
    assert_eq!(small["code"], "invalid_arguments");
    control
        .write(b"import os; print('CO' + 'LS=' + str(os.get_terminal_size().columns))\r")
        .unwrap();
    screen.until("COLS=132");
    let began = Instant::now();
    let closed = call(
        "terminal_close",
        InvokeBody::Json(serde_json::json!({"session": session})),
        None,
    )
    .unwrap();
    assert!(began.elapsed() < SETTLE_BOUND);
    assert_eq!(closed, serde_json::json!({}));
    let replaced = call(
        "terminal_write",
        InvokeBody::Raw(b"x".to_vec()),
        Some(session),
    )
    .unwrap_err();
    assert_eq!(replaced["code"], "session_unavailable");
    let stale = call(
        "terminal_ack",
        InvokeBody::Json(serde_json::json!({"session": session, "offset": 0})),
        None,
    )
    .unwrap_err();
    assert_eq!(stale["code"], "session_unavailable");
    drop(screen);
    done.store(true, std::sync::atomic::Ordering::Release);
    pump.join().unwrap();
    drop(app);
}

#[tokio::test]
async fn a_page_load_settles_every_kind_and_new_sessions_replace_them() {
    let launch = launch().await;
    let state = TerminalState::new(launch);
    let (python_sink, python_frames) = collector();
    let (tui_sink, tui_frames) = collector();
    let python = state
        .open(Kind::Python, 120, 40, python_sink, state.document())
        .unwrap();
    let tui = state
        .open(Kind::Tui, 120, 40, tui_sink, state.document())
        .unwrap();
    let python_control = Registered(&state, python);
    let mut python_screen = Screen::new(python_frames, &python_control);
    python_screen.until(">>> ");
    let tui_control = Registered(&state, tui);
    let mut tui_screen = Screen::new(tui_frames, &tui_control);
    tui_screen.until_raw(b"\x1b[?1049h");
    drop((python_screen, tui_screen));

    state.page_load(PageLoadEvent::Finished);
    assert!(state.with_session(python, |s| Ok(s.live())).unwrap());
    let began = Instant::now();
    state.page_load(PageLoadEvent::Started);
    let elapsed = began.elapsed();
    eprintln!("page load settled both kinds in {elapsed:.2?}");
    assert!(elapsed < SETTLE_BOUND);
    for id in [python, tui] {
        assert_eq!(
            state.with_session(id, |_| Ok(())).unwrap_err().code,
            ErrorCode::SessionUnavailable
        );
    }
    let (sink, frames) = collector();
    let reopened = state
        .open(Kind::Python, 120, 40, sink, state.document())
        .unwrap();
    assert!(reopened > tui);
    let control = Registered(&state, reopened);
    let mut screen = Screen::new(frames, &control);
    screen.until(">>> ");
    drop(screen);
    state.stop().unwrap();
}

/// Regression from the storage-root pin: with the canonical root override set
/// in the parent, every child kind and the CLI passthrough of a relocated
/// installed layout resolve exactly that root from any working directory.
mod relocated {
    use super::*;
    use std::collections::BTreeMap;

    // Reports the storage root this process resolves through both owners.
    const PROBE: &str = "import json, os, sys; from cadrumo.core.config import load_settings; from cadrumo.core.storage_environment import configured_storage_root; open(sys.argv[1], 'w', encoding='utf-8').write(json.dumps([str(configured_storage_root()), str(load_settings().cadrumo_local_storage_root), os.getcwd()]))";

    struct Scratch(PathBuf);
    impl Drop for Scratch {
        fn drop(&mut self) {
            if let Err(error) = fs::remove_dir_all(&self.0) {
                eprintln!("relocated package left at {:?}: {error}", self.0);
            }
        }
    }

    fn contract() -> serde_json::Value {
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json"))).unwrap()
    }

    /// A fresh directory outside any project, so the package resolves in
    /// installed mode.
    fn outside_project(label: &str) -> Scratch {
        let base = std::env::temp_dir().join(format!(
            "cadrumo-{label}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        assert!(
            !inside_project(&base),
            "the temporary directory must lie outside any project for an installed-mode layout"
        );
        Scratch(base)
    }

    fn settings_storage_names() -> Vec<String> {
        serde_json::from_value(contract()["storage_environment_allowlist"].clone()).unwrap()
    }

    /// The canonical root override, which wins in every mode.
    fn root_variable() -> String {
        contract()["root"]["variable"].as_str().unwrap().to_owned()
    }

    fn storage_name(key: &OsString, names: &[String]) -> bool {
        names.contains(&key.to_string_lossy().to_ascii_uppercase())
    }

    fn inside_project(path: &Path) -> bool {
        path.ancestors()
            .any(|ancestor| ancestor.join("pyproject.toml").is_file())
    }

    // Hard links keep relocation cheap on one volume; copies cover the rest.
    fn relocate(from: &Path, to: &Path) {
        fs::create_dir_all(to).unwrap();
        for entry in fs::read_dir(from).unwrap() {
            let entry = entry.unwrap();
            let kind = entry.file_type().unwrap();
            let target = to.join(entry.file_name());
            assert!(
                !kind.is_symlink(),
                "package contains a link: {:?}",
                entry.path()
            );
            if kind.is_dir() {
                relocate(&entry.path(), &target);
            } else if fs::hard_link(entry.path(), &target).is_err() {
                fs::copy(entry.path(), &target).unwrap();
            }
        }
    }

    fn read_report(report: &Path) -> Vec<PathBuf> {
        let values: Vec<String> =
            serde_json::from_str(&fs::read_to_string(report).unwrap()).unwrap();
        fs::remove_file(report).unwrap();
        values.into_iter().map(PathBuf::from).collect()
    }

    /// The probe's report, or `None` when the child refused to run it.
    fn try_probe(configuration: &ChildConfiguration, report: &Path) -> Option<Vec<PathBuf>> {
        let status = configuration
            .command()
            .arg("-c")
            .arg(PROBE)
            .arg(report)
            .status()
            .unwrap();
        status.success().then(|| read_report(report))
    }

    fn probe(configuration: &ChildConfiguration, report: &Path) -> Vec<PathBuf> {
        try_probe(configuration, report).expect("the probe child succeeds")
    }

    fn run(program: Program, launch: &Launch) -> Option<u32> {
        let (sink, frames) = collector();
        let session = Session::start(program, 120, 40, sink, launch.diagnostics.clone()).unwrap();
        let mut screen = Screen::new(frames, &session);
        screen.exit(WAIT)
    }

    fn assert_resolves(values: &[PathBuf], storage: &Path, cwd: &Path) {
        assert_eq!(values[0], storage, "configured_storage_root");
        assert_eq!(values[1], storage, "Settings.cadrumo_local_storage_root");
        assert!(same_path(&values[2], cwd), "child working directory");
    }

    fn child(
        launch: &Launch,
        directory: &Path,
        environment: BTreeMap<OsString, OsString>,
    ) -> ChildConfiguration {
        ChildConfiguration::new(
            launch.child.executable().to_owned(),
            directory.to_owned(),
            environment,
        )
        .unwrap()
    }

    #[tokio::test]
    async fn every_child_kind_resolves_the_explicit_storage_root_from_any_directory() {
        let scratch = outside_project("relocated");
        let package_root = scratch.0.join("package");
        relocate(&package(), &package_root);
        let explicit = scratch.0.join("storage");
        let inside = explicit.join("inside");
        let launch_directory = scratch.0.join("launch");
        let outside = scratch.0.join("outside");
        let reports = scratch.0.join("reports");
        for directory in [&inside, &launch_directory, &outside, &reports] {
            fs::create_dir_all(directory).unwrap();
        }
        let storage_names = settings_storage_names();
        let variable = root_variable();
        assert!(
            storage_names.contains(&variable),
            "{variable} is not a storage variable"
        );
        let mut environment: Vec<(OsString, OsString)> = std::env::vars_os()
            .filter(|(key, _)| !storage_name(key, &storage_names))
            .collect();
        environment.push((variable.into(), explicit.clone().into()));
        let parent = Parent {
            environment,
            working_directory: launch_directory.clone(),
        };
        let launch = environment::resolve(
            package_root.clone(),
            &parent,
            Arc::new(Diagnostics::default()),
        )
        .await
        .unwrap();
        assert_eq!(launch.working_directory, explicit, "projected storage root");
        let pinned: Vec<_> = launch
            .child
            .environment()
            .iter()
            .filter(|(key, _)| storage_name(key, &storage_names))
            .map(|(_, value)| PathBuf::from(value))
            .collect();
        assert_eq!(pinned, std::slice::from_ref(&explicit));

        // Every terminal kind, through its own launch configuration.
        for kind in [Kind::Python, Kind::Tui] {
            let report = reports.join("kind.json");
            let program = Program {
                arguments: arguments(&["-u", "-c", PROBE, &report.to_string_lossy()]),
                ..Program::for_kind(&launch, kind).unwrap()
            };
            let directory = program.directory.clone();
            assert_eq!(run(program, &launch), Some(0), "{kind:?} exit");
            let expected = if kind == Kind::Tui {
                &explicit
            } else {
                &launch.home
            };
            assert!(same_path(&directory, expected), "{kind:?} directory");
            assert_resolves(&read_report(&report), &explicit, expected);
        }
        // Children whose working directory lies inside and outside the root.
        for (directory, name) in [(&inside, "inside.json"), (&outside, "outside.json")] {
            let configuration = child(&launch, directory, launch.child.environment().clone());
            assert_resolves(
                &probe(&configuration, &reports.join(name)),
                &explicit,
                directory,
            );
        }

        // The CLI passthrough keeps the caller's directory.
        let passthrough = crate::headless(&launch, launch_directory.clone()).unwrap();
        assert_resolves(
            &probe(&passthrough, &reports.join("passthrough.json")),
            &explicit,
            &launch_directory,
        );
        let version = passthrough
            .command()
            .args(["-u", "-c", crate::CLI_ENTRYPOINT, "--version"])
            .output()
            .unwrap();
        assert!(version.status.success());

        for directory in [
            &explicit,
            &inside,
            &outside,
            &launch_directory,
            &package_root,
        ] {
            assert!(
                !directory.join("var").exists(),
                "a child resolved a second storage root beneath {directory:?}"
            );
        }

        // Falsifier: without the pin the children no longer agree on the
        // explicit root, whether they resolve another root or refuse.
        let mut unpinned = launch.child.environment().clone();
        unpinned.retain(|key, _| !storage_name(key, &storage_names));
        for (directory, name) in [
            (&inside, "unpinned-inside.json"),
            (&outside, "unpinned-outside.json"),
        ] {
            let configuration = child(&launch, directory, unpinned.clone());
            if let Some(values) = try_probe(&configuration, &reports.join(name)) {
                assert_ne!(values[0], explicit, "unpinned child in {directory:?}");
                assert_ne!(values[1], explicit, "unpinned child in {directory:?}");
            }
        }
    }

    /// The storage member the generated contract declares for the webview
    /// profile.
    fn webview_member() -> serde_json::Value {
        contract()["locations"]
            .as_array()
            .unwrap()
            .iter()
            .find(|location| location["category"] == "desktop-webview")
            .cloned()
            .expect("the contract declares the desktop webview member")
    }

    /// Resolves a launch with the parent's storage variables replaced by `pins`.
    async fn resolve_pinned(
        package_root: &Path,
        launch_directory: &Path,
        pins: &[(&str, &Path)],
    ) -> Launch {
        let storage_names = settings_storage_names();
        let mut environment: Vec<(OsString, OsString)> = std::env::vars_os()
            .filter(|(key, _)| !storage_name(key, &storage_names))
            .collect();
        for (name, value) in pins {
            assert!(
                storage_names.iter().any(|owned| owned == name),
                "{name} is not a storage variable"
            );
            environment.push(((*name).into(), (*value).into()));
        }
        let parent = Parent {
            environment,
            working_directory: launch_directory.to_owned(),
        };
        environment::resolve(
            package_root.to_owned(),
            &parent,
            Arc::new(Diagnostics::default()),
        )
        .await
        .unwrap()
    }

    /// The webview profile and the window state live in the declared storage
    /// member beneath the explicit root, not under the development tool cache,
    /// and an absolute override of that member is honoured.
    #[tokio::test]
    async fn the_webview_profile_and_window_state_live_in_the_declared_member() {
        use crate::shell::window_state::{self, Placement};

        let scratch = outside_project("webview");
        let package_root = scratch.0.join("package");
        relocate(&package(), &package_root);
        let explicit = scratch.0.join("storage");
        let launch_directory = scratch.0.join("launch");
        fs::create_dir_all(&launch_directory).unwrap();
        let member = webview_member();
        let root = root_variable();

        let launch = resolve_pinned(&package_root, &launch_directory, &[(&root, &explicit)]).await;
        assert_eq!(launch.working_directory, explicit, "projected storage root");
        assert_eq!(
            launch.webview,
            explicit.join(member["subpath"].as_str().unwrap()),
            "webview profile"
        );

        // The window state round-trips through the record the shell opens there.
        let record = launch.webview.join(window_state::FILE);
        let placements = BTreeMap::from([(
            "main".to_owned(),
            Placement {
                x: -1200,
                y: 40,
                width: 1440,
                height: 900,
                maximized: true,
            },
        )]);
        window_state::save(&record, &placements).unwrap();
        assert_eq!(window_state::load(&record), placements);
        assert_eq!(
            fs::read_dir(&launch.webview)
                .unwrap()
                .map(|entry| entry.unwrap().file_name())
                .collect::<Vec<_>>(),
            [window_state::FILE]
        );

        // The member is declared operator-overridable, so its absolute
        // override moves the profile while the storage root stays put.
        assert_eq!(member["override_policy"], "operator_overridable");
        let variable = member["variable"].as_str().unwrap();
        let elsewhere = scratch.0.join("elsewhere").join("profile");
        let overridden = resolve_pinned(
            &package_root,
            &launch_directory,
            &[(&root, &explicit), (variable, &elsewhere)],
        )
        .await;
        assert_eq!(
            overridden.working_directory, explicit,
            "projected storage root"
        );
        assert_eq!(overridden.webview, elsewhere, "overridden webview profile");
    }
}
