//! Darwin process capabilities; login and signed agent registration remain separate.

#[cfg(target_os = "macos")]
pub mod process;
pub mod records;
