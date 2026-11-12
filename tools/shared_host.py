"""Find the packaged or pinned shared host Python support. MIT."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(host=None):
    candidates=[]
    if host:
        host=Path(host).resolve()
        candidates += [host.parent/'python',host.parent.parent/'host/python']
    candidates += [ROOT/'python',ROOT/'build/deps/8080-cosim/host/python',ROOT.parent/'8080-cosim/host/python']
    for candidate in candidates:
        if (candidate/'jh_recovery/__init__.py').is_file():
            sys.path.insert(0,str(candidate));return candidate
    raise RuntimeError('Missing shared host Python support; update the pinned 8080-cosim checkout or release package')
