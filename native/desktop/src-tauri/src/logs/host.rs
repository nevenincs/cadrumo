//! Desktop-host records: the host's diagnostics events, and nothing else.
//!
//! Only `Diagnostics` events are read. Captured process output, which can hold
//! terminal bytes, is never requested from the snapshot.
use super::{
    format::Level,
    record::{Entry, ProcessRef},
};
use cadrumo_application::diagnostics::{DiagnosticSource, Diagnostics, Event, EventKind};
use serde::Serialize;
use serde_json::Value;
use std::collections::BTreeMap;

pub const SOURCE: &str = "host";
const LOGGER: &str = "desktop";

/// Tracks which diagnostics events were already turned into records.
///
/// Sequence numbers identify events even when their content and timestamps
/// are identical and the diagnostics ring has wrapped.
#[derive(Default)]
pub struct HostEvents {
    after: u64,
}

impl HostEvents {
    pub fn poll(&mut self, diagnostics: &Diagnostics) -> Vec<Entry> {
        // A cursor past every output chunk keeps captured output out.
        let events = diagnostics.snapshot(u64::MAX).events;
        let fresh = events
            .iter()
            .filter(|event| event.sequence > self.after)
            .map(entry)
            .collect();
        if let Some(last) = events.last() {
            self.after = last.sequence;
        }
        fresh
    }
}

fn token(value: impl Serialize) -> String {
    serde_json::to_value(value)
        .ok()
        .and_then(|value| value.as_str().map(str::to_owned))
        .unwrap_or_default()
}

pub(super) fn entry(event: &Event) -> Entry {
    let (source, logger) = match event.source {
        DiagnosticSource::Desktop => (SOURCE, LOGGER),
        DiagnosticSource::Manager => ("manager", "manager"),
    };
    let process = event.status.as_ref().map_or_else(
        || ProcessRef {
            role: logger.to_owned(),
            pid: event.host_pid,
        },
        |status| ProcessRef {
            role: token(status.role),
            pid: status.pid,
        },
    );
    let mut context = BTreeMap::from([
        ("event_id".to_owned(), Value::from(event.sequence)),
        ("host_pid".to_owned(), Value::from(event.host_pid)),
        ("process_id".to_owned(), Value::from(process.pid)),
        ("process_role".to_owned(), Value::from(process.role.clone())),
    ]);
    if let Some(stage) = event.stage {
        context.insert("stage".into(), Value::from(token(stage)));
    }
    if let Some(outcome) = event.outcome {
        context.insert("outcome".into(), Value::from(token(outcome)));
    }
    if let Some(code) = event.host_exit_code {
        context.insert("exit_code".into(), Value::from(code));
    }
    if let Some(role) = event.role
        && event.status.is_none()
    {
        context.insert("requested_role".into(), Value::from(token(role)));
    }
    if let Some(status) = &event.status {
        context.insert("process_ref".into(), Value::from(status.id));
        context.insert("phase".into(), Value::from(token(status.phase)));
        if let Some(code) = status.exit_code {
            context.insert("exit_code".into(), Value::from(code));
        }
    }
    if let Some(failure) = &event.failure {
        context.insert("reason_code".into(), Value::from(token(failure.code)));
        context.insert("operation".into(), Value::from(token(failure.operation)));
        if let Some(kind) = &failure.io_kind {
            context.insert("io_kind".into(), Value::from(format!("{kind:?}")));
        }
        if let Some(code) = failure.os_code {
            context.insert("os_code".into(), Value::from(code));
        }
    }
    if let Some(fact) = event.lifecycle {
        super::manager::lifecycle_context(fact, &mut context);
    }
    if let Some(fact) = event.webview_failure {
        webview_context(fact, &mut context);
    }
    if let Some(fact) = event.helper_timing {
        context.insert("helper_kind".into(), Value::from(token(fact.helper_kind)));
        context.insert("outcome".into(), Value::from(token(fact.outcome)));
        context.insert(
            "admission_wait_ms".into(),
            Value::from(fact.admission_wait_ms),
        );
        context.insert("total_ms".into(), Value::from(fact.total_ms));
        for (name, elapsed) in [
            ("spawn_ms", fact.spawn_ms),
            ("execution_ms", fact.execution_ms),
            ("cleanup_ms", fact.cleanup_ms),
            ("output_join_ms", fact.output_join_ms),
        ] {
            context.insert(name.into(), elapsed.map_or(Value::Null, Value::from));
        }
    }
    let mut message = token(event.kind);
    if let Some(fact) = event.lifecycle {
        let encoded = serde_json::to_value(fact).expect("closed lifecycle fact serializes");
        if let Some(name) = encoded["event"].as_str() {
            message.push_str(": ");
            message.push_str(name);
        }
        if let Some(pid) = context.get("runtime_pid").and_then(Value::as_u64) {
            message.push_str(&format!(" runtime pid {pid}"));
        }
    }
    if let Some(status) = &event.status {
        message.push_str(&format!(
            ": {} pid {}",
            serde_json::to_value(status.role)
                .ok()
                .and_then(|value| value.as_str().map(str::to_owned))
                .unwrap_or_default(),
            status.pid
        ));
        if let Some(code) = status.exit_code {
            message.push_str(&format!(", exit code {code}"));
        }
    }
    if let Some(failure) = &event.failure {
        message.push_str(&format!(
            ": {} during {}: {}",
            serde_json::to_value(failure.code)
                .ok()
                .and_then(|value| value.as_str().map(str::to_owned))
                .unwrap_or_default(),
            serde_json::to_value(failure.operation)
                .ok()
                .and_then(|value| value.as_str().map(str::to_owned))
                .unwrap_or_default(),
            failure.message
        ));
    }
    let level = match event.kind {
        EventKind::Failure => Level::Error,
        EventKind::ChildTerminated => Level::Warning,
        EventKind::ChildExited
            if event
                .status
                .as_ref()
                .is_some_and(|status| status.exit_code != Some(0)) =>
        {
            Level::Warning
        }
        _ => Level::Info,
    };
    Entry {
        source,
        timestamp: utc(event.timestamp_ms),
        timestamp_ms: Some(event.timestamp_ms),
        level: Some(level),
        logger: Some(logger.to_owned()),
        message,
        detail: None,
        process: Some(process),
        context,
    }
}

