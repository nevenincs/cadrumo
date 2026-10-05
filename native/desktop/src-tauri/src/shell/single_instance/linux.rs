//! The Linux desktop instance lock: an advisory file lock and per-session
//! Unix sockets in the user's private runtime directory.
//!
//! `XDG_RUNTIME_DIR` belongs to one user, is shared by that user's sessions
//! and is closed to every other account, so the lock is per user and no
//! other account can reach a socket. The kernel releases the file lock when
//! its holder exits.
//!
//! The holder listens on a socket named for its login session
//! (`XDG_SESSION_ID`). A second instance connects to its own session's
//! socket and waits for one acknowledgement byte. It writes nothing: the
//! connection is the request, and the holder never reads from it. When the
//! lock is held but its own session has no socket, the holder is in another
//! session.

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
/// How long a held lock may go without a socket for the caller's session
/// before the holder counts as being in another session. It covers the
/// moment between a holder taking the lock and binding its socket.
const HOLDER_GRACE: Duration = Duration::from_millis(500);
/// The session name used when the login manager sets no `XDG_SESSION_ID`.
const UNNAMED_SESSION: &str = "unnamed";

/// How a desktop instance claim ended.
pub enum InstanceClaim {
    /// This process holds the per-user instance lock.
    Primary(InstanceLock),
    /// The instance holding the lock acknowledged an activation request.
    Activated,
    /// The instance holding the lock runs in another session of this user.
    OtherSession,
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

/// Whether `name` is safe as a file name part: ASCII letters, digits, `.`,
/// `-` and `_`, not empty, at most `limit` bytes and without an edge dot.
fn file_name_part(name: &str, limit: usize) -> bool {
    !name.is_empty()
        && name.len() <= limit
        && name
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'-' | b'_'))
        && !name.starts_with('.')
        && !name.ends_with('.')
}

fn validate(family: &str, session: &str) -> io::Result<()> {
    if !file_name_part(family, 128) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "instance family is not a reverse-DNS identifier",
        ));
    }
    if !file_name_part(session, 64) || session.contains('.') {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "the session name is not a plain identifier",
        ));
    }
    Ok(())
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

/// This process's login session, or [`UNNAMED_SESSION`] when none is set.
fn current_session() -> io::Result<String> {
    match std::env::var("XDG_SESSION_ID") {
        Ok(session) if !session.is_empty() => Ok(session),
        Ok(_) | Err(std::env::VarError::NotPresent) => Ok(UNNAMED_SESSION.to_owned()),
        Err(std::env::VarError::NotUnicode(_)) => Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "XDG_SESSION_ID is not text",
        )),
    }
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

/// The socket prefix and suffix of `family`'s session sockets.
fn socket_affixes(family: &str) -> (String, &'static str) {
    (format!("{family}.desktop.session."), ".activate")
}

/// Claims the desktop instance for `family`, or hands activation to the
/// instance that holds it. A holder in this session that refuses or does
/// not answer within a round leaves the claim checking the lock again,
/// until `patience` runs out with [`io::ErrorKind::TimedOut`]. A holder in
/// another session gets no request.
pub fn claim_instance(family: &str, patience: Duration) -> io::Result<InstanceClaim> {
    claim_in(&runtime_directory()?, family, &current_session()?, patience)
}

