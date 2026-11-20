use super::*;

const PROFILE_A: &str = "11111111-1111-4111-8111-111111111111";
const PROFILE_B: &str = "22222222-2222-4222-8222-222222222222";
const JOB_1: &str = "1111111111111111111111111111111111111111111111111111111111111111";
const JOB_2: &str = "2222222222222222222222222222222222222222222222222222222222222222";

fn read(profile: &str, jobs: &[(&str, u64)]) -> BackgroundTaskRevisions {
    BackgroundTaskRevisions {
        profile_id: profile.to_owned(),
        tasks: jobs
            .iter()
            .map(|(job, revision)| BackgroundTaskRevision {
                family: BackgroundTaskFamily::LedgerClassification,
                job_id: Some((*job).to_owned()),
                revision: *revision,
            })
            .collect(),
    }
}
fn cued(cues: &[BackgroundTaskCue]) -> Vec<(&str, &str, u64)> {
    cues.iter()
        .map(|cue| {
            (
                cue.profile_id.as_str(),
                cue.job_id.as_deref().unwrap(),
                cue.revision,
            )
        })
        .collect()
}

#[test]
fn a_cue_is_sent_only_when_a_jobs_revision_rises() {
    let mut gate = Gate::default();
    // A job the gate has not read is new to it.
    assert_eq!(
        cued(&gate.advanced(&read(PROFILE_A, &[(JOB_1, 3)]))),
        [(PROFILE_A, JOB_1, 3)]
    );
    // The same revision, read again, is no change.
    assert!(gate.advanced(&read(PROFILE_A, &[(JOB_1, 3)])).is_empty());
    // An older revision, from a read that started before a newer one, is none either.
    assert!(gate.advanced(&read(PROFILE_A, &[(JOB_1, 2)])).is_empty());
    // A rise is cued, and only the job that rose.
    assert_eq!(
        cued(&gate.advanced(&read(PROFILE_A, &[(JOB_1, 4), (JOB_2, 1)]))),
        [(PROFILE_A, JOB_1, 4), (PROFILE_A, JOB_2, 1)]
    );
    assert_eq!(
        cued(&gate.advanced(&read(PROFILE_A, &[(JOB_1, 4), (JOB_2, 2)]))),
        [(PROFILE_A, JOB_2, 2)]
    );
    // The older read did not lower what the gate holds.
    assert!(gate.advanced(&read(PROFILE_A, &[(JOB_1, 3)])).is_empty());
}

#[test]
fn another_profile_or_an_ended_session_starts_the_gate_again() {
    let mut gate = Gate::default();
    gate.advanced(&read(PROFILE_A, &[(JOB_1, 5)]));
    // Another profile's job of the same identity is that profile's own.
    assert_eq!(
        cued(&gate.advanced(&read(PROFILE_B, &[(JOB_1, 1)]))),
        [(PROFILE_B, JOB_1, 1)]
    );
    assert_eq!(
        cued(&gate.advanced(&read(PROFILE_A, &[(JOB_1, 5)]))),
        [(PROFILE_A, JOB_1, 5)]
    );
    gate.reset();
    assert!(gate.current().is_empty());
    assert_eq!(
        cued(&gate.advanced(&read(PROFILE_A, &[(JOB_1, 5)]))),
        [(PROFILE_A, JOB_1, 5)]
    );
}

#[test]
fn a_subscriber_that_missed_cues_is_sent_every_revision_held() {
    let mut gate = Gate::default();
    gate.advanced(&read(PROFILE_A, &[(JOB_2, 7), (JOB_1, 2)]));
    assert_eq!(
        cued(&gate.current()),
        [(PROFILE_A, JOB_1, 2), (PROFILE_A, JOB_2, 7)]
    );
}

#[test]
fn a_cue_is_typed_and_carries_only_its_family_profile_job_and_revision() {
    let cue = BackgroundTaskCue {
        family: BackgroundTaskFamily::LedgerClassification,
        profile_id: PROFILE_A.into(),
        job_id: Some(JOB_1.into()),
        revision: 9,
    };
    assert_eq!(
        serde_json::to_value(&cue).unwrap(),
        json!({"family":"ledger_classification","profile_id":PROFILE_A,"job_id":JOB_1,"revision":9})
    );
    // A family without a job per record leaves the job out.
    let whole = BackgroundTaskCue {
        job_id: None,
        ..cue.clone()
    };
    assert_eq!(
        serde_json::to_value(&whole).unwrap(),
        json!({"family":"ledger_classification","profile_id":PROFILE_A,"revision":9})
    );
    // The window's channel receives the same document.
    let received = Arc::new(Mutex::new(Vec::new()));
    let kept = received.clone();
    let channel = Channel::<BackgroundTaskCue>::new(move |body| {
        if let tauri::ipc::InvokeResponseBody::Json(text) = body {
            lock(&kept).push(serde_json::from_str::<Value>(&text).unwrap());
        }
        Ok(())
    });
    channel.send(cue).unwrap();
    assert_eq!(
        *lock(&received),
        [
            json!({"family":"ledger_classification","profile_id":PROFILE_A,"job_id":JOB_1,"revision":9})
        ]
    );
}

