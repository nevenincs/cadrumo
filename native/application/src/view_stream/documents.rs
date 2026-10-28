//! The closed control documents of the Sede view stream.
//!
//! Every document is a closed serde type: an unknown member, kind or value is
//! refused, and a number outside its range is refused by `validate`, which the
//! readers and writers here call at the wire boundary. Downstream, toward the
//! window, travel [`ViewDownstream`] documents: the page (`view.image`,
//! `view.state`, `view.notice`, `view.closed`) and the transfers it starts
//! (`view.download`, `view.file_chooser`). Upstream, from the window, travel
//! [`ViewUpstream`] documents: credit, input, navigation, resize, dialog
//! answers, `view.close` and the replies to transfers. `view.transfer_complete`,
//! `view.transfer_credit` and `view.transfer_cancel` travel both ways.
//!
//! Page titles, URLs, dialog text, input and file names are private taxpayer
//! data, so the types that carry them print no content.

use super::Violation;
use serde::{Deserialize, Serialize};
use std::fmt;
use zeroize::Zeroizing;

/// The largest encoded JPEG one image may carry.
pub const IMAGE_MAX_BYTES: u32 = 2 * 1024 * 1024;
/// The most images a producer may have sent and not yet had credited back.
pub const CREDIT_MAX_IMAGES: u8 = 2;
/// The largest panel width or height, in CSS pixels.
pub const MAX_CSS_EXTENT: u32 = 4096;
/// The largest image width or height, in device pixels.
pub const MAX_PIXEL_EXTENT: u32 = 8192;
pub const MIN_SCALE: f64 = 0.5;
pub const MAX_SCALE: f64 = 4.0;
pub const MAX_URL_LENGTH: usize = 2048;
pub const MAX_PATH_LENGTH: usize = 2048;
pub const MAX_TITLE_LENGTH: usize = 1024;
pub const MAX_DIALOG_MESSAGE_LENGTH: usize = 2048;
pub const MAX_PROMPT_TEXT_LENGTH: usize = 1024;
pub const MAX_TEXT_INPUT_LENGTH: usize = 256;
pub const MAX_KEY_LENGTH: usize = 32;
pub const MAX_WHEEL_DELTA: i32 = 10_000;
/// The modifier bitmask as CDP spells it: Alt 1, Control 2, Meta 4, Shift 8.
pub const MAX_MODIFIERS: u8 = 15;
pub const MAX_CLICK_COUNT: u8 = 3;
/// The most chunks a receiver may have admitted and not yet seen, per transfer.
pub const TRANSFER_CREDIT_MAX_CHUNKS: u8 = 32;
pub const MAX_FILENAME_LENGTH: usize = 255;
pub const MAX_MIME_LENGTH: usize = 255;
pub const MAX_ACCEPT_ENTRIES: usize = 128;

const INVALID: Violation = Violation("view_document");

fn require(condition: bool) -> Result<(), Violation> {
    if condition { Ok(()) } else { Err(INVALID) }
}

/// Pydantic counts characters, not bytes, so the bounds do too.
fn char_count(value: &str) -> usize {
    value.chars().count()
}

fn has_control_character(value: &str) -> bool {
    value
        .chars()
        .any(|character| character < '\u{20}' || character == '\u{7f}')
}

fn within_scale(scale: f64) -> bool {
    scale.is_finite() && (MIN_SCALE..=MAX_SCALE).contains(&scale)
}

/// Whether `value` is exactly `length` lower-case hexadecimal characters.
pub fn is_lower_hex(value: &str, length: usize) -> bool {
    value.len() == length
        && value
            .bytes()
            .all(|byte| matches!(byte, b'0'..=b'9' | b'a'..=b'f'))
}

/// The host name an authority names, or `None` when it names none.
fn hostname(authority: &str) -> Option<&str> {
    let host = match authority.strip_prefix('[') {
        Some(bracketed) => bracketed.split_once(']')?.0,
        None => authority.split(':').next()?,
    };
    (!host.is_empty()).then_some(host)
}

/// A lower-case `https` origin and nothing else. Stricter than the Python
/// reader on whitespace and userinfo, never looser.
fn is_origin(origin: &str) -> bool {
    let Some(authority) = origin.strip_prefix("https://") else {
        return false;
    };
    authority == authority.to_lowercase()
        && !authority.chars().any(|character| {
            matches!(character, '/' | '?' | '#' | '@' | '\\') || character.is_whitespace()
        })
        && hostname(authority).is_some()
}

