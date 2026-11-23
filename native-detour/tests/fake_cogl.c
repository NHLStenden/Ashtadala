#include <stdio.h>
/* Fake Cogl parser to test interposition without GNOME running. */
int cogl_color_from_string(void *color, const char *str)
{
    snprintf((char *)color, 64, "%s", str ? str : "(null)");
    return str != NULL;
}
