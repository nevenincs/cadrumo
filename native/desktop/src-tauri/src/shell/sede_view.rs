//! The Browser page's host for the profile's Sede view.
//!
//! The view is the registered `live.sede.view` operation: the profile worker's
//! own Chromium page, streamed to the window as JPEG images while the
//! person's input travels back. This module submits it for the signed-in
//! profile, binds its view connection, and relays that connection onto one
//! Tauri channel that only the top document holds. Every command takes the
//! launch token (the dispatcher checks it) and names the view this host issued.
//!
//! The window never names a URL, a path or an identifier it was not given.
//! The host keeps the page's whole address, which the window never receives
//! (it is shown the origin and path), and opens it in the system browser only
//! when the person asks, after checking it as `open_external` does. A download or a file chooser asks the person in a
//! native dialog; the bytes go to the path chosen there, or come from the
//! files chosen there, and are not kept elsewhere, logged or shown to the window.
//!
//! The channel carries JSON messages and, after each `image` message, one raw
//! message holding that image's JPEG bytes, which the page receives by name
//! and takes as binary from the shell. Images, titles, addresses, input
//! and file names are private: they are relayed and dropped, and nothing here
//! logs them.
//!
//! The view ends when the person closes the page or the window, which asks it
//! to publish its session and settle, and when the person's session is lost,
//! which cancels it without publishing.
mod transfer;
mod upstream;

#[cfg(test)]
mod tests;

use super::{
    blocking,
    channel::RawFetch,
    external,
    relay::{self, Failure, Relayed, Result, lock},
    user_profile::ProfileHost,
};
use crate::agent::person::HeldPerson;
use cadrumo_application::{
    runtime_client::Refusal,
    view_stream::{
        chunks::AssembledImage,
        documents::{
            TRANSFER_CREDIT_MAX_CHUNKS, ViewClosedReason, ViewDialog, ViewDialogKind,
            ViewDialogPrompt, ViewDownload, ViewDownloadOutcome, ViewFileChooser, ViewInputEvent,
            ViewNavigateVerb, ViewNotice, ViewNoticeCode, ViewPageSecurity, ViewPhase, ViewResize,
            ViewState, ViewTransferComplete,
        },
        lane::{UploadFile, UploadOutcome, ViewEnd, ViewEvent, ViewLane},
        transfer::TransferChunk,
    },
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, VecDeque},
    sync::{
        Arc, Condvar, Mutex,
        atomic::{AtomicBool, AtomicU32, Ordering},
    },
    thread,
    time::{Duration, Instant},
};
use tauri::{
    State, Url, Webview,
    ipc::{Channel, InvokeResponseBody},
};
use transfer::{Dialogs, Download, NativeDialogs, upload_file};
use upstream::{Command, Upstream};

const DEFINITION: &str = "live.sede.view";
/// The runtime's refusal of a view whose browser is not open yet.
const NOT_YET: &str = "operation_unavailable";
/// How long the relay waits for an event before it looks at the session again.
const TICK: Duration = Duration::from_millis(200);
/// How long to wait before asking again for a view whose browser is not open.
const ATTACH_RETRY: Duration = Duration::from_millis(250);
/// Asks to attach this many times between looks at whether the operation still runs.
const ATTACH_TRIES_PER_LOOK: u32 = 8;
/// How long the runtime may take to answer one request to attach.
const ATTACH_EXCHANGE: Duration = Duration::from_secs(5);
/// How long a new view connection may take to open.
const CONNECT: Duration = Duration::from_secs(5);
/// How long between looks at a closing view's operation.
const SETTLE_POLL: Duration = Duration::from_millis(500);
/// The images a view may send before the window credits any.
const START_CREDIT: u8 = 2;
/// How many offers, dialogs and choosers wait for the person at once.
const PENDING_LIMIT: usize = 16;

fn failure(code: &'static str) -> Failure {
    Failure::new(code)
}

type Sent = std::result::Result<(), Refusal>;
/// Where a view's messages go: the window's channel, or a test's list. It
/// answers `false` once the window can no longer receive.
type Sink = Arc<dyn Fn(InvokeResponseBody) -> bool + Send + Sync>;

/// What the host needs of one view connection.
trait Lane: Send + Sync {
    fn recv(&self, timeout: Duration) -> Option<ViewEvent>;
    fn credit(&self, images: u8) -> Sent;
    fn input(&self, event: ViewInputEvent) -> Sent;
    fn navigate(&self, verb: ViewNavigateVerb) -> Sent;
    fn resize(&self, css_width: u32, css_height: u32, scale: f64) -> Sent;
    fn dialog(&self, dialog_id: u32, accept: bool, prompt_text: Option<String>) -> Sent;
    fn accept_download(&self, transfer_id: u32, size: Option<u64>) -> Sent;
    fn decline_download(&self, transfer_id: u32, outcome: ViewDownloadOutcome) -> Sent;
    fn download_credit(&self, transfer_id: u32, chunks: u8) -> Sent;
    fn cancel_download(&self, transfer_id: u32) -> Sent;
    fn cancel_file_chooser(&self, chooser_id: u32) -> Sent;
    fn supply_files(&self, chooser_id: u32, files: Vec<UploadFile>) -> Sent;
    /// The person closed the page or the window: the view publishes and settles.
    fn end_view(&self);
    /// The session was lost: the connection drops with nothing to publish.
    fn close(&self);
}

impl Lane for ViewLane {
    fn recv(&self, timeout: Duration) -> Option<ViewEvent> {
        ViewLane::recv(self, timeout)
    }
    fn credit(&self, images: u8) -> Sent {
        ViewLane::credit(self, images)
    }
    fn input(&self, event: ViewInputEvent) -> Sent {
        ViewLane::input(self, event)
    }
    fn navigate(&self, verb: ViewNavigateVerb) -> Sent {
        ViewLane::navigate(self, verb)
    }
    fn resize(&self, css_width: u32, css_height: u32, scale: f64) -> Sent {
        ViewLane::resize(self, css_width, css_height, scale)
    }
    fn dialog(&self, dialog_id: u32, accept: bool, prompt_text: Option<String>) -> Sent {
        ViewLane::dialog(self, dialog_id, accept, prompt_text)
    }
    fn accept_download(&self, transfer_id: u32, size: Option<u64>) -> Sent {
        ViewLane::accept_download(self, transfer_id, size)
    }
    fn decline_download(&self, transfer_id: u32, outcome: ViewDownloadOutcome) -> Sent {
        ViewLane::decline_download(self, transfer_id, outcome)
    }
    fn download_credit(&self, transfer_id: u32, chunks: u8) -> Sent {
        ViewLane::download_credit(self, transfer_id, chunks)
    }
    fn cancel_download(&self, transfer_id: u32) -> Sent {
        ViewLane::cancel_download(self, transfer_id)
    }
    fn cancel_file_chooser(&self, chooser_id: u32) -> Sent {
        ViewLane::cancel_file_chooser(self, chooser_id)
    }
    fn supply_files(&self, chooser_id: u32, files: Vec<UploadFile>) -> Sent {
        ViewLane::supply_files(self, chooser_id, files)
    }
    fn end_view(&self) {
        ViewLane::end_view(self);
    }
    fn close(&self) {
        ViewLane::close(self);
    }
}

