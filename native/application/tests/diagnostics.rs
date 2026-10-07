use cadrumo_application::{
    child::ChildConfiguration,
    diagnostics::logging::LogFile,
    diagnostics::{DiagnosticSource, Diagnostics, EventKind, HostOutcome, HostStage},
    error::application::{ApplicationError, ErrorCode, Operation},
    process::passthrough,
    process::status::{ProcessPhase, ProcessRole, Stream},
};
use std::{
    error::Error,
    ffi::OsString,
    fs,
    sync::{
        Arc, Barrier,
        atomic::{AtomicBool, Ordering},
    },
    thread,
    time::{Duration, Instant},
};

#[test]
fn private_causes_and_child_payloads_never_enter_native_logs() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let diagnostics = Diagnostics::default();
    diagnostics.event(EventKind::HostStarted, None, None);
    diagnostics.configure(directory.path(), 4096, 2).unwrap();
    let id = diagnostics.start(123, ProcessRole::Cli);
    let secret = b"synthetic-private-password";
    diagnostics.capture(id, Stream::Stdout, secret);
    diagnostics.capture(id, Stream::Stderr, b"failure bytes");
    let error = ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
        .caused_by(std::io::Error::other("synthetic-private-password"));
    assert!(error.source().is_some());
    diagnostics.failure(error);
    diagnostics.finish(id, Some(7), ProcessPhase::Exited);
    let snapshot = diagnostics.snapshot(0);
    assert_eq!(snapshot.processes[0].stdout_bytes, secret.len() as u64);
    assert_eq!(snapshot.processes[0].exit_code, Some(7));
    assert_eq!(snapshot.output[0].bytes, secret);
    let log = fs::read_to_string(snapshot.paths.unwrap().current).unwrap();
    assert!(!log.contains("synthetic-private-password"));
    assert!(log.contains("child_exited"));
    assert!(log.contains("read_failed"));
    assert!(log.contains("\"exitCode\":7"));
}

#[test]
fn rotation_bounds_files_and_capture_reports_discarded_bytes() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let file = LogFile::new(directory.path(), 512, 2).unwrap();
    for sequence in 0..20 {
        file.append(&cadrumo_application::diagnostics::Event {
            sequence,
            source: DiagnosticSource::Desktop,
            timestamp_ms: sequence,
            host_pid: 42,
            kind: EventKind::HostStarted,
            process: None,
            failure: None,
            status: None,
            stage: None,
            role: None,
            outcome: None,
            host_exit_code: None,
            lifecycle: None,
            webview_failure: None,
        })
        .unwrap();
    }
    for entry in fs::read_dir(directory.path()).unwrap() {
        let entry = entry.unwrap();
        assert!(entry.metadata().unwrap().len() <= 512);
    }
    assert_eq!(fs::read_dir(directory.path()).unwrap().count(), 4);
    let diagnostics = Diagnostics::default();
    let id = diagnostics.start(100, ProcessRole::Tui);
    diagnostics.capture(id, Stream::Terminal, &vec![b'x'; 512 * 1024]);
    let snapshot = diagnostics.snapshot(0);
    assert_eq!(
        snapshot.output.iter().map(|c| c.bytes.len()).sum::<usize>(),
        256 * 1024
    );
    assert_eq!(snapshot.dropped_bytes, 256 * 1024);
    assert_eq!(snapshot.processes[0].terminal_bytes, 512 * 1024);
    assert!(
        diagnostics
            .snapshot(snapshot.output[0].sequence)
            .output
            .is_empty()
    );
}

