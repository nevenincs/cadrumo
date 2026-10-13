//! Per-user runtime manager for the installed Cadrumo runtime.
//!
//! The manager image holds no profile, session, credential or tax-data authority.

#[cfg(all(feature = "fixture-test-mode", not(debug_assertions)))]
compile_error!("release builds refuse the fixture test mode");

#[cfg(windows)]
pub mod activation_probe;
#[cfg(any(windows, test))]
pub mod background;
pub mod contract;
pub mod custody;
pub mod diagnostics;
#[cfg(windows)]
pub mod desktop_host;
pub mod identity;
#[cfg(windows)]
pub mod installation;
pub mod installed;
pub mod invocation;
pub mod ipc;
pub mod lifecycle;
pub mod preferences;
pub mod session;
#[cfg(windows)]
pub mod service_windows;
#[cfg(windows)]
pub mod process_job;
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

pub mod successor;

#[cfg(windows)]
pub mod cutover_coordinator;
