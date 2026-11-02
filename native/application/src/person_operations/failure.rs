use super::protocol::RUNTIME_REFUSAL_CODES;
use crate::runtime_client::refusal::Refusal;

/// Why a relay action or a language read or set did not answer.
#[derive(Debug)]
pub enum RelayFailure {
    /// The relay's closed refusal; the session keeps holding. A busy subject
    /// names the operation that holds it. The code `unavailable` is never a
    /// decision: the runtime, its transport or a reply failed, so a mutation
    /// it carried may have committed.
    Refused {
        code: String,
        holder_operation_id: Option<String>,
    },
    /// A malformed request: the session answers `invalid` and ends.
    Invalid,
    /// The runtime, its transport or a reply failed: the session answers
    /// `unavailable` and ends. The refusal says which, for the log.
    Unavailable(Refusal),
}
/// A failure before it is answered: a closed refusal, the runtime's failure,
/// or a malformed request.
#[derive(Debug)]
pub(super) enum Failure {
    Refused {
        code: String,
        holder_operation_id: Option<String>,
    },
    Runtime(Refusal),
    Invalid,
}

pub(super) type Outcome<T> = Result<T, Failure>;

impl Failure {
    pub(super) fn code(code: &str) -> Self {
        Self::Refused {
            code: code.to_owned(),
            holder_operation_id: None,
        }
    }

    pub(super) fn frame() -> Self {
        Self::Runtime(Refusal::InvalidFrame)
    }

    /// A relay answers every runtime failure with its closed `unavailable`.
    pub(super) fn relayed(self) -> RelayFailure {
        match self {
            Self::Refused {
                code,
                holder_operation_id,
            } => RelayFailure::Refused {
                code,
                holder_operation_id,
            },
            Self::Runtime(_) => RelayFailure::Refused {
                code: "unavailable".to_owned(),
                holder_operation_id: None,
            },
            Self::Invalid => RelayFailure::Invalid,
        }
    }

    /// A language read or set has no closed refusal: any failure ends the session.
    pub(super) fn held(self) -> RelayFailure {
        match self {
            Self::Refused {
                code,
                holder_operation_id,
            } => RelayFailure::Unavailable(Refusal::Denied {
                code,
                sign_in: None,
                holder_operation_id,
                recovery_remaining_seconds: None,
            }),
            Self::Runtime(refusal) => RelayFailure::Unavailable(refusal),
            Self::Invalid => RelayFailure::Invalid,
        }
    }
}

impl From<Refusal> for Failure {
    /// A runtime decision is a closed refusal. A change a lost worker was
    /// serving is not one: it may have committed, so it stays the runtime's
    /// failure and a relay answers it with `unavailable`.
    fn from(refusal: Refusal) -> Self {
        match refusal {
            Refusal::Denied {
                code,
                holder_operation_id,
                ..
            } if !RUNTIME_REFUSAL_CODES.contains(&code.as_str()) => Self::Refused {
                code,
                holder_operation_id,
            },
            other => Self::Runtime(other),
        }
    }
}
