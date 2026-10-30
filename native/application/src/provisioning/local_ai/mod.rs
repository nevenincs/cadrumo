//! The local AI item: the program that runs models, installed from its pinned portable
//! archive, the one server run from it on the installation's fixed loopback address, and
//! the model the person selected for each local role, pulled through that server.
//!
//! `program` installs, checks, starts, stops and removes the program, records where it
//! is, and reports a copy installed outside Cadrumo without touching it. `supervision`
//! is the runtime manager's part: it keeps the server running while the program is set
//! up. `lease` keeps that server and a change of the program apart across processes.
//! `models` pulls and checks each selected model through the running server, and
//! `hardware` decides whether this computer can hold a model of a given size. `loopback` is the
//! client for the program's own API on this computer. [`reading`] folds the parts into
//! the item's one reading.

pub mod hardware;
pub mod lease;
pub mod loopback;
pub mod models;
pub mod program;
pub mod supervision;

#[cfg(test)]
pub(crate) mod fake_ollama;

use super::{
    failure::FailureCategory,
    state::{CheckMode, Observation, Reading},
};
use crate::error::Error;
use std::{fmt, io, process::ExitStatus, time::Duration};

/// The local AI's one reading from its program's observation and version and each selected
/// model's observation, the worst of them deciding.
pub fn reading(
    mode: CheckMode,
    program: Observation,
    version: Option<String>,
    models: &[Observation],
) -> Reading {
    let program = Reading {
        mode,
        observation: program,
        version,
    };
    let models: Vec<Reading> = models
        .iter()
        .map(|observation| Reading::new(mode, *observation))
        .collect();
    Reading::worst_of_parts(mode, &program, &models)
}

/// A local AI act that did not complete: one closed failure category, or an engine error
/// whose category [`LocalAiError::category`] decides.
#[derive(Debug)]
pub enum LocalAiError {
    Failed(FailureCategory),
    /// The server did not come up. Its category is always `program_not_running`; the
    /// cause is for logs and tests, and no surface words it.
    ServerStart(ServerStartFailure),
    Engine(Error),
}

impl LocalAiError {
    /// The closed category a surface words this failure with.
    pub fn category(&self) -> FailureCategory {
        match self {
            Self::Failed(category) => *category,
            Self::ServerStart(_) => FailureCategory::ProgramNotRunning,
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
            Self::ServerStart(cause) => write!(
                f,
                "local AI failed: {}: {cause}",
                FailureCategory::ProgramNotRunning
            ),
            Self::Engine(error) => write!(f, "local AI failed: {error}"),
        }
    }
}

impl std::error::Error for LocalAiError {}

/// What a start of the local AI server was doing when it failed, and how. Locale-neutral
/// facts for a diagnostic report or a test; a surface shows the category alone.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ServerStartFailure {
    /// The operating system refused the server's process group, its creation or its
    /// containment, so nothing ran.
    Launch {
        step: LaunchStep,
        kind: io::ErrorKind,
    },
    /// The program's standard error could not be read for its announcement.
    LogUnreadable,
    /// The program's standard error closed before it announced that it listens. The
    /// status is its exit status when it had already ended by then.
    Closed { exit: Option<ExitStatus> },
    /// The program announced nothing within the start budget.
    Silent { budget: Duration },
    /// The program announced it listens and was then asked its version.
    Version(VersionFailure),
}

/// The step of launching the server that the operating system refused.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LaunchStep {
    /// Opening the process group the server is created in.
    OpenGroup,
    /// Creating the process.
    Create,
    /// Containing the created process.
    Contain,
}

/// How the version question put to a server that announced itself went wrong.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum VersionFailure {
    /// The request itself failed, with the engine's account of it.
    Unreachable(String),
    /// The server answered another HTTP status.
    Status(u16),
    /// The answer was not a version document.
    Unreadable,
    /// The server runs another version than the pinned one.
    Different { found: String },
}

impl fmt::Display for ServerStartFailure {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Launch { step, kind } => write!(f, "{step} failed: {kind}"),
            Self::LogUnreadable => f.write_str("its standard error could not be read"),
            Self::Closed { exit: Some(exit) } => {
                write!(f, "it ended without announcing that it listens ({exit})")
            }
            Self::Closed { exit: None } => {
                f.write_str("its standard error closed before it announced that it listens")
            }
            Self::Silent { budget } => write!(
                f,
                "it announced nothing within the {}s start budget",
                budget.as_secs()
            ),
            Self::Version(failure) => write!(f, "its version could not be confirmed: {failure}"),
        }
    }
}

impl fmt::Display for LaunchStep {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::OpenGroup => "opening its process group",
            Self::Create => "creating its process",
            Self::Contain => "containing its process",
        })
    }
}

impl fmt::Display for VersionFailure {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Unreachable(account) => write!(f, "the request failed ({account})"),
            Self::Status(status) => write!(f, "it answered status {status}"),
            Self::Unreadable => f.write_str("its answer was not a version"),
            Self::Different { found } => write!(f, "it reports version {found}"),
        }
    }
}
