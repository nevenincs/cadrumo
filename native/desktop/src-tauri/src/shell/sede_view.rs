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
//!
//! Before each open the setup engine checks the browser's current local state.
//! A browser that is not usable ends `component_not_ready` with its setup action.
//! The runtime's recorded refusal provides the same recovery if the browser
//! becomes unavailable after the check. Other runtime refusals are logged.
pub(crate) mod commands;
mod lane;
mod protocol;
mod runtime;
#[cfg(test)]
mod tests;
mod transfer;
mod upstream;

use self::lane::Lane;

use self::protocol::{
    ChooserAnswered, Condition, Dialog, DownloadAnswered, Message, Outcome, Reason, Sink, Size,
    Transferred,
};

use self::runtime::{Started, ViewRuntime};

use self::transfer::{Dialogs, Download, upload_file};

use self::upstream::{Command, Upstream};

use super::clipboard;

use super::external;

use super::relay::{self, Failure, Result, lock};

use cadrumo_application::diagnostics::Diagnostics;

use cadrumo_application::diagnostics::service::{FeatureRefusal, RefusedFeature, ServiceFact};

use cadrumo_application::provisioning::items::ItemId;

use cadrumo_application::runtime_client::refusal::Refusal;

use cadrumo_application::view_stream::chunks::AssembledImage;

use cadrumo_application::view_stream::documents::{
    TRANSFER_CREDIT_MAX_CHUNKS, ViewClipboardAction, ViewClosedReason, ViewDialog, ViewDownload,
    ViewDownloadOutcome, ViewFileChooser, ViewInputEvent, ViewNavigateVerb, ViewNotice, ViewState,
    ViewTransferComplete,
};

use cadrumo_application::view_stream::lane::{UploadOutcome, ViewEnd, ViewEvent};

use cadrumo_application::view_stream::transfer::TransferChunk;

use std::collections::{BTreeMap, VecDeque};

use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};

use std::sync::{Arc, Condvar, Mutex, OnceLock, mpsc};

use std::thread;

use std::time::{Duration, Instant};

use tauri::ipc::InvokeResponseBody;

use tauri::{AppHandle, Url};

/// The runtime's refusal of a view whose browser is not open yet.
const NOT_YET: &str = "operation_unavailable";

/// How long the relay waits for an event before it looks at the session again.
const TICK: Duration = Duration::from_millis(200);

/// How long to wait before asking again for a view whose browser is not open.
const ATTACH_RETRY: Duration = Duration::from_millis(250);

/// Asks to attach this many times between looks at whether the operation still runs.
const ATTACH_TRIES_PER_LOOK: u32 = 8;

/// The images a view may send before the window credits any.
const START_CREDIT: u8 = 2;

/// How many offers, dialogs and choosers wait for the person at once.
const PENDING_LIMIT: usize = 16;

const CLIPBOARD_REPLY: Duration = Duration::from_secs(5);

fn failure(code: &'static str) -> Failure {
    Failure::new(code)
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
    /// The component a `ComponentNotReady` end names.
    needs: Option<ItemId>,
}

