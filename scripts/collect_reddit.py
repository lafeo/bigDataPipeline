import requests
import json
import time
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SEARCH_QUERIES, TARGET_SUBREDDITS, DATA_DIR

data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), DATA_DIR)
os.makedirs(data_path, exist_ok=True)

HEADERS = {"User-Agent": "BAMF-Sentiment-Analysis/1.0 (university project)"}


def search_subreddit(subreddit, query, sort="new", limit=100):
    posts = []
    after = None
    fetched = 0

    while fetched < limit:
        batch = min(limit - fetched, 100)
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {
            "q": query,
            "sort": sort,
            "restrict_sr": "on",
            "limit": batch,
            "t": "all",
        }
        if after:
            params["after"] = after

        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            if resp.status_code == 429:
                print(f"    Rate limited, waiting 60s...")
                time.sleep(60)
                continue
            if resp.status_code != 200:
                print(f"    Error {resp.status_code} for r/{subreddit} '{query}'")
                break

            data = resp.json()
            children = data.get("data", {}).get("children", [])
            if not children:
                break

            for child in children:
                d = child["data"]
                posts.append({
                    "id": d.get("id"),
                    "title": d.get("title"),
                    "selftext": d.get("selftext", ""),
                    "author": d.get("author"),
                    "created_utc": d.get("created_utc"),
                    "score": d.get("score"),
                    "url": d.get("url"),
                    "num_comments": d.get("num_comments"),
                    "subreddit": d.get("subreddit"),
                    "permalink": d.get("permalink"),
                    "query": query,
                })
                fetched += 1

            after = data.get("data", {}).get("after")
            if not after:
                break

        except requests.exceptions.RequestException as e:
            print(f"    Request error: {e}")
            break

        time.sleep(2)

    return posts


def get_post_comments(permalink, limit=50):
    comments = []
    url = f"https://www.reddit.com{permalink}.json"
    params = {"limit": limit, "sort": "top"}

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return comments

        data = resp.json()
        if len(data) < 2:
            return comments

        for child in data[1].get("data", {}).get("children", []):
            if child.get("kind") != "t1":
                continue
            d = child["data"]
            comments.append({
                "post_id": d.get("link_id", "").replace("t3_", ""),
                "comment_id": d.get("id"),
                "author": d.get("author"),
                "body": d.get("body", ""),
                "created_utc": d.get("created_utc"),
                "score": d.get("score"),
                "subreddit": d.get("subreddit"),
            })
    except Exception as e:
        print(f"    Comment error: {e}")

    return comments


def main():
    all_posts = []
    all_comments = []
    seen_ids = set()

    for subreddit in TARGET_SUBREDDITS:
        for query in SEARCH_QUERIES:
            print(f"Searching r/{subreddit} for '{query}'...")
            posts = search_subreddit(subreddit, query, limit=100)
            new = 0
            for p in posts:
                if p["id"] not in seen_ids:
                    seen_ids.add(p["id"])
                    all_posts.append(p)
                    new += 1
            print(f"  Found {len(posts)} results, {new} new (total unique: {len(all_posts)})")
            time.sleep(3)

    print(f"\nCollecting comments from {len(all_posts)} unique posts...")
    for i, post in enumerate(all_posts):
        if post.get("permalink"):
            comments = get_post_comments(post["permalink"])
            all_comments.extend(comments)
        if (i + 1) % 20 == 0:
            print(f"  Processed {i + 1}/{len(all_posts)} posts, {len(all_comments)} comments so far")
        time.sleep(2)

    posts_path = os.path.join(data_path, "reddit_posts.json")
    comments_path = os.path.join(data_path, "reddit_comments.json")

    with open(posts_path, "w", encoding="utf-8") as f:
        json.dump(all_posts, f, indent=2, ensure_ascii=False)

    with open(comments_path, "w", encoding="utf-8") as f:
        json.dump(all_comments, f, indent=2, ensure_ascii=False)

    print(f"\nDone!")
    print(f"  Posts: {len(all_posts)} saved to {posts_path}")
    print(f"  Comments: {len(all_comments)} saved to {comments_path}")


if __name__ == "__main__":
    main()
