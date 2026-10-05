//! Per-user runtime manager for the installed Cadrumo runtime.
//!
//! The manager image holds no profile, session, credential or tax-data authority.

#[cfg(all(feature = "fixture-test-mode", not(debug_assertions)))]
compile_error!("release builds refuse the fixture test mode");

pub mod contract;
pub mod identity;
pub mod supervision;
