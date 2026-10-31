//! The POSIX desktop instance lock: an advisory file lock and per-session
//! Unix sockets in a per-user directory closed to every other account.
//!
//! The caller's key is the channel family scoped to one storage root, so each
//! root has its own lock and sockets.
//!
//! The directory belongs to one user, is shared by that user's sessions and
//! is refused when other accounts can reach it, so the lock is per user and
//! no other account can reach a socket. The kernel releases the file lock
//! when its holder exits.
//!
//! The holder listens on a socket named for its login session. A second
//! instance connects to its own session's socket and waits for one
//! acknowledgement byte. It writes nothing: the connection is the request,
//! and the holder never reads from it. When the lock is held but its own
//! session has no socket, the holder is in another session.

use std::{
    fs::{self, File, OpenOptions, TryLockError},
    io::{self, Read, Write},
    os::unix::{
        ffi::OsStrExt,
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
/// The `sun_path` size in bytes, which includes the terminating NUL.
#[cfg(target_os = "linux")]
const SOCKET_PATH_LIMIT: usize = 108;
#[cfg(target_os = "macos")]
const SOCKET_PATH_LIMIT: usize = cadrumo_platform::RUNTIME_SOCKET_PATH_LIMIT;
/// The session name used when the login manager sets no `XDG_SESSION_ID`.
#[cfg(target_os = "linux")]
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
#[cfg(target_os = "linux")]
fn runtime_directory() -> io::Result<PathBuf> {
    runtime_directory_named(std::env::var_os("XDG_RUNTIME_DIR"))
}

/// `named`, the value of `XDG_RUNTIME_DIR`, as the runtime directory.
#[cfg(target_os = "linux")]
fn runtime_directory_named(named: Option<std::ffi::OsString>) -> io::Result<PathBuf> {
    let directory = named
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
#[cfg(target_os = "linux")]
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
            "the instance directory is open to other accounts",
        ));
    }
    Ok(())
}

/// The names of one family's lock file and session sockets.
struct Names {
    lock: String,
    prefix: String,
    suffix: &'static str,
}

impl Names {
    fn socket(&self, session: &str) -> String {
        format!("{}{session}{}", self.prefix, self.suffix)
    }
}

/// `sun_path` bounds the socket path, and the key, a channel family scoped to
/// one storage root, is long, so it enters the names as a short digest.
/// Collisions only matter between this user's own keys.
fn names(family: &str) -> Names {
    use sha2::{Digest, Sha256};
    let digest = Sha256::new()
        .chain_update(b"cadrumo-desktop-instance-v1\0")
        .chain_update(family.as_bytes())
        .finalize();
    let stem: String = digest[..6]
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect();
    Names {
        lock: format!("desktop-{stem}.lock"),
        prefix: format!("desktop-{stem}-"),
        suffix: ".sock",
    }
}

/// Claims the desktop instance for `family`, or hands activation to the
/// instance that holds it. A holder in this session that refuses or does
/// not answer within a round leaves the claim checking the lock again,
/// until `patience` runs out with [`io::ErrorKind::TimedOut`]. A holder in
/// another session gets no request.
///
/// The directory is the user's `XDG_RUNTIME_DIR` and the session the login
/// session the login manager names in `XDG_SESSION_ID`.
#[cfg(target_os = "linux")]
pub fn claim_instance(family: &str, patience: Duration) -> io::Result<InstanceClaim> {
    claim_in(
        &runtime_directory()?,
        family,
        &current_session()?,
        patience,
        &|| Ok(()),
    )
}

/// Claims the desktop instance for `family`, or hands activation to the
/// instance that holds it. A holder in this session that refuses or does
/// not answer within a round leaves the claim checking the lock again,
/// until `patience` runs out with [`io::ErrorKind::TimedOut`]. A holder in
/// another session gets no request.
///
/// The directory is the private transient transport directory the runtime's
/// sockets use, retained and rechecked against replacement, and the session
/// is the kernel audit session of the graphical login this process runs in.
#[cfg(target_os = "macos")]
pub fn claim_instance(family: &str, patience: Duration) -> io::Result<InstanceClaim> {
    let session = format!("{:x}", crate::launch::graphical_session()?);
    validate(family, &session)?;
    let transport = transport()?;
    claim_in(transport.directory(), family, &session, patience, &|| {
        transport.verify()
    })
}

/// The account's private transport directory.
#[cfg(all(target_os = "macos", not(test)))]
fn transport() -> io::Result<cadrumo_platform::transport::DarwinTransport> {
    cadrumo_platform::transport::DarwinTransport::installed(true)
}

