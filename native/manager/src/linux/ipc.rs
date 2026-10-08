//! Owner/session-qualified Unix sockets for the closed manager protocol.
#![allow(unsafe_code)]

use super::{
    login::Login,
    process::{Identity, Process},
};
use crate::{
    custody::{LocalLock, effective_uid},
    ipc::{
        Request, Response, decode,
        framing::{Frame, encode, write_some},
    },
    session::ManagerSession,
};
use std::{
    ffi::CString,
    fs::{self, File},
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
    thread,
    time::{Duration, Instant},
};

const TIMEOUT: Duration = Duration::from_secs(2);
const POLL: Duration = Duration::from_millis(10);

/// The caller supplies the canonical runtime socket directory, never a storage override.
pub fn endpoint(directory: &Path, session: &ManagerSession) -> io::Result<PathBuf> {
    if !directory.is_absolute() || session.user.parse::<u32>().ok() != Some(effective_uid()) {
        return Err(io::ErrorKind::InvalidInput.into());
    }
    for part in [
        crate::identity::MANAGER_ID,
        session.user.as_str(),
        session.session.as_str(),
    ] {
        if part.is_empty()
            || part.len() > 128
            || !part
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'-' | b'_'))
        {
            return Err(io::ErrorKind::InvalidInput.into());
        }
    }
    Ok(directory.join(format!(
        "{}.{}.session.{}.sock",
        crate::identity::MANAGER_ID,
        session.user,
        session.session
    )))
}

struct Directory(File);

