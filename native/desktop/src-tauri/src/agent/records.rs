//! The conversation answers the host composes from a conversation's runs:
//! its records, oldest first, and what its newest reply waits on.
//!
//! A field the host copies from a gateway answer keeps the gateway's value
//! unchanged, or null where the gateway served none; its schema names the
//! gateway's own definition. `snapshot.schema.json` beside this module is the
//! schema the window's generated types are written from, and a test here
//! keeps it equal to these types.

use super::stream::{Approval, Questionnaire, ToolFailure};
use serde::Serialize;
use serde_json::Value;

/// One read of a conversation: its records, and what its current reply
/// waits on.
#[derive(Debug, PartialEq, Serialize)]
#[cfg_attr(test, derive(schemars::JsonSchema), schemars(rename = "AgentSnapshot"))]
pub struct Snapshot {
    pub history: Vec<TurnRecord>,
    pub pending: Pending,
}

/// What a reply waits on: the questionnaires and the approvals it asked for
/// and nobody answered yet.
#[derive(Debug, Default, PartialEq, Serialize)]
#[cfg_attr(test, derive(schemars::JsonSchema), schemars(rename = "AgentPending"))]
pub struct Pending {
    pub questionnaires: Vec<Questionnaire>,
    pub approvals: Vec<Approval>,
}

/// What history lists of a conversation, oldest first: per reply, the
/// person's messages, its tool calls, the agent's messages, and last the
/// reply's own record.
#[derive(Debug, PartialEq, Serialize)]
#[cfg_attr(
    test,
    derive(schemars::JsonSchema),
    schemars(rename = "AgentTurnRecord")
)]
#[serde(untagged)]
pub enum TurnRecord {
    Person(PersonRecord),
    Tool(ToolRecord),
    Agent(AgentRecord),
    Reply(Box<ReplyRecord>),
}

macro_rules! record_kind {
    ($name:ident, $word:literal) => {
        #[doc = concat!("The `", $word, "` record's kind.")]
        #[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
        #[cfg_attr(test, derive(schemars::JsonSchema), schemars(inline))]
        pub enum $name {
            #[serde(rename = $word)]
            Only,
        }
    };
}

record_kind!(PersonKind, "person");
record_kind!(ToolKindTag, "tool");
record_kind!(AgentKind, "agent");
record_kind!(ReplyKind, "reply");

/// A message the person sent.
#[derive(Debug, PartialEq, Serialize)]
#[cfg_attr(
    test,
    derive(schemars::JsonSchema),
    schemars(rename = "AgentPersonRecord")
)]
pub struct PersonRecord {
    pub kind: PersonKind,
    /// cadrumo-agent's `message_id`; null where it served none.
    pub id: Option<String>,
    pub reply_id: String,
    pub text: String,
    /// When it was sent, as the agent's `timestamp`.
    #[cfg_attr(test, schemars(with = "Option<String>"))]
    pub sent_at: Value,
    /// The stored documents the message named, in the order it named them.
    pub attachments: Vec<DocumentReference>,
    /// The skills the message loaded, by name.
    pub skills: Vec<String>,
    /// The run whose conversation this message was carried from; null for a
    /// message said in this conversation. `sent_at` is then when it was first
    /// said.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub carried_from_run_id: Option<String>,
}

/// A stored document a message names, as the history echoes it.
#[derive(Debug, PartialEq, Eq, Serialize)]
#[cfg_attr(
    test,
    derive(schemars::JsonSchema),
    schemars(rename = "AgentDocumentReference")
)]
pub struct DocumentReference {
    pub name: String,
    pub sha256: Option<String>,
    pub media_type: Option<String>,
}

/// A tool call of a reply, as its history lists it.
#[derive(Debug, PartialEq, Eq, Serialize)]
#[cfg_attr(
    test,
    derive(schemars::JsonSchema),
    schemars(rename = "AgentToolRecord")
)]
pub struct ToolRecord {
    pub kind: ToolKindTag,
    pub reply_id: String,
    /// cadrumo-agent's `tool_call_id`.
    pub id: Option<String>,
    /// The tool's name, as the agent gives it.
    pub title: Option<String>,
    #[cfg_attr(test, schemars(schema_with = "relayed::tool_kind"))]
    pub tool_kind: Option<String>,
    #[cfg_attr(test, schemars(schema_with = "relayed::tool_call_status"))]
    pub status: Option<String>,
    /// The tool server that owns the tool, e.g. `cadrumo`; null where unnamed.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tool_server: Option<String>,
    /// The tool's own name within its server; null where unnamed.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tool_name: Option<String>,
    /// How far the tool reaches; null where the agent did not say.
    #[serde(skip_serializing_if = "Option::is_none")]
    #[cfg_attr(test, schemars(schema_with = "relayed::tool_reach"))]
    pub tool_reach: Option<String>,
    /// Why the call failed, where it failed and stated why.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub failure: Option<ToolFailure>,
    /// What the history says of the call, as the agent worded it and the
    /// host cut it: its text, its diffs' paths and the places it touched.
    pub details: Vec<String>,
}

/// A message the agent wrote.
#[derive(Debug, PartialEq, Eq, Serialize)]
#[cfg_attr(
    test,
    derive(schemars::JsonSchema),
    schemars(rename = "AgentMessageRecord")
)]
pub struct AgentRecord {
    pub kind: AgentKind,
    /// cadrumo-agent's `message_id`; null where it served none.
    pub id: Option<String>,
    pub reply_id: String,
    pub text: String,
    /// The run whose conversation this message was carried from; null for a
    /// message said in this conversation.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub carried_from_run_id: Option<String>,
}

