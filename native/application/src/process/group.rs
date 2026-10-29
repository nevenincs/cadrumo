//! The process group a child is created in on Linux and macOS.
//!
//! An owner that keeps a process scope for its children, as the desktop does,
//! has each child created into it, so the child and what it starts end with the owner
//! however the owner ends. Any other owner gives the child a group of its own, apart from
//! the terminal's job control.

use std::{io, os::unix::process::CommandExt, process::Command};

/// Creates `command`'s process in the owner's process scope when it keeps one, else in a
/// group of its own. Refused when the owner's scope no longer contains anything.
pub fn place(command: &mut Command) -> io::Result<()> {
    #[cfg(feature = "platform")]
    if let Some(scope) = cadrumo_platform::process_scope::current() {
        return scope.join(command);
    }
    command.process_group(0);
    Ok(())
}
