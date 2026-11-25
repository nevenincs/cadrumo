//! Identity-preserving process-exit notifications with an explicit cancellation wake.
//!
//! Register while the owner retains the child or authenticated process. Waiting
//! owns only observation handles; cancellation never terminates the process.

use std::{io, process::Child};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ExitWake {
    Exited,
    Cancelled,
}

#[derive(Debug)]
pub struct ProcessExitWatch(imp::Watch);

impl ProcessExitWatch {
    /// Register before publishing or reaping the owned child.
    pub fn for_child(child: &Child) -> io::Result<Self> {
        #[cfg(windows)]
        {
            use std::os::windows::io::AsHandle;
            Self::from_handle(child.as_handle())
        }
        #[cfg(target_os = "linux")]
        {
            imp::Watch::open(child.id()).map(Self)
        }
        #[cfg(target_os = "macos")]
        {
            Self::for_retained_pid(child.id())
        }
    }

    /// Duplicate the exact authenticated process handle, rather than reopen its PID.
    #[cfg(windows)]
    pub fn from_handle(process: std::os::windows::io::BorrowedHandle<'_>) -> io::Result<Self> {
        imp::Watch::new(process.try_clone_to_owned()?).map(Self)
    }

    /// Duplicate the exact pidfd used to authenticate the retained process.
    #[cfg(target_os = "linux")]
    pub fn from_pidfd(process: std::os::fd::BorrowedFd<'_>) -> io::Result<Self> {
        imp::Watch::new(process.try_clone_to_owned()?).map(Self)
    }

    /// Register while a retained process identity still proves this PID.
    /// The caller must recheck that identity after registration.
    #[cfg(target_os = "macos")]
    pub fn for_retained_pid(pid: u32) -> io::Result<Self> {
        imp::Watch::open(pid).map(Self)
    }

    /// Block on exit or cancellation, without a periodic observation interval.
    pub fn wait(&self) -> io::Result<ExitWake> {
        self.0.wait()
    }

    /// Wake an observer before joining it; this does not kill or reap the process.
    pub fn cancel(&self) -> io::Result<()> {
        self.0.cancel()
    }
}

#[cfg(windows)]
mod imp {
    use super::ExitWake;
    use std::{
        ffi::c_void,
        io,
        os::windows::io::{AsRawHandle, FromRawHandle, OwnedHandle},
        ptr,
    };
    type Handle = *mut c_void;
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn CreateEventW(
            attributes: *const crate::desktop::SecurityAttributes,
            manual: i32,
            initial: i32,
            name: *const u16,
        ) -> Handle;
        fn SetEvent(event: Handle) -> i32;
        fn WaitForMultipleObjects(
            count: u32,
            handles: *const Handle,
            all: i32,
            milliseconds: u32,
        ) -> u32;
    }

    #[derive(Debug)]
    pub struct Watch {
        process: OwnedHandle,
        cancelled: OwnedHandle,
    }
    impl Watch {
        pub fn new(process: OwnedHandle) -> io::Result<Self> {
            // SAFETY: no borrowed security descriptor or name; this call creates a new event.
            let event = unsafe { CreateEventW(ptr::null(), 1, 0, ptr::null()) };
            if event.is_null() {
                return Err(io::Error::last_os_error());
            }
            // SAFETY: successful creation transfers this distinct handle.
            let cancelled = unsafe { OwnedHandle::from_raw_handle(event) };
            Ok(Self { process, cancelled })
        }
        pub fn wait(&self) -> io::Result<ExitWake> {
            let handles = [self.cancelled.as_raw_handle(), self.process.as_raw_handle()];
            // SAFETY: both handles remain owned and live for this entire wait.
            match unsafe { WaitForMultipleObjects(2, handles.as_ptr(), 0, u32::MAX) } {
                0 => Ok(ExitWake::Cancelled),
                1 => Ok(ExitWake::Exited),
                _ => Err(io::Error::last_os_error()),
            }
        }
        pub fn cancel(&self) -> io::Result<()> {
            // SAFETY: this owned manual-reset event remains live.
            if unsafe { SetEvent(self.cancelled.as_raw_handle()) } == 0 {
                return Err(io::Error::last_os_error());
            }
            Ok(())
        }
    }
}