/// A URL on exactly `origin`, with no credentials, space or control character.
/// `origin` is an origin `is_origin` admits, so what follows it can only be the
/// path, query or fragment.
fn is_address_of(address: &str, origin: &str) -> bool {
    address
        .strip_prefix(origin)
        .is_some_and(|rest| rest.is_empty() || rest.starts_with(['/', '?', '#']))
        && !has_control_character(address)
        && !address.contains(' ')
}

fn is_file_name(name: &str) -> bool {
    (1..=MAX_FILENAME_LENGTH).contains(&char_count(name))
        && !name
            .chars()
            .any(|character| character < '\u{20}' || matches!(character, '\u{7f}' | '/' | '\\'))
        && name != "."
        && name != ".."
}

fn is_media_type(value: &str) -> bool {
    fn token(part: &str) -> bool {
        !part.is_empty()
            && part
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || b"!#$&^_.+-".contains(&byte))
    }
    (3..=MAX_MIME_LENGTH).contains(&value.len())
        && value
            .split_once('/')
            .is_some_and(|(kind, subtype)| token(kind) && token(subtype))
}

fn is_accept_token(value: &str) -> bool {
    (1..=MAX_MIME_LENGTH).contains(&value.len())
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"!#$&^_.+*/-".contains(&byte))
}

fn optional_media_type(value: Option<&str>) -> bool {
    value.is_none_or(is_media_type)
}

macro_rules! redacted_debug {
    ($($name:ident),+ $(,)?) => {
        $(impl fmt::Debug for $name {
            fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
                formatter.write_str(concat!(stringify!($name), "(..)"))
            }
        })+
    };
}

/// Where the view's operation is: logging in, browsing, or publishing on close.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ViewPhase {
    /// A login runs in the view; the person's input still reaches the page and
    /// interrupts an assisted step.
    Acquiring,
    /// The person browses; input reaches the page.
    Browsing,
    /// The view captures, verifies and publishes its session; the panel is busy.
    Closing,
}

/// Every notice the view may show.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ViewNoticeCode {
    DialogOpened,
}

/// The page dialog kinds, spelled as CDP and Playwright spell them.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ViewDialogKind {
    Alert,
    Confirm,
    Prompt,
    Beforeunload,
}

/// Why a view connection ended; the operation's own result says how it settled.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ViewClosedReason {
    /// The person closed the page or the window.
    Cancelled,
    IdleExpired,
    LifetimeExpired,
    /// The window's person session was signed out, locked, expired or replaced.
    SessionRetired,
    /// The view's operation settled for another reason.
    OperationEnded,
    /// A later attach bound a new view connection to the operation.
    Replaced,
    /// A peer sent a frame or document the contract refuses.
    ProtocolViolation,
    RuntimeStopping,
    /// The view's browser failed.
    Failed,
}

/// Announces the next image; its chunks follow at once, contiguous and in order.
///
/// `sequence` strictly increases on a view connection and may skip values,
/// because a producer without credit replaces its pending image.
/// `byte_length` equals the image length in every chunk header.
#[derive(Clone, Copy, Debug, PartialEq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewImage {
    pub sequence: u32,
    pub byte_length: u32,
    pub pixel_width: u32,
    pub pixel_height: u32,
    pub css_width: u32,
    pub css_height: u32,
    pub scale: f64,
}

impl ViewImage {
    pub fn validate(&self) -> Result<(), Violation> {
        require(
            (1..=IMAGE_MAX_BYTES).contains(&self.byte_length)
                && (1..=MAX_PIXEL_EXTENT).contains(&self.pixel_width)
                && (1..=MAX_PIXEL_EXTENT).contains(&self.pixel_height)
                && (1..=MAX_CSS_EXTENT).contains(&self.css_width)
                && (1..=MAX_CSS_EXTENT).contains(&self.css_height)
                && within_scale(self.scale),
        )
    }
}

/// The page: origin and path for the toolbar, and the full address for the
/// desktop host alone.
///
/// `origin` and `path` never carry a query or fragment; they are what the
/// window shows. `address` is the page's whole URL, query included, so that the
/// person's external open lands on the same page. The host keeps it in memory
/// and never relays it to the window; it is `None` when the worker could not
/// state it within the contract.
#[derive(Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewState {
    pub origin: String,
    pub path: String,
    #[serde(default)]
    pub address: Option<String>,
    pub title: String,
    pub can_go_back: bool,
    pub can_go_forward: bool,
    pub loading: bool,
    pub phase: ViewPhase,
}

