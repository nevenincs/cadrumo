//! Supervision core: launch, readiness, heartbeat, restart classes, adoption and stop.
//!
//! The core runs without a window or tray. Collaborators that later Steps provide, such as
//! the session-activity check and the installed-version catalogue, are injected traits.

pub mod adoption;
pub mod boot_record;
pub mod environment;
pub mod exit;
mod json;
pub mod launch;
pub mod process;
pub mod protocol;
pub mod restart;
pub mod stop;
pub mod supervisor;
#[cfg(windows)]
mod windows;
