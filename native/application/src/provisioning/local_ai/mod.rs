//! The local AI item: the program that runs models, installed from its pinned portable
//! archive, the one server run from it on the installation's fixed loopback address, and
//! the model the person selected for each local role, fetched by the engine itself.
//!
//! Two engines can serve the local models, and [`LocalEngine`] names them. `program`
//! installs, checks, starts, stops and removes the Ollama program, records where it is,
//! and reports a copy installed outside Cadrumo without touching it. `llama_server` runs
//! the llama-server the package carries, which nothing installs. `supervision` is the
//! runtime manager's part: it keeps the selected engine's server running while its
//! program is set up. `lease` keeps that server and a change of the program apart across
//! processes.
//! `models` fetches each selected model into the store and checks it on the running server.
//! `registry` fetches a model from its registry into the models folder without one, and
//! `huggingface` fetches a model's declared files from Hugging Face into the same store.
//! `hardware` decides whether this computer can hold a model of a given size. `loopback` is the
//! client for the program's own API on this computer. [`reading`] folds the parts into
//! the item's one reading.

pub mod hardware;
pub mod huggingface;
pub mod lease;
pub mod llama_server;
pub mod loopback;
pub mod models;
pub mod program;
pub mod registry;
pub mod supervision;

#[cfg(test)]
pub(crate) mod fake_llamacpp;
#[cfg(test)]
pub(crate) mod fake_ollama;

use super::{
    failure::FailureCategory,
    state::{CheckMode, Observation, Reading},
};
use crate::error::Error;
use loopback::{ExchangeFailure, ExchangePhase};
use serde::{Deserialize, Serialize};
use std::{fmt, io, path::Path, process::ExitStatus, time::Duration};

/// The engine that serves the local models, and so the one local AI server the runtime
/// manager runs. A person who has chosen none is served by `package_default_engine`:
/// the llama-server where the package carries it, otherwise Ollama. Stored as `ollama` or
/// `llamacpp`.
#[derive(Clone, Copy, Debug, Deserialize, Eq, Hash, PartialEq, Serialize)]
pub enum LocalEngine {
    /// The Ollama program the engine downloads on the person's approval.
    #[serde(rename = "ollama")]
    Ollama,
    /// The llama-server program the package carries.
    #[serde(rename = "llamacpp")]
    LlamaCpp,
}

/// The engine of a person who has chosen none, from what the package at `package_root`
/// carries: llama.cpp exactly when the package's `llama_server` folder holds the
/// llama-server program, since it needs no download, and Ollama otherwise. This is the only
/// default engine. A chosen engine is kept whatever the package carries: llama.cpp chosen on
/// a package without the llama-server is refused as not packaged, never served by Ollama.
#[cfg(feature = "platform")]
pub fn package_default_engine(package_root: &Path) -> LocalEngine {
    llama_server_folder_default(&super::installation::package_path(
        package_root,
        cadrumo_platform::LLAMA_SERVER,
    ))
}

/// `package_default_engine` for the package whose `llama_server` folder is
/// `llama_server_folder`, for a caller that holds that folder rather than the package root.
pub(crate) fn llama_server_folder_default(llama_server_folder: &Path) -> LocalEngine {
    if llama_server::carried(llama_server_folder) {
        LocalEngine::LlamaCpp
    } else {
        LocalEngine::Ollama
    }
}

/// Where the local engine runs a model: the device policy of its server's launch. The
/// same model files serve either, so no placement has a model list of its own. Stored as
/// `auto` or `cpu_only`.
#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, Hash, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Placement {
    /// The engine offloads layers to a device when one is present and the load fits.
    #[default]
    Auto,
    /// The engine keeps every layer on the processor.
    CpuOnly,
}

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
    /// The server did not come up or did not answer. Its category is always
    /// `program_not_running`; the cause is for logs and tests, and no surface words it.
    NotRunning(NotRunningCause),
    Engine(Error),
}

/// Why the local AI reads `program_not_running`: which start, wait or request ran out or
/// broke. Locale-neutral facts for a diagnostic report or a test, so a host too busy to
/// answer within a budget is not read as a program that is missing.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum NotRunningCause {
    /// A start of the server failed.
    Start(ServerStartFailure),
    /// No server was running by the end of the setup's wait for the manager to start it.
    /// `latest_start` is the kind of the manager's latest start when that start failed,
    /// as its start-failure record keeps it; absent when no start has failed since the
    /// last one that succeeded.
    NoServerWithin {
        budget: Duration,
        latest_start: Option<StartFailureKind>,
    },
    /// A request to the running server failed before it answered.
    Request {
        call: ServerCall,
        failure: ExchangeFailure,
    },
    /// The running server answered the model list with an unexpected HTTP status.
    ListStatus { status: u16 },
}

/// The request to the running server that a [`NotRunningCause`] names.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ServerCall {
    /// Listing the models the server holds.
    ListModels,
    /// Generating one token to check a model loads.
    Generate,
}

impl LocalAiError {
    /// The closed category a surface words this failure with.
    pub fn category(&self) -> FailureCategory {
        match self {
            Self::Failed(category) => *category,
            Self::NotRunning(_) => FailureCategory::ProgramNotRunning,
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
            Self::NotRunning(cause) => write!(
                f,
                "local AI failed: {}: {cause}",
                FailureCategory::ProgramNotRunning
            ),
            Self::Engine(error) => write!(f, "local AI failed: {error}"),
        }
    }
}

impl std::error::Error for LocalAiError {}

