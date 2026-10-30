//! Route Rust/Tauri metadata without rendering possibly private log arguments.
use cadrumo_application::{
    diagnostics::{
        Diagnostics,
        desktop::{DesktopDiagnostic, DesktopEvent, DiagnosticOrigin},
        service::LogLevel,
    },
    error::application::{ApplicationError, ErrorCode, Operation},
};
use std::sync::Arc;

struct NativeLogger(Arc<Diagnostics>);

impl log::Log for NativeLogger {
    fn enabled(&self, metadata: &log::Metadata<'_>) -> bool {
        metadata.level() <= log::Level::Debug
    }

    fn log(&self, record: &log::Record<'_>) {
        if !self.enabled(record.metadata()) {
            return;
        }
        // Only compiler-owned module locations, never a caller's dynamic target.
        let Some(module) = record.module_path_static() else {
            return;
        };
        let root = module.split("::").next().unwrap_or_default();
        let origin = match root {
            "tauri"
            | "tauri_runtime_wry"
            | "wry"
            | "tao"
            | "tauri_plugin_dialog"
            | "tauri_plugin_clipboard_manager" => DiagnosticOrigin::Tauri,
            "cadrumo_desktop" | "cadrumo_application" | "cadrumo_platform" => {
                DiagnosticOrigin::Rust
            }
            _ => return,
        };
        let level = match record.level() {
            log::Level::Error => LogLevel::Error,
            log::Level::Warn => LogLevel::Warning,
            log::Level::Info => LogLevel::Info,
            log::Level::Debug | log::Level::Trace => LogLevel::Debug,
        };
        self.0.desktop_diagnostic(DesktopDiagnostic {
            origin,
            logger: Some(module.to_owned()),
            event: DesktopEvent::NativeLog,
            level,
            command: None,
            code: None,
            dropped: 0,
            line: record.line(),
            column: None,
        });
    }

    fn flush(&self) {}
}

pub fn install(diagnostics: Arc<Diagnostics>) {
    if log::set_boxed_logger(Box::new(NativeLogger(diagnostics.clone()))).is_err() {
        diagnostics.failure(ApplicationError::new(
            ErrorCode::LogUnavailable,
            Operation::Logging,
        ));
        return;
    }
    log::set_max_level(log::LevelFilter::Debug);
}

#[cfg(test)]
mod tests {
    use super::*;
    use log::Log;

    #[test]
    fn tauri_records_keep_severity_and_location_without_rendering_arguments() {
        struct NeverRender;
        impl std::fmt::Display for NeverRender {
            fn fmt(&self, _: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
                panic!("diagnostic arguments must not be rendered")
            }
        }
        let diagnostics = Arc::new(Diagnostics::default());
        let logger = NativeLogger(diagnostics.clone());
        for level in [
            log::Level::Debug,
            log::Level::Info,
            log::Level::Warn,
            log::Level::Error,
        ] {
            logger.log(
                &log::Record::builder()
                    .level(level)
                    .module_path_static(Some("tauri::window"))
                    .target("private-target-canary")
                    .line(Some(42))
                    .args(format_args!("private-argument-canary {}", NeverRender))
                    .build(),
            );
        }
        let snapshot = diagnostics.snapshot(u64::MAX);
        assert_eq!(snapshot.events.len(), 4);
        assert_eq!(
            snapshot
                .events
                .iter()
                .map(|event| event.desktop_diagnostic.as_ref().unwrap().level)
                .collect::<Vec<_>>(),
            [
                LogLevel::Debug,
                LogLevel::Info,
                LogLevel::Warning,
                LogLevel::Error
            ]
        );
        let encoded = serde_json::to_string(&snapshot).unwrap();
        assert!(!encoded.contains("private-target-canary"));
        assert!(!encoded.contains("private-argument-canary"));
        assert!(encoded.contains("tauri::window"));
    }
}
