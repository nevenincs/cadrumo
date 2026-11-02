use cadrumo_platform::runtime_connect::ConnectRefusal;
use serde_json::Value;
use std::io;

/// The denial of a session a lost worker suspended: it grants nothing until a
/// fresh proof on the connection that holds it rebinds it.
pub const CUSTODY_RECOVERING: &str = "custody_recovering";

/// Why a connection or exchange did not answer. `code` spells it as the
/// runtime's Python clients do, so one refusal vocabulary reaches a window.
#[derive(Debug)]
pub enum Refusal {
    Unavailable,
    EndpointNotReady,
    EndpointUntrusted,
    PeerUntrusted,
    VersionMismatch,
    RootMismatch,
    InvalidFrame,
    ConnectionClosed,
    Timeout,
    /// The runtime answered with its typed refusal: an access denial code,
    /// for a sign-in the reason it was refused, for a busy subject the
    /// operation that holds it, and for a suspended session the whole seconds
    /// left in its recovery window.
    Denied {
        code: String,
        sign_in: Option<Value>,
        holder_operation_id: Option<String>,
        recovery_remaining_seconds: Option<u64>,
    },
    /// The worker was lost while it served a change this request carried, and
    /// the runtime now keeps the session suspended. The change may have taken
    /// effect, so its outcome is unknown and the request is not to be repeated
    /// as it stands: the operation it named, when it named one, says what
    /// happened once the session is back.
    Unsettled {
        operation_id: Option<String>,
        recovery_remaining_seconds: Option<u64>,
    },
    Io(io::Error),
}

impl From<io::Error> for Refusal {
    fn from(error: io::Error) -> Self {
        match error.kind() {
            io::ErrorKind::ConnectionAborted
            | io::ErrorKind::UnexpectedEof
            | io::ErrorKind::BrokenPipe
            | io::ErrorKind::NotConnected => Self::ConnectionClosed,
            io::ErrorKind::TimedOut => Self::Timeout,
            _ => Self::Io(error),
        }
    }
}

impl From<ConnectRefusal> for Refusal {
    fn from(refusal: ConnectRefusal) -> Self {
        match refusal {
            ConnectRefusal::NotReady => Self::EndpointNotReady,
            ConnectRefusal::EndpointUntrusted => Self::EndpointUntrusted,
            ConnectRefusal::PeerUntrusted => Self::PeerUntrusted,
            ConnectRefusal::Deadline => Self::Timeout,
            ConnectRefusal::Cancelled => Self::ConnectionClosed,
            ConnectRefusal::Failed(error) => Self::Io(error),
        }
    }
}

impl Refusal {
    /// The runtime's refusal `code`, with no sign-in reason or holder.
    pub fn denied(code: impl Into<String>) -> Self {
        Self::Denied {
            code: code.into(),
            sign_in: None,
            holder_operation_id: None,
            recovery_remaining_seconds: None,
        }
    }

    /// Whether the session waits for a fresh proof after the profile's worker was lost.
    pub fn is_custody_recovering(&self) -> bool {
        matches!(self, Self::Denied { code, .. } if code == CUSTODY_RECOVERING)
            || matches!(self, Self::Unsettled { .. })
    }

    /// Whether a change the request carried may have taken effect although it was refused.
    pub fn is_unsettled(&self) -> bool {
        matches!(self, Self::Unsettled { .. })
    }

    /// The operation whose change has an unknown effect, when the refused request named one.
    pub fn unsettled_operation_id(&self) -> Option<&str> {
        match self {
            Self::Unsettled { operation_id, .. } => operation_id.as_deref(),
            _ => None,
        }
    }

    /// The whole seconds left in a suspended session's recovery window, when the runtime said.
    pub fn recovery_remaining_seconds(&self) -> Option<u64> {
        match self {
            Self::Denied {
                recovery_remaining_seconds,
                ..
            }
            | Self::Unsettled {
                recovery_remaining_seconds,
                ..
            } => *recovery_remaining_seconds,
            _ => None,
        }
    }

    /// The operation that holds a refused request's subject, when the runtime named one.
    pub fn holder_operation_id(&self) -> Option<&str> {
        match self {
            Self::Denied {
                holder_operation_id,
                ..
            } => holder_operation_id.as_deref(),
            _ => None,
        }
    }

    /// The reason a sign-in was refused, when the runtime gave one: a receipt
    /// refusal reason, `throttled` or `credential_rejected`.
    pub fn sign_in_reason(&self) -> Option<&str> {
        match self {
            Self::Denied {
                sign_in: Some(sign_in),
                ..
            } => sign_in.get("reason").and_then(Value::as_str),
            _ => None,
        }
    }

    /// How long a throttled sign-in must wait, when the runtime said.
    pub fn remaining_seconds(&self) -> Option<u64> {
        match self {
            Self::Denied {
                sign_in: Some(sign_in),
                ..
            } => sign_in.get("remaining_seconds").and_then(Value::as_u64),
            _ => None,
        }
    }

    pub fn code(&self) -> &str {
        match self {
            Self::Unavailable | Self::Io(_) => "runtime_unavailable",
            Self::EndpointNotReady => "runtime_endpoint_not_ready",
            Self::EndpointUntrusted => "runtime_endpoint_untrusted",
            Self::PeerUntrusted => "runtime_peer_untrusted",
            Self::VersionMismatch => "runtime_version_mismatch",
            Self::RootMismatch => "runtime_root_mismatch",
            Self::InvalidFrame => "runtime_invalid_frame",
            Self::ConnectionClosed => "runtime_connection_closed",
            Self::Timeout => "runtime_timeout",
            Self::Denied { code, .. } => code,
            Self::Unsettled { .. } => CUSTODY_RECOVERING,
        }
    }
}
