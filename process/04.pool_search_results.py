#!/usr/bin/env python3
"""
Step04: Pool search results from multiple search methods
Uses depth-K pooling strategy (TREC standard)
"""
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List
from datetime import datetime
from collections import Counter

import pandas as pd


# Ensure project root is on sys.path
try:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
except Exception:
    pass


class SearchResultPooler:
    """Pool search results from multiple search methods using depth-K pooling"""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def pool_results(
        self,
        result_dfs: List[pd.DataFrame],
        method_names: List[str],
        depth_k: int = 20,
        verbose: bool = True
    ) -> pd.DataFrame:
        """
        Pool search results using depth-K pooling (TREC standard)

        Depth-K Pooling:
        - Take top-K documents from each method
        - Merge all documents (union)
        - Track which method(s) found each document
        - Remove duplicates

        Example with K=20, 3 methods:
        - Lexical top-20: [doc1, doc2, ..., doc20]
        - Semantic top-20: [doc2, doc5, ..., doc40]
        - Hybrid top-20: [doc1, doc2, ..., doc41]
        → Pool contains all unique docs (could be 20-60 docs)

        Args:
            result_dfs: List of search result DataFrames
            method_names: List of method names (e.g., ["lexical", "semantic"])
            depth_k: Take top-K from each method (default: 20)
            verbose: Show progress

        Returns:
            Pooled DataFrame with unique documents
        """
        if len(result_dfs) != len(method_names):
            raise ValueError("Number of result DataFrames must match number of method names")

        if verbose:
            print(f"\n  Depth-K Pooling (K={depth_k})")
            print(f"  Methods: {', '.join(method_names)}")

        records = []

        # Get all unique queries
        all_queries = set()
        for df in result_dfs:
            all_queries.update(df["query"].unique())

        total_queries = len(all_queries)
        if verbose:
            print(f"  Total queries to process: {total_queries}")

        # Process each query
        for query_idx, query in enumerate(sorted(all_queries), 1):
            query_pool: Dict[str, Dict] = {}  # doc_id -> document data

            # Get top-K from each method
            for method_idx, (df, method_name) in enumerate(zip(result_dfs, method_names)):
                # Filter results for this query
                query_results = df[df["query"] == query].copy()

                # Take top-K
                top_k_results = query_results.head(depth_k)

                # Add to pool
                for _, row in top_k_results.iterrows():
                    doc_id = row["doc_id"]

                    if doc_id not in query_pool:
                        # First time seeing this document
                        # Create dynamic rank/score columns for each method
                        doc_data = {
                            "query": query,
                            "doc_id": doc_id,
                            # Preserve query set (HEAD/TAIL) for downstream analysis
                            "query_set": row.get("query_set"),
                            "found_by_methods": [method_name],
                            "num_methods_found": 1,
                        }

                        # Add rank and score for this method
                        doc_data[f"{method_name}_rank"] = row["rank"]
                        doc_data[f"{method_name}_score"] = row.get("score")

                        # Initialize other methods as None
                        for other_method in method_names:
                            if other_method != method_name:
                                doc_data[f"{other_method}_rank"] = None
                                doc_data[f"{other_method}_score"] = None

                        # Add all other fields from the source (once)
                        for col in row.index:
                            if col not in [
                                "experiment_id", "experiment_name", "query_set",
                                "query", "rank", "index", "doc_id", "score"
                            ]:
                                doc_data[col] = row[col]

                        query_pool[doc_id] = doc_data

                    else:
                        # Document already in pool, update with this method's info
                        query_pool[doc_id]["found_by_methods"].append(method_name)
                        query_pool[doc_id]["num_methods_found"] += 1
                        query_pool[doc_id][f"{method_name}_rank"] = row["rank"]
                        query_pool[doc_id][f"{method_name}_score"] = row.get("score")

            # Convert found_by_methods list to comma-separated string
            for doc_id, doc_data in query_pool.items():
                doc_data["found_by_methods"] = ",".join(doc_data["found_by_methods"])
                records.append(doc_data)

            # Progress indicator
            if verbose and query_idx % 50 == 0:
                print(f"    Processed {query_idx}/{total_queries} queries...")

        if verbose:
            print(f"    ✓ Processed all {total_queries} queries")

        # Create DataFrame
        pooled_df = pd.DataFrame.from_records(records)

        # Calculate and display statistics
        if verbose:
            self._print_statistics(pooled_df, method_names, depth_k)

        return pooled_df

    def _print_statistics(
        self, pooled_df: pd.DataFrame, method_names: List[str], depth_k: int
    ) -> None:
        """Print pooling statistics"""
        total_docs = len(pooled_df)
        num_methods = len(method_names)

        # Count documents by number of methods that found them
        method_count_dist = Counter(pooled_df["num_methods_found"])

        print(f"\n  Pooling Statistics:")
        print(f"    Depth-K: {depth_k}")
        print(f"    Number of methods: {num_methods}")
        print(f"    Total unique documents in pool: {total_docs:,}")

        # Per-method contribution
        print(f"\n    Documents found per method:")
        for method in method_names:
            count = pooled_df[f"{method}_rank"].notna().sum()
            pct = count / total_docs * 100
            print(f"      {method}: {count:,} ({pct:.1f}%)")

        # Overlap analysis
        print(f"\n    Document overlap by number of methods:")
        for i in range(1, num_methods + 1):
            count = method_count_dist.get(i, 0)
            pct = count / total_docs * 100 if total_docs > 0 else 0
            label = "all methods" if i == num_methods else f"{i} method{'s' if i > 1 else ''} only"
            print(f"      Found by {label}: {count:,} ({pct:.1f}%)")

        # Unique contributions (found by only one method)
        print(f"\n    Unique contributions (found by only one method):")
        for method in method_names:
            # Documents found only by this method
            mask = (pooled_df["num_methods_found"] == 1) & (
                pooled_df["found_by_methods"] == method
            )
            count = mask.sum()
            pct = count / total_docs * 100 if total_docs > 0 else 0
            print(f"      {method} only: {count:,} ({pct:.1f}%)")

    def save_pool(
        self, df: pd.DataFrame, query_set: str, method_names: List[str], depth_k: int
    ) -> str:
        """Save pooled results to CSV"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        methods_str = "_".join(method_names)
        filename = f"pooled_{query_set.lower()}_{methods_str}_k{depth_k}_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)

        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        return filepath
    
    def save_statistics(
        self, df: pd.DataFrame, query_set: str, method_names: List[str], depth_k: int, output_path: str
    ) -> str:
        """Save pooling statistics to file"""
        stats_filename = output_path.replace('.csv', '_statistics.txt')
        
        total_docs = len(df)
        num_methods = len(method_names)
        num_queries = df['query'].nunique()
        method_count_dist = Counter(df["num_methods_found"])
        
        with open(stats_filename, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("Pooling Statistics Report\n")
            f.write("=" * 70 + "\n\n")
            
            # Basic info
            f.write(f"Query Set: {query_set}\n")
            f.write(f"Depth-K: {depth_k}\n")
            f.write(f"Methods: {', '.join(method_names)} ({num_methods} total)\n")
            f.write(f"Number of queries: {num_queries}\n")
            f.write(f"Total unique documents in pool: {total_docs:,}\n")
            f.write(f"Average documents per query: {total_docs / num_queries:.1f}\n\n")
            
            # Per-method contribution
            f.write("-" * 70 + "\n")
            f.write("Documents Found Per Method:\n")
            f.write("-" * 70 + "\n")
            for method in method_names:
                count = df[f"{method}_rank"].notna().sum()
                pct = count / total_docs * 100
                avg_per_query = count / num_queries
                f.write(f"  {method:20s}: {count:6,} ({pct:5.1f}%) - avg {avg_per_query:.1f} per query\n")
            f.write("\n")
            
            # Overlap analysis
            f.write("-" * 70 + "\n")
            f.write("Document Overlap by Number of Methods:\n")
            f.write("-" * 70 + "\n")
            for i in range(1, num_methods + 1):
                count = method_count_dist.get(i, 0)
                pct = count / total_docs * 100 if total_docs > 0 else 0
                label = "all methods" if i == num_methods else f"{i} method{'s' if i > 1 else ''} only"
                avg_per_query = count / num_queries
                f.write(f"  Found by {label:20s}: {count:6,} ({pct:5.1f}%) - avg {avg_per_query:.1f} per query\n")
            f.write("\n")
            
            # Unique contributions
            f.write("-" * 70 + "\n")
            f.write("Unique Contributions (found by only one method):\n")
            f.write("-" * 70 + "\n")
            for method in method_names:
                mask = (df["num_methods_found"] == 1) & (df["found_by_methods"] == method)
                count = mask.sum()
                pct = count / total_docs * 100 if total_docs > 0 else 0
                avg_per_query = count / num_queries
                f.write(f"  {method:20s} only: {count:6,} ({pct:5.1f}%) - avg {avg_per_query:.1f} per query\n")
            f.write("\n")
            
            # Query-level statistics
            f.write("-" * 70 + "\n")
            f.write("Query-Level Statistics:\n")
            f.write("-" * 70 + "\n")
            docs_per_query = df.groupby('query').size()
            f.write(f"  Min documents per query: {docs_per_query.min()}\n")
            f.write(f"  Max documents per query: {docs_per_query.max()}\n")
            f.write(f"  Mean documents per query: {docs_per_query.mean():.1f}\n")
            f.write(f"  Median documents per query: {docs_per_query.median():.1f}\n")
            f.write("\n")
            
            f.write("=" * 70 + "\n")
        
        return stats_filename


def load_search_results(filepath: str) -> pd.DataFrame:
    """Load search results from CSV"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    return pd.read_csv(filepath)


