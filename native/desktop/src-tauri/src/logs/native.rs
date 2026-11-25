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

/// The WebDriver plugin logs through `tracing`, which forwards to `log` with a
/// borrowed module path. Its listener bind and failure records are the only
/// evidence of whether the automation endpoint opened, so its own modules are
/// admitted, recorded under this fixed copy of their names and never under the
/// forwarded string.
const WDIO: &str = "tauri_plugin_wdio_webdriver";
const WDIO_MODULES: [&str; 6] = [
    "tauri_plugin_wdio_webdriver",
    "tauri_plugin_wdio_webdriver::server",
    "tauri_plugin_wdio_webdriver::server::handlers::direct_eval",
    "tauri_plugin_wdio_webdriver::platform::executor",
    "tauri_plugin_wdio_webdriver::platform::windows",
    "tauri_plugin_wdio_webdriver::platform::macos",
];

fn forwarded(record: &log::Record<'_>) -> Option<&'static str> {
    let module = record.module_path()?;
    WDIO_MODULES.iter().copied().find(|known| *known == module)
}

impl log::Log for NativeLogger {
    fn enabled(&self, metadata: &log::Metadata<'_>) -> bool {
        metadata.level() <= log::Level::Debug
    }

    fn log(&self, record: &log::Record<'_>) {
        if !self.enabled(record.metadata()) {
            return;
        }
        // Only compiler-owned module locations, never a caller's dynamic target.
        let Some(module) = record.module_path_static().or_else(|| forwarded(record)) else {
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
            "cadrumo_application" | "cadrumo_platform" => DiagnosticOrigin::Rust,
            WDIO => DiagnosticOrigin::Tauri,
            own if Some(own) == module_path!().split("::").next() => DiagnosticOrigin::Rust,
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
            reason: None,
            summary: None,
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
    fn this_binarys_compiler_owned_module_is_routed_without_private_arguments() {
        struct NeverRender;
        impl std::fmt::Display for NeverRender {
            fn fmt(&self, _: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
                panic!("diagnostic arguments must not be rendered")
            }
        }
        let diagnostics = Arc::new(Diagnostics::default());
        let logger = NativeLogger(diagnostics.clone());
        logger.log(
            &log::Record::builder()
                .level(log::Level::Debug)
                .module_path_static(Some(module_path!()))
                .target("private-target-canary")
                .line(Some(42))
                .args(format_args!("private-argument-canary {}", NeverRender))
                .build(),
        );
        let dynamic = module_path!().to_owned();
        logger.log(
            &log::Record::builder()
                .level(log::Level::Debug)
                .module_path(Some(&dynamic))
                .args(format_args!("private-argument-canary {}", NeverRender))
                .build(),
        );
        logger.log(
            &log::Record::builder()
                .level(log::Level::Debug)
                .module_path_static(Some("unrelated::module"))
                .args(format_args!("private-argument-canary {}", NeverRender))
                .build(),
        );
        let snapshot = diagnostics.snapshot(u64::MAX);
        assert_eq!(snapshot.events.len(), 1);
        let fact = snapshot.events[0].desktop_diagnostic.as_ref().unwrap();
        assert_eq!(fact.logger.as_deref(), Some(module_path!()));
        assert!(matches!(fact.origin, DiagnosticOrigin::Rust));
        assert_eq!(fact.line, Some(42));
        let encoded = serde_json::to_string(&snapshot).unwrap();
        assert!(!encoded.contains("private-target-canary"));
        assert!(!encoded.contains("private-argument-canary"));
    }

    #[test]
    fn the_webdriver_plugins_forwarded_records_are_kept_under_its_fixed_module_name() {
        struct NeverRender;
        impl std::fmt::Display for NeverRender {
            fn fmt(&self, _: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
                panic!("diagnostic arguments must not be rendered")
            }
        }
        let diagnostics = Arc::new(Diagnostics::default());
        let logger = NativeLogger(diagnostics.clone());
        let forwarded = String::from("tauri_plugin_wdio_webdriver::server");
        let lookalike = String::from("tauri_plugin_wdio_webdriver::server::private-canary");
        for module in [&forwarded, &lookalike] {
            logger.log(
                &log::Record::builder()
                    .level(log::Level::Error)
                    .module_path(Some(module))
                    .target("private-target-canary")
                    .line(Some(77))
                    .args(format_args!("private-argument-canary {}", NeverRender))
                    .build(),
            );
        }
        let snapshot = diagnostics.snapshot(u64::MAX);
        assert_eq!(snapshot.events.len(), 1);
        let fact = snapshot.events[0].desktop_diagnostic.as_ref().unwrap();
        assert_eq!(
            fact.logger.as_deref(),
            Some("tauri_plugin_wdio_webdriver::server")
        );
        assert!(matches!(fact.origin, DiagnosticOrigin::Tauri));
        assert_eq!(fact.level, LogLevel::Error);
        assert_eq!(fact.line, Some(77));
        let encoded = serde_json::to_string(&snapshot).unwrap();
        assert!(!encoded.contains("canary"));
    }

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