#[cfg(target_os = "linux")]
mod imp {
    use super::ExitWake;
    use std::{
        io,
        os::fd::{AsRawFd, FromRawFd, OwnedFd},
    };
    #[derive(Debug)]
    pub struct Watch {
        process: OwnedFd,
        cancelled: OwnedFd,
    }
    impl Watch {
        pub fn open(pid: u32) -> io::Result<Self> {
            let pid = i32::try_from(pid)
                .ok()
                .filter(|pid| *pid > 0)
                .ok_or(io::ErrorKind::InvalidInput)?;
            // SAFETY: pidfd_open takes plain integer arguments and returns a distinct descriptor.
            let raw = unsafe { libc::syscall(libc::SYS_pidfd_open, pid, 0) };
            if raw < 0 {
                return Err(io::Error::last_os_error());
            }
            // SAFETY: successful pidfd_open transfers this close-on-exec descriptor.
            Self::new(unsafe { OwnedFd::from_raw_fd(raw as i32) })
        }
        pub fn new(process: OwnedFd) -> io::Result<Self> {
            // SAFETY: eventfd takes integer flags and transfers a distinct descriptor.
            let raw = unsafe { libc::eventfd(0, libc::EFD_CLOEXEC | libc::EFD_NONBLOCK) };
            if raw < 0 {
                return Err(io::Error::last_os_error());
            }
            // SAFETY: successful eventfd transfers this descriptor.
            Ok(Self {
                process,
                cancelled: unsafe { OwnedFd::from_raw_fd(raw) },
            })
        }
        pub fn wait(&self) -> io::Result<ExitWake> {
            loop {
                let mut descriptors = [
                    libc::pollfd {
                        fd: self.cancelled.as_raw_fd(),
                        events: libc::POLLIN,
                        revents: 0,
                    },
                    libc::pollfd {
                        fd: self.process.as_raw_fd(),
                        events: libc::POLLIN,
                        revents: 0,
                    },
                ];
                // SAFETY: both initialized poll records refer to descriptors owned for this wait.
                if unsafe { libc::poll(descriptors.as_mut_ptr(), 2, -1) } < 0 {
                    let error = io::Error::last_os_error();
                    if error.kind() == io::ErrorKind::Interrupted {
                        continue;
                    }
                    return Err(error);
                }
                if descriptors
                    .iter()
                    .any(|value| value.revents & libc::POLLNVAL != 0)
                {
                    return Err(io::ErrorKind::InvalidInput.into());
                }
                if descriptors
                    .iter()
                    .any(|value| value.revents & libc::POLLERR != 0)
                {
                    return Err(io::ErrorKind::InvalidData.into());
                }
                if descriptors[0].revents & libc::POLLIN != 0 {
                    return Ok(ExitWake::Cancelled);
                }
                if descriptors[1].revents & (libc::POLLIN | libc::POLLHUP) != 0 {
                    return Ok(ExitWake::Exited);
                }
            }
        }
        pub fn cancel(&self) -> io::Result<()> {
            let value: u64 = 1;
            // SAFETY: one initialized u64 is written to this live eventfd.
            if unsafe { libc::write(self.cancelled.as_raw_fd(), (&value as *const u64).cast(), 8) }
                < 0
            {
                let error = io::Error::last_os_error();
                if error.kind() != io::ErrorKind::WouldBlock {
                    return Err(error);
                }
            }
            Ok(())
        }
    }
}

