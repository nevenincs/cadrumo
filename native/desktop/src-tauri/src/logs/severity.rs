use super::format::Level;
use cadrumo_application::diagnostics::{
    Event, EventKind, HostOutcome,
    helper::{HelperDecode, HelperOutcome},
    lifecycle::{LifecycleFact, RuntimeExit, RuntimeReason, SupervisorOutcome},
    service::{AgentRefusal, ServiceFact},
};
use cadrumo_application::process::status::ProcessRole;

const PROJECT_LOGGER_ROOTS: [&str; 5] = [
    "cadrumo",
    "cadrumo_client",
    "cadrumo_mcp",
    "cadrumo_runtime",
    "cadrumo_agent_service",
];

fn is_project_python_logger(name: &str) -> bool {
    PROJECT_LOGGER_ROOTS.iter().any(|root| {
        name == *root
            || name
                .strip_prefix(root)
                .is_some_and(|suffix| suffix.starts_with('.'))
    })
}

pub fn level(event: &Event) -> Level {
    if matches!(event.kind, EventKind::Panic) {
        return Level::Critical;
    }
    if event.failure.is_some() || event.webview_failure.is_some() {
        return Level::Error;
    }
    if let Some(fact) = event.lifecycle {
        return lifecycle(fact);
    }
    if let Some(fact) = event.service {
        return match fact {
            ServiceFact::AgentRefused {
                reason: AgentRefusal::SignedOut,
            } => Level::Debug,
            // No provider key yet is a state the agent column offers a way out of, not a fault.
            ServiceFact::AgentRefused {
                reason: AgentRefusal::ProviderCredentialMissing,
            } => Level::Info,
            ServiceFact::AgentRefused { .. } | ServiceFact::AgentProtocolRefused {} => Level::Error,
            ServiceFact::AgentRetryScheduled { .. } => Level::Warning,
            // The window says why and offers a way on; nothing here failed.
            ServiceFact::FeatureRefused { .. } => Level::Warning,
            ServiceFact::AgentRetryExhausted { .. } => Level::Error,
            ServiceFact::EnvironmentResolved { .. } => Level::Debug,
            ServiceFact::AgentReady { .. } | ServiceFact::ManagerInstallationCompleted { .. } => {
                Level::Info
            }
            _ => Level::Debug,
        };
    }
    if let Some(fact) = &event.helper_result {
        return match fact.envelope_decode {
            HelperDecode::Success => Level::Debug,
            HelperDecode::Refused
                if fact.command == "config.login"
                    && fact.code.as_deref() == Some("REFUSED_CLI_BOUNDARY")
                    && matches!(
                        fact.reason.as_deref(),
                        Some("credential_rejected" | "throttled")
                    ) =>
            {
                Level::Warning
            }
            _ => Level::Error,
        };
    }
    // Helper envelopes own the outcome classification. Exit and timing facts
    // remain available without multiplying one refusal into several failures.
    if event
        .status
        .as_ref()
        .is_some_and(|s| s.role == ProcessRole::SignIn)
        && (matches!(event.kind, EventKind::ChildExited)
            || (matches!(event.kind, EventKind::HelperTiming)
                && event
                    .helper_timing
                    .is_some_and(|fact| fact.outcome == HelperOutcome::NonzeroExit)))
    {
        return Level::Debug;
    }
    match event.kind {
        EventKind::Failure => Level::Error,
        EventKind::HostStopped if event.host_exit_code != Some(0) => Level::Error,
        EventKind::ChildExited
            if event
                .status
                .as_ref()
                .is_some_and(|s| s.exit_code != Some(0)) =>
        {
            Level::Error
        }
        EventKind::ChildTerminated => Level::Debug,
        EventKind::HelperTiming
            if event
                .status
                .as_ref()
                .is_some_and(|s| s.exit_code.is_some_and(|code| code != 0)) =>
        {
            Level::Error
        }
        EventKind::HelperTiming => match event.helper_timing.map(|fact| fact.outcome) {
            Some(HelperOutcome::Completed) => Level::Debug,
            _ => Level::Error,
        },
        EventKind::StageCompleted if event.outcome == Some(HostOutcome::Unavailable) => {
            Level::Error
        }
        EventKind::StageStarted | EventKind::StageCompleted => Level::Debug,
        EventKind::ChildStarted
        | EventKind::ChildExited
        | EventKind::HostStarted
        | EventKind::HostStopped
        | EventKind::WindowCloseRequested
        | EventKind::HostExitRequested => Level::Debug,
        _ => Level::Debug,
    }
}

