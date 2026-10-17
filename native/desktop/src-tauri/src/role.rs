//! Start a role of the Cadrumo binary before any console attachment, window or webview.
//!
//! The desktop and the command line keep every other first argument; only the reserved role
//! argument is claimed here, and an undeclared role is refused without starting anything.

use cadrumo_application::{
    error::application::{ApplicationError, ErrorCode, Operation},
    role::{self, Role},
};
use std::ffi::OsString;

/// The exit code of the role the process arguments select, or `None` when they select none.
pub fn dispatch() -> Option<i32> {
    let arguments: Vec<OsString> = std::env::args_os().skip(1).collect();
    Some(match role::select(&arguments)? {
        Ok((role, forwarded)) => run(role, forwarded),
        Err(_) => refuse(ErrorCode::InvalidArguments),
    })
}

#[cfg(windows)]
fn run(role: Role, forwarded: &[OsString]) -> i32 {
    let hosted = role.hosted();
    let Ok(executable) = std::env::current_exe() else {
        return refuse(ErrorCode::EnvironmentFailed);
    };
    cadrumo_interpreter_host::run_entrypoint(
        hosted.image,
        hosted.entrypoint,
        executable.as_os_str(),
        forwarded,
    )
    .unwrap_or_else(|| refuse(ErrorCode::InvalidArguments))
}

#[cfg(not(windows))]
fn run(_: Role, _: &[OsString]) -> i32 {
    refuse(ErrorCode::UnsupportedPlatform)
}

fn refuse(code: ErrorCode) -> i32 {
    let error = ApplicationError::new(code, Operation::Launch);
    eprintln!(
        "{}",
        serde_json::to_string(&error).unwrap_or_else(|_| "application_error".into())
    );
    match code {
        ErrorCode::InvalidArguments => 64,
        _ => 1,
    }
}
