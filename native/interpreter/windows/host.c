#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
#include "cadrumo_platform.h"
#include "contract.h"
#include "build_metadata.h"
#ifndef CADRUMO_DEVELOPMENT
#define CADRUMO_DEVELOPMENT 0
#endif
#define WIDE_LITERAL_(value) L##value
#define WIDE_LITERAL(value) WIDE_LITERAL_(value)

typedef int (__cdecl *bridge_main)(int, wchar_t **, const wchar_t **, int);

#ifndef CADRUMO_ENTRYPOINT
static int worker_handle(const wchar_t *text, uintptr_t *out) {
    uintptr_t value = 0;
    /* The supervisor serializes two distinct positive HANDLEs in decimal. */
    if (*text < L'1' || *text > L'9') return 0;
    for (const wchar_t *cursor = text; *cursor; ++cursor) {
        if (*cursor < L'0' || *cursor > L'9') return 0;
        uintptr_t digit = (uintptr_t)(*cursor - L'0');
        if (value > (UINTPTR_MAX - digit) / 10) return 0;
        value = value * 10 + digit;
    }
    if (value == UINTPTR_MAX) return 0;
    *out = value;
    return 1;
}

static int supervised_kdf_invocation(int argc, wchar_t **argv) {
    uintptr_t request = 0, result = 0;
    return argc == 7
        && !wcscmp(argv[1], L"-m")
        && !wcscmp(argv[2], L"cadrumo.adapters.persistence.storage.custody._kdf_worker")
        && !wcscmp(argv[3], L"--request-handle")
        && worker_handle(argv[4], &request)
        && !wcscmp(argv[5], L"--result-handle")
        && worker_handle(argv[6], &result)
        && request != result;
}
#endif

static wchar_t *path(cadrumo_context *ctx, uint32_t key) {
    cadrumo_buffer value = {0};
    if (cadrumo_platform_path(ctx, key, &value)) return NULL;
    int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
        (char *)value.data, (int)value.len, NULL, 0);
    wchar_t *result = count ? calloc((size_t)count + 1, sizeof(wchar_t)) : NULL;
    if (result) MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
        (char *)value.data, (int)value.len, result, count);
    cadrumo_platform_release(&value);
    return result;
}

#ifdef CADRUMO_ENTRYPOINT
/* A console entrypoint runs one declared console script through the package
 * interpreter. sys.executable remains that interpreter: runtime workers and the
 * supervised KDF child relaunch sys.executable with interpreter arguments. */
static int run_entrypoint(bridge_main run, int argc, wchar_t **argv, wchar_t **paths) {
    static const wchar_t command[] = L"import _cadrumo_bootstrap; _cadrumo_bootstrap.run_entrypoint('"
        WIDE_LITERAL(CADRUMO_ENTRYPOINT) L"')";
    size_t size = wcslen(paths[0]) + wcslen(WIDE_LITERAL(CADRUMO_EXECUTABLE)) + 2;
    wchar_t *interpreter = calloc(size, sizeof(wchar_t));
    wchar_t **forwarded = calloc((size_t)argc + 2, sizeof(wchar_t *));
    int result = 123;
    if (interpreter && forwarded
        && swprintf_s(interpreter, size, L"%ls\\%ls", paths[0], WIDE_LITERAL(CADRUMO_EXECUTABLE)) >= 0) {
        free(paths[2]);
        paths[2] = interpreter;
        interpreter = NULL;
        forwarded[0] = paths[2];
        forwarded[1] = L"-c";
        forwarded[2] = (wchar_t *)command;
        for (int i = 1; i < argc; ++i) forwarded[i + 2] = argv[i];
        result = run(argc + 2, forwarded, (const wchar_t **)paths, CADRUMO_DEVELOPMENT);
    } else {
        fprintf(stderr, "CADRUMO: cannot prepare the %s entrypoint\n", CADRUMO_ENTRYPOINT);
    }
    free(interpreter);
    free(forwarded);
    return result;
}
#endif

int wmain(int argc, wchar_t **argv) {
#ifndef CADRUMO_ENTRYPOINT
    if (argc == 2 && (!wcscmp(argv[1], L"--version") || !wcscmp(argv[1], L"-V"))) {
        printf("CADRUMO %s build %s (%s), Python %s [%s]\n", CADRUMO_VERSION,
            CADRUMO_BUILD_NUMBER, CADRUMO_BUILD_DATE, CADRUMO_PYTHON_VERSION,
            CADRUMO_DEVELOPMENT ? "development" : "production");
        return 0;
    }
#endif
    cadrumo_context *ctx = NULL;
    cadrumo_buffer error = {0};
    wchar_t *paths[10] = {0};
    wchar_t library[32768];
    int result = 120;
    if (cadrumo_platform_abi() != CADRUMO_PLATFORM_ABI ||
        cadrumo_platform_create(CADRUMO_PLATFORM_ABI, &ctx, &error)) goto failure;
    for (uint32_t i = 0; i < 10; ++i) {
        paths[i] = path(ctx, i);
        if (!paths[i]) goto failure;
    }
    if (!SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_SYSTEM32 | LOAD_LIBRARY_SEARCH_USER_DIRS) ||
        !AddDllDirectory(paths[5])) goto failure;
    if (swprintf_s(library, 32768, L"%ls\\%ls", paths[5], WIDE_LITERAL(CADRUMO_RUNTIME)) < 0) goto failure;
    if (!LoadLibraryExW(library, NULL, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32)) {
        fprintf(stderr, "CADRUMO: missing or incompatible bundled CPython DLL (Windows error %lu)\n", GetLastError());
        goto done;
    }
    if (swprintf_s(library, 32768, L"%ls\\%ls", paths[5], WIDE_LITERAL(CADRUMO_BRIDGE)) < 0) goto failure;
    HMODULE bridge = LoadLibraryExW(library, NULL,
        LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!bridge) goto failure;
    bridge_main run = (bridge_main)(void *)GetProcAddress(bridge, "cadrumo_python_main");
    if (!run) goto failure;
#ifdef CADRUMO_ENTRYPOINT
    if (cadrumo_platform_prepare(ctx, &error)) goto failure;
    result = run_entrypoint(run, argc, argv, paths);
#else
    /* The supervised KDF child attests its exact parent-owned neutral environment
     * before receiving any request. Application storage/tool projection would
     * replace that contract. Only its complete fixed invocation avoids projection;
     * context paths, isolated Python and package verification remain identical. */
    if (!supervised_kdf_invocation(argc, argv) && cadrumo_platform_prepare(ctx, &error)) goto failure;
    if (argc == 2 && !wcscmp(argv[1], L"--check-package")) {
        wchar_t *check[] = {argv[0], L"-c", L"import _cadrumo_bootstrap; _cadrumo_bootstrap.verify(full=True); print('CADRUMO package verified')"};
        result = run(3, check, (const wchar_t **)paths, CADRUMO_DEVELOPMENT);
    } else {
        result = run(argc, argv, (const wchar_t **)paths, CADRUMO_DEVELOPMENT);
    }
#endif
    goto done;
failure:
    if (error.data) fprintf(stderr, "CADRUMO: %.*s\n", (int)error.len, error.data);
    else fprintf(stderr, "CADRUMO: native bootstrap failed (Windows error %lu)\n", GetLastError());
done:
    cadrumo_platform_release(&error);
    cadrumo_platform_destroy(ctx);
    for (int i = 0; i < 10; ++i) free(paths[i]);
    return result;
}
