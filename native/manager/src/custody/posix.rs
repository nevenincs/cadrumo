//! POSIX custody primitives: descriptor-relative, no-follow calls below a pinned parent.
//!
//! Every descriptor this module opens is wrapped in an [`OwnedFd`] at once, so it is
//! closed exactly once.
#![allow(unsafe_code)]

use super::{refused, staging_suffix, wait_for_lock};
use std::ffi::{CString, OsStr};
use std::fs::File;
use std::io::{self, Write};
use std::os::fd::{AsRawFd, FromRawFd, OwnedFd};
use std::os::unix::ffi::OsStrExt;
use std::os::unix::fs::MetadataExt;
use std::path::{Component, Path};
use std::time::Instant;

const DIRECTORY_FLAGS: libc::c_int =
    libc::O_RDONLY | libc::O_DIRECTORY | libc::O_NOFOLLOW | libc::O_CLOEXEC;
const RECORD_MODE: libc::c_uint = 0o600;
const DIRECTORY_MODE: libc::mode_t = 0o700;

/// The parent directory, opened by a walk that followed no link.
#[derive(Debug)]
pub(super) struct Anchor(OwnedFd);

/// The effective user of this process.
pub(crate) fn effective_uid() -> u32 {
    // SAFETY: geteuid takes no arguments and cannot fail.
    unsafe { libc::geteuid() }
}

fn c_name(name: &OsStr) -> io::Result<CString> {
    CString::new(name.as_bytes())
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "a name must not contain NUL"))
}

/// Open `name` below the directory descriptor `directory`.
fn open_at(
    directory: libc::c_int,
    name: &CString,
    flags: libc::c_int,
    mode: libc::c_uint,
) -> io::Result<OwnedFd> {
    // SAFETY: `name` is NUL-terminated and outlives the call; `directory` is an open
    // directory descriptor the caller holds. A non-negative result is a new descriptor
    // that nothing else owns.
    let descriptor = unsafe { libc::openat(directory, name.as_ptr(), flags, mode) };
    if descriptor < 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: as above; the OwnedFd becomes its only owner.
    Ok(unsafe { OwnedFd::from_raw_fd(descriptor) })
}

/// Walk an absolute directory one component at a time without following links.
pub(super) fn anchor(directory: &Path) -> io::Result<Anchor> {
    let root = c_name(OsStr::new("/"))?;
    // SAFETY: the path is NUL-terminated and outlives the call; a non-negative result is
    // a new descriptor that the OwnedFd below then owns alone.
    let descriptor = unsafe { libc::open(root.as_ptr(), DIRECTORY_FLAGS) };
    if descriptor < 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: as above.
    let mut current = unsafe { OwnedFd::from_raw_fd(descriptor) };
    for component in directory.components() {
        match component {
            Component::RootDir => {}
            Component::Normal(name) => {
                current = open_at(current.as_raw_fd(), &c_name(name)?, DIRECTORY_FLAGS, 0)?;
            }
            Component::Prefix(_) | Component::CurDir | Component::ParentDir => {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidInput,
                    "a custody directory path must be absolute and normalized",
                ));
            }
        }
    }
    Ok(Anchor(current))
}

fn regular(file: File) -> io::Result<File> {
    if !file.metadata()?.file_type().is_file() {
        return Err(refused("a custody record must be a regular file"));
    }
    Ok(file)
}

/// Open the lock leaf no-follow and take `flock`, retrying while another holder has it.
pub(super) fn acquire_lock(
    anchor: &Anchor,
    _path: &Path,
    name: &OsStr,
    deadline: Instant,
) -> io::Result<Option<File>> {
    let file = regular(File::from(open_at(
        anchor.0.as_raw_fd(),
        &c_name(name)?,
        libc::O_RDWR | libc::O_CREAT | libc::O_NOFOLLOW | libc::O_CLOEXEC,
        RECORD_MODE,
    )?))?;
    loop {
        match file.try_lock() {
            Ok(()) => return Ok(Some(file)),
            Err(std::fs::TryLockError::WouldBlock) => {}
            Err(std::fs::TryLockError::Error(error)) => return Err(error),
        }
        if !wait_for_lock(deadline) {
            return Ok(None);
        }
    }
}

