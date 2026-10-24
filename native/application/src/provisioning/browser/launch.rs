//! One bounded headless launch of a browser executable, reading the version it reports.
//!
//! The browser starts with a throwaway profile, no first-run work, and its DevTools
//! endpoint on a loopback port it picks itself and announces on standard error. The engine
//! connects to that endpoint, asks for the browser's version over the DevTools protocol,
//! and then asks it to close, which also ends every process it started. The browser runs
//! without a console window, with only the environment the owner supplies, and on Unix in
//! a process group of its own. The engine waits for the browser's standard error to end,
//! which on Unix also waits for every process that inherited it. A browser that does not
//! answer or close within the budget is killed and reaped; that a kill also ends what the
//! browser started rests on the owner's process containment, a kill-on-close job on
//! Windows.

use crate::component::Cancellation;
use std::{
    collections::BTreeMap,
    ffi::OsString,
    fs,
    hash::BuildHasher,
    io::{self, BufRead, BufReader, Read, Write},
    net::{IpAddr, Ipv4Addr, Ipv6Addr, SocketAddr, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicU64, Ordering},
        mpsc,
    },
    thread,
    time::{Duration, Instant},
};

/// The longest standard error line read for the announcement; longer lines are drained.
const LINE_LIMIT: u64 = 4096;
/// The longest DevTools message read.
const MESSAGE_LIMIT: u64 = 1024 * 1024;
const HANDSHAKE_LIMIT: usize = 16 * 1024;
const ANNOUNCEMENT: &str = "DevTools listening on ";

/// The switches every launch passes before the page: the same headless defaults the
/// driver uses, so the check exercises the browser as the consumer will.
const SWITCHES: &[&str] = &[
    "--headless",
    "--remote-debugging-port=0",
    "--no-first-run",
    "--no-default-browser-check",
    "--no-sandbox",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-crash-reporter",
    "--disable-breakpad",
    "--disable-extensions",
    "--disable-sync",
    "--metrics-recording-only",
    "--password-store=basic",
    "--use-mock-keychain",
];

/// Why a launch reported no version, in closed words that carry no browser text.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LaunchFailure {
    /// The executable could not be started.
    Unrunnable,
    /// It was refused permission to start.
    NotPermitted,
    /// It ended before it announced its endpoint.
    Exited,
    /// It did not announce, answer or close within the budget.
    TimedOut,
    /// Its endpoint did not speak the protocol, or named no version.
    NoVersion,
    /// The throwaway profile could not be made.
    ProfileUnavailable,
    Cancelled,
}

/// The browser program one launch runs and the environment it runs with.
pub(super) struct Program<'a> {
    pub executable: &'a Path,
    /// Arguments placed before the switches; empty for a browser.
    pub leading: &'a [OsString],
    pub environment: &'a BTreeMap<OsString, OsString>,
}

/// Launches `program` headless with a profile made inside `scratch`, and returns the
/// version it reports. Nothing it started is left running when this returns.
pub(super) fn browser_version(
    program: &Program<'_>,
    scratch: &Path,
    budget: Duration,
    cancellation: &Cancellation,
) -> Result<String, LaunchFailure> {
    cancellation.check().map_err(|_| LaunchFailure::Cancelled)?;
    let deadline = Instant::now() + budget;
    let profile = Profile::new(scratch)?;
    let mut command = Command::new(program.executable);
    command
        .args(program.leading)
        .args(SWITCHES)
        .arg({
            let mut switch = OsString::from("--user-data-dir=");
            switch.push(profile.path.as_os_str());
            switch
        })
        .arg("about:blank")
        .current_dir(&profile.path)
        .env_clear()
        .envs(program.environment)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        command.creation_flags(CREATE_NO_WINDOW);
    }
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        command.process_group(0);
    }
    let child = crate::process::creation::run(|| command.spawn()).map_err(|error| {
        if error.kind() == io::ErrorKind::PermissionDenied {
            LaunchFailure::NotPermitted
        } else {
            LaunchFailure::Unrunnable
        }
    })?;
    let mut running = Running::new(child)?;
    let result = running.version(deadline, cancellation);
    running.close(deadline);
    drop(profile);
    result
}

/// The throwaway profile folder, removed when dropped.
struct Profile {
    path: PathBuf,
}

