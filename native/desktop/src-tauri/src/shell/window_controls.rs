use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use serde::{Deserialize, Serialize};
use std::sync::{
    Mutex,
    atomic::{AtomicBool, Ordering},
};
use tauri::{Manager, Runtime, State, Window, WindowEvent, ipc::Channel};

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Presentation {
    maximized: bool,
    fullscreen: bool,
    chrome: Chrome,
}

/// Who draws the window's minimise, maximise and close controls.
#[derive(Clone, Copy, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Chrome {
    /// The page draws them in its header.
    Custom,
    /// The system draws them, over the page's header.
    Native,
}

impl Chrome {
    const fn of_platform() -> Self {
        if cfg!(target_os = "macos") {
            Self::Native
        } else {
            Self::Custom
        }
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Action {
    Minimize,
    ToggleMaximize,
    Close,
    Drag,
    /// Restores and raises the window, as when something in it asks for the person.
    Focus,
    /// The page's answer to a close it was asked about: close now.
    CloseNow,
    /// The page's answer to a close it was asked about: the person stays.
    KeepOpen,
}

/// One top-document listener. A reload replaces it; an old cleanup cannot
/// remove the replacement registered by the next mount.
#[derive(Default)]
pub struct Controls(Mutex<Option<Channel<Presentation>>>);

/// The page's say over a close the system raised. While the page listens, a
/// close asks the page first, and the page answers by closing now or keeping
/// the window open. A second close while the first is unanswered closes, so a
/// page that stopped answering never holds the window open.
#[derive(Default)]
pub struct CloseGuard {
    listener: Mutex<Option<Channel<()>>>,
    asked: AtomicBool,
    releasing: AtomicBool,
}

impl CloseGuard {
    /// Whether this close waits for the page, which has just been asked.
    fn hold(&self) -> bool {
        if self.releasing.load(Ordering::Acquire) || self.asked.swap(true, Ordering::AcqRel) {
            return false;
        }
        let listener = self.listener.lock().unwrap_or_else(|e| e.into_inner());
        let asked = listener.as_ref().is_some_and(|page| page.send(()).is_ok());
        if !asked {
            self.asked.store(false, Ordering::Release);
        }
        asked
    }
}

/// Whether a close of `window` waits for its page's answer.
pub fn close_held<R: Runtime>(window: &Window<R>) -> bool {
    window.label() == "main"
        && window
            .try_state::<CloseGuard>()
            .is_some_and(|guard| guard.hold())
}

pub fn commands<R: Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        shell_window_action,
        shell_window_subscribe,
        shell_window_unsubscribe,
        shell_close_guard_subscribe,
        shell_close_guard_unsubscribe
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
        chrome: Chrome::of_platform(),
    })
}

#[tauri::command]
pub async fn shell_window_action<R: Runtime>(window: Window<R>, action: Action) -> Result<()> {
    // Window operations can synchronously ask the event loop for state.
    // Keep them outside WebView2's synchronous IPC callback.
    let diagnostics = window
        .try_state::<std::sync::Arc<crate::terminal::TerminalState>>()
        .map(|state| state.launch.diagnostics.clone());
    let result = tauri::async_runtime::spawn_blocking(move || perform_action(window, action))
        .await
        .map_err(|error| {
            ApplicationError::new(ErrorCode::Panic, Operation::Webview).caused_by(error)
        })
        .and_then(|result| result);
    if let (Err(error), Some(diagnostics)) = (&result, diagnostics) {
        diagnostics.failure(error.clone());
    }
    result
}

