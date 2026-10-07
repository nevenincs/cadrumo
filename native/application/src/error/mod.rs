pub mod application;

use std::{fmt, io};

#[derive(Debug)]
pub enum Error {
    Io(io::Error),
    Json(serde_json::Error),
    Archive(zip::result::ZipError),
    Invalid(String),
    Incompatible(String),
    Integrity(String),
    Busy,
    Cancelled,
    LimitExceeded,
    Download,
    TimedOut,
    ProbeFailed,
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(e) => write!(f, "filesystem operation failed: {e}"),
            Self::Json(e) => write!(f, "invalid metadata: {e}"),
            Self::Archive(e) => write!(f, "invalid component archive: {e}"),
            Self::Invalid(s) => write!(f, "invalid input: {s}"),
            Self::Incompatible(s) => write!(f, "incompatible component: {s}"),
            Self::Integrity(s) => write!(f, "integrity check failed: {s}"),
            Self::Busy => f.write_str("another component writer is active"),
            Self::Cancelled => f.write_str("provisioning cancelled"),
            Self::LimitExceeded => f.write_str("component resource limit exceeded"),
            Self::Download => f.write_str("component download failed"),
            Self::TimedOut => f.write_str("interpreter probe timed out"),
            Self::ProbeFailed => f.write_str("interpreter probe failed"),
        }
    }
}

impl std::error::Error for Error {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Io(error) => Some(error),
            Self::Json(error) => Some(error),
            Self::Archive(error) => Some(error),
            _ => None,
        }
    }
}
impl From<io::Error> for Error {
    fn from(value: io::Error) -> Self {
        Self::Io(value)
    }
}
impl From<serde_json::Error> for Error {
    fn from(value: serde_json::Error) -> Self {
        Self::Json(value)
    }
}
impl From<zip::result::ZipError> for Error {
    fn from(value: zip::result::ZipError) -> Self {
        Self::Archive(value)
    }
}
