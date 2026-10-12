use crate::{
    docs,
    environment::Launch,
    logs,
    manager::{self, ManagerStart},
    shell::{self, token::ShellToken},
    terminal::{self, TerminalState},
};
use cadrumo_application::{
    diagnostics::{Diagnostics, EventKind},
    error::application::{ApplicationError, ErrorCode, Operation, Result},
};
use std::{collections::BTreeSet, sync::Arc};
use tauri::{
    Manager, Runtime,
    http::HeaderMap,
    ipc::{Invoke, InvokeBody},
};

type Handler<R> = Box<dyn Fn(Invoke<R>) -> bool + Send + Sync>;

/// One module's app commands. Modules declare them with [`commands!`] and the
/// host composes every module behind the shell token check.
pub struct Commands<R: Runtime> {
    names: &'static [&'static str],
    handler: Handler<R>,
}

impl<R: Runtime> Commands<R> {
    pub fn new(names: &'static [&'static str], handler: Handler<R>) -> Self {
        Self { names, handler }
    }
}

macro_rules! commands {
    ($($command:ident),* $(,)?) => {
        $crate::app::Commands::new(
            &[$(stringify!($command)),*],
            Box::new(tauri::generate_handler![$($command),*]),
        )
    };
}
pub(crate) use commands;

const TOKEN_ARGUMENT: &str = "token";
const TOKEN_HEADER: &str = "x-cadrumo-token";

/// The token an invocation presents: the `token` argument of a JSON object
/// call, or the token header of any other body. A raw body becomes a JSON
/// byte array when Tauri falls back to its postMessage transport, and keeps
/// its headers.
fn presented_token<'a>(body: &'a InvokeBody, headers: &'a HeaderMap) -> &'a str {
    match body {
        InvokeBody::Json(arguments) if arguments.is_object() => {
            arguments.get(TOKEN_ARGUMENT).and_then(|v| v.as_str())
        }
        _ => headers.get(TOKEN_HEADER).and_then(|v| v.to_str().ok()),
    }
    .unwrap_or_default()
}

fn distinct(modules: &[&[&str]]) -> bool {
    let mut seen = BTreeSet::new();
    modules
        .iter()
        .flat_map(|names| names.iter())
        .all(|name| seen.insert(*name))
}

/// Routes each app command to its module after the shell token check, so no
/// command can be registered without it.
fn dispatch<R: Runtime>(
    modules: Vec<Commands<R>>,
    token: ShellToken,
    diagnostics: Arc<Diagnostics>,
) -> Result<impl Fn(Invoke<R>) -> bool + Send + Sync + 'static> {
    let names: Vec<_> = modules.iter().map(|module| module.names).collect();
    if !distinct(&names) {
        return Err(ApplicationError::new(
            ErrorCode::InvalidArguments,
            Operation::Webview,
        ));
    }
    Ok(move |invoke: Invoke<R>| {
        let command = invoke.message.command();
        let Some(module) = modules
            .iter()
            .find(|module| module.names.contains(&command))
        else {
            return false;
        };
        let presented = presented_token(invoke.message.payload(), invoke.message.headers());
        match token.verify(presented, Operation::Webview) {
            Ok(()) => (module.handler)(invoke),
            Err(error) => {
                diagnostics.failure(error.clone());
                invoke.resolver.reject(error);
                true
            }
        }
    })
}

