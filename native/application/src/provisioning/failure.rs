use crate::value::HostName;
use serde::{Deserialize, Serialize};
use std::{fmt, io};

/// The closed failure categories. Each maps to one plain sentence and at most one action
/// in the surfaces' locale catalogues; a surface never shows the category itself.
#[derive(Clone, Copy, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum FailureCategory {
    Offline,
    HostUnreachable,
    ServerError,
    SecureConnectionFailed,
    BlockedByNetwork,
    DiskFull,
    NoPermission,
    DamagedDownload,
    NotEnoughMemory,
    MemoryBusy,
    ProgramMissing,
    ProgramNotRunning,
    Interrupted,
    NeedsSignIn,
    NotInThisBuild,
    Cancelled,
    Unexpected,
}

impl FailureCategory {
    pub const ALL: [Self; 17] = [
        Self::Offline,
        Self::HostUnreachable,
        Self::ServerError,
        Self::SecureConnectionFailed,
        Self::BlockedByNetwork,
        Self::DiskFull,
        Self::NoPermission,
        Self::DamagedDownload,
        Self::NotEnoughMemory,
        Self::MemoryBusy,
        Self::ProgramMissing,
        Self::ProgramNotRunning,
        Self::Interrupted,
        Self::NeedsSignIn,
        Self::NotInThisBuild,
        Self::Cancelled,
        Self::Unexpected,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Offline => "offline",
            Self::HostUnreachable => "host_unreachable",
            Self::ServerError => "server_error",
            Self::SecureConnectionFailed => "secure_connection_failed",
            Self::BlockedByNetwork => "blocked_by_network",
            Self::DiskFull => "disk_full",
            Self::NoPermission => "no_permission",
            Self::DamagedDownload => "damaged_download",
            Self::NotEnoughMemory => "not_enough_memory",
            Self::MemoryBusy => "memory_busy",
            Self::ProgramMissing => "program_missing",
            Self::ProgramNotRunning => "program_not_running",
            Self::Interrupted => "interrupted",
            Self::NeedsSignIn => "needs_sign_in",
            Self::NotInThisBuild => "not_in_this_build",
            Self::Cancelled => "cancelled",
            Self::Unexpected => "unexpected",
        }
    }

    /// Whether a failure of this category may ever be retried. Approval, disk, permission,
    /// integrity, hardware, contention, build, sign-in, cancellation, certificate and
    /// network-policy failures are final on their first occurrence.
    pub fn may_be_transient(self) -> bool {
        !matches!(
            self,
            Self::DiskFull
                | Self::NoPermission
                | Self::DamagedDownload
                | Self::NotEnoughMemory
                | Self::MemoryBusy
                | Self::NotInThisBuild
                | Self::NeedsSignIn
                | Self::Cancelled
                | Self::SecureConnectionFailed
                | Self::BlockedByNetwork
        )
    }
}

impl fmt::Display for FailureCategory {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// Where a network exchange stopped: resolving the name, connecting, the TLS handshake,
/// the proxy's tunnel, reading or writing on the open connection, or the HTTP status the
/// server answered with.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FailureStage {
    Resolve,
    Connect,
    Tls,
    Tunnel,
    Io,
    Status,
}

impl FailureStage {
    /// A static identifier for this stage, as a diagnostic record keeps it.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Resolve => "resolve",
            Self::Connect => "connect",
            Self::Tls => "tls",
            Self::Tunnel => "tunnel",
            Self::Io => "io",
            Self::Status => "status",
        }
    }
}

/// One classified transfer failure: its category, whether another attempt may help, and
/// the locale-neutral facts a surface or a diagnostic report may show. None of them is a
/// value of the transfer: the host is a name without a path or a query.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct TransferFailure {
    pub category: FailureCategory,
    pub transient: bool,
    /// The HTTP status that decided the failure, when one did.
    pub http_status: Option<u16>,
    /// How many attempts were made before the failure became final; 0 while undecided.
    pub attempts: u32,
    /// Where the network exchange stopped, when the failure came from one.
    pub stage: Option<FailureStage>,
    /// The kind of the I/O error that ended the exchange, when one did.
    pub io_kind: Option<io::ErrorKind>,
    /// The host of the hop the failure came from.
    pub host: Option<HostName>,
}

