//! Windows calls behind the supervision core: process inspection and console Ctrl+C.
//!
//! Every handle this module opens is wrapped in an [`OwnedHandle`] at once, so it is closed
//! exactly once. The console attachment is process-wide state, serialized by one lock that
//! the launcher shares, so no process is ever started while this process is attached to a
//! runtime's console.
#![allow(unsafe_code)]

use std::ffi::{OsString, c_void};
use std::io;
use std::os::windows::ffi::OsStringExt;
use std::os::windows::io::{AsRawHandle, FromRawHandle, OwnedHandle, RawHandle};
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Mutex, MutexGuard, PoisonError};
use std::thread;
use std::time::{Duration, Instant};

type Handle = *mut c_void;

#[repr(C)]
#[derive(Default)]
struct FileTime {
    low: u32,
    high: u32,
}

const PROCESS_TERMINATE: u32 = 0x0001;
const PROCESS_QUERY_LIMITED_INFORMATION: u32 = 0x1000;
const SYNCHRONIZE: u32 = 0x0010_0000;
const TOKEN_QUERY: u32 = 0x0008;
const TOKEN_ELEVATION_TYPE_CLASS: u32 = 18;
const TOKEN_ELEVATION_TYPE_FULL: u32 = 2;
const WAIT_OBJECT_0: u32 = 0;
const WAIT_TIMEOUT: u32 = 0x102;
const CTRL_C_EVENT: u32 = 0;
const CTRL_BREAK_EVENT: u32 = 1;
const ERROR_ACCESS_DENIED: i32 = 5;
const ERROR_INVALID_HANDLE: i32 = 6;
const ERROR_INVALID_PARAMETER: i32 = 87;
const IMAGE_PATH_CAPACITY: u32 = 32_768;
/// The code a forced termination reports; Python owns `1` for forced job termination.
const TERMINATED_EXIT_CODE: u32 = 1;

#[link(name = "kernel32")]
unsafe extern "system" {
    fn OpenProcess(access: u32, inherit: i32, pid: u32) -> Handle;
    fn GetProcessTimes(
        process: Handle,
        creation: *mut FileTime,
        exit: *mut FileTime,
        kernel: *mut FileTime,
        user: *mut FileTime,
    ) -> i32;
    fn QueryFullProcessImageNameW(
        process: Handle,
        flags: u32,
        name: *mut u16,
        size: *mut u32,
    ) -> i32;
    fn ProcessIdToSessionId(pid: u32, session: *mut u32) -> i32;
    fn GetCurrentProcessId() -> u32;
    fn WaitForSingleObject(handle: Handle, milliseconds: u32) -> u32;
    fn GetExitCodeProcess(process: Handle, code: *mut u32) -> i32;
    fn TerminateProcess(process: Handle, code: u32) -> i32;
    fn AttachConsole(pid: u32) -> i32;
    fn FreeConsole() -> i32;
    fn GenerateConsoleCtrlEvent(event: u32, group: u32) -> i32;
    fn SetConsoleCtrlHandler(
        handler: Option<unsafe extern "system" fn(u32) -> i32>,
        add: i32,
    ) -> i32;
}

#[link(name = "advapi32")]
unsafe extern "system" {
    fn OpenProcessToken(process: Handle, access: u32, token: *mut Handle) -> i32;
    fn GetTokenInformation(
        token: Handle,
        class: u32,
        information: *mut c_void,
        length: u32,
        returned: *mut u32,
    ) -> i32;
}

