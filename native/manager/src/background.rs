//! Lifetime of one admitted manager, independent of the Windows message pump.

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
    sync::{
        Arc,
        mpsc::{Receiver, TryRecvError},
    },
    time::Duration,
};

// A continuously replenished diagnostics queue must yield to Windows messages.
const EVENTS_PER_POLL: usize = 64;

pub struct Background {
    installed: InstalledRuntime,
    ownership: Ownership,
    activity: fn() -> Box<dyn SessionActivity>,
    running: Option<Running>,
    first: bool,
    suspended: bool,
    diagnostics: Arc<Diagnostics>,
    waiting: Option<LifecycleFact>,
}

impl Background {
    pub fn new(
        installed: InstalledRuntime,
        session: ManagerSession,
        activity: fn() -> Box<dyn SessionActivity>,
        diagnostics: Arc<Diagnostics>,
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
            first: true,
            suspended: false,
            diagnostics,
            waiting: None,
        }
    }

    pub fn poll(&mut self) -> io::Result<()> {
        if let Some(running) = &mut self.running {
            drain_events(running, &self.diagnostics, EVENTS_PER_POLL);
            match running.ended.try_recv() {
                Ok(result) => {
                    let joined = running.join();
                    drain_events(running, &self.diagnostics, EVENT_QUEUE);
                    self.running = None;
                    report_failure(&self.diagnostics, joined)?;
                    let outcome = report_failure(&self.diagnostics, result)?;
                    diagnostics::supervision_outcome(&self.diagnostics, outcome);
                    match outcome {
                        Outcome::Failed { .. } | Outcome::Foreign(_) | Outcome::StoodDown(_) => {
                            return Err(io::Error::other("manager_runtime_unavailable"));
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
        if self.suspended {
            return Ok(());
        }
        let initial = self.first.then_some(StartKind::Manual);
        self.first = false;
        let collaborators = Collaborators {
            session: (self.activity)(),
            probe: Box::new(self.installed.clone()),
            versions: Box::new(self.installed.clone()),
            stop_signal: Box::new(PlatformStopSignal::default()),
        };
        let started = startup::start(
            self.installed.target.clone(),
            SupervisorConfig::default(),
            collaborators,
            &mut self.ownership,
            initial,
        );
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
        self.suspended = false;
        self.diagnostics.lifecycle(
            EventKind::StageCompleted,
            HostStage::Shutdown,
            LifecycleFact::SessionEndCancelled {},
            None,
        );
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
        drain_events(running, diagnostics, EVENT_QUEUE);
        let _ = report_failure(diagnostics, joined);
        if let Ok(outcome) = report_failure(diagnostics, result) {
            diagnostics::supervision_outcome(diagnostics, outcome);
        }
        true
    } else {
        drain_events(running, diagnostics, EVENTS_PER_POLL);
        false
    }
}

fn drain_events(running: &Running, diagnostics: &Diagnostics, limit: usize) {
    record_events(&running.events, diagnostics, limit);
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

fn record_events(events: &Receiver<Event>, diagnostics: &Diagnostics, limit: usize) {
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
