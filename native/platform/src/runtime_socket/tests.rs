use super::*;
use crate::transport::DarwinTransport;
use std::{
    io::{Read, Write},
    os::unix::{
        fs::{DirBuilderExt, PermissionsExt, symlink},
        net::{UnixListener, UnixStream},
    },
    thread,
    time::{SystemTime, UNIX_EPOCH},
};

const LEAF: &str = "0123456789abcdef0123456789abcdef.sock";

struct Scratch(PathBuf);
impl Scratch {
    fn new() -> Self {
        static NEXT: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(0);
        let path = fs::canonicalize("/tmp").unwrap().join(format!(
            "rs-{}-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::DirBuilder::new().mode(0o700).create(&path).unwrap();
        Self(path)
    }

    fn namespace(&self) -> DarwinTransport {
        DarwinTransport::beneath(&self.0, true).unwrap()
    }

    fn listen(&self) -> UnixListener {
        UnixListener::bind(self.namespace().socket_path(LEAF).unwrap()).unwrap()
    }

    fn connect(&self, deadline: Duration) -> Result<Socket, ConnectRefusal> {
        self.connect_cancellable(deadline, Arc::new(ConnectCancellation::new().unwrap()))
    }

    fn connect_cancellable(
        &self,
        deadline: Duration,
        cancellation: Arc<ConnectCancellation>,
    ) -> Result<Socket, ConnectRefusal> {
        Socket::connect_in(
            DarwinTransport::beneath(&self.0, false)
                .map(|transport| Box::new(transport) as Box<dyn Namespace>),
            LEAF,
            current_uid(),
            Instant::now() + deadline,
            cancellation,
        )
    }
}
impl Drop for Scratch {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).unwrap();
    }
}

fn connected(scratch: &Scratch) -> (Socket, UnixStream) {
    let listener = scratch.listen();
    let accepting = thread::spawn(move || listener.accept().unwrap().0);
    let socket = scratch.connect(Duration::from_secs(5)).unwrap();
    (socket, accepting.join().unwrap())
}

#[test]
fn a_connection_names_this_account_and_process_as_its_kernel_peer_and_carries_bytes() {
    let scratch = Scratch::new();
    let (socket, mut server) = connected(&scratch);
    assert_eq!(
        socket.peer(),
        &Peer {
            process_id: std::process::id(),
            owner_uid: current_uid(),
        }
    );
    let deadline = Instant::now() + Duration::from_secs(5);
    socket.write_all(b"hello", deadline).unwrap();
    let mut received = [0u8; 5];
    server.read_exact(&mut received).unwrap();
    assert_eq!(&received, b"hello");
    server.write_all(b"back").unwrap();
    let mut answer = [0u8; 4];
    socket.read_exact(&mut answer, deadline).unwrap();
    assert_eq!(&answer, b"back");
    drop(server);
    let mut byte = 0u8;
    assert_eq!(
        socket.read_idle_byte(&mut byte).unwrap_err().kind(),
        io::ErrorKind::UnexpectedEof
    );
}

#[test]
fn an_absent_namespace_an_absent_entry_and_a_stale_entry_are_not_ready() {
    let scratch = Scratch::new();
    assert!(matches!(
        scratch.connect(Duration::from_millis(200)),
        Err(ConnectRefusal::NotReady)
    ));
    scratch.namespace();
    assert!(matches!(
        scratch.connect(Duration::from_millis(200)),
        Err(ConnectRefusal::NotReady)
    ));
    drop(scratch.listen());
    let started = Instant::now();
    assert!(matches!(
        scratch.connect(Duration::from_millis(300)),
        Err(ConnectRefusal::NotReady)
    ));
    assert!(started.elapsed() >= Duration::from_millis(250));
}

#[test]
fn an_entry_or_namespace_that_is_not_the_runtimes_own_is_refused() {
    let scratch = Scratch::new();
    let path = scratch.namespace().socket_path(LEAF).unwrap();
    fs::write(&path, b"").unwrap();
    assert!(matches!(
        scratch.connect(Duration::from_millis(200)),
        Err(ConnectRefusal::EndpointUntrusted)
    ));
    fs::remove_file(&path).unwrap();
    let elsewhere = scratch.0.join("elsewhere.sock");
    let _listener = UnixListener::bind(&elsewhere).unwrap();
    symlink(&elsewhere, &path).unwrap();
    assert!(matches!(
        scratch.connect(Duration::from_millis(200)),
        Err(ConnectRefusal::EndpointUntrusted)
    ));
    fs::remove_file(&path).unwrap();
    let directory = scratch.namespace().directory().to_owned();
    fs::set_permissions(&directory, fs::Permissions::from_mode(0o755)).unwrap();
    assert!(matches!(
        scratch.connect(Duration::from_millis(200)),
        Err(ConnectRefusal::EndpointUntrusted)
    ));
    fs::set_permissions(&directory, fs::Permissions::from_mode(0o700)).unwrap();
}

