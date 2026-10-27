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

use crate::value::Sha256Digest;
use cadrumo_platform::runtime_pipe::{self, ConnectRefusal, Pipe};
use serde_json::{Map, Value, json};
use sha2::{Digest, Sha256};
use std::{
    io,
    path::Path,
    sync::{
        Arc, Condvar, Mutex,
        atomic::{AtomicBool, AtomicU64, Ordering},
        mpsc,
    },
    thread,
    time::{Duration, Instant, SystemTime},
};
use zeroize::Zeroizing;

const PROTOCOL_VERSION: u64 = 3;
const MAXIMUM_FRAME_BYTES: usize = 64 * 1024;
/// The longest secret one secret frame carries, and so the longest the runtime takes.
pub const MAXIMUM_SECRET_BYTES: usize = 64 * 1024;
/// The runtime stages a streamed submission in chunks of exactly this many
/// bytes, the last one excepted.
const SUBMISSION_PAYLOAD_CHUNK_BYTES: usize = 16_384;
const DOCUMENT_FRAME: u8 = b'J';
const SECRET_FRAME: u8 = b'S';
const EVENT_FRAME: u8 = b'E';
/// The longest a reply's remaining frames may take once its first frame arrived.
const FRAME_BUDGET: Duration = Duration::from_secs(5);
const TRANSFER_CHUNK_BYTES: usize = 16_384;
const TRANSFER_LIMIT_BYTES: usize = 1_048_576;
const RECEIPT_RECORD_MAX_BYTES: u64 = 8 * 1024;
const RECEIPT_FILENAME: &str = "session.v2.json";
const KEYSTORE_DIRECTORY: &str = "keystore";
const RECEIPT_KEYCHAIN_SERVICE: &str = "cadrumo:profile-session:v2";
const RECEIPT_KEY_BYTES: usize = 32;
/// The denial of a session a lost worker suspended: it grants nothing until a
/// fresh proof on the connection that holds it rebinds it.
pub const CUSTODY_RECOVERING: &str = "custody_recovering";

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
    /// The runtime answered with its typed refusal: an access denial code,
    /// for a sign-in the reason it was refused, for a busy subject the
    /// operation that holds it, and for a suspended session the whole seconds
    /// left in its recovery window.
    Denied {
        code: String,
        sign_in: Option<Value>,
        holder_operation_id: Option<String>,
        recovery_remaining_seconds: Option<u64>,
    },
    Io(io::Error),
}

impl Refusal {
    /// The runtime's refusal `code`, with no sign-in reason or holder.
    pub fn denied(code: impl Into<String>) -> Self {
        Self::Denied {
            code: code.into(),
            sign_in: None,
            holder_operation_id: None,
            recovery_remaining_seconds: None,
        }
    }

    /// Whether the session waits for a fresh proof after the profile's worker was lost.
    pub fn is_custody_recovering(&self) -> bool {
        matches!(self, Self::Denied { code, .. } if code == CUSTODY_RECOVERING)
    }

    /// The whole seconds left in a suspended session's recovery window, when the runtime said.
    pub fn recovery_remaining_seconds(&self) -> Option<u64> {
        match self {
            Self::Denied {
                recovery_remaining_seconds,
                ..
            } => *recovery_remaining_seconds,
            _ => None,
        }
    }

    /// The operation that holds a refused request's subject, when the runtime named one.
    pub fn holder_operation_id(&self) -> Option<&str> {
        match self {
            Self::Denied {
                holder_operation_id,
                ..
            } => holder_operation_id.as_deref(),
            _ => None,
        }
    }

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

/// A pushed event with the profile and session the runtime addressed it to,
/// for a holder that must tell its own session's cues from another's.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Pushed {
    pub event: Event,
    pub profile_id: Option<String>,
    pub session_id: Option<String>,
}

fn sha256_hex(bytes: &[u8]) -> String {
    Sha256Digest::of(bytes).to_string()
}

pub(crate) fn is_uuid(text: &str) -> bool {
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

pub(crate) fn frame(kind: u8, payload: &[u8]) -> Result<Vec<u8>, Refusal> {
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

/// Reads one frame before the caller's deadline, allowing at most
/// [`FRAME_BUDGET`] for the payload after its header.
pub(crate) fn read_frame(pipe: &Pipe, header_deadline: Instant) -> Result<(u8, Vec<u8>), Refusal> {
    let mut header = [0u8; 5];
    pipe.read_exact(&mut header, header_deadline)?;
    let (kind, size) = frame_header(&header)?;
    let mut payload = vec![0u8; size];
    pipe.read_exact(
        &mut payload,
        header_deadline.min(Instant::now() + FRAME_BUDGET),
    )?;
    Ok((kind, payload))
}

fn read_idle_frame(pipe: &Pipe) -> Result<(u8, Vec<u8>), Refusal> {
    let mut header = [0u8; 5];
    pipe.read_idle_byte(&mut header[0])?;
    let deadline = Instant::now() + FRAME_BUDGET;
    pipe.read_exact(&mut header[1..], deadline)?;
    let (kind, size) = frame_header(&header)?;
    let mut payload = vec![0u8; size];
    pipe.read_exact(&mut payload, deadline)?;
    Ok((kind, payload))
}

pub(crate) fn document(payload: &[u8]) -> Result<Map<String, Value>, Refusal> {
    match serde_json::from_slice::<Value>(payload) {
        Ok(Value::Object(object)) => Ok(object),
        _ => Err(Refusal::InvalidFrame),
    }
}

pub(crate) fn text<'a>(document: &'a Map<String, Value>, key: &str) -> Option<&'a str> {
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
    scoped: Mutex<Vec<mpsc::Sender<Pushed>>>,
    closed: AtomicBool,
}

impl Shared {
    fn subscribe(&self) -> mpsc::Receiver<Event> {
        let (sender, receiver) = mpsc::channel();
        let mut subscribers = self.subscribers.lock().unwrap_or_else(|p| p.into_inner());
        if self.closed.load(Ordering::Acquire) {
            let _ = sender.send(Event::Disconnected);
        } else {
            subscribers.push(sender);
        }
        receiver
    }

