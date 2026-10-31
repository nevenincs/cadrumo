//! Start a role of the Cadrumo binary before any console attachment, window or webview.
//!
//! The desktop and the command line keep every other first argument; only the reserved role
//! argument is claimed here, and an undeclared role is refused without starting anything.
//! Every role runs inside the linked interpreter host.

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
        Ok((role, forwarded)) => run(role, forwarded),
        Err(_) => refuse(ErrorCode::InvalidArguments),
    })
}

#[cfg(any(windows, unix))]
fn run(role: Role, forwarded: &[OsString]) -> i32 {
    let hosted = role.hosted();
    let Ok(executable) = std::env::current_exe() else {
        return refuse_launch(ErrorCode::EnvironmentFailed);
    };
    cadrumo_interpreter_host::run_entrypoint(
        hosted.image,
        hosted.entrypoint,
        executable.as_os_str(),
        forwarded,
    )
    .unwrap_or_else(|| refuse_launch(ErrorCode::InvalidArguments))
}

#[cfg(not(any(windows, unix)))]
fn run(_: Role, _: &[OsString]) -> i32 {
    refuse_launch(ErrorCode::UnsupportedPlatform)
}

/// Refuses a role the host cannot start at all, with the declared launch refusal a
/// supervisor reads as final: the same image would refuse again, so it is not retried.
fn refuse_launch(code: ErrorCode) -> i32 {
    report(code);
    LAUNCH_REFUSED_EXIT
}

const LAUNCH_REFUSED_EXIT: i32 = cadrumo_platform::LAUNCH_PROFILE_REFUSED_EXIT as i32;

fn report(code: ErrorCode) {
    let error = ApplicationError::new(code, Operation::Launch);
    eprintln!(
        "{}",
        serde_json::to_string(&error).unwrap_or_else(|_| "application_error".into())
    );
}

fn refuse(code: ErrorCode) -> i32 {
    report(code);
    64
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_role_the_host_cannot_start_exits_with_the_declared_terminal_refusal() {
        for code in [
            ErrorCode::UnsupportedPlatform,
            ErrorCode::EnvironmentFailed,
            ErrorCode::InvalidArguments,
        ] {
            assert_eq!(refuse_launch(code), 125, "{code:?}");
        }
        // A malformed role argument is a usage error for the person at the command line.
        assert_eq!(refuse(ErrorCode::InvalidArguments), 64);
    }
}