#[test]
fn early_failure_is_durable_and_same_target_configuration_does_not_replay() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let diagnostics = Diagnostics::default();
    diagnostics.event(EventKind::HostStarted, None, None);
    diagnostics.configure(directory.path(), 8192, 2).unwrap();
    diagnostics.host_failure(
        HostStage::Environment,
        ApplicationError::new(ErrorCode::EnvironmentFailed, Operation::Environment)
            .caused_by(std::io::Error::other("synthetic-private-projection-output")),
    );
    let file = diagnostics.snapshot(u64::MAX).paths.unwrap().current;
    let early = fs::read_to_string(&file).unwrap();
    assert_eq!(early.lines().count(), 2);
    assert!(early.contains("environment_failed"));
    assert!(!early.contains("synthetic-private-projection-output"));

    // Successful final projection retains the same path and can change policy.
    diagnostics
        .configure(&directory.path().join("."), 16384, 3)
        .unwrap();
    assert_eq!(fs::read_to_string(&file).unwrap(), early);
    diagnostics.host_stopped(1);
    diagnostics.configure(directory.path(), 16384, 3).unwrap();
    let records: Vec<serde_json::Value> = fs::read_to_string(&file)
        .unwrap()
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();
    assert_eq!(records.len(), 3);
    assert_eq!(records[0]["sequence"], 1);
    assert_eq!(records[1]["sequence"], 2);
    assert_eq!(records[2]["sequence"], 3);
    assert_eq!(records[2]["hostExitCode"], 1);
}

#[test]
fn failures_retain_child_identity_and_safe_os_codes_only() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let diagnostics = Diagnostics::default();
    diagnostics.configure(directory.path(), 4096, 2).unwrap();
    let id = diagnostics.start(912, ProcessRole::Cli);
    let error = ApplicationError::new(ErrorCode::WriteFailed, Operation::Cli).caused_by(
        std::io::Error::new(std::io::ErrorKind::BrokenPipe, "synthetic-private-password"),
    );
    diagnostics.failure_for(id, error);
    let os_error = std::io::Error::from_raw_os_error(5);
    let os_kind = os_error.kind();
    let error = ApplicationError::new(ErrorCode::CleanupFailed, Operation::Cli).caused_by(
        ApplicationError::new(ErrorCode::WriteFailed, Operation::Cli).caused_by(os_error),
    );
    diagnostics.failure_for(id, error);
    diagnostics.finish(id, Some(9), ProcessPhase::Failed);
    let snapshot = diagnostics.snapshot(u64::MAX);
    assert!(snapshot.output.is_empty());
    let failure = &snapshot.events[1];
    assert_eq!(failure.process, Some(id));
    assert_eq!(failure.role, Some(ProcessRole::Cli));
    assert_eq!(failure.status.as_ref().unwrap().pid, 912);
    assert_eq!(
        failure.failure.as_ref().unwrap().io_kind,
        Some(std::io::ErrorKind::BrokenPipe)
    );
    let nested = &snapshot.events[2];
    assert_eq!(nested.failure.as_ref().unwrap().os_code, Some(5));
    assert_eq!(nested.failure.as_ref().unwrap().io_kind, Some(os_kind));
    let log = fs::read_to_string(snapshot.paths.unwrap().current).unwrap();
    assert!(!log.contains("synthetic-private-password"));
    let records: Vec<serde_json::Value> = log
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();
    assert_eq!(records[1]["status"]["pid"], 912);
    assert_eq!(records[1]["failure"]["ioKind"], "BrokenPipe");
    assert_eq!(records[2]["failure"]["osCode"], 5);
    assert_eq!(records[3]["status"]["exitCode"], 9);
}

#[test]
fn host_lifecycle_records_are_ordered_and_preserved_before_configuration() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let diagnostics = Diagnostics::new(DiagnosticSource::Desktop);
    diagnostics.event(EventKind::HostStarted, None, None);
    diagnostics.host_event(EventKind::StageStarted, HostStage::Manager);
    diagnostics.host_outcome(HostStage::Manager, HostOutcome::Dispatched);
    diagnostics.host_failure(
        HostStage::Window,
        ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview),
    );
    diagnostics.host_stopped(69);
    diagnostics.configure(directory.path(), 4096, 2).unwrap();
    let snapshot = diagnostics.snapshot(u64::MAX);
    assert!(
        snapshot
            .events
            .iter()
            .enumerate()
            .all(|(index, event)| event.sequence == index as u64 + 1)
    );
    let log = fs::read_to_string(snapshot.paths.unwrap().current).unwrap();
    let records: Vec<serde_json::Value> = log
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();
    assert_eq!(records.len(), 5);
    assert_eq!(records[2]["source"], "desktop");
    assert_eq!(records[2]["stage"], "manager");
    assert_eq!(records[2]["outcome"], "dispatched");
    assert_eq!(records[3]["stage"], "window");
    assert_eq!(records[4]["hostExitCode"], 69);
}

