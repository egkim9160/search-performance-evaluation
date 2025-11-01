#!/usr/bin/env python3
"""
Step06: Upload labeled CSV to OpenSearch
Uploads pre-labeled CSV file to OpenSearch index
"""
import os
import sys
import argparse
from pathlib import Path
from typing import Optional
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv

try:
    from opensearchpy import OpenSearch
    from opensearchpy.helpers import bulk
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


def create_relevance_index(client: OpenSearch, index_name: str) -> bool:
    """Create relevance judgment index with mapping"""
    
    index_mapping = {
        "settings": {
            "number_of_shards": 3,
            "number_of_replicas": 1,
            "refresh_interval": "1s"
        },
        "mappings": {
            "properties": {
                # Query and document identification
                "query": {"type": "keyword"},
                "doc_id": {"type": "keyword"},
                "found_by_methods": {"type": "keyword"},
                "num_methods_found": {"type": "integer"},
                
                # Rank and scores from each method
                "lexical_rank": {"type": "integer"},
                "lexical_score": {"type": "float"},
                "semantic_rank": {"type": "integer"},
                "semantic_score": {"type": "float"},
                
                # Document content
                "BOARD_IDX": {"type": "integer"},
                "TITLE": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "BOARD_NAME": {"type": "keyword"},
                "CONTENT": {"type": "text"},
                "merged_comment": {"type": "text"},
                
                # Metadata
                "view_cnt": {"type": "integer"},
                "comment_cnt": {"type": "integer"},
                "agree_cnt": {"type": "integer"},
                "disagree_cnt": {"type": "integer"},
                "REG_DATE": {"type": "keyword"},
                "U_ID": {"type": "keyword"},
                
                # Relevance judgment (already labeled)
                "relevance": {"type": "integer"},
                "labeled_by": {"type": "keyword"},
                "labeled_at": {"type": "date"},
                "notes": {"type": "text"},
                
                # Tracking
                "created_at": {"type": "date"}
            }
        }
    }
    
    if client.indices.exists(index=index_name):
        print(f"  ⚠ Index already exists: {index_name}")
        return False
    
    client.indices.create(index=index_name, body=index_mapping)
    print(f"  ✓ Index created: {index_name}")
    return True


def upload_labeled_csv(
    client: OpenSearch,
    index_name: str,
    labeled_csv: str,
    verbose: bool = True
) -> int:
    """Upload labeled CSV to OpenSearch"""
    
    # Load CSV
    df = pd.read_csv(labeled_csv)
    
    if verbose:
        print(f"\n  Loading labeled CSV: {labeled_csv}")
        print(f"  Total records: {len(df):,}")
        
        # Check labeling status
        labeled_count = (~df['relevance'].isna()).sum() if 'relevance' in df.columns else 0
        print(f"  Labeled records: {labeled_count:,} ({labeled_count/len(df)*100:.1f}%)")
    
    # Prepare documents
    actions = []
    
    for idx, row in df.iterrows():
        doc = {
            "_index": index_name,
            "_id": f"{row['query']}_{row['doc_id']}",
            "_source": {}
        }
        
        # Add all fields
        for col in df.columns:
            val = row[col]
            
            if pd.isna(val):
                doc["_source"][col] = None
            else:
                doc["_source"][col] = val
        
        # Add timestamp
        if 'created_at' not in doc["_source"] or pd.isna(doc["_source"]['created_at']):
            doc["_source"]["created_at"] = datetime.now().isoformat()
        
        actions.append(doc)
        
        if verbose and (idx + 1) % 1000 == 0:
            print(f"    Prepared {idx + 1:,}/{len(df):,} documents...")
    
    # Bulk index
    if verbose:
        print(f"\n  Uploading {len(actions):,} documents to OpenSearch...")
    
    try:
        success, failed = bulk(client, actions, raise_on_error=False, stats_only=False)
        
        if verbose:
            print(f"\n  ✓ Upload completed:")
            print(f"    - Successfully indexed: {success:,}")
            if failed:
                print(f"    - Failed: {len(failed):,}")
                print(f"\n  First {min(3, len(failed))} errors:")
                for item in failed[:3]:
                    if 'index' in item:
                        error_info = item['index']
                        print(f"    Doc ID: {error_info.get('_id', 'N/A')}")
                        print(f"    Error: {error_info.get('error', {}).get('type', 'N/A')}")
                        print()
        
        return success
        
    except Exception as e:
        print(f"  ✗ Bulk upload failed: {e}")
        import traceback
        traceback.print_exc()
        raise