/// Take ownership of a handle a successful open returned; null means the open failed.
fn owned(handle: Handle) -> io::Result<OwnedHandle> {
    if handle.is_null() {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: `handle` was just returned open by the system to this process, is not null,
    // and nothing else holds or closes it, so the OwnedHandle becomes its only owner.
    Ok(unsafe { OwnedHandle::from_raw_handle(handle as RawHandle) })
}

fn raw(handle: &OwnedHandle) -> Handle {
    handle.as_raw_handle().cast()
}

/// A process opened by pid, held for as long as the value lives so the pid stays its own.
#[derive(Debug)]
pub(crate) struct HeldProcess {
    handle: OwnedHandle,
    pub(crate) can_terminate: bool,
}

pub(crate) fn open_process(pid: u32) -> io::Result<HeldProcess> {
    let base = PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE;
    // SAFETY: OpenProcess takes plain integers and returns a new handle or null.
    let with_terminate = unsafe { OpenProcess(base | PROCESS_TERMINATE, 0, pid) };
    if let Ok(handle) = owned(with_terminate) {
        return Ok(HeldProcess {
            handle,
            can_terminate: true,
        });
    }
    // SAFETY: as above; a runtime of a more privileged token still grants limited query.
    let handle = owned(unsafe { OpenProcess(base, 0, pid) })?;
    Ok(HeldProcess {
        handle,
        can_terminate: false,
    })
}

impl HeldProcess {
    /// The process creation time as FILETIME ticks, the boot record's stamp.
    pub(crate) fn creation_time(&self) -> io::Result<u64> {
        let (mut created, mut exited, mut kernel, mut user) = Default::default();
        // SAFETY: the handle is open with limited query access for this value's lifetime,
        // and the four out-pointers name distinct locals that outlive the call.
        let succeeded = unsafe {
            GetProcessTimes(
                raw(&self.handle),
                &mut created,
                &mut exited,
                &mut kernel,
                &mut user,
            )
        };
        if succeeded == 0 {
            return Err(io::Error::last_os_error());
        }
        let FileTime { low, high } = created;
        Ok((u64::from(high) << 32) | u64::from(low))
    }

    /// The full Win32 path of the process image.
    pub(crate) fn image(&self) -> io::Result<PathBuf> {
        let mut buffer = vec![0_u16; IMAGE_PATH_CAPACITY as usize];
        let mut length = IMAGE_PATH_CAPACITY;
        // SAFETY: `buffer` holds `length` UTF-16 units and outlives the call; the system
        // writes at most that many and stores the written length, excluding the terminator.
        let succeeded = unsafe {
            QueryFullProcessImageNameW(raw(&self.handle), 0, buffer.as_mut_ptr(), &mut length)
        };
        if succeeded == 0 {
            return Err(io::Error::last_os_error());
        }
        buffer.truncate(length as usize);
        Ok(PathBuf::from(OsString::from_wide(&buffer)))
    }

    /// Whether the process token is a full UAC-elevated token.
    pub(crate) fn fully_elevated(&self) -> io::Result<bool> {
        let mut token: Handle = std::ptr::null_mut();
        // SAFETY: the process handle is open with limited query access, which suffices for
        // TOKEN_QUERY on a same-user process; the out-pointer names a local.
        let succeeded = unsafe { OpenProcessToken(raw(&self.handle), TOKEN_QUERY, &mut token) };
        if succeeded == 0 {
            return Err(io::Error::last_os_error());
        }
        let token = owned(token)?;
        let mut elevation_type = 0_u32;
        let mut returned = 0_u32;
        // SAFETY: the token is open with TOKEN_QUERY; the buffer is one u32 local, exactly
        // the size of TOKEN_ELEVATION_TYPE, and `returned` is a local.
        let succeeded = unsafe {
            GetTokenInformation(
                raw(&token),
                TOKEN_ELEVATION_TYPE_CLASS,
                (&raw mut elevation_type).cast(),
                4,
                &mut returned,
            )
        };
        if succeeded == 0 {
            return Err(io::Error::last_os_error());
        }
        if returned != 4 {
            return Err(io::ErrorKind::InvalidData.into());
        }
        Ok(elevation_type == TOKEN_ELEVATION_TYPE_FULL)
    }

    /// The exit code once the process has ended, `None` while it runs.
    pub(crate) fn exit_code(&self) -> io::Result<Option<u32>> {
        // SAFETY: the handle is open with SYNCHRONIZE; a zero timeout only polls.
        match unsafe { WaitForSingleObject(raw(&self.handle), 0) } {
            WAIT_TIMEOUT => Ok(None),
            WAIT_OBJECT_0 => {
                let mut code = 0_u32;
                // SAFETY: the handle has limited query access; `code` is a local.
                if unsafe { GetExitCodeProcess(raw(&self.handle), &mut code) } == 0 {
                    return Err(io::Error::last_os_error());
                }
                Ok(Some(code))
            }
            _ => Err(io::Error::last_os_error()),
        }
    }

    /// Force the process to end; only for a runtime this manager launched or adopted.
    pub(crate) fn terminate(&self) -> io::Result<()> {
        if !self.can_terminate {
            return Err(io::Error::from_raw_os_error(ERROR_ACCESS_DENIED));
        }
        // SAFETY: the handle is open with PROCESS_TERMINATE and names the held process.
        if unsafe { TerminateProcess(raw(&self.handle), TERMINATED_EXIT_CODE) } == 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }
}

/// The Terminal Services session that `pid` runs in.
pub(crate) fn session_of(pid: u32) -> io::Result<u32> {
    let mut session = 0_u32;
    // SAFETY: plain pid in, one u32 local out.
    if unsafe { ProcessIdToSessionId(pid, &mut session) } == 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(session)
}

pub(crate) fn current_pid() -> u32 {
    // SAFETY: no arguments; always succeeds.
    unsafe { GetCurrentProcessId() }
}

/// Serializes console attachment against process launch for this whole process.
static CONSOLE_ATTACHMENT: Mutex<()> = Mutex::new(());
static ABSORBED_INTERRUPTS: AtomicU64 = AtomicU64::new(0);

/// Absorb the Ctrl+C this process generates for itself while attached.
///
/// It returns TRUE so the default handler, which would end this process, never runs. The
/// ignore flag is never set, so children never inherit "ignore Ctrl+C".
unsafe extern "system" fn absorb_interrupt(event: u32) -> i32 {
    if event == CTRL_C_EVENT || event == CTRL_BREAK_EVENT {
        ABSORBED_INTERRUPTS.fetch_add(1, Ordering::SeqCst);
        1
    } else {
        0
    }
}

/// Hold the console lock; the launcher holds it while it starts a process.
pub(crate) fn console_quiescent() -> MutexGuard<'static, ()> {
    CONSOLE_ATTACHMENT
        .lock()
        .unwrap_or_else(PoisonError::into_inner)
}

