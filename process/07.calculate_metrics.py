#!/usr/bin/env python3
"""
Step07: Calculate evaluation metrics (nDCG, MRR, Recall)
Compares different search methods using relevance judgments
OpenSearch version
"""
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import math

import pandas as pd
import numpy as np
from dotenv import load_dotenv

try:
    from opensearchpy import OpenSearch
except ImportError:
    print("Error: opensearch-py package is required. Install with: pip install opensearch-py")
    sys.exit(1)


# Ensure project root is on sys.path
try:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
except Exception:
    PROJECT_ROOT = Path.cwd()


def get_opensearch_client(env_file: Optional[str] = None) -> OpenSearch:
    """Get OpenSearch connection"""
    if env_file:
        env_path = Path(env_file)
    else:
        env_path = PROJECT_ROOT / ".env"
    
    if not env_path.exists():
        raise RuntimeError(f".env file not found: {env_path}")
    
    load_dotenv(str(env_path))
    
    host = os.getenv("OPENSEARCH_HOST")
    port = int(os.getenv("OPENSEARCH_PORT", "9200"))
    
    username = (
        os.getenv("OPENSEARCH_ID")
        or os.getenv("OPENSEARCH_USER")
        or os.getenv("OPENSEARCH_USERNAME")
    )
    password = (
        os.getenv("OPENSEARCH_PW")
        or os.getenv("OPENSEARCH_PASSWORD")
    )
    
    if not host or not username or not password:
        raise RuntimeError("Missing OpenSearch credentials in .env file")
    
    client = OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_auth=(username, password),
        use_ssl=True,
        verify_certs=False,
        ssl_show_warn=False,
        timeout=30,
        max_retries=2,
        retry_on_timeout=True,
    )
    
    if not client.ping():
        raise RuntimeError("Failed to connect to OpenSearch")
    
    return client


def dcg_at_k(relevances: List[int], k: int) -> float:
    """
    Calculate Discounted Cumulative Gain at K
    
    DCG@K = sum(rel_i / log2(i + 1)) for i in 1..k
    """
    relevances = relevances[:k]
    if not relevances:
        return 0.0
    
    dcg = sum((rel / math.log2(idx + 2)) for idx, rel in enumerate(relevances))
    return dcg


def ndcg_at_k(relevances: List[int], k: int) -> float:
    """
    Calculate Normalized Discounted Cumulative Gain at K
    
    nDCG@K = DCG@K / IDCG@K
    """
    dcg = dcg_at_k(relevances, k)
    
    # Ideal DCG (sort by relevance descending)
    ideal_relevances = sorted(relevances, reverse=True)
    idcg = dcg_at_k(ideal_relevances, k)
    
    if idcg == 0:
        return 0.0
    
    return dcg / idcg


def recall_at_k(relevances: List[int], k: int, threshold: int = 1) -> float:
    """
    Calculate Recall at K
    
    Recall@K = (# of relevant docs in top-K) / (# of total relevant docs)
    """
    total_relevant = sum(1 for rel in relevances if rel >= threshold)
    
    if total_relevant == 0:
        return 0.0
    
    relevant_at_k = sum(1 for rel in relevances[:k] if rel >= threshold)
    
    return relevant_at_k / total_relevant


def precision_at_k(relevances: List[int], k: int, threshold: int = 1) -> float:
    """
    Calculate Precision at K
    
    Precision@K = (# of relevant docs in top-K) / K
    """
    if k == 0:
        return 0.0
    
    relevant_at_k = sum(1 for rel in relevances[:k] if rel >= threshold)
    return relevant_at_k / k


def mrr(relevances: List[int], threshold: int = 1) -> float:
    """
    Calculate Mean Reciprocal Rank
    
    MRR = 1 / (rank of first relevant document)
    """
    for idx, rel in enumerate(relevances):
        if rel >= threshold:
            return 1.0 / (idx + 1)
    
    return 0.0


def average_precision(relevances: List[int], threshold: int = 1) -> float:
    """
    Calculate Average Precision
    
    AP = sum(P@k * rel_k) / # of relevant docs
    """
    total_relevant = sum(1 for rel in relevances if rel >= threshold)
    
    if total_relevant == 0:
        return 0.0
    
    ap_sum = 0.0
    relevant_count = 0
    
    for idx, rel in enumerate(relevances):
        if rel >= threshold:
            relevant_count += 1
            precision = relevant_count / (idx + 1)
            ap_sum += precision
    
    return ap_sum / total_relevant


