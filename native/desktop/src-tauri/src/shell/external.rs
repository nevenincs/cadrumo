//! Links that leave the application open in the system's own handlers.
//!
//! The shell relays links from the documentation frame, so the host decides
//! again what may leave: only `https:` and `mailto:` URLs, written plainly.
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use tauri::Url;

/// Longest URL accepted. Browsers serialize longer links, but a link the
/// documentation offers stays far below this.
const LIMIT: usize = 8192;
const HTTPS: &str = "https://";
const MAILTO: &str = "mailto:";

fn refused() -> ApplicationError {
    ApplicationError::new(ErrorCode::InvalidArguments, Operation::Webview)
}

/// Admits an absolute `https:` URL with a host and no user information, or a
/// `mailto:` URL with an address part, and returns its parsed form.
///
/// The text must be printable ASCII without a backslash, as a browser
/// serializes a link: whitespace, controls and bidirectional marks that the
/// URL parser would strip, fold or display misleadingly are refused rather
/// than repaired. The scheme must be written in lowercase.
pub fn admit(raw: &str) -> Result<Url> {
    if raw.len() > LIMIT
        || !raw
            .bytes()
            .all(|byte| byte.is_ascii_graphic() && byte != b'\\')
    {
        return Err(refused());
    }
    let url = Url::parse(raw).map_err(|e| refused().caused_by(e))?;
    let admitted = match url.scheme() {
        "https" => {
            raw.strip_prefix(HTTPS).is_some_and(|rest| {
                let authority = rest.split(['/', '?', '#']).next().unwrap_or_default();
                !authority.is_empty() && !authority.contains('@')
            }) && url.host_str().is_some_and(|host| !host.is_empty())
                && url.username().is_empty()
                && url.password().is_none()
        }
        "mailto" => raw.len() > MAILTO.len() && raw.starts_with(MAILTO),
        _ => false,
    };
    if admitted { Ok(url) } else { Err(refused()) }
}

/// Hands an admitted URL to the system's registered handler. The `BROWSER`
/// variable is not consulted.
pub fn open(url: &Url) -> Result<()> {
    opener::open(url.as_str())
        .map_err(|e| ApplicationError::new(ErrorCode::SpawnFailed, Operation::Webview).caused_by(e))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn https_and_mailto_links_are_admitted_as_parsed() {
        for raw in [
            "https://example.com",
            "https://example.com/",
            "https://example.com:8443/a/b?q=1&r=%20#part",
            "https://sede.agenciatributaria.gob.es/Sede/inicio.html",
            "https://xn--bcher-kva.example/",
            "mailto:someone@example.com",
            "mailto:someone@example.com?subject=Cadrumo%20help",
        ] {
            let url = admit(raw).unwrap_or_else(|e| panic!("{raw}: {e}"));
            assert!(matches!(url.scheme(), "https" | "mailto"), "{raw}");
        }
        assert_eq!(
            admit("https://Example.COM/A").unwrap().as_str(),
            "https://example.com/A"
        );
    }

    #[test]
    fn every_other_scheme_and_relative_reference_is_refused() {
        for raw in [
            "http://example.com/",
            "file:///C:/Windows/System32/calc.exe",
            "file://server/share",
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "cadrumo-docs://localhost/index.html",
            "http://cadrumo-docs.localhost/index.html",
            "tauri://localhost/",
            "ipc://localhost/desktop_environment",
            "ms-settings:privacy",
            "ftp://example.com/",
            "vbscript:msgbox",
            "/index.html",
            "index.html",
            "//example.com/",
            "example.com",
            "",
        ] {
            assert_eq!(
                admit(raw).unwrap_err().code,
                ErrorCode::InvalidArguments,
                "{raw}"
            );
        }
    }

    #[test]
    fn user_information_and_malformed_authorities_are_refused() {
        for raw in [
            "https://user@example.com/",
            "https://user:secret@example.com/",
            "https://@example.com/",
            "https://example.com@evil.example/",
            "https:example.com",
            "https:/example.com",
            "https:///example.com",
            "https://",
            "https://?q",
            "mailto:",
            "HTTPS://example.com/",
            "Mailto:someone@example.com",
        ] {
            assert!(admit(raw).is_err(), "{raw}");
        }
    }

    #[test]
    fn whitespace_controls_and_lookalike_text_are_refused_not_repaired() {
        let long = format!("https://example.com/{}", "a".repeat(LIMIT));
        for raw in [
            " https://example.com/",
            "https://example.com/ ",
            "https://exa mple.com/",
            "https://example.com/\t",
            "https://example.com/\n",
            "https://exa\tmple.com/",
            "\u{0}https://example.com/",
            "https://example.com/\u{7f}",
            "https://example.com\\@evil.example/",
            "https:\\\\example.com\\",
            "https://ex\u{202e}ample.com/",
            "https://example.com/\u{a0}",
            "https://b\u{fc}cher.example/",
            "mailto:some one@example.com",
            long.as_str(),
        ] {
            assert_eq!(
                admit(raw).unwrap_err().code,
                ErrorCode::InvalidArguments,
                "{raw:?}"
            );
        }
    }
}
