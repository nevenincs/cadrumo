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
