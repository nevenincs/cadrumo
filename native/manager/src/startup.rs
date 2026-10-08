//! Compose session ownership with supervision without coupling it to a frontend.

use crate::session::ownership::{Ownership, Role, StartKind};
use crate::supervision::{
    launch::LaunchTarget,
    supervisor::{
        Collaborators, EVENT_QUEUE, Event, Outcome, Supervisor, SupervisorConfig, SupervisorHandle,
    },
};
use std::{
    io,
    sync::{
        Arc,
        mpsc::{self, Receiver},
    },
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};

pub struct Running {
    pub handle: SupervisorHandle,
    pub events: Receiver<Event>,
    pub ended: Receiver<io::Result<Outcome>>,
    completion: Completion,
}

impl Running {
    pub fn join(&mut self) -> io::Result<()> {
        self.completion.join()
    }

    pub(crate) fn wait_settled(&mut self, bound: Duration) -> io::Result<Option<Outcome>> {
        self.completion.wait(&self.ended, bound)
    }

    /// A terminal report alone does not prove the supervising worker has returned.
    pub fn settled(&mut self) -> io::Result<Option<Outcome>> {
        self.completion.poll(&self.ended)
    }
}

#[derive(Default)]
struct Completion {
    worker: Option<JoinHandle<()>>,
    terminal: Option<Result<Outcome, Arc<io::Error>>>,
    failure: Option<&'static str>,
    delivered: bool,
}
impl Completion {
    fn wait(
        &mut self,
        ended: &Receiver<io::Result<Outcome>>,
        bound: Duration,
    ) -> io::Result<Option<Outcome>> {
        let deadline = Instant::now() + bound;
        loop {
            match self.poll(ended)? {
                Some(outcome) => return Ok(Some(outcome)),
                None => {
                    let remaining = deadline.saturating_duration_since(Instant::now());
                    if remaining.is_zero() {
                        return Ok(None);
                    }
                    thread::sleep(remaining.min(Duration::from_millis(1)));
                }
            }
        }
    }
    fn join(&mut self) -> io::Result<()> {
        if let Some(worker) = self.worker.take()
            && worker.join().is_err()
        {
            self.failure = Some("manager_supervisor_panicked");
        }
        match self.failure {
            Some(message) => Err(io::Error::other(message)),
            None => Ok(()),
        }
    }
    fn poll(&mut self, ended: &Receiver<io::Result<Outcome>>) -> io::Result<Option<Outcome>> {
        if self.delivered {
            return Ok(None);
        }
        if self.terminal.is_none() && self.failure.is_none() {
            match ended.try_recv() {
                Ok(result) => self.terminal = Some(result.map_err(Arc::new)),
                Err(mpsc::TryRecvError::Empty) => {}
                Err(mpsc::TryRecvError::Disconnected) => {
                    self.failure = Some("manager_supervisor_lost");
                }
            }
        }
        if self
            .worker
            .as_ref()
            .is_some_and(|worker| !worker.is_finished())
        {
            return match self.failure {
                Some(message) => Err(io::Error::other(message)),
                None => Ok(None),
            };
        }
        self.join()?;
        if let Some(Err(error)) = &self.terminal {
            return Err(io::Error::new(error.kind(), Arc::clone(error)));
        }
        match self.terminal.take() {
            Some(Ok(outcome)) => {
                self.delivered = true;
                Ok(Some(outcome))
            }
            _ => Ok(None),
        }
    }
}

/// A launch only follows an ownership permit. Other sessions remain observers.
pub fn start(
    target: LaunchTarget,
    config: SupervisorConfig,
    collaborators: Collaborators,
    ownership: &mut Ownership,
    initial: Option<StartKind>,
) -> io::Result<Start> {
    let role = match initial {
        Some(kind) => ownership.begin(kind)?,
        None => ownership.reassess(),
    };
    let (events, receive_events) = mpsc::sync_channel(EVENT_QUEUE);
    let supervisor = Supervisor::new(config, target, collaborators, events);
    let permit = match role {
        Role::Start(permit) => Some(permit),
        Role::OwnSession { .. } => None,
        other => return Ok(Start::Waiting(other)),
    };
    spawn(
        supervisor,
        if let Some(permit) = permit {
            Mode::Reserved(permit)
        } else {
            Mode::Adopting
        },
        receive_events,
    )
}

enum Mode {
    Reserved(crate::session::ownership::StartPermit),
    Adopting,
    Designated,
}
fn spawn(supervisor: Supervisor, mode: Mode, receive_events: Receiver<Event>) -> io::Result<Start> {
    let handle = supervisor.handle();
    let (ended, receive_ended) = mpsc::channel();
    let worker = thread::Builder::new()
        .name("manager-supervisor".into())
        .spawn(move || {
            let result = match mode {
                Mode::Reserved(permit) => supervisor.run_with_permit(permit),
                Mode::Adopting => Ok(supervisor.run_adopting()),
                Mode::Designated => Ok(supervisor.run()),
            };
            let _ = ended.send(result);
        })?;
    Ok(Start::Running(Running {
        handle,
        events: receive_events,
        ended: receive_ended,
        completion: Completion {
            worker: Some(worker),
            ..Completion::default()
        },
    }))
}