/// How a settled view ended, as its operation's terminal receipt says.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Condition {
    Succeeded,
    Refused,
    Failed,
    Cancelled,
    TimedOut,
    Interrupted,
}

/// Why browsing stopped, as the view's result names it.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Finish {
    Closed,
    PageLost,
    StreamEnded,
    Stopped,
    ProtocolViolation,
}

/// What the close-time publication of the session did.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
enum Publication {
    #[serde(rename = "published")]
    Published,
    #[serde(rename = "unchanged")]
    Unchanged,
    #[serde(rename = "kept-newer")]
    KeptNewer,
    #[serde(rename = "verification-failed")]
    VerificationFailed,
    /// AEAT showed the session signed in as another taxpayer.
    #[serde(rename = "identity-mismatch")]
    IdentityMismatch,
    #[serde(rename = "unknown")]
    Unknown,
}

/// The view's result: how it ended and what it did with the session. The
/// operation's journal holds no more than this.
#[derive(Deserialize)]
struct Report {
    end: Finish,
    publication: Option<Publication>,
}

/// What a settled view reported.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
struct Outcome {
    condition: Condition,
    end: Option<Finish>,
    publication: Option<Publication>,
}

/// What the host needs of the runtime for one submitted view.
trait ViewRuntime: Send + Sync {
    /// A connection bound to the running view, or why none is yet.
    fn attach(&self, operation: &str) -> std::result::Result<Arc<dyn Lane>, Refusal>;
    /// Whether the operation still runs; `None` when that cannot be told.
    fn running(&self, operation: &str) -> Option<bool>;
    /// Asks the runtime to cancel the operation, which ends the view without
    /// publishing. Best effort: a lost session cancels it on its own.
    fn cancel(&self, operation: &str);
    /// Follows the operation to its terminal receipt and says what it reported;
    /// `None` when that could not be observed in time.
    fn settled(&self, operation: &str) -> Option<Outcome>;
    /// Whether the session that submitted the view is still held.
    fn held(&self) -> bool;
}

/// The runtime as the window's own person session reaches it.
struct PersonRuntime {
    person: HeldPerson,
    sign_in: Arc<super::sign_in::SignIn>,
    subject: String,
}

impl PersonRuntime {
    fn relayed<'a>(&'a self, operation: &str) -> Relayed<'a> {
        Relayed {
            person: &self.person,
            operation: operation.to_owned(),
            definition: DEFINITION,
            subject: self.subject.clone(),
        }
    }
}

impl ViewRuntime for PersonRuntime {
    fn attach(&self, operation: &str) -> std::result::Result<Arc<dyn Lane>, Refusal> {
        let grant = lock(&self.person).view_attach(operation, Instant::now() + ATTACH_EXCHANGE)?;
        let (endpoint, cohort) = self.sign_in.runtime_target()?;
        let lane = ViewLane::open(&endpoint, &cohort, grant, Instant::now() + CONNECT)?;
        Ok(Arc::new(lane))
    }

    fn running(&self, operation: &str) -> Option<bool> {
        match tauri::async_runtime::block_on(relay::observe(&self.relayed(operation))) {
            Ok(projection) => Some(projection["lifecycle"] != "terminal"),
            // The runtime no longer knows the operation, so nothing of it runs.
            Err(gone) if gone.code == "not_admitted" => Some(false),
            Err(_) => None,
        }
    }

    fn cancel(&self, operation: &str) {
        let relayed = self.relayed(operation);
        tauri::async_runtime::block_on(async {
            let Ok(projection) = relay::observe(&relayed).await else {
                return;
            };
            if projection["lifecycle"] == "terminal" {
                return;
            }
            let _ = relay::call(
                &self.person,
                json!({"action":"operation_cancel", "operation_id":operation,
                    "expected_revision":projection["revision"]}),
            )
            .await;
        });
    }

    fn settled(&self, operation: &str) -> Option<Outcome> {
        let relayed = self.relayed(operation);
        let deadline = Instant::now() + relay::SETTLE_LIMIT;
        loop {
            let projection = tauri::async_runtime::block_on(relay::observe(&relayed)).ok()?;
            if projection["lifecycle"] == "terminal" {
                let condition: Condition =
                    serde_json::from_value(projection["terminal_condition"].clone()).ok()?;
                if condition != Condition::Succeeded {
                    return Some(Outcome {
                        condition,
                        end: None,
                        publication: None,
                    });
                }
                let document = tauri::async_runtime::block_on(relay::result(&relayed)).ok()?;
                let report: Report = serde_json::from_value(document["projection"].clone()).ok()?;
                return Some(Outcome {
                    condition,
                    end: Some(report.end),
                    publication: report.publication,
                });
            }
            if Instant::now() >= deadline {
                return None;
            }
            thread::sleep(SETTLE_POLL);
        }
    }

    fn held(&self) -> bool {
        match self.person.try_lock() {
            Ok(mut person) => person.is_open(),
            Err(std::sync::TryLockError::Poisoned(poisoned)) => poisoned.into_inner().is_open(),
            // An exchange is in flight, so the session is in use.
            Err(std::sync::TryLockError::WouldBlock) => true,
        }
    }
}

/// A view the host submitted: its operation and the runtime that runs it.
struct Started {
    operation: String,
    runtime: Arc<dyn ViewRuntime>,
}

/// Why a view ended, as the window is told.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
enum Reason {
    /// The person closed the page or the window.
    Closed,
    /// The person's session was lost, locked or signed out.
    SessionLost,
    Cancelled,
    OperationEnded,
    Replaced,
    ProtocolViolation,
    RuntimeStopping,
    Failed,
    /// The runtime could not be reached, or ended the stream without saying why.
    Unavailable,
    /// The runtime refused the view; `code` says why.
    Refused,
}

