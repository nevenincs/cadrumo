use cadrumo_application::{
    diagnostics::{
        Diagnostics, EventKind, HostStage,
        webview::{FailureReason, MonitorOperation, ProcessKind, ReadFailures, WebviewFailure},
    },
    error::application::{ErrorCode, Operation},
    process::status::{ProcessRole, Stream},
};
use serde_json::{Value, json};
use std::fs;

#[test]
fn browser_failure_persists_only_closed_numeric_metadata() {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let diagnostics = Diagnostics::default();
    diagnostics.configure(directory.path(), 8192, 2).unwrap();
    let child = diagnostics.start(9321, ProcessRole::Tui);
    diagnostics.capture(
        child,
        Stream::Terminal,
        b"private-url-password-profile-payload",
    );
    let fact = WebviewFailure::process(
        Some(3),
        Some(3),
        Some(0x8000_0003_u32 as i32),
        ReadFailures::default(),
    );
    diagnostics.webview_failure(fact);
    let snapshot = diagnostics.snapshot(u64::MAX);
    let event = snapshot.events.last().unwrap();
    assert!(matches!(event.kind, EventKind::Failure));
    assert_eq!(event.stage, Some(HostStage::Window));
    assert_eq!(event.webview_failure, Some(fact));
    assert!(event.process.is_none() && event.status.is_none() && event.role.is_none());
    assert!(event.host_exit_code.is_none());
    assert_eq!(
        event.failure.as_ref().unwrap().code,
        ErrorCode::WebviewProcessFailed
    );
    assert_eq!(
        event.failure.as_ref().unwrap().operation,
        Operation::Webview
    );
    let log = fs::read_to_string(snapshot.paths.unwrap().current).unwrap();
    assert!(!log.contains("private-url-password-profile-payload"));
    let record: Value = serde_json::from_str(log.lines().last().unwrap()).unwrap();
    assert_eq!(
        record["webviewFailure"],
        json!({
            "event": "process_failed",
            "kind": "frame_render_process_exited",
            "kindCode": 3,
            "reason": "crashed",
            "reasonCode": 3,
            "exitCode": -2_147_483_645_i32,
            "readFailures": {}
        })
    );
    assert!(!log.contains("processDescription") && !log.contains("failureSourceModulePath"));
}

#[test]
fn unresponsive_renderer_is_not_a_confirmed_exit_and_retention_stays_bounded() {
    let diagnostics = Diagnostics::default();
    for _ in 0..600 {
        diagnostics.webview_failure(WebviewFailure::process(
            Some(2),
            Some(1),
            Some(259),
            ReadFailures::default(),
        ));
    }
    let snapshot = diagnostics.snapshot(u64::MAX);
    assert_eq!(snapshot.events.len(), 512);
    assert!(snapshot.processes.is_empty() && snapshot.output.is_empty());
    assert_eq!(snapshot.events[0].sequence, 89);
    for event in snapshot.events {
        assert!(
            event.process.is_none() && event.status.is_none() && event.host_exit_code.is_none()
        );
        let fact = serde_json::to_value(event.webview_failure.unwrap()).unwrap();
        assert_eq!(fact["kind"], "render_process_unresponsive");
        assert_eq!(fact["reason"], "unresponsive");
        assert_eq!(fact["exitCode"], 259);
    }
}

#[test]
fn unknown_codes_partial_reads_and_monitor_refusal_remain_explicit() {
    let diagnostics = Diagnostics::default();
    diagnostics.webview_failure(WebviewFailure::process(
        Some(i32::MAX),
        Some(-9),
        None,
        ReadFailures {
            exit_code_hresult: Some(-2_147_467_259),
            ..ReadFailures::default()
        },
    ));
    diagnostics.webview_failure(WebviewFailure::process(
        None,
        None,
        None,
        ReadFailures {
            arguments_hresult: Some(-2_147_467_261),
            ..ReadFailures::default()
        },
    ));
    diagnostics.webview_failure(WebviewFailure::MonitorUnavailable {
        operation: MonitorOperation::Register,
        hresult: Some(-2_147_467_259),
    });
    let snapshot = diagnostics.snapshot(u64::MAX);
    let first = serde_json::to_value(&snapshot.events[0]).unwrap();
    assert_eq!(first["webviewFailure"]["kind"], "unrecognized");
    assert_eq!(first["webviewFailure"]["kindCode"], i32::MAX);
    assert_eq!(first["webviewFailure"]["reason"], "unrecognized");
    assert_eq!(first["webviewFailure"]["reasonCode"], -9);
    assert_eq!(
        first["webviewFailure"]["readFailures"]["exitCodeHresult"],
        -2_147_467_259_i32
    );
    let missing = serde_json::to_value(&snapshot.events[1]).unwrap();
    assert_eq!(missing["webviewFailure"]["kind"], Value::Null);
    assert_eq!(
        missing["webviewFailure"]["readFailures"]["argumentsHresult"],
        -2_147_467_261_i32
    );
    assert_eq!(
        snapshot.events[2].failure.as_ref().unwrap().code,
        ErrorCode::WebviewMonitorUnavailable
    );
    assert_eq!(
        serde_json::to_value(&snapshot.events[2]).unwrap()["webviewFailure"],
        json!({
            "event": "monitor_unavailable", "operation": "register", "hresult": -2_147_467_259_i32
        })
    );
    assert!(snapshot.processes.is_empty());
}

#[test]
fn known_enum_codes_follow_the_pinned_webview2_contract() {
    let kind_names = [
        "browser_process_exited",
        "render_process_exited",
        "render_process_unresponsive",
        "frame_render_process_exited",
        "utility_process_exited",
        "sandbox_helper_process_exited",
        "gpu_process_exited",
        "ppapi_plugin_process_exited",
        "ppapi_broker_process_exited",
        "unknown_process_exited",
    ];
    for (code, name) in kind_names.iter().enumerate() {
        assert_eq!(
            serde_json::to_value(ProcessKind::from_code(code as i32)).unwrap(),
            *name
        );
    }
    let reason_names = [
        "unexpected",
        "unresponsive",
        "terminated",
        "crashed",
        "launch_failed",
        "out_of_memory",
        "profile_deleted",
    ];
    for (code, name) in reason_names.iter().enumerate() {
        assert_eq!(
            serde_json::to_value(FailureReason::from_code(code as i32)).unwrap(),
            *name
        );
    }
    assert_eq!(ProcessKind::from_code(-1), ProcessKind::Unrecognized);
    assert_eq!(FailureReason::from_code(7), FailureReason::Unrecognized);
}
