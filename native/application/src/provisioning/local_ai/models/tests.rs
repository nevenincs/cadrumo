use super::*;
use crate::provisioning::{
    items::{ItemId, PROGRAM_PART},
    local_ai::{fake_ollama::FakeOllama, program::Server, reading},
    plan::PlanEntry,
    state::CheckMode,
};
use serde_json::{Value, json};
use std::{fs, time::Duration};

const GIB: u64 = 1024 * 1024 * 1024;

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

    fn digest(&self) -> Sha256Digest {
        Sha256Digest::of(&self.manifest)
    }

    fn size(&self) -> u64 {
        self.blobs.iter().map(|(_, bytes)| bytes.len() as u64).sum()
    }

    fn files(&self, root: &Path, name: &str) -> Vec<(PathBuf, Vec<u8>)> {
        let (model, tag) = name.split_once(':').unwrap();
        let mut files = vec![(
            root.join("manifests")
                .join(REGISTRY)
                .join("library")
                .join(model)
                .join(tag),
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

fn pins(text: &Stored, vision: &Stored) -> ModelPins {
    ModelPins::parse(&format!(
        "hosts = [\"registry.ollama.ai\"]\n\n[roles]\n\
         vision_transcription = \"qwen3-vl:2b\"\ntext_extraction = \"qwen3:1.7b\"\n\
         column_role_mapping = \"qwen3:1.7b\"\nsupply_nature_proposal = \"qwen3:1.7b\"\n\n\
         [[models]]\nname = \"qwen3:1.7b\"\nmanifest_digest = \"{}\"\ndownload_bytes = {}\n\
         memory_bytes = {}\nlicence = \"Apache-2.0\"\ncommercial_use_permitted = true\n\n\
         [[models]]\nname = \"qwen3-vl:2b\"\nmanifest_digest = \"{}\"\ndownload_bytes = {}\n\
         memory_bytes = {}\nlicence = \"Apache-2.0\"\ncommercial_use_permitted = true\n",
        text.digest(),
        text.size(),
        2 * GIB,
        vision.digest(),
        vision.size(),
        3 * GIB,
    ))
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
    let models = Models::new(pins(&text, &vision), root.path().join("models"));
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
}

const ROOMY: Hardware = Hardware {
    total_memory_bytes: Some(64 * GIB),
    nvidia_vram_bytes: None,
};

const PRESENT: Observation = Observation::Present { note: None };
const STALE: Observation = Observation::Differs {
    stale: StaleReason::DifferentModelVersion,
    note: None,
};

#[test]
fn the_plan_has_a_part_per_role_and_counts_a_shared_model_once() {
    let fixture = fixture();
    let parts = fixture.models.plan_parts();
    assert_eq!(
        parts
            .iter()
            .map(|part| part.part_id.as_str())
            .collect::<Vec<_>>(),
        MODEL_ROLES
    );
    for part in &parts {
        assert_eq!(part.destination, Some(Destination::OllamaModels));
        assert!(!part.installs_outside_program);
        assert_eq!(part.source_hosts[0].as_str(), "registry.ollama.ai");
    }
    assert_eq!(
        parts[1].target_version,
        Some(format!("qwen3:1.7b@{}", fixture.text.digest()))
    );
    assert_eq!(parts[1].target_version, parts[3].target_version);
    let program = PlanPart {
        part_id: PROGRAM_PART.into(),
        download_bytes: Some(1000),
        source_hosts: vec![crate::value::HostName::new("github.com").unwrap()],
        destination: Some(Destination::LocalAiProgram),
        installs_outside_program: false,
        target_version: Some("1.0.0".into()),
        advisories: Vec::new(),
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
}

#[test]
fn the_quick_check_reads_the_stored_manifest_against_its_pin() {
    let fixture = fixture();
    let root = fixture.models_root();
    let role = "text_extraction";
    assert_eq!(
        fixture.models.observe_quick(role, &ROOMY),
        Observation::Absent
    );
    fixture.text.write(&root, "qwen3:1.7b");
    assert_eq!(fixture.models.observe_quick(role, &ROOMY), PRESENT);
    assert_eq!(
        fixture.models.observe_quick("vision_transcription", &ROOMY),
        Observation::Absent
    );
    // Another manifest under the pinned name is a different model version.
    fixture.vision.write(&root, "qwen3:1.7b");
    assert_eq!(fixture.models.observe_quick(role, &ROOMY), STALE);
    fixture.text.write(&root, "qwen3:1.7b");
    // A layer that is missing or short reads as a model not yet all there.
    let files = fixture.text.files(&root, "qwen3:1.7b");
    fs::write(&files[2].0, b"short").unwrap();
    assert_eq!(
        fixture.models.observe_quick(role, &ROOMY),
        Observation::Absent
    );
    fs::remove_file(&files[2].0).unwrap();
    assert_eq!(
        fixture.models.observe_quick(role, &ROOMY),
        Observation::Absent
    );
    fixture.text.write(&root, "qwen3:1.7b");
    // A computer too small for the model is held back whatever is stored.
    let small = Hardware {
        total_memory_bytes: Some(GIB),
        nvidia_vram_bytes: Some(GIB),
    };
    assert_eq!(
        fixture.models.observe_quick(role, &small),
        Observation::Blocked(BlockedReason::Hardware)
    );
    let card = Hardware {
        total_memory_bytes: Some(GIB),
        nvidia_vram_bytes: Some(8 * GIB),
    };
    assert_eq!(fixture.models.observe_quick(role, &card), PRESENT);
    assert_eq!(
        fixture.models.observe_quick("no_such_role", &ROOMY),
        Observation::Blocked(BlockedReason::NotInThisBuild)
    );
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
        "text_extraction",
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
        state.installs.insert(
            "qwen3:1.7b".into(),
            text.files(&fixture.models_root(), "qwen3:1.7b"),
        );
    }
    let pulled = pull_with(
        &fixture,
        &fake,
        RetryPolicy::default(),
        &Cancellation::default(),
    );
    assert_eq!(pulled.result.unwrap(), PRESENT);
    let request = json!({ "model": "qwen3:1.7b", "stream": true });
    assert_eq!(pulled.pulls, [request.clone(), request]);
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
        fixture.models.observe_quick("text_extraction", &ROOMY),
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
fn a_registry_serving_another_manifest_leaves_the_model_stale() {
    let fixture = fixture();
    let fake = FakeOllama::start("1.0.0");
    {
        let mut state = fake.state.lock().unwrap();
        state.pulls.push_back(vec![json!({ "status": "success" })]);
        state.installs.insert(
            "qwen3:1.7b".into(),
            fixture.vision.files(&fixture.models_root(), "qwen3:1.7b"),
        );
    }
    let pulled = pull_with(
        &fixture,
        &fake,
        RetryPolicy::default(),
        &Cancellation::default(),
    );
    assert_eq!(pulled.result.unwrap(), STALE);
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
fn the_full_check_compares_the_servers_digest_and_generates_one_token() {
    let fixture = fixture();
    let role = "text_extraction";
    fixture.text.write(&fixture.models_root(), "qwen3:1.7b");
    let fake = FakeOllama::start("1.0.0");
    let server = Server::attached(fake.address(), "1.0.0");
    assert_eq!(
        fixture.models.observe_full(&server, role, &ROOMY),
        Observation::Absent,
        "the server does not list the model"
    );
    fake.state
        .lock()
        .unwrap()
        .tags
        .insert("qwen3:1.7b".into(), fixture.vision.digest().to_string());
    assert_eq!(fixture.models.observe_full(&server, role, &ROOMY), STALE);
    fake.state
        .lock()
        .unwrap()
        .tags
        .insert("qwen3:1.7b".into(), fixture.text.digest().to_string());
    assert_eq!(fixture.models.observe_full(&server, role, &ROOMY), PRESENT);
    let generation = fake
        .state
        .lock()
        .unwrap()
        .bodies
        .iter()
        .rfind(|body| body["prompt"].is_string())
        .cloned()
        .unwrap();
    assert_eq!(generation["model"], "qwen3:1.7b");
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
            json!({ "error": "model 'qwen3:1.7b' not found" }),
            Observation::Absent,
        ),
        (
            "500 Internal Server Error",
            json!({ "error": "llama runner process has terminated" }),
            Observation::Failed(FailureCategory::Unexpected),
        ),
    ] {
        fake.state.lock().unwrap().generation = Some((status.into(), answer));
        assert_eq!(fixture.models.observe_full(&server, role, &ROOMY), expected);
    }
    drop(fake);
    assert_eq!(
        fixture.models.observe_full(&server, role, &ROOMY),
        Observation::Failed(FailureCategory::ProgramNotRunning)
    );
}

#[test]
fn the_local_ai_reads_as_the_worst_of_its_program_and_models() {
    let version = Some("0.40.10".to_owned());
    let read = |program, models: &[Observation]| {
        reading(CheckMode::Quick, program, version.clone(), models).observation
    };
    assert_eq!(read(PRESENT, &[PRESENT, PRESENT]), PRESENT);
    assert_eq!(read(PRESENT, &[PRESENT, STALE]), STALE);
    assert_eq!(
        read(PRESENT, &[Observation::Absent, STALE]),
        Observation::Absent
    );
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
fn removal_takes_the_pinned_models_and_only_the_layers_nothing_else_uses() {
    let fixture = fixture();
    let root = fixture.models_root();
    fixture.text.write(&root, "qwen3:1.7b");
    fixture.vision.write(&root, "qwen3-vl:2b");
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
    for role in MODEL_ROLES {
        assert_eq!(
            fixture.models.observe_quick(role, &hardware),
            Observation::Absent,
            "{role}"
        );
    }
    let remaining = |stored: &Stored, name: &str| {
        stored
            .files(&root, name)
            .into_iter()
            .filter(|(path, _)| path.exists())
            .count()
    };
    assert_eq!(remaining(&fixture.vision, "qwen3-vl:2b"), 0);
    assert_eq!(
        remaining(&fixture.text, "qwen3:1.7b"),
        1,
        "only the layer the kept model uses stays"
    );
    assert!(kept.is_file() && own_blob.is_file());

    fs::write(&kept, b"{").unwrap();
    fixture.text.write(&root, "qwen3:1.7b");
    fixture.models.remove().unwrap();
    assert_eq!(
        remaining(&fixture.text, "qwen3:1.7b"),
        3,
        "an unreadable kept manifest keeps every layer"
    );
    fs::remove_dir_all(&root).unwrap();
    fixture.models.remove().unwrap();
}