fn open_existing(anchor: &Anchor, name: &CString, flags: libc::c_int) -> io::Result<Option<File>> {
    match open_at(anchor.0.as_raw_fd(), name, flags, 0) {
        Ok(descriptor) => regular(File::from(descriptor)).map(Some),
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(None),
        Err(error) => Err(error),
    }
}

/// Open a record no-follow for reading; `None` when it does not exist.
pub(super) fn open_record(anchor: &Anchor, _path: &Path, name: &OsStr) -> io::Result<Option<File>> {
    open_existing(
        anchor,
        &c_name(name)?,
        libc::O_RDONLY | libc::O_NOFOLLOW | libc::O_CLOEXEC,
    )
}

fn sync_directory(anchor: &Anchor) -> io::Result<()> {
    // SAFETY: the anchor descriptor is open for the duration of the call.
    if unsafe { libc::fsync(anchor.0.as_raw_fd()) } != 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

fn unlink_at(anchor: &Anchor, name: &CString) -> io::Result<()> {
    // SAFETY: the name is NUL-terminated and the anchor descriptor is open.
    if unsafe { libc::unlinkat(anchor.0.as_raw_fd(), name.as_ptr(), 0) } != 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

/// Stage `payload` as an exclusive sibling, sync it and rename it over the record.
pub(super) fn replace_record(
    anchor: &Anchor,
    _path: &Path,
    name: &OsStr,
    payload: &[u8],
) -> io::Result<()> {
    let mut staging_name = OsStr::new(".").to_os_string();
    staging_name.push(name);
    staging_name.push(".");
    staging_name.push(staging_suffix());
    let staging = c_name(&staging_name)?;
    let target = c_name(name)?;
    let mut file = File::from(open_at(
        anchor.0.as_raw_fd(),
        &staging,
        libc::O_WRONLY | libc::O_CREAT | libc::O_EXCL | libc::O_NOFOLLOW | libc::O_CLOEXEC,
        RECORD_MODE,
    )?);
    let published = file
        .write_all(payload)
        .and_then(|()| file.sync_all())
        .and_then(|()| {
            // SAFETY: both names are NUL-terminated and the anchor descriptor is open.
            let renamed = unsafe {
                libc::renameat(
                    anchor.0.as_raw_fd(),
                    staging.as_ptr(),
                    anchor.0.as_raw_fd(),
                    target.as_ptr(),
                )
            };
            if renamed != 0 {
                return Err(io::Error::last_os_error());
            }
            Ok(())
        });
    if let Err(error) = published {
        let _ = unlink_at(anchor, &staging);
        return Err(error);
    }
    sync_directory(anchor)
}

/// Remove a record after proving the name still holds the regular file opened first.
pub(super) fn clear_record(anchor: &Anchor, _path: &Path, name: &OsStr) -> io::Result<()> {
    let name = c_name(name)?;
    let flags = libc::O_RDONLY | libc::O_NOFOLLOW | libc::O_NONBLOCK | libc::O_CLOEXEC;
    let Some(opened) = open_existing(anchor, &name, flags)? else {
        return Ok(());
    };
    let Some(current) = open_existing(anchor, &name, flags)? else {
        return Ok(());
    };
    let (first, second) = (opened.metadata()?, current.metadata()?);
    if (first.dev(), first.ino()) != (second.dev(), second.ino()) {
        return Err(refused("a custody record changed identity before clear"));
    }
    unlink_at(anchor, &name)?;
    sync_directory(anchor)
}

/// Create the owner-only directory `name` below the anchor, accepting a real one.
pub(super) fn create_private_directory(
    anchor: &Anchor,
    _path: &Path,
    name: &OsStr,
) -> io::Result<()> {
    let name = c_name(name)?;
    // SAFETY: the name is NUL-terminated and the anchor descriptor is open.
    if unsafe { libc::mkdirat(anchor.0.as_raw_fd(), name.as_ptr(), DIRECTORY_MODE) } != 0 {
        let error = io::Error::last_os_error();
        if error.kind() != io::ErrorKind::AlreadyExists {
            return Err(error);
        }
    }
    open_at(anchor.0.as_raw_fd(), &name, DIRECTORY_FLAGS, 0).map(drop)
}
