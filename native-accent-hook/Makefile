CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra -Werror -std=c11
BUILD_DIR ?= build
TARGET = $(BUILD_DIR)/libaccent-hook.so

.PHONY: all clean test check
all: $(TARGET)

$(TARGET): src/accent_hook.c
	mkdir -p "$(BUILD_DIR)"
	$(CC) $(CFLAGS) -fPIC -shared -fvisibility=hidden -o "$@" "$<" -ldl -pthread

check: all
	readelf -Ws "$(TARGET)" | grep -E 'GLOBAL.*cogl_color_from_string'

test: all
	bash tests/test-hook.sh
	bash tests/test-install.sh

clean:
	rm -rf "$(BUILD_DIR)"