def get_index_stats(client: OpenSearch, index_name: str) -> dict:
    """Get statistics from relevance index"""
    
    stats = {}
    
    try:
        count_response = client.count(index=index_name)
        stats['total'] = count_response['count']
        
        agg_query = {
            "size": 0,
            "aggs": {
                "unique_queries": {
                    "cardinality": {"field": "query"}
                },
                "labeled_count": {
                    "filter": {"exists": {"field": "relevance"}}
                },
                "relevance_dist": {
                    "filter": {"exists": {"field": "relevance"}},
                    "aggs": {
                        "values": {
                            "terms": {"field": "relevance", "size": 10}
                        }
                    }
                }
            }
        }
        
        agg_response = client.search(index=index_name, body=agg_query)
        
        stats['unique_queries'] = agg_response['aggregations']['unique_queries']['value']
        stats['labeled'] = agg_response['aggregations']['labeled_count']['doc_count']
        
        stats['relevance_dist'] = {}
        buckets = agg_response['aggregations']['relevance_dist']['values']['buckets']
        for bucket in buckets:
            stats['relevance_dist'][bucket['key']] = bucket['doc_count']
        
    except Exception as e:
        print(f"  Warning: Failed to get stats: {e}")
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Step06: Upload labeled CSV to OpenSearch"
    )
    parser.add_argument(
        "--labeled_csv",
        required=True,
        help="Path to labeled CSV file"
    )
    parser.add_argument(
        "--index_name",
        required=True,
        help="OpenSearch index name"
    )
    parser.add_argument(
        "--env_file",
        help="Path to .env file (default: project_root/.env)"
    )
    parser.add_argument(
        "--delete_existing",
        action="store_true",
        help="Delete existing index before creating"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Show progress (default: True)"
    )
    args = parser.parse_args()
    
    print("=" * 70)
    print("Step06: Upload Labeled CSV to OpenSearch")
    print("=" * 70)
    
    # Connect to OpenSearch
    print("\n[1] Connecting to OpenSearch...")
    try:
        client = get_opensearch_client(args.env_file)
        cluster_info = client.info()
        print(f"  ✓ Connected to cluster: {cluster_info['cluster_name']}")
        print(f"    Version: {cluster_info['version']['number']}")
    except Exception as e:
        print(f"  ✗ OpenSearch connection failed: {e}")
        sys.exit(1)
    
    # Delete existing index if requested
    if args.delete_existing:
        print(f"\n[2] Deleting existing index: {args.index_name}")
        try:
            if client.indices.exists(index=args.index_name):
                client.indices.delete(index=args.index_name)
                print(f"  ✓ Index deleted")
            else:
                print(f"  ℹ Index does not exist")
        except Exception as e:
            print(f"  ✗ Failed to delete index: {e}")
    
    # Create index
    step_num = 2 if not args.delete_existing else 3
    print(f"\n[{step_num}] Creating relevance judgment index...")
    try:
        created = create_relevance_index(client, args.index_name)
        if not created:
            print(f"  ℹ Using existing index")
    except Exception as e:
        print(f"  ✗ Failed to create index: {e}")
        sys.exit(1)
    
    # Upload data
    step_num += 1
    print(f"\n[{step_num}] Uploading labeled CSV...")
    try:
        inserted = upload_labeled_csv(
            client, args.index_name, args.labeled_csv, args.verbose
        )
    except Exception as e:
        print(f"  ✗ Upload failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Get statistics
    step_num += 1
    print(f"\n[{step_num}] Index statistics:")
    stats = get_index_stats(client, args.index_name)
    print(f"  Total documents: {stats.get('total', 0):,}")
    print(f"  Unique queries: {stats.get('unique_queries', 0):,}")
    print(f"  Labeled documents: {stats.get('labeled', 0):,}")
    
    if stats.get('relevance_dist'):
        print(f"\n  Relevance distribution:")
        for rel, count in sorted(stats['relevance_dist'].items()):
            label = {2: "Very relevant", 1: "Partially relevant", 0: "Not relevant"}.get(rel, "Unknown")
            pct = count / max(stats.get('labeled', 1), 1) * 100
            print(f"    {rel} ({label}): {count:,} ({pct:.1f}%)")
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Index: {args.index_name}")
    print(f"Uploaded: {inserted:,} documents")
    print(f"Labeled: {stats.get('labeled', 0):,}/{stats.get('total', 0):,} ({stats.get('labeled', 0)/max(stats.get('total', 1), 1)*100:.1f}%)")
    print("=" * 70)
    print("\nNext step:")
    print(f"python process/07.calculate_metrics.py --index_name {args.index_name}")
    print("=" * 70)


if __name__ == "__main__":
    main()

