use super::*;
use crate::{
    component::Cancellation,
    provisioning::{
        connection::Network,
        items::ItemId,
        local_ai::{
            fake_ollama::FakeOllama,
            loopback::{ExchangeFailure, ExchangePhase},
            program::Server,
            reading,
        },
        plan::PlanEntry,
        state::{CheckMode, StaleReason},
        test_servers::{Reply, Request, TestCertificate, TlsServer, network_to, response},
        transfer::{Pacing, RetryPolicy},
    },
};
use serde_json::json;
use std::{collections::BTreeMap, fs, time::Duration};

const GIB: u64 = 1024 * 1024 * 1024;
/// Obviously synthetic names: the engine knows no model, so its tests name none.
const TEXT: &str = "synthetic-text:test";
const VISION: &str = "synthetic-vision:test";

/// One model as its registry serves it and the store keeps it: its manifest, and each
/// layer's bytes by digest.
struct Stored {
    manifest: Vec<u8>,
    blobs: Vec<(String, Vec<u8>)>,
}

impl Stored {
    fn new(seed: u8) -> Self {
        let blobs: Vec<(String, Vec<u8>)> = [
            vec![seed; 3],
            vec![seed.wrapping_add(1); 50],
            vec![seed; 70],
        ]
        .into_iter()
        .map(|bytes| (format!("sha256:{}", Sha256Digest::of(&bytes)), bytes))
        .collect();
        let layer = |media_type: &str, (digest, bytes): &(String, Vec<u8>)| json!({ "mediaType": media_type, "digest": digest, "size": bytes.len() });
        let manifest = json!({
            "schemaVersion": 2,
            "mediaType": registry::MANIFEST_MEDIA_TYPE,
            "config": layer("application/vnd.docker.container.image.v1+json", &blobs[0]),
            "layers": [
                layer(huggingface::MODEL_MEDIA_TYPE, &blobs[1]),
                layer("application/vnd.ollama.image.params", &blobs[2]),
            ],
        })
        .to_string()
        .into_bytes();
        Self { manifest, blobs }
    }

    fn size(&self) -> u64 {
        self.blobs.iter().map(|(_, bytes)| bytes.len() as u64).sum()
    }

    fn files(&self, root: &Path, name: &str) -> Vec<(PathBuf, Vec<u8>)> {
        let mut files = vec![(
            ModelName::parse(name).unwrap().manifest_path(root),
            self.manifest.clone(),
        )];
        for (digest, bytes) in &self.blobs {
            let hex = digest.strip_prefix("sha256:").unwrap();
            files.push((
                root.join("blobs").join(format!("sha256-{hex}")),
                bytes.clone(),
            ));
        }
        files
    }

    fn write(&self, root: &Path, name: &str) {
        for (path, bytes) in self.files(root, name) {
            fs::create_dir_all(path.parent().unwrap()).unwrap();
            fs::write(path, bytes).unwrap();
        }
    }

    /// The default registry's routes for this model under `name`: its manifest and each
    /// blob by digest.
    fn routes(&self, name: &str) -> Vec<(String, Vec<u8>)> {
        let name = ModelName::parse(name).unwrap();
        let repository = format!("/v2/{}/{}", name.namespace(), name.model());
        std::iter::once((
            format!("{repository}/manifests/{}", name.tag()),
            self.manifest.clone(),
        ))
        .chain(
            self.blobs
                .iter()
                .map(|(digest, bytes)| (format!("{repository}/blobs/{digest}"), bytes.clone())),
        )
        .collect()
    }
}

fn selected(role: &str, name: &str, size_bytes: u64) -> SelectedModel {
    SelectedModel::new(role, name, Some(size_bytes), None).unwrap()
}

/// The vision role reads with one model and two text roles share another.
fn selection(text: &Stored, vision: &Stored) -> LocalModels {
    LocalModels::new(vec![
        selected("vision_transcription", VISION, vision.size()),
        selected("text_extraction", TEXT, text.size()),
        selected("column_role_mapping", TEXT, text.size()),
    ])
    .unwrap()
}

struct Fixture {
    root: tempfile::TempDir,
    text: Stored,
    vision: Stored,
    models: Models,
}

fn fixture() -> Fixture {
    let root = tempfile::tempdir().unwrap();
    let text = Stored::new(1);
    let vision = Stored::new(7);
    let models = Models::new(selection(&text, &vision), root.path().join("models"));
    Fixture {
        root,
        text,
        vision,
        models,
    }
}

impl Fixture {
    fn models_root(&self) -> PathBuf {
        self.root.path().join("models")
    }

    fn text_model(&self) -> &SelectedModel {
        self.models.selection().for_role("text_extraction").unwrap()
    }

    fn vision_name(&self) -> &ModelName {
        self.models
            .selection()
            .for_role("vision_transcription")
            .unwrap()
            .name()
    }
}

const ROOMY: Hardware = Hardware {
    total_memory_bytes: Some(64 * GIB),
    nvidia_vram_bytes: None,
};

const PRESENT: Observation = Observation::Present;

