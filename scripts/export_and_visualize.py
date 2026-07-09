import json
import os
import re
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import pandas as pd
from wordcloud import WordCloud
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
VIZ_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "visualizations")
os.makedirs(VIZ_DIR, exist_ok=True)

sns.set_theme(style="whitegrid", font_scale=1.1)
COLORS = {"positive": "#2ecc71", "neutral": "#95a5a6", "negative": "#e74c3c"}

TOPIC_LABELS = {
    "asylum": "Asylum & Refugees",
    "policy": "Immigration Policy",
    "appointment": "Appointments (Termin)",
    "integration_course": "Integration Courses",
    "processing_time": "Processing Time / Delays",
    "visa": "Visa & Residence Permits",
    "general": "General Discussion",
    "citizenship": "Citizenship (Einbürgerung)",
    "staff_service": "Staff & Service Quality",
}

def clean_topic_label(t):
    return TOPIC_LABELS.get(t, t.replace("_", " ").title())


def load_data():
    with open(os.path.join(DATA_DIR, "videos_analyzed.json"), "r", encoding="utf-8") as f:
        videos = json.load(f)
    with open(os.path.join(DATA_DIR, "comments_analyzed.json"), "r", encoding="utf-8") as f:
        comments = json.load(f)

    # Filter out noise (same as DB cleanup)
    noise_ids = set()
    for v in videos:
        t = v["title"].lower()
        ch = v["channel"].lower()
        if any(w in t for w in ["pokemon", "fnaf", "diddy", "roblox", "minecraft", "bricks and minifig", "war trophies", "passfotos selbst", "vorstellungsgespräch"]):
            noise_ids.add(v["video_id"])
        if ch == "bamf" and not any(w in t for w in ["migra", "german", "asylum"]):
            noise_ids.add(v["video_id"])

    videos = [v for v in videos if v["video_id"] not in noise_ids]
    comments = [c for c in comments if c["video_id"] not in noise_ids]

    vdf = pd.DataFrame(videos)
    cdf = pd.DataFrame(comments)
    cdf["published_date"] = pd.to_datetime(cdf["published_at"])
    cdf["year"] = cdf["year_month"].str[:4]
    cdf["vader_compound"] = cdf["vader"].apply(lambda x: x["compound"])
    cdf["vader_label"] = cdf["vader"].apply(lambda x: x["label"])
    cdf["textblob_polarity"] = cdf["textblob"].apply(lambda x: x["polarity"])
    return vdf, cdf


def export_excel(vdf, cdf):
    print("Exporting Excel...")
    excel_path = os.path.join(DATA_DIR, "bamf_analysis_results.xlsx")

    # Monthly trend
    monthly = cdf.groupby("year_month").agg(
        comments=("vader_compound", "count"),
        avg_sentiment=("vader_compound", "mean"),
        positive=("vader_label", lambda x: (x == "positive").sum()),
        neutral=("vader_label", lambda x: (x == "neutral").sum()),
        negative=("vader_label", lambda x: (x == "negative").sum()),
    ).reset_index()
    monthly["neg_pct"] = (monthly["negative"] / monthly["comments"] * 100).round(1)
    monthly["avg_sentiment"] = monthly["avg_sentiment"].round(3)

    # Yearly
    yearly = cdf.groupby("year").agg(
        comments=("vader_compound", "count"),
        avg_sentiment=("vader_compound", "mean"),
        positive=("vader_label", lambda x: (x == "positive").sum()),
        neutral=("vader_label", lambda x: (x == "neutral").sum()),
        negative=("vader_label", lambda x: (x == "negative").sum()),
    ).reset_index()
    yearly["neg_pct"] = (yearly["negative"] / yearly["comments"] * 100).round(1)
    yearly["avg_sentiment"] = yearly["avg_sentiment"].round(3)

    # By topic
    topic_rows = []
    for _, row in cdf.iterrows():
        for t in row["topics"]:
            topic_rows.append({"topic": t, "vader_compound": row["vader_compound"], "vader_label": row["vader_label"]})
    tdf = pd.DataFrame(topic_rows)
    by_topic = tdf.groupby("topic").agg(
        count=("vader_compound", "count"),
        avg_sentiment=("vader_compound", "mean"),
        negative=("vader_label", lambda x: (x == "negative").sum()),
        positive=("vader_label", lambda x: (x == "positive").sum()),
    ).reset_index().sort_values("avg_sentiment")
    by_topic["avg_sentiment"] = by_topic["avg_sentiment"].round(3)

    # By language
    by_lang = cdf[cdf["language"].isin(["en", "de"])].groupby("language").agg(
        comments=("vader_compound", "count"),
        avg_sentiment=("vader_compound", "mean"),
        negative=("vader_label", lambda x: (x == "negative").sum()),
        positive=("vader_label", lambda x: (x == "positive").sum()),
    ).reset_index()
    by_lang["neg_pct"] = (by_lang["negative"] / by_lang["comments"] * 100).round(1)
    by_lang["avg_sentiment"] = by_lang["avg_sentiment"].round(3)

    # Overall
    overall = pd.DataFrame({
        "metric": ["Total Videos", "Total Comments", "Date Range", "Avg Sentiment", "% Positive", "% Neutral", "% Negative"],
        "value": [
            len(vdf), len(cdf),
            f"{cdf['year_month'].min()} to {cdf['year_month'].max()}",
            f"{cdf['vader_compound'].mean():.3f}",
            f"{(cdf['vader_label'] == 'positive').mean() * 100:.1f}%",
            f"{(cdf['vader_label'] == 'neutral').mean() * 100:.1f}%",
            f"{(cdf['vader_label'] == 'negative').mean() * 100:.1f}%",
        ]
    })

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        overall.to_excel(writer, sheet_name="Overview", index=False)
        monthly.to_excel(writer, sheet_name="Monthly Trend", index=False)
        yearly.to_excel(writer, sheet_name="Yearly Comparison", index=False)
        by_topic.to_excel(writer, sheet_name="By Topic", index=False)
        by_lang.to_excel(writer, sheet_name="By Language", index=False)

    print(f"  Saved: {excel_path}")


