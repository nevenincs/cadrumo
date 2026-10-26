//! Start a role of the Cadrumo binary before any console attachment, window or webview.
//!
//! The desktop and the command line keep every other first argument; only the reserved role
//! argument is claimed here, and an undeclared role is refused without starting anything.
//! The interpreter roles run inside the linked interpreter host; the `components` role runs
//! the native component engine and hosts no interpreter.

use cadrumo_application::{
    error::application::{ApplicationError, ErrorCode, Operation},
    role::{self, Role},
};
use std::ffi::OsString;

/// The exit code of the role the process arguments select, or `None` when they select none.
pub fn dispatch() -> Option<i32> {
    let arguments: Vec<OsString> = std::env::args_os().skip(1).collect();
    if let Some(code) = crate::auth_browser::dispatch(&arguments) {
        return Some(code);
    }
    Some(match role::select(&arguments)? {
        Ok((Role::Components, forwarded)) => components(forwarded),
        Ok((role, forwarded)) => run(role, forwarded),
        Err(_) => refuse(ErrorCode::InvalidArguments),
    })
}

/// The component engine's role. It first contains what it will start: on Windows it
/// places itself in a kill-on-close job, on Linux and macOS it keeps a process scope that
/// every browser check and query it starts is created into. Either way nothing it starts
/// outlives it, however the role ends.
fn components(forwarded: &[OsString]) -> i32 {
    #[cfg(windows)]
    {
        if super::contain_application().is_err() {
            return refuse(ErrorCode::SpawnFailed);
        }
    }
    #[cfg(unix)]
    {
        if cadrumo_platform::process_scope::contain_current().is_err() {
            return refuse(ErrorCode::SpawnFailed);
        }
    }
    cadrumo_application::provisioning::role_host::run(forwarded)
}

#[cfg(windows)]
fn run(role: Role, forwarded: &[OsString]) -> i32 {
    let Some(hosted) = role.hosted() else {
        return refuse(ErrorCode::InvalidArguments);
    };
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
