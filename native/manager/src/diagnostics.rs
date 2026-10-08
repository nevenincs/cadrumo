//! Project supervision into the shared, closed diagnostic schema.
use crate::{
    contract::{LOG_BACKUPS, LOG_MAX_BYTES, MANAGER_LOG},
    installed::InspectionFailure,
    session::ownership::{Role, WaitReason},
    supervision::{
        adoption::ForeignReason,
        environment::ManagedLocations,
        exit::{ExitReason, RuntimeExit},
        protocol::LineRefusal,
        restart::RestartClass,
        stop::StopSignalError,
        supervisor::{Effects, Event, Outcome, StandDownReason, StopCause, StopPath},
    },
};
use cadrumo_application::{
    diagnostics::{Diagnostics, EventKind, HostStage, lifecycle as fact},
    error::application::{ApplicationError, ErrorCode, Operation},
    value::RelativePath,
};
use std::{io, path::Path};

pub fn configure(locations: &ManagedLocations, diagnostics: &Diagnostics) {
    let result = configure_root(locations.storage_root(), diagnostics);
    if let Err(error) = result {
        diagnostics.host_failure(HostStage::Storage, error);
    }
}

fn configure_root(
    root: &Path,
    diagnostics: &Diagnostics,
) -> cadrumo_application::error::application::Result<()> {
    let member = RelativePath::new(MANAGER_LOG).map_err(|error| {
        ApplicationError::new(ErrorCode::LogUnavailable, Operation::Logging).caused_by(error)
    })?;
    diagnostics.configure_file(&member.under(root), LOG_MAX_BYTES, LOG_BACKUPS)
}

/// Preserve the stage and safe native cause without formatting its contents.
pub fn stage<T>(
    diagnostics: &Diagnostics,
    stage: HostStage,
    code: ErrorCode,
    operation: Operation,
    run: impl FnOnce() -> io::Result<T>,
) -> io::Result<T> {
    diagnostics.host_event(EventKind::StageStarted, stage);
    match run() {
        Ok(value) => {
            diagnostics.host_event(EventKind::StageCompleted, stage);
            Ok(value)
        }
        Err(error) => {
            let safe = ApplicationError::new(code, operation).caused_by(error);
            diagnostics.host_failure(stage, safe.clone());
            Err(io::Error::other(safe))
        }
    }
}

pub fn inspection_failed(diagnostics: &Diagnostics, error: InspectionFailure) -> io::Error {
    let refusal = error.refusal;
    diagnostics.lifecycle(
        EventKind::Failure,
        HostStage::Package,
        fact::LifecycleFact::InspectionRefused { reason: refusal },
        Some(
            ApplicationError::new(ErrorCode::PackageUnavailable, Operation::Package)
                .caused_by(error),
        ),
    );
    io::Error::other("manager_package_refused")
}

