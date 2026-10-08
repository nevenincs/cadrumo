//! Darwin socket namespace and channel primitives; no session policy lives here.
#![allow(unsafe_code)]
use crate::custody::LocalLock;
use cadrumo_platform::transport::DarwinTransport;
use std::{
    ffi::CString,
    fs::File,
    io, mem,
    os::{
        fd::{AsRawFd, FromRawFd, OwnedFd},
        unix::{
            ffi::OsStrExt,
            fs::MetadataExt,
            net::{UnixListener, UnixStream},
        },
    },
    path::{Component, Path, PathBuf},
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
    time::Duration,
};
pub(super) fn effective_uid() -> u32 {
    // SAFETY: geteuid takes no pointers and cannot fail.
    unsafe { libc::geteuid() }
}

pub(super) struct Directory(File, PathBuf, Option<DarwinTransport>);

impl Directory {
    pub(super) fn open(path: &Path) -> io::Result<Self> {
        if !path.is_absolute() {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        // SAFETY: constant terminated path and directory-only, non-inheritable open.
        let raw = unsafe {
            libc::open(
                c"/".as_ptr(),
                libc::O_RDONLY | libc::O_DIRECTORY | libc::O_NOFOLLOW | libc::O_CLOEXEC,
            )
        };
        if raw < 0 {
            return Err(io::Error::last_os_error());
        }
        // SAFETY: open transferred this fresh descriptor.
        let mut current = unsafe { File::from_raw_fd(raw) };
        for component in path.components() {
            match component {
                Component::RootDir => {}
                Component::Normal(name) => {
                    let name =
                        CString::new(name.as_bytes()).map_err(|_| io::ErrorKind::InvalidInput)?;
                    // SAFETY: parent is retained; leaf cannot follow a link.
                    let raw = unsafe {
                        libc::openat(
                            current.as_raw_fd(),
                            name.as_ptr(),
                            libc::O_RDONLY | libc::O_DIRECTORY | libc::O_NOFOLLOW | libc::O_CLOEXEC,
                        )
                    };
                    if raw < 0 {
                        return Err(io::Error::last_os_error());
                    }
                    // SAFETY: openat transferred this fresh descriptor.
                    current = unsafe { File::from_raw_fd(raw) };
                }
                _ => return Err(io::ErrorKind::InvalidInput.into()),
            }
        }
        let metadata = current.metadata()?;
        if metadata.uid() != effective_uid() || metadata.mode() & 0o7777 != 0o700 {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok(Self(current, path.to_owned(), None))
    }

    pub(super) fn installed(create: bool) -> io::Result<Self> {
        let transport = DarwinTransport::installed(create)?;
        let mut directory = Self::open(transport.directory())?;
        directory.2 = Some(transport);
        directory.verify()?;
        Ok(directory)
    }

    fn verify(&self) -> io::Result<()> {
        if let Some(transport) = &self.2 {
            transport.verify()?;
        }
        let current = Self::open(&self.1)?;
        let before = self.0.metadata()?;
        let after = current.0.metadata()?;
        if (before.dev(), before.ino()) != (after.dev(), after.ino()) {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok(())
    }

    pub(super) fn leaf(&self, name: &str) -> PathBuf {
        self.1.join(name)
    }

    fn record(&self, name: &str) -> io::Result<libc::stat> {
        self.verify()?;
        let name = CString::new(name).map_err(|_| io::ErrorKind::InvalidInput)?;
        // SAFETY: stat is a plain output record; all bytes will be supplied by fstatat.
        let mut metadata: libc::stat = unsafe { mem::zeroed() };
        // SAFETY: retained directory, terminated leaf, valid output; no symlink traversal.
        if unsafe {
            libc::fstatat(
                self.0.as_raw_fd(),
                name.as_ptr(),
                &mut metadata,
                libc::AT_SYMLINK_NOFOLLOW,
            )
        } != 0
        {
            return Err(io::Error::last_os_error());
        }
        self.verify()?;
        Ok(metadata)
    }

    fn socket_record(&self, name: &str) -> io::Result<((u64, u64), u16)> {
        let metadata = self.record(name)?;
        if metadata.st_mode & libc::S_IFMT != libc::S_IFSOCK || metadata.st_uid != effective_uid() {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok((
            (metadata.st_dev as u64, metadata.st_ino),
            metadata.st_mode & 0o7777,
        ))
    }

    fn socket(&self, name: &str) -> io::Result<(u64, u64)> {
        Ok(self.socket_record(name)?.0)
    }

    pub(super) fn private_socket(&self, name: &str) -> io::Result<(u64, u64)> {
        let (identity, mode) = self.socket_record(name)?;
        if mode != 0o600 {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok(identity)
    }

    fn restrict(&self, name: &str, identity: (u64, u64)) -> io::Result<()> {
        if self.socket(name)? != identity {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        let leaf = CString::new(name).map_err(|_| io::ErrorKind::InvalidInput)?;
        // SAFETY: descriptor-relative mode change; leaf cannot follow a symbolic link.
        if unsafe {
            libc::fchmodat(
                self.0.as_raw_fd(),
                leaf.as_ptr(),
                0o600,
                libc::AT_SYMLINK_NOFOLLOW,
            )
        } != 0
        {
            return Err(io::Error::last_os_error());
        }
        if self.private_socket(name)? != identity {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok(())
    }

    fn remove(&self, name: &str, identity: (u64, u64)) -> io::Result<()> {
        if self.socket(name)? != identity {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        let name = CString::new(name).map_err(|_| io::ErrorKind::InvalidInput)?;
        // SAFETY: relative leaf under retained owner-only directory, checked above.
        if unsafe { libc::unlinkat(self.0.as_raw_fd(), name.as_ptr(), 0) } != 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }
}

pub(super) struct NamespaceClaim {
    lock: LocalLock,
    directory: Directory,
    name: String,
    identity: (u64, u64),
    binding: AtomicBool,
}

/// One binding attempt/listener per shared claim, including when its leaf disappears.
struct BindingLease(Arc<NamespaceClaim>);

impl Drop for BindingLease {
    fn drop(&mut self) {
        self.0.binding.store(false, Ordering::Release);
    }
}

impl NamespaceClaim {
    pub(super) fn acquire(
        directory: Directory,
        name: &str,
        patience: Duration,
    ) -> io::Result<Option<Arc<Self>>> {
        if name.is_empty() || name.contains(['/', '\0']) || name == "." || name == ".." {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        let path = directory.leaf(name);
        socket_address(&path)?;
        directory.verify()?;
        let Some(lock) = LocalLock::acquire(&directory.leaf(&format!("{name}.lock")), patience)?
        else {
            return Ok(None);
        };
        let metadata = lock.metadata()?;
        let claim = Arc::new(Self {
            lock,
            directory,
            name: name.to_owned(),
            identity: (metadata.dev(), metadata.ino()),
            binding: AtomicBool::new(false),
        });
        claim.verify()?;
        Ok(Some(claim))
    }

    pub(super) fn name(&self) -> &str {
        &self.name
    }

    fn reserve(self: &Arc<Self>) -> io::Result<BindingLease> {
        self.binding
            .compare_exchange(false, true, Ordering::Acquire, Ordering::Relaxed)
            .map_err(|_| io::ErrorKind::AddrInUse)?;
        Ok(BindingLease(Arc::clone(self)))
    }

    fn verify(&self) -> io::Result<()> {
        self.directory.verify()?;
        let held = self.lock.metadata()?;
        let current = self.directory.record(&format!("{}.lock", self.name))?;
        if !held.file_type().is_file()
            || held.uid() != effective_uid()
            || held.mode() & 0o7777 != 0o600
            || held.nlink() != 1
            || (held.dev(), held.ino()) != self.identity
            || current.st_mode & libc::S_IFMT != libc::S_IFREG
            || current.st_uid != effective_uid()
            || current.st_mode & 0o7777 != 0o600
            || current.st_nlink != 1
            || (current.st_dev as u64, current.st_ino) != self.identity
        {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        self.directory.verify()
    }
}

pub(super) struct Socket {
    pub(super) listener: UnixListener,
    claim: Arc<NamespaceClaim>,
    identity: (u64, u64),
    // Release only after Drop's inode cleanup and the listener descriptor close.
    _binding: BindingLease,
}

impl Socket {
    #[cfg(test)]
    pub(super) fn bind(path: &Path) -> io::Result<Self> {
        let directory = Directory::open(path.parent().ok_or(io::ErrorKind::InvalidInput)?)?;
        let name = path
            .file_name()
            .and_then(|name| name.to_str())
            .ok_or(io::ErrorKind::InvalidInput)?;
        let claim = NamespaceClaim::acquire(directory, name, Duration::ZERO)?
            .ok_or(io::ErrorKind::AddrInUse)?;
        Self::bind_claim(claim)
    }

    pub(super) fn bind_claim(claim: Arc<NamespaceClaim>) -> io::Result<Self> {
        let binding = claim.reserve()?;
        claim.verify()?;
        let anchored = claim.directory.leaf(&claim.name);
        match claim.directory.socket(&claim.name) {
            Ok(identity) => match connect_now(&anchored) {
                Err(error) if error.kind() == io::ErrorKind::ConnectionRefused => {
                    claim.verify()?;
                    claim.directory.remove(&claim.name, identity)?
                }
                _ => return Err(io::ErrorKind::AddrInUse.into()),
            },
            Err(error) if error.kind() == io::ErrorKind::NotFound => {}
            Err(error) => return Err(error),
        }
        claim.verify()?;
        let listener = UnixListener::bind(&anchored)?;
        let identity = claim.directory.socket(&claim.name)?;
        let socket = Self {
            listener,
            claim,
            identity,
            _binding: binding,
        };
        socket.claim.verify()?;
        socket
            .claim
            .directory
            .restrict(&socket.claim.name, socket.identity)?;
        socket.listener.set_nonblocking(true)?;
        socket.verify()?;
        Ok(socket)
    }

    pub(super) fn verify(&self) -> io::Result<()> {
        self.claim.verify()?;
        if self.claim.directory.private_socket(&self.claim.name)? != self.identity {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok(())
    }
}

impl Drop for Socket {
    fn drop(&mut self) {
        if self.claim.verify().is_ok() {
            let _ = self.claim.directory.remove(&self.claim.name, self.identity);
        }
    }
}

fn socket_address(path: &Path) -> io::Result<libc::sockaddr_un> {
    let bytes = path.as_os_str().as_bytes();
    // SAFETY: sockaddr_un is a plain C struct whose zero value is valid.
    let mut address: libc::sockaddr_un = unsafe { mem::zeroed() };
    if bytes.is_empty() || bytes.len() >= address.sun_path.len() || bytes.contains(&0) {
        return Err(io::ErrorKind::InvalidInput.into());
    }
    address.sun_family = libc::AF_UNIX as libc::sa_family_t;
    for (slot, byte) in address.sun_path.iter_mut().zip(bytes) {
        *slot = *byte as libc::c_char;
    }
    address.sun_len = mem::size_of_val(&address) as u8;
    Ok(address)
}

pub(super) fn connect_now(path: &Path) -> io::Result<UnixStream> {
    let address = socket_address(path)?;
    // SAFETY: no pointer arguments. Darwin descriptor flags are set by configure
    // immediately after creation, before connect; this is not atomic CLOEXEC.
    let raw = unsafe { libc::socket(libc::AF_UNIX, libc::SOCK_STREAM, 0) };
    if raw < 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: successful socket transfers this new descriptor.
    let descriptor = unsafe { OwnedFd::from_raw_fd(raw) };
    let stream = UnixStream::from(descriptor);
    configure(&stream)?;
    // SAFETY: address and exact C struct size remain valid throughout connect.
    if unsafe {
        libc::connect(
            stream.as_raw_fd(),
            (&address as *const libc::sockaddr_un).cast(),
            mem::size_of_val(&address) as libc::socklen_t,
        )
    } != 0
    {
        let error = io::Error::last_os_error();
        if error.raw_os_error() == Some(libc::EINPROGRESS) {
            return Err(io::ErrorKind::WouldBlock.into());
        }
        return Err(error);
    }
    Ok(stream)
}

pub(super) fn configure(stream: &UnixStream) -> io::Result<()> {
    stream.set_nonblocking(true)?;
    // SAFETY: live socket; FD_CLOEXEC changes only this retained descriptor.
    if unsafe { libc::fcntl(stream.as_raw_fd(), libc::F_SETFD, libc::FD_CLOEXEC) } < 0 {
        return Err(io::Error::last_os_error());
    }
    let enabled: libc::c_int = 1;
    // SAFETY: Darwin SO_NOSIGPIPE is per-socket, with an exact readable integer.
    if unsafe {
        libc::setsockopt(
            stream.as_raw_fd(),
            libc::SOL_SOCKET,
            libc::SO_NOSIGPIPE,
            (&enabled as *const libc::c_int).cast(),
            mem::size_of_val(&enabled) as libc::socklen_t,
        )
    } != 0
    {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::os::unix::fs::{PermissionsExt, symlink};
    use std::time::{SystemTime, UNIX_EPOCH};

    struct Scratch(PathBuf);
    impl Scratch {
        fn new() -> Self {
            let path = fs::canonicalize("/tmp").unwrap().join(format!(
                "cmipc-{}-{}",
                std::process::id(),
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            ));
            fs::create_dir(&path).unwrap();
            fs::set_permissions(&path, fs::Permissions::from_mode(0o700)).unwrap();
            Self(path)
        }
    }
    impl Drop for Scratch {
        fn drop(&mut self) {
            fs::remove_dir_all(&self.0).unwrap();
        }
    }

    fn claim(directory: &Path) -> Option<Arc<NamespaceClaim>> {
        NamespaceClaim::acquire(
            Directory::open(directory).unwrap(),
            "fixture.sock",
            Duration::ZERO,
        )
        .unwrap()
    }

    fn released_claim(
        directory: &Path,
        previous: std::sync::Weak<NamespaceClaim>,
    ) -> Arc<NamespaceClaim> {
        assert!(
            previous.upgrade().is_none(),
            "a Rust session/listener capability remains held"
        );
        // Other native tests spawn children concurrently. Darwin posix_spawn can
        // briefly retain the open-file description until its CLOEXEC processing;
        // final Rust ownership release does not prove that kernel reference ended.
        // Use the existing bounded lock wait only after proving our claim is gone.
        NamespaceClaim::acquire(
            Directory::open(directory).unwrap(),
            "fixture.sock",
            Duration::from_secs(1),
        )
        .unwrap()
        .expect("kernel lock remained held after all local capabilities were released")
    }

    #[test]
    fn session_and_listener_share_one_lock_until_the_last_owner_releases_it() {
        for session_first in [false, true] {
            let scratch = Scratch::new();
            let session = claim(&scratch.0).unwrap();
            let released = Arc::downgrade(&session);
            let original = session.lock.metadata().unwrap().ino();
            let listener = Socket::bind_claim(Arc::clone(&session)).unwrap();
            assert!(claim(&scratch.0).is_none());
            assert!(
                matches!(Socket::bind_claim(Arc::clone(&session)), Err(error) if error.kind() == io::ErrorKind::AddrInUse)
            );
            if session_first {
                drop(session);
                assert!(claim(&scratch.0).is_none());
                listener.verify().unwrap();
                drop(listener);
            } else {
                drop(listener);
                assert!(claim(&scratch.0).is_none());
                let rebound = Socket::bind_claim(Arc::clone(&session)).unwrap();
                drop(rebound);
                assert!(claim(&scratch.0).is_none());
                drop(session);
            }
            let next = released_claim(&scratch.0, released);
            assert_eq!(next.lock.metadata().unwrap().ino(), original);
            assert!(!scratch.0.join("fixture.sock").exists());
        }
    }

    #[test]
    fn failed_bind_keeps_the_session_claim_without_reacquiring_it() {
        let scratch = Scratch::new();
        let path = scratch.0.join("fixture.sock");
        let session = claim(&scratch.0).unwrap();
        let released = Arc::downgrade(&session);
        let other = UnixListener::bind(&path).unwrap();
        assert!(
            matches!(Socket::bind_claim(Arc::clone(&session)), Err(error) if error.kind() == io::ErrorKind::AddrInUse)
        );
        assert!(claim(&scratch.0).is_none());
        drop(other);
        fs::remove_file(&path).unwrap();
        drop(Socket::bind_claim(Arc::clone(&session)).unwrap());
        assert!(claim(&scratch.0).is_none());
        drop(session);
        drop(released_claim(&scratch.0, released));
    }

    #[test]
    fn removed_socket_leaf_does_not_allow_another_listener_on_the_shared_claim() {
        let scratch = Scratch::new();
        let session = claim(&scratch.0).unwrap();
        let socket = Socket::bind_claim(Arc::clone(&session)).unwrap();
        fs::remove_file(scratch.0.join("fixture.sock")).unwrap();
        assert!(
            matches!(Socket::bind_claim(Arc::clone(&session)), Err(error) if error.kind() == io::ErrorKind::AddrInUse)
        );
        drop(socket);
        drop(Socket::bind_claim(Arc::clone(&session)).unwrap());
    }

    #[test]
    fn lock_incarnation_links_and_mode_are_verified_before_bind_poll_and_cleanup() {
        for change in ["mode", "replacement", "symlink", "hardlink", "removed"] {
            let scratch = Scratch::new();
            let session = claim(&scratch.0).unwrap();
            let socket = Socket::bind_claim(Arc::clone(&session)).unwrap();
            let path = scratch.0.join("fixture.sock.lock");
            match change {
                "mode" => fs::set_permissions(&path, fs::Permissions::from_mode(0o660)).unwrap(),
                "replacement" => {
                    fs::rename(&path, scratch.0.join("old.lock")).unwrap();
                    fs::write(&path, b"replacement").unwrap();
                    fs::set_permissions(&path, fs::Permissions::from_mode(0o600)).unwrap();
                }
                "symlink" => {
                    fs::remove_file(&path).unwrap();
                    symlink(scratch.0.join("target"), &path).unwrap();
                }
                "hardlink" => fs::hard_link(&path, scratch.0.join("alias.lock")).unwrap(),
                "removed" => fs::remove_file(&path).unwrap(),
                _ => unreachable!(),
            }
            assert!(session.verify().is_err(), "{change}");
            assert!(socket.verify().is_err(), "{change}");
            assert!(
                Socket::bind_claim(Arc::clone(&session)).is_err(),
                "{change}"
            );
            drop(socket);
            assert!(
                scratch.0.join("fixture.sock").exists(),
                "cleanup must refuse lost custody: {change}"
            );
            if change == "removed" {
                assert!(!path.exists());
            } else if change == "mode" {
                assert_eq!(fs::metadata(&path).unwrap().mode() & 0o7777, 0o660);
            }
        }
    }

    #[test]
    fn preexisting_public_lock_is_refused_without_permission_repair() {
        let scratch = Scratch::new();
        let path = scratch.0.join("fixture.sock.lock");
        fs::write(&path, b"").unwrap();
        fs::set_permissions(&path, fs::Permissions::from_mode(0o644)).unwrap();
        assert!(
            NamespaceClaim::acquire(
                Directory::open(&scratch.0).unwrap(),
                "fixture.sock",
                Duration::ZERO
            )
            .is_err()
        );
        assert_eq!(fs::metadata(&path).unwrap().mode() & 0o7777, 0o644);
        assert!(!scratch.0.join("fixture.sock").exists());
    }

    #[test]
    fn private_socket_lifetime_reclaims_stale_and_never_displaces_a_live_owner() {
        let scratch = Scratch::new();
        let path = scratch.0.join("fixture.sock");
        let foreign_listener = UnixListener::bind(&path).unwrap();
        assert!(
            matches!(Socket::bind(&path), Err(error) if error.kind() == io::ErrorKind::AddrInUse)
        );
        assert!(path.exists());
        drop(foreign_listener);
        fs::remove_file(&path).unwrap();
        drop(UnixListener::bind(&path).unwrap());
        let socket = Socket::bind(&path).unwrap();
        assert!(path.exists());
        assert!(
            matches!(Socket::bind(&path), Err(error) if error.kind() == io::ErrorKind::AddrInUse)
        );
        let client = connect_now(&path).unwrap();
        let (server, _) = socket.listener.accept().unwrap();
        configure(&server).unwrap();
        assert_eq!(
            socket
                .claim
                .directory
                .private_socket(&socket.claim.name)
                .unwrap(),
            socket.identity
        );
        drop(client);
        let released = Arc::downgrade(&socket.claim);
        drop(socket);
        assert!(!path.exists());
        let replacement = Socket::bind_claim(released_claim(&scratch.0, released)).unwrap();
        drop(replacement);
    }

    #[test]
    fn cleanup_preserves_replaced_leaf_and_bind_refuses_links_or_public_directory() {
        let scratch = Scratch::new();
        let path = scratch.0.join("fixture.sock");
        let socket = Socket::bind(&path).unwrap();
        fs::remove_file(&path).unwrap();
        fs::write(&path, b"replacement").unwrap();
        drop(socket);
        assert_eq!(fs::read(&path).unwrap(), b"replacement");
        fs::remove_file(&path).unwrap();
        symlink(scratch.0.join("target"), &path).unwrap();
        assert!(Socket::bind(&path).is_err());
        fs::remove_file(&path).unwrap();
        let link = scratch.0.join("directory-link");
        symlink(&scratch.0, &link).unwrap();
        assert!(Socket::bind(&link.join("fixture.sock")).is_err());
        fs::set_permissions(&scratch.0, fs::Permissions::from_mode(0o755)).unwrap();
        assert!(
            matches!(Socket::bind(&path), Err(error) if error.kind() == io::ErrorKind::PermissionDenied)
        );
    }

    #[test]
    fn mode_and_namespace_replacement_are_rejected() {
        let scratch = Scratch::new();
        let directory = scratch.0.join("owner");
        fs::create_dir(&directory).unwrap();
        fs::set_permissions(&directory, fs::Permissions::from_mode(0o700)).unwrap();
        let path = directory.join("fixture.sock");
        let socket = Socket::bind(&path).unwrap();
        fs::set_permissions(&path, fs::Permissions::from_mode(0o660)).unwrap();
        assert_eq!(
            socket
                .claim
                .directory
                .private_socket(&socket.claim.name)
                .unwrap_err()
                .kind(),
            io::ErrorKind::PermissionDenied
        );
        let moved = scratch.0.join("moved");
        fs::rename(&directory, &moved).unwrap();
        fs::create_dir(&directory).unwrap();
        fs::set_permissions(&directory, fs::Permissions::from_mode(0o700)).unwrap();
        fs::write(&path, b"replacement").unwrap();
        assert!(socket.claim.directory.verify().is_err());
        drop(socket);
        assert_eq!(fs::read(&path).unwrap(), b"replacement");
        assert!(moved.join("fixture.sock").exists());
    }

    #[test]
    fn stream_is_nonblocking_noninherited_and_suppresses_sigpipe_locally() {
        use std::io::Write;
        let (mut stream, peer) = UnixStream::pair().unwrap();
        configure(&stream).unwrap();
        let mut enabled: libc::c_int = 0;
        let mut length = mem::size_of_val(&enabled) as libc::socklen_t;
        // SAFETY: retained socket, writable integer and its exact size.
        assert_eq!(
            unsafe {
                libc::getsockopt(
                    stream.as_raw_fd(),
                    libc::SOL_SOCKET,
                    libc::SO_NOSIGPIPE,
                    (&mut enabled as *mut libc::c_int).cast(),
                    &mut length,
                )
            },
            0
        );
        assert_eq!(enabled, 1);
        // SAFETY: read-only queries on this retained descriptor.
        assert_ne!(
            unsafe { libc::fcntl(stream.as_raw_fd(), libc::F_GETFL) } & libc::O_NONBLOCK,
            0
        );
        // SAFETY: read-only descriptor flags query.
        assert_ne!(
            unsafe { libc::fcntl(stream.as_raw_fd(), libc::F_GETFD) } & libc::FD_CLOEXEC,
            0
        );
        drop(peer);
        assert_eq!(
            stream.write(b"closed").unwrap_err().kind(),
            io::ErrorKind::BrokenPipe
        );
    }

    #[test]
    fn socket_address_refuses_nul_and_overlong_paths_before_binding() {
        assert!(socket_address(Path::new("/private/tmp/valid.sock")).is_ok());
        assert!(socket_address(Path::new(&"x".repeat(104))).is_err());
        assert!(socket_address(Path::new("/tmp/x\0y")).is_err());
    }
}