impl ViewState {
    pub fn validate(&self) -> Result<(), Violation> {
        require(
            (1..=MAX_URL_LENGTH).contains(&char_count(&self.origin))
                && (1..=MAX_PATH_LENGTH).contains(&char_count(&self.path))
                && char_count(&self.title) <= MAX_TITLE_LENGTH
                && is_origin(&self.origin)
                && self.path.starts_with('/')
                && !self.path.contains(['?', '#'])
                && !has_control_character(&self.origin)
                && !has_control_character(&self.path)
                && self.address.as_deref().is_none_or(|address| {
                    (1..=MAX_URL_LENGTH).contains(&char_count(address))
                        && is_address_of(address, &self.origin)
                }),
        )
    }
}

/// A page dialog waiting for the person's answer under its `dialog_id`.
#[derive(Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewDialogPrompt {
    pub dialog_id: u32,
    pub dialog_kind: ViewDialogKind,
    pub message: String,
    #[serde(default)]
    pub default_prompt: Option<String>,
}

impl ViewDialogPrompt {
    pub fn validate(&self) -> Result<(), Violation> {
        require(
            self.dialog_id >= 1
                && char_count(&self.message) <= MAX_DIALOG_MESSAGE_LENGTH
                && self
                    .default_prompt
                    .as_deref()
                    .is_none_or(|text| char_count(text) <= MAX_PROMPT_TEXT_LENGTH)
                && (self.default_prompt.is_none() || self.dialog_kind == ViewDialogKind::Prompt),
        )
    }
}

/// One closed notice; `dialog_opened` carries exactly one dialog.
#[derive(Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewNotice {
    pub code: ViewNoticeCode,
    #[serde(default)]
    pub dialog: Option<ViewDialogPrompt>,
}

impl ViewNotice {
    pub fn validate(&self) -> Result<(), Violation> {
        require(self.dialog.is_some() == (self.code == ViewNoticeCode::DialogOpened))?;
        self.dialog
            .as_ref()
            .map_or(Ok(()), ViewDialogPrompt::validate)
    }
}

/// The last document on a view connection.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewClosed {
    pub reason: ViewClosedReason,
}

/// Offers a download to the person; its bytes flow only after the window accepts.
///
/// `filename` is a hint for the native save dialog and never a path. `size`
/// is a progress hint; the completion document carries the size that counts.
#[derive(Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewDownload {
    pub transfer_id: u32,
    pub filename: String,
    #[serde(default)]
    pub size: Option<u64>,
    #[serde(default)]
    pub mime: Option<String>,
}

impl ViewDownload {
    pub fn validate(&self) -> Result<(), Violation> {
        require(
            self.transfer_id >= 1
                && is_file_name(&self.filename)
                && optional_media_type(self.mime.as_deref()),
        )
    }
}

/// The page asks for files; the window answers under `chooser_id`.
#[derive(Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewFileChooser {
    pub chooser_id: u32,
    /// Extensions such as `.pdf` or media types such as `image/*`; empty when
    /// the page names none.
    pub accept: Vec<String>,
    pub multiple: bool,
}

impl ViewFileChooser {
    pub fn validate(&self) -> Result<(), Violation> {
        require(
            self.chooser_id >= 1
                && self.accept.len() <= MAX_ACCEPT_ENTRIES
                && self.accept.iter().all(|token| is_accept_token(token)),
        )
    }
}

/// The sender's close of a transfer: the exact size and sha256 of every byte it sent.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewTransferComplete {
    pub transfer_id: u32,
    pub size: u64,
    pub sha256: String,
}

impl ViewTransferComplete {
    pub fn validate(&self) -> Result<(), Violation> {
        require(self.transfer_id >= 1 && is_lower_hex(&self.sha256, 64))
    }
}

/// Admits more chunks of a transfer; outstanding credit never exceeds the window.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewTransferCredit {
    pub transfer_id: u32,
    pub chunks: u8,
}

impl ViewTransferCredit {
    pub fn validate(&self) -> Result<(), Violation> {
        require(self.transfer_id >= 1 && (1..=TRANSFER_CREDIT_MAX_CHUNKS).contains(&self.chunks))
    }
}

/// Which way a transfer's bytes travel.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ViewTransferDirection {
    /// From the page toward the window.
    Download,
    /// From the window toward the page.
    Upload,
}

