import json
import os
import psycopg2
from psycopg2.extras import execute_values

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_NAME = "bamf_sentiment"


def get_conn():
    return psycopg2.connect(dbname=DB_NAME)


def create_tables(conn):
    cur = conn.cursor()
    cur.execute("""
        DROP TABLE IF EXISTS comments CASCADE;
        DROP TABLE IF EXISTS videos CASCADE;

        CREATE TABLE videos (
            video_id        TEXT PRIMARY KEY,
            title           TEXT,
            description     TEXT,
            channel         TEXT,
            published_at    TIMESTAMP,
            year_month      TEXT,
            query           TEXT,
            language        TEXT,
            topics          TEXT[],
            vader_compound  REAL,
            vader_label     TEXT,
            textblob_polarity REAL,
            textblob_label  TEXT
        );

        CREATE TABLE comments (
            id              SERIAL PRIMARY KEY,
            video_id        TEXT REFERENCES videos(video_id),
            author          TEXT,
            text            TEXT,
            published_at    TIMESTAMP,
            year_month      TEXT,
            likes           INTEGER,
            language        TEXT,
            topics          TEXT[],
            vader_compound  REAL,
            vader_pos       REAL,
            vader_neg       REAL,
            vader_neu       REAL,
            vader_label     TEXT,
            textblob_polarity   REAL,
            textblob_subjectivity REAL,
            textblob_label  TEXT
        );

        CREATE INDEX idx_comments_video_id ON comments(video_id);
        CREATE INDEX idx_comments_year_month ON comments(year_month);
        CREATE INDEX idx_comments_vader_label ON comments(vader_label);
        CREATE INDEX idx_comments_language ON comments(language);
    """)
    conn.commit()
    cur.close()
    print("Tables created.")


def load_videos(conn):
    with open(os.path.join(DATA_DIR, "videos_analyzed.json"), "r", encoding="utf-8") as f:
        videos = json.load(f)

    cur = conn.cursor()
    rows = []
    for v in videos:
        rows.append((
            v["video_id"], v["title"], v["description"], v["channel"],
            v["published_at"], v["year_month"], v["query"], v["language"],
            v["topics"],
            v["vader"]["compound"], v["vader"]["label"],
            v["textblob"]["polarity"], v["textblob"]["label"],
        ))

    execute_values(cur, """
        INSERT INTO videos (video_id, title, description, channel, published_at,
            year_month, query, language, topics, vader_compound, vader_label,
            textblob_polarity, textblob_label)
        VALUES %s
        ON CONFLICT (video_id) DO NOTHING
    """, rows)
    conn.commit()
    cur.close()
    print(f"Loaded {len(rows)} videos.")


def load_comments(conn):
    with open(os.path.join(DATA_DIR, "comments_analyzed.json"), "r", encoding="utf-8") as f:
        comments = json.load(f)

    cur = conn.cursor()
    rows = []
    for c in comments:
        rows.append((
            c["video_id"], c["author"], c["text"], c["published_at"],
            c["year_month"], c["likes"], c["language"], c["topics"],
            c["vader"]["compound"], c["vader"]["pos"], c["vader"]["neg"], c["vader"]["neu"],
            c["vader"]["label"],
            c["textblob"]["polarity"], c["textblob"]["subjectivity"], c["textblob"]["label"],
        ))

    execute_values(cur, """
        INSERT INTO comments (video_id, author, text, published_at, year_month,
            likes, language, topics, vader_compound, vader_pos, vader_neg, vader_neu,
            vader_label, textblob_polarity, textblob_subjectivity, textblob_label)
        VALUES %s
    """, rows)
    conn.commit()
    cur.close()
    print(f"Loaded {len(rows)} comments.")


