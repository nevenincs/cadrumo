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
    sync::mpsc::{self, Receiver},
    thread::{self, JoinHandle},
};

pub struct Running {
    pub handle: SupervisorHandle,
    pub events: Receiver<Event>,
    pub ended: Receiver<io::Result<Outcome>>,
    worker: Option<JoinHandle<()>>,
}

impl Running {
    pub fn join(&mut self) -> io::Result<()> {
        if let Some(worker) = self.worker.take() {
            worker
                .join()
                .map_err(|_| io::Error::other("manager_supervisor_panicked"))?;
        }
        Ok(())
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
        worker: Some(worker),
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