class MetricsCalculator:
    """Calculate evaluation metrics for search methods"""
    
    def __init__(self, k_values: List[int] = [5, 10, 20]):
        self.k_values = k_values
    
    def calculate_for_query(
        self,
        relevances: List[int]
    ) -> Dict[str, float]:
        """Calculate all metrics for a single query"""
        
        metrics = {}
        
        # nDCG@K
        for k in self.k_values:
            metrics[f'ndcg@{k}'] = ndcg_at_k(relevances, k)
        
        # Recall@K
        for k in self.k_values:
            metrics[f'recall@{k}'] = recall_at_k(relevances, k, threshold=1)
        
        # Precision@K
        for k in self.k_values:
            metrics[f'precision@{k}'] = precision_at_k(relevances, k, threshold=1)
        
        # MRR
        metrics['mrr'] = mrr(relevances, threshold=1)
        
        # MAP (Mean Average Precision)
        metrics['map'] = average_precision(relevances, threshold=1)
        
        return metrics
    
    def load_results_from_opensearch(
        self,
        client: OpenSearch,
        index_names: List[str],
        method: str,
        subset: str = "all"
    ) -> Dict[str, List[Tuple[str, int]]]:
        """
        Load search results for a method from OpenSearch (supports multiple indices)
        
        Args:
            index_names: List of index names to load from
        
        Returns:
            dict[query] = [(doc_id, relevance), ...]
        """
        # Handle single index or list of indices
        if isinstance(index_names, str):
            index_names = [index_names]
        
        query_results = defaultdict(list)
        
        # Query each index and merge results
        for index_name in index_names:
            # Query to get labeled results with rank for the method
            query_body = {
                "query": {
                    "bool": {
                        "must": [
                            {"exists": {"field": f"{method}_rank"}},
                            {"exists": {"field": "relevance"}}
                        ]
                    }
                },
                "sort": [
                    {"query": {"order": "asc"}},  # query is already keyword type, no .keyword needed
                    {f"{method}_rank": {"order": "asc"}}
                ],
                "size": 10000  # Adjust based on your data size
            }

            # Apply subset filter if requested
            if subset in ("head", "tail"):
                query_body["query"]["bool"].setdefault("filter", []).append({
                    "term": {"query_set": subset.upper()}
                })
            
            response = client.search(index=index_name, body=query_body)
            hits = response['hits']['hits']
            
            # Group by query
            for hit in hits:
                doc = hit['_source']
                query_results[doc['query']].append(
                    (doc['doc_id'], doc['relevance'])
                )
        
        return dict(query_results)
    
    def calculate_for_method(
        self,
        client: OpenSearch,
        index_names: List[str],
        method: str,
        subset: str = "all",
        verbose: bool = True
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Calculate metrics for a search method (supports multiple indices)
        
        Args:
            index_names: List of index names or single index name
            subset: Query subset to evaluate (all/head/tail)
        
        Returns:
            (per_query_metrics_df, aggregated_metrics_dict)
        """
        if verbose:
            print(f"\n  Calculating metrics for: {method}")
        
        # Load results
        query_results = self.load_results_from_opensearch(client, index_names, method, subset=subset)
        
        if not query_results:
            print(f"    ⚠ No results found for {method}")
            return pd.DataFrame(), {}
        
        if verbose:
            print(f"    Loaded {len(query_results)} queries")
        
        # Calculate metrics for each query
        per_query_metrics = []
        
        for query, docs in query_results.items():
            # Extract relevances in rank order
            relevances = [rel for doc_id, rel in docs]
            
            # Calculate metrics
            metrics = self.calculate_for_query(relevances)
            metrics['query'] = query
            metrics['method'] = method
            metrics['num_results'] = len(relevances)
            metrics['num_relevant'] = sum(1 for rel in relevances if rel >= 1)
            
            per_query_metrics.append(metrics)
        
        # Create DataFrame
        df = pd.DataFrame(per_query_metrics)
        
        # Calculate aggregated metrics (mean across queries)
        agg_metrics = {}
        for col in df.columns:
            if col not in ['query', 'method', 'num_results', 'num_relevant']:
                agg_metrics[col] = df[col].mean()
        
        agg_metrics['num_queries'] = len(query_results)
        agg_metrics['avg_num_results'] = df['num_results'].mean()
        agg_metrics['avg_num_relevant'] = df['num_relevant'].mean()
        
        if verbose:
            print(f"    ✓ Metrics calculated for {len(query_results)} queries")
        
        return df, agg_metrics


def get_available_methods(client: OpenSearch, index_names: List[str]) -> List[str]:
    """Get list of search methods available in the index(es)"""
    
    # Handle single index or list
    if isinstance(index_names, str):
        index_names = [index_names]
    
    methods_set = set()
    
    # Get methods from all indices
    for index_name in index_names:
        # Get mapping
        mapping = client.indices.get_mapping(index=index_name)
        properties = mapping[index_name]['mappings']['properties']
        
        # Find fields ending with _rank
        for field_name in properties.keys():
            if field_name.endswith('_rank'):
                method = field_name.replace('_rank', '')
                methods_set.add(method)
    
    return sorted(list(methods_set))


def compare_methods(
    per_query_dfs: Dict[str, pd.DataFrame],
    methods: List[str],
    metric: str
) -> pd.DataFrame:
    """Compare methods on a specific metric"""
    
    comparison_data = []
    
    # Get all queries
    all_queries = set()
    for df in per_query_dfs.values():
        all_queries.update(df['query'].unique())
    
    for query in all_queries:
        row = {'query': query}
        
        for method in methods:
            if method in per_query_dfs:
                df = per_query_dfs[method]
                query_data = df[df['query'] == query]
                
                if not query_data.empty:
                    row[f'{method}_{metric}'] = query_data[metric].values[0]
                else:
                    row[f'{method}_{metric}'] = None
        
        comparison_data.append(row)
    
    return pd.DataFrame(comparison_data)


def main():
    parser = argparse.ArgumentParser(
        description="Step07: Calculate evaluation metrics (OpenSearch version)"
    )
    parser.add_argument(
        "--index_name",
        nargs="+",
        default=["search_relevance_judgments"],
        help="OpenSearch index name(s) - can specify multiple for combined evaluation"
    )
    parser.add_argument(
        "--methods",
        nargs="+",
        help="Methods to evaluate (default: auto-detect all)"
    )
    parser.add_argument(
        "--k_values",
        nargs="+",
        type=int,
        default=[5, 10, 20],
        help="K values for metrics (default: 5 10 20)"
    )
    parser.add_argument(
        "--output_dir",
        default="data/evaluation_results",
        help="Output directory for results"
    )
    parser.add_argument(
        "--subset",
        choices=["all", "head", "tail"],
        default="all",
        help="Evaluate on subset (all/head/tail). Requires 'query_set' field in index."
    )
    parser.add_argument(
        "--env_file",
        help="Path to .env file (default: project_root/.env)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Show progress (default: True)"
    )
    args = parser.parse_args()
    
    print("=" * 70)
    print("Step07: Calculate Evaluation Metrics (OpenSearch)")
    print("=" * 70)
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Connect to OpenSearch
    print("\n[1] Connecting to OpenSearch...")
    try:
        client = get_opensearch_client(args.env_file)
        cluster_info = client.info()
        print(f"  ✓ Connected to cluster: {cluster_info['cluster_name']}")
    except Exception as e:
        print(f"  ✗ OpenSearch connection failed: {e}")
        sys.exit(1)
    
    # Check indices exist
    index_names = args.index_name if isinstance(args.index_name, list) else [args.index_name]
    print(f"\n  Target indices: {', '.join(index_names)}")
    
    for idx_name in index_names:
        if not client.indices.exists(index=idx_name):
            print(f"\n  ✗ Error: Index '{idx_name}' does not exist")
            sys.exit(1)
    print(f"  ✓ All indices exist")
    
    # Detect or use specified methods
    print(f"\n[2] Detecting search methods...")
    if args.methods:
        methods = args.methods
        print(f"  Using specified methods: {', '.join(methods)}")
    else:
        methods = get_available_methods(client, index_names)
        print(f"  Auto-detected methods: {', '.join(methods)}")
    
    if not methods:
        print("  ✗ No search methods found")
        sys.exit(1)
    
    # Initialize calculator
    calculator = MetricsCalculator(k_values=args.k_values)
    print(f"  K values: {args.k_values}")
    
    # Calculate metrics for each method
    print(f"\n[3] Calculating metrics...")
    
    per_query_dfs = {}
    agg_metrics = {}
    
    for method in methods:
        try:
            per_query_df, agg = calculator.calculate_for_method(
                client, index_names, method, subset=args.subset, verbose=args.verbose
            )
            
            if not per_query_df.empty:
                per_query_dfs[method] = per_query_df
                agg_metrics[method] = agg
            else:
                print(f"    ⚠ Skipping {method} (no data)")
        
        except Exception as e:
            print(f"    ✗ Error calculating metrics for {method}: {e}")
            continue
    
    if not agg_metrics:
        print("\n  ✗ No metrics calculated")
        sys.exit(1)
    
    # Save per-query metrics
    print(f"\n[4] Saving results...")
    # Create subset subdirectory
    subset_out_dir = os.path.join(args.output_dir, args.subset)
    os.makedirs(subset_out_dir, exist_ok=True)
    for method, df in per_query_dfs.items():
        output_file = os.path.join(subset_out_dir, f"per_query_metrics_{method}.csv")
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"  ✓ Saved {method} per-query metrics: {output_file}")
    
    # Create aggregated metrics DataFrame
    agg_df = pd.DataFrame(agg_metrics).T
    agg_df.index.name = 'method'
    agg_file = os.path.join(subset_out_dir, "aggregated_metrics.csv")
    agg_df.to_csv(agg_file, encoding='utf-8-sig')
    print(f"  ✓ Saved aggregated metrics: {agg_file}")
    
    # Display results
    print(f"\n[5] Evaluation Results")
    print("=" * 70)
    
    # Show aggregated metrics
    print("\nAggregated Metrics (Mean across queries):")
    print("-" * 70)
    
    # Format for display
    display_cols = [col for col in agg_df.columns if '@' in col or col in ['mrr', 'map']]
    display_df = agg_df[display_cols].round(4)
    
    print(display_df.to_string())
    
    # Method comparison
    print("\n" + "=" * 70)
    print("Method Comparison:")
    print("-" * 70)
    
    for metric in ['ndcg@10', 'ndcg@20', 'recall@10', 'recall@20', 'mrr', 'map']:
        if metric not in display_df.columns:
            continue
        
        print(f"\n{metric.upper()}:")
        sorted_methods = display_df[metric].sort_values(ascending=False)
        
        for idx, (method, value) in enumerate(sorted_methods.items(), 1):
            badge = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else "  "
            print(f"  {badge} {method:20s}: {value:.4f}")
    
    # Find best performing queries
    print("\n" + "=" * 70)
    print("Query Analysis:")
    print("-" * 70)
    
    # Combine all per-query results
    all_queries_df = pd.concat(per_query_dfs.values(), ignore_index=True)
    
    # Top queries (best nDCG@20)
    print("\nTop 5 queries (highest nDCG@20):")
    top_queries = all_queries_df.nlargest(5, 'ndcg@20')[['query', 'method', 'ndcg@20', 'num_relevant']]
    for idx, row in top_queries.iterrows():
        print(f"  {row['query'][:50]:50s} | {row['method']:10s} | nDCG@20: {row['ndcg@20']:.4f}")
    
    # Worst queries
    print("\nBottom 5 queries (lowest nDCG@20):")
    bottom_queries = all_queries_df.nsmallest(5, 'ndcg@20')[['query', 'method', 'ndcg@20', 'num_relevant']]
    for idx, row in bottom_queries.iterrows():
        print(f"  {row['query'][:50]:50s} | {row['method']:10s} | nDCG@20: {row['ndcg@20']:.4f}")
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Methods evaluated: {len(agg_metrics)}")
    print(f"Queries analyzed: {agg_df['num_queries'].iloc[0]:.0f}")
    print(f"K values: {args.k_values}")
    print(f"Output directory: {args.output_dir}")
    print("=" * 70)
    print("\nNext step:")
    print(f"python process/08.visualize_results.py --results_dir {args.output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()

