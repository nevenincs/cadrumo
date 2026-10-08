//! Lifetime of one admitted manager, independent of the native event loop.

use crate::{
    diagnostics,
    installed::InstalledRuntime,
    session::{
        ManagerSession,
        ownership::{BootRecordLocator, Ownership, StartKind},
    },
    startup::{self, Running, Start},
    supervision::{
        stop::PlatformStopSignal,
        supervisor::{
            Collaborators, EVENT_QUEUE, Event, Outcome, Request, SessionActivity, SupervisorConfig,
        },
    },
};
use cadrumo_application::{
    diagnostics::{Diagnostics, EventKind, HostStage, lifecycle::LifecycleFact},
    error::application::{ApplicationError, ErrorCode, Operation},
};
use std::{
    io,
    sync::{Arc, mpsc::TryRecvError},
    time::Duration,
};

// A continuously replenished diagnostics queue must yield to native events.
const EVENTS_PER_POLL: usize = 64;

pub struct Background {
    installed: InstalledRuntime,
    ownership: Ownership,
    activity: fn() -> Box<dyn SessionActivity>,
    running: Option<Running>,
    initial: Option<StartKind>,
    blocked: bool,
    quitting: bool,
    suspended: bool,
    diagnostics: Arc<Diagnostics>,
    waiting: Option<LifecycleFact>,
    installation_watch: Option<Box<dyn crate::lifecycle::RemovalObservation>>,
    observation: Observation,
    cutover_pending: bool,
    update_failed: bool,
    reserved: Option<crate::session::claim::StartClaim>,
    designated: Option<crate::successor::InitialPermit>,
    reporter: Option<crate::successor::Reporter>,
}

impl Background {
    pub fn new(
        installed: InstalledRuntime,
        session: ManagerSession,
        activity: fn() -> Box<dyn SessionActivity>,
        diagnostics: Arc<Diagnostics>,
        initial: StartKind,
    ) -> Self {
        let ownership = Ownership::new(
            installed.target.storage_root().to_path_buf(),
            session,
            activity(),
            Box::new(BootRecordLocator::new(installed.target.storage_root())),
        );
        Self {
            installed,
            ownership,
            activity,
            running: None,
            initial: Some(initial),
            blocked: false,
            quitting: false,
            suspended: false,
            diagnostics,
            waiting: None,
            installation_watch: None,
            observation: Observation::default(),
            cutover_pending: false,
            update_failed: false,
            reserved: None,
            designated: None,
            reporter: None,
        }
    }

