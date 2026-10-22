//! The application's own connection to the installed runtime.
//!
//! A runtime owns a storage root and serves it over one native pipe. This
//! module derives that pipe's name from the root, connects as the runtime's
//! verified same-account peer, completes the cohort handshake, and then runs
//! correlated exchanges on the connection while the runtime pushes events
//! between replies. It also reads the proof of a stored sign-in and makes the
//! sign-in, status, activity and sign-out requests a person's frontend makes.
//!
//! A desktop window once started a Python child for each of these: a session
//! hold, a session watch and short `config` commands, each paying an
//! interpreter start and the product's import graph before its first request.
//! The same exchanges run here in the window's own process.
//!
//! Frames are `kind || u32 length || payload`: `J` carries one JSON document,
//! `S` one secret the runtime has said it is ready for, `E` an event the
//! runtime pushes between replies. Every reply names the request it answers,
//! the runtime's boot and this connection; an answer naming another is
//! refused and the connection closed, as the runtime's Python clients do.
//! Nothing here starts, stops or supervises a runtime.

use cadrumo_platform::runtime_pipe::{self, ConnectRefusal, Pipe};
use serde_json::{Map, Value, json};
use sha2::{Digest, Sha256};
use std::{
    io,
    path::Path,
    sync::{
        Arc, Mutex, MutexGuard,
        atomic::{AtomicBool, AtomicU64, Ordering},
        mpsc,
    },
    thread,
    time::{Duration, Instant, SystemTime},
};
use zeroize::Zeroizing;

const PROTOCOL_VERSION: u64 = 3;
const MAXIMUM_FRAME_BYTES: usize = 64 * 1024;
const MAXIMUM_SECRET_BYTES: usize = 64 * 1024;
const DOCUMENT_FRAME: u8 = b'J';
const SECRET_FRAME: u8 = b'S';
const EVENT_FRAME: u8 = b'E';
/// The longest a reply's remaining frames may take once its first frame arrived.
const FRAME_BUDGET: Duration = Duration::from_secs(5);
/// The idle read is re-armed on this cadence so a close is never waited out.
const IDLE_READ: Duration = Duration::from_secs(600);
const TRANSFER_CHUNK_BYTES: usize = 16_384;
const TRANSFER_LIMIT_BYTES: usize = 1_048_576;
const RECEIPT_RECORD_MAX_BYTES: u64 = 8 * 1024;
const RECEIPT_FILENAME: &str = "session.v2.json";
const KEYSTORE_DIRECTORY: &str = "keystore";
const RECEIPT_KEYCHAIN_SERVICE: &str = "cadrumo:profile-session:v2";
const RECEIPT_KEY_BYTES: usize = 32;

/// Why a connection or exchange did not answer. `code` spells it as the
/// runtime's Python clients do, so one refusal vocabulary reaches a window.
#[derive(Debug)]
pub enum Refusal {
    Unavailable,
    EndpointNotReady,
    EndpointUntrusted,
    PeerUntrusted,
    VersionMismatch,
    RootMismatch,
    InvalidFrame,
    ConnectionClosed,
    DeadlineExceeded,
    /// The runtime answered with its typed refusal: an access denial code and,
    /// for a sign-in, the reason it was refused.
    Denied {
        code: String,
        sign_in: Option<Value>,
    },
    Io(io::Error),
}

impl Refusal {
    /// The reason a sign-in was refused, when the runtime gave one: a receipt
    /// refusal reason, `throttled` or `credential_rejected`.
    pub fn sign_in_reason(&self) -> Option<&str> {
        match self {
            Self::Denied {
                sign_in: Some(sign_in),
                ..
            } => sign_in.get("reason").and_then(Value::as_str),
            _ => None,
        }
    }

    /// How long a throttled sign-in must wait, when the runtime said.
    pub fn remaining_seconds(&self) -> Option<u64> {
        match self {
            Self::Denied {
                sign_in: Some(sign_in),
                ..
            } => sign_in.get("remaining_seconds").and_then(Value::as_u64),
            _ => None,
        }
    }

    pub fn code(&self) -> &str {
        match self {
            Self::Unavailable | Self::Io(_) => "runtime_unavailable",
            Self::EndpointNotReady => "runtime_endpoint_not_ready",
            Self::EndpointUntrusted => "runtime_endpoint_untrusted",
            Self::PeerUntrusted => "runtime_peer_untrusted",
            Self::VersionMismatch => "runtime_version_mismatch",
            Self::RootMismatch => "runtime_root_mismatch",
            Self::InvalidFrame => "runtime_invalid_frame",
            Self::ConnectionClosed => "runtime_connection_closed",
            Self::DeadlineExceeded => "runtime_deadline_exceeded",
            Self::Denied { code, .. } => code,
        }
    }
}

impl std::fmt::Display for Refusal {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Io(error) => write!(formatter, "{}: {error}", self.code()),
            _ => formatter.write_str(self.code()),
        }
    }
}

impl std::error::Error for Refusal {}

impl From<io::Error> for Refusal {
    fn from(error: io::Error) -> Self {
        match error.kind() {
            io::ErrorKind::ConnectionAborted
            | io::ErrorKind::UnexpectedEof
            | io::ErrorKind::BrokenPipe
            | io::ErrorKind::NotConnected => Self::ConnectionClosed,
            io::ErrorKind::TimedOut => Self::DeadlineExceeded,
            _ => Self::Io(error),
        }
    }
}

impl From<ConnectRefusal> for Refusal {
    fn from(refusal: ConnectRefusal) -> Self {
        match refusal {
            ConnectRefusal::NotReady => Self::EndpointNotReady,
            ConnectRefusal::PeerUntrusted => Self::PeerUntrusted,
            ConnectRefusal::Deadline => Self::DeadlineExceeded,
            ConnectRefusal::Failed(error) => Self::Io(error),
        }
    }
}

/// The pipe a storage root's runtime serves, derived from the root alone.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Endpoint {
    pub pipe_name: String,
    /// The hex digest both peers compare in the handshake.
    pub storage_identity: String,
    /// The account that owns the root; the runtime's process must be its own.
    pub owner_sid: String,
}

impl Endpoint {
    /// The endpoint of `storage_root`, followed through links as the runtime
    /// follows it. A root that cannot be identified names no endpoint.
    pub fn of(storage_root: &Path) -> Result<Self, Refusal> {
        let identity =
            runtime_pipe::storage_identity(storage_root).map_err(|_| Refusal::EndpointUntrusted)?;
        let storage_identity = sha256_hex(identity.text().as_bytes());
        Ok(Self {
            pipe_name: format!(r"\\.\pipe\cadrumo-runtime-{storage_identity}"),
            storage_identity,
            owner_sid: identity.owner_sid,
        })
    }
}

/// What this process expects the runtime to be: the same installed version
/// and, where both know one, the same published authority generation.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Cohort {
    pub product_version: String,
    pub authority_generation: Option<String>,
}

/// The runtime's readiness, as its handshake stated it. The boot id is not a bearer.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Hello {
    pub boot_id: String,
    pub product_version: String,
    pub storage_identity: String,
    pub authority_generation: Option<String>,
}

