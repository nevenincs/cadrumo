//! WebView2 runtime requirements of the documentation scheme.
//!
//! The scheme needs `ICoreWebView2_22`, whose source-kind filter lets the
//! webview hand iframe and worker requests to a custom scheme, and
//! `ICoreWebView2Settings3`, which turns off browser accelerator keys. The
//! interface casts need `unsafe` COM calls, which this crate forbids, so the
//! probe lives in the platform crate. Each webview is probed once it is
//! ready; a missing interface ends the application with the typed
//! `unsupported_platform` error for the `webview` operation.
#![cfg(windows)]

use crate::shell::webview::require;
use cadrumo_application::{
    diagnostics::Diagnostics,
    error::application::{ApplicationError, ErrorCode, Operation, Result},
};
use cadrumo_platform::desktop::{WebviewInterface, missing_webview_interface};
use std::{io, sync::Arc};
use tauri::{Runtime, Webview};

/// Maps the platform probe to the host's typed outcome.
fn verdict(probe: io::Result<Option<WebviewInterface>>) -> Result<()> {
    match probe {
        Ok(None) => Ok(()),
        Ok(Some(interface)) => Err(ApplicationError::new(
            ErrorCode::UnsupportedPlatform,
            Operation::Webview,
        )
        .caused_by(io::Error::new(
            io::ErrorKind::Unsupported,
            format!("the WebView2 runtime lacks {interface:?}"),
        ))),
        Err(error) => Err(
            ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview).caused_by(error),
        ),
    }
}

/// Refuses to run on a WebView2 runtime without the required interfaces.
pub fn require_interfaces<R: Runtime>(webview: &Webview<R>, diagnostics: Arc<Diagnostics>) {
    require(webview, diagnostics, |platform| {
        verdict(missing_webview_interface(&platform.controller()))
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_missing_interface_is_an_unsupported_platform() {
        verdict(Ok(None)).unwrap();
        for interface in [WebviewInterface::Webview22, WebviewInterface::Settings3] {
            let error = verdict(Ok(Some(interface))).unwrap_err();
            assert_eq!(error.code, ErrorCode::UnsupportedPlatform);
            assert_eq!(error.operation, Operation::Webview);
        }
        let failed = verdict(Err(io::Error::other("E_FAIL"))).unwrap_err();
        assert_eq!(failed.code, ErrorCode::WebviewFailed);
        assert_eq!(failed.operation, Operation::Webview);
    }
}
