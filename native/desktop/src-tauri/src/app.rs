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
use std::{
    collections::BTreeSet,
    sync::{Arc, OnceLock},
};
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
            Ok(()) => {
                // Synchronous commands run inside WebView2's request callback,
                // which cannot unwind: an escaping panic would abort the host.
                let resolver = invoke.resolver.clone();
                std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| (module.handler)(invoke)))
                    .unwrap_or_else(|_| {
                        diagnostics.contained_panic(Some(HostStage::Window), Operation::Webview);
                        resolver
                            .reject(ApplicationError::new(ErrorCode::Panic, Operation::Webview));
                        true
                    })
            }
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
    logs::native::install(diagnostics.clone());
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
    let modules = vec![
        terminal::commands(),
        docs::commands(),
        logs::commands(),
        shell::commands(),
        shell::channel::commands(),
        shell::window_controls::commands(),
        shell::about::commands(),
        shell::sign_in::commands(),
        shell::provider_settings::commands(),
        shell::agent_access::commands(),
        shell::language::commands(),
        shell::setup::commands(),
        shell::user_profile::commands(),
        shell::user_profile::censo::commands(),
        shell::aeat_sync::commands(),
        shell::ledger::commands(),
        shell::modelo::commands(),
        shell::sede_view::commands(),
        manager::commands(),
        agent::commands(),
        crate::startup::commands(),
        crate::close_outcome::commands(),
    ];
    let registered = logs::frontend::RegisteredCommands(
        modules
            .iter()
            .flat_map(|module| module.names.iter().copied())
            .collect(),
    );
    let handler = dispatch(modules, token, diagnostics.clone())?;
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
        .manage(registered)
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
            let loading = tauri::WebviewWindowBuilder::from_config(app.handle(), &loading)?
                .center()
                .incognito(true)
                .initialization_script(script)
                .on_navigation(move |url| shell::navigation::allowed(&origins, url))
                .build()?;
            #[cfg(windows)]
            sharpen_icon(loading.as_ref().window(), None)?;
            #[cfg(not(windows))]
            drop(loading);
            Ok(())
        })
        .on_window_event(|window, event| {
            #[cfg(windows)]
            if let tauri::WindowEvent::ScaleFactorChanged { scale_factor, .. } = event
                && let Err(error) = sharpen_icon(window.clone(), Some(*scale_factor))
                && let Some(state) = window.try_state::<Arc<TerminalState>>()
            {
                state.launch.diagnostics.failure(webview_failure(error));
            }
            if window.label() == "startup" {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let startup = window
                        .state::<Arc<crate::startup::Startup>>()
                        .inner()
                        .clone();
                    startup.cancel();
                    let host = window.app_handle().clone();
                    let diagnostics = startup.diagnostics();
                    if let Err(error) = window.hide() {
                        diagnostics.failure(webview_failure(error));
                    }
                    spawn_detached(host.clone(), diagnostics, HostStage::Shutdown, async move {
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
                let view = window
                    .try_state::<Arc<shell::sede_view::SedeViewHost>>()
                    .map(|view| view.inner().clone());
                // A close the hidden window continues was already decided.
                if !view.as_ref().is_some_and(|view| view.window_closing()) {
                    // The page asks before staged work is dropped; it answers
                    // by closing or keeping the window open.
                    if shell::window_controls::close_held(window) {
                        api.prevent_close();
                        return;
                    }
                    state
                        .launch
                        .diagnostics
                        .host_event(EventKind::WindowCloseRequested, HostStage::Shutdown);
                }
                // An open view publishes the person's session before sign-in
                // ends it; the window goes away meanwhile instead of freezing.
                if let Some(view) = view
                    && close_behind(&view, window, &state.launch.diagnostics)
                {
                    api.prevent_close();
                    return;
                }
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
    #[cfg(unix)]
    quit_on_signal(
        &handle,
        &diagnostics,
        tokio::signal::unix::SignalKind::terminate(),
    )?;
    // The application can end without returning from the run loop: on macOS a Quit
    // terminates the process right after the loop reports its exit. Shutdown therefore
    // runs when the loop reports its exit, once, and the return path reuses its outcome.
    let shutdown: Arc<OnceLock<Result<()>>> = Arc::new(OnceLock::new());
    let settle = {
        let startup = startup.clone();
        let shutdown = shutdown.clone();
        move |handle: &tauri::AppHandle| {
            shutdown
                .get_or_init(|| {
                    startup.cancel();
                    tauri::async_runtime::block_on(startup.settle());
                    close_clients_and_supervision(handle)
                })
                .clone()
        }
    };
    let exiting = settle.clone();
    let code = app.run_return(move |handle, event| match event {
        tauri::RunEvent::ExitRequested { .. } => {
            diagnostics.host_event(EventKind::HostExitRequested, HostStage::Shutdown);
        }
        tauri::RunEvent::Exit => {
            // The process may end before the failure could be returned.
            if let Err(error) = exiting(handle) {
                diagnostics.failure(error);
            }
        }
        _ => {}
    });
    settle(&handle)?;
    if startup.failed() {
        return Ok(1);
    }
    Ok(code)
}

/// A termination request (a logout, a system shutdown or a stop sent to the process)
/// ends the window as a quit does, so the changes it submitted get the same settle
/// window and its runtime the same drain. Registered before the run loop starts, so
/// no such request meanwhile ends the process without them.
#[cfg(unix)]
fn quit_on_signal<R: Runtime>(
    handle: &tauri::AppHandle<R>,
    diagnostics: &Arc<Diagnostics>,
    kind: tokio::signal::unix::SignalKind,
) -> Result<()> {
    let host = handle.clone();
    let requests = on_signal(kind, move || host.exit(0)).map_err(|cause| {
        ApplicationError::new(ErrorCode::EnvironmentFailed, Operation::Launch).caused_by(cause)
    })?;
    spawn_detached(
        handle.clone(),
        diagnostics.clone(),
        HostStage::Shutdown,
        requests,
    );
    Ok(())
}

/// Takes `kind` from its default disposition now and answers each delivery with `act`
/// once the returned task runs. Every further delivery asks again; the close already
/// under way answers it.
#[cfg(unix)]
fn on_signal(
    kind: tokio::signal::unix::SignalKind,
    act: impl Fn() + Send + 'static,
) -> std::io::Result<impl std::future::Future<Output = ()> + Send + 'static> {
    let mut requests = tauri::async_runtime::block_on(async { tokio::signal::unix::signal(kind) })?;
    Ok(async move {
        while requests.recv().await.is_some() {
            act();
        }
    })
}

/// Hides `window` and lets `view` publish behind it, closing the window again
/// once the view has ended. Says whether the close waits for that. A launch
/// meanwhile is not answered by the hidden window: it waits for the lock.
fn close_behind<R: Runtime>(
    view: &Arc<shell::sede_view::SedeViewHost>,
    window: &tauri::Window<R>,
    diagnostics: &Arc<Diagnostics>,
) -> bool {
    let hidden = window.clone();
    let hiding = diagnostics.clone();
    let closing = window.clone();
    let continuing = diagnostics.clone();
    let close = view.close_behind(
        move || {
            shell::single_instance::close();
            if let Err(error) = hidden.hide() {
                hiding.failure(webview_failure(error));
            }
        },
        move || {
            if let Err(error) = closing.close() {
                continuing.failure(webview_failure(error));
                closing.app_handle().exit(1);
            }
        },
    );
    close == shell::sede_view::WindowClose::Behind
}

/// End runtime clients before asking their owned supervisor to drain. Attempt
/// every cleanup even after a failure, including on run-loop exit without a
/// window close event. Each owner keeps failed cleanup available for retry.
fn close_clients_and_supervision<R: Runtime>(handle: &tauri::AppHandle<R>) -> Result<()> {
    // First, while the person's session is still held: the view publishes its session.
    if let Some(view) = handle.try_state::<Arc<shell::sede_view::SedeViewHost>>() {
        view.close();
    }
    settle_changes(handle);
    if let Some(modelo) = handle.try_state::<Arc<shell::modelo::ModeloHost>>() {
        modelo.close();
    }
    if let Some(ledger) = handle.try_state::<Arc<shell::ledger::LedgerHost>>() {
        ledger.close();
    }
    if let Some(profile) = handle.try_state::<Arc<shell::user_profile::ProfileHost>>() {
        profile.close();
    }
    // Preparation may be opening a person connection. Wake it before joining
    // the agent or any observer that depends on that exact window connection.
    if let Some(sign_in) = handle.try_state::<Arc<shell::sign_in::SignIn>>() {
        sign_in.request_stop();
    }
    let language_cleanup = handle
        .try_state::<Arc<shell::language::LanguageHost>>()
        .map_or(Ok(()), |language| {
            tauri::async_runtime::block_on(language.close())
        });
    let setup_cleanup = handle
        .try_state::<Arc<shell::setup::SetupHost>>()
        .map_or(Ok(()), |setup| {
            tauri::async_runtime::block_on(setup.close())
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
        .and(setup_cleanup)
        .and(agent_cleanup)
        .and(sign_in_cleanup)
        .and(terminal_cleanup)
        .and(manager_cleanup)
}

/// Stops admitting changes, then gives the changes the window already submitted one
/// shared settle window to report before any client ends. What is still running then
/// is ended with its client; the runtime's journal keeps what happened to it, and this
/// root's next window says that its outcome is unknown.
fn settle_changes<R: Runtime>(handle: &tauri::AppHandle<R>) {
    let deadline =
        std::time::Instant::now() + cadrumo_application::shutdown::OPERATION_SETTLE_BOUND;
    let profile = handle
        .try_state::<Arc<shell::user_profile::ProfileHost>>()
        .map(|profile| profile.inner().clone());
    let sign_in = handle
        .try_state::<Arc<shell::sign_in::SignIn>>()
        .map(|sign_in| sign_in.inner().clone());
    let interrupted = tauri::async_runtime::block_on(async move {
        let relayed = async {
            match profile {
                Some(profile) => profile.settle(deadline).await,
                None => false,
            }
        };
        let helper = async {
            match sign_in {
                Some(sign_in) => sign_in.settle_changes(deadline).await,
                None => None,
            }
        };
        let (relayed, helper) = tokio::join!(relayed, helper);
        relayed
            .then_some(crate::close_outcome::PROFILE_RELAY)
            .into_iter()
            .chain(helper)
            .collect::<Vec<_>>()
    });
    if interrupted.is_empty() {
        return;
    }
    if let Some(outcomes) = handle
        .try_state::<Option<Arc<crate::close_outcome::CloseOutcomes>>>()
        .and_then(|outcomes| outcomes.inner().clone())
        && let Err(error) = outcomes.interrupted(&interrupted)
        && let Some(state) = handle.try_state::<Arc<TerminalState>>()
    {
        state.launch.diagnostics.failure(error);
    }
}

pub(crate) async fn assemble<R: Runtime>(
    app: tauri::AppHandle<R>,
    launch: Launch,
    startup: &crate::startup::Startup,
) -> Result<()> {
    let diagnostics = launch.diagnostics.clone();
    #[cfg(windows)]
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
        agent::dialog_plugin(),
    ] {
        startup.check_cancelled()?;
        app.plugin(plugin).map_err(|e| {
            ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview).caused_by(e)
        })?;
    }
    let manager = Arc::new(ManagerStart::new(&launch));
    app.manage(manager.clone());
    app.manage(crate::close_outcome::of(&launch));
    app.manage(Arc::new(TerminalState::new(launch)));
    let sign_in = app.state::<Arc<shell::sign_in::SignIn>>().inner().clone();
    let agent = app.state::<Arc<agent::AgentHost>>().inner().clone();
    app.manage(Arc::new(shell::setup::SetupHost::new(
        sign_in.clone(),
        agent,
        diagnostics.clone(),
    )));
    let profile = Arc::new(shell::user_profile::ProfileHost::new(sign_in.clone()));
    app.manage(profile.clone());
    app.manage(Arc::new(shell::ledger::LedgerHost::new(profile.clone())));
    app.manage(Arc::new(shell::sede_view::SedeViewHost::new(
        diagnostics.clone(),
    )));
    app.manage(Arc::new(shell::modelo::ModeloHost::new(profile)));
    startup.stage(crate::startup::Phase::Runtime);
    #[cfg(any(windows, target_os = "macos"))]
    tokio::select! {
        result = manager.ensure_ready(&sign_in) => result?,
        _ = startup.wait_cancelled() => { startup.check_cancelled()?; }
    }
    #[cfg(not(any(windows, target_os = "macos")))]
    manager.start(false).await?;
    startup.check_cancelled()?;
    startup.stage(crate::startup::Phase::Workspace);
    let config = &app.config().app.windows[0];
    let origins = startup.origins.clone();
    let workspace = tauri::WebviewWindowBuilder::from_config(&app, config).and_then(|builder| {
        #[cfg(windows)]
        let builder = {
            let arguments = shell::webview_environment::workspace_browser_arguments();
            let builder = match &arguments {
                Some(arguments) => builder.additional_browser_args(arguments),
                None => builder,
            };
            match shell::webview_environment::workspace_data_directory(
                data_directory,
                arguments.as_deref(),
            ) {
                Some(directory) => builder.data_directory(directory),
                None => builder,
            }
        };
        // The system draws the controls over the page's header.
        #[cfg(target_os = "macos")]
        let builder = builder
            .decorations(true)
            .title_bar_style(tauri::TitleBarStyle::Overlay)
            .hidden_title(true)
            .traffic_light_position(tauri::LogicalPosition::new(16.0, 15.0));
        let builder = builder.visible(false);
        builder
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
                                ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview)
                                    .caused_by(error),
                            );
                        return;
                    }
                    if let Some(loading) = window.app_handle().get_webview_window("startup")
                        && let Err(error) = loading.destroy()
                    {
                        window
                            .state::<Arc<TerminalState>>()
                            .launch
                            .diagnostics
                            .failure(webview_failure(error));
                    }
                }
            })
            .build()
    });
    #[cfg(windows)]
    let workspace = workspace.and_then(|window| {
        sharpen_icon(window.as_ref().window(), None)?;
        Ok(window)
    });
    workspace.map_err(|e| {
        ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview).caused_by(e)
    })?;
    #[cfg(any(windows, target_os = "macos"))]
    {
        let host = app.clone();
        spawn_detached(
            app.clone(),
            diagnostics.clone(),
            HostStage::Manager,
            async move {
                let mut lost_since = None;
                let mut changes = manager.supervision_changes();
                while !manager.is_closed() {
                    changes.borrow_and_update();
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
                    // Only a status change or the loss bound can change the verdict.
                    let bound = lost_since.map(|since| {
                        tokio::time::Instant::from_std(since + SUPERVISION_LOSS_BOUND)
                    });
                    tokio::select! {
                        changed = changes.changed() => {
                            if changed.is_err() {
                                break;
                            }
                        }
                        () = async {
                            match bound {
                                Some(bound) => tokio::time::sleep_until(bound).await,
                                None => std::future::pending().await,
                            }
                        } => {}
                    }
                }
            },
        );
    }
    Ok(())
}

