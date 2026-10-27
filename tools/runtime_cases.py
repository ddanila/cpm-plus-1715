# SPDX-License-Identifier: MIT
"""Required cases shared by suite execution and artifact acceptance."""
GROUPS = {
 'base': {'boot-dir','utilities','cold-read','erase','cold-delete','keyboard-warmboot'},
 'extra': {'multi-random-user','user-cold','directory-full','large-pip','multi-warmboot'},
 'storage': {'indexed-extents','indexed-cold','corruption-negative','disk-full','disk-full-cold'},
 'faults': {'write-protect','missing-system','bad-system-header','bad-system-payload','absent','crc-fault','reset-write','reset-cold-read'},
 'boot': {'set-system-attributes','attributed-cold-boot','fragmented-last-slot','reserved-system-block','out-of-range-system-block','repeated-system-block','short-system-records','wrong-system-extent','unused-system-allocation'},
 'keyboard': {'keyboard-phase-0','keyboard-phase-10000','keyboard-phase-80000','keyboard-wrap','keyboard-overflow','keyboard-prefix','keyboard-warm-preserve','keyboard-reset-clock'},
 'keyboard-rates': {'keyboard-rate-50000','keyboard-rate-20000'},
 'smoke': {'boot-dir','crc-fault','keyboard-phase-0'},
}

def expected_cases(suite):
    return set.union(*(cases for group,cases in GROUPS.items() if group!='smoke')) if suite=='all' else GROUPS[suite]
