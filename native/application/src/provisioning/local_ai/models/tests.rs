use super::*;
use crate::provisioning::{
    items::ItemId,
    local_ai::{fake_ollama::FakeOllama, program::Server, reading},
    plan::PlanEntry,
    state::{CheckMode, StaleReason},
};
use serde_json::{Value, json};
use std::{fs, time::Duration};

const GIB: u64 = 1024 * 1024 * 1024;
/// Obviously synthetic names: the engine knows no model, so its tests name none.
const TEXT: &str = "synthetic-text:test";
const VISION: &str = "synthetic-vision:test";

/// One model as the program stores it: its manifest, and each layer's bytes by digest.
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
        let layer =
            |(digest, bytes): &(String, Vec<u8>)| json!({ "digest": digest, "size": bytes.len() });
        let manifest = json!({
            "schemaVersion": 2,
            "config": layer(&blobs[0]),
            "layers": [layer(&blobs[1]), layer(&blobs[2])],
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
}

fn selected(role: &str, name: &str, size_bytes: u64) -> SelectedModel {
    SelectedModel::new(role, name, size_bytes).unwrap()
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
}

const ROOMY: Hardware = Hardware {
    total_memory_bytes: Some(64 * GIB),
    nvidia_vram_bytes: None,
};

const PRESENT: Observation = Observation::Present { note: None };

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
            SelectedModel::new(role, name, size).is_err(),
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
    for part in &parts {
        assert_eq!(part.destination, Some(Destination::OllamaModels));
        assert!(!part.installs_outside_program);
        assert_eq!(part.source_hosts[0].as_str(), "registry.ollama.ai");
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
        Destination::OllamaModels,
    )
    .unwrap();
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
        elsewhere.plan_parts()[0].source_hosts[0].as_str(),
        "models.example.com"
    );
    let none = Models::new(LocalModels::default(), fixture.models_root());
    assert!(none.plan_parts().is_empty(), "no selection plans no model");
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

/// A pacing that records each wait instead of waiting.
#[derive(Default)]
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
        Ok(())
    }
    fn jitter(&mut self) -> f64 {
        0.5
    }
}

fn progress(digest: &str, total: usize, completed: usize) -> Value {
    json!({ "status": format!("pulling {digest}"), "digest": digest, "total": total, "completed": completed })
}

struct Pulled {
    result: Result<Observation, LocalAiError>,
    events: Vec<TransferEvent>,
    waits: Vec<Duration>,
    pulls: Vec<Value>,
}

fn pull_with(
    fixture: &Fixture,
    fake: &FakeOllama,
    policy: RetryPolicy,
    cancellation: &Cancellation,
) -> Pulled {
    let server = Server::attached(fake.address(), "1.0.0");
    let mut pacing = RecordedPacing::default();
    let mut events = Vec::new();
    let mut sink = |event| events.push(event);
    let result = fixture.models.pull(
        &server,
        fixture.text_model(),
        &mut Pull {
            policy,
            pacing: &mut pacing,
            events: &mut sink,
            cancellation,
        },
    );
    let pulls = fake
        .state
        .lock()
        .unwrap()
        .bodies
        .iter()
        .filter(|body| body["stream"] == true)
        .cloned()
        .collect();
    Pulled {
        result,
        events,
        waits: pacing.waits,
        pulls,
    }
}