#[test]
fn a_selection_takes_well_formed_triples_only_and_orders_them_by_role() {
    for (role, name, size) in [
        ("text_extraction", "", 1),
        ("text_extraction", TEXT, 0),
        ("", TEXT, 1),
        ("Text", TEXT, 1),
        ("program", TEXT, 1),
        ("text_extraction", "../escape:test", 1),
        ("text_extraction", "a/b/c/d:test", 1),
        ("text_extraction", "synthetic:../test", 1),
        ("text_extraction", "synthetic\\model:test", 1),
        ("text_extraction", "synthetic model:test", 1),
        ("text_extraction", "Not.A.Host/space/model:test", 1),
        ("text_extraction", "synthetic-text:", 1),
    ] {
        assert!(
            SelectedModel::new(role, name, Some(size), None).is_err(),
            "{role} {name} {size}"
        );
    }
    let duplicate = LocalModels::new(vec![
        selected("text_extraction", TEXT, 1),
        selected("text_extraction", VISION, 1),
    ]);
    assert!(duplicate.is_err(), "a role is selected once");
    let two_sizes = LocalModels::new(vec![
        selected("text_extraction", TEXT, 1),
        selected("column_role_mapping", "SYNTHETIC-TEXT:TEST", 2),
    ]);
    assert!(two_sizes.is_err(), "one model has one size");
    let one_size = LocalModels::new(vec![
        selected("text_extraction", TEXT, 1),
        selected("column_role_mapping", "SYNTHETIC-TEXT:TEST", 1),
    ]);
    assert!(one_size.is_ok(), "a registry name reads regardless of case");
    // The store keeps a Hugging Face model under a name a registry could also serve; one
    // name has one source.
    let declared = hugging_face(&[1u8; 10], None);
    let two_sources = LocalModels::new(vec![
        SelectedModel::of_artefact(
            "text_extraction",
            ModelArtefact::HuggingFace(declared.clone()),
            None,
            None,
        )
        .unwrap(),
        SelectedModel::new(
            "column_role_mapping",
            &declared.name().to_string(),
            None,
            None,
        )
        .unwrap(),
    ]);
    assert!(two_sources.is_err(), "one model has one source");
    assert!(
        SelectedModel::of_artefact("program", ModelArtefact::HuggingFace(declared), None, None)
            .is_err()
    );
    let ordered = LocalModels::new(vec![
        selected("vision_transcription", VISION, 1),
        selected("column_role_mapping", TEXT, 1),
    ])
    .unwrap();
    assert_eq!(
        ordered
            .as_slice()
            .iter()
            .map(|model| model.role.as_str())
            .collect::<Vec<_>>(),
        ["column_role_mapping", "vision_transcription"]
    );
    assert!(LocalModels::default().is_empty());
}

#[test]
fn a_name_reads_as_the_program_reads_it() {
    for (written, shortest, host) in [
        ("synthetic", "synthetic:latest", "registry.ollama.ai"),
        (TEXT, TEXT, "registry.ollama.ai"),
        (
            "registry.ollama.ai/library/synthetic-text:test",
            TEXT,
            "registry.ollama.ai",
        ),
        (
            "someone/synthetic-text:test",
            "someone/synthetic-text:test",
            "registry.ollama.ai",
        ),
        (
            "models.example.com/someone/synthetic-text:test",
            "models.example.com/someone/synthetic-text:test",
            "models.example.com",
        ),
    ] {
        let name = ModelName::parse(written).unwrap();
        assert_eq!(name.to_string(), shortest, "{written}");
        assert_eq!(name.host().as_str(), host, "{written}");
        assert!(name.same(&ModelName::parse(shortest).unwrap()));
    }
    let name = ModelName::parse(TEXT).unwrap();
    assert!(name.same(&ModelName::parse("Synthetic-Text:TEST").unwrap()));
    assert!(!name.same(&ModelName::parse("synthetic-text:other").unwrap()));
    assert_eq!(
        name.manifest_path(Path::new("/models")),
        Path::new("/models/manifests/registry.ollama.ai/library/synthetic-text/test")
    );
}

#[test]
fn the_plan_has_a_part_per_selected_role_and_counts_a_shared_model_once() {
    let fixture = fixture();
    let parts = fixture.models.plan_parts();
    assert_eq!(
        parts
            .iter()
            .map(|part| part.part_id.as_str())
            .collect::<Vec<_>>(),
        [
            "column_role_mapping",
            "text_extraction",
            "vision_transcription"
        ]
    );
    let registry_hosts = registry::source_hosts(&ModelName::parse(TEXT).unwrap());
    assert!(
        registry_hosts.len() > 1,
        "the registry redirects to its storage"
    );
    for part in &parts {
        assert_eq!(part.destination, Some(Destination::OllamaModels));
        assert!(!part.installs_outside_program);
        assert_eq!(part.source_hosts[0].as_str(), "registry.ollama.ai");
        assert_eq!(
            part.source_hosts.iter().cloned().collect::<BTreeSet<_>>(),
            registry_hosts,
            "the plan names every host the fetch may reach"
        );
        assert_eq!(part.source_hosts.len(), registry_hosts.len());
    }
    assert_eq!(parts[0].target_version.as_deref(), Some(TEXT));
    assert_eq!(parts[0].target_version, parts[1].target_version);
    assert_eq!(parts[2].download_bytes, Some(fixture.vision.size()));
    let program = PlanPart {
        part_id: PROGRAM_PART.into(),
        download_bytes: Some(1000),
        source_hosts: vec![HostName::new("github.com").unwrap()],
        destination: Some(Destination::LocalAiProgram),
        installs_outside_program: false,
        target_version: Some("1.0.0".into()),
    };
    let entry = PlanEntry::of_parts(
        ItemId::LocalAi,
        std::iter::once(program).chain(parts).collect(),
    )
    .unwrap();
    assert_eq!(
        entry.destinations(),
        [Destination::LocalAiProgram, Destination::OllamaModels]
    );
    assert_eq!(
        entry.download_bytes,
        Some(1000 + fixture.text.size() + fixture.vision.size())
    );
    let elsewhere = Models::new(
        LocalModels::new(vec![selected(
            "text_extraction",
            "models.example.com/someone/synthetic-text:test",
            5,
        )])
        .unwrap(),
        fixture.models_root(),
    );
    assert_eq!(
        elsewhere.plan_parts()[0].source_hosts,
        [HostName::new("models.example.com").unwrap()],
        "another registry declares no storage of its own"
    );
    let none = Models::new(LocalModels::default(), fixture.models_root());
    assert!(none.plan_parts().is_empty(), "no selection plans no model");

    // A Hugging Face model is planned at its declared size from the hub and the storage
    // it redirects to, the hub first.
    let declared = hugging_face(&[3u8; 40], Some(&[4u8; 20][..]));
    let pinned = Models::new(
        LocalModels::new(vec![
            SelectedModel::of_artefact(
                "vision_transcription",
                ModelArtefact::HuggingFace(declared.clone()),
                None,
                None,
            )
            .unwrap(),
        ])
        .unwrap(),
        fixture.models_root(),
    );
    let part = &pinned.plan_parts()[0];
    assert_eq!(part.download_bytes, Some(60));
    assert_eq!(part.target_version, Some(declared.name().to_string()));
    assert_eq!(part.source_hosts[0].as_str(), huggingface::HUGGING_FACE);
    assert_eq!(
        part.source_hosts.iter().cloned().collect::<BTreeSet<_>>(),
        huggingface::source_hosts()
    );
    assert_eq!(pinned.selection().hosts(), huggingface::source_hosts());
}