def plot_1_monthly_trend(cdf):
    print("Chart 1: Monthly sentiment trend...")
    monthly = cdf.groupby("year_month")["vader_compound"].agg(["mean", "count"]).reset_index()
    monthly["date"] = pd.to_datetime(monthly["year_month"] + "-01")

    fig, ax1 = plt.subplots(figsize=(14, 6))
    ax1.plot(monthly["date"], monthly["mean"], color="#e74c3c", linewidth=2, marker="o", markersize=4, label="Avg Sentiment")
    ax1.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
    ax1.fill_between(monthly["date"], monthly["mean"], 0, where=monthly["mean"] >= 0, alpha=0.15, color="#2ecc71")
    ax1.fill_between(monthly["date"], monthly["mean"], 0, where=monthly["mean"] < 0, alpha=0.15, color="#e74c3c")
    ax1.set_xlabel("Month")
    ax1.set_ylabel("Average Sentiment (VADER Compound)", color="#e74c3c")
    ax1.set_title("BAMF Sentiment Trend Over Time (Jan 2024 – June 2026)", fontsize=14, fontweight="bold")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=45)

    ax2 = ax1.twinx()
    ax2.bar(monthly["date"], monthly["count"], width=20, alpha=0.15, color="#3498db", label="Comment Volume")
    ax2.set_ylabel("Comment Volume", color="#3498db")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    plt.tight_layout()
    plt.savefig(os.path.join(VIZ_DIR, "01_monthly_sentiment_trend.png"), dpi=150)
    plt.close()


def plot_2_sentiment_by_topic(cdf):
    print("Chart 2: Sentiment by topic...")
    topic_rows = []
    for _, row in cdf.iterrows():
        for t in row["topics"]:
            topic_rows.append({"topic": clean_topic_label(t), "compound": row["vader_compound"], "label": row["vader_label"]})
    tdf = pd.DataFrame(topic_rows)
    topic_avg = tdf.groupby("topic")["compound"].mean().sort_values()
    topic_count = tdf.groupby("topic")["compound"].count()

    fig, ax = plt.subplots(figsize=(12, 7))
    colors = ["#e74c3c" if v < -0.05 else "#2ecc71" if v > 0.05 else "#95a5a6" for v in topic_avg.values]
    bars = ax.barh(topic_avg.index, topic_avg.values, color=colors, edgecolor="white", linewidth=0.5)
    ax.axvline(x=0, color="black", linewidth=0.8)
    ax.set_xlabel("Average Sentiment Score (VADER)\n← More Negative          More Positive →", fontsize=11)
    ax.set_title("Public Sentiment by Topic — BAMF & German Immigration\n(YouTube Comments, 2024–2026)", fontsize=13, fontweight="bold")

    for bar, val in zip(bars, topic_avg.values):
        n = topic_count.get(topic_avg.index[list(topic_avg.values).index(val)], 0)
        ax.text(val + (0.005 if val >= 0 else -0.005), bar.get_y() + bar.get_height() / 2,
                f"{val:.3f} (n={n:,})", va="center", ha="left" if val >= 0 else "right", fontsize=9)

    plt.tight_layout()
    plt.savefig(os.path.join(VIZ_DIR, "02_sentiment_by_topic.png"), dpi=150)
    plt.close()


