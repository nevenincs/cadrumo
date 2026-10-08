//! Processes the supervisor holds: the runtime it launched or adopted, and inspection by pid.
//!
//! A held process keeps its native identity capability for the whole supervision;
//! adopted-process actions never target an uncorroborated numeric pid.

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
    /// The native login session; `None` when it could not be read.
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
    #[cfg(target_os = "macos")]
    held: crate::macos::process::Process,
    #[cfg(target_os = "macos")]
    admitted_session: Option<crate::macos::login::Session>,
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
#[cfg(not(any(windows, target_os = "linux", target_os = "macos")))]
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

#[cfg(not(any(windows, target_os = "linux", target_os = "macos")))]
fn adopted_exit(_opened: &OpenedProcess) -> io::Result<Option<RuntimeExit>> {
    Err(io::Error::from(io::ErrorKind::Unsupported))
}

#[cfg(windows)]
fn adopted_terminate(opened: &OpenedProcess) -> io::Result<()> {
    opened.held.terminate()
}

#[cfg(not(any(windows, target_os = "linux", target_os = "macos")))]
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

#[cfg(target_os = "macos")]
fn darwin_process_failure(error: io::Error) -> InspectError {
    // Only the process owner uses NotFound for its latched NOTE_EXIT evidence.
    // Native libproc ESRCH also proves absence; never interpret Mach status as errno.
    if error.raw_os_error() == Some(libc::ESRCH) || error.kind() == io::ErrorKind::NotFound {
        InspectError::NotRunning
    } else {
        InspectError::Failed(error)
    }
}

#[cfg(target_os = "macos")]
pub fn open_process(pid: u32) -> Result<OpenedProcess, InspectError> {
    let held = crate::macos::process::Process::open(pid).map_err(darwin_process_failure)?;
    let session = crate::macos::login::Login::open()
        .and_then(|login| login.process(&held))
        .map_err(InspectError::Failed)?;
    let observed = held.identity().map_err(darwin_process_failure)?;
    let identity = ProcessIdentity {
        pid: observed.incarnation.pid,
        created: observed
            .observed
            .created_microseconds()
            .map_err(InspectError::Failed)?,
        image: observed.image.clone(),
        // Process admission has verified non-root matching real/effective/saved UID
        // and refused P_SUGID; kernel audit UID is independently corroborated above.
        fully_elevated: Some(false),
        session: Some(session.id().to_string()),
    };
    Ok(OpenedProcess {
        identity,
        held,
        admitted_session: Some(session),
    })
}

#[cfg(target_os = "macos")]
fn adopted_exit(opened: &OpenedProcess) -> io::Result<Option<RuntimeExit>> {
    // kqueue proves exit, but an adopted non-child has no waitable exit status.
    opened
        .held
        .exited()
        .map(|exited| exited.then_some(RuntimeExit::Unknown))
}

