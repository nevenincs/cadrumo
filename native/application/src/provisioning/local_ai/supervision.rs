//! Supervision of the one local AI server: the runtime manager's part of the local AI.
//!
//! The supervisor runs the server of one [`Supervised`] program: the Ollama program the
//! engine installs, or the llama-server the package carries. An [`EngineProgram`] holds
//! only the selected engine's program, so the other engine's server is never started.
//! The server runs only on demand. Until its owner calls [`ServerSupervisor::demand`]
//! it is [`ServerState::Dormant`] and no process runs. A demand is a lease: the server
//! runs from the set-up program on its fixed address until [`IDLE_STOP`] after the last
//! demand, then it is stopped and dormant again. While demanded, a server that ends
//! without being asked to, or fails to start, is started again after a backoff that
//! doubles up to a ceiling, until too many restarts fall inside one window and
//! supervision fails until a retry. A server that ends when no demand is live is not
//! started again. A program change an engine asks for through the
//! [`lease`](super::lease) stops the server and holds every start off until the change is
//! over. A server whose program asks for a fresh start, as llama-server does once the
//! models in the store have changed, is stopped and started again at once, outside the
//! restart count. The owner stops the server on exit and at session end, and nothing is
//! started again until it resumes supervision.
//!
//! The supervisor never blocks: the owner calls [`ServerSupervisor::poll`] at its own pace
//! and at [`ServerSupervisor::next_due`], and each call looks once and acts once. Time is
//! the owner's monotonic clock, passed in.

use super::{
    LocalAiError, LocalEngine,
    llama_server::LlamaServer,
    program::{Containment, Program, Server},
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

/// How long one demand keeps the server running: the server is stopped this long after
/// the last demand, unless another demand renews it first.
pub const IDLE_STOP: Duration = Duration::from_secs(5 * 60);

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
    /// The program is not set up, so no server is run.
    NotSetUp,
    /// The program is set up and no demand is live, so no server runs until one is.
    Dormant,
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

/// A change of whether the server runs, with its cause, for the owner's log.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ServerChange {
    /// A live demand started the server, or started it again after it ended.
    StartedOnDemand,
    /// The last demand lapsed, so the running server was stopped.
    IdleStopped,
    /// The server ended while no demand was live, so it was not started again.
    EndedWithoutDemand,
}

/// The most changes kept for the owner between two reads; older ones are dropped.
const CHANGES_KEPT: usize = 16;

/// File facts that change whenever a program is set up or removed: a program found not
/// set up is looked at again only once they change.
pub type SetUpStamp = Option<(SystemTime, u64)>;

/// Reads the owner's environment by name.
pub type Environment = Box<dyn Fn(&str) -> Option<OsString> + Send>;

/// A program whose server the supervisor runs.
pub trait Supervised {
    /// Whether the program is ready to run a server from, read from files alone.
    fn is_set_up(&self) -> bool;

    /// The facts [`Self::is_set_up`] depends on, so a program not set up is read again
    /// only once they change.
    fn set_up_stamp(&self) -> SetUpStamp;

    /// The server this program started, when it has one.
    fn running_mut(&mut self) -> Option<&mut Server>;

    /// Whether an engine changes the program or asks to.
    fn change_requested(&self) -> bool;

    /// Whether the running server should be started again now to serve what it was not
    /// started with. It is asked only while the server runs.
    fn restart_due(&mut self) -> bool {
        false
    }

    /// Whether the server fetches anything through the operator's proxy, so a proxy
    /// setting the engine cannot use must keep it from running.
    fn uses_proxy(&self) -> bool;

    /// Starts the server on `address`, contained by `containment`, unless one runs.
    /// `Busy` while an engine changes the program or asks to, or another server holds
    /// the lease. `ambient` reads the supervisor's own environment for the operating
    /// system settings the server is given.
    fn serve(
        &mut self,
        address: SocketAddr,
        containment: &dyn Containment,
        ambient: &dyn Fn(&str) -> Option<OsString>,
        proxy: Option<&ProxySettings>,
    ) -> Result<(), LocalAiError>;

    /// Stops the server this program started, if any.
    fn halt(&mut self);
}

impl Supervised for Program {
    fn is_set_up(&self) -> bool {
        self.observe_quick() == Observation::Present
    }

    fn set_up_stamp(&self) -> SetUpStamp {
        let metadata = fs::symlink_metadata(self.locations().programs.join("active.json")).ok()?;
        Some((metadata.modified().ok()?, metadata.len()))
    }

