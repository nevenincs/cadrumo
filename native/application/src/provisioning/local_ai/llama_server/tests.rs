use super::*;
use crate::{
    provisioning::{
        local_ai::{
            ServerStartFailure, StartFailureKind, VersionFailure,
            fake_llamacpp::{
                HELPER_ARGUMENTS, HELPER_BUILD, HELPER_LOG, HELPER_MODE, HELPER_MODELS,
                HELPER_READY_GATE,
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
fn package(root: &Path) -> PathBuf {
    let folder = root.join("package").join("bin").join("llama");
    fs::create_dir_all(&folder).unwrap();
    fs::copy(std::env::current_exe().unwrap(), folder.join(EXECUTABLE)).unwrap();
    folder
}

fn packaged(root: &Path) -> (LlamaServer, Locations) {
    let locations = Locations::under(&root.join("storage"));
    let server = LlamaServer::packaged(&package(root), BUILD, &locations, LOAD_CONTEXT).unwrap();
    (server, locations)
}

/// Runs the fake router in the program's place, reporting `build_info` and adding
/// `environment`.
fn stand_in(server: &mut LlamaServer, build_info: &str, environment: &[(&str, &OsStr)]) {
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
fn blob(models: &Path, media_type: &str, bytes: &[u8]) -> serde_json::Value {
    let digest = Sha256Digest::of(bytes);
    let blobs = models.join("blobs");
    fs::create_dir_all(&blobs).unwrap();
    fs::write(blobs.join(format!("sha256-{digest}")), bytes).unwrap();
    json!({ "mediaType": media_type, "digest": format!("sha256:{digest}"), "size": bytes.len() })
}

/// Writes a manifest naming `layers` under `host/namespace/model/tag`.
fn manifest(models: &Path, path: [&str; 4], layers: &[serde_json::Value]) {
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

    let expected = format!(
        "[huggingface.co/Owner/Model-GGUF:Model-Q4_K_M]\nmodel = {}\nmmproj = {}\nctx-size = 4096\n\n\
         [qwen3-vl:4b-instruct]\nmodel = {}\nmmproj = {}\nctx-size = 4096\n\n\
         [qwen3:1.7b]\nmodel = {}\nctx-size = 4096\n\n",
        value_of(&models, b"hf weights"),
        value_of(&models, b"hf projector"),
        value_of(&models, b"vision weights"),
        value_of(&models, b"vision projector"),
        value_of(&models, b"text weights"),
    );
    assert_eq!(preset(&models, 4096), expected);
    assert_eq!(preset(&root.path().join("no-store"), 4096), "");
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
            OsString::from("--models-preset"),
            folder.join(PRESET).into_os_string(),
            OsString::from("--models-max"),
            OsString::from("1"),
            OsString::from("--no-models-autoload"),
        ]
    );
    let environment = |name: &str| command.environment.get(OsStr::new(name)).cloned();
    assert_eq!(
        environment("LLAMA_ARG_HOST"),
        Some(OsString::from("127.0.0.1"))
    );
    assert_eq!(
        environment("LLAMA_ARG_PORT"),
        Some(OsString::from(address.port().to_string()))
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
    // It was started on the address the engine gave it.
    let (_, body) = Loopback::new(address)
        .unwrap()
        .get("/fake/environment")
        .unwrap();
    let environment: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert_eq!(environment["LLAMA_ARG_PORT"], address.port().to_string());

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

fn supervisor(server: LlamaServer, address: SocketAddr) -> ServerSupervisor<LlamaServer> {
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

#[test]
fn a_model_new_in_the_store_restarts_an_idle_router_and_never_one_that_holds_a_model() {
    let root = tempfile::tempdir().unwrap();
    let (mut server, locations) = packaged(root.path());
    // The stand-in lists the model the store is about to present.
    stand_in(
        &mut server,
        BUILD_INFO,
        &[(HELPER_MODELS, OsStr::new("qwen3:1.7b"))],
    );
    let address = free_address();
    let mut supervisor = supervisor(server, address);
    let now = Instant::now();
    assert_running(&mut supervisor, now);
    let idle = process_id(&supervisor);
    let preset_file = locations
        .programs
        .parent()
        .unwrap()
        .join(FOLDER)
        .join(PRESET);
    assert_eq!(fs::read_to_string(&preset_file).unwrap(), "");

    // Nothing changed: the same server keeps running.
    assert_running(&mut supervisor, now);
    assert_eq!(process_id(&supervisor), idle);

    // A model arrives while nothing is loaded: the router is started again with it.
    manifest(
        &locations.models,
        ["registry.ollama.ai", "library", "qwen3", "1.7b"],
        &[blob(&locations.models, MODEL_MEDIA_TYPE, b"text weights")],
    );
    assert_running(&mut supervisor, now);
    let restarted = process_id(&supervisor);
    assert_ne!(restarted, idle);
    assert!(
        fs::read_to_string(&preset_file)
            .unwrap()
            .starts_with("[qwen3:1.7b]\n")
    );
    assert_eq!(
        supervisor.next_due(),
        None,
        "a fresh start is no crash and schedules nothing"
    );

    // Another arrives while the router holds a model: it keeps running as it is.
    let router = supervisor.program().server().unwrap().loopback();
    let (status, _) = router
        .post("/models/load", br#"{"model":"qwen3:1.7b"}"#)
        .unwrap();
    assert_eq!(status, 200);
    manifest(
        &locations.models,
        ["registry.ollama.ai", "library", "qwen3", "4b"],
        &[blob(&locations.models, MODEL_MEDIA_TYPE, b"more weights")],
    );
    assert_running(&mut supervisor, now);
    assert_eq!(process_id(&supervisor), restarted);
}
