//! Safe application-boundary failures. Original causes stay local, never serialized.
use serde::Serialize;
use std::{error::Error, fmt, sync::Arc};

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
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
    LockPoisoned,
    LogUnavailable,
    DesktopUnavailable,
    WebviewFailed,
    UnsupportedPlatform,
    InstanceLockForeign,
    Panic,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
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
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ApplicationError {
    pub code: ErrorCode,
    pub operation: Operation,
    pub message: &'static str,
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
            ErrorCode::LockPoisoned => "Application state is unavailable after a worker failure",
            ErrorCode::LogUnavailable => "The diagnostic log could not be written",
            ErrorCode::DesktopUnavailable => "No interactive desktop is available; use --headless",
            ErrorCode::WebviewFailed => "The application window could not be created",
            ErrorCode::UnsupportedPlatform => "Desktop operation is not available on this platform",
            ErrorCode::InstanceLockForeign => "Another account holds the application lock",
            ErrorCode::Panic => "An unexpected application failure occurred",
        };
        Self {
            code,
            operation,
            message,
            cause: None,
        }
    }
    pub fn caused_by<E: Error + Send + Sync + 'static>(mut self, cause: E) -> Self {
        self.cause = Some(Arc::new(cause));
        self
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
