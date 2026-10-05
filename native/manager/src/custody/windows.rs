//! Windows custody primitives, opening each file as the Python owner does.
//!
//! Plain opens go through the standard library with explicit access, sharing and flags. The
//! calls it does not offer, creating a directory with a security descriptor, renaming over
//! an existing record and deleting through a verified handle, are declared here. Every
//! handle is owned by a [`File`] at once, so it is closed exactly once.
#![allow(unsafe_code)]

use super::{refused, staging_suffix, wait_for_lock};
use std::ffi::{OsStr, c_void};
use std::fs::{File, OpenOptions};
use std::io::{self, Write};
use std::os::windows::ffi::OsStrExt;
use std::os::windows::fs::{MetadataExt, OpenOptionsExt};
use std::os::windows::io::AsRawHandle;
use std::path::{Component, Path, PathBuf};
use std::time::{Duration, Instant};

const GENERIC_READ: u32 = 0x8000_0000;
const DELETE: u32 = 0x0001_0000;
const FILE_SHARE_READ: u32 = 0x0000_0001;
const FILE_SHARE_WRITE: u32 = 0x0000_0002;
const FILE_FLAG_BACKUP_SEMANTICS: u32 = 0x0200_0000;
const FILE_FLAG_OPEN_REPARSE_POINT: u32 = 0x0020_0000;
const FILE_ATTRIBUTE_DIRECTORY: u32 = 0x0000_0010;
const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x0000_0400;
const ERROR_ACCESS_DENIED: i32 = 5;
const ERROR_SHARING_VIOLATION: i32 = 32;
const ERROR_LOCK_VIOLATION: i32 = 33;
const ERROR_ALREADY_EXISTS: i32 = 183;
const MOVEFILE_REPLACE_EXISTING: u32 = 0x0000_0001;
const FILE_DISPOSITION_INFO_CLASS: i32 = 4;
const SDDL_REVISION_1: u32 = 1;
/// What Python's `mkdir(mode=0o700)` applies on Windows: a protected list granting full
/// control to SYSTEM, Administrators and the owner, inherited by files and directories.
const PRIVATE_DIRECTORY_SDDL: &str = "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)";
/// How long a record replacement waits out readers holding the target open.
const REPLACE_BUDGET: Duration = Duration::from_secs(1);
const REPLACE_POLL: Duration = Duration::from_millis(10);

#[repr(C)]
struct SecurityAttributes {
    length: u32,
    descriptor: *mut c_void,
    inherit: i32,
}

#[link(name = "kernel32")]
unsafe extern "system" {
    fn CreateDirectoryW(path: *const u16, attributes: *const SecurityAttributes) -> i32;
    fn MoveFileExW(existing: *const u16, new: *const u16, flags: u32) -> i32;
    fn SetFileInformationByHandle(
        file: *mut c_void,
        class: i32,
        information: *const c_void,
        size: u32,
    ) -> i32;
    fn LocalFree(memory: *mut c_void) -> *mut c_void;
}

#[link(name = "advapi32")]
unsafe extern "system" {
    fn ConvertStringSecurityDescriptorToSecurityDescriptorW(
        text: *const u16,
        revision: u32,
        descriptor: *mut *mut c_void,
        size: *mut u32,
    ) -> i32;
}

/// Every component of a directory, held open without delete sharing, outermost first.
#[derive(Debug)]
pub(super) struct Anchor {
    _components: Vec<File>,
}

/// Pin `directory`: open every component below its root and verify it is a real directory.
///
/// Each component is opened without delete sharing, so none can be renamed, removed or
/// replaced by a link while the anchor lives. The final component is opened for reading.
pub(super) fn anchor(directory: &Path) -> io::Result<Anchor> {
    let normal = directory
        .components()
        .filter(|component| matches!(component, Component::Normal(_)))
        .count();
    let mut current = PathBuf::new();
    let mut held = Vec::with_capacity(normal);
    for component in directory.components() {
        match component {
            Component::Prefix(_) | Component::RootDir => current.push(component),
            Component::Normal(_) => {
                current.push(component);
                let access = if held.len() + 1 == normal {
                    GENERIC_READ
                } else {
                    0
                };
                held.push(open_directory(&current, access)?);
            }
            Component::CurDir | Component::ParentDir => {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidInput,
                    "a custody directory path must be normalized",
                ));
            }
        }
    }
    if held.is_empty() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "a custody directory must lie below a root",
        ));
    }
    Ok(Anchor { _components: held })
}

