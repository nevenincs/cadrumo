//! The Linux desktop instance lock: an advisory file lock and a Unix socket
//! in the user's private runtime directory.
//!
//! `XDG_RUNTIME_DIR` belongs to one user and is closed to every other
//! account, so the lock is per user and no other account can reach the
//! socket. The kernel releases the file lock when its holder exits.
//!
//! A second instance connects to the socket and waits for one
//! acknowledgement byte. It writes nothing: the connection is the request,
//! and the holder never reads from it.

use std::{
    fs::{self, File, OpenOptions, TryLockError},
    io::{self, Read, Write},
    os::unix::{
        fs::{OpenOptionsExt, PermissionsExt},
        net::{UnixListener, UnixStream},
    },
    path::{Path, PathBuf},
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};

/// How long a second instance waits for each acknowledgement before it
/// checks the lock again.
const ACKNOWLEDGEMENT_ROUND: Duration = Duration::from_millis(500);
/// The pause between attempts when no holder answered at all.
const RETRY: Duration = Duration::from_millis(50);

/// How a desktop instance claim ended.
pub enum InstanceClaim {
    /// This process holds the per-user instance lock.
    Primary(InstanceLock),
    /// The instance holding the lock acknowledged an activation request.
    Activated,
}

/// The per-user desktop instance lock.
pub struct InstanceLock {
    /// Holds the advisory lock until it closes.
    _file: File,
    listener: UnixListener,
    socket: PathBuf,
    server: Option<Server>,
}

struct Server {
    stop: Arc<AtomicBool>,
    thread: JoinHandle<()>,
}

fn validate(family: &str) -> io::Result<()> {
    let valid = !family.is_empty()
        && family.len() <= 128
        && family
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'-' | b'_'))
        && !family.starts_with('.')
        && !family.ends_with('.');
    if valid {
        Ok(())
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "instance family is not a reverse-DNS identifier",
        ))
    }
}

/// The user's runtime directory, refused unless it is closed to other
/// accounts.
fn runtime_directory() -> io::Result<PathBuf> {
    let directory = std::env::var_os("XDG_RUNTIME_DIR")
        .map(PathBuf::from)
        .filter(|path| path.is_absolute())
        .ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::NotFound,
                "XDG_RUNTIME_DIR does not name a directory",
            )
        })?;
    private(&directory)?;
    Ok(directory)
}

fn private(directory: &Path) -> io::Result<()> {
    let metadata = fs::metadata(directory)?;
    if !metadata.is_dir() || metadata.permissions().mode() & 0o077 != 0 {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "the runtime directory is open to other accounts",
        ));
    }
    Ok(())
}

/// Claims the desktop instance for `family`, or hands activation to the
/// instance that holds it. A holder that refuses or does not answer within
/// a round leaves the claim checking the lock again, until `patience` runs
/// out with [`io::ErrorKind::TimedOut`].
pub fn claim_instance(family: &str, patience: Duration) -> io::Result<InstanceClaim> {
    claim_in(&runtime_directory()?, family, patience)
}

fn claim_in(directory: &Path, family: &str, patience: Duration) -> io::Result<InstanceClaim> {
    validate(family)?;
    private(directory)?;
    let socket = directory.join(format!("{family}.desktop.activate"));
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .mode(0o600)
        .open(directory.join(format!("{family}.desktop.lock")))?;
    let deadline = Instant::now() + patience;
    loop {
        match file.try_lock() {
            Ok(()) => {
                // Only the holder binds the socket, so one left behind by a
                // holder that died is stale.
                match fs::remove_file(&socket) {
                    Ok(()) => {}
                    Err(error) if error.kind() == io::ErrorKind::NotFound => {}
                    Err(error) => return Err(error),
                }
                let listener = UnixListener::bind(&socket)?;
                return Ok(InstanceClaim::Primary(InstanceLock {
                    _file: file,
                    listener,
                    socket,
                    server: None,
                }));
            }
            Err(TryLockError::WouldBlock) => {}
            Err(TryLockError::Error(error)) => return Err(error),
        }
        let remaining = deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            return Err(io::ErrorKind::TimedOut.into());
        }
        if request(&socket, remaining.min(ACKNOWLEDGEMENT_ROUND))? {
            return Ok(InstanceClaim::Activated);
        }
        thread::sleep(RETRY.min(remaining));
    }
}

