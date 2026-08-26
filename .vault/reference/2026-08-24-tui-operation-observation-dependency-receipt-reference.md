{
  "receipt_schema_version": 1,
  "cohort": "c0.operation-projection",
  "implementation_commit": "49f5bbda9151523d88d36c03457ba11f4b2e04fe",
  "source_tree_digest": "6ee7ad99bd18eacb521533412ab986e00cbeb52cd1ae9daaa40ccb0c7fa3ee2b",
  "governing_adr": {
    "stem": "2026-08-11-tui-architecture-adr",
    "status": "accepted",
    "body_hash": "sha256:6a55376ca86e816708a6a497a8047b9e5d9cb96488cd70a9a0a88e6eabb6a81a",
    "producing_commit": "f3d439a8bfde16029b9ece651d687268a49d9853"
  },
  "staging_adr": {
    "stem": "2026-08-24-tui-operation-observation-adr",
    "status": "rejected",
    "body_hash": "sha256:e8f44be175c879eed50517f3590a50885714f8152b9d69892c9c97e05a29ac9a",
    "producing_commit": "c5ba8fd6eb3756da17f40806438344a257a02599"
  },
  "public_contract_set": {
    "contract_set_version": 1,
    "definitions": [
      {
        "manifest_version": 1,
        "definition_id": "auth.profile.login",
        "action_reference": null,
        "request_schema": {
          "schema_id": "auth.profile.login.request",
          "schema_version": 1,
          "schema_fingerprint": "b6ebd607a813efc70382b868871f5d7f808917063182ade19e5ec008589fef03"
        },
        "result_schema": null,
        "review_projection_schema": null,
        "interaction_response_schema": null,
        "workspace_refresh_target_schema": null,
        "interaction_kinds": [],
        "request_storage": "credential_free_journal",
        "durability": "recorded",
        "cancellation": "unsupported",
        "deadline": "absent",
        "replay": "idempotent_submit",
        "baseline": "none",
        "sensitive_input": "none",
        "conflict_scope": "definition_subject",
        "owned_resources": [],
        "permitted_effects": [
          "none",
          "updated",
          "unknown"
        ],
        "close_policy": "detach_allowed",
        "reconciliation_policy": "interrupt",
        "permitted_frontends": [
          "tui",
          "cli",
          "mcp"
        ],
        "ephemeral_secret_required": true,
        "definition_contract_digest": "e9c8b2f5f125c1272f380017248885da4f19d7f3769595c80da63bc753bba22d"
      },
      {
        "manifest_version": 1,
        "definition_id": "auth.profile.passphrase-rotate",
        "action_reference": null,
        "request_schema": {
          "schema_id": "auth.profile.passphrase-rotate.request",
          "schema_version": 1,
          "schema_fingerprint": "f668218cc93e20912f7cbd53e7ec4086de21e35337bc6c8079bdd2437a7db07c"
        },
        "result_schema": null,
        "review_projection_schema": null,
        "interaction_response_schema": null,
        "workspace_refresh_target_schema": null,
        "interaction_kinds": [],
        "request_storage": "secure_reference",
        "durability": "recorded",
        "cancellation": "unsupported",
        "deadline": "absent",
        "replay": "idempotent_submit",
        "baseline": "none",
        "sensitive_input": "none",
        "conflict_scope": "definition_subject",
        "owned_resources": [],
        "permitted_effects": [
          "none",
          "updated",
          "unknown"
        ],
        "close_policy": "detach_allowed",
        "reconciliation_policy": "interrupt",
        "permitted_frontends": [
          "tui",
          "cli",
          "mcp"
        ],
        "ephemeral_secret_required": true,
        "definition_contract_digest": "5ba111b35bb184644e3d97a12abbc7de0eaee8a2528f2dde6a4db0a5230ffdfc"
      },
      {
        "manifest_version": 1,
        "definition_id": "auth.provider.configure",
        "action_reference": null,
        "request_schema": {
          "schema_id": "auth.provider.configure.request",
          "schema_version": 1,
          "schema_fingerprint": "1638c6cdd64498b4cb715ea8813f11e0ae5b2c5b7705ca46c8081e9f5c078047"
        },
        "result_schema": null,
        "review_projection_schema": null,
        "interaction_response_schema": null,
        "workspace_refresh_target_schema": null,
        "interaction_kinds": [],
        "request_storage": "secure_reference",
        "durability": "recorded",
        "cancellation": "unsupported",
        "deadline": "absent",
        "replay": "idempotent_submit",
        "baseline": "none",
        "sensitive_input": "none",
        "conflict_scope": "definition_subject",
        "owned_resources": [],
        "permitted_effects": [
          "none",
          "updated",
          "unknown"
        ],
        "close_policy": "detach_allowed",
        "reconciliation_policy": "interrupt",
        "permitted_frontends": [
          "tui",
          "cli",
          "mcp"
        ],
        "ephemeral_secret_required": false,
        "definition_contract_digest": "6dfcdc35023c6b07899ce317bbc31b009d57a870affb8d73806e71a2f672b1ae"
      },
      {
        "manifest_version": 1,
        "definition_id": "auth.session.acquire",
        "action_reference": null,
        "request_schema": {
          "schema_id": "auth.session.acquire.request",
          "schema_version": 1,
          "schema_fingerprint": "b7c4c7337f7259d130c50b1eb819f40ef97239c4742bd49182986b9f57298bfc"
        },
        "result_schema": null,
        "review_projection_schema": null,
        "interaction_response_schema": null,
        "workspace_refresh_target_schema": null,
        "interaction_kinds": [],
        "request_storage": "secure_reference",
        "durability": "recorded",
        "cancellation": "unsupported",
        "deadline": "absent",
        "replay": "idempotent_submit",
        "baseline": "none",
        "sensitive_input": "none",
        "conflict_scope": "definition_subject",
        "owned_resources": [],
        "permitted_effects": [
          "none",
          "updated",
          "unknown"
        ],
        "close_policy": "detach_allowed",
        "reconciliation_policy": "interrupt",
        "permitted_frontends": [
          "tui",
          "cli",
          "mcp"
        ],
        "ephemeral_secret_required": false,
        "definition_contract_digest": "7e12497bfacab773d3dc812fd334ae165ddb6be8996c01cb75d8827666ed8380"
      },
      {
        "manifest_version": 1,
        "definition_id": "auth.session.logout",
        "action_reference": null,
        "request_schema": {
          "schema_id": "auth.session.logout.request",
          "schema_version": 1,
          "schema_fingerprint": "2153481c560235f12bc157021016853d2e970a2766215c6cc8bf64bd281e84aa"
        },
        "result_schema": null,
        "review_projection_schema": null,
        "interaction_response_schema": null,
        "workspace_refresh_target_schema": null,
        "interaction_kinds": [],
        "request_storage": "secure_reference",
        "durability": "recorded",
        "cancellation": "unsupported",
        "deadline": "absent",
        "replay": "idempotent_submit",
        "baseline": "none",
        "sensitive_input": "none",
        "conflict_scope": "definition_subject",
        "owned_resources": [],
        "permitted_effects": [
          "none",
          "updated",
          "unknown"
        ],
        "close_policy": "detach_allowed",
        "reconciliation_policy": "interrupt",
        "permitted_frontends": [
          "tui",
          "cli",
          "mcp"
        ],
        "ephemeral_secret_required": false,
        "definition_contract_digest": "1ea85af2d9492fa4608d6457080b2005e280148ef100654712fb6f8e82f8ee25"
      },
      {
        "manifest_version": 1,
        "definition_id": "auth.session.reset",
        "action_reference": null,
        "request_schema": {
          "schema_id": "auth.session.reset.request",
          "schema_version": 1,
          "schema_fingerprint": "2153481c560235f12bc157021016853d2e970a2766215c6cc8bf64bd281e84aa"
        },
        "result_schema": null,
        "review_projection_schema": null,
        "interaction_response_schema": null,
        "workspace_refresh_target_schema": null,
        "interaction_kinds": [],
        "request_storage": "secure_reference",
        "durability": "recorded",
        "cancellation": "unsupported",
        "deadline": "absent",
        "replay": "idempotent_submit",
        "baseline": "none",
        "sensitive_input": "none",
        "conflict_scope": "definition_subject",
        "owned_resources": [],
        "permitted_effects": [
          "none",
          "updated",
          "unknown"
        ],
        "close_policy": "detach_allowed",
        "reconciliation_policy": "interrupt",
        "permitted_frontends": [
          "tui",
          "cli",
          "mcp"
        ],
        "ephemeral_secret_required": false,
        "definition_contract_digest": "82c7335a2b813e7cb478c301fe5ac5e90be01e8e03055a9466fb0e66d5bb4f97"
      },
      {
        "manifest_version": 1,
        "definition_id": "export.google-sheets",
        "action_reference": null,
        "request_schema": {
          "schema_id": "export.google-sheets.request",
          "schema_version": 1,
          "schema_fingerprint": "390a027d7c8a80944a22444eefa5c21847989588164303cc1141298b5a66f68b"
        },
        "result_schema": null,
        "review_projection_schema": null,
        "interaction_response_schema": null,
        "workspace_refresh_target_schema": null,
        "interaction_kinds": [],
        "request_storage": "credential_free_journal",
        "durability": "recorded",
        "cancellation": "unsupported",
        "deadline": "absent",
        "replay": "idempotent_submit",
        "baseline": "none",
        "sensitive_input": "none",
        "conflict_scope": "definition_subject",
        "owned_resources": [],
        "permitted_effects": [
          "none",
          "updated",
          "unknown"
        ],
        "close_policy": "detach_allowed",
        "reconciliation_policy": "interrupt",
        "permitted_frontends": [
          "tui",
          "cli",
          "mcp"
        ],
        "ephemeral_secret_required": false,
        "definition_contract_digest": "049fcbe0eaa2f4312f2a23aa5def0c453ce688eaf61ee21f3eac51840427e51b"
      },
      {
        "manifest_version": 1,
        "definition_id": "live.filed-history.pull",
        "action_reference": null,
        "request_schema": {
          "schema_id": "live.filed-history.pull.request",
          "schema_version": 1,
          "schema_fingerprint": "eb313197977dada243e0b1cef92498796e1c02bf4ff4762cdefcc693aa92dff3"
        },
        "result_schema": null,
        "review_projection_schema": null,
        "interaction_response_schema": null,
        "workspace_refresh_target_schema": null,
        "interaction_kinds": [],
        "request_storage": "secure_reference",
        "durability": "recorded",
        "cancellation": "unsupported",
        "deadline": "absent",
        "replay": "idempotent_submit",
        "baseline": "none",
        "sensitive_input": "secure_reference",
        "conflict_scope": "definition_subject",
        "owned_resources": [],
        "permitted_effects": [
          "none",
          "updated",
          "unknown",
          "partial"
        ],
        "close_policy": "detach_allowed",
        "reconciliation_policy": "interrupt",
        "permitted_frontends": [
          "tui",
          "cli",
          "mcp"
        ],
        "ephemeral_secret_required": false,
        "definition_contract_digest": "e27b502127f1897a3efce25ee248e20b34b9076e14b960f8c482b544a1f572f3"
      },
      {
        "manifest_version": 1,
        "definition_id": "user-profile.bundle-export",
        "action_reference": null,
        "request_schema": {
          "schema_id": "user-profile.bundle-export.request",
          "schema_version": 1,
          "schema_fingerprint": "57623eab5986bfa69ace3e2dc68dd83875002c352ec067b56e3fc8c48f627fc9"
        },
        "result_schema": null,
        "review_projection_schema": null,
        "interaction_response_schema": null,
        "workspace_refresh_target_schema": null,
        "interaction_kinds": [],
        "request_storage": "secure_reference",
        "durability": "recorded",
        "cancellation": "unsupported",
        "deadline": "absent",
        "replay": "idempotent_submit",
        "baseline": "none",
        "sensitive_input": "secure_reference",
        "conflict_scope": "definition_subject",
        "owned_resources": [],
        "permitted_effects": [
          "none",
          "updated",
          "unknown"
        ],
        "close_policy": "detach_allowed",
        "reconciliation_policy": "interrupt",
        "permitted_frontends": [
          "tui",
          "cli",
          "mcp"
        ],
        "ephemeral_secret_required": true,
        "definition_contract_digest": "ee21f4620afb568abbc9997a83456b1b0ec2ab3564773ff2705fa16d544c7215"
      },
      {
        "manifest_version": 1,
        "definition_id": "user-profile.censo-review",
        "action_reference": null,
        "request_schema": {
          "schema_id": "user-profile.censo-review.request",
          "schema_version": 1,
          "schema_fingerprint": "a79bf95d9685c28162798e7397ca7e40a684b51ed74558154f516cf42167b775"
        },
        "result_schema": {
          "schema_id": "user-profile.censo-review.result",
          "schema_version": 1,
          "schema_fingerprint": "ce8e818254bc049679d7185acbc4d7cb8af52a0c8e7eed5edd4c94689d1fe35b"
        },
        "review_projection_schema": {
          "schema_id": "user-profile.censo-review.projection",
          "schema_version": 1,
          "schema_fingerprint": "11d1412acb90291c21852235b5300cb04f6424e40e44b53283044e8e0bb25057"
        },
        "interaction_response_schema": {
          "schema_id": "user-profile.censo-review.response",
          "schema_version": 1,
          "schema_fingerprint": "3c796225c303770f8740c6b4a340cc4175e13def1fd0418d7e68cacbb8458fc8"
        },
        "workspace_refresh_target_schema": null,
        "interaction_kinds": [
          "review"
        ],
        "request_storage": "secure_reference",
        "durability": "resumable",
        "cancellation": "cooperative",
        "deadline": "cooperative",
        "replay": "resumable",
        "baseline": "exact_approval",
        "sensitive_input": "secure_reference",
        "conflict_scope": "definition_subject",
        "owned_resources": [
          "async_task"
        ],
        "permitted_effects": [
          "none",
          "updated",
          "unknown"
        ],
        "close_policy": "detach_allowed",
        "reconciliation_policy": "resume_from_checkpoint",
        "permitted_frontends": [
          "tui",
          "cli",
          "mcp"
        ],
        "ephemeral_secret_required": false,
        "definition_contract_digest": "17d8cb10dc2ad2b9b3b5c1fc43ee102393eae008f18fd400ad6efb1b25a3bc8b"
      },
      {
        "manifest_version": 1,
        "definition_id": "user-profile.field-mutation",
        "action_reference": null,
        "request_schema": {
          "schema_id": "user-profile.field-mutation.request",
          "schema_version": 1,
          "schema_fingerprint": "9808b7691d582d2d04ffe1be1c2025ee1c3f37655038f9aea705882996cf2081"
        },
        "result_schema": null,
        "review_projection_schema": null,
        "interaction_response_schema": null,
        "workspace_refresh_target_schema": null,
        "interaction_kinds": [],
        "request_storage": "secure_reference",
        "durability": "recorded",
        "cancellation": "unsupported",
        "deadline": "absent",
        "replay": "idempotent_submit",
        "baseline": "none",
        "sensitive_input": "secure_reference",
        "conflict_scope": "definition_subject",
        "owned_resources": [],
        "permitted_effects": [
          "none",
          "updated",
          "unknown"
        ],
        "close_policy": "detach_allowed",
        "reconciliation_policy": "interrupt",
        "permitted_frontends": [
          "tui",
          "cli",
          "mcp"
        ],
        "ephemeral_secret_required": false,
        "definition_contract_digest": "c5122bdc506f4ffc24d383f0302987a054fe1f6aa0effb4f203f62dacbad8c25"
      },
      {
        "manifest_version": 1,
        "definition_id": "user-profile.logout",
        "action_reference": null,
        "request_schema": {
          "schema_id": "user-profile.logout.request",
          "schema_version": 1,
          "schema_fingerprint": "5505fddba80965bbf3f642e9f25b6952625416268ae005d540b7d05debdf094b"
        },
        "result_schema": null,
        "review_projection_schema": null,
        "interaction_response_schema": null,
        "workspace_refresh_target_schema": null,
        "interaction_kinds": [],
        "request_storage": "secure_reference",
        "durability": "recorded",
        "cancellation": "unsupported",
        "deadline": "absent",
        "replay": "idempotent_submit",
        "baseline": "none",
        "sensitive_input": "secure_reference",
        "conflict_scope": "definition_subject",
        "owned_resources": [],
        "permitted_effects": [
          "none",
          "updated",
          "unknown"
        ],
        "close_policy": "detach_allowed",
        "reconciliation_policy": "interrupt",
        "permitted_frontends": [
          "tui",
          "cli",
          "mcp"
        ],
        "ephemeral_secret_required": false,
        "definition_contract_digest": "dd60aeecf193d53e34d42de3035ab62e252c24a70f7d710e920fd312d2ad1594"
      },
      {
        "manifest_version": 1,
        "definition_id": "user-profile.repeatable-row-mutation",
        "action_reference": null,
        "request_schema": {
          "schema_id": "user-profile.repeatable-row-mutation.request",
          "schema_version": 1,
          "schema_fingerprint": "437e08368f9a093ae5cb665136b1aa98602a85c875bed8855e1b69a08eb0e6d9"
        },
        "result_schema": null,
        "review_projection_schema": null,
        "interaction_response_schema": null,
        "workspace_refresh_target_schema": null,
        "interaction_kinds": [],
        "request_storage": "secure_reference",
        "durability": "recorded",
        "cancellation": "unsupported",
        "deadline": "absent",
        "replay": "idempotent_submit",
        "baseline": "none",
        "sensitive_input": "secure_reference",
        "conflict_scope": "definition_subject",
        "owned_resources": [],
        "permitted_effects": [
          "none",
          "updated",
          "unknown"
        ],
        "close_policy": "detach_allowed",
        "reconciliation_policy": "interrupt",
        "permitted_frontends": [
          "tui",
          "cli",
          "mcp"
        ],
        "ephemeral_secret_required": false,
        "definition_contract_digest": "637244c1b43ab87c5fac9b3ce02bc05d1b8cb43c7555f306f60006c4c9fcc82b"
      }
    ],
    "contract_set_digest": "2d406050000318f75ef8deffcb08e98417825111b891b4d7bc74ffab70dee74c"
  },
  "definition_digests": [
    {
      "definition_id": "auth.profile.login",
      "definition_contract_digest": "e9c8b2f5f125c1272f380017248885da4f19d7f3769595c80da63bc753bba22d"
    },
    {
      "definition_id": "auth.profile.passphrase-rotate",
      "definition_contract_digest": "5ba111b35bb184644e3d97a12abbc7de0eaee8a2528f2dde6a4db0a5230ffdfc"
    },
    {
      "definition_id": "auth.provider.configure",
      "definition_contract_digest": "6dfcdc35023c6b07899ce317bbc31b009d57a870affb8d73806e71a2f672b1ae"
    },
    {
      "definition_id": "auth.session.acquire",
      "definition_contract_digest": "7e12497bfacab773d3dc812fd334ae165ddb6be8996c01cb75d8827666ed8380"
    },
    {
      "definition_id": "auth.session.logout",
      "definition_contract_digest": "1ea85af2d9492fa4608d6457080b2005e280148ef100654712fb6f8e82f8ee25"
    },
    {
      "definition_id": "auth.session.reset",
      "definition_contract_digest": "82c7335a2b813e7cb478c301fe5ac5e90be01e8e03055a9466fb0e66d5bb4f97"
    },
    {
      "definition_id": "export.google-sheets",
      "definition_contract_digest": "049fcbe0eaa2f4312f2a23aa5def0c453ce688eaf61ee21f3eac51840427e51b"
    },
    {
      "definition_id": "live.filed-history.pull",
      "definition_contract_digest": "e27b502127f1897a3efce25ee248e20b34b9076e14b960f8c482b544a1f572f3"
    },
    {
      "definition_id": "user-profile.bundle-export",
      "definition_contract_digest": "ee21f4620afb568abbc9997a83456b1b0ec2ab3564773ff2705fa16d544c7215"
    },
    {
      "definition_id": "user-profile.censo-review",
      "definition_contract_digest": "17d8cb10dc2ad2b9b3b5c1fc43ee102393eae008f18fd400ad6efb1b25a3bc8b"
    },
    {
      "definition_id": "user-profile.field-mutation",
      "definition_contract_digest": "c5122bdc506f4ffc24d383f0302987a054fe1f6aa0effb4f203f62dacbad8c25"
    },
    {
      "definition_id": "user-profile.logout",
      "definition_contract_digest": "dd60aeecf193d53e34d42de3035ab62e252c24a70f7d710e920fd312d2ad1594"
    },
    {
      "definition_id": "user-profile.repeatable-row-mutation",
      "definition_contract_digest": "637244c1b43ab87c5fac9b3ce02bc05d1b8cb43c7555f306f60006c4c9fcc82b"
    }
  ],
  "schema_identities": [
    {
      "schema_id": "auth.profile.login.request",
      "schema_version": 1,
      "schema_fingerprint": "b6ebd607a813efc70382b868871f5d7f808917063182ade19e5ec008589fef03"
    },
    {
      "schema_id": "auth.profile.passphrase-rotate.request",
      "schema_version": 1,
      "schema_fingerprint": "f668218cc93e20912f7cbd53e7ec4086de21e35337bc6c8079bdd2437a7db07c"
    },
    {
      "schema_id": "auth.provider.configure.request",
      "schema_version": 1,
      "schema_fingerprint": "1638c6cdd64498b4cb715ea8813f11e0ae5b2c5b7705ca46c8081e9f5c078047"
    },
    {
      "schema_id": "auth.session.acquire.request",
      "schema_version": 1,
      "schema_fingerprint": "b7c4c7337f7259d130c50b1eb819f40ef97239c4742bd49182986b9f57298bfc"
    },
    {
      "schema_id": "auth.session.logout.request",
      "schema_version": 1,
      "schema_fingerprint": "2153481c560235f12bc157021016853d2e970a2766215c6cc8bf64bd281e84aa"
    },
    {
      "schema_id": "auth.session.reset.request",
      "schema_version": 1,
      "schema_fingerprint": "2153481c560235f12bc157021016853d2e970a2766215c6cc8bf64bd281e84aa"
    },
    {
      "schema_id": "export.google-sheets.request",
      "schema_version": 1,
      "schema_fingerprint": "390a027d7c8a80944a22444eefa5c21847989588164303cc1141298b5a66f68b"
    },
    {
      "schema_id": "live.filed-history.pull.request",
      "schema_version": 1,
      "schema_fingerprint": "eb313197977dada243e0b1cef92498796e1c02bf4ff4762cdefcc693aa92dff3"
    },
    {
      "schema_id": "user-profile.bundle-export.request",
      "schema_version": 1,
      "schema_fingerprint": "57623eab5986bfa69ace3e2dc68dd83875002c352ec067b56e3fc8c48f627fc9"
    },
    {
      "schema_id": "user-profile.censo-review.projection",
      "schema_version": 1,
      "schema_fingerprint": "11d1412acb90291c21852235b5300cb04f6424e40e44b53283044e8e0bb25057"
    },
    {
      "schema_id": "user-profile.censo-review.request",
      "schema_version": 1,
      "schema_fingerprint": "a79bf95d9685c28162798e7397ca7e40a684b51ed74558154f516cf42167b775"
    },
    {
      "schema_id": "user-profile.censo-review.response",
      "schema_version": 1,
      "schema_fingerprint": "3c796225c303770f8740c6b4a340cc4175e13def1fd0418d7e68cacbb8458fc8"
    },
    {
      "schema_id": "user-profile.censo-review.result",
      "schema_version": 1,
      "schema_fingerprint": "ce8e818254bc049679d7185acbc4d7cb8af52a0c8e7eed5edd4c94689d1fe35b"
    },
    {
      "schema_id": "user-profile.field-mutation.request",
      "schema_version": 1,
      "schema_fingerprint": "9808b7691d582d2d04ffe1be1c2025ee1c3f37655038f9aea705882996cf2081"
    },
    {
      "schema_id": "user-profile.logout.request",
      "schema_version": 1,
      "schema_fingerprint": "5505fddba80965bbf3f642e9f25b6952625416268ae005d540b7d05debdf094b"
    },
    {
      "schema_id": "user-profile.repeatable-row-mutation.request",
      "schema_version": 1,
      "schema_fingerprint": "437e08368f9a093ae5cb665136b1aa98602a85c875bed8855e1b69a08eb0e6d9"
    }
  ],
  "schema_manifest_digest": "5bcb798b0b222b98aad1d656e93818b29aee563da3fec5ebdabab52fbc33b964",
  "canonical_definitions": [
    "cadrumo.application.operations.capabilities:OperationBaselinePolicy",
    "cadrumo.application.operations.capabilities:OperationCapabilities",
    "cadrumo.application.operations.capabilities:OperationConflictScope",
    "cadrumo.application.operations.capabilities:OperationOwnedResource",
    "cadrumo.application.operations.capabilities:OperationReplayPolicy",
    "cadrumo.application.operations.capabilities:OperationRequestStoragePolicy",
    "cadrumo.application.operations.capabilities:OperationSensitiveInputPolicy",
    "cadrumo.application.operations.composition:OperationComposedServices",
    "cadrumo.application.operations.composition:OperationSubmission",
    "cadrumo.application.operations.composition:OperationSubmissionService",
    "cadrumo.application.operations.composition:compose_operation_services",
    "cadrumo.application.operations.event_replay:OperationEventCursor",
    "cadrumo.application.operations.events:OperationEventCode",
    "cadrumo.application.operations.events:OperationEventSequence",
    "cadrumo.application.operations.events:OperationLogSeverity",
    "cadrumo.application.operations.frontend_contracts:OperationCancellationRefusalCode",
    "cadrumo.application.operations.frontend_contracts:OperationCancellationRefusalV1",
    "cadrumo.application.operations.frontend_contracts:OperationCancellationRequestV1",
    "cadrumo.application.operations.frontend_contracts:OperationCancellationResultV1",
    "cadrumo.application.operations.frontend_contracts:OperationCancellationSuccessV1",
    "cadrumo.application.operations.frontend_contracts:OperationCancellationVersionHeader",
    "cadrumo.application.operations.frontend_contracts:OperationDetachRefusalCode",
    "cadrumo.application.operations.frontend_contracts:OperationDetachRefusalV1",
    "cadrumo.application.operations.frontend_contracts:OperationDetachRequestV1",
    "cadrumo.application.operations.frontend_contracts:OperationDetachResultV1",
    "cadrumo.application.operations.frontend_contracts:OperationDetachSuccessV1",
    "cadrumo.application.operations.frontend_contracts:OperationDetachVersionHeader",
    "cadrumo.application.operations.frontend_contracts:OperationNoPendingInteractionV1",
    "cadrumo.application.operations.frontend_contracts:OperationObservationRefusalCode",
    "cadrumo.application.operations.frontend_contracts:OperationObservationRefusalV1",
    "cadrumo.application.operations.frontend_contracts:OperationObservationRequestV1",
    "cadrumo.application.operations.frontend_contracts:OperationObservationResultV1",
    "cadrumo.application.operations.frontend_contracts:OperationObservationSuccessV1",
    "cadrumo.application.operations.frontend_contracts:OperationObservationVersionHeader",
    "cadrumo.application.operations.frontend_contracts:OperationPublicDiagnosticEventV1",
    "cadrumo.application.operations.frontend_contracts:OperationPublicEffectEventV1",
    "cadrumo.application.operations.frontend_contracts:OperationPublicEventPageV1",
    "cadrumo.application.operations.frontend_contracts:OperationPublicEventV1",
    "cadrumo.application.operations.frontend_contracts:OperationPublicInteractionEventV1",
    "cadrumo.application.operations.frontend_contracts:OperationPublicLogEventV1",
    "cadrumo.application.operations.frontend_contracts:OperationPublicNoticeEventV1",
    "cadrumo.application.operations.frontend_contracts:OperationPublicPendingInteractionV1",
    "cadrumo.application.operations.frontend_contracts:OperationPublicPhaseEventV1",
    "cadrumo.application.operations.frontend_contracts:OperationPublicProgressEventV1",
    "cadrumo.application.operations.frontend_contracts:OperationPublicProgressV1",
    "cadrumo.application.operations.frontend_contracts:OperationPublicProjectionV1",
    "cadrumo.application.operations.frontend_contracts:OperationPublicReconciliationEventV1",
    "cadrumo.application.operations.frontend_contracts:OperationPublicTerminalEventV1",
    "cadrumo.application.operations.frontend_contracts:OperationResponseApplyRequestV1",
    "cadrumo.application.operations.frontend_contracts:OperationResponseControlRefusalCode",
    "cadrumo.application.operations.frontend_contracts:OperationResponseControlRefusalV1",
    "cadrumo.application.operations.frontend_contracts:OperationResponseControlRequestV1",
    "cadrumo.application.operations.frontend_contracts:OperationResponseControlResultV1",
    "cadrumo.application.operations.frontend_contracts:OperationResponseControlSuccessV1",
    "cadrumo.application.operations.frontend_contracts:OperationResponseControlVersionHeader",
    "cadrumo.application.operations.frontend_contracts:OperationResponseMutationRequestV1",
    "cadrumo.application.operations.frontend_contracts:OperationResponseMutationResultV1",
    "cadrumo.application.operations.frontend_contracts:OperationResponseMutationSuccessV1",
    "cadrumo.application.operations.frontend_contracts:OperationResponseRejectRequestV1",
    "cadrumo.application.operations.frontend_contracts:OperationReviewAvailableInteractionV1",
    "cadrumo.application.operations.frontend_contracts:OperationReviewProjectionReferenceV1",
    "cadrumo.application.operations.frontend_contracts:OperationReviewProjectionRefusalCode",
    "cadrumo.application.operations.frontend_contracts:OperationReviewProjectionRefusalV1",
    "cadrumo.application.operations.frontend_contracts:OperationReviewProjectionRequestV1",
    "cadrumo.application.operations.frontend_contracts:OperationReviewProjectionResultV1",
    "cadrumo.application.operations.frontend_contracts:OperationReviewProjectionSuccessV1",
    "cadrumo.application.operations.frontend_contracts:OperationReviewProjectionVersionHeader",
    "cadrumo.application.operations.frontend_contracts:OperationSubmissionReceiptV1",
    "cadrumo.application.operations.frontend_contracts:OperationUnsupportedInteractionV1",
    "cadrumo.application.operations.frontend_contracts:OperationWorkspaceRefreshTargetRefusalCode",
    "cadrumo.application.operations.frontend_contracts:OperationWorkspaceRefreshTargetRefusalV1",
    "cadrumo.application.operations.frontend_contracts:OperationWorkspaceRefreshTargetRequestV1",
    "cadrumo.application.operations.frontend_contracts:OperationWorkspaceRefreshTargetResultV1",
    "cadrumo.application.operations.frontend_contracts:OperationWorkspaceRefreshTargetSuccessV1",
    "cadrumo.application.operations.frontend_contracts:OperationWorkspaceRefreshTargetVersionHeader",
    "cadrumo.application.operations.interactions:OperationActorReference",
    "cadrumo.application.operations.interactions:OperationApplyResponse",
    "cadrumo.application.operations.interactions:OperationConsumedInteraction",
    "cadrumo.application.operations.interactions:OperationInteractionId",
    "cadrumo.application.operations.interactions:OperationInteractionRequest",
    "cadrumo.application.operations.interactions:OperationInteractionResponse",
    "cadrumo.application.operations.interactions:OperationPendingInteraction",
    "cadrumo.application.operations.interactions:OperationRejectResponse",
    "cadrumo.application.operations.interactions:OperationResponseIntent",
    "cadrumo.application.operations.interactions:OperationResponseToken",
    "cadrumo.application.operations.models:CredentialFreeOperationRequest",
    "cadrumo.application.operations.models:OperationDefinitionId",
    "cadrumo.application.operations.models:OperationDiagnosticReference",
    "cadrumo.application.operations.models:OperationId",
    "cadrumo.application.operations.models:OperationIdentity",
    "cadrumo.application.operations.models:OperationReconciliationOutcome",
    "cadrumo.application.operations.models:OperationReference",
    "cadrumo.application.operations.models:OperationRequest",
    "cadrumo.application.operations.models:OperationRevision",
    "cadrumo.application.operations.models:OperationSnapshot",
    "cadrumo.application.operations.models:OperationTerminalReceipt",
    "cadrumo.application.operations.models:new_operation_id",
    "cadrumo.application.operations.observation:OperationObservationService",
    "cadrumo.application.operations.projection_services:BoundOperationSecureResponseAuthority",
    "cadrumo.application.operations.projection_services:OperationCancellationService",
    "cadrumo.application.operations.projection_services:OperationControlSupervisor",
    "cadrumo.application.operations.projection_services:OperationDetachService",
    "cadrumo.application.operations.projection_services:OperationResponseControlService",
    "cadrumo.application.operations.projection_services:OperationReviewProjectionService",
    "cadrumo.application.operations.projection_services:OperationSecureResponseAuthority",
    "cadrumo.application.operations.projection_services:OperationWorkspaceRefreshTargetService",
    "cadrumo.application.operations.registry:OperationDefinition",
    "cadrumo.application.operations.registry:OperationExecutorFactory",
    "cadrumo.application.operations.registry:OperationFrontendProjection",
    "cadrumo.application.operations.registry:OperationPublicContractSetV1",
    "cadrumo.application.operations.registry:OperationPublicDefinitionContractV1",
    "cadrumo.application.operations.registry:OperationPublicDefinitionRegistrationV1",
    "cadrumo.application.operations.registry:OperationPublicSchemaId",
    "cadrumo.application.operations.registry:OperationReconciliationPolicy",
    "cadrumo.application.operations.registry:OperationRegistry",
    "cadrumo.application.operations.registry:OperationReviewProjector",
    "cadrumo.application.operations.registry:OperationSchemaBindingV1",
    "cadrumo.application.operations.registry:OperationSchemaIdentityV1",
    "cadrumo.application.operations.registry:OperationWorkspaceRefreshAdapter",
    "cadrumo.application.operations.registry:operation_public_schema_reference",
    "cadrumo.application.operations.secret_submission:EphemeralSecretSubmission",
    "cadrumo.application.operations.secret_submission:OperationEphemeralSecretAccess",
    "cadrumo.application.operations.secret_submission:OperationEphemeralSecretDeclaration",
    "cadrumo.application.operations.secret_submission:OperationSecretKind",
    "cadrumo.application.operations.secret_submission:OperationSecretRequirement",
    "cadrumo.application.operations.supervisor:OperationSupervisor"
  ],
  "canonical_definition_digest": "9c30689100f9e3532e10ded60c8480c5aa68f866704d59299f0722cf4a55906d",
  "capability_inventory": [
    {
      "definition_id": "auth.profile.login",
      "definition_contract_digest": "e9c8b2f5f125c1272f380017248885da4f19d7f3769595c80da63bc753bba22d",
      "observation_version": 1,
      "review_projection_version": 1,
      "response_control_version": 1,
      "cancellation_version": 1,
      "detach_version": 1,
      "refresh_target_version": 1
    },
    {
      "definition_id": "auth.profile.passphrase-rotate",
      "definition_contract_digest": "5ba111b35bb184644e3d97a12abbc7de0eaee8a2528f2dde6a4db0a5230ffdfc",
      "observation_version": 1,
      "review_projection_version": 1,
      "response_control_version": 1,
      "cancellation_version": 1,
      "detach_version": 1,
      "refresh_target_version": 1
    },
    {
      "definition_id": "auth.provider.configure",
      "definition_contract_digest": "6dfcdc35023c6b07899ce317bbc31b009d57a870affb8d73806e71a2f672b1ae",
      "observation_version": 1,
      "review_projection_version": 1,
      "response_control_version": 1,
      "cancellation_version": 1,
      "detach_version": 1,
      "refresh_target_version": 1
    },
    {
      "definition_id": "auth.session.acquire",
      "definition_contract_digest": "7e12497bfacab773d3dc812fd334ae165ddb6be8996c01cb75d8827666ed8380",
      "observation_version": 1,
      "review_projection_version": 1,
      "response_control_version": 1,
      "cancellation_version": 1,
      "detach_version": 1,
      "refresh_target_version": 1
    },
    {
      "definition_id": "auth.session.logout",
      "definition_contract_digest": "1ea85af2d9492fa4608d6457080b2005e280148ef100654712fb6f8e82f8ee25",
      "observation_version": 1,
      "review_projection_version": 1,
      "response_control_version": 1,
      "cancellation_version": 1,
      "detach_version": 1,
      "refresh_target_version": 1
    },
    {
      "definition_id": "auth.session.reset",
      "definition_contract_digest": "82c7335a2b813e7cb478c301fe5ac5e90be01e8e03055a9466fb0e66d5bb4f97",
      "observation_version": 1,
      "review_projection_version": 1,
      "response_control_version": 1,
      "cancellation_version": 1,
      "detach_version": 1,
      "refresh_target_version": 1
    },
    {
      "definition_id": "export.google-sheets",
      "definition_contract_digest": "049fcbe0eaa2f4312f2a23aa5def0c453ce688eaf61ee21f3eac51840427e51b",
      "observation_version": 1,
      "review_projection_version": 1,
      "response_control_version": 1,
      "cancellation_version": 1,
      "detach_version": 1,
      "refresh_target_version": 1
    },
    {
      "definition_id": "live.filed-history.pull",
      "definition_contract_digest": "e27b502127f1897a3efce25ee248e20b34b9076e14b960f8c482b544a1f572f3",
      "observation_version": 1,
      "review_projection_version": 1,
      "response_control_version": 1,
      "cancellation_version": 1,
      "detach_version": 1,
      "refresh_target_version": 1
    },
    {
      "definition_id": "user-profile.bundle-export",
      "definition_contract_digest": "ee21f4620afb568abbc9997a83456b1b0ec2ab3564773ff2705fa16d544c7215",
      "observation_version": 1,
      "review_projection_version": 1,
      "response_control_version": 1,
      "cancellation_version": 1,
      "detach_version": 1,
      "refresh_target_version": 1
    },
    {
      "definition_id": "user-profile.censo-review",
      "definition_contract_digest": "17d8cb10dc2ad2b9b3b5c1fc43ee102393eae008f18fd400ad6efb1b25a3bc8b",
      "observation_version": 1,
      "review_projection_version": 1,
      "response_control_version": 1,
      "cancellation_version": 1,
      "detach_version": 1,
      "refresh_target_version": 1
    },
    {
      "definition_id": "user-profile.field-mutation",
      "definition_contract_digest": "c5122bdc506f4ffc24d383f0302987a054fe1f6aa0effb4f203f62dacbad8c25",
      "observation_version": 1,
      "review_projection_version": 1,
      "response_control_version": 1,
      "cancellation_version": 1,
      "detach_version": 1,
      "refresh_target_version": 1
    },
    {
      "definition_id": "user-profile.logout",
      "definition_contract_digest": "dd60aeecf193d53e34d42de3035ab62e252c24a70f7d710e920fd312d2ad1594",
      "observation_version": 1,
      "review_projection_version": 1,
      "response_control_version": 1,
      "cancellation_version": 1,
      "detach_version": 1,
      "refresh_target_version": 1
    },
    {
      "definition_id": "user-profile.repeatable-row-mutation",
      "definition_contract_digest": "637244c1b43ab87c5fac9b3ce02bc05d1b8cb43c7555f306f60006c4c9fcc82b",
      "observation_version": 1,
      "review_projection_version": 1,
      "response_control_version": 1,
      "cancellation_version": 1,
      "detach_version": 1,
      "refresh_target_version": 1
    }
  ],
  "capability_inventory_digest": "4a79161ced26b22247a9791a5dd2096420114f5d396239a76e6f1d18ff205544",
  "semantic_producer_census": {
    "schema_version": 1,
    "tool_name": "vaultspec-rag",
    "result_schema": "vaultspec-rag.search.code.v1",
    "tool_version": "vaultspec-rag v0.4.2",
    "query": "public operation observation immutable snapshot progress fold safe review workspace refresh authority only:prod exclude:tests",
    "disposition": "success",
    "source_tree_digest": "6ee7ad99bd18eacb521533412ab986e00cbeb52cd1ae9daaa40ccb0c7fa3ee2b",
    "discovered_paths": [
      "src/cadrumo/application/operations/composition.py",
      "src/cadrumo/application/operations/frontend_contracts.py",
      "src/cadrumo/application/operations/models.py",
      "src/cadrumo/application/operations/observation.py",
      "src/cadrumo/application/operations/persistence/journal.py",
      "src/cadrumo/application/operations/projection_services.py",
      "src/cadrumo/application/operations/registry.py"
    ],
    "result_digest": "5a421e8c9765ffcb971242005f4d4bae2b78cdb565e62f6708182ddf1b450746"
  },
  "proofs": [
    {
      "proof_id": "atomic_interleaving",
      "source_path": "src/cadrumo/adapters/persistence/operations/tests/test_journal.py",
      "test_function": "test_operation_observation_is_one_locked_record_under_a_real_interleaved_transition",
      "source_digest": "a3cd4b64612b2d93b5bd224ed8095cb9d0312197beb3959b8a3916214ffd84c2"
    },
    {
      "proof_id": "current_only_deletion",
      "source_path": "src/cadrumo/adapters/persistence/operations/tests/test_journal.py",
      "test_function": "test_operation_journal_refuses_every_superseded_snapshot_schema_without_byte_mutation",
      "source_digest": "a3cd4b64612b2d93b5bd224ed8095cb9d0312197beb3959b8a3916214ffd84c2"
    },
    {
      "proof_id": "digest_drift_refusal",
      "source_path": "src/cadrumo/application/operations/tests/test_observation.py",
      "test_function": "test_observation_returns_closed_safe_refusals",
      "source_digest": "544585c9af6b890628c2335663f97b2c1c3e7100a41051fcf06ba723f594dcca"
    },
    {
      "proof_id": "production_di",
      "source_path": "src/cadrumo/entrypoints/tests/test_operation_composition.py",
      "test_function": "test_production_composition_reaches_the_owner_registry_fixed_point",
      "source_digest": "056e2a08f9546ae46d1a97da46efedf3648bcd1ad67f7e6beb91ae92844afacb"
    },
    {
      "proof_id": "progress_replay",
      "source_path": "src/cadrumo/application/operations/tests/test_observation.py",
      "test_function": "test_observation_resynchronization_replaces_progress_from_authoritative_checkpoint",
      "source_digest": "544585c9af6b890628c2335663f97b2c1c3e7100a41051fcf06ba723f594dcca"
    },
    {
      "proof_id": "restart_refresh",
      "source_path": "src/cadrumo/application/operations/tests/test_projection_services.py",
      "test_function": "test_refresh_target_resolves_only_authoritative_successful_terminal_receipt",
      "source_digest": "e9fec8199710bfbf9a5c22fe3ebc64cef123a9aa0c4d548af45038aec22c637d"
    },
    {
      "proof_id": "review_non_authority",
      "source_path": "src/cadrumo/application/operations/tests/test_projection_services.py",
      "test_function": "test_review_resolution_uses_encrypted_operand_and_is_read_only",
      "source_digest": "e9fec8199710bfbf9a5c22fe3ebc64cef123a9aa0c4d548af45038aec22c637d"
    },
    {
      "proof_id": "sentinel_non_retention",
      "source_path": "src/cadrumo/adapters/persistence/operations/tests/test_ephemeral_secret_submission.py",
      "test_function": "test_exact_one_shot_submission_executes_once_and_never_reaches_filesystem",
      "source_digest": "c2ad9b74e8dc87351681203be28ea28498650158bdc4da82661e43fc7856343e"
    },
    {
      "proof_id": "strict_round_trip",
      "source_path": "src/cadrumo/application/operations/tests/test_journal.py",
      "test_function": "test_observation_materialization_binds_snapshot_replay_and_progress_to_one_anchor",
      "source_digest": "d0a001d639cab4833945de67872eba8adc70d1ef73931891bca9965e32bea1db"
    }
  ]
}
