use super::*;
use crate::provisioning::{
    local_ai::{
        hardware::Hardware,
        models::{LocalModels, Models, SelectedModel},
    },
    state::Observation,
    test_servers::{Reply, Request, TestCertificate, TlsServer, network_to, response},
    transfer::{Pacing, RetryPolicy},
};
use serde_json::json;
use std::time::Duration;

/// Obviously synthetic: the engine knows no model, so its tests name none.
const NAME: &str = "synthetic-text:test";
const MANIFEST_TARGET: &str = "/v2/library/synthetic-text/manifests/test";
const BLOB_TARGET: &str = "/v2/library/synthetic-text/blobs/";
const STORE_TARGET: &str = "/store/";
const ELSEWHERE: &str = "elsewhere.example.com";
const MODEL_MEDIA_TYPE: &str = "application/vnd.ollama.image.model";

const ROOMY: Hardware = Hardware {
    total_memory_bytes: Some(64 * 1024 * 1024 * 1024),
    nvidia_vram_bytes: None,
};

/// A clock that advances by exactly what is waited, and fixed jitter.
struct RecordedPacing {
    now: Duration,
    waits: Vec<Duration>,
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

fn blob_host() -> &'static str {
    DEFAULT_REGISTRY_BLOB_HOSTS[0]
}

/// Every host the test server's certificate covers.
fn hosts() -> [&'static str; 3] {
    [DEFAULT_REGISTRY, blob_host(), ELSEWHERE]
}

fn payload(seed: u8, size: usize) -> Vec<u8> {
    (0..size)
        .map(|index| (index * 31 % 251) as u8 ^ seed)
        .collect()
}

/// A model as the registry serves it: its manifest, and each blob's digest and bytes,
/// config first.
struct Served {
    manifest: Vec<u8>,
    blobs: Vec<(String, Vec<u8>)>,
}

impl Served {
    fn new() -> Self {
        let blobs: Vec<(String, Vec<u8>)> =
            [payload(1, 300), payload(2, 150_000), payload(3, 90_000)]
                .into_iter()
                .map(|bytes| (Sha256Digest::of(&bytes).as_str().to_owned(), bytes))
                .collect();
        let descriptor = |media_type: &str, (hex, bytes): &(String, Vec<u8>)| {
            json!({
                "mediaType": media_type,
                "digest": format!("sha256:{hex}"),
                "size": bytes.len(),
            })
        };
        let manifest = json!({
            "schemaVersion": 2,
            "mediaType": MANIFEST_MEDIA_TYPE,
            "config": descriptor("application/vnd.docker.container.image.v1+json", &blobs[0]),
            "layers": [
                descriptor(MODEL_MEDIA_TYPE, &blobs[1]),
                descriptor("application/vnd.ollama.image.params", &blobs[2]),
            ],
        })
        .to_string()
        .into_bytes();
        Self { manifest, blobs }
    }

    fn total(&self) -> u64 {
        self.blobs.iter().map(|(_, bytes)| bytes.len() as u64).sum()
    }

    fn hex(&self, index: usize) -> &str {
        &self.blobs[index].0
    }

    fn stored(&self, root: &Path, index: usize) -> PathBuf {
        root.join("blobs")
            .join(format!("sha256-{}", self.hex(index)))
    }

    fn partial(&self, root: &Path, index: usize) -> PathBuf {
        root.join(PARTIAL)
            .join(format!("sha256-{}", self.hex(index)))
    }
}

fn manifest_file(root: &Path) -> PathBuf {
    root.join("manifests/registry.ollama.ai/library/synthetic-text/test")
}

fn empty(status: &str) -> Reply {
    Reply::Bytes(response(status, &[("Content-Length", "0".into())], b""))
}

/// Serves `bytes`, honouring a `Range` request.
fn ranged(request: &Request, bytes: &[u8]) -> Reply {
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
            bytes,
        )),
    }
}

