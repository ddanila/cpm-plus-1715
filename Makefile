# Tool rules adapted from cpm-plus-juku (BSD-2-Clause; third_party/JUKU-LICENSE).
PYTHON ?= python3
CC ?= cc
CXX ?= c++
BISON ?= bison
BUILD := build
OUT := out
BIN := $(BUILD)/bin
ZMAC := $(BIN)/zmac
ZXCC := $(BIN)/zxcc
ZXCC_ARCHIVE := third_party/zxcc/releases/zxcc-0.5.7.tar.gz
ZXCC_SOURCE := $(BUILD)/zxcc-0.5.7
ZXCC_PREFIX := $(BUILD)/zxcc-install
.DEFAULT_GOAL := all
.PHONY: all test
all: $(OUT)/cpm-plus-1715.img
$(BUILD)/system.inc: $(BUILD)/cpm3.sys tools/system_contract.py
	$(PYTHON) tools/system_contract.py
$(BUILD)/platform.cim: src/platform.asm $(BUILD)/system.inc $(ZMAC)
	$(ZMAC) --zmac -o $@ -o $(BUILD)/platform.lst $<
$(BUILD)/cpm3.sys: src/cpm3-bios.asm tools/regenerate_cpm3.py $(ZXCC)
	$(PYTHON) tools/regenerate_cpm3.py --adapter-address 0xc000 --top-page 0xbf --metadata-policy gencpm --output $@
$(OUT)/cpm-plus-1715.img: $(BUILD)/platform.cim $(BUILD)/cpm3.sys tools/build_image.py tools/media.py
	$(PYTHON) tools/build_image.py
$(BUILD) $(OUT) $(BIN) $(BUILD)/zmac:
	mkdir -p $@

$(BUILD)/zmac/docgen: third_party/zmac/doc.c | $(BUILD)/zmac
	$(CC) -O2 -DMK_DOC -Wno-main -o $@ $<

$(BUILD)/zmac/doc.inl: $(BUILD)/zmac/docgen third_party/zmac/doc.txt | $(BUILD)/zmac
	cp third_party/zmac/doc.txt $(BUILD)/zmac/doc.txt
	cd $(BUILD)/zmac && ./docgen >/dev/null

# Grouped targets (`&:`) need GNU make 4.3 and macOS ships 3.81, so every
# recipe here that writes more than one file names its command in a variable,
# hangs the dependency off one primary output, and gives each remaining output
# a rule that re-runs the command only if that file went missing on its own.
# The command cannot use $< or $@: it is shared by rules with different ones.
ZMAC_PARSER := $(BISON) --defines=$(BUILD)/zmac/parser.h \
	--output=$(BUILD)/zmac/parser.c third_party/zmac/zmac.y

$(BUILD)/zmac/parser.c: third_party/zmac/zmac.y | $(BUILD)/zmac
	$(ZMAC_PARSER)

$(BUILD)/zmac/parser.h: $(BUILD)/zmac/parser.c
	@test -f $@ || $(ZMAC_PARSER)

$(BUILD)/zmac/parser.o: $(BUILD)/zmac/parser.c $(BUILD)/zmac/parser.h \
		$(BUILD)/zmac/doc.inl third_party/zmac/mio.h
	$(CC) -O2 -c -I$(BUILD)/zmac -Ithird_party/zmac -o $@ $<

$(BUILD)/zmac/doc.o: third_party/zmac/doc.c $(BUILD)/zmac/doc.inl \
		$(BUILD)/zmac/parser.h
	$(CC) -O2 -c -I$(BUILD)/zmac -Ithird_party/zmac -o $@ $<

$(BUILD)/zmac/mio.o: third_party/zmac/mio.c $(BUILD)/zmac/parser.h \
		$(BUILD)/zmac/doc.inl
	$(CC) -O2 -c -I$(BUILD)/zmac -Ithird_party/zmac -o $@ $<

