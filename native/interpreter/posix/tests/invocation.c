#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "../../launch_profile.h"

static const char refusal[] = "{\"native_refusal\":\"invocation_undeclared\",\"subject\":\"cadrumo-agent\"}";

int main(void) {
    cadrumo_context *ctx = NULL;
    cadrumo_buffer error = {0};
    assert(cadrumo_platform_create(1, &ctx, &error) == 0);

    /* The refusal line is written whole and flushed as the last standard-error line. */
    FILE *capture = tmpfile();
    assert(capture != NULL);
    int saved = dup(2);
    assert(saved >= 0 && dup2(fileno(capture), 2) == 2);
    cadrumo_buffer line = {(uint8_t *)refusal, sizeof refusal - 1};
    write_launch_refusal(&line);
    assert(dup2(saved, 2) == 2);
    close(saved);
    char written[256] = {0};
    rewind(capture);
    assert(fgets(written, sizeof written, capture) != NULL);
    assert(strlen(written) == sizeof refusal && memcmp(written, refusal, sizeof refusal - 1) == 0);
    assert(written[sizeof refusal - 1] == '\n' && fgetc(capture) == EOF);
    fclose(capture);

    /* The declared supervised KDF invocation keeps its parent-defined environment. */
    char *kdf[] = {"python", "-m", "cadrumo.adapters.persistence.storage.custody._kdf_worker",
        "--request-fd", "3", "--result-fd", "4", "--descriptor-bound", "1024", NULL};
    assert(setenv("CADRUMO_INVOCATION_MARKER", "kept", 1) == 0);
    assert(define_launch(ctx, 9, kdf, &error) == 0);
    assert(error.data == NULL);
    const char *kept = getenv("CADRUMO_INVOCATION_MARKER");
    assert(kept != NULL && strcmp(kept, "kept") == 0);

    /* A standard descriptor is not the declared invocation: the interpreter's own
     * profile defines a closed environment that drops the undeclared marker. */
    kdf[4] = "2";
    assert(define_launch(ctx, 9, kdf, &error) == 0);
    assert(getenv("CADRUMO_INVOCATION_MARKER") == NULL && getenv("PATH") != NULL);
    cadrumo_platform_destroy(ctx);
    puts("interpreter launch profile: refusal line, declared invocation and closed default pass");
    return 0;
}
