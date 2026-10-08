//! Closed, versioned manager requests. Responses acknowledge only work actually done.
//!
//! This transport grants no runtime/profile authority. Readiness is refused until
//! cutover supplies its held, designated child; a PID in a request is never evidence.

use serde::{Deserialize, Serialize};
use std::io;

#[cfg(windows)]
pub mod windows;

pub const MAXIMUM_FRAME_BYTES: usize = 4096;

#[derive(Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(tag = "request", rename_all = "snake_case", deny_unknown_fields)]
pub enum Request {
    Reveal {
        schema: u32,
    },
    Retry {
        schema: u32,
    },
    SuccessorReady {
        schema: u32,
        runtime_pid: u32,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        report: Option<crate::cutover::Report>,
    },
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Outcome {
    RevealQueued,
    DesignationAccepted,
    SuccessorObserved,
    SuccessorReady,
    ReEvaluated,
    SurfaceUnavailable,
    DesignationRequired,
    Unavailable,
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Response {
    pub schema: u32,
    pub outcome: Outcome,
}

pub fn decode(bytes: &[u8]) -> io::Result<Request> {
    if bytes.is_empty() || bytes.len() > MAXIMUM_FRAME_BYTES {
        return Err(io::ErrorKind::InvalidData.into());
    }
    let request: Request = serde_json::from_slice(bytes).map_err(io::Error::other)?;
    let schema = match request {
        Request::Reveal { schema }
        | Request::Retry { schema }
        | Request::SuccessorReady { schema, .. } => schema,
    };
    if schema != 1
        || matches!(&request, Request::SuccessorReady { runtime_pid, report, .. } if report.as_ref().map_or(*runtime_pid == 0, |report| !report.valid(*runtime_pid)))
    {
        return Err(io::ErrorKind::InvalidData.into());
    }
    Ok(request)
}

/// Resolve only supported effects. PIDs do not admit successor readiness.
pub fn respond(request: Request, retry: impl FnOnce() -> io::Result<()>) -> Response {
    Response {
        schema: 1,
        outcome: match request {
            Request::Reveal { .. } => Outcome::SurfaceUnavailable,
            Request::Retry { .. } => match retry() {
                Ok(()) => Outcome::ReEvaluated,
                Err(_) => Outcome::Unavailable,
            },
            Request::SuccessorReady { .. } => Outcome::DesignationRequired,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn grammar_refuses_extra_fields_unknown_requests_and_schema() {
        for bytes in [
            br#"{"schema":1,"request":"stop"}"#.as_slice(),
            br#"{"schema":2,"request":"retry"}"#,
            br#"{"schema":1,"request":"reveal","command":"anything"}"#,
            br#"{"schema":1,"schema":1,"request":"retry"}"#,
            br#"{"schema":1,"request":"successor_ready","runtime_pid":0}"#,
            br#"{"schema":1,"request":"retry"}{}"#,
        ] {
            assert!(decode(bytes).is_err());
        }
        assert!(decode(&vec![b' '; MAXIMUM_FRAME_BYTES + 1]).is_err());
        assert_eq!(
            decode(br#"{"schema":1,"request":"retry"}"#).unwrap(),
            Request::Retry { schema: 1 }
        );
    }

    #[test]
    fn responses_never_claim_readiness_or_unimplemented_surface() {
        let unexpected = || panic!("only retry may re-evaluate");
        assert_eq!(
            respond(Request::Reveal { schema: 1 }, unexpected).outcome,
            Outcome::SurfaceUnavailable
        );
        assert_eq!(
            respond(
                Request::SuccessorReady {
                    schema: 1,
                    runtime_pid: 42,
                    report: None
                },
                unexpected
            )
            .outcome,
            Outcome::DesignationRequired
        );
        assert_eq!(
            respond(Request::Retry { schema: 1 }, || Ok(())).outcome,
            Outcome::ReEvaluated
        );
        assert_eq!(
            respond(Request::Retry { schema: 1 }, || Err(
                io::ErrorKind::PermissionDenied.into()
            ))
            .outcome,
            Outcome::Unavailable
        );
    }
}
