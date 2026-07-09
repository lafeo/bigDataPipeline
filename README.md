# BAMF Sentiment Analysis — Big Data & Analytics Final Project

YouTube sentiment analysis of BAMF (Germany's Federal Office for Migration & Refugees) using a Hadoop → PostgreSQL → Python pipeline.

**Corpus:** 50,329 comments · 1,386 videos · Jan 2024 – Jun 2026

---

## Requirements

- Docker Desktop (running)
- Python 3.10+
- PostgreSQL (running locally, default port 5432)
- A YouTube Data API v3 key (only needed if re-collecting data)

---

## Quick start (Docker + Hadoop)

### 1. Clone the repo

```bash
git clone https://github.com/lafeo/bigDataPipeline.git
cd bigDataPipeline
```

### 2. Set up your API key

```bash
cp .env.example .env
# Open .env and paste your YouTube API key
```

### 3. Install Python dependencies

```bash
pip install requests vaderSentiment textblob langdetect psycopg2-binary \
            python-dotenv wordcloud matplotlib seaborn pandas openpyxl
```

### 4. Build the Hadoop Docker image

```bash
cd hadoop
docker build -t hadoop-bamf .
```

This builds a single-node Hadoop 3.3.6 cluster (Ubuntu 22.04, OpenJDK 11).
Build takes ~3–5 minutes the first time (downloads Hadoop).

### 5. Start the container

```bash
docker run -d --name hadoop-bamf \
  -p 9870:9870 -p 8088:8088 -p 9000:9000 \
  -v "$(pwd)/hadoop/youtube_comments.ndjson:/data/youtube_comments.ndjson" \
  -v "$(pwd)/hadoop/youtube_videos.ndjson:/data/youtube_videos.ndjson" \
  -v "$(pwd)/hadoop/mapreduce:/mapreduce" \
  hadoop-bamf
```

Wait ~15 seconds for Hadoop to start, then verify:

```bash
docker exec hadoop-bamf jps
# Should show: NameNode, DataNode, SecondaryNameNode, ResourceManager, NodeManager
```

Web UIs:
- HDFS: http://localhost:9870
- YARN: http://localhost:8088

### 6. Load data into HDFS and run MapReduce cleaning

```bash
docker exec hadoop-bamf bash -c "
  hdfs dfs -mkdir -p /bamf_sentiment/raw && \
  hdfs dfs -put /data/youtube_comments.ndjson /bamf_sentiment/raw/ && \
  hdfs dfs -put /data/youtube_videos.ndjson   /bamf_sentiment/raw/ && \
  hadoop jar \$HADOOP_HOME/share/hadoop/tools/lib/hadoop-streaming-*.jar \
    -files /mapreduce/mapper.py,/mapreduce/reducer.py \
    -mapper  'python3 mapper.py'  \
    -reducer 'python3 reducer.py' \
    -input  /bamf_sentiment/raw/youtube_comments.ndjson \
    -output /bamf_sentiment/cleaned
"
```

Expected output: `Job ... completed successfully` with 54,754 reduce output records.

Check the cleaned data:
```bash
docker exec hadoop-bamf bash -c \
  "hdfs dfs -cat /bamf_sentiment/cleaned/part-00000 | head -3"
```

### 7. Stop the container when done

```bash
docker stop hadoop-bamf && docker rm hadoop-bamf
```

---

## Run the Python analysis pipeline

These steps run locally (not in Docker).

### Step 1 — Sentiment scoring

Reads `data/youtube_comments.json` and `data/youtube_videos.json`, runs
VADER + TextBlob + language detection + topic tagging, and writes
`data/comments_analyzed.json` and `data/videos_analyzed.json`.

```bash
python3 scripts/clean_and_analyze.py
```

Takes ~2–3 minutes for 56k comments.

### Step 2 — Load into PostgreSQL

Create the database first:
```bash
createdb bamf_sentiment
```

Then load:
```bash
python3 scripts/load_postgres.py
```

This creates the `videos` and `comments` tables, loads the data, and prints
SQL analysis results (sentiment distribution, monthly trend, etc.).

### Step 3 — Generate charts

```bash
python3 scripts/export_and_visualize.py
```

Outputs 9 PNG charts to `visualizations/` and an Excel summary to
`data/bamf_analysis_results.xlsx`.

---

## Re-collect data (optional)

Only needed if you want fresh data. Requires your API key in `.env`.

```bash
python3 scripts/collect_youtube.py           # initial pass (~9 queries)
python3 scripts/collect_youtube_expanded.py  # expanded pass (~26 queries)
```

Each pass takes 5–10 minutes. The expanded script appends to existing data.

---

## Project structure

```
.
├── config.py                    # API key (loaded from .env)
├── .env.example                 # Copy to .env and add your key
├── data/                        # Raw + analyzed JSON (gitignored)
├── visualizations/              # Output charts (gitignored)
├── scripts/
│   ├── collect_youtube.py       # Initial data collection
│   ├── collect_youtube_expanded.py
│   ├── clean_and_analyze.py     # Sentiment scoring + topic tagging
│   ├── load_postgres.py         # DB schema + loading + SQL analysis
│   └── export_and_visualize.py  # Charts + Excel export
└── hadoop/
    ├── Dockerfile               # hadoop-bamf image
    ├── config/                  # Hadoop XML configs
    ├── mapreduce/
    │   ├── mapper.py            # Text cleaning mapper
    │   └── reducer.py           # Deduplication reducer
    └── scripts/
        └── start-hadoop.sh      # Entrypoint
```

---

## Troubleshooting

**MapReduce job stuck at 0%**
YARN ran out of memory. Rebuild the image after confirming `hadoop/config/yarn-site.xml`
has `yarn.nodemanager.resource.memory-mb` set to at least `4096`.

**`YOUTUBE_API_KEY` not found**
Make sure you created `.env` from `.env.example` and filled in your key.

**PostgreSQL connection refused**
`load_postgres.py` connects to the local `bamf_sentiment` database with no
password. Adjust `get_conn()` in the script if your setup requires credentials.
