use super::*;
use crate::{
    component::Cancellation,
    provisioning::{
        connection::Network,
        failure::FailureCategory,
        local_ai::{
            hardware::Hardware,
            models::{LocalModels, ModelArtefact, Models, SelectedModel},
            registry::PARTIAL,
        },
        state::Observation,
        test_servers::{Reply, Request, TestCertificate, TlsServer, network_to, response},
        transfer::{Pacing, RetryPolicy, TransferEvent},
    },
};
use serde_json::json;
use std::{
    fs,
    path::{Path, PathBuf},
    time::Duration,
};

// Obviously synthetic: the engine knows no model, so its tests name none.
const REPOSITORY: &str = "synthetic-owner/synthetic-vision-gguf";
const REVISION: &str = "0123456789abcdef0123456789abcdef01234567";
const MODEL_FILE: &str = "synthetic-vision-q4.gguf";
const PROJECTOR_FILE: &str = "synthetic-projector-q8.gguf";
const RESOLVE_TARGET: &str =
    "/synthetic-owner/synthetic-vision-gguf/resolve/0123456789abcdef0123456789abcdef01234567/";
const STORE_TARGET: &str = "/xet-bridge/";
const ELSEWHERE: &str = "elsewhere.example.com";

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

fn file_host() -> &'static str {
    HUGGING_FACE_FILE_HOSTS[0]
}

/// Every host the test server's certificate covers.
fn hosts() -> [&'static str; 3] {
    [HUGGING_FACE, file_host(), ELSEWHERE]
}

fn payload(seed: u8, size: usize) -> Vec<u8> {
    (0..size)
        .map(|index| (index * 31 % 251) as u8 ^ seed)
        .collect()
}

/// The files a repository serves, by name, and the declaration the catalogue makes of
/// them.
struct Served {
    model: Vec<u8>,
    projector: Option<Vec<u8>>,
}

impl Served {
    fn with_projector() -> Self {
        Self {
            model: payload(1, 150_000),
            projector: Some(payload(2, 60_000)),
        }
    }

    fn without_projector() -> Self {
        Self {
            model: payload(1, 150_000),
            projector: None,
        }
    }

    fn declared(&self) -> HuggingFaceModel {
        let file = |name: &str, bytes: &[u8]| {
            HuggingFaceFile::new(name, Sha256Digest::of(bytes).as_str(), bytes.len() as u64)
                .unwrap()
        };
        HuggingFaceModel::new(
            REPOSITORY,
            REVISION,
            file(MODEL_FILE, &self.model),
            self.projector
                .as_deref()
                .map(|bytes| file(PROJECTOR_FILE, bytes)),
        )
        .unwrap()
    }

    fn files(&self) -> Vec<(String, Vec<u8>)> {
        std::iter::once((MODEL_FILE.to_owned(), self.model.clone()))
            .chain(
                self.projector
                    .iter()
                    .map(|bytes| (PROJECTOR_FILE.to_owned(), bytes.clone())),
            )
            .collect()
    }

    fn total(&self) -> u64 {
        self.files()
            .iter()
            .map(|(_, bytes)| bytes.len() as u64)
            .sum()
    }
}

fn hex(bytes: &[u8]) -> String {
    Sha256Digest::of(bytes).as_str().to_owned()
}

fn stored(root: &Path, bytes: &[u8]) -> PathBuf {
    root.join("blobs").join(format!("sha256-{}", hex(bytes)))
}

fn partial(root: &Path, bytes: &[u8]) -> PathBuf {
    root.join(PARTIAL).join(format!("sha256-{}", hex(bytes)))
}