fn claim_in(
    directory: &Path,
    family: &str,
    session: &str,
    patience: Duration,
) -> io::Result<InstanceClaim> {
    validate(family, session)?;
    private(directory)?;
    let (prefix, suffix) = socket_affixes(family);
    let socket = directory.join(format!("{prefix}{session}{suffix}"));
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .mode(0o600)
        .open(directory.join(format!("{family}.desktop.lock")))?;
    let deadline = Instant::now() + patience;
    let mut absent_since = None;
    loop {
        match file.try_lock() {
            Ok(()) => {
                // Only the holder binds session sockets, so any left behind
                // by a holder that died are stale, whatever their session.
                for entry in fs::read_dir(directory)? {
                    let name = entry?.file_name();
                    let name = name.to_string_lossy();
                    if name.starts_with(&prefix) && name.ends_with(suffix) {
                        match fs::remove_file(directory.join(&*name)) {
                            Ok(()) => {}
                            Err(error) if error.kind() == io::ErrorKind::NotFound => {}
                            Err(error) => return Err(error),
                        }
                    }
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
        match request(&socket, remaining.min(ACKNOWLEDGEMENT_ROUND))? {
            Reply::Acknowledged => return Ok(InstanceClaim::Activated),
            Reply::Unanswered => absent_since = None,
            Reply::Absent => {
                let since = *absent_since.get_or_insert_with(Instant::now);
                if since.elapsed() >= HOLDER_GRACE {
                    return Ok(InstanceClaim::OtherSession);
                }
            }
        }
        thread::sleep(RETRY.min(remaining));
    }
}

/// What became of one activation request.
enum Reply {
    Acknowledged,
    /// A holder in this session took the request and did not acknowledge it.
    Unanswered,
    /// Nothing listens for this session.
    Absent,
}

/// Sends one activation request on `socket`.
fn request(socket: &Path, wait: Duration) -> io::Result<Reply> {
    let mut stream = match UnixStream::connect(socket) {
        Ok(stream) => stream,
        Err(error)
            if matches!(
                error.kind(),
                io::ErrorKind::NotFound | io::ErrorKind::ConnectionRefused
            ) =>
        {
            return Ok(Reply::Absent);
        }
        Err(error) => return Err(error),
    };
    stream.set_read_timeout(Some(wait))?;
    let mut acknowledgement = [0u8; 1];
    match stream.read(&mut acknowledgement) {
        Ok(1) => Ok(Reply::Acknowledged),
        Ok(_) => Ok(Reply::Unanswered),
        Err(error)
            if matches!(
                error.kind(),
                io::ErrorKind::WouldBlock
                    | io::ErrorKind::TimedOut
                    | io::ErrorKind::ConnectionReset
            ) =>
        {
            Ok(Reply::Unanswered)
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
            // Short, because a socket path must fit in `sun_path`.
            let path = std::env::temp_dir().join(format!(
                "ci-{label}-{}-{}",
                std::process::id(),
                nanos % 1_000_000_000
            ));
            fs::create_dir_all(&path).unwrap();
            fs::set_permissions(&path, fs::Permissions::from_mode(0o700)).unwrap();
            Scratch(path)
        }

        fn socket(&self, session: &str) -> PathBuf {
            self.0
                .join(format!("{FAMILY}.desktop.session.{session}.activate"))
        }
    }
    impl Drop for Scratch {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    const FAMILY: &str = "test.cadrumo.instance";
    const SESSION: &str = "c2";

    fn outcome(claim: io::Result<InstanceClaim>) -> io::Result<&'static str> {
        claim.map(|claim| match claim {
            InstanceClaim::Primary(_) => "primary",
            InstanceClaim::Activated => "activated",
            InstanceClaim::OtherSession => "other-session",
        })
    }

    fn claim(directory: &Path, family: &str, session: &str) -> io::Result<&'static str> {
        outcome(claim_in(directory, family, session, Duration::from_secs(5)))
    }

    fn primary(directory: &Path, family: &str, session: &str) -> InstanceLock {
        match claim_in(directory, family, session, Duration::from_secs(5)).unwrap() {
            InstanceClaim::Primary(lock) => lock,
            _ => panic!("expected the lock"),
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
        let mut lock = primary(&scratch.0, FAMILY, SESSION);
        let count = counting(&mut lock, true);
        assert_eq!(claim(&scratch.0, FAMILY, SESSION).unwrap(), "activated");
        assert_eq!(count.load(Ordering::SeqCst), 1);
        // A connection that writes bytes is still one bare request: the
        // holder reads none of them and acknowledges with one byte.
        let mut stream = UnixStream::connect(scratch.socket(SESSION)).unwrap();
        stream.write_all(b"--open /tmp/elsewhere").unwrap();
        let mut reply = [0u8; 1];
        stream.read_exact(&mut reply).unwrap();
        assert_eq!(reply, [1]);
        assert_eq!(count.load(Ordering::SeqCst), 2);
    }

    #[test]
    fn a_holder_in_another_session_is_reported_without_a_request() {
        let scratch = Scratch::new("sessions");
        let mut lock = primary(&scratch.0, FAMILY, SESSION);
        let count = counting(&mut lock, true);
        let started = Instant::now();
        assert_eq!(claim(&scratch.0, FAMILY, "c3").unwrap(), "other-session");
        assert!(started.elapsed() < Duration::from_secs(2));
        assert_eq!(count.load(Ordering::SeqCst), 0);
        assert_eq!(claim(&scratch.0, FAMILY, SESSION).unwrap(), "activated");
        assert_eq!(count.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn the_grace_covers_a_holder_that_has_not_bound_its_socket_yet() {
        let scratch = Scratch::new("grace");
        let directory = scratch.0.clone();
        let socket = scratch.socket(SESSION);
        // Holds the lock by hand and binds the session socket late.
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(directory.join(format!("{FAMILY}.desktop.lock")))
            .unwrap();
        file.try_lock().unwrap();
        let holder = thread::spawn(move || {
            thread::sleep(Duration::from_millis(150));
            let listener = UnixListener::bind(&socket).unwrap();
            let (mut stream, _) = listener.accept().unwrap();
            stream.write_all(&[1]).unwrap();
            file
        });
        assert_eq!(claim(&directory, FAMILY, SESSION).unwrap(), "activated");
        holder.join().unwrap();
    }

    #[test]
    fn families_do_not_contend() {
        let scratch = Scratch::new("families");
        let _stable = primary(&scratch.0, FAMILY, SESSION);
        assert_eq!(
            claim(&scratch.0, &format!("{FAMILY}.preview"), SESSION).unwrap(),
            "primary"
        );
    }

    #[test]
    fn released_lock_passes_on_and_stale_sockets_are_swept() {
        let scratch = Scratch::new("release");
        let mut lock = primary(&scratch.0, FAMILY, SESSION);
        counting(&mut lock, true);
        drop(lock);
        assert!(!scratch.socket(SESSION).exists());
        // Sockets left by holders that died, in this session and another,
        // do not survive the next holder.
        for session in [SESSION, "c9"] {
            drop(UnixListener::bind(scratch.socket(session)).unwrap());
            assert!(scratch.socket(session).exists());
        }
        let mut next = primary(&scratch.0, FAMILY, SESSION);
        assert!(!scratch.socket("c9").exists());
        let count = counting(&mut next, true);
        assert_eq!(claim(&scratch.0, FAMILY, SESSION).unwrap(), "activated");
        assert_eq!(count.load(Ordering::SeqCst), 1);
        assert_eq!(claim(&scratch.0, FAMILY, "c9").unwrap(), "other-session");
    }

    #[test]
    fn a_refusing_holder_times_out_the_claim() {
        let scratch = Scratch::new("closing");
        let mut lock = primary(&scratch.0, FAMILY, SESSION);
        let count = counting(&mut lock, false);
        let error = claim_in(&scratch.0, FAMILY, SESSION, Duration::from_millis(800))
            .err()
            .unwrap();
        assert_eq!(error.kind(), io::ErrorKind::TimedOut);
        assert!(count.load(Ordering::SeqCst) >= 1);
    }

    /// The holder acknowledges on the connection that carried the request,
    /// so an acknowledgement it gives after that claim stopped waiting
    /// reaches no later claim, even one sent while the holder is closing.
    #[test]
    fn a_late_acknowledgement_does_not_answer_a_later_claim() {
        let scratch = Scratch::new("late");
        let mut lock = primary(&scratch.0, FAMILY, SESSION);
        let (decide, decisions) = std::sync::mpsc::channel::<bool>();
        let decisions = std::sync::Mutex::new(decisions);
        let (seen, requests) = std::sync::mpsc::channel::<()>();
        let closing = Arc::new(AtomicBool::new(false));
        let closed = closing.clone();
        lock.serve(move || {
            let _ = seen.send(());
            !closed.load(Ordering::SeqCst) && decisions.lock().unwrap().recv().unwrap_or(false)
        })
        .unwrap();
        // The first claim gives up while the holder still deliberates.
        let error = claim_in(&scratch.0, FAMILY, SESSION, Duration::from_millis(300))
            .err()
            .unwrap();
        assert_eq!(error.kind(), io::ErrorKind::TimedOut);
        requests.recv().unwrap();
        // The holder starts closing, then acknowledges that request late.
        closing.store(true, Ordering::SeqCst);
        decide.send(true).unwrap();
        let error = claim_in(&scratch.0, FAMILY, SESSION, Duration::from_millis(1500))
            .err()
            .unwrap();
        assert_eq!(error.kind(), io::ErrorKind::TimedOut);
        assert!(requests.try_iter().count() >= 1);
    }

    #[test]
    fn open_directories_invalid_families_and_sessions_are_refused() {
        let scratch = Scratch::new("refusal");
        fs::set_permissions(&scratch.0, fs::Permissions::from_mode(0o755)).unwrap();
        assert_eq!(
            claim(&scratch.0, FAMILY, SESSION).err().unwrap().kind(),
            io::ErrorKind::PermissionDenied
        );
        fs::set_permissions(&scratch.0, fs::Permissions::from_mode(0o700)).unwrap();
        for invalid in ["", ".hidden", "a/b", "../escape", "trailing."] {
            assert_eq!(
                claim(&scratch.0, invalid, SESSION).err().unwrap().kind(),
                io::ErrorKind::InvalidInput,
                "{invalid}"
            );
        }
        for invalid in ["", "a.b", "a/b", "..", &"s".repeat(65)] {
            assert_eq!(
                claim(&scratch.0, FAMILY, invalid).err().unwrap().kind(),
                io::ErrorKind::InvalidInput,
                "{invalid}"
            );
        }
    }
}
