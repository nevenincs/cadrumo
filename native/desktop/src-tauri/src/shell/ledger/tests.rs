use super::*;

fn definition(id: &str) -> Definition {
    admitted(id).unwrap()
}
fn object(value: Value) -> Map<String, Value> {
    value.as_object().unwrap().clone()
}

#[test]
fn the_window_names_no_profile_directory_or_account_secret() {
    for (id, payload) in [
        ("ledger.list", json!({"profile_id":"another"})),
        ("ledger.evidence.add", json!({"source_directory":"C:\\"})),
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
    ] {
        assert!(admit_fields(definition(id), &object(payload)).is_ok());
    }
}

/// A scratch folder with one file of each kind the purposes read.
fn scratch(name: &str) -> std::path::PathBuf {
    let root = std::env::temp_dir().join(format!(
        "cadrumo-ledger-tokens-{name}-{}",
        std::process::id()
    ));
    let _ = std::fs::remove_dir_all(&root);
    std::fs::create_dir_all(&root).unwrap();
    for file in ["statement.csv", "book.xlsx", "receipt.pdf"] {
        std::fs::write(root.join(file), b"x").unwrap();
    }
    root
}
fn token(files: &Files, identity: &Value, purpose: Purpose, path: std::path::PathBuf) -> Value {
    let picks =
        serde_json::to_value(files.issue_all(identity, purpose, vec![path]).unwrap()).unwrap();
    picks["files"][0]["token"].clone()
}

