use super::super::relay::Result;
use super::failure;
use cadrumo_application::view_stream::documents::{
    ViewClosedReason, ViewDialogKind, ViewDialogPrompt, ViewNoticeCode, ViewPageSecurity,
    ViewPhase, ViewResize,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tauri::ipc::InvokeResponseBody;

/// Where a view's messages go: the window's channel, or a test's list. It
/// answers `false` once the window can no longer receive.
pub(super) type Sink = Arc<dyn Fn(InvokeResponseBody) -> bool + Send + Sync>;

/// How a settled view ended, as its operation's terminal receipt says.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub(super) enum Condition {
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
pub(super) enum Finish {
    Closed,
    PageLost,
    StreamEnded,
    Stopped,
    ProtocolViolation,
}

/// What the close-time publication of the session did.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub(super) enum Publication {
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

/// What a settled view reported.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub(super) struct Outcome {
    pub(super) condition: Condition,
    pub(super) end: Option<Finish>,
    pub(super) publication: Option<Publication>,
}

/// Why a view ended, as the window is told.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub(super) enum Reason {
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
    /// A component the view needs is not set up; `recovery_action_id` names
    /// its setup.
    ComponentNotReady,
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
pub(super) enum Transferred {
    Done,
    Cancelled,
    Failed,
}

#[derive(Serialize)]
pub(super) struct Dialog {
    pub(super) dialog_id: u32,
    pub(super) dialog_kind: ViewDialogKind,
    pub(super) message: String,
    pub(super) default_prompt: Option<String>,
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
pub(super) enum Message {
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
        recovery_action_id: Option<&'static str>,
    },
}

#[derive(Debug, Serialize)]
pub struct Opened {
    pub(super) view: u32,
}

#[derive(Debug, Serialize)]
pub struct DownloadAnswered {
    /// Whether the download began: the person chose where to save it.
    pub(super) saving: bool,
}

#[derive(Debug, Serialize)]
pub struct ChooserAnswered {
    /// How many files went to the page.
    pub(super) supplied: u32,
}

/// The panel size a view starts at.
#[derive(Debug)]
pub(super) struct Size {
    pub(super) css_width: u32,
    pub(super) css_height: u32,
    pub(super) scale: f64,
}

impl Size {
    pub(super) fn admit(css_width: u32, css_height: u32, scale: f64) -> Result<Self> {
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