/// Normalize known application diagnostics already retained with old, incorrect levels.
/// Operator messages and foreign loggers keep the level the producer supplied.
pub fn python_level(
    original: Option<Level>,
    logger: Option<&str>,
    message: &str,
    context: &std::collections::BTreeMap<String, serde_json::Value>,
) -> Option<Level> {
    if !logger.is_some_and(is_project_python_logger)
        || matches!(original, Some(Level::Error | Level::Critical))
    {
        return original;
    }
    let outcome = context.get("outcome").and_then(serde_json::Value::as_str);
    if matches!(outcome, Some("failed" | "error" | "unconfirmed")) || message.ends_with("_failed") {
        return Some(Level::Error);
    }
    if message.starts_with("runtime_startup phase=") {
        return Some(Level::Debug);
    }
    let code = context.get("exit_code").and_then(serde_json::Value::as_i64);
    match message {
        "runtime_process_exited" => Some(if matches!(code, Some(64..=66)) {
            Level::Debug
        } else {
            Level::Error
        }),
        "tui_process_exited" | "profile_worker_process_exited" => Some(if code == Some(0) {
            Level::Debug
        } else {
            Level::Error
        }),
        "kdf_worker_lifecycle" if outcome == Some("completed") => Some(Level::Debug),
        "runtime_process_started"
        | "profile_worker_process_started"
        | "profile_worker_admitted"
        | "tui_process_started"
        | "tui_inventory_observed"
        | "tui_session_recompose_requested"
        | "runtime_connect_started"
        | "runtime_listener_drain_started"
        | "runtime_listener_drain_completed"
        | "tui_login_connect_started"
        | "tui_login_proof_started"
        | "tui_login_connection_cleanup_started" => Some(Level::Debug),
        _ => original,
    }
}