/// Give `window` its small icon at the small icon size of `scale` (its current scale when
/// `None`). Tauri sets the large-size entry of the application icon as the small icon, which
/// Windows then shrinks crudely in the title bar and in Task Manager.
#[cfg(windows)]
fn sharpen_icon<R: Runtime>(window: tauri::Window<R>, scale: Option<f64>) -> tauri::Result<()> {
    let scale = match scale {
        Some(scale) => scale,
        None => window.scale_factor()?,
    };
    let size = (16.0 * scale).round().clamp(16.0, 256.0) as u32;
    window.set_icon(tauri::image::Image::from_icon_resource(
        tauri::utils::platform::WINDOWS_APP_ICON_RESOURCE_ID,
        size,
        size,
    )?)
}

fn webview_failure(error: tauri::Error) -> ApplicationError {
    ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview).caused_by(error)
}

/// Nothing awaits a detached task; a panic in it is recorded and ends the host,
/// which would otherwise keep running without the task's work.
fn spawn_detached<R: Runtime>(
    host: tauri::AppHandle<R>,
    diagnostics: Arc<Diagnostics>,
    stage: HostStage,
    task: impl std::future::Future<Output = ()> + Send + 'static,
) {
    let task = tauri::async_runtime::spawn(task);
    tauri::async_runtime::spawn(async move {
        if task.await.is_err() {
            diagnostics.contained_panic(Some(stage), Operation::Webview);
            host.exit(1);
        }
    });
}