/// What the runtime pushed to this connection: a reason to read again,
/// never a value or an authority.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Event {
    /// A watched sign-in or the selection may have changed.
    SignInChanged,
    /// This connection's session ended: `kind` says how, `reason` why.
    SessionRetired {
        kind: String,
        reason: String,
    },
    LanguageChanged,
    RecordsChanged,
    AttendanceChanged,
    AttendanceAnswered,
    OperationChanged,
    PresentationRequested {
        destination: String,
    },
    ServiceLeaseChanged,
    LifecycleNotice,
    ModelRunRequested,
    /// The connection ended; no further reply or event will arrive.
    Disconnected,
}

fn sha256_hex(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn is_uuid(text: &str) -> bool {
    let bytes = text.as_bytes();
    bytes.len() == 36
        && bytes.iter().enumerate().all(|(index, byte)| match index {
            8 | 13 | 18 | 23 => *byte == b'-',
            _ => byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase(),
        })
}

static REQUEST_COUNTER: AtomicU64 = AtomicU64::new(0);

/// A fresh request id in UUID spelling. Replies are correlated by it on one
/// verified connection, so it needs to be distinct, not unguessable.
pub fn request_id() -> String {
    let nanos = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map_or(0, |elapsed| elapsed.as_nanos());
    let counter = REQUEST_COUNTER.fetch_add(1, Ordering::Relaxed);
    let mut hasher = Sha256::new();
    hasher.update(std::process::id().to_le_bytes());
    hasher.update(nanos.to_le_bytes());
    hasher.update(counter.to_le_bytes());
    hasher.update(format!("{:?}", thread::current().id()).as_bytes());
    let digest = hasher.finalize();
    let mut bytes = [0u8; 16];
    bytes.copy_from_slice(&digest[..16]);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    let hex: String = bytes.iter().map(|byte| format!("{byte:02x}")).collect();
    format!(
        "{}-{}-{}-{}-{}",
        &hex[..8],
        &hex[8..12],
        &hex[12..16],
        &hex[16..20],
        &hex[20..]
    )
}

fn frame(kind: u8, payload: &[u8]) -> Result<Vec<u8>, Refusal> {
    let limit = if kind == SECRET_FRAME {
        MAXIMUM_SECRET_BYTES
    } else {
        MAXIMUM_FRAME_BYTES
    };
    if payload.is_empty() || payload.len() > limit {
        return Err(Refusal::InvalidFrame);
    }
    let mut framed = Vec::with_capacity(5 + payload.len());
    framed.push(kind);
    framed.extend_from_slice(&(payload.len() as u32).to_be_bytes());
    framed.extend_from_slice(payload);
    Ok(framed)
}

fn frame_header(header: &[u8; 5]) -> Result<(u8, usize), Refusal> {
    let size = u32::from_be_bytes([header[1], header[2], header[3], header[4]]) as usize;
    if !matches!(header[0], DOCUMENT_FRAME | EVENT_FRAME) || size == 0 || size > MAXIMUM_FRAME_BYTES
    {
        return Err(Refusal::InvalidFrame);
    }
    Ok((header[0], size))
}

/// Reads one frame: its header within `header_deadline`, its payload within
/// [`FRAME_BUDGET`] of the header.
fn read_frame(pipe: &Pipe, header_deadline: Instant) -> Result<(u8, Vec<u8>), Refusal> {
    let mut header = [0u8; 5];
    pipe.read_exact(&mut header, header_deadline)?;
    let (kind, size) = frame_header(&header)?;
    let mut payload = vec![0u8; size];
    pipe.read_exact(&mut payload, Instant::now() + FRAME_BUDGET)?;
    Ok((kind, payload))
}

fn document(payload: &[u8]) -> Result<Map<String, Value>, Refusal> {
    match serde_json::from_slice::<Value>(payload) {
        Ok(Value::Object(object)) => Ok(object),
        _ => Err(Refusal::InvalidFrame),
    }
}

fn text<'a>(document: &'a Map<String, Value>, key: &str) -> Option<&'a str> {
    document.get(key).and_then(Value::as_str)
}

/// Decodes standard base64 with padding, refusing anything but the one
/// canonical spelling of the bytes.
pub fn base64_decode(encoded: &str) -> Option<Vec<u8>> {
    fn value(byte: u8) -> Option<u32> {
        Some(match byte {
            b'A'..=b'Z' => u32::from(byte - b'A'),
            b'a'..=b'z' => u32::from(byte - b'a') + 26,
            b'0'..=b'9' => u32::from(byte - b'0') + 52,
            b'+' => 62,
            b'/' => 63,
            _ => return None,
        })
    }
    let bytes = encoded.as_bytes();
    if bytes.is_empty() || !bytes.len().is_multiple_of(4) {
        return None;
    }
    let padding = bytes.iter().rev().take_while(|&&byte| byte == b'=').count();
    if padding > 2 || bytes[..bytes.len() - padding].contains(&b'=') {
        return None;
    }
    let mut decoded = Vec::with_capacity(bytes.len() / 4 * 3);
    for group in bytes.chunks(4) {
        let mut bits = 0u32;
        let mut count = 0;
        for &byte in group {
            if byte == b'=' {
                break;
            }
            bits = (bits << 6) | value(byte)?;
            count += 1;
        }
        let kept = match count {
            4 => 3,
            3 => 2,
            2 => 1,
            _ => return None,
        };
        bits <<= 6 * (4 - count);
        let octets = bits.to_be_bytes();
        // The bits a canonical encoding leaves unused are zero.
        if octets[1 + kept..].iter().any(|&byte| byte != 0) {
            return None;
        }
        decoded.extend_from_slice(&octets[1..1 + kept]);
    }
    Some(decoded)
}

struct Shared {
    connection_id: Mutex<Option<String>>,
    subscribers: Mutex<Vec<mpsc::Sender<Event>>>,
    closed: AtomicBool,
}

impl Shared {
    fn dispatch(&self, event: &Event) {
        self.subscribers
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .retain(|subscriber| subscriber.send(event.clone()).is_ok());
    }

    /// Binds the connection id a reply or event carries, refusing a change.
    fn bind_connection(&self, connection_id: &str) -> Result<(), Refusal> {
        let mut bound = self
            .connection_id
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        match bound.as_deref() {
            Some(current) if current != connection_id => Err(Refusal::InvalidFrame),
            Some(_) => Ok(()),
            None => {
                *bound = Some(connection_id.to_owned());
                Ok(())
            }
        }
    }
}

fn event(document: &Map<String, Value>) -> Event {
    match text(document, "kind") {
        Some("sign_in_changed") => Event::SignInChanged,
        Some("session_event") => Event::SessionRetired {
            kind: text(document, "event").unwrap_or_default().to_owned(),
            reason: text(document, "reason").unwrap_or_default().to_owned(),
        },
        Some("profile_language_changed") => Event::LanguageChanged,
        Some("profile_records_changed") => Event::RecordsChanged,
        Some("attendance_changed") => Event::AttendanceChanged,
        Some("attendance_answered") => Event::AttendanceAnswered,
        Some("operation_changed") => Event::OperationChanged,
        Some("presentation_requested") => Event::PresentationRequested {
            destination: text(document, "destination").unwrap_or_default().to_owned(),
        },
        Some("service_lease_changed") => Event::ServiceLeaseChanged,
        Some("lifecycle_notice") => Event::LifecycleNotice,
        Some("model_run_requested") => Event::ModelRunRequested,
        _ => Event::Disconnected,
    }
}

