//! The window's end of one view connection: [`ViewLane`].
//!
//! [`ViewLane::open`] presents an attach token on a new verified runtime
//! connection and, once the runtime answers `view_connected`, owns that
//! connection for the life of the view. There is no async runtime: the lane
//! runs on plain threads and every method takes `&self`, so a host shares one
//! lane between its command handlers.
//!
//! Two threads belong to the lane. The reader waits for the first byte of a
//! frame with no deadline, however long the page stays still, then must see
//! the rest of that frame within [`ViewTiming::frame_completion`]; it decodes
//! frames with the same rules the Python reader applies, and queues what they
//! complete. The upload pump sends the files the person chose, one transfer
//! at a time, chunk by chunk under the credit the page grants. Any thread may
//! write: each frame is written whole under one lock, so documents sit
//! between a transfer's chunks and nothing interleaves inside a frame.
//!
//! The consumer calls [`ViewLane::recv`] from one thread and gets
//! [`ViewEvent`]s in the order the frames arrived. The queue is bounded: a
//! consumer that stops reading makes the reader stop reading, and the runtime
//! unbinds a window that does not keep up. Images are the exception: the
//! queue holds at most one, and a newer image replaces an older one the
//! consumer has not taken yet, so the person always sees the newest page.
//!
//! Credit follows the stream contract. A view connection starts with no
//! credit, so the consumer grants the first with [`ViewLane::credit`]; each
//! image it draws earns one more, and never more than two are outstanding.
//! An image the queue replaces is never drawn, so the lane returns its credit
//! itself.
//!
//! The first end of the connection wins: a local [`ViewLane::close`], the
//! runtime closing the connection, a frame that breaks the contract, or a
//! frame that does not finish. It closes the connection, wakes every waiter
//! and surfaces as [`ViewEvent::Ended`] after the events already queued.
//! Nothing here retries; a closed view is attached again by a new token.

use super::{
    Violation,
    attach::{ViewAttachGrant, connect_view},
    chunks::{AssembledImage, KIND_CHUNK, KIND_DOCUMENT, MAXIMUM_FRAME_BYTES, encode_frame},
    decoder::{Downstream, DownstreamDecoder},
    documents::{
        CREDIT_MAX_IMAGES, ViewClose, ViewClosedReason, ViewCredit, ViewDialog, ViewDownload,
        ViewDownloadAnswer, ViewDownloadOutcome, ViewDownstream, ViewFileChooser,
        ViewFileChooserAnswer, ViewFileChooserOutcome, ViewInput, ViewInputEvent, ViewNavigate,
        ViewNavigateVerb, ViewNotice, ViewResize, ViewState, ViewTransferCancel,
        ViewTransferComplete, ViewTransferDirection, ViewUpload, ViewUpstream,
    },
    transfer::{SenderControl, TransferChunk, TransferReceiver, TransferSender},
};
use crate::runtime_client::{Cohort, Endpoint, Refusal};
use cadrumo_platform::runtime_pipe::Pipe;
use std::{
    collections::VecDeque,
    fmt, io,
    io::Read,
    sync::{
        Arc, Condvar, Mutex, MutexGuard,
        atomic::{AtomicBool, Ordering},
    },
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};
use zeroize::Zeroizing;

/// The most events the queue holds before the reader waits for the consumer.
const QUEUE_CAPACITY: usize = 256;

/// How long the request to close the view may take to write.
const CLOSE_REQUEST_BOUND: Duration = Duration::from_secs(1);

/// What the lane needs of a connection: a verified runtime pipe, or, in a
/// unit test of the lane's own logic, an in-memory stand-in.
pub trait ViewTransport: Send + Sync + 'static {
    /// Waits, with no deadline, for one byte, the start of a frame.
    fn read_idle_byte(&self, byte: &mut u8) -> io::Result<()>;
    /// Fills `buffer` before `deadline`.
    fn read_exact(&self, buffer: &mut [u8], deadline: Instant) -> io::Result<()>;
    /// Writes all of `bytes` before `deadline`.
    fn write_all(&self, bytes: &[u8], deadline: Instant) -> io::Result<()>;
    /// Ends the connection and every pending read and write.
    fn close(&self);
}

impl ViewTransport for Pipe {
    fn read_idle_byte(&self, byte: &mut u8) -> io::Result<()> {
        Pipe::read_idle_byte(self, byte)
    }

    fn read_exact(&self, buffer: &mut [u8], deadline: Instant) -> io::Result<()> {
        Pipe::read_exact(self, buffer, deadline)
    }

    fn write_all(&self, bytes: &[u8], deadline: Instant) -> io::Result<()> {
        Pipe::write_all(self, bytes, deadline)
    }

    fn close(&self) {
        Pipe::close(self);
    }
}

/// The bounds a lane keeps on frames it has begun. Neither limits how long
/// the stream may idle.
#[derive(Clone, Copy, Debug)]
pub struct ViewTiming {
    /// How long the rest of a frame may take once its first byte arrived.
    pub frame_completion: Duration,
    /// How long one frame may take to write.
    pub write: Duration,
}

impl Default for ViewTiming {
    fn default() -> Self {
        Self {
            frame_completion: Duration::from_secs(5),
            write: Duration::from_secs(5),
        }
    }
}

/// Why the lane ended.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ViewEnd {
    /// This side closed the lane.
    Closed,
    /// The runtime closed the connection, or it failed, without breaking the contract.
    Disconnected,
    /// A frame, header or document broke the contract; the closed name says which rule.
    Violation(&'static str),
    /// A frame, once begun, did not finish within its bound.
    TimedOut,
}

/// How an upload ended on this side.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum UploadOutcome {
    /// Every byte and the completion document were sent.
    Sent,
    /// The page stopped receiving it.
    Cancelled,
    /// The source failed, or its size differed from what was declared; the upload was cancelled.
    Failed,
}

/// What the stream delivered, in arrival order.
pub enum ViewEvent {
    /// The newest complete image; it is drawn, then credited.
    Image(AssembledImage),
    State(ViewState),
    Notice(ViewNotice),
    /// The runtime's last document, with the reason the view ended.
    Closed(ViewClosedReason),
    /// A download is offered: accept, decline or ignore it.
    Download(ViewDownload),
    /// The page asks for files: supply them or cancel.
    FileChooser(ViewFileChooser),
    /// One checked chunk of an accepted download, in order.
    DownloadChunk(TransferChunk),
    /// A download's bytes arrived whole and agree with the sender's size and sha256.
    DownloadComplete(ViewTransferComplete),
    /// The page stopped sending a download.
    DownloadCancelled {
        transfer_id: u32,
    },
    /// An upload from [`ViewLane::supply_files`] is over.
    UploadEnded {
        chooser_id: u32,
        transfer_id: u32,
        outcome: UploadOutcome,
    },
    /// The lane ended; this is the last event, and it repeats.
    Ended(ViewEnd),
}

impl fmt::Debug for ViewEvent {
    /// The kind of event only: its content is private.
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::Image(_) => "ViewEvent::Image",
            Self::State(_) => "ViewEvent::State",
            Self::Notice(_) => "ViewEvent::Notice",
            Self::Closed(_) => "ViewEvent::Closed",
            Self::Download(_) => "ViewEvent::Download",
            Self::FileChooser(_) => "ViewEvent::FileChooser",
            Self::DownloadChunk(_) => "ViewEvent::DownloadChunk",
            Self::DownloadComplete(_) => "ViewEvent::DownloadComplete",
            Self::DownloadCancelled { .. } => "ViewEvent::DownloadCancelled",
            Self::UploadEnded { .. } => "ViewEvent::UploadEnded",
            Self::Ended(_) => "ViewEvent::Ended",
        })
    }
}

/// One file the person chose for a page's file chooser.
pub struct UploadFile {
    pub name: String,
    pub mime: Option<String>,
    /// The file's exact byte count; an upload whose bytes differ is cancelled.
    pub size: u64,
    pub source: Box<dyn Read + Send>,
}

impl fmt::Debug for UploadFile {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("UploadFile(..)")
    }
}

fn locked<T>(mutex: &Mutex<T>) -> MutexGuard<'_, T> {
    mutex
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