/// Sends one activation request and reports whether the holder
/// acknowledged it.
fn request(socket: &Path, wait: Duration) -> io::Result<bool> {
    let mut stream = match UnixStream::connect(socket) {
        Ok(stream) => stream,
        // The holder has not bound its socket yet, or is going away.
        Err(error)
            if matches!(
                error.kind(),
                io::ErrorKind::NotFound | io::ErrorKind::ConnectionRefused
            ) =>
        {
            return Ok(false);
        }
        Err(error) => return Err(error),
    };
    stream.set_read_timeout(Some(wait))?;
    let mut acknowledgement = [0u8; 1];
    match stream.read(&mut acknowledgement) {
        Ok(read) => Ok(read == 1),
        Err(error)
            if matches!(
                error.kind(),
                io::ErrorKind::WouldBlock
                    | io::ErrorKind::TimedOut
                    | io::ErrorKind::ConnectionReset
            ) =>
        {
            Ok(false)
        }
        Err(error) => Err(error),
    }
}

impl InstanceLock {
    /// Answers activation requests on a worker thread until the lock drops.
    ///
    /// `on_activation` returns whether it accepted the request. A refused
    /// request is not acknowledged, so the second instance keeps waiting for
    /// the lock; a holder that is closing refuses.
    pub fn serve(&mut self, on_activation: impl Fn() -> bool + Send + 'static) -> io::Result<()> {
        if self.server.is_some() {
            return Err(io::Error::new(
                io::ErrorKind::AlreadyExists,
                "the instance lock already serves activation",
            ));
        }
        let listener = self.listener.try_clone()?;
        let stop = Arc::new(AtomicBool::new(false));
        let halt = stop.clone();
        let thread = thread::Builder::new()
            .name("desktop-activation".into())
            .spawn(move || {
                for connection in listener.incoming() {
                    if halt.load(Ordering::Acquire) {
                        return;
                    }
                    match connection {
                        // Nothing is read: the connection is the request.
                        Ok(mut stream) => {
                            if on_activation() {
                                let _ = stream.write_all(&[1]);
                            }
                        }
                        Err(_) => thread::sleep(RETRY),
                    }
                }
            })?;
        self.server = Some(Server { stop, thread });
        Ok(())
    }
}

