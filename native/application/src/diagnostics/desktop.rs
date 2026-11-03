//! Payload-free observations from the desktop and its presentation libraries.
use super::service::LogLevel;
use crate::error::application::ErrorCode;
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DesktopEvent {
    CommandRejected,
    UncaughtError,
    UnhandledRejection,
    ReactError,
    Console,
    NativeLog,
}

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DiagnosticOrigin {
    Frontend,
    Rust,
    Tauri,
}

/// A host relay's payload-free failure vocabulary, separate from application errors.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RelayFailureCode {
    Unavailable,
    Unknown,
    SavedUnread,
    Refused,
    NotAdmitted,
    NotSignedIn,
    Invalid,
    TooLarge,
    FileUnavailable,
    ReviewChanged,
    Conflict,
}

/// Only closed host codes may be persisted; exception and payload text never qualify.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(untagged)]
pub enum DesktopDiagnosticCode {
    Application(ErrorCode),
    Relay(RelayFailureCode),
}

impl From<ErrorCode> for DesktopDiagnosticCode {
    fn from(code: ErrorCode) -> Self {
        Self::Application(code)
    }
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DesktopDiagnostic {
    pub origin: DiagnosticOrigin,
    pub logger: Option<String>,
    pub event: DesktopEvent,
    pub level: LogLevel,
    /// Resolved against registered command names by the host.
    pub command: Option<String>,
    pub code: Option<DesktopDiagnosticCode>,
    pub dropped: u32,
    pub line: Option<u32>,
    pub column: Option<u32>,
}