    pub fn designated(
        &mut self,
        permit: crate::successor::InitialPermit,
        reporter: crate::successor::Reporter,
    ) {
        self.designated = Some(permit);
        self.reporter = Some(reporter);
    }
    pub fn storage_root(&self) -> &std::path::Path {
        self.installed.target.storage_root()
    }
    pub fn stopping(&self) -> bool {
        self.quitting || self.suspended
    }
    pub fn can_cutover(&self) -> bool {
        !self.quitting
            && !self.suspended
            && self.reporter.is_none()
            && ((self.running.is_some() && self.observation.ready && self.observation.confirmed)
                || (self.running.is_none()
                    && self.blocked
                    && self.observation.pid.is_some_and(|pid| {
                        matches!(
                            crate::supervision::process::open_process(pid),
                            Err(crate::supervision::process::InspectError::NotRunning)
                        )
                    })))
    }
    pub fn begin_cutover(&mut self) -> io::Result<Option<crate::session::claim::StartClaim>> {
        if !self.can_cutover() {
            return Ok(None);
        }
        let Some(claim) =
            crate::session::claim::StartClaim::take(self.storage_root(), Duration::ZERO)?
        else {
            return Ok(None);
        };
        if !(self.activity)().is_active()
            || !matches!(
                crate::session::quit::read_quit_marker(self.storage_root()),
                crate::session::quit::QuitState::Absent
            )
        {
            return Ok(None);
        }
        if let Some(running) = &self.running {
            if !running.handle.request(Request::StopIfIdle) {
                return Err(io::ErrorKind::WouldBlock.into());
            }
        } else {
            use crate::session::ownership::{Located, RuntimeLocator};
            if !matches!(
                BootRecordLocator::new(self.storage_root()).locate(),
                Located::Nothing
            ) {
                return Ok(None);
            }
        }
        self.cutover_pending = true;
        Ok(Some(claim))
    }
    pub fn idle_stopped(&self) -> bool {
        self.cutover_pending && self.running.is_none()
    }
    pub fn retry_idle(&self) {
        if self.cutover_pending
            && let Some(running) = &self.running
        {
            running.handle.request(Request::StopIfIdle);
        }
    }
    pub fn abandon_cutover(&mut self) {
        self.cutover_pending = false;
    }
    pub fn rollback(&mut self, claim: crate::session::claim::StartClaim) {
        self.cutover_pending = false;
        self.update_failed = true;
        self.blocked = false;
        self.reserved = Some(claim);
    }
    pub fn watch_installation(
        &mut self,
        observation: Box<dyn crate::lifecycle::RemovalObservation>,
    ) {
        self.installation_watch = Some(observation);
    }
    /// Confirmed native registration removal stops only this manager's
    /// owned runtime, without recording a user Quit preference or deleting files.
    fn uninstall(&mut self) -> io::Result<()> {
        if let Some(running) = &self.running
            && !running.handle.request(Request::Stop)
        {
            return Err(io::ErrorKind::WouldBlock.into());
        }
        self.quitting = true;
        self.suspended = true;
        Ok(())
    }
    pub fn poll(&mut self) -> io::Result<()> {
        if let Some(result) = self.reporter.as_ref().and_then(|reporter| reporter.poll()) {
            self.reporter = None;
            if matches!(result, crate::successor::ReportResult::Rejected) {
                self.uninstall()?;
            }
        }
        if !self.quitting
            && self
                .installation_watch
                .as_mut()
                .is_some_and(|watch| watch.removed())
        {
            self.uninstall()?;
        }
        if let Some(running) = &mut self.running {
            drain_events(
                running,
                &self.diagnostics,
                EVENTS_PER_POLL,
                Some(&mut self.observation),
            );
            self.observation.report(self.reporter.as_ref())?;
            match running.ended.try_recv() {
                Ok(result) => {
                    let joined = running.join();
                    drain_events(
                        running,
                        &self.diagnostics,
                        EVENT_QUEUE,
                        Some(&mut self.observation),
                    );
                    self.running = None;
                    report_failure(&self.diagnostics, joined)?;
                    let outcome = report_failure(&self.diagnostics, result)?;
                    diagnostics::supervision_outcome(&self.diagnostics, outcome);
                    match outcome {
                        Outcome::Failed { .. } | Outcome::Foreign(_) | Outcome::StoodDown(_) => {
                            self.blocked = true;
                            return Ok(());
                        }
                        _ => {}
                    }
                }
                Err(TryRecvError::Disconnected) => {
                    self.diagnostics.host_failure(
                        HostStage::Supervision,
                        ApplicationError::new(ErrorCode::ManagerUnavailable, Operation::Manager),
                    );
                    return Err(io::Error::other("manager_supervisor_lost"));
                }
                Err(TryRecvError::Empty) => return Ok(()),
            }
        }
        if self.suspended || self.blocked || self.quitting || self.cutover_pending {
            return Ok(());
        }
        let initial = self.initial.take();
        let collaborators = Collaborators {
            session: (self.activity)(),
            probe: Box::new(self.installed.clone()),
            versions: Box::new(self.installed.clone()),
            stop_signal: Box::new(PlatformStopSignal::default()),
        };
        self.observation = Observation::default();
        let started = if let Some(permit) = self.designated.take() {
            startup::start_designated(
                self.installed.target.clone(),
                SupervisorConfig::default(),
                collaborators,
                permit,
            )
        } else if let Some(claim) = self.reserved.take() {
            startup::start_reserved(
                self.installed.target.clone(),
                SupervisorConfig::default(),
                collaborators,
                claim,
            )
        } else {
            startup::start(
                self.installed.target.clone(),
                SupervisorConfig::default(),
                collaborators,
                &mut self.ownership,
                initial,
            )
        };
        match report_failure(&self.diagnostics, started)? {
            Start::Running(running) => {
                self.diagnostics.lifecycle(
                    EventKind::StageStarted,
                    HostStage::Supervision,
                    LifecycleFact::SupervisorStarted {},
                    None,
                );
                self.waiting = None;
                self.running = Some(running);
            }
            Start::Waiting(role) => {
                let fact = diagnostics::waiting(&role);
                if fact != self.waiting {
                    if let Some(fact) = fact {
                        let failure = match role {
                            crate::session::ownership::Role::Wait(reason) => {
                                diagnostics::wait_failure(reason)
                            }
                            _ => None,
                        };
                        self.diagnostics.lifecycle(
                            EventKind::StageCompleted,
                            HostStage::Supervision,
                            fact,
                            failure,
                        );
                    }
                    self.waiting = fact;
                }
            }
        }
        Ok(())
    }

