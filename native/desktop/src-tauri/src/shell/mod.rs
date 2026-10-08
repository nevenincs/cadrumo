pub mod channel;
mod clipboard;
mod external;
mod interrupts;
mod menu;
pub mod navigation;
pub mod sign_in;
pub mod single_instance;
pub mod token;
#[cfg(windows)]
pub mod webview;
#[cfg(windows)]
pub mod webview_environment;
pub mod window_state;

use crate::{app::Commands, docs, environment::Launch};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use serde::Serialize;
use std::sync::Arc;
use tauri::{
    AppHandle, Config, Manager, RunEvent, Runtime, State, Webview, WindowEvent,
    plugin::TauriPlugin,
    utils::config::{FrontendDist, WindowConfig},
};

/// What the shell needs from the launch to describe its environment.
struct Shell {
    output_language: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct DesktopEnvironment {
    output_language: String,
    docs: docs::Published,
}

#[derive(Serialize)]
struct ClipboardText {
    text: String,
}

#[derive(Serialize)]
struct ContextMenuResult {
    chosen: Option<String>,
}

fn unavailable() -> ApplicationError {
    ApplicationError::new(ErrorCode::DesktopUnavailable, Operation::Webview)
}

/// Runs blocking host work off the async runtime's workers.
async fn blocking<T: Send + 'static>(
    work: impl FnOnce() -> Result<T> + Send + 'static,
) -> Result<T> {
    tauri::async_runtime::spawn_blocking(work)
        .await
        .map_err(|e| ApplicationError::new(ErrorCode::Panic, Operation::Webview).caused_by(e))?
}

#[tauri::command]
fn desktop_environment(
    shell: State<'_, Shell>,
    docs: State<'_, docs::Published>,
) -> DesktopEnvironment {
    DesktopEnvironment {
        output_language: shell.output_language.clone(),
        docs: docs.inner().clone(),
    }
}

/// Resolving and starting the system handler can block, so the launch runs
/// off the main thread, as Tauri's own opener plugin launches URLs from its
/// asynchronous commands.
#[tauri::command]
async fn open_external(url: String) -> Result<()> {
    let url = external::admit(&url)?;
    blocking(move || external::open(&url)).await
}

#[tauri::command]
async fn shell_clipboard_read<R: Runtime>(app: AppHandle<R>) -> Result<ClipboardText> {
    let text = blocking(move || clipboard::read(&app)).await?;
    Ok(ClipboardText { text })
}

#[tauri::command]
async fn shell_clipboard_write<R: Runtime>(app: AppHandle<R>, text: String) -> Result<()> {
    clipboard::admit(&text)?;
    blocking(move || clipboard::write(&app, text)).await
}

/// Resolves when the popup has closed. The popup blocks its thread until
/// then, so the command is asynchronous and the wait runs off the workers.
#[tauri::command]
async fn shell_context_menu<R: Runtime>(
    webview: Webview<R>,
    items: Vec<serde_json::Value>,
    x: Option<f64>,
    y: Option<f64>,
) -> Result<ContextMenuResult> {
    let popups = webview
        .try_state::<Arc<menu::Popups>>()
        .ok_or_else(unavailable)?
        .inner()
        .clone();
    let position = menu::position(x, y)?;
    let claim = popups.claim()?;
    let menu = menu::Menu::new(popups.next_sequence(), items)?;
    let window = webview.window();
    let chosen = blocking(move || {
        let _claim = claim;
        show(&window, &popups, &menu, position)
    })
    .await?;
    Ok(ContextMenuResult { chosen })
}

#[cfg(windows)]
fn show<R: Runtime>(
    window: &tauri::Window<R>,
    popups: &menu::Popups,
    menu: &menu::Menu,
    position: Option<tauri::LogicalPosition<f64>>,
) -> Result<Option<String>> {
    menu::show(window, popups, menu, position)
}

/// Elsewhere a native popup returns before the menu closes, so the choice
/// cannot be awaited the same way.
#[cfg(not(windows))]
fn show<R: Runtime>(
    _window: &tauri::Window<R>,
    _popups: &menu::Popups,
    _menu: &menu::Menu,
    _position: Option<tauri::LogicalPosition<f64>>,
) -> Result<Option<String>> {
    Err(ApplicationError::new(
        ErrorCode::UnsupportedPlatform,
        Operation::Webview,
    ))
}