#[derive(Debug, PartialEq, Eq)]
enum Pushed {
    Queued,
    /// An older image the consumer never took was dropped for the new one.
    Replaced,
    /// The lane had ended.
    Dropped,
}

#[derive(Default)]
struct QueueState {
    items: VecDeque<ViewEvent>,
    end: Option<ViewEnd>,
}

#[derive(Default)]
struct EventQueue {
    state: Mutex<QueueState>,
    ready: Condvar,
    space: Condvar,
}

impl EventQueue {
    /// Queues an event, waiting for room unless it is an image, which replaces
    /// the image already queued.
    fn push(&self, event: ViewEvent) -> Pushed {
        let image = matches!(event, ViewEvent::Image(_));
        let mut state = locked(&self.state);
        loop {
            if state.end.is_some() {
                return Pushed::Dropped;
            }
            if image || state.items.len() < QUEUE_CAPACITY {
                break;
            }
            state = self
                .space
                .wait(state)
                .unwrap_or_else(|poisoned| poisoned.into_inner());
        }
        let older = if image {
            state
                .items
                .iter()
                .position(|item| matches!(item, ViewEvent::Image(_)))
        } else {
            None
        };
        let replaced = older.and_then(|index| state.items.remove(index)).is_some();
        state.items.push_back(event);
        self.ready.notify_one();
        if replaced {
            Pushed::Replaced
        } else {
            Pushed::Queued
        }
    }

    /// The next event, waiting up to `timeout`; once the lane ended and the
    /// queue is empty, the end, every time.
    fn recv(&self, timeout: Duration) -> Option<ViewEvent> {
        let deadline = Instant::now() + timeout;
        let mut state = locked(&self.state);
        loop {
            if let Some(event) = state.items.pop_front() {
                self.space.notify_one();
                return Some(event);
            }
            if let Some(end) = state.end {
                return Some(ViewEvent::Ended(end));
            }
            let remaining = deadline.checked_duration_since(Instant::now())?;
            state = self
                .ready
                .wait_timeout(state, remaining)
                .unwrap_or_else(|poisoned| poisoned.into_inner())
                .0;
        }
    }

    /// Records the first end and wakes the consumer and any waiting producer.
    fn finish(&self, end: ViewEnd) {
        let mut state = locked(&self.state);
        state.end.get_or_insert(end);
        self.ready.notify_all();
        self.space.notify_all();
    }

    /// Drops every queued event, wiping the images among them.
    fn clear(&self) {
        locked(&self.state).items.clear();
        self.space.notify_all();
    }
}

struct UploadJob {
    chooser_id: u32,
    file: UploadFile,
}

#[derive(Default)]
struct UploadState {
    jobs: VecDeque<UploadJob>,
    active: Option<(u32, Arc<SenderControl>)>,
    last_started: u32,
    closed: bool,
}

#[derive(Default)]
struct Uploads {
    state: Mutex<UploadState>,
    wake: Condvar,
}

impl Uploads {
    fn enqueue(&self, chooser_id: u32, files: Vec<UploadFile>) -> bool {
        let mut state = locked(&self.state);
        if state.closed {
            return false;
        }
        state
            .jobs
            .extend(files.into_iter().map(|file| UploadJob { chooser_id, file }));
        self.wake.notify_all();
        true
    }

    /// The next file to send, waiting for one; `None` once the lane ended.
    fn next_job(&self) -> Option<UploadJob> {
        let mut state = locked(&self.state);
        loop {
            if state.closed {
                return None;
            }
            if let Some(job) = state.jobs.pop_front() {
                return Some(job);
            }
            state = self
                .wake
                .wait(state)
                .unwrap_or_else(|poisoned| poisoned.into_inner());
        }
    }

    fn begin(&self, transfer_id: u32, control: Arc<SenderControl>) {
        let mut state = locked(&self.state);
        state.last_started = transfer_id;
        state.active = Some((transfer_id, control));
    }

    fn finish(&self) {
        locked(&self.state).active = None;
    }

    /// Applies a credit document of the page's. Credit for an upload that is
    /// already over crossed its completion on the wire; credit for one never
    /// announced is a violation.
    fn grant(&self, transfer_id: u32, chunks: u8) -> Result<(), Violation> {
        let state = locked(&self.state);
        match &state.active {
            Some((active, control)) if *active == transfer_id => control.grant(chunks),
            _ if transfer_id <= state.last_started => Ok(()),
            _ => Err(Violation("view_transfer_unknown")),
        }
    }

    /// Applies the page's cancel of one of this side's uploads.
    fn cancel_by_peer(&self, transfer_id: u32) -> Result<(), Violation> {
        let state = locked(&self.state);
        match &state.active {
            Some((active, control)) if *active == transfer_id => {
                control.cancel();
                Ok(())
            }
            _ if transfer_id <= state.last_started => Ok(()),
            _ => Err(Violation("view_transfer_unknown")),
        }
    }

    /// Ends every upload: queued files are dropped and the one in flight stops.
    fn shutdown(&self) {
        let mut state = locked(&self.state);
        state.closed = true;
        state.jobs.clear();
        if let Some((_, control)) = &state.active {
            control.cancel();
        }
        self.wake.notify_all();
    }
}

fn ended_by(error: io::Error) -> ViewEnd {
    if error.kind() == io::ErrorKind::TimedOut {
        ViewEnd::TimedOut
    } else {
        ViewEnd::Disconnected
    }
}

/// Reads one frame of kind `J` or `B`. The wait for its first byte has no
/// deadline; the rest of the frame has `completion`.
fn read_view_frame(
    transport: &dyn ViewTransport,
    completion: Duration,
) -> Result<(u8, Zeroizing<Vec<u8>>), ViewEnd> {
    let mut header = [0u8; 5];
    transport.read_idle_byte(&mut header[0]).map_err(ended_by)?;
    let deadline = Instant::now() + completion;
    transport
        .read_exact(&mut header[1..], deadline)
        .map_err(ended_by)?;
    let kind = header[0];
    let size = u32::from_be_bytes([header[1], header[2], header[3], header[4]]) as usize;
    if !matches!(kind, KIND_DOCUMENT | KIND_CHUNK) || size == 0 || size > MAXIMUM_FRAME_BYTES {
        return Err(ViewEnd::Violation("view_frame"));
    }
    let mut payload = Zeroizing::new(vec![0u8; size]);
    transport
        .read_exact(&mut payload, deadline)
        .map_err(ended_by)?;
    Ok((kind, payload))
}

struct Core {
    transport: Arc<dyn ViewTransport>,
    timing: ViewTiming,
    write: Mutex<()>,
    closed: AtomicBool,
    /// Images the window has granted credit for and not yet received.
    window: Mutex<u8>,
    events: EventQueue,
    downloads: Arc<TransferReceiver>,
    uploads: Uploads,
}

impl Core {
    fn is_closed(&self) -> bool {
        self.closed.load(Ordering::Acquire)
    }

    /// Ends the lane. The first end wins; later calls change nothing.
    fn fail(&self, end: ViewEnd) {
        if self.closed.swap(true, Ordering::AcqRel) {
            return;
        }
        self.transport.close();
        self.events.finish(end);
        self.uploads.shutdown();
    }

    /// Writes one whole frame; a failed write ends the lane.
    fn write_frame(&self, frame: &[u8]) -> Result<(), Refusal> {
        self.write_frame_within(frame, self.timing.write)
    }

    fn write_frame_within(&self, frame: &[u8], bound: Duration) -> Result<(), Refusal> {
        let _writing = locked(&self.write);
        if self.is_closed() {
            return Err(Refusal::ConnectionClosed);
        }
        self.transport
            .write_all(frame, Instant::now() + bound)
            .map_err(|error| {
                let end = ended_by(error);
                self.fail(end);
                if end == ViewEnd::TimedOut {
                    Refusal::DeadlineExceeded
                } else {
                    Refusal::ConnectionClosed
                }
            })
    }

    /// Validates a document and writes it. A document the contract refuses is
    /// never written and does not end the lane.
    fn send(&self, document: &ViewUpstream) -> Result<(), Refusal> {
        self.send_within(document, self.timing.write)
    }

