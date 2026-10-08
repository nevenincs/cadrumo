//! Per-user runtime manager for the installed Cadrumo runtime.
//!
//! The manager image holds no profile, session, credential or tax-data authority.

#[cfg(all(feature = "fixture-test-mode", not(debug_assertions)))]
compile_error!("release builds refuse the fixture test mode");

#[cfg(any(windows, test))]
pub mod admission;
#[cfg(windows)]
pub mod background;
pub mod contract;
pub mod custody;
pub mod diagnostics;
pub mod identity;
#[cfg(windows)]
pub mod installation;
pub mod installed;
pub mod ipc;
pub mod preferences;
pub mod session;
pub mod startup;
pub mod strings;
pub mod supervision;
#[cfg(windows)]
pub mod windows_lifecycle;
#[cfg(windows)]
pub mod windows_tray;

#[cfg(target_os = "linux")]
pub mod linux;

#[cfg(any(target_os = "macos", test))]
pub mod macos;

pub mod cutover;
#[cfg(windows)]
pub mod cutover_parent;
#[cfg(windows)]
pub mod cutover_windows;
pub mod failed_versions;
#[cfg(windows)]
pub mod installation_watch;

#[cfg(windows)]
pub mod cutover_child;

#[cfg(windows)]
pub mod cutover_coordinator;
