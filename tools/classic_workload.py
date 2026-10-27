"""Original MIT CP/M workload using BDOS, without ROM/BIOS patches.

FCB=0280h, source DMA=0300h, read DMA=0400h, entry=0100h.
Creates PICOTEST.TXT; writes, closes, resets, reopens and compares 20 records.
"""

def program(records=20):
    if not 1 <= records <= 128:
        raise ValueError("record count must be between 1 and 128")
    b = bytearray()
    labels = {}
    fix = []

    def emit(*xs):
        b.extend(xs)

    def label(x):
        labels[x] = 256 + len(b)

    def word(op, labelname):
        emit(op)
        fix.append((len(b), labelname))
        emit(0, 0)

    def call(n, addr=None):
        if addr is not None:
            emit(17, addr & 255, addr >> 8)
        emit(14, n, 205, 5, 0)

    def check():
        emit(183)
        word(194, 'fail')
    call(26, 768)
    call(22, 640)
    emit(60)
    word(202, 'fail')
    emit(6, records)
    label('write')
    emit(197)
    call(21, 640)
    emit(193)
    check()
    emit(5)
    word(194, 'write')
    call(16, 640)
    emit(60)
    word(202, 'fail')
    call(13)
    emit(175, 50, 140, 2, 50, 160, 2)
    call(15, 640)
    emit(60)
    word(202, 'fail')
    call(26, 1024)
    emit(6, records)
    label('read')
    emit(197)
    call(20, 640)
    emit(193)
    check()
    emit(197, 33, 0, 3, 17, 0, 4, 6, 128)
    label('cmp')
    emit(26, 190)
    word(194, 'fail')
    emit(35, 19, 5)
    word(194, 'cmp')
    emit(193, 5)
    word(194, 'read')
    call(16, 640)
    word(17, 'ok')
    word(195, 'print')
    label('fail')
    word(17, 'bad')
    label('print')
    call(9)
    emit(195, 0, 0)
    label('ok')
    b.extend(b'PICO READ WRITE OK\r\n$')
    label('bad')
    b.extend(b'PICO TEST FAILED\r\n$')
    for at, name in fix:
        b[at:at + 2] = labels[name].to_bytes(2, 'little')
    assert len(b) < 384
    b.extend(bytes(384 - len(b)))
    b.extend(b'\x00PICOTESTTXT' + bytes(24))
    b.extend(bytes(512 - len(b)))
    payload = (b'Pico1715 independent stock BIOS test. ' * 4)[:126] + b'\r\n'
    assert len(payload) == 128
    b.extend(payload)
    return (bytes(b), payload)

def install(image, records=20, block=62):
    if len(image) != 819200:
        raise ValueError('workload requires qualified 80x2x5x1024 image')
    disk = bytearray(image)
    entries = [disk[i:i + 32] for i in range(20480, 24576, 32)]
    used = {0, 1}
    for entry in entries:
        if entry[0] < 16:
            used.update((int.from_bytes(entry[j:j + 2], 'little') for j in range(16, 32, 2)))
    if block is None:
        block = next((i for i in range(2, (len(disk)-20480)//2048) if i not in used), None)
    if block is None or not 2 <= block < (len(disk)-20480)//2048:
        raise ValueError('no valid free fixture block')
    if block in used or any((bytes((c & 127 for c in e[1:12])) == b'PICOTESTCOM' for e in entries if e[0] < 16)):
        raise ValueError('fixture block or filename occupied')
    slot = next((i for i, e in enumerate(entries) if e[0] == 229), None)
    if slot is None:
        raise ValueError('no free directory entry')
    code, payload = program(records)
    entry = bytearray(32)
    entry[:12] = b'\x00PICOTESTCOM'
    entry[15] = (len(code) + 127) // 128
    entry[16:18] = block.to_bytes(2, 'little')
    disk[20480 + slot * 32:20480 + (slot + 1) * 32] = entry
    offset = 20480 + block * 2048
    disk[offset:offset + len(code)] = code
    return (bytes(disk), payload)

def small_file(image, name):
    """Independent user-0/single-extent file check for the qualified DPB."""
    matches = [image[i:i + 32] for i in range(20480, 24576, 32) if image[i] == 0 and bytes((c & 127 for c in image[i + 1:i + 12])) == name]
    if len(matches) != 1 or matches[0][12] or matches[0][14]:
        raise ValueError('expected one extent')
    entry = matches[0]
    blocks = [int.from_bytes(entry[j:j + 2], 'little') for j in range(16, 32, 2)]
    data = b''.join((image[20480 + k * 2048:20480 + (k + 1) * 2048] for k in blocks if k))
    size = entry[15] * 128
    if len(data) < size:
        raise ValueError('short allocation')
    return data[:size]
