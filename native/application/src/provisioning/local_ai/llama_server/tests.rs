use super::*;
use crate::{
    provisioning::{
        local_ai::{
            ServerStartFailure, StartFailureKind, VersionFailure,
            fake_llamacpp::{
                FakeLlamaCpp, HELPER_ARGUMENTS, HELPER_BUILD, HELPER_LOG, HELPER_MODE,
                HELPER_MODELS, HELPER_READY_GATE, ModelStatus, Scripted,
            },
            program::{
                Uncontained, announcement, announces, latest_start_failure,
                tests::{ambient, answers, free_address},
            },
            supervision::{RestartPolicy, ServerState, ServerSupervisor},
        },
        proxy::PROXY_URL,
    },
    value::Sha256Digest,
};
use serde_json::json;
use std::{
    path::Path,
    time::{Duration, Instant},
};

const BUILD: &str = "b12184";
const BUILD_INFO: &str = "b12184-c0ab6e5c0";

/// A package whose `llama_server` folder holds the test binary as the program.
pub(crate) fn package(root: &Path) -> PathBuf {
    let folder = root.join("package").join("bin").join("llama");
    fs::create_dir_all(&folder).unwrap();
    fs::copy(std::env::current_exe().unwrap(), folder.join(EXECUTABLE)).unwrap();
    folder
}

pub(crate) fn packaged(root: &Path) -> (LlamaServer, Locations) {
    let locations = Locations::under(&root.join("storage"));
    let server = LlamaServer::packaged(&package(root), BUILD, &locations, LOAD_CONTEXT).unwrap();
    (server, locations)
}

/// Runs the fake router in the program's place, reporting `build_info` and adding
/// `environment`.
pub(crate) fn stand_in(server: &mut LlamaServer, build_info: &str, environment: &[(&str, &OsStr)]) {
    let mut added = vec![
        (OsString::from(HELPER_MODE), OsString::from("serve")),
        (OsString::from(HELPER_BUILD), OsString::from(build_info)),
    ];
    added.extend(
        environment
            .iter()
            .map(|(name, value)| (OsString::from(name), value.to_os_string())),
    );
    server.serve_override = Some(ServeOverride {
        arguments: HELPER_ARGUMENTS.map(OsString::from).to_vec(),
        environment: added,
    });
}

/// Writes `bytes` into the store as a blob and returns its manifest descriptor.
pub(crate) fn blob(models: &Path, media_type: &str, bytes: &[u8]) -> serde_json::Value {
    let digest = Sha256Digest::of(bytes);
    let blobs = models.join("blobs");
    fs::create_dir_all(&blobs).unwrap();
    fs::write(blobs.join(format!("sha256-{digest}")), bytes).unwrap();
    json!({ "mediaType": media_type, "digest": format!("sha256:{digest}"), "size": bytes.len() })
}

/// Writes a manifest naming `layers` under `host/namespace/model/tag`.
pub(crate) fn manifest(models: &Path, path: [&str; 4], layers: &[serde_json::Value]) {
    let config = blob(
        models,
        "application/vnd.docker.container.image.v1+json",
        format!("config of {}", path.join("/")).as_bytes(),
    );
    let [host, namespace, model, tag] = path;
    let folder = models
        .join("manifests")
        .join(host)
        .join(namespace)
        .join(model);
    fs::create_dir_all(&folder).unwrap();
    let document = json!({
        "schemaVersion": 2,
        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
        "config": config,
        "layers": layers,
    });
    fs::write(folder.join(tag), document.to_string()).unwrap();
}

/// Where the store keeps `bytes`, as a preset names it.
fn value_of(models: &Path, bytes: &[u8]) -> String {
    let path = models
        .join("blobs")
        .join(format!("sha256-{}", Sha256Digest::of(bytes)));
    let text = path.to_str().unwrap().to_owned();
    if cfg!(windows) {
        text.replace('\\', "/")
    } else {
        text
    }
}

