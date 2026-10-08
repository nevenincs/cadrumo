//! Held Darwin exit observation and kernel pidversion-bound signalling.
#![allow(unsafe_code)]

use super::records::{self, Incarnation, Observation, SignalDelivery};
use std::{
    cell::Cell,
    ffi::{CStr, OsString, c_int, c_void},
    io,
    os::{
        fd::{AsRawFd, FromRawFd, OwnedFd},
        unix::ffi::OsStringExt,
    },
    path::PathBuf,
    ptr,
};

type PidInfo = unsafe extern "C" fn(c_int, c_int, u64, *mut c_void, c_int) -> c_int;
type PidPath = unsafe extern "C" fn(*mut [u32; 8], *mut c_void, u32) -> c_int;
type Signal = unsafe extern "C" fn(*mut [u32; 8], c_int) -> c_int;

fn reset_errno() {
    // SAFETY: Darwin __error returns this thread's writable errno slot.
    unsafe {
        *libc::__error() = 0;
    }
}

fn native_failure() -> io::Error {
    let error = io::Error::last_os_error();
    if error.raw_os_error() == Some(0) {
        io::ErrorKind::InvalidData.into()
    } else {
        error
    }
}

struct Library(*mut c_void);
// SAFETY: dlopen returns a process-wide loader reference, not thread-local state.
// Library owns one reference and may move with its function pointers to another
// thread; Drop releases it exactly once after its owner stops using those pointers.
// This does not grant shared access (Sync); Process also retains its Cell !Sync.
unsafe impl Send for Library {}

impl Drop for Library {
    fn drop(&mut self) {
        // SAFETY: the uniquely owned handle came from dlopen.
        unsafe {
            libc::dlclose(self.0);
        }
    }
}

struct Native {
    _library: Library,
    info: PidInfo,
    path: PidPath,
    signal: Signal,
}

impl Native {
    fn open() -> io::Result<Self> {
        // SAFETY: fixed system-library path; the handle is retained with all symbols.
        let handle = unsafe {
            libc::dlopen(
                c"/usr/lib/libproc.dylib".as_ptr(),
                libc::RTLD_NOW | libc::RTLD_LOCAL,
            )
        };
        if handle.is_null() {
            return Err(io::ErrorKind::Unsupported.into());
        }
        let library = Library(handle);
        let symbol = |name: &CStr| -> io::Result<*mut c_void> {
            // SAFETY: terminated name and live library handle.
            let value = unsafe { libc::dlsym(handle, name.as_ptr()) };
            if value.is_null() {
                Err(io::ErrorKind::Unsupported.into())
            } else {
                Ok(value)
            }
        };
        // SAFETY: signatures match libproc.h; the library outlives its function pointers.
        unsafe {
            Ok(Self {
                info: std::mem::transmute::<*mut c_void, PidInfo>(symbol(c"proc_pidinfo")?),
                path: std::mem::transmute::<*mut c_void, PidPath>(symbol(
                    c"proc_pidpath_audittoken",
                )?),
                signal: std::mem::transmute::<*mut c_void, Signal>(symbol(
                    c"proc_signal_with_audittoken",
                )?),
                _library: library,
            })
        }
    }

