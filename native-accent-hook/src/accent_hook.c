/*
 * Ashtadala native accent hook — ELF symbol interposition for GNOME Shell 51.
 *
 * Intercepts Cogl's gboolean cogl_color_from_string(CoglColor *, const char *)
 * and changes only the exact built-in slate hex before its Cogl conversion.
 * No GNOME development headers are needed because the color pointer is opaque.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define SLATE "#6f8396"
#define DEFAULT_ACCENT "#fb996c"
#define COLOR_ENV "ASHTADALA_ACCENT_COLOR"
#define LOG_ENV "ASHTADALA_ACCENT_LOG"

typedef int (*parse_fn)(void *color, const char *str);
static parse_fn original;
static pthread_once_t resolve_once = PTHREAD_ONCE_INIT;
static atomic_int reported_match = ATOMIC_VAR_INIT(0);
static atomic_int reported_error = ATOMIC_VAR_INIT(0);

static int logging_enabled(void)
{
    const char *v = getenv(LOG_ENV);
    return v && v[0] == '1' && v[1] == '\0';
}

static void emit_log(const char *action, const char *color)
{
    if (!logging_enabled())
        return;
    char line[256];
    int len = snprintf(line, sizeof(line),
                       "[ashtadala-accent] pid=%ld %s%s%s\n",
                       (long)getpid(), action, color ? " " : "",
                       color ? color : "");
    if (len > 0 && (size_t)len < sizeof(line))
        (void)write(STDERR_FILENO, line, (size_t)len);
}

/* A load marker helps distinguish wrong service wiring from wrong C hook. */
__attribute__((constructor)) static void on_load(void)
{
    emit_log("loaded", NULL);
}

static void resolve_original(void)
{
    void *symbol = dlsym(RTLD_NEXT, "cogl_color_from_string");
    /* ELF/POSIX dlsym: copy object pointer bits into function pointer. */
    memcpy(&original, &symbol, sizeof(original));
}

static int is_valid_hex(const char *str)
{
    if (!str || strlen(str) != 7 || str[0] != '#')
        return 0;
    for (unsigned i = 1; i <= 6; ++i) {
        char c = str[i];
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') ||
              (c >= 'A' && c <= 'F')))
            return 0;
    }
    return 1;
}

__attribute__((visibility("default")))
int cogl_color_from_string(void *color, const char *str)
{
    (void)pthread_once(&resolve_once, resolve_original);
    if (!original) {
        if (atomic_exchange(&reported_error, 1) == 0)
            emit_log("ERROR: original cogl_color_from_string not found", NULL);
        return 0;
    }

    if (str && strcmp(str, SLATE) == 0) {
        const char *chosen = getenv(COLOR_ENV);
        str = is_valid_hex(chosen) ? chosen : DEFAULT_ACCENT;
        if (atomic_exchange(&reported_match, 1) == 0)
            emit_log("replaced native slate with", str);
    }
    return original(color, str);
}
