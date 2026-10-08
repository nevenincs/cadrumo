//! Restrict browser features and observe failures of each shell WebView.
//! The shell's keymap and native menus own browser accelerator keys and
//! context menus; process-failure callbacks carry only numeric telemetry.
//!
//! The COM calls live in the platform crate; this module reports their
//! outcome and refuses a webview it could not restrict. Missing failure
//! telemetry is reported without terminating or reloading the shell.
use cadrumo_application::{
    diagnostics::{
        Diagnostics,
        webview::{MonitorOperation, ReadFailures, WebviewFailure},
    },
    error::application::{ApplicationError, ErrorCode, Operation, Result},
};
use std::{io, sync::Arc};
use tauri::{AppHandle, Manager, Runtime, Webview};

/// Maps a platform outcome to the host's typed failure: a runtime without
/// the needed settings interface is an unsupported platform, anything else a
/// webview failure.
pub fn verdict(outcome: io::Result<()>) -> Result<()> {
    outcome.map_err(|error| {
        let code = if error.kind() == io::ErrorKind::Unsupported {
            ErrorCode::UnsupportedPlatform
        } else {
            ErrorCode::WebviewFailed
        };
        ApplicationError::new(code, Operation::Webview).caused_by(error)
    })
}

/// Records the failure and ends the application: a webview that could not be
/// configured as required is not shown to the user.
pub fn refuse<R: Runtime>(app: &AppHandle<R>, diagnostics: &Diagnostics, error: ApplicationError) {
    diagnostics.failure(error);
    app.exit(1);
}

/// Runs `check` against the webview's controller on the main thread,
/// refusing on any failure, including a failure to reach the webview.
pub fn require<R: Runtime>(
    webview: &Webview<R>,
    diagnostics: Arc<Diagnostics>,
    check: impl FnOnce(&tauri::webview::PlatformWebview) -> Result<()> + Send + 'static,
) {
    let app = webview.app_handle().clone();
    let reporter = diagnostics.clone();
    let dispatched = webview.with_webview(move |platform| {
        if let Err(error) = check(&platform) {
            refuse(&app, &reporter, error);
        }
    });
    if let Err(error) = dispatched {
        refuse(
            webview.app_handle(),
            &diagnostics,
            ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview).caused_by(error),
        );
    }
}

/// Turns off browser accelerator keys and default context menus.
pub fn restrict<R: Runtime>(webview: &Webview<R>, diagnostics: Arc<Diagnostics>) {
    require(webview, diagnostics, |platform| {
        verdict(cadrumo_platform::desktop::disable_browser_features(
            &platform.controller(),
        ))
    });
}

/// Observe process failures independently of browser-feature admission. Missing
/// telemetry is recorded but does not end or reload an otherwise usable shell.
pub fn observe<R: Runtime>(webview: &Webview<R>, diagnostics: Arc<Diagnostics>) {
    use cadrumo_platform::desktop::webview_process::{self, MonitorOperation as PlatformOperation};
    let reporter = diagnostics.clone();
    let dispatched = webview.with_webview(move |platform| {
        let sink = reporter.clone();
        let result = webview_process::monitor(&platform.controller(), move |failure| {
            sink.webview_failure(process_fact(failure));
        });
        if let Err(failure) = result {
            let operation = match failure.operation {
                PlatformOperation::CoreWebview => MonitorOperation::CoreWebview,
                PlatformOperation::Register => MonitorOperation::Register,
            };
            reporter.webview_failure(WebviewFailure::MonitorUnavailable {
                operation,
                hresult: Some(failure.hresult),
            });
        }
    });
    if dispatched.is_err() {
        diagnostics.webview_failure(WebviewFailure::MonitorUnavailable {
            operation: MonitorOperation::Dispatch,
            hresult: None,
        });
    }
}

fn process_fact(
    failure: cadrumo_platform::desktop::webview_process::ProcessFailure,
) -> WebviewFailure {
    let reads = failure.read_failures;
    WebviewFailure::process(
        failure.kind,
        failure.reason,
        failure.exit_code,
        ReadFailures {
            arguments_hresult: reads.arguments_hresult,
            kind_hresult: reads.kind_hresult,
            details_hresult: reads.details_hresult,
            reason_hresult: reads.reason_hresult,
            exit_code_hresult: reads.exit_code_hresult,
        },
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_missing_settings_interface_is_an_unsupported_platform() {
        verdict(Ok(())).unwrap();
        let missing =
            verdict(Err(io::Error::new(io::ErrorKind::Unsupported, "no cast"))).unwrap_err();
        assert_eq!(missing.code, ErrorCode::UnsupportedPlatform);
        assert_eq!(missing.operation, Operation::Webview);
        let failed = verdict(Err(io::Error::other("E_FAIL"))).unwrap_err();
        assert_eq!(failed.code, ErrorCode::WebviewFailed);
        assert_eq!(failed.operation, Operation::Webview);
        assert!(std::error::Error::source(&failed).is_some());
    }

    #[test]
    fn process_observations_preserve_partial_metadata_without_claiming_a_child_exit() {
        use cadrumo_platform::desktop::webview_process::{ProcessFailure, ReadFailures as Reads};
        let fact = process_fact(ProcessFailure {
            kind: Some(2),
            reason: None,
            exit_code: Some(259),
            read_failures: Reads {
                reason_hresult: Some(-2_147_467_259),
                ..Reads::default()
            },
        });
        let diagnostics = Diagnostics::default();
        diagnostics.webview_failure(fact);
        let snapshot = diagnostics.snapshot(u64::MAX);
        assert!(snapshot.processes.is_empty() && snapshot.output.is_empty());
        let event = &snapshot.events[0];
        assert!(event.process.is_none() && event.status.is_none());
        assert_eq!(event.webview_failure, Some(fact));
        let serialized = serde_json::to_value(event).unwrap();
        assert_eq!(
            serialized["webviewFailure"]["kind"],
            "render_process_unresponsive"
        );
        assert_eq!(serialized["webviewFailure"]["exitCode"], 259);
        assert_eq!(
            serialized["webviewFailure"]["readFailures"]["reasonHresult"],
            -2_147_467_259_i32
        );
    }
}