#[test]
fn event_identity_survives_ring_eviction() {
    let diagnostics = Diagnostics::default();
    for _ in 0..600 {
        diagnostics.host_event(EventKind::StageStarted, HostStage::Manager);
    }
    let snapshot = diagnostics.snapshot(u64::MAX);
    assert_eq!(snapshot.events.len(), 512);
    assert_eq!(snapshot.events[0].sequence, 89);
    assert_eq!(snapshot.events[511].sequence, 600);
}

#[test]
fn application_wrappers_preserve_real_io_reason_without_the_private_path() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let error = fs::read(directory.path().join("synthetic-private-path")).unwrap_err();
    let expected_code = error.raw_os_error().unwrap();
    let error = ApplicationError::new(ErrorCode::PackageUnavailable, Operation::Package)
        .caused_by(cadrumo_application::error::Error::Io(error));
    assert_eq!(error.io_kind, Some(std::io::ErrorKind::NotFound));
    assert_eq!(error.os_code, Some(expected_code));
    let serialized = serde_json::to_string(&error).unwrap();
    assert!(!serialized.contains("synthetic-private-path"));
    assert!(serialized.contains("NotFound"));
}

#[test]
fn real_spawn_failure_preserves_role_without_logging_launch_payloads() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let diagnostics = Arc::new(Diagnostics::default());
    diagnostics.configure(directory.path(), 4096, 2).unwrap();
    let configuration = ChildConfiguration::new(
        directory.path().join("synthetic-private-executable.exe"),
        directory.path().to_owned(),
        std::collections::BTreeMap::from([(
            OsString::from("SYNTHETIC_SECRET"),
            OsString::from("synthetic-private-credential"),
        )]),
    )
    .unwrap();
    let error = passthrough(
        &configuration,
        &[OsString::from("synthetic-private-argument")],
        diagnostics.clone(),
        Arc::new(AtomicBool::new(false)),
    )
    .unwrap_err();
    assert_eq!(error.code, ErrorCode::SpawnFailed);
    assert_eq!(error.io_kind, Some(std::io::ErrorKind::NotFound));
    assert!(error.os_code.is_some());
    let snapshot = diagnostics.snapshot(u64::MAX);
    assert!(snapshot.processes.is_empty());
    assert!(snapshot.output.is_empty());
    assert_eq!(snapshot.events.len(), 1);
    assert_eq!(snapshot.events[0].role, Some(ProcessRole::Cli));
    assert!(snapshot.events[0].status.is_none());
    let log = std::fs::read_to_string(snapshot.paths.unwrap().current).unwrap();
    assert!(!log.contains("synthetic-private"));
    assert!(!log.contains("SYNTHETIC_SECRET"));
    let record: serde_json::Value = serde_json::from_str(log.trim_end()).unwrap();
    assert_eq!(record["role"], "cli");
    assert_eq!(record["failure"]["ioKind"], "NotFound");
}

#[test]
fn logging_failure_is_observable_without_replacing_process_result() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let obstruction = directory.path().join("file");
    fs::write(&obstruction, b"original").unwrap();
    let diagnostics = Diagnostics::default();
    diagnostics.event(EventKind::HostStarted, None, None);
    let failure = diagnostics.configure(&obstruction, 4096, 2).err().unwrap();
    diagnostics.failure(failure);
    assert_eq!(
        diagnostics.snapshot(0).log_failure.unwrap().code,
        ErrorCode::LogUnavailable
    );
    assert_eq!(fs::read(obstruction).unwrap(), b"original");
}