impl Directory {
    fn open(path: &Path) -> io::Result<Self> {
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
        if metadata.uid() != effective_uid() || metadata.mode() & 0o077 != 0 {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok(Self(current))
    }

    fn leaf(&self, name: &str) -> PathBuf {
        PathBuf::from(format!("/proc/self/fd/{}", self.0.as_raw_fd())).join(name)
    }

    fn socket(&self, name: &str) -> io::Result<(u64, u64)> {
        use std::os::unix::fs::FileTypeExt;
        let metadata = fs::symlink_metadata(self.leaf(name))?;
        if !metadata.file_type().is_socket() || metadata.uid() != effective_uid() {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok((metadata.dev(), metadata.ino()))
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

struct Socket {
    listener: UnixListener,
    directory: Directory,
    name: String,
    identity: (u64, u64),
    _lock: LocalLock,
}

impl Socket {
    fn bind(path: &Path) -> io::Result<Self> {
        let directory = Directory::open(path.parent().ok_or(io::ErrorKind::InvalidInput)?)?;
        let name = path
            .file_name()
            .and_then(|name| name.to_str())
            .ok_or(io::ErrorKind::InvalidInput)?
            .to_owned();
        // The canonical no-follow custody path pins its own parent. Recheck its identity
        // against our socket anchor before using the lock to reclaim a stale leaf.
        let lock =
            LocalLock::acquire(&path.with_file_name(format!("{name}.lock")), Duration::ZERO)?
                .ok_or(io::ErrorKind::AddrInUse)?;
        if lock.metadata()?.uid() != effective_uid() {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        let check = Directory::open(path.parent().ok_or(io::ErrorKind::InvalidInput)?)?;
        if (directory.0.metadata()?.dev(), directory.0.metadata()?.ino())
            != (check.0.metadata()?.dev(), check.0.metadata()?.ino())
        {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        let anchored = directory.leaf(&name);
        match directory.socket(&name) {
            Ok(identity) => match connect_now(&anchored) {
                Err(error) if error.kind() == io::ErrorKind::ConnectionRefused => {
                    directory.remove(&name, identity)?
                }
                _ => return Err(io::ErrorKind::AddrInUse.into()),
            },
            Err(error) if error.kind() == io::ErrorKind::NotFound => {}
            Err(error) => return Err(error),
        }
        let listener = UnixListener::bind(&anchored)?;
        let identity = directory.socket(&name)?;
        let socket = Self {
            listener,
            directory,
            name,
            identity,
            _lock: lock,
        };
        socket.listener.set_nonblocking(true)?;
        Ok(socket)
    }
}

impl Drop for Socket {
    fn drop(&mut self) {
        let _ = self.directory.remove(&self.name, self.identity);
    }
}

struct Peer {
    process: Process,
    identity: Identity,
}

impl Peer {
    fn inspect(
        stream: &UnixStream,
        session: &ManagerSession,
        images: &[PathBuf],
    ) -> io::Result<Self> {
        let process = Process::peer(stream)?;
        let identity = process.identity()?;
        if identity.privileged
            || identity.uid.to_string() != session.user
            || !images.contains(&identity.image)
        {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        let peer = Self { process, identity };
        peer.revalidate(session)?;
        Ok(peer)
    }

    fn revalidate(&self, session: &ManagerSession) -> io::Result<()> {
        let login = Login::open()?.session(&self.process)?;
        if login.id != session.session
            || login.uid.to_string() != session.user
            || login.closing
            || self.process.identity()? != self.identity
        {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok(())
    }
}

enum State {
    Reading {
        stream: UnixStream,
        peer: Peer,
        frame: Frame,
        deadline: Instant,
    },
    Writing {
        stream: UnixStream,
        peer: Peer,
        bytes: Vec<u8>,
        written: usize,
        deadline: Instant,
    },
}

/// One bounded connection at a time; polling never waits for socket I/O.
pub struct Server {
    socket: Socket,
    state: Option<State>,
    session: ManagerSession,
    images: Vec<PathBuf>,
    manager: PathBuf,
    owner: Peer,
}

impl Server {
    /// Package admission and the session lock precede this call.
    pub fn bind_installed(
        directory: &Path,
        package: &Path,
        _session_lock: &crate::session::instance::SessionLock,
    ) -> io::Result<Self> {
        let contract: cadrumo_application::installation::DiscoveryContract =
            serde_json::from_str(crate::contract::INSTALLATION_CONTRACT)
                .map_err(io::Error::other)?;
        let manager = fs::canonicalize(
            contract
                .manager_member()
                .map_err(io::Error::other)?
                .under(package),
        )?;
        if manager != fs::canonicalize(std::env::current_exe()?)? {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        let mut images = vec![manager.clone()];
        for image in contract
            .layout
            .application_images
            .iter()
            .filter(|image| image.target == "desktop-host-build")
        {
            if image.placement != "." {
                return Err(io::ErrorKind::InvalidData.into());
            }
            let member = cadrumo_application::value::RelativePath::new(format!(
                "{}{}",
                image.name, contract.layout.entrypoint_suffix
            ))
            .map_err(io::Error::other)?;
            let path = member.under(package);
            if path.is_file() {
                images.push(fs::canonicalize(path)?);
            }
        }
        let session = ManagerSession::current()?;
        let process = Process::open(std::process::id())?;
        let owner = Peer {
            identity: process.identity()?,
            process,
        };
        owner.revalidate(&session)?;
        let socket = Socket::bind(&endpoint(directory, &session)?)?;
        Ok(Self {
            socket,
            state: None,
            session,
            images,
            manager,
            owner,
        })
    }

    /// The held peer is exposed to cutover admission; a request PID is never authority.
    pub fn poll(
        &mut self,
        mut handle: impl FnMut(&Process, Request) -> Response,
    ) -> io::Result<()> {
        self.owner.revalidate(&self.session)?;
        for _ in 0..4 {
            if self.state.is_none() {
                let (stream, _) = match self.socket.listener.accept() {
                    Ok(connection) => connection,
                    Err(error)
                        if matches!(
                            error.kind(),
                            io::ErrorKind::WouldBlock | io::ErrorKind::Interrupted
                        ) =>
                    {
                        break;
                    }
                    Err(error) => return Err(error),
                };
                stream.set_nonblocking(true)?;
                let Ok(peer) = Peer::inspect(&stream, &self.session, &self.images) else {
                    continue;
                };
                self.state = Some(State::Reading {
                    stream,
                    peer,
                    frame: Frame::new(),
                    deadline: Instant::now() + TIMEOUT,
                });
            }
            let state = self.state.take().ok_or(io::ErrorKind::BrokenPipe)?;
            match self.advance(state, &mut handle) {
                Ok((next, progressed)) => {
                    self.state = next;
                    if !progressed {
                        break;
                    }
                }
                Err(_) => break,
            }
        }
        Ok(())
    }

    fn advance(
        &self,
        state: State,
        handle: &mut impl FnMut(&Process, Request) -> Response,
    ) -> io::Result<(Option<State>, bool)> {
        match state {
            State::Reading {
                mut stream,
                peer,
                mut frame,
                deadline,
            } => {
                if Instant::now() >= deadline {
                    return Err(io::ErrorKind::TimedOut.into());
                }
                peer.revalidate(&self.session)?;
                let Some(bytes) = frame.read(&mut stream)? else {
                    return Ok((
                        Some(State::Reading {
                            stream,
                            peer,
                            frame,
                            deadline,
                        }),
                        false,
                    ));
                };
                let request = decode(&bytes)?;
                if matches!(request, Request::SuccessorReady { .. })
                    && peer.identity.image != self.manager
                {
                    return Err(io::ErrorKind::PermissionDenied.into());
                }
                peer.revalidate(&self.session)?;
                let response = handle(&peer.process, request);
                let bytes = encode(&serde_json::to_vec(&response).map_err(io::Error::other)?)?;
                Ok((
                    Some(State::Writing {
                        stream,
                        peer,
                        bytes,
                        written: 0,
                        deadline,
                    }),
                    true,
                ))
            }
            State::Writing {
                mut stream,
                peer,
                bytes,
                mut written,
                deadline,
            } => {
                if Instant::now() >= deadline {
                    return Err(io::ErrorKind::TimedOut.into());
                }
                peer.revalidate(&self.session)?;
                if write_some(&mut stream, &bytes, &mut written)? {
                    Ok((None, true))
                } else {
                    Ok((
                        Some(State::Writing {
                            stream,
                            peer,
                            bytes,
                            written,
                            deadline,
                        }),
                        false,
                    ))
                }
            }
        }
    }
}

fn connect_now(path: &Path) -> io::Result<UnixStream> {
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
    // SAFETY: no pointer arguments; flags require atomic noninheritance and nonblocking I/O.
    let raw = unsafe {
        libc::socket(
            libc::AF_UNIX,
            libc::SOCK_STREAM | libc::SOCK_NONBLOCK | libc::SOCK_CLOEXEC,
            0,
        )
    };
    if raw < 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: successful socket transfers this new descriptor.
    let descriptor = unsafe { OwnedFd::from_raw_fd(raw) };
    // SAFETY: address and exact C struct size remain valid throughout connect.
    if unsafe {
        libc::connect(
            descriptor.as_raw_fd(),
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
    Ok(UnixStream::from(descriptor))
}

/// Bounded client exchange; authenticate the manager before transmitting a request.
pub fn request(directory: &Path, manager: &Path, request: &Request) -> io::Result<Response> {
    let session = ManagerSession::current()?;
    let path = endpoint(directory, &session)?;
    let directory = Directory::open(directory)?;
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or(io::ErrorKind::InvalidInput)?;
    let identity = directory.socket(name)?;
    let deadline = Instant::now() + TIMEOUT;
    let mut stream = loop {
        match connect_now(&directory.leaf(name)) {
            Ok(stream) => break stream,
            Err(error) if error.kind() == io::ErrorKind::WouldBlock => {}
            Err(error) => return Err(error),
        }
        if Instant::now() >= deadline {
            return Err(io::ErrorKind::TimedOut.into());
        }
        thread::sleep(POLL);
    };
    if directory.socket(name)? != identity {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    let peer = Peer::inspect(&stream, &session, &[fs::canonicalize(manager)?])?;
    let bytes = serde_json::to_vec(request).map_err(io::Error::other)?;
    decode(&bytes)?;
    let bytes = encode(&bytes)?;
    let mut written = 0;
    let mut frame = Frame::new();
    loop {
        if Instant::now() >= deadline {
            return Err(io::ErrorKind::TimedOut.into());
        }
        peer.revalidate(&session)?;
        if written != bytes.len() {
            write_some(&mut stream, &bytes, &mut written)?;
        } else if let Some(bytes) = frame.read(&mut stream)? {
            peer.revalidate(&session)?;
            let response: Response = serde_json::from_slice(&bytes).map_err(io::Error::other)?;
            if response.schema != 1 {
                return Err(io::ErrorKind::InvalidData.into());
            }
            return Ok(response);
        }
        thread::sleep(POLL);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::{PermissionsExt, symlink};
    use std::time::{SystemTime, UNIX_EPOCH};

    struct Scratch(PathBuf);
    impl Scratch {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!(
                "cadrumo-ipc-{}-{}",
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
        assert_eq!(Process::peer(&server).unwrap().pid(), std::process::id());
        drop(client);
        drop(socket);
        assert!(!path.exists());
        let replacement = Socket::bind(&path).unwrap();
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
    fn native_peer_is_not_admitted_by_an_image_match_without_owner_session_evidence() {
        let (stream, _other) = UnixStream::pair().unwrap();
        let session = ManagerSession {
            user: "invalid-owner".into(),
            session: "invented".into(),
        };
        assert!(
            matches!(Peer::inspect(&stream, &session, &[std::env::current_exe().unwrap()]), Err(error) if error.kind() == io::ErrorKind::PermissionDenied)
        );
    }

    #[test]
    fn endpoint_uses_native_owner_session_and_refuses_path_components() {
        let session = ManagerSession {
            user: effective_uid().to_string(),
            session: "c42".into(),
        };
        let path = endpoint(Path::new("/run/user/1000"), &session).unwrap();
        assert!(path.to_str().unwrap().ends_with(".session.c42.sock"));
        assert!(endpoint(Path::new("relative"), &session).is_err());
        let forged = ManagerSession {
            session: "../elsewhere".into(),
            ..session
        };
        assert!(endpoint(Path::new("/run/user/1000"), &forged).is_err());
    }
}
