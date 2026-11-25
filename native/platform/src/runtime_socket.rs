//! The client side of the runtime's local stream socket, without its protocol.
//!
//! A runtime owns one socket per storage root, named after the root's physical
//! identity, inside a private per-account namespace. This module connects to
//! such a socket, refuses an entry that is not the runtime's own, verifies
//! that the process on the other end is a live process of the same account,
//! and moves bytes across it under absolute deadlines. A close from any thread
//! ends every pending transfer. Frames, the handshake and every request belong
//! to the caller. Nothing here listens, starts or stops anything.

use crate::runtime_connect::ConnectRefusal;
use std::{
    fs, io, mem,
    os::{
        fd::{AsRawFd, FromRawFd, OwnedFd, RawFd},
        unix::fs::{FileTypeExt, MetadataExt},
    },
    path::{Path, PathBuf},
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    time::{Duration, Instant},
};

/// How long a refused connection waits before it is attempted again. Some kernels
/// refuse a listener whose queue is full, so a refusal alone does not prove absence.
const REFUSED_RETRY: Duration = Duration::from_millis(25);

/// The physical identity of a storage root, which names its runtime's socket.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StorageIdentity {
    pub uid: u32,
    pub dev: u64,
    pub ino: u64,
}

impl StorageIdentity {
    /// The text the runtime hashes into its storage identity.
    pub fn text(&self) -> String {
        format!("{}:{}:{}", self.uid, self.dev, self.ino)
    }
}

/// This process's real account id, the one the runtime's peer checks compare.
pub fn current_uid() -> u32 {
    // SAFETY: getuid has no arguments and cannot fail.
    unsafe { libc::getuid() }
}

/// Reads the identity of the existing directory `root` names, through any links,
/// and refuses one this account does not own.
pub fn storage_identity(root: &Path) -> io::Result<StorageIdentity> {
    let metadata = fs::metadata(fs::canonicalize(root)?)?;
    let uid = current_uid();
    if !metadata.is_dir() || metadata.uid() != uid {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    Ok(StorageIdentity {
        uid,
        dev: metadata.dev(),
        ino: metadata.ino(),
    })
}

/// The private directory a runtime publishes its entry in, rechecked on every use.
pub(crate) trait Namespace {
    /// The path of the entry `leaf` inside the namespace, once the namespace verifies.
    fn socket_path(&self, leaf: &str) -> io::Result<PathBuf>;
    /// Whether the namespace is still the private directory first admitted.
    fn verify(&self) -> io::Result<()>;
}

#[cfg(target_os = "macos")]
impl Namespace for crate::transport::DarwinTransport {
    fn socket_path(&self, leaf: &str) -> io::Result<PathBuf> {
        crate::transport::DarwinTransport::socket_path(self, leaf)
    }

    fn verify(&self) -> io::Result<()> {
        crate::transport::DarwinTransport::verify(self)
    }
}

/// The process behind a connected socket, read from the kernel, never from the wire.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Peer {
    pub process_id: u32,
    pub owner_uid: u32,
}

fn last_error() -> io::Error {
    io::Error::last_os_error()
}

fn owned(raw: RawFd) -> io::Result<OwnedFd> {
    if raw < 0 {
        return Err(last_error());
    }
    // SAFETY: callers transfer one fresh descriptor this process now owns.
    Ok(unsafe { OwnedFd::from_raw_fd(raw) })
}

fn configure(descriptor: &OwnedFd) -> io::Result<()> {
    let raw = descriptor.as_raw_fd();
    // SAFETY: live owned descriptor; only its descriptor and status flags change.
    unsafe {
        if libc::fcntl(raw, libc::F_SETFD, libc::FD_CLOEXEC) < 0 {
            return Err(last_error());
        }
        let flags = libc::fcntl(raw, libc::F_GETFL);
        if flags < 0 || libc::fcntl(raw, libc::F_SETFL, flags | libc::O_NONBLOCK) < 0 {
            return Err(last_error());
        }
    }
    Ok(())
}