#[cfg(target_os = "macos")]
mod imp {
    use super::ExitWake;
    use std::{
        io,
        os::fd::{AsRawFd, FromRawFd, OwnedFd},
        ptr,
    };
    #[derive(Debug)]
    pub struct Watch(OwnedFd);
    impl Watch {
        pub fn open(pid: u32) -> io::Result<Self> {
            if pid == 0 {
                return Err(io::ErrorKind::InvalidInput.into());
            }
            // SAFETY: kqueue creates a distinct descriptor without borrowed arguments.
            let raw = unsafe { libc::kqueue() };
            if raw < 0 {
                return Err(io::Error::last_os_error());
            }
            // SAFETY: successful creation transfers this descriptor.
            let queue = unsafe { OwnedFd::from_raw_fd(raw) };
            // SAFETY: this live descriptor must not be inherited by later children.
            if unsafe { libc::fcntl(queue.as_raw_fd(), libc::F_SETFD, libc::FD_CLOEXEC) } < 0 {
                return Err(io::Error::last_os_error());
            }
            let changes = [
                libc::kevent {
                    ident: pid as libc::uintptr_t,
                    filter: libc::EVFILT_PROC,
                    flags: libc::EV_ADD | libc::EV_ENABLE | libc::EV_ONESHOT,
                    fflags: libc::NOTE_EXIT,
                    data: 0,
                    udata: ptr::null_mut(),
                },
                libc::kevent {
                    ident: 0,
                    filter: libc::EVFILT_USER,
                    flags: libc::EV_ADD | libc::EV_ENABLE | libc::EV_CLEAR,
                    fflags: 0,
                    data: 0,
                    udata: ptr::null_mut(),
                },
            ];
            // SAFETY: two initialized registration records, no output storage or timeout.
            if unsafe {
                libc::kevent(
                    queue.as_raw_fd(),
                    changes.as_ptr(),
                    2,
                    ptr::null_mut(),
                    0,
                    ptr::null(),
                )
            } < 0
            {
                let error = io::Error::last_os_error();
                return Err(if error.raw_os_error() == Some(libc::ESRCH) {
                    io::ErrorKind::NotFound.into()
                } else {
                    error
                });
            }
            Ok(Self(queue))
        }
        pub fn wait(&self) -> io::Result<ExitWake> {
            loop {
                // SAFETY: this plain output record accepts zeroed storage.
                let mut event: libc::kevent = unsafe { std::mem::zeroed() };
                // SAFETY: one output record; this owned queue waits for an exit or user wake.
                if unsafe {
                    libc::kevent(
                        self.0.as_raw_fd(),
                        ptr::null(),
                        0,
                        &mut event,
                        1,
                        ptr::null(),
                    )
                } < 0
                {
                    let error = io::Error::last_os_error();
                    if error.kind() == io::ErrorKind::Interrupted {
                        continue;
                    }
                    return Err(error);
                }
                if event.flags & libc::EV_ERROR != 0 {
                    return Err(io::ErrorKind::InvalidData.into());
                }
                if event.filter == libc::EVFILT_USER {
                    return Ok(ExitWake::Cancelled);
                }
                if event.filter == libc::EVFILT_PROC && event.fflags & libc::NOTE_EXIT != 0 {
                    return Ok(ExitWake::Exited);
                }
            }
        }
        pub fn cancel(&self) -> io::Result<()> {
            let change = libc::kevent {
                ident: 0,
                filter: libc::EVFILT_USER,
                flags: 0,
                fflags: libc::NOTE_TRIGGER,
                data: 0,
                udata: ptr::null_mut(),
            };
            // SAFETY: one initialized user-event trigger against the queue owned here.
            if unsafe {
                libc::kevent(
                    self.0.as_raw_fd(),
                    &change,
                    1,
                    ptr::null_mut(),
                    0,
                    ptr::null(),
                )
            } < 0
            {
                return Err(io::Error::last_os_error());
            }
            Ok(())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        process::{Command, Stdio},
        sync::{Arc, mpsc},
        thread,
        time::Duration,
    };

    fn child_waiting_for_eof() -> Child {
        #[cfg(windows)]
        let mut command = {
            use std::os::windows::process::CommandExt;
            let root = std::env::var_os("SystemRoot").unwrap();
            let mut command = Command::new(
                std::path::Path::new(&root).join("System32/WindowsPowerShell/v1.0/powershell.exe"),
            );
            command.args([
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                "[Console]::In.ReadToEnd() | Out-Null",
            ]);
            command.creation_flags(0x0800_0000);
            command
        };
        #[cfg(unix)]
        let mut command = {
            let mut command = Command::new("/bin/sh");
            command.args(["-c", "while IFS= read -r line; do :; done"]);
            command
        };
        command
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .unwrap()
    }

    #[test]
    fn cancelling_the_observer_does_not_terminate_its_owned_child() {
        let mut child = child_waiting_for_eof();
        let watch = Arc::new(ProcessExitWatch::for_child(&child).unwrap());
        let observer = watch.clone();
        let (completed, observed) = mpsc::channel();
        let waiting = thread::spawn(move || completed.send(observer.wait()).unwrap());
        watch.cancel().unwrap();
        let result = observed.recv_timeout(Duration::from_secs(5));
        let still_running = child.try_wait().unwrap().is_none();
        // Always release the real process before assertions or observer joins.
        let _ = child.kill();
        child.wait().unwrap();
        waiting.join().unwrap();
        assert_eq!(result.unwrap().unwrap(), ExitWake::Cancelled);
        assert!(still_running);
    }

    #[test]
    fn the_retained_process_exit_wakes_its_observer() {
        let mut child = child_waiting_for_eof();
        let watch = Arc::new(ProcessExitWatch::for_child(&child).unwrap());
        let observer = watch.clone();
        let (completed, observed) = mpsc::channel();
        let waiting = thread::spawn(move || completed.send(observer.wait()).unwrap());
        drop(child.stdin.take());
        child.wait().unwrap();
        let result = observed.recv_timeout(Duration::from_secs(5));
        watch.cancel().unwrap();
        waiting.join().unwrap();
        assert_eq!(result.unwrap().unwrap(), ExitWake::Exited);
    }
}