#[test]
fn the_classification_read_answers_each_listed_jobs_revision_for_its_profile_only() {
    let family = BackgroundTaskFamily::LedgerClassification;
    let projection = json!({"profile_id":PROFILE_A,"queue_revision":JOB_2,"more":false,
        "jobs":[{"job_id":JOB_1,"revision":4,"status":"running"},
                {"job_id":JOB_2,"revision":1,"status":"dismissed"}]});
    assert_eq!(
        family.revisions(&projection, PROFILE_A).unwrap(),
        read(PROFILE_A, &[(JOB_1, 4), (JOB_2, 1)]).tasks
    );
    assert!(family.revisions(&projection, PROFILE_B).is_err());
    for refused in [
        json!({"profile_id":PROFILE_A}),
        json!({"profile_id":PROFILE_A,"jobs":[{"job_id":"j1","revision":1}]}),
        json!({"profile_id":PROFILE_A,"jobs":[{"job_id":JOB_1,"revision":0}]}),
        json!({"profile_id":PROFILE_A,"jobs":[{"job_id":JOB_1,"revision":"4"}]}),
    ] {
        assert!(family.revisions(&refused, PROFILE_A).is_err(), "{refused}");
    }
    assert_eq!(
        family.read_payload(PROFILE_A),
        json!({"profile_id":PROFILE_A,"limit":50,"include_dismissed":true})
    );
}

#[test]
fn each_familys_read_is_a_read_of_the_shipped_ledger_family_about_the_profile() {
    let contracts: Value =
        serde_json::from_str(include_str!("../ledger/relay_contracts.json")).unwrap();
    for family in BackgroundTaskFamily::ALL {
        let facts = &contracts["operations"][family.read_definition()];
        assert_eq!(facts["may_write"], false, "{family:?}");
        assert_eq!(facts["review"], false, "{family:?}");
        assert_eq!(
            facts["subject"],
            json!({"kind":"profile","path":[]}),
            "{family:?}"
        );
    }
}

#[test]
fn records_changed_wakes_one_read_however_many_arrive_together() {
    let (sender, mut events) = tokio::sync::broadcast::channel(4);
    assert_eq!(wake_of(Ok(PersonEvent::OperationChanged)), None);
    assert_eq!(wake_of(Ok(PersonEvent::LanguageChanged)), None);
    for _ in 0..3 {
        sender.send(PersonEvent::RecordsChanged).unwrap();
    }
    sender.send(PersonEvent::OperationChanged).unwrap();
    let first = wake_of(Ok(PersonEvent::RecordsChanged)).unwrap();
    assert_eq!(
        coalesced(first, &mut events),
        Wakes {
            read: true,
            ..Wakes::default()
        }
    );
    assert!(events.try_recv().is_err(), "the burst was taken whole");
    // An ended session clears what the gate read; a change after it still reads.
    sender.send(PersonEvent::RecordsChanged).unwrap();
    assert_eq!(
        coalesced(Wake::Reset, &mut events),
        Wakes {
            reset: true,
            read: true,
            end: false
        }
    );
    // Missed events are a reason to read.
    for _ in 0..6 {
        sender.send(PersonEvent::OperationChanged).unwrap();
    }
    assert_eq!(
        coalesced(Wake::Read, &mut events),
        Wakes {
            read: true,
            ..Wakes::default()
        }
    );
    drop(sender);
    assert_eq!(wake_of(Err(RecvError::Closed)), Some(Wake::End));
    assert!(coalesced(Wake::Read, &mut events).end);
}

fn tasks() -> BackgroundTasks {
    BackgroundTasks::new(Arc::new(ProfileHost::new(Arc::new(
        super::super::sign_in::SignIn::new(&crate::terminal::tests::unit_launch()),
    ))))
}