/// A test run claims in the namespace its process owns, and refuses when it owns none, so
/// it never reaches the account's directory.
#[cfg(all(target_os = "macos", test))]
fn transport() -> io::Result<cadrumo_platform::transport::DarwinTransport> {
    let base = isolation::base()
        .ok_or_else(|| io::Error::other("a test claimed without an isolated namespace"))?;
    cadrumo_platform::transport::DarwinTransport::beneath(&base, true)
}

/// The isolated transport namespace of a test run, shared by the test process and the
/// helper processes it launches.
#[cfg(all(test, target_os = "macos"))]
pub(super) mod isolation {
    use std::{
        fs,
        os::unix::fs::PermissionsExt,
        path::PathBuf,
        sync::Mutex,
        time::{SystemTime, UNIX_EPOCH},
    };

    struct State {
        base: Option<PathBuf>,
        leases: usize,
    }

    static STATE: Mutex<State> = Mutex::new(State {
        base: None,
        leases: 0,
    });

    /// Keeps the namespace alive; the last lease removes it.
    pub(in crate::shell::single_instance) struct Lease;

    /// Creates the namespace on the first lease. The path is short because a socket
    /// path must fit its bound, and it is private to this user.
    pub(in crate::shell::single_instance) fn lease() -> Lease {
        let mut state = STATE.lock().unwrap();
        if state.leases == 0 && state.base.is_none() {
            let nanos = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let base = fs::canonicalize("/tmp").unwrap().join(format!(
                "ci-ns-{}-{}",
                std::process::id(),
                nanos % 1_000_000
            ));
            fs::create_dir_all(&base).unwrap();
            fs::set_permissions(&base, fs::Permissions::from_mode(0o700)).unwrap();
            state.base = Some(base);
        }
        state.leases += 1;
        Lease
    }

    impl Drop for Lease {
        fn drop(&mut self) {
            let mut state = STATE.lock().unwrap();
            state.leases -= 1;
            if state.leases == 0
                && let Some(base) = state.base.take()
            {
                let _ = fs::remove_dir_all(base);
            }
        }
    }

    /// The namespace the process claims in, while a lease or an adoption holds one.
    pub(in crate::shell::single_instance) fn base() -> Option<PathBuf> {
        STATE.lock().unwrap().base.clone()
    }

    /// A helper process claims in the namespace its launching test owns.
    pub(in crate::shell::single_instance) fn adopt(base: PathBuf) {
        let mut state = STATE.lock().unwrap();
        state.base = Some(base);
        state.leases += 1;
    }
}