/// The kind of a failed server start without its detail: what the start-failure record
/// keeps for an engine that waits in another process than the one that started.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum StartFailureKind {
    Launch,
    LogUnreadable,
    Closed,
    Silent,
    NotReady,
    VersionUnconfirmed,
}

impl StartFailureKind {
    const ALL: [Self; 6] = [
        Self::Launch,
        Self::LogUnreadable,
        Self::Closed,
        Self::Silent,
        Self::NotReady,
        Self::VersionUnconfirmed,
    ];

    /// A static identifier for this kind, as a diagnostic record keeps it.
    pub fn reason(self) -> &'static str {
        match self {
            Self::Launch => "server_launch_failed",
            Self::LogUnreadable => "server_log_unreadable",
            Self::Closed => "server_closed_before_listening",
            Self::Silent => "server_start_budget_expired",
            Self::NotReady => "server_not_ready",
            Self::VersionUnconfirmed => "server_version_unconfirmed",
        }
    }

    /// The kind a stored identifier names, when this build knows it.
    pub fn from_reason(reason: &str) -> Option<Self> {
        Self::ALL.into_iter().find(|kind| kind.reason() == reason)
    }
}

impl ServerStartFailure {
    /// This failure's kind, without its detail.
    pub fn kind(&self) -> StartFailureKind {
        match self {
            Self::Launch { .. } => StartFailureKind::Launch,
            Self::LogUnreadable => StartFailureKind::LogUnreadable,
            Self::Closed { .. } => StartFailureKind::Closed,
            Self::Silent { .. } => StartFailureKind::Silent,
            Self::NotReady { .. } => StartFailureKind::NotReady,
            Self::Version(_) => StartFailureKind::VersionUnconfirmed,
        }
    }

    /// What the last version question got, for a start whose version was not
    /// confirmed; none for any other kind.
    pub fn last_check(&self) -> Option<String> {
        match self {
            Self::Version(failure) => Some(failure.check()),
            _ => None,
        }
    }
}

impl VersionFailure {
    /// What the version question got, without any value the server sent: `unreachable`,
    /// `status_` and the HTTP status, `unreadable`, or `different_version`.
    pub fn check(&self) -> String {
        match self {
            Self::Unreachable(_) => "unreachable".to_owned(),
            Self::Status(status) => format!("status_{status}"),
            Self::Unreadable => "unreadable".to_owned(),
            Self::Different { .. } => "different_version".to_owned(),
        }
    }
}

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
    /// The program announced that it listens and did not answer ready within the start
    /// budget. The status is its latest answer to the readiness question, absent when it
    /// never answered one.
    NotReady {
        budget: Duration,
        status: Option<u16>,
    },
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
            Self::NotReady {
                budget,
                status: Some(status),
            } => write!(
                f,
                "it was not ready within the {}s start budget (status {status})",
                budget.as_secs()
            ),
            Self::NotReady {
                budget,
                status: None,
            } => write!(
                f,
                "it did not answer ready within the {}s start budget",
                budget.as_secs()
            ),
            Self::Version(failure) => write!(f, "its version could not be confirmed: {failure}"),
        }
    }
}

impl NotRunningCause {
    /// A static identifier for this cause, as a diagnostic record keeps it.
    pub fn reason(&self) -> &'static str {
        match self {
            Self::Start(failure) => failure.kind().reason(),
            Self::NoServerWithin { .. } => "server_wait_expired",
            Self::Request { call, failure } => match (call, failure.phase) {
                (ServerCall::ListModels, ExchangePhase::Connect) => "model_list_connect_failed",
                (ServerCall::ListModels, ExchangePhase::Exchange) => "model_list_request_failed",
                (ServerCall::Generate, ExchangePhase::Connect) => "generate_connect_failed",
                (ServerCall::Generate, ExchangePhase::Exchange) => "generate_request_failed",
            },
            Self::ListStatus { .. } => "model_list_status_unexpected",
        }
    }

    /// The I/O error kind behind this cause, `TimedOut` when a request's bound ran out.
    pub fn io_kind(&self) -> Option<io::ErrorKind> {
        match self {
            Self::Start(ServerStartFailure::Launch { kind, .. }) => Some(*kind),
            Self::Request { failure, .. } => Some(failure.kind),
            _ => None,
        }
    }

    /// The kind of the failed start behind a wait that expired, when one was recorded.
    pub fn latest_start(&self) -> Option<StartFailureKind> {
        match self {
            Self::NoServerWithin { latest_start, .. } => *latest_start,
            _ => None,
        }
    }
}

impl fmt::Display for NotRunningCause {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Start(failure) => failure.fmt(f),
            Self::NoServerWithin {
                budget,
                latest_start,
            } => {
                write!(
                    f,
                    "no server was running within the {}s wait",
                    budget.as_secs()
                )?;
                match latest_start {
                    Some(kind) => write!(f, "; the latest start failed: {}", kind.reason()),
                    None => Ok(()),
                }
            }
            Self::Request { call, failure } => write!(
                f,
                "the {call} request failed while {}: {} (bound {}s)",
                match failure.phase {
                    ExchangePhase::Connect => "connecting",
                    ExchangePhase::Exchange => "exchanging",
                },
                failure.kind,
                failure.bound.as_secs()
            ),
            Self::ListStatus { status } => {
                write!(f, "the model list was answered with status {status}")
            }
        }
    }
}

impl fmt::Display for ServerCall {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::ListModels => "model list",
            Self::Generate => "generate",
        })
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