/// One verified connection: exchanges from any thread, one at a time, and the
/// events the runtime pushes between them.
pub struct Connection {
    pipe: Arc<Pipe>,
    hello: Hello,
    shared: Arc<Shared>,
    exchange: Mutex<mpsc::Receiver<Map<String, Value>>>,
    reader: Mutex<Option<thread::JoinHandle<()>>>,
}

fn hello_document(endpoint: &Endpoint, cohort: &Cohort) -> Value {
    json!({
        "kind": "client_hello",
        "protocol_version": PROTOCOL_VERSION,
        "product_version": cohort.product_version,
        "storage_identity": endpoint.storage_identity,
        "authority_generation": cohort.authority_generation,
        "lifecycle_notices": "v1",
    })
}

fn server_hello(
    document: &Map<String, Value>,
    endpoint: &Endpoint,
    cohort: &Cohort,
) -> Result<Hello, Refusal> {
    if text(document, "kind") != Some("server_hello")
        || document.get("protocol_version").and_then(Value::as_u64) != Some(PROTOCOL_VERSION)
    {
        return Err(Refusal::InvalidFrame);
    }
    let boot_id = text(document, "boot_id")
        .filter(|id| is_uuid(id))
        .ok_or(Refusal::InvalidFrame)?;
    let product_version = text(document, "product_version").ok_or(Refusal::InvalidFrame)?;
    let storage_identity = text(document, "storage_identity").ok_or(Refusal::InvalidFrame)?;
    let authority_generation = text(document, "authority_generation").map(str::to_owned);
    if product_version != cohort.product_version
        || matches!(
            (&authority_generation, &cohort.authority_generation),
            (Some(observed), Some(expected)) if observed != expected
        )
    {
        return Err(Refusal::VersionMismatch);
    }
    if storage_identity != endpoint.storage_identity {
        return Err(Refusal::RootMismatch);
    }
    Ok(Hello {
        boot_id: boot_id.to_owned(),
        product_version: product_version.to_owned(),
        storage_identity: storage_identity.to_owned(),
        authority_generation,
    })
}

fn read_loop(
    pipe: Arc<Pipe>,
    shared: Arc<Shared>,
    replies: mpsc::Sender<Map<String, Value>>,
    boot_id: String,
) {
    loop {
        let (kind, payload) = match read_frame(&pipe, Instant::now() + IDLE_READ) {
            Ok(frame) => frame,
            Err(Refusal::DeadlineExceeded) if !shared.closed.load(Ordering::Acquire) => continue,
            Err(_) => break,
        };
        let Ok(document) = document(&payload) else {
            break;
        };
        if kind == DOCUMENT_FRAME {
            if replies.send(document).is_err() {
                break;
            }
            continue;
        }
        let Some(connection_id) = text(&document, "connection_id") else {
            break;
        };
        if text(&document, "runtime_boot_id") != Some(boot_id.as_str())
            || shared.bind_connection(connection_id).is_err()
        {
            break;
        }
        let pushed = event(&document);
        if pushed == Event::Disconnected {
            break;
        }
        shared.dispatch(&pushed);
    }
    shared.closed.store(true, Ordering::Release);
    pipe.close();
    shared.dispatch(&Event::Disconnected);
}

impl Connection {
    /// Connects to `endpoint` as `cohort` before `deadline`: the peer is
    /// verified, the handshake completed, and the event reader started. No
    /// credential is involved.
    pub fn open(endpoint: &Endpoint, cohort: &Cohort, deadline: Instant) -> Result<Self, Refusal> {
        let pipe = Pipe::connect(&endpoint.pipe_name, &endpoint.owner_sid, deadline)?;
        let payload = serde_json::to_vec(&hello_document(endpoint, cohort))
            .map_err(|_| Refusal::InvalidFrame)?;
        pipe.write_all(&frame(DOCUMENT_FRAME, &payload)?, deadline)?;
        let (kind, payload) = read_frame(&pipe, deadline)?;
        if kind != DOCUMENT_FRAME {
            return Err(Refusal::InvalidFrame);
        }
        let hello = server_hello(&document(&payload)?, endpoint, cohort)?;
        let pipe = Arc::new(pipe);
        let shared = Arc::new(Shared {
            connection_id: Mutex::new(None),
            subscribers: Mutex::new(Vec::new()),
            closed: AtomicBool::new(false),
        });
        let (replies, exchange) = mpsc::channel();
        let reader = {
            let (pipe, shared, boot_id) = (pipe.clone(), shared.clone(), hello.boot_id.clone());
            thread::Builder::new()
                .name("runtime-connection-reader".into())
                .spawn(move || read_loop(pipe, shared, replies, boot_id))
                .map_err(Refusal::Io)?
        };
        Ok(Self {
            pipe,
            hello,
            shared,
            exchange: Mutex::new(exchange),
            reader: Mutex::new(Some(reader)),
        })
    }

    pub fn hello(&self) -> &Hello {
        &self.hello
    }

    /// The id the runtime gave this connection, once a reply or event named it.
    pub fn connection_id(&self) -> Option<String> {
        self.shared
            .connection_id
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .clone()
    }

    pub fn closed(&self) -> bool {
        self.shared.closed.load(Ordering::Acquire)
    }