impl From<ViewClosedReason> for Reason {
    fn from(reason: ViewClosedReason) -> Self {
        match reason {
            ViewClosedReason::Cancelled => Self::Cancelled,
            ViewClosedReason::IdleExpired
            | ViewClosedReason::LifetimeExpired
            | ViewClosedReason::OperationEnded => Self::OperationEnded,
            ViewClosedReason::SessionRetired => Self::SessionLost,
            ViewClosedReason::Replaced => Self::Replaced,
            ViewClosedReason::ProtocolViolation => Self::ProtocolViolation,
            ViewClosedReason::RuntimeStopping => Self::RuntimeStopping,
            ViewClosedReason::Failed => Self::Failed,
        }
    }
}

/// How a transfer ended.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
enum Transferred {
    Done,
    Cancelled,
    Failed,
}

#[derive(Serialize)]
struct Dialog {
    dialog_id: u32,
    dialog_kind: ViewDialogKind,
    message: String,
    default_prompt: Option<String>,
}

impl From<ViewDialogPrompt> for Dialog {
    fn from(prompt: ViewDialogPrompt) -> Self {
        Self {
            dialog_id: prompt.dialog_id,
            dialog_kind: prompt.dialog_kind,
            message: prompt.message,
            default_prompt: prompt.default_prompt,
        }
    }
}

/// What the window receives on its channel. Every message names its `view`,
/// so a late message of an earlier view is told apart.
#[derive(Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
enum Message {
    /// The view connection is bound and two images are credited.
    Opened { view: u32 },
    /// Announces the next raw message, which holds this image's JPEG bytes.
    Image {
        view: u32,
        sequence: u32,
        byte_length: u32,
        pixel_width: u32,
        pixel_height: u32,
        css_width: u32,
        css_height: u32,
        scale: f64,
    },
    /// The page the person is on. A page that is not `secure` has no origin
    /// or path, and `external` says whether the host holds an address it
    /// would open.
    #[serde(rename = "state")]
    Page {
        view: u32,
        security: ViewPageSecurity,
        origin: Option<String>,
        path: Option<String>,
        title: String,
        can_go_back: bool,
        can_go_forward: bool,
        loading: bool,
        phase: ViewPhase,
        external: bool,
    },
    /// A notice; `dialog_opened` carries the dialog the person answers.
    Notice {
        view: u32,
        code: ViewNoticeCode,
        dialog: Option<Dialog>,
    },
    /// A download is offered; answer it with the download answer command.
    Download {
        view: u32,
        transfer_id: u32,
        filename: String,
        size: Option<u64>,
        mime: Option<String>,
    },
    DownloadEnded {
        view: u32,
        transfer_id: u32,
        outcome: Transferred,
    },
    /// The page asks for files; answer it with the file chooser answer command.
    FileChooser {
        view: u32,
        chooser_id: u32,
        accept: Vec<String>,
        multiple: bool,
    },
    UploadEnded {
        view: u32,
        chooser_id: u32,
        outcome: Transferred,
    },
    /// The person closed the view and its session is being published.
    Closing { view: u32 },
    /// The last message of a view.
    Ended {
        view: u32,
        reason: Reason,
        code: Option<String>,
        outcome: Option<Outcome>,
    },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Phase {
    /// Submitted; the browser is not open yet.
    Attaching,
    Open,
    /// Publishing the session, or ending.
    Closing,
    Ended,
}

/// Why the host is ending a view, when it is the one ending it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Stop {
    /// The person closed the page or the window.
    Closed,
    /// The person's session was lost.
    SessionLost,
}

struct Control {
    phase: Phase,
    lane: Option<Arc<dyn Lane>>,
    stop: Option<Stop>,
    /// The last document the runtime sent: why it ended the view.
    reported: Option<ViewClosedReason>,
}

/// A download waiting for the person's answer.
struct Offered {
    filename: String,
    size: Option<u64>,
}

/// A file chooser waiting for the person's answer.
struct Chooser {
    multiple: bool,
}

/// What the host issued to the window for it to answer. An identifier the
/// window sends that is not here was never issued, and is refused.
#[derive(Default)]
struct Held {
    /// The current page's whole address, query included, as the worker stated
    /// it. It stays here: the window gets the origin and path only.
    address: Option<String>,
    dialogs: VecDeque<u32>,
    downloads: BTreeMap<u32, Offered>,
    choosers: BTreeMap<u32, Chooser>,
}

impl Held {
    fn note_dialog(&mut self, dialog_id: u32) {
        if self.dialogs.len() >= PENDING_LIMIT {
            self.dialogs.pop_front();
        }
        self.dialogs.push_back(dialog_id);
    }

    fn take_dialog(&mut self, dialog_id: u32) -> bool {
        let Some(position) = self.dialogs.iter().position(|known| *known == dialog_id) else {
            return false;
        };
        self.dialogs.remove(position);
        true
    }

    /// Notes an offer; answers the oldest one it had to drop for room.
    fn offer_download(&mut self, transfer_id: u32, offered: Offered) -> Option<u32> {
        let dropped = (self.downloads.len() >= PENDING_LIMIT)
            .then(|| self.downloads.pop_first().map(|(id, _)| id))
            .flatten();
        self.downloads.insert(transfer_id, offered);
        dropped
    }

    /// Notes a chooser; answers the oldest one it had to drop for room.
    fn offer_chooser(&mut self, chooser_id: u32, chooser: Chooser) -> Option<u32> {
        let dropped = (self.choosers.len() >= PENDING_LIMIT)
            .then(|| self.choosers.pop_first().map(|(id, _)| id))
            .flatten();
        self.choosers.insert(chooser_id, chooser);
        dropped
    }
}

/// How a view ended, before its operation is looked at.
struct End {
    reason: Reason,
    code: Option<String>,
    /// Whether the operation's receipt is worth waiting for.
    settle: bool,
}

impl End {
    fn of(reason: Reason, settle: bool) -> Self {
        Self {
            reason,
            code: None,
            settle,
        }
    }

    fn reported(reason: ViewClosedReason) -> Self {
        let reason = Reason::from(reason);
        Self::of(
            reason,
            !matches!(reason, Reason::SessionLost | Reason::RuntimeStopping),
        )
    }
}

