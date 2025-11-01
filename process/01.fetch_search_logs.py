#!/usr/bin/env python3
"""
Fetch search log data from MySQL database (medigate.SE_LOG table)
Query: Search logs from MUZZIMA category after 2024-01-01
"""
import os
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import mysql.connector
from mysql.connector.connection import MySQLConnection
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import matplotlib
from datetime import datetime, timedelta
matplotlib.rcParams['font.family'] = 'NanumGothic'  # For Korean text
matplotlib.rcParams['axes.unicode_minus'] = False

# Ensure project root (search-performance-evaluation/) is on sys.path
try:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
except Exception:
    pass


def _load_env_from_project_root() -> None:
    """Load .env from project root (search-performance-evaluation/)"""
    try:
        project_root = Path(__file__).resolve().parent.parent
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(str(env_path))
    except Exception:
        # Silently ignore (use system environment variables)
        pass


_load_env_from_project_root()


# Search log query template
SEARCH_LOG_QUERY_TEMPLATE = """
SELECT
  WORD,
  COUNT(*) AS cnt
FROM medigate.SE_LOG
WHERE SUB_CATEGORY_CODE = 'MUZZIMA'
  AND LOG_DATE > '{start_date}'
  AND LOG_DATE <= '{end_date}'
GROUP BY WORD
HAVING COUNT(*) > 1
ORDER BY cnt DESC
"""


def get_connection() -> MySQLConnection:
    """Get MySQL connection using db_utils module"""
    from module.db_utils import get_connection as db_connect
    return db_connect()


def fetch_dataframe(conn: MySQLConnection, query: str, params: Optional[tuple] = None) -> pd.DataFrame:
    """Execute query and return result as pandas DataFrame"""
    return pd.read_sql(query, conn, params=params)


def plot_frequency_distribution(df: pd.DataFrame, output_dir: str, min_freq: int = 5, max_queries: int = 5000) -> None:
    """
    Plot head-tail distribution of search query frequencies
    Shows top queries (up to max_queries) with frequency >= min_freq in horizontal layout

    Args:
        df: DataFrame with 'WORD' and 'cnt' columns
        output_dir: Directory to save the plot
        min_freq: Minimum frequency threshold to include in plot
        max_queries: Maximum number of queries to plot (default: 5000)
    """
    if df.empty:
        print("[warn] No data to plot")
        return

    # Filter data with frequency >= min_freq
    df_filtered = df[df['cnt'] >= min_freq].copy()

    if df_filtered.empty:
        print(f"[warn] No queries with frequency >= {min_freq}")
        return

    print(f"\n[4] Generating frequency distribution plot...")
    print(f"  - Queries with cnt >= {min_freq}: {len(df_filtered):,}")
    print(f"  - Total searches covered: {df_filtered['cnt'].sum():,}")

    # Limit to max_queries
    plot_n = min(max_queries, len(df_filtered))
    df_plot = df_filtered.head(plot_n)

    # Create single horizontal plot
    fig, ax = plt.subplots(1, 1, figsize=(14, 6))

    # Plot as horizontal line plot (without labels)
    x_range = range(len(df_plot))
    ax.plot(x_range, df_plot['cnt'].values, color='steelblue', linewidth=1.5, alpha=0.8)
    ax.fill_between(x_range, df_plot['cnt'].values, alpha=0.3, color='steelblue')

    ax.set_xlabel('Query Rank', fontsize=12)
    ax.set_ylabel('Search Count (log scale)', fontsize=12)

    # Title with total statistics
    title_text = f'Search Query Frequency Distribution (Top {plot_n:,} queries, cnt >= {min_freq})\n'
    title_text += f'Unique search terms: {len(df):,}  |  Total search count: {df["cnt"].sum():,}'
    ax.set_title(title_text, fontsize=13, fontweight='bold', pad=15)

    ax.set_yscale('log')
    ax.grid(alpha=0.3, linestyle='--')

    # Add floating annotation for max only
    max_val = df_plot['cnt'].max()
    max_idx = df_plot['cnt'].idxmax()
    max_pos = df_plot.index.get_loc(max_idx)

    # Max annotation (floating above the point)
    ax.annotate(f'Max: {max_val:,}',
                xy=(max_pos, max_val),
                xytext=(max_pos, max_val * 2.5),
                fontsize=10,
                fontweight='bold',
                color='darkred',
                ha='left',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7, edgecolor='darkred'),
                arrowprops=dict(arrowstyle='->', color='darkred', lw=1.5))

    plt.tight_layout()

    # Save plot
    plot_path = os.path.join(output_dir, 'frequency_distribution.png')
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    print(f"✓ Plot saved to: {plot_path}")

    # Show statistics for full dataset
    print(f"\n  Full dataset statistics:")
    print(f"    - Total unique queries: {len(df):,}")
    print(f"    - Queries plotted: {plot_n:,}")
    print(f"    - Queries with cnt >= {min_freq}: {len(df_filtered):,} ({len(df_filtered)/len(df)*100:.1f}%)")
    print(f"    - Total searches (cnt >= {min_freq}): {df_filtered['cnt'].sum():,}")
    print(f"    - Total searches (all): {df['cnt'].sum():,}")

    plt.close()


