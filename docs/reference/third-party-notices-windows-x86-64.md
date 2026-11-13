<!-- GENERATED FILE - DO NOT EDIT.
Regenerate with: uv run --no-sync python -m dev.packaging.native.third_party_notices --target windows-x86-64 --build <the CMake binary directory>
Source of truth: the package the assembly stages -->

# Third-party notices (windows-x86-64)

This page lists every third-party component the windows-x86-64 package installs,
with its version, the licence it declares and where the package carries the
licence text. Package assembly refuses to build while this page differs from
what it stages, while a listed licence text is missing, and while any
component declares the GNU General Public License or the GNU Affero General
Public License.

## Interpreter, programs and runtimes

| Component | Version | Licence | Licence text in the package |
| --- | --- | --- | --- |
| CPython, with the libraries of its build | 3.13.11 | PSF-2.0, with the notices of the libraries it bundles | `docs/licenses/CPython.txt` |
| llama.cpp: llama-server and the llama, ggml and mtmd libraries | b12184 | MIT | `docs/licenses/llama.cpp/LICENSE` |
| LLVM OpenMP runtime (libomp.dll) from the llama.cpp release | b12184 | Apache-2.0 WITH LLVM-exception | `docs/licenses/llama.cpp/LICENSE-LLVM-OpenMP` |
| Microsoft Visual C++ runtime (msvcp140.dll, vcruntime140.dll, vcruntime140_1.dll) | 14.44.35112 | Microsoft Visual C++ Redistributable terms | none shipped |
| Node.js, the agent runtime | 26.12.1 | MIT | `cadrumo/node/LICENSE` |
| Node.js, the Playwright driver | as shipped in playwright 1.64.1 | MIT | `cadrumo/site-packages/playwright/driver/LICENSE` |

## Python distributions

