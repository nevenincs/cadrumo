//! The refusal vocabulary every runtime connection shares, whatever carries its bytes.

use std::io;

/// Why a connection could not be made.
#[derive(Debug)]
pub enum ConnectRefusal {
    /// No endpoint of that name exists, or none became free in time.
    NotReady,
    /// The endpoint's namespace or entry is not the private one the runtime publishes.
    EndpointUntrusted,
    /// The endpoint's server is not a live process of the expected account.
    PeerUntrusted,
    /// The deadline passed before the endpoint answered.
    Deadline,
    Cancelled,
    Failed(io::Error),
}

impl std::fmt::Display for ConnectRefusal {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NotReady => formatter.write_str("runtime endpoint not ready"),
            Self::EndpointUntrusted => formatter.write_str("runtime endpoint untrusted"),
            Self::PeerUntrusted => formatter.write_str("runtime peer untrusted"),
            Self::Deadline => formatter.write_str("runtime connect deadline exceeded"),
            Self::Cancelled => formatter.write_str("runtime connect cancelled"),
            Self::Failed(error) => write!(formatter, "runtime connect failed: {error}"),
        }
    }
}

impl std::error::Error for ConnectRefusal {}