    fn subscribe_scoped(&self) -> mpsc::Receiver<Pushed> {
        let (sender, receiver) = mpsc::channel();
        let mut subscribers = self.scoped.lock().unwrap_or_else(|p| p.into_inner());
        if self.closed.load(Ordering::Acquire) {
            let _ = sender.send(Pushed {
                event: Event::Disconnected,
                profile_id: None,
                session_id: None,
            });
        } else {
            subscribers.push(sender);
        }
        receiver
    }

    fn dispatch(&self, pushed: &Pushed) {
        self.subscribers
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .retain(|subscriber| subscriber.send(pushed.event.clone()).is_ok());
        self.scoped
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .retain(|subscriber| subscriber.send(pushed.clone()).is_ok());
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
    exchange: ExchangeQueue,
    reader: Mutex<Option<thread::JoinHandle<()>>>,
}

struct ExchangeQueue {
    replies: Mutex<Option<mpsc::Receiver<Map<String, Value>>>>,
    available: Condvar,
}

impl ExchangeQueue {
    fn claim(&self, deadline: Instant) -> Result<ExchangeClaim<'_>, Refusal> {
        let mut replies = self.replies.lock().unwrap_or_else(|p| p.into_inner());
        loop {
            let Some(remaining) = deadline.checked_duration_since(Instant::now()) else {
                // A release may have woken this claimant just as its budget
                // elapsed. Pass that wake on while the receiver is available.
                if replies.is_some() {
                    self.available.notify_one();
                }
                return Err(Refusal::DeadlineExceeded);
            };
            if let Some(replies) = replies.take() {
                return Ok(ExchangeClaim {
                    owner: self,
                    replies: Some(replies),
                });
            }
            (replies, _) = self
                .available
                .wait_timeout(replies, remaining)
                .unwrap_or_else(|p| p.into_inner());
        }
    }
}

struct ExchangeClaim<'a> {
    owner: &'a ExchangeQueue,
    replies: Option<mpsc::Receiver<Map<String, Value>>>,
}

impl std::ops::Deref for ExchangeClaim<'_> {
    type Target = mpsc::Receiver<Map<String, Value>>;

    fn deref(&self) -> &Self::Target {
        self.replies
            .as_ref()
            .expect("a held exchange owns its replies")
    }
}

impl Drop for ExchangeClaim<'_> {
    fn drop(&mut self) {
        *self.owner.replies.lock().unwrap_or_else(|p| p.into_inner()) = self.replies.take();
        self.owner.available.notify_one();
    }
}

/// The client's hello. A connection that asks for lifecycle notices receives
/// `E` frames between replies; one that does not never does.
fn hello_document(endpoint: &Endpoint, cohort: &Cohort, lifecycle_notices: bool) -> Value {
    let mut hello = json!({
        "kind": "client_hello",
        "protocol_version": PROTOCOL_VERSION,
        "product_version": cohort.product_version,
        "storage_identity": endpoint.storage_identity,
        "authority_generation": cohort.authority_generation,
    });
    if lifecycle_notices {
        hello["lifecycle_notices"] = json!("v1");
    }
    hello
}

/// Connects to `endpoint` before `deadline`, verifies the runtime as its
/// pipe's same-account peer, and completes the cohort handshake. Every
/// connection to the runtime, an event-reading one or a view stream, starts here.
pub(crate) fn handshake(
    endpoint: &Endpoint,
    cohort: &Cohort,
    lifecycle_notices: bool,
    deadline: Instant,
) -> Result<(Pipe, Hello), Refusal> {
    let pipe = Pipe::connect(&endpoint.pipe_name, &endpoint.owner_sid, deadline)?;
    let payload = serde_json::to_vec(&hello_document(endpoint, cohort, lifecycle_notices))
        .map_err(|_| Refusal::InvalidFrame)?;
    pipe.write_all(&frame(DOCUMENT_FRAME, &payload)?, deadline)?;
    let (kind, payload) = read_frame(&pipe, deadline)?;
    if kind != DOCUMENT_FRAME {
        return Err(Refusal::InvalidFrame);
    }
    let hello = server_hello(&document(&payload)?, endpoint, cohort)?;
    Ok((pipe, hello))
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
    while let Ok((kind, payload)) = read_idle_frame(&pipe) {
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
        let pushed = Pushed {
            event: event(&document),
            profile_id: text(&document, "profile_id").map(str::to_owned),
            session_id: text(&document, "session_id").map(str::to_owned),
        };
        if pushed.event == Event::Disconnected {
            break;
        }
        shared.dispatch(&pushed);
    }
    shared.closed.store(true, Ordering::Release);
    pipe.close();
    shared.dispatch(&Pushed {
        event: Event::Disconnected,
        profile_id: None,
        session_id: None,
    });
}

