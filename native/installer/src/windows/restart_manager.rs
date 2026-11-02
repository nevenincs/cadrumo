//! Read-only Restart Manager file-use evidence.
use super::{result, wide};
use crate::admission::{MAX_PRODUCTS, Refusal};
use std::{path::PathBuf, ptr};

const ERROR_MORE_DATA: u32 = 234;

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct FileTime {
    low: u32,
    high: u32,
}
#[repr(C)]
#[derive(Clone, Copy, Default)]
struct UniqueProcess {
    pid: u32,
    started: FileTime,
}
#[repr(C)]
#[derive(Clone, Copy)]
struct ProcessInfo {
    process: UniqueProcess,
    name: [u16; 256],
    service: [u16; 64],
    kind: i32,
    status: u32,
    session: u32,
    restartable: i32,
}
#[link(name = "rstrtmgr")]
unsafe extern "system" {
    fn RmStartSession(session: *mut u32, flags: u32, key: *mut u16) -> u32;
    fn RmEndSession(session: u32) -> u32;
    fn RmRegisterResources(
        session: u32,
        files: u32,
        paths: *const *const u16,
        applications: u32,
        processes: *const UniqueProcess,
        services: u32,
        names: *const *const u16,
    ) -> u32;
    fn RmGetList(
        session: u32,
        needed: *mut u32,
        count: *mut u32,
        processes: *mut ProcessInfo,
        reboot: *mut u32,
    ) -> u32;
}
struct RestartSession(u32);
impl Drop for RestartSession {
    fn drop(&mut self) {
        // SAFETY: The wrapper owns exactly one successful Restart Manager session.
        unsafe {
            RmEndSession(self.0);
        }
    }
}

#[derive(Debug, PartialEq, Eq)]
pub struct FileUse {
    pub pid: u32,
    pub creation_time: u64,
    pub session: u32,
}

/// Read-only supplementary evidence. The caller must already exclude new launches
/// and hold the version lease. An empty list alone never authorizes removal.
/// No shutdown, restart, process termination or reboot API is imported.
pub fn file_users(files: &[PathBuf]) -> Result<Vec<FileUse>, Refusal> {
    if files.is_empty() || files.len() > MAX_PRODUCTS {
        return Err(Refusal::InvalidRequest);
    }
    let names = files
        .iter()
        .map(|path| {
            if !path.is_absolute() {
                return Err(Refusal::InvalidRequest);
            }
            wide(path.to_str().ok_or(Refusal::InvalidRequest)?)
        })
        .collect::<Result<Vec<_>, _>>()?;
    let mut id = 0;
    let mut key = [0; 33];
    // SAFETY: Both outputs are writable with the documented key capacity.
    result(unsafe { RmStartSession(&mut id, 0, key.as_mut_ptr()) })?;
    let session = RestartSession(id);
    for chunk in names.chunks(256) {
        let paths = chunk.iter().map(|name| name.as_ptr()).collect::<Vec<_>>();
        // SAFETY: Every pointer addresses a live terminated path for this synchronous call.
        result(unsafe {
            RmRegisterResources(
                session.0,
                paths.len() as u32,
                paths.as_ptr(),
                0,
                ptr::null(),
                0,
                ptr::null(),
            )
        })?;
    }
    let mut capacity = 0;
    for _ in 0..4 {
        let mut needed = 0;
        let mut count = capacity;
        let mut reboot = 0;
        let mut processes = Vec::<ProcessInfo>::with_capacity(capacity as usize);
        // SAFETY: The vector reserves count records; set_len follows only a successful
        // call whose returned count fits that reservation. Null is valid for count zero.
        let status = unsafe {
            RmGetList(
                session.0,
                &mut needed,
                &mut count,
                if capacity == 0 {
                    ptr::null_mut()
                } else {
                    processes.as_mut_ptr()
                },
                &mut reboot,
            )
        };
        if reboot != 0 {
            return Err(Refusal::IncompleteInventory);
        }
        if status == ERROR_MORE_DATA {
            if needed == 0 || needed > 4096 {
                return Err(Refusal::IncompleteInventory);
            }
            capacity = needed;
            continue;
        }
        result(status)?;
        if count > capacity {
            return Err(Refusal::IncompleteInventory);
        }
        // SAFETY: Successful RmGetList initialized exactly count records in allocated storage.
        unsafe {
            processes.set_len(count as usize);
        }
        return Ok(processes
            .into_iter()
            .map(|p| FileUse {
                pid: p.process.pid,
                creation_time: (u64::from(p.process.started.high) << 32)
                    | u64::from(p.process.started.low),
                session: p.session,
            })
            .collect());
    }
    Err(Refusal::IncompleteInventory)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn live_restart_manager_inspects_an_unused_file_without_mutating_it() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("unowned.txt");
        std::fs::write(&path, b"retained").unwrap();
        assert_eq!(file_users(std::slice::from_ref(&path)), Ok(vec![]));
        assert_eq!(std::fs::read(&path).unwrap(), b"retained");
        assert_eq!(file_users(&[]), Err(Refusal::InvalidRequest));
        assert_eq!(
            file_users(&[PathBuf::from("relative")]),
            Err(Refusal::InvalidRequest)
        );
    }
}