/// Stops a transfer, from either end.
///
/// `direction` says which way the transfer's bytes travel, because the two
/// ends allocate ids independently.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewTransferCancel {
    pub direction: ViewTransferDirection,
    pub transfer_id: u32,
}

impl ViewTransferCancel {
    pub fn validate(&self) -> Result<(), Violation> {
        require(self.transfer_id >= 1)
    }
}

/// Everything a view connection sends toward the window.
#[derive(Clone, PartialEq, Deserialize)]
#[serde(tag = "kind")]
pub enum ViewDownstream {
    #[serde(rename = "view.image")]
    Image(ViewImage),
    #[serde(rename = "view.state")]
    State(ViewState),
    #[serde(rename = "view.notice")]
    Notice(ViewNotice),
    #[serde(rename = "view.closed")]
    Closed(ViewClosed),
    #[serde(rename = "view.download")]
    Download(ViewDownload),
    #[serde(rename = "view.file_chooser")]
    FileChooser(ViewFileChooser),
    #[serde(rename = "view.transfer_complete")]
    TransferComplete(ViewTransferComplete),
    #[serde(rename = "view.transfer_credit")]
    TransferCredit(ViewTransferCredit),
    #[serde(rename = "view.transfer_cancel")]
    TransferCancel(ViewTransferCancel),
}

impl ViewDownstream {
    /// Decodes and validates one `J` payload; any failure is a violation that
    /// carries no document content.
    pub fn decode(payload: &[u8]) -> Result<Self, Violation> {
        let document: Self = serde_json::from_slice(payload).map_err(|_| INVALID)?;
        document.validate()?;
        Ok(document)
    }

    pub fn validate(&self) -> Result<(), Violation> {
        match self {
            Self::Image(document) => document.validate(),
            Self::State(document) => document.validate(),
            Self::Notice(document) => document.validate(),
            Self::Closed(_) => Ok(()),
            Self::Download(document) => document.validate(),
            Self::FileChooser(document) => document.validate(),
            Self::TransferComplete(document) => document.validate(),
            Self::TransferCredit(document) => document.validate(),
            Self::TransferCancel(document) => document.validate(),
        }
    }

    /// The document's `kind`, as it is spelled on the wire.
    pub fn kind(&self) -> &'static str {
        match self {
            Self::Image(_) => "view.image",
            Self::State(_) => "view.state",
            Self::Notice(_) => "view.notice",
            Self::Closed(_) => "view.closed",
            Self::Download(_) => "view.download",
            Self::FileChooser(_) => "view.file_chooser",
            Self::TransferComplete(_) => "view.transfer_complete",
            Self::TransferCredit(_) => "view.transfer_credit",
            Self::TransferCancel(_) => "view.transfer_cancel",
        }
    }
}

/// Grants the producer more images after drawing; outstanding credit never exceeds two.
///
/// A view connection starts with no credit, so the window grants its first
/// credit after attaching.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewCredit {
    pub images: u8,
}

impl ViewCredit {
    pub fn validate(&self) -> Result<(), Violation> {
        require((1..=CREDIT_MAX_IMAGES).contains(&self.images))
    }
}

/// Pointer actions, translated to CDP `mousePressed`, `mouseReleased` and `mouseMoved`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PointerAction {
    Down,
    Up,
    Move,
}

/// Pointer buttons as CDP spells them.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PointerButton {
    None,
    Left,
    Middle,
    Right,
}

/// Key actions, translated to CDP `keyDown` and `keyUp`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum KeyAction {
    Down,
    Up,
}

/// A pointer event at CSS pixel coordinates within the panel.
#[derive(Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PointerInput {
    pub action: PointerAction,
    pub x: u32,
    pub y: u32,
    pub button: PointerButton,
    pub click_count: u8,
    pub modifiers: u8,
}

impl PointerInput {
    pub fn validate(&self) -> Result<(), Violation> {
        let press_is_whole = match self.action {
            PointerAction::Move => self.click_count == 0,
            PointerAction::Down | PointerAction::Up => {
                self.button != PointerButton::None && self.click_count >= 1
            }
        };
        require(
            self.x < MAX_CSS_EXTENT
                && self.y < MAX_CSS_EXTENT
                && self.click_count <= MAX_CLICK_COUNT
                && self.modifiers <= MAX_MODIFIERS
                && press_is_whole,
        )
    }
}

