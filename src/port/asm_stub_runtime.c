#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#endif

#define REPORTED_MAX 4096

extern const char *const gPortAsmPlaceholderData[];

// Set PORT_ASM_STUBS=continue to log and return 0 instead of exiting.
static int ShouldContinue(void) {
    static int mode = -1;
    if (mode < 0) {
        const char *env = getenv("PORT_ASM_STUBS");
        mode = env != NULL && strcmp(env, "continue") == 0;
    }
    return mode;
}

static int IsFirstReport(const char *name) {
    static const char *reported[REPORTED_MAX];
    uintptr_t start = ((uintptr_t)name >> 3) % REPORTED_MAX;
    for (int i = 0; i < REPORTED_MAX; i++) {
        const char **slot = &reported[(start + i) % REPORTED_MAX];
        if (*slot == name) {
            return 0;
        }
        if (*slot == NULL) {
            *slot = name;
            return 1;
        }
    }
    return 0;
}

uintptr_t PortAsm_Unimplemented(const char *name, const char *file) {
    if (IsFirstReport(name)) {
        fprintf(stderr, "[asm-stub] %s (%s) has no C implementation yet\n", name, file);
        FILE *log = fopen("asm_stubs.log", "a");
        if (log != NULL) {
            fprintf(log, "%s %s\n", name, file);
            fclose(log);
        }
    }
    if (ShouldContinue()) {
        return 0;
    }
    fflush(stderr);
#ifdef _WIN32
    char message[256];
    snprintf(message, sizeof(message), "%s (%s) is still assembly and has no C implementation yet.\n\nThe name was also written to asm_stubs.log.", name, file);
    MessageBoxA(NULL, message, "pokeheartgold PC port", MB_OK | MB_ICONERROR);
#endif
    exit(1);
}

__attribute__((constructor)) static void ReportPlaceholders(void) {
    for (int i = 0; gPortAsmPlaceholderData[i] != NULL; i++) {
        fprintf(stderr, "[asm-stub] warning: %s is a zero-filled placeholder\n", gPortAsmPlaceholderData[i]);
    }
}
