//! Contracts consumed by native manager hosts and upgrade coordination.
//!
//! Concrete lifetime orchestration remains owned by Background. Native event loops
//! use these contracts without acquiring or duplicating its process and start claims.

use crate::background::Background;
use crate::session::claim::StartClaim;
use std::{io, path::Path};

pub trait CutoverRuntime {
    fn root(&self) -> Option<&Path> {
        None
    }
    fn can_cutover(&self) -> bool {
        false
    }
    fn stopping(&self) -> bool {
        false
    }
    fn resume_session(&mut self) {}
    fn begin_cutover(&mut self) -> io::Result<Option<StartClaim>> {
        Ok(None)
    }
    fn idle_stopped(&self) -> bool {
        false
    }
    fn retry_idle(&self) {}
    fn abandon_cutover(&mut self) {}
    fn rollback(&mut self, _claim: StartClaim) {}
}
impl CutoverRuntime for Background {
    fn root(&self) -> Option<&Path> {
        Some(self.storage_root())
    }
    fn can_cutover(&self) -> bool {
        self.can_cutover()
    }
    fn stopping(&self) -> bool {
        self.stopping()
    }
    fn resume_session(&mut self) {
        self.cancel_session_end();
    }
    fn begin_cutover(&mut self) -> io::Result<Option<StartClaim>> {
        self.begin_cutover()
    }
    fn idle_stopped(&self) -> bool {
        self.idle_stopped()
    }
    fn retry_idle(&self) {
        self.retry_idle();
    }
    fn abandon_cutover(&mut self) {
        self.abandon_cutover();
    }
    fn rollback(&mut self, claim: StartClaim) {
        self.rollback(claim);
    }
}

pub trait ManagerLifecycle: CutoverRuntime {
    fn retry(&mut self) -> io::Result<()> {
        self.poll()
    }
    fn restart(&mut self) -> io::Result<()> {
        Err(io::ErrorKind::Unsupported.into())
    }
    fn quit(&mut self) -> io::Result<()> {
        Err(io::ErrorKind::Unsupported.into())
    }
    fn status(&self) -> &'static str {
        "waiting"
    }
    fn quit_completed(&self) -> bool {
        false
    }
    fn poll(&mut self) -> io::Result<()>;
    fn begin_session_end(&mut self);
    fn session_end_settled(&self) -> bool;
    fn session_end(&mut self);
    fn cancel_session_end(&mut self);
}
impl ManagerLifecycle for Background {
    fn retry(&mut self) -> io::Result<()> {
        Background::retry(self)
    }
    fn restart(&mut self) -> io::Result<()> {
        Background::restart(self)
    }
    fn quit(&mut self) -> io::Result<()> {
        Background::quit(self)
    }
    fn status(&self) -> &'static str {
        Background::status(self)
    }
    fn quit_completed(&self) -> bool {
        Background::quit_completed(self)
    }
    fn poll(&mut self) -> io::Result<()> {
        Background::poll(self)
    }
    fn begin_session_end(&mut self) {
        Background::begin_session_end(self);
    }
    fn session_end_settled(&self) -> bool {
        Background::session_end_settled(self)
    }
    fn session_end(&mut self) {
        Background::session_end(self);
    }
    fn cancel_session_end(&mut self) {
        Background::cancel_session_end(self);
    }
}

/// Native evidence that an admitted installation has completed removal.
/// Unknown observations and transient upgrade gaps must not report removal.
pub trait RemovalObservation {
    fn removed(&mut self) -> bool;
}