/// An owned, persistent cancellation signal, registered before connecting. Once
/// cancelled it stays cancelled, and every wait that observes it ends.
#[derive(Debug)]
pub struct ConnectCancellation {
    cancelled: AtomicBool,
    readable: OwnedFd,
    writable: OwnedFd,
}

impl ConnectCancellation {
    pub fn new() -> io::Result<Self> {
        let mut ends = [0 as libc::c_int; 2];
        // SAFETY: pipe writes exactly two descriptors into the local array.
        if unsafe { libc::pipe(ends.as_mut_ptr()) } != 0 {
            return Err(last_error());
        }
        let readable = owned(ends[0]);
        let writable = owned(ends[1]);
        let (readable, writable) = (readable?, writable?);
        configure(&readable)?;
        configure(&writable)?;
        Ok(Self {
            cancelled: AtomicBool::new(false),
            readable,
            writable,
        })
    }

    pub fn cancel(&self) {
        if self.cancelled.swap(true, Ordering::AcqRel) {
            return;
        }
        let byte = 1u8;
        // SAFETY: one byte from a local into this owned, non-blocking pipe. The pipe is
        // never drained, so it stays readable for every later wait.
        unsafe {
            libc::write(self.writable.as_raw_fd(), (&byte as *const u8).cast(), 1);
        }
    }

    pub fn cancelled(&self) -> bool {
        self.cancelled.load(Ordering::Acquire)
    }
}

/// Waits until `descriptor` reports `events`, the deadline passes (`TimedOut`) or the
/// cancellation fires (`ConnectionAborted`). No deadline waits for as long as it takes.
fn wait(
    descriptor: RawFd,
    events: libc::c_short,
    deadline: Option<Instant>,
    cancellation: &ConnectCancellation,
) -> io::Result<()> {
    loop {
        if cancellation.cancelled() {
            return Err(io::ErrorKind::ConnectionAborted.into());
        }
        let timeout = match deadline {
            None => -1,
            Some(end) => match end.checked_duration_since(Instant::now()) {
                Some(remaining) if !remaining.is_zero() => {
                    remaining.as_millis().clamp(1, i32::MAX as u128) as libc::c_int
                }
                _ => return Err(io::ErrorKind::TimedOut.into()),
            },
        };
        let mut descriptors = [
            libc::pollfd {
                fd: descriptor,
                events,
                revents: 0,
            },
            libc::pollfd {
                fd: cancellation.readable.as_raw_fd(),
                events: libc::POLLIN,
                revents: 0,
            },
        ];
        // SAFETY: two initialized pollfd records for descriptors held by the caller.
        let ready = unsafe { libc::poll(descriptors.as_mut_ptr(), 2, timeout) };
        if ready < 0 {
            let error = last_error();
            if error.kind() == io::ErrorKind::Interrupted {
                continue;
            }
            return Err(error);
        }
        if descriptors[1].revents != 0 || cancellation.cancelled() {
            return Err(io::ErrorKind::ConnectionAborted.into());
        }
        if descriptors[0].revents & (events | libc::POLLHUP | libc::POLLERR | libc::POLLNVAL) != 0 {
            return Ok(());
        }
    }
}

fn socket_address(path: &Path) -> io::Result<(libc::sockaddr_un, libc::socklen_t)> {
    use std::os::unix::ffi::OsStrExt;
    // SAFETY: sockaddr_un is plain data, valid when zeroed.
    let mut address: libc::sockaddr_un = unsafe { mem::zeroed() };
    let bytes = path.as_os_str().as_bytes();
    if bytes.len() >= address.sun_path.len() || bytes.contains(&0) {
        return Err(io::ErrorKind::InvalidInput.into());
    }
    address.sun_family = libc::AF_UNIX as libc::sa_family_t;
    for (target, byte) in address.sun_path.iter_mut().zip(bytes) {
        *target = *byte as libc::c_char;
    }
    #[cfg(target_os = "macos")]
    {
        address.sun_len = mem::size_of::<libc::sockaddr_un>() as u8;
    }
    Ok((
        address,
        mem::size_of::<libc::sockaddr_un>() as libc::socklen_t,
    ))
}

