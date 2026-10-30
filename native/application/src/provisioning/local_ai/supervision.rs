//! Supervision of the one local AI server: the runtime manager's part of the local AI.
//!
//! While the program is set up, meaning its pinned version is active and intact, the
//! supervisor keeps a server running from it on the installation's fixed address. A
//! server that ends without being asked to, or fails to start, is started again after a
//! backoff that doubles up to a ceiling, until too many restarts fall inside one window
//! and supervision fails until a retry. A program change an engine asks for through the
//! [`lease`](super::lease) stops the server and holds every start off until the change is
//! over. The owner stops the server on exit and at session end, and nothing is started
//! again until it resumes supervision.
//!
//! The supervisor never blocks: the owner calls [`ServerSupervisor::poll`] at its own pace
//! and at [`ServerSupervisor::next_due`], and each call looks once and acts once. Time is
//! the owner's monotonic clock, passed in.

use super::{
    LocalAiError,
    program::{Containment, Program},
};
use crate::{
    error::Error,
    provisioning::{proxy::ProxySettings, state::Observation},
};
use std::{
    collections::VecDeque,
    ffi::OsString,
    fs,
    net::SocketAddr,
    time::{Duration, Instant, SystemTime},
};

/// The restart backoff and the crash-loop ceiling.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RestartPolicy {
    /// Delay before the first restart in a window.
    pub initial_backoff: Duration,
    /// Upper bound of any one delay.
    pub maximum_backoff: Duration,
    /// Restarts admitted inside one window; the next failure fails supervision.
    pub crash_loop_limit: usize,
    /// Width of the sliding window.
    pub crash_loop_window: Duration,
}

impl Default for RestartPolicy {
    fn default() -> Self {
        Self {
            initial_backoff: Duration::from_secs(1),
            maximum_backoff: Duration::from_secs(60),
            crash_loop_limit: 5,
            crash_loop_window: Duration::from_secs(600),
        }
    }
}

impl RestartPolicy {
    fn backoff(&self, prior: usize) -> Duration {
        let doublings = u32::try_from(prior).unwrap_or(u32::MAX).min(31);
        self.initial_backoff
            .checked_mul(1 << doublings)
            .unwrap_or(self.maximum_backoff)
            .min(self.maximum_backoff)
    }
}

/// Where supervision stands after a poll.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ServerState {
    /// The pinned program is not active and intact, so no server is run.
    NotSetUp,
    /// An engine changes the program or asks to; no server runs until it is done.
    Held,
    /// The server runs and answered with the pinned version when it started.
    Running,
    /// The server ended or did not start; it is started again at `at`.
    Restarting { at: Instant },
    /// Too many restarts inside one window; nothing starts until a retry.
    Failed,
    /// The owner stopped the server; nothing starts until it resumes.
    Stopped,
    /// The proxy setting this owner started with is one the engine cannot use, so no
    /// server is run: a server started without it would reach the model registry
    /// directly, which is the opposite of what the setting asks for. The setting is the
    /// owner's own environment and cannot change while it runs, so nothing starts until
    /// the owner is started again with a setting the engine can use.
    ProxyRefused,
}

/// The active pointer's file facts, which change whenever a version is activated or
/// removed: a program found not set up is looked at again only once they change.
type PointerStamp = Option<(SystemTime, u64)>;

/// Reads the owner's environment by name.
pub type Environment = Box<dyn Fn(&str) -> Option<OsString> + Send>;

/// Runs the local AI server for its owner.
pub struct ServerSupervisor {
    program: Program,
    address: SocketAddr,
    containment: Box<dyn Containment + Send>,
    environment: Environment,
    policy: RestartPolicy,
    restarts: VecDeque<Instant>,
    state: ServerState,
    not_set_up: Option<PointerStamp>,
    proxy: Option<ProxySettings>,
    proxy_refused: bool,
    /// Why the latest start failed, until a start succeeds; for logs and tests.
    last_start_failure: Option<LocalAiError>,
}

impl ServerSupervisor {
    /// Supervises `program`'s server on `address`, a loopback address, contained by
    /// `containment`. `environment` reads the owner's environment: the operating system
    /// settings the server is given, and the operator's proxy for the models it
    /// downloads.
    ///
    /// The proxy setting is read here, once. A process's environment block is its own
    /// and cannot be changed from outside it, so this is the setting for the whole of
    /// this supervisor's life: a setting the operator changes afterwards reaches the
    /// server at the next start of the owner. A setting the engine cannot use runs no
    /// server at all.
    pub fn new(
        program: Program,
        address: SocketAddr,
        containment: Box<dyn Containment + Send>,
        environment: Environment,
    ) -> Result<Self, Error> {
        if !address.ip().is_loopback() {
            return Err(Error::Invalid(
                "the local AI answers on loopback only".into(),
            ));
        }
        let (proxy, proxy_refused) = match ProxySettings::from_settings(|name| {
            environment(name).and_then(|value| value.into_string().ok())
        }) {
            Ok(proxy) => (proxy, false),
            Err(_) => (None, true),
        };
        Ok(Self {
            program,
            address,
            containment,
            environment,
            policy: RestartPolicy::default(),
            restarts: VecDeque::new(),
            state: ServerState::NotSetUp,
            not_set_up: None,
            proxy,
            proxy_refused,
            last_start_failure: None,
        })
    }