$(BUILD)/zmac/zi80dis.o: third_party/zmac/zi80dis.cpp \
		third_party/zmac/zi80dis.h $(BUILD)/zmac/parser.h
	$(CXX) -O2 -Wno-unused-result -c -I$(BUILD)/zmac \
		-Ithird_party/zmac -o $@ $<

$(ZMAC): $(BUILD)/zmac/parser.o $(BUILD)/zmac/doc.o \
		$(BUILD)/zmac/mio.o $(BUILD)/zmac/zi80dis.o | $(BIN)
	$(CXX) -o $@ $^

$(ZXCC): $(ZXCC_ARCHIVE) | $(BUILD) $(BIN)
	test "$$(sha256sum $< | cut -d' ' -f1)" = \
		6095119a31a610de84ff8f049d17421dd912c6fd2df18373e5f0a3bc796eb4bf
	mkdir -p $(ZXCC_SOURCE) $(ZXCC_PREFIX)
	tar -xzf $< --strip-components=1 -C $(ZXCC_SOURCE)
	cd $(ZXCC_SOURCE) && CFLAGS='-O2 -std=gnu17' \
		./configure --prefix=$(abspath $(ZXCC_PREFIX))
	$(MAKE) -C $(ZXCC_SOURCE)
	$(MAKE) -C $(ZXCC_SOURCE) install
	cp $(ZXCC_PREFIX)/bin/zxcc $@


.PHONY: test test-rom probe firmware-probe
PICO ?= ../Pico1715
DAC ?= ../dac-emulation
test: all serial test-rom
	$(PYTHON) -m unittest discover -s tests -p '*_test.py'
test-rom: all
	$(PYTHON) tools/build_test_rom.py
probe:
	$(PYTHON) tools/build_probe.py --pico $(PICO) --dac $(DAC)
firmware-probe:
	$(PYTHON) tools/build_probe.py --pico $(PICO) --dac $(DAC) --firmware

$(BUILD)/reliability-test.cim: src/reliability-test.asm $(ZMAC)
	$(ZMAC) --zmac -o $@ $<
$(BUILD)/directory-test.cim: src/directory-test.asm $(ZMAC)
	$(ZMAC) --zmac -o $@ $<
all: $(BUILD)/reliability-test.cim $(BUILD)/directory-test.cim

$(BUILD)/keyboard-map.json: $(BUILD)/platform.cim tools/keyboard_map.py
	$(PYTHON) tools/keyboard_map.py
$(BUILD)/keyboard.inc: $(BUILD)/keyboard-map.json
	@test -f $@ || $(PYTHON) tools/keyboard_map.py
all: $(BUILD)/keyboard-map.json

$(BUILD)/keyboard-test.cim: src/keyboard-test.asm $(BUILD)/keyboard.inc $(ZMAC)
	$(ZMAC) --zmac -o $@ $<
all: $(BUILD)/keyboard-test.cim

$(BUILD)/p1715test.cim: src/p1715test.asm $(ZMAC)
	$(ZMAC) --zmac -o $@ -o $(BUILD)/p1715test.lst $<
$(OUT)/cpm-plus-1715.img: $(BUILD)/p1715test.cim
all: $(BUILD)/p1715test.cim

.PHONY: serial
serial: all $(OUT)/cpm-plus-1715-serial.img
$(BUILD)/platform-serial.cim: src/platform-serial.asm src/platform.asm src/serial-platform.asm src/serial-common.asm src/serial-crc-table.asm $(BUILD)/system.inc $(ZMAC) third_party/juku-common/platform/rom-host-services.asm third_party/juku-common/platform/netdisk-v3.asm third_party/juku-common/platform/rom-abi.inc
	$(ZMAC) --zmac -o $@ -o $(BUILD)/platform-serial.lst $<
$(OUT)/cpm-plus-1715-serial.img: $(BUILD)/platform-serial.cim $(OUT)/cpm-plus-1715.img
	$(PYTHON) tools/build_image.py --serial