    /// Every event pushed from now on, ending with [`Event::Disconnected`].
    pub fn subscribe(&self) -> mpsc::Receiver<Event> {
        let (sender, receiver) = mpsc::channel();
        if self.closed() {
            let _ = sender.send(Event::Disconnected);
        } else {
            self.shared
                .subscribers
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner())
                .push(sender);
        }
        receiver
    }

    /// Stops exchanges and ends the connection; the reader thread is joined.
    pub fn close(&self) {
        self.shared.closed.store(true, Ordering::Release);
        self.pipe.close();
        let reader = self
            .reader
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .take();
        if let Some(reader) = reader
            && reader.thread().id() != thread::current().id()
        {
            let _ = reader.join();
        }
    }

    fn fail(&self, refusal: Refusal) -> Refusal {
        if !matches!(refusal, Refusal::Denied { .. }) {
            self.close();
        }
        refusal
    }

    fn claim(
        &self,
        deadline: Instant,
    ) -> Result<MutexGuard<'_, mpsc::Receiver<Map<String, Value>>>, Refusal> {
        let exchange = self
            .exchange
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        if self.closed() {
            return Err(Refusal::ConnectionClosed);
        }
        if Instant::now() >= deadline {
            return Err(Refusal::DeadlineExceeded);
        }
        Ok(exchange)
    }

    fn write(&self, kind: u8, payload: &[u8], deadline: Instant) -> Result<(), Refusal> {
        let framed = Zeroizing::new(frame(kind, payload)?);
        self.pipe.write_all(&framed, deadline)?;
        Ok(())
    }

    fn next_reply(
        &self,
        replies: &mpsc::Receiver<Map<String, Value>>,
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        let remaining = deadline.saturating_duration_since(Instant::now());
        match replies.recv_timeout(remaining) {
            Ok(reply) => Ok(reply),
            Err(mpsc::RecvTimeoutError::Timeout) => Err(Refusal::DeadlineExceeded),
            Err(mpsc::RecvTimeoutError::Disconnected) => Err(Refusal::ConnectionClosed),
        }
    }

    fn verify_reply(&self, reply: &Map<String, Value>, request_id: &str) -> Result<(), Refusal> {
        if text(reply, "request_id") != Some(request_id)
            || text(reply, "runtime_boot_id") != Some(self.hello.boot_id.as_str())
        {
            return Err(Refusal::InvalidFrame);
        }
        let connection_id = text(reply, "connection_id").ok_or(Refusal::InvalidFrame)?;
        self.shared.bind_connection(connection_id)
    }

    /// The reply to `request_id`: verified, a transfer assembled from its
    /// chunks, and a refusal returned as [`Refusal::Denied`].
    fn reply(
        &self,
        replies: &mpsc::Receiver<Map<String, Value>>,
        request_id: &str,
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        let mut reply = self.next_reply(replies, deadline)?;
        self.verify_reply(&reply, request_id)?;
        if text(&reply, "kind").is_some_and(|kind| kind.ends_with("_transfer")) {
            reply = self.assemble_transfer(replies, &reply, request_id)?;
        }
        if text(&reply, "kind") == Some("access_refusal") {
            return Err(Refusal::Denied {
                code: text(&reply, "code").unwrap_or_default().to_owned(),
                sign_in: reply
                    .get("sign_in")
                    .filter(|value| !value.is_null())
                    .cloned(),
            });
        }
        Ok(reply)
    }

    fn assemble_transfer(
        &self,
        replies: &mpsc::Receiver<Map<String, Value>>,
        header: &Map<String, Value>,
        request_id: &str,
    ) -> Result<Map<String, Value>, Refusal> {
        let byte_count = header
            .get("byte_count")
            .and_then(Value::as_u64)
            .filter(|&count| (2..=TRANSFER_LIMIT_BYTES as u64).contains(&count))
            .ok_or(Refusal::InvalidFrame)? as usize;
        let digest = text(header, "payload_digest").ok_or(Refusal::InvalidFrame)?;
        let mut payload = Vec::with_capacity(byte_count);
        while payload.len() < byte_count {
            let chunk = self.next_reply(replies, Instant::now() + FRAME_BUDGET)?;
            let offset = chunk
                .get("offset")
                .and_then(Value::as_u64)
                .ok_or(Refusal::InvalidFrame)?;
            let encoded = text(&chunk, "encoded").ok_or(Refusal::InvalidFrame)?;
            let bytes = base64_decode(encoded).ok_or(Refusal::InvalidFrame)?;
            let expected = (byte_count - payload.len()).min(TRANSFER_CHUNK_BYTES);
            if offset as usize != payload.len() || bytes.len() != expected {
                return Err(Refusal::InvalidFrame);
            }
            payload.extend_from_slice(&bytes);
        }
        if sha256_hex(&payload) != digest {
            return Err(Refusal::InvalidFrame);
        }
        let reply = document(&payload)?;
        self.verify_reply(&reply, request_id)?;
        Ok(reply)
    }

    /// Sends `request`, whose `request_id` the reply must carry, and returns
    /// that reply. A frame the runtime could not have sent closes the connection.
    pub fn exchange(
        &self,
        request: &Value,
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        let request_id = request
            .get("request_id")
            .and_then(Value::as_str)
            .ok_or(Refusal::InvalidFrame)?
            .to_owned();
        let replies = self.claim(deadline)?;
        let payload = serde_json::to_vec(request).map_err(|_| Refusal::InvalidFrame)?;
        self.write(DOCUMENT_FRAME, &payload, deadline)
            .and_then(|()| self.reply(&replies, &request_id, deadline))
            .map_err(|refusal| self.fail(refusal))
    }

    /// Sends `request`, then `secret` once the runtime says it is ready for
    /// it, and returns the final reply. A refusal before readiness never
    /// consumes the secret.
    pub fn exchange_with_secret(
        &self,
        request: &Value,
        secret: &[u8],
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        let request_id = request
            .get("request_id")
            .and_then(Value::as_str)
            .ok_or(Refusal::InvalidFrame)?
            .to_owned();
        let replies = self.claim(deadline)?;
        let payload = serde_json::to_vec(request).map_err(|_| Refusal::InvalidFrame)?;
        let delivered = (|| {
            self.write(DOCUMENT_FRAME, &payload, deadline)?;
            let ready = self.reply(&replies, &request_id, deadline)?;
            if text(&ready, "kind") != Some("secret_ready") {
                return Err(Refusal::InvalidFrame);
            }
            self.write(SECRET_FRAME, secret, deadline)?;
            self.reply(&replies, &request_id, deadline)
        })();
        delivered.map_err(|refusal| self.fail(refusal))
    }
}

impl Drop for Connection {
    fn drop(&mut self) {
        self.close();
    }
}

/// The frontend a sign-in is made from; the runtime decides what each may do.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Frontend {
    Desktop,
    Cli,
    Tui,
}

impl Frontend {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Desktop => "desktop",
            Self::Cli => "cli",
            Self::Tui => "tui",
        }
    }
}

/// A profile's stored sign-in as the runtime observes it: never proof of authentication.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SignInStatus {
    /// `present`, `absent` or `unknown`.
    pub presence: String,
    pub idle_deadline: Option<String>,
    pub absolute_deadline: Option<String>,
}

/// Which profile is selected and which holds the live sign-in.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ActiveProfile {
    pub selected_profile_id: Option<String>,
    pub signed_in_profile_id: Option<String>,
    pub presence: String,
}

/// A session the runtime admitted on this connection.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Admitted {
    pub profile_id: String,
    pub session_id: String,
    pub connection_id: String,
    pub runtime_boot_id: String,
    pub expires_at: Option<String>,
    /// Whether the person's sign-in was stored for other frontends, when the
    /// reply says.
    pub session_persisted: Option<bool>,
    pub signed_out_profile_ids: Vec<String>,
}

/// What a sign-out removed.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SignedOut {
    pub session_ids: Vec<String>,
    pub receipt_removed: bool,
    pub keychain_removed: bool,
    /// The profile's persisted automation setting, which a sign-out keeps; not access.
    pub automation_enabled: Option<bool>,
    /// Whether an issued key can still admit; `None` when the runtime could not say.
    pub automation_access_remains: Option<bool>,
}

fn uuid_list(value: Option<&Value>) -> Vec<String> {
    value
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .map(str::to_owned)
                .collect()
        })
        .unwrap_or_default()
}

fn admitted(reply: &Map<String, Value>, profile_id: &str) -> Result<Admitted, Refusal> {
    if text(reply, "kind") != Some("profile_status") {
        return Err(Refusal::InvalidFrame);
    }
    let status = reply
        .get("status")
        .and_then(Value::as_object)
        .ok_or(Refusal::InvalidFrame)?;
    let flag = |key: &str| status.get(key).and_then(Value::as_bool).unwrap_or(false);
    if let Some(denial) = text(status, "denial") {
        return Err(Refusal::Denied {
            code: denial.to_owned(),
            sign_in: None,
        });
    }
    let session_id = text(status, "session_id");
    if !flag("connected")
        || !flag("credential_authenticated")
        || !flag("profile_bound")
        || text(status, "profile_id") != Some(profile_id)
        || session_id.is_none()
    {
        return Err(Refusal::Denied {
            code: "profile_mismatch".into(),
            sign_in: None,
        });
    }
    Ok(Admitted {
        profile_id: profile_id.to_owned(),
        session_id: session_id.unwrap_or_default().to_owned(),
        connection_id: text(reply, "connection_id").unwrap_or_default().to_owned(),
        runtime_boot_id: text(reply, "runtime_boot_id")
            .unwrap_or_default()
            .to_owned(),
        expires_at: text(status, "session_expires_at").map(str::to_owned),
        session_persisted: reply
            .get("human_login")
            .and_then(Value::as_object)
            .and_then(|login| login.get("session_persisted"))
            .and_then(Value::as_bool),
        signed_out_profile_ids: uuid_list(reply.get("signed_out_profile_ids")),
    })
}

