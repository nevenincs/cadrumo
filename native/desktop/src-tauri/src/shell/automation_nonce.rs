//! The isolated WebDriver host's answer to "are you the process I launched?".
//!
//! The automation launcher cannot always read the socket table, so it proves
//! ownership over the WebDriver connection instead: it hands the host a fresh
//! nonce in its environment and reads it back from the page it drives. Only a
//! host compiled with `native-automation` and given a WebDriver port exposes
//! it; a malformed nonce refuses the launch.
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};

#[cfg(feature = "native-automation")]
const VARIABLE: &str = "CADRUMO_AUTOMATION_NONCE";
const PROPERTY: &str = "__cadrumoAutomationNonce";
const LENGTH: usize = 64;

/// The page script that defines the nonce once, read-only, or `None` when the
/// launcher supplied no nonce or no WebDriver port.
pub fn script(
    nonce: Option<&std::ffi::OsStr>,
    webdriver_port: Option<&std::ffi::OsStr>,
) -> Result<Option<String>> {
    let (Some(nonce), Some(_)) = (nonce, webdriver_port) else {
        return Ok(None);
    };
    let nonce = nonce
        .to_str()
        .filter(|value| value.len() == LENGTH && value.bytes().all(|b| b.is_ascii_hexdigit()))
        .ok_or_else(|| ApplicationError::new(ErrorCode::InvalidArguments, Operation::Webview))?;
    Ok(Some(format!(
        "Object.defineProperty(window, \"{PROPERTY}\", {{ value: \"{nonce}\", writable: false, configurable: false }});\n"
    )))
}

#[cfg(feature = "native-automation")]
pub fn current() -> Result<Option<String>> {
    script(
        std::env::var_os(VARIABLE).as_deref(),
        std::env::var_os("TAURI_WEBDRIVER_PORT").as_deref(),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ffi::OsStr;

    const NONCE: &str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

    #[test]
    fn a_launch_with_a_port_and_a_well_formed_nonce_defines_it_read_only() {
        let script = script(Some(OsStr::new(NONCE)), Some(OsStr::new("4444")))
            .unwrap()
            .unwrap();
        assert_eq!(script.matches(NONCE).count(), 1);
        assert!(script.contains(PROPERTY) && script.contains("writable: false"));
    }

    #[test]
    fn no_nonce_or_no_port_exposes_nothing() {
        assert!(script(None, Some(OsStr::new("4444"))).unwrap().is_none());
        assert!(script(Some(OsStr::new(NONCE)), None).unwrap().is_none());
    }

    #[test]
    fn a_malformed_nonce_refuses_the_launch() {
        let port = Some(OsStr::new("4444"));
        for bad in [
            "",
            &NONCE[1..],
            &format!("{NONCE}0"),
            &NONCE.replace('a', "g"),
            &format!("{}\"", &NONCE[1..]),
        ] {
            let error = script(Some(OsStr::new(bad)), port).unwrap_err();
            assert_eq!(error.code, ErrorCode::InvalidArguments);
        }
    }
}