/// The record of a reply (a run) itself.
#[derive(Debug, PartialEq, Serialize)]
#[cfg_attr(
    test,
    derive(schemars::JsonSchema),
    schemars(rename = "AgentReplyRecord")
)]
pub struct ReplyRecord {
    pub kind: ReplyKind,
    /// The run's id: the reply's handle.
    pub id: String,
    /// The run's status, from its status read or else its history.
    #[cfg_attr(test, schemars(schema_with = "relayed::thread_status"))]
    pub status: Value,
    /// For a failed run, why its provider failed.
    #[cfg_attr(test, schemars(schema_with = "relayed::provider_condition"))]
    pub provider_condition: Value,
    /// For a failed run, the agent's one line about it.
    #[cfg_attr(test, schemars(with = "Option<String>"))]
    pub failure_reason: Value,
    /// Messages queued behind the run's current turn; 0 where the agent
    /// served no count.
    #[cfg_attr(test, schemars(with = "u64"))]
    pub queued_messages: Value,
    pub selection: Option<RanWith>,
    pub usage: Option<Usage>,
}

/// What a reply ran with, as the agent froze it when the run started.
#[derive(Debug, PartialEq, Serialize)]
#[cfg_attr(test, derive(schemars::JsonSchema), schemars(rename = "AgentRanWith"))]
pub struct RanWith {
    #[cfg_attr(test, schemars(schema_with = "relayed::provider"))]
    pub provider: Value,
    #[cfg_attr(test, schemars(schema_with = "relayed::provider_transport"))]
    pub transport: Value,
    #[cfg_attr(test, schemars(with = "Option<String>"))]
    pub provider_display_name: Value,
    #[cfg_attr(test, schemars(with = "Option<String>"))]
    pub model: Value,
    #[cfg_attr(test, schemars(with = "Option<String>"))]
    pub model_display_name: Value,
    #[cfg_attr(test, schemars(schema_with = "relayed::effort"))]
    pub effort: Value,
}

/// The tokens a run's provider reported, as the agent counts them.
#[derive(Debug, PartialEq, Serialize)]
#[cfg_attr(test, derive(schemars::JsonSchema), schemars(rename = "AgentUsage"))]
pub struct Usage {
    #[cfg_attr(test, schemars(with = "Option<u64>"))]
    pub input_tokens: Value,
    #[cfg_attr(test, schemars(with = "Option<u64>"))]
    pub output_tokens: Value,
}

/// The schemas of fields the host copies from a gateway answer: the
/// gateway's own definition, or null where the host may find none. The
/// window's generator resolves each name against the agent's pinned schema.
#[cfg(test)]
pub(super) mod relayed {
    use schemars::{Schema, SchemaGenerator, json_schema};

    fn named(name: &str) -> Schema {
        json_schema!({ "$ref": format!("#/$defs/{name}") })
    }

    fn nullable(name: &str) -> Schema {
        json_schema!({ "anyOf": [named(name), { "type": "null" }] })
    }

    pub fn thread_status(_: &mut SchemaGenerator) -> Schema {
        nullable("ThreadStatus")
    }

    pub fn provider_condition(_: &mut SchemaGenerator) -> Schema {
        nullable("ProviderCondition")
    }

    pub fn tool_kind(_: &mut SchemaGenerator) -> Schema {
        nullable("ToolKind")
    }

    pub fn tool_reach(_: &mut SchemaGenerator) -> Schema {
        nullable("ToolReach")
    }

    pub fn tool_call_status(_: &mut SchemaGenerator) -> Schema {
        nullable("ToolCallStatus")
    }

    pub fn provider(_: &mut SchemaGenerator) -> Schema {
        nullable("Provider")
    }

    /// A selection is listed only where its transport is a string.
    pub fn provider_transport(_: &mut SchemaGenerator) -> Schema {
        named("ProviderTransport")
    }

    pub fn effort(_: &mut SchemaGenerator) -> Schema {
        nullable("Effort")
    }
}

#[cfg(test)]
mod tests {
    use super::Snapshot;
    use schemars::generate::SchemaSettings;

    /// The schema the window's generated types are written from.
    const SCHEMA_FILE: &str = include_str!("snapshot.schema.json");

    /// Where a refreshed schema is written, when set to an absolute path.
    const WRITE_TO: &str = "CADRUMO_AGENT_SNAPSHOT_SCHEMA_OUT";

    fn schema() -> String {
        let mut generator = SchemaSettings::draft2020_12()
            .for_serialize()
            .into_generator();
        generator.subschema_for::<Snapshot>();
        let definitions = generator.take_definitions(true);
        let document = serde_json::json!({ "root": "AgentSnapshot", "$defs": definitions });
        serde_json::to_string_pretty(&document).unwrap() + "\n"
    }

    #[test]
    fn the_snapshot_schema_file_is_current() {
        let fresh = schema();
        if let Some(target) = std::env::var_os(WRITE_TO) {
            let target = std::path::PathBuf::from(target);
            assert!(target.is_absolute(), "{WRITE_TO} must be an absolute path");
            std::fs::write(&target, &fresh).unwrap();
        }
        assert!(
            SCHEMA_FILE.replace("\r\n", "\n") == fresh,
            "src/agent/snapshot.schema.json is stale: run this test with {WRITE_TO} set to its absolute path"
        );
    }
}
