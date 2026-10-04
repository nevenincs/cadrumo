//! Safe application-boundary failures. Original causes stay local, never serialized.
use serde::Serialize;
use std::{error::Error, fmt, sync::Arc};

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum FailureCode {
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
pub struct Failure {
    pub code: FailureCode,
    pub operation: Operation,
    pub message: &'static str,
    #[serde(skip)]
    cause: Option<Arc<dyn Error + Send + Sync>>,
}

impl Failure {
    pub fn new(code: FailureCode, operation: Operation) -> Self {
        let message = match code {
            FailureCode::InvalidArguments => "Invalid application arguments",
            FailureCode::PackageUnavailable => "The application package could not be verified",
            FailureCode::EnvironmentFailed => "The packaged environment could not be prepared",
            FailureCode::TimedOut => "The child process exceeded its deadline",
            FailureCode::OutputLimit => "The child output exceeded its limit",
            FailureCode::SpawnFailed => "The child process could not be started",
            FailureCode::ReadFailed => "The child output could not be read",
            FailureCode::WriteFailed => "The child input could not be written",
            FailureCode::ResizeFailed => "The terminal could not be resized",
            FailureCode::CleanupFailed => "Child cleanup could not be confirmed",
            FailureCode::SessionUnavailable => "The terminal session is unavailable",
            FailureCode::QueueFull => "The terminal input queue is full",
            FailureCode::LockPoisoned => "Application state is unavailable after a worker failure",
            FailureCode::LogUnavailable => "The diagnostic log could not be written",
            FailureCode::DesktopUnavailable => {
                "No interactive desktop is available; use --headless"
            }
            FailureCode::WebviewFailed => "The application window could not be created",
            FailureCode::UnsupportedPlatform => {
                "Desktop operation is not available on this platform"
            }
            FailureCode::Panic => "An unexpected application failure occurred",
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
impl fmt::Display for Failure {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:?}: {}", self.code, self.message)
    }
}
impl fmt::Debug for Failure {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        fmt::Display::fmt(self, f)
    }
}
impl Error for Failure {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        self.cause.as_deref().map(|e| e as &dyn Error)
    }
}
pub type Result<T> = std::result::Result<T, Failure>;