#[test]
fn a_package_without_the_program_reports_it_not_packaged_and_never_starts_it() {
    let root = tempfile::tempdir().unwrap();
    let locations = Locations::under(&root.path().join("storage"));
    let empty = root.path().join("package").join("bin").join("llama");
    fs::create_dir_all(&empty).unwrap();
    assert_eq!(
        LlamaServer::packaged(&empty, BUILD, &locations, LOAD_CONTEXT).err(),
        Some(LlamaServerUnavailable::NotPackaged)
    );
    let folder = package(root.path());
    for build in ["12184", "b", "b12x", "0.40.10"] {
        assert_eq!(
            LlamaServer::packaged(&folder, build, &locations, LOAD_CONTEXT).err(),
            Some(LlamaServerUnavailable::Invalid),
            "{build}"
        );
    }
    assert_eq!(
        LlamaServer::packaged(&folder, BUILD, &locations, 0).err(),
        Some(LlamaServerUnavailable::Invalid)
    );
    assert!(!locations.programs.parent().unwrap().join(FOLDER).exists());
}

#[test]
fn the_preset_presents_each_whole_model_with_its_context_and_projector() {
    let root = tempfile::tempdir().unwrap();
    let models = root.path().join("models");
    let registry = ["registry.ollama.ai", "library"];
    // A registry vision model with a projector layer, and a text model.
    manifest(
        &models,
        [registry[0], registry[1], "qwen3-vl", "4b-instruct"],
        &[
            blob(&models, MODEL_MEDIA_TYPE, b"vision weights"),
            blob(&models, PROJECTOR_MEDIA_TYPE, b"vision projector"),
            blob(
                &models,
                "application/vnd.ollama.image.template",
                b"template",
            ),
        ],
    );
    manifest(
        &models,
        [registry[0], registry[1], "qwen3", "1.7b"],
        &[blob(&models, MODEL_MEDIA_TYPE, b"text weights")],
    );
    // A Hugging Face model file and its projector under its own host.
    manifest(
        &models,
        ["huggingface.co", "Owner", "Model-GGUF", "Model-Q4_K_M"],
        &[
            blob(&models, MODEL_MEDIA_TYPE, b"hf weights"),
            blob(&models, PROJECTOR_MEDIA_TYPE, b"hf projector"),
        ],
    );
    // A model with a layer missing, one with no model layer and one with two present
    // nothing.
    let mut missing = blob(&models, MODEL_MEDIA_TYPE, b"gone");
    missing["size"] = json!(9999);
    manifest(
        &models,
        [registry[0], registry[1], "partial", "latest"],
        &[missing],
    );
    manifest(
        &models,
        [registry[0], registry[1], "nothing", "latest"],
        &[blob(&models, PROJECTOR_MEDIA_TYPE, b"lonely projector")],
    );
    manifest(
        &models,
        [registry[0], registry[1], "twice", "latest"],
        &[
            blob(&models, MODEL_MEDIA_TYPE, b"first"),
            blob(&models, MODEL_MEDIA_TYPE, b"second"),
        ],
    );

    let hf = "huggingface.co/Owner/Model-GGUF:Model-Q4_K_M";
    let expected = format!(
        "[{}]\nalias = {hf}\nmodel = {}\nmmproj = {}\nctx-size = 4096\n\n\
         [{}]\nalias = qwen3-vl:4b-instruct\nmodel = {}\nmmproj = {}\nctx-size = 4096\n\n\
         [{}]\nalias = qwen3:1.7b\nmodel = {}\nctx-size = 4096\n\n",
        router_id(hf),
        value_of(&models, b"hf weights"),
        value_of(&models, b"hf projector"),
        router_id("qwen3-vl:4b-instruct"),
        value_of(&models, b"vision weights"),
        value_of(&models, b"vision projector"),
        router_id("qwen3:1.7b"),
        value_of(&models, b"text weights"),
    );
    assert_eq!(preset(&models, 4096), expected);
    assert_eq!(preset(&root.path().join("no-store"), 4096), "");
}