| Component | Version | Licence | Licence text in the package |
| --- | --- | --- | --- |
| aiosqlite | 0.22.1 | MIT License | `cadrumo/site-packages/aiosqlite-0.22.1.dist-info` |
| alembic | 1.20.0 | MIT | `cadrumo/site-packages/alembic-1.20.0.dist-info` |
| annotated-doc | 0.0.5 | MIT | `cadrumo/site-packages/annotated_doc-0.0.5.dist-info` |
| annotated-types | 0.8.0 | MIT | `cadrumo/site-packages/annotated_types-0.8.0.dist-info` |
| anthropic | 1.13.0 | MIT License | `cadrumo/site-packages/anthropic-1.13.0.dist-info` |
| anyio | 4.16.0 | MIT | `cadrumo/site-packages/anyio-4.16.0.dist-info` |
| argon2-cffi | 25.1.0 | MIT | `cadrumo/site-packages/argon2_cffi-25.1.0.dist-info` |
| argon2-cffi-bindings | 26.1.0 | MIT | `cadrumo/site-packages/argon2_cffi_bindings-26.1.0.dist-info` |
| attrs | 26.1.0 | MIT | `cadrumo/site-packages/attrs-26.1.0.dist-info` |
| beautifulsoup4 | 4.15.0 | MIT License | `cadrumo/site-packages/beautifulsoup4-4.15.0.dist-info` |
| certifi | 2026.10.23 | Mozilla Public License 2.0 (MPL 2.0) | `cadrumo/site-packages/certifi-2026.10.23.dist-info` |
| cffi | 2.1.1 | MIT-0 | `cadrumo/site-packages/cffi-2.1.1.dist-info` |
| charset-normalizer | 3.5.2 | MIT | `cadrumo/site-packages/charset_normalizer-3.5.2.dist-info` |
| click | 8.5.0 | BSD-3-Clause | `cadrumo/site-packages/click-8.5.0.dist-info` |
| colorama | 0.4.6 | BSD License | `cadrumo/site-packages/colorama-0.4.6.dist-info` |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | `cadrumo/site-packages/cryptography-50.0.2.dist-info` |
| defusedxml | 0.7.1 | Python Software Foundation License | `cadrumo/site-packages/defusedxml-0.7.1.dist-info` |
| distro | 1.9.0 | Apache Software License | `cadrumo/site-packages/distro-1.9.0.dist-info` |
| docstring-parser | 0.18.0 | MIT License | `cadrumo/site-packages/docstring_parser-0.18.0.dist-info` |
| et-xmlfile | 2.0.0 | MIT License | `cadrumo/site-packages/et_xmlfile-2.0.0.dist-info` |
| fastapi | 0.143.3 | MIT | `cadrumo/site-packages/fastapi-0.143.3.dist-info` |
| google-api-core | 2.43.2 | Apache Software License | `cadrumo/site-packages/google_api_core-2.43.2.dist-info` |
| google-api-python-client | 2.201.0 | Apache Software License | `cadrumo/site-packages/google_api_python_client-2.201.0.dist-info` |
| google-auth | 2.62.0 | Apache Software License | `cadrumo/site-packages/google_auth-2.62.0.dist-info` |
| google-auth-httplib2 | 0.4.4 | Apache Software License | `cadrumo/site-packages/google_auth_httplib2-0.4.4.dist-info` |
| google-auth-oauthlib | 1.5.0 | Apache Software License | `cadrumo/site-packages/google_auth_oauthlib-1.5.0.dist-info` |
| googleapis-common-protos | 1.76.0 | Apache-2.0 | `cadrumo/site-packages/googleapis_common_protos-1.76.0.dist-info` |
| greenlet | 3.5.6 | MIT AND PSF-2.0 | `cadrumo/site-packages/greenlet-3.5.6.dist-info` |
| h11 | 0.16.0 | MIT License | `cadrumo/site-packages/h11-0.16.0.dist-info` |
| httpcore | 1.0.9 | BSD-3-Clause | `cadrumo/site-packages/httpcore-1.0.9.dist-info` |
| httpcore2 | 2.16.0 | BSD-3-Clause | `cadrumo/site-packages/httpcore2-2.16.0.dist-info` |
| httplib2 | 0.32.1 | MIT License | `cadrumo/site-packages/httplib2-0.32.1.dist-info` |
| httpx | 0.28.1 | BSD License | `cadrumo/site-packages/httpx-0.28.1.dist-info` |
| httpx2 | 2.16.0 | BSD-3-Clause | `cadrumo/site-packages/httpx2-2.16.0.dist-info` |
| idna | 3.20 | BSD-3-Clause | `cadrumo/site-packages/idna-3.20.dist-info` |
| jaraco-classes | 3.4.0 | MIT License | `cadrumo/site-packages/jaraco.classes-3.4.0.dist-info` |
| jaraco-context | 6.1.2 | MIT | `cadrumo/site-packages/jaraco_context-6.1.2.dist-info` |
| jaraco-functools | 4.6.0 | MIT | `cadrumo/site-packages/jaraco_functools-4.6.0.dist-info` |
| jiter | 0.17.0 | MIT | `cadrumo/site-packages/jiter-0.17.0.dist-info` |
| jsonpatch | 1.35 | BSD-3-Clause | `cadrumo/site-packages/jsonpatch-1.35.dist-info` |
| jsonpointer | 3.2.1 | BSD License | `cadrumo/site-packages/jsonpointer-3.2.1.dist-info` |
| jsonschema | 4.26.0 | MIT | `cadrumo/site-packages/jsonschema-4.26.0.dist-info` |
| jsonschema-specifications | 2025.9.1 | MIT | `cadrumo/site-packages/jsonschema_specifications-2025.9.1.dist-info` |
| keyring | 25.7.0 | MIT | `cadrumo/site-packages/keyring-25.7.0.dist-info` |
| langchain-core | 1.6.12 | MIT License | `cadrumo/site-packages/langchain_core-1.6.12.dist-info` |
| langchain-openai | 1.7.2 | MIT License | `cadrumo/site-packages/langchain_openai-1.7.2.dist-info` |
| langchain-protocol | 0.0.19 | MIT License | `cadrumo/site-packages/langchain_protocol-0.0.19.dist-info` |
| langgraph | 1.2.16 | MIT | `cadrumo/site-packages/langgraph-1.2.16.dist-info` |
| langgraph-checkpoint | 4.3.0 | MIT | `cadrumo/site-packages/langgraph_checkpoint-4.3.0.dist-info` |
| langgraph-checkpoint-sqlite | 3.1.2 | MIT | `cadrumo/site-packages/langgraph_checkpoint_sqlite-3.1.2.dist-info` |
| langgraph-prebuilt | 1.1.1 | MIT | `cadrumo/site-packages/langgraph_prebuilt-1.1.1.dist-info` |
| langgraph-sdk | 0.4.8 | MIT | `cadrumo/site-packages/langgraph_sdk-0.4.8.dist-info` |
| langsmith | 0.14.11 | MIT License | `cadrumo/site-packages/langsmith-0.14.11.dist-info` |
| linkify-it-py | 2.2.0 | MIT License | `cadrumo/site-packages/linkify_it_py-2.2.0.dist-info` |
| lxml | 6.1.3 | BSD-3-Clause | `cadrumo/site-packages/lxml-6.1.3.dist-info` |
| mako | 1.4.3 | MIT | `cadrumo/site-packages/mako-1.4.3.dist-info` |
| markdown-it-py | 4.2.0 | MIT License | `cadrumo/site-packages/markdown_it_py-4.2.0.dist-info` |
| markupsafe | 3.0.4 | BSD-3-Clause | `cadrumo/site-packages/markupsafe-3.0.4.dist-info` |
| mcp | 2.3.0 | MIT License | `cadrumo/site-packages/mcp-2.3.0.dist-info` |
| mcp-types | 2.3.0 | MIT License | `cadrumo/site-packages/mcp_types-2.3.0.dist-info` |
| mdit-py-plugins | 0.6.1 | MIT License | `cadrumo/site-packages/mdit_py_plugins-0.6.1.dist-info` |
| mdurl | 0.1.2 | MIT License | `cadrumo/site-packages/mdurl-0.1.2.dist-info` |
| more-itertools | 11.2.1 | MIT | `cadrumo/site-packages/more_itertools-11.2.1.dist-info` |
| oauthlib | 4.0.1 | BSD-3-Clause | `cadrumo/site-packages/oauthlib-4.0.1.dist-info` |
| openai | 3.29.0 | Apache-2.0 | `cadrumo/site-packages/openai-3.29.0.dist-info` |
| openpyxl | 3.1.5 | MIT License | `cadrumo/site-packages/openpyxl-3.1.5.dist-info` |
| opentelemetry-api | 1.45.2 | Apache-2.0 | `cadrumo/site-packages/opentelemetry_api-1.45.2.dist-info` |
| opentelemetry-sdk | 1.45.2 | Apache-2.0 | `cadrumo/site-packages/opentelemetry_sdk-1.45.2.dist-info` |
| opentelemetry-semantic-conventions | 0.66b2 | Apache-2.0 | `cadrumo/site-packages/opentelemetry_semantic_conventions-0.66b2.dist-info` |
| orjson | 3.13.0 | MPL-2.0 AND (Apache-2.0 OR MIT) | `cadrumo/site-packages/orjson-3.13.0.dist-info` |
| ormsgpack | 1.13.0 | Apache-2.0 OR MIT | `cadrumo/site-packages/ormsgpack-1.13.0.dist-info` |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | `cadrumo/site-packages/packaging-26.3.dist-info` |
| pdfminer-six | 20260107 | MIT | `cadrumo/site-packages/pdfminer_six-20260107.dist-info` |
| pdfplumber | 0.11.10 | MIT License | `cadrumo/site-packages/pdfplumber-0.11.10.dist-info` |
| pikepdf | 10.17.0 | MPL-2.0 | `cadrumo/site-packages/pikepdf-10.17.0.dist-info` |
| pillow | 13.0.0 | MIT-CMU | `cadrumo/site-packages/pillow-13.0.0.dist-info` |
| platformdirs | 4.14.2 | MIT | `cadrumo/site-packages/platformdirs-4.14.2.dist-info` |
| playwright | 1.64.1 | Apache-2.0 | `cadrumo/site-packages/playwright-1.64.1.dist-info` |
| playwright-stealth | 2.0.3 | MIT | `cadrumo/site-packages/playwright_stealth-2.0.3.dist-info` |
| prompt-toolkit | 3.0.53 | BSD License | `cadrumo/site-packages/prompt_toolkit-3.0.53.dist-info` |
| proto-plus | 1.29.0 | Apache Software License | `cadrumo/site-packages/proto_plus-1.29.0.dist-info` |
| protobuf | 7.36.2 | 3-Clause BSD License | `cadrumo/site-packages/protobuf-7.36.2.dist-info` |
| psutil | 7.2.2 | BSD-3-Clause | `cadrumo/site-packages/psutil-7.2.2.dist-info` |
| pyasn1 | 0.6.5 | BSD-2-Clause | `cadrumo/site-packages/pyasn1-0.6.5.dist-info` |
| pyasn1-modules | 0.4.2 | BSD License | `cadrumo/site-packages/pyasn1_modules-0.4.2.dist-info` |
| pycparser | 3.12 | BSD-3-Clause | `cadrumo/site-packages/pycparser-3.12.dist-info` |
| pydantic | 2.14.2 | MIT | `cadrumo/site-packages/pydantic-2.14.2.dist-info` |
| pydantic-core | 2.50.2 | MIT | `cadrumo/site-packages/pydantic_core-2.50.2.dist-info` |
| pydantic-settings | 2.16.2 | MIT | `cadrumo/site-packages/pydantic_settings-2.16.2.dist-info` |
| pyee | 14.0.0 | MIT License | `cadrumo/site-packages/pyee-14.0.0.dist-info` |
| pygments | 2.21.0 | BSD-2-Clause | `cadrumo/site-packages/pygments-2.21.0.dist-info` |
| pyjwt | 2.15.1 | MIT | `cadrumo/site-packages/pyjwt-2.15.1.dist-info` |
| pyparsing | 3.3.3 | MIT | `cadrumo/site-packages/pyparsing-3.3.3.dist-info` |
| pypdfium2 | 5.14.0 | BSD-3-Clause, Apache-2.0, dependency licenses | `cadrumo/site-packages/pypdfium2-5.14.0.dist-info` |
| python-dotenv | 1.2.4 | BSD-3-Clause | `cadrumo/site-packages/python_dotenv-1.2.4.dist-info` |
| python-i18n | 0.3.9 | MIT License | `cadrumo/site-packages/python_i18n-0.3.9.dist-info` |
| python-multipart | 0.0.33 | Apache-2.0 | `cadrumo/site-packages/python_multipart-0.0.33.dist-info` |
| pywin32 | 312 | Python Software Foundation License | `cadrumo/site-packages/pywin32-312.dist-info` |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause | `cadrumo/site-packages/pywin32_ctypes-0.2.3.dist-info` |
| pyyaml | 6.0.3 | MIT License | `cadrumo/site-packages/pyyaml-6.0.3.dist-info` |
| questionary | 2.1.1 | MIT License | `cadrumo/site-packages/questionary-2.1.1.dist-info` |
| referencing | 0.37.0 | MIT | `cadrumo/site-packages/referencing-0.37.0.dist-info` |
| regex | 2026.9.29 | Apache-2.0 AND CNRI-Python | `cadrumo/site-packages/regex-2026.9.29.dist-info` |
| reportlab | 5.1.0 | BSD License | `cadrumo/site-packages/reportlab-5.1.0.dist-info` |
| requests | 2.34.2 | Apache Software License | `cadrumo/site-packages/requests-2.34.2.dist-info` |
| requests-oauthlib | 2.0.0 | BSD License | `cadrumo/site-packages/requests_oauthlib-2.0.0.dist-info` |
| requests-toolbelt | 1.0.0 | Apache Software License | `cadrumo/site-packages/requests_toolbelt-1.0.0.dist-info` |
| rich | 15.0.0 | MIT License | `cadrumo/site-packages/rich-15.0.0.dist-info` |
| rpds-py | 2026.9.1 | MIT | `cadrumo/site-packages/rpds_py-2026.9.1.dist-info` |
| rtoml | 0.14.0 | MIT License | `cadrumo/site-packages/rtoml-0.14.0.dist-info` |
| shellingham | 1.5.4 | ISC License (ISCL) | `cadrumo/site-packages/shellingham-1.5.4.dist-info` |
| sniffio | 1.3.1 | Apache Software License / MIT License | `cadrumo/site-packages/sniffio-1.3.1.dist-info` |
| snowballstemmer | 3.1.1 | BSD-3-Clause | `cadrumo/site-packages/snowballstemmer-3.1.1.dist-info` |
| soupsieve | 3.0.4 | MIT | `cadrumo/site-packages/soupsieve-3.0.4.dist-info` |
| sqlalchemy | 2.1.6 | MIT | `cadrumo/site-packages/sqlalchemy-2.1.6.dist-info` |
| sqlite-vec | 0.1.9 | MIT License, Apache License, Version 2.0 | `cadrumo/site-packages/sqlite_vec-0.1.9.dist-info` |
| sse-starlette | 3.6.0 | BSD-3-Clause | `cadrumo/site-packages/sse_starlette-3.6.0.dist-info` |
| starlette | 1.10.0 | BSD-3-Clause | `cadrumo/site-packages/starlette-1.10.0.dist-info` |
| tenacity | 9.2.1 | Apache-2.0 | `cadrumo/site-packages/tenacity-9.2.1.dist-info` |
| textual | 8.2.8 | MIT License | `cadrumo/site-packages/textual-8.2.8.dist-info` |
| tiktoken | 0.14.0 | stated in LICENSE | `cadrumo/site-packages/tiktoken-0.14.0.dist-info` |
| truststore | 0.10.5 | MIT | `cadrumo/site-packages/truststore-0.10.5.dist-info` |
| typer | 0.29.0 | MIT | `cadrumo/site-packages/typer-0.29.0.dist-info` |
| typing-extensions | 4.16.0 | PSF-2.0 | `cadrumo/site-packages/typing_extensions-4.16.0.dist-info` |
| typing-inspection | 0.4.4 | MIT | `cadrumo/site-packages/typing_inspection-0.4.4.dist-info` |
| tzdata | 2026.6 | Apache-2.0 | `cadrumo/site-packages/tzdata-2026.6.dist-info` |
| uritemplate | 4.2.0 | BSD 3-Clause OR Apache-2.0 | `cadrumo/site-packages/uritemplate-4.2.0.dist-info` |
| urllib3 | 2.8.0 | MIT | `cadrumo/site-packages/urllib3-2.8.0.dist-info` |
| uuid-utils | 0.17.1 | BSD-3-Clause | `cadrumo/site-packages/uuid_utils-0.17.1.dist-info` |
| uvicorn | 0.54.0 | BSD-3-Clause | `cadrumo/site-packages/uvicorn-0.54.0.dist-info` |
| wcwidth | 0.9.4 | MIT License | `cadrumo/site-packages/wcwidth-0.9.4.dist-info` |
| websockets | 16.1.1 | BSD-3-Clause | `cadrumo/site-packages/websockets-16.1.1.dist-info` |
| xlrd | 2.0.2 | BSD License | `cadrumo/site-packages/xlrd-2.0.2.dist-info` |
| xxhash | 4.0.1 | BSD-2-Clause | `cadrumo/site-packages/xxhash-4.0.1.dist-info` |
| zstandard | 0.25.0 | BSD-3-Clause | `cadrumo/site-packages/zstandard-0.25.0.dist-info` |

