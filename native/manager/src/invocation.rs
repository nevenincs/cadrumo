//! Closed manager activation intent, retained through native redispatch.

use crate::ipc::Request;
use std::{ffi::OsString, io};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Intent {
    Manual,
    SignIn,
    Retry,
}

impl Intent {
    pub fn argument(self) -> Option<&'static str> {
        match self {
            Self::Manual => None,
            Self::SignIn => Some("--sign-in"),
            Self::Retry => Some("--retry"),
        }
    }

    pub fn existing_request(self) -> Option<Request> {
        match self {
            Self::Manual => Some(Request::Reveal { schema: 1 }),
            Self::SignIn => None,
            Self::Retry => Some(Request::Retry { schema: 1 }),
        }
    }
}

#[derive(Debug, PartialEq, Eq)]
pub enum Invocation {
    Start { intent: Intent, breakaway: bool },
    Cutover(crate::cutover::Designation),
    Version,
    SupportsRetry,
}

impl Invocation {
    pub fn parse(arguments: &[OsString]) -> io::Result<Self> {
        let (arguments, breakaway) = match arguments {
            [flag, tail @ ..] if flag == "--breakaway-attempt" => (tail, true),
            _ => (arguments, false),
        };
        let intent = match arguments {
            [] => Intent::Manual,
            [flag] if flag == "--sign-in" => Intent::SignIn,
            [flag] if flag == "--retry" => Intent::Retry,
            [flag] if flag == "--version" && !breakaway => return Ok(Self::Version),
            [flag] if flag == "--supports-retry" && !breakaway => return Ok(Self::SupportsRetry),
            [flag, value] if flag == "--cutover" && !breakaway => {
                let designation =
                    value
                        .to_str()
                        .ok_or(io::ErrorKind::InvalidInput)
                        .and_then(|text| {
                            crate::cutover::Designation::parse(text)
                                .map_err(|_| io::ErrorKind::InvalidInput)
                        })?;
                return Ok(Self::Cutover(designation));
            }
            _ => return Err(io::ErrorKind::InvalidInput.into()),
        };
        Ok(Self::Start { intent, breakaway })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn redispatch_preserves_explicit_recovery_and_sign_in() {
        for intent in [Intent::Manual, Intent::SignIn, Intent::Retry] {
            for breakaway in [false, true] {
                let arguments: Vec<OsString> = breakaway
                    .then_some("--breakaway-attempt")
                    .into_iter()
                    .chain(intent.argument())
                    .map(OsString::from)
                    .collect();
                assert_eq!(
                    Invocation::parse(&arguments).unwrap(),
                    Invocation::Start { intent, breakaway }
                );
            }
        }
        assert_eq!(
            Intent::Manual.existing_request(),
            Some(Request::Reveal { schema: 1 })
        );
        assert_eq!(Intent::SignIn.existing_request(), None);
        assert_eq!(
            Intent::Retry.existing_request(),
            Some(Request::Retry { schema: 1 })
        );
    }

    #[test]
    fn ambiguous_or_combined_activation_is_refused() {
        for arguments in [
            vec!["--retry", "--sign-in"],
            vec!["--retry", "--retry"],
            vec!["--breakaway-attempt", "--breakaway-attempt"],
            vec!["--breakaway-attempt", "--version"],
            vec!["--breakaway-attempt", "--supports-retry"],
            vec!["--supports-retry", "--retry"],
            vec!["--supports-retry", "--supports-retry"],
            vec![
                "--retry",
                "--cutover",
                "1:0.6.0:00000000000000000000000000000000",
            ],
            vec!["--cutover", "invalid"],
            vec!["start"],
        ] {
            let arguments: Vec<_> = arguments.into_iter().map(OsString::from).collect();
            assert_eq!(
                Invocation::parse(&arguments).unwrap_err().kind(),
                io::ErrorKind::InvalidInput
            );
        }
    }

    #[test]
    fn version_and_cutover_keep_their_closed_grammar() {
        assert_eq!(
            Invocation::parse(&["--version".into()]).unwrap(),
            Invocation::Version
        );
        assert_eq!(
            Invocation::parse(&["--supports-retry".into()]).unwrap(),
            Invocation::SupportsRetry
        );
        let designation = crate::cutover::Designation {
            parent_pid: 7,
            parent_version: "0.5.0".into(),
            nonce: "0123456789abcdef0123456789abcdef".into(),
        };
        assert_eq!(
            Invocation::parse(&["--cutover".into(), designation.argument().into()]).unwrap(),
            Invocation::Cutover(designation)
        );
    }
}