#[test]
fn a_section_the_router_cannot_rewrite_names_each_model_and_the_alias_is_its_name() {
    let names = [
        "qwen3:1.7b",
        "qwen3:1.7B",
        "qwen3-vl:4b-instruct",
        "huggingface.co/Owner/Model-GGUF:Model-Q4_K_M",
    ];
    let ids: Vec<String> = names.iter().map(|name| router_id(name)).collect();
    for (id, name) in ids.iter().zip(names) {
        // The router reads a colon as a repository and a quantisation and rewrites the
        // section's name, so no id has one, nor anything but a plain token.
        assert!(
            id.starts_with("m-") && id[2..].bytes().all(|c| c.is_ascii_hexdigit()),
            "{name}: {id}"
        );
        assert_eq!(*id, router_id(name), "one name has one id every time");
    }
    let distinct: std::collections::BTreeSet<&String> = ids.iter().collect();
    assert_eq!(distinct.len(), names.len(), "{ids:?}");

    // A model is found by the id the router lists it under or by an alias, and by no
    // other name.
    let entry = json!({ "id": ids[0], "aliases": [names[0]], "status": { "value": "unloaded" } });
    assert!(answers_to(&entry, names[0]));
    assert!(answers_to(&entry, &ids[0]));
    assert!(!answers_to(&entry, names[1]));
    assert!(!answers_to(&json!({ "id": ids[0] }), names[0]));
}

#[test]
fn the_router_runs_from_the_preset_on_its_address_with_no_model_loaded_or_evicted_by_itself() {
    let root = tempfile::tempdir().unwrap();
    let (server, locations) = packaged(root.path());
    let address = free_address();
    let command = server.serve_command(address, &ambient).unwrap();
    let folder = locations.programs.parent().unwrap().join(FOLDER);
    assert_eq!(command.executable, server.executable());
    assert_eq!(
        command.arguments,
        [
            OsString::from("--host"),
            OsString::from("127.0.0.1"),
            OsString::from("--port"),
            OsString::from(address.port().to_string()),
            OsString::from("--models-preset"),
            folder.join(PRESET).into_os_string(),
            OsString::from("--models-max"),
            OsString::from("1"),
            OsString::from("--no-models-autoload"),
        ]
    );
    let environment = |name: &str| command.environment.get(OsStr::new(name)).cloned();
    // The address is the router's alone: the model instances it starts inherit its
    // environment and must not read it as theirs.
    assert!(
        command
            .environment
            .keys()
            .all(|name| !name.to_string_lossy().starts_with("LLAMA_ARG_")),
        "{:?}",
        command.environment
    );
    assert_eq!(
        environment("LLAMA_CACHE"),
        Some(folder.join("home").join("cache").into_os_string())
    );
    assert!(
        command
            .environment
            .keys()
            .all(|name| !name.to_string_lossy().starts_with("OLLAMA_")),
        "{:?}",
        command.environment
    );
    assert_eq!(command.working_directory, folder.join("home"));
    assert!(
        server
            .serve_command("192.0.2.1:23744".parse().unwrap(), &ambient)
            .is_err(),
        "only a loopback address is served"
    );
}

#[test]
fn each_program_is_waited_for_by_its_own_announcement() {
    let llama = [
        "0.00.280.393 I srv  server_on_li: listening on http://127.0.0.1:23744",
        "main: server is listening on http://127.0.0.1:23744 - starting the main loop",
    ];
    let ollama =
        "time=2026-11-07 level=INFO msg=\"Listening on 127.0.0.1:23743 (version 0.40.10)\"";
    for line in llama {
        assert!(announces(
            announcement(LocalEngine::LlamaCpp),
            line.as_bytes()
        ));
        assert!(!announces(
            announcement(LocalEngine::Ollama),
            line.as_bytes()
        ));
    }
    assert!(announces(
        announcement(LocalEngine::Ollama),
        ollama.as_bytes()
    ));
    assert!(!announces(
        announcement(LocalEngine::LlamaCpp),
        ollama.as_bytes()
    ));
}

