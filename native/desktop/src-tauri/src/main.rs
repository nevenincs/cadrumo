#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod package;
mod terminal;

use std::{io, path::PathBuf, sync::Mutex};
use tauri::{Manager, State};
use terminal::{Output, Session, TerminalState};

#[tauri::command]
fn terminal_start(state: State<'_, TerminalState>, cols: u16, rows: u16) -> Result<(), String> {
    let mut session = state.session.lock().map_err(|e| e.to_string())?;
    if session.is_some() {
        return Err("A TUI session is already running".into());
    }
    *session = Some(Session::start(
        &state.launch,
        cols,
        rows,
        &["-m", "cadrumo.entrypoints.tui"],
    )?);
    Ok(())
}

#[tauri::command]
fn terminal_input(state: State<'_, TerminalState>, data: Vec<u8>) -> Result<(), String> {
    state
        .session
        .lock()
        .map_err(|e| e.to_string())?
        .as_mut()
        .ok_or("TUI is not running")?
        .input(&data)
}

#[tauri::command]
fn terminal_resize(state: State<'_, TerminalState>, cols: u16, rows: u16) -> Result<(), String> {
    state
        .session
        .lock()
        .map_err(|e| e.to_string())?
        .as_ref()
        .ok_or("TUI is not running")?
        .resize(cols, rows)
}

#[tauri::command]
fn terminal_read(state: State<'_, TerminalState>) -> Result<Output, String> {
    state
        .session
        .lock()
        .map_err(|e| e.to_string())?
        .as_mut()
        .ok_or("TUI is not running")?
        .read()
}

#[tauri::command]
fn terminal_stop(state: State<'_, TerminalState>) -> Result<(), String> {
    state.session.lock().map_err(|e| e.to_string())?.take();
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    if cfg!(target_os = "macos") {
        return Err(
            io::Error::other("macOS WebView storage containment remains unverified").into(),
        );
    }
    let root = std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT")
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .unwrap_or(
            std::env::current_exe()?
                .parent()
                .ok_or("Executable has no parent")?
                .to_owned(),
        );
    let launch =
        tauri::async_runtime::block_on(package::resolve(root)).map_err(io::Error::other)?;
    let data_directory = launch.webview.clone();
    tauri::Builder::default()
        .manage(TerminalState {
            launch,
            session: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            terminal_start,
            terminal_input,
            terminal_resize,
            terminal_read,
            terminal_stop
        ])
        .setup(move |app| {
            let title = app.config().product_name.as_deref().unwrap_or("CADRUMO");
            tauri::WebviewWindowBuilder::new(
                app,
                "main",
                tauri::WebviewUrl::App("index.html".into()),
            )
            .title(title)
            .inner_size(1440.0, 1050.0)
            .min_inner_size(520.0, 400.0)
            .data_directory(data_directory)
            .build()?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::Destroyed) {
                let state = window.state::<TerminalState>();
                if let Ok(mut session) = state.session.lock() {
                    session.take();
                }
            }
        })
        .run(tauri::generate_context!())?;
    Ok(())
}