/// One view the host submitted and relays.
struct View {
    id: u32,
    operation: String,
    runtime: Arc<dyn ViewRuntime>,
    sink: Sink,
    /// Messages leave one at a time, so nothing falls between an image's
    /// announcement and its bytes.
    outbound: Mutex<()>,
    control: Mutex<Control>,
    /// Signalled when the view reaches `Phase::Ended`.
    ended: Condvar,
    held: Mutex<Held>,
    /// The downloads being written.
    transfers: Mutex<BTreeMap<u32, Download>>,
    upstream: Upstream,
}

impl View {
    fn new(id: u32, started: Started, sink: Sink) -> Self {
        Self {
            id,
            operation: started.operation,
            runtime: started.runtime,
            sink,
            outbound: Mutex::new(()),
            control: Mutex::new(Control {
                phase: Phase::Attaching,
                lane: None,
                stop: None,
                reported: None,
            }),
            ended: Condvar::new(),
            held: Mutex::new(Held::default()),
            transfers: Mutex::new(BTreeMap::new()),
            upstream: Upstream::default(),
        }
    }

    fn phase(&self) -> Phase {
        lock(&self.control).phase
    }

    /// Waits until the view has ended, or until `deadline`; says whether it ended.
    fn wait_ended(&self, deadline: Instant) -> bool {
        let mut control = lock(&self.control);
        while control.phase != Phase::Ended {
            let Some(remaining) = deadline.checked_duration_since(Instant::now()) else {
                return false;
            };
            control = self
                .ended
                .wait_timeout(control, remaining)
                .unwrap_or_else(std::sync::PoisonError::into_inner)
                .0;
        }
        true
    }

    /// The connection, while the view is open for the person's commands.
    fn lane(&self) -> Result<Arc<dyn Lane>> {
        let control = lock(&self.control);
        match (&control.lane, control.phase) {
            (Some(lane), Phase::Open) => Ok(lane.clone()),
            _ => Err(failure("not_admitted")),
        }
    }

    /// Sends one JSON message; `false` once the window cannot receive.
    fn send(&self, message: &Message) -> bool {
        self.emit(message, None)
    }

    /// Sends a message and, directly after it, raw bytes it announces.
    fn emit(&self, message: &Message, raw: Option<Vec<u8>>) -> bool {
        let Ok(json) = serde_json::to_string(message) else {
            return false;
        };
        let _outbound = lock(&self.outbound);
        (self.sink)(InvokeResponseBody::Json(json))
            && raw.is_none_or(|bytes| (self.sink)(InvokeResponseBody::Raw(bytes)))
    }

    /// The person closed the page or the window: the view publishes its
    /// session and settles. A view whose browser is not open yet is cancelled,
    /// by this call when `cancel_now`, else by its own relay.
    fn request_close(&self, cancel_now: bool) {
        let lane = {
            let mut control = lock(&self.control);
            match control.phase {
                Phase::Attaching => {
                    control.stop.get_or_insert(Stop::Closed);
                    drop(control);
                    if cancel_now {
                        self.runtime.cancel(&self.operation);
                    }
                    return;
                }
                Phase::Open => {
                    control.stop.get_or_insert(Stop::Closed);
                    control.phase = Phase::Closing;
                    control.lane.clone()
                }
                Phase::Closing | Phase::Ended => None,
            }
        };
        if let Some(lane) = lane {
            self.send(&Message::Closing { view: self.id });
            lane.end_view();
        }
    }

    /// The person's session was lost: cancels the view so it publishes nothing
    /// and drops its connection.
    fn lose_session(&self, lane: &Arc<dyn Lane>) {
        {
            let mut control = lock(&self.control);
            if control.stop.is_some() {
                return;
            }
            control.stop = Some(Stop::SessionLost);
            control.phase = Phase::Closing;
        }
        self.runtime.cancel(&self.operation);
        lane.close();
    }

    /// Runs the view from submission to its last message.
    fn run(self: &Arc<Self>) {
        let end = self.serve();
        let outcome = if end.settle {
            self.runtime.settled(&self.operation)
        } else {
            None
        };
        self.finish(&end, outcome);
    }

    fn serve(self: &Arc<Self>) -> End {
        let lane = match self.attach() {
            Ok(lane) => lane,
            Err(end) => return end,
        };
        let stop = {
            let mut control = lock(&self.control);
            control.lane = Some(lane.clone());
            control.phase = if control.stop.is_some() {
                Phase::Closing
            } else {
                Phase::Open
            };
            control.stop
        };
        // The window grants the rest as it draws; a view connection starts with none.
        let _ = lane.credit(START_CREDIT);
        self.send(&Message::Opened { view: self.id });
        let writer = {
            let view = self.clone();
            let lane = lane.clone();
            thread::Builder::new()
                .name("sede-view-writer".into())
                .spawn(move || view.write(&lane))
        };
        match stop {
            Some(Stop::Closed) => {
                self.send(&Message::Closing { view: self.id });
                lane.end_view();
            }
            // Nothing sets this before a connection exists; ending is still the right answer.
            Some(Stop::SessionLost) => {
                self.runtime.cancel(&self.operation);
                lane.close();
            }
            None => {}
        }
        if writer.is_err() {
            // Nothing could send the person's input, so the view cannot be used.
            lane.close();
        }
        let ended = self.relay(&lane);
        {
            let mut control = lock(&self.control);
            control.phase = Phase::Closing;
        }
        self.upstream.close();
        if let Ok(writer) = writer {
            let _ = writer.join();
        }
        self.end_of(ended)
    }

    /// Binds a view connection to the running view, waiting while its browser
    /// opens. A view the person closes, or whose session is lost, meanwhile
    /// is cancelled.
    fn attach(&self) -> std::result::Result<Arc<dyn Lane>, End> {
        let mut tries = 0u32;
        loop {
            let stop = lock(&self.control).stop;
            if stop.is_some() || !self.runtime.held() {
                self.runtime.cancel(&self.operation);
                return Err(match stop {
                    Some(Stop::Closed) => End::of(Reason::Closed, true),
                    _ => End::of(Reason::SessionLost, false),
                });
            }
            match self.runtime.attach(&self.operation) {
                Ok(lane) => return Ok(lane),
                Err(Refusal::Denied { code, .. }) if code == NOT_YET => {
                    tries += 1;
                    if tries.is_multiple_of(ATTACH_TRIES_PER_LOOK)
                        && self.runtime.running(&self.operation) == Some(false)
                    {
                        return Err(End::of(Reason::OperationEnded, true));
                    }
                    thread::sleep(ATTACH_RETRY);
                }
                Err(Refusal::Denied { code, .. }) => {
                    self.runtime.cancel(&self.operation);
                    return Err(End {
                        code: Some(code),
                        ..End::of(Reason::Refused, false)
                    });
                }
                Err(_) => {
                    self.runtime.cancel(&self.operation);
                    return Err(End::of(Reason::Unavailable, false));
                }
            }
        }
    }