/// The registry: the manifest at its route, or 404 when there is none; each blob route
/// redirected to `/store/<hex>` on `redirect`; and the store serving `blobs`.
fn registry(
    manifest: Option<Vec<u8>>,
    blobs: Vec<(String, Vec<u8>)>,
    redirect: &str,
) -> impl Fn(&Request) -> Reply + Send + Sync + 'static {
    let redirect = redirect.to_owned();
    move |request: &Request| {
        let target = request.target();
        if target == MANIFEST_TARGET {
            return match &manifest {
                Some(bytes) => Reply::Bytes(response(
                    "200 OK",
                    &[
                        ("Content-Type", MANIFEST_MEDIA_TYPE.to_owned()),
                        ("Content-Length", bytes.len().to_string()),
                    ],
                    bytes,
                )),
                None => empty("404 Not Found"),
            };
        }
        if let Some(hex) = target
            .strip_prefix(BLOB_TARGET)
            .and_then(|digest| digest.strip_prefix("sha256:"))
        {
            return Reply::Bytes(response(
                "307 Temporary Redirect",
                &[
                    ("Location", format!("https://{redirect}{STORE_TARGET}{hex}")),
                    ("Content-Length", "0".into()),
                ],
                b"",
            ));
        }
        let stored = target
            .strip_prefix(STORE_TARGET)
            .and_then(|hex| blobs.iter().find(|(held, _)| held == hex));
        match stored {
            Some((_, bytes)) => ranged(request, bytes),
            None => empty("404 Not Found"),
        }
    }
}

fn setup(
    handler: impl Fn(&Request) -> Reply + Send + Sync + 'static,
) -> (TestCertificate, TlsServer, tempfile::TempDir) {
    let certificate = TestCertificate::new(&hosts());
    let server = TlsServer::start(&certificate, handler);
    (certificate, server, tempfile::tempdir().unwrap())
}

struct Run {
    result: Result<RegistryManifest, RegistryError>,
    events: Vec<TransferEvent>,
    waits: Vec<Duration>,
}

/// Pulls the synthetic model into `root` with every test host approved.
fn pull(network: &Network, root: &Path) -> Run {
    let approved: BTreeSet<HostName> = hosts()
        .iter()
        .map(|host| HostName::new(*host).unwrap())
        .collect();
    let mut pacing = RecordedPacing {
        now: Duration::ZERO,
        waits: Vec::new(),
    };
    let mut events = Vec::new();
    let cancellation = Cancellation::default();
    let result = {
        let mut sink = |event| events.push(event);
        let mut transfer = Transfer {
            network,
            hosts: &approved,
            policy: RetryPolicy::default(),
            pacing: &mut pacing,
            events: &mut sink,
            cancellation: &cancellation,
        };
        Registry::new(root.to_path_buf()).pull(&ModelName::parse(NAME).unwrap(), &mut transfer)
    };
    Run {
        result,
        events,
        waits: pacing.waits,
    }
}

/// Pulls the synthetic model into `root` with every test host approved, each event going
/// to `observe` as it happens.
fn pull_observed(
    network: &Network,
    root: &Path,
    mut observe: impl FnMut(TransferEvent),
) -> Result<RegistryManifest, RegistryError> {
    let approved: BTreeSet<HostName> = hosts()
        .iter()
        .map(|host| HostName::new(*host).unwrap())
        .collect();
    let mut pacing = RecordedPacing {
        now: Duration::ZERO,
        waits: Vec::new(),
    };
    let cancellation = Cancellation::default();
    let mut transfer = Transfer {
        network,
        hosts: &approved,
        policy: RetryPolicy::default(),
        pacing: &mut pacing,
        events: &mut observe,
        cancellation: &cancellation,
    };
    Registry::new(root.to_path_buf()).pull(&ModelName::parse(NAME).unwrap(), &mut transfer)
}

fn store_requests(server: &TlsServer, served: &Served, index: usize) -> Vec<Request> {
    let target = format!("{STORE_TARGET}{}", served.hex(index));
    server
        .requests
        .lock()
        .unwrap()
        .iter()
        .filter(|request| request.target() == target)
        .cloned()
        .collect()
}

/// The progress a run reported: each event's completed bytes, every total checked.
fn progress(run: &Run, total: u64) -> Vec<u64> {
    run.events
        .iter()
        .map(|event| match event {
            TransferEvent::Progress {
                completed,
                total: reported,
            } => {
                assert_eq!(*reported, total);
                *completed
            }
            other => panic!("{other:?}"),
        })
        .collect()
}

