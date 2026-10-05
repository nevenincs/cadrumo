//! WebView2 settings the shell needs from every webview: no browser
//! accelerator keys (reload, print, find, zoom, developer tools) and no
//! default context menus, so the shell's keymap and native menus own both.
//!
//! The COM calls live in the platform crate; this module reports their
//! outcome and refuses to keep running a webview it could not restrict.
use cadrumo_application::{
    diagnostics::Diagnostics,
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
}
