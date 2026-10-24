//! The pinned transfer: one archive, fetched over approved HTTPS hops, retried while the
//! fault is transient, resumed from its partial bytes, and accepted only at its pinned
//! size and SHA-256.
//!
//! Hop policy, for every request and every redirect: HTTPS on the default port, an address
//! without credentials, a host that is both declared and in the approved plan, and at most
//! five redirects in one chain. An unapproved hop is `blocked_by_network`, and bytes that
//! do not match the pin are `damaged_download`; neither is retried, and no other source is
//! tried after them; nor after a full disk, a refused permission or a cancellation. Every
//! other failure on one source gives way to the next source, and a source whose failure
//! was final is not asked again when the others are retried.
//!
//! Retry follows the setup contract: a transient fault (a reset, refused or timed-out
//! connection, a resolver failure, an HTTP 5xx or 429, a body that ended early) waits from
//! 2 s, doubling to at most 60 s, with jitter adding up to half of each wait but never
//! passing 60 s, for at most 6 attempts inside 15 minutes. Each wait is announced before it starts and observes
//! cancellation. Cancellation is checked between chunks, not during a blocked read; the
//! connection's own I/O bound ends such a read.
//!
//! The partial file belongs to the caller, who holds the item's writer lock. Its bytes
//! survive an interruption and are resumed with a `Range` request; a server that ignores
//! the range is read from the start again.

use super::{
    connection::{ConnectFailure, Network, Stage},
    failure::{FailureCategory, TransferFailure},
    http::{self, Body, Framing},
    url::HttpsUrl,
};
use crate::{
    component::Cancellation,
    error::Error,
    value::{HostName, Sha256Digest},
};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeSet, hash_map::RandomState},
    fs::{self, File},
    hash::BuildHasher,
    io::{self, BufReader, Read, Seek, SeekFrom, Write},
    path::Path,
    time::{Duration, Instant},
};

/// The longest redirect chain one request may follow.
pub const MAX_REDIRECTS: usize = 5;
const CHUNK_BYTES: usize = 64 * 1024;

/// Backoff bounds for transient transfer failures.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RetryPolicy {
    pub initial_delay: Duration,
    pub max_delay: Duration,
    pub max_attempts: u32,
    pub window: Duration,
}

impl Default for RetryPolicy {
    fn default() -> Self {
        Self {
            initial_delay: Duration::from_secs(2),
            max_delay: Duration::from_secs(60),
            max_attempts: 6,
            window: Duration::from_secs(15 * 60),
        }
    }
}

impl RetryPolicy {
    /// The wait before retry number `retry` (1 for the first) with `jitter` in `[0, 1]`:
    /// the base doubles from the initial delay to the maximum, and jitter adds up to half
    /// the base on top, so retries never bunch together, never come sooner than the base,
    /// and never wait longer than the maximum.
    pub fn delay(&self, retry: u32, jitter: f64) -> Duration {
        let doubling = 1u32
            .checked_shl(retry.saturating_sub(1))
            .unwrap_or(u32::MAX);
        let base = self
            .initial_delay
            .checked_mul(doubling)
            .unwrap_or(self.max_delay)
            .min(self.max_delay);
        base.mul_f64(1.0 + 0.5 * jitter.clamp(0.0, 1.0))
            .min(self.max_delay)
    }
}

/// The clock and randomness the retry loop runs on. The engine uses [`SystemPacing`]; an
/// owner that must observe the schedule without waiting supplies its own.
pub trait Pacing {
    /// Time since the first attempt began.
    fn elapsed(&self) -> Duration;
    /// Waits `delay`, returning early with `Error::Cancelled` once `cancellation` is set.
    fn wait(&mut self, delay: Duration, cancellation: &Cancellation) -> Result<(), Error>;
    /// A fraction in `[0, 1]`.
    fn jitter(&mut self) -> f64;
}

/// Real time, and jitter from the process's randomly keyed hasher.
pub struct SystemPacing {
    started: Instant,
    state: RandomState,
    draws: u64,
}

impl Default for SystemPacing {
    fn default() -> Self {
        Self {
            started: Instant::now(),
            state: RandomState::new(),
            draws: 0,
        }
    }
}

impl Pacing for SystemPacing {
    fn elapsed(&self) -> Duration {
        self.started.elapsed()
    }

    fn wait(&mut self, delay: Duration, cancellation: &Cancellation) -> Result<(), Error> {
        let until = Instant::now() + delay;
        loop {
            cancellation.check()?;
            let left = until.saturating_duration_since(Instant::now());
            if left.is_zero() {
                return Ok(());
            }
            std::thread::sleep(left.min(Duration::from_millis(100)));
        }
    }

    fn jitter(&mut self) -> f64 {
        self.draws += 1;
        (self.state.hash_one(self.draws) >> 11) as f64 / (1u64 << 53) as f64
    }
}

/// What a running transfer reports.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TransferEvent {
    /// Bytes held so far, out of the pinned size; resumed bytes count from the start.
    Progress { completed: u64, total: u64 },
    /// A transient failure is retried as `attempt` after `delay`; reported before waiting.
    Retrying { attempt: u32, delay: Duration },
}

/// One pinned archive and its sources, in the order they are tried.
#[derive(Clone, Copy, Debug)]
pub struct Pinned<'a> {
    pub sources: &'a [HttpsUrl],
    pub size: u64,
    pub sha256: &'a Sha256Digest,
}

/// One transfer's network, approved hosts, retry schedule, event sink and cancellation.
pub struct Transfer<'a> {
    pub network: &'a Network,
    /// Hosts both declared and in the approved plan; no hop may leave them.
    pub hosts: &'a BTreeSet<HostName>,
    pub policy: RetryPolicy,
    pub pacing: &'a mut dyn Pacing,
    pub events: &'a mut dyn FnMut(TransferEvent),
    pub cancellation: &'a Cancellation,
}

