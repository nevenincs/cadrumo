use super::{Output, Session, TerminalState};
use crate::app::Commands;
use cadrumo_application::{
    diagnostics::{Diagnostics, Snapshot},
    error::application::{ApplicationError, ErrorCode, Operation, Result},
};
use std::sync::Arc;
use tauri::{Runtime, State};

fn failure(code: ErrorCode) -> ApplicationError {
    ApplicationError::new(code, Operation::Terminal)
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
                .map_err(|_| failure(ErrorCode::LockPoisoned))?;
            if session.is_some() {
                return Err(failure(ErrorCode::SessionUnavailable));
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
                .map_err(|_| failure(ErrorCode::LockPoisoned))?
                .as_mut()
                .ok_or_else(|| failure(ErrorCode::SessionUnavailable))?
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
                .map_err(|_| failure(ErrorCode::LockPoisoned))?
                .as_ref()
                .ok_or_else(|| failure(ErrorCode::SessionUnavailable))?
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
                .map_err(|_| failure(ErrorCode::LockPoisoned))?
                .as_mut()
                .ok_or_else(|| failure(ErrorCode::SessionUnavailable))?
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

pub fn commands<R: Runtime>() -> Commands<R> {
    crate::app::commands![
        terminal_start,
        terminal_input,
        terminal_resize,
        terminal_read,
        terminal_stop,
        diagnostics_snapshot
    ]
}