    /// Relays the connection's events to the window until the connection ends.
    fn relay(&self, lane: &Arc<dyn Lane>) -> ViewEnd {
        loop {
            match lane.recv(TICK) {
                Some(ViewEvent::Ended(end)) => return end,
                Some(ViewEvent::Closed(reason)) => {
                    lock(&self.control).reported = Some(reason);
                    // The runtime ends a view whose session it retired or whose
                    // runtime stops; nothing is left to publish.
                    if matches!(
                        reason,
                        ViewClosedReason::SessionRetired | ViewClosedReason::RuntimeStopping
                    ) {
                        self.lose_session(lane);
                    }
                }
                Some(event) => {
                    if !self.forward(lane, event) {
                        // The window's page is gone: the person closed it.
                        self.request_close(false);
                    }
                }
                None => {}
            }
            if !self.runtime.held() {
                self.lose_session(lane);
            }
        }
    }

    fn end_of(&self, ended: ViewEnd) -> End {
        let control = lock(&self.control);
        match (control.stop, control.reported, ended) {
            (Some(Stop::SessionLost), _, _) => End::of(Reason::SessionLost, false),
            (Some(Stop::Closed), _, _) => End::of(Reason::Closed, true),
            (None, Some(reason), _) => End::reported(reason),
            (None, None, ViewEnd::Violation(_)) => End::of(Reason::ProtocolViolation, true),
            (None, None, _) => End::of(Reason::Unavailable, true),
        }
    }

    fn finish(&self, end: &End, outcome: Option<Outcome>) {
        {
            let mut control = lock(&self.control);
            control.phase = Phase::Ended;
            control.lane = None;
        }
        self.upstream.close();
        *lock(&self.held) = Held::default();
        // Dropping a download that never finished removes its partial file.
        lock(&self.transfers).clear();
        self.send(&Message::Ended {
            view: self.id,
            reason: end.reason,
            code: end.code.clone(),
            outcome,
        });
        self.ended.notify_all();
    }

    /// Sends the person's queued commands to the page, in order.
    fn write(&self, lane: &Arc<dyn Lane>) {
        while let Some(command) = self.upstream.next() {
            // A refused document never ends the connection, and a failed write
            // already did: the relay sees the end.
            let _ = match command {
                Command::Input(event) => lane.input(event),
                Command::Navigate(verb) => lane.navigate(verb),
                Command::Resize {
                    css_width,
                    css_height,
                    scale,
                } => lane.resize(css_width, css_height, scale),
                Command::Dialog {
                    dialog_id,
                    accept,
                    prompt_text,
                } => lane.dialog(dialog_id, accept, prompt_text),
                Command::Credit(images) => lane.credit(images),
            };
        }
    }

    /// Passes one event on to the window; `false` once it cannot receive.
    fn forward(&self, lane: &Arc<dyn Lane>, event: ViewEvent) -> bool {
        match event {
            ViewEvent::Image(image) => self.image(image),
            ViewEvent::State(state) => self.page(state),
            ViewEvent::Notice(notice) => self.notice(notice),
            ViewEvent::Download(download) => self.offered(lane, download),
            ViewEvent::FileChooser(chooser) => self.chooser(lane, chooser),
            ViewEvent::DownloadChunk(chunk) => self.chunk(lane, &chunk),
            ViewEvent::DownloadComplete(complete) => self.complete(&complete),
            ViewEvent::DownloadCancelled { transfer_id } => self.stopped(transfer_id),
            ViewEvent::UploadEnded {
                chooser_id,
                outcome,
                ..
            } => self.send(&Message::UploadEnded {
                view: self.id,
                chooser_id,
                outcome: match outcome {
                    UploadOutcome::Sent => Transferred::Done,
                    UploadOutcome::Cancelled => Transferred::Cancelled,
                    UploadOutcome::Failed => Transferred::Failed,
                },
            }),
            // The relay handles the end of the connection and the runtime's last document.
            ViewEvent::Closed(_) | ViewEvent::Ended(_) => true,
        }
    }

    /// The announcement, then the JPEG bytes as one raw message. The lane's
    /// copy is wiped when it drops; the copy handed to the channel cannot be.
    fn image(&self, image: AssembledImage) -> bool {
        let announcement = image.announcement;
        self.emit(
            &Message::Image {
                view: self.id,
                sequence: announcement.sequence,
                byte_length: announcement.byte_length,
                pixel_width: announcement.pixel_width,
                pixel_height: announcement.pixel_height,
                css_width: announcement.css_width,
                css_height: announcement.css_height,
                scale: announcement.scale,
            },
            Some(image.data.to_vec()),
        )
    }

    fn page(&self, state: ViewState) -> bool {
        // Every navigation states its page. One whose address the worker could
        // not state, an insecure or unknown page included, clears the previous
        // one, so neither the toolbar nor the external open stays on an
        // earlier page.
        let external = state
            .address
            .as_deref()
            .is_some_and(|address| external::admit(address).is_ok());
        lock(&self.held).address = state.address;
        self.send(&Message::Page {
            view: self.id,
            security: state.security,
            origin: state.origin,
            path: state.path,
            title: state.title,
            can_go_back: state.can_go_back,
            can_go_forward: state.can_go_forward,
            loading: state.loading,
            phase: state.phase,
            external,
        })
    }

    fn notice(&self, notice: ViewNotice) -> bool {
        if let Some(dialog) = &notice.dialog {
            lock(&self.held).note_dialog(dialog.dialog_id);
        }
        self.send(&Message::Notice {
            view: self.id,
            code: notice.code,
            dialog: notice.dialog.map(Dialog::from),
        })
    }

    fn offered(&self, lane: &Arc<dyn Lane>, download: ViewDownload) -> bool {
        let dropped = lock(&self.held).offer_download(
            download.transfer_id,
            Offered {
                filename: download.filename.clone(),
                size: download.size,
            },
        );
        if let Some(dropped) = dropped {
            // The window was shown too many offers to answer: refuse the oldest.
            let _ = lane.decline_download(dropped, ViewDownloadOutcome::Refused);
        }
        self.send(&Message::Download {
            view: self.id,
            transfer_id: download.transfer_id,
            filename: download.filename,
            size: download.size,
            mime: download.mime,
        })
    }