enum Attempt {
    Done,
    Failed(TransferFailure),
}

impl Transfer<'_> {
    /// Fetches `pinned` into `partial`, which holds exactly the pinned bytes on success.
    /// A failure leaves resumable bytes in place, except damaged bytes, which are removed.
    pub fn fetch(&mut self, pinned: Pinned<'_>, partial: &Path) -> Result<(), Error> {
        if pinned.sources.is_empty() || pinned.size == 0 {
            return Err(Error::Invalid(
                "a pinned transfer needs a source and a size".into(),
            ));
        }
        // A source whose failure was final is not asked again; the others are retried.
        let mut exhausted = vec![false; pinned.sources.len()];
        let mut last = None;
        for attempt in 1..=self.policy.max_attempts {
            self.cancellation.check()?;
            let mut retryable = false;
            for (source, done) in pinned.sources.iter().zip(exhausted.iter_mut()) {
                if *done {
                    continue;
                }
                match self.attempt(source, pinned, partial)? {
                    Attempt::Done => return Ok(()),
                    Attempt::Failed(found) if stops_every_source(found.category) => {
                        return Err(final_failure(found, attempt));
                    }
                    Attempt::Failed(found) => {
                        retryable |= found.transient;
                        *done = !found.transient;
                        last = Some(found);
                    }
                }
            }
            let failure =
                last.unwrap_or_else(|| TransferFailure::final_(FailureCategory::Unexpected));
            if !retryable || attempt == self.policy.max_attempts {
                return Err(final_failure(failure, attempt));
            }
            let delay = self.policy.delay(attempt, self.pacing.jitter());
            if self.pacing.elapsed() + delay > self.policy.window {
                return Err(final_failure(failure, attempt));
            }
            (self.events)(TransferEvent::Retrying {
                attempt: attempt + 1,
                delay,
            });
            self.pacing.wait(delay, self.cancellation)?;
        }
        Err(Error::Download(TransferFailure::final_(
            FailureCategory::Unexpected,
        )))
    }

    /// One request chain against one source. `Err` is only cancellation or a final local
    /// refusal; every network outcome is an `Attempt`.
    fn attempt(
        &mut self,
        source: &HttpsUrl,
        pinned: Pinned<'_>,
        partial: &Path,
    ) -> Result<Attempt, Error> {
        let mut file = match open_partial(partial) {
            Ok(file) => file,
            Err(error) => return Ok(Attempt::Failed(file_failure(&error))),
        };
        let mut held = match file.metadata() {
            Ok(meta) => meta.len(),
            Err(error) => return Ok(Attempt::Failed(file_failure(&error))),
        };
        if held > pinned.size {
            if let Err(error) = file.set_len(0) {
                return Ok(Attempt::Failed(file_failure(&error)));
            }
            held = 0;
        }
        let mut hash = Sha256::new();
        if held > 0 {
            file.seek(SeekFrom::Start(0)).map_err(Error::Io)?;
            if let Err(error) = hash_prefix(&mut file, held, &mut hash, self.cancellation) {
                return match error {
                    Error::Io(error) => Ok(Attempt::Failed(file_failure(&error))),
                    other => Err(other),
                };
            }
        }
        if held == pinned.size {
            return finish(file, hash, pinned, partial);
        }
        let cancellation = self.cancellation;
        let stop = move || cancellation.check().is_err();
        let mut url = source.clone();
        let mut redirects = 0;
        loop {
            self.cancellation.check()?;
            if !self.admitted(&url) {
                return Ok(Attempt::Failed(TransferFailure::final_(
                    FailureCategory::BlockedByNetwork,
                )));
            }
            let mut stream = match self.network.open(&url, None) {
                Ok(stream) => stream,
                Err(failure) => return Ok(Attempt::Failed(connect_failure(&failure))),
            };
            let range = format!("bytes={held}-");
            let headers: &[(&str, &str)] = if held > 0 { &[("Range", &range)] } else { &[] };
            if let Err(error) =
                http::write_request(&mut stream, "GET", url.target(), &url.authority(), headers)
            {
                return Ok(Attempt::Failed(network_failure(&error)));
            }
            let mut reader = BufReader::with_capacity(CHUNK_BYTES, stream);
            let head = http::read_head(&mut reader, &stop);
            self.cancellation.check()?;
            let head = match head {
                Ok(head) => head,
                Err(error) => return Ok(Attempt::Failed(network_failure(&error))),
            };
            if head.redirect() {
                redirects += 1;
                let next = head
                    .header("location")
                    .map(|location| url.redirect(location));
                match next {
                    Some(Ok(next)) if redirects <= MAX_REDIRECTS => {
                        url = next;
                        continue;
                    }
                    _ => {
                        return Ok(Attempt::Failed(
                            TransferFailure::final_(FailureCategory::BlockedByNetwork)
                                .with_status(head.status),
                        ));
                    }
                }
            }
            if let Some(failure) = TransferFailure::of_status(head.status) {
                return Ok(Attempt::Failed(failure));
            }
            let framing = match Framing::of(&head) {
                Ok(framing) => framing,
                Err(error) => return Ok(Attempt::Failed(network_failure(&error))),
            };
            let expected_range = format!("bytes {held}-{}/{}", pinned.size - 1, pinned.size);
            let resumed =
                head.status == 206 && head.header("content-range") == Some(expected_range.as_str());
            if (head.status == 206 && !resumed) || !matches!(head.status, 200 | 206) {
                return Ok(Attempt::Failed(
                    TransferFailure::final_(FailureCategory::Unexpected).with_status(head.status),
                ));
            }
            if !resumed && held > 0 {
                // The server sent the whole archive: start over from its first byte.
                if let Err(error) = file
                    .set_len(0)
                    .and_then(|()| file.seek(SeekFrom::Start(0)).map(|_| ()))
                {
                    return Ok(Attempt::Failed(file_failure(&error)));
                }
                held = 0;
                hash = Sha256::new();
            }
            if let Framing::Length(length) = framing
                && held.checked_add(length) != Some(pinned.size)
            {
                return Ok(Attempt::Failed(TransferFailure::final_(
                    FailureCategory::DamagedDownload,
                )));
            }
            if let Err(error) = file.seek(SeekFrom::End(0)) {
                return Ok(Attempt::Failed(file_failure(&error)));
            }
            let mut body = Body::new(reader, framing, &stop);
            match self.stream(&mut body, &mut file, &mut hash, held, pinned.size)? {
                Some(failure) => return Ok(Attempt::Failed(failure)),
                None => return finish(file, hash, pinned, partial),
            }
        }
    }

    fn admitted(&self, url: &HttpsUrl) -> bool {
        url.default_port() && self.hosts.contains(url.host())
    }

    /// Copies the body into the partial file, hashing and reporting as it goes.
    fn stream(
        &mut self,
        body: &mut impl Read,
        file: &mut File,
        hash: &mut Sha256,
        mut held: u64,
        size: u64,
    ) -> Result<Option<TransferFailure>, Error> {
        let mut buffer = vec![0u8; CHUNK_BYTES];
        loop {
            self.cancellation.check()?;
            let read = body.read(&mut buffer);
            self.cancellation.check()?;
            let read = match read {
                Ok(0) => return Ok(None),
                Ok(read) => read,
                Err(error) => return Ok(Some(network_failure(&error))),
            };
            if held + read as u64 > size {
                return Ok(Some(TransferFailure::final_(
                    FailureCategory::DamagedDownload,
                )));
            }
            if let Err(error) = file.write_all(&buffer[..read]) {
                return Ok(Some(file_failure(&error)));
            }
            hash.update(&buffer[..read]);
            held += read as u64;
            (self.events)(TransferEvent::Progress {
                completed: held,
                total: size,
            });
        }
    }
}