fn webview_context(
    fact: cadrumo_application::diagnostics::webview::WebviewFailure,
    context: &mut BTreeMap<String, Value>,
) {
    use cadrumo_application::diagnostics::webview::WebviewFailure;
    match fact {
        WebviewFailure::ProcessFailed {
            kind,
            kind_code,
            reason,
            reason_code,
            exit_code,
            read_failures,
        } => {
            context.insert("webview_event".into(), Value::from("process_failed"));
            if let Some(kind) = kind {
                context.insert("webview_process_kind".into(), Value::from(token(kind)));
            }
            if let Some(reason) = reason {
                context.insert("webview_reason".into(), Value::from(token(reason)));
            }
            for (name, code) in [
                ("webview_process_kind_code", kind_code),
                ("webview_reason_code", reason_code),
                ("webview_exit_code", exit_code),
                ("webview_arguments_hresult", read_failures.arguments_hresult),
                ("webview_kind_hresult", read_failures.kind_hresult),
                ("webview_details_hresult", read_failures.details_hresult),
                ("webview_reason_hresult", read_failures.reason_hresult),
                ("webview_exit_code_hresult", read_failures.exit_code_hresult),
            ] {
                if let Some(code) = code {
                    context.insert(name.into(), Value::from(code));
                }
            }
        }
        WebviewFailure::MonitorUnavailable { operation, hresult } => {
            context.insert("webview_event".into(), Value::from("monitor_unavailable"));
            context.insert(
                "webview_monitor_operation".into(),
                Value::from(token(operation)),
            );
            if let Some(hresult) = hresult {
                context.insert("webview_hresult".into(), Value::from(hresult));
            }
        }
    }
}

