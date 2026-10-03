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

int wmain(int argc, wchar_t **argv) {
    if (argc == 2 && (!wcscmp(argv[1], L"--version") || !wcscmp(argv[1], L"-V"))) {
        printf("CADRUMO %s build %s (%s), Python %s [%s]\n", CADRUMO_VERSION,
            CADRUMO_BUILD_NUMBER, CADRUMO_BUILD_DATE, CADRUMO_PYTHON_VERSION,
            CADRUMO_DEVELOPMENT ? "development" : "production");
        return 0;
    }
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
    if (cadrumo_platform_prepare(ctx, &error)) goto failure;
    if (argc == 2 && !wcscmp(argv[1], L"--check-package")) {
        wchar_t *check[] = {argv[0], L"-c", L"import _cadrumo_bootstrap; _cadrumo_bootstrap.verify(full=True); print('CADRUMO package verified')"};
        result = run(3, check, (const wchar_t **)paths, CADRUMO_DEVELOPMENT);
    } else {
        result = run(argc, argv, (const wchar_t **)paths, CADRUMO_DEVELOPMENT);
    }
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
