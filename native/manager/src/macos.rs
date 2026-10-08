//! Darwin process capabilities; login and signed agent registration remain separate.

pub mod activity;
pub mod lifecycle;
pub mod login;
pub mod naming;
#[cfg(target_os = "macos")]
pub mod process;
pub mod records;

#[cfg(target_os = "macos")]
pub mod ipc;