    /// A client asks only for reassessment; no running process is interrupted.
    pub fn retry(&mut self) -> io::Result<()> {
        if self.quitting || self.suspended {
            return Err(io::ErrorKind::WouldBlock.into());
        }
        crate::failed_versions::FailedVersions::retry(self.installed.target.storage_root())?;
        self.blocked = false;
        self.update_failed = false;
        self.poll()
    }

    /// Called after the tray's explicit interruption warning. Normal supervisor
    /// stop/drain completes before the next manual ownership assessment.
    pub fn restart(&mut self) -> io::Result<()> {
        if self.quitting || self.suspended {
            return Err(io::ErrorKind::WouldBlock.into());
        }
        if let Some(running) = &self.running
            && !running.handle.request(Request::Stop)
        {
            return Err(io::ErrorKind::WouldBlock.into());
        }
        self.blocked = false;
        self.initial = Some(StartKind::Manual);
        Ok(())
    }

    /// Suppress automatic starts before asking only our owned supervisor to stop.
    pub fn quit(&mut self) -> io::Result<()> {
        self.ownership.record_quit()?;
        if let Some(running) = &self.running
            && !running.handle.request(Request::Stop)
        {
            return Err(io::ErrorKind::WouldBlock.into());
        }
        self.quitting = true;
        self.suspended = true;
        Ok(())
    }

    pub fn quit_completed(&self) -> bool {
        self.quitting && self.running.is_none()
    }

    pub fn status(&self) -> &'static str {
        if self.quitting || self.suspended {
            return "stopping";
        }
        if self.update_failed {
            return "update_failed";
        }
        if self.blocked {
            return "unavailable";
        }
        if self.waiting.is_some() {
            return "waiting";
        }
        for event in self.diagnostics.snapshot(u64::MAX).events.iter().rev() {
            match event.lifecycle {
                Some(LifecycleFact::Ready { .. }) => return "running",
                Some(
                    LifecycleFact::SupervisorStarted { .. }
                    | LifecycleFact::Launched { .. }
                    | LifecycleFact::RestartScheduled { .. },
                ) => return "starting",
                Some(LifecycleFact::StopRequested { .. }) => return "stopping",
                Some(
                    LifecycleFact::HangDetected { .. }
                    | LifecycleFact::Exited { .. }
                    | LifecycleFact::ChannelClosed { .. }
                    | LifecycleFact::Failed { .. },
                ) => return "unavailable",
                _ => {}
            }
        }
        "waiting"
    }

    pub fn session_end(&mut self) {
        self.suspended = true;
        if let Some(running) = &mut self.running {
            if settle_session(running, &self.diagnostics, Duration::from_millis(3500)) {
                self.running = None;
            }
        } else {
            self.diagnostics.lifecycle(
                EventKind::StageStarted,
                HostStage::Shutdown,
                LifecycleFact::SessionEndRequested {},
                None,
            );
        }
    }

    pub fn cancel_session_end(&mut self) {
        // A still-settling supervisor must exit before a fresh one may start.
        self.suspended = self.quitting;
        self.diagnostics.lifecycle(
            EventKind::StageCompleted,
            HostStage::Shutdown,
            LifecycleFact::SessionEndCancelled {},
            None,
        );
    }
}

#[derive(Default)]
struct Observation {
    pid: Option<u32>,
    ready: bool,
    confirmed: bool,
    reported_launch: bool,
    reported_ready: bool,
}
impl Observation {
    fn observe(&mut self, event: &Event) {
        match event {
            Event::Launched { pid, .. } => {
                *self = Self {
                    pid: Some(*pid),
                    ..Self::default()
                };
            }
            Event::Ready { pid, .. } if self.pid == Some(*pid) => self.ready = true,
            Event::BootRecordConfirmed { pid } if self.pid == Some(*pid) => self.confirmed = true,
            _ => {}
        }
    }
    fn report(&mut self, reporter: Option<&crate::successor::Reporter>) -> io::Result<()> {
        if let Some(reporter) = reporter
            && let Some(pid) = self.pid
        {
            if !self.reported_launch {
                reporter.launched(pid)?;
                self.reported_launch = true;
            }
            if self.ready && self.confirmed && !self.reported_ready {
                reporter.ready(pid)?;
                self.reported_ready = true;
            }
        }
        Ok(())
    }
}

