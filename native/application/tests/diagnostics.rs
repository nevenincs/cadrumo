use cadrumo_application::{
    diagnostics::{Diagnostics, EventKind},
    failure::{Failure, FailureCode, Operation},
    logging::LogFile,
    tracking::{ProcessPhase, ProcessRole, Stream},
};
use std::{error::Error, fs};

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
    let error = Failure::new(FailureCode::ReadFailed, Operation::Cli)
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
            timestamp_ms: sequence,
            host_pid: 42,
            kind: EventKind::HostStarted,
            process: None,
            failure: None,
            status: None,
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
        FailureCode::LogUnavailable
    );
    assert_eq!(fs::read(obstruction).unwrap(), b"original");
}
