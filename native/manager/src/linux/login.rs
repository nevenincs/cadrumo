//! Native logind identity; environment session names never grant admission.
#![allow(unsafe_code)]

use super::process::Process;
use std::{
    ffi::{CStr, CString, c_char, c_int, c_void},
    io,
    os::fd::AsRawFd,
};

type PidSession = unsafe extern "C" fn(c_int, *mut *mut c_char) -> c_int;
type PidOwner = unsafe extern "C" fn(c_int, *mut u32) -> c_int;
type SessionText = unsafe extern "C" fn(*const c_char, *mut *mut c_char) -> c_int;
type SessionFlag = unsafe extern "C" fn(*const c_char) -> c_int;

struct Library(*mut c_void);
impl Drop for Library {
    fn drop(&mut self) {
        // SAFETY: this handle came from dlopen and remains uniquely owned.
        unsafe {
            libc::dlclose(self.0);
        }
    }
}

pub struct Login {
    _library: Library,
    pid_session: PidSession,
    pid_owner: PidOwner,
    session_type: SessionText,
    session_class: SessionText,
    session_state: SessionText,
    session_active: SessionFlag,
    session_remote: SessionFlag,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Session {
    pub id: String,
    pub uid: u32,
    pub active: bool,
    pub closing: bool,
}

impl Login {
    pub fn open() -> io::Result<Self> {
        // SAFETY: constant C string; RTLD_NOW resolves all required dependencies now.
        let handle = unsafe {
            libc::dlopen(
                c"libsystemd.so.0".as_ptr(),
                libc::RTLD_NOW | libc::RTLD_LOCAL,
            )
        };
        if handle.is_null() {
            return Err(io::ErrorKind::Unsupported.into());
        }
        let library = Library(handle);
        let symbol = |name: &CStr| -> io::Result<*mut c_void> {
            // SAFETY: the loaded library remains live and name is terminated.
            let value = unsafe { libc::dlsym(handle, name.as_ptr()) };
            if value.is_null() {
                Err(io::ErrorKind::Unsupported.into())
            } else {
                Ok(value)
            }
        };
        // SAFETY: each symbol has the exact signature documented by sd-login.h;
        // _library keeps the code mapped until all function pointers are discarded.
        unsafe {
            Ok(Self {
                pid_session: std::mem::transmute::<*mut c_void, PidSession>(symbol(
                    c"sd_pidfd_get_session",
                )?),
                pid_owner: std::mem::transmute::<*mut c_void, PidOwner>(symbol(
                    c"sd_pidfd_get_owner_uid",
                )?),
                session_type: std::mem::transmute::<*mut c_void, SessionText>(symbol(
                    c"sd_session_get_type",
                )?),
                session_class: std::mem::transmute::<*mut c_void, SessionText>(symbol(
                    c"sd_session_get_class",
                )?),
                session_state: std::mem::transmute::<*mut c_void, SessionText>(symbol(
                    c"sd_session_get_state",
                )?),
                session_active: std::mem::transmute::<*mut c_void, SessionFlag>(symbol(
                    c"sd_session_is_active",
                )?),
                session_remote: std::mem::transmute::<*mut c_void, SessionFlag>(symbol(
                    c"sd_session_is_remote",
                )?),
                _library: library,
            })
        }
    }

    pub fn session(&self, process: &Process) -> io::Result<Session> {
        process.require_alive()?;
        let identity = process.identity()?;
        if identity.privileged || identity.uid != crate::custody::effective_uid() {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        let (id, uid) = self.binding(process)?;
        let session = CString::new(id.as_str()).map_err(|_| io::ErrorKind::InvalidData)?;
        let kind = text(|out| {
            // SAFETY: session and writable out pointers remain valid for this call.
            unsafe { (self.session_type)(session.as_ptr(), out) }
        })?;
        let class = text(|out| {
            // SAFETY: session and writable out pointers remain valid for this call.
            unsafe { (self.session_class)(session.as_ptr(), out) }
        })?;
        let state = text(|out| {
            // SAFETY: session and writable out pointers remain valid for this call.
            unsafe { (self.session_state)(session.as_ptr(), out) }
        })?;
        // SAFETY: session is a valid terminated string retained across these calls.
        let remote = unsafe { (self.session_remote)(session.as_ptr()) };
        // SAFETY: same retained session string.
        let active = unsafe { (self.session_active)(session.as_ptr()) };
        if !matches!(kind.as_str(), "x11" | "wayland")
            || class != "user"
            || remote != 0
            || active < 0
            || !matches!(state.as_str(), "active" | "online" | "closing")
            || uid != identity.uid
        {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        if self.binding(process)? != (id.clone(), uid) {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        process.require_alive()?;
        Ok(Session {
            id,
            uid,
            active: active > 0 && state == "active",
            closing: state == "closing",
        })
    }

    fn binding(&self, process: &Process) -> io::Result<(String, u32)> {
        let id = text(|out| {
            // SAFETY: pidfd stays owned; out is writable for the library allocation.
            unsafe { (self.pid_session)(process.descriptor().as_raw_fd(), out) }
        })?;
        if id.is_empty()
            || id.len() > 64
            || !id
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || b"_-".contains(&byte))
        {
            return Err(io::ErrorKind::InvalidData.into());
        }
        let mut uid = u32::MAX;
        // SAFETY: pidfd remains owned and uid is a writable u32.
        check(unsafe { (self.pid_owner)(process.descriptor().as_raw_fd(), &mut uid) })?;
        if uid == u32::MAX {
            return Err(io::ErrorKind::InvalidData.into());
        }
        Ok((id, uid))
    }
}

fn check(result: c_int) -> io::Result<()> {
    if result < 0 {
        Err(io::Error::from_raw_os_error(-result))
    } else {
        Ok(())
    }
}

fn text(call: impl FnOnce(*mut *mut c_char) -> c_int) -> io::Result<String> {
    let mut output = std::ptr::null_mut();
    let result = call(&mut output);
    if output.is_null() {
        check(result)?;
        return Err(io::ErrorKind::InvalidData.into());
    }
    // SAFETY: sd-login allocates a terminated string with malloc on successful output.
    let value = unsafe { CStr::from_ptr(output) }
        .to_str()
        .map(str::to_owned)
        .map_err(|_| io::ErrorKind::InvalidData);
    // SAFETY: sd-login's allocated result is released once with libc free.
    unsafe {
        libc::free(output.cast());
    }
    check(result)?;
    value.map_err(Into::into)
}
