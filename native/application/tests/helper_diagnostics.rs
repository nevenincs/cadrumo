use cadrumo_application::{
    diagnostics::{
        Diagnostics, EventKind,
        helper::{HelperKind, HelperOutcome, HelperTiming},
    },
    error::application::ErrorCode,
    process::status::{ProcessPhase, ProcessRole, Stream},
};
use serde_json::{Value, json};
use std::fs;

fn timing(outcome: HelperOutcome) -> HelperTiming {
    HelperTiming {
        helper_kind: HelperKind::Mutation,
        outcome,
        admission_wait_ms: 250,
        spawn_ms: Some(20),
        execution_ms: Some(900),
        cleanup_ms: Some(1),
        output_join_ms: Some(2),
        total_ms: 1180,
    }
}

#[test]
fn helper_summary_persists_only_closed_timings_and_existing_process_attribution() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let diagnostics = Diagnostics::default();
    diagnostics.configure(directory.path(), 8192, 2).unwrap();
    let process = diagnostics.start(4242, ProcessRole::SignIn);
    diagnostics.capture(
        process,
        Stream::Stdout,
        b"private-password-profile-output-canary",
    );
    diagnostics.finish(process, Some(7), ProcessPhase::Exited);
    let fact = timing(HelperOutcome::Completed);
    diagnostics.helper_timing(Some(process), fact);
    let snapshot = diagnostics.snapshot(u64::MAX);
    let event = snapshot.events.last().unwrap();
    assert!(matches!(event.kind, EventKind::HelperTiming));
    assert_eq!(event.process, Some(process));
    assert_eq!(event.status.as_ref().unwrap().exit_code, Some(7));
    assert_eq!(event.helper_timing, Some(fact));
    assert!(event.stage.is_none() && event.failure.is_none());
    let log = fs::read_to_string(snapshot.paths.unwrap().current).unwrap();
    assert!(!log.contains("private-password-profile-output-canary"));
    let record: Value = serde_json::from_str(log.lines().last().unwrap()).unwrap();
    assert_eq!(
        record["helperTiming"],
        json!({
            "helperKind": "mutation",
            "outcome": "completed",
            "admissionWaitMs": 250,
            "spawnMs": 20,
            "executionMs": 900,
            "cleanupMs": 1,
            "outputJoinMs": 2,
            "totalMs": 1180,
        })
    );
    let mut forged = record["helperTiming"].clone();
    forged["password"] = json!("private-canary");
    assert!(serde_json::from_value::<HelperTiming>(forged).is_err());
}

#[test]
fn unavailable_sink_does_not_lose_timing_or_claim_a_spawn_for_admission_refusal() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let diagnostics = Diagnostics::default();
    let unavailable = directory.path().join("unavailable-log");
    fs::create_dir(&unavailable).unwrap();
    diagnostics.configure_file(&unavailable, 8192, 2).unwrap();
    let fact = HelperTiming {
        spawn_ms: None,
        execution_ms: None,
        cleanup_ms: None,
        output_join_ms: None,
        ..timing(HelperOutcome::AdmissionRefused)
    };
    diagnostics.helper_timing(None, fact);
    let snapshot = diagnostics.snapshot(u64::MAX);
    assert_eq!(
        snapshot.log_failure.as_ref().unwrap().code,
        ErrorCode::LogUnavailable
    );
    assert!(snapshot.processes.is_empty() && snapshot.output.is_empty());
    let event = snapshot.events.last().unwrap();
    assert!(event.process.is_none() && event.status.is_none());
    assert_eq!(event.role, Some(ProcessRole::SignIn));
    let encoded = serde_json::to_value(event).unwrap();
    assert!(encoded["helperTiming"]["spawnMs"].is_null());
    for _ in 0..600 {
        diagnostics.helper_timing(None, fact);
    }
    assert_eq!(diagnostics.snapshot(u64::MAX).events.len(), 512);
}