impl End {
    fn of(reason: Reason, settle: bool) -> Self {
        Self {
            reason,
            code: None,
            settle,
            needs: None,
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
    clipboard_gate: Mutex<()>,
    clipboard_wait: Mutex<Option<(u32, mpsc::SyncSender<Option<String>>)>>,
    clipboard_issued: AtomicU32,
    diagnostics: Arc<Diagnostics>,
}

impl View {
    fn new(id: u32, started: Started, sink: Sink, diagnostics: Arc<Diagnostics>) -> Self {
        Self {
            id,
            operation: started.operation,
            runtime: started.runtime,
            sink,
            diagnostics,
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
            clipboard_gate: Mutex::new(()),
            clipboard_wait: Mutex::new(None),
            clipboard_issued: AtomicU32::new(0),
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
        let mut end = self.serve();
        let outcome = if end.settle {
            self.runtime.settled(&self.operation)
        } else {
            None
        };
        let refused = outcome.is_some_and(|outcome| outcome.condition == Condition::Refused);
        if refused && let Some(item) = self.runtime.needs(&self.operation) {
            end.reason = Reason::ComponentNotReady;
            end.needs = Some(item);
        }
        if refused || matches!(end.reason, Reason::Refused) {
            self.diagnostics.service(
                None,
                ServiceFact::FeatureRefused {
                    feature: RefusedFeature::SedeView,
                    refusal: if end.needs.is_some() {
                        FeatureRefusal::ComponentNotReady
                    } else {
                        FeatureRefusal::Refused
                    },
                    item: end.needs,
                },
            );
        }
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
        lock(&self.clipboard_wait).take();
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
            recovery_action_id: end.needs.map(|item| item.declaration().recovery_action),
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
                Command::Clipboard { request_id, action } => lane.clipboard(request_id, action),
                Command::ClipboardCommit { request_id, apply } => {
                    lane.clipboard_commit(request_id, apply)
                }
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
            ViewEvent::ClipboardSelection(selection) => {
                let mut pending = lock(&self.clipboard_wait);
                if pending
                    .as_ref()
                    .is_some_and(|(request_id, _)| *request_id == selection.request_id)
                    && let Some((_, sender)) = pending.take()
                {
                    let _ = sender.send(selection.text);
                }
                true
            }
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

    /// A private, bounded reply to an explicit desktop clipboard command.
    fn selected_text(
        &self,
        action: ViewClipboardAction,
        timeout: Duration,
    ) -> Result<(u32, String)> {
        let request_id = self
            .clipboard_issued
            .fetch_add(1, Ordering::AcqRel)
            .wrapping_add(1);
        if request_id == 0 {
            return Err(failure("unavailable"));
        }
        let (sender, receiver) = mpsc::sync_channel(1);
        *lock(&self.clipboard_wait) = Some((request_id, sender));
        if let Err(error) = self.queue(Command::Clipboard { request_id, action }) {
            lock(&self.clipboard_wait).take();
            return Err(error);
        }
        let reply = receiver.recv_timeout(timeout);
        lock(&self.clipboard_wait).take();
        if reply.is_err() && action == ViewClipboardAction::Cut {
            // The worker processes this after selection, releasing its held DOM handle.
            let _ = self.queue(Command::ClipboardCommit {
                request_id,
                apply: false,
            });
        }
        match reply {
            Ok(Some(text)) => Ok((request_id, text)),
            _ => Err(failure("unavailable")),
        }
    }
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

/// The window's one view, and the commands that drive it.
pub struct SedeViewHost {
    current: Mutex<Option<Arc<View>>>,
    issued: AtomicU32,
    closed: AtomicBool,
    /// When the window began closing. Every wait for the view ends by then,
    /// however many times the close is asked for.
    deadline: OnceLock<Instant>,
    behind: Mutex<Behind>,
    opener: Box<dyn Opener>,
    diagnostics: Arc<Diagnostics>,
}

/// A window close that waits for the view off the window's thread.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Behind {
    Idle,
    /// The window is hidden and the view is publishing.
    Settling,
    /// The view has ended, or the deadline passed.
    Settled,
}

/// What the window does with a close it was asked for.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum WindowClose {
    /// Nothing is left to wait for: the window closes now.
    Now,
    /// The view is publishing behind the hidden window, which stays until
    /// the close continues.
    Behind,
}

impl SedeViewHost {
    pub fn new(diagnostics: Arc<Diagnostics>) -> Self {
        Self::with_opener(Box::new(System), diagnostics)
    }

    fn with_opener(opener: Box<dyn Opener>, diagnostics: Arc<Diagnostics>) -> Self {
        Self {
            current: Mutex::new(None),
            issued: AtomicU32::new(0),
            closed: AtomicBool::new(false),
            deadline: OnceLock::new(),
            behind: Mutex::new(Behind::Idle),
            opener,
            diagnostics,
        }
    }

    /// Logs a view the runtime refused to submit.
    fn submission_refused(&self, failure: &Failure) {
        if failure.code == "refused" {
            self.diagnostics.service(
                None,
                ServiceFact::FeatureRefused {
                    feature: RefusedFeature::SedeView,
                    refusal: FeatureRefusal::Refused,
                    item: None,
                },
            );
        }
    }

    /// Ends the view when the window closes: it publishes its session and
    /// settles. Returns once the view has ended, so the caller can then end
    /// the person's session, which a publication still in flight needs. The
    /// wait is bounded by how long any submitted operation is followed,
    /// counted from the first close, so a repeated close waits no longer.
    pub fn close(&self) {
        self.close_within(relay::SETTLE_LIMIT);
    }

    fn close_within(&self, limit: Duration) {
        let deadline = *self.deadline.get_or_init(|| Instant::now() + limit);
        self.closed.store(true, Ordering::Release);
        let view = lock(&self.current).clone();
        if let Some(view) = view {
            view.request_close(true);
            view.wait_ended(deadline);
        }
    }

    /// Whether a close of the window has hidden it to wait for the view.
    pub fn window_closing(&self) -> bool {
        *lock(&self.behind) != Behind::Idle
    }

    /// Asks for the window's close without holding the window's thread. While
    /// a view is open, `hide` runs at once and the view publishes and ends on
    /// a thread of its own; `then` runs there afterwards, or once the close
    /// deadline passed, to continue the close. Otherwise, or once that wait
    /// is over, the window closes now, and [`Self::close`] returns at once.
    pub fn close_behind(
        self: &Arc<Self>,
        hide: impl FnOnce(),
        then: impl FnOnce() + Send + 'static,
    ) -> WindowClose {
        self.close_behind_within(relay::SETTLE_LIMIT, hide, then)
    }

    fn close_behind_within(
        self: &Arc<Self>,
        limit: Duration,
        hide: impl FnOnce(),
        then: impl FnOnce() + Send + 'static,
    ) -> WindowClose {
        {
            let mut behind = lock(&self.behind);
            match *behind {
                Behind::Settling => return WindowClose::Behind,
                Behind::Settled => return WindowClose::Now,
                Behind::Idle => {}
            }
            let open = lock(&self.current)
                .as_ref()
                .is_some_and(|view| view.phase() != Phase::Ended);
            if !open {
                return WindowClose::Now;
            }
            *behind = Behind::Settling;
        }
        hide();
        let host = self.clone();
        let spawned = thread::Builder::new()
            .name("sede-view-window-close".into())
            .spawn(move || {
                // The close continues even if the wait failed: the deadline
                // bounds shutdown, and a hidden window must not stay behind.
                let _ = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                    host.close_within(limit);
                }));
                *lock(&host.behind) = Behind::Settled;
                then();
            });
        if spawned.is_err() {
            // The window's own close then waits for the view instead.
            *lock(&self.behind) = Behind::Settled;
            return WindowClose::Now;
        }
        WindowClose::Behind
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

    /// End a view before submission when the fresh browser check found it unusable.
    fn component_not_ready(&self, sink: Sink) -> Result<u32> {
        let current = lock(&self.current);
        self.admits(current.as_ref())?;
        let view = self.issued.fetch_add(1, Ordering::AcqRel) + 1;
        drop(current);
        self.diagnostics.service(
            None,
            ServiceFact::FeatureRefused {
                feature: RefusedFeature::SedeView,
                refusal: FeatureRefusal::ComponentNotReady,
                item: Some(ItemId::Browser),
            },
        );
        let message = Message::Ended {
            view,
            reason: Reason::ComponentNotReady,
            code: None,
            outcome: None,
            recovery_action_id: Some(ItemId::Browser.declaration().recovery_action),
        };
        let body = serde_json::to_string(&message).map_err(|_| failure("unavailable"))?;
        if !sink(InvokeResponseBody::Json(body)) {
            return Err(failure("unavailable"));
        }
        Ok(view)
    }

    /// Takes the one place for a submitted view and starts relaying it. A view
    /// that cannot take it is cancelled.
    fn open_with(self: &Arc<Self>, started: Started, sink: Sink) -> Result<u32> {
        let id = self.issued.fetch_add(1, Ordering::AcqRel) + 1;
        let view = Arc::new(View::new(id, started, sink, self.diagnostics.clone()));
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

    fn clipboard<R: tauri::Runtime>(
        &self,
        id: u32,
        action: ViewClipboardAction,
        app: &AppHandle<R>,
    ) -> Result<()> {
        self.clipboard_with(id, action, |text| {
            clipboard::write(app, text).map_err(|_| failure("unavailable"))
        })
    }

    fn clipboard_with(
        &self,
        id: u32,
        action: ViewClipboardAction,
        write: impl FnOnce(String) -> Result<()>,
    ) -> Result<()> {
        let view = self.view(id)?;
        let _gate = lock(&view.clipboard_gate);
        if !view.runtime.held() {
            return Err(failure("not_admitted"));
        }
        let (request_id, text) = view.selected_text(action, CLIPBOARD_REPLY)?;
        // A view or session that changed while the worker selected text cannot write it.
        let current = self.view(id)?;
        if !Arc::ptr_eq(&current, &view) || !view.runtime.held() || view.phase() != Phase::Open {
            if action == ViewClipboardAction::Cut {
                let _ = view.queue(Command::ClipboardCommit {
                    request_id,
                    apply: false,
                });
            }
            return Err(failure("not_admitted"));
        }
        let written = write(text);
        if action == ViewClipboardAction::Cut {
            view.queue(Command::ClipboardCommit {
                request_id,
                apply: written.is_ok(),
            })?;
        }
        written
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
