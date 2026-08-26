---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:62b7ecc53ada14beb2e8af42e720ab7960968807b490fce9b52c05c1537cf53b'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# `agent-harness-refoundation` ledger

## Changes

- `S01` `T` `src/aeat/entrypoints/mcp/_input_schema.py`
- `S02` `T` `src/aeat/entrypoints/mcp/_tools.py`
- `S03` `T` `src/aeat/entrypoints/mcp/_toolsets.py`
- `S04` `T` `src/aeat/entrypoints/mcp/_annotations.py`
- `S05` `T` `src/aeat/entrypoints/mcp/tests/test_tools_and_dispatch.py`
- `S06` `T` `src/aeat/entrypoints/mcp/_meta_tools.py`
- `S07` `T` `src/aeat/entrypoints/mcp/_server.py`
- `S08` `T` `src/aeat/entrypoints/mcp/tests/test_meta_tools.py`
- `S09` `T` `src/aeat/entrypoints/mcp/_harness_tools.py`
- `S10` `T` `src/aeat/entrypoints/mcp/_resources.py`
- `S11` `T` `src/aeat/entrypoints/mcp/_server.py`
- `S12` `T` `src/aeat/entrypoints/mcp/tests/test_harness_delivery.py`
- `S13` `T` `src/aeat/entrypoints/mcp/_prompts.py`
- `S14` `T` `src/aeat/entrypoints/mcp/_server.py`
- `S15` `T` `src/aeat/agent/_workspace.py`
- `S16` `T` `src/aeat/entrypoints/cli/_app_agent_workspace.py`
- `S17` `T` `src/aeat/entrypoints/mcp/tests/test_prompts.py`
- `S18` `T` `src/aeat/agent/tests/test_workspace.py`
- `S19` `T` `src/aeat/entrypoints/mcp/_elicitation.py`
- `S20` `T` `src/aeat/entrypoints/mcp/_server.py`
- `S21` `T` `src/aeat/entrypoints/mcp/tests/test_elicitation.py`
- `S22` `T` `src/aeat/entrypoints/mcp/_faithfulness.py`
- `S23` `T` `src/aeat/entrypoints/mcp/_server.py`
- `S24` `T` `src/aeat/entrypoints/mcp/_persona_scope.py`
- `S25` `T` `src/aeat/entrypoints/mcp/_telemetry.py`
- `S26` `T` `src/aeat/entrypoints/mcp/tests/test_serving_gates.py`
- `S27` `T` `src/aeat/entrypoints/mcp/tests/test_client_handshake.py`
- `S28` `T` `src/aeat/agent/eval/_live_harness.py`
- `S29` `T` `src/aeat/agent/eval/_live_scoring.py`
- `S30` `T` `src/aeat/agent/eval/_models.py`
- `S31` `T` `src/aeat/agent/eval/_flywheel.py`
- `S32` `T` `src/aeat/agent/eval/_report.py`
- `S33` `T` `src/aeat/agent/eval/tests/test_live_harness.py`
- `S34` `T` `src/aeat/agent/_skill_metadata.py`
- `S35` `T` `src/aeat/agent/__init__.py`
- `S36` `T` `src/aeat/agent/tests/test_skill_applies_when.py`
- `S37` `T` `src/aeat/_data/agent/skills/alta-contribuyente/SKILL.md`
- `S38` `T` `src/aeat/_data/agent/skills/arrendador/SKILL.md`
- `S39` `T` `src/aeat/_data/agent/skills/autonomo-estimacion-directa/SKILL.md`
- `S40` `T` `src/aeat/_data/agent/skills/autonomo-modulos/SKILL.md`
- `S41` `T` `src/aeat/_data/agent/skills/clasificar/SKILL.md`
- `S42` `T` `src/aeat/_data/agent/skills/exportar-declaracion/SKILL.md`
- `S43` `T` `src/aeat/_data/agent/skills/intra-community-operator/SKILL.md`
- `S44` `T` `src/aeat/_data/agent/skills/llevar-libro/SKILL.md`
- `S45` `T` `src/aeat/_data/agent/skills/preparar-modelo-100/SKILL.md`
- `S46` `T` `src/aeat/_data/agent/skills/preparar-modelo-111/SKILL.md`
- `S47` `T` `src/aeat/_data/agent/skills/preparar-modelo-115/SKILL.md`
- `S48` `T` `src/aeat/_data/agent/skills/preparar-modelo-130/SKILL.md`
- `S49` `T` `src/aeat/_data/agent/skills/preparar-modelo-131/SKILL.md`
- `S50` `T` `src/aeat/_data/agent/skills/preparar-modelo-180/SKILL.md`
- `S51` `T` `src/aeat/_data/agent/skills/preparar-modelo-190/SKILL.md`
- `S52` `T` `src/aeat/_data/agent/skills/preparar-modelo-193/SKILL.md`
- `S53` `T` `src/aeat/_data/agent/skills/preparar-modelo-200/SKILL.md`
- `S54` `T` `src/aeat/_data/agent/skills/preparar-modelo-202/SKILL.md`
- `S55` `T` `src/aeat/_data/agent/skills/preparar-modelo-303/SKILL.md`
- `S56` `T` `src/aeat/_data/agent/skills/preparar-modelo-309/SKILL.md`
- `S57` `T` `src/aeat/_data/agent/skills/preparar-modelo-322/SKILL.md`
- `S58` `T` `src/aeat/_data/agent/skills/preparar-modelo-349/SKILL.md`
- `S59` `T` `src/aeat/_data/agent/skills/preparar-modelo-353/SKILL.md`
- `S60` `T` `src/aeat/_data/agent/skills/preparar-modelo-369/SKILL.md`
- `S61` `T` `src/aeat/_data/agent/skills/preparar-modelo-390/SKILL.md`
- `S62` `T` `src/aeat/_data/agent/skills/pyme-sociedad/SKILL.md`
- `S63` `T` `src/aeat/_data/agent/skills/reconciliar/SKILL.md`
- `S64` `T` `src/aeat/_data/agent/skills/retenedor-empleador/SKILL.md`
- `S65` `T` `src/aeat/_data/agent/skills/regularizar-atrasos/SKILL.md`
- `S66` `T` `src/aeat/agent/eval/scenarios/regularizar_atrasos.toml`
- `S67` `T` `src/aeat/_data/agent/skills/cierre-trimestre/SKILL.md`
- `S68` `T` `src/aeat/agent/eval/scenarios/cierre_trimestre.toml`
- `S69` `T` `src/aeat/_data/agent/skills/resumen-anual/SKILL.md`
- `S70` `T` `src/aeat/agent/eval/scenarios/resumen_anual.toml`
- `S71` `T` `src/aeat/_data/agent/skills/rectificar-declaracion/SKILL.md`
- `S72` `T` `src/aeat/agent/eval/scenarios/rectificar_declaracion.toml`
- `S73` `T` `src/aeat/_data/agent/skills/inicio-actividad/SKILL.md`
- `S74` `T` `src/aeat/agent/eval/scenarios/inicio_actividad.toml`
- `S75` `T` `src/aeat/_data/agent/skills/cese-actividad/SKILL.md`
- `S76` `T` `src/aeat/agent/eval/scenarios/cese_actividad.toml`
- `S77` `T` `src/aeat/application/corpus_search/_lexical_index.py`
- `S78` `T` `src/aeat/application/corpus_search/_citation_lookup.py`
- `S79` `T` `src/aeat/application/corpus_search/_embed_build.py`
- `S80` `T` `src/aeat/application/corpus_search/_query_embed.py`
- `S81` `T` `src/aeat/entrypoints/mcp/_corpus_tools.py`
- `S82` `T` `src/aeat/entrypoints/mcp/_resources.py`
- `S83` `T` `src/aeat/entrypoints/mcp/_terminology_tools.py`
- `S84` `T` `src/aeat/application/corpus_search/tests/test_retrieval.py`
- `S85` `T` `packaging/mcpb/manifest.json`
- `S86` `T` `packaging/mcpb/build.py`
- `S87` `T` `src/aeat/application/corpus_search/tests/test_search_shippability.py`
- `S88` `T` `src/aeat/application/corpus_search/_retrieval.py`
- `S89` `T` `pyproject.toml`
- `S90` `T` `src/aeat/application/corpus_search/THIRD_PARTY_NOTICES.md`