/// Failures no other source can cure: the bytes, the network's policy, the disk, the
/// permissions or the person decided. Every other failure gives way to the next source.
fn stops_every_source(category: FailureCategory) -> bool {
    matches!(
        category,
        FailureCategory::DamagedDownload
            | FailureCategory::BlockedByNetwork
            | FailureCategory::DiskFull
            | FailureCategory::NoPermission
            | FailureCategory::Cancelled
    )
}

fn final_failure(mut failure: TransferFailure, attempts: u32) -> Error {
    failure.transient = false;
    failure.attempts = attempts;
    Error::Download(failure)
}

/// Accepts the partial file at exactly the pinned size and digest; damaged bytes are
/// removed so the next attempt starts clean.
fn finish(file: File, hash: Sha256, pinned: Pinned<'_>, partial: &Path) -> Result<Attempt, Error> {
    if let Err(error) = file.sync_all() {
        return Ok(Attempt::Failed(file_failure(&error)));
    }
    let size = file.metadata().map_err(Error::Io)?.len();
    drop(file);
    if size == pinned.size && Sha256Digest::from_hash(hash.finalize())? == *pinned.sha256 {
        return Ok(Attempt::Done);
    }
    fs::remove_file(partial)?;
    Ok(Attempt::Failed(TransferFailure::final_(
        FailureCategory::DamagedDownload,
    )))
}

fn open_partial(path: &Path) -> io::Result<File> {
    crate::filesystem::refuse_links(path)
        .map_err(|_| io::Error::from(io::ErrorKind::PermissionDenied))?;
    File::options()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(path)
}

fn hash_prefix(
    file: &mut File,
    length: u64,
    hash: &mut Sha256,
    cancellation: &Cancellation,
) -> Result<(), Error> {
    let mut buffer = vec![0u8; CHUNK_BYTES];
    let mut left = length;
    while left > 0 {
        cancellation.check()?;
        let want = buffer
            .len()
            .min(usize::try_from(left).unwrap_or(usize::MAX));
        file.read_exact(&mut buffer[..want])?;
        hash.update(&buffer[..want]);
        left -= want as u64;
    }
    Ok(())
}

/// A local file failure: the volume's space and permissions decide, never a retry.
pub(crate) fn file_failure(error: &io::Error) -> TransferFailure {
    // Windows' ERROR_HANDLE_DISK_FULL and ERROR_DISK_FULL, where a kind is not mapped.
    let full = matches!(
        error.kind(),
        io::ErrorKind::StorageFull | io::ErrorKind::QuotaExceeded
    ) || (cfg!(windows) && matches!(error.raw_os_error(), Some(39 | 112)));
    let category = if full {
        FailureCategory::DiskFull
    } else if matches!(
        error.kind(),
        io::ErrorKind::PermissionDenied | io::ErrorKind::ReadOnlyFilesystem
    ) {
        FailureCategory::NoPermission
    } else {
        FailureCategory::Unexpected
    };
    TransferFailure::final_(category)
}

/// A failure on an open connection: a broken, stalled, truncated or garbled answer.
fn network_failure(error: &io::Error) -> TransferFailure {
    if error.kind() == io::ErrorKind::InvalidData
        && error
            .get_ref()
            .is_some_and(|inner| inner.is::<rustls::Error>())
    {
        return TransferFailure::final_(FailureCategory::SecureConnectionFailed);
    }
    TransferFailure::transient(FailureCategory::HostUnreachable)
}