pub fn plugin<R: Runtime>(launch: &Launch) -> TauriPlugin<R> {
    let sign_in = Arc::new(sign_in::SignIn::new(launch));
    let output_language = launch.output_language.clone();
    #[cfg(windows)]
    let diagnostics = launch.diagnostics.clone();
    let popups = Arc::new(menu::Popups::default());
    let recorder = popups.clone();
    let activation = launch.diagnostics.clone();
    let window_states = Arc::new(window_state::WindowStates::open(
        &launch.webview,
        launch.diagnostics.clone(),
    ));
    let builder = tauri::plugin::Builder::new("cadrumo-shell")
        .setup(move |app, _| {
            #[cfg(windows)]
            interrupts::restore(&diagnostics);
            single_instance::verify(app.config())?;
            app.manage(Shell { output_language });
            app.manage(sign_in);
            app.manage(popups);
            app.manage(channel::Deliveries::default());
            Ok(())
        })
        .on_window_ready(move |window| {
            window_states.attach(&window);
            single_instance::attach(&window, activation.clone());
        })
        .on_event(move |_, event| match event {
            RunEvent::MenuEvent(event) => recorder.record(&event.id().0),
            RunEvent::WindowEvent {
                event: WindowEvent::Destroyed,
                ..
            }
            | RunEvent::Exit => single_instance::close(),
            _ => {}
        });
    #[cfg(windows)]
    let builder = {
        let ready = launch.diagnostics.clone();
        builder.on_webview_ready(move |webview| {
            webview::restrict(&webview, ready.clone());
            webview::observe(&webview, ready.clone());
        })
    };
    builder.build()
}

/// The clipboard plugin, registered for its Rust API only: no capability
/// grants its commands to a webview.
pub fn clipboard_plugin<R: Runtime>() -> TauriPlugin<R> {
    tauri_plugin_clipboard_manager::init()
}

pub fn commands<R: Runtime>() -> Commands<R> {
    crate::app::commands![
        desktop_environment,
        open_external,
        shell_clipboard_read,
        shell_clipboard_write,
        shell_context_menu
    ]
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

    fn invoke(
        window: &tauri::WebviewWindow<tauri::test::MockRuntime>,
        cmd: &str,
    ) -> std::result::Result<(), serde_json::Value> {
        tauri::test::get_ipc_response(
            window,
            tauri::webview::InvokeRequest {
                cmd: cmd.into(),
                callback: tauri::ipc::CallbackFn(0),
                error: tauri::ipc::CallbackFn(1),
                url: if cfg!(windows) {
                    "http://tauri.localhost"
                } else {
                    "tauri://localhost"
                }
                .parse()
                .unwrap(),
                body: tauri::ipc::InvokeBody::Json(serde_json::json!({"text": "probe"})),
                headers: Default::default(),
                invoke_key: tauri::test::INVOKE_KEY.to_owned(),
            },
        )
        .map(|_| ())
    }

    /// The application's real access control, as built from its configuration
    /// and the plugins' permission manifests, grants the webview no plugin
    /// command, so the shell origin and the documentation frame alike reach
    /// the clipboard only through the token-checked app commands.
    #[test]
    fn the_configuration_grants_no_plugin_command() {
        let app = tauri::test::mock_builder()
            .plugin(clipboard_plugin())
            .build(tauri::generate_context!(test = true))
            .unwrap();
        let window = tauri::WebviewWindowBuilder::new(&app, "main", Default::default())
            .build()
            .unwrap();
        let plugin_commands = [
            "plugin:clipboard-manager|read_text",
            "plugin:clipboard-manager|write_text",
            "plugin:clipboard-manager|clear",
            "plugin:menu|popup",
            "plugin:menu|new",
            "plugin:window|close",
            "plugin:webview|print",
            "plugin:opener|open_url",
            "plugin:window-state|save_window_state",
        ];
        for cmd in plugin_commands {
            let refused = invoke(&window, cmd).unwrap_err();
            assert!(
                refused.as_str().is_some_and(|m| m.contains("not allowed")),
                "{cmd}: {refused}"
            );
        }
        // Control: a granted permission is admitted, so the refusals above are
        // the access control's and not an unknown command's. Reading leaves
        // the clipboard as it was.
        app.add_capability(
            tauri::ipc::CapabilityBuilder::new("control")
                .window("main")
                .permission("clipboard-manager:allow-read-text"),
        )
        .unwrap();
        let admitted = invoke(&window, "plugin:clipboard-manager|read_text");
        assert!(
            admitted
                .as_ref()
                .err()
                .and_then(|m| m.as_str())
                .is_none_or(|m| !m.contains("not allowed")),
            "{admitted:?}"
        );
    }
}