/// Why a console interrupt was not delivered.
#[derive(Debug)]
pub(crate) enum ConsoleInterruptError {
    /// This process already has a console, so it cannot attach to the runtime's.
    AlreadyAttached,
    /// The target has no console to attach to, or has ended.
    NoConsole,
    Failed,
    /// The event was generated, but this process did not observe it within the bound.
    Unconfirmed,
}

/// Attach to `pid`'s console, generate Ctrl+C, wait within `bound` for it, then detach.
///
/// The absorber is registered after attaching and stays registered for the whole
/// attachment: a registration made while this process had no console did not survive
/// `AttachConsole`, and the default handler then ended this process. The caller holds a
/// handle to `pid`, so the pid cannot name another process meanwhile.
pub(crate) fn interrupt_console(pid: u32, bound: Duration) -> Result<(), ConsoleInterruptError> {
    let _attached = console_quiescent();
    // SAFETY: plain pid in; success attaches this process to that console until FreeConsole.
    if unsafe { AttachConsole(pid) } == 0 {
        let error = io::Error::last_os_error();
        return Err(match error.raw_os_error() {
            Some(ERROR_ACCESS_DENIED) => ConsoleInterruptError::AlreadyAttached,
            Some(ERROR_INVALID_HANDLE | ERROR_INVALID_PARAMETER) => {
                ConsoleInterruptError::NoConsole
            }
            _ => ConsoleInterruptError::Failed,
        });
    }
    let result = interrupt_attached(bound);
    // SAFETY: detaches from the console attached above; no process was started meanwhile
    // because the launcher needs the lock this function holds.
    unsafe { FreeConsole() };
    // SAFETY: removes the registration made while attached; detached, this process receives
    // no console events, so none can reach the default handler afterwards.
    unsafe { SetConsoleCtrlHandler(Some(absorb_interrupt), 0) };
    result
}

fn interrupt_attached(bound: Duration) -> Result<(), ConsoleInterruptError> {
    // An inherited "ignore Ctrl+C" flag would hide the interrupt from the absorber, so the
    // delivery could not be confirmed. Clearing it never sets the flag for children.
    // SAFETY: a null handler with FALSE only clears this process's ignore flag.
    unsafe { SetConsoleCtrlHandler(None, 0) };
    // SAFETY: the handler is a plain function with the PHANDLER_ROUTINE signature that only
    // touches an atomic; it is removed again only after this process has detached.
    if unsafe { SetConsoleCtrlHandler(Some(absorb_interrupt), 1) } == 0 {
        return Err(ConsoleInterruptError::Failed);
    }
    let before = ABSORBED_INTERRUPTS.load(Ordering::SeqCst);
    // SAFETY: this process is attached; group 0 names every process on that console, and
    // the absorber keeps the event from ending this one.
    if unsafe { GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0) } == 0 {
        return Err(ConsoleInterruptError::Failed);
    }
    let deadline = Instant::now() + bound;
    while Instant::now() < deadline {
        if ABSORBED_INTERRUPTS.load(Ordering::SeqCst) > before {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(2));
    }
    Err(ConsoleInterruptError::Unconfirmed)
}