fn stream_socket() -> io::Result<OwnedFd> {
    // SAFETY: creates one new descriptor, owned immediately below.
    let descriptor = owned(unsafe { libc::socket(libc::AF_UNIX, libc::SOCK_STREAM, 0) })?;
    configure(&descriptor)?;
    #[cfg(target_os = "macos")]
    {
        let enabled: libc::c_int = 1;
        // SAFETY: SO_NOSIGPIPE is per-socket, with an exact readable integer.
        if unsafe {
            libc::setsockopt(
                descriptor.as_raw_fd(),
                libc::SOL_SOCKET,
                libc::SO_NOSIGPIPE,
                (&enabled as *const libc::c_int).cast(),
                mem::size_of_val(&enabled) as libc::socklen_t,
            )
        } != 0
        {
            return Err(last_error());
        }
    }
    Ok(descriptor)
}

fn socket_error(descriptor: &OwnedFd) -> io::Result<()> {
    let mut code: libc::c_int = 0;
    let mut size = mem::size_of_val(&code) as libc::socklen_t;
    // SAFETY: an exact writable integer for SO_ERROR on a live socket.
    if unsafe {
        libc::getsockopt(
            descriptor.as_raw_fd(),
            libc::SOL_SOCKET,
            libc::SO_ERROR,
            (&mut code as *mut libc::c_int).cast(),
            &mut size,
        )
    } != 0
    {
        return Err(last_error());
    }
    if code != 0 {
        return Err(io::Error::from_raw_os_error(code));
    }
    Ok(())
}

/// One connection attempt; `Ok(None)` is a refusal worth retrying.
fn attempt(
    path: &Path,
    deadline: Instant,
    cancellation: &ConnectCancellation,
) -> Result<Option<OwnedFd>, ConnectRefusal> {
    let descriptor = stream_socket().map_err(ConnectRefusal::Failed)?;
    let (address, length) = socket_address(path).map_err(|_| ConnectRefusal::EndpointUntrusted)?;
    // SAFETY: a complete local address for this owned socket.
    let result = unsafe {
        libc::connect(
            descriptor.as_raw_fd(),
            (&address as *const libc::sockaddr_un).cast(),
            length,
        )
    };
    let outcome = if result == 0 {
        Ok(())
    } else {
        let error = last_error();
        match error.raw_os_error() {
            Some(libc::EINPROGRESS | libc::EAGAIN | libc::EINTR) => {
                wait(
                    descriptor.as_raw_fd(),
                    libc::POLLOUT,
                    Some(deadline),
                    cancellation,
                )
                .map_err(|error| match error.kind() {
                    io::ErrorKind::TimedOut => ConnectRefusal::Deadline,
                    io::ErrorKind::ConnectionAborted => ConnectRefusal::Cancelled,
                    _ => ConnectRefusal::Failed(error),
                })?;
                socket_error(&descriptor)
            }
            _ => Err(error),
        }
    };
    match outcome {
        Ok(()) => Ok(Some(descriptor)),
        Err(error) => match error.raw_os_error() {
            Some(libc::ENOENT) => Err(ConnectRefusal::NotReady),
            Some(libc::ECONNREFUSED) => Ok(None),
            _ => Err(ConnectRefusal::EndpointUntrusted),
        },
    }
}