    fn running_mut(&mut self) -> Option<&mut Server> {
        self.server_mut()
    }

    fn change_requested(&self) -> bool {
        self.leases().change_requested().unwrap_or(false)
    }

    fn uses_proxy(&self) -> bool {
        true
    }

    fn serve(
        &mut self,
        address: SocketAddr,
        containment: &dyn Containment,
        ambient: &dyn Fn(&str) -> Option<OsString>,
        proxy: Option<&ProxySettings>,
    ) -> Result<(), LocalAiError> {
        self.start(address, containment, ambient, proxy).map(|_| ())
    }

    fn halt(&mut self) {
        self.stop();
    }
}

/// The program of the one selected engine, whose server is the only one supervised: the
/// other engine's program is never built, so nothing can start its server.
pub enum EngineProgram {
    Ollama(Box<Program>),
    LlamaCpp(Box<LlamaServer>),
}

impl EngineProgram {
    /// The program of `engine`: `ollama` or `llama` builds it, and only the selected
    /// one is ever called.
    pub fn select<E>(
        engine: LocalEngine,
        ollama: impl FnOnce() -> Result<Program, E>,
        llama: impl FnOnce() -> Result<LlamaServer, E>,
    ) -> Result<Self, E> {
        Ok(match engine {
            LocalEngine::Ollama => Self::Ollama(Box::new(ollama()?)),
            LocalEngine::LlamaCpp => Self::LlamaCpp(Box::new(llama()?)),
        })
    }

    pub fn engine(&self) -> LocalEngine {
        match self {
            Self::Ollama(_) => LocalEngine::Ollama,
            Self::LlamaCpp(_) => LocalEngine::LlamaCpp,
        }
    }

    fn program(&self) -> &dyn Supervised {
        match self {
            Self::Ollama(program) => &**program,
            Self::LlamaCpp(program) => &**program,
        }
    }

    fn program_mut(&mut self) -> &mut dyn Supervised {
        match self {
            Self::Ollama(program) => &mut **program,
            Self::LlamaCpp(program) => &mut **program,
        }
    }
}

impl Supervised for EngineProgram {
    fn is_set_up(&self) -> bool {
        self.program().is_set_up()
    }

    fn set_up_stamp(&self) -> SetUpStamp {
        self.program().set_up_stamp()
    }

    fn running_mut(&mut self) -> Option<&mut Server> {
        self.program_mut().running_mut()
    }

    fn change_requested(&self) -> bool {
        self.program().change_requested()
    }

    fn restart_due(&mut self) -> bool {
        self.program_mut().restart_due()
    }

    fn uses_proxy(&self) -> bool {
        self.program().uses_proxy()
    }

    fn serve(
        &mut self,
        address: SocketAddr,
        containment: &dyn Containment,
        ambient: &dyn Fn(&str) -> Option<OsString>,
        proxy: Option<&ProxySettings>,
    ) -> Result<(), LocalAiError> {
        self.program_mut()
            .serve(address, containment, ambient, proxy)
    }

    fn halt(&mut self) {
        self.program_mut().halt();
    }
}

/// Runs the local AI server of `P` for its owner.
pub struct ServerSupervisor<P: Supervised = Program> {
    program: P,
    address: SocketAddr,
    containment: Box<dyn Containment + Send>,
    environment: Environment,
    policy: RestartPolicy,
    restarts: VecDeque<Instant>,
    /// How long a demand keeps the server running.
    idle_stop: Duration,
    /// The moment the latest demand lapses; none before the first. Kept in memory only, so
    /// no demand outlives this supervisor.
    demanded_until: Option<Instant>,
    /// Changes not yet read by the owner, oldest first.
    changes: VecDeque<ServerChange>,
    state: ServerState,
    not_set_up: Option<SetUpStamp>,
    proxy: Option<ProxySettings>,
    proxy_refused: bool,
    /// Why the latest start failed, until a start succeeds; for logs and tests.
    last_start_failure: Option<LocalAiError>,
}