def main():
    parser = argparse.ArgumentParser(
        description="Step04: Pool search results using depth-K pooling (TREC standard)"
    )
    parser.add_argument(
        "--results",
        nargs="+",
        required=True,
        help="Paths to search result CSV files (space-separated)"
    )
    parser.add_argument(
        "--results_head",
        nargs="+",
        help="HEAD result CSV paths per method (same order as --methods)"
    )
    parser.add_argument(
        "--results_tail",
        nargs="+",
        help="TAIL result CSV paths per method (same order as --methods)"
    )
    parser.add_argument(
        "--methods",
        nargs="+",
        required=True,
        help="Method names corresponding to result files (space-separated, e.g., lexical semantic hybrid)"
    )
    parser.add_argument(
        "--output_dir",
        default="data/pooled_results",
        help="Output directory for pooled results"
    )
    parser.add_argument(
        "--depth_k",
        type=int,
        default=20,
        help="Depth-K: Take top-K from each method (default: 20)"
    )
    parser.add_argument(
        "--query_set",
        default="ALL",
        help="Query set name for output filename (default: ALL)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Show statistics (default: True)"
    )
    args = parser.parse_args()

    # Determine loading mode (legacy single list vs head/tail lists)
    use_ht = args.results_head is not None and args.results_tail is not None
    if use_ht:
        if len(args.results_head) != len(args.methods) or len(args.results_tail) != len(args.methods):
            print("Error: --results_head and --results_tail must be provided with the same length as --methods")
            sys.exit(1)
    else:
        if len(args.results) != len(args.methods):
            print(f"Error: Number of result files ({len(args.results)}) must match number of methods ({len(args.methods)})")
            sys.exit(1)

    print("=" * 70)
    print("Step04: Pool Search Results (Depth-K Pooling)")
    print("=" * 70)

    # Load results
    print(f"\n[1] Loading search results...")
    result_dfs = []
    if use_ht:
        for head_fp, tail_fp, method_name in zip(args.results_head, args.results_tail, args.methods):
            try:
                df_head = load_search_results(head_fp)
                df_tail = load_search_results(tail_fp)
                df_combined = pd.concat([df_head, df_tail], ignore_index=True)
                result_dfs.append(df_combined)
                print(f"  ✓ {method_name}: {len(df_combined)} records (HEAD {len(df_head)}, TAIL {len(df_tail)})")
            except Exception as e:
                print(f"  ✗ Failed to load {method_name} head/tail results: {e}")
                sys.exit(1)
    else:
        for filepath, method_name in zip(args.results, args.methods):
            try:
                df = load_search_results(filepath)
                result_dfs.append(df)
                print(f"  ✓ {method_name}: {len(df)} records from {filepath}")
            except Exception as e:
                print(f"  ✗ Failed to load {method_name} results: {e}")
                sys.exit(1)

    # Initialize pooler
    pooler = SearchResultPooler(args.output_dir)
    print(f"\n[2] Pooling configuration:")
    print(f"  Output directory: {args.output_dir}")
    print(f"  Depth-K: {args.depth_k} (take top-{args.depth_k} from each method)")
    print(f"  Methods: {', '.join(args.methods)}")

    # Pool results
    print(f"\n[3] Pooling results...")
    try:
        pooled_df = pooler.pool_results(
            result_dfs=result_dfs,
            method_names=args.methods,
            depth_k=args.depth_k,
            verbose=args.verbose
        )

        print(f"\n  ✓ Pooled {len(pooled_df)} unique documents")
    except Exception as e:
        print(f"  ✗ Pooling failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Save pooled results
    print(f"\n[4] Saving pooled results...")
    try:
        filepath = pooler.save_pool(
            pooled_df, args.query_set, args.methods, args.depth_k
        )
        print(f"  ✓ Saved to: {filepath}")
    except Exception as e:
        print(f"  ✗ Failed to save: {e}")
        sys.exit(1)
    
    # Save statistics
    print(f"\n[5] Saving pooling statistics...")
    try:
        stats_filepath = pooler.save_statistics(
            pooled_df, args.query_set, args.methods, args.depth_k, filepath
        )
        print(f"  ✓ Statistics saved to: {stats_filepath}")
    except Exception as e:
        print(f"  ⚠ Failed to save statistics: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    for method_name, df in zip(args.methods, result_dfs):
        print(f"{method_name} results: {len(df):,}")
    print(f"Pooled documents: {len(pooled_df):,}")
    print(f"Depth-K: {args.depth_k}")
    print(f"Output file: {filepath}")
    print(f"Statistics file: {stats_filepath}")
    print("=" * 70)


if __name__ == "__main__":
    main()
