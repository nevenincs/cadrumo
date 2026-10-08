//! Logging tests only use isolated files and closed in-memory supervision facts.
use cadrumo_application::{
    diagnostics::{DiagnosticSource, Diagnostics, EventKind, HostStage},
    error::application::{ErrorCode, Operation},
};
use cadrumo_manager::{
    contract::MANAGER_LOG,
    diagnostics::{stage, supervision_event, supervision_outcome},
    session::ownership::WaitReason,
    supervision::{
        adoption::ForeignReason,
        exit::{ExitReason, RuntimeExit},
        protocol::LineRefusal,
        restart::RestartClass,
        stop::StopSignalError,
        supervisor::{Effects, Event, Outcome, StandDownReason, StopCause, StopPath},
    },
};
use std::{
    fs, io,
    path::PathBuf,
    sync::atomic::{AtomicUsize, Ordering},
    time::Duration,
};

struct Scratch(PathBuf);
impl Scratch {
    fn new() -> Self {
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let root = std::env::temp_dir().join(format!(
            "manager-log-fixture-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&root).unwrap();
        Self(root)
    }
}
impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

#[test]
fn supervision_facts_survive_durable_replay_without_identifiers_or_protocol_payloads() {
    let scratch = Scratch::new();
    let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
    diagnostics.host_event(EventKind::HostStarted, HostStage::Admission);
    let events = [
        Event::Launched {
            pid: 42,
            version: "synthetic-private-version".into(),
        },
        Event::Ready {
            pid: 42,
            boot_id: "synthetic-private-boot".into(),
        },
        Event::BootRecordConfirmed { pid: 42 },
        Event::AnnouncementRefused(LineRefusal::Oversized),
        Event::CommandRefused(LineRefusal::Malformed),
        Event::HangDetected {
            pid: 42,
            ready: true,
        },
        Event::StopRequested {
            pid: 42,
            cause: StopCause::SessionEnd,
            path: StopPath::Undelivered(StopSignalError::NoConsole),
        },
        Event::Terminated { pid: 42 },
        Event::EffectsUnknown { pid: 42 },
        Event::Exited {
            pid: 42,
            exit: RuntimeExit::Reason(ExitReason::SessionEndSettle),
            announced: Some(ExitReason::SessionEndSettle),
        },
        Event::RestartScheduled {
            class: RestartClass::Hang,
            delay: Duration::from_millis(2500),
        },
        Event::VersionReprobed {
            version: "synthetic-private-reprobe".into(),
        },
        Event::Adopted {
            pid: 43,
            version: "synthetic-private-adopted".into(),
        },
        Event::Foreign(ForeignReason::OtherSession),
        Event::StoodDown(StandDownReason::RootMismatch),
        Event::LaunchFailed {
            kind: io::ErrorKind::PermissionDenied,
        },
        Event::RestartDeferred(WaitReason::ClaimUnavailable(
            io::ErrorKind::PermissionDenied,
        )),
        Event::Failed {
            last: RestartClass::LaunchFailure,
        },
    ];
    for event in &events {
        supervision_event(&diagnostics, event);
    }
    supervision_outcome(
        &diagnostics,
        Outcome::Stopped {
            effects: Effects::Unknown,
        },
    );
    let current = scratch.0.join(MANAGER_LOG);
    diagnostics.configure_file(&current, 65536, 2).unwrap();
    let text = fs::read_to_string(&current).unwrap();
    diagnostics.configure_file(&current, 65536, 2).unwrap();
    assert_eq!(fs::read_to_string(&current).unwrap(), text);
    assert!(!text.contains("synthetic-private"));
    assert!(!text.contains("bootId") && !text.contains("\"version\""));
    let records = text
        .lines()
        .map(|line| serde_json::from_str::<serde_json::Value>(line).unwrap())
        .collect::<Vec<_>>();
    assert_eq!(records.len(), events.len() + 2);
    assert!(records.iter().all(|record| record["source"] == "manager"));
    assert_eq!(
        records[1]["lifecycle"],
        serde_json::json!({"event":"launched", "pid":42})
    );
    assert_eq!(
        records[7]["lifecycle"]["path"],
        serde_json::json!({"delivery":"undelivered","refusal":"no_console"})
    );
    assert_eq!(records[10]["lifecycle"]["announced"], "session_end_settle");
    assert_eq!(records[10]["lifecycle"]["exit"]["code"], 66);
    assert_eq!(records[11]["lifecycle"]["delayMs"], 2500);
    assert_eq!(records[16]["failure"]["ioKind"], "PermissionDenied");
    for record in [
        &records[4],
        &records[5],
        &records[6],
        &records[9],
        &records[14],
        &records[15],
        &records[16],
        &records[18],
    ] {
        assert_eq!(record["kind"], "failure");
    }
    for record in [
        &records[1],
        &records[2],
        &records[3],
        &records[10],
        &records[11],
        &records[13],
    ] {
        assert_eq!(record["kind"], "stage_completed");
    }
    assert_eq!(
        records.last().unwrap()["lifecycle"]["result"],
        serde_json::json!({"outcome":"stopped","effects":"unknown"})
    );
    assert!(diagnostics.snapshot(0).output.is_empty());
}

#[test]
fn termination_failures_remain_distinct_and_retain_only_safe_native_facts() {
    #[cfg(windows)]
    let permission_code = 5; // ERROR_ACCESS_DENIED
    #[cfg(unix)]
    let permission_code = libc::EACCES;
    let scratch = Scratch::new();
    let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
    let current = scratch.0.join(MANAGER_LOG);
    diagnostics.configure_file(&current, 16384, 1).unwrap();
    for event in [
        Event::TerminationRequested { pid: 7 },
        Event::TerminationFailed {
            pid: 7,
            kind: io::ErrorKind::PermissionDenied,
            os_code: Some(permission_code),
        },
        Event::TerminationUnconfirmed { pid: 7 },
        Event::ProcessInspectionFailed {
            pid: 7,
            kind: io::ErrorKind::InvalidInput,
            os_code: None,
        },
    ] {
        supervision_event(&diagnostics, &event);
    }
    let records: Vec<serde_json::Value> = fs::read_to_string(current)
        .unwrap()
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();
    assert_eq!(records[0]["kind"], "stage_started");
    assert_eq!(records[0]["lifecycle"]["event"], "termination_requested");
    assert_eq!(records[1]["lifecycle"]["event"], "termination_failed");
    assert_eq!(records[1]["failure"]["ioKind"], "PermissionDenied");
    assert_eq!(records[1]["failure"]["osCode"], permission_code);
    assert_eq!(records[2]["lifecycle"]["event"], "termination_unconfirmed");
    assert_eq!(records[2]["failure"]["ioKind"], "TimedOut");
    assert_eq!(
        records[3]["lifecycle"]["event"],
        "process_inspection_failed"
    );
    assert!(
        records[1..]
            .iter()
            .all(|record| record["kind"] == "failure")
    );
}

#[test]
fn stage_failure_keeps_safe_io_facts_and_buffer_until_a_canonical_file_is_selected() {
    let scratch = Scratch::new();
    let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
    let result: io::Result<()> = stage(
        &diagnostics,
        HostStage::Storage,
        ErrorCode::EnvironmentFailed,
        Operation::Environment,
        || {
            Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "synthetic-private-root",
            ))
        },
    );
    assert!(result.is_err());
    assert!(diagnostics.snapshot(0).paths.is_none());
    assert_eq!(fs::read_dir(&scratch.0).unwrap().count(), 0);
    let current = scratch.0.join(MANAGER_LOG);
    diagnostics.configure_file(&current, 4096, 1).unwrap();
    let text = fs::read_to_string(current).unwrap();
    assert!(text.contains("\"stage\":\"storage\""));
    assert!(text.contains("environment_failed") && text.contains("InvalidInput"));
    assert!(!text.contains("synthetic-private"));
}

