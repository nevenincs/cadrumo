use crate::{app::Commands, environment::Launch};
use tauri::{Runtime, plugin::TauriPlugin};

pub fn plugin<R: Runtime>(_launch: &Launch) -> TauriPlugin<R> {
    tauri::plugin::Builder::new("cadrumo-logs").build()
}

pub fn commands<R: Runtime>() -> Commands<R> {
    crate::app::commands![]
}