fn present(root: &Path) -> Observation {
    let selected = SelectedModel::new("text", NAME, None).unwrap();
    let models = Models::new(
        LocalModels::new(vec![selected.clone()]).unwrap(),
        root.to_path_buf(),
    );
    models.observe_quick(&selected, &ROOMY)
}

#[test]
fn a_pull_stores_every_blob_and_then_the_manifest_in_the_program_layout() {
    let served = Served::new();
    let (certificate, server, directory) = setup(registry(
        Some(served.manifest.clone()),
        served.blobs.clone(),
        blob_host(),
    ));
    let network = network_to(certificate.roots(), server.address(), None);
    let root = directory.path();
    assert_eq!(present(root), Observation::Absent);
    let run = pull(&network, root);
    let manifest = run.result.unwrap();
    assert_eq!(manifest.bytes(), served.manifest.as_slice());
    assert_eq!(manifest.config().digest.as_str(), served.hex(0));
    assert_eq!(manifest.layers().len(), 2);
    assert_eq!(manifest.layers()[0].media_type, MODEL_MEDIA_TYPE);
    assert_eq!(manifest.total_bytes(), served.total());

    assert_eq!(fs::read(manifest_file(root)).unwrap(), served.manifest);
    for (index, (_, bytes)) in served.blobs.iter().enumerate() {
        assert_eq!(fs::read(served.stored(root, index)).unwrap(), *bytes);
    }
    assert_eq!(fs::read_dir(root.join("blobs")).unwrap().count(), 3);
    assert_eq!(fs::read_dir(root.join(PARTIAL)).unwrap().count(), 0);
    assert_eq!(present(root), Observation::Present);

    let requests = server.requests.lock().unwrap();
    assert_eq!(requests[0].target(), MANIFEST_TARGET);
    assert_eq!(requests[0].header("accept"), Some(MANIFEST_MEDIA_TYPE));
    assert_eq!(requests[0].header("host"), Some(DEFAULT_REGISTRY));
    let stored: Vec<&Request> = requests
        .iter()
        .filter(|request| request.target().starts_with(STORE_TARGET))
        .collect();
    assert_eq!(stored.len(), 3);
    assert!(
        stored
            .iter()
            .all(|request| request.header("host") == Some(blob_host()))
    );
    assert!(run.waits.is_empty());
}

#[test]
fn progress_counts_the_whole_model_against_the_manifest_sizes_and_never_goes_back() {
    let served = Served::new();
    let (certificate, server, directory) = setup(registry(
        Some(served.manifest.clone()),
        served.blobs.clone(),
        blob_host(),
    ));
    let network = network_to(certificate.roots(), server.address(), None);
    let run = pull(&network, directory.path());
    run.result.as_ref().unwrap();
    let completed = progress(&run, served.total());
    assert_eq!(completed.first(), Some(&0));
    assert_eq!(completed.last(), Some(&served.total()));
    assert!(completed.windows(2).all(|pair| pair[0] <= pair[1]));
    let first_layer_done = served.blobs[0].1.len() as u64 + served.blobs[1].1.len() as u64;
    assert!(completed.contains(&first_layer_done));
}

#[test]
fn a_damaged_blob_is_refused_deleted_and_publishes_no_manifest() {
    let served = Served::new();
    let mut blobs = served.blobs.clone();
    blobs[1].1[10] ^= 0xff;
    let (certificate, server, directory) =
        setup(registry(Some(served.manifest.clone()), blobs, blob_host()));
    let network = network_to(certificate.roots(), server.address(), None);
    let root = directory.path();
    let run = pull(&network, root);
    let error = run.result.unwrap_err();
    assert!(matches!(error, RegistryError::Damaged), "{error:?}");
    assert_eq!(error.category(), FailureCategory::DamagedDownload);
    assert!(!served.stored(root, 1).exists());
    assert!(!served.partial(root, 1).exists());
    assert!(!manifest_file(root).exists());
    assert!(!served.stored(root, 2).exists(), "nothing after the damage");
    assert_eq!(
        store_requests(&server, &served, 1).len(),
        1,
        "never retried"
    );
    assert_eq!(present(root), Observation::Absent);
}

