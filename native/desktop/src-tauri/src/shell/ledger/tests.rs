use super::*;

fn definition(id: &str) -> Definition {
    admitted(id).unwrap()
}
fn object(value: Value) -> Map<String, Value> {
    value.as_object().unwrap().clone()
}

#[test]
fn the_window_names_no_profile_directory_path_or_account_secret() {
    for (id, payload) in [
        ("ledger.list", json!({"profile_id":"another"})),
        ("ledger.evidence.add", json!({"source_directory":"C:\\"})),
        (
            "ledger.import",
            json!({"files":["C:\\statement.csv"],"provider":"auto"}),
        ),
        ("ledger.import", json!({"verify_source":"C:\\x.csv"})),
        ("ledger.export", json!({"output_path":"C:\\out.csv"})),
        (
            "ledger.invoice.import",
            json!({"source_path":"C:\\book.xlsx","kind":"RECEIVED"}),
        ),
        (
            "ledger.evidence.batch",
            json!({"sources":["C:\\a.pdf"],"direction":"RECEIVED"}),
        ),
        (
            "ledger.own_account",
            json!({"action":"update","own_account_id":"acc-01","iban":"ES00"}),
        ),
        (
            "ledger.own_account",
            json!({"action":"add","bank_name":"x"}),
        ),
    ] {
        assert_eq!(
            admit_fields(definition(id), &object(payload.clone()))
                .unwrap_err()
                .code,
            "invalid",
            "{id} {payload}"
        );
    }
    for (id, payload) in [
        ("ledger.list", json!({"filters":[],"limit":200})),
        ("ledger.own_account", json!({"action":"list"})),
        (
            "ledger.own_account",
            json!({"action":"update","own_account_id":"acc-01","label":"Main"}),
        ),
        // Only the definition that reads a path owns its path field.
        (
            "ledger.update",
            json!({"transaction_id":"t","source_path":"kept for the contract"}),
        ),
    ] {
        assert!(admit_fields(definition(id), &object(payload)).is_ok());
    }
}

