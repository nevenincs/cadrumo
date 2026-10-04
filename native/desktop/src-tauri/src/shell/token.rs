use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use std::fmt::Write;

const SCRIPT: &str = include_str!("token.js");
const ORIGINS: &str = "__CADRUMO_SHELL_ORIGINS__";
const TOKEN: &str = "__CADRUMO_SHELL_TOKEN__";
const BYTES: usize = 32;

/// The per-launch secret that app commands require from the shell document.
///
/// It is held only in memory and handed to the webview through the shell's
/// initialization script. It has no Debug, Display or Serialize so it cannot
/// reach logs, diagnostics or IPC responses by accident.
pub struct ShellToken(String);

impl ShellToken {
    pub fn mint() -> Result<Self> {
        let mut bytes = [0; BYTES];
        getrandom::fill(&mut bytes).map_err(|e| {
            ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview)
                .caused_by(std::io::Error::other(e.to_string()))
        })?;
        let mut encoded = String::with_capacity(BYTES * 2);
        for byte in bytes {
            write!(encoded, "{byte:02x}").map_err(|e| {
                ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview)
                    .caused_by(std::io::Error::other(e))
            })?;
        }
        Ok(Self(encoded))
    }

    #[cfg(test)]
    pub fn value(&self) -> &str {
        &self.0
    }

    /// Refuses any presented value other than this launch's token.
    pub fn verify(&self, presented: &str, operation: Operation) -> Result<()> {
        if constant_time_equal(self.0.as_bytes(), presented.as_bytes()) {
            Ok(())
        } else {
            Err(ApplicationError::new(
                ErrorCode::InvalidArguments,
                operation,
            ))
        }
    }

    /// Renders the initialization script that exposes the token once to a top
    /// frame on one of `origins`.
    pub fn script(&self, origins: &[String]) -> Result<String> {
        let refused = |e: serde_json::Error| {
            ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview).caused_by(e)
        };
        let token = serde_json::to_string(&self.0).map_err(refused)?;
        let origins = serde_json::to_string(origins).map_err(refused)?;
        Ok(SCRIPT.replace(TOKEN, &token).replace(ORIGINS, &origins))
    }
}

/// Compares every byte regardless of where the first difference occurs. The
/// token length is public, so a length mismatch may return early.
fn constant_time_equal(expected: &[u8], presented: &[u8]) -> bool {
    if expected.len() != presented.len() {
        return false;
    }
    let difference = expected
        .iter()
        .zip(presented)
        .fold(0u8, |difference, (left, right)| difference | (left ^ right));
    std::hint::black_box(difference) == 0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn minted_tokens_carry_32_random_bytes_and_differ() {
        let first = ShellToken::mint().unwrap();
        let second = ShellToken::mint().unwrap();
        assert_eq!(first.0.len(), BYTES * 2);
        assert!(first.0.bytes().all(|byte| byte.is_ascii_hexdigit()));
        assert_ne!(first.0, second.0);
    }

    #[test]
    fn verification_accepts_only_the_exact_token() {
        let token = ShellToken::mint().unwrap();
        let exact = token.0.clone();
        token.verify(&exact, Operation::Terminal).unwrap();
        let mut altered = exact.clone().into_bytes();
        let last = altered.len() - 1;
        altered[last] = if altered[last] == b'0' { b'1' } else { b'0' };
        let altered = String::from_utf8(altered).unwrap();
        for presented in [
            "",
            &exact[1..],
            &altered,
            &format!("{exact}0"),
            &exact.to_uppercase(),
        ] {
            if presented == exact {
                continue;
            }
            let error = token.verify(presented, Operation::Terminal).unwrap_err();
            assert_eq!(error.code, ErrorCode::InvalidArguments);
            assert_eq!(error.operation, Operation::Terminal);
        }
    }

    #[test]
    fn comparison_examines_every_byte() {
        assert!(constant_time_equal(b"abcd", b"abcd"));
        assert!(!constant_time_equal(b"abcd", b"abce"));
        assert!(!constant_time_equal(b"abcd", b"xbcd"));
        assert!(!constant_time_equal(b"abcd", b"abc"));
    }

    #[test]
    fn script_embeds_origins_and_token_as_json_literals() {
        let token = ShellToken::mint().unwrap();
        let origins = vec!["http://tauri.localhost".to_owned()];
        let script = token.script(&origins).unwrap();
        assert!(!script.contains(ORIGINS) && !script.contains(TOKEN));
        assert_eq!(script.matches(&token.0).count(), 1);
        assert!(script.ends_with(&format!(
            "}})([\"http://tauri.localhost\"], \"{}\");\n",
            token.0
        )));
    }
}