#[test]
fn a_partial_blob_resumes_with_a_range_and_is_verified_whole() {
    let served = Served::new();
    let (certificate, server, directory) = setup(registry(
        Some(served.manifest.clone()),
        served.blobs.clone(),
        blob_host(),
    ));
    let network = network_to(certificate.roots(), server.address(), None);
    let root = directory.path();
    fs::create_dir_all(root.join(PARTIAL)).unwrap();
    fs::write(served.partial(root, 1), &served.blobs[1].1[..60_000]).unwrap();
    let run = pull(&network, root);
    run.result.unwrap();
    assert_eq!(fs::read(served.stored(root, 1)).unwrap(), served.blobs[1].1);
    assert!(!served.partial(root, 1).exists());
    let resumed = store_requests(&server, &served, 1);
    assert_eq!(resumed.len(), 1);
    assert_eq!(resumed[0].header("range"), Some("bytes=60000-"));
    assert_eq!(present(root), Observation::Present);

    // A partial whose kept bytes are wrong is caught when the whole blob is hashed.
    let (certificate, server, directory) = setup(registry(
        Some(served.manifest.clone()),
        served.blobs.clone(),
        blob_host(),
    ));
    let network = network_to(certificate.roots(), server.address(), None);
    let root = directory.path();
    let mut kept = served.blobs[1].1[..60_000].to_vec();
    kept[5] ^= 0xff;
    fs::create_dir_all(root.join(PARTIAL)).unwrap();
    fs::write(served.partial(root, 1), &kept).unwrap();
    let run = pull(&network, root);
    assert!(matches!(run.result, Err(RegistryError::Damaged)));
    assert!(!served.partial(root, 1).exists());
    assert!(!served.stored(root, 1).exists());
    assert!(!manifest_file(root).exists());
}

#[test]
fn a_blob_already_stored_whole_is_kept_and_a_wrong_one_is_fetched_again() {
    let served = Served::new();
    let (certificate, server, directory) = setup(registry(
        Some(served.manifest.clone()),
        served.blobs.clone(),
        blob_host(),
    ));
    let network = network_to(certificate.roots(), server.address(), None);
    let root = directory.path();
    fs::create_dir_all(root.join("blobs")).unwrap();
    fs::write(served.stored(root, 1), &served.blobs[1].1).unwrap();
    let mut wrong = served.blobs[2].1.clone();
    wrong[0] ^= 0xff;
    fs::write(served.stored(root, 2), &wrong).unwrap();
    let run = pull(&network, root);
    run.result.as_ref().unwrap();
    assert!(store_requests(&server, &served, 1).is_empty());
    assert_eq!(store_requests(&server, &served, 2).len(), 1);
    assert_eq!(fs::read(served.stored(root, 2)).unwrap(), served.blobs[2].1);
    let completed = progress(&run, served.total());
    assert_eq!(completed.last(), Some(&served.total()));
    assert!(completed.windows(2).all(|pair| pair[0] <= pair[1]));
    assert_eq!(present(root), Observation::Present);
}

#[test]
fn a_tag_the_registry_does_not_have_is_not_found_at_once() {
    let served = Served::new();
    let (certificate, server, directory) = setup(registry(None, served.blobs.clone(), blob_host()));
    let network = network_to(certificate.roots(), server.address(), None);
    let root = directory.path();
    let run = pull(&network, root);
    let error = run.result.unwrap_err();
    assert!(matches!(error, RegistryError::NotFound), "{error:?}");
    assert_eq!(error.category(), FailureCategory::Unexpected);
    assert_eq!(server.targets(), [MANIFEST_TARGET]);
    assert!(run.waits.is_empty());
    assert!(!root.join("manifests").exists());
    assert!(!root.join("blobs").exists());
}

#[test]
fn a_redirect_to_a_host_not_declared_for_the_registry_is_refused() {
    let served = Served::new();
    // The plan approves the stranger, but it is no storage host of the registry.
    let (certificate, server, directory) = setup(registry(
        Some(served.manifest.clone()),
        served.blobs.clone(),
        ELSEWHERE,
    ));
    let network = network_to(certificate.roots(), server.address(), None);
    let root = directory.path();
    let run = pull(&network, root);
    let error = run.result.unwrap_err();
    match &error {
        RegistryError::Network(failure) => {
            assert_eq!(failure.category, FailureCategory::BlockedByNetwork);
            assert_eq!(failure.attempts, 1);
        }
        other => panic!("{other:?}"),
    }
    assert!(
        !server
            .targets()
            .iter()
            .any(|target| target.starts_with(STORE_TARGET))
    );
    assert!(run.waits.is_empty());
    assert!(!manifest_file(root).exists());
    assert_eq!(fs::read_dir(root.join("blobs")).unwrap().count(), 0);
}