#[test]
fn a_request_the_relay_cannot_take_is_refused_before_it_is_written() {
    let request = |payload: Value| {
        json!({"action":"operation_submit", "definition_id":"ledger.classify.bulk",
            "subject_ref":"profile:00000000-0000-4000-8000-000000000000", "payload":payload})
    };
    let near = "a".repeat(PAYLOAD_LIMIT - r#"{"csv_text":""}"#.len());
    assert!(admit_size(&request(json!({ "csv_text": near }))).is_ok());
    let over = format!("{near}a");
    assert_eq!(
        admit_size(&request(json!({ "csv_text": over })))
            .unwrap_err()
            .code,
        "too_large"
    );
    // Within the payload's characters, but not within the line's bytes.
    let wide = "\u{20ac}".repeat(6_000);
    assert_eq!(
        admit_size(&request(json!({ "csv_text": wide })))
            .unwrap_err()
            .code,
        "too_large"
    );
}

fn projection(lifecycle: &str) -> Value {
    json!({"lifecycle":lifecycle, "terminal_condition":null, "effect":"none",
        "refusal_ref":null, "failure_error_code":null, "revision":3, "cancellable_now":false,
        "pending_interaction":{"disposition":"none"}})
}

#[test]
fn only_a_settled_no_effect_stop_is_a_refusal_and_any_other_effect_is_unknown() {
    let mut p = projection("terminal");
    p["terminal_condition"] = json!("succeeded");
    p["effect"] = json!("updated");
    assert_eq!(phase(&p), Phase::Succeeded);
    p["terminal_condition"] = json!("refused");
    p["effect"] = json!("none");
    p["refusal_ref"] = json!("REFUSED_CLI_VALIDATION_BOUNDARY");
    assert_eq!(
        phase(&p),
        Phase::Stopped(Some("REFUSED_CLI_VALIDATION_BOUNDARY".into()))
    );
    p["terminal_condition"] = json!("failed");
    p["refusal_ref"] = Value::Null;
    p["failure_error_code"] = json!("FAIL_LEDGER_SEALED");
    assert_eq!(phase(&p), Phase::Stopped(Some("FAIL_LEDGER_SEALED".into())));
    for effect in ["unknown", "partial", "updated"] {
        p["effect"] = json!(effect);
        assert_eq!(phase(&p), Phase::Unknown, "{effect}");
    }
    let mut paused = projection("running");
    assert_eq!(phase(&paused), Phase::Running);
    assert!(!waits_on_person(&paused));
    paused["pending_interaction"] = json!({"disposition":"review_available"});
    assert_eq!(phase(&paused), Phase::Review);
    assert!(waits_on_person(&paused));
    paused["pending_interaction"] = json!({"disposition":"unsupported"});
    assert_eq!(phase(&paused), Phase::Running);
    assert!(waits_on_person(&paused));
}

#[test]
fn a_window_follows_only_its_own_sessions_operations() {
    let operations = Operations::default();
    let tracked = |operation: &str, session: &str| Tracked {
        operation: operation.into(),
        definition: definition("ledger.list"),
        subject: "profile:p".into(),
        identity: json!({"profile_id":"p","session_id":session}),
        shown: None,
    };
    operations.track(tracked("a", "one"));
    assert!(operations.find("a").is_ok());
    assert_eq!(operations.find("b").unwrap_err().code, "not_admitted");
    operations.track(tracked("b", "two"));
    assert!(
        operations.find("a").is_err(),
        "a new session forgets the last"
    );
    for at in 0..TRACKED_LIMIT {
        operations.track(tracked(&format!("n{at}"), "two"));
    }
    assert!(
        operations.find("b").is_err(),
        "the oldest is forgotten first"
    );
    assert!(operations.find(&format!("n{}", TRACKED_LIMIT - 1)).is_ok());
    operations.clear();
    assert!(operations.find("n0").is_err());
}

#[test]
fn outcomes_and_reviews_reach_the_window_in_the_contracts_shape() {
    let settled = Outcome::Settled {
        operation_id: "op".into(),
        revision: 4,
        result: json!({"rows":[]}),
    };
    assert_eq!(
        serde_json::to_value(&settled).unwrap(),
        json!({"kind":"settled","operation_id":"op","revision":4,"result":{"rows":[]}})
    );
    let review = Outcome::Review {
        operation_id: "op".into(),
        revision: 2,
        cancellable: false,
    };
    assert_eq!(serde_json::to_value(&review).unwrap()["kind"], "review");
    let mut failure = Failure::new("refused");
    assert_eq!(
        serde_json::to_value(&failure).unwrap(),
        json!({"code":"refused","operation_id":null}),
        "a failure without a reason keeps the profile pages' shape"
    );
    failure.reason = Some("subject_busy".into());
    assert_eq!(
        serde_json::to_value(&failure).unwrap()["reason"],
        "subject_busy"
    );
    assert_eq!(
        review_refusal(&json!({"kind":"operation_refused","code":"not_pending"})).code,
        "review_changed"
    );
    assert_eq!(
        review_refusal(&json!({"kind":"operation_refused","code":"unavailable"})).code,
        "refused"
    );
}

/// A stand-in for the session hold: it answers each request with the next
/// scripted reply, after checking the request's action and named fields,
/// and stops at anything else. A step may first push an operation change.
#[cfg(windows)]
mod relayed {
    use super::*;
    use crate::agent::person::{Person, request_id};
    use std::time::Duration;

    const PROFILE: &str = "11111111-1111-4111-8111-111111111111";
    const OPERATION: &str = "abababababababababababababababababababababababababababababababab";

    struct Holder {
        person: HeldPerson,
        identity: Value,
        events: tokio::sync::broadcast::Sender<PersonEvent>,
    }

    fn step(action: &str, expect: Value, reply: Value, push: bool) -> Value {
        json!({"action":action, "expect":expect, "reply":reply, "push":push})
    }

    fn holder(steps: impl Fn(&Value) -> Vec<Value>) -> Holder {
        let identity = json!({
            "kind": "session_held",
            "profile_id": PROFILE,
            "session_id": request_id().unwrap(),
            "runtime_boot_id": request_id().unwrap(),
            "connection_id": request_id().unwrap(),
        });
        let mut all = vec![step(
            "observe_events",
            json!([]),
            json!({"kind":"events_observed", "runtime_boot_id":identity["runtime_boot_id"],
                "connection_id":identity["connection_id"]}),
            false,
        )];
        for mut scripted in steps(&identity) {
            for key in [
                "profile_id",
                "session_id",
                "runtime_boot_id",
                "connection_id",
            ] {
                scripted["reply"][key] = identity[key].clone();
            }
            all.push(scripted);
        }
        let script = String::from("& { [Console]::Out.WriteLine('")
            + &identity.to_string()
            + "'); [Console]::Out.Flush(); $steps = '"
            + &Value::Array(all).to_string().replace('\'', "''")
            + "' | ConvertFrom-Json; $i = 0; \
               while (($line = [Console]::In.ReadLine()) -ne $null) { \
                 $request = $line | ConvertFrom-Json; \
                 if ($i -ge $steps.Count) { exit 7 }; \
                 $step = $steps[$i]; $i++; \
                 if ($request.action -ne $step.action) { exit 7 }; \
                 foreach ($pair in $step.expect) { \
                   $value = $request; \
                   foreach ($key in $pair[0].Split('.')) { $value = $value.$key }; \
                   if ([string]$value -ne [string]$pair[1]) { exit 8 } }; \
                 if ($step.push) { [Console]::Out.WriteLine('{\"kind\":\"runtime_event\",\"event\":\"operation_changed\"}') }; \
                 $reply = $step.reply; \
                 $reply | Add-Member -NotePropertyName request_id -NotePropertyValue $request.request_id -Force; \
                 [Console]::Out.WriteLine(($reply | ConvertTo-Json -Compress -Depth 20)); \
                 [Console]::Out.Flush(); \
               } }";
        let mut person = Person::hold_answering_within(
            crate::agent::runner::tests::powershell(&script),
            PROFILE,
            Duration::from_secs(60),
        )
        .unwrap();
        let (events, _) = tokio::sync::broadcast::channel(16);
        person.observe_events(events.clone()).unwrap();
        Holder {
            person: Arc::new(Mutex::new(person)),
            identity,
            events,
        }
    }

    fn observed(definition: &str, lifecycle: &str, extra: Value) -> Value {
        let mut p = json!({"operation_id":OPERATION, "definition_id":definition,
            "subject_ref":format!("profile:{PROFILE}"), "lifecycle":lifecycle,
            "terminal_condition":null, "effect":"none", "refusal_ref":null,
            "failure_error_code":null, "revision":1, "cancellable_now":false,
            "pending_interaction":{"disposition":"none"}});
        for (key, value) in extra.as_object().unwrap() {
            p[key] = value.clone();
        }
        json!({"kind":"operation_observed", "observation":{"projection":p}})
    }

    #[tokio::test]
    async fn a_read_is_submitted_for_the_held_profile_and_settles_to_its_result() {
        let held = holder(|_| {
            vec![
                step(
                    "operation_submit",
                    json!([
                        ["definition_id", "ledger.list"],
                        ["subject_ref", format!("profile:{PROFILE}")],
                        ["payload.profile_id", PROFILE],
                        ["payload.limit", 200]
                    ]),
                    json!({"kind":"operation_submitted","operation_id":OPERATION}),
                    false,
                ),
                step(
                    "operation_observe",
                    json!([["operation_id", OPERATION]]),
                    observed("ledger.list", "running", json!({})),
                    true,
                ),
                step(
                    "operation_observe",
                    json!([]),
                    observed(
                        "ledger.list",
                        "terminal",
                        json!({"terminal_condition":"succeeded","revision":2}),
                    ),
                    false,
                ),
                step(
                    "operation_result",
                    json!([["operation_id", OPERATION]]),
                    json!({"kind":"operation_result","operation_id":OPERATION,"definition_id":"ledger.list",
                        "document":{"projection":{"rows":[{"transaction_id":"t1"}]}}}),
                    false,
                ),
            ]
        });
        let operations = Operations::default();
        let mut events = held.events.subscribe();
        let outcome = submit_on(
            &operations,
            &held.person,
            &mut events,
            definition("ledger.list"),
            object(json!({"limit":200})),
        )
        .await
        .unwrap();
        assert_eq!(
            outcome,
            Outcome::Settled {
                operation_id: OPERATION.into(),
                revision: 2,
                result: json!({"rows":[{"transaction_id":"t1"}]}),
            }
        );
        let tracked = operations.find(OPERATION).unwrap();
        assert_eq!(tracked.identity, held.identity);
    }

    #[tokio::test]
    async fn a_settled_refusal_carries_its_code_and_declared_detail() {
        let detail = json!({"detail_version":1,"kind":"registered_error",
            "error_code":"REFUSED_CLI_VALIDATION_BOUNDARY","context":[]});
        let held = holder(|_| {
            vec![
                step(
                    "operation_submit",
                    json!([]),
                    json!({"kind":"operation_submitted","operation_id":OPERATION}),
                    false,
                ),
                step(
                    "operation_observe",
                    json!([]),
                    observed(
                        "ledger.update",
                        "terminal",
                        json!({"terminal_condition":"refused",
                        "refusal_ref":"REFUSED_CLI_VALIDATION_BOUNDARY"}),
                    ),
                    false,
                ),
                step(
                    "operation_result",
                    json!([]),
                    json!({"kind":"operation_result","operation_id":OPERATION,"definition_id":"ledger.update",
                        "document":{"projection":detail}}),
                    false,
                ),
            ]
        });
        let operations = Operations::default();
        let mut events = held.events.subscribe();
        let outcome = submit_on(
            &operations,
            &held.person,
            &mut events,
            definition("ledger.update"),
            object(json!({"transaction_id":"t1","patch":{}})),
        )
        .await
        .unwrap();
        assert_eq!(
            outcome,
            Outcome::Refused {
                operation_id: OPERATION.into(),
                revision: 1,
                reason: Some("REFUSED_CLI_VALIDATION_BOUNDARY".into()),
                detail: Some(detail),
            }
        );
    }

    #[tokio::test]
    async fn a_refused_submission_keeps_its_code_and_tracks_nothing() {
        let held = holder(|_| {
            vec![step(
                "operation_submit",
                json!([]),
                json!({"kind":"operation_refused","code":"subject_busy","holder_operation_id":null}),
                false,
            )]
        });
        let operations = Operations::default();
        let mut events = held.events.subscribe();
        let refused = submit_on(
            &operations,
            &held.person,
            &mut events,
            definition("ledger.add"),
            object(json!({})),
        )
        .await
        .unwrap_err();
        assert_eq!(refused.code, "refused");
        assert_eq!(refused.reason.as_deref(), Some("subject_busy"));
        assert!(operations.find(OPERATION).is_err());
    }

    #[tokio::test]
    async fn an_oversize_request_never_reaches_the_relay() {
        // The holder stops at any request: an oversize one must not be sent.
        let held = holder(|_| vec![]);
        let operations = Operations::default();
        let mut events = held.events.subscribe();
        let refused = submit_on(
            &operations,
            &held.person,
            &mut events,
            definition("ledger.classify.bulk"),
            object(json!({"csv_text":"a".repeat(PAYLOAD_LIMIT)})),
        )
        .await
        .unwrap_err();
        assert_eq!(refused.code, "too_large");
        assert!(lock(&held.person).is_open(), "the bridge is still held");
    }

    #[tokio::test]
    async fn a_review_is_answered_only_with_the_digest_the_window_was_shown() {
        let digest = "c".repeat(64);
        let review = |d: &str| {
            json!({"kind":"operation_review","operation_id":OPERATION,"interaction_id":"i-1",
                "revision":5,"expires_at":null,"review_digest":d,
                "document":{"projection":{"proposal":{"classification":"BUSINESS"}}}})
        };
        let held = holder(|_| {
            vec![
                step(
                    "operation_submit",
                    json!([["definition_id", "ledger.classify.review"]]),
                    json!({"kind":"operation_submitted","operation_id":OPERATION}),
                    false,
                ),
                step(
                    "operation_observe",
                    json!([]),
                    observed(
                        "ledger.classify.review",
                        "running",
                        json!({"pending_interaction":{"disposition":"review_available"},"revision":5}),
                    ),
                    false,
                ),
                step(
                    "operation_review",
                    json!([]),
                    review(&"c".repeat(64)),
                    false,
                ),
                step(
                    "operation_respond",
                    json!([
                        ["interaction_id", "i-1"],
                        ["revision", 5],
                        ["review_digest", "c".repeat(64)],
                        ["decision", "apply"]
                    ]),
                    json!({"kind":"operation_responded","operation_id":OPERATION,"decision":"apply"}),
                    true,
                ),
                step(
                    "operation_observe",
                    json!([]),
                    observed(
                        "ledger.classify.review",
                        "terminal",
                        json!({"terminal_condition":"succeeded","effect":"updated","revision":7}),
                    ),
                    false,
                ),
                step(
                    "operation_result",
                    json!([]),
                    json!({"kind":"operation_result","operation_id":OPERATION,
                        "definition_id":"ledger.classify.review","document":{"projection":{"outcome":"applied"}}}),
                    false,
                ),
            ]
        });
        let operations = Operations::default();
        let mut events = held.events.subscribe();
        let paused = submit_on(
            &operations,
            &held.person,
            &mut events,
            definition("ledger.classify.review"),
            object(json!({"transaction_id":"t1","mode":"classification"})),
        )
        .await
        .unwrap();
        assert!(matches!(paused, Outcome::Review { revision: 5, .. }));
        let tracked = operations.find(OPERATION).unwrap();
        // Nothing was shown yet: no answer is sent.
        assert_eq!(
            answer_on(
                &operations,
                &tracked,
                &held.person,
                &mut events,
                &digest,
                Decision::Apply
            )
            .await
            .unwrap_err()
            .code,
            "review_changed"
        );
        let shown = review_on(&operations, &tracked, &held.person)
            .await
            .unwrap();
        assert_eq!(shown.review_digest, digest);
        assert_eq!(shown.review["proposal"]["classification"], "BUSINESS");
        let tracked = operations.find(OPERATION).unwrap();
        // Another digest than the one shown is refused here, without an exchange.
        assert_eq!(
            answer_on(
                &operations,
                &tracked,
                &held.person,
                &mut events,
                &"d".repeat(64),
                Decision::Apply
            )
            .await
            .unwrap_err()
            .code,
            "review_changed"
        );
        let settled = answer_on(
            &operations,
            &tracked,
            &held.person,
            &mut events,
            &digest,
            Decision::Apply,
        )
        .await
        .unwrap();
        assert_eq!(
            settled,
            Outcome::Settled {
                operation_id: OPERATION.into(),
                revision: 7,
                result: json!({"outcome":"applied"}),
            }
        );
        assert!(operations.find(OPERATION).unwrap().shown.is_none());
    }

    #[tokio::test]
    async fn an_answer_to_a_review_that_changed_is_refused_as_changed() {
        let held = holder(|_| {
            vec![
                step(
                    "operation_review",
                    json!([]),
                    json!({"kind":"operation_review","operation_id":OPERATION,"interaction_id":"i-1",
                        "revision":5,"expires_at":null,"review_digest":"c".repeat(64),
                        "document":{"projection":{}}}),
                    false,
                ),
                step(
                    "operation_respond",
                    json!([]),
                    json!({"kind":"operation_refused","code":"review_changed","holder_operation_id":null}),
                    false,
                ),
            ]
        });
        let operations = Operations::default();
        operations.track(Tracked {
            operation: OPERATION.into(),
            definition: definition("ledger.split.review"),
            subject: format!("profile:{PROFILE}"),
            identity: held.identity.clone(),
            shown: None,
        });
        let tracked = operations.find(OPERATION).unwrap();
        review_on(&operations, &tracked, &held.person)
            .await
            .unwrap();
        let tracked = operations.find(OPERATION).unwrap();
        let mut events = held.events.subscribe();
        let refused = answer_on(
            &operations,
            &tracked,
            &held.person,
            &mut events,
            &"c".repeat(64),
            Decision::Reject,
        )
        .await
        .unwrap_err();
        assert_eq!(refused.code, "review_changed");
        assert!(operations.find(OPERATION).unwrap().shown.is_none());
    }

    #[tokio::test]
    async fn a_cancel_names_the_observed_revision_and_a_refusal_keeps_its_code() {
        let held = holder(|_| {
            vec![step(
                "operation_cancel",
                json!([["operation_id", OPERATION], ["expected_revision", 9]]),
                json!({"kind":"operation_refused","code":"cancellation_unsupported","holder_operation_id":null}),
                false,
            )]
        });
        let tracked = Tracked {
            operation: OPERATION.into(),
            definition: definition("ledger.import"),
            subject: format!("profile:{PROFILE}"),
            identity: held.identity.clone(),
            shown: None,
        };
        let refused = cancel_on(&tracked, &held.person, 9).await.unwrap_err();
        assert_eq!(refused.code, "refused");
        assert_eq!(refused.reason.as_deref(), Some("cancellation_unsupported"));
        assert_eq!(refused.operation_id.as_deref(), Some(OPERATION));
    }
}