pub fn supervision_event(diagnostics: &Diagnostics, event: &Event) {
    let (fact, failure) = match event {
        Event::RestartDeferred(reason) => (
            fact::LifecycleFact::RestartDeferred {
                reason: wait_reason(*reason),
            },
            wait_failure(*reason),
        ),
        Event::OwnershipChanged => (fact::LifecycleFact::OwnershipChanged {}, None),
        Event::Launched { pid, .. } => (fact::LifecycleFact::Launched { pid: *pid }, None),
        Event::LaunchFailed { kind } => (
            fact::LifecycleFact::LaunchFailed {},
            Some(
                ApplicationError::new(ErrorCode::SpawnFailed, Operation::Manager)
                    .caused_by(io::Error::from(*kind)),
            ),
        ),
        Event::Ready { pid, .. } => (fact::LifecycleFact::Ready { pid: *pid }, None),
        Event::BootRecordConfirmed { pid } => {
            (fact::LifecycleFact::BootRecordConfirmed { pid: *pid }, None)
        }
        Event::BootRecordMismatch { pid } => {
            (fact::LifecycleFact::BootRecordMismatch { pid: *pid }, None)
        }
        Event::AnnouncementRefused(reason) => (
            fact::LifecycleFact::AnnouncementRefused {
                reason: line_refusal(*reason),
            },
            None,
        ),
        Event::CommandRefused(reason) => (
            fact::LifecycleFact::CommandRefused {
                reason: line_refusal(*reason),
            },
            None,
        ),
        Event::ChannelClosed { pid } => (fact::LifecycleFact::ChannelClosed { pid: *pid }, None),
        Event::Busy { pid } => (fact::LifecycleFact::Busy { pid: *pid }, None),
        Event::IdleStopUnavailable { pid } => {
            (fact::LifecycleFact::IdleStopUnavailable { pid: *pid }, None)
        }
        Event::HangDetected { pid, ready } => (
            fact::LifecycleFact::HangDetected {
                pid: *pid,
                ready: *ready,
            },
            None,
        ),
        Event::StopRequested { pid, cause, path } => (
            fact::LifecycleFact::StopRequested {
                pid: *pid,
                cause: stop_cause(*cause),
                path: stop_path(*path),
            },
            None,
        ),
        Event::Terminated { pid } => (fact::LifecycleFact::Terminated { pid: *pid }, None),
        Event::TerminationRequested { pid } => (
            fact::LifecycleFact::TerminationRequested { pid: *pid },
            None,
        ),
        Event::TerminationFailed { pid, kind, os_code } => (
            fact::LifecycleFact::TerminationFailed { pid: *pid },
            Some(native_failure(ErrorCode::CleanupFailed, *kind, *os_code)),
        ),
        Event::TerminationUnconfirmed { pid } => (
            fact::LifecycleFact::TerminationUnconfirmed { pid: *pid },
            Some(native_failure(
                ErrorCode::CleanupFailed,
                io::ErrorKind::TimedOut,
                None,
            )),
        ),
        Event::ProcessInspectionFailed { pid, kind, os_code } => (
            fact::LifecycleFact::ProcessInspectionFailed { pid: *pid },
            Some(native_failure(ErrorCode::ReadFailed, *kind, *os_code)),
        ),
        Event::EffectsUnknown { pid } => (fact::LifecycleFact::EffectsUnknown { pid: *pid }, None),
        Event::Exited {
            pid,
            exit,
            announced,
        } => (
            fact::LifecycleFact::Exited {
                pid: *pid,
                exit: runtime_exit(*exit),
                announced: announced.map(runtime_reason),
            },
            None,
        ),
        Event::VersionReprobed { .. } => (fact::LifecycleFact::VersionReprobed {}, None),
        Event::RestartScheduled { class, delay } => (
            fact::LifecycleFact::RestartScheduled {
                class: restart_class(*class),
                delay_ms: u64::try_from(delay.as_millis()).unwrap_or(u64::MAX),
            },
            None,
        ),
        Event::Adopted { pid, .. } => (fact::LifecycleFact::Adopted { pid: *pid }, None),
        Event::Foreign(reason) => (
            fact::LifecycleFact::Foreign {
                reason: foreign_reason(*reason),
            },
            None,
        ),
        Event::StoodDown(reason) => (
            fact::LifecycleFact::StoodDown {
                reason: stand_down_reason(*reason),
            },
            None,
        ),
        Event::AwaitingActiveSession => (fact::LifecycleFact::AwaitingActiveSession {}, None),
        Event::Failed { last } => (
            fact::LifecycleFact::Failed {
                last: restart_class(*last),
            },
            None,
        ),
    };
    diagnostics.lifecycle(
        if failure.is_some()
            || matches!(
                event,
                Event::BootRecordMismatch { .. }
                    | Event::AnnouncementRefused(_)
                    | Event::CommandRefused(_)
                    | Event::HangDetected { .. }
                    | Event::EffectsUnknown { .. }
                    | Event::Foreign(_)
                    | Event::StoodDown(_)
                    | Event::Failed { .. }
            )
        {
            EventKind::Failure
        } else if matches!(event, Event::TerminationRequested { .. }) {
            EventKind::StageStarted
        } else {
            EventKind::StageCompleted
        },
        HostStage::Supervision,
        fact,
        failure,
    );
}

fn native_failure(code: ErrorCode, kind: io::ErrorKind, os_code: Option<i32>) -> ApplicationError {
    let error = os_code
        .map(io::Error::from_raw_os_error)
        .unwrap_or_else(|| io::Error::from(kind));
    ApplicationError::new(code, Operation::Manager).caused_by(error)
}

pub fn supervision_outcome(diagnostics: &Diagnostics, outcome: Outcome) {
    let result = match outcome {
        Outcome::RestartDeferred(reason) => fact::SupervisorOutcome::RestartDeferred {
            reason: wait_reason(reason),
        },
        Outcome::OwnershipChanged => fact::SupervisorOutcome::OwnershipChanged {},
        Outcome::Stopped { effects } => fact::SupervisorOutcome::Stopped {
            effects: effects_fact(effects),
        },
        Outcome::StoodDown(reason) => fact::SupervisorOutcome::StoodDown {
            reason: stand_down_reason(reason),
        },
        Outcome::Foreign(reason) => fact::SupervisorOutcome::Foreign {
            reason: foreign_reason(reason),
        },
        Outcome::AwaitingActiveSession => fact::SupervisorOutcome::AwaitingActiveSession {},
        Outcome::Failed { last } => fact::SupervisorOutcome::Failed {
            last: restart_class(last),
        },
    };
    diagnostics.lifecycle(
        if matches!(
            outcome,
            Outcome::Foreign(_) | Outcome::StoodDown(_) | Outcome::Failed { .. }
        ) {
            EventKind::Failure
        } else {
            EventKind::StageCompleted
        },
        HostStage::Supervision,
        fact::LifecycleFact::SupervisorEnded { result },
        None,
    );
}

