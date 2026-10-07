//! Safe application-boundary failures. Original causes stay local, never serialized.
use serde::{Deserialize, Serialize};
use std::{error::Error, fmt, sync::Arc};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCode {
    InvalidArguments,
    PackageUnavailable,
    EnvironmentFailed,
    TimedOut,
    OutputLimit,
    SpawnFailed,
    ReadFailed,
    WriteFailed,
    ResizeFailed,
    CleanupFailed,
    SessionUnavailable,
    QueueFull,
    CliBusy,
    CliWaitTimedOut,
    LockPoisoned,
    LogUnavailable,
    DesktopUnavailable,
    WebviewFailed,
    WebviewProcessFailed,
    WebviewMonitorUnavailable,
    UnsupportedPlatform,
    InstanceLockForeign,
    ManagerUnavailable,
    ManagerDispatchFailed,
    Panic,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Operation {
    Launch,
    Package,
    Environment,
    Cli,
    Terminal,
    Logging,
    Webview,
    Shutdown,
    Manager,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ApplicationError {
    pub code: ErrorCode,
    pub operation: Operation,
    pub message: &'static str,
    #[serde(
        serialize_with = "serialize_io_kind",
        skip_serializing_if = "Option::is_none"
    )]
    pub io_kind: Option<std::io::ErrorKind>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub os_code: Option<i32>,
    #[serde(skip)]
    cause: Option<Arc<dyn Error + Send + Sync>>,
}

impl ApplicationError {
    pub fn new(code: ErrorCode, operation: Operation) -> Self {
        let message = match code {
            ErrorCode::InvalidArguments => "Invalid application arguments",
            ErrorCode::PackageUnavailable => "The application package could not be verified",
            ErrorCode::EnvironmentFailed => "The packaged environment could not be prepared",
            ErrorCode::TimedOut => "The child process exceeded its deadline",
            ErrorCode::OutputLimit => "The child output exceeded its limit",
            ErrorCode::SpawnFailed => "The child process could not be started",
            ErrorCode::ReadFailed => "The child output could not be read",
            ErrorCode::WriteFailed => "The child input could not be written",
            ErrorCode::ResizeFailed => "The terminal could not be resized",
            ErrorCode::CleanupFailed => "Child cleanup could not be confirmed",
            ErrorCode::SessionUnavailable => "The terminal session is unavailable",
            ErrorCode::QueueFull => "The terminal input queue is full",
            ErrorCode::CliBusy => "The sign-in helper is busy",
            ErrorCode::CliWaitTimedOut => "Waiting for the sign-in helper timed out",
            ErrorCode::LockPoisoned => "Application state is unavailable after a worker failure",
            ErrorCode::LogUnavailable => "The diagnostic log could not be written",
            ErrorCode::DesktopUnavailable => "No interactive desktop is available; use --headless",
            ErrorCode::WebviewFailed => "The application window could not be created",
            ErrorCode::WebviewProcessFailed => "An application browser process failed",
            ErrorCode::WebviewMonitorUnavailable => "Browser process diagnostics are unavailable",
            ErrorCode::UnsupportedPlatform => "Desktop operation is not available on this platform",
            ErrorCode::InstanceLockForeign => "Another account holds the application lock",
            ErrorCode::ManagerUnavailable => "The background-services manager is unavailable",
            ErrorCode::ManagerDispatchFailed => {
                "The background-services manager could not be started"
            }
            ErrorCode::Panic => "An unexpected application failure occurred",
        };
        Self {
            code,
            operation,
            message,
            io_kind: None,
            os_code: None,
            cause: None,
        }
    }
    pub fn caused_by<E: Error + Send + Sync + 'static>(mut self, cause: E) -> Self {
        // Wrappers can carry an I/O cause; only its enum kind and numeric OS
        // code may leave this boundary, never its path or formatted message.
        self.io_kind = None;
        self.os_code = None;
        let mut current: &(dyn Error + 'static) = &cause;
        for _ in 0..32 {
            if let Some(error) = current.downcast_ref::<std::io::Error>() {
                self.io_kind = Some(error.kind());
                self.os_code = error.raw_os_error();
                if self.os_code.is_some() {
                    break;
                }
            }
            match current.source() {
                Some(source) => current = source,
                None => break,
            }
        }
        self.cause = Some(Arc::new(cause));
        self
    }
}
fn serialize_io_kind<S: serde::Serializer>(
    kind: &Option<std::io::ErrorKind>,
    serializer: S,
) -> std::result::Result<S::Ok, S::Error> {
    match kind {
        Some(kind) => serializer.serialize_str(&format!("{kind:?}")),
        None => serializer.serialize_none(),
    }
}
impl fmt::Display for ApplicationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:?}: {}", self.code, self.message)
    }
}
impl fmt::Debug for ApplicationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        fmt::Display::fmt(self, f)
    }
}
impl Error for ApplicationError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        self.cause.as_deref().map(|e| e as &dyn Error)
    }
}
pub type Result<T> = std::result::Result<T, ApplicationError>;