/// RFC 3339 UTC text with milliseconds for epoch milliseconds.
fn utc(epoch_ms: u64) -> String {
    let days = epoch_ms / 86_400_000;
    let rest = epoch_ms % 86_400_000;
    // Civil date from days since 1970-01-01 (Howard Hinnant's algorithm).
    let z = days as i64 + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = yoe + era * 400 + i64::from(month <= 2);
    format!(
        "{year:04}-{month:02}-{day:02}T{:02}:{:02}:{:02}.{:03}Z",
        rest / 3_600_000,
        rest / 60_000 % 60,
        rest / 1_000 % 60,
        rest % 1_000
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use cadrumo_application::{
        diagnostics::helper::{HelperKind, HelperOutcome, HelperTiming},
        error::application::{ApplicationError, ErrorCode, Operation},
        process::status::{ProcessPhase, ProcessRole, Stream},
    };

    #[test]
    fn helper_phase_durations_project_as_closed_scalars_without_child_output() {
        let diagnostics = Diagnostics::default();
        let id = diagnostics.start(4242, ProcessRole::SignIn);
        diagnostics.capture(id, Stream::Stdout, b"private-helper-output-canary");
        diagnostics.finish(id, Some(7), ProcessPhase::Exited);
        diagnostics.helper_timing(
            Some(id),
            HelperTiming {
                helper_kind: HelperKind::Mutation,
                outcome: HelperOutcome::Completed,
                admission_wait_ms: 250,
                spawn_ms: Some(20),
                execution_ms: Some(900),
                cleanup_ms: Some(1),
                output_join_ms: Some(2),
                total_ms: 1180,
            },
        );
        diagnostics.helper_timing(
            None,
            HelperTiming {
                helper_kind: HelperKind::Read,
                outcome: HelperOutcome::AdmissionRefused,
                admission_wait_ms: 30000,
                spawn_ms: None,
                execution_ms: None,
                cleanup_ms: None,
                output_join_ms: None,
                total_ms: 30001,
            },
        );
        let mut host = HostEvents::default();
        let entries = host.poll(&diagnostics);
        let completed = &entries[2];
        assert!(
            completed
                .message
                .starts_with("helper_timing: sign_in pid 4242")
        );
        assert_eq!(completed.context["helper_kind"], "mutation");
        assert_eq!(completed.context["outcome"], "completed");
        assert_eq!(completed.context["process_ref"], id);
        assert_eq!(completed.context["exit_code"], 7);
        assert_eq!(completed.context["admission_wait_ms"], 250);
        assert_eq!(completed.context["spawn_ms"], 20);
        assert_eq!(completed.context["execution_ms"], 900);
        assert_eq!(completed.context["cleanup_ms"], 1);
        assert_eq!(completed.context["output_join_ms"], 2);
        assert_eq!(completed.context["total_ms"], 1180);
        let refused = &entries[3];
        assert_eq!(refused.context["outcome"], "admission_refused");
        assert!(refused.context["spawn_ms"].is_null());
        assert!(!refused.context.contains_key("process_ref"));
        assert_eq!(refused.context["requested_role"], "sign_in");
        assert!(host.poll(&diagnostics).is_empty());
        for entry in entries {
            assert!(!format!("{entry:?}").contains("private-helper-output-canary"));
            assert!(entry.context.len() <= 32);
            assert!(
                entry
                    .context
                    .values()
                    .all(|value| !value.is_array() && !value.is_object())
            );
        }
    }

    #[test]
    fn utc_text_matches_known_instants() {
        assert_eq!(utc(0), "1970-01-01T00:00:00.000Z");
        assert_eq!(utc(951_782_400_000), "2000-02-29T00:00:00.000Z");
        assert_eq!(utc(1_791_117_001_042), "2026-10-04T12:30:01.042Z");
        assert_eq!(utc(4_107_542_399_999), "2100-02-28T23:59:59.999Z");
    }

    #[test]
    fn events_become_records_once_and_captured_output_never_does() {
        let diagnostics = Diagnostics::default();
        let mut host = HostEvents::default();
        diagnostics.event(EventKind::HostStarted, None, None);
        let id = diagnostics.start(4242, ProcessRole::Tui);
        diagnostics.capture(id, Stream::Terminal, b"PTY-PAYLOAD-7f3a");
        diagnostics.capture(id, Stream::Stdout, b"STDOUT-PAYLOAD-7f3a");
        let first = host.poll(&diagnostics);
        assert_eq!(
            first.iter().map(|e| e.message.as_str()).collect::<Vec<_>>(),
            ["host_started", "child_started: tui pid 4242"]
        );
        assert!(host.poll(&diagnostics).is_empty());
        diagnostics.finish(id, Some(3), ProcessPhase::Exited);
        diagnostics.failure(ApplicationError::new(
            ErrorCode::SpawnFailed,
            Operation::Terminal,
        ));
        let second = host.poll(&diagnostics);
        assert_eq!(second.len(), 2);
        assert_eq!(second[0].message, "child_exited: tui pid 4242, exit code 3");
        assert_eq!(second[0].level, Some(Level::Warning));
        assert_eq!(
            second[0].process,
            Some(ProcessRef {
                role: "tui".to_owned(),
                pid: 4242
            })
        );
        assert_eq!(
            second[1].message,
            "failure: spawn_failed during terminal: The child process could not be started"
        );
        assert_eq!(second[1].level, Some(Level::Error));
        for entry in first.iter().chain(&second) {
            assert_eq!(entry.source, SOURCE);
            assert!(entry.timestamp_ms.is_some() && entry.timestamp.ends_with('Z'));
            assert!(!format!("{entry:?}").contains("7f3a"));
        }
    }

    #[test]
    fn full_diagnostics_ring_yields_only_new_events() {
        let diagnostics = Diagnostics::default();
        let mut host = HostEvents::default();
        for pid in 0..600 {
            diagnostics.start(pid, ProcessRole::Cli);
        }
        assert_eq!(host.poll(&diagnostics).len(), 512);
        diagnostics.start(9_999, ProcessRole::Cli);
        let fresh = host.poll(&diagnostics);
        assert_eq!(fresh.len(), 1);
        assert_eq!(fresh[0].message, "child_started: cli pid 9999");
    }

    #[test]
    fn stage_outcomes_and_safe_failure_fields_reach_the_view() {
        use cadrumo_application::diagnostics::{HostOutcome, HostStage};
        let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
        diagnostics.host_outcome(HostStage::Manager, HostOutcome::AlreadyRunning);
        diagnostics.spawn_failure(
            ProcessRole::Tui,
            ApplicationError::new(ErrorCode::SpawnFailed, Operation::Terminal)
                .caused_by(std::io::Error::from_raw_os_error(2)),
        );
        let mut host = HostEvents::default();
        let records = host.poll(&diagnostics);
        assert_eq!(records[0].source, "manager");
        assert_eq!(records[0].context["stage"], "manager");
        assert_eq!(records[0].context["outcome"], "already_running");
        assert_eq!(records[1].context["requested_role"], "tui");
        assert_eq!(records[1].context["reason_code"], "spawn_failed");
        assert_eq!(records[1].context["os_code"], 2);
        assert_eq!(records[1].process.as_ref().unwrap().role, "manager");
        assert!(host.poll(&diagnostics).is_empty());
        for _ in 0..600 {
            diagnostics.host_outcome(HostStage::Manager, HostOutcome::AlreadyRunning);
        }
        assert_eq!(host.poll(&diagnostics).len(), 512);
        diagnostics.host_outcome(HostStage::Manager, HostOutcome::AlreadyRunning);
        assert_eq!(host.poll(&diagnostics).len(), 1);
    }

    #[test]
    fn webview_failure_context_keeps_numeric_telemetry_and_host_attribution() {
        use cadrumo_application::diagnostics::webview::{
            MonitorOperation, ReadFailures, WebviewFailure,
        };
        let diagnostics = Diagnostics::default();
        diagnostics.webview_failure(WebviewFailure::process(
            Some(2),
            Some(1),
            Some(259),
            ReadFailures::default(),
        ));
        diagnostics.webview_failure(WebviewFailure::process(
            Some(104),
            Some(-9),
            None,
            ReadFailures {
                exit_code_hresult: Some(-2_147_467_259),
                ..ReadFailures::default()
            },
        ));
        diagnostics.webview_failure(WebviewFailure::MonitorUnavailable {
            operation: MonitorOperation::Register,
            hresult: Some(-2_147_467_259),
        });
        let mut host = HostEvents::default();
        let entries = host.poll(&diagnostics);
        assert_eq!(
            entries[0].context["webview_process_kind"],
            "render_process_unresponsive"
        );
        assert_eq!(entries[0].context["webview_exit_code"], 259);
        assert!(!entries[0].context.contains_key("exit_code"));
        assert_eq!(entries[1].context["webview_process_kind"], "unrecognized");
        assert_eq!(entries[1].context["webview_process_kind_code"], 104);
        assert_eq!(entries[1].context["webview_reason_code"], -9);
        assert_eq!(
            entries[1].context["webview_exit_code_hresult"],
            -2_147_467_259_i32
        );
        assert_eq!(entries[2].context["webview_monitor_operation"], "register");
        assert_eq!(entries[2].context["webview_hresult"], -2_147_467_259_i32);
        assert!(host.poll(&diagnostics).is_empty());
        for entry in entries {
            assert_eq!(entry.level, Some(Level::Error));
            assert_eq!(entry.context["stage"], "window");
            assert_eq!(entry.process.as_ref().unwrap().pid, std::process::id());
            assert_eq!(entry.process.as_ref().unwrap().role, "desktop");
            assert!(entry.context.len() <= 32);
            assert!(
                entry
                    .context
                    .values()
                    .all(|value| !value.is_array() && !value.is_object())
            );
        }
    }
}
