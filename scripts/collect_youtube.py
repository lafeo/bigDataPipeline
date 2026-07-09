import requests
import json
import time
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import YOUTUBE_API_KEY, SEARCH_QUERIES, DATA_DIR

BASE_URL = "https://www.googleapis.com/youtube/v3"
data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), DATA_DIR)
os.makedirs(data_path, exist_ok=True)


def search_videos(query, max_results=50):
    videos = []
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": min(max_results, 50),
        "order": "relevance",
        "publishedAfter": "2024-01-01T00:00:00Z",
        "key": YOUTUBE_API_KEY,
    }
    url = f"{BASE_URL}/search"

    fetched = 0
    next_page = None

    while fetched < max_results:
        if next_page:
            params["pageToken"] = next_page

        resp = requests.get(url, params=params)
        if resp.status_code != 200:
            print(f"  Error {resp.status_code}: {resp.text[:200]}")
            break

        data = resp.json()
        for item in data.get("items", []):
            videos.append({
                "video_id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "channel": item["snippet"]["channelTitle"],
                "published_at": item["snippet"]["publishedAt"],
                "query": query,
            })
            fetched += 1

        next_page = data.get("nextPageToken")
        if not next_page:
            break
        time.sleep(0.5)

    return videos


def get_video_comments(video_id, max_comments=100):
    comments = []
    params = {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": min(max_comments, 100),
        "order": "relevance",
        "textFormat": "plainText",
        "key": YOUTUBE_API_KEY,
    }
    url = f"{BASE_URL}/commentThreads"

    try:
        resp = requests.get(url, params=params)
        if resp.status_code != 200:
            return comments

        data = resp.json()
        for item in data.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "video_id": video_id,
                "author": snippet["authorDisplayName"],
                "text": snippet["textDisplay"],
                "published_at": snippet["publishedAt"],
                "likes": snippet["likeCount"],
            })
    except Exception as e:
        print(f"  Comments disabled or error for {video_id}: {e}")

    return comments


def main():
    all_videos = []
    all_comments = []
    seen_video_ids = set()

    for query in SEARCH_QUERIES:
        print(f"Searching YouTube for: '{query}'")
        videos = search_videos(query, max_results=50)
        new = 0
        for v in videos:
            if v["video_id"] not in seen_video_ids:
                seen_video_ids.add(v["video_id"])
                all_videos.append(v)
                new += 1
        print(f"  Found {len(videos)} videos, {new} new (total unique: {len(all_videos)})")
        time.sleep(1)

    print(f"\nCollecting comments from {len(all_videos)} unique videos...")
    for i, video in enumerate(all_videos):
        comments = get_video_comments(video["video_id"])
        all_comments.extend(comments)
        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(all_videos)} videos, {len(all_comments)} comments so far")
        time.sleep(0.3)

    videos_path = os.path.join(data_path, "youtube_videos.json")
    comments_path = os.path.join(data_path, "youtube_comments.json")

    with open(videos_path, "w", encoding="utf-8") as f:
        json.dump(all_videos, f, indent=2, ensure_ascii=False)

    with open(comments_path, "w", encoding="utf-8") as f:
        json.dump(all_comments, f, indent=2, ensure_ascii=False)

    print(f"\nDone!")
    print(f"  Videos: {len(all_videos)} saved to {videos_path}")
    print(f"  Comments: {len(all_comments)} saved to {comments_path}")


if __name__ == "__main__":
    main()