    fn record<const N: usize>(&self, pid: u32, flavor: c_int) -> io::Result<[u8; N]> {
        if pid == 0 || pid > i32::MAX as u32 {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        let mut bytes = [0u8; N];
        reset_errno();
        // SAFETY: bounded PID, exact writable record buffer; libproc copies bytes out.
        let count = unsafe {
            (self.info)(
                pid as c_int,
                flavor,
                0,
                bytes.as_mut_ptr().cast(),
                N as c_int,
            )
        };
        if count <= 0 {
            return Err(native_failure());
        }
        if count as usize != N {
            return Err(io::ErrorKind::InvalidData.into());
        }
        Ok(bytes)
    }

    fn incarnation(&self, pid: u32) -> io::Result<Incarnation> {
        records::incarnation(
            &self.record::<{ records::UNIQUE_INFO_BYTES }>(pid, 17)?,
            pid,
        )
    }

    fn identity(&self, pid: u32, uid: u32) -> io::Result<Identity> {
        let incarnation = self.incarnation(pid)?;
        let observed = records::observation(
            &self.record::<{ records::BSD_INFO_BYTES }>(pid, 3)?,
            pid,
            uid,
        )?;
        let mut token = records::signal_token(incarnation, observed.uid, observed.gid)?;
        let mut bytes = [0u8; 4096];
        reset_errno();
        // SAFETY: complete audit token and bounded writable path; kernel verifies pidversion.
        let count =
            unsafe { (self.path)(&mut token, bytes.as_mut_ptr().cast(), bytes.len() as u32) };
        if count <= 0 {
            return Err(native_failure());
        }
        let count = count as usize;
        if count >= bytes.len() || bytes[count] != 0 || bytes[..count].contains(&0) {
            return Err(io::ErrorKind::InvalidData.into());
        }
        let image = PathBuf::from(OsString::from_vec(bytes[..count].to_vec()));
        if !image.is_absolute() || self.incarnation(pid)? != incarnation {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        let after = records::observation(
            &self.record::<{ records::BSD_INFO_BYTES }>(pid, 3)?,
            pid,
            uid,
        )?;
        if after != observed || self.incarnation(pid)? != incarnation {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok(Identity {
            incarnation,
            observed,
            image,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Identity {
    pub incarnation: Incarnation,
    pub observed: Observation,
    pub image: PathBuf,
}

/// The watch observes exit; only the audit-token API grants exact signal targeting.
pub struct Process {
    native: Native,
    queue: OwnedFd,
    identity: Identity,
    exited: Cell<bool>,
}

impl std::fmt::Debug for Process {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("Process")
            .field("identity", &self.identity)
            .field("exited", &self.exited.get())
            .finish_non_exhaustive()
    }
}

impl Process {
    pub fn open(pid: u32) -> io::Result<Self> {
        // SAFETY: geteuid has no arguments and cannot fail.
        let uid = unsafe { libc::geteuid() };
        if uid == 0 {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        let native = Native::open()?;
        let identity = native.identity(pid, uid)?;
        // SAFETY: kqueue creates a distinct descriptor without pointer arguments.
        let raw = unsafe { libc::kqueue() };
        if raw < 0 {
            return Err(io::Error::last_os_error());
        }
        // SAFETY: kqueue transferred this descriptor; every later failure closes it.
        let queue = unsafe { OwnedFd::from_raw_fd(raw) };
        // SAFETY: the held descriptor is live and must not survive exec.
        if unsafe { libc::fcntl(queue.as_raw_fd(), libc::F_SETFD, libc::FD_CLOEXEC) } < 0 {
            return Err(io::Error::last_os_error());
        }
        let process = Self {
            native,
            queue,
            identity,
            exited: Cell::new(false),
        };
        let change = libc::kevent {
            ident: pid as libc::uintptr_t,
            filter: libc::EVFILT_PROC,
            flags: libc::EV_ADD | libc::EV_ENABLE | libc::EV_CLEAR,
            fflags: libc::NOTE_EXIT,
            data: 0,
            udata: ptr::null_mut(),
        };
        process.observe(Some(&change))?;
        process.revalidate()?;
        Ok(process)
    }

    pub fn identity(&self) -> io::Result<&Identity> {
        self.revalidate()?;
        Ok(&self.identity)
    }

    pub fn exited(&self) -> io::Result<bool> {
        self.observe(None)
    }

    fn observe(&self, change: Option<&libc::kevent>) -> io::Result<bool> {
        if self.exited.get() {
            return Ok(true);
        }
        // SAFETY: kevent is a plain output record; zeroed fields are valid input storage.
        let mut event: libc::kevent = unsafe { std::mem::zeroed() };
        let timeout = libc::timespec {
            tv_sec: 0,
            tv_nsec: 0,
        };
        // SAFETY: all optional input/output records and the zero timeout outlive the call.
        let count = unsafe {
            libc::kevent(
                self.queue.as_raw_fd(),
                change.map_or(ptr::null(), ptr::from_ref),
                i32::from(change.is_some()),
                &mut event,
                1,
                &timeout,
            )
        };
        if count < 0 {
            return Err(io::Error::last_os_error());
        }
        if count == 0 {
            return Ok(false);
        }
        if count != 1
            || event.ident != self.identity.incarnation.pid as libc::uintptr_t
            || event.filter != libc::EVFILT_PROC
        {
            return Err(io::ErrorKind::InvalidData.into());
        }
        if event.flags & libc::EV_ERROR != 0 {
            let code = i32::try_from(event.data)
                .ok()
                .filter(|code| *code > 0)
                .ok_or(io::ErrorKind::InvalidData)?;
            return Err(io::Error::from_raw_os_error(code));
        }
        if event.fflags & libc::NOTE_EXIT == 0 {
            return Err(io::ErrorKind::InvalidData.into());
        }
        self.exited.set(true);
        Ok(true)
    }

    fn revalidate(&self) -> io::Result<()> {
        if self.exited()? {
            return Err(io::ErrorKind::NotFound.into());
        }
        if self
            .native
            .identity(self.identity.incarnation.pid, self.identity.observed.uid)?
            != self.identity
        {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        if self.exited()? {
            return Err(io::ErrorKind::NotFound.into());
        }
        Ok(())
    }

    pub fn signal(&self, signal: c_int) -> io::Result<SignalDelivery> {
        if !(1..32).contains(&signal) {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        if self.exited()? {
            return Ok(SignalDelivery::Gone);
        }
        self.revalidate()?;
        let mut token = records::signal_token(
            self.identity.incarnation,
            self.identity.observed.uid,
            self.identity.observed.gid,
        )?;
        reset_errno();
        // SAFETY: the kernel compares pidversion atomically with signal delivery; no PID fallback.
        let result = unsafe { (self.native.signal)(&mut token, signal) };
        records::signal_delivery(if result == -1 {
            native_failure()
                .raw_os_error()
                .ok_or(io::ErrorKind::Other)?
        } else {
            result
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        os::unix::process::ExitStatusExt,
        process::{Child, Command, Stdio},
    };

    struct InputChild(Child);
    impl Drop for InputChild {
        fn drop(&mut self) {
            drop(self.0.stdin.take());
            self.0.wait().unwrap();
        }
    }

    #[test]
    fn native_signal_capability_targets_only_its_owned_test_child() {
        for signal in [libc::SIGTERM, libc::SIGKILL] {
            let mut child = InputChild(
                Command::new("/bin/cat")
                    .stdin(Stdio::piped())
                    .stdout(Stdio::null())
                    .spawn()
                    .unwrap(),
            );
            let held = Process::open(child.0.id()).unwrap();
            assert_eq!(held.signal(signal).unwrap(), SignalDelivery::Delivered);
            assert_eq!(child.0.wait().unwrap().signal(), Some(signal));
            assert!(held.exited().unwrap());
            assert_eq!(held.signal(signal).unwrap(), SignalDelivery::Gone);
        }
    }

    #[test]
    fn process_custody_can_move_to_the_supervisor_thread() {
        let held = Process::open(std::process::id()).unwrap();
        std::thread::spawn(move || {
            assert_eq!(held.identity().unwrap().incarnation.pid, std::process::id());
            assert!(!held.exited().unwrap());
        })
        .join()
        .unwrap();
    }
}