impl Profile {
    fn new(scratch: &Path) -> Result<Self, LaunchFailure> {
        static LAUNCHES: AtomicU64 = AtomicU64::new(0);
        let launch = LAUNCHES.fetch_add(1, Ordering::Relaxed);
        let path = scratch.join(format!(
            "cadrumo-browser-check-{}-{launch}",
            std::process::id()
        ));
        crate::filesystem::refuse_links(scratch).map_err(|_| LaunchFailure::ProfileUnavailable)?;
        fs::create_dir_all(scratch).map_err(|_| LaunchFailure::ProfileUnavailable)?;
        fs::create_dir(&path).map_err(|_| LaunchFailure::ProfileUnavailable)?;
        Ok(Self { path })
    }
}

impl Drop for Profile {
    fn drop(&mut self) {
        // The browser has been reaped; a file a late helper still holds stays behind in
        // the owner's temporary folder rather than failing the check.
        if crate::filesystem::refuse_links(&self.path).is_ok() {
            let _ = fs::remove_dir_all(&self.path);
        }
    }
}

enum Announced {
    Endpoint(String),
    Ended,
}

/// A launched browser: its process and what its standard error has said.
struct Running {
    child: Option<Child>,
    said: mpsc::Receiver<Announced>,
    ended: bool,
}

impl Running {
    fn new(mut child: Child) -> Result<Self, LaunchFailure> {
        let Some(stderr) = child.stderr.take() else {
            let _ = child.kill();
            let _ = child.wait();
            return Err(LaunchFailure::Unrunnable);
        };
        let (sender, said) = mpsc::channel();
        // Reads every line so the browser never blocks on a full pipe, reports the first
        // announcement, and reports the end of the stream.
        thread::spawn(move || {
            let mut reader = BufReader::new(stderr);
            let mut line = Vec::new();
            let mut announced = false;
            loop {
                line.clear();
                match reader
                    .by_ref()
                    .take(LINE_LIMIT)
                    .read_until(b'\n', &mut line)
                {
                    Ok(0) | Err(_) => break,
                    Ok(_) if !announced => {
                        if let Some(endpoint) = endpoint_of(&line) {
                            announced = true;
                            let _ = sender.send(Announced::Endpoint(endpoint));
                        }
                    }
                    Ok(_) => {}
                }
            }
            let _ = sender.send(Announced::Ended);
        });
        Ok(Self {
            child: Some(child),
            said,
            ended: false,
        })
    }

    fn version(
        &mut self,
        deadline: Instant,
        cancellation: &Cancellation,
    ) -> Result<String, LaunchFailure> {
        let endpoint = match self.said.recv_timeout(left(deadline)) {
            Ok(Announced::Endpoint(endpoint)) => endpoint,
            Ok(Announced::Ended) | Err(mpsc::RecvTimeoutError::Disconnected) => {
                self.ended = true;
                return Err(LaunchFailure::Exited);
            }
            Err(mpsc::RecvTimeoutError::Timeout) => return Err(LaunchFailure::TimedOut),
        };
        cancellation.check().map_err(|_| LaunchFailure::Cancelled)?;
        devtools_version(&endpoint, deadline)
    }

    /// Waits for the browser to close, until `deadline`, then kills and reaps it.
    fn close(&mut self, deadline: Instant) {
        if !self.ended {
            self.ended = matches!(
                self.said.recv_timeout(left(deadline)),
                Ok(Announced::Ended) | Err(mpsc::RecvTimeoutError::Disconnected)
            );
        }
        if let Some(mut child) = self.child.take() {
            if !matches!(child.try_wait(), Ok(Some(_))) {
                let _ = child.kill();
            }
            let _ = child.wait();
        }
    }
}

