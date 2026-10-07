//! Admit persisted manager events through the native diagnostics schema.
use super::{host, record::Entry};
use cadrumo_application::{
    diagnostics::{
        DiagnosticSource, Event, EventKind, HostOutcome, HostStage,
        lifecycle::{LifecycleFact, RuntimeExit, StopPath, SupervisorOutcome},
    },
    error::application::{ApplicationError, ErrorCode, Operation},
    process::status::{ProcessPhase, ProcessRole, ProcessStatus},
};
use serde::{Deserialize, Serialize, de::IgnoredAny};
use serde_json::Value;
use std::collections::BTreeMap;

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct WireEvent {
    sequence: u64,
    source: DiagnosticSource,
    timestamp_ms: u64,
    host_pid: u32,
    kind: EventKind,
    process: Option<u64>,
    failure: Option<WireFailure>,
    status: Option<WireStatus>,
    stage: Option<HostStage>,
    role: Option<ProcessRole>,
    outcome: Option<HostOutcome>,
    host_exit_code: Option<i32>,
    lifecycle: Option<LifecycleFact>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct WireFailure {
    code: ErrorCode,
    operation: Operation,
    // Only the catalogue's text may reach the view, even if a file was edited.
    #[serde(rename = "message")]
    _message: IgnoredAny,
    io_kind: Option<IoKind>,
    os_code: Option<i32>,
}

#[derive(Deserialize, Serialize)]
enum IoKind {
    NotFound,
    PermissionDenied,
    ConnectionRefused,
    ConnectionReset,
    HostUnreachable,
    NetworkUnreachable,
    ConnectionAborted,
    NotConnected,
    AddrInUse,
    AddrNotAvailable,
    NetworkDown,
    BrokenPipe,
    AlreadyExists,
    WouldBlock,
    NotADirectory,
    IsADirectory,
    DirectoryNotEmpty,
    ReadOnlyFilesystem,
    FilesystemLoop,
    StaleNetworkFileHandle,
    InvalidInput,
    InvalidData,
    TimedOut,
    WriteZero,
    StorageFull,
    NotSeekable,
    QuotaExceeded,
    FileTooLarge,
    ResourceBusy,
    ExecutableFileBusy,
    Deadlock,
    CrossesDevices,
    TooManyLinks,
    InvalidFilename,
    ArgumentListTooLong,
    Interrupted,
    Unsupported,
    UnexpectedEof,
    OutOfMemory,
    InProgress,
    Other,
    Uncategorized,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct WireStatus {
    id: u64,
    pid: u32,
    role: ProcessRole,
    phase: ProcessPhase,
    started_ms: u64,
    finished_ms: Option<u64>,
    exit_code: Option<i32>,
    stdout_bytes: u64,
    stderr_bytes: u64,
    terminal_bytes: u64,
}

impl From<WireStatus> for ProcessStatus {
    fn from(status: WireStatus) -> Self {
        Self {
            id: status.id,
            pid: status.pid,
            role: status.role,
            phase: status.phase,
            started_ms: status.started_ms,
            finished_ms: status.finished_ms,
            exit_code: status.exit_code,
            stdout_bytes: status.stdout_bytes,
            stderr_bytes: status.stderr_bytes,
            terminal_bytes: status.terminal_bytes,
        }
    }
}

pub(super) fn parse(line: &[u8]) -> Option<Entry> {
    let wire: WireEvent = serde_json::from_slice(line).ok()?;
    if wire.source != DiagnosticSource::Manager {
        return None;
    }
    let io_kind = wire
        .failure
        .as_ref()
        .and_then(|failure| failure.io_kind.as_ref());
    let failure = wire.failure.as_ref().map(|failure| {
        let mut error = ApplicationError::new(failure.code, failure.operation);
        error.os_code = failure.os_code;
        error
    });
    let mut entry = host::entry(&Event {
        sequence: wire.sequence,
        source: wire.source,
        timestamp_ms: wire.timestamp_ms,
        host_pid: wire.host_pid,
        kind: wire.kind,
        process: wire.process,
        failure,
        status: wire.status.map(Into::into),
        stage: wire.stage,
        role: wire.role,
        outcome: wire.outcome,
        host_exit_code: wire.host_exit_code,
        lifecycle: wire.lifecycle,
        webview_failure: None,
    });
    if let Some(kind) = io_kind {
        field(&mut entry.context, "io_kind", kind);
    }
    Some(entry)
}

fn field(context: &mut BTreeMap<String, Value>, name: &str, value: impl Serialize) {
    if let Ok(value) = serde_json::to_value(value) {
        context.insert(name.to_owned(), value);
    }
}

/// Only enum tokens and numeric/bool facts from admitted native variants.
pub(super) fn lifecycle_context(fact: LifecycleFact, context: &mut BTreeMap<String, Value>) {
    let encoded = serde_json::to_value(fact).expect("closed lifecycle fact serializes");
    context.insert("lifecycle_event".into(), encoded["event"].clone());
    use LifecycleFact::*;
    match fact {
        AdmissionRefused { reason } => field(context, "lifecycle_reason", reason),
        InspectionRefused { reason } => field(context, "lifecycle_reason", reason),
        Waiting { reason } | RestartDeferred { reason } => {
            field(context, "lifecycle_reason", reason)
        }
        Observing { pid }
        | Launched { pid }
        | Ready { pid }
        | BootRecordConfirmed { pid }
        | BootRecordMismatch { pid }
        | ChannelClosed { pid }
        | Busy { pid }
        | IdleStopUnavailable { pid }
        | Terminated { pid }
        | EffectsUnknown { pid }
        | Adopted { pid } => field(context, "runtime_pid", pid),
        AnnouncementRefused { reason } | CommandRefused { reason } => {
            field(context, "lifecycle_reason", reason)
        }
        HangDetected { pid, ready } => {
            field(context, "runtime_pid", pid);
            field(context, "ready", ready);
        }
        StopRequested { pid, cause, path } => {
            field(context, "runtime_pid", pid);
            field(context, "stop_cause", cause);
            match path {
                StopPath::Channel {} => field(context, "stop_delivery", "channel"),
                StopPath::Signal {} => field(context, "stop_delivery", "signal"),
                StopPath::Undelivered { refusal } => {
                    field(context, "stop_delivery", "undelivered");
                    field(context, "stop_refusal", refusal);
                }
            }
        }
        Exited {
            pid,
            exit,
            announced,
        } => {
            field(context, "runtime_pid", pid);
            let encoded = serde_json::to_value(exit).expect("closed exit serializes");
            context.insert(
                "exit_classification".into(),
                encoded["classification"].clone(),
            );
            match exit {
                RuntimeExit::Reason { reason, code } => {
                    field(context, "exit_reason", reason);
                    field(context, "runtime_exit_code", code);
                }
                RuntimeExit::LaunchFailure { code } | RuntimeExit::Crash { code } => {
                    field(context, "runtime_exit_code", code)
                }
                _ => {}
            }
            if let Some(reason) = announced {
                field(context, "announced_reason", reason);
            }
        }
        RestartScheduled { class, delay_ms } => {
            field(context, "restart_class", class);
            field(context, "delay_ms", delay_ms);
        }
        Foreign { reason } => field(context, "lifecycle_reason", reason),
        StoodDown { reason } => field(context, "lifecycle_reason", reason),
        Failed { last } => field(context, "restart_class", last),
        EventsDropped { count } => field(context, "events_dropped", count),
        SupervisorEnded { result } => {
            let encoded = serde_json::to_value(result).expect("closed outcome serializes");
            context.insert("supervisor_outcome".into(), encoded["outcome"].clone());
            match result {
                SupervisorOutcome::RestartDeferred { reason } => {
                    field(context, "lifecycle_reason", reason)
                }
                SupervisorOutcome::Stopped { effects } => field(context, "effects", effects),
                SupervisorOutcome::StoodDown { reason } => {
                    field(context, "lifecycle_reason", reason)
                }
                SupervisorOutcome::Foreign { reason } => field(context, "lifecycle_reason", reason),
                SupervisorOutcome::Failed { last } => field(context, "restart_class", last),
                SupervisorOutcome::OwnershipChanged {}
                | SupervisorOutcome::AwaitingActiveSession {} => {}
            }
        }
        SupervisorStarted {}
        | OwnershipChanged {}
        | LaunchFailed {}
        | VersionReprobed {}
        | AwaitingActiveSession {}
        | SessionEndRequested {}
        | SessionEndCancelled {} => {}
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use cadrumo_application::diagnostics::Diagnostics;

    fn wire() -> Value {
        let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
        diagnostics.lifecycle(
            EventKind::StageCompleted,
            HostStage::Supervision,
            LifecycleFact::Exited {
                pid: 4321,
                exit: RuntimeExit::Crash { code: 0xc0000005 },
                announced: None,
            },
            Some(
                ApplicationError::new(ErrorCode::ReadFailed, Operation::Manager)
                    .caused_by(std::io::Error::from_raw_os_error(2)),
            ),
        );
        serde_json::to_value(&diagnostics.snapshot(u64::MAX).events[0]).unwrap()
    }

    #[test]
    fn native_manager_events_admit_only_safe_catalogue_and_lifecycle_fields() {
        let mut wire = wire();
        wire["failure"]["message"] = Value::from("PRIVATE-CONTENT-7f3a");
        let entry = parse(&serde_json::to_vec(&wire).unwrap()).unwrap();
        assert_eq!(entry.source, "manager");
        assert_eq!(entry.context["runtime_pid"], 4321);
        assert_eq!(entry.context["runtime_exit_code"], 0xc0000005_u32);
        assert_eq!(entry.context["exit_classification"], "crash");
        assert_eq!(entry.context["reason_code"], "read_failed");
        assert_eq!(entry.context["io_kind"], "NotFound");
        assert_eq!(entry.context["os_code"], 2);
        assert!(entry.message.contains("exited runtime pid 4321"));
        assert!(entry.message.contains("The child output could not be read"));
        assert!(!format!("{entry:?}").contains("7f3a"));
        assert!(
            entry
                .context
                .values()
                .all(|value| !value.is_array() && !value.is_object())
        );
    }

    #[test]
    fn foreign_unknown_and_payload_bearing_shapes_are_refused() {
        for (path, value) in [
            (vec!["source"], Value::from("desktop")),
            (vec!["private"], Value::from("PRIVATE-CONTENT-7f3a")),
            (vec!["kind"], Value::from("unexpected-token")),
            (
                vec!["failure", "ioKind"],
                Value::from("PRIVATE-CONTENT-7f3a"),
            ),
            (
                vec!["lifecycle", "private"],
                Value::from("PRIVATE-CONTENT-7f3a"),
            ),
            (
                vec!["lifecycle", "exit", "private"],
                Value::from("PRIVATE-CONTENT-7f3a"),
            ),
            (vec!["lifecycle", "pid"], Value::from("4321")),
        ] {
            let mut wire = wire();
            let mut slot = &mut wire;
            for key in path {
                slot = &mut slot[key];
            }
            *slot = value;
            assert!(parse(&serde_json::to_vec(&wire).unwrap()).is_none());
        }
        assert!(parse(b"PRIVATE-CONTENT-7f3a").is_none());
        for lifecycle in [
            serde_json::json!({"event": "supervisor_started", "private": "PRIVATE-CONTENT-7f3a"}),
            serde_json::json!({"event": "exited", "pid": 1, "exit": {"classification": "zero", "private": "PRIVATE-CONTENT-7f3a"}, "announced": null}),
            serde_json::json!({"event": "stop_requested", "pid": 1, "cause": "requested", "path": {"delivery": "signal", "private": "PRIVATE-CONTENT-7f3a"}}),
            serde_json::json!({"event": "supervisor_ended", "result": {"outcome": "ownership_changed", "private": "PRIVATE-CONTENT-7f3a"}}),
        ] {
            let mut wire = wire();
            wire["lifecycle"] = lifecycle;
            assert!(parse(&serde_json::to_vec(&wire).unwrap()).is_none());
        }
    }

    #[test]
    fn bounded_producer_event_loss_is_visible_as_a_numeric_fact() {
        let mut wire = wire();
        wire["kind"] = Value::from("failure");
        wire["lifecycle"] = serde_json::json!({"event": "events_dropped", "count": 17});
        let entry = parse(&serde_json::to_vec(&wire).unwrap()).unwrap();
        assert_eq!(entry.context["events_dropped"], 17);
        assert_eq!(entry.context["lifecycle_event"], "events_dropped");
        assert_eq!(entry.level, Some(super::super::format::Level::Error));
        assert!(entry.message.contains("events_dropped"));
    }
}