def plot_3_language_comparison(cdf):
    print("Chart 3: German vs English sentiment...")
    lang_df = cdf[cdf["language"].isin(["en", "de"])].copy()
    lang_df["language"] = lang_df["language"].map({"en": "English", "de": "German"})

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Sentiment distribution
    for lang, color in [("English", "#3498db"), ("German", "#e67e22")]:
        subset = lang_df[lang_df["language"] == lang]["vader_compound"]
        ax1.hist(subset, bins=50, alpha=0.6, color=color, label=f"{lang} (n={len(subset):,})", density=True)
    ax1.axvline(x=0, color="black", linewidth=0.8, linestyle="--")
    ax1.set_xlabel("Sentiment Score")
    ax1.set_ylabel("Density")
    ax1.set_title("Sentiment Distribution: German vs English")
    ax1.legend()

    # Stacked bar
    crosstab = pd.crosstab(lang_df["language"], lang_df["vader_label"], normalize="index") * 100
    crosstab = crosstab[["negative", "neutral", "positive"]]
    crosstab.plot(kind="bar", stacked=True, ax=ax2, color=[COLORS["negative"], COLORS["neutral"], COLORS["positive"]])
    ax2.set_ylabel("Percentage")
    ax2.set_title("Sentiment Breakdown by Language")
    ax2.set_xticklabels(ax2.get_xticklabels(), rotation=0)
    ax2.legend(title="Sentiment")

    plt.tight_layout()
    plt.savefig(os.path.join(VIZ_DIR, "03_language_comparison.png"), dpi=150)
    plt.close()


def plot_4_yearly_comparison(cdf):
    print("Chart 4: Year-over-year...")
    yearly = cdf.groupby("year")["vader_label"].value_counts(normalize=True).unstack() * 100
    yearly = yearly[["negative", "neutral", "positive"]]

    fig, ax = plt.subplots(figsize=(8, 5))
    yearly.plot(kind="bar", stacked=True, ax=ax, color=[COLORS["negative"], COLORS["neutral"], COLORS["positive"]])
    ax.set_ylabel("Percentage (%)")
    ax.set_title("Year-over-Year Sentiment Shift (2024–2026)", fontsize=13, fontweight="bold")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
    ax.legend(title="Sentiment", bbox_to_anchor=(1.02, 1))

    for i, year in enumerate(yearly.index):
        cumsum = 0
        for col in ["negative", "neutral", "positive"]:
            val = yearly.loc[year, col]
            ax.text(i, cumsum + val / 2, f"{val:.1f}%", ha="center", va="center", fontsize=9, fontweight="bold", color="white")
            cumsum += val

    plt.tight_layout()
    plt.savefig(os.path.join(VIZ_DIR, "04_yearly_comparison.png"), dpi=150)
    plt.close()


def plot_5_overall_donut(cdf):
    print("Chart 5: Overall sentiment donut...")
    counts = cdf["vader_label"].value_counts()
    labels = ["Positive", "Neutral", "Negative"]
    sizes = [counts.get("positive", 0), counts.get("neutral", 0), counts.get("negative", 0)]
    colors_list = [COLORS["positive"], COLORS["neutral"], COLORS["negative"]]

    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors_list, autopct="%1.1f%%",
                                       startangle=90, pctdistance=0.8, wedgeprops=dict(width=0.4))
    for t in autotexts:
        t.set_fontsize(12)
        t.set_fontweight("bold")
    ax.set_title(f"Overall Sentiment Distribution\n({sum(sizes):,} comments)", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(VIZ_DIR, "05_overall_donut.png"), dpi=150)
    plt.close()