#[test]
fn a_subscribe_read_cues_every_subscriber_about_a_newer_revision_it_finds() {
    let tasks = tasks();
    let mut first = tasks.cues.subscribe();
    let mut second = tasks.cues.subscribe();
    tasks.publish(&read(PROFILE_A, &[(JOB_1, 2)]));
    for subscriber in [&mut first, &mut second] {
        let cue = subscriber.try_recv().unwrap();
        assert_eq!(cued(&[cue]), [(PROFILE_A, JOB_1, 2)]);
        assert!(subscriber.try_recv().is_err());
    }
    // A later read of the same revision, by the watcher or another window, cues nothing.
    tasks.publish(&read(PROFILE_A, &[(JOB_1, 2)]));
    assert!(first.try_recv().is_err());
    // Closing forgets what was read.
    tasks.close();
    assert!(lock(&tasks.gate).current().is_empty());
}

/// The schema the window's generated types are written from.
const SCHEMA_FILE: &str = include_str!("../background_tasks.schema.json");

/// Where a refreshed schema is written, when set to an absolute path.
const WRITE_TO: &str = "CADRUMO_BACKGROUND_TASKS_SCHEMA_OUT";

fn schema() -> String {
    let mut generator = schemars::generate::SchemaSettings::draft2020_12()
        .for_serialize()
        .into_generator();
    generator.subschema_for::<BackgroundTaskCue>();
    generator.subschema_for::<BackgroundTaskRevisions>();
    let definitions = generator.take_definitions(true);
    let document = json!({
        "roots": ["BackgroundTaskCue", "BackgroundTaskRevisions"],
        "$defs": definitions,
    });
    serde_json::to_string_pretty(&document).unwrap() + "\n"
}

#[test]
fn the_background_tasks_schema_file_is_current() {
    let fresh = schema();
    if let Some(target) = std::env::var_os(WRITE_TO) {
        let target = std::path::PathBuf::from(target);
        assert!(target.is_absolute(), "{WRITE_TO} must be an absolute path");
        std::fs::write(&target, &fresh).unwrap();
    }
    assert!(
        SCHEMA_FILE.replace("\r\n", "\n") == fresh,
        "src/shell/background_tasks.schema.json is stale: run this test with {WRITE_TO} set to its absolute path"
    );
}

#[cfg(windows)]
mod relayed {
    use super::super::super::scripted::{OPERATION, PROFILE, holder, observed, resulted, step};
    use super::*;

    const LIST: &str = "ledger.classify.job.list";

    fn subject() -> String {
        relay::subject(PROFILE)
    }
    fn submitted() -> Value {
        step(
            "operation_submit",
            json!([
                ["definition_id", LIST],
                ["subject_ref", subject()],
                ["payload.profile_id", PROFILE],
                ["payload.limit", 50],
                ["payload.include_dismissed", true]
            ]),
            json!({"kind":"operation_submitted","operation_id":OPERATION}),
            false,
        )
    }

    #[tokio::test]
    async fn the_revision_read_lists_the_profiles_jobs_and_answers_their_revisions() {
        let held = holder(|_| {
            vec![
                submitted(),
                step(
                    "operation_observe",
                    json!([["operation_id", OPERATION]]),
                    observed(
                        LIST,
                        &subject(),
                        "terminal",
                        json!({"terminal_condition":"succeeded","revision":2}),
                    ),
                    false,
                ),
                step(
                    "operation_result",
                    json!([["operation_id", OPERATION]]),
                    resulted(
                        LIST,
                        json!({"profile_id":PROFILE,"queue_revision":JOB_2,"more":false,
                            "jobs":[{"job_id":JOB_1,"revision":6},{"job_id":JOB_2,"revision":2}]}),
                    ),
                    false,
                ),
            ]
        });
        let serial = tokio::sync::Mutex::new(());
        let revisions = read_on(
            &serial,
            &held.person,
            PROFILE,
            BackgroundTaskFamily::LedgerClassification,
            held.events.subscribe(),
        )
        .await
        .unwrap();
        assert_eq!(revisions, read(PROFILE, &[(JOB_1, 6), (JOB_2, 2)]).tasks);
        assert!(serial.try_lock().is_ok());
    }

    #[tokio::test]
    async fn a_refused_revision_read_answers_no_revision() {
        let held = holder(|_| {
            vec![
                submitted(),
                step(
                    "operation_observe",
                    json!([["operation_id", OPERATION]]),
                    observed(
                        LIST,
                        &subject(),
                        "terminal",
                        json!({"terminal_condition":"refused","refusal_ref":"not_ready","revision":2}),
                    ),
                    false,
                ),
            ]
        });
        let serial = tokio::sync::Mutex::new(());
        let refused = read_on(
            &serial,
            &held.person,
            PROFILE,
            BackgroundTaskFamily::LedgerClassification,
            held.events.subscribe(),
        )
        .await
        .unwrap_err();
        assert_eq!(refused.code, "refused");
    }
}
