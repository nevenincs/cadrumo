use crate::{
    package::Launch,
    terminal::{Output, Session, TerminalState},
};
use cadrumo_application::{
    diagnostics::{Diagnostics, EventKind, Snapshot},
    failure::{Failure, FailureCode, Operation, Result},
};
use std::sync::{Arc, Mutex};
use tauri::{Manager, State};

fn failure(code: FailureCode) -> Failure {
    Failure::new(code, Operation::Terminal)
}
fn record<T>(diagnostics: &Diagnostics, outcome: Result<T>) -> Result<T> {
    if let Err(error) = &outcome {
        diagnostics.failure(error.clone());
    }
    outcome
}
#[tauri::command]
fn terminal_start(state: State<'_, Arc<TerminalState>>, cols: u16, rows: u16) -> Result<()> {
    record(
        &state.launch.diagnostics,
        (|| {
            let mut session = state
                .session
                .lock()
                .map_err(|_| failure(FailureCode::LockPoisoned))?;
            if session.is_some() {
                return Err(failure(FailureCode::SessionUnavailable));
            }
            *session = Some(Session::start(
                &state.launch,
                cols,
                rows,
                &["-m", "cadrumo.entrypoints.tui"],
            )?);
            Ok(())
        })(),
    )
}
#[tauri::command]
fn terminal_input(state: State<'_, Arc<TerminalState>>, data: Vec<u8>) -> Result<()> {
    record(
        &state.launch.diagnostics,
        (|| {
            state
                .session
                .lock()
                .map_err(|_| failure(FailureCode::LockPoisoned))?
                .as_mut()
                .ok_or_else(|| failure(FailureCode::SessionUnavailable))?
                .input(&data)
        })(),
    )
}
#[tauri::command]
fn terminal_resize(state: State<'_, Arc<TerminalState>>, cols: u16, rows: u16) -> Result<()> {
    record(
        &state.launch.diagnostics,
        (|| {
            state
                .session
                .lock()
                .map_err(|_| failure(FailureCode::LockPoisoned))?
                .as_ref()
                .ok_or_else(|| failure(FailureCode::SessionUnavailable))?
                .resize(cols, rows)
        })(),
    )
}
#[tauri::command]
fn terminal_read(state: State<'_, Arc<TerminalState>>) -> Result<Output> {
    record(
        &state.launch.diagnostics,
        (|| {
            state
                .session
                .lock()
                .map_err(|_| failure(FailureCode::LockPoisoned))?
                .as_mut()
                .ok_or_else(|| failure(FailureCode::SessionUnavailable))?
                .read()
        })(),
    )
}
#[tauri::command]
fn terminal_stop(state: State<'_, Arc<TerminalState>>) -> Result<()> {
    record(&state.launch.diagnostics, state.stop())
}
#[tauri::command]
fn diagnostics_snapshot(state: State<'_, Arc<TerminalState>>, after: u64) -> Snapshot {
    state.launch.diagnostics.snapshot(after)
}

pub fn run(launch: Launch) -> Result<i32> {
    if cfg!(target_os = "macos") {
        return Err(Failure::new(
            FailureCode::UnsupportedPlatform,
            Operation::Webview,
        ));
    }
    #[cfg(windows)]
    cadrumo_platform::desktop::detach_console();
    let diagnostics = launch.diagnostics.clone();
    diagnostics.event(EventKind::GuiSelected, None, None);
    let data_directory = launch.webview.clone();
    let state = Arc::new(TerminalState {
        launch,
        session: Mutex::new(None),
    });
    let setup_diagnostics = diagnostics.clone();
    let app = tauri::Builder::default()
        .manage(state.clone())
        .invoke_handler(tauri::generate_handler![
            terminal_start,
            terminal_input,
            terminal_resize,
            terminal_read,
            terminal_stop,
            diagnostics_snapshot
        ])
        .setup(move |app| {
            let title = app.config().product_name.as_deref().unwrap_or("CADRUMO");
            if let Err(error) = tauri::WebviewWindowBuilder::new(
                app,
                "main",
                tauri::WebviewUrl::App("index.html".into()),
            )
            .title(title)
            .inner_size(1440.0, 1050.0)
            .min_inner_size(520.0, 400.0)
            .data_directory(data_directory)
            .build()
            {
                setup_diagnostics.failure(
                    Failure::new(FailureCode::WebviewFailed, Operation::Webview).caused_by(error),
                );
                app.handle().exit(1);
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            let state = window.state::<Arc<TerminalState>>();
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
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
        .build(tauri::generate_context!())
        .map_err(|e| Failure::new(FailureCode::WebviewFailed, Operation::Webview).caused_by(e))?;
    let code = app.run_return(|_, _| {});
    state.stop()?;
    Ok(code)
}
