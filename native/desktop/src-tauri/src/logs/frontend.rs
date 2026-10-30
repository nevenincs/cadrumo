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
}