    /// The same supervisor with `policy` instead of the default.
    pub fn with_policy(mut self, policy: RestartPolicy) -> Self {
        self.policy = policy;
        self
    }

    pub fn state(&self) -> ServerState {
        self.state
    }

    pub fn address(&self) -> SocketAddr {
        self.address
    }

    /// Why the latest attempt to start the server failed, until one succeeds. The cause
    /// is for the owner's logs; a surface shows only its category.
    pub fn last_start_failure(&self) -> Option<&LocalAiError> {
        self.last_start_failure.as_ref()
    }

    pub fn program(&self) -> &Program {
        &self.program
    }

    /// The moment a scheduled restart is due, when one is.
    pub fn next_due(&self) -> Option<Instant> {
        match self.state {
            ServerState::Restarting { at } => Some(at),
            _ => None,
        }
    }

    /// Looks once and acts once: notices an ended server, a requested program change or
    /// a newly set-up program, and starts, stops or schedules accordingly.
    pub fn poll(&mut self, now: Instant) -> ServerState {
        match self.state {
            ServerState::Stopped | ServerState::Failed => return self.state,
            ServerState::Restarting { at } if now < at => return self.state,
            _ => {}
        }
        if self.proxy_refused {
            self.program.stop();
            self.state = ServerState::ProxyRefused;
            return self.state;
        }
        if let Some(server) = self.program.server_mut() {
            if server.exited() {
                // Reaps it, removes its record and gives the lease up.
                self.program.stop();
                return self.failed_start(now);
            }
            if self.program.leases().change_requested().unwrap_or(false) {
                self.program.stop();
                self.state = ServerState::Held;
            } else {
                self.state = ServerState::Running;
            }
            return self.state;
        }
        let stamp = self.pointer_stamp();
        if self.not_set_up == Some(stamp) && self.state == ServerState::NotSetUp {
            return self.state;
        }
        if self.program.observe_quick() != Observation::Present {
            self.not_set_up = Some(stamp);
            self.state = ServerState::NotSetUp;
            return self.state;
        }
        self.not_set_up = None;
        let started = self.program.start(
            self.address,
            self.containment.as_ref(),
            self.environment.as_ref(),
            self.proxy.as_ref(),
        );
        match started {
            Ok(_) => {
                self.last_start_failure = None;
                self.state = ServerState::Running;
            }
            Err(LocalAiError::Engine(Error::Busy)) => self.state = ServerState::Held,
            Err(error) => {
                self.last_start_failure = Some(error);
                return self.failed_start(now);
            }
        }
        self.state
    }

    /// Admits one restart at `now`, or fails supervision at the crash-loop ceiling.
    fn failed_start(&mut self, now: Instant) -> ServerState {
        while let Some(&oldest) = self.restarts.front() {
            if now.saturating_duration_since(oldest) < self.policy.crash_loop_window {
                break;
            }
            self.restarts.pop_front();
        }
        self.state = if self.restarts.len() >= self.policy.crash_loop_limit {
            ServerState::Failed
        } else {
            let delay = self.policy.backoff(self.restarts.len());
            self.restarts.push_back(now);
            ServerState::Restarting { at: now + delay }
        };
        self.state
    }

    fn pointer_stamp(&self) -> PointerStamp {
        let metadata =
            fs::symlink_metadata(self.program.locations().programs.join("active.json")).ok()?;
        Some((metadata.modified().ok()?, metadata.len()))
    }

    /// Stops the server and starts nothing until [`Self::resume`]: the owner exits, or
    /// its session ends.
    pub fn stop(&mut self) {
        self.program.stop();
        self.state = ServerState::Stopped;
    }

    /// Supervises again after a stop, as when an ending session was cancelled; the next
    /// poll looks afresh.
    pub fn resume(&mut self) {
        if self.state == ServerState::Stopped {
            self.state = ServerState::NotSetUp;
            self.not_set_up = None;
        }
    }

    /// Forgets every earlier restart after supervision failed, at the person's Retry.
    pub fn retry(&mut self) {
        self.restarts.clear();
        if self.state == ServerState::Failed {
            self.state = ServerState::NotSetUp;
            self.not_set_up = None;
        }
    }

    /// The supervised program, for a test to reach its server.
    #[cfg(test)]
    pub(crate) fn program_mut(&mut self) -> &mut Program {
        &mut self.program
    }
}

impl Drop for ServerSupervisor {
    fn drop(&mut self) {
        self.program.stop();
    }
}

#[cfg(test)]
mod tests;