/// The runtime's entry: a socket this account owns, never followed through a link.
fn owned_entry(path: &Path, expected_uid: u32) -> Result<(u64, u64), ConnectRefusal> {
    match fs::symlink_metadata(path) {
        Ok(metadata) if metadata.file_type().is_socket() && metadata.uid() == expected_uid => {
            Ok((metadata.dev(), metadata.ino()))
        }
        Ok(_) => Err(ConnectRefusal::EndpointUntrusted),
        Err(error) if error.kind() == io::ErrorKind::NotFound => Err(ConnectRefusal::NotReady),
        Err(_) => Err(ConnectRefusal::EndpointUntrusted),
    }
}

#[cfg(target_os = "macos")]
fn socket_record<const N: usize>(descriptor: RawFd, option: libc::c_int) -> io::Result<[u8; N]> {
    let mut bytes = [0u8; N];
    let mut size = N as libc::socklen_t;
    // SAFETY: an exact writable record for this local-socket option on a live socket.
    if unsafe { libc::getsockopt(descriptor, 0, option, bytes.as_mut_ptr().cast(), &mut size) } != 0
    {
        return Err(last_error());
    }
    if size as usize != N {
        return Err(io::ErrorKind::InvalidData.into());
    }
    Ok(bytes)
}

/// The words of a kernel audit token: auid, euid, egid, ruid, rgid, pid, asid, pidversion.
#[cfg(target_os = "macos")]
pub(crate) fn audit_token_peer(token: &[u8; 32], reported_pid: i32, owner: u32) -> Option<Peer> {
    let word = |index: usize| {
        u32::from_ne_bytes([
            token[index * 4],
            token[index * 4 + 1],
            token[index * 4 + 2],
            token[index * 4 + 3],
        ])
    };
    let (audit_uid, uid, real_uid, pid, session, version) =
        (word(0), word(1), word(3), word(5), word(6), word(7));
    let admitted = uid == owner
        && real_uid == uid
        && audit_uid == uid
        && pid > 0
        && pid <= i32::MAX as u32
        && reported_pid >= 0
        && pid == reported_pid as u32
        && session > 0
        && session < 0xFFFF_FFFE
        && version > 0;
    admitted.then_some(Peer {
        process_id: pid,
        owner_uid: uid,
    })
}

