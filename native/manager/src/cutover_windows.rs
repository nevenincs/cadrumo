//! Native evidence for a direct-child cutover, never process-name targeting.
#![allow(unsafe_code)]
use std::{
    ffi::c_void,
    io, mem,
    os::windows::io::{AsRawHandle, FromRawHandle, OwnedHandle},
    ptr,
};

type Handle = *mut c_void;
#[repr(C)]
struct ProcessEntry {
    size: u32,
    usage: u32,
    pid: u32,
    heap: usize,
    module: u32,
    threads: u32,
    parent: u32,
    priority: i32,
    flags: u32,
    image: [u16; 260],
}
#[link(name = "kernel32")]
unsafe extern "system" {
    fn CreateToolhelp32Snapshot(flags: u32, pid: u32) -> Handle;
    fn Process32FirstW(snapshot: Handle, entry: *mut ProcessEntry) -> i32;
    fn Process32NextW(snapshot: Handle, entry: *mut ProcessEntry) -> i32;
}
#[link(name = "bcrypt")]
unsafe extern "system" {
    fn BCryptGenRandom(algorithm: Handle, buffer: *mut u8, length: u32, flags: u32) -> i32;
}

pub fn nonce() -> io::Result<String> {
    let mut bytes = [0_u8; 16];
    // SAFETY: use the system-preferred cryptographic RNG with an exact writable buffer.
    if unsafe { BCryptGenRandom(ptr::null_mut(), bytes.as_mut_ptr(), 16, 2) } != 0 {
        return Err(io::Error::other("manager_cutover_random_unavailable"));
    }
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}

/// Snapshot only immediate child PIDs. The caller must retain the parent process
/// handle, then independently hold/verify every returned child before acting.
/// Enumeration is not authority; PID, parent PID and an executable basename alone
/// never authorize a stop. Called after successor exit to close the pre-report race.
pub fn children(parent: u32) -> io::Result<Vec<u32>> {
    // SAFETY: a read-only, noninheritable process-list snapshot, with no module/heap access.
    let raw = unsafe { CreateToolhelp32Snapshot(2, 0) };
    if raw as isize == -1 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: a successful snapshot handle has exactly this owner and closes on drop.
    let snapshot = unsafe { OwnedHandle::from_raw_handle(raw) };
    // SAFETY: unused PROCESSENTRY32W members are zero; dwSize advertises the ABI size.
    let mut entry: ProcessEntry = unsafe { mem::zeroed() };
    entry.size = mem::size_of::<ProcessEntry>() as u32;
    let mut found = Vec::new();
    // SAFETY: the owned snapshot and writable ABI-sized record live through enumeration.
    let mut present = unsafe { Process32FirstW(snapshot.as_raw_handle(), &mut entry) };
    for _ in 0..65536 {
        if present == 0 {
            let error = io::Error::last_os_error();
            return if error.raw_os_error() == Some(18) {
                Ok(found)
            } else {
                Err(error)
            };
        }
        if entry.parent == parent {
            found.push(entry.pid);
        }
        // SAFETY: the snapshot and the same writable record remain owned and alive.
        present = unsafe { Process32NextW(snapshot.as_raw_handle(), &mut entry) };
    }
    Err(io::Error::other("manager_process_inventory_limit"))
}

/// A held, natively verified immediate runtime child of the designated manager.
/// This is the only runtime process the cutover rollback is allowed to terminate.
pub struct RuntimeWitness {
    process: crate::supervision::process::RuntimeProcess,
    identity: crate::supervision::process::ProcessIdentity,
}
impl RuntimeWitness {
    pub fn hold(
        parent: u32,
        parent_created: u64,
        pid: u32,
        selected: &cadrumo_application::installation::Selection,
    ) -> io::Result<Self> {
        let opened = crate::supervision::process::open_process(pid)
            .map_err(|_| io::Error::from(io::ErrorKind::PermissionDenied))?;
        let image = crate::supervision::launch::runtime_image(&selected.package);
        // Holding the process before the snapshot prevents PID reuse during checks.
        if opened.identity.created < parent_created || !children(parent)?.contains(&pid) {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        crate::ipc::windows::verify_process(pid, &image)?;
        let identity = opened.identity.clone();
        Ok(Self {
            process: crate::supervision::process::RuntimeProcess::Adopted(opened),
            identity,
        })
    }
    pub fn pid(&self) -> u32 {
        self.identity.pid
    }
    pub fn ready(
        &mut self,
        root: &std::path::Path,
        selected: &cadrumo_application::installation::Selection,
    ) -> io::Result<()> {
        use crate::supervision::{boot_record::read_boot_record, protocol::Admission};
        let boot =
            read_boot_record(root).map_err(|_| io::Error::from(io::ErrorKind::InvalidData))?;
        let version = selected.version.map(|part| part.to_string()).join(".");
        if self.process.try_exit()?.is_some()
            || boot.pid != self.identity.pid
            || boot.process_created != self.identity.created
            || boot.version != version
            || boot.admission != Admission::Native
            || !boot
                .package_directory
                .as_ref()
                .is_some_and(|package| crate::ipc::windows::same_image(package, &selected.package))
        {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok(())
    }
    pub fn terminate(&mut self) -> io::Result<()> {
        if self.process.try_exit()?.is_none() {
            self.process.terminate()?;
        }
        Ok(())
    }
    pub fn ended(&mut self) -> io::Result<bool> {
        Ok(self.process.try_exit()?.is_some())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        os::windows::process::CommandExt,
        process::{Command, Stdio},
    };
    #[test]
    fn cryptographic_designation_and_native_direct_child_evidence() {
        let first = nonce().unwrap();
        assert_eq!(first.len(), 32);
        assert_ne!(first, nonce().unwrap());
        let image = std::path::PathBuf::from(std::env::var_os("SystemRoot").unwrap())
            .join("System32/cmd.exe");
        let mut child = Command::new(image)
            .args(["/D", "/Q", "/C", "pause"])
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .creation_flags(0x0800_0000)
            .spawn()
            .unwrap();
        let observed = children(std::process::id());
        let _ = child.kill();
        child.wait().unwrap();
        assert!(observed.unwrap().contains(&child.id()));
    }
}