/// A wheel scroll at CSS pixel coordinates, with deltas in CSS pixels.
#[derive(Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WheelInput {
    pub x: u32,
    pub y: u32,
    pub delta_x: i32,
    pub delta_y: i32,
    pub modifiers: u8,
}

impl WheelInput {
    pub fn validate(&self) -> Result<(), Violation> {
        let delta = -MAX_WHEEL_DELTA..=MAX_WHEEL_DELTA;
        require(
            self.x < MAX_CSS_EXTENT
                && self.y < MAX_CSS_EXTENT
                && delta.contains(&self.delta_x)
                && delta.contains(&self.delta_y)
                && self.modifiers <= MAX_MODIFIERS,
        )
    }
}

/// A key event with its DOM `key` and `code` values; printable text arrives as text input.
#[derive(Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct KeyInput {
    pub action: KeyAction,
    pub key: String,
    pub code: String,
    pub modifiers: u8,
}

impl KeyInput {
    pub fn validate(&self) -> Result<(), Violation> {
        require(
            (1..=MAX_KEY_LENGTH).contains(&char_count(&self.key))
                && char_count(&self.code) <= MAX_KEY_LENGTH
                && !has_control_character(&self.key)
                && !has_control_character(&self.code)
                && self.modifiers <= MAX_MODIFIERS,
        )
    }
}

/// Text inserted at the focus, translated to CDP `Input.insertText`.
#[derive(Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TextInput {
    pub text: String,
}

impl TextInput {
    pub fn validate(&self) -> Result<(), Violation> {
        require(
            (1..=MAX_TEXT_INPUT_LENGTH).contains(&char_count(&self.text))
                && !has_control_character(&self.text),
        )
    }
}

/// One person input event for the view's page.
#[derive(Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum ViewInputEvent {
    Pointer(PointerInput),
    Wheel(WheelInput),
    Key(KeyInput),
    Text(TextInput),
}

impl ViewInputEvent {
    pub fn validate(&self) -> Result<(), Violation> {
        match self {
            Self::Pointer(event) => event.validate(),
            Self::Wheel(event) => event.validate(),
            Self::Key(event) => event.validate(),
            Self::Text(event) => event.validate(),
        }
    }
}

#[derive(Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewInput {
    pub event: ViewInputEvent,
}

/// The toolbar's navigation verbs; `home` opens the Sede start page.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ViewNavigateVerb {
    Back,
    Forward,
    Reload,
    Home,
}

/// A toolbar navigation; the view never accepts a URL from the window.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewNavigate {
    pub verb: ViewNavigateVerb,
}

/// The panel's new CSS size and device pixel ratio.
#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewResize {
    pub css_width: u32,
    pub css_height: u32,
    pub scale: f64,
}

impl ViewResize {
    pub fn validate(&self) -> Result<(), Violation> {
        require(
            (1..=MAX_CSS_EXTENT).contains(&self.css_width)
                && (1..=MAX_CSS_EXTENT).contains(&self.css_height)
                && within_scale(self.scale),
        )
    }
}

/// The person's answer to the dialog announced under `dialog_id`.
#[derive(Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewDialog {
    pub dialog_id: u32,
    pub accept: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub prompt_text: Option<String>,
}

impl ViewDialog {
    pub fn validate(&self) -> Result<(), Violation> {
        require(
            self.dialog_id >= 1
                && self
                    .prompt_text
                    .as_deref()
                    .is_none_or(|text| char_count(text) <= MAX_PROMPT_TEXT_LENGTH)
                && (self.accept || self.prompt_text.is_none()),
        )
    }
}

/// The person closed the page or the window: end the view and publish its session.
///
/// Closing is not a cancellation. The view stops taking input, publishes its
/// session through the canonical custody path and settles; a view connection
/// that drops without this document is closed the same way.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewClose {}

/// The window's answer to a download offer.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ViewDownloadOutcome {
    /// The person chose a path in the native save dialog; bytes flow once credit arrives.
    Accepted,
    /// The host declined the file; no bytes will be sent.
    Refused,
    /// The person closed the save dialog; no bytes will be sent.
    Cancelled,
}

/// Accepts, refuses or cancels the download offered under `transfer_id`.
///
/// It is the first and only answer to an offer. Stopping an accepted
/// download in flight is `view.transfer_cancel`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewDownloadAnswer {
    pub transfer_id: u32,
    pub outcome: ViewDownloadOutcome,
}