fn open_directory(path: &Path, access: u32) -> io::Result<File> {
    let directory = OpenOptions::new()
        .access_mode(access)
        .share_mode(FILE_SHARE_READ | FILE_SHARE_WRITE)
        .custom_flags(FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT)
        .open(path)?;
    let attributes = directory.metadata()?.file_attributes();
    if attributes & FILE_ATTRIBUTE_DIRECTORY == 0 || attributes & FILE_ATTRIBUTE_REPARSE_POINT != 0
    {
        return Err(refused(
            "a custody directory must not be a reparse point or non-directory",
        ));
    }
    Ok(directory)
}

/// Refuse a handle that names a directory or a reparse point rather than a regular file.
fn regular(file: File) -> io::Result<File> {
    let attributes = file.metadata()?.file_attributes();
    if attributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT) != 0 {
        return Err(refused(
            "a custody record must not be a reparse point or directory",
        ));
    }
    Ok(file)
}

/// Open the lock leaf for read and write with no sharing, retrying a held leaf.
pub(super) fn acquire_lock(
    _anchor: &Anchor,
    path: &Path,
    _name: &OsStr,
    deadline: Instant,
) -> io::Result<Option<File>> {
    loop {
        // OPEN_ALWAYS: one lock object, created once and never replaced.
        let opened = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .share_mode(0)
            .custom_flags(FILE_FLAG_OPEN_REPARSE_POINT)
            .open(path);
        match opened {
            Ok(file) => return regular(file).map(Some),
            Err(error)
                if matches!(
                    error.raw_os_error(),
                    Some(ERROR_SHARING_VIOLATION | ERROR_LOCK_VIOLATION)
                ) => {}
            Err(error) => return Err(error),
        }
        if !wait_for_lock(deadline) {
            return Ok(None);
        }
    }
}

/// Open a record for reading, sharing only read and write; `None` when it does not exist.
pub(super) fn open_record(
    _anchor: &Anchor,
    path: &Path,
    _name: &OsStr,
) -> io::Result<Option<File>> {
    let opened = OpenOptions::new()
        .read(true)
        .share_mode(FILE_SHARE_READ | FILE_SHARE_WRITE)
        .custom_flags(FILE_FLAG_OPEN_REPARSE_POINT)
        .open(path);
    match opened {
        Ok(file) => regular(file).map(Some),
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(None),
        Err(error) => Err(error),
    }
}

/// Stage `payload` beside the record and move it over the record.
pub(super) fn replace_record(
    _anchor: &Anchor,
    path: &Path,
    name: &OsStr,
    payload: &[u8],
) -> io::Result<()> {
    let mut staging_name = name.to_os_string();
    staging_name.push(".");
    staging_name.push(staging_suffix());
    let mut staging = Staging {
        path: path.with_file_name(staging_name),
        published: false,
    };
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .share_mode(0)
        .custom_flags(FILE_FLAG_OPEN_REPARSE_POINT)
        .open(&staging.path)?;
    file.write_all(payload)?;
    file.sync_all()?;
    drop(file);
    let deadline = Instant::now() + REPLACE_BUDGET;
    loop {
        match move_replacing(&staging.path, path) {
            Ok(()) => {
                staging.published = true;
                return Ok(());
            }
            // A reader's handle denies the replacement; a denying ACL looks the same, and
            // only the budget separates the two.
            Err(error)
                if matches!(
                    error.raw_os_error(),
                    Some(ERROR_ACCESS_DENIED | ERROR_SHARING_VIOLATION)
                ) && Instant::now() < deadline =>
            {
                std::thread::sleep(REPLACE_POLL);
            }
            Err(error) => return Err(error),
        }
    }
}

/// A staged sibling, removed unless it was published.
struct Staging {
    path: PathBuf,
    published: bool,
}

impl Drop for Staging {
    fn drop(&mut self) {
        if !self.published {
            let _ = std::fs::remove_file(&self.path);
        }
    }
}