impl Drop for InstanceLock {
    fn drop(&mut self) {
        if let Some(server) = self.server.take() {
            server.stop.store(true, Ordering::Release);
            // Wakes the accept call so the worker sees the stop flag.
            let _ = UnixStream::connect(&self.socket);
            let _ = server.thread.join();
        }
        // The lock is still held here, so the socket path is this holder's.
        let _ = fs::remove_file(&self.socket);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::AtomicUsize;
    use std::time::{SystemTime, UNIX_EPOCH};

    struct Scratch(PathBuf);
    impl Scratch {
        fn new(label: &str) -> Self {
            let nanos = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let path = std::env::temp_dir().join(format!(
                "cadrumo-instance-{label}-{}-{nanos}",
                std::process::id()
            ));
            fs::create_dir_all(&path).unwrap();
            fs::set_permissions(&path, fs::Permissions::from_mode(0o700)).unwrap();
            Scratch(path)
        }
    }
    impl Drop for Scratch {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    const FAMILY: &str = "test.cadrumo.instance";

    fn outcome(claim: io::Result<InstanceClaim>) -> io::Result<&'static str> {
        claim.map(|claim| match claim {
            InstanceClaim::Primary(_) => "primary",
            InstanceClaim::Activated => "activated",
        })
    }

    fn primary(directory: &Path, family: &str) -> InstanceLock {
        match claim_in(directory, family, Duration::from_secs(5)).unwrap() {
            InstanceClaim::Primary(lock) => lock,
            InstanceClaim::Activated => panic!("expected the lock"),
        }
    }

    fn counting(lock: &mut InstanceLock, accept: bool) -> Arc<AtomicUsize> {
        let count = Arc::new(AtomicUsize::new(0));
        let seen = count.clone();
        lock.serve(move || {
            seen.fetch_add(1, Ordering::SeqCst);
            accept
        })
        .unwrap();
        count
    }

    #[test]
    fn second_claim_hands_activation_to_the_holder_and_sends_nothing() {
        let scratch = Scratch::new("activation");
        let mut lock = primary(&scratch.0, FAMILY);
        let count = counting(&mut lock, true);
        assert_eq!(
            outcome(claim_in(&scratch.0, FAMILY, Duration::from_secs(5))).unwrap(),
            "activated"
        );
        assert_eq!(count.load(Ordering::SeqCst), 1);
        // A connection that writes bytes is still one bare request: the
        // holder reads none of them and acknowledges with one byte.
        let mut stream =
            UnixStream::connect(scratch.0.join(format!("{FAMILY}.desktop.activate"))).unwrap();
        stream.write_all(b"--open /tmp/elsewhere").unwrap();
        let mut reply = [0u8; 1];
        stream.read_exact(&mut reply).unwrap();
        assert_eq!(reply, [1]);
        assert_eq!(count.load(Ordering::SeqCst), 2);
    }

    #[test]
    fn families_do_not_contend() {
        let scratch = Scratch::new("families");
        let _stable = primary(&scratch.0, FAMILY);
        assert_eq!(
            outcome(claim_in(
                &scratch.0,
                &format!("{FAMILY}.preview"),
                Duration::from_secs(5)
            ))
            .unwrap(),
            "primary"
        );
    }

    #[test]
    fn released_lock_passes_on_and_a_stale_socket_is_replaced() {
        let scratch = Scratch::new("release");
        let mut lock = primary(&scratch.0, FAMILY);
        counting(&mut lock, true);
        drop(lock);
        let socket = scratch.0.join(format!("{FAMILY}.desktop.activate"));
        assert!(!socket.exists());
        // A socket left by a holder that died does not block the next one.
        drop(UnixListener::bind(&socket).unwrap());
        assert!(socket.exists());
        let mut next = primary(&scratch.0, FAMILY);
        let count = counting(&mut next, true);
        assert_eq!(
            outcome(claim_in(&scratch.0, FAMILY, Duration::from_secs(5))).unwrap(),
            "activated"
        );
        assert_eq!(count.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn a_refusing_holder_times_out_the_claim() {
        let scratch = Scratch::new("closing");
        let mut lock = primary(&scratch.0, FAMILY);
        let count = counting(&mut lock, false);
        let error = claim_in(&scratch.0, FAMILY, Duration::from_millis(800))
            .err()
            .unwrap();
        assert_eq!(error.kind(), io::ErrorKind::TimedOut);
        assert!(count.load(Ordering::SeqCst) >= 1);
    }

    #[test]
    fn open_directories_and_invalid_families_are_refused() {
        let scratch = Scratch::new("refusal");
        fs::set_permissions(&scratch.0, fs::Permissions::from_mode(0o755)).unwrap();
        assert_eq!(
            claim_in(&scratch.0, FAMILY, Duration::from_secs(1))
                .err()
                .unwrap()
                .kind(),
            io::ErrorKind::PermissionDenied
        );
        fs::set_permissions(&scratch.0, fs::Permissions::from_mode(0o700)).unwrap();
        for invalid in ["", ".hidden", "a/b", "../escape", "trailing."] {
            assert_eq!(
                claim_in(&scratch.0, invalid, Duration::from_secs(1))
                    .err()
                    .unwrap()
                    .kind(),
                io::ErrorKind::InvalidInput,
                "{invalid}"
            );
        }
    }
}