    fn send_within(&self, document: &ViewUpstream, bound: Duration) -> Result<(), Refusal> {
        let payload = document.encode().map_err(|_| Refusal::InvalidFrame)?;
        let frame = encode_frame(KIND_DOCUMENT, &payload).map_err(|_| Refusal::InvalidFrame)?;
        self.write_frame_within(&frame, bound)
    }

    /// Grants the page credit for images the window has room for.
    fn grant_credit(&self, images: u8) -> Result<(), Refusal> {
        let credit = ViewCredit { images };
        credit.validate().map_err(|_| Refusal::InvalidFrame)?;
        {
            let mut window = locked(&self.window);
            if *window + images > CREDIT_MAX_IMAGES {
                return Err(Refusal::InvalidFrame);
            }
            *window += images;
        }
        self.send(&ViewUpstream::Credit(credit))
    }

    fn read_loop(&self) {
        let mut decoder = DownstreamDecoder::new(self.downloads.clone());
        loop {
            let outcome = read_view_frame(self.transport.as_ref(), self.timing.frame_completion)
                .and_then(|(kind, payload)| self.dispatch(&mut decoder, kind, &payload));
            if let Err(end) = outcome {
                decoder.discard();
                self.fail(end);
                return;
            }
        }
    }

    fn dispatch(
        &self,
        decoder: &mut DownstreamDecoder,
        kind: u8,
        payload: &[u8],
    ) -> Result<(), ViewEnd> {
        let decoded = decoder
            .push(kind, payload)
            .map_err(|violation| ViewEnd::Violation(violation.check()))?;
        match decoded {
            None => Ok(()),
            Some(Downstream::Image(image)) => self.deliver_image(image),
            Some(Downstream::Chunk(chunk)) => {
                self.events.push(ViewEvent::DownloadChunk(chunk));
                Ok(())
            }
            Some(Downstream::Document(document)) => self.deliver_document(document),
        }
    }

    fn deliver_image(&self, image: AssembledImage) -> Result<(), ViewEnd> {
        {
            let mut window = locked(&self.window);
            if *window == 0 {
                return Err(ViewEnd::Violation("view_image_without_credit"));
            }
            *window -= 1;
        }
        if self.events.push(ViewEvent::Image(image)) == Pushed::Replaced {
            // The replaced image is never drawn, so nothing else would credit it.
            self.grant_credit(1).map_err(|_| ViewEnd::Disconnected)?;
        }
        Ok(())
    }

    fn deliver_document(&self, document: ViewDownstream) -> Result<(), ViewEnd> {
        let event = match document {
            ViewDownstream::State(state) => ViewEvent::State(state),
            ViewDownstream::Notice(notice) => ViewEvent::Notice(notice),
            ViewDownstream::Closed(closed) => ViewEvent::Closed(closed.reason),
            ViewDownstream::Download(download) => ViewEvent::Download(download),
            ViewDownstream::FileChooser(chooser) => ViewEvent::FileChooser(chooser),
            ViewDownstream::TransferComplete(complete) => ViewEvent::DownloadComplete(complete),
            ViewDownstream::TransferCredit(credit) => {
                return self
                    .uploads
                    .grant(credit.transfer_id, credit.chunks)
                    .map_err(|violation| ViewEnd::Violation(violation.check()));
            }
            ViewDownstream::TransferCancel(cancel) => match cancel.direction {
                ViewTransferDirection::Download => ViewEvent::DownloadCancelled {
                    transfer_id: cancel.transfer_id,
                },
                ViewTransferDirection::Upload => {
                    return self
                        .uploads
                        .cancel_by_peer(cancel.transfer_id)
                        .map_err(|violation| ViewEnd::Violation(violation.check()));
                }
            },
            // The decoder consumes announcements; one that reaches here is not an image run.
            ViewDownstream::Image(_) => {
                return Err(ViewEnd::Violation("view_image_without_chunks"));
            }
        };
        self.events.push(event);
        Ok(())
    }

    fn pump_loop(&self) {
        let mut last_id: u32 = 0;
        while let Some(job) = self.uploads.next_job() {
            let Some(transfer_id) = last_id.checked_add(1) else {
                self.fail(ViewEnd::Violation("view_transfer_id"));
                return;
            };
            last_id = transfer_id;
            let chooser_id = job.chooser_id;
            let Some(outcome) = self.send_file(transfer_id, job) else {
                // Not sending a file the person chose must not leave the view looking alive.
                self.fail(ViewEnd::Disconnected);
                return;
            };
            self.events.push(ViewEvent::UploadEnded {
                chooser_id,
                transfer_id,
                outcome,
            });
        }
    }

    /// Announces one file and streams it under credit; `None` when the lane ended.
    fn send_file(&self, transfer_id: u32, job: UploadJob) -> Option<UploadOutcome> {
        let UploadFile {
            name,
            mime,
            size,
            source,
        } = job.file;
        let mut sender = TransferSender::new(transfer_id, source).ok()?;
        let control = sender.control();
        // The page cannot grant credit before it hears of the upload.
        self.uploads.begin(transfer_id, control.clone());
        let announced = self.send(&ViewUpstream::Upload(ViewUpload {
            chooser_id: job.chooser_id,
            transfer_id,
            name,
            size,
            mime,
        }));
        let outcome = match announced {
            Ok(()) => self.stream_upload(&mut sender, &control, size),
            Err(_) => None,
        };
        self.uploads.finish();
        outcome
    }

    fn stream_upload(
        &self,
        sender: &mut TransferSender,
        control: &SenderControl,
        declared: u64,
    ) -> Option<UploadOutcome> {
        loop {
            if !control.wait_ready() {
                if self.is_closed() {
                    return None;
                }
                return self.cancel_upload(sender.transfer_id(), UploadOutcome::Cancelled);
            }
            let chunk = match sender.next_chunk() {
                Ok(Some(chunk)) => chunk,
                Ok(None) => continue,
                Err(_) => return self.cancel_upload(sender.transfer_id(), UploadOutcome::Failed),
            };
            let total = chunk.offset + chunk.body_length as u64;
            if total > declared || (chunk.last && total != declared) {
                // The receiver would refuse these bytes and end the whole connection.
                return self.cancel_upload(sender.transfer_id(), UploadOutcome::Failed);
            }
            let frame = encode_frame(KIND_CHUNK, &chunk.payload).ok()?;
            self.write_frame(&frame).ok()?;
            if chunk.last {
                let Ok(complete) = sender.completion() else {
                    return self.cancel_upload(sender.transfer_id(), UploadOutcome::Failed);
                };
                self.send(&ViewUpstream::TransferComplete(complete)).ok()?;
                return Some(UploadOutcome::Sent);
            }
        }
    }

    fn cancel_upload(&self, transfer_id: u32, outcome: UploadOutcome) -> Option<UploadOutcome> {
        self.send(&ViewUpstream::TransferCancel(ViewTransferCancel {
            direction: ViewTransferDirection::Upload,
            transfer_id,
        }))
        .ok()?;
        Some(outcome)
    }
}

/// One open view connection, shared by the host's threads.
pub struct ViewLane {
    core: Arc<Core>,
    threads: Mutex<Vec<JoinHandle<()>>>,
}

impl ViewLane {
    /// Presents `grant` on a new verified connection to `endpoint` before
    /// `deadline` and, once the runtime answers `view_connected`, starts the
    /// lane. The stream starts with no credit: grant the first with
    /// [`ViewLane::credit`].
    pub fn open(
        endpoint: &Endpoint,
        cohort: &Cohort,
        grant: ViewAttachGrant,
        deadline: Instant,
    ) -> Result<Self, Refusal> {
        let (pipe, _connected) = connect_view(endpoint, cohort, grant, deadline)?;
        Self::start(Arc::new(pipe), ViewTiming::default())
    }

