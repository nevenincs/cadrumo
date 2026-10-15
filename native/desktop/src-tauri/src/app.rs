use crate::{
    agent, docs,
    environment::Launch,
    logs,
    manager::{self, ManagerStart},
    shell::{self, token::ShellToken},
    terminal::{self, TerminalState},
};
use cadrumo_application::{
    diagnostics::{Diagnostics, EventKind, HostStage},
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

pub fn run(
    root: std::path::PathBuf,
    parent: crate::environment::Parent,
    diagnostics: Arc<Diagnostics>,
) -> Result<i32> {
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
    diagnostics.event(EventKind::GuiSelected, None, None);
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
            shell::provider_settings::commands(),
            shell::agent_access::commands(),
            shell::language::commands(),
            manager::commands(),
            agent::commands(),
            crate::startup::commands(),
        ],
        token,
        diagnostics.clone(),
    )?;
    let startup = Arc::new(crate::startup::Startup::new(
        root,
        parent,
        diagnostics.clone(),
        script.clone(),
        origins.clone(),
    ));
    let app = tauri::Builder::default()
        .plugin(crate::startup::plugin(diagnostics.clone()))
        .manage(startup.clone())
        .invoke_handler(handler)
        .channel_interceptor(shell::channel::interceptor(diagnostics.clone()))
        .setup(move |app| {
            shell::single_instance::verify(app.config())?;
            let config = app.config().app.windows[0].clone();
            let mut loading = config;
            loading.label = "startup".into();
            loading.url = tauri::WebviewUrl::App("startup.html".into());
            loading.decorations = true;
            loading.width = 480.0;
            loading.height = 300.0;
            loading.min_width = Some(380.0);
            loading.min_height = Some(240.0);
            tauri::WebviewWindowBuilder::from_config(app.handle(), &loading)?
                .center()
                .incognito(true)
                .initialization_script(script)
                .on_navigation(move |url| shell::navigation::allowed(&origins, url))
                .build()?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if window.label() == "startup" {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let startup = window
                        .state::<Arc<crate::startup::Startup>>()
                        .inner()
                        .clone();
                    startup.cancel();
                    let host = window.app_handle().clone();
                    let _ = window.hide();
                    tauri::async_runtime::spawn(async move {
                        startup.settle().await;
                        host.exit(0);
                    });
                }
                return;
            }
            let Some(state) = window.try_state::<Arc<TerminalState>>() else {
                return;
            };
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                state
                    .launch
                    .diagnostics
                    .host_event(EventKind::WindowCloseRequested, HostStage::Shutdown);
                if let Err(error) = close_clients_and_supervision(window.app_handle()) {
                    api.prevent_close();
                    state.launch.diagnostics.failure(error);
                    window.app_handle().exit(1);
                }
            } else if matches!(event, tauri::WindowEvent::Destroyed)
                && let Err(error) = state.shutdown()
            {
                state.launch.diagnostics.failure(error);
            }
        })
        .build(context)
        .map_err(|e| {
            ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview).caused_by(e)
        })?;
    let handle = app.handle().clone();
    let code = app.run_return(move |_, event| {
        if matches!(event, tauri::RunEvent::ExitRequested { .. }) {
            diagnostics.host_event(EventKind::HostExitRequested, HostStage::Shutdown);
        }
    });
    startup.cancel();
    tauri::async_runtime::block_on(startup.settle());
    close_clients_and_supervision(&handle)?;
    if startup.failed() {
        return Ok(1);
    }
    Ok(code)
}

