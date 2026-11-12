"""MIT. Robotron protocol adapters for the native shared recovery engine."""
import json
from pathlib import Path
from ravi.transport import FDTransport
from serial_session import bootstrap


def recover(port,config):
    settings=config['settings'];options=config['options'];session=Path(config['session'])
    port.apply(settings['baud'],settings['parity'],settings['stop_bits'])
    wire=FDTransport(port.fd,duplicate=False)
    if options['profile']=='stock1715':
        from ravi.backends.robotron1715.boot import StockBoot,BootError
        boot=StockBoot(wire)
        try:boot.handshake(timeout=3)
        except BootError:return dict(status='unknown')
        # From here LOAD/EXEC is single-use. Any exception ends recovery.
        try:bootstrap(wire,Path(options['platform']).read_bytes(),session,120,boot=boot)
        except Exception as error:
            raise RuntimeError('Stock LOAD/EXEC state uncertain; reset required before retry') from error
        return dict(status='booted',rom=dict(protocol='R1715BT',version='unknown'))
    from ravi.backends.robotron1715w.discovery import identify_at_rate
    try:monitor=identify_at_rate(wire,5)
    except TimeoutError:return dict(status='unknown')
    identity=monitor.identity
    if identity['protocol']!='W4' or identity['baud']!=settings['baud']:
        raise ValueError('expected W4 at configured rate')
    print('ROM confirmed: '+json.dumps(identity),flush=True)
    code=Path(options['platform']).read_bytes();start=options['start'];entry=options['entry']
    monitor.write_memory(start,code)
    actual=monitor.read_memory(start,len(code))
    (session/'platform-readback.bin').write_bytes(actual)
    if actual!=code:raise ValueError('platform readback mismatch')
    try:monitor.start(entry)
    except TimeoutError:
        # EXEC may have happened. Never repeat it here: the native host first
        # looks for a checked runtime request, then requires fresh ROM identity.
        return dict(status='unknown',rom=identity,execution_uncertain=True)
    return dict(status='booted',rom=identity)
