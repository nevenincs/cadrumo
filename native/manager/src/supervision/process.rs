//! Processes the supervisor holds: the runtime it launched or adopted, and inspection by pid.
//!
//! A held process keeps its handle open for the whole supervision, so its pid can never
//! name another process while the supervisor acts on it.

use super::exit::RuntimeExit;
use std::io;
use std::path::PathBuf;
use std::process::{Child, ExitStatus};

/// What the supervisor observed about one live process.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProcessIdentity {
    pub pid: u32,
    /// The platform-native creation stamp, comparable with the boot record's.
    pub created: u64,
    pub image: PathBuf,
    /// Whether the token is fully elevated; `None` when the token could not be read.
    pub fully_elevated: Option<bool>,
    /// The Terminal Services session; `None` when it could not be read.
    pub session: Option<String>,
}

/// Why a process could not be inspected.
#[derive(Debug)]
pub enum InspectError {
    /// No live process has that pid.
    NotRunning,
    /// This platform has no inspection yet.
    Unsupported,
    Failed(io::Error),
}

/// A process opened by pid and held, with what was observed through that same handle.
#[derive(Debug)]
pub struct OpenedProcess {
    pub identity: ProcessIdentity,
    #[cfg(windows)]
    held: super::windows::HeldProcess,
    #[cfg(target_os = "linux")]
    held: crate::linux::process::Process,
}

/// Open and inspect the live process `pid`.
#[cfg(windows)]
pub fn open_process(pid: u32) -> Result<OpenedProcess, InspectError> {
    use super::windows;
    const ERROR_INVALID_PARAMETER: i32 = 87;
    let held = windows::open_process(pid).map_err(|error| match error.raw_os_error() {
        Some(ERROR_INVALID_PARAMETER) => InspectError::NotRunning,
        _ => InspectError::Failed(error),
    })?;
    // An ended process stays openable while any handle to it is open elsewhere.
    if held.exit_code().map_err(InspectError::Failed)?.is_some() {
        return Err(InspectError::NotRunning);
    }
    let identity = ProcessIdentity {
        pid,
        created: held.creation_time().map_err(InspectError::Failed)?,
        image: held.image().map_err(InspectError::Failed)?,
        fully_elevated: held.fully_elevated().ok(),
        session: windows::session_of(pid)
            .ok()
            .map(|session| session.to_string()),
    };
    Ok(OpenedProcess { identity, held })
}

/// Open and inspect the live process `pid`.
#[cfg(not(any(windows, target_os = "linux")))]
pub fn open_process(_pid: u32) -> Result<OpenedProcess, InspectError> {
    Err(InspectError::Unsupported)
}

/// The session this manager runs in, when the platform reports one.
pub fn current_session() -> Option<String> {
    #[cfg(windows)]
    {
        super::windows::session_of(super::windows::current_pid())
            .ok()
            .map(|session| session.to_string())
    }
    #[cfg(target_os = "linux")]
    {
        let process = crate::linux::process::Process::open(std::process::id()).ok()?;
        crate::linux::login::Login::open()
            .ok()?
            .session(&process)
            .ok()
            .map(|session| session.id)
    }
    #[cfg(target_os = "macos")]
    {
        crate::session::ManagerSession::current()
            .ok()
            .map(|session| session.session)
    }
    #[cfg(not(any(windows, target_os = "linux", target_os = "macos")))]
    {
        None
    }
}

/// The runtime under supervision.
#[derive(Debug)]
pub enum RuntimeProcess {
    /// Launched by this manager; the child owns the process handle and the protocol pipes.
    Launched(Child),
    /// Adopted by identity; supervised by handle and stop signal only.
    Adopted(OpenedProcess),
}

impl RuntimeProcess {
    pub fn pid(&self) -> u32 {
        match self {
            Self::Launched(child) => child.id(),
            Self::Adopted(opened) => opened.identity.pid,
        }
    }

    /// How the process ended, or `None` while it runs.
    pub fn try_exit(&mut self) -> io::Result<Option<RuntimeExit>> {
        match self {
            Self::Launched(child) => child.try_wait().map(|status| status.map(exit_of)),
            Self::Adopted(opened) => adopted_exit(opened),
        }
    }

    /// Force the process to end.
    pub fn terminate(&mut self) -> io::Result<()> {
        match self {
            Self::Launched(child) => child.kill(),
            Self::Adopted(opened) => adopted_terminate(opened),
        }
    }
}

#[cfg(windows)]
fn adopted_exit(opened: &OpenedProcess) -> io::Result<Option<RuntimeExit>> {
    opened
        .held
        .exit_code()
        .map(|code| code.map(RuntimeExit::from_code))
}

#[cfg(not(any(windows, target_os = "linux")))]
fn adopted_exit(_opened: &OpenedProcess) -> io::Result<Option<RuntimeExit>> {
    Err(io::Error::from(io::ErrorKind::Unsupported))
}

#[cfg(windows)]
fn adopted_terminate(opened: &OpenedProcess) -> io::Result<()> {
    opened.held.terminate()
}

#[cfg(not(any(windows, target_os = "linux")))]
fn adopted_terminate(_opened: &OpenedProcess) -> io::Result<()> {
    Err(io::Error::from(io::ErrorKind::Unsupported))
}

#[cfg(target_os = "linux")]
pub fn open_process(pid: u32) -> Result<OpenedProcess, InspectError> {
    let failure = |error: io::Error| match error.raw_os_error() {
        Some(libc::ESRCH | libc::ENOENT) => InspectError::NotRunning,
        _ if error.kind() == io::ErrorKind::NotFound => InspectError::NotRunning,
        _ => InspectError::Failed(error),
    };
    let held = crate::linux::process::Process::open(pid).map_err(failure)?;
    let observed = held.identity().map_err(failure)?;
    if observed.uid != crate::custody::effective_uid() {
        return Err(InspectError::Failed(io::ErrorKind::PermissionDenied.into()));
    }
    let session = crate::linux::login::Login::open()
        .and_then(|login| login.session(&held))
        .ok();
    held.require_alive().map_err(failure)?;
    Ok(OpenedProcess {
        identity: ProcessIdentity {
            pid,
            created: observed.created,
            image: observed.image,
            fully_elevated: Some(observed.privileged),
            session: session.map(|session| session.id),
        },
        held,
    })
}

#[cfg(target_os = "linux")]
fn adopted_exit(opened: &OpenedProcess) -> io::Result<Option<RuntimeExit>> {
    // A non-child pidfd proves death, but does not expose a waitable exit status.
    opened
        .held
        .alive()
        .map(|alive| (!alive).then_some(RuntimeExit::Unknown))
}

#[cfg(target_os = "linux")]
fn adopted_terminate(opened: &OpenedProcess) -> io::Result<()> {
    opened.held.signal(libc::SIGKILL)
}

#[cfg(target_os = "linux")]
pub(super) fn adopted_stop(opened: &OpenedProcess) -> io::Result<()> {
    opened.held.signal(libc::SIGTERM)
}

/// Read a platform exit status as the unsigned code the exit-reason table uses.
pub fn exit_of(status: ExitStatus) -> RuntimeExit {
    if let Some(code) = status.code() {
        return RuntimeExit::from_code(u32::from_ne_bytes(code.to_ne_bytes()));
    }
    #[cfg(unix)]
    {
        use std::os::unix::process::ExitStatusExt;
        if let Some(signal) = status.signal() {
            // POSIX shells report a signal exit as 128 + N, inside the reserved range.
            return RuntimeExit::from_code(128 + signal.unsigned_abs());
        }
    }
    RuntimeExit::Unknown
}
