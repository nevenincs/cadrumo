pub mod channel;
pub mod token;

use crate::{app::Commands, environment::Launch};
use tauri::{
    Config, Runtime,
    plugin::TauriPlugin,
    utils::config::{FrontendDist, WindowConfig},
};

pub fn plugin<R: Runtime>(_launch: &Launch) -> TauriPlugin<R> {
    tauri::plugin::Builder::new("cadrumo-shell").build()
}

pub fn commands<R: Runtime>() -> Commands<R> {
    crate::app::commands![]
}

/// The origins that may serve the shell document in `window`, following how
/// tauri resolves an app URL: the custom protocol origin, plus a development
/// server or a remote frontend when the configuration selects one.
pub fn origins(config: &Config, window: &WindowConfig) -> Vec<String> {
    let protocol = if cfg!(any(windows, target_os = "android")) {
        let scheme = if window.use_https_scheme {
            "https"
        } else {
            "http"
        };
        format!("{scheme}://tauri.localhost")
    } else {
        "tauri://localhost".to_owned()
    };
    let served = if tauri::is_dev() {
        config.build.dev_url.as_ref()
    } else {
        match &config.build.frontend_dist {
            Some(FrontendDist::Url(url)) => Some(url),
            _ => None,
        }
    };
    let mut origins = vec![protocol];
    if let Some(url) = served {
        origins.push(url.origin().ascii_serialization());
    }
    origins
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shell_origin_follows_the_https_scheme_choice() {
        let config = Config::default();
        let mut window = WindowConfig::default();
        let insecure = origins(&config, &window);
        window.use_https_scheme = true;
        let secure = origins(&config, &window);
        if cfg!(windows) {
            assert_eq!(insecure[0], "http://tauri.localhost");
            assert_eq!(secure[0], "https://tauri.localhost");
        } else {
            assert_eq!(insecure[0], "tauri://localhost");
            assert_eq!(secure[0], "tauri://localhost");
        }
    }

    #[test]
    fn served_frontend_adds_its_origin() {
        let mut config = Config::default();
        let url: tauri::Url = "http://127.0.0.1:1420/index.html".parse().unwrap();
        config.build.dev_url = Some(url.clone());
        config.build.frontend_dist = Some(FrontendDist::Url(url));
        let resolved = origins(&config, &WindowConfig::default());
        assert_eq!(resolved.len(), 2);
        assert_eq!(resolved[1], "http://127.0.0.1:1420");
    }
}
