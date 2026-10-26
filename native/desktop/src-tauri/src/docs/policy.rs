use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use std::collections::HashMap;
use tauri::utils::config::{Config, Csp, CspDirectiveSources, WindowConfig};

/// The URI scheme that serves the packaged documentation.
pub const SCHEME: &str = "cadrumo-docs";

/// The policy sent before the shell origins are known. It frames nothing and
/// runs nothing, so a premature response cannot widen what a page may do.
pub const CLOSED: &str =
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'";

/// The origin pages on the documentation scheme see, following how the
/// webview serves a custom scheme: an `http(s)://<scheme>.localhost` host on
/// Windows, chosen by the window's https setting, and `<scheme>://localhost`
/// elsewhere.
pub fn origin(window: &WindowConfig) -> String {
    origin_for(cfg!(windows), window.use_https_scheme)
}

pub fn origin_for(windows: bool, https: bool) -> String {
    if windows {
        let transport = if https { "https" } else { "http" };
        format!("{transport}://{SCHEME}.localhost")
    } else {
        format!("{SCHEME}://localhost")
    }
}

/// The content security policy for every documentation response.
///
/// Pagefind instantiates WebAssembly from bytes and runs a same-origin
/// classic worker, so `'wasm-unsafe-eval'` and `worker-src 'self'` are the
/// only widening. `connect-src 'self'` keeps documentation scripts away from
/// the IPC transport, and only the shell may frame the documentation.
pub fn content_security_policy(
    script_hashes: &[String],
    shell_origins: &[String],
) -> Result<String> {
    if shell_origins.is_empty() || !shell_origins.iter().all(|origin| serialized_origin(origin)) {
        return Err(ApplicationError::new(
            ErrorCode::WebviewFailed,
            Operation::Webview,
        ));
    }
    let hashes: String = script_hashes
        .iter()
        .map(|hash| format!(" '{hash}'"))
        .collect();
    Ok(format!(
        "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'{hashes}; worker-src 'self'; \
         style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; \
         connect-src 'self'; object-src 'none'; frame-src 'none'; base-uri 'self'; \
         form-action 'self'; frame-ancestors {}",
        shell_origins.join(" ")
    ))
}

/// An origin as `Url::origin().ascii_serialization()` writes it. The value
/// enters a header and a CSP source list, so separators are refused.
fn serialized_origin(value: &str) -> bool {
    let Some((scheme, host)) = value.split_once("://") else {
        return false;
    };
    !scheme.is_empty()
        && !host.is_empty()
        && scheme.bytes().all(|byte| {
            byte.is_ascii_lowercase() || byte.is_ascii_digit() || b"+-.".contains(&byte)
        })
        && host.bytes().all(|byte| {
            byte.is_ascii_lowercase() || byte.is_ascii_digit() || b".-:[]".contains(&byte)
        })
}

/// Whether the shell document's policy frames exactly the documentation
/// origin. The build writes that directive; this rechecks it against the
/// origin computed for the running platform.
pub fn shell_frames(config: &Config, docs_origin: &str) -> bool {
    let security = &config.app.security;
    let policy = if tauri::is_dev() {
        security.dev_csp.as_ref().or(security.csp.as_ref())
    } else {
        security.csp.as_ref()
    };
    let Some(policy) = policy else {
        return false;
    };
    let directives: HashMap<String, CspDirectiveSources> = Csp::clone(policy).into();
    directives.get("frame-src").is_some_and(|sources| {
        Vec::<String>::from(sources.clone())
            .iter()
            .filter(|source| !source.is_empty())
            .eq([docs_origin].iter())
    })
}
