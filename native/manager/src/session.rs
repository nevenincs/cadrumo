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
    /// The Terminal Services session number on Windows, native login session on POSIX.
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
    #[cfg(target_os = "macos")]
    pub fn current() -> io::Result<Self> {
        // Keep the current incarnation held through kernel audit-token and graphical
        // session corroboration. Environment values are not login authority.
        let process = crate::macos::process::Process::open(std::process::id())?;
        let session = crate::macos::login::Login::open()?.current(&process)?;
        Ok(Self {
            user: session.uid().to_string(),
            session: session.id().to_string(),
        })
    }

    /// The user and session of this process.
    #[cfg(not(any(windows, target_os = "linux", target_os = "macos")))]
    pub fn current() -> io::Result<Self> {
        Err(io::ErrorKind::Unsupported.into())
    }
}

#[cfg(all(test, target_os = "macos"))]
mod macos_tests {
    use super::*;

    #[test]
    fn shared_session_preserves_native_admission_and_coordinates() {
        let process = crate::macos::process::Process::open(std::process::id()).unwrap();
        match crate::macos::login::Login::open()
            .unwrap()
            .current(&process)
        {
            Ok(native) => {
                let shared = ManagerSession::current().unwrap();
                assert_eq!(shared.user, native.uid().to_string());
                assert_eq!(shared.session, native.id().to_string());
                assert_eq!(
                    crate::supervision::process::current_session(),
                    Some(shared.session)
                );
            }
            Err(error) => {
                assert_eq!(ManagerSession::current().unwrap_err().kind(), error.kind());
                assert!(crate::supervision::process::current_session().is_none());
            }
        }
    }
}