def plot_6_wordclouds(cdf):
    print("Chart 6: Word clouds (English comments only for readability)...")
    stop_words = {"the", "a", "an", "is", "it", "to", "in", "for", "of", "and", "that", "this",
                  "with", "on", "are", "was", "be", "at", "have", "has", "had", "not", "but",
                  "they", "them", "their", "you", "your", "we", "our", "he", "she", "his", "her",
                  "from", "or", "as", "by", "do", "if", "so", "just", "about", "would", "can",
                  "will", "there", "been", "more", "when", "who", "what", "how", "all", "my",
                  "me", "than", "no", "like", "very", "also", "up", "out", "one", "its",
                  "these", "those", "don", "get", "got", "should", "could", "really",
                  "much", "even", "still", "going", "want", "think", "know", "right",
                  "said", "way", "back", "thing", "things", "many", "make", "made",
                  "people", "country", "video", "said", "would", "actually", "see"}

    en_df = cdf[cdf["language"] == "en"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7))

    pos_text = " ".join(en_df[en_df["vader_label"] == "positive"]["text"].tolist())
    neg_text = " ".join(en_df[en_df["vader_label"] == "negative"]["text"].tolist())

    wc_pos = WordCloud(width=900, height=500, background_color="white", colormap="Greens",
                       stopwords=stop_words, max_words=60, min_font_size=12).generate(pos_text)
    wc_neg = WordCloud(width=900, height=500, background_color="white", colormap="Reds",
                       stopwords=stop_words, max_words=60, min_font_size=12).generate(neg_text)

    ax1.imshow(wc_pos, interpolation="bilinear")
    ax1.set_title("Positive Comments — Most Frequent Words\n(English comments only)", fontsize=13, fontweight="bold", color="#2ecc71")
    ax1.axis("off")

    ax2.imshow(wc_neg, interpolation="bilinear")
    ax2.set_title("Negative Comments — Most Frequent Words\n(English comments only)", fontsize=13, fontweight="bold", color="#e74c3c")
    ax2.axis("off")

    plt.suptitle("Word Cloud Analysis — BAMF & German Immigration Discourse on YouTube", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(VIZ_DIR, "06_wordclouds_english.png"), dpi=150, bbox_inches="tight")
    plt.close()

    # Also make a German word cloud with translations annotated
    print("Chart 6b: Word clouds (German comments with translations)...")
    de_stop = {"die", "der", "das", "und", "ist", "ein", "eine", "den", "dem", "des",
               "nicht", "auch", "sich", "mit", "auf", "für", "von", "ich", "es", "sie",
               "wir", "man", "nur", "noch", "aber", "dass", "nach", "bei", "oder", "was",
               "werden", "schon", "wenn", "hat", "sind", "hier", "dann", "mal", "war",
               "im", "zu", "da", "so", "doch", "wie", "mehr", "ja", "kann", "haben",
               "alle", "diese", "wird", "sein", "gibt", "wer", "zum", "zur", "aus",
               "bin", "mir", "dir", "uns", "ihr", "mich", "dich", "einer", "einem",
               "er", "als", "über", "vor", "alles", "du", "was", "jetzt", "immer",
               "können", "müssen", "sollen", "wollen", "muss", "soll", "will", "kann"}

    de_df = cdf[cdf["language"] == "de"]
    de_neg_text = " ".join(de_df[de_df["vader_label"] == "negative"]["text"].tolist())
    de_pos_text = " ".join(de_df[de_df["vader_label"] == "positive"]["text"].tolist())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7))

    if de_pos_text.strip():
        wc_de_pos = WordCloud(width=900, height=500, background_color="white", colormap="Greens",
                              stopwords=de_stop, max_words=50, min_font_size=12).generate(de_pos_text)
        ax1.imshow(wc_de_pos, interpolation="bilinear")
    ax1.set_title("Positive German Comments — Key Words", fontsize=13, fontweight="bold", color="#2ecc71")
    ax1.axis("off")

    if de_neg_text.strip():
        wc_de_neg = WordCloud(width=900, height=500, background_color="white", colormap="Reds",
                              stopwords=de_stop, max_words=50, min_font_size=12).generate(de_neg_text)
        ax2.imshow(wc_de_neg, interpolation="bilinear")
    ax2.set_title("Negative German Comments — Key Words", fontsize=13, fontweight="bold", color="#e74c3c")
    ax2.axis("off")

    translations = "Key German terms: Flüchtlinge=Refugees, Asyl=Asylum, Abschiebung=Deportation, Einwanderung=Immigration, Arbeit=Work, Sprache=Language, Kriminalität=Crime, Staat=State"
    plt.suptitle("Word Cloud — German-Language Comments\n", fontsize=14, fontweight="bold", y=1.02)
    fig.text(0.5, -0.02, translations, ha="center", fontsize=10, style="italic", color="gray")
    plt.tight_layout()
    plt.savefig(os.path.join(VIZ_DIR, "06b_wordclouds_german.png"), dpi=150, bbox_inches="tight")
    plt.close()


