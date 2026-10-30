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

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DesktopDiagnostic {
    pub origin: DiagnosticOrigin,
    pub logger: Option<String>,
    pub event: DesktopEvent,
    pub level: LogLevel,
    /// Resolved against registered command names by the host.
    pub command: Option<String>,
    pub code: Option<ErrorCode>,
    pub dropped: u32,
    pub line: Option<u32>,
    pub column: Option<u32>,
}