impl Connection {
    /// The stored sign-in of `profile_id`, without admitting a session. With
    /// `watch`, the runtime also pushes [`Event::SignInChanged`] whenever any
    /// sign-in may have changed, until the connection closes.
    pub fn sign_in_status(
        &self,
        profile_id: &str,
        watch: bool,
        deadline: Instant,
    ) -> Result<SignInStatus, Refusal> {
        let reply = self.exchange(
            &json!({
                "action": "sign_in_status",
                "request_id": request_id(),
                "profile_id": profile_id,
                "watch": watch,
            }),
            deadline,
        )?;
        if text(&reply, "kind") != Some("sign_in_status")
            || text(&reply, "profile_id") != Some(profile_id)
        {
            return Err(self.fail(Refusal::InvalidFrame));
        }
        let status = reply
            .get("status")
            .and_then(Value::as_object)
            .ok_or_else(|| self.fail(Refusal::InvalidFrame))?;
        Ok(SignInStatus {
            presence: text(status, "presence").unwrap_or("unknown").to_owned(),
            idle_deadline: text(status, "idle_deadline").map(str::to_owned),
            absolute_deadline: text(status, "absolute_deadline").map(str::to_owned),
        })
    }

    /// Which profile is selected and signed in, on a connection that holds no
    /// session. With `watch`, [`Event::SignInChanged`] follows every change.
    pub fn active_profile(&self, watch: bool, deadline: Instant) -> Result<ActiveProfile, Refusal> {
        let reply = self.exchange(
            &json!({"action": "active_profile", "request_id": request_id(), "watch": watch}),
            deadline,
        )?;
        if text(&reply, "kind") != Some("active_profile") {
            return Err(self.fail(Refusal::InvalidFrame));
        }
        Ok(ActiveProfile {
            selected_profile_id: text(&reply, "selected_profile_id").map(str::to_owned),
            signed_in_profile_id: text(&reply, "signed_in_profile_id").map(str::to_owned),
            presence: text(&reply, "presence").unwrap_or("unknown").to_owned(),
        })
    }

    /// The profile `name` resolves to, by identifier or exact label, with its
    /// label; `None` when it names no live profile. Credential-free.
    pub fn login_target(
        &self,
        name: &str,
        deadline: Instant,
    ) -> Result<Option<(String, String)>, Refusal> {
        let reply = self.exchange(
            &json!({"action": "login_target", "request_id": request_id(), "name": name}),
            deadline,
        )?;
        if text(&reply, "kind") != Some("login_target") {
            return Err(self.fail(Refusal::InvalidFrame));
        }
        Ok(match (text(&reply, "profile_id"), text(&reply, "label")) {
            (Some(profile_id), Some(label)) if is_uuid(profile_id) => {
                Some((profile_id.to_owned(), label.to_owned()))
            }
            (None, None) => None,
            _ => return Err(self.fail(Refusal::InvalidFrame)),
        })
    }

    fn login(
        &self,
        profile_id: &str,
        frontend: Frontend,
        method: &str,
        secret: &[u8],
        persist_receipt: bool,
        deadline: Instant,
    ) -> Result<Admitted, Refusal> {
        let request = json!({
            "action": "profile_login",
            "request_id": request_id(),
            "profile_id": profile_id,
            "frontend": frontend.as_str(),
            "method": method,
            "persist_receipt": persist_receipt,
        });
        let reply = self.exchange_with_secret(&request, secret, deadline)?;
        admitted(&reply, profile_id).map_err(|refusal| self.fail(refusal))
    }

    /// Signs `profile_id` in with `password`. With `persist_receipt`, the
    /// runtime stores the sign-in for the person's other frontends.
    pub fn login_password(
        &self,
        profile_id: &str,
        frontend: Frontend,
        password: &[u8],
        persist_receipt: bool,
        deadline: Instant,
    ) -> Result<Admitted, Refusal> {
        self.login(
            profile_id,
            frontend,
            "password",
            password,
            persist_receipt,
            deadline,
        )
    }

    /// Resumes the stored sign-in of `profile_id` by presenting its `proof`.
    pub fn login_receipt(
        &self,
        profile_id: &str,
        frontend: Frontend,
        proof: &[u8],
        deadline: Instant,
    ) -> Result<Admitted, Refusal> {
        self.login(profile_id, frontend, "receipt", proof, false, deadline)
    }

    fn session(
        &self,
        action: &str,
        session: &Admitted,
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        self.exchange(
            &json!({
                "action": action,
                "request_id": request_id(),
                "profile_id": session.profile_id,
                "session_id": session.session_id,
            }),
            deadline,
        )
    }

    /// Rechecks `session` without extending it; the runtime's status object.
    pub fn status(
        &self,
        session: &Admitted,
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        let reply = self.session("session_status", session, deadline)?;
        reply
            .get("status")
            .and_then(Value::as_object)
            .cloned()
            .ok_or_else(|| self.fail(Refusal::InvalidFrame))
    }

    /// Reports the person's own input on `session`, which may extend it.
    pub fn note_activity(&self, session: &Admitted, deadline: Instant) -> Result<(), Refusal> {
        let reply = self.session("session_activity", session, deadline)?;
        match reply
            .get("status")
            .and_then(Value::as_object)
            .and_then(|status| text(status, "denial"))
        {
            Some(denial) => Err(Refusal::Denied {
                code: denial.to_owned(),
                sign_in: None,
            }),
            None => Ok(()),
        }
    }

    /// Signs the person out of the profile everywhere: the stored sign-in is
    /// revoked and every human session of the profile ends.
    pub fn sign_out(&self, session: &Admitted, deadline: Instant) -> Result<SignedOut, Refusal> {
        let reply = self.session("human_sign_out", session, deadline)?;
        if text(&reply, "kind") != Some("human_signed_out") {
            return Err(self.fail(Refusal::InvalidFrame));
        }
        let flag = |key: &str| reply.get(key).and_then(Value::as_bool).unwrap_or(false);
        Ok(SignedOut {
            session_ids: uuid_list(reply.get("session_ids")),
            receipt_removed: flag("receipt_removed"),
            keychain_removed: flag("keychain_removed"),
            automation_enabled: reply.get("automation_enabled").and_then(Value::as_bool),
            automation_access_remains: reply
                .get("automation_access_remains")
                .and_then(Value::as_bool),
        })
    }
}

/// Why no proof of a stored sign-in could be read. The names are the
/// runtime's own refusal reasons for the same states.
#[derive(Debug, PartialEq, Eq)]
pub enum ProofRefusal {
    /// The profile holds no stored sign-in.
    Absent,
    /// The receipt names a credential-store entry that is not there.
    KeychainEntryMissing,
    /// The credential store could not be read.
    KeyringUnavailable,
    /// The receipt or its entry is not what a runtime writes.
    Malformed,
    /// The receipt names another profile.
    Tampered,
}