#[test]
fn the_quick_check_reads_the_stored_manifest_and_its_layers() {
    let fixture = fixture();
    let root = fixture.models_root();
    let model = fixture.text_model();
    assert_eq!(
        fixture.models.observe_quick(model, &ROOMY),
        Observation::Absent
    );
    // Every layer stored and no manifest naming them: the model is absent.
    for (path, bytes) in fixture.text.files(&root, TEXT).into_iter().skip(1) {
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(path, bytes).unwrap();
    }
    assert_eq!(
        fixture.models.observe_quick(model, &ROOMY),
        Observation::Absent
    );
    fixture.text.write(&root, TEXT);
    assert_eq!(fixture.models.observe_quick(model, &ROOMY), PRESENT);
    let vision = fixture
        .models
        .selection()
        .for_role("vision_transcription")
        .unwrap();
    assert_eq!(
        fixture.models.observe_quick(vision, &ROOMY),
        Observation::Absent
    );
    // Whichever manifest the registry served under the name is the model: the program
    // verified it as it pulled, and the engine pins no digest to compare it with.
    fixture.vision.write(&root, TEXT);
    assert_eq!(fixture.models.observe_quick(model, &ROOMY), PRESENT);
    fixture.text.write(&root, TEXT);
    // A layer that is missing or short reads as a model not yet all there.
    let files = fixture.text.files(&root, TEXT);
    fs::write(&files[2].0, b"short").unwrap();
    assert_eq!(
        fixture.models.observe_quick(model, &ROOMY),
        Observation::Absent
    );
    fs::remove_file(&files[2].0).unwrap();
    assert_eq!(
        fixture.models.observe_quick(model, &ROOMY),
        Observation::Absent
    );
    fixture.text.write(&root, TEXT);
    fs::write(&files[0].0, b"{").unwrap();
    assert_eq!(
        fixture.models.observe_quick(model, &ROOMY),
        Observation::Failed(FailureCategory::DamagedDownload)
    );
}

#[test]
fn the_hardware_floor_is_the_size_the_caller_stated() {
    let fixture = fixture();
    fixture.text.write(&fixture.models_root(), TEXT);
    let small = Hardware {
        total_memory_bytes: Some(GIB),
        nvidia_vram_bytes: Some(GIB),
    };
    let large = selected("text_extraction", TEXT, GIB + 1);
    assert_eq!(
        fixture.models.observe_quick(&large, &small),
        Observation::Blocked(BlockedReason::Hardware)
    );
    let card = Hardware {
        total_memory_bytes: Some(GIB),
        nvidia_vram_bytes: Some(GIB + 1),
    };
    assert_eq!(fixture.models.observe_quick(&large, &card), PRESENT);
    let fitting = selected("text_extraction", TEXT, GIB);
    assert_eq!(fixture.models.observe_quick(&fitting, &small), PRESENT);
}

/// A pacing that advances by each wait instead of waiting.
#[derive(Default)]
struct RecordedPacing {
    now: Duration,
}

impl Pacing for RecordedPacing {
    fn elapsed(&self) -> Duration {
        self.now
    }
    fn wait(&mut self, delay: Duration, cancellation: &Cancellation) -> Result<(), Error> {
        cancellation.check()?;
        self.now += delay;
        Ok(())
    }
    fn jitter(&mut self) -> f64 {
        0.5
    }
}

// Obviously synthetic: the engine knows no model, so its tests name none.
const HF_REPOSITORY: &str = "synthetic-owner/synthetic-vision-gguf";
const HF_REVISION: &str = "0123456789abcdef0123456789abcdef01234567";
/// The storage host the hub redirected a GGUF file to when it was probed.
const HF_STORAGE_HOST: &str = "us.aws.cdn.hf.co";
const HF_STORAGE: &str = "/xet-bridge/";

/// A Hugging Face declaration of `model` and its optional `projector` bytes.
fn hugging_face(model: &[u8], projector: Option<&[u8]>) -> HuggingFaceModel {
    let file = |name: &str, bytes: &[u8]| {
        HuggingFaceFile::new(name, Sha256Digest::of(bytes).as_str(), bytes.len() as u64).unwrap()
    };
    HuggingFaceModel::new(
        HF_REPOSITORY,
        HF_REVISION,
        file("synthetic-vision-q4.gguf", model),
        projector.map(|bytes| file("synthetic-projector-q8.gguf", bytes)),
    )
    .unwrap()
}

fn answer(bytes: &[u8]) -> Reply {
    Reply::Bytes(response(
        "200 OK",
        &[("Content-Length", bytes.len().to_string())],
        bytes,
    ))
}

/// The publishers a fetch reaches, on one TLS server whose certificate covers every host a
/// registry or Hugging Face fetch may reach: the default registry serving `routes` by
/// target, and the Hugging Face hub redirecting each `resolve` route of `files` to its
/// storage host, which serves the bytes by digest.
struct Publishers {
    certificate: TestCertificate,
    server: TlsServer,
}

impl Publishers {
    fn start(routes: Vec<(String, Vec<u8>)>, files: Vec<(String, Vec<u8>)>) -> Self {
        let hosts: Vec<String> = registry::source_hosts(&ModelName::parse(TEXT).unwrap())
            .into_iter()
            .chain(huggingface::source_hosts())
            .map(|host| host.as_str().to_owned())
            .collect();
        let names: Vec<&str> = hosts.iter().map(String::as_str).collect();
        let certificate = TestCertificate::new(&names);
        let routes: BTreeMap<String, Vec<u8>> = routes.into_iter().collect();
        let resolve = format!("/{HF_REPOSITORY}/resolve/{HF_REVISION}/");
        let server = TlsServer::start(&certificate, move |request: &Request| {
            let target = request.target();
            if let Some(bytes) = routes.get(target) {
                return answer(bytes);
            }
            if let Some(name) = target.strip_prefix(resolve.as_str())
                && let Some((_, bytes)) = files.iter().find(|(held, _)| held == name)
            {
                return Reply::Bytes(response(
                    "302 Found",
                    &[
                        (
                            "Location",
                            format!(
                                "https://{HF_STORAGE_HOST}{HF_STORAGE}{}",
                                Sha256Digest::of(bytes)
                            ),
                        ),
                        ("Content-Length", "0".into()),
                    ],
                    b"",
                ));
            }
            let stored = target.strip_prefix(HF_STORAGE).and_then(|hex| {
                files
                    .iter()
                    .find(|(_, bytes)| Sha256Digest::of(bytes).as_str() == hex)
            });
            match stored {
                Some((_, bytes)) => answer(bytes),
                None => Reply::Bytes(response(
                    "404 Not Found",
                    &[("Content-Length", "0".into())],
                    b"",
                )),
            }
        });
        Self {
            certificate,
            server,
        }
    }