pub fn run(launch: Launch) -> Result<i32> {
    if cfg!(target_os = "macos") {
        return Err(ApplicationError::new(
            ErrorCode::UnsupportedPlatform,
            Operation::Webview,
        ));
    }
    // Before the console detaches, so the refusal still reaches it.
    #[cfg(windows)]
    shell::webview_environment::refuse_overrides()?;
    #[cfg(windows)]
    cadrumo_platform::desktop::detach_console();
    let diagnostics = launch.diagnostics.clone();
    diagnostics.event(EventKind::GuiSelected, None, None);
    let data_directory = launch.webview.clone();
    let context = tauri::generate_context!();
    let window =
        context.config().app.windows.first().ok_or_else(|| {
            ApplicationError::new(ErrorCode::InvalidArguments, Operation::Webview)
        })?;
    let token = ShellToken::mint()?;
    let origins = shell::origins(context.config(), window);
    let script = token.script(&origins)?;
    let handler = dispatch(
        vec![
            terminal::commands(),
            docs::commands(),
            logs::commands(),
            shell::commands(),
            shell::window_controls::commands(),
            shell::sign_in::commands(),
            manager::commands(),
        ],
        token,
        diagnostics.clone(),
    )?;
    let builder = tauri::Builder::default()
        .plugin(terminal::plugin(&launch))
        .plugin(docs::plugin(&launch))
        .plugin(logs::plugin(&launch))
        .plugin(shell::plugin(&launch))
        .plugin(shell::clipboard_plugin());
    let manager_start = Arc::new(ManagerStart::new(&launch));
    let startup_manager = manager_start.clone();
    let state = Arc::new(TerminalState::new(launch));
    let setup_diagnostics = diagnostics.clone();
    let navigation_diagnostics = diagnostics.clone();
    let app = builder
        .manage(state.clone())
        .manage(manager_start)
        .invoke_handler(handler)
        .channel_interceptor(shell::channel::interceptor(diagnostics.clone()))
        .setup(move |app| {
            #[cfg(windows)]
            {
                let sign_in = app.state::<Arc<shell::sign_in::SignIn>>().inner().clone();
                if let Err(error) =
                    tauri::async_runtime::block_on(startup_manager.ensure_ready(&sign_in))
                {
                    setup_diagnostics.failure(error);
                    tauri::async_runtime::block_on(startup_manager.close());
                    let _ = tauri::async_runtime::block_on(sign_in.stop());
                    app.handle().exit(1);
                    return Ok(());
                }
            }
            #[cfg(not(windows))]
            {
                let manager = startup_manager.clone();
                let diagnostics = setup_diagnostics.clone();
                tauri::async_runtime::spawn(async move {
                    if let Err(error) = manager.start(false).await {
                        diagnostics.failure(error);
                    }
                });
            }
            let outcome = (|| {
                let config = app.config().app.windows.first().ok_or_else(|| {
                    ApplicationError::new(ErrorCode::InvalidArguments, Operation::Webview)
                })?;
                tauri::WebviewWindowBuilder::from_config(app.handle(), config)
                    .and_then(|builder| {
                        // WebView2 raises this for the top frame only, so the
                        // documentation frame navigates freely.
                        builder
                            .data_directory(data_directory)
                            .initialization_script(script)
                            .on_navigation(move |url| {
                                let allowed = shell::navigation::allowed(&origins, url);
                                if !allowed {
                                    navigation_diagnostics.failure(ApplicationError::new(
                                        ErrorCode::InvalidArguments,
                                        Operation::Webview,
                                    ));
                                }
                                allowed
                            })
                            .build()
                    })
                    .map_err(|error| {
                        ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview)
                            .caused_by(error)
                    })
            })();
            if let Err(error) = outcome {
                setup_diagnostics.failure(error);
                app.handle().exit(1);
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            let state = window.state::<Arc<TerminalState>>();
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let manager = window.state::<Arc<ManagerStart>>();
                if let Err(error) = tauri::async_runtime::block_on(manager.close_checked()) {
                    api.prevent_close();
                    state.launch.diagnostics.failure(error);
                    window.app_handle().exit(1);
                    return;
                }
                let sign_in = window.state::<Arc<shell::sign_in::SignIn>>();
                if let Err(error) = tauri::async_runtime::block_on(sign_in.stop()) {
                    api.prevent_close();
                    state.launch.diagnostics.failure(error);
                }
                if let Err(error) = state.stop() {
                    api.prevent_close();
                    state.launch.diagnostics.failure(error);
                }
            } else if matches!(event, tauri::WindowEvent::Destroyed)
                && let Err(error) = state.stop()
            {
                state.launch.diagnostics.failure(error);
            }
        })
        .build(context)
        .map_err(|e| {
            ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview).caused_by(e)
        })?;
    let sign_in = app.state::<Arc<shell::sign_in::SignIn>>().inner().clone();
    let manager = app.state::<Arc<ManagerStart>>().inner().clone();
    #[cfg(windows)]
    let monitoring = {
        let watched = manager.clone();
        let host = app.handle().clone();
        let watched_diagnostics = diagnostics.clone();
        tauri::async_runtime::spawn(async move {
            let mut lost_since = None;
            while !watched.is_closed() {
                let now = std::time::Instant::now();
                if let Err(error) =
                    supervision_continues(watched.supervision_status(), &mut lost_since, now)
                {
                    watched.report_failure(error.clone());
                    watched_diagnostics.failure(error);
                    host.exit(1);
                    break;
                }
                tokio::time::sleep(std::time::Duration::from_millis(500)).await;
            }
        })
    };
    let code = app.run_return(|_, _| {});
    #[cfg(windows)]
    monitoring.abort();
    let manager_cleanup = tauri::async_runtime::block_on(manager.close_checked());
    let sign_in_cleanup = tauri::async_runtime::block_on(sign_in.stop());
    let terminal_cleanup = state.stop();
    manager_cleanup?;
    sign_in_cleanup?;
    terminal_cleanup?;
    Ok(code)
}

