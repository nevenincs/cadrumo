//! Read-only SCM custody and bounded stop of an exactly verified product service.
#![allow(unsafe_code)]

use super::{expand, wide};
use crate::admission::Refusal;
use cadrumo_application::value::Sha256Digest;
use serde::Deserialize;
use std::{
    collections::BTreeMap,
    path::{Path, PathBuf},
    ptr,
    time::{Duration, Instant},
};
use windows_sys::Win32::{
    Foundation::*,
    System::{Services::*, Threading::*},
};

#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Description {
    component: String,
    pub name: String,
    binary: String,
    arguments: String,
    account: String,
    start: String,
}
impl Description {
    pub(super) fn validate(
        &self,
        application: &str,
        components: &[String],
        files: &BTreeMap<String, Sha256Digest>,
    ) -> Result<(), Refusal> {
        if self.name != format!("{application}.manager")
            || !components.contains(&self.component)
            || !self.binary.starts_with("[INSTALL_ROOT]")
            || !files.contains_key(self.binary.trim_start_matches("[INSTALL_ROOT]"))
            || self.arguments != "--service"
            || self.account != "LocalSystem"
            || self.start != "auto"
        {
            return Err(Refusal::InvalidRequest);
        }
        wide(&self.name)?;
        Ok(())
    }
}
struct Handle(SC_HANDLE);
impl Drop for Handle {
    fn drop(&mut self) {
        unsafe {
            CloseServiceHandle(self.0);
        }
    }
}
fn service(name: &str, access: u32) -> Result<Option<Handle>, Refusal> {
    // SAFETY: local SCM connection; no database mutation is requested.
    let scm = unsafe { OpenSCManagerW(ptr::null(), ptr::null(), SC_MANAGER_CONNECT) };
    if scm.is_null() {
        return Err(Refusal::NativeFailure);
    }
    let scm = Handle(scm);
    let name = wide(name)?;
    // SAFETY: retained SCM connection and terminated bounded name.
    let handle = unsafe { OpenServiceW(scm.0, name.as_ptr(), access) };
    if handle.is_null() {
        if unsafe { GetLastError() } == ERROR_SERVICE_DOES_NOT_EXIST {
            return Ok(None);
        }
        return Err(Refusal::NativeFailure);
    }
    Ok(Some(Handle(handle)))
}
unsafe fn text(value: *const u16, buffer: &[usize]) -> Result<String, Refusal> {
    if value.is_null() {
        return Err(Refusal::IncompleteInventory);
    }
    let start = buffer.as_ptr() as usize;
    let end = start + size_of_val(buffer);
    let pointer = value as usize;
    if pointer < start || pointer >= end || !pointer.is_multiple_of(2) {
        return Err(Refusal::IncompleteInventory);
    }
    let maximum = (end - pointer) / 2;
    let mut length = 0;
    // SAFETY: pointer and bounded string extent lie within successful native query output.
    while length < maximum && unsafe { *value.add(length) } != 0 {
        length += 1;
    }
    if length == maximum {
        return Err(Refusal::IncompleteInventory);
    }
    String::from_utf16(unsafe { std::slice::from_raw_parts(value, length) })
        .map_err(|_| Refusal::IncompleteInventory)
}
fn verified(handle: &Handle, expected: &Description, prefix: &Path) -> Result<(), Refusal> {
    let mut needed = 0;
    // SAFETY: size-only SCM query.
    unsafe {
        QueryServiceConfigW(handle.0, ptr::null_mut(), 0, &mut needed);
    }
    if needed < size_of::<QUERY_SERVICE_CONFIGW>() as u32 || needed > 65536 {
        return Err(Refusal::IncompleteInventory);
    }
    let mut buffer = vec![0_usize; (needed as usize).div_ceil(size_of::<usize>())];
    // SAFETY: pointer-aligned native output buffer has requested capacity.
    if unsafe { QueryServiceConfigW(handle.0, buffer.as_mut_ptr().cast(), needed, &mut needed) }
        == 0
    {
        return Err(Refusal::NativeFailure);
    }
    let config = unsafe { &*buffer.as_ptr().cast::<QUERY_SERVICE_CONFIGW>() };
    let binary = unsafe { text(config.lpBinaryPathName, &buffer) }?;
    let account = unsafe { text(config.lpServiceStartName, &buffer) }?;
    let image = expand(&expected.binary, prefix)?;
    let expected_binary = format!("\"{image}\" {}", expected.arguments);
    let unquoted_binary = format!("{image} {}", expected.arguments);
    let valid_binary = binary == expected_binary
        || (!image.chars().any(char::is_whitespace) && binary == unquoted_binary);
    if config.dwServiceType != SERVICE_WIN32_OWN_PROCESS
        || config.dwStartType != SERVICE_AUTO_START
        || config.dwErrorControl != SERVICE_ERROR_NORMAL
        || account != expected.account
        || !valid_binary
    {
        return Err(Refusal::IncompleteInventory);
    }
    Ok(())
}
fn status(handle: &Handle) -> Result<SERVICE_STATUS_PROCESS, Refusal> {
    let mut state: SERVICE_STATUS_PROCESS = unsafe { std::mem::zeroed() };
    let mut needed = 0;
    // SAFETY: exact native service process status output structure.
    if unsafe {
        QueryServiceStatusEx(
            handle.0,
            SC_STATUS_PROCESS_INFO,
            (&mut state as *mut SERVICE_STATUS_PROCESS).cast(),
            size_of_val(&state) as u32,
            &mut needed,
        )
    } == 0
    {
        return Err(Refusal::NativeFailure);
    }
    Ok(state)
}
pub fn verify(expected: &Description, prefix: &Path) -> Result<(), Refusal> {
    let handle = service(&expected.name, SERVICE_QUERY_CONFIG | SERVICE_QUERY_STATUS)?
        .ok_or(Refusal::IncompleteInventory)?;
    verified(&handle, expected, prefix)
}

