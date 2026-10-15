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

#[test]
fn helper_projection_rejects_forged_sources_and_preserves_native_refusal_codes() {
    use cadrumo_application::diagnostics::helper::{
        HelperDecode, HelperExecutable, HelperIdentity, HelperResult,
    };
    let identity = HelperIdentity {
        command: "config.login",
        executable: HelperExecutable::Runtime,
    };
    for source in [
        "private.module:submit:42",
        "C:/private/file.py:submit:42",
        "cadrumo_private:submit:42",
        "cadrumo_runtime.host:submit:0",
        "cadrumo_runtime.host:submit:999999999999",
        "cadrumo_runtime.host:submit:42:extra",
    ] {
        let envelope = json!({"schema_version":"2", "command":"config.login", "status":"error", "error":{"code":"INTERNAL", "context":{"exception_type":"Private value\ncanary", "raised_at":source, "reason":"private reason"}}});
        let fact = HelperResult::inspect(
            identity,
            false,
            &[],
            &serde_json::to_vec(&envelope).unwrap(),
        );
        assert_eq!(fact.envelope_decode, HelperDecode::Refused);
        assert!(fact.raised_at.is_none() && fact.exception_type.is_none() && fact.reason.is_none());
    }
    for code in [
        "launch_value_missing",
        "launch_value_malformed",
        "invocation_undeclared",
    ] {
        let native = json!({"native_refusal":code,"subject":"PRIVATE-SUBJECT-CANARY"});
        let fact =
            HelperResult::inspect(identity, false, &[], &serde_json::to_vec(&native).unwrap());
        assert_eq!(fact.envelope_decode, HelperDecode::NativeRefused);
        assert_eq!(fact.code.as_deref(), Some(code));
        assert!(!serde_json::to_string(&fact).unwrap().contains("CANARY"));
    }
    for bytes in [b"not an envelope PRIVATE-CANARY".as_slice(), br#"{"schema_version":"2","command":"config.logout","status":"error","error":{"code":"INTERNAL"}}"#.as_slice()] {
        let fact = HelperResult::inspect(identity, false, &[], bytes);
        assert_eq!(fact.envelope_decode, HelperDecode::Malformed);
        assert!(fact.code.is_none());
    }
}