fn lifecycle(fact: LifecycleFact) -> Level {
    use LifecycleFact::*;
    match fact {
        AdmissionRefused { .. }
        | InspectionRefused { .. }
        | LaunchFailed {}
        | BootRecordMismatch { .. }
        | HangDetected { .. }
        | TerminationFailed { .. }
        | TerminationUnconfirmed { .. }
        | ProcessInspectionFailed { .. }
        | EffectsUnknown { .. }
        | Failed { .. } => Level::Error,
        Exited { exit, .. } => match exit {
            RuntimeExit::Crash { .. } | RuntimeExit::LaunchFailure { .. } => Level::Error,
            RuntimeExit::Reason {
                reason: RuntimeReason::UnexpectedFailure | RuntimeReason::DrainWatchdog,
                ..
            } => Level::Error,
            RuntimeExit::ControlC {} | RuntimeExit::Terminated {} | RuntimeExit::Unknown {} => {
                Level::Warning
            }
            RuntimeExit::Reason {
                reason:
                    RuntimeReason::SupervisorStop
                    | RuntimeReason::SignalStop
                    | RuntimeReason::SessionEndSettle,
                ..
            }
            | RuntimeExit::Zero {} => Level::Debug,
            RuntimeExit::Reason {
                reason: RuntimeReason::LoginWitnessLoss,
                ..
            } => Level::Warning,
            RuntimeExit::Reason { .. } => Level::Error,
        },
        SupervisorEnded {
            result: SupervisorOutcome::Failed { .. },
            ..
        } => Level::Error,
        AnnouncementRefused { .. }
        | CommandRefused { .. }
        | ChannelClosed { .. }
        | IdleStopUnavailable { .. }
        | TerminationRequested { .. }
        | Terminated { .. }
        | RestartScheduled { .. }
        | Foreign { .. }
        | StoodDown { .. }
        | EventsDropped { .. } => Level::Warning,
        Waiting { .. }
        | RestartDeferred { .. }
        | Busy { .. }
        | BootRecordConfirmed { .. }
        | VersionReprobed {} => Level::Debug,
        Ready { .. } => Level::Info,
        _ => Level::Debug,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use cadrumo_application::{
        diagnostics::{
            Diagnostics, HostStage,
            service::{FeatureRefusal, RefusedFeature},
        },
        process::status::ProcessRole,
        provisioning::items::ItemId,
    };

    #[test]
    fn helper_refusal_has_one_warning_and_bad_output_still_has_one_error() {
        use cadrumo_application::diagnostics::helper::{
            HelperExecutable, HelperIdentity, HelperKind, HelperResult, HelperTiming,
        };
        use cadrumo_application::process::status::ProcessPhase;
        let identity = HelperIdentity {
            command: "config.login",
            executable: HelperExecutable::Cli,
        };
        let refusal = serde_json::json!({
            "schema_version": "2", "command": "config.login", "status": "error",
            "error": { "code": "REFUSED_CLI_BOUNDARY", "context": { "reason": "credential_rejected" } }
        }).to_string();
        for (stderr, expected) in [
            (refusal.as_bytes(), Level::Warning),
            (b"broken child".as_slice(), Level::Error),
        ] {
            let diagnostics = Diagnostics::default();
            let id = diagnostics.start(4200, ProcessRole::SignIn);
            diagnostics.finish_helper(id, Some(2), ProcessPhase::Exited);
            diagnostics.helper_result(
                Some(id),
                HelperResult::inspect(identity, false, b"", stderr),
                None,
            );
            diagnostics.helper_timing(
                Some(id),
                HelperTiming {
                    helper_kind: HelperKind::Mutation,
                    outcome: HelperOutcome::NonzeroExit,
                    admission_wait_ms: 0,
                    spawn_ms: Some(1),
                    execution_ms: Some(500),
                    cleanup_ms: Some(1),
                    output_join_ms: Some(0),
                    total_ms: 502,
                },
            );
            let events = diagnostics.snapshot(0).events;
            assert_eq!(
                events.iter().map(level).collect::<Vec<_>>(),
                [Level::Debug, Level::Debug, expected, Level::Debug]
            );
            assert_eq!(events[1].status.as_ref().unwrap().exit_code, Some(2));
            assert!(events[1].failure.is_none());
        }
        let diagnostics = Diagnostics::default();
        let id = diagnostics.start(4201, ProcessRole::SignIn);
        diagnostics.finish_helper(id, None, ProcessPhase::Failed);
        assert_eq!(
            level(diagnostics.snapshot(0).events.last().unwrap()),
            Level::Error
        );
    }

    #[test]
    fn owned_python_logger_families_are_closed_at_the_package_boundary() {
        for name in [
            "cadrumo",
            "cadrumo.application.workflow",
            "cadrumo_client.commands.stdio",
            "cadrumo_mcp.mcp",
            "cadrumo_runtime.adapters.server",
            "cadrumo_agent_service.host.controller",
        ] {
            assert!(is_project_python_logger(name), "{name}");
        }
        for name in [
            "cadrumo_clientish.commands",
            "cadrumo_mcp_vendor.mcp",
            "cadrumo_runtimeish.adapters.server",
            "cadrumo_agent_service_vendor.host.controller",
            "foreign_runtime.adapters.server",
        ] {
            assert!(!is_project_python_logger(name), "{name}");
        }
    }

    #[test]
    fn retained_python_failures_and_trace_rows_are_corrected_without_demoting_real_info() {
        use serde_json::json;
        use std::collections::BTreeMap;
        assert_eq!(
            python_level(
                Some(Level::Info),
                Some("cadrumo_runtime.adapters.server"),
                "runtime_startup phase=listener_listen transition=leave elapsed_seconds=0.008000",
                &BTreeMap::new()
            ),
            Some(Level::Debug)
        );
        let failure = BTreeMap::from([("outcome".to_owned(), json!("failed"))]);
        assert_eq!(
            python_level(
                Some(Level::Info),
                Some("cadrumo.worker"),
                "worker_lifecycle",
                &failure
            ),
            Some(Level::Error)
        );
        let normal = BTreeMap::from([("exit_code".to_owned(), json!(64))]);
        assert_eq!(
            python_level(
                Some(Level::Info),
                Some("cadrumo_runtime.host.main"),
                "runtime_process_exited",
                &normal
            ),
            Some(Level::Debug)
        );
        assert_eq!(
            python_level(
                Some(Level::Info),
                Some("cadrumo.worker"),
                "service ready",
                &BTreeMap::new()
            ),
            Some(Level::Info)
        );
        assert_eq!(
            python_level(
                Some(Level::Info),
                Some("other.worker"),
                "worker_lifecycle",
                &failure
            ),
            Some(Level::Info)
        );
        assert_eq!(
            python_level(
                Some(Level::Error),
                Some("cadrumo.worker"),
                "runtime_process_started",
                &normal
            ),
            Some(Level::Error)
        );
    }

    #[test]
    fn startup_detail_is_debug_and_process_failures_are_errors() {
        let diagnostics = Diagnostics::default();
        diagnostics.event(EventKind::HostStarted, None, None);
        diagnostics.host_event(EventKind::StageStarted, HostStage::Environment);
        diagnostics.host_outcome(HostStage::Environment, HostOutcome::Ready);
        let process = diagnostics.start(4200, ProcessRole::SignIn);
        diagnostics.finish(
            process,
            Some(7),
            cadrumo_application::process::status::ProcessPhase::Exited,
        );
        diagnostics.host_stopped(1);
        assert_eq!(
            diagnostics
                .snapshot(u64::MAX)
                .events
                .iter()
                .map(level)
                .collect::<Vec<_>>(),
            [
                Level::Debug,
                Level::Debug,
                Level::Debug,
                Level::Debug,
                Level::Error,
                Level::Error
            ]
        );
    }

    #[test]
    fn routine_process_churn_is_debug_for_every_child_role() {
        use cadrumo_application::process::status::ProcessPhase;
        for role in [
            ProcessRole::Environment,
            ProcessRole::SignIn,
            ProcessRole::ManagerDispatch,
            ProcessRole::Cli,
            ProcessRole::AgentLauncher,
            ProcessRole::Tui,
            ProcessRole::Repl,
            ProcessRole::Console,
        ] {
            let diagnostics = Diagnostics::default();
            let process = diagnostics.start(4200, role);
            diagnostics.finish(process, Some(0), ProcessPhase::Exited);
            let events = diagnostics.snapshot(u64::MAX).events;
            assert!(events.iter().all(|event| level(event) == Level::Debug));
            let process = diagnostics.start(4201, role);
            diagnostics.finish(process, Some(1), ProcessPhase::Terminated);
            assert_eq!(
                level(diagnostics.snapshot(u64::MAX).events.last().unwrap()),
                Level::Debug
            );
            let process = diagnostics.start(4202, role);
            diagnostics.finish(process, Some(1), ProcessPhase::Exited);
            let mut snapshot = diagnostics.snapshot(u64::MAX);
            let event = snapshot.events.pop().unwrap();
            assert_eq!(level(&event), Level::Error);
            assert_eq!(
                event.failure.unwrap().code,
                cadrumo_application::error::application::ErrorCode::ChildFailed
            );
        }
    }

    #[test]
    fn runtime_admission_failures_are_errors_even_with_reserved_exit_codes() {
        for reason in [
            RuntimeReason::OwnerBusy,
            RuntimeReason::RootMismatch,
            RuntimeReason::VersionMismatch,
            RuntimeReason::ElevatedTokenRefused,
            RuntimeReason::UnexpectedFailure,
            RuntimeReason::DrainWatchdog,
        ] {
            assert_eq!(
                lifecycle(LifecycleFact::Exited {
                    pid: 42,
                    exit: RuntimeExit::Reason { reason, code: 67 },
                    announced: None
                }),
                Level::Error
            );
        }
    }

    #[test]
    fn runtime_crashes_do_not_inherit_the_stage_completed_level() {
        let diagnostics = Diagnostics::default();
        for (fact, expected) in [
            (
                LifecycleFact::Exited {
                    pid: 42,
                    exit: RuntimeExit::Crash { code: 0xc0000005 },
                    announced: None,
                },
                Level::Error,
            ),
            (
                LifecycleFact::RestartScheduled {
                    class: cadrumo_application::diagnostics::lifecycle::RestartClass::Unexpected,
                    delay_ms: 1000,
                },
                Level::Warning,
            ),
            (LifecycleFact::Ready { pid: 42 }, Level::Info),
            (LifecycleFact::BootRecordConfirmed { pid: 42 }, Level::Debug),
        ] {
            diagnostics.lifecycle(
                EventKind::StageCompleted,
                HostStage::Supervision,
                fact,
                None,
            );
            assert_eq!(
                level(diagnostics.snapshot(u64::MAX).events.last().unwrap()),
                expected
            );
        }
    }

    #[test]
    fn service_lifecycle_distinguishes_readiness_refusals_and_retry() {
        let diagnostics = Diagnostics::default();
        for (fact, expected) in [
            (
                ServiceFact::AgentReady {
                    generation: 1,
                    gateway_port: 4444,
                },
                Level::Info,
            ),
            (
                ServiceFact::AgentRefused {
                    reason: AgentRefusal::SignedOut,
                },
                Level::Debug,
            ),
            (
                ServiceFact::AgentRefused {
                    reason: AgentRefusal::ProviderCredentialMissing,
                },
                Level::Info,
            ),
            (
                ServiceFact::AgentRefused {
                    reason: AgentRefusal::ServiceFailed,
                },
                Level::Error,
            ),
            (ServiceFact::AgentProtocolRefused {}, Level::Error),
            (
                ServiceFact::AgentRetryScheduled { delay_ms: 30000 },
                Level::Warning,
            ),
            (
                ServiceFact::FeatureRefused {
                    feature: RefusedFeature::SedeView,
                    refusal: FeatureRefusal::ComponentNotReady,
                    item: Some(ItemId::Browser),
                },
                Level::Warning,
            ),
        ] {
            diagnostics.service(None, fact);
            assert_eq!(
                level(diagnostics.snapshot(u64::MAX).events.last().unwrap()),
                expected
            );
        }
    }
}