impl TransferFailure {
    /// A failure that another attempt may cure; a category that is never retried stays final.
    pub fn transient(category: FailureCategory) -> Self {
        Self {
            transient: category.may_be_transient(),
            ..Self::final_(category)
        }
    }

    pub fn final_(category: FailureCategory) -> Self {
        Self {
            category,
            transient: false,
            http_status: None,
            attempts: 0,
            stage: None,
            io_kind: None,
            host: None,
        }
    }

    pub fn with_status(mut self, status: u16) -> Self {
        self.http_status = Some(status);
        self
    }

    pub fn at_stage(mut self, stage: FailureStage) -> Self {
        self.stage = Some(stage);
        self
    }

    pub fn with_io_kind(mut self, kind: Option<io::ErrorKind>) -> Self {
        self.io_kind = kind;
        self
    }

    /// The failure as it came from `host`, unless an earlier hop already named its own.
    pub fn from_host(mut self, host: &HostName) -> Self {
        if self.host.is_none() {
            self.host = Some(host.clone());
        }
        self
    }

    /// Classifies an HTTP status a transfer received; `None` for a success or a redirect.
    /// A server that answers 429 or 5xx was reached and is having a problem of its own,
    /// which is not a host that cannot be reached.
    pub fn of_status(status: u16) -> Option<Self> {
        let failure = match status {
            0..400 => return None,
            429 | 500.. => Self::transient(FailureCategory::ServerError),
            403 | 407 => Self::final_(FailureCategory::BlockedByNetwork),
            _ => Self::final_(FailureCategory::Unexpected),
        };
        Some(failure.with_status(status).at_stage(FailureStage::Status))
    }
}

impl fmt::Display for TransferFailure {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.category.as_str())
    }
}

/// A transfer failure is the cause a diagnostic record keeps of a failed download, as its
/// value-free facts.
impl std::error::Error for TransferFailure {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn categories_spell_their_closed_codes() {
        for category in FailureCategory::ALL {
            assert_eq!(
                serde_json::to_value(category).unwrap(),
                serde_json::Value::String(category.as_str().into())
            );
        }
        assert_eq!(FailureCategory::ALL.len(), 17);
    }

    #[test]
    fn statuses_classify_as_the_retry_contract_says() {
        for status in [429, 500, 502, 503, 599] {
            let failure = TransferFailure::of_status(status).unwrap();
            assert_eq!(failure.category, FailureCategory::ServerError);
            assert!(failure.transient, "{status}");
            assert_eq!(
                (failure.http_status, failure.stage),
                (Some(status), Some(FailureStage::Status))
            );
        }
        for (status, category) in [
            (403, FailureCategory::BlockedByNetwork),
            (407, FailureCategory::BlockedByNetwork),
            (404, FailureCategory::Unexpected),
            (416, FailureCategory::Unexpected),
        ] {
            let failure = TransferFailure::of_status(status).unwrap();
            assert_eq!((failure.category, failure.transient), (category, false));
            assert_eq!(failure.http_status, Some(status));
        }
        assert_eq!(TransferFailure::of_status(200), None);
        assert_eq!(TransferFailure::of_status(302), None);
    }

    #[test]
    fn a_category_that_is_never_retried_cannot_be_made_transient() {
        for category in FailureCategory::ALL {
            assert_eq!(
                TransferFailure::transient(category).transient,
                category.may_be_transient()
            );
        }
        assert!(!TransferFailure::transient(FailureCategory::DamagedDownload).transient);
        assert!(TransferFailure::transient(FailureCategory::HostUnreachable).transient);
        assert!(TransferFailure::transient(FailureCategory::ServerError).transient);
    }
}