/// How long the GUI tolerates lost supervision while the manager repairs it.
const SUPERVISION_LOSS_BOUND: std::time::Duration = std::time::Duration::from_secs(90);

pub(crate) fn supervision_continues(
    status: Result<bool>,
    lost_since: &mut Option<std::time::Instant>,
    now: std::time::Instant,
) -> Result<()> {
    if status? {
        *lost_since = None;
    } else if now.duration_since(*lost_since.get_or_insert(now)) >= SUPERVISION_LOSS_BOUND {
        return Err(ApplicationError::new(
            ErrorCode::ManagerUnavailable,
            Operation::Manager,
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    #[cfg(unix)]
    #[test]
    fn a_signal_delivered_to_the_process_asks_the_window_to_close() {
        // A signal nothing else in this test binary uses, so the delivery is this test's alone.
        let (asked, answered) = std::sync::mpsc::channel();
        let requests = super::on_signal(
            tokio::signal::unix::SignalKind::user_defined1(),
            move || {
                let _ = asked.send(());
            },
        )
        .unwrap();
        tauri::async_runtime::spawn(requests);
        for _ in 0..2 {
            let delivered = std::process::Command::new("/bin/kill")
                .args(["-USR1", &std::process::id().to_string()])
                .status()
                .unwrap();
            assert!(delivered.success());
            answered
                .recv_timeout(std::time::Duration::from_secs(10))
                .expect("the delivery asked the window to close");
        }
    }

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
            shell::channel::commands(),
            shell::window_controls::commands(),
            shell::about::commands(),
            shell::sign_in::commands(),
            shell::provider_settings::commands(),
            shell::agent_access::commands(),
            shell::language::commands(),
            shell::setup::commands(),
            shell::user_profile::commands(),
            shell::user_profile::censo::commands(),
            shell::aeat_sync::commands(),
            shell::ledger::commands(),
            shell::modelo::commands(),
            shell::sede_view::commands(),
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

    #[tauri::command]
    fn panicking_command() -> Result<()> {
        let private = std::hint::black_box("synthetic-private-value");
        panic!("a synchronous command fails with {private}")
    }

    #[test]
    fn a_panicking_synchronous_command_is_rejected_and_recorded_instead_of_aborting() {
        let token = ShellToken::mint().unwrap();
        let exact = token.value().to_owned();
        let diagnostics = Arc::new(Diagnostics::default());
        let modules = vec![crate::app::commands![panicking_command]];
        let app = mock_builder()
            .invoke_handler(dispatch(modules, token, diagnostics.clone()).unwrap())
            .build(mock_context(noop_assets()))
            .unwrap();
        let window = WebviewWindowBuilder::new(&app, "main", Default::default())
            .build()
            .unwrap();
        let reply = get_ipc_response(
            &window,
            InvokeRequest {
                cmd: "panicking_command".into(),
                callback: CallbackFn(0),
                error: CallbackFn(1),
                url: if cfg!(windows) {
                    "http://tauri.localhost"
                } else {
                    "tauri://localhost"
                }
                .parse()
                .unwrap(),
                body: InvokeBody::Json(serde_json::json!({"token": exact})),
                headers: HeaderMap::new(),
                invoke_key: INVOKE_KEY.to_owned(),
            },
        )
        .unwrap_err();
        assert_eq!(reply["code"], "panic");
        assert_eq!(reply["operation"], "webview");
        assert!(!reply.to_string().contains("synthetic-private-value"));
        let recorded = diagnostics.snapshot(u64::MAX).events;
        assert!(recorded.iter().any(|event| {
            matches!(event.kind, EventKind::Failure)
                && event.stage == Some(HostStage::Window)
                && event
                    .failure
                    .as_ref()
                    .is_some_and(|failure| failure.code == ErrorCode::Panic)
        }));
    }
}