#[test]
fn a_build_is_the_pinned_tag_alone_or_with_its_commit() {
    assert!(build_matches("b12184", "b12184"));
    assert!(build_matches("b12184-c0ab6e5c0", "b12184"));
    for other in [
        "b12185",
        "b121840",
        "b121840-c0ab6e5c0",
        "b1218",
        "",
        "12184",
    ] {
        assert!(!build_matches(other, "b12184"), "{other}");
    }
}

/// Waits until the helper's request log holds `line`.
fn logged(log: &Path, line: &str) {
    let deadline = Instant::now() + Duration::from_secs(30);
    while !fs::read_to_string(log).is_ok_and(|written| written.contains(line)) {
        assert!(Instant::now() < deadline, "the helper never logged {line}");
        std::thread::sleep(Duration::from_millis(20));
    }
}

#[test]
fn a_router_that_listens_is_waited_for_until_ready_and_then_its_build_is_confirmed() {
    let root = tempfile::tempdir().unwrap();
    let (mut server, locations) = packaged(root.path());
    let ready = root.path().join("ready");
    let log = root.path().join("requests.log");
    stand_in(
        &mut server,
        BUILD_INFO,
        &[
            (HELPER_READY_GATE, ready.as_os_str()),
            (HELPER_LOG, log.as_os_str()),
        ],
    );
    // The router answers 503 until the gate is there, which opens once it has been asked.
    let opener = {
        let (ready, log) = (ready.clone(), log.clone());
        std::thread::spawn(move || {
            logged(&log, "GET /health");
            fs::write(&ready, b"").unwrap();
        })
    };
    let address = free_address();
    server.serve(address, &Uncontained, &ambient, None).unwrap();
    opener.join().unwrap();

    let written = fs::read_to_string(&log).unwrap();
    let health = written.matches("GET /health").count();
    assert!(health >= 2, "asked while unready and once ready: {written}");
    assert!(
        written.find("GET /props").unwrap() > written.rfind("GET /health").unwrap(),
        "the build is asked once it is ready: {written}"
    );
    let folder = locations.programs.parent().unwrap().join(FOLDER);
    let record = ServerRecord::read(&folder).unwrap();
    assert_eq!(record.address, address.to_string());
    assert_eq!(record.version, BUILD);
    assert_eq!(record.models, locations.models);
    assert_eq!(record.proxy, None);
    assert!(folder.join(PRESET).is_file());
    // It was started on the address the engine gave it, on its command line.
    let (_, body) = Loopback::new(address)
        .unwrap()
        .get("/fake/arguments")
        .unwrap();
    let arguments: Vec<String> = serde_json::from_slice(&body).unwrap();
    let port = address.port().to_string();
    assert!(
        arguments
            .windows(2)
            .any(|pair| pair[0] == "--port" && pair[1] == port),
        "{arguments:?}"
    );
    let (_, body) = Loopback::new(address)
        .unwrap()
        .get("/fake/environment")
        .unwrap();
    let environment: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert!(environment.get("LLAMA_ARG_PORT").is_none(), "{environment}");

    server.halt();
    assert!(!answers(address));
    assert!(ServerRecord::read(&folder).is_none());
}

#[test]
fn a_router_of_another_build_is_ended_and_not_running() {
    let root = tempfile::tempdir().unwrap();
    let (mut server, locations) = packaged(root.path());
    stand_in(&mut server, "b99999-0000000", &[]);
    let address = free_address();
    let error = server
        .serve(address, &Uncontained, &ambient, None)
        .expect_err("another build is not the pinned one");
    assert!(
        matches!(
            &error,
            LocalAiError::NotRunning(NotRunningCause::Start(ServerStartFailure::Version(
                VersionFailure::Different { found }
            ))) if found == "b99999-0000000"
        ),
        "{error}"
    );
    assert_eq!(error.category(), FailureCategory::ProgramNotRunning);
    let folder = locations.programs.parent().unwrap().join(FOLDER);
    assert_eq!(
        latest_start_failure(&folder),
        Some(StartFailureKind::VersionUnconfirmed)
    );
    assert!(server.server().is_none());
    assert!(ServerRecord::read(&folder).is_none());
    assert!(!answers(address));
}

