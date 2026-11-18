//! Closed operational facts; credentials, paths and protocol text are excluded.
use crate::provisioning::items::ItemId;
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum LogLevel {
    Debug,
    #[default]
    Info,
    Warning,
    Error,
    Critical,
}

impl LogLevel {
    pub fn operator(value: &str) -> Option<Self> {
        match value.trim().to_ascii_uppercase().as_str() {
            "" | "DEFAULT" | "VERBOSE" => Some(Self::Info),
            "QUIET" => Some(Self::Error),
            name => Self::parse(name),
        }
    }
    pub fn parse(name: &str) -> Option<Self> {
        Some(match name {
            "DEBUG" => Self::Debug,
            "INFO" => Self::Info,
            "WARNING" => Self::Warning,
            "ERROR" => Self::Error,
            "CRITICAL" => Self::Critical,
            _ => return None,
        })
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub enum AgentRefusal {
    #[serde(rename = "agent_platform_unsupported")]
    UnsupportedPlatform,
    #[serde(rename = "agent_service_absent")]
    ServiceAbsent,
    #[serde(rename = "agent_service_incompatible")]
    ServiceIncompatible,
    #[serde(rename = "agent_signed_out")]
    SignedOut,
    #[serde(rename = "agent_runtime_unavailable")]
    RuntimeUnavailable,
    #[serde(rename = "agent_provider_credential_missing")]
    ProviderCredentialMissing,
    #[serde(rename = "agent_service_failed")]
    ServiceFailed,
    #[serde(rename = "agent_timeout")]
    Timeout,
}

impl AgentRefusal {
    pub fn from_launcher(code: &str) -> Self {
        match code {
            "agent_platform_unsupported" => Self::UnsupportedPlatform,
            "agent_service_absent" => Self::ServiceAbsent,
            "agent_service_incompatible" => Self::ServiceIncompatible,
            "agent_signed_out" => Self::SignedOut,
            "agent_runtime_unavailable" => Self::RuntimeUnavailable,
            "agent_provider_credential_missing" => Self::ProviderCredentialMissing,
            "agent_timeout" => Self::Timeout,
            _ => Self::ServiceFailed,
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AgentStopCause {
    /// The person signed out, or the runtime retired their session as signed out.
    SignedOut,
    /// No person session is held yet, and none is signed out.
    SignInUnavailable,
    RuntimeUnavailable,
    ProfileChanged,
    WindowClosing,
    LauncherRefused,
    LauncherEnded,
    ProtocolRefused,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum InstallationScope {
    User,
    Machine,
}

/// A desktop feature whose work could not start.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RefusedFeature {
    SedeView,
}

/// One of the three reads the setup admission check makes of the agent service before a
/// local model download. Named for the service's administration action, never a payload.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AdmissionRead {
    /// The lanes the profile lists, with the kind of access each takes.
    ProviderLanes,
    /// cadrumo-agent's model catalogue.
    Catalog,
    /// The models the person added to their lanes' lists.
    LocalModels,
}

/// How an admission read ended, whatever it was for.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AdmissionReadOutcome {
    /// The service replied and the reply was usable.
    Answered,
    /// The service did not answer, or refused for a reason other than a sign-out.
    Unanswered,
    /// Nobody is signed in, or the service refused with a code the person can act on.
    Refused,
    /// The service replied, but the reply is outside its contract.
    Invalid,
}

/// Why the window presented its stored sign-in again to hold a person session.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PersonRestoreCause {
    /// The window held no person session for the profile.
    NoHeldSession,
    /// The session the window held had ended, or was another profile's.
    HeldSessionEnded,
}

/// How presenting the stored sign-in ended.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PersonRestoreOutcome {
    /// The runtime admitted a person session from the stored sign-in.
    Restored,
    /// The stored sign-in was refused for good, such as after an idle lapse;
    /// the person signs in again.
    Refused,
    /// The attempt did not settle, and may be tried again.
    Unavailable,
}

/// Why a feature could not start.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum FeatureRefusal {
    /// A component the feature needs is not ready; its setup is offered.
    ComponentNotReady,
    /// The runtime refused the feature's operation for another reason.
    Refused,
}

/// Where following an operation ended.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SettleEnd {
    /// The operation reached its terminal state and its outcome was read.
    Settled,
    /// The operation waits on the person, at a review.
    Person,
    /// Observing it, or reading its outcome, failed.
    Failed,
    /// No outcome was observed within the window's bound.
    Unobserved,
}

/// What woke the last observe of a followed operation.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SettleWake {
    /// None: the first observe, right after submitting or answering.
    First,
    /// The runtime's change cue, or a cue stream that fell behind.
    Cue,
    /// The recheck bound, which ran out with no cue.
    Recheck,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(
    tag = "event",
    rename_all = "snake_case",
    rename_all_fields = "camelCase",
    deny_unknown_fields
)]
pub enum ServiceFact {
    AgentStarting {
        generation: u64,
    },
    /// A start's host side: building the service command, launching its
    /// process, and acquiring the person session, which runs alongside the
    /// launch and the service's own start.
    AgentStartupTiming {
        generation: u64,
        command_ms: u64,
        spawn_ms: u64,
        /// The parts of `spawn_ms`: waiting for a blocking thread to start the
        /// process, waiting for the host's one process-creation lock, creating
        /// the process, and containing it (its job, adoption and output readers).
        queue_ms: u64,
        creation_lock_ms: u64,
        create_ms: u64,
        contain_ms: u64,
        person_ms: u64,
    },
    /// How long the runtime's admission of the service's person connection
    /// took, from the service's ready report until its administration could
    /// answer, or until it was refused.
    AgentAdmissionTiming {
        generation: u64,
        admitted: bool,
        elapsed_ms: u64,
    },
    AgentReady {
        generation: u64,
        gateway_port: u16,
    },
    AgentRefused {
        reason: AgentRefusal,
    },
    AgentStopping {
        cause: AgentStopCause,
    },
    AgentStopped {
        cause: AgentStopCause,
    },
    AgentRetryScheduled {
        delay_ms: u64,
    },
    AgentRetryExhausted {
        attempts: u32,
    },
    AgentProtocolRefused {},
    /// How long one setup admission read took, from the request to its settled outcome.
    SetupAdmissionRead {
        read: AdmissionRead,
        outcome: AdmissionReadOutcome,
        elapsed_ms: u64,
    },
    /// How following one operation the window submitted or answered went: where it
    /// ended, what woke the observe that ended it, how many observes it took and how
    /// many of their waits a change cue ended, their time, the time to read its
    /// outcome (a settled operation's result document), and the whole wait.
    OperationSettle {
        end: SettleEnd,
        wake: SettleWake,
        observes: u32,
        cues: u32,
        observe_ms: u64,
        outcome_ms: u64,
        elapsed_ms: u64,
    },
    /// The window presented its stored sign-in to hold a person session.
    PersonRestore {
        cause: PersonRestoreCause,
        outcome: PersonRestoreOutcome,
    },
    ManagerInstallationStarted {
        scope: InstallationScope,
    },
    ManagerInstallationCompleted {
        scope: InstallationScope,
    },
    EnvironmentResolved {
        package_abi: u32,
        log_level: LogLevel,
        log_level_overridden: bool,
    },
    /// `item` is the component a `component_not_ready` refusal names.
    FeatureRefused {
        feature: RefusedFeature,
        refusal: FeatureRefusal,
        item: Option<ItemId>,
    },
}