    /// Runs a lane over any transport that already carries the stream.
    pub(crate) fn start(
        transport: Arc<dyn ViewTransport>,
        timing: ViewTiming,
    ) -> Result<Self, Refusal> {
        let core = Arc::new(Core {
            transport,
            timing,
            write: Mutex::new(()),
            closed: AtomicBool::new(false),
            window: Mutex::new(0),
            events: EventQueue::default(),
            downloads: Arc::new(TransferReceiver::new(ViewTransferDirection::Download)),
            uploads: Uploads::default(),
        });
        let lane = Self {
            core: core.clone(),
            threads: Mutex::new(Vec::new()),
        };
        let reader = {
            let core = core.clone();
            thread::Builder::new()
                .name("view-stream-reader".into())
                .spawn(move || core.read_loop())
        };
        let pump = {
            let core = core.clone();
            thread::Builder::new()
                .name("view-stream-upload".into())
                .spawn(move || core.pump_loop())
        };
        match (reader, pump) {
            (Ok(reader), Ok(pump)) => {
                locked(&lane.threads).extend([reader, pump]);
                Ok(lane)
            }
            (reader, pump) => {
                core.fail(ViewEnd::Closed);
                let started = reader.into_iter().chain(pump);
                started.for_each(|thread| {
                    let _ = thread.join();
                });
                Err(Refusal::Io(io::Error::other(
                    "the view threads did not start",
                )))
            }
        }
    }

    /// The next event, waiting up to `timeout`; `None` if none came. After
    /// the lane ended and the queue drained, [`ViewEvent::Ended`], every time.
    pub fn recv(&self, timeout: Duration) -> Option<ViewEvent> {
        self.core.events.recv(timeout)
    }

    /// Whether the lane ended.
    pub fn is_closed(&self) -> bool {
        self.core.is_closed()
    }

    /// The person closed the page or the window: asks the view to publish its
    /// session and settle, then closes the lane as [`ViewLane::close`] does.
    ///
    /// This is a close, not a cancellation. The request gets a short bound
    /// and is best effort: a lane that cannot send it is closed all the same,
    /// and a connection that drops without it is closed the same way by the
    /// runtime. Do not use it when the session was lost; [`ViewLane::close`]
    /// then ends the lane with nothing to publish.
    pub fn end_view(&self) {
        let bound = self.core.timing.write.min(CLOSE_REQUEST_BOUND);
        // Whether it was sent changes nothing here: the lane closes either way.
        let _ = self
            .core
            .send_within(&ViewUpstream::Close(ViewClose {}), bound);
        self.close();
    }

    /// Ends the view from this side: closes the connection, drops what is
    /// queued and waits for the lane's threads. The runtime unbinds the view
    /// at once; there is nothing to send first, and a view whose connection
    /// drops is closed the same way as one whose window sent `view.close`.
    pub fn close(&self) {
        self.core.fail(ViewEnd::Closed);
        self.core.events.clear();
        let threads = std::mem::take(&mut *locked(&self.threads));
        for thread in threads {
            if thread.thread().id() != thread::current().id() {
                let _ = thread.join();
            }
        }
    }

    /// Grants the page credit for `images` more images. Call it once per
    /// image drawn, and once with two to start the stream. More than two
    /// outstanding is refused here and does not end the lane.
    pub fn credit(&self, images: u8) -> Result<(), Refusal> {
        self.core.grant_credit(images)
    }

    /// Forwards one person input event to the page.
    pub fn input(&self, event: ViewInputEvent) -> Result<(), Refusal> {
        self.core.send(&ViewUpstream::Input(ViewInput { event }))
    }

    /// Asks the page to go back, forward, reload or home.
    pub fn navigate(&self, verb: ViewNavigateVerb) -> Result<(), Refusal> {
        self.core
            .send(&ViewUpstream::Navigate(ViewNavigate { verb }))
    }

    /// Tells the page the panel's new CSS size and device pixel ratio.
    pub fn resize(&self, css_width: u32, css_height: u32, scale: f64) -> Result<(), Refusal> {
        self.core.send(&ViewUpstream::Resize(ViewResize {
            css_width,
            css_height,
            scale,
        }))
    }

    /// Answers the page dialog announced under `dialog_id`.
    pub fn dialog(
        &self,
        dialog_id: u32,
        accept: bool,
        prompt_text: Option<String>,
    ) -> Result<(), Refusal> {
        self.core.send(&ViewUpstream::Dialog(ViewDialog {
            dialog_id,
            accept,
            prompt_text,
        }))
    }

    /// Accepts the download offered under `transfer_id`, whose bytes the host
    /// will write where the person chose. `size` is the byte count the offer
    /// declared, if it did. No bytes flow until [`ViewLane::download_credit`].
    pub fn accept_download(&self, transfer_id: u32, size: Option<u64>) -> Result<(), Refusal> {
        self.core
            .downloads
            .expect(transfer_id, size)
            .map_err(|_| Refusal::InvalidFrame)?;
        self.core
            .send(&ViewUpstream::DownloadAnswer(ViewDownloadAnswer {
                transfer_id,
                outcome: ViewDownloadOutcome::Accepted,
            }))
    }

    /// Declines the offered download: `Refused` when the host will not take
    /// it, `Cancelled` when the person closed the save dialog.
    pub fn decline_download(
        &self,
        transfer_id: u32,
        outcome: ViewDownloadOutcome,
    ) -> Result<(), Refusal> {
        if outcome == ViewDownloadOutcome::Accepted {
            return Err(Refusal::InvalidFrame);
        }
        self.core
            .send(&ViewUpstream::DownloadAnswer(ViewDownloadAnswer {
                transfer_id,
                outcome,
            }))
    }

    /// Admits `chunks` more chunks of an accepted download. Grant as the
    /// host writes bytes out: at most 32 are outstanding, about 2 MiB.
    pub fn download_credit(&self, transfer_id: u32, chunks: u8) -> Result<(), Refusal> {
        let credit = self
            .core
            .downloads
            .grant(transfer_id, chunks)
            .map_err(|_| Refusal::InvalidFrame)?;
        self.core.send(&ViewUpstream::TransferCredit(credit))
    }

    /// Stops receiving an accepted download. Chunks already in flight are
    /// discarded; the host discards the bytes it wrote.
    pub fn cancel_download(&self, transfer_id: u32) -> Result<(), Refusal> {
        match self.core.downloads.cancel(transfer_id) {
            Some(cancel) => self.core.send(&ViewUpstream::TransferCancel(cancel)),
            None => Ok(()),
        }
    }

    /// Tells the page the person closed the open dialog.
    pub fn cancel_file_chooser(&self, chooser_id: u32) -> Result<(), Refusal> {
        self.core
            .send(&ViewUpstream::FileChooserAnswer(ViewFileChooserAnswer {
                chooser_id,
                outcome: ViewFileChooserOutcome::Cancelled,
                file_count: 0,
            }))
    }

    /// Supplies the files the person chose for the chooser under `chooser_id`.
    ///
    /// The answer is sent now. The files then stream one at a time from the
    /// lane's upload thread, each under the credit the page grants, and each
    /// ends with a [`ViewEvent::UploadEnded`]. A page that did not allow
    /// several files gets exactly one.
    pub fn supply_files(&self, chooser_id: u32, files: Vec<UploadFile>) -> Result<(), Refusal> {
        let file_count = u32::try_from(files.len()).map_err(|_| Refusal::InvalidFrame)?;
        for file in &files {
            // Each file must form a document the page accepts, or none is sent.
            ViewUpstream::Upload(ViewUpload {
                chooser_id,
                transfer_id: 1,
                name: file.name.clone(),
                size: file.size,
                mime: file.mime.clone(),
            })
            .validate()
            .map_err(|_| Refusal::InvalidFrame)?;
        }
        self.core
            .send(&ViewUpstream::FileChooserAnswer(ViewFileChooserAnswer {
                chooser_id,
                outcome: ViewFileChooserOutcome::Supplied,
                file_count,
            }))?;
        if self.core.uploads.enqueue(chooser_id, files) {
            Ok(())
        } else {
            Err(Refusal::ConnectionClosed)
        }
    }
}

