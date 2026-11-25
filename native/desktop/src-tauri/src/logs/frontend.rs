use cadrumo_application::diagnostics::{
    desktop::{
        BackendReason, DesktopDiagnostic, DesktopEvent, DesktopSummary, module_name,
        redact_template,
    },
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
    /// The backend's closed code beside a relay failure's `code`.
    #[serde(default)]
    reason: Option<String>,
    /// The message's authored shape with its values already taken out; the
    /// host takes them out again.
    #[serde(default)]
    template: Option<String>,
    /// The script the first stack frame names.
    #[serde(default)]
    module: Option<String>,
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
        let summary = DesktopSummary {
            template: self.template.as_deref().and_then(redact_template),
            module: self.module.as_deref().and_then(module_name),
        };
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
            reason: self.reason.as_deref().and_then(BackendReason::parse),
            summary: (summary != DesktopSummary::default()).then_some(summary),
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

    fn admitted(fields: serde_json::Value) -> serde_json::Value {
        let commands = RegisteredCommands(BTreeSet::from(["modelo_submit"]));
        let mut raw = serde_json::json!({
            "event": "console", "level": "ERROR", "command": null, "code": null, "dropped": 0,
        });
        for (key, value) in fields.as_object().unwrap() {
            raw[key] = value.clone();
        }
        let report: Report = serde_json::from_value(raw).unwrap();
        let diagnostics = cadrumo_application::diagnostics::Diagnostics::default();
        diagnostics.desktop_diagnostic(report.admit(&commands));
        let entries = super::super::host::HostEvents::default().poll(&diagnostics);
        serde_json::json!({ "message": entries[0].message, "context": entries[0].context })
    }

    #[test]
    fn a_console_record_says_what_happened_without_its_values() {
        let entry = admitted(serde_json::json!({
            "template": "Invalid prop `value` of value `2` supplied to `Progress`. Defaulting to `null`.",
            "module": "http://127.0.0.1:1430/assets/palette-Ab12_c.js?v=3#x",
            "line": 12, "column": 345,
        }));
        assert_eq!(
            entry["message"],
            "frontend_console: Invalid prop `…` of value `…` supplied to `…`. \
             Defaulting to `…`. at palette-Ab12_c.js:12:345"
        );
        assert_eq!(entry["context"]["module"], "palette-Ab12_c.js");
        assert_eq!(entry["context"]["line"], 12);
    }

    #[test]
    fn private_values_never_survive_the_template_or_the_module() {
        for (template, module) in [
            (
                "Cannot read X1234567L for Juan García 1.234,56 \"secret\"",
                r"C:\Users\Juan\a.js",
            ),
            (
                "TypeError: juan@example.com IBAN ES9121000418450200051332",
                "file:///home/private-canary/x",
            ),
            (
                "Failed `private-canary",
                "https://example.com/private-canary/",
            ),
        ] {
            let encoded =
                admitted(serde_json::json!({ "template": template, "module": module })).to_string();
            for secret in [
                "X1234567L",
                "Juan",
                "Garc",
                "1.234",
                "secret",
                "example.com",
                "ES91",
                "private-canary",
                "Users",
                "home",
            ] {
                assert!(!encoded.contains(secret), "{secret} in {encoded}");
            }
        }
        let entry =
            admitted(serde_json::json!({ "template": "12 345", "module": "/private/x.exe" }));
        assert_eq!(entry["message"], "frontend_console");
    }

    #[test]
    fn a_relay_failure_names_the_backend_code_beside_its_own() {
        let entry = admitted(serde_json::json!({
            "event": "command_rejected", "command": "modelo_submit", "code": "unknown",
            "reason": "ERROR_FINANCIAL_AGGREGATION_VALIDATION",
        }));
        assert_eq!(
            entry["message"],
            "frontend_command_rejected: modelo_submit: unknown (ERROR_FINANCIAL_AGGREGATION_VALIDATION)"
        );
        assert_eq!(
            entry["context"]["backend_code"],
            "ERROR_FINANCIAL_AGGREGATION_VALIDATION"
        );
        for reason in [
            "X1234567L",
            "a b",
            "ERROR_ X",
            "1_ERROR",
            "Juan",
            "ok_\nsecret",
            "",
        ] {
            let entry = admitted(serde_json::json!({
                "event": "command_rejected", "command": "modelo_submit", "code": "unknown",
                "reason": reason,
            }));
            assert!(entry["context"].get("backend_code").is_none(), "{reason:?}");
        }
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
            "agent_gateway_model_not_installed",
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
            for field in ["message", "operation_id", "payload", "exception", "stack"] {
                let mut extra = raw.clone();
                extra[field] = serde_json::json!("private-canary");
                assert!(serde_json::from_value::<Report>(extra).is_err());
            }
        }
    }
}