    fn chooser(&self, lane: &Arc<dyn Lane>, chooser: ViewFileChooser) -> bool {
        let dropped = lock(&self.held).offer_chooser(
            chooser.chooser_id,
            Chooser {
                multiple: chooser.multiple,
            },
        );
        if let Some(dropped) = dropped {
            let _ = lane.cancel_file_chooser(dropped);
        }
        self.send(&Message::FileChooser {
            view: self.id,
            chooser_id: chooser.chooser_id,
            accept: chooser.accept,
            multiple: chooser.multiple,
        })
    }

    /// Writes one chunk of an accepted download where the person chose, then
    /// admits the next.
    fn chunk(&self, lane: &Arc<dyn Lane>, chunk: &TransferChunk) -> bool {
        let id = chunk.transfer_id;
        let written = lock(&self.transfers)
            .get_mut(&id)
            .map(|download| download.write(chunk).is_ok());
        match written {
            Some(true) => {
                if !chunk.last {
                    let _ = lane.download_credit(id, 1);
                }
                true
            }
            // A write that failed, or a transfer this host did not accept: stop it.
            Some(false) | None => {
                lock(&self.transfers).remove(&id);
                let _ = lane.cancel_download(id);
                self.send(&Message::DownloadEnded {
                    view: self.id,
                    transfer_id: id,
                    outcome: Transferred::Failed,
                })
            }
        }
    }

    fn complete(&self, complete: &ViewTransferComplete) -> bool {
        let Some(download) = lock(&self.transfers).remove(&complete.transfer_id) else {
            return true;
        };
        let saved = download.finish(complete.size).is_ok();
        self.send(&Message::DownloadEnded {
            view: self.id,
            transfer_id: complete.transfer_id,
            outcome: if saved {
                Transferred::Done
            } else {
                Transferred::Failed
            },
        })
    }

    /// The page stopped sending a download; what was written is removed.
    fn stopped(&self, transfer_id: u32) -> bool {
        lock(&self.transfers).remove(&transfer_id);
        self.send(&Message::DownloadEnded {
            view: self.id,
            transfer_id,
            outcome: Transferred::Cancelled,
        })
    }

    /// The person's answer to a download offered under `transfer_id`: save it
    /// where the native save dialog chooses, or decline it. Blocks while the
    /// dialog is open.
    fn answer_download(
        &self,
        transfer_id: u32,
        save: bool,
        dialogs: &dyn Dialogs,
    ) -> Result<DownloadAnswered> {
        self.lane()?;
        let offered = lock(&self.held)
            .downloads
            .remove(&transfer_id)
            .ok_or_else(|| failure("invalid"))?;
        let chosen = if save {
            dialogs.save(&offered.filename)
        } else {
            None
        };
        // The view may have ended while the dialog was open.
        let lane = self.lane()?;
        let Some(target) = chosen else {
            let _ = lane.decline_download(transfer_id, ViewDownloadOutcome::Cancelled);
            return Ok(DownloadAnswered { saving: false });
        };
        let Ok(download) = Download::create(target) else {
            let _ = lane.decline_download(transfer_id, ViewDownloadOutcome::Refused);
            return Err(failure("file_unavailable"));
        };
        lock(&self.transfers).insert(transfer_id, download);
        let admitted = lane
            .accept_download(transfer_id, offered.size)
            .and_then(|()| lane.download_credit(transfer_id, TRANSFER_CREDIT_MAX_CHUNKS));
        if admitted.is_err() {
            lock(&self.transfers).remove(&transfer_id);
            let _ = lane.decline_download(transfer_id, ViewDownloadOutcome::Refused);
            return Err(failure("unavailable"));
        }
        Ok(DownloadAnswered { saving: true })
    }

    /// The person's answer to a file chooser the page opened under
    /// `chooser_id`: the files the native open dialog chooses go to the page,
    /// or the chooser is cancelled. Blocks while the dialog is open.
    fn answer_chooser(
        &self,
        chooser_id: u32,
        choose: bool,
        dialogs: &dyn Dialogs,
    ) -> Result<ChooserAnswered> {
        self.lane()?;
        let chooser = lock(&self.held)
            .choosers
            .remove(&chooser_id)
            .ok_or_else(|| failure("invalid"))?;
        let chosen = if choose {
            dialogs.open(chooser.multiple)
        } else {
            Vec::new()
        };
        let lane = self.lane()?;
        let wanted = if chooser.multiple { chosen.len() } else { 1 };
        let files: std::io::Result<Vec<_>> = chosen
            .iter()
            .take(wanted)
            .map(|path| upload_file(path))
            .collect();
        let Ok(files) = files else {
            let _ = lane.cancel_file_chooser(chooser_id);
            return Err(failure("file_unavailable"));
        };
        if files.is_empty() {
            let _ = lane.cancel_file_chooser(chooser_id);
            return Ok(ChooserAnswered { supplied: 0 });
        }
        let supplied = u32::try_from(files.len()).map_err(|_| failure("invalid"))?;
        if lane.supply_files(chooser_id, files).is_err() {
            let _ = lane.cancel_file_chooser(chooser_id);
            return Err(failure("invalid"));
        }
        Ok(ChooserAnswered { supplied })
    }

    fn queue(&self, command: Command) -> Result<()> {
        self.lane()?;
        if self.upstream.push(command) {
            Ok(())
        } else {
            Err(failure("unavailable"))
        }
    }
}

#[derive(Debug, Serialize)]
pub struct Opened {
    view: u32,
}

#[derive(Debug, Serialize)]
pub struct DownloadAnswered {
    /// Whether the download began: the person chose where to save it.
    saving: bool,
}

#[derive(Debug, Serialize)]
pub struct ChooserAnswered {
    /// How many files went to the page.
    supplied: u32,
}

/// Opens an address in the person's own browser. The system's handler, or a
/// test's list.
trait Opener: Send + Sync {
    fn open(&self, url: &Url) -> Result<()>;
}

struct System;

impl Opener for System {
    fn open(&self, url: &Url) -> Result<()> {
        external::open(url).map_err(|_| failure("unavailable"))
    }
}

/// The panel size a view starts at.
#[derive(Debug)]
struct Size {
    css_width: u32,
    css_height: u32,
    scale: f64,
}

