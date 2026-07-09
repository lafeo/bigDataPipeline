import json
import re
import os
import sys
from datetime import datetime

from langdetect import detect, LangDetectException
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

TOPIC_KEYWORDS = {
    "visa": ["visa", "visum", "aufenthaltstitel", "residence permit", "blue card", "work permit", "arbeitserlaubnis"],
    "asylum": ["asylum", "asyl", "refugee", "flüchtling", "geflüchtete", "schutz", "protection", "abschiebung", "deportation"],
    "citizenship": ["einbürgerung", "citizenship", "naturalization", "staatsangehörigkeit", "passport", "reisepass"],
    "integration_course": ["integration course", "integrationskurs", "language course", "sprachkurs", "b1", "deutsch lernen"],
    "processing_time": ["waiting", "months", "delay", "slow", "long time", "warten", "monate", "dauert", "how long", "timeline"],
    "appointment": ["appointment", "termin", "booking", "slot", "ausländerbehörde"],
    "staff_service": ["rude", "unhelpful", "friendly", "helpful", "staff", "employee", "beamte", "sachbearbeiter", "mitarbeiter"],
    "policy": ["policy", "law", "gesetz", "reform", "fachkräfte", "immigration law", "regulation", "ampel", "cdu", "afd", "coalition"],
}


def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&amp;|&lt;|&gt;|&quot;|&#39;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def detect_language(text):
    if not text or len(text) < 20:
        return "unknown"
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"


def classify_topics(text):
    text_lower = text.lower()
    matched = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            matched.append(topic)
    return matched if matched else ["general"]


def analyze_sentiment_vader(text):
    analyzer = SentimentIntensityAnalyzer()
    scores = analyzer.polarity_scores(text)
    compound = scores["compound"]
    if compound >= 0.05:
        label = "positive"
    elif compound <= -0.05:
        label = "negative"
    else:
        label = "neutral"
    return {"compound": compound, "pos": scores["pos"], "neg": scores["neg"], "neu": scores["neu"], "label": label}


def analyze_sentiment_textblob(text):
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    if polarity > 0.05:
        label = "positive"
    elif polarity < -0.05:
        label = "negative"
    else:
        label = "neutral"
    return {"polarity": polarity, "subjectivity": blob.sentiment.subjectivity, "label": label}


def process_videos(videos):
    processed = []
    for v in videos:
        clean_title = clean_text(v["title"])
        clean_desc = clean_text(v.get("description", ""))
        combined = f"{clean_title} {clean_desc}"
        lang = detect_language(combined)
        topics = classify_topics(combined)

        vader = analyze_sentiment_vader(combined)
        textblob = analyze_sentiment_textblob(combined)

        processed.append({
            "video_id": v["video_id"],
            "title": clean_title,
            "description": clean_desc,
            "channel": v["channel"],
            "published_at": v["published_at"],
            "query": v["query"],
            "year_month": v["published_at"][:7],
            "language": lang,
            "topics": topics,
            "vader": vader,
            "textblob": textblob,
        })
    return processed


def process_comments(comments):
    processed = []
    skipped = 0
    for c in comments:
        clean = clean_text(c["text"])
        if len(clean) < 5:
            skipped += 1
            continue

        lang = detect_language(clean)
        topics = classify_topics(clean)
        vader = analyze_sentiment_vader(clean)
        textblob = analyze_sentiment_textblob(clean)

        processed.append({
            "video_id": c["video_id"],
            "author": c["author"],
            "text": clean,
            "published_at": c["published_at"],
            "year_month": c["published_at"][:7],
            "likes": c["likes"],
            "language": lang,
            "topics": topics,
            "vader": vader,
            "textblob": textblob,
        })
    print(f"  Skipped {skipped} comments (too short)")
    return processed


def print_summary(videos, comments):
    print("\n" + "=" * 60)
    print("DATASET SUMMARY")
    print("=" * 60)

    print(f"\nVideos: {len(videos)}")
    print(f"Comments: {len(comments)}")

    lang_dist = {}
    for c in comments:
        lang_dist[c["language"]] = lang_dist.get(c["language"], 0) + 1
    print("\nComment languages:")
    for lang, count in sorted(lang_dist.items(), key=lambda x: -x[1])[:5]:
        print(f"  {lang}: {count} ({100*count/len(comments):.1f}%)")

    print("\nComment sentiment (VADER):")
    sent_dist = {}
    for c in comments:
        sent_dist[c["vader"]["label"]] = sent_dist.get(c["vader"]["label"], 0) + 1
    for label in ["positive", "neutral", "negative"]:
        count = sent_dist.get(label, 0)
        print(f"  {label}: {count} ({100*count/len(comments):.1f}%)")

    avg_compound = sum(c["vader"]["compound"] for c in comments) / len(comments)
    print(f"  Average compound score: {avg_compound:.3f}")

    print("\nTop topics in comments:")
    topic_counts = {}
    for c in comments:
        for t in c["topics"]:
            topic_counts[t] = topic_counts.get(t, 0) + 1
    for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
        print(f"  {topic}: {count}")

    print("\nSentiment by topic (VADER avg compound):")
    topic_sentiments = {}
    for c in comments:
        for t in c["topics"]:
            if t not in topic_sentiments:
                topic_sentiments[t] = []
            topic_sentiments[t].append(c["vader"]["compound"])
    for topic, scores in sorted(topic_sentiments.items(), key=lambda x: sum(x[1])/len(x[1])):
        avg = sum(scores) / len(scores)
        print(f"  {topic}: {avg:.3f} (n={len(scores)})")


def main():
    print("Loading data...")
    with open(os.path.join(DATA_DIR, "youtube_videos.json"), "r", encoding="utf-8") as f:
        videos_raw = json.load(f)
    with open(os.path.join(DATA_DIR, "youtube_comments.json"), "r", encoding="utf-8") as f:
        comments_raw = json.load(f)

    print(f"Loaded {len(videos_raw)} videos, {len(comments_raw)} comments")

    print("\nProcessing videos...")
    videos = process_videos(videos_raw)
    print(f"  Processed {len(videos)} videos")

    print("\nProcessing comments (this may take a minute)...")
    comments = process_comments(comments_raw)
    print(f"  Processed {len(comments)} comments")

    print_summary(videos, comments)

    with open(os.path.join(DATA_DIR, "videos_analyzed.json"), "w", encoding="utf-8") as f:
        json.dump(videos, f, indent=2, ensure_ascii=False)
    with open(os.path.join(DATA_DIR, "comments_analyzed.json"), "w", encoding="utf-8") as f:
        json.dump(comments, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to:")
    print(f"  data/videos_analyzed.json")
    print(f"  data/comments_analyzed.json")


if __name__ == "__main__":
    main()
