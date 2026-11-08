use cadrumo_application::diagnostics::service::AgentRefusal as Refusal;
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use serde::Serialize;
use std::future::Future;
use std::pin::Pin;
use std::process::Command;
use std::sync::Arc;
use zeroize::Zeroizing;

pub(super) fn service_refusal(code: &str) -> Refusal {
    match code {
        "signed_out" => Refusal::SignedOut,
        "credentials_unavailable" | "credentials_invalid" => Refusal::ProviderCredentialMissing,
        "agent_incompatible" | "stores_newer" => Refusal::ServiceIncompatible,
        _ => Refusal::from_launcher(code),
    }
}

/// What the service answered a start request.
#[derive(Debug, PartialEq, Eq)]
pub(super) enum StartReply {
    Starting,
    /// Other tree work holds the service; the agent it serves is unchanged.
    Busy,
    Refused(Refusal),
}

pub(super) fn start_reply(reply: &serde_json::Value) -> Result<StartReply> {
    match (reply["kind"].as_str(), reply["code"].as_str()) {
        (Some("starting"), _) => Ok(StartReply::Starting),
        (Some("refused"), Some("busy")) => Ok(StartReply::Busy),
        (Some("refused"), code) => Ok(StartReply::Refused(service_refusal(
            code.unwrap_or("service_failed"),
        ))),
        _ => Err(ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
            .with_reason("agent_start_reply_unexpected")),
    }
}

/// Where the agent service of the signed-in profile is.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "state", rename_all = "snake_case")]
pub enum State {
    Stopped,
    Starting,
    Ready { agent_version: String },
    Refused { code: Refusal },
}

/// The published status: its state, and the lane it runs on.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Status {
    #[serde(flatten)]
    pub state: State,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub lane: Option<&'static str>,
}

/// What the sign-in status allows, read from one observation.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Allowed {
    /// Serve the profile with this label.
    Serve(String),
    /// A local sign-in change fences authority until its fresh observation.
    Pending,
    Refuse(Refusal),
}

/// One sign-in observation, as the supervisor reads it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Observation {
    pub supported: bool,
    pub present: bool,
    pub runtime_available: bool,
    pub refused: bool,
    pub active_profile: Option<String>,
}

/// Anything but a present sign-in on a working runtime with a selected
/// profile stops the agent. A failed read is unknown, and unknown stops it.
pub fn allowed(observed: &Result<Observation>) -> Allowed {
    if let Err(error) = observed
        && error.code == ErrorCode::SessionUnavailable
        && error.reason.as_deref() == Some("sign_in_mutation_in_progress")
    {
        return Allowed::Pending;
    }
    let Ok(observed) = observed else {
        return Allowed::Refuse(Refusal::RuntimeUnavailable);
    };
    if !observed.supported {
        return Allowed::Refuse(Refusal::ServiceAbsent);
    }
    if !observed.runtime_available || observed.refused {
        return Allowed::Refuse(Refusal::RuntimeUnavailable);
    }
    match (&observed.active_profile, observed.present) {
        (Some(profile), true) => Allowed::Serve(profile.clone()),
        _ => Allowed::Refuse(Refusal::SignedOut),
    }
}

pub type Observe =
    Arc<dyn Fn() -> Pin<Box<dyn Future<Output = Result<Observation>> + Send>> + Send + Sync>;

/// Resolves at the next sign-in observation after it is called; supervision
/// looks again then, and never on a timer of its own.
pub type Changed = Arc<dyn Fn() -> Pin<Box<dyn Future<Output = ()> + Send>> + Send + Sync>;

/// Builds the command for the profile, given the bearer minted for it.
pub type Launch = Arc<dyn Fn(&str, &str) -> Result<Prepared> + Send + Sync>;

/// What one start runs.
pub struct Prepared {
    pub command: Command,
    pub person: Option<super::super::person::HeldPerson>,
    /// The local engine a profile that chose none runs, as the package decides it.
    pub local_engine_default: cadrumo_application::provisioning::local_ai::LocalEngine,
}

/// How the gateway of the running launcher is reached. The bearer goes
/// nowhere but to that loopback gateway.
#[derive(Clone)]
pub struct Gateway {
    pub port: u16,
    pub bearer: Arc<Zeroizing<String>>,
    /// The profile's agent workspace the launcher reported.
    pub workspace_root: String,
    /// Which launcher reported it; a later one is another gateway.
    pub generation: u64,
    /// A controller can replace its gateway without replacing the launcher.
    /// Retained observations must not authorize that replacement, even if its
    /// port is reused.
    pub(super) instance: Arc<()>,
}

impl Gateway {
    pub fn same_instance(&self, other: &Self) -> bool {
        Arc::ptr_eq(&self.instance, &other.instance)
    }
}

#[cfg(test)]
mod tests;