impl Drop for Running {
    fn drop(&mut self) {
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

fn left(deadline: Instant) -> Duration {
    deadline.saturating_duration_since(Instant::now())
}

/// The DevTools endpoint a standard error line announces, when it names a loopback one.
fn endpoint_of(line: &[u8]) -> Option<String> {
    let text = std::str::from_utf8(line).ok()?.trim();
    let endpoint = text.strip_prefix(ANNOUNCEMENT)?;
    let rest = endpoint.strip_prefix("ws://")?;
    let (authority, path) = rest.split_once('/')?;
    loopback(authority)?;
    path.bytes()
        .all(|c| c.is_ascii_alphanumeric() || b"/-_".contains(&c))
        .then(|| endpoint.to_owned())
}

/// The loopback address an endpoint authority names; any other host is refused.
fn loopback(authority: &str) -> Option<SocketAddr> {
    let (host, port) = authority.rsplit_once(':')?;
    let ip = match host {
        "127.0.0.1" => IpAddr::V4(Ipv4Addr::LOCALHOST),
        "[::1]" => IpAddr::V6(Ipv6Addr::LOCALHOST),
        _ => return None,
    };
    Some(SocketAddr::new(
        ip,
        port.parse().ok().filter(|port| *port != 0)?,
    ))
}

/// Asks the browser at `endpoint` for its version, then asks it to close.
fn devtools_version(endpoint: &str, deadline: Instant) -> Result<String, LaunchFailure> {
    let rest = endpoint
        .strip_prefix("ws://")
        .ok_or(LaunchFailure::NoVersion)?;
    let (authority, path) = rest.split_once('/').ok_or(LaunchFailure::NoVersion)?;
    let address = loopback(authority).ok_or(LaunchFailure::NoVersion)?;
    let timed_out = |error: io::Error| match error.kind() {
        io::ErrorKind::TimedOut | io::ErrorKind::WouldBlock => LaunchFailure::TimedOut,
        _ => LaunchFailure::NoVersion,
    };
    let budget = left(deadline);
    if budget.is_zero() {
        return Err(LaunchFailure::TimedOut);
    }
    let stream = TcpStream::connect_timeout(&address, budget).map_err(timed_out)?;
    let mut socket = Socket::open(stream, authority, path, deadline).map_err(timed_out)?;
    socket
        .send(br#"{"id":1,"method":"Browser.getVersion"}"#, deadline)
        .map_err(timed_out)?;
    let product = loop {
        let message = socket.receive(deadline).map_err(timed_out)?;
        let Ok(value) = serde_json::from_slice::<serde_json::Value>(&message) else {
            return Err(LaunchFailure::NoVersion);
        };
        if value.get("id").and_then(serde_json::Value::as_u64) == Some(1) {
            break value
                .pointer("/result/product")
                .and_then(serde_json::Value::as_str)
                .map(str::to_owned)
                .ok_or(LaunchFailure::NoVersion)?;
        }
    };
    // The browser closes itself and everything it started; a refusal here leaves the kill.
    let _ = socket.send(br#"{"id":2,"method":"Browser.close"}"#, deadline);
    version_of(&product).ok_or(LaunchFailure::NoVersion)
}

/// `156.0.8078.4` from a product such as `HeadlessChrome/156.0.8078.4`.
fn version_of(product: &str) -> Option<String> {
    let (_, version) = product.split_once('/')?;
    (!version.is_empty()
        && version.len() <= 64
        && version.bytes().all(|c| c.is_ascii_digit() || c == b'.'))
    .then(|| version.to_owned())
}

/// A client WebSocket over one loopback connection, enough for request and answer.
struct Socket {
    reader: BufReader<TcpStream>,
    masks: std::hash::RandomState,
    sent: u64,
}

impl Socket {
    /// Opens the WebSocket. The accept key is not checked: the peer is the child this
    /// launch started, at the loopback address it announced, and no proxy is in between.
    fn open(stream: TcpStream, authority: &str, path: &str, deadline: Instant) -> io::Result<Self> {
        let masks = std::hash::RandomState::new();
        let key = base64(
            &[
                masks.hash_one(1u8).to_le_bytes(),
                masks.hash_one(2u8).to_le_bytes(),
            ]
            .concat(),
        );
        let mut socket = Self {
            reader: BufReader::new(stream),
            masks,
            sent: 2,
        };
        socket.deadline(deadline)?;
        let request = format!(
            "GET /{path} HTTP/1.1\r\nHost: {authority}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        );
        socket.reader.get_mut().write_all(request.as_bytes())?;
        let mut head = 0usize;
        let mut status = String::new();
        loop {
            let mut line = String::new();
            let read = socket
                .reader
                .by_ref()
                .take(HANDSHAKE_LIMIT as u64)
                .read_line(&mut line)?;
            head += read;
            if read == 0 || head > HANDSHAKE_LIMIT {
                return Err(io::Error::from(io::ErrorKind::InvalidData));
            }
            if status.is_empty() {
                status = line;
            } else if line == "\r\n" {
                break;
            }
        }
        if !status.starts_with("HTTP/1.1 101") {
            return Err(io::Error::from(io::ErrorKind::InvalidData));
        }
        Ok(socket)
    }

    fn deadline(&mut self, deadline: Instant) -> io::Result<()> {
        let budget = left(deadline);
        if budget.is_zero() {
            return Err(io::Error::from(io::ErrorKind::TimedOut));
        }
        let stream = self.reader.get_mut();
        stream.set_read_timeout(Some(budget))?;
        stream.set_write_timeout(Some(budget))
    }

    fn send(&mut self, text: &[u8], deadline: Instant) -> io::Result<()> {
        self.frame(0x1, text, deadline)
    }

    fn frame(&mut self, opcode: u8, payload: &[u8], deadline: Instant) -> io::Result<()> {
        self.deadline(deadline)?;
        self.sent += 1;
        let mask = (self.masks.hash_one(self.sent) as u32).to_le_bytes();
        let mut frame = vec![0x80 | opcode];
        match payload.len() {
            length @ 0..126 => frame.push(0x80 | length as u8),
            length @ 126..=0xffff => {
                frame.push(0x80 | 126);
                frame.extend_from_slice(&(length as u16).to_be_bytes());
            }
            length => {
                frame.push(0x80 | 127);
                frame.extend_from_slice(&(length as u64).to_be_bytes());
            }
        }
        frame.extend_from_slice(&mask);
        frame.extend(
            payload
                .iter()
                .enumerate()
                .map(|(i, byte)| byte ^ mask[i % 4]),
        );
        self.reader.get_mut().write_all(&frame)
    }

    /// The next whole text message, answering pings and joining fragments.
    fn receive(&mut self, deadline: Instant) -> io::Result<Vec<u8>> {
        let mut message = Vec::new();
        loop {
            self.deadline(deadline)?;
            let mut head = [0u8; 2];
            self.reader.read_exact(&mut head)?;
            let finished = head[0] & 0x80 != 0;
            let opcode = head[0] & 0x0f;
            let mut length = u64::from(head[1] & 0x7f);
            if length == 126 {
                let mut wide = [0u8; 2];
                self.reader.read_exact(&mut wide)?;
                length = u64::from(u16::from_be_bytes(wide));
            } else if length == 127 {
                let mut wide = [0u8; 8];
                self.reader.read_exact(&mut wide)?;
                length = u64::from_be_bytes(wide);
            }
            if length > MESSAGE_LIMIT.saturating_sub(message.len() as u64) {
                return Err(io::Error::from(io::ErrorKind::InvalidData));
            }
            let mut mask = None;
            if head[1] & 0x80 != 0 {
                let mut key = [0u8; 4];
                self.reader.read_exact(&mut key)?;
                mask = Some(key);
            }
            let mut payload = vec![0u8; length as usize];
            self.reader.read_exact(&mut payload)?;
            if let Some(key) = mask {
                for (i, byte) in payload.iter_mut().enumerate() {
                    *byte ^= key[i % 4];
                }
            }
            match opcode {
                0x0 | 0x1 => {
                    message.extend_from_slice(&payload);
                    if finished {
                        return Ok(message);
                    }
                }
                0x9 => self.frame(0xA, &payload, deadline)?,
                0xA => {}
                _ => return Err(io::Error::from(io::ErrorKind::ConnectionAborted)),
            }
        }
    }
}

fn base64(bytes: &[u8]) -> String {
    const ALPHABET: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(bytes.len().div_ceil(3) * 4);
    for chunk in bytes.chunks(3) {
        let value = u32::from(chunk[0]) << 16
            | u32::from(*chunk.get(1).unwrap_or(&0)) << 8
            | u32::from(*chunk.get(2).unwrap_or(&0));
        for index in 0..4 {
            if index <= chunk.len() {
                out.push(char::from(
                    ALPHABET[(value >> (18 - 6 * index) & 0x3f) as usize],
                ));
            } else {
                out.push('=');
            }
        }
    }
    out
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;

    /// The environment variable that turns [`fake_browser`] on in a child test process,
    /// with the behaviour to play: `version=<v>`, `exit` or `silent`.
    pub(crate) const FAKE_BROWSER: &str = "CADRUMO_TEST_FAKE_BROWSER";
    const FAKE_TEST: &str = "provisioning::browser::launch::tests::fake_browser";

    /// The arguments that make this test binary play the browser: run only the fake,
    /// uncaptured, and read every browser argument after `--` as a test filter that
    /// matches nothing else.
    pub(crate) fn fake_leading() -> Vec<OsString> {
        [
            "--exact",
            FAKE_TEST,
            "--nocapture",
            "--test-threads=1",
            "--",
        ]
        .map(OsString::from)
        .to_vec()
    }

    pub(crate) fn fake_environment(behaviour: &str) -> BTreeMap<OsString, OsString> {
        let mut environment: BTreeMap<OsString, OsString> = std::env::vars_os().collect();
        environment.insert(FAKE_BROWSER.into(), behaviour.into());
        environment
    }

    /// Plays a browser for a launch from another test: it checks the switches it was
    /// given, announces a loopback DevTools endpoint on standard error, answers the
    /// version request and exits when asked to close. Does nothing unless started as
    /// that browser.
    #[test]
    fn fake_browser() {
        let Some(behaviour) = std::env::var_os(FAKE_BROWSER) else {
            return;
        };
        let behaviour = behaviour.into_string().unwrap();
        let arguments: Vec<String> = std::env::args().collect();
        let profile = arguments
            .iter()
            .find_map(|argument| argument.strip_prefix("--user-data-dir="))
            .expect("a profile folder");
        assert!(Path::new(profile).is_dir());
        assert!(
            arguments
                .iter()
                .any(|argument| argument == "--remote-debugging-port=0")
        );
        assert_eq!(arguments.last().map(String::as_str), Some("about:blank"));
        if behaviour == "silent" {
            return;
        }
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let mut stderr = io::stderr();
        writeln!(stderr, "[0101/000000.000:INFO] warming up").unwrap();
        writeln!(
            stderr,
            "{ANNOUNCEMENT}ws://127.0.0.1:{port}/devtools/browser/fake-id"
        )
        .unwrap();
        stderr.flush().unwrap();
        let (stream, _) = listener.accept().unwrap();
        let mut reader = BufReader::new(stream);
        let mut line = String::new();
        reader.read_line(&mut line).unwrap();
        assert_eq!(line, "GET /devtools/browser/fake-id HTTP/1.1\r\n");
        loop {
            line.clear();
            reader.read_line(&mut line).unwrap();
            if line == "\r\n" {
                break;
            }
        }
        reader
            .get_mut()
            .write_all(b"HTTP/1.1 101 WebSocket Protocol Handshake\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n")
            .unwrap();
        if behaviour == "exit" {
            std::process::exit(0);
        }
        let version = behaviour.strip_prefix("version=").unwrap();
        loop {
            let request = read_client_frame(&mut reader);
            let request: serde_json::Value = serde_json::from_slice(&request).unwrap();
            let id = request["id"].as_u64().unwrap();
            let answer = match request["method"].as_str().unwrap() {
                "Browser.getVersion" => serde_json::json!({"id": id, "result": {
                    "protocolVersion": "1.3", "product": format!("HeadlessChrome/{version}"),
                    "revision": "@fake", "userAgent": "fake", "jsVersion": "1"}}),
                "Browser.close" => std::process::exit(0),
                other => panic!("unexpected method {other}"),
            };
            // An event first, as a real browser may send, then the answer in two fragments.
            write_server_frame(
                reader.get_mut(),
                0x1,
                true,
                br#"{"method":"Target.targetCreated","params":{}}"#,
            );
            let text = answer.to_string().into_bytes();
            let (first, second) = text.split_at(text.len() / 2);
            write_server_frame(reader.get_mut(), 0x1, false, first);
            write_server_frame(reader.get_mut(), 0x0, true, second);
        }
    }

    fn read_client_frame(reader: &mut BufReader<TcpStream>) -> Vec<u8> {
        let mut head = [0u8; 2];
        reader.read_exact(&mut head).unwrap();
        assert_eq!(head[0], 0x81, "one final text frame");
        assert_ne!(head[1] & 0x80, 0, "a client frame is masked");
        let length = usize::from(head[1] & 0x7f);
        assert!(length < 126);
        let mut key = [0u8; 4];
        reader.read_exact(&mut key).unwrap();
        let mut payload = vec![0u8; length];
        reader.read_exact(&mut payload).unwrap();
        payload
            .iter_mut()
            .enumerate()
            .for_each(|(i, byte)| *byte ^= key[i % 4]);
        payload
    }

    fn write_server_frame(stream: &mut TcpStream, opcode: u8, finished: bool, payload: &[u8]) {
        let mut frame = vec![if finished { 0x80 } else { 0 } | opcode];
        if payload.len() < 126 {
            frame.push(payload.len() as u8);
        } else {
            frame.push(126);
            frame.extend_from_slice(&(payload.len() as u16).to_be_bytes());
        }
        frame.extend_from_slice(payload);
        stream.write_all(&frame).unwrap();
    }

    fn launch(behaviour: &str, scratch: &Path, budget: Duration) -> Result<String, LaunchFailure> {
        let executable = std::env::current_exe().unwrap();
        let leading = fake_leading();
        let environment = fake_environment(behaviour);
        browser_version(
            &Program {
                executable: &executable,
                leading: &leading,
                environment: &environment,
            },
            scratch,
            budget,
            &Cancellation::default(),
        )
    }

    #[test]
    fn a_launch_reads_the_reported_version_and_the_browser_closes_itself() {
        let scratch = tempfile::tempdir().unwrap();
        assert_eq!(
            launch(
                "version=156.0.8078.4",
                scratch.path(),
                Duration::from_secs(60)
            ),
            Ok("156.0.8078.4".to_owned())
        );
        assert_eq!(
            fs::read_dir(scratch.path()).unwrap().count(),
            0,
            "the throwaway profile is removed"
        );
    }

    #[test]
    fn a_browser_that_ends_or_answers_nothing_reports_no_version() {
        let scratch = tempfile::tempdir().unwrap();
        assert_eq!(
            launch("silent", scratch.path(), Duration::from_secs(60)),
            Err(LaunchFailure::Exited)
        );
        assert_eq!(
            launch("exit", scratch.path(), Duration::from_secs(60)),
            Err(LaunchFailure::NoVersion)
        );
        let missing = scratch.path().join("no-such-browser");
        let environment = BTreeMap::new();
        assert_eq!(
            browser_version(
                &Program {
                    executable: &missing,
                    leading: &[],
                    environment: &environment,
                },
                scratch.path(),
                Duration::from_secs(60),
                &Cancellation::default(),
            ),
            Err(LaunchFailure::Unrunnable)
        );
        let cancelled = Cancellation::default();
        cancelled.cancel();
        assert_eq!(
            browser_version(
                &Program {
                    executable: &missing,
                    leading: &[],
                    environment: &environment,
                },
                scratch.path(),
                Duration::from_secs(60),
                &cancelled,
            ),
            Err(LaunchFailure::Cancelled)
        );
        assert_eq!(fs::read_dir(scratch.path()).unwrap().count(), 0);
    }

    #[test]
    fn only_a_loopback_endpoint_announcement_is_followed() {
        for (line, expected) in [
            (
                "DevTools listening on ws://127.0.0.1:9222/devtools/browser/0b1c-2d\n",
                Some("ws://127.0.0.1:9222/devtools/browser/0b1c-2d"),
            ),
            (
                "DevTools listening on ws://[::1]:9222/devtools/browser/x\r\n",
                Some("ws://[::1]:9222/devtools/browser/x"),
            ),
            (
                "DevTools listening on ws://example.com:9222/devtools/browser/x",
                None,
            ),
            (
                "DevTools listening on ws://127.0.0.1:0/devtools/browser/x",
                None,
            ),
            (
                "DevTools listening on ws://127.0.0.1:9222/devtools/browser/x?y",
                None,
            ),
            (
                "DevTools listening on wss://127.0.0.1:9222/devtools/browser/x",
                None,
            ),
            ("[INFO] DevTools listening on ws://127.0.0.1:9222/x", None),
        ] {
            assert_eq!(endpoint_of(line.as_bytes()).as_deref(), expected, "{line}");
        }
        assert_eq!(
            version_of("HeadlessChrome/156.0.8078.4").as_deref(),
            Some("156.0.8078.4")
        );
        assert_eq!(version_of("HeadlessChrome/156.0.x"), None);
        assert_eq!(version_of("HeadlessChrome"), None);
        assert_eq!(base64(b"Man"), "TWFu");
        assert_eq!(base64(b"Ma"), "TWE=");
        assert_eq!(base64(b"M"), "TQ==");
        assert_eq!(base64(&[0u8; 16]).len(), 24);
    }
}
