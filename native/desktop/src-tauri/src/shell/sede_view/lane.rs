use cadrumo_application::runtime_client::refusal::Refusal;
use cadrumo_application::view_stream::documents::{
    ViewClipboardAction, ViewDownloadOutcome, ViewInputEvent, ViewNavigateVerb,
};
use cadrumo_application::view_stream::lane::{UploadFile, ViewEvent, ViewLane};
use std::time::Duration;

pub(super) type Sent = std::result::Result<(), Refusal>;

/// What the host needs of one view connection.
pub(super) trait Lane: Send + Sync {
    fn recv(&self, timeout: Duration) -> Option<ViewEvent>;
    fn credit(&self, images: u8) -> Sent;
    fn input(&self, event: ViewInputEvent) -> Sent;
    fn navigate(&self, verb: ViewNavigateVerb) -> Sent;
    fn clipboard(&self, request_id: u32, action: ViewClipboardAction) -> Sent;
    fn clipboard_commit(&self, request_id: u32, apply: bool) -> Sent;
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
    fn clipboard(&self, request_id: u32, action: ViewClipboardAction) -> Sent {
        ViewLane::clipboard(self, request_id, action)
    }
    fn clipboard_commit(&self, request_id: u32, apply: bool) -> Sent {
        ViewLane::clipboard_commit(self, request_id, apply)
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
