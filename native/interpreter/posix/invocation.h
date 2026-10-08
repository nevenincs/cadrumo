#ifndef CADRUMO_POSIX_INVOCATION_H
#define CADRUMO_POSIX_INVOCATION_H
#include <limits.h>
#include <string.h>

static int descriptor_number(const char *text, int *out) {
    int value = 0;
    if (*text < '1' || *text > '9') return 0;
    for (const char *cursor = text; *cursor; ++cursor) {
        if (*cursor < '0' || *cursor > '9') return 0;
        int digit = *cursor - '0';
        if (value > (INT_MAX - digit) / 10) return 0;
        value = value * 10 + digit;
    }
    *out = value;
    return 1;
}

static int supervised_kdf_invocation(int argc, char **argv) {
    int request = 0, result = 0, bound = 0;
    return argc == 9
        && !strcmp(argv[1], "-m")
        && !strcmp(argv[2], "cadrumo.adapters.persistence.storage.custody._kdf_worker")
        && !strcmp(argv[3], "--request-fd") && descriptor_number(argv[4], &request)
        && !strcmp(argv[5], "--result-fd") && descriptor_number(argv[6], &result)
        && !strcmp(argv[7], "--descriptor-bound") && descriptor_number(argv[8], &bound)
        && request > 2 && result > 2 && request != result && bound > request && bound > result;
}
#endif