#[test]
fn a_cut_off_pull_is_pulled_again_and_reports_byte_progress_for_the_whole_model() {
    let fixture = fixture();
    let fake = FakeOllama::start("1.0.0");
    let text = &fixture.text;
    let (config, first, second) = (&text.blobs[0], &text.blobs[1], &text.blobs[2]);
    {
        let mut state = fake.state.lock().unwrap();
        state.pulls.push_back(vec![
            json!({ "status": "pulling manifest" }),
            progress(&first.0, first.1.len(), 20),
        ]);
        // The program resumes the layer it had begun.
        state.pulls.push_back(vec![
            json!({ "status": "pulling manifest" }),
            progress(&first.0, first.1.len(), 20),
            progress(&first.0, first.1.len(), first.1.len()),
            progress(&second.0, second.1.len(), second.1.len()),
            progress(&config.0, config.1.len(), config.1.len()),
            json!({ "status": "verifying sha256 digest" }),
            json!({ "status": "writing manifest" }),
            json!({ "status": "success" }),
        ]);
        state
            .installs
            .insert(TEXT.into(), text.files(&fixture.models_root(), TEXT));
    }
    let pulled = pull_with(
        &fixture,
        &fake,
        RetryPolicy::default(),
        &Cancellation::default(),
    );
    assert_eq!(pulled.result.unwrap(), PRESENT);
    let request = json!({ "model": TEXT, "stream": true });
    assert_eq!(pulled.pulls, [request.clone(), request]);
    assert_eq!(
        fake.state
            .lock()
            .unwrap()
            .requests
            .last()
            .map(String::as_str),
        Some("GET /api/tags HTTP/1.1"),
        "the pulled model is read back from the server's own list"
    );
    assert_eq!(pulled.waits.len(), 1);
    assert!((Duration::from_secs(2)..=Duration::from_secs(3)).contains(&pulled.waits[0]));
    let total = text.size();
    let completed: Vec<u64> = pulled
        .events
        .iter()
        .filter_map(|event| match event {
            TransferEvent::Progress {
                completed,
                total: of,
            } => {
                assert_eq!(*of, total);
                Some(*completed)
            }
            TransferEvent::Retrying { .. } => None,
        })
        .collect();
    assert_eq!(completed.first(), Some(&20));
    assert_eq!(completed.last(), Some(&total));
    assert!(
        completed
            .windows(2)
            .filter(|pair| pair[1] < pair[0])
            .count()
            == 0
    );
    assert!(matches!(
        pulled
            .events
            .iter()
            .find(|event| matches!(event, TransferEvent::Retrying { .. })),
        Some(TransferEvent::Retrying { attempt: 2, .. })
    ));
    assert_eq!(
        fixture.models.observe_quick(fixture.text_model(), &ROOMY),
        PRESENT
    );

    // A present model is not pulled again.
    let again = pull_with(
        &fixture,
        &fake,
        RetryPolicy::default(),
        &Cancellation::default(),
    );
    assert_eq!(again.result.unwrap(), PRESENT);
    assert_eq!(again.pulls.len(), 2, "no new pull request");
}

#[test]
fn a_pull_the_program_calls_done_but_did_not_store_fails_rather_than_finishing() {
    let fixture = fixture();
    let fake = FakeOllama::start("1.0.0");
    fake.state
        .lock()
        .unwrap()
        .pulls
        .push_back(vec![json!({ "status": "success" })]);
    let pulled = pull_with(
        &fixture,
        &fake,
        RetryPolicy::default(),
        &Cancellation::default(),
    );
    assert_eq!(
        pulled.result.unwrap_err().category(),
        FailureCategory::DamagedDownload
    );
    assert_eq!(pulled.pulls.len(), 1);
}