pub(crate) fn start_designated(
    target: LaunchTarget,
    config: SupervisorConfig,
    collaborators: Collaborators,
    permit: crate::successor::InitialPermit,
) -> io::Result<Start> {
    if permit.root() != target.storage_root()
        || !collaborators.session.is_active()
        || !matches!(
            crate::session::quit::read_quit_marker(target.storage_root()),
            crate::session::quit::QuitState::Absent
        )
    {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    let (events, receive) = mpsc::sync_channel(EVENT_QUEUE);
    spawn(
        Supervisor::new(config, target, collaborators, events),
        Mode::Designated,
        receive,
    )
}

pub fn start_reserved(
    target: LaunchTarget,
    config: SupervisorConfig,
    collaborators: Collaborators,
    claim: crate::session::claim::StartClaim,
) -> io::Result<Start> {
    let (events, receive) = mpsc::sync_channel(EVENT_QUEUE);
    spawn(
        Supervisor::new(config, target, collaborators, events),
        Mode::Reserved(crate::session::ownership::StartPermit::from_claim(claim)),
        receive,
    )
}

pub enum Start {
    Running(Running),
    Waiting(Role),
}

#[cfg(test)]
mod completion_tests {
    use super::*;
    use crate::supervision::supervisor::Effects;
    const STOPPED: Outcome = Outcome::Stopped {
        effects: Effects::Unknown,
    };

    #[test]
    fn terminal_report_waits_for_worker_and_preserves_unknown_effects() {
        let (send, ended) = mpsc::channel();
        let (published, ready) = mpsc::channel();
        let (release, gate) = mpsc::channel();
        let worker = thread::spawn(move || {
            send.send(Ok(STOPPED)).unwrap();
            published.send(()).unwrap();
            gate.recv_timeout(Duration::from_secs(5)).unwrap();
        });
        let mut completion = Completion {
            worker: Some(worker),
            ..Completion::default()
        };
        ready.recv_timeout(Duration::from_secs(5)).unwrap();
        assert!(completion.poll(&ended).unwrap().is_none());
        assert!(completion.terminal.is_some());
        let started = Instant::now();
        assert!(
            completion
                .wait(&ended, Duration::from_millis(10))
                .unwrap()
                .is_none()
        );
        assert!(started.elapsed() < Duration::from_secs(1));
        assert!(completion.worker.is_some());
        release.send(()).unwrap();
        assert_eq!(
            completion.wait(&ended, Duration::from_secs(5)).unwrap(),
            Some(STOPPED)
        );
        assert!(completion.worker.is_none());
        assert!(completion.poll(&ended).unwrap().is_none());
    }

    #[test]
    fn terminal_failure_and_disconnection_never_become_success() {
        for terminal_error in [false, true] {
            let (send, ended) = mpsc::channel();
            let worker = thread::spawn(move || {
                if terminal_error {
                    send.send(Err(io::Error::from_raw_os_error(47))).unwrap();
                }
            });
            let mut completion = Completion {
                worker: Some(worker),
                ..Completion::default()
            };
            let deadline = Instant::now() + Duration::from_secs(5);
            while !completion.worker.as_ref().unwrap().is_finished() {
                assert!(Instant::now() < deadline);
                thread::yield_now();
            }
            let first = completion.poll(&ended).unwrap_err();
            let second = completion.poll(&ended).unwrap_err();
            if terminal_error {
                let retained = |error: &io::Error| {
                    Arc::clone(
                        error
                            .get_ref()
                            .unwrap()
                            .downcast_ref::<Arc<io::Error>>()
                            .unwrap(),
                    )
                };
                let first = retained(&first);
                let second = retained(&second);
                assert_eq!(first.raw_os_error(), Some(47));
                assert!(Arc::ptr_eq(&first, &second));
            }
            assert!(!completion.delivered);
            assert!(completion.worker.is_none());
        }
    }

    #[test]
    fn panic_after_success_report_is_not_clean_completion() {
        let (send, ended) = mpsc::channel();
        let worker = thread::spawn(move || {
            send.send(Ok(STOPPED)).unwrap();
            panic!("fixture worker panic after reporting");
        });
        let mut completion = Completion {
            worker: Some(worker),
            ..Completion::default()
        };
        assert!(completion.wait(&ended, Duration::from_secs(5)).is_err());
        assert!(completion.poll(&ended).is_err());
        assert!(completion.terminal.is_some());
        assert!(!completion.delivered);
    }
}
