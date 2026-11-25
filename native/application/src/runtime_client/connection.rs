use super::endpoint::{Endpoint, OpenCancellation, RuntimeChannel};
use super::events::{Event, Pushed, event};
use super::framing::{
    DOCUMENT_FRAME, FRAME_BUDGET, SECRET_FRAME, SUBMISSION_PAYLOAD_CHUNK_BYTES,
    TRANSFER_CHUNK_BYTES, TRANSFER_LIMIT_BYTES, base64_decode, document, frame, read_idle_frame,
    sha256_hex, text,
};
use super::handshake::{Cohort, Hello, handshake_cancellable};
use super::refusal::Refusal;
use super::session::access_refusal;
use serde_json::{Map, Value};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Condvar, Mutex, mpsc};
use std::thread;
use std::time::Instant;
use zeroize::Zeroizing;

impl std::fmt::Display for Refusal {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Io(error) => write!(formatter, "{}: {error}", self.code()),
            _ => formatter.write_str(self.code()),
        }
    }
}

impl std::error::Error for Refusal {}

pub(super) struct Shared {
    pub(super) connection_id: Mutex<Option<String>>,
    pub(super) subscribers: Mutex<Vec<mpsc::Sender<Event>>>,
    pub(super) scoped: Mutex<Vec<mpsc::Sender<Pushed>>>,
    pub(super) closed: AtomicBool,
    pub(super) timeout: AtomicBool,
}

impl Shared {
    pub(super) fn subscribe(&self) -> mpsc::Receiver<Event> {
        let (sender, receiver) = mpsc::channel();
        let mut subscribers = self.subscribers.lock().unwrap_or_else(|p| p.into_inner());
        if self.closed.load(Ordering::Acquire) {
            let _ = sender.send(Event::Disconnected);
        } else {
            subscribers.push(sender);
        }
        receiver
    }