def plot_7_top_channels(cdf, vdf):
    print("Chart 7: Top channels sentiment...")
    merged = cdf.merge(vdf[["video_id", "channel"]], on="video_id", how="left")
    ch_stats = merged.groupby("channel").agg(
        count=("vader_compound", "count"),
        avg_sent=("vader_compound", "mean")
    ).reset_index()
    ch_stats = ch_stats[ch_stats["count"] >= 50].sort_values("avg_sent")
    top = pd.concat([ch_stats.head(8), ch_stats.tail(5)]).drop_duplicates()

    fig, ax = plt.subplots(figsize=(10, 7))
    colors = ["#e74c3c" if v < -0.05 else "#2ecc71" if v > 0.05 else "#95a5a6" for v in top["avg_sent"]]
    ax.barh(top["channel"], top["avg_sent"], color=colors)
    ax.axvline(x=0, color="black", linewidth=0.8)
    ax.set_xlabel("Average Sentiment Score")
    ax.set_title("Sentiment by YouTube Channel (min 50 comments)", fontsize=13, fontweight="bold")

    for i, (_, row) in enumerate(top.iterrows()):
        ax.text(row["avg_sent"] + 0.005 * (1 if row["avg_sent"] >= 0 else -1),
                i, f"n={row['count']}", va="center", fontsize=8, color="gray")

    plt.tight_layout()
    plt.savefig(os.path.join(VIZ_DIR, "07_top_channels.png"), dpi=150)
    plt.close()


def plot_8_topic_sentiment_over_time(cdf):
    print("Chart 8: Topic sentiment over time...")
    topic_rows = []
    for _, row in cdf.iterrows():
        for t in row["topics"]:
            if t != "general":
                topic_rows.append({"topic": t, "year_month": row["year_month"], "compound": row["vader_compound"]})
    tdf = pd.DataFrame(topic_rows)

    quarterly = tdf.copy()
    quarterly["quarter"] = quarterly["year_month"].str[:4] + "-Q" + ((pd.to_datetime(quarterly["year_month"] + "-01").dt.month - 1) // 3 + 1).astype(str)
    q_avg = quarterly.groupby(["quarter", "topic"])["compound"].mean().reset_index()

    fig, ax = plt.subplots(figsize=(14, 7))
    key_topics = ["asylum", "policy", "visa", "citizenship", "appointment"]
    topic_colors = {
        "asylum": "#e74c3c",
        "policy": "#e67e22",
        "visa": "#3498db",
        "citizenship": "#2ecc71",
        "appointment": "#9b59b6",
    }
    for topic in key_topics:
        subset = q_avg[q_avg["topic"] == topic].sort_values("quarter")
        if len(subset) > 1:
            ax.plot(subset["quarter"], subset["compound"], marker="o",
                    label=clean_topic_label(topic), linewidth=2.5,
                    color=topic_colors.get(topic, None), markersize=6)

    ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
    ax.set_xlabel("Quarter", fontsize=11)
    ax.set_ylabel("Average Sentiment Score\n← Negative          Positive →", fontsize=11)
    ax.set_title("How Sentiment Shifted Over Time by Topic (Quarterly Averages)\nBAMF & German Immigration — YouTube Comments, 2024–2026",
                 fontsize=13, fontweight="bold")
    ax.legend(title="Topic", fontsize=10, title_fontsize=11, loc="upper right")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(VIZ_DIR, "08_topic_sentiment_over_time.png"), dpi=150)
    plt.close()


def main():
    vdf, cdf = load_data()
    print(f"Loaded {len(vdf)} videos, {len(cdf)} comments")

    export_excel(vdf, cdf)

    plot_1_monthly_trend(cdf)
    plot_2_sentiment_by_topic(cdf)
    plot_3_language_comparison(cdf)
    plot_4_yearly_comparison(cdf)
    plot_5_overall_donut(cdf)
    plot_6_wordclouds(cdf)  # generates both english + german word clouds
    plot_7_top_channels(cdf, vdf)
    plot_8_topic_sentiment_over_time(cdf)

    print(f"\nAll done! Files saved to:")
    print(f"  Excel: data/bamf_analysis_results.xlsx")
    print(f"  Charts: visualizations/ ({len(os.listdir(VIZ_DIR))} files)")
    for f in sorted(os.listdir(VIZ_DIR)):
        print(f"    - {f}")


if __name__ == "__main__":
    main()
