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
pub mod installed;
pub mod session;
pub mod startup;
pub mod supervision;
#[cfg(windows)]
pub mod windows_lifecycle;
