---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:b93be0aecef729f445784e2ff2739158cce64c5511c332a3a1abda640bfe7456'
step_id: 'S18'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Mark casilla_continuidad_evolutions as a chain family and delete every family_dispositions entry declared for it across revision.toml files in one change

## Scope

- `src/cadrumo/domain/calculations/registry/schema.py`
- `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/revision.toml`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/_data/registry/aeat/modelos/036/revisions/2025-02-03-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/038/revisions/2024-desde-06/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/038/revisions/2025-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/111/revisions/2019-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/115/revisions/2019-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/117/revisions/2019-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/122/revisions/2017-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/123/revisions/2019-2023/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/126/revisions/2019-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/128/revisions/2019-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/131/revisions/2019-2023/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/136/revisions/2026/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/145/revisions/2012-01-31-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/156/revisions/2003-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/165/revisions/2013-2015/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/165/revisions/2016-2022/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/165/revisions/2023-2025/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/165/revisions/2026-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2019-2022/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/181/revisions/2022-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/182/revisions/2025/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2025-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/185/revisions/2003-2025/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/187/revisions/2022-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/188/revisions/2023-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/189/revisions/2025/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/190/revisions/2024/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/190/revisions/2025-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/193/revisions/2024/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/193/revisions/2025-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/194/revisions/2019/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/194/revisions/2023/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/194/revisions/2024/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/202/revisions/2019-2022/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/202/revisions/2023-2024/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2025/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2026-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/216/revisions/2024-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/220/revisions/2024/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/220/revisions/2025/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/222/revisions/2025-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/270/revisions/2013-2022/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/270/revisions/2023-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/280/revisions/2025/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/296/revisions/2024-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2022/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2024-desde-09-y-3t/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2024-hasta-08-y-2t/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2025/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/308/revisions/2009-2011-junio/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/308/revisions/2011-julio-2015/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/308/revisions/2016-2018/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/308/revisions/2019-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/309/revisions/2004-2015/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/309/revisions/2016-2017/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/309/revisions/2018-2022/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/309/revisions/2023-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2008-2022/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2023/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2024-2025/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2026-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/341/revisions/2005-2015/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/345/revisions/2025/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2011-2024/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2025-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/353/revisions/2021-2025/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/353/revisions/2026-desde-02/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/369/revisions/esquema-exterior/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/369/revisions/esquema-importacion/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/369/revisions/esquema-union/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2021/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/490/revisions/2021/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/490/revisions/2022-1t/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/490/revisions/2022-2t-4t/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/490/revisions/2023-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/576/revisions/2007/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/576/revisions/2008-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/604/revisions/2021-2023/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/604/revisions/2024-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/714/revisions/2021/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/714/revisions/2022/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/714/revisions/2023/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/714/revisions/2024/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/714/revisions/2025/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/720/revisions/2013-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/721/revisions/2023/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/721/revisions/2024/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/763/revisions/2012-2t-3t/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/763/revisions/2013-2014/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/763/revisions/2015-2017/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/763/revisions/2018-1t-3t/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/763/revisions/2018-4t/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/763/revisions/2019-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/revision.toml`
- `verify:` `load_modelo_directory over all 58 modelo directories` -> `pass`
