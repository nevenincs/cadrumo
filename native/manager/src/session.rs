//! Session ownership: one manager per logon session and one starter per user.
//!
//! A per-session lock admits one manager in each logon session of the user. Several
//! sessions share one runtime per storage root, so a per-user start claim under the
//! storage root's `.runtime/` decides which manager starts it, and a Quit marker beside the
//! claim keeps every manager from starting it after the user quit. The manager that
//! launched the runtime owns it; managers in other sessions only observe it.

pub mod claim;
pub mod instance;
pub mod ownership;
pub mod quit;

#[cfg(target_os = "linux")]
mod linux;
#[cfg(windows)]
mod windows;

use std::io;

/// The signed-in user and logon session a manager runs in.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ManagerSession {
    /// The user's security identifier on Windows, the effective uid on POSIX.
    pub user: String,
    /// The Terminal Services session number on Windows, the login session on Linux.
    pub session: String,
}

impl ManagerSession {
    /// The user and session of this process.
    #[cfg(windows)]
    pub fn current() -> io::Result<Self> {
        let session = crate::supervision::process::current_session()
            .ok_or_else(|| io::Error::other("the session of this process cannot be read"))?;
        Ok(Self {
            user: windows::User::current()?.sid,
            session: session.to_string(),
        })
    }

    /// The user and session of this process.
    #[cfg(target_os = "linux")]
    pub fn current() -> io::Result<Self> {
        Ok(Self {
            user: crate::custody::effective_uid().to_string(),
            session: crate::supervision::process::current_session()
                .ok_or(io::ErrorKind::PermissionDenied)?,
        })
    }

    /// The user and session of this process.
    #[cfg(not(any(windows, target_os = "linux")))]
    pub fn current() -> io::Result<Self> {
        Err(io::ErrorKind::Unsupported.into())
    }
}