def run_analysis(conn):
    cur = conn.cursor()

    print("\n" + "=" * 60)
    print("SQL ANALYSIS RESULTS")
    print("=" * 60)

    # 1. Overall sentiment distribution
    print("\n--- 1. Overall Sentiment Distribution ---")
    cur.execute("""
        SELECT vader_label, COUNT(*) as cnt,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) as pct,
               ROUND(AVG(vader_compound)::numeric, 3) as avg_compound
        FROM comments
        GROUP BY vader_label
        ORDER BY cnt DESC;
    """)
    for row in cur.fetchall():
        print(f"  {row[0]:10s}: {row[1]:5d} ({row[2]}%) avg={row[3]}")

    # 2. Sentiment over time (monthly)
    print("\n--- 2. Monthly Sentiment Trend ---")
    cur.execute("""
        SELECT year_month, COUNT(*) as cnt,
               ROUND(AVG(vader_compound)::numeric, 3) as avg_sentiment,
               SUM(CASE WHEN vader_label='negative' THEN 1 ELSE 0 END) as neg_count,
               SUM(CASE WHEN vader_label='positive' THEN 1 ELSE 0 END) as pos_count
        FROM comments
        GROUP BY year_month
        ORDER BY year_month;
    """)
    print(f"  {'Month':<10} {'Count':>6} {'AvgSent':>8} {'Neg':>5} {'Pos':>5}")
    for row in cur.fetchall():
        print(f"  {row[0]:<10} {row[1]:>6} {row[2]:>8} {row[3]:>5} {row[4]:>5}")

    # 3. Sentiment by topic
    print("\n--- 3. Sentiment by Topic ---")
    cur.execute("""
        SELECT unnest(topics) as topic, COUNT(*) as cnt,
               ROUND(AVG(vader_compound)::numeric, 3) as avg_sentiment,
               ROUND(AVG(textblob_polarity)::numeric, 3) as avg_polarity
        FROM comments
        GROUP BY topic
        ORDER BY avg_sentiment ASC;
    """)
    print(f"  {'Topic':<20} {'Count':>6} {'VADER':>8} {'TextBlob':>9}")
    for row in cur.fetchall():
        print(f"  {row[0]:<20} {row[1]:>6} {row[2]:>8} {row[3]:>9}")

    # 4. Sentiment by language
    print("\n--- 4. Sentiment by Language ---")
    cur.execute("""
        SELECT language, COUNT(*) as cnt,
               ROUND(AVG(vader_compound)::numeric, 3) as avg_sentiment
        FROM comments
        WHERE language IN ('en', 'de')
        GROUP BY language
        ORDER BY avg_sentiment;
    """)
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} comments, avg sentiment = {row[2]}")

    # 5. Most discussed videos (by comment count)
    print("\n--- 5. Most Discussed Videos (Top 10) ---")
    cur.execute("""
        SELECT v.title, v.channel, COUNT(c.id) as comment_count,
               ROUND(AVG(c.vader_compound)::numeric, 3) as avg_sentiment
        FROM videos v
        JOIN comments c ON v.video_id = c.video_id
        GROUP BY v.video_id, v.title, v.channel
        ORDER BY comment_count DESC
        LIMIT 10;
    """)
    for i, row in enumerate(cur.fetchall(), 1):
        print(f"  {i}. [{row[2]} comments, sent={row[3]}] {row[1]}: {row[0][:70]}")

    # 6. Most negative comments (potential pain points)
    print("\n--- 6. Most Negative Comments (Top 5 by likes) ---")
    cur.execute("""
        SELECT text, likes, vader_compound, topics
        FROM comments
        WHERE vader_label = 'negative' AND likes >= 3
        ORDER BY likes DESC, vader_compound ASC
        LIMIT 5;
    """)
    for i, row in enumerate(cur.fetchall(), 1):
        print(f"  {i}. [likes={row[1]}, sent={row[2]}, topics={row[3]}]")
        print(f"     {row[0][:120]}...")

    # 7. Sentiment shift: 2024 vs 2025 vs 2026
    print("\n--- 7. Year-over-Year Sentiment Comparison ---")
    cur.execute("""
        SELECT LEFT(year_month, 4) as year, COUNT(*) as cnt,
               ROUND(AVG(vader_compound)::numeric, 3) as avg_sentiment,
               ROUND(100.0 * SUM(CASE WHEN vader_label='negative' THEN 1 ELSE 0 END) / COUNT(*)::numeric, 1) as neg_pct
        FROM comments
        GROUP BY LEFT(year_month, 4)
        ORDER BY year;
    """)
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} comments, avg={row[2]}, negative={row[3]}%")

    cur.close()


def main():
    conn = get_conn()
    print("Connected to PostgreSQL.")

    create_tables(conn)
    load_videos(conn)
    load_comments(conn)
    run_analysis(conn)

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