#[test]
fn a_silent_server_ends_a_read_at_its_deadline() {
    let scratch = Scratch::new();
    let (socket, _server) = connected(&scratch);
    let started = Instant::now();
    let mut buffer = [0u8; 4];
    let error = socket
        .read_exact(&mut buffer, Instant::now() + Duration::from_millis(200))
        .unwrap_err();
    assert_eq!(error.kind(), io::ErrorKind::TimedOut);
    assert!(started.elapsed() >= Duration::from_millis(190));
}

#[test]
fn a_close_from_another_thread_ends_an_idle_read_and_a_held_write() {
    let scratch = Scratch::new();
    let (socket, _server) = connected(&scratch);
    let socket = Arc::new(socket);
    let reader = {
        let socket = socket.clone();
        thread::spawn(move || {
            let mut byte = 0u8;
            socket.read_idle_byte(&mut byte)
        })
    };
    let writer = {
        let socket = socket.clone();
        // Far more than the kernel buffers while the server never reads.
        thread::spawn(move || socket.write_all_while_open(&vec![7u8; 16 * 1024 * 1024]))
    };
    thread::sleep(Duration::from_millis(200));
    assert!(!reader.is_finished() && !writer.is_finished());
    socket.close();
    assert!(reader.join().unwrap().is_err());
    assert!(writer.join().unwrap().is_err());
    let mut byte = 0u8;
    assert_eq!(
        socket.read_idle_byte(&mut byte).unwrap_err().kind(),
        io::ErrorKind::ConnectionAborted
    );
}

#[test]
fn a_cancellation_ends_a_connect_that_is_waiting() {
    let scratch = Scratch::new();
    scratch.namespace();
    drop(scratch.listen());
    let cancellation = Arc::new(ConnectCancellation::new().unwrap());
    let cancelling = {
        let cancellation = cancellation.clone();
        thread::spawn(move || {
            thread::sleep(Duration::from_millis(150));
            cancellation.cancel();
        })
    };
    let started = Instant::now();
    assert!(matches!(
        scratch.connect_cancellable(Duration::from_secs(10), cancellation),
        Err(ConnectRefusal::Cancelled)
    ));
    assert!(started.elapsed() < Duration::from_secs(5));
    cancelling.join().unwrap();
}

#[test]
fn a_write_after_the_peer_closed_fails_without_a_signal() {
    let scratch = Scratch::new();
    let (socket, server) = connected(&scratch);
    drop(server);
    let deadline = Instant::now() + Duration::from_secs(5);
    // The first write can land in the buffer before the kernel sees the close.
    let outcome = socket
        .write_all(b"x", deadline)
        .and_then(|()| socket.write_all(b"y", deadline));
    assert_eq!(outcome.unwrap_err().kind(), io::ErrorKind::BrokenPipe);
}

#[test]
fn an_audit_token_admits_only_this_accounts_live_matching_process() {
    let token = |words: [u32; 8]| {
        let mut bytes = [0u8; 32];
        for (index, word) in words.iter().enumerate() {
            bytes[index * 4..index * 4 + 4].copy_from_slice(&word.to_ne_bytes());
        }
        bytes
    };
    let good = [501, 501, 20, 501, 20, 4242, 100_009, 7];
    assert_eq!(
        audit_token_peer(&token(good), 4242, 501),
        Some(Peer {
            process_id: 4242,
            owner_uid: 501
        })
    );
    assert_eq!(audit_token_peer(&token(good), 4243, 501), None);
    assert_eq!(audit_token_peer(&token(good), 4242, 502), None);
    for (index, value) in [
        (0, 502),
        (1, 502),
        (3, 502),
        (5, 0),
        (5, u32::MAX),
        (6, 0),
        (6, 0xFFFF_FFFE),
        (7, 0),
    ] {
        let mut words = good;
        words[index] = value;
        let reported = words[5] as i32;
        assert_eq!(
            audit_token_peer(&token(words), reported, 501),
            None,
            "word {index} = {value}"
        );
    }
}

#[test]
fn a_storage_identity_names_the_resolved_directory_of_this_account() {
    let scratch = Scratch::new();
    let alias = scratch.0.join("alias");
    symlink(&scratch.0, &alias).unwrap();
    let identity = storage_identity(&alias).unwrap();
    let metadata = fs::metadata(&scratch.0).unwrap();
    assert_eq!(
        identity.text(),
        format!("{}:{}:{}", current_uid(), metadata.dev(), metadata.ino())
    );
    let file = scratch.0.join("file");
    fs::write(&file, b"").unwrap();
    assert!(storage_identity(&file).is_err());
    assert!(storage_identity(&scratch.0.join("absent")).is_err());
}
