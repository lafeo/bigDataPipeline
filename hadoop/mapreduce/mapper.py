#!/usr/bin/env python3
"""
MapReduce Mapper: Cleans YouTube comment text data.
- Removes URLs, HTML tags, HTML entities
- Strips extra whitespace
- Skips comments shorter than 5 characters
- Emits: video_id<TAB>cleaned_json
"""
import sys
import json
import re

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue

    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        continue

    text = record.get("text", "")

    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove HTML entities
    text = re.sub(r'&amp;|&lt;|&gt;|&quot;|&#39;', ' ', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Skip short/empty comments
    if len(text) < 5:
        continue

    record["text"] = text
    video_id = record.get("video_id", "unknown")

    print(f"{video_id}\t{json.dumps(record, ensure_ascii=False)}")
