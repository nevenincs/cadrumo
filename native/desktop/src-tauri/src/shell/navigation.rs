//! The top frame stays on the shell document.
//!
//! A top-level navigation would replace the shell, settling every terminal
//! session and handing the main webview, its initialization script and its
//! IPC to whatever page loaded. Only the shell's own origins may load there.
//! Navigation inside the documentation frame does not reach this policy.
use tauri::Url;

/// The origin of `url` in the form [`super::origins`] lists, or `None` for a
/// URL without a host. A custom scheme such as `tauri:` has an opaque URL
/// origin, so the origin is spelled from its parts.
fn origin(url: &Url) -> Option<String> {
    let host = url.host_str().filter(|host| !host.is_empty())?;
    Some(match url.port() {
        Some(port) => format!("{}://{host}:{port}", url.scheme()),
        None => format!("{}://{host}", url.scheme()),
    })
}

/// Whether the top frame may navigate to `url`: one of the shell `origins`,
/// without user information.
pub fn allowed(origins: &[String], url: &Url) -> bool {
    url.username().is_empty()
        && url.password().is_none()
        && origin(url).is_some_and(|origin| origins.contains(&origin))
}

#[cfg(test)]
mod tests {
    use super::*;
    use tauri::{
        Config,
        utils::config::{FrontendDist, WindowConfig},
    };

    fn parsed(raw: &str) -> Url {
        raw.parse().unwrap()
    }

    #[test]
    fn the_packaged_shell_origin_is_the_only_destination() {
        let origins = super::super::origins(&Config::default(), &WindowConfig::default());
        let shell = if cfg!(windows) {
            "http://tauri.localhost"
        } else {
            "tauri://localhost"
        };
        assert_eq!(origins, [shell]);
        for raw in [
            format!("{shell}/"),
            format!("{shell}/index.html"),
            format!("{shell}/index.html?view=logs#top"),
        ] {
            assert!(allowed(&origins, &parsed(&raw)), "{raw}");
        }
        for raw in [
            "https://tauri.localhost/index.html",
            "http://tauri.localhost:8080/index.html",
            "http://user@tauri.localhost/index.html",
            "http://tauri.localhost.example.com/",
            "http://localhost/",
            "tauri://localhost.example/",
            "http://cadrumo-docs.localhost/index.html",
            "cadrumo-docs://localhost/index.html",
            "https://sede.agenciatributaria.gob.es/",
            "https://example.com/",
            "file:///C:/Windows/System32/calc.exe",
            "about:blank",
            "data:text/html,<p>replaced</p>",
            "javascript:alert(1)",
            "http://127.0.0.1:1420/",
        ] {
            if cfg!(windows) || !raw.starts_with("tauri://localhost/") {
                assert!(!allowed(&origins, &parsed(raw)), "{raw}");
            }
        }
        if !cfg!(windows) {
            assert!(!allowed(&origins, &parsed("http://tauri.localhost/")));
        }
    }

    #[test]
    fn a_served_frontend_adds_exactly_its_origin() {
        let mut config = Config::default();
        let url = parsed("http://127.0.0.1:1420/index.html");
        config.build.dev_url = Some(url.clone());
        config.build.frontend_dist = Some(FrontendDist::Url(url));
        let origins = super::super::origins(&config, &WindowConfig::default());
        assert!(allowed(&origins, &parsed("http://127.0.0.1:1420/")));
        assert!(allowed(&origins, &parsed("http://127.0.0.1:1420/logs?x=1")));
        assert!(!allowed(&origins, &parsed("http://127.0.0.1:1421/")));
        assert!(!allowed(&origins, &parsed("https://127.0.0.1:1420/")));
        assert!(!allowed(&origins, &parsed("http://localhost:1420/")));
    }
}
