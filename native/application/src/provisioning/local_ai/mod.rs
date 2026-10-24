//! The local AI item: the program that runs models, installed from its pinned portable
//! archive and run as the engine's own child, and the model every catalogue role reads
//! with, pulled through that program.
//!
//! `program` installs, checks, starts, stops and removes the program, and reports a copy
//! installed outside Cadrumo without touching it. `loopback` is the engine's client for
//! the program's own API on this computer.

pub mod loopback;
pub mod program;

#[cfg(test)]
pub(crate) mod fake_ollama;

use super::failure::FailureCategory;
use crate::error::Error;
use std::fmt;

/// A local AI act that did not complete: one closed failure category, or an engine error
/// whose category [`LocalAiError::category`] decides.
#[derive(Debug)]
pub enum LocalAiError {
    Failed(FailureCategory),
    Engine(Error),
}

impl LocalAiError {
    /// The closed category a surface words this failure with.
    pub fn category(&self) -> FailureCategory {
        match self {
            Self::Failed(category) => *category,
            Self::Engine(Error::Download(failure)) => failure.category,
            Self::Engine(Error::Cancelled) => FailureCategory::Cancelled,
            Self::Engine(Error::Io(error)) => super::transfer::file_failure(error).category,
            Self::Engine(Error::Integrity(_) | Error::Archive(_) | Error::LimitExceeded) => {
                FailureCategory::DamagedDownload
            }
            Self::Engine(_) => FailureCategory::Unexpected,
        }
    }
}

impl From<Error> for LocalAiError {
    fn from(error: Error) -> Self {
        Self::Engine(error)
    }
}

impl From<std::io::Error> for LocalAiError {
    fn from(error: std::io::Error) -> Self {
        Self::Engine(Error::Io(error))
    }
}

impl fmt::Display for LocalAiError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Failed(category) => write!(f, "local AI failed: {category}"),
            Self::Engine(error) => write!(f, "local AI failed: {error}"),
        }
    }
}

impl std::error::Error for LocalAiError {}
