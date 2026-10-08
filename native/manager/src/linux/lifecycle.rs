//! Linux session observations and process termination notification.
#![allow(unsafe_code)]

use super::{login::Login, process::Process};
use crate::supervision::supervisor::SessionActivity;
use std::{
    io,
    sync::atomic::{AtomicBool, Ordering},
};

static ENDING: AtomicBool = AtomicBool::new(false);
static INSTALLED: AtomicBool = AtomicBool::new(false);

extern "C" fn ending(_signal: libc::c_int) {
    // A signal handler performs only a lock-free atomic store, never I/O or locking.
    ENDING.store(true, Ordering::SeqCst);
}

pub struct Termination {
    term: libc::sigaction,
    interrupt: libc::sigaction,
}

impl Termination {
    pub fn install() -> io::Result<Self> {
        if INSTALLED.swap(true, Ordering::SeqCst) {
            return Err(io::ErrorKind::AlreadyExists.into());
        }
        // SAFETY: zeroed sigaction is initialized below before registering it.
        let mut action: libc::sigaction = unsafe { std::mem::zeroed() };
        action.sa_sigaction = ending as *const () as usize;
        // SAFETY: sa_mask points to an initialized writable sigset_t.
        unsafe {
            libc::sigemptyset(&mut action.sa_mask);
        }
        // SAFETY: old handlers are writable sigaction storage.
        let mut term: libc::sigaction = unsafe { std::mem::zeroed() };
        // SAFETY: same initialized writable storage requirement.
        let mut interrupt: libc::sigaction = unsafe { std::mem::zeroed() };
        ENDING.store(false, Ordering::SeqCst);
        // SAFETY: handler is a process-lifetime function with C ABI.
        if unsafe { libc::sigaction(libc::SIGTERM, &action, &mut term) } != 0 {
            INSTALLED.store(false, Ordering::SeqCst);
            return Err(io::Error::last_os_error());
        }
        // SAFETY: same process-lifetime handler; previous handler retained for restoration.
        if unsafe { libc::sigaction(libc::SIGINT, &action, &mut interrupt) } != 0 {
            let error = io::Error::last_os_error();
            // SAFETY: term was filled by successful sigaction immediately above.
            unsafe {
                libc::sigaction(libc::SIGTERM, &term, std::ptr::null_mut());
            }
            INSTALLED.store(false, Ordering::SeqCst);
            return Err(error);
        }
        Ok(Self { term, interrupt })
    }

    pub fn requested(&self) -> bool {
        ENDING.load(Ordering::SeqCst)
    }
}

impl Drop for Termination {
    fn drop(&mut self) {
        // SAFETY: these handlers were saved by this unique registration owner.
        unsafe {
            libc::sigaction(libc::SIGTERM, &self.term, std::ptr::null_mut());
            libc::sigaction(libc::SIGINT, &self.interrupt, std::ptr::null_mut());
        }
        INSTALLED.store(false, Ordering::SeqCst);
    }
}

pub struct Activity;
impl SessionActivity for Activity {
    fn is_active(&self) -> bool {
        if ENDING.load(Ordering::SeqCst) {
            return false;
        }
        let observed =
            Process::open(std::process::id()).and_then(|process| Login::open()?.session(&process));
        observed.is_ok_and(|session| session.active && !session.closing)
    }
}

/// Admission reports absence/refusal; no environment-only session fallback exists.
pub fn require_current() -> io::Result<super::login::Session> {
    let process = Process::open(std::process::id())?;
    let session = Login::open()?.session(&process)?;
    if session.closing {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    Ok(session)
}

/// A bounded query to the real system bus. Ignore environment bus addresses and
/// bind the property read to the root-owned logind unique bus owner.
pub fn shutdown_requested() -> io::Result<bool> {
    use std::{os::fd::AsRawFd, os::unix::net::UnixStream, time::Duration};
    use zbus::blocking::{Proxy, connection::Builder};
    let stream = UnixStream::connect("/run/dbus/system_bus_socket")?;
    // SAFETY: credential storage is writable for exactly the requested byte count.
    let mut credentials: libc::ucred = unsafe { std::mem::zeroed() };
    let mut size = std::mem::size_of::<libc::ucred>() as libc::socklen_t;
    // SAFETY: stream owns a live Unix socket, pointers describe initialized storage.
    if unsafe {
        libc::getsockopt(
            stream.as_raw_fd(),
            libc::SOL_SOCKET,
            libc::SO_PEERCRED,
            (&mut credentials as *mut libc::ucred).cast(),
            &mut size,
        )
    } != 0
    {
        return Err(io::Error::last_os_error());
    }
    if size as usize != std::mem::size_of::<libc::ucred>() || credentials.uid != 0 {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    stream.set_read_timeout(Some(Duration::from_secs(1)))?;
    stream.set_write_timeout(Some(Duration::from_secs(1)))?;
    let connection = Builder::async_io_unix_stream(stream)
        .method_timeout(Duration::from_secs(1))
        .max_queued(16)
        .build()
        .map_err(io::Error::other)?;
    let bus = Proxy::new(
        &connection,
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
    )
    .map_err(io::Error::other)?;
    let owner: String = bus
        .call("GetNameOwner", &("org.freedesktop.login1",))
        .map_err(io::Error::other)?;
    let uid: u32 = bus
        .call("GetConnectionUnixUser", &(&owner,))
        .map_err(io::Error::other)?;
    if uid != 0 {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    let login = Proxy::new(
        &connection,
        owner.as_str(),
        "/org/freedesktop/login1",
        "org.freedesktop.login1.Manager",
    )
    .map_err(io::Error::other)?;
    let preparing: bool = login
        .get_property("PreparingForShutdown")
        .map_err(io::Error::other)?;
    let after: String = bus
        .call("GetNameOwner", &("org.freedesktop.login1",))
        .map_err(io::Error::other)?;
    if after != owner {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    Ok(preparing)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn termination_is_unique_suppresses_activity_and_restores_handlers() {
        let guard = Termination::install().unwrap();
        assert!(Termination::install().is_err());
        assert!(!guard.requested());
        // Exercise the actual installed signal disposition on this test process.
        // SAFETY: our installed SIGTERM handler only updates the atomic flag.
        assert_eq!(unsafe { libc::raise(libc::SIGTERM) }, 0);
        assert!(guard.requested());
        assert!(!Activity.is_active());
        drop(guard);
        let fresh = Termination::install().unwrap();
        assert!(!fresh.requested());
    }
}
