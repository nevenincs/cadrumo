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
            shell::sign_in::commands(),
            manager::commands(),
        ],
        token,
        diagnostics.clone(),
    )?;
    let builder = tauri::Builder::default()
        .plugin(terminal::plugin(&launch))
        .plugin(docs::plugin(&launch)?)
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
            tauri::async_runtime::spawn(async move {
                // Failures are retained in diagnostics; the window remains usable.
                let _ = startup_manager.start(false).await;
            });
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
                tauri::async_runtime::block_on(manager.close());
                let sign_in = window.state::<Arc<shell::sign_in::SignIn>>();
                if let Err(error) = sign_in.children.stop() {
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
    let code = app.run_return(|_, _| {});
    tauri::async_runtime::block_on(manager.close());
    let sign_in_cleanup = sign_in.children.stop();
    let terminal_cleanup = state.stop();
    sign_in_cleanup?;
    terminal_cleanup?;
    Ok(code)
}

#[cfg(test)]
mod tests {
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
