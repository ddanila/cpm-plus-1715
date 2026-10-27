#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Deterministic simulator packages with explicit, current qualification inputs."""
import argparse
import json
import zipfile
from pathlib import Path
from evidence import ROOT, sha, sources, outputs, atomic_json


def validate(reports, release=False):
    current, built = sources(), outputs()
    deps=json.loads((ROOT/'dependencies.json').read_text())
    coverage=set()
    for report in reports:
        if report.get('schema') != 2 or report.get('status') != 'passed':
            raise ValueError('missing or failed qualification status')
        if report.get('source_sha256') != current or report.get('dependencies') != deps:
            raise ValueError('qualification sources or dependencies are stale')
        if report.get('fresh_source_build'):
            if report.get('equal_outputs') != built:
                raise ValueError('reproducibility outputs mismatch')
            coverage.add('reproducible')
            continue
        if report.get('output_sha256') != built or report.get('image_sha256') != built['out/cpm-plus-1715.img']:
            raise ValueError('qualified outputs mismatch')
        if report.get('hardware_executed') is not False:
            raise ValueError('simulator report required')
        cases=report.get('cases',[])
        if not cases or any(c.get('status')!='passed' for c in cases):
            raise ValueError('missing or failed cases')
        from runtime_cases import expected_cases
        if {c['case'] for c in cases} != expected_cases(report['suite']) or len(cases)!=len(expected_cases(report['suite'])):
            raise ValueError('incomplete or duplicate runtime cases')
        profile=report.get('rom_profile')
        expected_rom=built['build/test.rom'] if profile=='public-fixture' else '51cb80639b5667f2611da71ce7305061566cf3474bda7db6fc82709d08e46d01'
        if profile not in ('public-fixture','stock-reference') or report.get('rom_sha256')!=expected_rom:
            raise ValueError('ROM profile mismatch')
        if report['suite']=='all':coverage.add((report['backend'],profile))
    required={'reproducible',('native','public-fixture')}
    if release: required |= {('native','stock-reference'),('firmware','stock-reference')}
    if not required <= coverage:
        raise ValueError(f'missing required qualification: {required-coverage}')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',type=Path,action='append',required=True)
    p.add_argument('--release',action='store_true',help='require full stock-ROM and firmware evidence')
    a=p.parse_args()
    try:
        reports=[json.loads(path.read_text()) for path in a.report]
        validate(reports,a.release)
        if len({path.name for path in a.report})!=len(a.report):raise ValueError('duplicate report names')
        out=ROOT/'out'
        files={'cpm-plus-1715.img':out/'cpm-plus-1715.img','CPM3.SYS':ROOT/'build/cpm3.sys','platform.bin':ROOT/'build/platform.cim','memory-map.json':ROOT/'build/system-map.json','keyboard-map.json':ROOT/'build/keyboard-map.json','README.md':ROOT/'README.md','NOTICE.md':ROOT/'NOTICE.md','LICENSE':ROOT/'LICENSE','JUKU-LICENSE':ROOT/'third_party/JUKU-LICENSE','CPM-LICENSE.md':ROOT/'third_party/cpm3/LICENSE.md'}
        for path in a.report:files['reports/'+path.name]=path
        for name in ('design.md','qualification.md','disk-tools.md','keyboard.md'):files['docs/'+name]=ROOT/'docs'/name
        manifest={'schema':2,'hardware_executed':False,'status':'simulation qualification only',
                  'qualification':'release' if a.release else 'ci',
                  'dependencies':json.loads((ROOT/'dependencies.json').read_text()),
                  'files':{n:sha(path.read_bytes()) for n,path in files.items()}}
        atomic_json(out/'manifest.json',manifest);files['manifest.json']=out/'manifest.json'
        temporary=out/'cpm-plus-1715-simulator.zip.tmp'
        with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,path in sorted(files.items()):
                info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,path.read_bytes())
        temporary.replace(out/'cpm-plus-1715-simulator.zip')
        print(out/'cpm-plus-1715-simulator.zip')
    except (OSError,ValueError,KeyError) as exc:p.exit(1,f'error: {exc}\n')

if __name__=='__main__':main()
