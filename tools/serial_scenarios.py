"""Console and file assertions shared by emulator and physical serial campaigns."""
from media import inspect


def basic_console(command):
    command('DIR', b'P1715TST')
    command('TYPE HELLX\bO.TXT', b'Native CP/M Plus on Robotron 1715')


def file_utilities(command, image, baseline, before_copy=lambda: None, after_copy=lambda: None):
    before_copy()
    command('PIP COPY.TXT=HELLO.TXT')
    assert inspect(image.read_bytes())[(0, 'COPY.TXT')].data == baseline[(0, 'HELLO.TXT')]
    after_copy()
    command('RENAME NEW.TXT=COPY.TXT')
    files = inspect(image.read_bytes())
    assert (0, 'COPY.TXT') not in files and files[(0, 'NEW.TXT')].data == baseline[(0, 'HELLO.TXT')]
    command('SUBMIT TEST', b'Native CP/M Plus on Robotron 1715')


def patterned_file(image):
    expected = b''.join(bytes(i ^ j for j in range(128)) for i in range(256))
    expected = b'P1715TEST-v1\0\1\2\3'+expected[16:]
    assert inspect(image.read_bytes())[(0, 'P1715TST.DAT')].data == expected


def baseline_unchanged(image, baseline):
    files = {k: v.data for k, v in inspect(image.read_bytes()).items()}
    assert files == baseline, 'unexpected files or changed baseline data'
