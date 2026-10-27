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
test: all test-rom
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