#[cfg(target_os = "macos")]
fn darwin_signal(opened: &OpenedProcess, signal: i32) -> io::Result<()> {
    if opened.held.exited()? {
        return Err(io::Error::from_raw_os_error(libc::ESRCH));
    }
    let admitted = opened
        .admitted_session
        .as_ref()
        .ok_or(io::ErrorKind::PermissionDenied)?;
    let manager = crate::macos::process::Process::open(std::process::id())?;
    let owner = crate::macos::login::Login::process_identity(&manager)?;
    let target = crate::macos::login::Login::process_identity(&opened.held).map_err(|error| {
        if error.kind() == io::ErrorKind::NotFound {
            io::Error::from_raw_os_error(libc::ESRCH)
        } else {
            error
        }
    })?;
    require_darwin_signal_session(
        Some((admitted.uid(), admitted.id())),
        (owner.uid(), owner.id()),
        (target.uid(), target.id()),
    )?;
    if crate::macos::login::Login::process_identity(&manager)? != owner {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    // Session checks are bounded observations, not atomic with delivery. The
    // subsequent native signal does atomically require the held pidversion.
    let delivery = opened.held.signal(signal).map_err(|error| {
        if error.kind() == io::ErrorKind::NotFound {
            io::Error::from_raw_os_error(libc::ESRCH)
        } else {
            error
        }
    })?;
    match delivery {
        crate::macos::records::SignalDelivery::Delivered => Ok(()),
        crate::macos::records::SignalDelivery::Gone => {
            Err(io::Error::from_raw_os_error(libc::ESRCH))
        }
    }
}

#[cfg(target_os = "macos")]
fn require_darwin_signal_session(
    admitted: Option<(u32, u32)>,
    owner: (u32, u32),
    target: (u32, u32),
) -> io::Result<()> {
    if admitted != Some(owner) || target != owner {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    Ok(())
}

#[cfg(target_os = "macos")]
fn adopted_terminate(opened: &OpenedProcess) -> io::Result<()> {
    darwin_signal(opened, libc::SIGKILL)
}

#[cfg(target_os = "macos")]
pub(super) fn adopted_stop(opened: &OpenedProcess) -> io::Result<()> {
    darwin_signal(opened, libc::SIGTERM)
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

#[cfg(all(test, target_os = "macos"))]
mod darwin_tests {
    use super::*;
    use crate::supervision::stop::{PlatformStopSignal, StopSignal, StopSignalError};
    use std::process::{Command, Stdio};

    struct InputChild(Child);
    impl InputChild {
        fn new() -> Self {
            Self(
                Command::new("/bin/cat")
                    .stdin(Stdio::piped())
                    .stdout(Stdio::null())
                    .spawn()
                    .unwrap(),
            )
        }
        // Only this synthetic test constructs an unadmitted OpenedProcess. It tests
        // held lifecycle capabilities even when the test runner is an SSH session.
        fn held(&self) -> OpenedProcess {
            let held = crate::macos::process::Process::open(self.0.id()).unwrap();
            let observed = held.identity().unwrap();
            let identity = ProcessIdentity {
                pid: self.0.id(),
                created: observed.observed.created_microseconds().unwrap(),
                image: observed.image.clone(),
                fully_elevated: Some(false),
                session: None,
            };
            OpenedProcess {
                identity,
                held,
                admitted_session: None,
            }
        }
    }
    impl Drop for InputChild {
        fn drop(&mut self) {
            drop(self.0.stdin.take());
            self.0.wait().unwrap();
        }
    }

    #[test]
    fn adopted_normal_exit_is_unknown_and_stop_reports_not_running() {
        let child = InputChild::new();
        let mut runtime = RuntimeProcess::Adopted(child.held());
        assert_eq!(runtime.try_exit().unwrap(), None);
        drop(child);
        assert_eq!(runtime.try_exit().unwrap(), Some(RuntimeExit::Unknown));
        assert_eq!(
            PlatformStopSignal::default().deliver(&mut runtime),
            Err(StopSignalError::NotRunning)
        );
        assert_eq!(
            runtime.terminate().unwrap_err().raw_os_error(),
            Some(libc::ESRCH)
        );
    }

    #[test]
    fn unadmitted_process_has_no_signal_authority() {
        let child = InputChild::new();
        let mut runtime = RuntimeProcess::Adopted(child.held());
        assert_eq!(
            PlatformStopSignal::default().deliver(&mut runtime),
            Err(StopSignalError::Failed)
        );
        assert_eq!(
            runtime.terminate().unwrap_err().kind(),
            io::ErrorKind::PermissionDenied
        );
        assert_eq!(runtime.try_exit().unwrap(), None);
    }

    #[test]
    fn signal_session_requires_retained_admission_and_both_current_owners() {
        assert!(require_darwin_signal_session(Some((501, 42)), (501, 42), (501, 42)).is_ok());
        for (admitted, owner, target) in [
            (None, (501, 42), (501, 42)),
            (Some((501, 42)), (501, 43), (501, 42)),
            (Some((501, 42)), (501, 42), (501, 43)),
            (Some((501, 42)), (501, 43), (501, 43)),
            (Some((501, 42)), (502, 42), (501, 42)),
            (Some((501, 42)), (501, 42), (502, 42)),
        ] {
            assert_eq!(
                require_darwin_signal_session(admitted, owner, target)
                    .unwrap_err()
                    .kind(),
                io::ErrorKind::PermissionDenied
            );
        }
    }

    #[test]
    fn only_process_absence_is_a_stale_record() {
        for error in [
            io::Error::from_raw_os_error(libc::ESRCH),
            io::ErrorKind::NotFound.into(),
        ] {
            assert!(matches!(
                darwin_process_failure(error),
                InspectError::NotRunning
            ));
        }
        for error in [
            io::Error::other("task_name_for_pid: Mach status 5"),
            io::ErrorKind::PermissionDenied.into(),
            io::ErrorKind::InvalidData.into(),
            io::ErrorKind::Unsupported.into(),
        ] {
            assert!(matches!(
                darwin_process_failure(error),
                InspectError::Failed(_)
            ));
        }
        // Real inspection preserves the graphical policy on both desktop and SSH runners.
        let held = crate::macos::process::Process::open(std::process::id()).unwrap();
        let expected = crate::macos::login::Login::open().unwrap().process(&held);
        match expected {
            Ok(session) => assert_eq!(
                open_process(std::process::id()).unwrap().identity.session,
                Some(session.id().to_string())
            ),
            Err(_) => assert!(matches!(
                open_process(std::process::id()),
                Err(InspectError::Failed(_))
            )),
        }
    }
}