/// Claims in `directory`, calling `verify` before the lock file opens and
/// again once the lock is held, so a namespace that was replaced meanwhile
/// refuses the claim.
fn claim_in(
    directory: &Path,
    family: &str,
    session: &str,
    patience: Duration,
    verify: &dyn Fn() -> io::Result<()>,
) -> io::Result<InstanceClaim> {
    validate(family, session)?;
    verify()?;
    private(directory)?;
    let names = names(family);
    let socket = directory.join(names.socket(session));
    // Refuses a socket path at or above the platform bound before anything binds it.
    if socket.as_os_str().as_bytes().len() >= SOCKET_PATH_LIMIT {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "the instance socket path exceeds the platform bound",
        ));
    }
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .mode(0o600)
        .open(directory.join(&names.lock))?;
    let deadline = Instant::now() + patience;
    let mut absent_since = None;
    loop {
        match file.try_lock() {
            Ok(()) => {
                verify()?;
                // Only the holder binds session sockets, so any left behind
                // by a holder that died are stale, whatever their session.
                for entry in fs::read_dir(directory)? {
                    let name = entry?.file_name();
                    let name = name.to_string_lossy();
                    if name.starts_with(&names.prefix) && name.ends_with(names.suffix) {
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
    // A refusing holder drops the connection at once, and a platform may refuse the option
    // on a connection whose peer has already closed it. That is a refusal, not a failure;
    // the wait is never zero, which is the other cause of this error.
    match stream.set_read_timeout(Some(wait)) {
        Ok(()) => {}
        Err(error) if error.kind() == io::ErrorKind::InvalidInput && !wait.is_zero() => {
            return Ok(Reply::Unanswered);
        }
        Err(error) => return Err(error),
    }
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

    /// The per-user temporary directory is too deep for `sun_path` here.
    #[cfg(target_os = "macos")]
    fn scratch_base() -> PathBuf {
        PathBuf::from("/private/tmp")
    }
    #[cfg(not(target_os = "macos"))]
    fn scratch_base() -> PathBuf {
        std::env::temp_dir()
    }

    fn unverified() -> io::Result<()> {
        Ok(())
    }

    struct Scratch(PathBuf);
    impl Scratch {
        fn new(label: &str) -> Self {
            let nanos = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            // Short, because a socket path must fit in `sun_path`.
            let path = scratch_base().join(format!(
                "ci-{label}-{}-{}",
                std::process::id(),
                nanos % 1_000_000_000
            ));
            fs::create_dir_all(&path).unwrap();
            fs::set_permissions(&path, fs::Permissions::from_mode(0o700)).unwrap();
            Scratch(path)
        }

        fn socket(&self, session: &str) -> PathBuf {
            self.0.join(names(FAMILY).socket(session))
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
        outcome(claim_in(
            directory,
            family,
            session,
            Duration::from_secs(5),
            &unverified,
        ))
    }

    fn primary(directory: &Path, family: &str, session: &str) -> InstanceLock {
        match claim_in(
            directory,
            family,
            session,
            Duration::from_secs(5),
            &unverified,
        )
        .unwrap()
        {
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
            .open(directory.join(names(FAMILY).lock))
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

    /// The keys of one family on two storage roots hold two locks at once,
    /// each answering only its own launches.
    #[test]
    fn roots_do_not_contend() {
        let scratch = Scratch::new("roots");
        let [first, second] = ["0".repeat(63) + "1", "f".repeat(64)]
            .map(|root| cadrumo_application::instance_scope::root_scoped(FAMILY, &root).unwrap());
        let mut held = primary(&scratch.0, &first, SESSION);
        let count = counting(&mut held, true);
        assert_eq!(claim(&scratch.0, &second, SESSION).unwrap(), "primary");
        assert_eq!(count.load(Ordering::SeqCst), 0);
        assert_eq!(claim(&scratch.0, &first, SESSION).unwrap(), "activated");
        assert_eq!(count.load(Ordering::SeqCst), 1);
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
        let error = claim_in(
            &scratch.0,
            FAMILY,
            SESSION,
            Duration::from_millis(800),
            &unverified,
        )
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
        let error = claim_in(
            &scratch.0,
            FAMILY,
            SESSION,
            Duration::from_millis(300),
            &unverified,
        )
        .err()
        .unwrap();
        assert_eq!(error.kind(), io::ErrorKind::TimedOut);
        requests.recv().unwrap();
        // The holder starts closing, then acknowledges that request late.
        closing.store(true, Ordering::SeqCst);
        decide.send(true).unwrap();
        let error = claim_in(
            &scratch.0,
            FAMILY,
            SESSION,
            Duration::from_millis(1500),
            &unverified,
        )
        .err()
        .unwrap();
        assert_eq!(error.kind(), io::ErrorKind::TimedOut);
        assert!(requests.try_iter().count() >= 1);
    }

    /// A holder that refuses drops the connection at once, so a request races the close.
    /// The race is a refusal in every interleaving, never a failure of the claim.
    #[test]
    fn a_connection_the_holder_drops_at_once_is_an_unanswered_request() {
        let scratch = Scratch::new("dropped");
        let socket = scratch.socket(SESSION);
        let listener = UnixListener::bind(&socket).unwrap();
        const REQUESTS: usize = 2000;
        let holder = thread::spawn(move || {
            for connection in listener.incoming().take(REQUESTS) {
                drop(connection);
            }
        });
        for attempt in 0..REQUESTS {
            let reply = request(&socket, Duration::from_millis(500))
                .unwrap_or_else(|error| panic!("request {attempt} failed: {error}"));
            assert!(
                matches!(reply, Reply::Unanswered),
                "request {attempt} was answered"
            );
        }
        holder.join().unwrap();
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

    /// A namespace check that fails before the lock file opens, or once the
    /// lock is held, refuses the claim and binds no socket.
    #[test]
    fn a_namespace_that_fails_its_check_refuses_the_claim() {
        let scratch = Scratch::new("verify");
        let replaced = || Err(io::Error::from(io::ErrorKind::PermissionDenied));
        let refused = claim_in(
            &scratch.0,
            FAMILY,
            SESSION,
            Duration::from_secs(1),
            &replaced,
        );
        assert_eq!(
            refused.err().unwrap().kind(),
            io::ErrorKind::PermissionDenied
        );
        assert!(!scratch.0.join(names(FAMILY).lock).exists());
        let checks = AtomicUsize::new(0);
        let replaced_later = || {
            if checks.fetch_add(1, Ordering::SeqCst) == 0 {
                Ok(())
            } else {
                Err(io::Error::from(io::ErrorKind::PermissionDenied))
            }
        };
        let refused = claim_in(
            &scratch.0,
            FAMILY,
            SESSION,
            Duration::from_secs(1),
            &replaced_later,
        );
        assert_eq!(
            refused.err().unwrap().kind(),
            io::ErrorKind::PermissionDenied
        );
        assert_eq!(checks.load(Ordering::SeqCst), 2);
        assert!(!scratch.socket(SESSION).exists());
        // The refused claim released the lock, so a sound namespace takes it.
        assert_eq!(claim(&scratch.0, FAMILY, SESSION).unwrap(), "primary");
    }

    /// The names stay within the socket bound whatever the family's length,
    /// and distinct families keep distinct names.
    #[test]
    fn compact_names_fit_the_bound_and_keep_families_apart() {
        let long = format!("md.{}", "a".repeat(125));
        let stable = names("md.neve.cadrumo");
        let preview = names("md.neve.cadrumo.preview");
        assert_ne!(stable.prefix, preview.prefix);
        assert_ne!(stable.lock, preview.lock);
        let widest = names(&long).socket(&format!("{:x}", u32::MAX));
        assert_eq!(widest.len(), 34, "{widest}");
        assert!(file_name_part(&widest, 64));
        let scoped = |family: &str, root: &str| {
            names(&cadrumo_application::instance_scope::root_scoped(family, root).unwrap())
        };
        let (one, other) = ("0".repeat(63) + "1", "f".repeat(64));
        let first = scoped("md.neve.cadrumo", &one);
        for different in [
            scoped("md.neve.cadrumo", &other),
            scoped("md.neve.cadrumo.preview", &one),
            stable,
        ] {
            assert_ne!(first.prefix, different.prefix);
            assert_ne!(first.lock, different.lock);
        }
        assert_eq!(first.socket(&format!("{:x}", u32::MAX)).len(), 34);
    }

    /// A directory below `scratch` whose path is `length` bytes, closed to other accounts.
    fn directory_of_length(scratch: &Scratch, length: usize) -> PathBuf {
        let stem = scratch.0.join("run-user");
        let missing = length - stem.as_os_str().as_bytes().len() - 1;
        let directory = stem.join("d".repeat(missing));
        fs::create_dir_all(&directory).unwrap();
        fs::set_permissions(&directory, fs::Permissions::from_mode(0o700)).unwrap();
        assert_eq!(directory.as_os_str().as_bytes().len(), length);
        directory
    }

    /// A storage-root-scoped key of its real length claims under a long runtime
    /// directory, for both channels, and the two never share a lock.
    #[test]
    fn a_root_scoped_key_of_real_length_claims_under_a_long_directory() {
        let scratch = Scratch::new("long");
        let directory = directory_of_length(&scratch, 60);
        let root = "ab".repeat(32);
        let stable = format!("md.neve.cadrumo.root.{root}");
        let preview = format!("md.neve.cadrumo.preview.root.{root}");
        let held = primary(&directory, &stable, SESSION);
        let widest = names(&stable).socket(&format!("{:x}", u32::MAX));
        assert!(directory.join(widest).as_os_str().as_bytes().len() < SOCKET_PATH_LIMIT);
        assert_eq!(claim(&directory, &preview, SESSION).unwrap(), "primary");
        let contender = claim_in(
            &directory,
            &stable,
            SESSION,
            Duration::from_millis(600),
            &unverified,
        );
        assert_eq!(contender.err().unwrap().kind(), io::ErrorKind::TimedOut);
        drop(held);
    }

    /// A socket path at the platform bound is refused before the lock file opens.
    #[test]
    fn a_socket_path_beyond_the_bound_is_refused_before_anything_is_created() {
        let scratch = Scratch::new("bound");
        let key = format!("md.neve.cadrumo.root.{}", "ab".repeat(32));
        let leaf = names(&key).socket(SESSION).len() + 1;
        let fits = directory_of_length(&scratch, SOCKET_PATH_LIMIT - 1 - leaf);
        assert_eq!(claim(&fits, &key, SESSION).unwrap(), "primary");
        let beyond = directory_of_length(&scratch, SOCKET_PATH_LIMIT - leaf);
        let refused = claim(&beyond, &key, SESSION).err().unwrap();
        assert_eq!(refused.kind(), io::ErrorKind::InvalidInput);
        assert!(!beyond.join(names(&key).lock).exists());
    }

    /// The runtime directory must be named, absolute and closed to other accounts.
    #[cfg(target_os = "linux")]
    #[test]
    fn the_runtime_directory_must_be_named_absolute_and_private() {
        let scratch = Scratch::new("xdg");
        let named = |path: &Path| runtime_directory_named(Some(path.as_os_str().to_owned()));
        assert_eq!(named(&scratch.0).unwrap(), scratch.0);
        assert_eq!(
            runtime_directory_named(None).err().unwrap().kind(),
            io::ErrorKind::NotFound
        );
        assert_eq!(
            named(Path::new("relative/run")).err().unwrap().kind(),
            io::ErrorKind::NotFound
        );
        fs::set_permissions(&scratch.0, fs::Permissions::from_mode(0o755)).unwrap();
        assert_eq!(
            named(&scratch.0).err().unwrap().kind(),
            io::ErrorKind::PermissionDenied
        );
    }
}
