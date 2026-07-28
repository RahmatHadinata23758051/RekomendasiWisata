import os
import subprocess
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def generate_paper_visualizations(
    results_csv="reports/benchmark_recommender_results.csv",
    output_dir="reports/figures"
):
    os.makedirs(output_dir, exist_ok=True)
    if not os.path.exists(results_csv):
        raise FileNotFoundError(f"Benchmark results CSV not found at: {results_csv}")

    # 1. Try running Rscript if available
    r_script = "Model/visualization/generate_benchmark_plots.R"
    try:
        print("Attempting to execute R visualization script (ggplot2)...")
        res = subprocess.run(["Rscript", r_script], capture_output=True, text=True, check=True)
        print("Rscript Output:\n", res.stdout)
        print("R Visualizations generated successfully!")
        return
    except Exception as e:
        print(f"Rscript not available or failed ({e}). Falling back to Seaborn/Matplotlib Academic Paper styling...")

    # 2. Python Matplotlib / Seaborn Publication-Quality Styling
    df = pd.read_csv(results_csv)
    df["algo_clean"] = df["algorithm"].str.replace("Candidate ", "C").str.replace("Baseline ", "B")

    sns.set_theme(style="whitegrid", font="sans-serif")
    palette = ["#2b5c8f", "#3690c0", "#67a9cf", "#02818a"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=300)

    # Plot 1: Precision@10 Bar Chart
    ax1 = axes[0]
    bars = ax1.bar(df["algo_clean"], df["precision_at_10"], color=palette, edgecolor="black", width=0.5)
    ax1.set_title("Algorithm Performance Comparison (Precision@10)", fontsize=12, fontweight="bold", pad=12)
    ax1.set_xlabel("Algorithm Candidate", fontsize=10, fontweight="bold")
    ax1.set_ylabel("Mean Precision@10 Score", fontsize=10, fontweight="bold")
    ax1.set_ylim(0, 1.1)

    for bar in bars:
        height = bar.get_height()
        ax1.annotate(f"{height:.3f}",
                     xy=(bar.get_x() + bar.get_width() / 2, height),
                     xytext=(0, 3),  # 3 points vertical offset
                     textcoords="offset points",
                     ha='center', va='bottom', fontsize=9, fontweight='bold')

    # Plot 2: Latency vs Coverage Scatter
    ax2 = axes[1]
    ax2.scatter(df["latency_ms"], df["catalog_coverage_pct"], color=palette, s=150, zorder=5)
    for _, row in df.iterrows():
        ax2.annotate(row["algo_clean"], (row["latency_ms"], row["catalog_coverage_pct"]),
                     textcoords="offset points", xytext=(0, 8), ha='center', fontsize=9, fontweight='bold')

    ax2.set_title("Latency vs Catalog Coverage Tradeoff", fontsize=12, fontweight="bold", pad=12)
    ax2.set_xlabel("Inference Latency (ms)", fontsize=10, fontweight="bold")
    ax2.set_ylabel("Catalog Coverage (%)", fontsize=10, fontweight="bold")
    ax2.set_ylim(0, max(df["catalog_coverage_pct"]) * 1.3)
    ax2.set_xlim(0, max(df["latency_ms"]) * 1.3)

    plt.tight_layout()
    out_img = os.path.join(output_dir, "benchmark_recommender_paper_figure.png")
    plt.savefig(out_img, dpi=300)
    plt.close()
    print(f"Academic Paper Visualization saved to: {out_img}")

if __name__ == "__main__":
    generate_paper_visualizations()
