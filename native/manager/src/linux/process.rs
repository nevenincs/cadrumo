//! Linux process handles. Every observation is bracketed by pidfd liveness checks.
#![allow(unsafe_code)]

use std::{
    fs,
    io::{self, Read},
    os::fd::{AsRawFd, FromRawFd, OwnedFd},
    path::PathBuf,
};

#[derive(Debug)]
pub struct Process {
    descriptor: OwnedFd,
    pid: u32,
}

#[derive(Debug, PartialEq, Eq)]
pub struct Identity {
    pub created: u64,
    pub image: PathBuf,
    pub uid: u32,
    pub privileged: bool,
}

impl Process {
    pub fn open(pid: u32) -> io::Result<Self> {
        let pid = i32::try_from(pid)
            .ok()
            .filter(|pid| *pid > 0)
            .ok_or(io::ErrorKind::InvalidInput)?;
        // SAFETY: pidfd_open receives only integer values and returns an owned descriptor.
        let descriptor = unsafe { libc::syscall(libc::SYS_pidfd_open, pid, 0) };
        if descriptor < 0 {
            return Err(io::Error::last_os_error());
        }
        // SAFETY: successful pidfd_open returns a new close-on-exec descriptor.
        let descriptor = unsafe { OwnedFd::from_raw_fd(descriptor as i32) };
        let process = Self {
            descriptor,
            pid: pid as u32,
        };
        process.require_alive()?;
        Ok(process)
    }

    pub fn descriptor(&self) -> &OwnedFd {
        &self.descriptor
    }

    pub fn alive(&self) -> io::Result<bool> {
        let mut poll = libc::pollfd {
            fd: self.descriptor.as_raw_fd(),
            events: libc::POLLIN,
            revents: 0,
        };
        // SAFETY: poll points to one initialized pollfd for this owned descriptor.
        let result = unsafe { libc::poll(&mut poll, 1, 0) };
        if result < 0 {
            return Err(io::Error::last_os_error());
        }
        if poll.revents & libc::POLLNVAL != 0 {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        Ok(result == 0)
    }

    pub fn require_alive(&self) -> io::Result<()> {
        if self.alive()? {
            Ok(())
        } else {
            Err(io::ErrorKind::NotFound.into())
        }
    }

    pub fn signal(&self, signal: i32) -> io::Result<()> {
        // SAFETY: the descriptor is owned and pidfd_send_signal receives no siginfo pointer.
        let result = unsafe {
            libc::syscall(
                libc::SYS_pidfd_send_signal,
                self.descriptor.as_raw_fd(),
                signal,
                std::ptr::null::<libc::siginfo_t>(),
                0,
            )
        };
        if result < 0 {
            Err(io::Error::last_os_error())
        } else {
            Ok(())
        }
    }

    pub fn identity(&self) -> io::Result<Identity> {
        self.require_alive()?;
        let root = PathBuf::from("/proc").join(self.pid.to_string());
        let before = start_ticks(&bounded(root.join("stat"))?)?;
        let status = bounded(root.join("status"))?;
        let (uid, privileged) = credentials(&status)?;
        let image = fs::read_link(root.join("exe"))?;
        let after = start_ticks(&bounded(root.join("stat"))?)?;
        self.require_alive()?;
        if before != after || !image.is_absolute() {
            return Err(io::ErrorKind::InvalidData.into());
        }
        Ok(Identity {
            created: before,
            image,
            uid,
            privileged,
        })
    }
}

fn bounded(path: PathBuf) -> io::Result<String> {
    let mut value = String::new();
    fs::File::open(path)?
        .take(65537)
        .read_to_string(&mut value)?;
    if value.len() > 65536 {
        return Err(io::ErrorKind::InvalidData.into());
    }
    Ok(value)
}

fn start_ticks(stat: &str) -> io::Result<u64> {
    let value = stat
        .rsplit_once(") ")
        .and_then(|(_, suffix)| suffix.split_ascii_whitespace().nth(19))
        .filter(|value| !value.is_empty() && value.bytes().all(|byte| byte.is_ascii_digit()))
        .and_then(|value| value.parse::<u64>().ok())
        .filter(|value| *value > 0);
    value.ok_or_else(|| io::ErrorKind::InvalidData.into())
}

fn credentials(status: &str) -> io::Result<(u32, bool)> {
    let mut uid = None;
    let mut capabilities = None;
    for line in status.lines() {
        if let Some(value) = line.strip_prefix("Uid:") {
            if uid.is_some() {
                return Err(io::ErrorKind::InvalidData.into());
            }
            let values = value
                .split_ascii_whitespace()
                .map(str::parse::<u32>)
                .collect::<Result<Vec<_>, _>>()
                .map_err(|_| io::ErrorKind::InvalidData)?;
            if values.len() != 4 || values.iter().any(|value| *value != values[0]) {
                return Err(io::ErrorKind::PermissionDenied.into());
            }
            uid = Some(values[0]);
        }
        if let Some(value) = line.strip_prefix("CapEff:") {
            if capabilities.is_some() {
                return Err(io::ErrorKind::InvalidData.into());
            }
            capabilities = Some(
                u64::from_str_radix(value.trim(), 16).map_err(|_| io::ErrorKind::InvalidData)?,
            );
        }
    }
    let uid = uid.ok_or(io::ErrorKind::InvalidData)?;
    let capabilities = capabilities.ok_or(io::ErrorKind::InvalidData)?;
    Ok((uid, uid == 0 || capabilities != 0))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn kernel_start_ticks_allow_parentheses_in_command_and_reject_missing_identity() {
        let stat = format!("42 (a ) strange name) S {} 789 0", "0 ".repeat(18));
        assert_eq!(start_ticks(&stat).unwrap(), 789);
        assert!(start_ticks("42 (command) S 0").is_err());
    }

    #[test]
    fn credentials_require_all_uid_fields_and_no_ambiguous_duplicates() {
        assert_eq!(
            credentials("Uid:\t1000 1000 1000 1000\nCapEff:\t0000\n").unwrap(),
            (1000, false)
        );
        assert!(credentials("Uid: 1000 0 1000 1000\nCapEff: 0").is_err());
        assert!(credentials("Uid: 1000 1000 1000 1000\nCapEff: 0\nCapEff: 0").is_err());
        assert_eq!(credentials("Uid: 0 0 0 0\nCapEff: 0").unwrap(), (0, true));
    }

    #[test]
    fn held_pidfd_observes_child_exit_and_never_signals_a_reused_pid() {
        let mut child = std::process::Command::new("/bin/sleep")
            .arg("30")
            .spawn()
            .unwrap();
        let process = Process::open(child.id()).unwrap();
        assert!(process.alive().unwrap());
        assert!(process.identity().unwrap().created > 0);
        process.signal(libc::SIGTERM).unwrap();
        child.wait().unwrap();
        assert!(!process.alive().unwrap());
        assert!(process.signal(libc::SIGTERM).is_err());
        assert!(process.identity().is_err());
    }
}