/// A failure before the session was established, classified by the stage it stopped at.
fn connect_failure(failure: &ConnectFailure) -> TransferFailure {
    match failure.stage {
        Stage::Tls => TransferFailure::final_(FailureCategory::SecureConnectionFailed),
        Stage::Tunnel(Some(status)) => match status {
            403 | 407 => TransferFailure::final_(FailureCategory::BlockedByNetwork),
            429 | 500.. => TransferFailure::transient(FailureCategory::HostUnreachable),
            _ => TransferFailure::final_(FailureCategory::HostUnreachable),
        }
        .with_status(status),
        // Resolver failures are temporary on every platform: only Windows reports a missing
        // name apart from a temporary one, and the same fault must not retry on one system
        // and stop on another.
        Stage::Resolve | Stage::Connect | Stage::Tunnel(None) | Stage::Io => {
            TransferFailure::transient(FailureCategory::HostUnreachable)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::provisioning::{
        proxy::{PROXY_BYPASS, PROXY_URL, ProxySettings},
        test_servers::{
            ProxyAnswer, ProxyServer, Reply, Request, TestCertificate, TlsServer, network_nowhere,
            network_to, response,
        },
    };
    use std::sync::{
        Arc, Mutex,
        atomic::{AtomicUsize, Ordering},
    };

    const HOSTS: [&str; 3] = [
        "cdn.example.com",
        "mirror.example.com",
        "elsewhere.example.com",
    ];

    /// A clock that advances by exactly what is waited, and fixed jitter.
    struct RecordedPacing {
        now: Duration,
        waits: Vec<Duration>,
    }

    impl RecordedPacing {
        fn new() -> Self {
            Self {
                now: Duration::ZERO,
                waits: Vec::new(),
            }
        }
    }

    impl Pacing for RecordedPacing {
        fn elapsed(&self) -> Duration {
            self.now
        }
        fn wait(&mut self, delay: Duration, cancellation: &Cancellation) -> Result<(), Error> {
            cancellation.check()?;
            self.waits.push(delay);
            self.now += delay;
            cancellation.check()
        }
        fn jitter(&mut self) -> f64 {
            0.5
        }
    }

    fn payload(size: usize) -> Vec<u8> {
        (0..size).map(|index| (index * 31 % 251) as u8).collect()
    }

    fn approved(names: &[&str]) -> BTreeSet<HostName> {
        names
            .iter()
            .map(|name| HostName::new(*name).unwrap())
            .collect()
    }

    fn url(value: &str) -> HttpsUrl {
        HttpsUrl::parse(value).unwrap()
    }

    struct Run {
        result: Result<(), Error>,
        events: Vec<TransferEvent>,
        waits: Vec<Duration>,
    }

    fn run(
        network: &Network,
        hosts: &[&str],
        sources: &[&str],
        bytes: &[u8],
        partial: &Path,
    ) -> Run {
        run_with(
            network,
            hosts,
            sources,
            bytes,
            partial,
            RetryPolicy::default(),
        )
    }

    fn run_with(
        network: &Network,
        hosts: &[&str],
        sources: &[&str],
        bytes: &[u8],
        partial: &Path,
        policy: RetryPolicy,
    ) -> Run {
        let hosts = approved(hosts);
        let sources: Vec<HttpsUrl> = sources.iter().map(|value| url(value)).collect();
        let digest = Sha256Digest::of(bytes);
        let mut pacing = RecordedPacing::new();
        let mut events = Vec::new();
        let cancellation = Cancellation::default();
        let result = {
            let mut sink = |event| events.push(event);
            let mut transfer = Transfer {
                network,
                hosts: &hosts,
                policy,
                pacing: &mut pacing,
                events: &mut sink,
                cancellation: &cancellation,
            };
            transfer.fetch(
                Pinned {
                    sources: &sources,
                    size: bytes.len() as u64,
                    sha256: &digest,
                },
                partial,
            )
        };
        Run {
            result,
            events,
            waits: pacing.waits,
        }
    }

    fn failure(run: &Run) -> TransferFailure {
        match &run.result {
            Err(Error::Download(failure)) => *failure,
            other => panic!("expected a download failure, got {other:?}"),
        }
    }

    fn empty(status: &str) -> Reply {
        Reply::Bytes(response(status, &[("Content-Length", "0".into())], b""))
    }

    /// Serves `bytes`, honouring a `Range` request.
    fn serving(bytes: Vec<u8>) -> impl Fn(&Request) -> Reply + Send + Sync + 'static {
        move |request: &Request| {
            let size = bytes.len();
            let start = request
                .header("range")
                .and_then(|range| range.strip_prefix("bytes="))
                .and_then(|range| range.strip_suffix("-"))
                .and_then(|start| start.parse::<usize>().ok());
            match start {
                Some(start) => Reply::Bytes(response(
                    "206 Partial Content",
                    &[
                        ("Content-Length", (size - start).to_string()),
                        (
                            "Content-Range",
                            format!("bytes {start}-{}/{size}", size - 1),
                        ),
                    ],
                    &bytes[start..],
                )),
                None => Reply::Bytes(response(
                    "200 OK",
                    &[("Content-Length", size.to_string())],
                    &bytes,
                )),
            }
        }
    }

    fn setup(
        handler: impl Fn(&Request) -> Reply + Send + Sync + 'static,
    ) -> (TestCertificate, TlsServer, tempfile::TempDir) {
        let certificate = TestCertificate::new(&HOSTS);
        let server = TlsServer::start(&certificate, handler);
        (certificate, server, tempfile::tempdir().unwrap())
    }

    const SOURCE: &str = "https://cdn.example.com/a.zip";

    #[test]
    fn a_fresh_download_holds_exactly_the_pinned_bytes_and_reports_byte_progress() {
        let bytes = payload(200_000);
        let (certificate, server, directory) = setup(serving(bytes.clone()));
        let network = network_to(certificate.roots(), server.address(), None);
        let partial = directory.path().join("a.part");
        let run = run(&network, &HOSTS[..1], &[SOURCE], &bytes, &partial);
        run.result.unwrap();
        assert_eq!(std::fs::read(&partial).unwrap(), bytes);
        let completed: Vec<u64> = run
            .events
            .iter()
            .map(|event| match event {
                TransferEvent::Progress { completed, total } => {
                    assert_eq!(*total, bytes.len() as u64);
                    *completed
                }
                other => panic!("{other:?}"),
            })
            .collect();
        assert!(completed.windows(2).all(|pair| pair[0] < pair[1]));
        assert_eq!(completed.last(), Some(&(bytes.len() as u64)));
        assert_eq!(server.targets(), ["/a.zip"]);
        let requests = server.requests.lock().unwrap();
        assert!(requests[0].header("range").is_none());
        assert_eq!(requests[0].header("accept-encoding"), Some("identity"));
    }

    #[test]
    fn partial_bytes_resume_with_a_range_and_a_server_ignoring_it_restarts() {
        let bytes = payload(150_000);
        let (certificate, server, directory) = setup(serving(bytes.clone()));
        let network = network_to(certificate.roots(), server.address(), None);
        let partial = directory.path().join("a.part");
        std::fs::write(&partial, &bytes[..60_000]).unwrap();
        let resumed = run(&network, &HOSTS[..1], &[SOURCE], &bytes, &partial);
        resumed.result.unwrap();
        assert_eq!(std::fs::read(&partial).unwrap(), bytes);
        assert_eq!(
            server.requests.lock().unwrap()[0].header("range"),
            Some("bytes=60000-")
        );
        assert!(matches!(
            resumed.events.first(),
            Some(TransferEvent::Progress { completed, .. }) if *completed > 60_000
        ));

        let whole = bytes.clone();
        let (certificate, server, directory) = setup(move |_: &Request| {
            Reply::Bytes(response(
                "200 OK",
                &[("Content-Length", whole.len().to_string())],
                &whole,
            ))
        });
        let network = network_to(certificate.roots(), server.address(), None);
        let partial = directory.path().join("b.part");
        std::fs::write(&partial, &bytes[..60_000]).unwrap();
        run(&network, &HOSTS[..1], &[SOURCE], &bytes, &partial)
            .result
            .unwrap();
        assert_eq!(std::fs::read(&partial).unwrap(), bytes);
    }

    #[test]
    fn a_truncated_body_is_retried_after_the_announced_wait_and_resumed() {
        let bytes = payload(120_000);
        let served = AtomicUsize::new(0);
        let full = serving(bytes.clone());
        let cut = bytes.clone();
        let (certificate, server, directory) = setup(move |request: &Request| {
            if served.fetch_add(1, Ordering::SeqCst) == 0 {
                return Reply::Cut(response(
                    "200 OK",
                    &[("Content-Length", cut.len().to_string())],
                    &cut[..50_000],
                ));
            }
            full(request)
        });
        let network = network_to(certificate.roots(), server.address(), None);
        let partial = directory.path().join("a.part");
        let run = run(&network, &HOSTS[..1], &[SOURCE], &bytes, &partial);
        run.result.unwrap();
        assert_eq!(std::fs::read(&partial).unwrap(), bytes);
        assert_eq!(run.waits, [Duration::from_millis(2500)]);
        assert!(run.events.contains(&TransferEvent::Retrying {
            attempt: 2,
            delay: Duration::from_millis(2500)
        }));
        let requests = server.requests.lock().unwrap();
        assert_eq!(requests.len(), 2);
        let range = requests[1].header("range").unwrap();
        assert!(
            range.starts_with("bytes=") && range != "bytes=0-",
            "{range}"
        );
    }

    #[test]
    fn transient_statuses_are_retried_within_the_budget_and_then_reported_final() {
        let (certificate, server, directory) = setup(|_: &Request| empty("503 Busy"));
        let network = network_to(certificate.roots(), server.address(), None);
        let run = run(
            &network,
            &HOSTS[..1],
            &[SOURCE],
            b"bytes",
            &directory.path().join("a.part"),
        );
        let failure = failure(&run);
        assert_eq!(failure.category, FailureCategory::HostUnreachable);
        assert!(!failure.transient);
        assert_eq!((failure.attempts, failure.http_status), (6, Some(503)));
        assert_eq!(
            run.waits,
            [2, 4, 8, 16, 32].map(|seconds| Duration::from_secs(seconds).mul_f64(1.25))
        );
        assert_eq!(server.targets().len(), 6);

        let answered = AtomicUsize::new(0);
        let bytes = payload(10_000);
        let ok = serving(bytes.clone());
        let (certificate, server, directory) = setup(move |request: &Request| {
            if answered.fetch_add(1, Ordering::SeqCst) == 0 {
                empty("429 Slow down")
            } else {
                ok(request)
            }
        });
        let network = network_to(certificate.roots(), server.address(), None);
        let retried = super::tests::run(
            &network,
            &HOSTS[..1],
            &[SOURCE],
            &bytes,
            &directory.path().join("a.part"),
        );
        retried.result.unwrap();
        assert_eq!(retried.waits.len(), 1);
    }

    #[test]
    fn the_retry_window_stops_a_retry_that_would_start_after_it_closes() {
        let (certificate, server, directory) = setup(|_: &Request| empty("500 Down"));
        let network = network_to(certificate.roots(), server.address(), None);
        let policy = RetryPolicy {
            window: Duration::from_secs(4),
            ..RetryPolicy::default()
        };
        let run = run_with(
            &network,
            &HOSTS[..1],
            &[SOURCE],
            b"bytes",
            &directory.path().join("a.part"),
            policy,
        );
        assert_eq!(failure(&run).attempts, 2);
        assert_eq!(run.waits, [Duration::from_millis(2500)]);
    }

    #[test]
    fn permanent_statuses_and_damaged_bytes_are_final_on_the_first_attempt() {
        let (certificate, server, directory) = setup(|_: &Request| empty("404 Not Found"));
        let network = network_to(certificate.roots(), server.address(), None);
        let run = run(
            &network,
            &HOSTS[..1],
            &[SOURCE],
            b"bytes",
            &directory.path().join("a.part"),
        );
        let found = failure(&run);
        assert_eq!(
            (found.category, found.attempts, found.http_status),
            (FailureCategory::Unexpected, 1, Some(404))
        );
        assert!(run.waits.is_empty());

        let pinned = payload(5_000);
        let mut other = pinned.clone();
        other[100] ^= 0xff;
        let (certificate, server, directory) = setup(serving(other));
        let network = network_to(certificate.roots(), server.address(), None);
        let partial = directory.path().join("a.part");
        let run = super::tests::run(
            &network,
            &HOSTS[..2],
            &[SOURCE, "https://mirror.example.com/a.zip"],
            &pinned,
            &partial,
        );
        assert_eq!(failure(&run).category, FailureCategory::DamagedDownload);
        assert!(!partial.exists(), "damaged bytes must not be resumed");
        assert_eq!(
            server.targets().len(),
            1,
            "no other source after damaged bytes"
        );

        for reply in [
            response("200 OK", &[("Content-Length", "10".into())], b"0123456789"),
            response("200 OK", &[], &payload(5_001)),
        ] {
            let reply = Arc::new(Mutex::new(Some(reply)));
            let (certificate, server, directory) = setup(move |_: &Request| {
                Reply::Bytes(reply.lock().unwrap().take().unwrap_or_default())
            });
            let network = network_to(certificate.roots(), server.address(), None);
            let run = super::tests::run(
                &network,
                &HOSTS[..1],
                &[SOURCE],
                &pinned,
                &directory.path().join("a.part"),
            );
            assert_eq!(failure(&run).category, FailureCategory::DamagedDownload);
            assert_eq!(server.targets().len(), 1);
        }
    }

    const MIRROR: &str = "https://mirror.example.com/a.zip";

    /// Serves the archive at `/a.zip` and answers every other target with `status`.
    fn archive_or(
        status: &'static str,
        bytes: Vec<u8>,
    ) -> impl Fn(&Request) -> Reply + Send + Sync + 'static {
        let ok = serving(bytes);
        move |request: &Request| match request.target() {
            "/a.zip" => ok(request),
            _ => empty(status),
        }
    }

    #[test]
    fn a_final_status_on_one_source_gives_way_to_the_next_source() {
        let bytes = payload(8_000);
        for status in ["404 Not Found", "416 Range Not Satisfiable", "410 Gone"] {
            let (certificate, server, directory) = setup(archive_or(status, bytes.clone()));
            let network = network_to(certificate.roots(), server.address(), None);
            let partial = directory.path().join("a.part");
            let run = run(
                &network,
                &HOSTS[..2],
                &["https://cdn.example.com/missing", MIRROR],
                &bytes,
                &partial,
            );
            run.result.unwrap();
            assert_eq!(std::fs::read(&partial).unwrap(), bytes, "{status}");
            assert_eq!(server.targets(), ["/missing", "/a.zip"], "{status}");
            assert!(run.waits.is_empty(), "{status}");
        }
    }

    #[test]
    fn a_refused_certificate_or_an_unresolvable_name_gives_way_to_the_next_source() {
        let bytes = payload(8_000);
        let mirror_only = TestCertificate::new(&["mirror.example.com"]);
        let server = TlsServer::start(&mirror_only, serving(bytes.clone()));
        let directory = tempfile::tempdir().unwrap();
        let network = network_to(mirror_only.roots(), server.address(), None);
        let partial = directory.path().join("tls.part");
        let run = run(&network, &HOSTS[..2], &[SOURCE, MIRROR], &bytes, &partial);
        run.result.unwrap();
        assert_eq!(std::fs::read(&partial).unwrap(), bytes);
        assert!(run.waits.is_empty());
        assert_eq!(server.targets(), ["/a.zip"]);

        let (certificate, server, directory) = setup(serving(bytes.clone()));
        let address = server.address();
        // The Windows code for a name that does not exist: it must read as on any system.
        let resolve: Arc<crate::provisioning::connection::Resolve> =
            Arc::new(move |host: &str, _: u16| {
                if host == "cdn.example.com" {
                    Err(io::Error::from_raw_os_error(11001))
                } else {
                    Ok(vec![address])
                }
            });
        let network = Network::with_parts(certificate.roots(), resolve, None);
        let partial = directory.path().join("dns.part");
        let run = super::tests::run(&network, &HOSTS[..2], &[SOURCE, MIRROR], &bytes, &partial);
        run.result.unwrap();
        assert_eq!(std::fs::read(&partial).unwrap(), bytes);
        assert!(run.waits.is_empty());
    }

    #[test]
    fn a_resolver_failure_classifies_alike_on_every_system() {
        for os_code in [None, Some(11001), Some(11002), Some(-2)] {
            let found = connect_failure(&ConnectFailure {
                stage: Stage::Resolve,
                connected: false,
                io_kind: None,
                os_code,
            });
            assert_eq!(
                (found.category, found.transient),
                (FailureCategory::HostUnreachable, true),
                "{os_code:?}"
            );
        }
    }

    #[test]
    fn every_source_failing_reports_the_last_and_retries_only_the_transient_ones() {
        let (certificate, server, directory) = setup(|request: &Request| match request.target() {
            "/missing" => empty("404 Not Found"),
            "/gone" => empty("416 Range Not Satisfiable"),
            _ => empty("503 Busy"),
        });
        let network = network_to(certificate.roots(), server.address(), None);
        let run = run(
            &network,
            &HOSTS[..2],
            &[
                "https://cdn.example.com/missing",
                "https://mirror.example.com/gone",
            ],
            b"bytes",
            &directory.path().join("a.part"),
        );
        let found = failure(&run);
        assert_eq!(
            (found.category, found.attempts, found.http_status),
            (FailureCategory::Unexpected, 1, Some(416))
        );
        assert!(!found.transient);
        assert!(run.waits.is_empty());
        assert_eq!(server.targets(), ["/missing", "/gone"]);

        server.requests.lock().unwrap().clear();
        let run = super::tests::run(
            &network,
            &HOSTS[..2],
            &[
                "https://cdn.example.com/missing",
                "https://mirror.example.com/busy",
            ],
            b"bytes",
            &directory.path().join("b.part"),
        );
        let found = failure(&run);
        assert_eq!(
            (found.category, found.attempts, found.http_status),
            (FailureCategory::HostUnreachable, 6, Some(503))
        );
        let targets = server.targets();
        assert_eq!(targets.iter().filter(|t| *t == "/missing").count(), 1);
        assert_eq!(targets.iter().filter(|t| *t == "/busy").count(), 6);
        assert_eq!(run.waits.len(), 5);
    }

    #[test]
    fn a_damaged_or_blocked_first_source_stops_every_source() {
        let bytes = payload(4_000);
        let mut damaged = bytes.clone();
        damaged[7] ^= 0xff;
        let ok = serving(bytes.clone());
        let bad = serving(damaged);
        let (certificate, server, directory) =
            setup(move |request: &Request| match request.target() {
                "/damaged" => bad(request),
                "/forbidden" => empty("403 Forbidden"),
                "/away" => Reply::Bytes(response(
                    "302 Found",
                    &[("Location", "https://elsewhere.example.com/a.zip".into())],
                    b"",
                )),
                _ => ok(request),
            });
        let network = network_to(certificate.roots(), server.address(), None);
        for (start, category) in [
            ("damaged", FailureCategory::DamagedDownload),
            ("forbidden", FailureCategory::BlockedByNetwork),
            ("away", FailureCategory::BlockedByNetwork),
        ] {
            server.requests.lock().unwrap().clear();
            let source = format!("https://cdn.example.com/{start}");
            let run = run(
                &network,
                &HOSTS[..2],
                &[source.as_str(), MIRROR],
                &bytes,
                &directory.path().join(format!("{start}.part")),
            );
            let found = failure(&run);
            assert_eq!((found.category, found.attempts), (category, 1), "{start}");
            assert!(run.waits.is_empty(), "{start}");
            assert!(
                !server.targets().contains(&"/a.zip".to_owned()),
                "{start}: no other source after it"
            );
        }
    }

    #[test]
    fn redirects_follow_only_approved_https_hops_on_the_default_port_and_at_most_five() {
        let bytes = payload(4_000);
        let ok = serving(bytes.clone());
        let redirect = |status: &str, location: &str| {
            Reply::Bytes(response(status, &[("Location", location.to_owned())], b""))
        };
        let (certificate, server, directory) =
            setup(move |request: &Request| match request.target() {
                "/start" => redirect("302 Found", "https://mirror.example.com/final"),
                "/elsewhere" => redirect("301 Moved", "https://elsewhere.example.com/final"),
                "/plain" => redirect("307 Temporary", "http://mirror.example.com/final"),
                "/port" => redirect("308 Permanent", "https://mirror.example.com:8443/final"),
                "/loop" => redirect("302 Found", "/loop"),
                "/nowhere" => Reply::Bytes(response("302 Found", &[], b"")),
                _ => ok(request),
            });
        let network = network_to(certificate.roots(), server.address(), None);
        let approved = &HOSTS[..2];
        run(
            &network,
            approved,
            &["https://cdn.example.com/start"],
            &bytes,
            &directory.path().join("ok.part"),
        )
        .result
        .unwrap();
        assert_eq!(server.targets(), ["/start", "/final"]);
        for start in ["elsewhere", "plain", "port", "nowhere", "loop"] {
            server.requests.lock().unwrap().clear();
            let source = format!("https://cdn.example.com/{start}");
            let run = run(
                &network,
                approved,
                &[source.as_str()],
                &bytes,
                &directory.path().join(format!("{start}.part")),
            );
            let found = failure(&run);
            assert_eq!(
                (found.category, found.attempts),
                (FailureCategory::BlockedByNetwork, 1),
                "{start}"
            );
            assert!(run.waits.is_empty());
            assert!(!server.targets().contains(&"/final".to_owned()), "{start}");
        }
        assert_eq!(server.targets().len(), MAX_REDIRECTS + 1);
        let run = run(
            &network,
            approved,
            &["https://elsewhere.example.com/a"],
            &bytes,
            &directory.path().join("e.part"),
        );
        assert_eq!(failure(&run).category, FailureCategory::BlockedByNetwork);
    }

    #[test]
    fn a_certificate_this_network_does_not_trust_is_a_final_secure_connection_failure() {
        let bytes = payload(100);
        let (_, server, directory) = setup(serving(bytes.clone()));
        let stranger = TestCertificate::new(&HOSTS);
        let network = network_to(stranger.roots(), server.address(), None);
        let run = run(
            &network,
            &HOSTS[..1],
            &[SOURCE],
            &bytes,
            &directory.path().join("a.part"),
        );
        let found = failure(&run);
        assert_eq!(
            (found.category, found.attempts),
            (FailureCategory::SecureConnectionFailed, 1)
        );
        assert!(run.waits.is_empty());
    }

    #[test]
    fn a_stalled_body_or_an_unresolvable_name_is_a_transient_host_failure() {
        let (certificate, server, directory) = setup(|_: &Request| {
            Reply::Hold(response(
                "200 OK",
                &[("Content-Length", "100".into())],
                b"partial",
            ))
        });
        let mut network = network_to(certificate.roots(), server.address(), None);
        network.io_timeout = Duration::from_millis(200);
        let single = RetryPolicy {
            max_attempts: 1,
            ..RetryPolicy::default()
        };
        let partial = directory.path().join("a.part");
        let run = run_with(
            &network,
            &HOSTS[..1],
            &[SOURCE],
            &payload(100),
            &partial,
            single,
        );
        assert_eq!(failure(&run).category, FailureCategory::HostUnreachable);
        assert_eq!(
            std::fs::read(&partial).unwrap(),
            b"partial",
            "stalled bytes stay resumable"
        );

        let nowhere = network_nowhere(certificate.roots());
        let run = super::tests::run(
            &nowhere,
            &HOSTS[..1],
            &[SOURCE],
            b"x",
            &directory.path().join("b.part"),
        );
        assert_eq!(
            (failure(&run).category, failure(&run).attempts),
            (FailureCategory::HostUnreachable, 6)
        );
    }

    fn proxied(url: String, bypass: &str) -> Option<ProxySettings> {
        let bypass = bypass.to_owned();
        ProxySettings::from_settings(move |name| match name {
            PROXY_URL => Some(url.clone()),
            PROXY_BYPASS => Some(bypass.clone()),
            _ => None,
        })
        .unwrap()
    }

    #[test]
    fn the_proxy_tunnels_with_its_credentials_refuses_as_the_network_and_is_bypassed_when_listed() {
        let bytes = payload(30_000);
        let (certificate, server, directory) = setup(serving(bytes.clone()));
        let proxy = ProxyServer::start(ProxyAnswer::Tunnel(server.address()));
        let network = network_to(
            certificate.roots(),
            server.address(),
            proxied(proxy.url("ada:s%3Acret@"), ""),
        );
        run(
            &network,
            &HOSTS[..1],
            &[SOURCE],
            &bytes,
            &directory.path().join("a.part"),
        )
        .result
        .unwrap();
        {
            let requests = proxy.requests.lock().unwrap();
            assert_eq!(requests[0].line, "CONNECT cdn.example.com:443 HTTP/1.1");
            assert_eq!(
                requests[0].header("proxy-authorization"),
                Some("Basic YWRhOnM6Y3JldA==")
            );
        }

        let refusing = ProxyServer::start(ProxyAnswer::Refuse(407));
        let network = network_to(
            certificate.roots(),
            server.address(),
            proxied(refusing.url(""), ""),
        );
        let run = run(
            &network,
            &HOSTS[..1],
            &[SOURCE],
            &bytes,
            &directory.path().join("b.part"),
        );
        let found = failure(&run);
        assert_eq!(
            (found.category, found.http_status, found.attempts),
            (FailureCategory::BlockedByNetwork, Some(407), 1)
        );

        let bypassed = ProxyServer::start(ProxyAnswer::Refuse(403));
        let network = network_to(
            certificate.roots(),
            server.address(),
            proxied(bypassed.url(""), "example.com"),
        );
        super::tests::run(
            &network,
            &HOSTS[..1],
            &[SOURCE],
            &bytes,
            &directory.path().join("c.part"),
        )
        .result
        .unwrap();
        assert!(bypassed.requests.lock().unwrap().is_empty());
    }

    #[test]
    fn cancellation_stops_between_chunks_and_during_a_retry_wait() {
        let bytes = payload(400_000);
        let (certificate, server, directory) = setup(serving(bytes.clone()));
        let network = network_to(certificate.roots(), server.address(), None);
        let cancellation = Cancellation::default();
        let hosts = approved(&HOSTS[..1]);
        let sources = [url(SOURCE)];
        let digest = Sha256Digest::of(&bytes);
        let mut pacing = RecordedPacing::new();
        let mut chunks = 0;
        let partial = directory.path().join("a.part");
        let result = {
            let mut sink = |event| {
                if let TransferEvent::Progress { .. } = event {
                    chunks += 1;
                    cancellation.cancel();
                }
            };
            Transfer {
                network: &network,
                hosts: &hosts,
                policy: RetryPolicy::default(),
                pacing: &mut pacing,
                events: &mut sink,
                cancellation: &cancellation,
            }
            .fetch(
                Pinned {
                    sources: &sources,
                    size: bytes.len() as u64,
                    sha256: &digest,
                },
                &partial,
            )
        };
        assert!(matches!(result, Err(Error::Cancelled)));
        assert_eq!(chunks, 1);
        assert!(std::fs::metadata(&partial).unwrap().len() < bytes.len() as u64);

        let (certificate, server, directory) = setup(|_: &Request| empty("502 Bad"));
        let network = network_to(certificate.roots(), server.address(), None);
        let cancellation = Cancellation::default();
        let mut pacing = RecordedPacing::new();
        let result = {
            let mut sink = |event| {
                if let TransferEvent::Retrying { .. } = event {
                    cancellation.cancel();
                }
            };
            Transfer {
                network: &network,
                hosts: &hosts,
                policy: RetryPolicy::default(),
                pacing: &mut pacing,
                events: &mut sink,
                cancellation: &cancellation,
            }
            .fetch(
                Pinned {
                    sources: &sources,
                    size: 1,
                    sha256: &digest,
                },
                &directory.path().join("b.part"),
            )
        };
        assert!(matches!(result, Err(Error::Cancelled)));
        assert!(pacing.waits.is_empty());
        assert_eq!(server.targets().len(), 1);
    }

    #[test]
    fn delays_start_at_two_seconds_double_and_never_pass_a_minute() {
        let policy = RetryPolicy::default();
        assert_eq!(policy.delay(1, 0.0), Duration::from_secs(2));
        assert_eq!(policy.delay(1, 1.0), Duration::from_secs(3));
        assert_eq!(policy.delay(2, 0.0), Duration::from_secs(4));
        assert_eq!(policy.delay(3, 1.0), Duration::from_secs(12));
        assert_eq!(policy.delay(5, 1.0), Duration::from_secs(48));
        assert_eq!(policy.delay(6, 0.0), Duration::from_secs(60));
        assert_eq!(policy.delay(6, 1.0), Duration::from_secs(60));
        assert_eq!(policy.delay(40, 1.0), Duration::from_secs(60));
        let mut pacing = SystemPacing::default();
        for _ in 0..64 {
            assert!((0.0..=1.0).contains(&pacing.jitter()));
        }
    }
}