pub(crate) fn supervisor(
    server: LlamaServer,
    address: SocketAddr,
) -> ServerSupervisor<LlamaServer> {
    // A proxy setting the engine cannot use keeps no llama-server from running: it
    // downloads nothing.
    let environment = |name: &str| {
        if name == PROXY_URL {
            return Some(OsString::from("ftp://proxy.example:3128"));
        }
        ambient(name)
    };
    ServerSupervisor::new(
        server,
        address,
        Box::new(Uncontained),
        Box::new(environment),
    )
    .unwrap()
    .with_policy(RestartPolicy {
        initial_backoff: Duration::from_secs(1),
        maximum_backoff: Duration::from_secs(4),
        crash_loop_limit: 2,
        crash_loop_window: Duration::from_secs(60),
    })
}

fn assert_running(supervisor: &mut ServerSupervisor<LlamaServer>, now: Instant) {
    let state = supervisor.poll(now);
    assert_eq!(
        state,
        ServerState::Running,
        "the start failed with: {:?}",
        supervisor.last_start_failure().map(ToString::to_string)
    );
}

fn process_id(supervisor: &ServerSupervisor<LlamaServer>) -> Option<u32> {
    supervisor.program().server().and_then(Server::process_id)
}

#[test]
fn the_supervisor_restarts_a_crashed_router_on_its_address() {
    let root = tempfile::tempdir().unwrap();
    let (mut server, _) = packaged(root.path());
    stand_in(&mut server, BUILD_INFO, &[]);
    let address = free_address();
    let mut supervisor = supervisor(server, address);
    let start = Instant::now();
    assert_running(&mut supervisor, start);
    let first = process_id(&supervisor);

    let _ = Loopback::new(address).unwrap().post("/fake/exit", b"{}");
    supervisor
        .program_mut()
        .running_mut()
        .expect("a running server")
        .wait_exit();
    let due = start + Duration::from_secs(1);
    assert_eq!(supervisor.poll(start), ServerState::Restarting { at: due });
    assert!(!answers(address), "nothing restarts before its backoff");
    assert_running(&mut supervisor, due);
    assert!(answers(address));
    assert_ne!(process_id(&supervisor), first);

    drop(supervisor);
    assert!(!answers(address));
}

fn name(text: &str) -> ModelName {
    ModelName::parse(text).unwrap()
}

