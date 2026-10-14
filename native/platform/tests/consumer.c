#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#endif
#include "cadrumo_platform.h"
#include "contract.h"
#define CADRUMO_CONSUMER_IMAGE CADRUMO_LAUNCH_IMAGE_PYTHON

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

    /* Launch-profile definition: invalid arguments, an undeclared image, the kdf-child's
     * unchanged parent environment, then the generic interpreter's closed environment. */
    assert(cadrumo_platform_define(NULL, CADRUMO_CONSUMER_IMAGE, 0, NULL, &error) == 2);
    assert(cadrumo_platform_create(1, &ctx, &error) == 0);
    assert(cadrumo_platform_define(ctx, NULL, 0, NULL, &error) == 2);
    assert(cadrumo_platform_define(ctx, CADRUMO_CONSUMER_IMAGE, 1, NULL, &error) == 2);
    assert(cadrumo_platform_define(ctx, "undeclared-image", 0, NULL, &error) == 3);
    assert(error.data != NULL && error.len > 0);
    cadrumo_platform_release(&error);
#ifdef _WIN32
    const cadrumo_native_char *kdf[] = {(const cadrumo_native_char *)L"-S", (const cadrumo_native_char *)L"-m",
        (const cadrumo_native_char *)L"cadrumo.adapters.persistence.storage.custody._kdf_worker",
        (const cadrumo_native_char *)L"--request-handle", (const cadrumo_native_char *)L"5",
        (const cadrumo_native_char *)L"--result-handle", (const cadrumo_native_char *)L"6"};
    assert(SetEnvironmentVariableA("CADRUMO_CONSUMER_MARKER", "kept"));
#else
    const cadrumo_native_char *kdf[] = {"-m", "cadrumo.adapters.persistence.storage.custody._kdf_worker",
        "--request-fd", "3", "--result-fd", "4", "--descriptor-bound", "1024"};
    assert(setenv("CADRUMO_CONSUMER_MARKER", "kept", 1) == 0);
#endif
    assert(cadrumo_platform_define(ctx, CADRUMO_CONSUMER_IMAGE, sizeof kdf / sizeof kdf[0], kdf, &error) == 0);
    assert(error.data == NULL && environment_matches("CADRUMO_CONSUMER_MARKER", "kept"));
    assert(cadrumo_platform_define(ctx, CADRUMO_CONSUMER_IMAGE, 0, NULL, &error) == 0);
    assert(error.data == NULL && environment_matches("CADRUMO_CONSUMER_MARKER", NULL));
    assert(!environment_matches("PATH", NULL));
    /* An agent invocation whose option lacks its value is refused as undeclared, with the one
     * refusal line, before anything is defined. */
    static const char refusal[] = "{\"native_refusal\":\"invocation_undeclared\",\"subject\":\"cadrumo-agent\"}";
#ifdef _WIN32
    const cadrumo_native_char *migrate[] = {(const cadrumo_native_char *)L"-m",
        (const cadrumo_native_char *)L"cadrumo_agent.cli.main", (const cadrumo_native_char *)L"migrate",
        (const cadrumo_native_char *)L"--expect-from"};
#else
    const cadrumo_native_char *migrate[] = {"-m", "cadrumo_agent.cli.main", "migrate", "--expect-from"};
#endif
    assert(cadrumo_platform_define(ctx, CADRUMO_LAUNCH_IMAGE_CADRUMO_AGENT, sizeof migrate / sizeof migrate[0], migrate, &error) == 4);
    assert(error.len == sizeof refusal - 1 && memcmp(error.data, refusal, sizeof refusal - 1) == 0);
    cadrumo_platform_release(&error);
    assert(environment_matches("CADRUMO_CONSUMER_MARKER", NULL));
    cadrumo_platform_destroy(ctx);
    puts("C consumer ABI 1: statuses, path keys, provider buffers and launch definition pass");
    return 0;
}