    fn network(&self) -> Network {
        network_to(self.certificate.roots(), self.server.address(), None)
    }
}

struct Fetched {
    result: Result<Observation, LocalAiError>,
    /// The bytes the pull reported its progress against, when it finished.
    bytes: Option<u64>,
    events: Vec<TransferEvent>,
}

/// Fetches `model` with `models` through `network`, reaching only the `approved` hosts.
fn fetch(
    models: &Models,
    model: &SelectedModel,
    network: &Network,
    approved: &[HostName],
) -> Fetched {
    let hosts: BTreeSet<HostName> = approved.iter().cloned().collect();
    let mut pacing = RecordedPacing::default();
    let mut events = Vec::new();
    let cancellation = Cancellation::default();
    let pulled = {
        let mut sink = |event| events.push(event);
        models.pull(
            model,
            &mut Transfer {
                network,
                hosts: &hosts,
                policy: RetryPolicy::default(),
                pacing: &mut pacing,
                events: &mut sink,
                cancellation: &cancellation,
            },
        )
    };
    let bytes = pulled.as_ref().ok().map(|pulled| pulled.bytes);
    Fetched {
        result: pulled.map(|pulled| pulled.observation),
        bytes,
        events,
    }
}

/// The progress a fetch reported, as completed and total bytes.
fn progress(events: &[TransferEvent]) -> Vec<(u64, u64)> {
    events
        .iter()
        .filter_map(|event| match event {
            TransferEvent::Progress { completed, total } => Some((*completed, *total)),
            TransferEvent::Retrying { .. } => None,
        })
        .collect()
}

/// The hosts the plan approves for the part `role`.
fn approved_for(models: &Models, role: &str) -> Vec<HostName> {
    models
        .plan_parts()
        .into_iter()
        .find(|part| part.part_id == role)
        .unwrap()
        .source_hosts
}

#[test]
fn a_registry_model_is_fetched_by_the_engine_into_the_store_with_no_server() {
    let fixture = fixture();
    let publishers = Publishers::start(fixture.text.routes(TEXT), Vec::new());
    // A server runs beside the store, as the manager's does; the fetch asks it nothing.
    let fake = FakeOllama::start("1.0.0");
    let model = fixture.text_model();
    let approved = approved_for(&fixture.models, "text_extraction");
    let fetched = fetch(&fixture.models, model, &publishers.network(), &approved);
    assert_eq!(fetched.result.unwrap(), PRESENT);

    let root = fixture.models_root();
    assert_eq!(
        fs::read(ModelName::parse(TEXT).unwrap().manifest_path(&root)).unwrap(),
        fixture.text.manifest,
        "the store keeps the manifest the registry served"
    );
    for (path, bytes) in fixture.text.files(&root, TEXT).into_iter().skip(1) {
        assert_eq!(fs::read(path).unwrap(), bytes);
    }
    assert_eq!(fixture.models.observe_quick(model, &ROOMY), PRESENT);
    let total = fixture.text.size();
    let reported = progress(&fetched.events);
    assert!(reported.iter().all(|(_, of)| *of == total), "{reported:?}");
    assert_eq!(reported.first(), Some(&(0, total)));
    assert_eq!(reported.last(), Some(&(total, total)));
    assert!(reported.windows(2).all(|pair| pair[0].0 <= pair[1].0));
    let targets = publishers.server.targets();
    assert_eq!(targets.len(), 1 + fixture.text.blobs.len(), "{targets:?}");
    assert!(
        fake.state.lock().unwrap().requests.is_empty(),
        "no server is asked to pull or list anything"
    );

    // A model the store holds whole is not fetched again.
    let again = fetch(&fixture.models, model, &publishers.network(), &approved);
    assert_eq!(again.result.unwrap(), PRESENT);
    assert_eq!(
        again.events,
        [TransferEvent::Progress {
            completed: total,
            total
        }]
    );
    assert_eq!(publishers.server.targets().len(), targets.len());
}

/// A model no catalogue sizes, as one the person names: planned with an unknown download,
/// never held back by a floor it has no size for, and fetched with progress against the
/// sizes its manifest declares.
#[test]
fn a_model_of_unknown_size_is_planned_unsized_and_fetched_against_its_manifest_sizes() {
    let root = tempfile::tempdir().unwrap();
    let stored = Stored::new(5);
    assert!(SelectedModel::new("download", TEXT, Some(0), None).is_err());
    let models = Models::new(
        LocalModels::new(vec![
            SelectedModel::new("download", TEXT, None, None).unwrap(),
        ])
        .unwrap(),
        root.path().join("models"),
    );
    let model = &models.selection().as_slice()[0];
    let parts = models.plan_parts();
    assert_eq!(parts[0].download_bytes, None);
    assert_eq!(models.download_bytes(model), None);
    let tiny = Hardware {
        total_memory_bytes: Some(1),
        nvidia_vram_bytes: None,
    };
    assert_eq!(models.observe_quick(model, &tiny), Observation::Absent);
    let publishers = Publishers::start(stored.routes(TEXT), Vec::new());
    let fetched = fetch(
        &models,
        model,
        &publishers.network(),
        &parts[0].source_hosts,
    );
    assert_eq!(fetched.result.unwrap(), PRESENT);
    let reported = progress(&fetched.events);
    assert!(
        reported
            .iter()
            .all(|(completed, total)| completed <= total && *total == stored.size()),
        "{reported:?}"
    );
    assert_eq!(reported.last(), Some(&(stored.size(), stored.size())));
    assert_eq!(models.download_bytes(model), Some(stored.size()));
}

