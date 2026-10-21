use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::{Manager, Runtime, State, Window, WindowEvent, ipc::Channel};

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Presentation {
    maximized: bool,
    fullscreen: bool,
}

#[derive(Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Action {
    Minimize,
    ToggleMaximize,
    Close,
    Drag,
}

/// One top-document listener. A reload replaces it; an old cleanup cannot
/// remove the replacement registered by the next mount.
#[derive(Default)]
pub struct Controls(Mutex<Option<Channel<Presentation>>>);

pub fn commands<R: Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        shell_window_action,
        shell_window_subscribe,
        shell_window_unsubscribe
    ]
}

fn failure(error: tauri::Error) -> ApplicationError {
    ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview).caused_by(error)
}

fn main_window<R: Runtime>(window: &Window<R>) -> Result<()> {
    if window.label() != "main" {
        return Err(ApplicationError::new(
            ErrorCode::InvalidArguments,
            Operation::Webview,
        ));
    }
    Ok(())
}

fn presentation<R: Runtime>(window: &Window<R>) -> Result<Presentation> {
    Ok(Presentation {
        maximized: window.is_maximized().map_err(failure)?,
        fullscreen: window.is_fullscreen().map_err(failure)?,
    })
}

#[tauri::command]
pub fn shell_window_action<R: Runtime>(window: Window<R>, action: Action) -> Result<()> {
    main_window(&window)?;
    match action {
        Action::Minimize => window.minimize(),
        // close() raises CloseRequested, preserving cleanup and refusal.
        Action::Close => window.close(),
        Action::Drag => window.start_dragging(),
        Action::ToggleMaximize => {
            if window.is_fullscreen().map_err(failure)? {
                return Ok(());
            }
            if window.is_maximized().map_err(failure)? {
                window.unmaximize()
            } else if window.is_resizable().map_err(failure)? {
                window.maximize()
            } else {
                return Ok(());
            }
        }
    }
    .map_err(failure)
}

#[tauri::command]
pub fn shell_window_subscribe<R: Runtime>(
    window: Window<R>,
    controls: State<'_, Controls>,
    updates: Channel<Presentation>,
) -> Result<u32> {
    main_window(&window)?;
    let id = updates.id();
    let mut listener = controls.0.lock().unwrap_or_else(|e| e.into_inner());
    updates.send(presentation(&window)?).map_err(failure)?;
    *listener = Some(updates);
    Ok(id)
}

#[tauri::command]
pub fn shell_window_unsubscribe<R: Runtime>(
    window: Window<R>,
    controls: State<'_, Controls>,
    subscription: u32,
) -> Result<()> {
    main_window(&window)?;
    let mut listener = controls.0.lock().unwrap_or_else(|e| e.into_inner());
    if listener
        .as_ref()
        .is_some_and(|channel| channel.id() == subscription)
    {
        *listener = None;
    }
    Ok(())
}

pub fn attach<R: Runtime>(window: &Window<R>) {
    if window.label() != "main" {
        return;
    }
    let observed = window.clone();
    window.on_window_event(move |event| {
        let controls = observed.state::<Controls>();
        let mut listener = controls.0.lock().unwrap_or_else(|e| e.into_inner());
        if matches!(event, WindowEvent::Destroyed) {
            *listener = None;
        } else if matches!(event, WindowEvent::Resized(_) | WindowEvent::Focused(_))
            && let Some(channel) = listener.as_ref()
            && let Ok(state) = presentation(&observed)
            && channel.send(state).is_err()
        {
            *listener = None;
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    use tauri::test::{mock_builder, mock_context, noop_assets};

    #[test]
    fn old_cleanup_cannot_remove_a_replacement_subscription() {
        let app = mock_builder()
            .manage(Controls::default())
            .build(mock_context(noop_assets()))
            .unwrap();
        let old = Channel::<Presentation>::new(|_| Ok(()));
        let current = Channel::<Presentation>::new(|_| Ok(()));
        let current_id = current.id();
        *app.state::<Controls>().0.lock().unwrap() = Some(current);
        let main = tauri::WebviewWindowBuilder::new(&app, "main", Default::default())
            .build()
            .unwrap();
        let window = main.as_ref().window().clone();
        shell_window_unsubscribe(window.clone(), app.state(), old.id()).unwrap();
        assert!(app.state::<Controls>().0.lock().unwrap().is_some());
        shell_window_unsubscribe(window, app.state(), current_id).unwrap();
        assert!(app.state::<Controls>().0.lock().unwrap().is_none());
    }

    #[test]
    fn window_actions_are_closed_and_cannot_address_another_window() {
        for name in ["minimize", "toggle_maximize", "close", "drag"] {
            assert!(serde_json::from_value::<Action>(serde_json::json!(name)).is_ok());
        }
        for name in ["destroy", "execute", "set_title", "exit"] {
            assert!(serde_json::from_value::<Action>(serde_json::json!(name)).is_err());
        }
        let app = mock_builder().build(mock_context(noop_assets())).unwrap();
        let other = tauri::WebviewWindowBuilder::new(&app, "docs", Default::default())
            .build()
            .unwrap();
        assert_eq!(
            shell_window_action(other.as_ref().window().clone(), Action::Close)
                .unwrap_err()
                .code,
            ErrorCode::InvalidArguments
        );
    }
}
