#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#endif
#include "cadrumo_platform.h"

static int environment_matches(const char *name, const char *expected) {
#ifdef _WIN32
    SetLastError(ERROR_SUCCESS);
    DWORD size = GetEnvironmentVariableA(name, NULL, 0);
    if (size == 0) {
        return expected == NULL && GetLastError() == ERROR_ENVVAR_NOT_FOUND;
    }
    char *value = malloc(size);
    assert(value != NULL);
    DWORD length = GetEnvironmentVariableA(name, value, size);
    assert(length > 0 && length < size);
    int matches = expected != NULL && strcmp(value, expected) == 0;
    free(value);
    return matches;
#else
    const char *value = getenv(name);
    return expected == NULL ? value == NULL : value != NULL && strcmp(value, expected) == 0;
#endif
}

int main(int argc, char **argv) {
    cadrumo_context *ctx = NULL;
    cadrumo_buffer error = {0}, path = {0};
    assert(cadrumo_platform_abi() == 1);
    if ((argc == 2 || argc == 3 || argc == 5) && strcmp(argv[1], "--expect-create-refusal") == 0) {
        if (argc == 5) assert(environment_matches(argv[3], argv[4]));
        assert(cadrumo_platform_create(1, &ctx, &error) == 3);
        assert(ctx == NULL && error.data != NULL && error.len > 0);
        if (argc >= 3) {
            size_t expected = strlen(argv[2]);
            assert(error.len > expected && memcmp(error.data, argv[2], expected) == 0);
        }
        if (argc == 5) assert(environment_matches(argv[3], argv[4]));
        cadrumo_platform_release(&error);
        assert(error.data == NULL && error.len == 0);
        puts("C consumer ABI 1: create refusal and error buffer pass");
        return 0;
    }
    if (argc == 4 && strcmp(argv[1], "--expect-prepare-refusal") == 0) {
        assert(environment_matches(argv[2], argv[3]));
        assert(cadrumo_platform_create(1, &ctx, &error) == 0);
        assert(cadrumo_platform_prepare(ctx, &error) == 3);
        assert(error.data != NULL && error.len > 0);
        assert(environment_matches(argv[2], argv[3]));
        cadrumo_platform_release(&error);
        cadrumo_platform_destroy(ctx);
        puts("C consumer ABI 1: prepare refusal preserves ambient environment");
        return 0;
    }
    if (argc == 4 && strcmp(argv[1], "--expect-prepare-success") == 0) {
        assert(environment_matches(argv[2], argv[3]));
        assert(cadrumo_platform_create(1, &ctx, &error) == 0);
        assert(cadrumo_platform_prepare(ctx, &error) == 0);
        assert(error.data == NULL && error.len == 0);
        assert(environment_matches(argv[2], NULL));
        cadrumo_platform_release(&error);
        cadrumo_platform_destroy(ctx);
        puts("C consumer ABI 1: prepare succeeds and clears generated-prefix marker");
        return 0;
    }
    assert(cadrumo_platform_create(2, &ctx, &error) == 1);
    assert(ctx == NULL && error.len > 0);
    assert(error.len == strlen("Incompatible platform ABI"));
    assert(memcmp(error.data, "Incompatible platform ABI", error.len) == 0);
    cadrumo_platform_release(&error);
    cadrumo_platform_release(&error);
    assert(error.data == NULL && error.len == 0);
    assert(cadrumo_platform_create(1, NULL, &error) == 2);
    assert(cadrumo_platform_create(1, &ctx, NULL) == 2);
    assert(cadrumo_platform_path(NULL, 0, &path) == 2);
    assert(cadrumo_platform_prepare(NULL, &error) == 2);
    assert(cadrumo_platform_create(1, &ctx, &error) == 0);
    for (uint32_t key = 0; key < CADRUMO_PATH_KEYS; ++key) {
        assert(cadrumo_platform_path(ctx, key, &path) == 0);
        assert(path.data != NULL && path.len > 0);
        cadrumo_platform_release(&path);
    }
    assert(cadrumo_platform_path(ctx, UINT32_MAX, &path) == 2);
    assert(path.data == NULL && path.len == 0);
    assert(cadrumo_platform_path(ctx, 1, &path) == 0);
    cadrumo_platform_destroy(ctx);
    assert(path.data != NULL && path.len > 0);
    cadrumo_platform_release(&path);
    cadrumo_platform_release(&path);
    assert(path.data == NULL && path.len == 0);
    cadrumo_platform_release(NULL);
    cadrumo_platform_destroy(NULL);
    puts("C consumer ABI 1: statuses, path keys and provider buffers pass");
    return 0;
}