#[test]
fn a_pull_reports_the_total_its_manifest_states_not_the_size_a_catalogue_gave() {
    let root = tempfile::tempdir().unwrap();
    let stored = Stored::new(5);
    let models = Models::new(
        LocalModels::new(vec![selected("download", TEXT, 7)]).unwrap(),
        root.path().join("models"),
    );
    let model = &models.selection().as_slice()[0];
    let publishers = Publishers::start(stored.routes(TEXT), Vec::new());
    let approved = approved_for(&models, "download");
    let fetched = fetch(&models, model, &publishers.network(), &approved);
    assert_eq!(fetched.result.unwrap(), PRESENT);
    assert_eq!(fetched.bytes, Some(stored.size()));
    let reported = progress(&fetched.events);
    assert_eq!(reported.last(), Some(&(stored.size(), stored.size())));
    assert!(
        reported.iter().all(|(_, total)| *total == stored.size()),
        "{reported:?}"
    );
}

#[test]
fn a_fetch_reaches_only_the_hosts_the_approved_plan_names() {
    let fixture = fixture();
    let publishers = Publishers::start(fixture.text.routes(TEXT), Vec::new());
    let model = fixture.text_model();
    let storage_only: Vec<HostName> = registry::source_hosts(model.name())
        .into_iter()
        .filter(|host| host != model.name().host())
        .collect();
    assert!(!storage_only.is_empty());
    let fetched = fetch(&fixture.models, model, &publishers.network(), &storage_only);
    assert!(
        matches!(
            &fetched.result,
            Err(error) if error.category() == FailureCategory::BlockedByNetwork
        ),
        "{:?}",
        fetched.result
    );
    assert!(publishers.server.targets().is_empty(), "nothing was sent");
    assert_eq!(
        fixture.models.observe_quick(model, &ROOMY),
        Observation::Absent
    );
}

#[test]
fn a_layer_that_is_not_its_digest_fails_the_fetch_and_the_model_stays_absent() {
    let fixture = fixture();
    let mut routes = fixture.text.routes(TEXT);
    // Same size, other bytes: only the manifest's digest tells them apart.
    routes[2].1[0] ^= 0xff;
    let publishers = Publishers::start(routes, Vec::new());
    let model = fixture.text_model();
    let approved = approved_for(&fixture.models, "text_extraction");
    let fetched = fetch(&fixture.models, model, &publishers.network(), &approved);
    assert!(
        matches!(
            fetched.result,
            Err(LocalAiError::Failed(FailureCategory::DamagedDownload))
        ),
        "{:?}",
        fetched.result
    );
    assert!(
        !ModelName::parse(TEXT)
            .unwrap()
            .manifest_path(&fixture.models_root())
            .exists(),
        "no manifest names a model the store does not hold whole"
    );
    assert_eq!(
        fixture.models.observe_quick(model, &ROOMY),
        Observation::Absent
    );
}

#[test]
fn a_hugging_face_model_is_fetched_from_its_declared_files_into_the_same_store() {
    let root = tempfile::tempdir().unwrap();
    let models_root = root.path().join("models");
    let model_bytes: Vec<u8> = (0..90_000u32).map(|index| (index % 251) as u8).collect();
    let projector_bytes = vec![7u8; 30_000];
    let declared = hugging_face(&model_bytes, Some(projector_bytes.as_slice()));
    let models = Models::new(
        LocalModels::new(vec![
            SelectedModel::of_artefact(
                "vision_transcription",
                ModelArtefact::HuggingFace(declared.clone()),
                None,
                None,
            )
            .unwrap(),
        ])
        .unwrap(),
        models_root.clone(),
    );
    let model = &models.selection().as_slice()[0];
    assert_eq!(models.observe_quick(model, &ROOMY), Observation::Absent);
    let publishers = Publishers::start(
        Vec::new(),
        vec![
            (declared.model().file().to_owned(), model_bytes.clone()),
            (
                declared.projector().unwrap().file().to_owned(),
                projector_bytes.clone(),
            ),
        ],
    );
    let approved = approved_for(&models, "vision_transcription");
    let fetched = fetch(&models, model, &publishers.network(), &approved);
    assert_eq!(fetched.result.unwrap(), PRESENT);
    assert_eq!(models.observe_quick(model, &ROOMY), PRESENT);
    let total = declared.download_bytes();
    assert_eq!(models.download_bytes(model), Some(total));
    let reported = progress(&fetched.events);
    assert!(reported.iter().all(|(_, of)| *of == total), "{reported:?}");
    assert_eq!(reported.last(), Some(&(total, total)));
    let requests = publishers.server.requests.lock().unwrap().clone();
    let hosts: Vec<Option<&str>> = requests
        .iter()
        .map(|request| request.header("host"))
        .collect();
    assert_eq!(
        hosts,
        [
            Some(huggingface::HUGGING_FACE),
            Some(HF_STORAGE_HOST),
            Some(huggingface::HUGGING_FACE),
            Some(HF_STORAGE_HOST),
        ],
        "each file is resolved on the hub and read from its storage"
    );

    // Removal takes the manifest and every layer only it used, as for a registry model.
    models.remove_named(model.name()).unwrap();
    assert_eq!(models.observe_quick(model, &ROOMY), Observation::Absent);
    assert_eq!(fs::read_dir(models_root.join("blobs")).unwrap().count(), 0);
}