impl Size {
    fn admit(css_width: u32, css_height: u32, scale: f64) -> Result<Self> {
        ViewResize {
            css_width,
            css_height,
            scale,
        }
        .validate()
        .map_err(|_| failure("invalid"))?;
        Ok(Self {
            css_width,
            css_height,
            scale,
        })
    }
}

/// The view's registered request: the profile and the panel's starting size.
/// The start page is the backend's own; the window never names one.
fn request(profile_id: &str, size: &Size) -> Value {
    json!({"profile_id":profile_id, "css_width":size.css_width,
        "css_height":size.css_height, "scale":size.scale})
}

/// Submits the Sede view for the window's signed-in profile.
async fn start(profile: &ProfileHost, size: &Size) -> Result<Started> {
    let _serial = profile.serial().await;
    let person = profile.person(None).await?;
    let profile_id = relay::profile_of(&person).await?;
    let subject = relay::subject(&profile_id);
    // A lost answer may still have started a view, so the submission counts as a mutation.
    let operation = relay::submit(
        &person,
        DEFINITION,
        &subject,
        request(&profile_id, size),
        true,
    )
    .await?;
    Ok(Started {
        operation,
        runtime: Arc::new(PersonRuntime {
            person,
            sign_in: profile.sign_in().clone(),
            subject,
        }),
    })
}

/// The window's one view, and the commands that drive it.
pub struct SedeViewHost {
    current: Mutex<Option<Arc<View>>>,
    issued: AtomicU32,
    closed: AtomicBool,
    opener: Box<dyn Opener>,
}

impl SedeViewHost {
    pub fn new() -> Self {
        Self::with_opener(Box::new(System))
    }

    fn with_opener(opener: Box<dyn Opener>) -> Self {
        Self {
            current: Mutex::new(None),
            issued: AtomicU32::new(0),
            closed: AtomicBool::new(false),
            opener,
        }
    }

    /// Ends the view when the window closes: it publishes its session and
    /// settles. Returns once the view has ended, so the caller can then end
    /// the person's session, which a publication still in flight needs. The
    /// wait is bounded by how long any submitted operation is followed.
    pub fn close(&self) {
        self.close_within(relay::SETTLE_LIMIT);
    }

    fn close_within(&self, limit: Duration) {
        let deadline = Instant::now() + limit;
        self.closed.store(true, Ordering::Release);
        let view = lock(&self.current).clone();
        if let Some(view) = view {
            view.request_close(true);
            view.wait_ended(deadline);
        }
    }

    /// The top document was replaced: the page that held the view is gone. Runs
    /// on the thread that loads pages, so the close, which writes to the
    /// runtime, is left to a thread of its own.
    pub fn page_replaced(&self) {
        let view = lock(&self.current).clone();
        if let Some(view) = view {
            let _ = thread::Builder::new()
                .name("sede-view-page-close".into())
                .spawn(move || view.request_close(false));
        }
    }

    /// Whether another view may start.
    fn admit_open(&self) -> Result<()> {
        self.admits(lock(&self.current).as_ref())
    }

    fn admits(&self, current: Option<&Arc<View>>) -> Result<()> {
        if self.closed.load(Ordering::Acquire) {
            return Err(failure("unavailable"));
        }
        if current.is_some_and(|view| view.phase() != Phase::Ended) {
            return Err(failure("conflict"));
        }
        Ok(())
    }

    /// Takes the one place for a submitted view and starts relaying it. A view
    /// that cannot take it is cancelled.
    fn open_with(self: &Arc<Self>, started: Started, sink: Sink) -> Result<u32> {
        let id = self.issued.fetch_add(1, Ordering::AcqRel) + 1;
        let view = Arc::new(View::new(id, started, sink));
        let admitted = {
            let mut current = lock(&self.current);
            let refused = self.admits(current.as_ref());
            if refused.is_ok() {
                *current = Some(view.clone());
            }
            refused
        };
        if let Err(refused) = admitted {
            view.runtime.cancel(&view.operation);
            return Err(refused);
        }
        let host = self.clone();
        let relayed = view.clone();
        let spawned = thread::Builder::new()
            .name("sede-view-relay".into())
            .spawn(move || {
                relayed.run();
                host.release(&relayed);
            });
        if spawned.is_err() {
            self.release(&view);
            view.runtime.cancel(&view.operation);
            return Err(failure("unavailable"));
        }
        Ok(id)
    }

    /// Frees the place of a view that ended.
    fn release(&self, view: &Arc<View>) {
        let mut current = lock(&self.current);
        if current.as_ref().is_some_and(|held| Arc::ptr_eq(held, view)) {
            *current = None;
        }
    }

    /// The view `id` names, while it has not ended.
    fn view(&self, id: u32) -> Result<Arc<View>> {
        lock(&self.current)
            .clone()
            .filter(|view| view.id == id && view.phase() != Phase::Ended)
            .ok_or_else(|| failure("not_admitted"))
    }

    fn close_view(&self, id: u32) -> Result<()> {
        self.view(id)?.request_close(false);
        Ok(())
    }

    fn input(&self, id: u32, event: ViewInputEvent) -> Result<()> {
        event.validate().map_err(|_| failure("invalid"))?;
        self.view(id)?.queue(Command::Input(event))
    }

    fn navigate(&self, id: u32, verb: ViewNavigateVerb) -> Result<()> {
        self.view(id)?.queue(Command::Navigate(verb))
    }

    fn resize(&self, id: u32, css_width: u32, css_height: u32, scale: f64) -> Result<()> {
        let size = Size::admit(css_width, css_height, scale)?;
        self.view(id)?.queue(Command::Resize {
            css_width: size.css_width,
            css_height: size.css_height,
            scale: size.scale,
        })
    }

    /// One image drawn: the page may send another.
    fn credit(&self, id: u32) -> Result<()> {
        self.view(id)?.queue(Command::Credit(1))
    }

    fn dialog(
        &self,
        id: u32,
        dialog_id: u32,
        accept: bool,
        prompt_text: Option<String>,
    ) -> Result<()> {
        let view = self.view(id)?;
        let answer = ViewDialog {
            dialog_id,
            accept,
            prompt_text,
        };
        answer.validate().map_err(|_| failure("invalid"))?;
        if !lock(&view.held).take_dialog(dialog_id) {
            return Err(failure("invalid"));
        }
        let queued = view.queue(Command::Dialog {
            dialog_id,
            accept: answer.accept,
            prompt_text: answer.prompt_text,
        });
        if queued.is_err() {
            lock(&view.held).note_dialog(dialog_id);
        }
        queued
    }

