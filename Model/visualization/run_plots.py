import os
import subprocess
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

def generate_paper_visualizations(
    rec_csv="reports/benchmark_recommender_results.csv",
    sent_csv="reports/benchmark_sentiment_results.csv",
    output_dir="reports/figures"
):
    os.makedirs(output_dir, exist_ok=True)
    sns.set_theme(style="whitegrid", font="sans-serif")
    paper_colors = ["#2b5c8f", "#3690c0", "#67a9cf", "#02818a"]

    # -------------------------------------------------------------
    # 1. Recommender Benchmark Figure (Publication Quality)
    # -------------------------------------------------------------
    if os.path.exists(rec_csv):
        df_rec = pd.read_csv(rec_csv)
        df_rec["algo_clean"] = [
            "B1: Simple Cosine",
            "B2: Weighted Multi-Metric",
            "C3: TF-IDF + Penalty",
            "C4: Hybrid Multi-Objective"
        ]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)

        # Plot 1A: Horizontal Bar Chart for Precision@10 (Prevents Text Overlap)
        bars = ax1.barh(df_rec["algo_clean"], df_rec["precision_at_10"], color=paper_colors, edgecolor="black", height=0.55)
        ax1.set_title("Algorithm Performance Comparison (Precision@10)", fontsize=12, fontweight="bold", pad=12)
        ax1.set_xlabel("Mean Precision@10 Score", fontsize=10, fontweight="bold")
        ax1.set_xlim(0, 1.15)
        ax1.invert_yaxis()  # Best on top

        for bar in bars:
            width = bar.get_width()
            ax1.annotate(f"{width:.4f}",
                         xy=(width, bar.get_y() + bar.get_height() / 2),
                         xytext=(6, 0), textcoords="offset points",
                         ha="left", va="center", fontsize=9, fontweight="bold")

        # Plot 1B: Latency vs Catalog Coverage Scatter (Non-overlapping labels)
        scatter = ax2.scatter(df_rec["latency_ms"], df_rec["catalog_coverage_pct"], color=paper_colors, s=180, zorder=5, edgecolor="black")
        
        # Stagger text label offsets to guarantee zero overlap
        y_offsets = [12, -15, 12, -15]
        x_offsets = [-5, 5, -5, 5]

        for i, row in df_rec.iterrows():
            ax2.annotate(row["algo_clean"], 
                         xy=(row["latency_ms"], row["catalog_coverage_pct"]),
                         xytext=(x_offsets[i], y_offsets[i]), 
                         textcoords="offset points",
                         ha="center", fontsize=9, fontweight="bold",
                         bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#cccccc", alpha=0.8))

        ax2.set_title("Inference Latency vs Catalog Coverage Tradeoff", fontsize=12, fontweight="bold", pad=12)
        ax2.set_xlabel("Inference Latency (ms)", fontsize=10, fontweight="bold")
        ax2.set_ylabel("Catalog Coverage (%)", fontsize=10, fontweight="bold")
        ax2.set_ylim(0, max(df_rec["catalog_coverage_pct"]) * 1.4)
        ax2.set_xlim(0, max(df_rec["latency_ms"]) * 1.4)

        plt.tight_layout(pad=3.0)
        out_rec_fig = os.path.join(output_dir, "recommender_benchmark_paper_figure.png")
        plt.savefig(out_rec_fig, dpi=300)
        plt.close()
        print(f"Recommender Paper Figure saved to: {out_rec_fig}")

    # -------------------------------------------------------------
    # 2. Sentiment Benchmark Figure (Publication Quality)
    # -------------------------------------------------------------
    if os.path.exists(sent_csv):
        df_sent = pd.read_csv(sent_csv)
        df_sent["algo_clean"] = [
            "B1: Lexicon (VADER)",
            "B2: TF-IDF + Logistic Reg",
            "C3: Fine-Tuned IndoBERT"
        ]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)

        # Plot 2A: Accuracy vs Macro F1 Score
        x = np.arange(len(df_sent))
        width = 0.35

        rects1 = ax1.bar(x - width/2, df_sent["accuracy"], width, label="Accuracy", color="#2b5c8f", edgecolor="black")
        rects2 = ax1.bar(x + width/2, df_sent["macro_f1"], width, label="Macro F1-Score", color="#02818a", edgecolor="black")

        ax1.set_title("Sentiment Model Comparison (Accuracy & Macro F1)", fontsize=12, fontweight="bold", pad=12)
        ax1.set_ylabel("Score (0.0 to 1.0)", fontsize=10, fontweight="bold")
        ax1.set_xticks(x)
        ax1.set_xticklabels(df_sent["algo_clean"], fontsize=9, fontweight="bold")
        ax1.set_ylim(0, 1.15)
        ax1.legend(loc="upper left")

        for r in rects1:
            h = r.get_height()
            ax1.annotate(f"{h:.3f}", xy=(r.get_x() + r.get_width()/2, h), xytext=(0, 3),
                         textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")
        for r in rects2:
            h = r.get_height()
            ax1.annotate(f"{h:.3f}", xy=(r.get_x() + r.get_width()/2, h), xytext=(0, 3),
                         textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")

        # Plot 2B: Latency per Sample (ms)
        bars_lat = ax2.bar(df_sent["algo_clean"], df_sent["latency_per_sample_ms"], color=["#3690c0", "#67a9cf", "#02818a"], edgecolor="black", width=0.45)
        ax2.set_title("Inference Latency per Sample (ms)", fontsize=12, fontweight="bold", pad=12)
        ax2.set_ylabel("Latency per Sample (ms)", fontsize=10, fontweight="bold")
        ax2.set_ylim(0, max(df_sent["latency_per_sample_ms"]) * 1.35)

        for bar in bars_lat:
            h = bar.get_height()
            ax2.annotate(f"{h:.3f} ms", xy=(bar.get_x() + bar.get_width()/2, h), xytext=(0, 3),
                         textcoords="offset points", ha="center", va="bottom", fontsize=9, fontweight="bold")

        plt.tight_layout(pad=3.0)
        out_sent_fig = os.path.join(output_dir, "sentiment_benchmark_paper_figure.png")
        plt.savefig(out_sent_fig, dpi=300)
        plt.close()
        print(f"Sentiment Paper Figure saved to: {out_sent_fig}")

    # Also attempt Rscript if R is available
    r_script = "Model/visualization/generate_benchmark_plots.R"
    if os.path.exists(r_script):
        try:
            subprocess.run(["Rscript", r_script], capture_output=True, text=True, check=False)
        except Exception:
            pass

if __name__ == "__main__":
    generate_paper_visualizations()