#[test]
fn a_cancelled_pull_keeps_resumable_bytes_and_publishes_no_manifest() {
    let served = Served::new();
    let (certificate, server, directory) = setup(registry(
        Some(served.manifest.clone()),
        served.blobs.clone(),
        blob_host(),
    ));
    let network = network_to(certificate.roots(), server.address(), None);
    let root = directory.path();
    let approved: BTreeSet<HostName> = hosts()
        .iter()
        .map(|host| HostName::new(*host).unwrap())
        .collect();
    let mut pacing = RecordedPacing {
        now: Duration::ZERO,
        waits: Vec::new(),
    };
    let cancellation = Cancellation::default();
    let config = served.blobs[0].1.len() as u64;
    let result = {
        let mut sink = |event| {
            if let TransferEvent::Progress { completed, .. } = event
                && completed > config
            {
                cancellation.cancel();
            }
        };
        let mut transfer = Transfer {
            network: &network,
            hosts: &approved,
            policy: RetryPolicy::default(),
            pacing: &mut pacing,
            events: &mut sink,
            cancellation: &cancellation,
        };
        Registry::new(root.to_path_buf()).pull(&ModelName::parse(NAME).unwrap(), &mut transfer)
    };
    assert!(matches!(result, Err(RegistryError::Cancelled)));
    assert!(!manifest_file(root).exists());
    assert!(!served.stored(root, 1).exists());
    let kept = fs::metadata(served.partial(root, 1)).unwrap().len();
    assert!(kept > 0 && kept < served.blobs[1].1.len() as u64);
}

#[test]
fn the_default_registry_declares_its_blob_storage_and_another_registry_only_itself() {
    let default = source_hosts(&ModelName::parse(NAME).unwrap());
    assert_eq!(default.len(), 1 + DEFAULT_REGISTRY_BLOB_HOSTS.len());
    assert!(default.contains(&HostName::new(DEFAULT_REGISTRY).unwrap()));
    for host in DEFAULT_REGISTRY_BLOB_HOSTS {
        assert!(default.contains(&HostName::new(*host).unwrap()), "{host}");
    }
    let other =
        source_hosts(&ModelName::parse("models.example.com/team/synthetic-text:test").unwrap());
    assert_eq!(
        other.into_iter().collect::<Vec<_>>(),
        [HostName::new("models.example.com").unwrap()]
    );
}

#[test]
fn manifests_naming_blobs_the_store_cannot_hold_are_damaged() {
    fn digest(seed: &[u8]) -> String {
        format!("sha256:{}", Sha256Digest::of(seed))
    }
    let layer = |digest: String, size: u64| json!({ "mediaType": MODEL_MEDIA_TYPE, "digest": digest, "size": size });
    let document = |version: u32, config: serde_json::Value, layers: Vec<serde_json::Value>| {
        json!({ "schemaVersion": version, "config": config, "layers": layers })
            .to_string()
            .into_bytes()
    };
    let config = || layer(digest(b"c"), 1);
    let fine = document(2, config(), vec![layer(digest(b"a"), 5)]);
    assert_eq!(RegistryManifest::parse(fine).unwrap().total_bytes(), 6);
    let shared = document(
        2,
        config(),
        vec![layer(digest(b"a"), 5), layer(digest(b"a"), 5)],
    );
    let shared = RegistryManifest::parse(shared).unwrap();
    assert_eq!((shared.blobs().len(), shared.total_bytes()), (2, 6));

    let upper = digest(b"a")
        .to_ascii_uppercase()
        .replacen("SHA256", "sha256", 1);
    for bytes in [
        document(1, config(), vec![layer(digest(b"a"), 5)]),
        document(2, config(), Vec::new()),
        document(2, config(), vec![layer(upper, 5)]),
        document(
            2,
            config(),
            vec![layer(digest(b"a").replace("sha256:", "md5:"), 5)],
        ),
        document(2, config(), vec![layer("sha256:abc".into(), 5)]),
        document(
            2,
            config(),
            vec![layer(digest(b"a"), 5), layer(digest(b"a"), 6)],
        ),
        document(
            2,
            config(),
            vec![layer(digest(b"a"), u64::MAX), layer(digest(b"b"), 1)],
        ),
        b"not a manifest".to_vec(),
    ] {
        assert!(matches!(
            RegistryManifest::parse(bytes),
            Err(RegistryError::Damaged)
        ));
    }
}

