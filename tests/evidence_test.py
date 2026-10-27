# SPDX-License-Identifier: MIT
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from evidence import atomic_json, sources, outputs
from package import validate
from runtime_cases import expected_cases

class EvidenceTests(unittest.TestCase):
    def reports(self):
        common=dict(schema=2,status='passed',source_sha256=sources(),dependencies=json.loads((ROOT/'dependencies.json').read_text()))
        built=outputs()
        repro=common|dict(fresh_source_build=True,equal_outputs=built)
        runtime=common|dict(output_sha256=built,image_sha256=built['out/cpm-plus-1715.img'],hardware_executed=False,
            backend='native',rom_profile='public-fixture',rom_sha256=built['build/test.rom'],suite='all',
            cases=[dict(case=name,status='passed') for name in sorted(expected_cases('all'))])
        return [repro,runtime]

    def test_required_coverage(self):
        reports=self.reports()
        validate(reports)
        with self.assertRaisesRegex(ValueError,'missing required'):validate(reports,True)
        stock=copy.deepcopy(reports[1]);stock['rom_profile']='stock-reference';stock['rom_sha256']='51cb80639b5667f2611da71ce7305061566cf3474bda7db6fc82709d08e46d01'
        validate(reports+[stock,stock|dict(backend='firmware')],True)

    def test_stale_failed_incomplete_wrong_rom(self):
        for field,value in [('status','failed'),('source_sha256',{}),('output_sha256',{}),('cases',[]),('rom_sha256','bad')]:
            reports=self.reports();reports[1][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):validate(reports)
        reports=self.reports();reports[1]['cases'].append(reports[1]['cases'][0])
        with self.assertRaises(ValueError):validate(reports)

    def test_atomic_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'report.json'
            atomic_json(p,{'old':1})
            with patch('evidence.os.replace',side_effect=OSError('injected')):
                with self.assertRaises(OSError):atomic_json(p,{'new':2})
            self.assertEqual(json.loads(p.read_text()),{'old':1})
            self.assertEqual(list(Path(tmp).iterdir()),[p])

    def test_timeout_reaps_runner(self):
        import os, subprocess
        from check_runtime import execute
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            with self.assertRaises(subprocess.TimeoutExpired):
                execute([sys.executable,'-c','import time; time.sleep(30)'],os.environ.copy(),path,timeout=0.1)
            self.assertTrue((path/'stderr.log').exists())
