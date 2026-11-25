//! Reads the agent service's console environment for the signed-in profile and
//! tells the window when its revision changes.
//!
//! The window learns the revision only; the console reads the environment
//! itself each time it starts. A read the service refuses, or cannot answer,
//! is the base environment, so a console never keeps a previous profile's values.
use super::AgentHost;
use crate::terminal::console_environment::{ConsoleEnvironment, EVENT};
use std::sync::Arc;
use tauri::{AppHandle, Emitter, Runtime};

impl AgentHost {
    /// The console environment of the profile signed in now, or the base.
    pub(crate) fn console_environment(&self) -> ConsoleEnvironment {
        self.administer(serde_json::json!({"action":"console_environment"}), None)
            .ok()
            .and_then(|answer| ConsoleEnvironment::parse(&answer))
            .unwrap_or_else(ConsoleEnvironment::base)
    }
}

/// Re-reads at every sign-in observation, which a sign-in, a sign-out and a
/// profile change each make, and each time the agent becomes ready for a
/// profile, and emits [`EVENT`] whenever the revision differs from the last read.
pub(super) fn watch<R: Runtime>(app: AppHandle<R>, host: &Arc<AgentHost>) {
    let ready = Arc::new(tokio::sync::Notify::new());
    let woken = ready.clone();
    host.supervisor
        .on_ready(Arc::new(move || woken.notify_one()));
    let host = Arc::downgrade(host);
    drop(tauri::async_runtime::spawn(async move {
        let mut last: Option<String> = None;
        loop {
            let Some(reader) = host.upgrade() else {
                return;
            };
            // Both wakes are registered before the read, so none arriving meanwhile is lost.
            let observed = reader.sign_in.observation_changed();
            let agent_ready = ready.notified();
            tokio::pin!(agent_ready);
            agent_ready.as_mut().enable();
            let changed = tauri::async_runtime::spawn_blocking(move || {
                reader.console_environment().changed()
            })
            .await
            .unwrap_or_else(|_| ConsoleEnvironment::base().changed());
            if last.as_deref() != Some(changed.revision.as_str()) {
                if last.is_some() {
                    // The window may not be listening; the next change emits again.
                    let _ = app.emit(EVENT, &changed);
                }
                last = Some(changed.revision);
            }
            tokio::select! {
                () = observed => {},
                () = &mut agent_ready => {},
            }
        }
    }));
}
