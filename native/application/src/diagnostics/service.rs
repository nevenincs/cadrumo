//! Closed operational facts; credentials, paths and protocol text are excluded.
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
}

impl AgentRefusal {
    pub fn from_launcher(code: &str) -> Self {
        match code {
            "agent_service_absent" => Self::ServiceAbsent,
            "agent_service_incompatible" => Self::ServiceIncompatible,
            "agent_signed_out" => Self::SignedOut,
            "agent_runtime_unavailable" => Self::RuntimeUnavailable,
            "agent_provider_credential_missing" => Self::ProviderCredentialMissing,
            _ => Self::ServiceFailed,
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AgentStopCause {
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
    AgentProtocolRefused {},
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
}
