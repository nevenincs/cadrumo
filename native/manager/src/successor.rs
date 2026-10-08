//! Sealed successor launch authority and bounded reporting capabilities.
//!
//! Only a native admission producer nested here may mint these values.
use std::{
    io,
    path::{Path, PathBuf},
    sync::mpsc::{Receiver, SyncSender, TryRecvError},
};

#[cfg(windows)]
pub mod windows;

/// Only successful native parent/child/pipe admission can construct this value.
/// It authorizes one initial launch under the parent's still-held start claim.
pub struct InitialPermit {
    root: PathBuf,
}
impl InitialPermit {
    pub(crate) fn root(&self) -> &Path {
        &self.root
    }
}
pub enum ReportResult {
    Committed,
    ParentExited,
    Rejected,
}
enum Phase {
    Launched,
    Ready,
}
pub struct Reporter {
    send: SyncSender<(u32, Phase)>,
    result: Receiver<ReportResult>,
}
impl Reporter {
    pub fn launched(&self, pid: u32) -> io::Result<()> {
        self.send
            .try_send((pid, Phase::Launched))
            .map_err(io::Error::other)
    }
    pub fn ready(&self, pid: u32) -> io::Result<()> {
        self.send
            .try_send((pid, Phase::Ready))
            .map_err(io::Error::other)
    }
    pub fn poll(&self) -> Option<ReportResult> {
        match self.result.try_recv() {
            Ok(result) => Some(result),
            Err(TryRecvError::Empty) => None,
            Err(TryRecvError::Disconnected) => Some(ReportResult::Rejected),
        }
    }
}