def main():
    """Main execution function"""
    import argparse

    # Calculate default start date (6 months before end date)
    default_end_date = "2025-10-30"
    end_dt = datetime.strptime(default_end_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=180)  # 6 months
    default_start_date = start_dt.strftime("%Y-%m-%d")

    parser = argparse.ArgumentParser(description="Fetch search log data from MySQL")
    parser.add_argument("--start_date", type=str, default=default_start_date,
                       help=f"Start date in YYYY-MM-DD format (default: {default_start_date})")
    parser.add_argument("--end_date", type=str, default=default_end_date,
                       help=f"End date in YYYY-MM-DD format (default: {default_end_date})")
    parser.add_argument("--out_dir", type=str, default="data/raw",
                       help="Output directory (default: data/raw)")
    parser.add_argument("--output_file", type=str, default="search_logs.csv",
                       help="Output CSV filename (default: search_logs.csv)")
    parser.add_argument("--min_freq", type=int, default=5,
                       help="Minimum frequency to include in plot (default: 5)")
    parser.add_argument("--max_queries", type=int, default=5000,
                       help="Maximum number of queries to plot (default: 5000)")
    parser.add_argument("--no_plot", action="store_true",
                       help="Skip plotting")
    args = parser.parse_args()

    # Validate date format
    try:
        datetime.strptime(args.start_date, "%Y-%m-%d")
        datetime.strptime(args.end_date, "%Y-%m-%d")
    except ValueError:
        print("Error: Dates must be in YYYY-MM-DD format")
        sys.exit(1)

    print("=" * 60)
    print("Search Log Data Extraction")
    print("=" * 60)

    # 1. Connect to database
    print("\n[1] Connecting to MySQL database...")
    try:
        conn = get_connection()
        print("✓ Database connection established")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        sys.exit(1)

    # 2. Execute query
    print("\n[2] Executing search log query...")
    print(f"Query: Fetch MUZZIMA search logs from {args.start_date} to {args.end_date}")

    # Build query with date parameters
    query = SEARCH_LOG_QUERY_TEMPLATE.format(
        start_date=args.start_date,
        end_date=args.end_date
    )

    try:
        df = fetch_dataframe(conn, query)

        # Clean WORD column
        if not df.empty and 'WORD' in df.columns:
            # Strip whitespace
            df['WORD'] = df['WORD'].str.strip()
            # Remove leading/trailing quotes (single or double)
            df['WORD'] = df['WORD'].str.strip('"\'')
            df['WORD'] = df['WORD'].str.strip()  # Strip again after quote removal
            # Remove empty strings
            df = df[df['WORD'] != '']
            # Recalculate counts after cleaning (in case duplicates were created)
            df = df.groupby('WORD', as_index=False)['cnt'].sum()
            df = df.sort_values('cnt', ascending=False).reset_index(drop=True)

        print(f"✓ Query executed successfully")
        print(f"  - Total records: {len(df):,}")
        print(f"  - Unique words: {df['WORD'].nunique():,}")
        print(f"  - Total search count: {df['cnt'].sum():,}")

        if not df.empty:
            print(f"\n  Top 5 search terms:")
            for idx, row in df.head(5).iterrows():
                print(f"    {idx+1}. {row['WORD']}: {row['cnt']:,} searches")
    except Exception as e:
        print(f"✗ Query execution failed: {e}")
        conn.close()
        sys.exit(1)

    # 3. Save to CSV
    print(f"\n[3] Saving results to CSV...")
    os.makedirs(args.out_dir, exist_ok=True)
    output_path = os.path.join(args.out_dir, args.output_file)

    try:
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"✓ Data saved to: {output_path}")
    except Exception as e:
        print(f"✗ Failed to save CSV: {e}")
        conn.close()
        sys.exit(1)

    # 4. Close connection
    conn.close()
    print("\n✓ Database connection closed")

    # 4. Generate visualization
    if not args.no_plot and not df.empty:
        try:
            plot_frequency_distribution(df, args.out_dir, min_freq=args.min_freq, max_queries=args.max_queries)
        except Exception as e:
            print(f"[warn] Plotting failed: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total search records: {len(df):,}")
    print(f"Unique search terms: {df['WORD'].nunique():,}")
    print(f"Total search count: {df['cnt'].sum():,}")
    print(f"Output file: {output_path}")
    if not args.no_plot:
        print(f"Plot file: {os.path.join(args.out_dir, 'frequency_distribution.png')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
