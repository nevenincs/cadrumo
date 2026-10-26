//! Graceful stop delivery outside the protocol channel.
//!
//! Every runtime version maps console Ctrl+C on Windows and SIGTERM on POSIX to its drain.
//! The manager uses the signal when it has no usable channel, such as for an adopted runtime.
//! On Windows it never sets "ignore Ctrl+C" (`SetConsoleCtrlHandler(NULL, TRUE)`) and never
//! uses `CREATE_NEW_PROCESS_GROUP`; a handler registered for the whole attachment absorbs
//! the Ctrl+C it generates for itself while attached to the runtime's console.

use super::process::RuntimeProcess;
use std::time::Duration;

/// Why a stop signal was not delivered.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StopSignalError {
    /// The runtime has already ended.
    NotRunning,
    /// This platform cannot signal this kind of held process yet.
    Unsupported,
    /// This process already has a console of its own and cannot attach to the runtime's.
    AlreadyAttached,
    /// The runtime has no console to receive the interrupt.
    NoConsole,
    /// The interrupt was generated but not observed within the bound.
    Unconfirmed,
    /// The operating system refused the delivery.
    Failed,
}

/// Delivers the stop signal every runtime version maps to its graceful drain.
pub trait StopSignal: Send {
    /// Ask the held `runtime` to drain; the caller still bounds the wait for its exit.
    fn deliver(&self, runtime: &mut RuntimeProcess) -> Result<(), StopSignalError>;
}

/// Console Ctrl+C on Windows, SIGTERM through the held child on POSIX.
#[derive(Clone, Copy, Debug)]
pub struct PlatformStopSignal {
    /// How long Windows delivery waits to observe its own interrupt before detaching.
    pub delivery_bound: Duration,
}

impl Default for PlatformStopSignal {
    fn default() -> Self {
        Self {
            delivery_bound: Duration::from_secs(1),
        }
    }
}

impl StopSignal for PlatformStopSignal {
    #[cfg(windows)]
    fn deliver(&self, runtime: &mut RuntimeProcess) -> Result<(), StopSignalError> {
        use super::windows::{ConsoleInterruptError, interrupt_console};
        match runtime.try_exit() {
            Ok(Some(_)) => return Err(StopSignalError::NotRunning),
            Ok(None) => {}
            Err(_) => return Err(StopSignalError::Failed),
        }
        interrupt_console(runtime.pid(), self.delivery_bound).map_err(|error| match error {
            ConsoleInterruptError::AlreadyAttached => StopSignalError::AlreadyAttached,
            ConsoleInterruptError::NoConsole => StopSignalError::NoConsole,
            ConsoleInterruptError::Unconfirmed => StopSignalError::Unconfirmed,
            ConsoleInterruptError::Failed => StopSignalError::Failed,
        })
    }

    #[cfg(unix)]
    fn deliver(&self, runtime: &mut RuntimeProcess) -> Result<(), StopSignalError> {
        match runtime {
            RuntimeProcess::Launched(child) => match child.try_wait() {
                Ok(None) => posix::terminate(child.id()),
                Ok(Some(_)) => Err(StopSignalError::NotRunning),
                Err(_) => Err(StopSignalError::Failed),
            },
            #[cfg(any(target_os = "linux", target_os = "macos"))]
            RuntimeProcess::Adopted(opened) => {
                super::process::adopted_stop(opened).map_err(|error| {
                    if error.raw_os_error() == Some(libc::ESRCH) {
                        StopSignalError::NotRunning
                    } else {
                        StopSignalError::Failed
                    }
                })
            }
            #[cfg(not(any(target_os = "linux", target_os = "macos")))]
            RuntimeProcess::Adopted(_) => Err(StopSignalError::Unsupported),
        }
    }

    #[cfg(not(any(windows, unix)))]
    fn deliver(&self, _runtime: &mut RuntimeProcess) -> Result<(), StopSignalError> {
        Err(StopSignalError::Unsupported)
    }
}

#[cfg(unix)]
#[allow(unsafe_code)]
mod posix {
    use super::StopSignalError;

    const SIGTERM: i32 = 15;

    unsafe extern "C" {
        fn kill(pid: i32, signal: i32) -> i32;
    }

    /// Send SIGTERM to an unreaped child of this process.
    pub(super) fn terminate(pid: u32) -> Result<(), StopSignalError> {
        let pid = i32::try_from(pid).map_err(|_| StopSignalError::Failed)?;
        // SAFETY: `pid` names a child this process has not reaped, so the kernel keeps the
        // pid reserved for it; kill takes plain integers and touches no memory of ours.
        if unsafe { kill(pid, SIGTERM) } == 0 {
            Ok(())
        } else {
            Err(StopSignalError::Failed)
        }
    }
}
