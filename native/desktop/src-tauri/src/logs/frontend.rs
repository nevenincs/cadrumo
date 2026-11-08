use cadrumo_application::diagnostics::{
    desktop::{DesktopDiagnostic, DesktopEvent},
    service::LogLevel,
};
use std::collections::BTreeSet;
use std::sync::Arc;
use tauri::State;

pub(crate) struct RegisteredCommands(pub BTreeSet<&'static str>);

#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub(super) struct Report {
    event: DesktopEvent,
    level: LogLevel,
    command: Option<String>,
    code: Option<String>,
    dropped: u32,
    line: Option<u32>,
    column: Option<u32>,
}

pub(super) fn record(
    startup: State<'_, Arc<crate::startup::Startup>>,
    commands: State<'_, RegisteredCommands>,
    report: Report,
) {
    startup
        .diagnostics()
        .desktop_diagnostic(report.admit(&commands));
}

impl Report {
    fn admit(self, commands: &RegisteredCommands) -> DesktopDiagnostic {
        let command = self
            .command
            .and_then(|name| commands.0.get(name.as_str()).map(|name| (*name).to_owned()));
        let code = self
            .code
            .and_then(|code| serde_json::from_value(serde_json::Value::String(code)).ok());
        DesktopDiagnostic {
            origin: cadrumo_application::diagnostics::desktop::DiagnosticOrigin::Frontend,
            logger: None,
            event: self.event,
            level: self.level,
            command,
            code,
            dropped: self.dropped,
            line: self.line,
            column: self.column,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn diagnostic_input_cannot_turn_private_strings_into_log_fields() {
        let commands = RegisteredCommands(BTreeSet::from(["shell_window_action"]));
        let raw = serde_json::json!({
            "event": "command_rejected", "level": "ERROR",
            "command": "private-canary", "code": "private-canary", "dropped": 0,
        });
        let report: Report = serde_json::from_value(raw.clone()).unwrap();
        let encoded = serde_json::to_string(&report.admit(&commands)).unwrap();
        assert!(!encoded.contains("private-canary"));
        let mut extra = raw;
        extra["message"] = serde_json::json!("private-canary");
        assert!(serde_json::from_value::<Report>(extra).is_err());
    }

    #[test]
    fn agent_refusal_codes_survive_as_tokens_and_free_text_does_not() {
        let commands = RegisteredCommands(BTreeSet::from(["agent_provider_catalog"]));
        let admit = |code: &str| {
            let raw = serde_json::json!({
                "event":"command_rejected", "level":"WARNING",
                "command":"agent_provider_catalog", "code":code, "dropped":0,
            });
            let report: Report = serde_json::from_value(raw).unwrap();
            serde_json::to_value(report.admit(&commands)).unwrap()
        };
        for code in [
            "agent_service_busy",
            "agent_reconnecting",
            "agent_signed_out",
            "agent_gateway_409",
            "agent_gateway_attachment_not_found",
        ] {
            let encoded = admit(code);
            assert_eq!(encoded["code"], code);
            assert_eq!(encoded["level"], "WARNING");
            let diagnostics = cadrumo_application::diagnostics::Diagnostics::default();
            diagnostics.desktop_diagnostic(
                serde_json::from_value::<Report>(serde_json::json!({
                    "event":"command_rejected", "level":"WARNING",
                    "command":"agent_provider_catalog", "code":code, "dropped":0,
                }))
                .unwrap()
                .admit(&commands),
            );
            let entries = super::super::host::HostEvents::default().poll(&diagnostics);
            assert_eq!(entries[0].context["reason_code"], code);
        }
        let long = format!("agent_{}", "a".repeat(100));
        for code in [
            "agent_",
            "agent",
            "Agent_Service_Busy",
            "agent_service busy",
            "agent_private-canary",
            "agent_pässword",
            "agent_service_busy
secret",
            long.as_str(),
        ] {
            assert!(admit(code)["code"].is_null(), "{code:?}");
        }
    }

    #[test]
    fn registered_relay_failure_codes_survive_without_private_failure_fields() {
        let commands = RegisteredCommands(BTreeSet::from(["ledger_submit"]));
        for code in [
            "unavailable",
            "unknown",
            "saved_unread",
            "refused",
            "not_admitted",
            "not_signed_in",
            "invalid",
            "too_large",
            "file_unavailable",
            "review_changed",
            "conflict",
            "session_unavailable",
            "read_failed",
        ] {
            let raw = serde_json::json!({
                "event":"command_rejected", "level":"ERROR", "command":"ledger_submit",
                "code":code, "dropped":0,
            });
            let report: Report = serde_json::from_value(raw.clone()).unwrap();
            let admitted = report.admit(&commands);
            let encoded = serde_json::to_value(&admitted).unwrap();
            assert_eq!(encoded["code"], code);
            assert_eq!(encoded["command"], "ledger_submit");
            let diagnostics = cadrumo_application::diagnostics::Diagnostics::default();
            diagnostics.desktop_diagnostic(admitted);
            let entries = super::super::host::HostEvents::default().poll(&diagnostics);
            assert_eq!(entries[0].context["reason_code"], code);
            for field in ["reason", "message", "operation_id", "payload", "exception"] {
                let mut extra = raw.clone();
                extra[field] = serde_json::json!("private-canary");
                assert!(serde_json::from_value::<Report>(extra).is_err());
            }
        }
    }
}