#[test]
fn a_model_new_in_the_store_restarts_an_idle_router_and_waits_for_a_held_one_to_be_let_go() {
    let root = tempfile::tempdir().unwrap();
    let (mut server, locations) = packaged(root.path());
    // The stand-in lists the models the store is about to present.
    stand_in(
        &mut server,
        BUILD_INFO,
        &[(HELPER_MODELS, OsStr::new("qwen3:1.7b,qwen3:4b"))],
    );
    let address = free_address();
    let mut supervisor = supervisor(server, address);
    let now = Instant::now();
    assert_running(&mut supervisor, now);
    let idle = process_id(&supervisor);
    let folder = server_folder(&locations).unwrap();
    let preset_file = folder.join(PRESET);
    assert_eq!(fs::read_to_string(&preset_file).unwrap(), "");
    let (small, large) = (name("qwen3:1.7b"), name("qwen3:4b"));
    assert_eq!(presentation(&folder, &small), Presentation::NotPresented);

    // Nothing changed: the same server keeps running.
    assert_running(&mut supervisor, now);
    assert_eq!(process_id(&supervisor), idle);

    // A model arrives while nothing is loaded: the router is started again with it.
    manifest(
        &locations.models,
        ["registry.ollama.ai", "library", "qwen3", "1.7b"],
        &[blob(&locations.models, MODEL_MEDIA_TYPE, b"text weights")],
    );
    // Until the next look the running router does not present it, and says so.
    assert_eq!(load(&folder, &small), Err(LoadRefused::NotPresented));
    assert_running(&mut supervisor, now);
    let restarted = process_id(&supervisor);
    assert_ne!(restarted, idle);
    assert!(
        fs::read_to_string(&preset_file)
            .unwrap()
            .starts_with(&format!(
                "[{}]\nalias = qwen3:1.7b\n",
                router_id("qwen3:1.7b")
            ))
    );
    assert_eq!(
        supervisor.next_due(),
        None,
        "a fresh start is no crash and schedules nothing"
    );
    assert_eq!(presentation(&folder, &small), Presentation::Presented);
    assert_eq!(load(&folder, &small), Ok(()));

    // Another arrives while the router holds a model: the model in use is never
    // unloaded for it, and the router drains, refusing every new load for a retry.
    manifest(
        &locations.models,
        ["registry.ollama.ai", "library", "qwen3", "4b"],
        &[blob(&locations.models, MODEL_MEDIA_TYPE, b"more weights")],
    );
    assert_running(&mut supervisor, now);
    assert_eq!(process_id(&supervisor), restarted);
    // The drain's marker is written at the first look; the looks after it leave it alone.
    let marker = folder.join(RESTARTING);
    fs::write(&marker, b"written once").unwrap();
    for _ in 0..3 {
        assert_running(&mut supervisor, now);
        assert_eq!(process_id(&supervisor), restarted);
    }
    assert_eq!(fs::read(&marker).unwrap(), b"written once");
    assert!(folder.join(RESTARTING).exists());
    assert_eq!(presentation(&folder, &large), Presentation::Restarting);
    assert_eq!(presentation(&folder, &small), Presentation::Restarting);
    let refused = load(&folder, &small).unwrap_err();
    assert_eq!(refused, LoadRefused::Restarting);
    assert!(refused.retryable());
    let router = supervisor.program().server().unwrap().loopback();
    let (_, body) = router.get("/models").unwrap();
    let models: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert!(
        models["data"]
            .as_array()
            .unwrap()
            .iter()
            .any(|model| model["id"] == "qwen3:1.7b" && model["status"]["value"] == "loaded"),
        "the held model stays loaded: {models}"
    );

    // Once its holder lets it go, the next look starts the router again with both.
    let (status, _) = router
        .post("/models/unload", br#"{"model":"qwen3:1.7b"}"#)
        .unwrap();
    assert_eq!(status, 200);
    assert_running(&mut supervisor, now);
    assert_ne!(process_id(&supervisor), restarted);
    assert!(!folder.join(RESTARTING).exists());
    assert_eq!(presentation(&folder, &large), Presentation::Presented);
    assert_eq!(load(&folder, &large), Ok(()));
}

/// A router answered from the test process, recorded in `folder` as the running server
/// of process `process_id`, presenting `models`.
fn recorded_router(folder: &Path, fake: &FakeLlamaCpp, process_id: u32, models: &[&str]) {
    fs::create_dir_all(folder).unwrap();
    filesystem::replace_json(
        &folder.join(SERVER_RECORD),
        &ServerRecord {
            schema: SERVER_RECORD_SCHEMA,
            address: fake.address().to_string(),
            version: BUILD.to_owned(),
            executable: folder.join(EXECUTABLE),
            models: folder.join("models"),
            process_id,
            proxy: None,
        },
    )
    .unwrap();
    let mut preset = String::new();
    let mut state = fake.state.lock().unwrap();
    for model in models {
        let _ = write!(
            preset,
            "[{}]\nalias = {model}\nmodel = /m\nctx-size = 8192\n\n",
            router_id(model)
        );
        state
            .models
            .insert((*model).to_owned(), ModelStatus::Unloaded);
    }
    fs::write(folder.join(PRESET), preset).unwrap();
}

#[test]
fn a_load_says_whether_it_stayed_and_a_restart_that_overtakes_it_is_retried_not_failed() {
    let root = tempfile::tempdir().unwrap();
    let folder = root.path().join(FOLDER);
    let model = name("qwen3:1.7b");
    assert_eq!(load(&folder, &model), Err(LoadRefused::NotRunning));
    assert_eq!(presentation(&folder, &model), Presentation::NotRunning);

    let fake = FakeLlamaCpp::start(BUILD_INFO);
    recorded_router(&folder, &fake, 7, &["qwen3:1.7b"]);
    let status = |fake: &FakeLlamaCpp| fake.state.lock().unwrap().models["qwen3:1.7b"];
    let loads = |fake: &FakeLlamaCpp| -> Vec<String> {
        fake.state
            .lock()
            .unwrap()
            .requests
            .iter()
            .filter(|line| line.starts_with("POST /models/"))
            .cloned()
            .collect()
    };
    assert_eq!(presentation(&folder, &model), Presentation::Presented);
    assert_eq!(
        load(&folder, &name("qwen3:4b")),
        Err(LoadRefused::NotPresented)
    );

    // A drain begun before the load: nothing is asked of the router.
    let marker = folder.join(RESTARTING);
    fs::write(&marker, b"").unwrap();
    assert_eq!(load(&folder, &model), Err(LoadRefused::Restarting));
    assert!(loads(&fake).is_empty());
    fs::remove_file(&marker).unwrap();

    // A drain begun while the load was on its way: the model it loaded is let go again,
    // so the restart is not kept waiting for it, and the caller retries.
    fake.state.lock().unwrap().on_load = Some(Box::new({
        let marker = marker.clone();
        move || fs::write(&marker, b"").unwrap()
    }));
    assert_eq!(load(&folder, &model), Err(LoadRefused::Restarting));
    assert_eq!(status(&fake), ModelStatus::Unloaded);
    assert_eq!(
        loads(&fake),
        ["POST /models/load HTTP/1.1", "POST /models/unload HTTP/1.1"]
    );
    fs::remove_file(&marker).unwrap();

    // Held before the load, it is another caller's: it is never unloaded.
    fake.state
        .lock()
        .unwrap()
        .models
        .insert("qwen3:1.7b".into(), ModelStatus::Loaded);
    assert_eq!(load(&folder, &model), Err(LoadRefused::Restarting));
    assert_eq!(status(&fake), ModelStatus::Loaded);
    assert_eq!(loads(&fake).len(), 3, "no unload: {:?}", loads(&fake));
    fs::remove_file(&marker).unwrap();

    // The router was started again under the load: another process is in the record.
    fake.state.lock().unwrap().on_load = Some(Box::new({
        let folder = folder.clone();
        move || {
            let mut record = ServerRecord::read(&folder).unwrap();
            record.process_id = 8;
            filesystem::replace_json(&folder.join(SERVER_RECORD), &record).unwrap();
        }
    }));
    assert_eq!(load(&folder, &model), Err(LoadRefused::Restarting));
    fake.state.lock().unwrap().on_load = None;

    // A router that refuses the load is a failure to report, not to retry.
    fake.state.lock().unwrap().failures.insert(
        "/models/load".into(),
        Scripted {
            status: "500 Internal Server Error".into(),
            body: json!({ "error": { "message": "out of memory" } }),
        },
    );
    let failed = load(&folder, &model).unwrap_err();
    assert_eq!(
        failed,
        LoadRefused::Failed {
            status: Some(500),
            out_of_memory: true
        }
    );
    assert!(!failed.retryable());
    fake.state.lock().unwrap().failures.clear();

    // Otherwise the load stays.
    fake.state
        .lock()
        .unwrap()
        .models
        .insert("qwen3:1.7b".into(), ModelStatus::Unloaded);
    assert_eq!(load(&folder, &model), Ok(()));
    assert_eq!(status(&fake), ModelStatus::Loaded);
    assert_eq!(presentation(&folder, &model), Presentation::Presented);
}

/// What one check of `model` on a router drained or not, in `folder`, came to.
fn check(folder: &Path, model: &ModelName, budget: Duration) -> Result<bool, LocalAiError> {
    check_model(folder, model, "Reply with one word.", budget)
}

#[test]
fn a_full_check_a_drain_overtakes_waits_for_the_restart_within_its_budget() {
    let root = tempfile::tempdir().unwrap();
    let folder = root.path().join(FOLDER);
    let fake = FakeLlamaCpp::start(BUILD_INFO);
    recorded_router(&folder, &fake, 7, &["qwen3:1.7b"]);
    let model = name("qwen3:1.7b");
    let marker = folder.join(RESTARTING);
    fs::write(&marker, b"").unwrap();
    let requests = |fake: &FakeLlamaCpp| fake.state.lock().unwrap().requests.len();

    // The drain ends while the check waits: it then loads, generates and unloads.
    let ended = {
        let marker = marker.clone();
        std::thread::spawn(move || {
            std::thread::sleep(Duration::from_millis(600));
            fs::remove_file(&marker).unwrap();
        })
    };
    let started = Instant::now();
    assert!(check(&folder, &model, Duration::from_secs(30)).unwrap());
    assert!(started.elapsed() >= Duration::from_millis(500));
    ended.join().unwrap();
    assert_eq!(
        fake.state.lock().unwrap().models["qwen3:1.7b"],
        ModelStatus::Unloaded
    );

    // A drain that outlasts the budget ends the wait there, asking the router nothing.
    fs::write(&marker, b"").unwrap();
    let asked = requests(&fake);
    let started = Instant::now();
    let refused = check(&folder, &model, Duration::from_millis(600)).unwrap_err();
    assert!(
        matches!(
            refused,
            LocalAiError::Failed(FailureCategory::ProgramNotRunning)
        ),
        "{refused:?}"
    );
    assert!(started.elapsed() >= Duration::from_millis(600));
    assert!(started.elapsed() < Duration::from_secs(10));
    assert_eq!(requests(&fake), asked);
}

#[test]
fn a_load_refused_for_memory_reads_not_enough_memory_and_any_other_refusal_unexpected() {
    let root = tempfile::tempdir().unwrap();
    let folder = root.path().join(FOLDER);
    let fake = FakeLlamaCpp::start(BUILD_INFO);
    recorded_router(&folder, &fake, 7, &["qwen3:1.7b"]);
    let model = name("qwen3:1.7b");
    let refuse = |body: serde_json::Value| {
        fake.state.lock().unwrap().failures.insert(
            "/models/load".into(),
            Scripted {
                status: "500 Internal Server Error".into(),
                body,
            },
        );
    };
    let category = |result: Result<bool, LocalAiError>| match result {
        Err(LocalAiError::Failed(category)) => category,
        other => panic!("expected a failure, got {other:?}"),
    };

    refuse(json!({ "error": { "message": "failed to allocate memory for the model" } }));
    assert_eq!(
        load(&folder, &model),
        Err(LoadRefused::Failed {
            status: Some(500),
            out_of_memory: true
        })
    );
    assert_eq!(
        category(check(&folder, &model, Duration::from_secs(5))),
        FailureCategory::NotEnoughMemory
    );
    refuse(json!({ "error": "Out of MEMORY" }));
    assert_eq!(
        category(check(&folder, &model, Duration::from_secs(5))),
        FailureCategory::NotEnoughMemory
    );

    refuse(json!({ "error": { "message": "failed to load model" } }));
    assert_eq!(
        load(&folder, &model),
        Err(LoadRefused::Failed {
            status: Some(500),
            out_of_memory: false
        })
    );
    assert_eq!(
        category(check(&folder, &model, Duration::from_secs(5))),
        FailureCategory::Unexpected
    );
    refuse(json!("no JSON error at all"));
    assert_eq!(
        category(check(&folder, &model, Duration::from_secs(5))),
        FailureCategory::Unexpected
    );
}
