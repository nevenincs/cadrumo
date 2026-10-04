//! Plain-text clipboard access for the shell, over the clipboard-manager
//! plugin's Rust API. The plugin's own webview commands stay ungranted.
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use tauri::{Manager, Runtime};
use tauri_plugin_clipboard_manager::Clipboard;

/// Largest text the shell may place on the clipboard, in UTF-8 bytes.
pub const TEXT_LIMIT: usize = 1024 * 1024;

fn unavailable() -> ApplicationError {
    ApplicationError::new(ErrorCode::DesktopUnavailable, Operation::Webview)
}

pub fn admit(text: &str) -> Result<()> {
    if text.len() > TEXT_LIMIT {
        return Err(ApplicationError::new(
            ErrorCode::InvalidArguments,
            Operation::Webview,
        ));
    }
    Ok(())
}

pub fn read<R: Runtime>(app: &impl Manager<R>) -> Result<String> {
    app.try_state::<Clipboard<R>>()
        .ok_or_else(unavailable)?
        .read_text()
        .map_err(|e| ApplicationError::new(ErrorCode::ReadFailed, Operation::Webview).caused_by(e))
}

pub fn write<R: Runtime>(app: &impl Manager<R>, text: String) -> Result<()> {
    admit(&text)?;
    app.try_state::<Clipboard<R>>()
        .ok_or_else(unavailable)?
        .write_text(text)
        .map_err(|e| ApplicationError::new(ErrorCode::WriteFailed, Operation::Webview).caused_by(e))
}

#[cfg(test)]
mod tests {
    use super::*;
    use tauri::test::{mock_builder, mock_context, noop_assets};

    #[test]
    fn text_up_to_one_mebibyte_is_admitted() {
        admit("").unwrap();
        admit(&"a".repeat(TEXT_LIMIT)).unwrap();
        // A multi-byte character that crosses the limit counts in bytes.
        let crossing = format!("{}\u{e1}", "a".repeat(TEXT_LIMIT - 1));
        assert_eq!(
            admit(&crossing).unwrap_err().code,
            ErrorCode::InvalidArguments
        );
        assert_eq!(
            admit(&"a".repeat(TEXT_LIMIT + 1)).unwrap_err().code,
            ErrorCode::InvalidArguments
        );
    }

    #[test]
    fn oversized_text_is_refused_before_the_clipboard_is_reached() {
        let app = mock_builder().build(mock_context(noop_assets())).unwrap();
        let error = write(&app, "a".repeat(TEXT_LIMIT + 1)).unwrap_err();
        assert_eq!(error.code, ErrorCode::InvalidArguments);
        // Without the plugin there is no clipboard to reach.
        assert_eq!(
            write(&app, "a".into()).unwrap_err().code,
            ErrorCode::DesktopUnavailable
        );
        assert_eq!(read(&app).unwrap_err().code, ErrorCode::DesktopUnavailable);
    }
}