/// End runtime clients before asking their owned supervisor to drain. Attempt
/// every cleanup even after a failure, including on run-loop exit without a
/// window close event. Each owner keeps failed cleanup available for retry.
fn close_clients_and_supervision<R: Runtime>(handle: &tauri::AppHandle<R>) -> Result<()> {
    let language_cleanup = handle
        .try_state::<Arc<shell::language::LanguageHost>>()
        .map_or(Ok(()), |language| {
            tauri::async_runtime::block_on(language.close())
        });
    let agent_cleanup = handle
        .try_state::<Arc<agent::AgentHost>>()
        .map_or(Ok(()), |agent| {
            tauri::async_runtime::block_on(agent.close())
        });
    let sign_in_cleanup = handle
        .try_state::<Arc<shell::sign_in::SignIn>>()
        .map_or(Ok(()), |sign_in| {
            tauri::async_runtime::block_on(sign_in.stop())
        });
    let terminal_cleanup = handle
        .try_state::<Arc<TerminalState>>()
        .map_or(Ok(()), |terminal| terminal.shutdown());
    let manager_cleanup = handle
        .try_state::<Arc<ManagerStart>>()
        .map_or(Ok(()), |manager| {
            tauri::async_runtime::block_on(manager.close_checked())
        });
    language_cleanup
        .and(agent_cleanup)
        .and(sign_in_cleanup)
        .and(terminal_cleanup)
        .and(manager_cleanup)
}

pub(crate) async fn assemble<R: Runtime>(
    app: tauri::AppHandle<R>,
    launch: Launch,
    startup: &crate::startup::Startup,
) -> Result<()> {
    let diagnostics = launch.diagnostics.clone();
    let data_directory = launch.webview.clone();
    if let Some(lease) = launch._publication.as_ref() {
        std::mem::forget(lease.clone());
    }
    for plugin in [
        terminal::plugin(&launch),
        docs::plugin(&launch),
        logs::plugin(&launch),
        shell::plugin(&launch),
        agent::plugin(&launch),
        shell::clipboard_plugin(),
    ] {
        startup.check_cancelled()?;
        app.plugin(plugin).map_err(|e| {
            ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview).caused_by(e)
        })?;
    }
    let manager = Arc::new(ManagerStart::new(&launch));
    app.manage(manager.clone());
    app.manage(Arc::new(TerminalState::new(launch)));
    let sign_in = app.state::<Arc<shell::sign_in::SignIn>>().inner().clone();
    startup.stage(crate::startup::Phase::Runtime);
    #[cfg(windows)]
    tokio::select! {
        result = manager.ensure_ready(&sign_in) => result?,
        _ = startup.wait_cancelled() => { startup.check_cancelled()?; }
    }
    #[cfg(not(windows))]
    manager.start(false).await?;
    startup.check_cancelled()?;
    startup.stage(crate::startup::Phase::Workspace);
    let config = &app.config().app.windows[0];
    let origins = startup.origins.clone();
    tauri::WebviewWindowBuilder::from_config(&app, config)
        .and_then(|builder| {
            builder
                .visible(false)
                .data_directory(data_directory)
                .initialization_script(startup.script.clone())
                .on_navigation(move |url| shell::navigation::allowed(&origins, url))
                .on_page_load(|window, payload| {
                    if matches!(payload.event(), tauri::webview::PageLoadEvent::Finished) {
                        if let Err(error) = window.show() {
                            window
                                .state::<Arc<TerminalState>>()
                                .launch
                                .diagnostics
                                .failure(
                                    ApplicationError::new(
                                        ErrorCode::WebviewFailed,
                                        Operation::Webview,
                                    )
                                    .caused_by(error),
                                );
                            return;
                        }
                        if let Some(loading) = window.app_handle().get_webview_window("startup") {
                            let _ = loading.destroy();
                        }
                    }
                })
                .build()
        })
        .map_err(|e| {
            ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview).caused_by(e)
        })?;
    #[cfg(windows)]
    {
        let host = app.clone();
        tauri::async_runtime::spawn(async move {
            let mut lost_since = None;
            while !manager.is_closed() {
                if let Err(error) = supervision_continues(
                    manager.supervision_status(),
                    &mut lost_since,
                    std::time::Instant::now(),
                ) {
                    manager.report_failure(error.clone());
                    diagnostics.failure(error);
                    host.exit(1);
                    break;
                }
                tokio::time::sleep(std::time::Duration::from_millis(500)).await;
            }
        });
    }
    Ok(())
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
            shell::provider_settings::commands(),
            shell::agent_access::commands(),
            shell::language::commands(),
            manager::commands(),
            agent::commands(),
            crate::startup::commands(),
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
