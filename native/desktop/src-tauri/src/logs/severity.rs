use super::format::Level;
use cadrumo_application::{
    diagnostics::{
        Event, EventKind, HostOutcome,
        helper::HelperOutcome,
        lifecycle::{LifecycleFact, RuntimeExit, RuntimeReason, SupervisorOutcome},
        service::{AgentRefusal, ServiceFact},
    },
    process::status::ProcessRole,
};

pub fn level(event: &Event) -> Level {
    if event.failure.is_some() || event.webview_failure.is_some() {
        return Level::Error;
    }
    if let Some(fact) = event.lifecycle {
        return lifecycle(fact);
    }
    if let Some(fact) = event.service {
        return match fact {
            ServiceFact::AgentRefused {
                reason: AgentRefusal::SignedOut,
            } => Level::Info,
            ServiceFact::AgentRefused { .. } | ServiceFact::AgentProtocolRefused {} => Level::Error,
            ServiceFact::AgentRetryScheduled { .. } => Level::Warning,
            ServiceFact::EnvironmentResolved { .. } => Level::Debug,
            _ => Level::Info,
        };
    }
    match event.kind {
        EventKind::Failure => Level::Error,
        EventKind::HostStopped if event.host_exit_code != Some(0) => Level::Error,
        EventKind::ChildExited
            if event
                .status
                .as_ref()
                .is_some_and(|s| s.exit_code != Some(0)) =>
        {
            Level::Error
        }
        EventKind::ChildTerminated => Level::Warning,
        EventKind::HelperTiming
            if event
                .status
                .as_ref()
                .is_some_and(|s| s.exit_code.is_some_and(|code| code != 0)) =>
        {
            Level::Error
        }
        EventKind::HelperTiming => match event.helper_timing.map(|fact| fact.outcome) {
            Some(HelperOutcome::Completed) => Level::Debug,
            _ => Level::Error,
        },
        EventKind::StageCompleted if event.outcome == Some(HostOutcome::Unavailable) => {
            Level::Warning
        }
        EventKind::StageStarted | EventKind::StageCompleted => Level::Debug,
        EventKind::ChildStarted | EventKind::ChildExited
            if matches!(
                event.role,
                Some(ProcessRole::SignIn | ProcessRole::ManagerDispatch | ProcessRole::Environment)
            ) =>
        {
            Level::Debug
        }
        _ => Level::Info,
    }
}

fn lifecycle(fact: LifecycleFact) -> Level {
    use LifecycleFact::*;
    match fact {
        AdmissionRefused { .. }
        | InspectionRefused { .. }
        | LaunchFailed {}
        | BootRecordMismatch { .. }
        | HangDetected { .. }
        | TerminationFailed { .. }
        | TerminationUnconfirmed { .. }
        | ProcessInspectionFailed { .. }
        | EffectsUnknown { .. }
        | Failed { .. } => Level::Error,
        Exited { exit, .. } => match exit {
            RuntimeExit::Crash { .. } | RuntimeExit::LaunchFailure { .. } => Level::Error,
            RuntimeExit::Reason {
                reason: RuntimeReason::UnexpectedFailure | RuntimeReason::DrainWatchdog,
                ..
            } => Level::Error,
            RuntimeExit::ControlC {} | RuntimeExit::Terminated {} | RuntimeExit::Unknown {} => {
                Level::Warning
            }
            _ => Level::Info,
        },
        SupervisorEnded {
            result: SupervisorOutcome::Failed { .. },
            ..
        } => Level::Error,
        AnnouncementRefused { .. }
        | CommandRefused { .. }
        | ChannelClosed { .. }
        | IdleStopUnavailable { .. }
        | TerminationRequested { .. }
        | Terminated { .. }
        | RestartScheduled { .. }
        | Foreign { .. }
        | StoodDown { .. }
        | EventsDropped { .. } => Level::Warning,
        Waiting { .. }
        | RestartDeferred { .. }
        | Busy { .. }
        | BootRecordConfirmed { .. }
        | VersionReprobed {} => Level::Debug,
        _ => Level::Info,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use cadrumo_application::diagnostics::{Diagnostics, HostStage};

    #[test]
    fn startup_detail_is_debug_and_process_failures_are_errors() {
        let diagnostics = Diagnostics::default();
        diagnostics.event(EventKind::HostStarted, None, None);
        diagnostics.host_event(EventKind::StageStarted, HostStage::Environment);
        diagnostics.host_outcome(HostStage::Environment, HostOutcome::Ready);
        let process = diagnostics.start(4200, ProcessRole::SignIn);
        diagnostics.finish(
            process,
            Some(7),
            cadrumo_application::process::status::ProcessPhase::Exited,
        );
        diagnostics.host_stopped(1);
        assert_eq!(
            diagnostics
                .snapshot(u64::MAX)
                .events
                .iter()
                .map(level)
                .collect::<Vec<_>>(),
            [
                Level::Info,
                Level::Debug,
                Level::Debug,
                Level::Debug,
                Level::Error,
                Level::Error
            ]
        );
    }

    #[test]
    fn runtime_crashes_do_not_inherit_the_stage_completed_level() {
        let diagnostics = Diagnostics::default();
        for (fact, expected) in [
            (
                LifecycleFact::Exited {
                    pid: 42,
                    exit: RuntimeExit::Crash { code: 0xc0000005 },
                    announced: None,
                },
                Level::Error,
            ),
            (
                LifecycleFact::RestartScheduled {
                    class: cadrumo_application::diagnostics::lifecycle::RestartClass::Unexpected,
                    delay_ms: 1000,
                },
                Level::Warning,
            ),
            (LifecycleFact::Ready { pid: 42 }, Level::Info),
            (LifecycleFact::BootRecordConfirmed { pid: 42 }, Level::Debug),
        ] {
            diagnostics.lifecycle(
                EventKind::StageCompleted,
                HostStage::Supervision,
                fact,
                None,
            );
            assert_eq!(
                level(diagnostics.snapshot(u64::MAX).events.last().unwrap()),
                expected
            );
        }
    }

    #[test]
    fn service_lifecycle_distinguishes_readiness_refusals_and_retry() {
        let diagnostics = Diagnostics::default();
        for (fact, expected) in [
            (
                ServiceFact::AgentReady {
                    generation: 1,
                    gateway_port: 4444,
                },
                Level::Info,
            ),
            (
                ServiceFact::AgentRefused {
                    reason: AgentRefusal::SignedOut,
                },
                Level::Info,
            ),
            (
                ServiceFact::AgentRefused {
                    reason: AgentRefusal::ServiceFailed,
                },
                Level::Error,
            ),
            (ServiceFact::AgentProtocolRefused {}, Level::Error),
            (
                ServiceFact::AgentRetryScheduled { delay_ms: 30000 },
                Level::Warning,
            ),
        ] {
            diagnostics.service(None, fact);
            assert_eq!(
                level(diagnostics.snapshot(u64::MAX).events.last().unwrap()),
                expected
            );
        }
    }
}