## JavaScript packages of the agent runtime

| Component | Version | Licence | Licence text in the package |
| --- | --- | --- | --- |
| @agentclientprotocol/claude-agent-acp | 0.93.0 | Apache-2.0 | `cadrumo/node_modules/@agentclientprotocol/claude-agent-acp` |
| @agentclientprotocol/sdk | 1.9.0 | Apache-2.0 | `cadrumo/node_modules/@agentclientprotocol/sdk` |
| @anthropic-ai/claude-agent-sdk | 0.3.300 | SEE LICENSE IN README.md | `cadrumo/node_modules/@anthropic-ai/claude-agent-sdk` |
| @anthropic-ai/sdk | 0.135.0 | MIT | `cadrumo/node_modules/@anthropic-ai/sdk` |
| @babel/runtime | 7.29.10 | MIT | `cadrumo/node_modules/@babel/runtime` |
| @hono/node-server | 2.1.5 | MIT | `cadrumo/node_modules/@hono/node-server` |
| @modelcontextprotocol/sdk | 1.32.1 | MIT | `cadrumo/node_modules/@modelcontextprotocol/sdk` |
| @opentelemetry/api | 1.9.1 | Apache-2.0 | `cadrumo/node_modules/@opentelemetry/api` |
| @stablelib/base64 | 1.0.1 | MIT | `cadrumo/node_modules/@stablelib/base64` |
| accepts | 2.0.0 | MIT | `cadrumo/node_modules/accepts` |
| ajv | 8.20.0 | MIT | `cadrumo/node_modules/ajv` |
| ajv-formats | 3.0.1 | MIT | `cadrumo/node_modules/ajv-formats` |
| body-parser | 2.4.0 | MIT | `cadrumo/node_modules/body-parser` |
| content-type | 2.1.0 | MIT | `cadrumo/node_modules/body-parser/node_modules/content-type` |
| bytes | 3.1.2 | MIT | `cadrumo/node_modules/bytes` |
| call-bind-apply-helpers | 1.0.2 | MIT | `cadrumo/node_modules/call-bind-apply-helpers` |
| call-bound | 1.0.4 | MIT | `cadrumo/node_modules/call-bound` |
| content-disposition | 2.0.1 | MIT | `cadrumo/node_modules/content-disposition` |
| content-type | 1.0.5 | MIT | `cadrumo/node_modules/content-type` |
| cookie | 0.7.2 | MIT | `cadrumo/node_modules/cookie` |
| cookie-signature | 1.2.2 | MIT | `cadrumo/node_modules/cookie-signature` |
| cors | 2.8.6 | MIT | `cadrumo/node_modules/cors` |
| cross-spawn | 7.0.6 | MIT | `cadrumo/node_modules/cross-spawn` |
| debug | 4.4.3 | MIT | `cadrumo/node_modules/debug` |
| depd | 2.0.0 | MIT | `cadrumo/node_modules/depd` |
| diff | 9.0.0 | BSD-3-Clause | `cadrumo/node_modules/diff` |
| dunder-proto | 1.0.1 | MIT | `cadrumo/node_modules/dunder-proto` |
| ee-first | 1.1.1 | MIT | `cadrumo/node_modules/ee-first` |
| encodeurl | 2.0.0 | MIT | `cadrumo/node_modules/encodeurl` |
| es-define-property | 1.0.1 | MIT | `cadrumo/node_modules/es-define-property` |
| es-errors | 1.3.0 | MIT | `cadrumo/node_modules/es-errors` |
| es-object-atoms | 1.1.2 | MIT | `cadrumo/node_modules/es-object-atoms` |
| escape-html | 1.0.3 | MIT | `cadrumo/node_modules/escape-html` |
| etag | 1.8.1 | MIT | `cadrumo/node_modules/etag` |
| eventsource | 3.0.7 | MIT | `cadrumo/node_modules/eventsource` |
| eventsource-parser | 3.1.1 | MIT | `cadrumo/node_modules/eventsource-parser` |
| express | 5.3.0 | MIT | `cadrumo/node_modules/express` |
| express-rate-limit | 8.7.1 | MIT | `cadrumo/node_modules/express-rate-limit` |
| content-type | 2.1.0 | MIT | `cadrumo/node_modules/express/node_modules/content-type` |
| fast-deep-equal | 3.1.3 | MIT | `cadrumo/node_modules/fast-deep-equal` |
| fast-sha256 | 1.3.0 | Unlicense | `cadrumo/node_modules/fast-sha256` |
| fast-uri | 3.1.9 | BSD-3-Clause | `cadrumo/node_modules/fast-uri` |
| finalhandler | 2.1.1 | MIT | `cadrumo/node_modules/finalhandler` |
| forwarded | 0.2.0 | MIT | `cadrumo/node_modules/forwarded` |
| fresh | 2.0.0 | MIT | `cadrumo/node_modules/fresh` |
| function-bind | 1.1.2 | MIT | `cadrumo/node_modules/function-bind` |
| get-intrinsic | 1.3.0 | MIT | `cadrumo/node_modules/get-intrinsic` |
| get-proto | 1.0.1 | MIT | `cadrumo/node_modules/get-proto` |
| gopd | 1.2.0 | MIT | `cadrumo/node_modules/gopd` |
| has-symbols | 1.1.0 | MIT | `cadrumo/node_modules/has-symbols` |
| hasown | 2.0.4 | MIT | `cadrumo/node_modules/hasown` |
| hono | 4.13.13 | MIT | `cadrumo/node_modules/hono` |
| http-errors | 2.0.1 | MIT | `cadrumo/node_modules/http-errors` |
| iconv-lite | 0.7.3 | MIT | `cadrumo/node_modules/iconv-lite` |
| inherits | 2.0.4 | ISC | `cadrumo/node_modules/inherits` |
| ip-address | 10.7.4 | MIT | `cadrumo/node_modules/ip-address` |
| ipaddr.js | 1.9.1 | MIT | `cadrumo/node_modules/ipaddr.js` |
| is-promise | 4.0.0 | MIT | `cadrumo/node_modules/is-promise` |
| isexe | 2.0.0 | ISC | `cadrumo/node_modules/isexe` |
| jose | 6.2.12 | MIT | `cadrumo/node_modules/jose` |
| json-schema-to-ts | 3.1.1 | MIT | `cadrumo/node_modules/json-schema-to-ts` |
| json-schema-traverse | 1.0.0 | MIT | `cadrumo/node_modules/json-schema-traverse` |
| json-schema-typed | 8.0.2 | BSD-2-Clause | `cadrumo/node_modules/json-schema-typed` |
| math-intrinsics | 1.1.0 | MIT | `cadrumo/node_modules/math-intrinsics` |
| media-typer | 1.1.1 | MIT | `cadrumo/node_modules/media-typer` |
| merge-descriptors | 2.0.0 | MIT | `cadrumo/node_modules/merge-descriptors` |
| mime-db | 1.54.0 | MIT | `cadrumo/node_modules/mime-db` |
| mime-types | 3.0.2 | MIT | `cadrumo/node_modules/mime-types` |
| ms | 2.1.3 | MIT | `cadrumo/node_modules/ms` |
| negotiator | 1.1.0 | MIT | `cadrumo/node_modules/negotiator` |
| content-type | 2.1.0 | MIT | `cadrumo/node_modules/negotiator/node_modules/content-type` |
| object-assign | 4.1.1 | MIT | `cadrumo/node_modules/object-assign` |
| object-inspect | 1.13.4 | MIT | `cadrumo/node_modules/object-inspect` |
| on-finished | 2.4.1 | MIT | `cadrumo/node_modules/on-finished` |
| once | 1.4.0 | ISC | `cadrumo/node_modules/once` |
| parseurl | 1.3.3 | MIT | `cadrumo/node_modules/parseurl` |
| path-key | 3.1.1 | MIT | `cadrumo/node_modules/path-key` |
| path-to-regexp | 8.4.2 | MIT | `cadrumo/node_modules/path-to-regexp` |
| pkce-challenge | 5.0.1 | MIT | `cadrumo/node_modules/pkce-challenge` |
| proxy-addr | 2.0.8 | MIT | `cadrumo/node_modules/proxy-addr` |
| qs | 6.16.1 | BSD-3-Clause | `cadrumo/node_modules/qs` |
| range-parser | 1.3.0 | MIT | `cadrumo/node_modules/range-parser` |
| raw-body | 3.0.2 | MIT | `cadrumo/node_modules/raw-body` |
| require-from-string | 2.0.2 | MIT | `cadrumo/node_modules/require-from-string` |
| router | 2.2.0 | MIT | `cadrumo/node_modules/router` |
| safer-buffer | 2.1.2 | MIT | `cadrumo/node_modules/safer-buffer` |
| send | 1.2.1 | MIT | `cadrumo/node_modules/send` |
| serve-static | 2.2.1 | MIT | `cadrumo/node_modules/serve-static` |
| setprototypeof | 1.2.0 | ISC | `cadrumo/node_modules/setprototypeof` |
| shebang-command | 2.0.0 | MIT | `cadrumo/node_modules/shebang-command` |
| shebang-regex | 3.0.0 | MIT | `cadrumo/node_modules/shebang-regex` |
| side-channel | 1.1.1 | MIT | `cadrumo/node_modules/side-channel` |
| side-channel-list | 1.0.1 | MIT | `cadrumo/node_modules/side-channel-list` |
| side-channel-map | 1.0.1 | MIT | `cadrumo/node_modules/side-channel-map` |
| side-channel-weakmap | 1.0.2 | MIT | `cadrumo/node_modules/side-channel-weakmap` |
| standardwebhooks | 1.1.1 | MIT | `cadrumo/node_modules/standardwebhooks` |
| statuses | 2.0.2 | MIT | `cadrumo/node_modules/statuses` |
| toidentifier | 1.0.1 | MIT | `cadrumo/node_modules/toidentifier` |
| ts-algebra | 2.0.0 | MIT | `cadrumo/node_modules/ts-algebra` |
| type-is | 2.1.0 | MIT | `cadrumo/node_modules/type-is` |
| content-type | 2.1.0 | MIT | `cadrumo/node_modules/type-is/node_modules/content-type` |
| unpipe | 1.0.0 | MIT | `cadrumo/node_modules/unpipe` |
| vary | 1.1.2 | MIT | `cadrumo/node_modules/vary` |
| which | 2.0.2 | ISC | `cadrumo/node_modules/which` |
| wrappy | 1.0.2 | ISC | `cadrumo/node_modules/wrappy` |
| zod | 4.6.7 | MIT | `cadrumo/node_modules/zod` |
| zod-to-json-schema | 3.25.2 | ISC | `cadrumo/node_modules/zod-to-json-schema` |