#[test]
fn file_tokens_become_paths_only_where_the_definition_reads_a_file() {
    let root = scratch("substitute");
    let files = Files::default();
    let session = json!({"session_id":"one"});
    let statement = token(
        &files,
        &session,
        Purpose::BankStatements,
        root.join("statement.csv"),
    );
    let book = token(
        &files,
        &session,
        Purpose::InvoiceBooks,
        root.join("book.xlsx"),
    );
    let receipt = token(
        &files,
        &session,
        Purpose::Documents,
        root.join("receipt.pdf"),
    );
    let text = |path: std::path::PathBuf| json!(path.to_str().unwrap());

    let mut import = object(json!({"files":[statement],"provider":"auto","verify_source":null}));
    substitute(&files, &session, definition("ledger.import"), &mut import).unwrap();
    assert_eq!(import["files"], json!([text(root.join("statement.csv"))]));
    assert_eq!(import["verify_source"], Value::Null);
    assert!(!import.contains_key("source_directory"));

    let mut add = object(json!({"source_path":receipt}));
    let folders = substitute(
        &files,
        &session,
        definition("ledger.evidence.add"),
        &mut add,
    )
    .unwrap();
    assert_eq!(folders, [root.to_str().unwrap()]);
    assert_eq!(add["source_path"], text(root.join("receipt.pdf")));
    assert_eq!(add["source_directory"], text(root.clone()));

    let mut book_import = object(json!({"source_path":book,"kind":"RECEIVED"}));
    substitute(
        &files,
        &session,
        definition("ledger.invoice.import"),
        &mut book_import,
    )
    .unwrap();
    assert_eq!(book_import["source_path"], text(root.join("book.xlsx")));

    for (id, payload, code) in [
        // A path, not a token.
        (
            "ledger.import",
            json!({"files":[root.join("statement.csv").to_str().unwrap()]}),
            "invalid",
        ),
        // A token picked for another purpose.
        ("ledger.import", json!({"files":[book.clone()]}), "invalid"),
        (
            "ledger.evidence.add",
            json!({"source_path":statement.clone()}),
            "invalid",
        ),
        // No file at all, or not a list.
        ("ledger.import", json!({"files":[]}), "invalid"),
        (
            "ledger.import",
            json!({"files":statement.clone()}),
            "invalid",
        ),
        (
            "ledger.invoice.import",
            json!({"source_path":null}),
            "invalid",
        ),
        // A token this session never issued.
        (
            "ledger.import",
            json!({"files":["file-0000"]}),
            "file_unavailable",
        ),
    ] {
        assert_eq!(
            substitute(
                &files,
                &session,
                definition(id),
                &mut object(payload.clone())
            )
            .unwrap_err()
            .code,
            code,
            "{id} {payload}"
        );
    }
    // Only the fields a definition reads files from are substituted.
    let mut update = object(json!({"transaction_id":"t","source_path":statement.clone()}));
    substitute(&files, &session, definition("ledger.update"), &mut update).unwrap();
    assert_eq!(update["source_path"], statement);
    // Another session's window cannot use these tokens.
    assert_eq!(
        substitute(
            &files,
            &json!({"session_id":"two"}),
            definition("ledger.invoice.import"),
            &mut object(json!({"source_path":book})),
        )
        .unwrap_err()
        .code,
        "file_unavailable"
    );
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn an_export_is_shown_in_the_file_manager_only_once_written_and_only_by_its_save_token() {
    let root = scratch("reveal");
    let files = Files::default();
    let session = json!({"session_id":"one"});
    let target = root.join("ledger-2026-4T.csv");
    let saved = serde_json::to_value(files.issue_save(&session, "csv", target.clone()).unwrap())
        .unwrap()["files"][0]["token"]
        .clone();
    let saved = saved.as_str().unwrap();
    // Not written yet: there is nothing to show.
    assert_eq!(files.saved(&session, saved).unwrap_err().code, "file_unavailable");
    std::fs::write(&target, b"x").unwrap();
    assert_eq!(files.saved(&session, saved).unwrap(), target);
    // A file picked to be read is never shown through this door.
    let picked = token(&files, &session, Purpose::BankStatements, root.join("statement.csv"));
    assert_eq!(files.saved(&session, picked.as_str().unwrap()).unwrap_err().code, "invalid");
    // Nor is a save token from another session, or one never issued.
    let other = json!({"session_id":"two"});
    assert_eq!(files.saved(&other, saved).unwrap_err().code, "file_unavailable");
    assert_eq!(files.saved(&session, "not-a-token").unwrap_err().code, "invalid");
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn an_export_goes_only_where_the_person_saved_its_format() {
    let files = Files::default();
    let session = json!({"session_id":"one"});
    let target = std::env::temp_dir().join("ledger-export.jsonl");
    let saved =
        serde_json::to_value(files.issue_save(&session, "jsonl", target.clone()).unwrap()).unwrap();
    let saved = saved["files"][0]["token"].clone();
    let mut export = object(json!({"output_path":saved,"export_format":"jsonl"}));
    substitute(&files, &session, definition("ledger.export"), &mut export).unwrap();
    assert_eq!(export["output_path"], json!(target.to_str().unwrap()));
    for format in [json!("csv"), json!(1)] {
        let mut mismatched = object(json!({"output_path":saved,"export_format":format}));
        assert_eq!(
            substitute(
                &files,
                &session,
                definition("ledger.export"),
                &mut mismatched
            )
            .unwrap_err()
            .code,
            "invalid"
        );
    }
    let mut defaulted = object(json!({"output_path":saved}));
    assert!(
        substitute(
            &files,
            &session,
            definition("ledger.export"),
            &mut defaulted
        )
        .is_err(),
        "an absent format is the contract's csv"
    );
}

#[test]
fn an_own_account_change_comes_only_as_a_raw_object_to_add_or_update() {
    let raw = |text: &str| InvokeBody::Raw(text.as_bytes().to_vec());
    let added = own_account_body(&raw(
        r#" {"action":"add","label":"Main","holding":"own","iban":"ES9121000418450200051332"}"#,
    ))
    .unwrap();
    assert_eq!(added.0["iban"], "ES9121000418450200051332");
    assert!(
        own_account_body(&raw(
            r#"{"action":"update","own_account_id":"acc-01","bank_name":"B"}"#
        ))
        .is_ok()
    );
    for refused in [
        r#"{"action":"list"}"#.to_owned(),
        r#"{"action":"add","profile_id":"another","iban":"ES00"}"#.to_owned(),
        r#"["add"]"#.to_owned(),
        "not json".to_owned(),
        format!(
            r#"{{"action":"add","label":"{}"}}"#,
            "a".repeat(SECRET_BODY_LIMIT)
        ),
    ] {
        assert_eq!(
            own_account_body(&raw(&refused)).unwrap_err().code,
            "invalid"
        );
    }
    assert_eq!(
        own_account_body(&InvokeBody::Json(json!({"action":"add"})))
            .unwrap_err()
            .code,
        "invalid",
        "a JSON argument can be logged by the transport; only a raw body carries it"
    );
    // Dropping the request overwrites its text.
    let mut kept = own_account_body(&raw(r#"{"action":"add","iban":"ES00"}"#)).unwrap();
    cadrumo_application::person_operations::wipe(&mut kept.0);
    assert_eq!(kept.0["iban"], "");
}

#[test]
fn dialog_words_are_bounded_and_a_suggested_name_names_no_folder() {
    assert!(label_admitted("Extractos bancarios"));
    assert!(!label_admitted(""));
    assert!(!label_admitted(&"a".repeat(LABEL_LIMIT + 1)));
    assert!(!label_admitted("line\nbreak"));
    assert!(file_name_admitted("libro-2026.csv"));
    for refused in ["..\\up.csv", "C:\\x.csv", "a/b.csv", ".hidden"] {
        assert!(!file_name_admitted(refused), "{refused}");
    }
}

#[test]
fn a_classification_review_holds_its_movement_and_every_other_definition_the_profile() {
    let profile = "11111111-1111-4111-8111-111111111111";
    let review = definition("ledger.classify.review");
    assert_eq!(
        subject(
            review,
            profile,
            &object(json!({"transaction_id":"ab12cd34"}))
        )
        .unwrap(),
        "ab12cd34"
    );
    for refused in [
        json!({}),
        json!({"transaction_id":""}),
        json!({"transaction_id":7}),
    ] {
        assert_eq!(
            subject(review, profile, &object(refused.clone()))
                .unwrap_err()
                .code,
            "invalid",
            "{refused}"
        );
    }
    for id in ["ledger.split.review", "ledger.list", "ledger.update"] {
        assert_eq!(
            subject(
                definition(id),
                profile,
                &object(json!({"transaction_id":"ab12cd34"}))
            )
            .unwrap(),
            relay::subject(profile),
            "{id}"
        );
    }
}

#[cfg(windows)]
mod relayed {
    use super::super::super::scripted::{OPERATION, PROFILE, holder, observed, step};
    use super::*;

    fn subject() -> String {
        relay::subject(PROFILE)
    }

    /// The session the window still holds.
    struct Held;
    impl settle::Session for Held {
        async fn holds(&self, _person: &HeldPerson) -> Result<()> {
            Ok(())
        }
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
                    observed("ledger.list", &subject(), "running", json!({})),
                    true,
                ),
                step(
                    "operation_observe",
                    json!([]),
                    observed(
                        "ledger.list",
                        &subject(),
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
            held.identity.clone(),
            &mut events,
            definition("ledger.list"),
            Wiped(json!({"limit":200})),
            Vec::new(),
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
    async fn a_page_reaches_the_window_with_its_file_name_and_image_and_no_folder() {
        // Base64 carries "/" and "+", which the folder reduction must leave alone.
        let image = "data:image/png;base64,iVBORw0KGgo+/Users/alba/AAAA+/x==";
        let held = holder(|_| {
            vec![
                step(
                    "operation_submit",
                    json!([
                        ["definition_id", "ledger.evidence.page"],
                        ["payload.profile_id", PROFILE],
                        ["payload.evidence_id", "ev-1"],
                        ["payload.page", 2]
                    ]),
                    json!({"kind":"operation_submitted","operation_id":OPERATION}),
                    false,
                ),
                step(
                    "operation_observe",
                    json!([]),
                    observed(
                        "ledger.evidence.page",
                        &subject(),
                        "terminal",
                        json!({"terminal_condition":"succeeded","revision":2}),
                    ),
                    false,
                ),
                step(
                    "operation_result",
                    json!([]),
                    json!({"kind":"operation_result","operation_id":OPERATION,
                        "definition_id":"ledger.evidence.page",
                        "document":{"projection":{"file_name":r"C:\Users\alba\Tickets\ticket-plenoil.jpg",
                            "media_type":"image/jpeg","page":2,"page_count":3,
                            "source_sha256":"ab","image_data_url":image}}}),
                    false,
                ),
            ]
        });
        let operations = Operations::default();
        let mut events = held.events.subscribe();
        let outcome = submit_on(
            &operations,
            &held.person,
            held.identity.clone(),
            &mut events,
            definition("ledger.evidence.page"),
            Wiped(json!({"evidence_id":"ev-1","page":2,"max_width":1200})),
            Vec::new(),
        )
        .await
        .unwrap();
        let Outcome::Settled { result, .. } = outcome else {
            panic!("the page read did not settle: {outcome:?}");
        };
        // A worker that named where the file lay is reduced to its name; the
        // image passes untouched.
        assert_eq!(result["file_name"], "ticket-plenoil.jpg");
        assert_eq!(result["image_data_url"], image);
        assert!(!result.to_string().contains("Tickets"));
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
                        &subject(),
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
            held.identity.clone(),
            &mut events,
            definition("ledger.update"),
            Wiped(json!({"transaction_id":"t1","patch":{}})),
            Vec::new(),
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
    async fn an_own_accounts_number_reaches_the_relay_only_in_its_request() {
        let iban = "ES9121000418450200051332";
        let held = holder(|_| {
            vec![
                step(
                    "operation_submit",
                    json!([
                        ["definition_id", "ledger.own_account"],
                        ["payload.action", "add"],
                        ["payload.iban", iban],
                        ["payload.profile_id", PROFILE]
                    ]),
                    json!({"kind":"operation_submitted","operation_id":OPERATION}),
                    false,
                ),
                step(
                    "operation_observe",
                    json!([]),
                    observed(
                        "ledger.own_account",
                        &subject(),
                        "terminal",
                        json!({"terminal_condition":"succeeded","effect":"updated"}),
                    ),
                    false,
                ),
                step(
                    "operation_result",
                    json!([]),
                    json!({"kind":"operation_result","operation_id":OPERATION,
                        "definition_id":"ledger.own_account",
                        "document":{"projection":{"own_account_id":"acc-01","masked_iban":"ES**1332"}}}),
                    false,
                ),
            ]
        });
        let body = InvokeBody::Raw(
            format!(r#"{{"action":"add","label":"Main","holding":"own","iban":"{iban}"}}"#)
                .into_bytes(),
        );
        let operations = Operations::default();
        let mut events = held.events.subscribe();
        let outcome = submit_on(
            &operations,
            &held.person,
            held.identity.clone(),
            &mut events,
            definition("ledger.own_account"),
            own_account_body(&body).unwrap(),
            Vec::new(),
        )
        .await
        .unwrap();
        let Outcome::Settled { result, .. } = outcome else {
            panic!("the account was added");
        };
        assert!(
            !result.to_string().contains(iban),
            "only the masked view returns"
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
            held.identity.clone(),
            &mut events,
            definition("ledger.add"),
            Wiped(json!({})),
            Vec::new(),
        )
        .await
        .unwrap_err();
        assert_eq!(refused.code, "refused");
        assert_eq!(refused.reason.as_deref(), Some("subject_busy"));
        assert!(operations.find(OPERATION).is_err());
    }

    #[tokio::test]
    async fn a_submission_the_window_could_not_follow_is_refused_before_it_is_sent() {
        // The relay answers nothing: a request that reached it would be lost.
        let held = holder(|_| Vec::new());
        let operations = Operations::default();
        for at in 0..settle::FOLLOWED_CEILING {
            operations.track(Tracked::new(
                format!("{at:064x}"),
                definition("ledger.update").settling(),
                subject(),
                held.identity.clone(),
                Vec::new(),
            ));
        }
        let mut events = held.events.subscribe();
        let refused = submit_on(
            &operations,
            &held.person,
            held.identity.clone(),
            &mut events,
            definition("ledger.add"),
            Wiped(json!({})),
            Vec::new(),
        )
        .await
        .unwrap_err();
        assert_eq!((refused.code, refused.operation_id), ("unavailable", None));
        assert!(lock(&held.person).is_open(), "nothing reached the relay");
        assert!(operations.find(&format!("{:064x}", 0)).is_ok());
    }

    #[tokio::test]
    async fn a_write_whose_submission_reply_was_lost_is_unknown_and_a_read_stays_refused() {
        for (id, code, reason) in [
            ("ledger.add", "unknown", None),
            ("ledger.list", "refused", Some("unavailable")),
        ] {
            let held = holder(|_| {
                vec![step(
                    "operation_submit",
                    json!([]),
                    json!({"kind":"operation_refused","code":"unavailable","holder_operation_id":null}),
                    false,
                )]
            });
            let operations = Operations::default();
            let mut events = held.events.subscribe();
            let failed = submit_on(
                &operations,
                &held.person,
                held.identity.clone(),
                &mut events,
                definition(id),
                Wiped(json!({})),
                Vec::new(),
            )
            .await
            .unwrap_err();
            assert_eq!(failed.code, code, "{id}");
            assert_eq!(failed.reason.as_deref(), reason, "{id}");
        }
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
            held.identity.clone(),
            &mut events,
            definition("ledger.classify.bulk"),
            Wiped(json!({"csv_text":"a".repeat(relay::PAYLOAD_LIMIT)})),
            Vec::new(),
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
                    json!([
                        ["definition_id", "ledger.classify.review"],
                        ["subject_ref", "t1"],
                        ["payload.transaction_id", "t1"]
                    ]),
                    json!({"kind":"operation_submitted","operation_id":OPERATION}),
                    false,
                ),
                step(
                    "operation_observe",
                    json!([]),
                    observed(
                        "ledger.classify.review",
                        "t1",
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
                        "t1",
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
            held.identity.clone(),
            &mut events,
            definition("ledger.classify.review"),
            Wiped(json!({"transaction_id":"t1","mode":"classification"})),
            Vec::new(),
        )
        .await
        .unwrap();
        assert!(matches!(paused, Outcome::Review { revision: 5, .. }));
        let tracked = operations.find(OPERATION).unwrap();
        // Nothing was shown yet: no answer is sent.
        assert_eq!(
            settle::answer_on(
                &Held,
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
        let shown = settle::review_on(&operations, &tracked, &held.person)
            .await
            .unwrap();
        assert_eq!(shown.review_digest, digest);
        assert_eq!(shown.review["proposal"]["classification"], "BUSINESS");
        let tracked = operations.find(OPERATION).unwrap();
        // Another digest than the one shown is refused here, without an exchange.
        assert_eq!(
            settle::answer_on(
                &Held,
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
        let settled = settle::answer_on(
            &Held,
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
}