    fn download_answer(
        &self,
        id: u32,
        transfer_id: u32,
        save: bool,
        dialogs: &dyn Dialogs,
    ) -> Result<DownloadAnswered> {
        self.view(id)?.answer_download(transfer_id, save, dialogs)
    }

    fn chooser_answer(
        &self,
        id: u32,
        chooser_id: u32,
        choose: bool,
        dialogs: &dyn Dialogs,
    ) -> Result<ChooserAnswered> {
        self.view(id)?.answer_chooser(chooser_id, choose, dialogs)
    }

    /// Opens the page's address in the system browser. The address is the
    /// host's own, checked again as `open_external` checks a link before it
    /// leaves the application.
    fn open_external(&self, id: u32) -> Result<()> {
        let view = self.view(id)?;
        let text = lock(&view.held)
            .address
            .clone()
            .ok_or_else(|| failure("unavailable"))?;
        let url = external::admit(&text).map_err(|_| failure("invalid"))?;
        self.opener.open(&url)
    }
}

impl Default for SedeViewHost {
    fn default() -> Self {
        Self::new()
    }
}

/// A view's messages on the window's channel. The images reach the page as
/// binary, which the page takes by name. It ends when the channel refuses a
/// message or the shell reports that one could not be delivered to the page.
fn channel_sink<R: tauri::Runtime>(
    webview: Webview<R>,
    messages: Channel<InvokeResponseBody>,
) -> Sink {
    let fetch = RawFetch::new(webview, messages.id());
    Arc::new(move |body| messages.send(body).is_ok() && !fetch.failed())
}

/// Opens the Sede view for the signed-in profile at the panel's size and
/// relays it on `messages` until it ends. The answer comes before the browser
/// is open; `opened` follows on the channel.
///
/// Refuses `conflict` while the previous view has not ended, which includes the
/// time it takes to publish its session.
#[tauri::command]
async fn sede_view_open<R: tauri::Runtime>(
    host: State<'_, Arc<SedeViewHost>>,
    profile: State<'_, Arc<ProfileHost>>,
    webview: Webview<R>,
    css_width: u32,
    css_height: u32,
    scale: f64,
    messages: Channel<InvokeResponseBody>,
) -> Result<Opened> {
    let size = Size::admit(css_width, css_height, scale)?;
    host.admit_open()?;
    let started = start(&profile, &size).await?;
    let sink = channel_sink(webview, messages);
    let owner = host.inner().clone();
    let view = blocking(move || Ok(owner.open_with(started, sink))).await??;
    Ok(Opened { view })
}

/// The person closed the page: the view publishes its session and settles.
/// `closing` and then `ended` follow on the channel.
#[tauri::command]
async fn sede_view_close(host: State<'_, Arc<SedeViewHost>>, view: u32) -> Result<()> {
    let owner = host.inner().clone();
    blocking(move || Ok(owner.close_view(view))).await?
}

/// Forwards one input event: a pointer, wheel, key or text event of the person.
#[tauri::command]
fn sede_view_input(
    host: State<'_, Arc<SedeViewHost>>,
    view: u32,
    event: ViewInputEvent,
) -> Result<()> {
    host.input(view, event)
}

/// Back, forward, reload or home. The window never names an address.
#[tauri::command]
fn sede_view_navigate(
    host: State<'_, Arc<SedeViewHost>>,
    view: u32,
    verb: ViewNavigateVerb,
) -> Result<()> {
    host.navigate(view, verb)
}

#[tauri::command]
fn sede_view_resize(
    host: State<'_, Arc<SedeViewHost>>,
    view: u32,
    css_width: u32,
    css_height: u32,
    scale: f64,
) -> Result<()> {
    host.resize(view, css_width, css_height, scale)
}

/// Grants the page one more image. Call it once for each `image` message
/// received, drawn or not: the host grants the first two itself.
#[tauri::command]
fn sede_view_credit(host: State<'_, Arc<SedeViewHost>>, view: u32) -> Result<()> {
    host.credit(view)
}

/// The person's answer to a page dialog the view announced under `dialog_id`.
#[tauri::command]
fn sede_view_dialog(
    host: State<'_, Arc<SedeViewHost>>,
    view: u32,
    dialog_id: u32,
    accept: bool,
    prompt_text: Option<String>,
) -> Result<()> {
    host.dialog(view, dialog_id, accept, prompt_text)
}

/// The person's answer to a download the view offered under `transfer_id`.
/// With `save`, the native save dialog asks where; a dialog closed unchosen
/// declines the download. The answer waits for the dialog. `download_ended`
/// follows on the channel when the bytes are written.
#[tauri::command]
async fn sede_view_download_answer<R: tauri::Runtime>(
    host: State<'_, Arc<SedeViewHost>>,
    window: tauri::WebviewWindow<R>,
    view: u32,
    transfer_id: u32,
    save: bool,
) -> Result<DownloadAnswered> {
    let owner = host.inner().clone();
    blocking(move || Ok(owner.download_answer(view, transfer_id, save, &NativeDialogs(window))))
        .await?
}

/// The person's answer to a file chooser the page opened under `chooser_id`.
/// With `choose`, the native open dialog asks which files; a dialog closed
/// unchosen cancels the chooser. The answer waits for the dialog.
/// `upload_ended` follows on the channel for each file.
#[tauri::command]
async fn sede_view_file_chooser_answer<R: tauri::Runtime>(
    host: State<'_, Arc<SedeViewHost>>,
    window: tauri::WebviewWindow<R>,
    view: u32,
    chooser_id: u32,
    choose: bool,
) -> Result<ChooserAnswered> {
    let owner = host.inner().clone();
    blocking(move || Ok(owner.chooser_answer(view, chooser_id, choose, &NativeDialogs(window))))
        .await?
}

/// Opens the page the person is on in the system browser. The window sends
/// no address.
#[tauri::command]
async fn sede_view_open_external(host: State<'_, Arc<SedeViewHost>>, view: u32) -> Result<()> {
    let owner = host.inner().clone();
    blocking(move || Ok(owner.open_external(view))).await?
}

pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        sede_view_open,
        sede_view_close,
        sede_view_input,
        sede_view_navigate,
        sede_view_resize,
        sede_view_credit,
        sede_view_dialog,
        sede_view_download_answer,
        sede_view_file_chooser_answer,
        sede_view_open_external
    ]
}
