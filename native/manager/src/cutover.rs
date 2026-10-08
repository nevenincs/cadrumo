//! Closed one-time designation for a held direct-child successor.
//! A command-line designation alone grants nothing: its parent must authenticate
//! and accept that exact live child before the initial start-claim exemption exists.
use cadrumo_application::installation::version;
use serde::{Deserialize, Serialize};
use std::io;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Designation {
    pub parent_pid: u32,
    pub parent_version: String,
    pub nonce: String,
}
impl Designation {
    pub fn parse(text: &str) -> io::Result<Self> {
        let fields: Vec<_> = text.split(':').collect();
        if fields.len() != 3 || text.len() > 96 {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        let parent_pid: u32 = fields[0].parse().map_err(io::Error::other)?;
        if parent_pid == 0 || parent_pid.to_string() != fields[0] || !valid_nonce(fields[2]) {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        version(fields[1]).map_err(io::Error::other)?;
        Ok(Self {
            parent_pid,
            parent_version: fields[1].into(),
            nonce: fields[2].into(),
        })
    }
    pub fn argument(&self) -> String {
        format!("{}:{}:{}", self.parent_pid, self.parent_version, self.nonce)
    }
    pub fn endpoint(&self) -> String {
        format!("{}.cutover.{}", crate::identity::MANAGER_ID, self.nonce)
    }
}
pub fn valid_nonce(value: &str) -> bool {
    value.len() == 32
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(tag = "phase", rename_all = "snake_case", deny_unknown_fields)]
pub enum Report {
    Claim { nonce: String },
    Launched { nonce: String },
    Ready { nonce: String },
    Acknowledged { nonce: String },
}
impl Report {
    pub fn nonce(&self) -> &str {
        match self {
            Self::Claim { nonce }
            | Self::Launched { nonce }
            | Self::Ready { nonce }
            | Self::Acknowledged { nonce } => nonce,
        }
    }
    pub fn valid(&self, runtime_pid: u32) -> bool {
        valid_nonce(self.nonce()) && (matches!(self, Self::Claim { .. }) == (runtime_pid == 0))
    }
}

/// Closed handshake state. `peer` is supplied by native pipe peer inspection;
/// `runtime` is not accepted until the caller holds and verifies that process.
pub struct Handshake {
    child: u32,
    nonce: String,
    claimed: bool,
    runtime: Option<u32>,
    ready: bool,
    acknowledged: bool,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Accepted {
    Claim,
    Launched,
    Ready,
    Acknowledged,
}
impl Handshake {
    pub fn new(child: u32, nonce: String) -> io::Result<Self> {
        if child == 0 || !valid_nonce(&nonce) {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        Ok(Self {
            child,
            nonce,
            claimed: false,
            runtime: None,
            ready: false,
            acknowledged: false,
        })
    }
    pub fn accept(
        &mut self,
        peer: u32,
        runtime: u32,
        report: &Report,
        verify: impl FnOnce(u32, bool) -> io::Result<()>,
    ) -> io::Result<Accepted> {
        if peer != self.child
            || report.nonce() != self.nonce
            || !report.valid(runtime)
            || self.acknowledged
        {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        match report {
            Report::Claim { .. } if !self.claimed => {
                self.claimed = true;
                Ok(Accepted::Claim)
            }
            Report::Launched { .. } if self.claimed && self.runtime.is_none() => {
                verify(runtime, false)?;
                self.runtime = Some(runtime);
                Ok(Accepted::Launched)
            }
            Report::Ready { .. } if !self.ready && self.runtime == Some(runtime) => {
                verify(runtime, true)?;
                self.ready = true;
                Ok(Accepted::Ready)
            }
            Report::Acknowledged { .. } if self.ready && self.runtime == Some(runtime) => {
                verify(runtime, true)?;
                self.acknowledged = true;
                Ok(Accepted::Acknowledged)
            }
            _ => Err(io::ErrorKind::PermissionDenied.into()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    const NONCE: &str = "0123456789abcdef0123456789abcdef";
    #[test]
    fn designation_and_authenticated_reports_are_ordered_one_time_and_proof_bound() {
        let designation = Designation::parse(&format!("42:1.0.0:{NONCE}")).unwrap();
        assert_eq!(designation.argument(), format!("42:1.0.0:{NONCE}"));
        for invalid in [
            format!("0:1.0.0:{NONCE}"),
            format!("042:1.0.0:{NONCE}"),
            format!("42:01.0.0:{NONCE}"),
        ] {
            assert!(Designation::parse(&invalid).is_err());
        }
        let claim = Report::Claim {
            nonce: NONCE.into(),
        };
        let launched = Report::Launched {
            nonce: NONCE.into(),
        };
        let ready = Report::Ready {
            nonce: NONCE.into(),
        };
        let acknowledged = Report::Acknowledged {
            nonce: NONCE.into(),
        };
        let mut state = Handshake::new(100, NONCE.into()).unwrap();
        let no_proof = |_, _| panic!("unadmitted request must not inspect or signal a process");
        assert!(state.accept(101, 0, &claim, no_proof).is_err());
        assert!(state.accept(100, 500, &ready, no_proof).is_err());
        assert!(state.accept(100, 500, &acknowledged, no_proof).is_err());
        assert_eq!(
            state.accept(100, 0, &claim, no_proof).unwrap(),
            Accepted::Claim
        );
        assert!(state.accept(100, 0, &claim, no_proof).is_err());
        assert!(
            state
                .accept(100, 500, &launched, |_, _| Err(
                    io::ErrorKind::PermissionDenied.into()
                ))
                .is_err()
        );
        assert_eq!(
            state
                .accept(100, 500, &launched, |pid, ready| {
                    assert_eq!(pid, 500);
                    assert!(!ready);
                    Ok(())
                })
                .unwrap(),
            Accepted::Launched
        );
        assert!(state.accept(100, 501, &ready, no_proof).is_err());
        assert!(
            state
                .accept(100, 500, &ready, |_, _| Err(
                    io::ErrorKind::InvalidData.into()
                ))
                .is_err()
        );
        assert_eq!(
            state
                .accept(100, 500, &ready, |pid, ready| {
                    assert_eq!(pid, 500);
                    assert!(ready);
                    Ok(())
                })
                .unwrap(),
            Accepted::Ready
        );
        assert!(state.accept(100, 500, &ready, no_proof).is_err());
        assert!(state.accept(101, 500, &acknowledged, no_proof).is_err());
        assert!(state.accept(100, 501, &acknowledged, no_proof).is_err());
        assert!(
            state
                .accept(100, 500, &acknowledged, |_, _| Err(
                    io::ErrorKind::BrokenPipe.into()
                ))
                .is_err()
        );
        assert_eq!(
            state
                .accept(100, 500, &acknowledged, |pid, ready| {
                    assert_eq!(pid, 500);
                    assert!(ready);
                    Ok(())
                })
                .unwrap(),
            Accepted::Acknowledged
        );
        assert!(state.accept(100, 500, &acknowledged, no_proof).is_err());
    }
}