#[test]
fn registry_failures_read_as_the_closed_categories() {
    for (error, category) in [
        (RegistryError::NotFound, FailureCategory::Unexpected),
        (RegistryError::Damaged, FailureCategory::DamagedDownload),
        (RegistryError::Cancelled, FailureCategory::Cancelled),
        (
            RegistryError::from(io::Error::from(io::ErrorKind::PermissionDenied)),
            FailureCategory::NoPermission,
        ),
        (
            RegistryError::from(Error::Download(
                TransferFailure::final_(FailureCategory::Unexpected).with_status(404),
            )),
            FailureCategory::Unexpected,
        ),
        (
            RegistryError::from(Error::Download(TransferFailure::transient(
                FailureCategory::HostUnreachable,
            ))),
            FailureCategory::HostUnreachable,
        ),
    ] {
        assert_eq!(error.category(), category, "{error:?}");
        assert_eq!(LocalAiError::from(error).category(), category);
    }
    assert!(matches!(
        RegistryError::from(Error::Download(
            TransferFailure::final_(FailureCategory::Unexpected).with_status(404)
        )),
        RegistryError::NotFound
    ));
    assert!(matches!(
        LocalAiError::from(RegistryError::Cancelled),
        LocalAiError::Engine(Error::Cancelled)
    ));
}

#[test]
fn a_blob_cleared_before_the_manifest_is_written_is_fetched_again() {
    let served = Served::new();
    let (certificate, server, directory) = setup(registry(
        Some(served.manifest.clone()),
        served.blobs.clone(),
        blob_host(),
    ));
    let network = network_to(certificate.roots(), server.address(), None);
    let root = directory.path();
    let cleared = served.stored(root, 1);
    let total = served.total();
    let mut clears = 0;
    let mut reported = Vec::new();
    let result = pull_observed(&network, root, |event| {
        if let TransferEvent::Progress { completed, .. } = event {
            reported.push(completed);
            // A program serving the store starts once every blob is in and clears the
            // blobs no manifest names yet.
            if completed == total && clears == 0 && fs::remove_file(&cleared).is_ok() {
                clears += 1;
            }
        }
    });
    result.unwrap();
    assert_eq!(clears, 1);
    assert_eq!(fs::read(&cleared).unwrap(), served.blobs[1].1);
    assert_eq!(fs::read(manifest_file(root)).unwrap(), served.manifest);
    assert_eq!(
        store_requests(&server, &served, 1).len(),
        2,
        "the cleared blob is fetched again"
    );
    assert_eq!(store_requests(&server, &served, 2).len(), 1);
    assert!(reported.windows(2).all(|pair| pair[0] <= pair[1]));
    assert_eq!(reported.last(), Some(&total));
    assert_eq!(present(root), Observation::Present);
}

#[test]
fn a_blob_that_keeps_being_cleared_publishes_no_manifest() {
    let served = Served::new();
    let (certificate, server, directory) = setup(registry(
        Some(served.manifest.clone()),
        served.blobs.clone(),
        blob_host(),
    ));
    let network = network_to(certificate.roots(), server.address(), None);
    let root = directory.path();
    let cleared = served.stored(root, 1);
    let total = served.total();
    let result = pull_observed(&network, root, |event| {
        if let TransferEvent::Progress { completed, .. } = event
            && completed == total
        {
            let _ = fs::remove_file(&cleared);
        }
    });
    let error = result.unwrap_err();
    assert!(matches!(error, RegistryError::Engine(_)), "{error:?}");
    assert_eq!(error.category(), FailureCategory::Unexpected);
    assert!(!manifest_file(root).exists());
    assert_eq!(
        store_requests(&server, &served, 1).len(),
        1 + RESTORE_ROUNDS,
        "fetched again a bounded number of times"
    );
    assert_eq!(present(root), Observation::Absent);
}