#[cfg(target_os = "macos")]
fn kernel_peer(descriptor: RawFd, owner: u32) -> io::Result<Peer> {
    // SOL_LOCAL=0 with LOCAL_PEERTOKEN=6 and LOCAL_PEERPID=2.
    let token = socket_record::<32>(descriptor, 6)?;
    let pid = i32::from_ne_bytes(socket_record::<4>(descriptor, 2)?);
    let (mut uid, mut gid) = (0, 0);
    // SAFETY: a live local socket and two writable outputs.
    if unsafe { libc::getpeereid(descriptor, &mut uid, &mut gid) } != 0 {
        return Err(last_error());
    }
    let peer = audit_token_peer(&token, pid, owner)
        .filter(|peer| peer.owner_uid == uid)
        .ok_or(io::ErrorKind::PermissionDenied)?;
    if socket_record::<32>(descriptor, 6)? != token {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    Ok(peer)
}

#[cfg(target_os = "linux")]
fn kernel_peer(descriptor: RawFd, owner: u32) -> io::Result<Peer> {
    // SAFETY: ucred is plain data, valid when zeroed.
    let mut credentials: libc::ucred = unsafe { mem::zeroed() };
    let mut size = mem::size_of_val(&credentials) as libc::socklen_t;
    // SAFETY: an exact writable ucred record for SO_PEERCRED on a live socket.
    if unsafe {
        libc::getsockopt(
            descriptor,
            libc::SOL_SOCKET,
            libc::SO_PEERCRED,
            (&mut credentials as *mut libc::ucred).cast(),
            &mut size,
        )
    } != 0
    {
        return Err(last_error());
    }
    if size as usize != mem::size_of_val(&credentials)
        || credentials.uid != owner
        || credentials.pid <= 0
    {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    Ok(Peer {
        process_id: credentials.pid as u32,
        owner_uid: credentials.uid,
    })
}

#[cfg(target_os = "linux")]
const SEND_FLAGS: libc::c_int = libc::MSG_NOSIGNAL;
#[cfg(not(target_os = "linux"))]
const SEND_FLAGS: libc::c_int = 0;

/// One connected socket: bounded reads and writes from any thread, and a close
/// that ends a transfer another thread is blocked in.
#[derive(Debug)]
pub struct Socket {
    descriptor: Mutex<Option<Arc<OwnedFd>>>,
    cancellation: Arc<ConnectCancellation>,
    peer: Peer,
}

impl Socket {
    /// Connects to the runtime entry `leaf` before `deadline` and verifies its server
    /// as a live process owned by `expected_uid`. A refusing listener is attempted
    /// again within the deadline; an absent one is reported as not ready, never created.
    pub fn connect_cancellable(
        leaf: &str,
        expected_uid: u32,
        deadline: Instant,
        cancellation: Arc<ConnectCancellation>,
    ) -> Result<Self, ConnectRefusal> {
        #[cfg(target_os = "macos")]
        let namespace = crate::transport::DarwinTransport::installed(false)
            .map(|transport| Box::new(transport) as Box<dyn Namespace>);
        // This platform's runtime namespace is not yet part of the shared contract.
        #[cfg(not(target_os = "macos"))]
        let namespace = Err(io::ErrorKind::Unsupported.into());
        Self::connect_in(namespace, leaf, expected_uid, deadline, cancellation)
    }

    pub(crate) fn connect_in(
        namespace: io::Result<Box<dyn Namespace>>,
        leaf: &str,
        expected_uid: u32,
        deadline: Instant,
        cancellation: Arc<ConnectCancellation>,
    ) -> Result<Self, ConnectRefusal> {
        let transport = namespace.map_err(|error| match error.kind() {
            io::ErrorKind::NotFound => ConnectRefusal::NotReady,
            io::ErrorKind::Unsupported => ConnectRefusal::Failed(error),
            _ => ConnectRefusal::EndpointUntrusted,
        })?;
        let path = transport
            .socket_path(leaf)
            .map_err(|_| ConnectRefusal::EndpointUntrusted)?;
        let fence = || -> Result<(u64, u64), ConnectRefusal> {
            transport
                .verify()
                .map_err(|_| ConnectRefusal::EndpointUntrusted)?;
            owned_entry(&path, expected_uid)
        };
        let original = fence()?;
        let descriptor = loop {
            if cancellation.cancelled() {
                return Err(ConnectRefusal::Cancelled);
            }
            if let Some(descriptor) = attempt(&path, deadline, &cancellation)? {
                break descriptor;
            }
            let pause = deadline
                .checked_duration_since(Instant::now())
                .map(|remaining| remaining.min(REFUSED_RETRY))
                .filter(|pause| !pause.is_zero())
                .ok_or(ConnectRefusal::NotReady)?;
            // A pause the cancellation ends early; its own expiry is the retry.
            match wait(
                cancellation.readable.as_raw_fd(),
                libc::POLLIN,
                Some(Instant::now() + pause),
                &cancellation,
            ) {
                Err(error) if error.kind() == io::ErrorKind::TimedOut => {}
                _ => return Err(ConnectRefusal::Cancelled),
            }
        };
        if fence()? != original {
            return Err(ConnectRefusal::EndpointUntrusted);
        }
        let peer = kernel_peer(descriptor.as_raw_fd(), expected_uid)
            .map_err(|_| ConnectRefusal::PeerUntrusted)?;
        Ok(Self {
            descriptor: Mutex::new(Some(Arc::new(descriptor))),
            cancellation,
            peer,
        })
    }

    pub fn peer(&self) -> &Peer {
        &self.peer
    }

    fn retained(&self) -> io::Result<Arc<OwnedFd>> {
        self.descriptor
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .as_ref()
            .cloned()
            .ok_or_else(|| io::ErrorKind::ConnectionAborted.into())
    }

    /// Fills `buffer` before `deadline`; a peer that closes first is an unexpected end.
    pub fn read_exact(&self, buffer: &mut [u8], deadline: Instant) -> io::Result<()> {
        self.read_until(buffer, Some(deadline))
    }

    /// Waits for input or closure without a periodic timer. Protocol callers
    /// use this for the first byte only, then bound the remainder of a frame.
    pub fn read_idle_byte(&self, byte: &mut u8) -> io::Result<()> {
        self.read_until(std::slice::from_mut(byte), None)
    }

    fn read_until(&self, buffer: &mut [u8], deadline: Option<Instant>) -> io::Result<()> {
        let retained = self.retained()?;
        let descriptor = retained.as_raw_fd();
        let mut filled = 0usize;
        while filled < buffer.len() {
            wait(descriptor, libc::POLLIN, deadline, &self.cancellation)?;
            let remaining = &mut buffer[filled..];
            // SAFETY: the writable remainder of the caller's buffer on a retained socket.
            let received = unsafe {
                libc::recv(
                    descriptor,
                    remaining.as_mut_ptr().cast(),
                    remaining.len(),
                    0,
                )
            };
            match received {
                0 => return Err(io::ErrorKind::UnexpectedEof.into()),
                count if count > 0 => filled += count as usize,
                _ => {
                    let error = last_error();
                    if !matches!(
                        error.kind(),
                        io::ErrorKind::WouldBlock | io::ErrorKind::Interrupted
                    ) {
                        return Err(error);
                    }
                }
            }
        }
        Ok(())
    }

    /// Writes all of `bytes` before `deadline`.
    pub fn write_all(&self, bytes: &[u8], deadline: Instant) -> io::Result<()> {
        self.write_until(bytes, Some(deadline))
    }

    /// Writes all of `bytes` for as long as the connection lives. A peer that
    /// stops reading holds the write; the peer's end fails it, and a close
    /// from any thread ends it.
    pub fn write_all_while_open(&self, bytes: &[u8]) -> io::Result<()> {
        self.write_until(bytes, None)
    }

    fn write_until(&self, bytes: &[u8], deadline: Option<Instant>) -> io::Result<()> {
        let retained = self.retained()?;
        let descriptor = retained.as_raw_fd();
        let mut written = 0usize;
        while written < bytes.len() {
            if self.cancellation.cancelled() {
                return Err(io::ErrorKind::ConnectionAborted.into());
            }
            let remaining = &bytes[written..];
            // SAFETY: the readable remainder of the caller's bytes on a retained socket.
            let sent = unsafe {
                libc::send(
                    descriptor,
                    remaining.as_ptr().cast(),
                    remaining.len(),
                    SEND_FLAGS,
                )
            };
            match sent {
                0 => return Err(io::ErrorKind::WriteZero.into()),
                count if count > 0 => written += count as usize,
                _ => {
                    let error = last_error();
                    match error.kind() {
                        io::ErrorKind::WouldBlock => {
                            wait(descriptor, libc::POLLOUT, deadline, &self.cancellation)?
                        }
                        io::ErrorKind::Interrupted => {}
                        _ => return Err(error),
                    }
                }
            }
        }
        Ok(())
    }

    /// Ends every pending transfer and releases the socket; later calls report
    /// an aborted connection.
    pub fn close(&self) {
        self.cancellation.cancel();
        let taken = self
            .descriptor
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .take();
        if let Some(descriptor) = taken {
            // SAFETY: shutting down this process's own retained socket; the descriptor
            // closes when the last transfer holding it ends.
            unsafe {
                libc::shutdown(descriptor.as_raw_fd(), libc::SHUT_RDWR);
            }
        }
    }
}

impl Drop for Socket {
    fn drop(&mut self) {
        self.close();
    }
}

#[cfg(all(test, target_os = "macos"))]
mod tests;