impl ViewDownloadAnswer {
    pub fn validate(&self) -> Result<(), Violation> {
        require(self.transfer_id >= 1)
    }
}

/// The window's answer to a file chooser request.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ViewFileChooserOutcome {
    /// The person chose files; one `view.upload` per file follows.
    Supplied,
    /// The person closed the open dialog.
    Cancelled,
}

/// Supplies files for the chooser, or cancels it.
///
/// A supplied answer names how many files follow, at least one and exactly
/// one when the chooser was not `multiple`; each file then travels as a
/// `view.upload` and its chunks.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewFileChooserAnswer {
    pub chooser_id: u32,
    pub outcome: ViewFileChooserOutcome,
    pub file_count: u32,
}

impl ViewFileChooserAnswer {
    pub fn validate(&self) -> Result<(), Violation> {
        require(
            self.chooser_id >= 1
                && (self.outcome == ViewFileChooserOutcome::Supplied) == (self.file_count > 0),
        )
    }
}

/// Describes one file supplied for the chooser; its chunks and completion follow.
///
/// `size` is the file's exact byte count; the receiver refuses an upload
/// whose bytes differ from it.
#[derive(Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewUpload {
    pub chooser_id: u32,
    pub transfer_id: u32,
    pub name: String,
    pub size: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mime: Option<String>,
}

impl ViewUpload {
    pub fn validate(&self) -> Result<(), Violation> {
        require(
            self.chooser_id >= 1
                && self.transfer_id >= 1
                && is_file_name(&self.name)
                && optional_media_type(self.mime.as_deref()),
        )
    }
}

/// Everything the window sends on a view connection.
#[derive(Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind")]
pub enum ViewUpstream {
    #[serde(rename = "view.credit")]
    Credit(ViewCredit),
    #[serde(rename = "view.input")]
    Input(ViewInput),
    #[serde(rename = "view.navigate")]
    Navigate(ViewNavigate),
    #[serde(rename = "view.resize")]
    Resize(ViewResize),
    #[serde(rename = "view.dialog")]
    Dialog(ViewDialog),
    #[serde(rename = "view.close")]
    Close(ViewClose),
    #[serde(rename = "view.download_answer")]
    DownloadAnswer(ViewDownloadAnswer),
    #[serde(rename = "view.file_chooser_answer")]
    FileChooserAnswer(ViewFileChooserAnswer),
    #[serde(rename = "view.upload")]
    Upload(ViewUpload),
    #[serde(rename = "view.transfer_complete")]
    TransferComplete(ViewTransferComplete),
    #[serde(rename = "view.transfer_credit")]
    TransferCredit(ViewTransferCredit),
    #[serde(rename = "view.transfer_cancel")]
    TransferCancel(ViewTransferCancel),
}

impl ViewUpstream {
    pub fn validate(&self) -> Result<(), Violation> {
        match self {
            Self::Credit(document) => document.validate(),
            Self::Input(document) => document.event.validate(),
            Self::Navigate(_) => Ok(()),
            Self::Resize(document) => document.validate(),
            Self::Dialog(document) => document.validate(),
            Self::Close(_) => Ok(()),
            Self::DownloadAnswer(document) => document.validate(),
            Self::FileChooserAnswer(document) => document.validate(),
            Self::Upload(document) => document.validate(),
            Self::TransferComplete(document) => document.validate(),
            Self::TransferCredit(document) => document.validate(),
            Self::TransferCancel(document) => document.validate(),
        }
    }

    /// Validates the document and encodes it as one `J` payload, which holds
    /// private input until it is dropped.
    pub fn encode(&self) -> Result<Zeroizing<Vec<u8>>, Violation> {
        self.validate()?;
        serde_json::to_vec(self)
            .map(Zeroizing::new)
            .map_err(|_| INVALID)
    }

    /// The document's `kind`, as it is spelled on the wire.
    pub fn kind(&self) -> &'static str {
        match self {
            Self::Credit(_) => "view.credit",
            Self::Input(_) => "view.input",
            Self::Navigate(_) => "view.navigate",
            Self::Resize(_) => "view.resize",
            Self::Dialog(_) => "view.dialog",
            Self::Close(_) => "view.close",
            Self::DownloadAnswer(_) => "view.download_answer",
            Self::FileChooserAnswer(_) => "view.file_chooser_answer",
            Self::Upload(_) => "view.upload",
            Self::TransferComplete(_) => "view.transfer_complete",
            Self::TransferCredit(_) => "view.transfer_credit",
            Self::TransferCancel(_) => "view.transfer_cancel",
        }
    }
}