impl Connection {
    /// Connects to `endpoint` as `cohort` before `deadline`: the peer is
    /// verified, the handshake completed, and the event reader started. No
    /// credential is involved.
    pub fn open(endpoint: &Endpoint, cohort: &Cohort, deadline: Instant) -> Result<Self, Refusal> {
        let (pipe, hello) = handshake(endpoint, cohort, true, deadline)?;
        let pipe = Arc::new(pipe);
        let shared = Arc::new(Shared {
            connection_id: Mutex::new(None),
            subscribers: Mutex::new(Vec::new()),
            scoped: Mutex::new(Vec::new()),
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
            exchange: ExchangeQueue {
                replies: Mutex::new(Some(exchange)),
                available: Condvar::new(),
            },
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
        self.shared.subscribe()
    }

    /// As [`Connection::subscribe`], with the profile and session each event names.
    pub fn subscribe_scoped(&self) -> mpsc::Receiver<Pushed> {
        self.shared.subscribe_scoped()
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

    fn claim(&self, deadline: Instant) -> Result<ExchangeClaim<'_>, Refusal> {
        let exchange = self.exchange.claim(deadline)?;
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
        replies: &mpsc::Receiver<Map<String, Value>>,
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        let remaining = deadline
            .checked_duration_since(Instant::now())
            .filter(|remaining| !remaining.is_zero())
            .ok_or(Refusal::DeadlineExceeded)?;
        match replies.recv_timeout(remaining) {
            Ok(_) if Instant::now() >= deadline => Err(Refusal::DeadlineExceeded),
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
        let mut reply = Self::next_reply(replies, deadline)?;
        self.verify_reply(&reply, request_id)?;
        if text(&reply, "kind").is_some_and(|kind| kind.ends_with("_transfer")) {
            reply = self.assemble_transfer(replies, &reply, request_id, deadline)?;
        }
        if text(&reply, "kind") == Some("access_refusal") {
            return Err(access_refusal(&reply));
        }
        Ok(reply)
    }

    fn assemble_transfer(
        &self,
        replies: &mpsc::Receiver<Map<String, Value>>,
        header: &Map<String, Value>,
        request_id: &str,
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        let deadline = deadline.min(Instant::now() + FRAME_BUDGET);
        let byte_count = header
            .get("byte_count")
            .and_then(Value::as_u64)
            .filter(|&count| (2..=TRANSFER_LIMIT_BYTES as u64).contains(&count))
            .ok_or(Refusal::InvalidFrame)? as usize;
        let digest = text(header, "payload_digest").ok_or(Refusal::InvalidFrame)?;
        let mut payload = Vec::with_capacity(byte_count);
        while payload.len() < byte_count {
            let chunk = Self::next_reply(replies, deadline)?;
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
        // A request can carry private input; its encoding is overwritten once written.
        let payload =
            Zeroizing::new(serde_json::to_vec(request).map_err(|_| Refusal::InvalidFrame)?);
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

impl Connection {
    /// Sends `request`, an `operation_submit_payload` whose descriptor names
    /// `payload`'s length, then `payload` in secret frames once the runtime
    /// is ready for exactly that descriptor, and returns the final reply. A
    /// refusal before readiness never sends the payload.
    pub fn exchange_streamed(
        &self,
        request: &Value,
        payload: &[u8],
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        let request_id = request
            .get("request_id")
            .and_then(Value::as_str)
            .ok_or(Refusal::InvalidFrame)?
            .to_owned();
        let replies = self.claim(deadline)?;
        let header =
            Zeroizing::new(serde_json::to_vec(request).map_err(|_| Refusal::InvalidFrame)?);
        let delivered = (|| {
            self.write(DOCUMENT_FRAME, &header, deadline)?;
            let ready = self.reply(&replies, &request_id, deadline)?;
            if !ready_for(request, &ready) {
                return Err(Refusal::InvalidFrame);
            }
            for chunk in payload.chunks(SUBMISSION_PAYLOAD_CHUNK_BYTES) {
                self.write(SECRET_FRAME, chunk, deadline)?;
            }
            self.reply(&replies, &request_id, deadline)
        })();
        delivered.map_err(|refusal| self.fail(refusal))
    }
}

/// Whether `ready` admits the upload `request` declared, and no other.
fn ready_for(request: &Value, ready: &Map<String, Value>) -> bool {
    text(ready, "kind") == Some("operation_payload_ready")
        && request.get("descriptor").is_some()
        && ready.get("descriptor") == request.get("descriptor")
}

impl Drop for Connection {
    fn drop(&mut self) {
        self.close();
    }
}

/// What a held session's requests need of a connection: correlated exchanges
/// and the events pushed to it. [`Connection`] is the one real implementation;
/// a unit test of the logic layered on it may answer in its place.
pub trait SessionExchange: Send + Sync {
    /// As [`Connection::exchange`].
    fn exchange(&self, request: &Value, deadline: Instant) -> Result<Map<String, Value>, Refusal>;
    /// As [`Connection::exchange_streamed`].
    fn exchange_streamed(
        &self,
        request: &Value,
        payload: &[u8],
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal>;
    /// As [`Connection::exchange_with_secret`].
    fn exchange_with_secret(
        &self,
        request: &Value,
        secret: &[u8],
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal>;
    /// As [`Connection::subscribe_scoped`].
    fn subscribe_scoped(&self) -> mpsc::Receiver<Pushed>;
    /// As [`Connection::close`]: for a peer that broke the protocol.
    fn close(&self);
}

impl SessionExchange for Connection {
    fn exchange(&self, request: &Value, deadline: Instant) -> Result<Map<String, Value>, Refusal> {
        Connection::exchange(self, request, deadline)
    }

    fn exchange_streamed(
        &self,
        request: &Value,
        payload: &[u8],
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        Connection::exchange_streamed(self, request, payload, deadline)
    }

    fn exchange_with_secret(
        &self,
        request: &Value,
        secret: &[u8],
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        Connection::exchange_with_secret(self, request, secret, deadline)
    }

    fn subscribe_scoped(&self) -> mpsc::Receiver<Pushed> {
        Connection::subscribe_scoped(self)
    }

    fn close(&self) {
        Connection::close(self);
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

/// The runtime's typed refusal as its `access_refusal` document spells it.
fn access_refusal(reply: &Map<String, Value>) -> Refusal {
    Refusal::Denied {
        code: text(reply, "code").unwrap_or_default().to_owned(),
        sign_in: reply
            .get("sign_in")
            .filter(|value| !value.is_null())
            .cloned(),
        holder_operation_id: text(reply, "holder_operation_id").map(str::to_owned),
        recovery_remaining_seconds: recovery_window(reply),
    }
}

/// The whole seconds a document names as left in a suspended session's recovery window.
fn recovery_window(document: &Map<String, Value>) -> Option<u64> {
    document
        .get("recovery_remaining_seconds")
        .and_then(Value::as_u64)
}

/// The refusal a status's `denial` stands for, with the window a suspended session names.
fn denial(status: &Map<String, Value>) -> Option<Refusal> {
    text(status, "denial").map(|code| Refusal::Denied {
        code: code.to_owned(),
        sign_in: None,
        holder_operation_id: None,
        recovery_remaining_seconds: recovery_window(status),
    })
}

/// Where a session stands, as the runtime's status for it reads.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Standing {
    /// The lease grants access.
    Held,
    /// A lost worker suspended it: it grants nothing until a fresh proof on
    /// its own connection rebinds it, or its window ends.
    Recovering { remaining_seconds: Option<u64> },
    /// The runtime refuses it for the denial's own reason; it is not coming back by itself.
    Refused(String),
}

impl Standing {
    /// Reads the status object the runtime answered for `session`.
    pub fn of(status: &Map<String, Value>, session: &Admitted) -> Self {
        match text(status, "denial") {
            Some(CUSTODY_RECOVERING) => Self::Recovering {
                remaining_seconds: recovery_window(status),
            },
            Some(code) => Self::Refused(code.to_owned()),
            None if text(status, "session_id") == Some(session.session_id.as_str()) => Self::Held,
            None => Self::Refused("profile_mismatch".to_owned()),
        }
    }
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
    if let Some(refusal) = denial(status) {
        return Err(refusal);
    }
    let session_id = text(status, "session_id");
    if !flag("connected")
        || !flag("credential_authenticated")
        || !flag("profile_bound")
        || text(status, "profile_id") != Some(profile_id)
        || session_id.is_none()
    {
        return Err(Refusal::denied("profile_mismatch"));
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
        present_login(
            self,
            profile_id,
            frontend,
            method,
            secret,
            persist_receipt,
            deadline,
        )
        .map_err(|refusal| self.fail(refusal))
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

    /// Resumes the stored sign-in of `profile_id` from `storage_root` with the
    /// proof its receipt names, as every other frontend resumes it.
    ///
    /// A sign-in that completes between reading the proof and the runtime's
    /// check replaces the receipt, so the proof read before it no longer
    /// unwraps the one the runtime reads. Such a refusal is retried with a
    /// fresh read, a bounded number of times and only while the proof differs
    /// from the one refused.
    pub fn resume_receipt(
        &self,
        storage_root: &Path,
        profile_id: &str,
        frontend: Frontend,
        deadline: Instant,
    ) -> Result<Admitted, ResumeRefusal> {
        present_stored_proof(
            storage_root,
            profile_id,
            deadline,
            || self.closed(),
            |proof| self.login_receipt(profile_id, frontend, proof, deadline),
        )
    }

    /// Rechecks `session` without extending it; the runtime's status object.
    pub fn status(
        &self,
        session: &Admitted,
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        session_status(self, session, deadline).map_err(|refusal| self.fail(refusal))
    }

    /// Reports the person's own input on `session`, which may extend it.
    pub fn note_activity(&self, session: &Admitted, deadline: Instant) -> Result<(), Refusal> {
        let reply = session_exchange(self, "session_activity", session, deadline)?;
        match reply
            .get("status")
            .and_then(Value::as_object)
            .and_then(denial)
        {
            Some(refusal) => Err(refusal),
            None => Ok(()),
        }
    }

    /// Signs the person out of the profile everywhere: the stored sign-in is
    /// revoked and every human session of the profile ends.
    pub fn sign_out(&self, session: &Admitted, deadline: Instant) -> Result<SignedOut, Refusal> {
        human_sign_out(self, session, deadline).map_err(|refusal| self.fail(refusal))
    }
}

/// Asks the runtime for one of `session`'s own actions, which names no more than its identity.
fn session_exchange(
    exchange: &dyn SessionExchange,
    action: &str,
    session: &Admitted,
    deadline: Instant,
) -> Result<Map<String, Value>, Refusal> {
    exchange.exchange(
        &json!({
            "action": action,
            "request_id": request_id(),
            "profile_id": session.profile_id,
            "session_id": session.session_id,
        }),
        deadline,
    )
}

/// Rechecks `session` without extending it, through whatever carries its
/// exchanges: the runtime's status object.
pub fn session_status(
    exchange: &dyn SessionExchange,
    session: &Admitted,
    deadline: Instant,
) -> Result<Map<String, Value>, Refusal> {
    session_exchange(exchange, "session_status", session, deadline)?
        .get("status")
        .and_then(Value::as_object)
        .cloned()
        .ok_or(Refusal::InvalidFrame)
}

/// Where `session` stands now. A refusal the runtime answers in place of a
/// status is a standing too; a lost or failed exchange is not.
pub fn session_standing(
    exchange: &dyn SessionExchange,
    session: &Admitted,
    deadline: Instant,
) -> Result<Standing, Refusal> {
    match session_status(exchange, session, deadline) {
        Ok(status) => Ok(Standing::of(&status, session)),
        Err(Refusal::Denied {
            code,
            recovery_remaining_seconds,
            ..
        }) => Ok(if code == CUSTODY_RECOVERING {
            Standing::Recovering {
                remaining_seconds: recovery_remaining_seconds,
            }
        } else {
            Standing::Refused(code)
        }),
        Err(refusal) => Err(refusal),
    }
}

/// Sends one `profile_login` with its `secret` and reads the session it admits.
fn present_login(
    exchange: &dyn SessionExchange,
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
    let reply = exchange.exchange_with_secret(&request, secret, deadline)?;
    admitted(&reply, profile_id)
}

/// Presents a fresh proof for `session` on the connection that holds it. A
/// suspended session returns under its own identity; a login that admits
/// another one is no rebind.
fn rebind(
    exchange: &dyn SessionExchange,
    session: &Admitted,
    frontend: Frontend,
    method: &str,
    secret: &[u8],
    persist_receipt: bool,
    deadline: Instant,
) -> Result<Admitted, Refusal> {
    let rebound = present_login(
        exchange,
        &session.profile_id,
        frontend,
        method,
        secret,
        persist_receipt,
        deadline,
    )?;
    if rebound.session_id != session.session_id {
        return Err(Refusal::denied("session_mismatch"));
    }
    Ok(rebound)
}

/// Rebinds a suspended `session` on the connection that holds it, by the
/// profile's `password`. The sign-in is stored for the person's other
/// frontends, as the window's own password sign-in stores it.
pub fn rebind_password(
    exchange: &dyn SessionExchange,
    session: &Admitted,
    frontend: Frontend,
    password: &[u8],
    deadline: Instant,
) -> Result<Admitted, Refusal> {
    rebind(
        exchange, session, frontend, "password", password, true, deadline,
    )
}

/// Rebinds a suspended `session` on the connection that holds it, by the
/// proof of the stored sign-in under `storage_root`, read fresh as every
/// presentation of it is.
pub fn rebind_receipt(
    exchange: &dyn SessionExchange,
    storage_root: &Path,
    session: &Admitted,
    frontend: Frontend,
    deadline: Instant,
) -> Result<Admitted, ResumeRefusal> {
    present_stored_proof(
        storage_root,
        &session.profile_id,
        deadline,
        || false,
        |proof| {
            rebind(
                exchange, session, frontend, "receipt", proof, false, deadline,
            )
        },
    )
}

/// Signs the person out of `session`'s profile everywhere, through whatever
/// carries that session's exchanges: the stored sign-in is revoked and every
/// human session of the profile ends.
pub fn human_sign_out(
    exchange: &dyn SessionExchange,
    session: &Admitted,
    deadline: Instant,
) -> Result<SignedOut, Refusal> {
    let reply = exchange.exchange(
        &json!({
            "action": "human_sign_out",
            "request_id": request_id(),
            "profile_id": session.profile_id,
            "session_id": session.session_id,
        }),
        deadline,
    )?;
    if text(&reply, "kind") != Some("human_signed_out") {
        return Err(Refusal::InvalidFrame);
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

/// Presentations of one resume; each after the first needs a proof that
/// changed since the last refusal.
const RECEIPT_PROOF_ATTEMPTS: usize = 3;

/// The persisted-session refusal reasons a runtime may name for a presented receipt.
const RECEIPT_REFUSAL_REASONS: [&str; 9] = [
    "absent",
    "malformed",
    "schema_version_mismatch",
    "expired_idle",
    "expired_absolute",
    "keychain_entry_missing",
    "keyring_unavailable",
    "custody_changed",
    "tampered",
];

/// Reads the stored sign-in's proof and has `present` offer it to the runtime.
///
/// A sign-in that completes between reading the proof and the runtime's check
/// replaces the receipt, so the proof read before it no longer unwraps the one
/// the runtime reads. Such a refusal is retried with a fresh read, a bounded
/// number of times and only while the proof differs from the one refused.
fn present_stored_proof<T>(
    storage_root: &Path,
    profile_id: &str,
    deadline: Instant,
    closed: impl Fn() -> bool,
    present: impl Fn(&[u8]) -> Result<T, Refusal>,
) -> Result<T, ResumeRefusal> {
    let mut presented: Option<Zeroizing<Vec<u8>>> = None;
    for attempt in 1..=RECEIPT_PROOF_ATTEMPTS {
        let proof = stored_sign_in_proof(storage_root, profile_id)
            .map_err(|refusal| ResumeRefusal::Receipt(refusal.code().to_owned()))?;
        if presented
            .as_ref()
            .is_some_and(|refused| **refused == *proof)
        {
            // No sign-in replaced the receipt: the proof was refused for itself.
            return Err(ResumeRefusal::Receipt("tampered".to_owned()));
        }
        let refusal = match present(&proof) {
            Ok(admitted) => return Ok(admitted),
            Err(refusal) => refusal,
        };
        let Some(reason) = receipt_refusal(&refusal) else {
            return Err(ResumeRefusal::Runtime(refusal));
        };
        if reason != "tampered"
            || attempt == RECEIPT_PROOF_ATTEMPTS
            || Instant::now() >= deadline
            || closed()
        {
            return Err(ResumeRefusal::Receipt(reason.to_owned()));
        }
        presented = Some(proof);
    }
    Err(ResumeRefusal::Receipt("tampered".to_owned()))
}

/// Why a stored sign-in was not resumed.
#[derive(Debug)]
pub enum ResumeRefusal {
    /// The receipt does not sign this login in, by its persisted-session
    /// refusal reason: none is stored, it could not be read, or the runtime
    /// refused it.
    Receipt(String),
    /// The runtime could not be asked, or refused for another reason.
    Runtime(Refusal),
}

impl ResumeRefusal {
    pub fn code(&self) -> &str {
        match self {
            Self::Receipt(reason) => reason,
            Self::Runtime(refusal) => refusal.code(),
        }
    }
}

impl std::fmt::Display for ResumeRefusal {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Receipt(reason) => write!(formatter, "receipt_refused: {reason}"),
            Self::Runtime(refusal) => refusal.fmt(formatter),
        }
    }
}

impl std::error::Error for ResumeRefusal {}

/// The receipt refusal a runtime denial of a presented receipt stands for,
/// if it is one: the sign-in reason it names, or the denial's own meaning.
fn receipt_refusal(refusal: &Refusal) -> Option<&str> {
    if let Some(reason) = refusal
        .sign_in_reason()
        .filter(|reason| RECEIPT_REFUSAL_REASONS.contains(reason))
    {
        return Some(reason);
    }
    match refusal {
        Refusal::Denied { code, .. } => match code.as_str() {
            // The runtime deleted a receipt that no longer signs this login in.
            "authentication_required" => Some("absent"),
            // The denial does not distinguish idle from absolute expiry.
            "session_expired" => Some("expired_idle"),
            "custody_changed" => Some("custody_changed"),
            "credential_rejected" => Some("tampered"),
            _ => None,
        },
        _ => None,
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
    fn an_expired_exchange_does_not_accept_a_buffered_reply() {
        let (sender, receiver) = mpsc::channel();
        sender.send(Map::new()).unwrap();
        assert!(matches!(
            Connection::next_reply(&receiver, Instant::now()),
            Err(Refusal::DeadlineExceeded)
        ));
        assert!(
            Connection::next_reply(&receiver, Instant::now() + Duration::from_secs(1))
                .unwrap()
                .is_empty()
        );
    }

    #[test]
    fn a_reply_wait_ends_at_its_deadline_without_waiting_for_sender_exit() {
        let (_sender, receiver) = mpsc::channel();
        assert!(matches!(
            Connection::next_reply(&receiver, Instant::now() + Duration::from_millis(20)),
            Err(Refusal::DeadlineExceeded)
        ));
    }

    #[test]
    fn a_queued_exchange_times_out_without_disturbing_the_owner() {
        let (sender, receiver) = mpsc::channel();
        let queue = Arc::new(ExchangeQueue {
            replies: Mutex::new(Some(receiver)),
            available: Condvar::new(),
        });
        let owner = queue
            .claim(Instant::now() + Duration::from_secs(2))
            .unwrap();
        let (done, finished) = mpsc::channel();
        let contender = {
            let queue = queue.clone();
            thread::spawn(move || {
                let timed_out = matches!(
                    queue.claim(Instant::now() + Duration::from_millis(50)),
                    Err(Refusal::DeadlineExceeded)
                );
                done.send(timed_out).unwrap();
            })
        };
        let timed_out = finished.recv_timeout(Duration::from_secs(2));
        sender.send(Map::new()).unwrap();
        assert!(
            owner
                .recv_timeout(Duration::from_secs(1))
                .unwrap()
                .is_empty()
        );
        drop(owner);
        contender.join().unwrap();
        assert!(timed_out.unwrap());
        assert!(queue.claim(Instant::now() + Duration::from_secs(1)).is_ok());
    }

    #[test]
    fn subscription_racing_disconnect_always_receives_the_terminal_event() {
        for _ in 0..100 {
            let shared = Arc::new(Shared {
                connection_id: Mutex::new(None),
                subscribers: Mutex::new(Vec::new()),
                scoped: Mutex::new(Vec::new()),
                closed: AtomicBool::new(false),
            });
            let barrier = Arc::new(std::sync::Barrier::new(2));
            let subscriber = {
                let shared = shared.clone();
                let barrier = barrier.clone();
                thread::spawn(move || {
                    barrier.wait();
                    (shared.subscribe(), shared.subscribe_scoped())
                })
            };
            barrier.wait();
            shared.closed.store(true, Ordering::Release);
            shared.dispatch(&Pushed {
                event: Event::Disconnected,
                profile_id: None,
                session_id: None,
            });
            let (plain, scoped) = subscriber.join().unwrap();
            assert_eq!(
                plain.recv_timeout(Duration::from_secs(1)).unwrap(),
                Event::Disconnected
            );
            assert_eq!(
                scoped.recv_timeout(Duration::from_secs(1)).unwrap().event,
                Event::Disconnected
            );
            assert!(plain.try_recv().is_err());
            assert!(scoped.try_recv().is_err());
        }
    }

    #[test]
    fn an_expired_claimant_passes_on_a_release_wake() {
        let (_sender, receiver) = mpsc::channel();
        let queue = Arc::new(ExchangeQueue {
            replies: Mutex::new(None),
            available: Condvar::new(),
        });
        let (waiting, started) = mpsc::channel();
        let (done, finished) = mpsc::channel();
        let waiter = {
            let queue = queue.clone();
            thread::spawn(move || {
                let held = queue.replies.lock().unwrap();
                waiting.send(()).unwrap();
                let (held, timeout) = queue
                    .available
                    .wait_timeout(held, Duration::from_secs(3))
                    .unwrap();
                done.send(!timeout.timed_out() && held.is_some()).unwrap();
            })
        };
        started.recv_timeout(Duration::from_secs(1)).unwrap();
        // The receiver became available, but the release wake went to an
        // expired claimant rather than the waiter above.
        *queue.replies.lock().unwrap() = Some(receiver);
        assert!(matches!(
            queue.claim(Instant::now() - Duration::from_secs(1)),
            Err(Refusal::DeadlineExceeded)
        ));
        let woke = finished.recv_timeout(Duration::from_secs(1));
        waiter.join().unwrap();
        assert!(woke.unwrap());
    }

    #[test]
    fn a_streamed_payload_follows_only_readiness_for_the_declared_upload() {
        let descriptor = json!({"kind": "financial_operand_input", "byte_count": 70_000});
        let request = json!({"action": "operation_submit_payload", "descriptor": descriptor});
        let ready = |kind: &str, descriptor: Value| {
            json!({"kind": kind, "descriptor": descriptor})
                .as_object()
                .unwrap()
                .clone()
        };
        assert!(ready_for(
            &request,
            &ready("operation_payload_ready", descriptor.clone())
        ));
        assert!(!ready_for(
            &request,
            &ready(
                "operation_payload_ready",
                json!({"kind": "financial_operand_input", "byte_count": 69_999})
            )
        ));
        assert!(!ready_for(
            &request,
            &ready("operation_submitted", descriptor.clone())
        ));
        assert!(!ready_for(
            &json!({"action": "operation_submit_payload"}),
            &ready("operation_payload_ready", Value::Null)
        ));
        // Every chunk but the last fills one secret frame within its bound.
        assert!(frame(SECRET_FRAME, &[0; SUBMISSION_PAYLOAD_CHUNK_BYTES]).is_ok());
    }

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
    fn a_refused_receipt_reads_as_its_receipt_reason_and_other_refusals_do_not() {
        let named = Refusal::Denied {
            code: "authentication_required".into(),
            sign_in: Some(json!({"reason": "expired_absolute"})),
            holder_operation_id: None,
            recovery_remaining_seconds: None,
        };
        assert_eq!(receipt_refusal(&named), Some("expired_absolute"));
        for (code, reason) in [
            ("authentication_required", "absent"),
            ("session_expired", "expired_idle"),
            ("custody_changed", "custody_changed"),
            ("credential_rejected", "tampered"),
        ] {
            assert_eq!(
                receipt_refusal(&Refusal::denied(code)),
                Some(reason),
                "{code}"
            );
        }
        let throttled = Refusal::Denied {
            code: "credential_rejected".into(),
            sign_in: Some(json!({"reason": "throttled", "remaining_seconds": 30})),
            holder_operation_id: None,
            recovery_remaining_seconds: None,
        };
        assert_eq!(receipt_refusal(&throttled), Some("tampered"));
        assert_eq!(receipt_refusal(&Refusal::denied("profile_locked")), None);
        assert_eq!(receipt_refusal(&Refusal::ConnectionClosed), None);
    }

    #[test]
    fn a_busy_subject_names_its_holder() {
        let busy = Refusal::Denied {
            code: "subject_busy".into(),
            sign_in: None,
            holder_operation_id: Some("0f0f0f0f-0000-4000-8000-000000000000".into()),
            recovery_remaining_seconds: None,
        };
        assert_eq!(
            busy.holder_operation_id(),
            Some("0f0f0f0f-0000-4000-8000-000000000000")
        );
        assert_eq!(Refusal::denied("subject_busy").holder_operation_id(), None);
        assert_eq!(Refusal::InvalidFrame.holder_operation_id(), None);
    }

    #[test]
    fn a_refusal_of_a_suspended_session_carries_its_recovery_window() {
        let document = |code: &str, window: Value| {
            json!({
                "kind": "access_refusal", "code": code, "sign_in": null,
                "recovery_remaining_seconds": window,
            })
            .as_object()
            .unwrap()
            .clone()
        };
        let waiting = access_refusal(&document("custody_recovering", json!(87)));
        assert!(waiting.is_custody_recovering());
        assert_eq!(waiting.recovery_remaining_seconds(), Some(87));
        assert_eq!(waiting.code(), CUSTODY_RECOVERING);
        // The window is the runtime's to name: none given is none known, not zero.
        let unnamed = access_refusal(&document("custody_recovering", Value::Null));
        assert!(unnamed.is_custody_recovering());
        assert_eq!(unnamed.recovery_remaining_seconds(), None);
        let ended = access_refusal(&document("custody_unavailable", Value::Null));
        assert!(!ended.is_custody_recovering());
        assert_eq!(ended.code(), "custody_unavailable");
        assert_eq!(Refusal::ConnectionClosed.recovery_remaining_seconds(), None);
        assert!(!Refusal::ConnectionClosed.is_custody_recovering());
    }

    fn held() -> Admitted {
        Admitted {
            profile_id: "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d".into(),
            session_id: "1a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d".into(),
            connection_id: "2a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d".into(),
            runtime_boot_id: "3a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d".into(),
            expires_at: None,
            session_persisted: None,
            signed_out_profile_ids: Vec::new(),
        }
    }

    #[test]
    fn a_status_reads_as_held_recovering_or_refused_for_the_session_it_names() {
        let status = |value: Value| value.as_object().unwrap().clone();
        let session = held();
        assert_eq!(
            Standing::of(
                &status(json!({"session_id": session.session_id, "denial": null})),
                &session
            ),
            Standing::Held
        );
        // Whole seconds, rounded up by the runtime; the session keeps its identity.
        assert_eq!(
            Standing::of(
                &status(json!({
                    "session_id": session.session_id, "denial": "custody_recovering",
                    "recovery_remaining_seconds": 119, "credential_authenticated": false,
                })),
                &session
            ),
            Standing::Recovering {
                remaining_seconds: Some(119)
            }
        );
        assert_eq!(
            Standing::of(
                &status(json!({"session_id": session.session_id, "denial": "custody_recovering"})),
                &session
            ),
            Standing::Recovering {
                remaining_seconds: None
            }
        );
        assert_eq!(
            Standing::of(
                &status(json!({"session_id": session.session_id, "denial": "custody_unavailable"})),
                &session
            ),
            Standing::Refused("custody_unavailable".into())
        );
        // A status that names another session, or none, is no standing of this one.
        for other in [
            json!({"session_id": "4a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d", "denial": null}),
            json!({"session_id": null, "denial": null}),
        ] {
            assert_eq!(
                Standing::of(&status(other), &session),
                Standing::Refused("profile_mismatch".into())
            );
        }
    }

    #[test]
    fn an_admitted_status_of_a_suspended_session_is_refused_with_its_window() {
        let reply = json!({
            "kind": "profile_status",
            "status": {
                "connected": true, "credential_authenticated": false, "profile_bound": true,
                "profile_id": "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d",
                "session_id": "1a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d",
                "denial": "custody_recovering", "recovery_remaining_seconds": 42,
            },
        });
        let refused = admitted(
            reply.as_object().unwrap(),
            "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d",
        )
        .unwrap_err();
        assert!(refused.is_custody_recovering());
        assert_eq!(refused.recovery_remaining_seconds(), Some(42));
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
        let hello = hello_document(&endpoint(), &cohort(Some("a1")), true);
        assert_eq!(
            hello,
            json!({
                "kind": "client_hello", "protocol_version": 3, "product_version": "0.6.0",
                "storage_identity": "f".repeat(64), "authority_generation": "a1", "lifecycle_notices": "v1"
            })
        );
        assert!(hello_document(&endpoint(), &cohort(None), true)["authority_generation"].is_null());
    }

    #[test]
    fn a_hello_that_asks_for_no_lifecycle_notices_omits_the_member() {
        let hello = hello_document(&endpoint(), &cohort(Some("a1")), false);
        assert_eq!(
            hello,
            json!({
                "kind": "client_hello", "protocol_version": 3, "product_version": "0.6.0",
                "storage_identity": "f".repeat(64), "authority_generation": "a1"
            })
        );
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
/// `CADRUMO_RUNTIME_LIVE_PASSWORD_FILE` a file holding that profile's password
/// and `CADRUMO_RUNTIME_LIVE_WORK_UNIT` a Modelo 303 work unit it holds.
/// `dev/runtime_lifecycle/native_client_live.py` arranges all of it.
#[cfg(test)]
mod live_tests {
    use super::*;

    struct Live {
        root: std::path::PathBuf,
        cohort: Cohort,
        profile_id: String,
        password: Zeroizing<Vec<u8>>,
        /// A Modelo 303 work unit the profile holds.
        work_unit: String,
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
            work_unit: std::env::var("CADRUMO_RUNTIME_LIVE_WORK_UNIT").ok()?,
        })
    }

    fn soon() -> Instant {
        Instant::now() + Duration::from_secs(30)
    }

    /// The real connection, noting each definition whose streamed upload the
    /// runtime took and answered with an admitted operation.
    struct Streams<'a> {
        connection: &'a Connection,
        streamed: Mutex<Vec<String>>,
    }

    impl SessionExchange for Streams<'_> {
        fn exchange(
            &self,
            request: &Value,
            deadline: Instant,
        ) -> Result<Map<String, Value>, Refusal> {
            self.connection.exchange(request, deadline)
        }

        fn exchange_streamed(
            &self,
            request: &Value,
            payload: &[u8],
            deadline: Instant,
        ) -> Result<Map<String, Value>, Refusal> {
            let answered = self
                .connection
                .exchange_streamed(request, payload, deadline)?;
            if text(&answered, "kind") == Some("operation_submitted") {
                let definition = text(request.as_object().unwrap(), "definition_id");
                self.streamed
                    .lock()
                    .unwrap()
                    .push(definition.unwrap_or_default().to_owned());
            }
            Ok(answered)
        }

        fn exchange_with_secret(
            &self,
            request: &Value,
            secret: &[u8],
            deadline: Instant,
        ) -> Result<Map<String, Value>, Refusal> {
            self.connection
                .exchange_with_secret(request, secret, deadline)
        }

        fn subscribe_scoped(&self) -> mpsc::Receiver<Pushed> {
            self.connection.subscribe_scoped()
        }

        fn close(&self) {
            self.connection.close();
        }
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

        // The stored sign-in is resumed with the proof its receipt names, as a
        // window resumes it when it finds the profile signed in; timed from connecting.
        assert!(stored_sign_in_proof(&live.root, &live.profile_id).is_ok());
        let started = Instant::now();
        let resumed = Connection::open(&endpoint, &live.cohort, soon()).unwrap();
        let session = resumed
            .resume_receipt(&live.root, &live.profile_id, Frontend::Cli, soon())
            .unwrap();
        let resumed_in = started.elapsed();
        assert_eq!(session.profile_id, live.profile_id);
        assert_eq!(
            resumed.connection_id().as_deref(),
            Some(session.connection_id.as_str())
        );
        let status = resumed.status(&session, soon()).unwrap();
        assert_eq!(status["session_id"], json!(session.session_id));
        resumed.note_activity(&session, soon()).unwrap();

        // The window's own password sign-in, on a development root, timed from
        // connecting. Storing it for the other frontends is admitted only from
        // the installed desktop image, so this sign-in is not stored.
        let started = Instant::now();
        let window = Connection::open(&endpoint, &live.cohort, soon()).unwrap();
        let connected = started.elapsed();
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
        let signed_in = started.elapsed();
        println!(
            "native sign-in: connect {} ms, password sign-in {} ms; receipt resume {} ms",
            connected.as_millis(),
            signed_in.as_millis(),
            resumed_in.as_millis()
        );
        assert_eq!(held.profile_id, live.profile_id);
        assert!(
            window.status(&held, soon()).unwrap()["credential_authenticated"]
                .as_bool()
                .unwrap()
        );
        // A registered operation runs through the window's session: the
        // profile's language, as the desktop reads it.
        let language =
            crate::person_operations::read_profile_language(&window, &held, soon()).unwrap();
        assert!(
            language
                .language
                .as_deref()
                .is_none_or(|language| ["es", "en", "ca", "hu"].contains(&language)),
            "{:?}",
            language.language
        );

        // A real Modelo 303 edit's preflight and apply operands, its renewal
        // and a plain submission too large for one frame all reach the
        // runtime's staging streamed: the runtime reads each upload's header,
        // says it is ready for exactly that upload, takes its bytes, decodes
        // them and answers with the operation it admitted. The baseline is the
        // one the form read admitted in the desktop frontend's committed
        // `modelo-303-1T-en.json` envelope, extracted whole, here naming this
        // profile and the work unit the harness created for it.
        let mut baseline: Value = serde_json::from_str(include_str!(
            "../tests/data/modelo-303-admitted-baseline.json"
        ))
        .unwrap();
        baseline["bucket_id"] = json!(live.profile_id);
        baseline["work_unit_id"] = json!(live.work_unit);
        let unit = live.work_unit.clone();
        let operand = json!({"input_version": 2, "output_language": "en",
            "submission": {"edit_contract_version": 1, "baseline": baseline,
            "mutation_family": baseline["mutation_family"], "scalar_intents": []}});
        let statement = json!({"profile_id": live.profile_id,
            "csv_text": "fecha,concepto,importe\n".repeat(4 * 1024)});
        let recording = Streams {
            connection: &window,
            streamed: Mutex::new(Vec::new()),
        };
        let mut relay = crate::person_operations::OperationRelay::new();
        let mut submit = |action: &str, definition: &str, subject: String, member: &str, body| {
            let mut request = Map::new();
            request.insert("definition_id".into(), json!(definition));
            request.insert("subject_ref".into(), json!(subject));
            request.insert(member.into(), body);
            relay.handle(&recording, &held, action, &request)
        };
        let renewal = json!({"profile_id": live.profile_id, "baseline": baseline,
            "output_language": "en"});
        for (action, definition, member, body) in [
            (
                "operation_financial_submit",
                "modelo.edit.preflight",
                "input",
                operand.clone(),
            ),
            (
                "operation_financial_submit",
                "modelo.edit.apply",
                "input",
                operand,
            ),
            ("operation_submit", "modelo.edit.renew", "payload", renewal),
        ] {
            let answered = submit(action, definition, unit.clone(), member, body);
            let Ok(reply) = answered else {
                panic!("{definition}: {answered:?}");
            };
            assert_eq!(reply["kind"], "operation_submitted", "{definition}");
        }
        let classified = submit(
            "operation_submit",
            "ledger.classify.bulk",
            format!("profile:{}", live.profile_id),
            "payload",
            statement,
        )
        .unwrap();
        assert_eq!(classified["kind"], "operation_submitted");
        assert_eq!(
            *recording.streamed.lock().unwrap(),
            [
                "modelo.edit.preflight",
                "modelo.edit.apply",
                "modelo.edit.renew",
                "ledger.classify.bulk"
            ],
            "both went through the runtime's streamed upload"
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