#[test]
fn the_full_check_looks_the_model_up_in_the_servers_list_and_generates_one_token() {
    let fixture = fixture();
    let model = fixture.text_model();
    fixture.text.write(&fixture.models_root(), TEXT);
    let fake = FakeOllama::start("1.0.0");
    let server = Server::attached(fake.address(), "1.0.0");
    assert_eq!(
        fixture.models.observe_full(&server, model, &ROOMY),
        Observation::Absent,
        "the server does not list the model"
    );
    fake.state
        .lock()
        .unwrap()
        .tags
        .insert("synthetic-text:other".into());
    assert_eq!(
        fixture.models.observe_full(&server, model, &ROOMY),
        Observation::Absent,
        "another tag of the model is another model"
    );
    fake.state
        .lock()
        .unwrap()
        .tags
        .insert("registry.ollama.ai/library/Synthetic-Text:test".into());
    assert_eq!(fixture.models.observe_full(&server, model, &ROOMY), PRESENT);
    let generation = fake
        .state
        .lock()
        .unwrap()
        .bodies
        .iter()
        .rfind(|body| body["prompt"].is_string())
        .cloned()
        .unwrap();
    assert_eq!(generation["model"], TEXT);
    assert_eq!(generation["options"]["num_predict"], 1);
    assert_eq!(generation["keep_alive"], 0);
    assert_eq!(generation["stream"], false);
    for (status, answer, expected) in [
        (
            "500 Internal Server Error",
            json!({ "error": "model requires more system memory (9.1 GiB) than is available (4.0 GiB)" }),
            Observation::Failed(FailureCategory::NotEnoughMemory),
        ),
        (
            "404 Not Found",
            json!({ "error": "model 'synthetic-text:test' not found" }),
            Observation::Absent,
        ),
        (
            "500 Internal Server Error",
            json!({ "error": "runner process has terminated" }),
            Observation::Failed(FailureCategory::Unexpected),
        ),
    ] {
        fake.state.lock().unwrap().generation = Some((status.into(), answer));
        assert_eq!(
            fixture.models.observe_full(&server, model, &ROOMY),
            expected
        );
    }
    drop(fake);
    assert_eq!(
        fixture.models.observe_full(&server, model, &ROOMY),
        Observation::Failed(FailureCategory::ProgramNotRunning)
    );
    // The setup's check keeps which request failed, so a server that went away reads
    // apart from one too busy to answer within a budget.
    let gone = fixture
        .models
        .check_full(&server, model, &ROOMY)
        .expect_err("a server that went away fails the full check");
    assert_eq!(gone.category(), FailureCategory::ProgramNotRunning);
    assert!(
        matches!(
            &gone,
            LocalAiError::NotRunning(NotRunningCause::Request {
                call: ServerCall::ListModels,
                failure: ExchangeFailure {
                    phase: ExchangePhase::Connect,
                    bound,
                    ..
                },
            }) if *bound == server.loopback().connect_timeout
        ),
        "the connect failed, under the connect bound: {gone:?}"
    );
}

#[test]
fn the_local_ai_reads_as_the_worst_of_its_program_and_models() {
    let version = Some("0.40.10".to_owned());
    let read = |program, models: &[Observation]| {
        reading(CheckMode::Quick, program, version.clone(), models).observation
    };
    let older = Observation::Differs {
        stale: StaleReason::ProgramTooOld,
    };
    assert_eq!(read(PRESENT, &[PRESENT, PRESENT]), PRESENT);
    assert_eq!(
        read(PRESENT, &[]),
        PRESENT,
        "no selection is the program alone"
    );
    assert_eq!(read(older, &[PRESENT]), older);
    assert_eq!(read(older, &[Observation::Absent]), Observation::Absent);
    assert_eq!(
        read(
            Observation::Absent,
            &[PRESENT, Observation::Blocked(BlockedReason::Hardware)]
        ),
        Observation::Blocked(BlockedReason::Hardware)
    );
    assert_eq!(
        reading(CheckMode::Full, PRESENT, version.clone(), &[PRESENT]).version,
        version
    );
}

#[test]
fn removal_takes_the_selected_models_and_only_the_layers_nothing_else_uses() {
    let fixture = fixture();
    let root = fixture.models_root();
    fixture.text.write(&root, TEXT);
    fixture.vision.write(&root, VISION);
    // A model the person keeps beside them shares the text model's first layer.
    let shared = &fixture.text.blobs[0];
    let own = vec![9u8; 11];
    let own_digest = format!("sha256:{}", Sha256Digest::of(&own));
    let kept_manifest = json!({
        "schemaVersion": 2,
        "config": { "digest": shared.0, "size": shared.1.len() },
        "layers": [{ "digest": own_digest, "size": own.len() }],
    })
    .to_string();
    let kept = root.join("manifests/registry.ollama.ai/library/kept/latest");
    fs::create_dir_all(kept.parent().unwrap()).unwrap();
    fs::write(&kept, kept_manifest).unwrap();
    let own_blob = root.join(format!(
        "blobs/sha256-{}",
        own_digest.strip_prefix("sha256:").unwrap()
    ));
    fs::write(&own_blob, &own).unwrap();

    fixture.models.remove().unwrap();
    let hardware = Hardware::default();
    for model in fixture.models.selection().as_slice() {
        assert_eq!(
            fixture.models.observe_quick(model, &hardware),
            Observation::Absent,
            "{}",
            model.role
        );
    }
    let remaining = |stored: &Stored, name: &str| {
        stored
            .files(&root, name)
            .into_iter()
            .filter(|(path, _)| path.exists())
            .count()
    };
    assert_eq!(remaining(&fixture.vision, VISION), 0);
    assert_eq!(
        remaining(&fixture.text, TEXT),
        1,
        "only the layer the kept model uses stays"
    );
    assert!(kept.is_file() && own_blob.is_file());

    fs::write(&kept, b"{").unwrap();
    fixture.text.write(&root, TEXT);
    fixture.models.remove().unwrap();
    assert_eq!(
        remaining(&fixture.text, TEXT),
        3,
        "an unreadable kept manifest keeps every layer"
    );

    // Without a selection nothing is removed.
    fs::write(&kept, b"{}").unwrap();
    fixture.text.write(&root, TEXT);
    Models::new(LocalModels::default(), root.clone())
        .remove()
        .unwrap();
    assert_eq!(remaining(&fixture.text, TEXT), 4);
    fs::remove_dir_all(&root).unwrap();
    fixture.models.remove().unwrap();
}

