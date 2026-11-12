#!/usr/bin/env python3
"""MIT. An uncertain W4 EXEC must rediscover, never replay the command."""
import tempfile
from pathlib import Path
from unittest.mock import patch,Mock
import recovery_profile

with tempfile.TemporaryDirectory() as directory:
    root=Path(directory);code=root/'platform.cim';code.write_bytes(b'test')
    port=Mock();port.fd=7
    monitor=Mock();monitor.identity=dict(protocol='W4',baud=62400)
    monitor.read_memory.return_value=b'test';monitor.start.side_effect=TimeoutError('lost ACK')
    config=dict(session=str(root),settings=dict(baud=62400,parity='N',stop_bits=1),
        options=dict(profile='w4',platform=str(code),start=0xe000,entry=0xe033))
    with patch.object(recovery_profile,'FDTransport'),patch('ravi.backends.robotron1715w.discovery.identify_at_rate',return_value=monitor):
        result=recovery_profile.recover(port,config)
    assert result['status']=='unknown' and result['execution_uncertain']
    monitor.start.assert_called_once_with(0xe033)
    monitor.write_memory.assert_called_once_with(0xe000,b'test')
print('RECOVERY-PROFILE: PASS (uncertain W4 execution returns to discovery)')

with tempfile.TemporaryDirectory() as directory:
    root=Path(directory);code=root/'platform.cim';code.write_bytes(b'test')
    port=Mock();port.fd=7
    config=dict(session=str(root),settings=dict(baud=9600,parity='O',stop_bits=2),
        options=dict(profile='stock1715',platform=str(code)))
    with patch.object(recovery_profile,'FDTransport'),patch('ravi.backends.robotron1715.boot.StockBoot'),patch.object(recovery_profile,'bootstrap',side_effect=ConnectionError('lost link')) as boot:
        try:recovery_profile.recover(port,config)
        except RuntimeError as error:assert 'reset required' in str(error)
        else:raise AssertionError('uncertain stock execution allowed reconnect/replay')
        assert boot.call_count==1
print('RECOVERY-PROFILE: PASS (uncertain stock LOAD/EXEC requires reset)')