/// Remove a record through a handle opened for delete and verified first.
pub(super) fn clear_record(_anchor: &Anchor, path: &Path, _name: &OsStr) -> io::Result<()> {
    // Readers and writers may share; nothing may delete or replace it meanwhile.
    let opened = OpenOptions::new()
        .access_mode(GENERIC_READ | DELETE)
        .share_mode(FILE_SHARE_READ | FILE_SHARE_WRITE)
        .custom_flags(FILE_FLAG_OPEN_REPARSE_POINT)
        .open(path);
    let file = match opened {
        Ok(file) => regular(file)?,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(()),
        Err(error) => return Err(error),
    };
    let delete: u8 = 1;
    // SAFETY: the handle is open with DELETE access for the duration of the call, and the
    // information is one BOOLEAN local, exactly the size of FILE_DISPOSITION_INFO.
    let marked = unsafe {
        SetFileInformationByHandle(
            file.as_raw_handle().cast(),
            FILE_DISPOSITION_INFO_CLASS,
            (&raw const delete).cast(),
            1,
        )
    };
    if marked == 0 {
        return Err(io::Error::last_os_error());
    }
    // The record is removed when this, its only handle with delete access, closes.
    drop(file);
    Ok(())
}

/// Create `path` with the owner-only security Python's `mkdir(mode=0o700)` applies.
pub(super) fn create_private_directory(
    _anchor: &Anchor,
    path: &Path,
    _name: &OsStr,
) -> io::Result<()> {
    let descriptor = SecurityDescriptor::from_sddl(PRIVATE_DIRECTORY_SDDL)?;
    let attributes = SecurityAttributes {
        length: u32::try_from(size_of::<SecurityAttributes>()).map_err(io::Error::other)?,
        descriptor: descriptor.0,
        inherit: 0,
    };
    let wide = wide_path(path)?;
    // SAFETY: the path is NUL-terminated and the attributes and their descriptor outlive
    // the call, which only reads them.
    let created = unsafe { CreateDirectoryW(wide.as_ptr(), &attributes) };
    if created == 0 {
        let error = io::Error::last_os_error();
        if error.raw_os_error() != Some(ERROR_ALREADY_EXISTS) {
            return Err(error);
        }
    }
    // An existing entry is accepted only when it is a real directory.
    anchor(path).map(drop)
}

/// Rename `existing` over `new`, as Python's `os.replace` does on Windows.
fn move_replacing(existing: &Path, new: &Path) -> io::Result<()> {
    let existing = wide_path(existing)?;
    let new = wide_path(new)?;
    // SAFETY: both paths are NUL-terminated buffers that outlive the call.
    if unsafe { MoveFileExW(existing.as_ptr(), new.as_ptr(), MOVEFILE_REPLACE_EXISTING) } == 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

fn wide_path(path: &Path) -> io::Result<Vec<u16>> {
    let wide: Vec<u16> = path.as_os_str().encode_wide().collect();
    if wide.contains(&0) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "a custody path must not contain NUL",
        ));
    }
    Ok(wide.into_iter().chain([0]).collect())
}

/// A security descriptor the system allocated with `LocalAlloc`, released on drop.
struct SecurityDescriptor(*mut c_void);

impl SecurityDescriptor {
    fn from_sddl(sddl: &str) -> io::Result<Self> {
        let text: Vec<u16> = sddl.encode_utf16().chain([0]).collect();
        let mut descriptor = std::ptr::null_mut();
        // SAFETY: the SDDL text is NUL-terminated and outlives the call, which writes one
        // LocalAlloc descriptor pointer into the local that `Self` then owns.
        let converted = unsafe {
            ConvertStringSecurityDescriptorToSecurityDescriptorW(
                text.as_ptr(),
                SDDL_REVISION_1,
                &mut descriptor,
                std::ptr::null_mut(),
            )
        };
        if converted == 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(Self(descriptor))
    }
}

impl Drop for SecurityDescriptor {
    fn drop(&mut self) {
        // SAFETY: the pointer came from the SDDL conversion, which documents LocalAlloc
        // memory, and is released only here.
        unsafe {
            LocalFree(self.0);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_private_directory_security_is_what_python_applies() {
        // Parsing proves the text is a valid descriptor; the conformance test compares the
        // security of a directory each side created.
        assert!(SecurityDescriptor::from_sddl(PRIVATE_DIRECTORY_SDDL).is_ok());
        assert!(SecurityDescriptor::from_sddl("not a descriptor").is_err());
    }
}