impl ProofRefusal {
    pub fn code(&self) -> &'static str {
        match self {
            Self::Absent => "absent",
            Self::KeychainEntryMissing => "keychain_entry_missing",
            Self::KeyringUnavailable => "keyring_unavailable",
            Self::Malformed => "malformed",
            Self::Tampered => "tampered",
        }
    }
}

/// The receipt locator: the profile and session that name its credential-store half.
#[derive(Debug, PartialEq, Eq)]
pub struct ReceiptLocator {
    pub profile_id: String,
    pub session_id: String,
}

/// Reads the schema-independent locator of the receipt bytes a runtime wrote.
pub fn receipt_locator(payload: &[u8], profile_id: &str) -> Result<ReceiptLocator, ProofRefusal> {
    let document = document(payload).map_err(|_| ProofRefusal::Malformed)?;
    if document
        .get("schema_version")
        .and_then(Value::as_u64)
        .is_none_or(|version| version == 0)
    {
        return Err(ProofRefusal::Malformed);
    }
    let named = text(&document, "profile_id")
        .filter(|id| is_uuid(id))
        .ok_or(ProofRefusal::Malformed)?;
    let session_id = text(&document, "session_id")
        .filter(|id| is_uuid(id))
        .ok_or(ProofRefusal::Malformed)?;
    if named != profile_id {
        return Err(ProofRefusal::Tampered);
    }
    Ok(ReceiptLocator {
        profile_id: named.to_owned(),
        session_id: session_id.to_owned(),
    })
}

/// The credential-store account a receipt's key is stored under.
pub fn receipt_account(locator: &ReceiptLocator) -> String {
    format!("{}:{}", locator.profile_id, locator.session_id)
}

/// Decodes a stored key as the runtime's keyring writes it: the base64 text
/// of 32 bytes, as UTF-16 or UTF-8.
fn decode_stored_key(blob: &[u8]) -> Result<Zeroizing<Vec<u8>>, ProofRefusal> {
    let utf16 = blob.len().is_multiple_of(2).then(|| {
        let units: Vec<u16> = blob
            .as_chunks::<2>()
            .0
            .iter()
            .map(|pair| u16::from_le_bytes(*pair))
            .collect();
        Zeroizing::new(String::from_utf16(&units).unwrap_or_default())
    });
    let utf8 = Zeroizing::new(String::from_utf8(blob.to_vec()).unwrap_or_default());
    let key = utf16
        .as_deref()
        .and_then(|encoded| base64_decode(encoded))
        .or_else(|| base64_decode(&utf8))
        .map(Zeroizing::new)
        .ok_or(ProofRefusal::Malformed)?;
    if key.len() != RECEIPT_KEY_BYTES {
        return Err(ProofRefusal::Malformed);
    }
    Ok(key)
}