impl<P: Supervised> ServerSupervisor<P> {
    /// Supervises `program`'s server on `address`, a loopback address, contained by
    /// `containment`. `environment` reads the owner's environment: the operating system
    /// settings the server is given, and the operator's proxy for the models it
    /// downloads.
    ///
    /// The proxy setting is read here, once. A process's environment block is its own
    /// and cannot be changed from outside it, so this is the setting for the whole of
    /// this supervisor's life: a setting the operator changes afterwards reaches the
    /// server at the next start of the owner. A setting the engine cannot use runs no
    /// server at all from a program that fetches through it.
    pub fn new(
        program: P,
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
            idle_stop: IDLE_STOP,
            demanded_until: None,
            changes: VecDeque::new(),
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

    /// The same supervisor with demands that keep the server running for `idle_stop`
    /// instead of [`IDLE_STOP`].
    pub fn with_idle_stop(mut self, idle_stop: Duration) -> Self {
        self.idle_stop = idle_stop;
        self
    }

    /// Demands the server at `now`, or renews a live demand: the next poll starts it
    /// when it does not run, and it keeps running until the idle stop after this demand.
    pub fn demand(&mut self, now: Instant) {
        let until = now + self.idle_stop;
        self.demanded_until = Some(self.demanded_until.map_or(until, |held| held.max(until)));
    }

    /// Whether a demand is live at `now`.
    fn demanded(&self, now: Instant) -> bool {
        self.demanded_until.is_some_and(|until| now < until)
    }

    /// The changes since the last read, oldest first.
    pub fn take_changes(&mut self) -> Vec<ServerChange> {
        self.changes.drain(..).collect()
    }

    fn changed(&mut self, change: ServerChange) {
        if self.changes.len() == CHANGES_KEPT {
            self.changes.pop_front();
        }
        self.changes.push_back(change);
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

    pub fn program(&self) -> &P {
        &self.program
    }

    /// The moment a look is next due: a scheduled restart, or the idle stop of a running
    /// server.
    pub fn next_due(&self) -> Option<Instant> {
        match self.state {
            ServerState::Restarting { at } => Some(at),
            ServerState::Running => self.demanded_until,
            _ => None,
        }
    }

    /// Looks once and acts once: notices an ended server, a requested program change, a
    /// server its program wants started again, a lapsed demand, or a newly set-up program,
    /// and starts, stops or schedules accordingly. Only a live demand starts a server.
    pub fn poll(&mut self, now: Instant) -> ServerState {
        let demanded = self.demanded(now);
        match self.state {
            ServerState::Stopped | ServerState::Failed => return self.state,
            ServerState::Restarting { at } if now < at => return self.state,
            _ => {}
        }
        if self.proxy_refused && self.program.uses_proxy() {
            self.program.halt();
            self.state = ServerState::ProxyRefused;
            return self.state;
        }
        if let Some(server) = self.program.running_mut() {
            if server.exited() {
                // Reaps it, removes its record and gives the lease up.
                self.program.halt();
                if !demanded {
                    // Nobody needs it: a server that ends while no demand is live,
                    // stopped by its process ID or crashed, stays down.
                    self.changed(ServerChange::EndedWithoutDemand);
                    self.state = ServerState::Dormant;
                    return self.state;
                }
                return self.failed_start(now);
            }
            if self.program.change_requested() {
                self.program.halt();
                self.state = ServerState::Held;
                return self.state;
            }
            if !demanded {
                // The idle stop: the last demand has lapsed.
                self.program.halt();
                self.changed(ServerChange::IdleStopped);
                self.state = ServerState::Dormant;
                return self.state;
            }
            if !self.program.restart_due() {
                self.state = ServerState::Running;
                return self.state;
            }
            // Started again below, at once and outside the restart count: nothing failed.
            self.program.halt();
        }
        let stamp = self.program.set_up_stamp();
        if self.not_set_up == Some(stamp) && self.state == ServerState::NotSetUp {
            return self.state;
        }
        if !self.program.is_set_up() {
            self.not_set_up = Some(stamp);
            self.state = ServerState::NotSetUp;
            return self.state;
        }
        self.not_set_up = None;
        if !demanded {
            self.state = ServerState::Dormant;
            return self.state;
        }
        let started = self.program.serve(
            self.address,
            self.containment.as_ref(),
            self.environment.as_ref(),
            self.proxy.as_ref(),
        );
        match started {
            Ok(()) => {
                self.last_start_failure = None;
                self.changed(ServerChange::StartedOnDemand);
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

    /// Stops the server and starts nothing until [`Self::resume`]: the owner exits, or
    /// its session ends.
    pub fn stop(&mut self) {
        self.program.halt();
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
    pub(crate) fn program_mut(&mut self) -> &mut P {
        &mut self.program
    }
}

impl<P: Supervised> Drop for ServerSupervisor<P> {
    fn drop(&mut self) {
        self.program.halt();
    }
}

#[cfg(test)]
mod tests;
