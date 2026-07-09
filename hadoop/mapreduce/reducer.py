#!/usr/bin/env python3
"""
MapReduce Reducer: Deduplicates comments per video.
- Groups by video_id (pre-sorted by Hadoop)
- Removes duplicate comments (same video_id + same text)
- Emits cleaned JSON, one record per line
"""
import sys
import json

current_video = None
seen_texts = set()
total_in = 0
total_out = 0
duplicates = 0

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue

    total_in += 1

    try:
        video_id, json_str = line.split("\t", 1)
        record = json.loads(json_str)
    except (ValueError, json.JSONDecodeError):
        continue

    if video_id != current_video:
        current_video = video_id
        seen_texts = set()

    text = record.get("text", "")
    if text in seen_texts:
        duplicates += 1
        continue

    seen_texts.add(text)
    total_out += 1
    print(json.dumps(record, ensure_ascii=False))

sys.stderr.write(f"Reducer stats: {total_in} in, {total_out} out, {duplicates} duplicates removed\n")
