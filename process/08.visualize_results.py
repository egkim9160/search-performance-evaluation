#!/usr/bin/env python3
"""
Step08: Visualize evaluation results
Creates charts and reports comparing search methods
"""
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns

# Set up matplotlib for Korean text
matplotlib.rcParams['font.family'] = 'NanumGothic'
matplotlib.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")


# Ensure project root is on sys.path
try:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
except Exception:
    PROJECT_ROOT = Path.cwd()


def plot_metric_comparison(
    agg_df: pd.DataFrame,
    metrics: List[str],
    output_dir: str,
    title: str = "Search Method Comparison"
):
    """Plot bar chart comparing methods on multiple metrics"""

    n_metrics = len(metrics)
    fig, axes = plt.subplots(1, n_metrics, figsize=(6*n_metrics, 5))

    if n_metrics == 1:
        axes = [axes]

    for idx, metric in enumerate(metrics):
        if metric not in agg_df.columns:
            continue

        ax = axes[idx]

        # Sort by metric value
        data = agg_df[metric].sort_values(ascending=False)

        # Plot
        bars = ax.bar(range(len(data)), data.values, color='steelblue', alpha=0.7)

        # Color the best bar
        bars[0].set_color('gold')
        bars[0].set_alpha(0.9)

        # Set labels
        ax.set_xticks(range(len(data)))
        ax.set_xticklabels(data.index, rotation=45, ha='right')
        ax.set_ylabel(metric.upper(), fontsize=12, fontweight='bold')
        ax.set_title(f'{metric.upper()}', fontsize=13, fontweight='bold')

        # Add value labels on bars
        for i, (idx_val, value) in enumerate(data.items()):
            ax.text(i, value + 0.01, f'{value:.4f}',
                   ha='center', va='bottom', fontsize=10, fontweight='bold')

        # Set y-axis range
        ax.set_ylim(0, min(1.0, data.max() * 1.15))

        # Grid
        ax.grid(axis='y', alpha=0.3, linestyle='--')

    plt.suptitle(title, fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()

    # Save
    output_file = os.path.join(output_dir, 'method_comparison.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_file}")

    plt.close()


def plot_metric_heatmap(
    agg_df: pd.DataFrame,
    metrics: List[str],
    output_dir: str
):
    """Plot heatmap of all metrics"""

    # Select metrics
    plot_data = agg_df[metrics].T

    # Create figure
    fig, ax = plt.subplots(figsize=(max(10, len(agg_df)*1.5), max(6, len(metrics)*0.8)))

    # Plot heatmap
    sns.heatmap(
        plot_data,
        annot=True,
        fmt='.4f',
        cmap='YlOrRd',
        cbar_kws={'label': 'Metric Value'},
        linewidths=0.5,
        ax=ax
    )

    ax.set_title('Evaluation Metrics Heatmap', fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('Search Method', fontsize=12, fontweight='bold')
    ax.set_ylabel('Metric', fontsize=12, fontweight='bold')

    plt.tight_layout()

    # Save
    output_file = os.path.join(output_dir, 'metrics_heatmap.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_file}")

    plt.close()


def plot_ndcg_by_k(
    agg_df: pd.DataFrame,
    k_values: List[int],
    output_dir: str
):
    """Plot nDCG across different K values"""

    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot each method
    for method in agg_df.index:
        ndcg_values = []
        valid_k = []

        for k in sorted(k_values):
            metric_name = f'ndcg@{k}'
            if metric_name in agg_df.columns:
                ndcg_values.append(agg_df.loc[method, metric_name])
                valid_k.append(k)

        if ndcg_values:
            ax.plot(valid_k, ndcg_values, marker='o', linewidth=2, markersize=8, label=method)

    ax.set_xlabel('K', fontsize=12, fontweight='bold')
    ax.set_ylabel('nDCG@K', fontsize=12, fontweight='bold')
    ax.set_title('nDCG across different K values', fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3, linestyle='--')

    plt.tight_layout()

    # Save
    output_file = os.path.join(output_dir, 'ndcg_by_k.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_file}")

    plt.close()


def plot_recall_by_k(
    agg_df: pd.DataFrame,
    k_values: List[int],
    output_dir: str
):
    """Plot Recall across different K values"""

    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot each method
    for method in agg_df.index:
        recall_values = []
        valid_k = []

        for k in sorted(k_values):
            metric_name = f'recall@{k}'
            if metric_name in agg_df.columns:
                recall_values.append(agg_df.loc[method, metric_name])
                valid_k.append(k)

        if recall_values:
            ax.plot(valid_k, recall_values, marker='s', linewidth=2, markersize=8, label=method)

    ax.set_xlabel('K', fontsize=12, fontweight='bold')
    ax.set_ylabel('Recall@K', fontsize=12, fontweight='bold')
    ax.set_title('Recall across different K values', fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3, linestyle='--')

    plt.tight_layout()

    # Save
    output_file = os.path.join(output_dir, 'recall_by_k.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_file}")

    plt.close()


def plot_per_query_distribution(
    per_query_dfs: Dict[str, pd.DataFrame],
    metric: str,
    output_dir: str
):
    """Plot distribution of per-query metrics"""

    fig, ax = plt.subplots(figsize=(12, 6))

    data_to_plot = []
    labels = []

    for method, df in per_query_dfs.items():
        if metric in df.columns:
            data_to_plot.append(df[metric].values)
            labels.append(method)

    if not data_to_plot:
        print(f"  ⚠ No data for metric: {metric}")
        return

    # Create violin plot
    parts = ax.violinplot(data_to_plot, positions=range(len(labels)),
                          showmeans=True, showmedians=True)

    # Color
    for pc in parts['bodies']:
        pc.set_facecolor('steelblue')
        pc.set_alpha(0.6)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel(metric.upper(), fontsize=12, fontweight='bold')
    ax.set_title(f'Distribution of {metric.upper()} across queries',
                fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    plt.tight_layout()

    # Save
    output_file = os.path.join(output_dir, f'distribution_{metric}.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: {output_file}")

    plt.close()


def create_summary_report(
    agg_df: pd.DataFrame,
    output_dir: str
):
    """Create markdown summary report"""

    report_lines = []

    report_lines.append("# Search Evaluation Results Summary")
    report_lines.append("")
    report_lines.append(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")

    # Overall comparison
    report_lines.append("## Overall Comparison")
    report_lines.append("")

    # Key metrics table
    key_metrics = ['ndcg@10', 'ndcg@20', 'recall@10', 'recall@20', 'mrr', 'map']
    available_metrics = [m for m in key_metrics if m in agg_df.columns]

    if available_metrics:
        report_lines.append("### Key Metrics")
        report_lines.append("")

        # Create markdown table
        header = "| Method | " + " | ".join([m.upper() for m in available_metrics]) + " |"
        separator = "|--------|" + "|".join(["--------"] * len(available_metrics)) + "|"

        report_lines.append(header)
        report_lines.append(separator)

        for method in agg_df.index:
            row = f"| {method} |"
            for metric in available_metrics:
                value = agg_df.loc[method, metric]
                row += f" {value:.4f} |"
            report_lines.append(row)

        report_lines.append("")

    # Best method per metric
    report_lines.append("## Best Method per Metric")
    report_lines.append("")

    for metric in available_metrics:
        best_method = agg_df[metric].idxmax()
        best_value = agg_df[metric].max()
        report_lines.append(f"- **{metric.upper()}**: {best_method} ({best_value:.4f})")

    report_lines.append("")

    # Performance differences
    report_lines.append("## Performance Differences (vs. Baseline)")
    report_lines.append("")

    if 'lexical' in agg_df.index:
        baseline = 'lexical'
        report_lines.append(f"Baseline: {baseline}")
        report_lines.append("")

        for metric in available_metrics:
            report_lines.append(f"### {metric.upper()}")
            report_lines.append("")

            baseline_value = agg_df.loc[baseline, metric]

            for method in agg_df.index:
                if method == baseline:
                    continue

                value = agg_df.loc[method, metric]
                diff = value - baseline_value
                pct_change = (diff / baseline_value * 100) if baseline_value > 0 else 0

                symbol = "✅" if diff > 0 else "❌" if diff < 0 else "➖"
                report_lines.append(
                    f"- {symbol} **{method}**: {value:.4f} "
                    f"({diff:+.4f}, {pct_change:+.1f}%)"
                )

            report_lines.append("")

    # Save report
    report_file = os.path.join(output_dir, 'EVALUATION_REPORT.md')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print(f"  ✓ Saved: {report_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Step08: Visualize evaluation results"
    )
    parser.add_argument(
        "--results_dir",
        default="data/evaluation_results",
        help="Directory containing evaluation results"
    )
    parser.add_argument(
        "--output_dir",
        help="Output directory for visualizations (default: same as results_dir)"
    )
    parser.add_argument(
        "--k_values",
        nargs="+",
        type=int,
        default=[5, 10, 20],
        help="K values to visualize (default: 5 10 20)"
    )
    args = parser.parse_args()

    # Set output directory
    output_dir = args.output_dir or args.results_dir
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 70)
    print("Step08: Visualize Evaluation Results")
    print("=" * 70)

    # Load aggregated metrics
    print(f"\n[1] Loading results from: {args.results_dir}")

    agg_file = os.path.join(args.results_dir, 'aggregated_metrics.csv')
    if not os.path.exists(agg_file):
        print(f"  ✗ Aggregated metrics file not found: {agg_file}")
        print("  Please run step 07 first: python process/07.calculate_metrics.py")
        sys.exit(1)

    agg_df = pd.read_csv(agg_file, index_col='method')
    print(f"  ✓ Loaded aggregated metrics: {len(agg_df)} methods")

    # Load per-query metrics
    per_query_dfs = {}
    for method in agg_df.index:
        per_query_file = os.path.join(args.results_dir, f'per_query_metrics_{method}.csv')
        if os.path.exists(per_query_file):
            per_query_dfs[method] = pd.read_csv(per_query_file)
            print(f"  ✓ Loaded per-query metrics: {method}")

    # Create visualizations
    print(f"\n[2] Creating visualizations...")

    # 1. Overall comparison
    key_metrics = ['ndcg@10', 'ndcg@20', 'mrr']
    available_metrics = [m for m in key_metrics if m in agg_df.columns]

    if available_metrics:
        plot_metric_comparison(agg_df, available_metrics, output_dir)

    # 2. Heatmap
    all_metrics = [col for col in agg_df.columns if '@' in col or col in ['mrr', 'map']]
    if all_metrics:
        plot_metric_heatmap(agg_df, all_metrics, output_dir)

    # 3. nDCG by K
    plot_ndcg_by_k(agg_df, args.k_values, output_dir)

    # 4. Recall by K
    plot_recall_by_k(agg_df, args.k_values, output_dir)

    # 5. Per-query distributions
    if per_query_dfs:
        for metric in ['ndcg@20', 'recall@20']:
            plot_per_query_distribution(per_query_dfs, metric, output_dir)

    # Create summary report
    print(f"\n[3] Creating summary report...")
    create_summary_report(agg_df, output_dir)

    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Input directory: {args.results_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Visualizations created: 6+ charts")
    print(f"Report: EVALUATION_REPORT.md")
    print("=" * 70)


if __name__ == "__main__":
    main()