#[test]
fn explicit_file_targets_replay_and_rotate_without_using_the_default_sink() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let current = directory.path().join("fixture-lifecycle.log");
    let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
    diagnostics.host_event(EventKind::HostStarted, HostStage::Admission);
    diagnostics.configure_file(&current, 1024, 2).unwrap();
    let early = fs::read_to_string(&current).unwrap();
    diagnostics.configure_file(&current, 1024, 2).unwrap();
    assert_eq!(fs::read_to_string(&current).unwrap(), early);
    for _ in 0..30 {
        diagnostics.host_outcome(HostStage::Supervision, HostOutcome::Ready);
    }
    let snapshot = diagnostics.snapshot(0);
    assert_eq!(snapshot.paths.as_ref().unwrap().current, current);
    assert_eq!(
        snapshot.paths.unwrap().lock,
        directory.path().join("fixture-lifecycle.log.lock")
    );
    assert!(!directory.path().join("cadrumo-native.jsonl").exists());
    assert!(!directory.path().join("cadrumo-native.lock").exists());
    let mut records = Vec::new();
    for name in [
        "fixture-lifecycle.log.2",
        "fixture-lifecycle.log.1",
        "fixture-lifecycle.log",
    ] {
        let bytes = fs::read(directory.path().join(name)).unwrap();
        assert!(bytes.len() <= 1024);
        assert_eq!(bytes.last(), Some(&b'\n'));
        records.extend(
            String::from_utf8(bytes)
                .unwrap()
                .lines()
                .map(|line| serde_json::from_str::<serde_json::Value>(line).unwrap()),
        );
    }
    assert!(
        records
            .windows(2)
            .all(|pair| pair[0]["sequence"].as_u64().unwrap() + 1 == pair[1]["sequence"])
    );
    assert_eq!(records.last().unwrap()["sequence"], 31);
    assert!(
        records
            .iter()
            .all(|record| record["source"] == "manager" && record.get("lifecycle").is_none())
    );
}

#[test]
fn explicit_file_target_refuses_relative_and_parent_paths() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
    diagnostics.host_event(EventKind::HostStarted, HostStage::Admission);
    for path in [
        std::path::PathBuf::from("relative.log"),
        directory.path().join("../unresolved.log"),
    ] {
        assert!(diagnostics.configure_file(&path, 4096, 1).is_err());
    }
    assert!(diagnostics.snapshot(0).paths.is_none());
    assert_eq!(fs::read_dir(directory.path()).unwrap().count(), 0);
    let records = diagnostics.snapshot(0).events;
    assert_eq!(records.len(), 1);
}