fn manifest_file(root: &Path) -> PathBuf {
    root.join("manifests/huggingface.co/synthetic-owner/synthetic-vision-gguf/synthetic-vision-q4")
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

/// The hub: each `resolve` route of `files` redirected, as the hub does, to
/// `/xet-bridge/<hex>` on `redirect`, and that storage serving the bytes by digest.
fn hub(
    files: Vec<(String, Vec<u8>)>,
    redirect: &str,
) -> impl Fn(&Request) -> Reply + Send + Sync + 'static {
    let redirect = redirect.to_owned();
    move |request: &Request| {
        let target = request.target();
        if let Some(name) = target.strip_prefix(RESOLVE_TARGET) {
            return match files.iter().find(|(held, _)| held == name) {
                Some((_, bytes)) => Reply::Bytes(response(
                    "302 Found",
                    &[
                        (
                            "Location",
                            format!("https://{redirect}{STORE_TARGET}{}", hex(bytes)),
                        ),
                        ("Content-Length", "0".into()),
                    ],
                    b"",
                )),
                None => empty("404 Not Found"),
            };
        }
        let held = target
            .strip_prefix(STORE_TARGET)
            .and_then(|digest| files.iter().find(|(_, bytes)| hex(bytes) == digest));
        match held {
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

/// Fetches `model` into `root` with every test host approved.
fn pull(network: &Network, root: &Path, model: &HuggingFaceModel) -> Run {
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
        Registry::new(root.to_path_buf()).pull_hugging_face(model, &mut transfer)
    };
    Run {
        result,
        events,
        waits: pacing.waits,
    }
}

fn store_requests(server: &TlsServer, bytes: &[u8]) -> Vec<Request> {
    let target = format!("{STORE_TARGET}{}", hex(bytes));
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

fn models(root: &Path, model: &HuggingFaceModel) -> (Models, SelectedModel) {
    let selected = SelectedModel::new("vision", &model.name().to_string(), None).unwrap();
    let models = Models::new(
        LocalModels::new(vec![selected.clone()]).unwrap(),
        root.to_path_buf(),
    );
    (models, selected)
}

fn present(root: &Path, model: &HuggingFaceModel) -> Observation {
    let (models, selected) = models(root, model);
    models.observe_quick(&selected, &ROOMY)
}

fn descriptor(media_type: &str, bytes: &[u8]) -> serde_json::Value {
    json!({
        "mediaType": media_type,
        "digest": format!("sha256:{}", hex(bytes)),
        "size": bytes.len(),
    })
}

#[test]
fn a_fetch_stores_both_files_and_then_a_manifest_the_store_reads_as_any_other() {
    let served = Served::with_projector();
    let model = served.declared();
    let projector = served.projector.clone().unwrap();
    let (certificate, server, directory) = setup(hub(served.files(), file_host()));
    let network = network_to(certificate.roots(), server.address(), None);
    let root = directory.path();
    assert_eq!(present(root, &model), Observation::Absent);
    let run = pull(&network, root, &model);
    let manifest = run.result.unwrap();
    assert!(run.waits.is_empty());

    assert_eq!(fs::read(stored(root, &served.model)).unwrap(), served.model);
    assert_eq!(fs::read(stored(root, &projector)).unwrap(), projector);
    let config = fs::read(
        root.join("blobs")
            .join(format!("sha256-{}", manifest.config().digest)),
    )
    .unwrap();
    assert_eq!(
        serde_json::from_slice::<serde_json::Value>(&config).unwrap(),
        json!({
            "model_format": "gguf",
            "rootfs": {
                "type": "layers",
                "diff_ids": [
                    format!("sha256:{}", hex(&served.model)),
                    format!("sha256:{}", hex(&projector)),
                ],
            },
        })
    );
    assert_eq!(fs::read_dir(root.join("blobs")).unwrap().count(), 3);
    assert_eq!(fs::read_dir(root.join(PARTIAL)).unwrap().count(), 0);

    let written = fs::read(manifest_file(root)).unwrap();
    assert_eq!(written, manifest.bytes());
    assert_eq!(
        serde_json::from_slice::<serde_json::Value>(&written).unwrap(),
        json!({
            "schemaVersion": 2,
            "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
            "config": descriptor("application/vnd.docker.container.image.v1+json", &config),
            "layers": [
                descriptor("application/vnd.ollama.image.model", &served.model),
                descriptor("application/vnd.ollama.image.projector", &projector),
            ],
        })
    );
    assert_eq!(present(root, &model), Observation::Present);

    let requests = server.requests.lock().unwrap().clone();
    let resolved: Vec<&Request> = requests
        .iter()
        .filter(|request| request.target().starts_with(RESOLVE_TARGET))
        .collect();
    assert_eq!(
        resolved
            .iter()
            .map(|request| request.target().to_owned())
            .collect::<Vec<_>>(),
        [
            format!("{RESOLVE_TARGET}{MODEL_FILE}"),
            format!("{RESOLVE_TARGET}{PROJECTOR_FILE}"),
        ]
    );
    assert!(
        resolved
            .iter()
            .all(|request| request.header("host") == Some(HUGGING_FACE))
    );
    let fetched: Vec<&Request> = requests
        .iter()
        .filter(|request| request.target().starts_with(STORE_TARGET))
        .collect();
    assert_eq!(fetched.len(), 2);
    assert!(
        fetched
            .iter()
            .all(|request| request.header("host") == Some(file_host()))
    );

    // The same declaration again fetches nothing and publishes the same bytes.
    let again = pull(&network, root, &model);
    assert_eq!(again.result.unwrap().bytes(), written.as_slice());
    assert_eq!(fs::read(manifest_file(root)).unwrap(), written);
    assert_eq!(server.requests.lock().unwrap().len(), requests.len());

    // Removal takes the manifest and every layer it alone used, config included.
    let (models, _) = models(root, &model);
    models.remove_named(model.name()).unwrap();
    assert!(!manifest_file(root).exists());
    assert_eq!(fs::read_dir(root.join("blobs")).unwrap().count(), 0);
    assert_eq!(present(root, &model), Observation::Absent);
}

#[test]
fn a_model_without_a_projector_is_one_layer_and_whole() {
    let served = Served::without_projector();
    let model = served.declared();
    let (certificate, server, directory) = setup(hub(served.files(), file_host()));
    let network = network_to(certificate.roots(), server.address(), None);
    let root = directory.path();
    let run = pull(&network, root, &model);
    let manifest = run.result.as_ref().unwrap();
    assert_eq!(manifest.layers().len(), 1);
    assert_eq!(manifest.layers()[0].media_type, MODEL_MEDIA_TYPE);
    assert_eq!(manifest.layers()[0].digest.as_str(), hex(&served.model));
    let written: serde_json::Value =
        serde_json::from_slice(&fs::read(manifest_file(root)).unwrap()).unwrap();
    assert_eq!(
        written["layers"],
        json!([descriptor(MODEL_MEDIA_TYPE, &served.model)])
    );
    assert_eq!(fs::read_dir(root.join("blobs")).unwrap().count(), 2);
    assert_eq!(present(root, &model), Observation::Present);
    assert_eq!(model.download_bytes(), served.total());
    assert_eq!(progress(&run, served.total()).last(), Some(&served.total()));
}

#[test]
fn progress_counts_the_declared_files_against_their_declared_sizes() {
    let served = Served::with_projector();
    let model = served.declared();
    let (certificate, server, directory) = setup(hub(served.files(), file_host()));
    let network = network_to(certificate.roots(), server.address(), None);
    let run = pull(&network, directory.path(), &model);
    run.result.as_ref().unwrap();
    assert_eq!(model.download_bytes(), served.total());
    let completed = progress(&run, served.total());
    assert_eq!(completed.first(), Some(&0));
    assert_eq!(completed.last(), Some(&served.total()));
    assert!(completed.windows(2).all(|pair| pair[0] <= pair[1]));
    assert!(completed.contains(&(served.model.len() as u64)));
}

#[test]
fn a_file_not_matching_its_declared_digest_is_refused_deleted_and_publishes_nothing() {
    let served = Served::with_projector();
    let model = served.declared();
    let mut files = served.files();
    // Same size, other bytes: only the digest tells them apart.
    files[0].1[10] ^= 0xff;
    let damaged = files[0].1.clone();
    let (certificate, server, directory) = setup(hub(files, file_host()));
    let network = network_to(certificate.roots(), server.address(), None);
    let root = directory.path();
    let run = pull(&network, root, &model);
    let error = run.result.unwrap_err();
    assert!(matches!(error, RegistryError::Damaged), "{error:?}");
    assert_eq!(error.category(), FailureCategory::DamagedDownload);
    assert_eq!(store_requests(&server, &damaged).len(), 1, "never retried");
    assert!(!partial(root, &served.model).exists());
    assert!(!stored(root, &served.model).exists());
    assert!(!stored(root, served.projector.as_deref().unwrap()).exists());
    assert!(!manifest_file(root).exists());
    assert_eq!(present(root, &model), Observation::Absent);
}

#[test]
fn a_partial_file_resumes_with_a_range_and_is_verified_whole() {
    let served = Served::with_projector();
    let model = served.declared();
    let (certificate, server, directory) = setup(hub(served.files(), file_host()));
    let network = network_to(certificate.roots(), server.address(), None);
    let root = directory.path();
    fs::create_dir_all(root.join(PARTIAL)).unwrap();
    fs::write(partial(root, &served.model), &served.model[..60_000]).unwrap();
    let run = pull(&network, root, &model);
    run.result.as_ref().unwrap();
    assert_eq!(fs::read(stored(root, &served.model)).unwrap(), served.model);
    assert!(!partial(root, &served.model).exists());
    let resumed = store_requests(&server, &served.model);
    assert_eq!(resumed.len(), 1);
    assert_eq!(resumed[0].header("range"), Some("bytes=60000-"));
    let completed = progress(&run, served.total());
    assert!(completed.windows(2).all(|pair| pair[0] <= pair[1]));
    assert_eq!(present(root, &model), Observation::Present);
}

#[test]
fn a_redirect_to_a_host_not_declared_for_hugging_face_is_refused() {
    let served = Served::with_projector();
    let model = served.declared();
    // The plan approves the stranger, but it is no storage host of the hub.
    let (certificate, server, directory) = setup(hub(served.files(), ELSEWHERE));
    let network = network_to(certificate.roots(), server.address(), None);
    let root = directory.path();
    let run = pull(&network, root, &model);
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
fn hugging_face_declares_the_hub_and_its_storage_hosts_only() {
    let declared = source_hosts();
    assert_eq!(declared.len(), 1 + HUGGING_FACE_FILE_HOSTS.len());
    assert!(declared.contains(&HostName::new(HUGGING_FACE).unwrap()));
    for host in HUGGING_FACE_FILE_HOSTS {
        assert!(declared.contains(&HostName::new(*host).unwrap()), "{host}");
    }
    let artefact = ModelArtefact::HuggingFace(Served::with_projector().declared());
    assert_eq!(artefact.source_hosts(), declared);
    assert_eq!(
        artefact.name().to_string(),
        "huggingface.co/synthetic-owner/synthetic-vision-gguf:synthetic-vision-q4"
    );
}

#[test]
fn a_catalogue_artefact_reads_as_a_registry_name_or_pinned_hugging_face_files() {
    let model = hex(b"model");
    let projector = hex(b"projector");
    let file = |name: &str, digest: &str, size: u64| json!({ "file": name, "sha256": digest, "size_bytes": size });
    let declaration = |repository: &str, revision: &str, projector: Option<serde_json::Value>| {
        let mut value = json!({
            "source": "huggingface",
            "repository": repository,
            "revision": revision,
            "model": file(MODEL_FILE, &model, 5),
        });
        if let Some(projector) = projector {
            value["projector"] = projector;
        }
        value
    };
    let read = |value: serde_json::Value| serde_json::from_value::<ModelArtefact>(value);

    let registry = read(json!({ "source": "registry", "name": "synthetic-text:test" })).unwrap();
    match &registry {
        ModelArtefact::Registry(name) => assert_eq!(name.to_string(), "synthetic-text:test"),
        other => panic!("{other:?}"),
    }
    assert_eq!(
        registry.source_hosts(),
        crate::provisioning::local_ai::registry::source_hosts(registry.name())
    );

    let pinned = read(declaration(
        REPOSITORY,
        REVISION,
        Some(file(PROJECTOR_FILE, &projector, 7)),
    ))
    .unwrap();
    let pinned = match pinned {
        ModelArtefact::HuggingFace(pinned) => pinned,
        other => panic!("{other:?}"),
    };
    assert_eq!(pinned.revision(), REVISION);
    assert_eq!(pinned.model().file(), MODEL_FILE);
    assert_eq!(pinned.model().sha256().as_str(), model);
    assert_eq!(pinned.projector().map(HuggingFaceFile::size), Some(7));
    assert_eq!(pinned.download_bytes(), 12);
    let alone = read(declaration(REPOSITORY, REVISION, None)).unwrap();
    assert!(
        matches!(&alone, ModelArtefact::HuggingFace(declared) if declared.projector().is_none())
    );

    for refused in [
        declaration("synthetic-owner", REVISION, None),
        declaration("a/b/c", REVISION, None),
        declaration("synthetic-owner/../x", REVISION, None),
        declaration("-owner/synthetic-vision-gguf", REVISION, None),
        declaration(REPOSITORY, "main", None),
        declaration(REPOSITORY, &REVISION.to_ascii_uppercase(), None),
        declaration(REPOSITORY, &REVISION[..39], None),
        declaration(REPOSITORY, REVISION, Some(file(MODEL_FILE, &projector, 7))),
        declaration(REPOSITORY, REVISION, Some(file(PROJECTOR_FILE, &model, 5))),
        declaration(
            REPOSITORY,
            REVISION,
            Some(file("sub/x.gguf", &projector, 7)),
        ),
        declaration(REPOSITORY, REVISION, Some(file("x.bin", &projector, 7))),
        declaration(REPOSITORY, REVISION, Some(file(".gguf", &projector, 7))),
        declaration(REPOSITORY, REVISION, Some(file(PROJECTOR_FILE, "abc", 7))),
        declaration(
            REPOSITORY,
            REVISION,
            Some(file(PROJECTOR_FILE, &projector, 0)),
        ),
        json!({ "source": "registry", "name": "" }),
        json!({ "source": "elsewhere", "name": "synthetic-text:test" }),
    ] {
        assert!(read(refused.clone()).is_err(), "{refused}");
    }
}
