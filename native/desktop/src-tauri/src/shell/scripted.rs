//! A stand-in for the session hold, for tests that follow operations over the
//! relay: it answers each request with the next scripted reply, after checking
//! the request's action and named fields, and stops at anything else. A step
//! may first push an operation change.
use crate::agent::person::{HeldPerson, Person, PersonEvent, request_id};
use serde_json::{Value, json};
use std::{
    sync::{Arc, Mutex},
    time::Duration,
};

pub(super) const PROFILE: &str = "11111111-1111-4111-8111-111111111111";
pub(super) const OPERATION: &str =
    "abababababababababababababababababababababababababababababababab";

pub(super) struct Holder {
    pub(super) person: HeldPerson,
    pub(super) identity: Value,
    pub(super) events: tokio::sync::broadcast::Sender<PersonEvent>,
}

/// One scripted exchange: `expect` lists `[dotted.field, value]` pairs the
/// request must carry.
pub(super) fn step(action: &str, expect: Value, reply: Value, push: bool) -> Value {
    json!({"action":action, "expect":expect, "reply":reply, "push":push})
}

pub(super) fn holder(steps: impl Fn(&Value) -> Vec<Value>) -> Holder {
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

/// The relay's observation of the scripted operation, with `extra` fields.
pub(super) fn observed(definition: &str, subject: &str, lifecycle: &str, extra: Value) -> Value {
    let mut p = json!({"operation_id":OPERATION, "definition_id":definition,
        "subject_ref":subject, "lifecycle":lifecycle,
        "terminal_condition":null, "effect":"none", "refusal_ref":null,
        "failure_error_code":null, "revision":1, "cancellable_now":false,
        "pending_interaction":{"disposition":"none"}});
    for (key, value) in extra.as_object().unwrap() {
        p[key] = value.clone();
    }
    json!({"kind":"operation_observed", "observation":{"projection":p}})
}

/// The relay's result document for the scripted operation.
pub(super) fn resulted(definition: &str, projection: Value) -> Value {
    json!({"kind":"operation_result","operation_id":OPERATION,"definition_id":definition,
        "document":{"projection":projection}})
}