    pub(super) fn subscribe_scoped(&self) -> mpsc::Receiver<Pushed> {
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

    pub(super) fn dispatch(&self, pushed: &Pushed) {
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
    pub(super) fn bind_connection(&self, connection_id: &str) -> Result<(), Refusal> {
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

/// One verified connection: exchanges from any thread, one at a time, and the
/// events the runtime pushes between them.
pub struct Connection {
    pub(super) pipe: Arc<RuntimeChannel>,
    pub(super) hello: Hello,
    pub(super) shared: Arc<Shared>,
    pub(super) exchange: Arc<ExchangeQueue>,
    pub(super) reader: Mutex<Option<thread::JoinHandle<()>>>,
}

pub(super) struct ExchangeQueue {
    pub(super) replies: Mutex<Option<mpsc::Receiver<Map<String, Value>>>>,
    pub(super) available: Condvar,
    pub(super) closed: AtomicBool,
}

impl ExchangeQueue {
    pub(super) fn close(&self) {
        let _replies = self.replies.lock().unwrap_or_else(|p| p.into_inner());
        self.closed.store(true, Ordering::Release);
        self.available.notify_all();
    }
    pub(super) fn claim(&self, deadline: Instant) -> Result<ExchangeClaim<'_>, Refusal> {
        self.claim_observed(deadline, || {})
    }

    pub(super) fn claim_observed(
        &self,
        deadline: Instant,
        before_wait: impl FnOnce(),
    ) -> Result<ExchangeClaim<'_>, Refusal> {
        let mut before_wait = Some(before_wait);
        let mut replies = self.replies.lock().unwrap_or_else(|p| p.into_inner());
        loop {
            if self.closed.load(Ordering::Acquire) {
                return Err(Refusal::ConnectionClosed);
            }
            let Some(remaining) = deadline.checked_duration_since(Instant::now()) else {
                // A release may have woken this claimant just as its budget
                // elapsed. Pass that wake on while the receiver is available.
                if replies.is_some() {
                    self.available.notify_one();
                }
                return Err(Refusal::Timeout);
            };
            if let Some(replies) = replies.take() {
                return Ok(ExchangeClaim {
                    owner: self,
                    replies: Some(replies),
                });
            }
            if let Some(before_wait) = before_wait.take() {
                before_wait();
            }
            (replies, _) = self
                .available
                .wait_timeout(replies, remaining)
                .unwrap_or_else(|p| p.into_inner());
        }
    }
}

pub(super) struct ExchangeClaim<'a> {
    pub(super) owner: &'a ExchangeQueue,
    pub(super) replies: Option<mpsc::Receiver<Map<String, Value>>>,
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

pub(super) fn read_loop(
    pipe: Arc<RuntimeChannel>,
    shared: Arc<Shared>,
    replies: mpsc::Sender<Map<String, Value>>,
    boot_id: String,
    queue: Arc<ExchangeQueue>,
) {
    loop {
        let (kind, payload) = match read_idle_frame(&pipe) {
            Ok(frame) => frame,
            Err(Refusal::Timeout) => {
                shared.timeout.store(true, Ordering::Release);
                break;
            }
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
    queue.close();
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
        Self::open_cancellable(
            endpoint,
            cohort,
            deadline,
            Arc::new(OpenCancellation::new().map_err(Refusal::Io)?),
        )
    }

    /// The caller retains cancellation before entering any connect or hello wait.
    pub fn open_cancellable(
        endpoint: &Endpoint,
        cohort: &Cohort,
        deadline: Instant,
        cancellation: Arc<OpenCancellation>,
    ) -> Result<Self, Refusal> {
        let (pipe, hello) =
            handshake_cancellable(endpoint, cohort, true, deadline, cancellation.clone())?;
        if cancellation.cancelled() {
            return Err(Refusal::ConnectionClosed);
        }
        let pipe = Arc::new(pipe);
        let shared = Arc::new(Shared {
            connection_id: Mutex::new(None),
            subscribers: Mutex::new(Vec::new()),
            scoped: Mutex::new(Vec::new()),
            closed: AtomicBool::new(false),
            timeout: AtomicBool::new(false),
        });
        let (replies, exchange) = mpsc::channel();
        let exchange = Arc::new(ExchangeQueue {
            replies: Mutex::new(Some(exchange)),
            available: Condvar::new(),
            closed: AtomicBool::new(false),
        });
        let reader = {
            let (pipe, shared, boot_id) = (pipe.clone(), shared.clone(), hello.boot_id.clone());
            let queue = exchange.clone();
            thread::Builder::new()
                .name("runtime-connection-reader".into())
                .spawn(move || read_loop(pipe, shared, replies, boot_id, queue))
                .map_err(Refusal::Io)?
        };
        Ok(Self {
            pipe,
            hello,
            shared,
            exchange,
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

    /// Fence and wake I/O without waiting for the retained reader to join.
    pub fn request_close(&self) {
        self.shared.closed.store(true, Ordering::Release);
        self.exchange.close();
        self.pipe.close();
    }

    /// Stops exchanges and ends the connection; the reader thread is joined.
    pub fn close(&self) {
        self.request_close();
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

    pub(super) fn fail(&self, refusal: Refusal) -> Refusal {
        if !matches!(refusal, Refusal::Denied { .. }) {
            self.close();
        }
        refusal
    }

    pub(super) fn claim(&self, deadline: Instant) -> Result<ExchangeClaim<'_>, Refusal> {
        let exchange = self.exchange.claim(deadline)?;
        if self.closed() {
            return Err(Refusal::ConnectionClosed);
        }
        if Instant::now() >= deadline {
            return Err(Refusal::Timeout);
        }
        Ok(exchange)
    }

    pub(super) fn write(&self, kind: u8, payload: &[u8], deadline: Instant) -> Result<(), Refusal> {
        let framed = Zeroizing::new(frame(kind, payload)?);
        self.pipe.write_all(&framed, deadline)?;
        Ok(())
    }

    pub(super) fn next_reply(
        replies: &mpsc::Receiver<Map<String, Value>>,
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        let remaining = deadline
            .checked_duration_since(Instant::now())
            .filter(|remaining| !remaining.is_zero())
            .ok_or(Refusal::Timeout)?;
        match replies.recv_timeout(remaining) {
            Ok(_) if Instant::now() >= deadline => Err(Refusal::Timeout),
            Ok(reply) => Ok(reply),
            Err(mpsc::RecvTimeoutError::Timeout) => Err(Refusal::Timeout),
            Err(mpsc::RecvTimeoutError::Disconnected) => Err(Refusal::ConnectionClosed),
        }
    }

    pub(super) fn verify_reply(
        &self,
        reply: &Map<String, Value>,
        request_id: &str,
    ) -> Result<(), Refusal> {
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
    pub(super) fn reply(
        &self,
        replies: &mpsc::Receiver<Map<String, Value>>,
        request_id: &str,
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        let mut reply = Self::next_reply(replies, deadline).map_err(|refusal| {
            if matches!(refusal, Refusal::ConnectionClosed)
                && self.shared.timeout.load(Ordering::Acquire)
            {
                Refusal::Timeout
            } else {
                refusal
            }
        })?;
        self.verify_reply(&reply, request_id)?;
        if text(&reply, "kind").is_some_and(|kind| kind.ends_with("_transfer")) {
            reply = self.assemble_transfer(replies, &reply, request_id, deadline)?;
        }
        if text(&reply, "kind") == Some("access_refusal") {
            return Err(access_refusal(&reply));
        }
        Ok(reply)
    }

    pub(super) fn assemble_transfer(
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
pub(super) fn ready_for(request: &Value, ready: &Map<String, Value>) -> bool {
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
