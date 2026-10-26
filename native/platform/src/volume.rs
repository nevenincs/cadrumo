//! Free space on the volume that holds a path.
//!
//! The component engine checks a setup's download against the space its storage root's
//! volume has left before any byte moves. The figure is what the calling user may still
//! write, after any quota the system applies to that user.
use std::{io, path::Path};

/// The bytes the calling user may still write on the volume holding `path`, which must
/// exist.
pub fn available_bytes(path: &Path) -> io::Result<u64> {
    imp::available_bytes(path)
}

#[cfg(windows)]
mod imp {
    use std::{io, os::windows::ffi::OsStrExt, path::Path, ptr};

    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn GetDiskFreeSpaceExW(
            directory: *const u16,
            free_to_caller: *mut u64,
            total: *mut u64,
            free: *mut u64,
        ) -> i32;
    }

    pub(super) fn available_bytes(path: &Path) -> io::Result<u64> {
        let mut wide: Vec<u16> = path.as_os_str().encode_wide().collect();
        if wide.contains(&0) {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        wide.push(0);
        let mut free_to_caller = 0u64;
        // SAFETY: `wide` is a NUL-terminated UTF-16 path with no interior NUL that lives
        // across the call. `free_to_caller` is one live, writable u64, which has the
        // layout of the ULARGE_INTEGER the call writes; the total and free outputs are
        // optional and passed as null, so the call writes nothing else.
        let succeeded = unsafe {
            GetDiskFreeSpaceExW(
                wide.as_ptr(),
                &mut free_to_caller,
                ptr::null_mut(),
                ptr::null_mut(),
            )
        };
        if succeeded == 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(free_to_caller)
    }
}

#[cfg(unix)]
mod imp {
    use std::{ffi::CString, io, mem::MaybeUninit, os::unix::ffi::OsStrExt, path::Path};

    pub(super) fn available_bytes(path: &Path) -> io::Result<u64> {
        let path = CString::new(path.as_os_str().as_bytes())
            .map_err(|_| io::Error::from(io::ErrorKind::InvalidInput))?;
        let mut stats = MaybeUninit::<libc::statvfs>::uninit();
        // SAFETY: `path` is NUL-terminated with no interior NUL and lives across the call;
        // `stats` is writable storage for exactly one `statvfs`, which the call fills on
        // success and leaves alone on failure.
        if unsafe { libc::statvfs(path.as_ptr(), stats.as_mut_ptr()) } != 0 {
            return Err(io::Error::last_os_error());
        }
        // SAFETY: the call succeeded, so it initialised every field of `stats`.
        let stats = unsafe { stats.assume_init() };
        // Blocks free to an unprivileged user, in fragment-size units.
        Ok(widened(stats.f_bavail).saturating_mul(widened(stats.f_frsize)))
    }

    /// The field types differ by platform, 32 or 64 bits wide; each fits in a u64.
    fn widened<T: Into<u64>>(value: T) -> u64 {
        value.into()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn an_existing_folder_has_space_and_a_missing_one_is_an_error() {
        let folder = std::env::temp_dir();
        assert!(available_bytes(&folder).unwrap() > 0);
        let missing = folder.join("cadrumo-volume-test-missing").join("below");
        assert!(available_bytes(&missing).is_err());
    }
}