pub fn verify_running(expected: &Description, prefix: &Path) -> Result<(), Refusal> {
    let handle = service(&expected.name, SERVICE_QUERY_CONFIG | SERVICE_QUERY_STATUS)?
        .ok_or(Refusal::IncompleteInventory)?;
    verified(&handle, expected, prefix)?;
    // A configured but failed/stopped broker is not a healthy installed registration.
    if status(&handle)?.dwCurrentState != SERVICE_RUNNING {
        return Err(Refusal::IncompleteInventory);
    }
    Ok(())
}
pub fn verify_absent(name: &str) -> Result<(), Refusal> {
    if service(name, SERVICE_QUERY_CONFIG)?.is_some() {
        return Err(Refusal::IncompleteInventory);
    }
    Ok(())
}
/// Restore availability after a failed maintenance transaction; never recreate a service.
pub struct RestartGuard {
    expected: Description,
    prefix: PathBuf,
    restore: bool,
}
impl RestartGuard {
    /// Settle explicitly so the maintenance receipt can report restoration failures.
    pub fn restore(&mut self) -> Result<(), Refusal> {
        if !std::mem::take(&mut self.restore) {
            return Ok(());
        }
        start_existing(&self.expected, &self.prefix)
    }
}
impl Drop for RestartGuard {
    fn drop(&mut self) {
        if self.restore {
            let _ = start_existing(&self.expected, &self.prefix);
        }
    }
}
/// Start only an already configured, custody-verified service; never register one.
pub(crate) fn start_existing(expected: &Description, prefix: &Path) -> Result<(), Refusal> {
    let Some(handle) = service(
        &expected.name,
        SERVICE_QUERY_CONFIG | SERVICE_QUERY_STATUS | SERVICE_START,
    )?
    else {
        return Ok(());
    };
    verified(&handle, expected, prefix)?;
    let deadline = Instant::now() + Duration::from_secs(10);
    // A previous bounded stop may still be settling. Do not start through STOP_PENDING.
    loop {
        match status(&handle)?.dwCurrentState {
            SERVICE_RUNNING => return Ok(()),
            SERVICE_STOPPED => break,
            SERVICE_STOP_PENDING | SERVICE_START_PENDING if Instant::now() < deadline => {
                std::thread::sleep(Duration::from_millis(100));
            }
            _ => return Err(Refusal::NativeFailure),
        }
    }
    // SAFETY: exact preexisting verified configuration; no arguments or new registration.
    if unsafe { StartServiceW(handle.0, 0, ptr::null()) } == 0
        && unsafe { GetLastError() } != ERROR_SERVICE_ALREADY_RUNNING
    {
        return Err(Refusal::NativeFailure);
    }
    while Instant::now() < deadline {
        if status(&handle)?.dwCurrentState == SERVICE_RUNNING {
            return Ok(());
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    Err(Refusal::NativeFailure)
}
pub fn stop(
    expected: &Description,
    prefix: &Path,
    held: &mut Vec<RestartGuard>,
) -> Result<(), Refusal> {
    held.push(RestartGuard {
        expected: expected.clone(),
        prefix: prefix.to_path_buf(),
        restore: false,
    });
    let guard = held.last_mut().expect("just retained restoration guard");
    let Some(handle) = service(
        &expected.name,
        SERVICE_QUERY_CONFIG | SERVICE_QUERY_STATUS | SERVICE_STOP,
    )?
    else {
        return Ok(());
    };
    verified(&handle, expected, prefix)?;
    let initial = status(&handle)?;
    if initial.dwCurrentState == SERVICE_STOPPED {
        return Ok(());
    }
    guard.restore = true;
    // Retain the process incarnation before cooperative stop; a recycled numeric PID
    // must never grant permission to terminate another process after the deadline.
    let process = unsafe {
        OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE | PROCESS_SYNCHRONIZE,
            0,
            initial.dwProcessId,
        )
    };
    if process.is_null() {
        return Err(Refusal::NativeFailure);
    }
    struct Process(HANDLE);
    impl Drop for Process {
        fn drop(&mut self) {
            unsafe {
                CloseHandle(self.0);
            }
        }
    }
    let process = Process(process);
    let mut image = vec![0_u16; 32768];
    let mut length = image.len() as u32;
    // SAFETY: retained process handle; writable bounded image-path buffer.
    if unsafe { QueryFullProcessImageNameW(process.0, 0, image.as_mut_ptr(), &mut length) } == 0 {
        return Err(Refusal::NativeFailure);
    }
    let image =
        String::from_utf16(&image[..length as usize]).map_err(|_| Refusal::IncompleteInventory)?;
    let expected_image = expand(&expected.binary, prefix)?;
    if std::fs::canonicalize(image).map_err(|_| Refusal::IncompleteInventory)?
        != std::fs::canonicalize(expected_image).map_err(|_| Refusal::IncompleteInventory)?
        || status(&handle)?.dwProcessId != initial.dwProcessId
    {
        return Err(Refusal::IncompleteInventory);
    }
    let mut acknowledged: SERVICE_STATUS = unsafe { std::mem::zeroed() };
    // SAFETY: verified exact product service; normal SCM stop precedes escalation.
    if unsafe { ControlService(handle.0, SERVICE_CONTROL_STOP, &mut acknowledged) } == 0
        && unsafe { GetLastError() } != ERROR_SERVICE_NOT_ACTIVE
    {
        return Err(Refusal::NativeFailure);
    }
    let deadline = Instant::now() + Duration::from_secs(15);
    while Instant::now() < deadline {
        if status(&handle)?.dwCurrentState == SERVICE_STOPPED {
            return Ok(());
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    if status(&handle)?.dwProcessId != initial.dwProcessId {
        return Err(Refusal::InUse);
    }
    // SAFETY: exact retained, image-verified service process; cooperative stop timed out.
    if unsafe { TerminateProcess(process.0, 1) } == 0 {
        return Err(Refusal::NativeFailure);
    }
    let deadline = Instant::now() + Duration::from_secs(5);
    while Instant::now() < deadline {
        if status(&handle)?.dwCurrentState == SERVICE_STOPPED {
            return Ok(());
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    Err(Refusal::InUse)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn absent_product_service_is_observed_without_registration() {
        let name = format!("cadrumo.test.absent.{}", std::process::id());
        verify_absent(&name).unwrap();
        let expected = Description {
            component: String::new(),
            name: name.clone(),
            binary: "[INSTALL_ROOT]absent.exe".into(),
            arguments: "--service".into(),
            account: "LocalSystem".into(),
            start: "auto".into(),
        };
        // Restoration must not resurrect a removed service, nor certify absent repair.
        start_existing(&expected, Path::new("C:\\")).unwrap();
        assert!(verify_running(&expected, Path::new("C:\\")).is_err());
        verify_absent(&name).unwrap();
    }
}