/// Publish restart suppression and settle before any diagnostic file I/O.
/// False retains the running supervisor so cleanup ownership survives the bound.
pub fn settle_session(running: &mut Running, diagnostics: &Diagnostics, bound: Duration) -> bool {
    running.handle.request(Request::SessionEnd);
    let ended = running.ended.recv_timeout(bound);
    diagnostics.lifecycle(
        EventKind::StageStarted,
        HostStage::Shutdown,
        LifecycleFact::SessionEndRequested {},
        None,
    );
    if let Ok(result) = ended {
        let joined = running.join();
        drain_events(running, diagnostics, EVENT_QUEUE, None);
        let _ = report_failure(diagnostics, joined);
        if let Ok(outcome) = report_failure(diagnostics, result) {
            diagnostics::supervision_outcome(diagnostics, outcome);
        }
        true
    } else {
        drain_events(running, diagnostics, EVENTS_PER_POLL, None);
        false
    }
}

fn drain_events(
    running: &Running,
    diagnostics: &Diagnostics,
    limit: usize,
    mut observation: Option<&mut Observation>,
) {
    for event in running.events.try_iter().take(limit) {
        if let Some(observation) = &mut observation {
            observation.observe(&event);
        }
        diagnostics::supervision_event(diagnostics, &event);
    }
    let count = running.handle.take_dropped_events();
    if count > 0 {
        diagnostics.lifecycle(
            EventKind::Failure,
            HostStage::Supervision,
            LifecycleFact::EventsDropped { count },
            Some(ApplicationError::new(
                ErrorCode::OutputLimit,
                Operation::Manager,
            )),
        );
    }
}

#[cfg(test)]
fn record_events(
    events: &std::sync::mpsc::Receiver<Event>,
    diagnostics: &Diagnostics,
    limit: usize,
) {
    for event in events.try_iter().take(limit) {
        diagnostics::supervision_event(diagnostics, &event);
    }
}

fn report_failure<T>(diagnostics: &Diagnostics, result: io::Result<T>) -> io::Result<T> {
    result.map_err(|error| {
        let safe = ApplicationError::new(ErrorCode::ManagerUnavailable, Operation::Manager)
            .caused_by(error);
        diagnostics.host_failure(HostStage::Supervision, safe.clone());
        io::Error::other(safe)
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use cadrumo_application::diagnostics::DiagnosticSource;
    use std::sync::mpsc;

    #[test]
    fn polling_leaves_backlog_for_later_messages_and_final_drain_finishes_it() {
        let (send, receive) = mpsc::sync_channel(EVENT_QUEUE);
        for pid in 1..=512 {
            send.try_send(Event::Ready {
                pid,
                boot_id: "opaque-boot".into(),
            })
            .unwrap();
        }
        let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
        record_events(&receive, &diagnostics, EVENTS_PER_POLL);
        let first = diagnostics.snapshot(u64::MAX);
        assert_eq!(first.events.len(), 64);
        assert_eq!(
            first.events.last().unwrap().lifecycle,
            Some(LifecycleFact::Ready { pid: 64 })
        );

        // A producer can replenish the queue; a second poll still yields.
        for pid in 513..=576 {
            send.try_send(Event::Ready {
                pid,
                boot_id: "opaque-boot".into(),
            })
            .unwrap();
        }
        record_events(&receive, &diagnostics, EVENTS_PER_POLL);
        assert_eq!(diagnostics.snapshot(u64::MAX).events.len(), 128);
        drop(send);
        record_events(&receive, &diagnostics, EVENT_QUEUE);
        assert!(matches!(
            receive.try_recv(),
            Err(mpsc::TryRecvError::Disconnected)
        ));
        let final_events = diagnostics.snapshot(u64::MAX).events;
        assert_eq!(
            final_events.last().unwrap().lifecycle,
            Some(LifecycleFact::Ready { pid: 576 })
        );
    }
}