#[test]
fn pull_failures_take_their_category_and_only_passing_ones_are_retried() {
    let fixture = fixture();
    let policy = RetryPolicy {
        max_attempts: 3,
        ..RetryPolicy::default()
    };
    for (error, category, attempts) in [
        (
            "write /models/blobs: no space left on device",
            FailureCategory::DiskFull,
            1,
        ),
        (
            "pull model manifest: file does not exist",
            FailureCategory::Unexpected,
            1,
        ),
        (
            "tls: failed to verify certificate: x509",
            FailureCategory::SecureConnectionFailed,
            1,
        ),
        (
            "dial tcp: lookup registry.ollama.ai: no such host",
            FailureCategory::Offline,
            3,
        ),
        (
            "max retries exceeded: 503 Service Unavailable",
            FailureCategory::HostUnreachable,
            3,
        ),
    ] {
        let fake = FakeOllama::start("1.0.0");
        for _ in 0..attempts {
            fake.state.lock().unwrap().pulls.push_back(vec![
                json!({ "status": "pulling manifest" }),
                json!({ "error": error }),
            ]);
        }
        let pulled = pull_with(&fixture, &fake, policy, &Cancellation::default());
        assert!(
            matches!(pulled.result, Err(LocalAiError::Failed(found)) if found == category),
            "{error}"
        );
        assert_eq!(pulled.pulls.len(), attempts, "{error}");
    }
    let fake = FakeOllama::start("1.0.0");
    let cancelled = Cancellation::default();
    cancelled.cancel();
    let pulled = pull_with(&fixture, &fake, policy, &cancelled);
    assert_eq!(
        pulled.result.unwrap_err().category(),
        FailureCategory::Cancelled
    );
    assert!(pulled.pulls.is_empty());
    assert_eq!(
        pull_error_category("Bad Gateway"),
        FailureCategory::HostUnreachable
    );
    assert_eq!(
        pull_error_category("something new"),
        FailureCategory::Unexpected
    );
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
}

/// The pull path end to end for a model no catalogue has: pulled by the name the
/// selection spells, stored where the program keeps that name, read back from the
/// server's list and answering one token, with no digest compared anywhere.
#[test]
fn a_synthetic_model_from_any_registry_is_pulled_listed_and_checked_by_its_name() {
    const SYNTHETIC: &str = "models.example.com/someone/synthetic-model:test";
    let root = tempfile::tempdir().unwrap();
    let models_root = root.path().join("models");
    let stored = Stored::new(3);
    let models = Models::new(
        LocalModels::new(vec![selected("text_extraction", SYNTHETIC, stored.size())]).unwrap(),
        models_root.clone(),
    );
    let model = &models.selection().as_slice()[0];
    let fake = FakeOllama::start("1.0.0");
    {
        let mut state = fake.state.lock().unwrap();
        let mut lines = vec![json!({ "status": "pulling manifest" })];
        for (digest, bytes) in &stored.blobs {
            lines.push(progress(digest, bytes.len(), bytes.len()));
        }
        lines.push(json!({ "status": "success" }));
        state.pulls.push_back(lines);
        state
            .installs
            .insert(SYNTHETIC.into(), stored.files(&models_root, SYNTHETIC));
    }
    let server = Server::attached(fake.address(), "1.0.0");
    assert_eq!(models.observe_quick(model, &ROOMY), Observation::Absent);
    let mut pacing = RecordedPacing::default();
    let mut events = Vec::new();
    let pulled = models
        .pull(
            &server,
            model,
            &mut Pull {
                policy: RetryPolicy::default(),
                pacing: &mut pacing,
                events: &mut |event| events.push(event),
                cancellation: &Cancellation::default(),
            },
        )
        .unwrap();
    assert_eq!(pulled, PRESENT);
    assert!(matches!(
        events.last(),
        Some(TransferEvent::Progress { completed, total }) if *completed == stored.size() && *total == stored.size()
    ));
    assert!(
        models_root
            .join("manifests/models.example.com/someone/synthetic-model/test")
            .is_file()
    );
    assert_eq!(models.observe_full(&server, model, &ROOMY), PRESENT);
    let state = fake.state.lock().unwrap();
    let named: Vec<&Value> = state
        .bodies
        .iter()
        .filter(|body| body["model"].is_string())
        .map(|body| &body["model"])
        .collect();
    assert!(!named.is_empty());
    assert!(named.iter().all(|name| **name == SYNTHETIC), "{named:?}");
    assert_eq!(
        models.plan_parts()[0].source_hosts[0].as_str(),
        "models.example.com"
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
        note: None,
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
