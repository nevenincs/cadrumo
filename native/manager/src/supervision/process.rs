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
    pub session: Option<u32>,
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
        session: windows::session_of(pid).ok(),
    };
    Ok(OpenedProcess { identity, held })
}

/// Open and inspect the live process `pid`.
#[cfg(not(windows))]
pub fn open_process(_pid: u32) -> Result<OpenedProcess, InspectError> {
    Err(InspectError::Unsupported)
}

/// The session this manager runs in, when the platform reports one.
pub fn current_session() -> Option<u32> {
    #[cfg(windows)]
    {
        super::windows::session_of(super::windows::current_pid()).ok()
    }
    #[cfg(not(windows))]
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
    pub fn try_exit(&mut self) -> Option<RuntimeExit> {
        match self {
            Self::Launched(child) => match child.try_wait() {
                Ok(status) => status.map(exit_of),
                Err(_) => Some(RuntimeExit::Unknown),
            },
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
fn adopted_exit(opened: &OpenedProcess) -> Option<RuntimeExit> {
    match opened.held.exit_code() {
        Ok(code) => code.map(RuntimeExit::from_code),
        Err(_) => Some(RuntimeExit::Unknown),
    }
}

#[cfg(not(windows))]
fn adopted_exit(_opened: &OpenedProcess) -> Option<RuntimeExit> {
    Some(RuntimeExit::Unknown)
}

#[cfg(windows)]
fn adopted_terminate(opened: &OpenedProcess) -> io::Result<()> {
    opened.held.terminate()
}

#[cfg(not(windows))]
fn adopted_terminate(_opened: &OpenedProcess) -> io::Result<()> {
    Err(io::Error::from(io::ErrorKind::Unsupported))
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
