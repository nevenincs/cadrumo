//! What the system's user database records about this process's account.
//!
//! The database is asked through the C library, which consults whatever
//! directory service the system uses, so an account need not appear in
//! `/etc/passwd`.

use std::{
    ffi::{CStr, OsStr},
    io, mem,
    os::unix::ffi::OsStrExt,
    path::PathBuf,
    ptr,
};

/// The largest record buffer asked for before the lookup is refused.
const RECORD_LIMIT: usize = 1024 * 1024;

/// The login shell the user database records for this process's real account, or
/// `None` when the account has no entry or its entry names no shell.
pub fn current_login_shell() -> io::Result<Option<PathBuf>> {
    // SAFETY: getuid has no arguments and cannot fail.
    let uid = unsafe { libc::getuid() };
    login_shell(uid)
}

/// The login shell the user database records for `uid`, or `None` when the
/// account has no entry or its entry names no shell.
pub fn login_shell(uid: u32) -> io::Result<Option<PathBuf>> {
    // SAFETY: sysconf has no pointer arguments.
    let suggested = unsafe { libc::sysconf(libc::_SC_GETPW_R_SIZE_MAX) };
    let mut size = usize::try_from(suggested)
        .ok()
        .filter(|size| *size > 0)
        .unwrap_or(16 * 1024);
    loop {
        let mut buffer = vec![0 as libc::c_char; size];
        // SAFETY: passwd is plain data, valid when zeroed.
        let mut record: libc::passwd = unsafe { mem::zeroed() };
        let mut found: *mut libc::passwd = ptr::null_mut();
        // SAFETY: the record, buffer and result pointer are writable for the stated
        // sizes and outlive every read of the record below.
        let status = unsafe {
            libc::getpwuid_r(
                uid,
                &mut record,
                buffer.as_mut_ptr(),
                buffer.len(),
                &mut found,
            )
        };
        if status == libc::ERANGE && size < RECORD_LIMIT {
            size = (size * 2).min(RECORD_LIMIT);
            continue;
        }
        if status != 0 {
            return Err(io::Error::from_raw_os_error(status));
        }
        if found.is_null() || record.pw_shell.is_null() {
            return Ok(None);
        }
        // SAFETY: a terminated string inside `buffer`, which is still held.
        let shell = unsafe { CStr::from_ptr(record.pw_shell) }.to_bytes();
        if shell.is_empty() {
            return Ok(None);
        }
        return Ok(Some(PathBuf::from(OsStr::from_bytes(shell))));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::process::Command;

    #[test]
    fn the_login_shell_is_the_one_the_directory_service_records() {
        let name = Command::new("/usr/bin/id").arg("-un").output().unwrap();
        let name = String::from_utf8(name.stdout).unwrap();
        // An independent reader of the same directory service.
        #[cfg(target_os = "macos")]
        let recorded = {
            let output = Command::new("/usr/bin/dscacheutil")
                .args(["-q", "user", "-a", "name", name.trim()])
                .output()
                .unwrap();
            String::from_utf8(output.stdout)
                .unwrap()
                .lines()
                .find_map(|line| line.strip_prefix("shell: ").map(str::to_owned))
                .unwrap()
        };
        #[cfg(target_os = "linux")]
        let recorded = {
            let output = Command::new("/usr/bin/getent")
                .args(["passwd", name.trim()])
                .output()
                .unwrap();
            String::from_utf8(output.stdout)
                .unwrap()
                .trim()
                .rsplit(':')
                .next()
                .unwrap()
                .to_owned()
        };
        assert_eq!(
            current_login_shell().unwrap(),
            Some(PathBuf::from(recorded))
        );
    }

    #[test]
    fn an_account_without_an_entry_has_no_shell() {
        // Far above any account this system assigns; no entry names it.
        assert_eq!(login_shell(u32::MAX - 7).unwrap(), None);
    }
}