pub(crate) fn supervision_continues(
    status: Result<bool>,
    lost_since: &mut Option<std::time::Instant>,
    now: std::time::Instant,
) -> Result<()> {
    if status? {
        *lost_since = None;
    } else if now.duration_since(*lost_since.get_or_insert(now))
        >= std::time::Duration::from_secs(90)
    {
        return Err(ApplicationError::new(
            ErrorCode::ManagerUnavailable,
            Operation::Manager,
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    #[test]
    fn healthy_gui_allows_bounded_repair_but_fails_prolonged_or_terminal_supervision_loss() {
        use super::*;
        use std::time::{Duration, Instant};
        let now = Instant::now();
        let mut lost = None;
        supervision_continues(Ok(true), &mut lost, now).unwrap();
        supervision_continues(Ok(false), &mut lost, now).unwrap();
        supervision_continues(Ok(false), &mut lost, now + Duration::from_secs(89)).unwrap();
        assert_eq!(
            supervision_continues(Ok(false), &mut lost, now + Duration::from_secs(90))
                .unwrap_err()
                .code,
            ErrorCode::ManagerUnavailable
        );
        supervision_continues(Ok(true), &mut lost, now + Duration::from_secs(91)).unwrap();
        assert!(lost.is_none());
        supervision_continues(Ok(false), &mut lost, now + Duration::from_secs(92)).unwrap();
        assert_eq!(
            supervision_continues(
                Err(ApplicationError::new(
                    ErrorCode::ManagerUnavailable,
                    Operation::Manager
                )),
                &mut lost,
                now + Duration::from_secs(93)
            )
            .unwrap_err()
            .code,
            ErrorCode::ManagerUnavailable
        );
    }
    use super::*;
    use tauri::{
        WebviewWindowBuilder,
        http::HeaderValue,
        ipc::CallbackFn,
        test::{INVOKE_KEY, get_ipc_response, mock_builder, mock_context, noop_assets},
        webview::InvokeRequest,
    };

    #[test]
    fn every_registered_command_requires_the_shell_token() {
        let token = ShellToken::mint().unwrap();
        let exact = token.value().to_owned();
        let wrong = "0".repeat(exact.len());
        let modules = vec![
            terminal::commands(),
            docs::commands(),
            logs::commands(),
            shell::commands(),
            shell::window_controls::commands(),
            shell::sign_in::commands(),
            manager::commands(),
        ];
        let names: Vec<&str> = modules
            .iter()
            .flat_map(|m| m.names.iter().copied())
            .collect();
        assert!(names.contains(&"diagnostics_snapshot") && names.contains(&"terminal_open"));
        let diagnostics = Arc::new(Diagnostics::default());
        let app = mock_builder()
            .invoke_handler(dispatch(modules, token, diagnostics).unwrap())
            .build(mock_context(noop_assets()))
            .unwrap();
        let window = WebviewWindowBuilder::new(&app, "main", Default::default())
            .build()
            .unwrap();
        let call = |cmd: &str, body: InvokeBody, header: Option<&str>| {
            let mut headers = HeaderMap::new();
            if let Some(value) = header {
                headers.insert(TOKEN_HEADER, HeaderValue::from_str(value).unwrap());
            }
            get_ipc_response(
                &window,
                InvokeRequest {
                    cmd: cmd.into(),
                    callback: CallbackFn(0),
                    error: CallbackFn(1),
                    url: if cfg!(windows) {
                        "http://tauri.localhost"
                    } else {
                        "tauri://localhost"
                    }
                    .parse()
                    .unwrap(),
                    body,
                    headers,
                    invoke_key: INVOKE_KEY.to_owned(),
                },
            )
        };
        let refused = serde_json::to_value(ApplicationError::new(
            ErrorCode::InvalidArguments,
            Operation::Webview,
        ))
        .unwrap();
        for name in &names {
            for (body, header) in [
                (InvokeBody::Json(serde_json::json!({"after": 0})), None),
                (
                    InvokeBody::Json(serde_json::json!({"token": wrong, "after": 0})),
                    None,
                ),
                (
                    InvokeBody::Json(serde_json::json!({"after": 0})),
                    Some(exact.as_str()),
                ),
                (InvokeBody::Raw(b"input".to_vec()), None),
                (InvokeBody::Raw(b"input".to_vec()), Some(wrong.as_str())),
                (InvokeBody::Json(serde_json::json!([105, 110])), None),
                (
                    InvokeBody::Json(serde_json::json!([105, 110])),
                    Some(wrong.as_str()),
                ),
                (InvokeBody::Json(serde_json::json!([105, 110])), Some("")),
            ] {
                assert_eq!(call(name, body, header).unwrap_err(), refused, "{name}");
            }
            // The exact token passes the guard; the unmanaged terminal state
            // then fails inside the command, not at the token check.
            let admitted = call(
                name,
                InvokeBody::Json(serde_json::json!({"token": exact, "after": 0})),
                None,
            );
            assert_ne!(admitted.err(), Some(refused.clone()), "{name}");
            // A byte array from the postMessage fallback presents the header.
            let fallback = call(
                name,
                InvokeBody::Json(serde_json::json!([105, 110])),
                Some(exact.as_str()),
            );
            assert_ne!(fallback.err(), Some(refused.clone()), "{name}");
        }
    }

    #[test]
    fn json_calls_present_the_token_argument_and_raw_calls_the_header() {
        let mut headers = HeaderMap::new();
        headers.insert(TOKEN_HEADER, HeaderValue::from_static("from-header"));
        let json = InvokeBody::Json(serde_json::json!({"token": "from-argument", "cols": 80}));
        assert_eq!(presented_token(&json, &headers), "from-argument");
        let raw = InvokeBody::Raw(b"input".to_vec());
        assert_eq!(presented_token(&raw, &headers), "from-header");
        let empty = HeaderMap::new();
        assert_eq!(presented_token(&raw, &empty), "");
        let fallback = InvokeBody::Json(serde_json::json!([105, 110]));
        assert_eq!(presented_token(&fallback, &headers), "from-header");
        assert_eq!(presented_token(&fallback, &empty), "");
        for missing in [serde_json::json!({}), serde_json::json!({"token": 7})] {
            assert_eq!(presented_token(&InvokeBody::Json(missing), &headers), "");
        }
        let null = InvokeBody::Json(serde_json::Value::Null);
        assert_eq!(presented_token(&null, &headers), "from-header");
    }

    #[test]
    fn command_names_must_be_unique_across_modules() {
        assert!(distinct(&[&["a", "b"], &["c"], &[]]));
        assert!(!distinct(&[&["a", "b"], &["b"]]));
    }

    #[test]
    fn unpresented_token_is_refused() {
        let token = ShellToken::mint().unwrap();
        let headers = HeaderMap::new();
        let body = InvokeBody::Json(serde_json::json!({"cols": 80}));
        let error = token
            .verify(presented_token(&body, &headers), Operation::Webview)
            .unwrap_err();
        assert_eq!(error.code, ErrorCode::InvalidArguments);
    }
}