#[test]
fn closed_lifecycle_decoder_refuses_unknown_payload_fields_and_tokens() {
    use cadrumo_application::diagnostics::lifecycle::LifecycleFact;
    for record in [
        r#"{"event":"ready","pid":1,"bootId":"synthetic-private"}"#,
        r#"{"event":"foreign","reason":"synthetic-private"}"#,
        r#"{"event":"supervisor_started","payload":"synthetic-private"}"#,
        r#"{"event":"exited","pid":1,"exit":{"classification":"zero","payload":"synthetic-private"},"announced":null}"#,
        r#"{"event":"supervisor_ended","result":{"outcome":"ownership_changed","payload":"synthetic-private"}}"#,
        r#"{"event":"stop_requested","pid":1,"cause":"session_end","path":{"delivery":"signal","payload":"synthetic-private"}}"#,
    ] {
        assert!(serde_json::from_str::<LifecycleFact>(record).is_err());
    }
    assert_eq!(
        serde_json::from_str::<LifecycleFact>(r#"{"event":"ready","pid":1}"#).unwrap(),
        LifecycleFact::Ready { pid: 1 }
    );
}

#[test]
fn concurrent_writers_rotate_complete_records_and_keep_bounded_state() {
    const WRITERS: usize = 8;
    const CYCLES: usize = 64;
    const PAYLOAD_BYTES: usize = 2048;
    const FILE_BYTES: u64 = 4096;
    const CAPTURE_BYTES: usize = 256 * 1024;
    const EVENTS: u64 = (WRITERS * CYCLES * 4) as u64;

    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let diagnostics = Arc::new(Diagnostics::default());
    diagnostics
        .configure(directory.path(), FILE_BYTES, 2)
        .unwrap();
    let barrier = Arc::new(Barrier::new(WRITERS + 1));
    let done = Arc::new(AtomicBool::new(false));
    let started = Instant::now();
    let observed = thread::scope(|scope| {
        let reader_diagnostics = diagnostics.clone();
        let reader_done = done.clone();
        let reader = scope.spawn(move || {
            let mut snapshots = 0;
            while !reader_done.load(Ordering::Acquire) {
                let snapshot = reader_diagnostics.snapshot(0);
                assert!(snapshot.events.len() <= 512);
                assert!(snapshot.processes.len() <= 128);
                assert!(snapshot.output.len() <= 512);
                assert!(
                    snapshot
                        .output
                        .iter()
                        .map(|chunk| chunk.bytes.len())
                        .sum::<usize>()
                        <= CAPTURE_BYTES
                );
                assert!(
                    snapshot
                        .events
                        .windows(2)
                        .all(|events| events[0].sequence < events[1].sequence)
                );
                snapshots += 1;
                thread::sleep(Duration::from_millis(1));
            }
            snapshots
        });
        let mut writers = Vec::new();
        for writer in 0..WRITERS {
            let diagnostics = diagnostics.clone();
            let barrier = barrier.clone();
            writers.push(scope.spawn(move || {
                let mut payload = vec![b'x'; PAYLOAD_BYTES];
                let canary = b"synthetic-private-captured-stream";
                payload[..canary.len()].copy_from_slice(canary);
                barrier.wait();
                for cycle in 0..CYCLES {
                    let pid = (10_000 + writer * CYCLES + cycle) as u32;
                    let id = diagnostics.start(pid, ProcessRole::Cli);
                    diagnostics.capture(id, Stream::Stdout, &payload);
                    diagnostics.failure_for(
                        id,
                        ApplicationError::new(ErrorCode::WriteFailed, Operation::Cli).caused_by(
                            std::io::Error::new(
                                std::io::ErrorKind::BrokenPipe,
                                "synthetic-private-cause",
                            ),
                        ),
                    );
                    diagnostics.finish(id, Some(0), ProcessPhase::Exited);
                    diagnostics.host_outcome(HostStage::Manager, HostOutcome::Ready);
                }
            }));
        }
        barrier.wait();
        let outcomes: Vec<_> = writers.into_iter().map(|writer| writer.join()).collect();
        done.store(true, Ordering::Release);
        let observed = reader.join().unwrap();
        for outcome in outcomes {
            outcome.unwrap();
        }
        observed
    });
    let elapsed = started.elapsed();
    let snapshot = diagnostics.snapshot(0);
    assert!(snapshot.log_failure.is_none());
    assert_eq!(snapshot.events.len(), 512);
    assert_eq!(snapshot.events.first().unwrap().sequence, EVENTS - 511);
    assert_eq!(snapshot.events.last().unwrap().sequence, EVENTS);
    assert_eq!(snapshot.processes.len(), 128);
    assert!(snapshot.processes.iter().all(|process| {
        process.phase == ProcessPhase::Exited
            && process.finished_ms.is_some()
            && process.exit_code == Some(0)
            && process.stdout_bytes == PAYLOAD_BYTES as u64
    }));
    let retained = snapshot
        .output
        .iter()
        .map(|chunk| chunk.bytes.len())
        .sum::<usize>();
    assert_eq!(retained, CAPTURE_BYTES);
    assert_eq!(
        snapshot.dropped_bytes + retained as u64,
        (WRITERS * CYCLES * PAYLOAD_BYTES) as u64
    );
    assert!(observed > 0);

    let paths = snapshot.paths.unwrap();
    let mut sequences = Vec::new();
    let mut retained_file_bytes = 0;
    for path in [
        paths.current.with_file_name("cadrumo-native.jsonl.2"),
        paths.current.with_file_name("cadrumo-native.jsonl.1"),
        paths.current,
    ] {
        let text = fs::read_to_string(path).unwrap();
        retained_file_bytes += text.len();
        assert!((text.len() as u64) <= FILE_BYTES);
        assert!(text.ends_with('\n'));
        assert!(!text.contains("synthetic-private"));
        for line in text.lines() {
            let event: serde_json::Value = serde_json::from_str(line).unwrap();
            sequences.push(event["sequence"].as_u64().unwrap());
        }
    }
    assert!(sequences.windows(2).all(|pair| pair[0] + 1 == pair[1]));
    assert_eq!(sequences.last(), Some(&EVENTS));
    assert_eq!(fs::read_dir(directory.path()).unwrap().count(), 4);
    eprintln!(
        "native diagnostics concurrency: writers={WRITERS}, events={EVENTS}, elapsed_ms={}, events_per_second={:.0}, snapshots={observed}, retained_file_bytes={retained_file_bytes}, retained_capture_bytes={retained}, processes={}, events_in_memory={}",
        elapsed.as_millis(),
        EVENTS as f64 / elapsed.as_secs_f64(),
        snapshot.processes.len(),
        snapshot.events.len(),
    );
}

#[test]
fn failed_configuration_recovers_buffered_events_without_replacing_the_primary() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let obstruction = directory.path().join("logs");
    fs::write(&obstruction, b"original").unwrap();
    let diagnostics = Diagnostics::default();
    diagnostics.event(EventKind::HostStarted, None, None);
    let primary = ApplicationError::new(ErrorCode::EnvironmentFailed, Operation::Environment)
        .caused_by(std::io::Error::other("synthetic-private-environment-error"));
    diagnostics.host_failure(HostStage::Environment, primary.clone());
    let sink_error = diagnostics.configure(&obstruction, 8192, 2).unwrap_err();
    diagnostics.failure(sink_error);
    assert!(diagnostics.snapshot(u64::MAX).paths.is_none());
    assert_eq!(primary.code, ErrorCode::EnvironmentFailed);

    let preserved = directory.path().join("preserved-obstruction");
    fs::rename(&obstruction, &preserved).unwrap();
    diagnostics.configure(&obstruction, 8192, 2).unwrap();
    diagnostics.host_stopped(1);
    let snapshot = diagnostics.snapshot(u64::MAX);
    assert_eq!(
        snapshot.log_failure.unwrap().code,
        ErrorCode::LogUnavailable
    );
    let log = fs::read_to_string(snapshot.paths.unwrap().current).unwrap();
    assert!(!log.contains("synthetic-private"));
    let records: Vec<serde_json::Value> = log
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();
    assert_eq!(records.len(), 4);
    assert_eq!(records[1]["failure"]["code"], "environment_failed");
    assert_eq!(records[2]["failure"]["code"], "log_unavailable");
    assert_eq!(records[3]["hostExitCode"], 1);
    assert_eq!(fs::read(preserved).unwrap(), b"original");
}