#[test]
fn refusals_and_faults_have_failure_severity_while_expected_liveness_stays_ordinary() {
    let scratch = Scratch::new();
    let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
    let current = scratch.0.join(MANAGER_LOG);
    diagnostics.configure_file(&current, 16384, 1).unwrap();
    for event in [
        Event::BootRecordMismatch { pid: 7 },
        Event::AnnouncementRefused(LineRefusal::Malformed),
        Event::CommandRefused(LineRefusal::Oversized),
        Event::HangDetected {
            pid: 7,
            ready: false,
        },
        Event::Foreign(ForeignReason::RecordUnreadable),
        Event::StoodDown(StandDownReason::ElevatedTokenRefused),
        Event::Failed {
            last: RestartClass::Unexpected,
        },
        Event::EffectsUnknown { pid: 7 },
    ] {
        supervision_event(&diagnostics, &event);
    }
    for event in [
        Event::Busy { pid: 7 },
        Event::Ready {
            pid: 7,
            boot_id: "synthetic-private".into(),
        },
        Event::Exited {
            pid: 7,
            exit: RuntimeExit::Zero,
            announced: None,
        },
    ] {
        supervision_event(&diagnostics, &event);
    }
    supervision_outcome(
        &diagnostics,
        Outcome::Failed {
            last: RestartClass::Hang,
        },
    );
    let records = fs::read_to_string(current)
        .unwrap()
        .lines()
        .map(|line| serde_json::from_str::<serde_json::Value>(line).unwrap())
        .collect::<Vec<_>>();
    assert_eq!(records.len(), 12);
    assert!(
        records[..8]
            .iter()
            .all(|record| record["kind"] == "failure")
    );
    assert!(
        records[8..11]
            .iter()
            .all(|record| record["kind"] == "stage_completed")
    );
    assert_eq!(records[11]["kind"], "failure");
}