#[test]
fn a_named_model_is_removed_alone_and_the_layers_others_use_stay() {
    let fixture = fixture();
    let root = fixture.models_root();
    fixture.text.write(&root, TEXT);
    fixture.vision.write(&root, VISION);
    // A third model, outside any selection, shares the text model's config layer.
    let shared = &fixture.text.blobs[0];
    let other = root.join("manifests/registry.ollama.ai/library/other/latest");
    fs::create_dir_all(other.parent().unwrap()).unwrap();
    let other_manifest = json!({
        "schemaVersion": 2,
        "config": { "digest": shared.0, "size": shared.1.len() },
        "layers": [],
    })
    .to_string();
    fs::write(&other, &other_manifest).unwrap();
    let remaining = |stored: &Stored, name: &str| {
        stored
            .files(&root, name)
            .into_iter()
            .filter(|(path, _)| path.exists())
            .count()
    };
    let unselected = Models::new(LocalModels::default(), root.clone());

    unselected
        .remove_named(&ModelName::parse(TEXT).unwrap())
        .unwrap();
    assert_eq!(
        remaining(&fixture.text, TEXT),
        1,
        "only the layer another model uses stays"
    );
    assert_eq!(
        remaining(&fixture.vision, VISION),
        4,
        "every other model stays"
    );
    assert!(other.is_file());

    fixture.text.write(&root, TEXT);
    fs::write(&other, b"{").unwrap();
    unselected
        .remove_named(&ModelName::parse(TEXT).unwrap())
        .unwrap();
    assert_eq!(
        remaining(&fixture.text, TEXT),
        3,
        "an unreadable kept manifest keeps every layer"
    );

    unselected
        .remove_named(&ModelName::parse("synthetic-absent:test").unwrap())
        .unwrap();
    assert_eq!(
        remaining(&fixture.vision, VISION),
        4,
        "a model not stored removes nothing"
    );
}

/// A blob file the store holds that no manifest names, and the bytes it holds.
fn orphan_blob(root: &Path, seed: u8) -> PathBuf {
    let bytes = vec![seed; 13];
    let path = root
        .join("blobs")
        .join(format!("sha256-{}", Sha256Digest::of(&bytes)));
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(&path, bytes).unwrap();
    path
}

/// Writes bytes of a fetch that never finished, and returns their paths.
fn partial_files(root: &Path) -> Vec<PathBuf> {
    let folder = root.join(registry::PARTIAL);
    fs::create_dir_all(&folder).unwrap();
    ["sha256-0000", "manifest-1-0"]
        .into_iter()
        .map(|name| {
            let path = folder.join(name);
            fs::write(&path, b"unfinished").unwrap();
            path
        })
        .collect()
}

#[test]
fn removal_clears_the_partial_folder_and_the_blobs_no_remaining_manifest_names() {
    let fixture = fixture();
    let root = fixture.models_root();
    fixture.text.write(&root, TEXT);
    fixture.vision.write(&root, VISION);
    // A model the person keeps shares the text model's first layer.
    let shared = &fixture.text.blobs[0];
    let kept = root.join("manifests/registry.ollama.ai/library/kept/latest");
    fs::create_dir_all(kept.parent().unwrap()).unwrap();
    let kept_manifest = json!({
        "schemaVersion": 2,
        "config": { "digest": shared.0, "size": shared.1.len() },
        "layers": [],
    })
    .to_string();
    fs::write(&kept, &kept_manifest).unwrap();
    // A blob an earlier fetch or removal left behind, and a file that is no blob.
    let orphan = orphan_blob(&root, 40);
    let stray = root.join("blobs/notes.txt");
    fs::write(&stray, b"not a blob").unwrap();
    let partials = partial_files(&root);

    fixture.models.remove_named(fixture.vision_name()).unwrap();
    assert!(!orphan.exists(), "an unreferenced blob is reclaimed");
    assert!(stray.is_file(), "a file that is no blob stays");
    assert!(partials.iter().all(|path| !path.exists()));
    assert!(root.join(registry::PARTIAL).is_dir());
    let present = |stored: &Stored, name: &str| {
        stored
            .files(&root, name)
            .into_iter()
            .filter(|(path, _)| path.exists())
            .count()
    };
    assert_eq!(present(&fixture.vision, VISION), 0);
    assert_eq!(
        present(&fixture.text, TEXT),
        4,
        "a stored model other than the removed one keeps its manifest and layers"
    );
    assert!(kept.is_file());

    // Unreadable kept manifests keep every blob, but unfinished bytes are no model's.
    let orphan = orphan_blob(&root, 41);
    let partials = partial_files(&root);
    fs::write(&kept, b"{").unwrap();
    fixture.models.remove().unwrap();
    assert!(
        orphan.is_file(),
        "an unreadable kept manifest keeps every blob"
    );
    assert!(partials.iter().all(|path| !path.exists()));
}

/// A selection of `name` alone, stating `context` as its llama.cpp context.
fn stating(root: &Path, name: &str, context: Option<u32>) -> Models {
    Models::new(
        LocalModels::new(vec![
            SelectedModel::new(
                "download",
                name,
                None,
                context.map(|context| NonZeroU32::new(context).unwrap()),
            )
            .unwrap(),
        ])
        .unwrap(),
        root.to_path_buf(),
    )
}

fn context(value: u32) -> Option<NonZeroU32> {
    NonZeroU32::new(value)
}

#[test]
fn a_context_record_reads_back_is_replaced_and_refuses_what_it_cannot_hold() {
    let directory = tempfile::tempdir().unwrap();
    let root = directory.path().join("models");
    let name = ModelName::parse(TEXT).unwrap();
    assert_eq!(recorded_context(&root, &name), None, "nothing recorded yet");

    record_context(&root, &name, NonZeroU32::new(4096).unwrap()).unwrap();
    let file = root
        .join("cadrumo")
        .join("llamacpp-context")
        .join("registry.ollama.ai")
        .join("library")
        .join("synthetic-text")
        .join("test.json");
    assert_eq!(
        fs::read_to_string(&file).unwrap(),
        r#"{"schema":1,"llamacpp_context":4096}"#
    );
    assert_eq!(recorded_context(&root, &name), context(4096));
    // Outside the folders Ollama reads.
    assert!(!root.join("manifests").exists() && !root.join("blobs").exists());

    record_context(&root, &name, NonZeroU32::new(8192).unwrap()).unwrap();
    assert_eq!(recorded_context(&root, &name), context(8192));
    assert_eq!(
        fs::read_dir(file.parent().unwrap()).unwrap().count(),
        1,
        "a replacement leaves no other file"
    );

    // A tag with a dot keeps it: `.json` is added, never put in its place.
    let dotted = ModelName::parse("synthetic-text:1.5b").unwrap();
    record_context(&root, &dotted, NonZeroU32::new(2048).unwrap()).unwrap();
    assert!(file.with_file_name("1.5b.json").is_file());
    assert_eq!(recorded_context(&root, &dotted), context(2048));
    assert_eq!(recorded_context(&root, &name), context(8192));

    for bytes in [
        br#"{"schema":1,"llamacpp_context":0}"#.as_slice(),
        br#"{"schema":2,"llamacpp_context":4096}"#,
        br#"{"schema":1,"llamacpp_context":4096,"extra":0}"#,
        br#"{"schema":1}"#,
        br#"{"schema":1,"llamacpp_context":-1}"#,
        br#"{"schema":1,"llamacpp_context":"4096"}"#,
        b"{",
    ] {
        fs::write(&file, bytes).unwrap();
        assert_eq!(
            recorded_context(&root, &name),
            None,
            "{}",
            String::from_utf8_lossy(bytes)
        );
    }
    // A record longer than any context record is not read.
    let mut long = br#"{"schema":1,"llamacpp_context":4096}"#.to_vec();
    long.resize(8192, b' ');
    fs::write(&file, long).unwrap();
    assert_eq!(recorded_context(&root, &name), None);
}