fn perform_action<R: Runtime>(window: Window<R>, action: Action) -> Result<()> {
    main_window(&window)?;
    match action {
        Action::Minimize => window.minimize(),
        // close() raises CloseRequested, preserving cleanup and refusal.
        Action::Close => window.close(),
        Action::CloseNow => {
            if let Some(guard) = window.try_state::<CloseGuard>() {
                guard.releasing.store(true, Ordering::Release);
            }
            let result = window.close();
            if result.is_err()
                && let Some(guard) = window.try_state::<CloseGuard>()
            {
                guard.releasing.store(false, Ordering::Release);
            }
            result
        }
        Action::KeepOpen => {
            if let Some(guard) = window.try_state::<CloseGuard>() {
                guard.asked.store(false, Ordering::Release);
            }
            Ok(())
        }
        Action::Drag => window.start_dragging(),
        Action::Focus => window
            .unminimize()
            .and_then(|()| window.show())
            .and_then(|()| window.set_focus()),
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

#[tauri::command]
pub fn shell_close_guard_subscribe<R: Runtime>(
    window: Window<R>,
    guard: State<'_, CloseGuard>,
    requests: Channel<()>,
) -> Result<u32> {
    main_window(&window)?;
    let id = requests.id();
    *guard.listener.lock().unwrap_or_else(|e| e.into_inner()) = Some(requests);
    Ok(id)
}

#[tauri::command]
pub fn shell_close_guard_unsubscribe<R: Runtime>(
    window: Window<R>,
    guard: State<'_, CloseGuard>,
    subscription: u32,
) -> Result<()> {
    main_window(&window)?;
    let mut listener = guard.listener.lock().unwrap_or_else(|e| e.into_inner());
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

    #[tokio::test]
    async fn the_principal_window_accepts_close_now_off_the_ipc_callback() {
        let app = mock_builder()
            .manage(CloseGuard::default())
            .build(mock_context(noop_assets()))
            .unwrap();
        let main = tauri::WebviewWindowBuilder::new(&app, "main", Default::default())
            .build()
            .unwrap();
        shell_window_action(main.as_ref().window().clone(), Action::CloseNow)
            .await
            .unwrap();
        assert!(app.state::<CloseGuard>().releasing.load(Ordering::Acquire));
    }

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
    fn a_close_asks_a_listening_page_once_and_never_holds_the_window_twice() {
        let guard = CloseGuard::default();
        // No page listens: the window closes.
        assert!(!guard.hold());
        let asked = std::sync::Arc::new(std::sync::atomic::AtomicUsize::new(0));
        let counted = asked.clone();
        *guard.listener.lock().unwrap() = Some(Channel::<()>::new(move |_| {
            counted.fetch_add(1, Ordering::SeqCst);
            Ok(())
        }));
        // The page is asked, and a second close while it has not answered
        // closes: a page that stopped answering cannot keep the window open.
        assert!(guard.hold());
        assert!(!guard.hold());
        assert_eq!(asked.load(Ordering::SeqCst), 1);
        // The person stayed: the next close asks again.
        guard.asked.store(false, Ordering::Release);
        assert!(guard.hold());
        assert_eq!(asked.load(Ordering::SeqCst), 2);
        // The page chose to close: nothing holds it any longer.
        guard.asked.store(false, Ordering::Release);
        guard.releasing.store(true, Ordering::Release);
        assert!(!guard.hold());
    }

    #[test]
    fn a_page_that_cannot_be_reached_never_holds_the_window() {
        let guard = CloseGuard::default();
        *guard.listener.lock().unwrap() = Some(Channel::<()>::new(|_| {
            Err(tauri::Error::FailedToReceiveMessage)
        }));
        assert!(!guard.hold());
        // A failed ask leaves the next close free to ask again.
        assert!(!guard.asked.load(Ordering::Acquire));
    }

    #[test]
    fn window_actions_are_closed_and_cannot_address_another_window() {
        for name in [
            "minimize",
            "toggle_maximize",
            "close",
            "drag",
            "close_now",
            "keep_open",
        ] {
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
            perform_action(other.as_ref().window().clone(), Action::Close)
                .unwrap_err()
                .code,
            ErrorCode::InvalidArguments
        );
    }
}