pub fn waiting(role: &Role) -> Option<fact::LifecycleFact> {
    match role {
        Role::Observe(runtime) => Some(fact::LifecycleFact::Observing { pid: runtime.pid() }),
        Role::Wait(reason) => Some(fact::LifecycleFact::Waiting {
            reason: wait_reason(*reason),
        }),
        Role::OwnSession { .. } | Role::Start(_) => None,
    }
}

pub fn wait_failure(reason: WaitReason) -> Option<ApplicationError> {
    if let WaitReason::ClaimUnavailable(kind) = reason {
        Some(
            ApplicationError::new(ErrorCode::ManagerUnavailable, Operation::Manager)
                .caused_by(io::Error::from(kind)),
        )
    } else {
        None
    }
}

fn runtime_exit(exit: RuntimeExit) -> fact::RuntimeExit {
    match exit {
        RuntimeExit::Reason(reason) => fact::RuntimeExit::Reason {
            reason: runtime_reason(reason),
            code: reason.code(),
        },
        RuntimeExit::Zero => fact::RuntimeExit::Zero {},
        RuntimeExit::ControlC => fact::RuntimeExit::ControlC {},
        RuntimeExit::LaunchFailure(code) => fact::RuntimeExit::LaunchFailure { code },
        RuntimeExit::Crash(code) => fact::RuntimeExit::Crash { code },
        RuntimeExit::Terminated => fact::RuntimeExit::Terminated {},
        RuntimeExit::Unknown => fact::RuntimeExit::Unknown {},
    }
}

fn stop_path(path: StopPath) -> fact::StopPath {
    match path {
        StopPath::Channel => fact::StopPath::Channel {},
        StopPath::Signal => fact::StopPath::Signal {},
        StopPath::Undelivered(refusal) => fact::StopPath::Undelivered {
            refusal: stop_signal_refusal(refusal),
        },
    }
}

macro_rules! enum_projection {
    ($function:ident, $source:ident, $destination:ident, $($variant:ident),+ $(,)?) => {
        fn $function(value: $source) -> fact::$destination {
            match value { $($source::$variant => fact::$destination::$variant,)+ }
        }
    };
}
enum_projection!(
    foreign_reason,
    ForeignReason,
    ForeignReason,
    RecordAbsent,
    RecordUnreadable,
    StaleRecord,
    IdentityMismatch,
    Uninspectable,
    OtherSession,
    Elevated,
    DevelopmentAdmission,
    NotInstalled,
    VersionMismatch,
    FailedVersion
);
enum_projection!(
    stand_down_reason,
    StandDownReason,
    StandDownReason,
    RootMismatch,
    ElevatedTokenRefused,
    VersionMismatch
);
enum_projection!(
    restart_class,
    RestartClass,
    RestartClass,
    Unexpected,
    LaunchFailure,
    Hang,
    OutsideStop,
    WitnessLoss
);
enum_projection!(
    stop_cause,
    StopCause,
    StopCause,
    Defect,
    Hang,
    IdleRequested,
    Requested,
    SessionEnd
);
enum_projection!(
    stop_signal_refusal,
    StopSignalError,
    StopSignalRefusal,
    NotRunning,
    Unsupported,
    AlreadyAttached,
    NoConsole,
    Unconfirmed,
    Failed
);
enum_projection!(
    runtime_reason,
    ExitReason,
    RuntimeReason,
    SupervisorStop,
    SignalStop,
    SessionEndSettle,
    OwnerBusy,
    RootMismatch,
    VersionMismatch,
    LoginWitnessLoss,
    DrainWatchdog,
    ElevatedTokenRefused,
    UnexpectedFailure
);
enum_projection!(effects_fact, Effects, Effects, Settled, Unknown);
enum_projection!(line_refusal, LineRefusal, LineRefusal, Malformed, Oversized);

fn wait_reason(reason: WaitReason) -> fact::WaitReason {
    match reason {
        WaitReason::Quit => fact::WaitReason::Quit,
        WaitReason::QuitUnreadable => fact::WaitReason::QuitUnreadable,
        WaitReason::Inactive => fact::WaitReason::Inactive,
        WaitReason::StartingElsewhere => fact::WaitReason::StartingElsewhere,
        WaitReason::ClaimUnavailable(_) => fact::WaitReason::ClaimUnavailable,
    }
}

#[cfg(any(windows, test))]
pub fn admission_refused(diagnostics: &Diagnostics, reason: crate::admission::Refusal) {
    use crate::admission::Refusal;
    let reason = match reason {
        Refusal::SessionUnavailable => fact::AdmissionRefusal::SessionUnavailable,
        Refusal::SessionZero => fact::AdmissionRefusal::SessionZero,
        Refusal::ElevationUnavailable => fact::AdmissionRefusal::ElevationUnavailable,
        Refusal::FullyElevated => fact::AdmissionRefusal::FullyElevated,
        Refusal::DesktopUnavailable => fact::AdmissionRefusal::DesktopUnavailable,
    };
    diagnostics.lifecycle(
        EventKind::Failure,
        HostStage::Admission,
        fact::LifecycleFact::AdmissionRefused { reason },
        None,
    );
}