impl Drop for ViewLane {
    fn drop(&mut self) {
        self.close();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::view_stream::{
        chunks::CHUNK_BODY_BYTES,
        documents::{TRANSFER_CREDIT_MAX_CHUNKS, TextInput, ViewImage},
        vectors::{pattern, sha256_hex},
    };
    use serde_json::{Value, json};
    use std::{io::Cursor, sync::mpsc};

    #[derive(Default)]
    struct HalfState {
        bytes: VecDeque<u8>,
        eof: bool,
        aborted: bool,
    }

    #[derive(Default)]
    struct Half {
        state: Mutex<HalfState>,
        ready: Condvar,
    }

    /// One end of an in-memory duplex stream that behaves as a pipe does:
    /// closing aborts this end's reads and writes and ends the other's reads.
    struct End {
        incoming: Arc<Half>,
        outgoing: Arc<Half>,
    }

    fn duplex() -> (Arc<End>, Arc<End>) {
        let (one, other) = (Arc::new(Half::default()), Arc::new(Half::default()));
        (
            Arc::new(End {
                incoming: one.clone(),
                outgoing: other.clone(),
            }),
            Arc::new(End {
                incoming: other,
                outgoing: one,
            }),
        )
    }

    impl End {
        fn pull(&self, buffer: &mut [u8], deadline: Option<Instant>) -> io::Result<()> {
            let mut state = locked(&self.incoming.state);
            let mut filled = 0;
            while filled < buffer.len() {
                if state.aborted {
                    return Err(io::ErrorKind::ConnectionAborted.into());
                }
                if let Some(byte) = state.bytes.pop_front() {
                    buffer[filled] = byte;
                    filled += 1;
                    continue;
                }
                if state.eof {
                    return Err(io::ErrorKind::UnexpectedEof.into());
                }
                state = match deadline {
                    None => self
                        .incoming
                        .ready
                        .wait(state)
                        .unwrap_or_else(|poisoned| poisoned.into_inner()),
                    Some(deadline) => {
                        let Some(remaining) = deadline.checked_duration_since(Instant::now())
                        else {
                            return Err(io::ErrorKind::TimedOut.into());
                        };
                        self.incoming
                            .ready
                            .wait_timeout(state, remaining)
                            .unwrap_or_else(|poisoned| poisoned.into_inner())
                            .0
                    }
                };
            }
            Ok(())
        }

        /// The peer's side of a frame: writes `kind || length || payload`.
        fn send_frame(&self, kind: u8, payload: &[u8]) {
            let frame = encode_frame(kind, payload).unwrap();
            self.push_raw(&frame);
        }

        fn push_raw(&self, bytes: &[u8]) {
            let mut state = locked(&self.outgoing.state);
            state.bytes.extend(bytes);
            self.outgoing.ready.notify_all();
        }

        fn send_json(&self, document: &Value) {
            self.send_frame(KIND_DOCUMENT, &serde_json::to_vec(document).unwrap());
        }

        /// Reads one frame the lane wrote.
        fn take_frame(&self) -> (u8, Vec<u8>) {
            let deadline = Some(Instant::now() + Duration::from_secs(10));
            let mut header = [0u8; 5];
            self.pull(&mut header, deadline).expect("a frame header");
            let size = u32::from_be_bytes([header[1], header[2], header[3], header[4]]) as usize;
            let mut payload = vec![0u8; size];
            self.pull(&mut payload, deadline).expect("a frame payload");
            (header[0], payload)
        }

        fn take_json(&self) -> Value {
            let (kind, payload) = self.take_frame();
            assert_eq!(kind, KIND_DOCUMENT);
            serde_json::from_slice(&payload).unwrap()
        }

        fn is_quiet(&self) -> bool {
            thread::sleep(Duration::from_millis(150));
            locked(&self.incoming.state).bytes.is_empty()
        }
    }

    impl ViewTransport for End {
        fn read_idle_byte(&self, byte: &mut u8) -> io::Result<()> {
            self.pull(std::slice::from_mut(byte), None)
        }

        fn read_exact(&self, buffer: &mut [u8], deadline: Instant) -> io::Result<()> {
            self.pull(buffer, Some(deadline))
        }

        fn write_all(&self, bytes: &[u8], _deadline: Instant) -> io::Result<()> {
            let closed_here = locked(&self.incoming.state).aborted;
            let mut state = locked(&self.outgoing.state);
            if closed_here || state.eof || state.aborted {
                return Err(io::ErrorKind::BrokenPipe.into());
            }
            state.bytes.extend(bytes);
            self.outgoing.ready.notify_all();
            Ok(())
        }

        fn close(&self) {
            locked(&self.incoming.state).aborted = true;
            locked(&self.outgoing.state).eof = true;
            self.incoming.ready.notify_all();
            self.outgoing.ready.notify_all();
        }
    }

    /// What the runtime does to provoke a violation.
    type Provoke = Box<dyn Fn(&End)>;

    fn lane_with(timing: ViewTiming) -> (ViewLane, Arc<End>) {
        let (window, runtime) = duplex();
        (ViewLane::start(window, timing).unwrap(), runtime)
    }

    fn lane() -> (ViewLane, Arc<End>) {
        lane_with(ViewTiming::default())
    }

    fn soon() -> Duration {
        Duration::from_secs(10)
    }

    fn announce(sequence: u32, length: usize) -> Value {
        json!({"kind": "view.image", "sequence": sequence, "byte_length": length,
               "pixel_width": 4, "pixel_height": 4, "css_width": 4, "css_height": 4, "scale": 1.0})
    }

    /// The runtime's side of one image: its announcement and its chunks.
    fn send_image(runtime: &End, sequence: u32, data: &[u8]) {
        runtime.send_json(&announce(sequence, data.len()));
        let count = data.len().div_ceil(CHUNK_BODY_BYTES);
        for (index, body) in data.chunks(CHUNK_BODY_BYTES).enumerate() {
            let last = index + 1 == count;
            let mut payload = vec![1, u8::from(last), 0, 0];
            payload.extend(sequence.to_be_bytes());
            payload.extend((index as u16).to_be_bytes());
            payload.extend((count as u16).to_be_bytes());
            payload.extend((data.len() as u32).to_be_bytes());
            payload.extend(body);
            runtime.send_frame(KIND_CHUNK, &payload);
        }
    }

    fn state_document(title: &str) -> Value {
        json!({"kind": "view.state", "origin": "https://sede.agenciatributaria.gob.es",
               "path": "/Sede/inicio.html", "title": title, "can_go_back": false,
               "can_go_forward": false, "loading": false, "phase": "browsing"})
    }

    fn announcement(sequence: u32) -> ViewImage {
        match serde_json::from_value(announce(sequence, 1)).unwrap() {
            ViewDownstream::Image(image) => image,
            _ => panic!("an image announcement"),
        }
    }

    fn state_of(title: &str) -> ViewState {
        match serde_json::from_value(state_document(title)).unwrap() {
            ViewDownstream::State(state) => state,
            _ => panic!("a state document"),
        }
    }

    fn next_event(lane: &ViewLane) -> ViewEvent {
        lane.recv(soon()).expect("an event")
    }

    #[test]
    fn upstream_calls_reach_the_wire_as_the_documents_python_reads() {
        let (lane, runtime) = lane();
        lane.credit(2).unwrap();
        assert_eq!(
            runtime.take_json(),
            json!({"kind": "view.credit", "images": 2})
        );
        lane.navigate(ViewNavigateVerb::Reload).unwrap();
        assert_eq!(
            runtime.take_json(),
            json!({"kind": "view.navigate", "verb": "reload"})
        );
        lane.resize(1280, 800, 1.25).unwrap();
        assert_eq!(
            runtime.take_json(),
            json!({"kind": "view.resize", "css_width": 1280, "css_height": 800, "scale": 1.25})
        );
        lane.dialog(3, true, Some("sí".into())).unwrap();
        assert_eq!(
            runtime.take_json(),
            json!({"kind": "view.dialog", "dialog_id": 3, "accept": true, "prompt_text": "sí"})
        );
        lane.dialog(4, false, None).unwrap();
        assert_eq!(
            runtime.take_json(),
            json!({"kind": "view.dialog", "dialog_id": 4, "accept": false})
        );
        lane.input(ViewInputEvent::Text(TextInput { text: "ñ".into() }))
            .unwrap();
        assert_eq!(
            runtime.take_json(),
            json!({"kind": "view.input", "event": {"type": "text", "text": "ñ"}})
        );
    }

    #[test]
    fn documents_the_contract_refuses_are_never_written_and_do_not_end_the_lane() {
        let (lane, runtime) = lane();
        assert!(matches!(
            lane.resize(0, 800, 1.0),
            Err(Refusal::InvalidFrame)
        ));
        assert!(matches!(
            lane.dialog(0, true, None),
            Err(Refusal::InvalidFrame)
        ));
        assert!(matches!(
            lane.dialog(1, false, Some("x".into())),
            Err(Refusal::InvalidFrame)
        ));
        assert!(matches!(lane.credit(0), Err(Refusal::InvalidFrame)));
        assert!(matches!(lane.credit(3), Err(Refusal::InvalidFrame)));
        lane.credit(2).unwrap();
        assert!(
            matches!(lane.credit(1), Err(Refusal::InvalidFrame)),
            "two are outstanding"
        );
        assert!(!lane.is_closed());
        assert_eq!(
            runtime.take_json(),
            json!({"kind": "view.credit", "images": 2}),
            "the first frame on the wire is the one legal credit"
        );
        assert!(runtime.is_quiet());
    }

    #[test]
    fn an_image_arrives_whole_and_each_drawn_image_earns_credit_back() {
        let (lane, runtime) = lane();
        lane.credit(2).unwrap();
        runtime.take_json();
        let data = pattern(0, 70_000);
        send_image(&runtime, 7, &data);
        let ViewEvent::Image(image) = next_event(&lane) else {
            panic!("an image");
        };
        assert_eq!(image.announcement.sequence, 7);
        assert_eq!(sha256_hex(&image.data), sha256_hex(&data));
        lane.credit(1).unwrap();
        assert_eq!(
            runtime.take_json(),
            json!({"kind": "view.credit", "images": 1})
        );
    }

    #[test]
    fn a_newer_image_replaces_one_nobody_took_and_its_credit_comes_back() {
        let (lane, runtime) = lane();
        lane.credit(2).unwrap();
        runtime.take_json();
        send_image(&runtime, 1, &pattern(0, 100));
        send_image(&runtime, 5, &pattern(1, 200));
        // The lane credits the image it dropped; seeing that credit means both were read.
        assert_eq!(
            runtime.take_json(),
            json!({"kind": "view.credit", "images": 1})
        );
        let ViewEvent::Image(image) = next_event(&lane) else {
            panic!("an image");
        };
        assert_eq!(image.announcement.sequence, 5, "the newest wins");
        assert_eq!(sha256_hex(&image.data), sha256_hex(&pattern(1, 200)));
        assert!(lane.recv(Duration::from_millis(100)).is_none());
        // Two outstanding credits were spent by two images; one came back, so one more may be granted.
        lane.credit(1).unwrap();
        assert!(matches!(lane.credit(1), Err(Refusal::InvalidFrame)));
    }

    #[test]
    fn documents_keep_their_order_around_images() {
        let (lane, runtime) = lane();
        lane.credit(2).unwrap();
        runtime.take_json();
        runtime.send_json(&state_document("one"));
        send_image(&runtime, 1, &pattern(0, 10));
        runtime.send_json(&json!({"kind": "view.closed", "reason": "session_retired"}));
        assert!(matches!(next_event(&lane), ViewEvent::State(state) if state.title == "one"));
        assert!(matches!(next_event(&lane), ViewEvent::Image(_)));
        assert!(matches!(
            next_event(&lane),
            ViewEvent::Closed(ViewClosedReason::SessionRetired)
        ));
    }

    #[test]
    fn an_idle_stream_never_times_out_but_a_frame_begun_and_not_finished_does() {
        let timing = ViewTiming {
            frame_completion: Duration::from_millis(150),
            write: Duration::from_secs(5),
        };
        let (lane, runtime) = lane_with(timing);
        assert!(
            lane.recv(Duration::from_millis(600)).is_none(),
            "four completion bounds of silence is not a failure"
        );
        assert!(!lane.is_closed());
        runtime.send_json(&state_document("after the quiet"));
        assert!(matches!(next_event(&lane), ViewEvent::State(_)));
        // A frame's first bytes, and then nothing.
        runtime.push_raw(&[KIND_DOCUMENT, 0, 0]);
        assert!(matches!(
            next_event(&lane),
            ViewEvent::Ended(ViewEnd::TimedOut)
        ));
        assert!(lane.is_closed());
    }

    #[test]
    fn every_violation_ends_the_lane_with_its_check_and_later_writes_fail() {
        let cases: [(&str, Provoke); 5] = [
            (
                "view_chunk_unannounced",
                Box::new(|runtime| {
                    let mut payload = vec![1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1];
                    payload.push(9);
                    runtime.send_frame(KIND_CHUNK, &payload);
                }),
            ),
            (
                "view_frame",
                Box::new(|runtime| runtime.send_frame(b'S', b"secret")),
            ),
            (
                "view_document",
                Box::new(|runtime| runtime.send_json(&json!({"kind": "view.credit", "images": 1}))),
            ),
            (
                "view_image_interleaved",
                Box::new(|runtime| {
                    runtime.send_json(&announce(1, 65_521));
                    runtime.send_json(&state_document("inside"));
                }),
            ),
            (
                "view_transfer_unknown",
                Box::new(|runtime| {
                    runtime.send_json(
                        &json!({"kind": "view.transfer_credit", "transfer_id": 4, "chunks": 1}),
                    );
                }),
            ),
        ];
        for (check, provoke) in cases {
            let (lane, runtime) = lane();
            lane.credit(2).unwrap();
            runtime.take_json();
            provoke(&runtime);
            assert!(
                matches!(next_event(&lane), ViewEvent::Ended(ViewEnd::Violation(found)) if found == check),
                "{check}"
            );
            assert!(matches!(
                lane.navigate(ViewNavigateVerb::Back),
                Err(Refusal::ConnectionClosed)
            ));
            assert!(
                matches!(lane.recv(Duration::ZERO), Some(ViewEvent::Ended(_))),
                "the end repeats"
            );
        }
    }

    #[test]
    fn an_image_without_credit_is_a_violation() {
        let (lane, runtime) = lane();
        send_image(&runtime, 1, &pattern(0, 10));
        assert!(matches!(
            next_event(&lane),
            ViewEvent::Ended(ViewEnd::Violation("view_image_without_credit"))
        ));
    }

    #[test]
    fn the_runtime_closing_the_connection_ends_the_lane_after_queued_events() {
        let (lane, runtime) = lane();
        runtime.send_json(&json!({"kind": "view.closed", "reason": "cancelled"}));
        runtime.close();
        assert!(matches!(
            next_event(&lane),
            ViewEvent::Closed(ViewClosedReason::Cancelled)
        ));
        assert!(matches!(
            next_event(&lane),
            ViewEvent::Ended(ViewEnd::Disconnected)
        ));
    }

    #[test]
    fn ending_the_view_asks_for_its_close_and_a_plain_close_sends_nothing() {
        let (lane, runtime) = lane();
        lane.end_view();
        assert_eq!(runtime.take_json(), json!({"kind": "view.close"}));
        assert!(lane.is_closed());
        assert!(matches!(
            lane.recv(Duration::ZERO),
            Some(ViewEvent::Ended(ViewEnd::Closed))
        ));
        lane.end_view();
        let (plain, quiet) = self::lane();
        plain.close();
        assert!(quiet.is_quiet());
    }

    #[test]
    fn closing_the_lane_ends_its_threads_and_surfaces_as_closed() {
        let (lane, runtime) = lane();
        runtime.send_json(&state_document("never taken"));
        lane.close();
        assert!(matches!(
            lane.recv(Duration::ZERO),
            Some(ViewEvent::Ended(ViewEnd::Closed))
        ));
        assert!(matches!(
            lane.navigate(ViewNavigateVerb::Home),
            Err(Refusal::ConnectionClosed)
        ));
        assert!(locked(&lane.threads).is_empty());
        lane.close();
    }

    #[test]
    fn a_download_is_offered_accepted_credited_received_and_verified() {
        let (lane, runtime) = lane();
        let content = pattern(0, 2 * CHUNK_BODY_BYTES + 77);
        runtime.send_json(&json!({"kind": "view.download", "transfer_id": 1,
            "filename": "justificante.pdf", "size": content.len(), "mime": "application/pdf"}));
        let ViewEvent::Download(offer) = next_event(&lane) else {
            panic!("an offer");
        };
        assert_eq!(offer.filename, "justificante.pdf");
        lane.accept_download(offer.transfer_id, offer.size).unwrap();
        assert_eq!(
            runtime.take_json(),
            json!({"kind": "view.download_answer", "transfer_id": 1, "outcome": "accepted"})
        );
        lane.download_credit(1, 3).unwrap();
        assert_eq!(
            runtime.take_json(),
            json!({"kind": "view.transfer_credit", "transfer_id": 1, "chunks": 3})
        );
        let mut sender = TransferSender::new(1, Box::new(Cursor::new(content.clone()))).unwrap();
        sender.control().grant(3).unwrap();
        while let Some(chunk) = sender.next_chunk().unwrap() {
            runtime.send_frame(KIND_CHUNK, &chunk.payload);
        }
        runtime.send_json(
            &serde_json::to_value(ViewUpstream::TransferComplete(sender.completion().unwrap()))
                .unwrap(),
        );
        let mut received = Vec::new();
        loop {
            match next_event(&lane) {
                ViewEvent::DownloadChunk(chunk) => {
                    assert_eq!(chunk.offset, received.len() as u64);
                    received.extend_from_slice(&chunk.data);
                }
                ViewEvent::DownloadComplete(complete) => {
                    assert_eq!(complete.size, content.len() as u64);
                    break;
                }
                other => panic!("{other:?}"),
            }
        }
        assert_eq!(received, content);
    }

    #[test]
    fn download_bytes_that_disagree_with_their_completion_end_the_lane() {
        let (lane, runtime) = lane();
        runtime.send_json(&json!({"kind": "view.download", "transfer_id": 1, "filename": "a.txt"}));
        assert!(matches!(next_event(&lane), ViewEvent::Download(_)));
        lane.accept_download(1, None).unwrap();
        lane.download_credit(1, 1).unwrap();
        let mut sender = TransferSender::new(1, Box::new(Cursor::new(vec![1, 2, 3]))).unwrap();
        sender.control().grant(1).unwrap();
        let chunk = sender.next_chunk().unwrap().unwrap();
        runtime.send_frame(KIND_CHUNK, &chunk.payload);
        runtime.send_json(&json!({"kind": "view.transfer_complete", "transfer_id": 1,
            "size": 3, "sha256": "0".repeat(64)}));
        loop {
            match next_event(&lane) {
                ViewEvent::DownloadChunk(_) => {}
                ViewEvent::Ended(ViewEnd::Violation("view_transfer_digest")) => break,
                other => panic!("{other:?}"),
            }
        }
    }

    #[test]
    fn a_download_chunk_without_credit_is_a_violation_and_a_misused_call_is_not() {
        let (lane, runtime) = lane();
        assert!(lane.download_credit(1, 1).is_err());
        assert!(!lane.is_closed());
        runtime.send_json(&json!({"kind": "view.download", "transfer_id": 1, "filename": "a.txt"}));
        assert!(matches!(next_event(&lane), ViewEvent::Download(_)));
        lane.accept_download(1, None).unwrap();
        assert!(
            lane.accept_download(1, None).is_err(),
            "ids strictly increase"
        );
        assert!(
            lane.decline_download(2, ViewDownloadOutcome::Accepted)
                .is_err()
        );
        lane.decline_download(2, ViewDownloadOutcome::Cancelled)
            .unwrap();
        assert!(!lane.is_closed());
        let mut sender = TransferSender::new(1, Box::new(Cursor::new(vec![9]))).unwrap();
        sender.control().grant(1).unwrap();
        runtime.send_frame(KIND_CHUNK, &sender.next_chunk().unwrap().unwrap().payload);
        loop {
            if let ViewEvent::Ended(end) = next_event(&lane) {
                assert_eq!(end, ViewEnd::Violation("view_transfer_credit"));
                break;
            }
        }
    }

    #[test]
    fn cancelling_a_download_tells_the_page_and_discards_what_crosses() {
        let (lane, runtime) = lane();
        runtime.send_json(&json!({"kind": "view.download", "transfer_id": 1, "filename": "a.txt"}));
        assert!(matches!(next_event(&lane), ViewEvent::Download(_)));
        lane.accept_download(1, None).unwrap();
        lane.download_credit(1, 2).unwrap();
        runtime.take_json();
        runtime.take_json();
        lane.cancel_download(1).unwrap();
        assert_eq!(
            runtime.take_json(),
            json!({"kind": "view.transfer_cancel", "direction": "download", "transfer_id": 1})
        );
        lane.cancel_download(1).unwrap();
        assert!(runtime.is_quiet(), "a second cancel sends nothing");
        let mut sender = TransferSender::new(1, Box::new(Cursor::new(vec![7; 5]))).unwrap();
        sender.control().grant(1).unwrap();
        runtime.send_frame(KIND_CHUNK, &sender.next_chunk().unwrap().unwrap().payload);
        runtime.send_json(
            &json!({"kind": "view.transfer_cancel", "direction": "download",
            "transfer_id": 1}),
        );
        runtime.send_json(&state_document("after"));
        assert!(
            matches!(
                next_event(&lane),
                ViewEvent::DownloadCancelled { transfer_id: 1 }
            ),
            "the crossing chunk was discarded, so the next event is the cancel"
        );
        assert!(matches!(next_event(&lane), ViewEvent::State(_)));
    }

    fn read_uploads(runtime: &End, files: &[(u32, Vec<u8>)]) -> Vec<(u32, Vec<u8>, bool)> {
        // The page side: expect each upload, grant credit, take its chunks and completion.
        let receiver = TransferReceiver::new(ViewTransferDirection::Upload);
        let mut finished = Vec::new();
        for (transfer_id, content) in files {
            let announced = runtime.take_json();
            assert_eq!(announced["kind"], "view.upload");
            assert_eq!(announced["transfer_id"], *transfer_id);
            assert_eq!(announced["size"], content.len());
            receiver
                .expect(*transfer_id, Some(content.len() as u64))
                .unwrap();
            let mut got = Vec::new();
            let mut sent_credit = 0usize;
            let mut done = false;
            while !done {
                if sent_credit == 0 {
                    let chunks = TRANSFER_CREDIT_MAX_CHUNKS.min(2);
                    receiver.grant(*transfer_id, chunks).unwrap();
                    runtime.send_json(&json!({"kind": "view.transfer_credit",
                        "transfer_id": transfer_id, "chunks": chunks}));
                    sent_credit = usize::from(chunks);
                }
                let (kind, payload) = runtime.take_frame();
                if kind == KIND_CHUNK {
                    sent_credit -= 1;
                    let chunk = receiver.accept(&payload).unwrap().unwrap();
                    got.extend_from_slice(&chunk.data);
                    done = chunk.last;
                } else {
                    panic!("a chunk was due");
                }
            }
            let complete = runtime.take_json();
            assert_eq!(complete["kind"], "view.transfer_complete");
            let Ok(ViewUpstream::TransferComplete(complete)) = serde_json::from_value(complete)
            else {
                panic!("a completion");
            };
            receiver.observe_complete(&complete).unwrap();
            finished.push((*transfer_id, got, true));
        }
        finished
    }

    #[test]
    fn files_are_answered_then_announced_and_streamed_one_at_a_time_under_credit() {
        let (lane, runtime) = lane();
        let first = pattern(0, 3 * CHUNK_BODY_BYTES + 1);
        let second = vec![];
        lane.supply_files(
            9,
            vec![
                UploadFile {
                    name: "factura.pdf".into(),
                    mime: Some("application/pdf".into()),
                    size: first.len() as u64,
                    source: Box::new(Cursor::new(first.clone())),
                },
                UploadFile {
                    name: "vacío.txt".into(),
                    mime: None,
                    size: 0,
                    source: Box::new(Cursor::new(second.clone())),
                },
            ],
        )
        .unwrap();
        assert_eq!(
            runtime.take_json(),
            json!({"kind": "view.file_chooser_answer", "chooser_id": 9,
                   "outcome": "supplied", "file_count": 2})
        );
        let finished = read_uploads(&runtime, &[(1, first.clone()), (2, second.clone())]);
        assert_eq!(finished[0].1, first);
        assert_eq!(finished[1].1, second);
        for expected in [1, 2] {
            assert!(matches!(
                next_event(&lane),
                ViewEvent::UploadEnded { chooser_id: 9, transfer_id, outcome: UploadOutcome::Sent }
                    if transfer_id == expected
            ));
        }
    }

    #[test]
    fn an_upload_waits_for_credit_and_sends_no_byte_without_it() {
        let (lane, runtime) = lane();
        lane.supply_files(
            1,
            vec![UploadFile {
                name: "a.bin".into(),
                mime: None,
                size: 10,
                source: Box::new(Cursor::new(vec![0; 10])),
            }],
        )
        .unwrap();
        runtime.take_json();
        assert_eq!(runtime.take_json()["kind"], "view.upload");
        assert!(runtime.is_quiet(), "no credit, so no chunk");
    }

    #[test]
    fn the_page_cancelling_an_upload_is_answered_and_ends_it() {
        let (lane, runtime) = lane();
        lane.supply_files(
            1,
            vec![UploadFile {
                name: "a.bin".into(),
                mime: None,
                size: 10,
                source: Box::new(Cursor::new(vec![0; 10])),
            }],
        )
        .unwrap();
        runtime.take_json();
        runtime.take_json();
        runtime.send_json(
            &json!({"kind": "view.transfer_cancel", "direction": "upload",
            "transfer_id": 1}),
        );
        assert_eq!(
            runtime.take_json(),
            json!({"kind": "view.transfer_cancel", "direction": "upload", "transfer_id": 1})
        );
        assert!(matches!(
            next_event(&lane),
            ViewEvent::UploadEnded {
                outcome: UploadOutcome::Cancelled,
                transfer_id: 1,
                ..
            }
        ));
        // A cancel that crosses a finished upload changes nothing; a cancel of one never started ends the lane.
        runtime.send_json(
            &json!({"kind": "view.transfer_cancel", "direction": "upload",
            "transfer_id": 1}),
        );
        runtime.send_json(&json!({"kind": "view.transfer_credit", "transfer_id": 1, "chunks": 1}));
        runtime.send_json(&state_document("alive"));
        assert!(matches!(next_event(&lane), ViewEvent::State(_)));
        runtime.send_json(
            &json!({"kind": "view.transfer_cancel", "direction": "upload",
            "transfer_id": 2}),
        );
        assert!(matches!(
            next_event(&lane),
            ViewEvent::Ended(ViewEnd::Violation("view_transfer_unknown"))
        ));
    }

    #[test]
    fn an_upload_whose_bytes_differ_from_its_declared_size_is_cancelled_not_completed() {
        for (declared, actual) in [(5u64, 9usize), (9, 5)] {
            let (lane, runtime) = lane();
            lane.supply_files(
                1,
                vec![UploadFile {
                    name: "a.bin".into(),
                    mime: None,
                    size: declared,
                    source: Box::new(Cursor::new(vec![3; actual])),
                }],
            )
            .unwrap();
            runtime.take_json();
            runtime.take_json();
            runtime
                .send_json(&json!({"kind": "view.transfer_credit", "transfer_id": 1, "chunks": 1}));
            assert_eq!(
                runtime.take_json(),
                json!({"kind": "view.transfer_cancel", "direction": "upload", "transfer_id": 1}),
                "declared {declared}, actual {actual}"
            );
            assert!(matches!(
                next_event(&lane),
                ViewEvent::UploadEnded {
                    outcome: UploadOutcome::Failed,
                    ..
                }
            ));
            assert!(!lane.is_closed());
        }
    }

    #[test]
    fn files_that_are_not_documents_the_page_accepts_are_refused_before_anything_is_sent() {
        let (lane, runtime) = lane();
        let file = |name: &str| UploadFile {
            name: name.into(),
            mime: None,
            size: 0,
            source: Box::new(Cursor::new(Vec::new())),
        };
        assert!(matches!(
            lane.supply_files(1, vec![file("../x")]),
            Err(Refusal::InvalidFrame)
        ));
        assert!(matches!(
            lane.supply_files(0, vec![file("x")]),
            Err(Refusal::InvalidFrame)
        ));
        assert!(matches!(
            lane.supply_files(1, Vec::new()),
            Err(Refusal::InvalidFrame)
        ));
        assert!(runtime.is_quiet());
        lane.cancel_file_chooser(4).unwrap();
        assert_eq!(
            runtime.take_json(),
            json!({"kind": "view.file_chooser_answer", "chooser_id": 4,
                   "outcome": "cancelled", "file_count": 0})
        );
    }

    #[test]
    fn closing_the_lane_stops_an_upload_that_is_waiting_for_credit() {
        let (lane, runtime) = lane();
        lane.supply_files(
            1,
            vec![UploadFile {
                name: "a.bin".into(),
                mime: None,
                size: 10,
                source: Box::new(Cursor::new(vec![0; 10])),
            }],
        )
        .unwrap();
        runtime.take_json();
        runtime.take_json();
        lane.close();
        assert!(locked(&lane.threads).is_empty());
        let file = UploadFile {
            name: "b.bin".into(),
            mime: None,
            size: 0,
            source: Box::new(Cursor::new(Vec::new())),
        };
        assert!(matches!(
            lane.supply_files(1, vec![file]),
            Err(Refusal::ConnectionClosed)
        ));
    }

    #[test]
    fn the_event_queue_holds_one_image_and_a_full_queue_makes_the_producer_wait() {
        let image = |sequence: u32| {
            ViewEvent::Image(AssembledImage {
                announcement: announcement(sequence),
                data: Zeroizing::new(vec![0]),
            })
        };
        let queue = Arc::new(EventQueue::default());
        assert_eq!(queue.push(image(1)), Pushed::Queued);
        assert_eq!(
            queue.push(ViewEvent::DownloadCancelled { transfer_id: 1 }),
            Pushed::Queued
        );
        assert_eq!(queue.push(image(2)), Pushed::Replaced);
        assert!(matches!(
            queue.recv(Duration::ZERO),
            Some(ViewEvent::DownloadCancelled { .. })
        ));
        assert!(matches!(
            queue.recv(Duration::ZERO),
            Some(ViewEvent::Image(image)) if image.announcement.sequence == 2
        ));
        assert!(queue.recv(Duration::from_millis(20)).is_none());

        for id in 0..QUEUE_CAPACITY as u32 {
            assert_eq!(
                queue.push(ViewEvent::DownloadCancelled { transfer_id: id }),
                Pushed::Queued
            );
        }
        let (done, finished) = mpsc::channel();
        let producer = {
            let queue = queue.clone();
            thread::spawn(move || {
                let pushed = queue.push(ViewEvent::DownloadCancelled { transfer_id: 999 });
                done.send(pushed).unwrap();
            })
        };
        assert!(
            finished.recv_timeout(Duration::from_millis(150)).is_err(),
            "the producer waits for the consumer"
        );
        assert!(queue.recv(Duration::ZERO).is_some());
        assert_eq!(
            finished.recv_timeout(Duration::from_secs(5)).unwrap(),
            Pushed::Queued
        );
        producer.join().unwrap();
        queue.finish(ViewEnd::Disconnected);
        queue.finish(ViewEnd::Closed);
        assert_eq!(queue.push(image(3)), Pushed::Dropped);
        let mut drained = 0;
        while let Some(event) = queue.recv(Duration::ZERO) {
            match event {
                ViewEvent::Ended(end) => {
                    assert_eq!(end, ViewEnd::Disconnected, "the first end wins");
                    break;
                }
                _ => drained += 1,
            }
        }
        assert_eq!(drained, QUEUE_CAPACITY);
    }

    #[test]
    fn events_print_only_their_kind() {
        let event = ViewEvent::State(state_of("private title"));
        assert_eq!(format!("{event:?}"), "ViewEvent::State");
        assert!(
            !format!(
                "{:?}",
                UploadFile {
                    name: "private.pdf".into(),
                    mime: None,
                    size: 0,
                    source: Box::new(Cursor::new(Vec::new())),
                }
            )
            .contains("private")
        );
    }
}