/// The proof of `profile_id`'s stored sign-in under `storage_root`: the key
/// its receipt names in this user's credential store. Nothing is decrypted,
/// unwrapped, evaluated or deleted; the runtime does all of that when the
/// proof is presented. The caller presents the key once and drops it.
pub fn stored_sign_in_proof(
    storage_root: &Path,
    profile_id: &str,
) -> Result<Zeroizing<Vec<u8>>, ProofRefusal> {
    if !is_uuid(profile_id) {
        return Err(ProofRefusal::Malformed);
    }
    let path = storage_root
        .join(KEYSTORE_DIRECTORY)
        .join(profile_id)
        .join(RECEIPT_FILENAME);
    let metadata = match std::fs::symlink_metadata(&path) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Err(ProofRefusal::Absent),
        Err(_) => return Err(ProofRefusal::Malformed),
    };
    if !metadata.is_file() || metadata.len() > RECEIPT_RECORD_MAX_BYTES {
        return Err(ProofRefusal::Malformed);
    }
    let payload = std::fs::read(&path).map_err(|error| {
        if error.kind() == io::ErrorKind::NotFound {
            ProofRefusal::Absent
        } else {
            ProofRefusal::Malformed
        }
    })?;
    let locator = receipt_locator(&payload, profile_id)?;
    let account = receipt_account(&locator);
    let read = |target: &str| {
        runtime_pipe::read_generic_credential(target).map_err(|_| ProofRefusal::KeyringUnavailable)
    };
    // The keyring stores one entry under the service name and the rest under
    // `account@service`; the service entry answers only for its own account.
    let stored = match read(RECEIPT_KEYCHAIN_SERVICE)? {
        Some(credential) if credential.user_name == account => Some(credential),
        _ => read(&format!("{account}@{RECEIPT_KEYCHAIN_SERVICE}"))?,
    };
    let credential = stored.ok_or(ProofRefusal::KeychainEntryMissing)?;
    let blob = Zeroizing::new(credential.blob);
    decode_stored_key(&blob)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frames_carry_a_kind_a_big_endian_length_and_bounded_payloads() {
        let framed = frame(DOCUMENT_FRAME, b"{}").unwrap();
        assert_eq!(framed, [b'J', 0, 0, 0, 2, b'{', b'}']);
        assert!(frame(DOCUMENT_FRAME, b"").is_err());
        assert!(frame(DOCUMENT_FRAME, &vec![b'x'; MAXIMUM_FRAME_BYTES]).is_ok());
        assert!(frame(DOCUMENT_FRAME, &vec![b'x'; MAXIMUM_FRAME_BYTES + 1]).is_err());
        assert_eq!(frame_header(&[b'E', 0, 0, 1, 0]).unwrap(), (b'E', 256));
        for header in [
            [b'S', 0, 0, 0, 1],
            [b'J', 0, 0, 0, 0],
            [b'J', 0, 1, 0, 1],
            [b'X', 0, 0, 0, 1],
        ] {
            assert!(frame_header(&header).is_err(), "{header:?}");
        }
    }

    #[test]
    fn base64_accepts_only_the_canonical_spelling() {
        assert_eq!(base64_decode("aGk=").unwrap(), b"hi");
        assert_eq!(base64_decode("aGV5").unwrap(), b"hey");
        assert_eq!(base64_decode("aA==").unwrap(), b"h");
        assert_eq!(
            base64_decode("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
                .unwrap()
                .len(),
            32
        );
        for rejected in ["", "aGk", "aGk=x", "a===", "aGl=", "aB==", "a Gk=", "YQ=="] {
            if rejected == "YQ==" {
                assert_eq!(base64_decode(rejected).unwrap(), b"a");
                continue;
            }
            assert!(base64_decode(rejected).is_none(), "{rejected}");
        }
    }

    #[test]
    fn request_ids_are_distinct_version_four_uuids() {
        let first = request_id();
        let second = request_id();
        assert!(is_uuid(&first), "{first}");
        assert_ne!(first, second);
        assert_eq!(&first[14..15], "4");
        assert!(matches!(&first[19..20], "8" | "9" | "a" | "b"));
        assert!(!is_uuid("0A1B2C3D-4E5F-4A6B-9C7D-8E9F0A1B2C3D"));
    }

    fn endpoint() -> Endpoint {
        Endpoint {
            pipe_name: r"\\.\pipe\cadrumo-runtime-test".into(),
            storage_identity: "f".repeat(64),
            owner_sid: "S-1-5-21-1-2-3-1001".into(),
        }
    }

    fn cohort(generation: Option<&str>) -> Cohort {
        Cohort {
            product_version: "0.6.0".into(),
            authority_generation: generation.map(str::to_owned),
        }
    }

    #[test]
    fn the_client_hello_names_the_cohort_and_asks_for_lifecycle_notices() {
        let hello = hello_document(&endpoint(), &cohort(Some("a1")));
        assert_eq!(
            hello,
            json!({
                "kind": "client_hello", "protocol_version": 3, "product_version": "0.6.0",
                "storage_identity": "f".repeat(64), "authority_generation": "a1", "lifecycle_notices": "v1"
            })
        );
        assert!(hello_document(&endpoint(), &cohort(None))["authority_generation"].is_null());
    }

    fn server(version: &str, identity: &str, generation: Option<&str>) -> Map<String, Value> {
        let mut document = json!({
            "kind": "server_hello", "protocol_version": 3, "product_version": version,
            "storage_identity": identity, "boot_id": "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d",
            "authority_generation": generation,
        });
        document.as_object_mut().unwrap().clone()
    }

    #[test]
    fn the_server_hello_must_match_version_root_and_any_shared_generation() {
        let identity = "f".repeat(64);
        let hello = server_hello(
            &server("0.6.0", &identity, Some("a1")),
            &endpoint(),
            &cohort(Some("a1")),
        )
        .unwrap();
        assert_eq!(hello.boot_id, "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d");
        assert_eq!(hello.authority_generation.as_deref(), Some("a1"));
        // A side that knows no generation does not refuse the other's.
        assert!(
            server_hello(
                &server("0.6.0", &identity, None),
                &endpoint(),
                &cohort(Some("a1"))
            )
            .is_ok()
        );
        assert!(
            server_hello(
                &server("0.6.0", &identity, Some("a1")),
                &endpoint(),
                &cohort(None)
            )
            .is_ok()
        );
        assert!(matches!(
            server_hello(
                &server("0.6.0", &identity, Some("a2")),
                &endpoint(),
                &cohort(Some("a1"))
            ),
            Err(Refusal::VersionMismatch)
        ));
        assert!(matches!(
            server_hello(
                &server("0.6.1", &identity, None),
                &endpoint(),
                &cohort(None)
            ),
            Err(Refusal::VersionMismatch)
        ));
        assert!(matches!(
            server_hello(
                &server("0.6.0", &"e".repeat(64), None),
                &endpoint(),
                &cohort(None)
            ),
            Err(Refusal::RootMismatch)
        ));
        let mut wrong = server("0.6.0", &identity, None);
        wrong.insert("protocol_version".into(), json!(2));
        assert!(matches!(
            server_hello(&wrong, &endpoint(), &cohort(None)),
            Err(Refusal::InvalidFrame)
        ));
    }

    #[test]
    fn events_are_read_by_kind_and_an_unknown_kind_ends_the_connection() {
        let read = |value: Value| event(value.as_object().unwrap());
        assert_eq!(
            read(json!({"kind": "sign_in_changed"})),
            Event::SignInChanged
        );
        assert_eq!(
            read(
                json!({"kind": "session_event", "event": "signed_out", "reason": "authentication_required"})
            ),
            Event::SessionRetired {
                kind: "signed_out".into(),
                reason: "authentication_required".into()
            }
        );
        assert_eq!(
            read(json!({"kind": "presentation_requested", "destination": "ledger_entries"})),
            Event::PresentationRequested {
                destination: "ledger_entries".into()
            }
        );
        assert_eq!(read(json!({"kind": "profile_status"})), Event::Disconnected);
    }

    #[test]
    fn an_admitted_status_binds_the_profile_and_a_denial_is_the_runtimes_code() {
        let reply = |status: Value, extra: Value| {
            let mut document = json!({
                "kind": "profile_status", "request_id": "r", "runtime_boot_id": "b", "connection_id": "c",
                "status": status, "signed_out_profile_ids": ["0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3e"],
            });
            if let Some(extra) = extra.as_object() {
                document.as_object_mut().unwrap().extend(extra.clone());
            }
            document.as_object().unwrap().clone()
        };
        let live = json!({
            "connected": true, "credential_authenticated": true, "profile_bound": true,
            "profile_id": "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d", "session_id": "1a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d",
            "session_expires_at": "2026-10-22T18:00:00Z", "denial": null,
        });
        let session = admitted(
            &reply(
                live.clone(),
                json!({"human_login": {"session_persisted": true}}),
            ),
            "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d",
        )
        .unwrap();
        assert_eq!(session.session_id, "1a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d");
        assert_eq!(session.session_persisted, Some(true));
        assert_eq!(
            session.signed_out_profile_ids,
            ["0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3e"]
        );
        assert_eq!(session.expires_at.as_deref(), Some("2026-10-22T18:00:00Z"));
        let other = admitted(
            &reply(live.clone(), Value::Null),
            "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3e",
        )
        .unwrap_err();
        assert_eq!(other.code(), "profile_mismatch");
        let mut denied = live.clone();
        denied["denial"] = json!("profile_locked");
        assert_eq!(
            admitted(
                &reply(denied, Value::Null),
                "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d"
            )
            .unwrap_err()
            .code(),
            "profile_locked"
        );
    }

    #[test]
    fn a_receipt_locator_names_its_profile_and_session_or_is_refused() {
        let profile = "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";
        let session = "1a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";
        let payload = format!(
            r#"{{"profile_id":"{profile}","schema_version":3,"session_id":"{session}","wrapped":"x"}}"#
        );
        let locator = receipt_locator(payload.as_bytes(), profile).unwrap();
        assert_eq!(locator.session_id, session);
        assert_eq!(receipt_account(&locator), format!("{profile}:{session}"));
        assert_eq!(
            receipt_locator(payload.as_bytes(), "2a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d")
                .unwrap_err(),
            ProofRefusal::Tampered
        );
        for malformed in [
            "",
            "[]",
            r#"{"profile_id":"x","session_id":"y","schema_version":1}"#,
        ] {
            assert_eq!(
                receipt_locator(malformed.as_bytes(), profile).unwrap_err(),
                ProofRefusal::Malformed
            );
        }
    }

    #[test]
    fn a_stored_key_is_base64_text_in_utf16_or_utf8() {
        let encoded = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=";
        let utf16: Vec<u8> = encoded.encode_utf16().flat_map(u16::to_le_bytes).collect();
        assert_eq!(
            decode_stored_key(&utf16).unwrap().as_slice(),
            (0u8..32).collect::<Vec<_>>()
        );
        assert_eq!(decode_stored_key(encoded.as_bytes()).unwrap().len(), 32);
        assert_eq!(
            decode_stored_key(b"aGk=").unwrap_err(),
            ProofRefusal::Malformed
        );
        assert_eq!(
            decode_stored_key(&[0xff, 0xfe, 0xfd]).unwrap_err(),
            ProofRefusal::Malformed
        );
    }

    #[test]
    fn a_profile_without_a_receipt_has_no_proof() {
        let root =
            std::env::temp_dir().join(format!("cadrumo-runtime-client-{}", std::process::id()));
        let profile = "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";
        std::fs::create_dir_all(root.join(KEYSTORE_DIRECTORY).join(profile)).unwrap();
        assert_eq!(
            stored_sign_in_proof(&root, profile).unwrap_err(),
            ProofRefusal::Absent
        );
        assert_eq!(
            stored_sign_in_proof(&root, "not-a-profile").unwrap_err(),
            ProofRefusal::Malformed
        );
        let receipt = root
            .join(KEYSTORE_DIRECTORY)
            .join(profile)
            .join(RECEIPT_FILENAME);
        std::fs::write(&receipt, b"{}").unwrap();
        assert_eq!(
            stored_sign_in_proof(&root, profile).unwrap_err(),
            ProofRefusal::Malformed
        );
        std::fs::write(
            &receipt,
            format!(r#"{{"profile_id":"{profile}","schema_version":3,"session_id":"1a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d"}}"#),
        )
        .unwrap();
        // The locator is read; the entry it names was never stored.
        assert_eq!(
            stored_sign_in_proof(&root, profile).unwrap_err(),
            ProofRefusal::KeychainEntryMissing
        );
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn an_absent_endpoint_is_not_ready_and_an_unknown_root_names_none() {
        let endpoint = Endpoint {
            pipe_name: format!(r"\\.\pipe\cadrumo-runtime-absent-{}", std::process::id()),
            storage_identity: "f".repeat(64),
            owner_sid: runtime_pipe::current_user_sid().unwrap(),
        };
        let refused = match Connection::open(
            &endpoint,
            &cohort(None),
            Instant::now() + Duration::from_secs(2),
        ) {
            Ok(_) => panic!("an absent pipe must not connect"),
            Err(refused) => refused,
        };
        assert!(matches!(refused, Refusal::EndpointNotReady), "{refused}");
        assert!(matches!(
            Endpoint::of(Path::new(r"C:\cadrumo-no-such-root")),
            Err(Refusal::EndpointUntrusted)
        ));
        let here = Endpoint::of(&std::env::temp_dir()).unwrap();
        assert_eq!(
            here.pipe_name,
            format!(r"\\.\pipe\cadrumo-runtime-{}", here.storage_identity)
        );
        assert_eq!(here.storage_identity.len(), 64);
    }
}

/// Against a running runtime: `CADRUMO_RUNTIME_LIVE_ROOT` names the storage
/// root it serves, `CADRUMO_RUNTIME_LIVE_VERSION` its product version,
/// `CADRUMO_RUNTIME_LIVE_PROFILE_ID` a profile on that root and
/// `CADRUMO_RUNTIME_LIVE_PASSWORD_FILE` a file holding that profile's password.
/// `dev/runtime_lifecycle/native_client_live.py` arranges all of it.
#[cfg(test)]
mod live_tests {
    use super::*;

    struct Live {
        root: std::path::PathBuf,
        cohort: Cohort,
        profile_id: String,
        password: Zeroizing<Vec<u8>>,
    }

    fn live() -> Option<Live> {
        let root = std::env::var_os("CADRUMO_RUNTIME_LIVE_ROOT")?;
        let password_file = std::env::var_os("CADRUMO_RUNTIME_LIVE_PASSWORD_FILE")?;
        Some(Live {
            root: root.into(),
            cohort: Cohort {
                product_version: std::env::var("CADRUMO_RUNTIME_LIVE_VERSION").ok()?,
                authority_generation: None,
            },
            profile_id: std::env::var("CADRUMO_RUNTIME_LIVE_PROFILE_ID").ok()?,
            password: Zeroizing::new(std::fs::read(password_file).ok()?),
        })
    }

    fn soon() -> Instant {
        Instant::now() + Duration::from_secs(30)
    }

    #[test]
    #[ignore = "needs a running runtime: see dev/runtime_lifecycle/native_client_live.py"]
    fn a_window_signs_in_reads_its_session_and_signs_out_natively() {
        let live = live().expect("CADRUMO_RUNTIME_LIVE_* must name a served root");
        let endpoint = Endpoint::of(&live.root).unwrap();
        let watcher = Connection::open(&endpoint, &live.cohort, soon()).unwrap();
        assert_eq!(watcher.hello().product_version, live.cohort.product_version);
        let cues = watcher.subscribe();
        let (named, label) = watcher
            .login_target(&live.profile_id, soon())
            .unwrap()
            .unwrap();
        assert_eq!(named, live.profile_id);
        assert!(!label.is_empty());
        assert!(
            watcher
                .login_target("no-such-profile-label", soon())
                .unwrap()
                .is_none()
        );
        let active = watcher.active_profile(true, soon()).unwrap();
        assert_eq!(
            active.selected_profile_id.as_deref(),
            Some(live.profile_id.as_str())
        );
        let before = watcher
            .sign_in_status(&live.profile_id, true, soon())
            .unwrap();
        assert_eq!(
            before.presence, "present",
            "the harness stored a CLI sign-in first"
        );

        // The stored sign-in is resumed with the proof its receipt names.
        let proof = stored_sign_in_proof(&live.root, &live.profile_id).unwrap();
        let resumed = Connection::open(&endpoint, &live.cohort, soon()).unwrap();
        let session = resumed
            .login_receipt(&live.profile_id, Frontend::Cli, &proof, soon())
            .unwrap();
        assert_eq!(session.profile_id, live.profile_id);
        assert_eq!(
            resumed.connection_id().as_deref(),
            Some(session.connection_id.as_str())
        );
        let status = resumed.status(&session, soon()).unwrap();
        assert_eq!(status["session_id"], json!(session.session_id));
        resumed.note_activity(&session, soon()).unwrap();

        // The window's own password sign-in, on a development root.
        let window = Connection::open(&endpoint, &live.cohort, soon()).unwrap();
        let retirements = resumed.subscribe();
        let held = window
            .login_password(
                &live.profile_id,
                Frontend::Desktop,
                &live.password,
                false,
                soon(),
            )
            .unwrap();
        assert_eq!(held.profile_id, live.profile_id);
        assert!(
            window.status(&held, soon()).unwrap()["credential_authenticated"]
                .as_bool()
                .unwrap()
        );

        // Signing out ends every human session and revokes the stored sign-in.
        let out = window.sign_out(&held, soon()).unwrap();
        assert!(out.automation_enabled.is_some() || out.automation_access_remains.is_none());
        assert!(out.session_ids.contains(&held.session_id));
        assert!(out.session_ids.contains(&session.session_id));
        assert!(out.receipt_removed);
        let retired = retirements.recv_timeout(Duration::from_secs(10)).unwrap();
        assert!(
            matches!(retired, Event::SessionRetired { .. }),
            "{retired:?}"
        );
        let cue = cues.recv_timeout(Duration::from_secs(10)).unwrap();
        assert_eq!(cue, Event::SignInChanged);
        let after = watcher
            .sign_in_status(&live.profile_id, false, soon())
            .unwrap();
        assert_eq!(after.presence, "absent");
        assert_eq!(
            stored_sign_in_proof(&live.root, &live.profile_id).unwrap_err(),
            ProofRefusal::Absent
        );
        let refused = resumed.status(&session, soon()).unwrap_err();
        assert!(
            matches!(refused, Refusal::Denied { .. } | Refusal::ConnectionClosed),
            "{refused}"
        );
        window.close();
        watcher.close();
    }
}
