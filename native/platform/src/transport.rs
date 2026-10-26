//! Private Darwin transport directories, independent of the persistent data root.

use crate::{DARWIN_RUNTIME_SOCKET_DIRECTORY, POSIX_DIRECTORY_MODE, RUNTIME_SOCKET_PATH_LIMIT};
use std::{
    ffi::{CStr, CString},
    fs::{self, File},
    io,
    os::{
        fd::{AsRawFd, FromRawFd},
        unix::{ffi::OsStrExt, fs::MetadataExt},
    },
    path::{Component, Path, PathBuf},
    sync::{Mutex, OnceLock},
};

struct Directory {
    file: File,
    path: PathBuf,
}

impl Directory {
    fn open(path: &Path) -> io::Result<Self> {
        if !path.is_absolute() {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        // SAFETY: the constant is terminated; open returns a new owned descriptor.
        let raw = unsafe { libc::open(c"/".as_ptr(), directory_flags()) };
        let mut file = owned_file(raw)?;
        for component in path.components() {
            match component {
                Component::RootDir => {}
                Component::Normal(name) => {
                    let name =
                        CString::new(name.as_bytes()).map_err(|_| io::ErrorKind::InvalidInput)?;
                    // SAFETY: the parent is held and the leaf cannot follow a link.
                    file = owned_file(unsafe {
                        libc::openat(file.as_raw_fd(), name.as_ptr(), directory_flags())
                    })?;
                    let metadata = file.metadata()?;
                    // SAFETY: geteuid has no pointer arguments and cannot fail.
                    let uid = unsafe { libc::geteuid() };
                    if ![0, uid].contains(&metadata.uid())
                        || (metadata.mode() & 0o022 != 0 && metadata.mode() & 0o1000 == 0)
                    {
                        return Err(io::ErrorKind::PermissionDenied.into());
                    }
                }
                _ => return Err(io::ErrorKind::InvalidInput.into()),
            }
        }
        let directory = Self {
            file,
            path: path.to_owned(),
        };
        directory.private()?;
        Ok(directory)
    }

    fn private(&self) -> io::Result<()> {
        let metadata = self.file.metadata()?;
        // SAFETY: geteuid has no pointer arguments and cannot fail.
        let uid = unsafe { libc::geteuid() };
        if !metadata.is_dir()
            || metadata.uid() != uid
            || metadata.mode() & 0o7777 != POSIX_DIRECTORY_MODE
        {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok(())
    }

    fn verify(&self) -> io::Result<()> {
        self.private()?;
        let current = Self::open(&self.path)?;
        let held = self.file.metadata()?;
        let observed = current.file.metadata()?;
        if (held.dev(), held.ino()) != (observed.dev(), observed.ino()) {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok(())
    }

    fn retained(&self) -> io::Result<Self> {
        self.verify()?;
        Ok(Self {
            file: self.file.try_clone()?,
            path: self.path.clone(),
        })
    }
}

fn directory_flags() -> libc::c_int {
    libc::O_RDONLY | libc::O_DIRECTORY | libc::O_NOFOLLOW | libc::O_CLOEXEC
}

fn owned_file(raw: libc::c_int) -> io::Result<File> {
    if raw < 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: callers transfer one fresh successful open/openat descriptor.
    Ok(unsafe { File::from_raw_fd(raw) })
}

fn native_base() -> io::Result<&'static Directory> {
    static BASE: OnceLock<Result<Directory, (io::ErrorKind, String)>> = OnceLock::new();
    BASE.get_or_init(|| query_native_base().map_err(|error| (error.kind(), error.to_string())))
        .as_ref()
        .map_err(|(kind, message)| io::Error::new(*kind, message.clone()))
}

fn query_native_base() -> io::Result<Directory> {
    // The public query may materialize its OS-owned cache base. It has no TMPDIR fallback.
    // SAFETY: a null buffer with length zero queries the required buffer length.
    let length = unsafe { libc::confstr(libc::_CS_DARWIN_USER_CACHE_DIR, std::ptr::null_mut(), 0) };
    if length == 0 || length > libc::PATH_MAX as usize {
        return Err(io::ErrorKind::InvalidData.into());
    }
    let mut bytes = vec![0u8; length];
    // SAFETY: the buffer is writable for exactly length bytes, including the terminator.
    let actual = unsafe {
        libc::confstr(
            libc::_CS_DARWIN_USER_CACHE_DIR,
            bytes.as_mut_ptr().cast(),
            bytes.len(),
        )
    };
    if actual != length {
        return Err(io::ErrorKind::InvalidData.into());
    }
    let name = CStr::from_bytes_with_nul(&bytes).map_err(|_| io::ErrorKind::InvalidData)?;
    let name = name.to_str().map_err(|_| io::ErrorKind::InvalidData)?;
    let path = Path::new(name);
    if !path.is_absolute() {
        return Err(io::ErrorKind::InvalidData.into());
    }
    // Canonicalize only this OS-returned alias; every subsequent admission walks no-follow.
    Directory::open(&fs::canonicalize(path)?)
}

/// Retains both the OS cache base and the product directory. Never removes either.
pub struct DarwinTransport {
    base: Directory,
    directory: Directory,
}

impl DarwinTransport {
    /// Resolve the installed default. Passive clients do not create the product directory.
    pub fn installed(create: bool) -> io::Result<Self> {
        static PRODUCT: Mutex<Option<Directory>> = Mutex::new(None);
        Self::resolve(native_base()?, create, &PRODUCT)
    }

    fn resolve(
        base: &Directory,
        create: bool,
        retained: &Mutex<Option<Directory>>,
    ) -> io::Result<Self> {
        let mut retained = retained
            .lock()
            .map_err(|_| io::Error::other("transport namespace custody poisoned"))?;
        if let Some(directory) = retained.as_ref() {
            return Ok(Self {
                base: base.retained()?,
                directory: directory.retained()?,
            });
        }
        let resolved = Self::prepare(base, create)?;
        *retained = Some(resolved.directory.retained()?);
        Ok(resolved)
    }

    fn prepare(base: &Directory, create: bool) -> io::Result<Self> {
        let base = base.retained()?;
        let name = Path::new(DARWIN_RUNTIME_SOCKET_DIRECTORY);
        if name.components().count() != 1
            || !matches!(name.components().next(), Some(Component::Normal(_)))
        {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        let name = CString::new(DARWIN_RUNTIME_SOCKET_DIRECTORY)
            .map_err(|_| io::ErrorKind::InvalidInput)?;
        if create {
            // SAFETY: creation is relative to the retained base; the leaf is one component.
            let result = unsafe {
                libc::mkdirat(
                    base.file.as_raw_fd(),
                    name.as_ptr(),
                    POSIX_DIRECTORY_MODE as libc::mode_t,
                )
            };
            if result != 0 {
                let error = io::Error::last_os_error();
                if error.kind() != io::ErrorKind::AlreadyExists {
                    return Err(error);
                }
            }
        }
        // SAFETY: directory-only admission beneath the retained base without following a link.
        let file = owned_file(unsafe {
            libc::openat(base.file.as_raw_fd(), name.as_ptr(), directory_flags())
        })?;
        let directory = Directory {
            file,
            path: base.path.join(DARWIN_RUNTIME_SOCKET_DIRECTORY),
        };
        let result = Self { base, directory };
        result.verify()?;
        Ok(result)
    }

    pub fn directory(&self) -> &Path {
        &self.directory.path
    }

    pub fn verify(&self) -> io::Result<()> {
        self.base.verify()?;
        self.directory.verify()
    }

    pub fn socket_path(&self, name: &str) -> io::Result<PathBuf> {
        self.verify()?;
        let leaf = Path::new(name);
        if leaf.components().count() != 1
            || !matches!(leaf.components().next(), Some(Component::Normal(_)))
            || name.contains('\0')
        {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        let path = self.directory.path.join(leaf);
        if path.as_os_str().as_bytes().len() >= RUNTIME_SOCKET_PATH_LIMIT {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        Ok(path)
    }
}

#[cfg(test)]
mod tests;
