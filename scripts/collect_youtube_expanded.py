import requests
import json
import time
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import YOUTUBE_API_KEY, DATA_DIR

BASE_URL = "https://www.googleapis.com/youtube/v3"
data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), DATA_DIR)

EXPANDED_QUERIES = [
    "BAMF interview experience",
    "BAMF Anhörung",
    "Germany visa rejected",
    "Germany visa experience",
    "Abschiebung Deutschland",
    "Fachkräfteeinwanderungsgesetz",
    "Aufenthaltsgenehmigung",
    "Germany Blue Card experience",
    "Ausländerbehörde Erfahrung",
    "Einbürgerungstest",
    "German citizenship process",
    "asylum seeker Germany experience",
    "BAMF Asylverfahren",
    "integration course Germany experience",
    "Integrationskurs Erfahrung",
    "Germany immigration problems",
    "Germany deportation",
    "refugee Germany 2024",
    "refugee Germany 2025",
    "Flüchtlinge Deutschland",
    "migration debate Germany",
    "BAMF scandal",
    "BAMF reform",
    "Ausländerbehörde Berlin Termin",
    "Germany family reunification visa",
    "Familiennachzug Deutschland",
]


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
    next_page = None
    fetched = 0

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


def get_video_comments(video_id, max_comments=200):
    comments = []
    params = {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": 100,
        "order": "relevance",
        "textFormat": "plainText",
        "key": YOUTUBE_API_KEY,
    }
    url = f"{BASE_URL}/commentThreads"
    next_page = None

    while len(comments) < max_comments:
        if next_page:
            params["pageToken"] = next_page
        try:
            resp = requests.get(url, params=params)
            if resp.status_code != 200:
                break
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
            next_page = data.get("nextPageToken")
            if not next_page:
                break
            time.sleep(0.3)
        except Exception as e:
            print(f"  Comments error for {video_id}: {e}")
            break
    return comments


def main():
    # Load existing videos to avoid duplicates
    existing_path = os.path.join(data_path, "youtube_videos.json")
    with open(existing_path, "r", encoding="utf-8") as f:
        existing_videos = json.load(f)
    existing_ids = {v["video_id"] for v in existing_videos}

    existing_comments_path = os.path.join(data_path, "youtube_comments.json")
    with open(existing_comments_path, "r", encoding="utf-8") as f:
        existing_comments = json.load(f)

    print(f"Existing: {len(existing_ids)} videos, {len(existing_comments)} comments")

    new_videos = []
    for query in EXPANDED_QUERIES:
        print(f"Searching: '{query}'")
        videos = search_videos(query, max_results=50)
        new = 0
        for v in videos:
            if v["video_id"] not in existing_ids:
                existing_ids.add(v["video_id"])
                new_videos.append(v)
                new += 1
        print(f"  Found {len(videos)}, {new} new (total new: {len(new_videos)})")
        time.sleep(1)

    print(f"\nCollecting comments from {len(new_videos)} new videos (up to 200 per video)...")
    new_comments = []
    for i, video in enumerate(new_videos):
        comments = get_video_comments(video["video_id"], max_comments=200)
        new_comments.extend(comments)
        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(new_videos)} videos, {len(new_comments)} new comments")
        time.sleep(0.3)

    # Also collect MORE comments from existing videos (we only got 100 before)
    print(f"\nGetting additional comments from existing top videos...")
    existing_video_ids_with_comments = {c["video_id"] for c in existing_comments}
    extra_comments = []
    top_existing = [v for v in existing_videos if v["video_id"] in existing_video_ids_with_comments][:50]
    for i, video in enumerate(top_existing):
        comments = get_video_comments(video["video_id"], max_comments=200)
        for c in comments:
            if c["text"] not in {ec["text"] for ec in existing_comments if ec["video_id"] == c["video_id"]}:
                extra_comments.append(c)
        if (i + 1) % 10 == 0:
            print(f"  Checked {i + 1}/{len(top_existing)} existing videos, {len(extra_comments)} extra comments")
        time.sleep(0.3)

    # Merge and save
    all_videos = existing_videos + new_videos
    all_comments = existing_comments + new_comments + extra_comments

    with open(os.path.join(data_path, "youtube_videos.json"), "w", encoding="utf-8") as f:
        json.dump(all_videos, f, indent=2, ensure_ascii=False)
    with open(os.path.join(data_path, "youtube_comments.json"), "w", encoding="utf-8") as f:
        json.dump(all_comments, f, indent=2, ensure_ascii=False)

    print(f"\nDone!")
    print(f"  New videos: {len(new_videos)}")
    print(f"  New comments from new videos: {len(new_comments)}")
    print(f"  Extra comments from existing videos: {len(extra_comments)}")
    print(f"  TOTAL videos: {len(all_videos)}")
    print(f"  TOTAL comments: {len(all_comments)}")


if __name__ == "__main__":
    main()