#[cfg(unix)]
#[test]
fn a_context_record_behind_a_link_is_neither_read_nor_written() {
    use std::os::unix::fs::symlink;
    let directory = tempfile::tempdir().unwrap();
    let root = directory.path().join("models");
    let name = ModelName::parse(TEXT).unwrap();
    let outside = directory.path().join("outside");
    fs::create_dir_all(&outside).unwrap();
    fs::write(
        outside.join("test.json"),
        br#"{"schema":1,"llamacpp_context":4096}"#,
    )
    .unwrap();
    let folder = root
        .join("cadrumo")
        .join("llamacpp-context")
        .join("registry.ollama.ai")
        .join("library");
    fs::create_dir_all(&folder).unwrap();
    symlink(&outside, folder.join("synthetic-text")).unwrap();

    assert_eq!(recorded_context(&root, &name), None);
    assert!(record_context(&root, &name, NonZeroU32::new(2048).unwrap()).is_err());
    assert_eq!(
        fs::read(outside.join("test.json")).unwrap(),
        br#"{"schema":1,"llamacpp_context":4096}"#,
        "nothing is written through the link"
    );
}

#[test]
fn a_pull_records_the_stated_context_also_for_a_model_already_stored_and_fetches_nothing() {
    let directory = tempfile::tempdir().unwrap();
    let root = directory.path().join("models");
    let name = ModelName::parse(TEXT).unwrap();
    let stored = Stored::new(5);
    let publishers = Publishers::start(stored.routes(TEXT), Vec::new());

    // A fetched pull records the context once the model is whole.
    let models = stating(&root, TEXT, Some(4096));
    let model = &models.selection().as_slice()[0];
    let fetched = fetch(
        &models,
        model,
        &publishers.network(),
        &approved_for(&models, "download"),
    );
    assert_eq!(fetched.result.unwrap(), PRESENT);
    assert_eq!(recorded_context(&root, &name), context(4096));
    let targets = publishers.server.targets().len();
    assert!(targets > 0);

    // A pull of a stored model that states another context records it and fetches
    // nothing.
    let models = stating(&root, TEXT, Some(2048));
    let model = &models.selection().as_slice()[0];
    let again = fetch(
        &models,
        model,
        &publishers.network(),
        &approved_for(&models, "download"),
    );
    assert_eq!(again.result.unwrap(), PRESENT);
    assert_eq!(recorded_context(&root, &name), context(2048));
    assert_eq!(
        publishers.server.targets().len(),
        targets,
        "nothing fetched"
    );

    // A pull that states no context leaves the earlier record as it was.
    let models = stating(&root, TEXT, None);
    let model = &models.selection().as_slice()[0];
    let silent = fetch(
        &models,
        model,
        &publishers.network(),
        &approved_for(&models, "download"),
    );
    assert_eq!(silent.result.unwrap(), PRESENT);
    assert_eq!(recorded_context(&root, &name), context(2048));
    assert_eq!(publishers.server.targets().len(), targets);

    // A model stored before any context was stated gets one from its next pull, with no
    // download.
    let vision = ModelName::parse(VISION).unwrap();
    Stored::new(9).write(&root, VISION);
    assert_eq!(recorded_context(&root, &vision), None);
    let models = stating(&root, VISION, Some(16384));
    let model = &models.selection().as_slice()[0];
    let present = fetch(
        &models,
        model,
        &publishers.network(),
        &approved_for(&models, "download"),
    );
    assert_eq!(present.result.unwrap(), PRESENT);
    assert_eq!(recorded_context(&root, &vision), context(16384));
    assert_eq!(publishers.server.targets().len(), targets);
}

#[test]
fn removal_deletes_the_removed_models_contexts_and_keeps_a_kept_models() {
    let fixture = fixture();
    let root = fixture.models_root();
    fixture.text.write(&root, TEXT);
    fixture.vision.write(&root, VISION);
    let (text, vision) = (
        ModelName::parse(TEXT).unwrap(),
        fixture.vision_name().clone(),
    );
    let kept = ModelName::parse("synthetic-kept:test").unwrap();
    Stored::new(3).write(&root, "synthetic-kept:test");
    for (name, value) in [(&text, 4096), (&vision, 2048), (&kept, 8192)] {
        record_context(&root, name, NonZeroU32::new(value).unwrap()).unwrap();
    }

    fixture.models.remove().unwrap();
    assert_eq!(recorded_context(&root, &text), None);
    assert_eq!(recorded_context(&root, &vision), None);
    assert_eq!(
        recorded_context(&root, &kept),
        context(8192),
        "a kept model keeps its context"
    );

    // A model removed by name loses its context, also when its manifest is already gone.
    let unselected = Models::new(LocalModels::default(), root.clone());
    record_context(&root, &text, NonZeroU32::new(4096).unwrap()).unwrap();
    unselected.remove_named(&text).unwrap();
    assert_eq!(recorded_context(&root, &text), None);
    assert_eq!(recorded_context(&root, &kept), context(8192));
    unselected.remove_named(&kept).unwrap();
    assert_eq!(recorded_context(&root, &kept), None);
}
