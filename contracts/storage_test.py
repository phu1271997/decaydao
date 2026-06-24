# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
#
# storage_test.py — deploy THIS first on a fresh Studio to confirm the
# environment works (version line, storage types, schema) before the real
# DecayDAO contract. If this fails, the problem is your Studio session, not
# DecayDAO. See common_error.md "RECOMMENDED DEPLOY PROCEDURE".

from genlayer import *

import json
from dataclasses import dataclass


@allow_storage
@dataclass
class Item:
    label: str
    count: bigint


class Contract(gl.Contract):
    items: TreeMap[str, Item]
    total: bigint

    def __init__(self):
        self.total = bigint(0)

    @gl.public.write
    def add(self, key: str, label: str) -> None:
        self.items[key] = Item(label=label, count=bigint(1))
        self.total = self.total + bigint(1)

    @gl.public.view
    def get_total(self) -> int:
        return int(self.total)

    @gl.public.view
    def dump(self) -> str:
        out = []
        for k in self.items:
            it = self.items[k]
            out.append({"key": k, "label": it.label, "count": int(it.count)})
        return json.dumps(out)
