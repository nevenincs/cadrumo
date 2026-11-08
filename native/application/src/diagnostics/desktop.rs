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

/// A refusal code of the agent host, such as `agent_service_busy`. The host
/// words these itself, and the gateway's own code is appended to a fixed
/// `agent_gateway_` prefix after the host has checked its characters, so a
/// code is a short snake_case token and never exception or payload text.
#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(transparent)]
pub struct AgentRefusalCode(String);

impl AgentRefusalCode {
    const PREFIX: &'static str = "agent_";
    const MAX_LEN: usize = 96;

    pub fn parse(code: &str) -> Option<Self> {
        let rest = code.strip_prefix(Self::PREFIX)?;
        let token = !rest.is_empty()
            && code.len() <= Self::MAX_LEN
            && rest
                .bytes()
                .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_');
        token.then(|| Self(code.to_owned()))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl<'de> Deserialize<'de> for AgentRefusalCode {
    fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        let code = String::deserialize(deserializer)?;
        Self::parse(&code)
            .ok_or_else(|| serde::de::Error::custom("not an agent refusal code token"))
    }
}

/// Only closed host codes may be persisted; exception and payload text never qualify.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(untagged)]
pub enum DesktopDiagnosticCode {
    Application(ErrorCode),
    Relay(RelayFailureCode),
    Agent(AgentRefusalCode),
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
