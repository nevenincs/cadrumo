use super::format::Level;
use cadrumo_application::{
    diagnostics::{
        Event, EventKind, HostOutcome,
        helper::HelperOutcome,
        service::{AgentRefusal, ServiceFact},
        lifecycle::{LifecycleFact, RuntimeExit, RuntimeReason, SupervisorOutcome},
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
            ServiceFact::AgentRefused { reason: AgentRefusal::SignedOut } => Level::Info,
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
            if event.status.as_ref().is_some_and(|s| s.exit_code != Some(0)) => Level::Error,
        EventKind::ChildTerminated => Level::Warning,
        EventKind::HelperTiming if event.status.as_ref().is_some_and(|s| s.exit_code.is_some_and(|code| code != 0)) => Level::Error,
        EventKind::HelperTiming => match event.helper_timing.map(|fact| fact.outcome) {
            Some(HelperOutcome::Completed) => Level::Debug,
            _ => Level::Error,
        },
        EventKind::StageCompleted if event.outcome == Some(HostOutcome::Unavailable) => Level::Warning,
        EventKind::StageStarted | EventKind::StageCompleted => Level::Debug,
        EventKind::ChildStarted | EventKind::ChildExited
            if matches!(event.role, Some(ProcessRole::SignIn | ProcessRole::ManagerDispatch | ProcessRole::Environment)) => Level::Debug,
        _ => Level::Info,
    }
}

fn lifecycle(fact: LifecycleFact) -> Level {
    use LifecycleFact::*;
    match fact {
        AdmissionRefused { .. } | InspectionRefused { .. } | LaunchFailed {} |
        BootRecordMismatch { .. } | HangDetected { .. } | TerminationFailed { .. } |
        TerminationUnconfirmed { .. } | ProcessInspectionFailed { .. } |
        EffectsUnknown { .. } | Failed { .. } => Level::Error,
        Exited { exit, .. } => match exit {
            RuntimeExit::Crash { .. } | RuntimeExit::LaunchFailure { .. } => Level::Error,
            RuntimeExit::Reason { reason: RuntimeReason::UnexpectedFailure | RuntimeReason::DrainWatchdog, .. } => Level::Error,
            RuntimeExit::ControlC {} | RuntimeExit::Terminated {} | RuntimeExit::Unknown {} => Level::Warning,
            _ => Level::Info,
        },
        SupervisorEnded { result: SupervisorOutcome::Failed { .. }, .. } => Level::Error,
        AnnouncementRefused { .. } | CommandRefused { .. } | ChannelClosed { .. } |
        IdleStopUnavailable { .. } | TerminationRequested { .. } | Terminated { .. } |
        RestartScheduled { .. } | Foreign { .. } | StoodDown { .. } |
        EventsDropped { .. } => Level::Warning,
        Waiting { .. } | RestartDeferred { .. } | Busy { .. } |
        BootRecordConfirmed { .. } | VersionReprobed {} => Level::Debug,
        _ => Level::Info,
    }
}