#[test]
fn a_busy_sink_keeps_the_primary_in_memory_and_future_writes_resume() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let diagnostics = Diagnostics::default();
    diagnostics.configure(directory.path(), 8192, 2).unwrap();
    diagnostics.event(EventKind::HostStarted, None, None);
    let paths = diagnostics.snapshot(u64::MAX).paths.unwrap();
    let lock = fs::OpenOptions::new()
        .read(true)
        .write(true)
        .open(&paths.lock)
        .unwrap();
    lock.lock().unwrap();
    diagnostics.host_failure(
        HostStage::Environment,
        ApplicationError::new(ErrorCode::EnvironmentFailed, Operation::Environment),
    );
    let blocked = diagnostics.snapshot(u64::MAX);
    assert_eq!(blocked.events.len(), 2);
    assert_eq!(
        blocked.events[1].failure.as_ref().unwrap().code,
        ErrorCode::EnvironmentFailed
    );
    assert_eq!(blocked.log_failure.unwrap().code, ErrorCode::LogUnavailable);
    assert_eq!(
        fs::read_to_string(&paths.current).unwrap().lines().count(),
        1
    );
    drop(lock);

    diagnostics.host_stopped(1);
    let log = fs::read_to_string(paths.current).unwrap();
    let sequences: Vec<u64> = log
        .lines()
        .map(|line| {
            serde_json::from_str::<serde_json::Value>(line).unwrap()["sequence"]
                .as_u64()
                .unwrap()
        })
        .collect();
    assert_eq!(sequences, [1, 3]);
    let recovered = diagnostics.snapshot(u64::MAX);
    assert_eq!(recovered.events.len(), 3);
    assert_eq!(
        recovered.log_failure.unwrap().code,
        ErrorCode::LogUnavailable
    );
    eprintln!(
        "native diagnostics busy-sink recovery: persistent_sequences={sequences:?}, memory_sequences=[1, 2, 3], log_failure=log_unavailable"
    );
}