.PHONY: serial-probe
serial-probe: serial
	$(PYTHON) tools/build_probe.py --pico $(PICO) --dac $(DAC) --serial
$(BUILD)/serial-test.rom: src/serial-test-rom.asm $(ZMAC)
	$(ZMAC) --zmac -o $(BUILD)/serial-test.cim $<
	cp $(BUILD)/serial-test.cim $@
serial: $(BUILD)/serial-test.rom

.PHONY: tools
TOOLS_INPUTS := $(shell find src/cpmbox third_party/cpmbox third_party/hitech -type f)
tools: $(OUT)/tools/manifest.json
$(OUT)/tools/manifest.json: $(ZXCC) $(ZMAC) tools/build_tools.py tools/build_pipemgr.py $(TOOLS_INPUTS) third_party/tools-inputs.json third_party/cpm3/releases/cpm3bin_unix-20260607.zip
	$(PYTHON) tools/build_tools.py
$(OUT)/cpm-plus-1715-serial.img: $(OUT)/tools/manifest.json tools/tool_bundle.py tools/build_image.py tools/media.py

.PHONY: wm
wm: $(OUT)/cpm-plus-1715-wm.img
$(BUILD)/platform-wm.cim: src/platform-wm.asm src/platform.asm src/serial-platform.asm src/serial-common.asm src/serial-crc-table.asm $(BUILD)/system.inc $(ZMAC) $(wildcard third_party/juku-common/platform/*.asm) third_party/juku-common/platform/rom-abi.inc
	$(ZMAC) --zmac -o $@ -o $(BUILD)/platform-wm.lst $<
$(OUT)/cpm-plus-1715-wm.img: $(BUILD)/platform-wm.cim $(BUILD)/cpm3.sys $(BUILD)/p1715test.cim tools/build_image.py tools/media.py
	$(PYTHON) tools/build_image.py --wm

.PHONY: wm-probe
WM_CORE := $(addprefix $(DAC)/,machines/robotron1715m/robotron.c machines/robotron1715m/disk.c machines/robotron1715m/sio.c machines/robotron1715m/keyboard_board.c machines/robotron1715m/keyboard_cpu.c common/cpu/z80.c common/media/media.c common/trace/trace.c)
wm-probe: build/wm-probe
build/wm-probe: tools/wm_probe.c $(WM_CORE) $(DAC)/machines/robotron1715m/robotron.h | build
	$(CC) -std=c11 -O2 -Wall -Wextra -Werror -I$(DAC) tools/wm_probe.c $(WM_CORE) -o $@

.PHONY: wm-fast
wm-fast: $(OUT)/cpm-plus-1715-wm-fast.img
$(BUILD)/platform-wm-fast.cim: src/platform-wm-fast.asm src/platform.asm src/serial-platform.asm src/serial-common.asm src/serial-crc-table.asm $(BUILD)/system.inc $(ZMAC) $(wildcard third_party/juku-common/platform/*.asm) third_party/juku-common/platform/rom-abi.inc
	$(ZMAC) --zmac -o $@ -o $(BUILD)/platform-wm-fast.lst $<
$(OUT)/cpm-plus-1715-wm-fast.img: $(BUILD)/platform-wm-fast.cim $(BUILD)/cpm3.sys $(BUILD)/p1715test.cim tools/build_image.py tools/media.py
	$(PYTHON) tools/build_image.py --wm-fast

.PHONY: wm-62400
wm-62400: $(OUT)/cpm-plus-1715-wm-62400.img
$(BUILD)/platform-wm-62400.cim: src/platform-wm-62400.asm src/platform.asm src/serial-platform.asm src/serial-common.asm src/serial-crc-table.asm $(BUILD)/system.inc $(ZMAC) $(wildcard third_party/juku-common/platform/*.asm)
	$(ZMAC) --zmac -o $@ -o $(BUILD)/platform-wm-62400.lst $<
$(OUT)/cpm-plus-1715-wm-62400.img: $(BUILD)/platform-wm-62400.cim $(BUILD)/cpm3.sys tools/build_image.py tools/media.py
	$(PYTHON) tools/build_image.py --wm-62400

.PHONY: wm-9600
wm-9600: $(OUT)/cpm-plus-1715-wm-9600.img
$(BUILD)/platform-wm-9600.cim: src/platform-wm-9600.asm src/platform.asm src/serial-platform.asm src/serial-common.asm src/serial-crc-table.asm $(BUILD)/system.inc $(ZMAC) $(wildcard third_party/juku-common/platform/*.asm)
	$(ZMAC) --zmac -o $@ -o $(BUILD)/platform-wm-9600.lst $<
$(OUT)/cpm-plus-1715-wm-9600.img: $(BUILD)/platform-wm-9600.cim $(BUILD)/cpm3.sys tools/build_image.py tools/media.py
	$(PYTHON) tools/build_image.py --wm-9600

.PHONY: wm-banked
wm-banked: $(foreach rate,9600 fast 62400,$(OUT)/cpm-plus-1715-wm-banked-$(rate).img $(BUILD)/banked/platform-$(rate).json)
$(BUILD)/banked/cpm3.sys: src/cpm3-banked-bios.asm tools/build_banked.py tools/regenerate_cpm3.py third_party/cpm3/scb.asm third_party/cpm3/gencpm.dat $(wildcard third_party/cpm3/releases/*.zip) $(ZXCC)
	$(PYTHON) tools/build_banked.py
$(BUILD)/banked/system.inc: $(BUILD)/banked/cpm3.sys
	@test -f $@ || $(PYTHON) tools/build_banked.py
$(BUILD)/banked/platform-%.cim: src/platform-banked-%.asm src/platform.asm src/banked-loader.asm src/serial-platform.asm src/serial-common.asm src/serial-crc-table.asm $(BUILD)/banked/system.inc $(ZMAC) $(wildcard third_party/juku-common/platform/*.asm) third_party/juku-common/platform/rom-abi.inc
	$(ZMAC) --zmac -o $@ -o $(BUILD)/banked/platform-$*.lst $<
$(OUT)/cpm-plus-1715-wm-banked-%.img: $(BUILD)/banked/platform-%.cim $(BUILD)/banked/cpm3.sys tools/build_image.py tools/media.py
	$(PYTHON) tools/build_image.py --banked $*

.SECONDARY: $(foreach rate,9600 fast 62400,$(BUILD)/banked/platform-$(rate).cim)

$(BUILD)/banked-probe: tools/banked_probe.c $(WM_CORE) $(DAC)/machines/robotron1715m/robotron.h | build
	$(CC) -std=c11 -O2 -Wall -Wextra -Werror -I$(DAC) tools/banked_probe.c $(WM_CORE) -o $@
.PHONY: test-banked
test-banked: wm-banked $(BUILD)/banked-probe

$(BUILD)/banked/tpa-test.cim: src/banked-tpa-test.asm $(ZMAC) $(BUILD)/banked/cpm3.sys
	$(ZMAC) --zmac -o $@ $<
$(BUILD)/banked/disk-test.cim: src/banked-disk-test.asm $(ZMAC) $(BUILD)/banked/cpm3.sys
	$(ZMAC) --zmac -o $@ $<
test-banked: $(BUILD)/banked/tpa-test.cim $(BUILD)/banked/disk-test.cim

test-banked:
	$(BUILD)/banked-probe $(BUILD)/banked/cpm3.sys
	$(PYTHON) -m unittest discover -s tests -p 'banked*_test.py'
	$(PYTHON) tools/build_banked.py --check

$(BUILD)/banked/platform-%.json: $(OUT)/cpm-plus-1715-wm-banked-%.img
	@test -f $@ || $(PYTHON) tools/build_image.py --banked $*