redacted_debug!(
    ViewState,
    ViewDialogPrompt,
    ViewNotice,
    ViewDownload,
    ViewFileChooser,
    ViewDownstream,
    PointerInput,
    WheelInput,
    KeyInput,
    TextInput,
    ViewInputEvent,
    ViewInput,
    ViewDialog,
    ViewUpload,
    ViewUpstream,
);

#[cfg(test)]
mod tests {
    use super::*;
    use crate::view_stream::vectors::{self, Direction};

    #[test]
    fn documents_in_the_shared_vectors_are_accepted_or_refused_as_python_does() {
        let vectors = vectors::load();
        let mut accepted = 0;
        for entry in vectors.accepted_documents() {
            let payload = entry.payload();
            match entry.direction {
                Direction::Downstream => {
                    let document = ViewDownstream::decode(&payload)
                        .unwrap_or_else(|violation| panic!("{}: {violation}", entry.name));
                    assert_eq!(
                        document.kind(),
                        entry.document["kind"].as_str().unwrap(),
                        "{}",
                        entry.name
                    );
                }
                Direction::Upstream => {
                    let document = decode_upstream(&payload)
                        .unwrap_or_else(|violation| panic!("{}: {violation}", entry.name));
                    // What the window writes, Python reads back as the same document.
                    let encoded = document.encode().unwrap();
                    assert_eq!(
                        decode_upstream(&encoded).unwrap(),
                        document,
                        "{}",
                        entry.name
                    );
                }
            }
            accepted += 1;
        }
        assert!(accepted > 40, "{accepted}");
    }

    #[test]
    fn refused_documents_in_the_shared_vectors_are_refused() {
        let vectors = vectors::load();
        let mut refused = 0;
        for entry in vectors.refused_documents() {
            let payload = entry.payload();
            let outcome = match entry.direction {
                Direction::Downstream => ViewDownstream::decode(&payload).map(|_| ()),
                Direction::Upstream => decode_upstream(&payload).map(|_| ()),
            };
            assert_eq!(outcome, Err(INVALID), "{}", entry.name);
            refused += 1;
        }
        assert!(refused > 60, "{refused}");
    }

    fn decode_upstream(payload: &[u8]) -> Result<ViewUpstream, Violation> {
        let document: ViewUpstream = serde_json::from_slice(payload).map_err(|_| INVALID)?;
        document.validate()?;
        Ok(document)
    }

    #[test]
    fn private_documents_print_no_content() {
        let state = ViewDownstream::State(ViewState {
            origin: "https://sede.agenciatributaria.gob.es".into(),
            path: "/Sede/inicio.html".into(),
            address: Some(
                "https://sede.agenciatributaria.gob.es/Sede/inicio.html?nif=private".into(),
            ),
            title: "private title".into(),
            can_go_back: false,
            can_go_forward: false,
            loading: false,
            phase: ViewPhase::Browsing,
        });
        let input = ViewUpstream::Input(ViewInput {
            event: ViewInputEvent::Text(TextInput {
                text: "private text".into(),
            }),
        });
        for printed in [format!("{state:?}"), format!("{input:?}")] {
            assert!(!printed.contains("private"), "{printed}");
            assert!(!printed.contains("sede"), "{printed}");
        }
    }

    #[test]
    fn origins_follow_the_python_checks() {
        for origin in [
            "https://sede.agenciatributaria.gob.es",
            "https://localhost:8443",
            "https://[::1]:8443",
        ] {
            assert!(is_origin(origin), "{origin}");
        }
        for origin in [
            "http://sede.agenciatributaria.gob.es",
            "https://",
            "https://:443",
            "https://Sede.example",
            "https://sede.example/",
            "https://sede.example?q",
            "https://user@sede.example",
            "https://sede .example",
        ] {
            assert!(!is_origin(origin), "{origin}");
        }
    }

    #[test]
    fn bounds_count_characters_not_bytes() {
        let text = "ñ".repeat(MAX_TEXT_INPUT_LENGTH);
        assert!(
            TextInput { text: text.clone() }.validate().is_ok(),
            "256 two-byte characters fit"
        );
        assert!(
            TextInput {
                text: format!("{text}ñ")
            }
            .validate()
            .is_err()
        );
    }
}