#[test]
fn incomplete_configuration_retry_preserves_buffered_events_without_duplicates() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let diagnostics = Diagnostics::default();
    diagnostics.event(EventKind::HostStarted, None, None);
    let first_record_bytes = serde_json::to_vec(&diagnostics.snapshot(u64::MAX).events[0])
        .unwrap()
        .len() as u64
        + 1;
    diagnostics.host_failure(
        HostStage::Environment,
        ApplicationError::new(ErrorCode::EnvironmentFailed, Operation::Environment)
            .caused_by(std::io::Error::other("synthetic-private-primary")),
    );
    let error = diagnostics
        .configure(directory.path(), first_record_bytes, 2)
        .unwrap_err();
    assert_eq!(error.code, ErrorCode::LogUnavailable);
    diagnostics.failure(error);
    let incomplete = diagnostics.snapshot(u64::MAX);
    assert!(incomplete.paths.is_none());
    assert_eq!(incomplete.events.len(), 3);
    assert_eq!(
        incomplete.log_failure.unwrap().code,
        ErrorCode::LogUnavailable
    );
    let file = directory.path().join("cadrumo-native.jsonl");
    let first = fs::read_to_string(&file).unwrap();
    assert_eq!(first.lines().count(), 1);
    assert_eq!(
        serde_json::from_str::<serde_json::Value>(first.trim()).unwrap()["sequence"],
        1
    );

    diagnostics.configure(directory.path(), 8192, 2).unwrap();
    diagnostics.host_stopped(1);
    let log = fs::read_to_string(file).unwrap();
    assert!(!log.contains("synthetic-private"));
    let records: Vec<serde_json::Value> = log
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();
    let sequences: Vec<u64> = records
        .iter()
        .map(|record| record["sequence"].as_u64().unwrap())
        .collect();
    let primary_failures = records
        .iter()
        .filter(|record| record["failure"]["code"] == "environment_failed")
        .count();
    let sink_failures = records
        .iter()
        .filter(|record| record["failure"]["code"] == "log_unavailable")
        .count();
    eprintln!(
        "native diagnostics partial-config recovery: first_records=1, first_error=log_unavailable, retry_sequences={sequences:?}, primary_failures={primary_failures}, sink_failures={sink_failures}"
    );
    assert_eq!(primary_failures, 1);
    assert_eq!(sink_failures, 1);
    assert_eq!(sequences, [1, 2, 3, 4]);
}

#[test]
fn retrying_a_different_target_replays_all_events_and_preserves_the_active_sink_on_failure() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let active = directory.path().join("active");
    let interrupted = directory.path().join("interrupted");
    let replacement = directory.path().join("replacement");
    let diagnostics = Diagnostics::default();
    diagnostics.event(EventKind::HostStarted, None, None);
    let first_record_bytes = serde_json::to_vec(&diagnostics.snapshot(u64::MAX).events[0])
        .unwrap()
        .len() as u64
        + 1;
    diagnostics.configure(&active, 8192, 2).unwrap();
    diagnostics.host_failure(
        HostStage::Environment,
        ApplicationError::new(ErrorCode::EnvironmentFailed, Operation::Environment),
    );
    let error = diagnostics
        .configure(&interrupted, first_record_bytes, 2)
        .unwrap_err();
    diagnostics.failure(error);
    let snapshot = diagnostics.snapshot(u64::MAX);
    assert_eq!(
        snapshot.paths.unwrap().current,
        active.join("cadrumo-native.jsonl")
    );
    assert_eq!(snapshot.events.len(), 3);
    let previous = fs::read_to_string(active.join("cadrumo-native.jsonl")).unwrap();
    assert_eq!(previous.lines().count(), 3);
    assert_eq!(
        fs::read_to_string(interrupted.join("cadrumo-native.jsonl"))
            .unwrap()
            .lines()
            .count(),
        1
    );

    diagnostics.configure(&replacement, 8192, 2).unwrap();
    diagnostics.host_stopped(1);
    let installed = diagnostics.snapshot(u64::MAX).paths.unwrap().current;
    assert_eq!(installed, replacement.join("cadrumo-native.jsonl"));
    let sequences: Vec<u64> = fs::read_to_string(installed)
        .unwrap()
        .lines()
        .map(|line| {
            serde_json::from_str::<serde_json::Value>(line).unwrap()["sequence"]
                .as_u64()
                .unwrap()
        })
        .collect();
    assert_eq!(sequences, [1, 2, 3, 4]);
    assert_eq!(
        fs::read_to_string(active.join("cadrumo-native.jsonl")).unwrap(),
        previous
    );
}
