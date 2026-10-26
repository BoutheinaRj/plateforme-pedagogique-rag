#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path

total = 0
files = list(Path('data/json_out').rglob('*.json'))

print("JSON Files Found:")
print("-" * 80)

for fpath in sorted(files):
    with open(fpath, encoding='utf-8') as f:
        chunks = json.load(f)
        if isinstance(chunks, list):
            count = len(chunks)
            total += count
            fname = fpath.name
            print(f"  {fname:50} : {count:3} chunks")

print("-" * 80)
print(f"TOTAL: {total} chunks from {len(files)} files")


