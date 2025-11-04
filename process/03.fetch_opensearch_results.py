#!/usr/bin/env python3
"""
Step03: Fetch search results from OpenSearch based on configuration
Reads JSON config files and executes multiple search combinations
"""
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv

try:
    from opensearchpy import OpenSearch
except ImportError:
    print("Error: opensearch-py package is required. Install with: pip install opensearch-py")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("Warning: openai package not found. Semantic search will not be available.")
    OpenAI = None


# Ensure project root is on sys.path
try:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
except Exception:
    PROJECT_ROOT = Path.cwd()

# (deprecated) legacy multi-file configs removed


class EmbeddingGenerator:
    """Generate embeddings using OpenAI API"""

    def __init__(self, api_url: str, model: str):
        """
        Initialize embedding generator

        Args:
            api_url: OpenAI-compatible API URL
            model: Embedding model name
        """
        if OpenAI is None:
            raise RuntimeError("openai package is required for embedding generation")

        self.model = model
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=api_url,
            timeout=240,
            max_retries=2,
        )

    def generate(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        response = self.client.embeddings.create(
            input=[text],
            model=self.model
        )
        return response.data[0].embedding


class OpenSearchClient:
    """OpenSearch client wrapper"""

    def __init__(self, env_file: str):
        """Initialize OpenSearch client from environment file"""
        load_dotenv(env_file)

        host = os.getenv("OPENSEARCH_HOST")
        port = int(os.getenv("OPENSEARCH_PORT", "9200"))

        # Support various username/password key names
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
            raise RuntimeError(
                "Missing OpenSearch credentials in .env file. "
                "Required: OPENSEARCH_HOST, OPENSEARCH_ID/USER, OPENSEARCH_PW/PASSWORD"
            )

        self.client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_auth=(username, password),
            use_ssl=True,
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30,
            max_retries=2,
            retry_on_timeout=True,
        )

        # Verify connection
        if not self.client.ping():
            raise RuntimeError("Failed to connect to OpenSearch (ping failed)")

        print(f"  ✓ Connected to OpenSearch: {host}:{port}")

    def search(self, index: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Execute search query"""
        return self.client.search(index=index, body=body)


class QueryBuilder:
    """Build OpenSearch query from configuration"""

    @staticmethod
    def build_query(
        query_method: Dict[str, Any],
        index_config: Dict[str, Any],
        query_text: str,
        top_k: int = 20,
        embedding_generator: EmbeddingGenerator = None
    ) -> Dict[str, Any]:
        """
        Build query body based on query method and index configuration

        Args:
            query_method: Query method configuration from query_config.json
            index_config: Index configuration from index_config.json
            query_text: Search query text
            top_k: Number of results to return
            embedding_generator: Embedding generator for semantic queries

        Returns:
            OpenSearch query body
        """
        query_structure = query_method["query_structure"]
        query_type = query_structure["type"]

        if query_type == "match":
            return QueryBuilder._build_match_query(
                query_structure, index_config, query_text, top_k
            )

        elif query_type == "multi_match":
            return QueryBuilder._build_multi_match_query(
                query_structure, index_config, query_text, top_k
            )

        elif query_type == "bool":
            return QueryBuilder._build_bool_query(
                query_structure, index_config, query_text, top_k
            )

        elif query_type == "knn":
            if embedding_generator is None:
                raise ValueError("Embedding generator is required for kNN queries")
            return QueryBuilder._build_knn_query(
                query_structure, index_config, query_text, top_k, embedding_generator
            )

        elif query_type == "hybrid":
            if embedding_generator is None:
                raise ValueError("Embedding generator is required for hybrid queries")
            return QueryBuilder._build_hybrid_query(
                query_structure, index_config, query_text, top_k, embedding_generator
            )

        else:
            raise ValueError(f"Unsupported query type: {query_type}")

    @staticmethod
    def _build_match_query(
        structure: Dict, index_config: Dict, query_text: str, top_k: int
    ) -> Dict:
        """Build simple match query"""
        content_field = index_config["fields"]["content"]
        board_filter = index_config.get("board_filter")

        query_body = {
            "_source": index_config.get("source_fields", True),
            "size": top_k
        }

        # Add BOARD_NAME filter if specified
        if board_filter:
            board_name_field = index_config["fields"]["board_name"]
            query_body["query"] = {
                "bool": {
                    "must": [
                        {
                            "match": {
                                content_field: {
                                    "query": query_text,
                                    "operator": structure.get("operator", "and")
                                }
                            }
                        }
                    ],
                    "filter": [
                        {
                            "term": {
                                board_name_field: board_filter
                            }
                        }
                    ]
                }
            }
        else:
            query_body["query"] = {
                "match": {
                    content_field: {
                        "query": query_text,
                        "operator": structure.get("operator", "and")
                    }
                }
            }

        return query_body

    @staticmethod
    def _build_multi_match_query(
        structure: Dict, index_config: Dict, query_text: str, top_k: int
    ) -> Dict:
        """Build multi-match query"""
        # Build fields with boosts from query method config
        field_boosts = structure.get("field_boosts", {})
        fields = []

        for field_key, boost in field_boosts.items():
            actual_field = index_config["fields"].get(field_key)
            if actual_field:
                fields.append(f"{actual_field}^{boost}")

        # Fallback: if no fields specified, use content field
        if not fields:
            content_field = index_config["fields"]["content"]
            fields = [content_field]

        return {
            "query": {
                "multi_match": {
                    "query": query_text,
                    "fields": fields,
                    "operator": structure.get("operator", "and")
                }
            },
            "_source": index_config.get("source_fields", True),
            "size": top_k
        }

    @staticmethod
    def _build_bool_query(
        structure: Dict, index_config: Dict, query_text: str, top_k: int
    ) -> Dict:
        """Build bool query"""
        content_field = index_config["fields"]["content"]

        must_clause = structure.get("must", {})
        should_clause = structure.get("should", {})

        query_body = {
            "query": {
                "bool": {}
            },
            "_source": index_config.get("source_fields", True),
            "size": top_k
        }

        # Build must clause
        if must_clause.get("type") == "match":
            query_body["query"]["bool"]["must"] = {
                "match": {
                    content_field: {
                        "query": query_text,
                        "operator": must_clause.get("operator", "and")
                    }
                }
            }

        # Build should clause
        if should_clause.get("type") == "match":
            keywords_field = index_config["fields"].get("keywords")
            if keywords_field:
                query_body["query"]["bool"]["should"] = {
                    "match": {
                        keywords_field: {
                            "query": query_text,
                            "boost": should_clause.get("boost", 1.0)
                        }
                    }
                }

        return query_body

    @staticmethod
    def _build_knn_query(
        structure: Dict,
        index_config: Dict,
        query_text: str,
        top_k: int,
        embedding_generator: EmbeddingGenerator
    ) -> Dict:
        """Build kNN (semantic) query"""
        # Generate embedding for query text
        query_vector = embedding_generator.generate(query_text)

        embedding_field = index_config.get("embedding_field", "vector_field")
        board_filter = index_config.get("board_filter")
        k = structure.get("k", top_k)

        query_body = {
            "size": k,
            "_source": index_config.get("source_fields", True),
            "query": {
                "knn": {
                    embedding_field: {
                        "vector": query_vector,
                        "k": k
                    }
                }
            }
        }

        # Add BOARD_NAME filter if specified
        if board_filter:
            board_name_field = index_config["fields"]["board_name"]
            query_body["query"]["knn"][embedding_field]["filter"] = {
                "term": {
                    board_name_field: board_filter
                }
            }

        return query_body

    @staticmethod
    def _build_hybrid_query(
        _structure: Dict, _index_config: Dict, _query_text: str, _top_k: int
    ) -> Dict:
        """Build hybrid query (lexical + semantic)"""
        # Note: Embedding generation required
        raise NotImplementedError(
            "Hybrid query requires both lexical and semantic components. "
            "Please implement embedding model integration."
        )


class SearchResultCollector:
    """Collect and save search results"""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def collect_results(
        self,
        client: OpenSearchClient,
        experiment: Dict[str, Any],
        index_config: Dict[str, Any],
        query_method: Dict[str, Any],
        queries_df: pd.DataFrame,
        query_set_name: str,
        top_k: int = 20,
        verbose: bool = True,
        embedding_generator: EmbeddingGenerator = None
    ) -> pd.DataFrame:
        """
        Execute searches for all queries and collect results

        Args:
            client: OpenSearch client
            experiment: Experiment configuration
            index_config: Index configuration
            query_method: Query method configuration
            queries_df: DataFrame with query column
            query_set_name: "HEAD" or "TAIL"
            top_k: Number of results to return
            verbose: Show progress

        Returns:
            DataFrame with search results
        """
        records = []
        failed_queries = []
        total_queries = len(queries_df)
        experiment_id = experiment["id"]
        experiment_name = experiment["name"]
        index_name = index_config["name"]

        if verbose:
            print(f"\n    Processing {query_set_name} queries ({total_queries} queries)...")

        for idx, row in queries_df.iterrows():
            query_text = row["query"]

            try:
                # Build query
                query_body = QueryBuilder.build_query(
                    query_method, index_config, query_text, top_k, embedding_generator
                )

                # Execute search
                response = client.search(index=index_name, body=query_body)

                # Extract hits
                hits = response.get("hits", {}).get("hits", [])

                # Collect results
                for rank, hit in enumerate(hits, start=1):
                    source = hit.get("_source", {}) or {}

                    record = {
                        "experiment_id": experiment_id,
                        "experiment_name": experiment_name,
                        "query_set": query_set_name,
                        "query": query_text,
                        "rank": rank,
                        "index": hit.get("_index"),
                        "doc_id": hit.get("_id"),
                        "score": hit.get("_score"),
                    }

                    # Add source fields
                    for field in index_config.get("source_fields", []):
                        value = source.get(field)
                        # Handle list fields (e.g., keywords)
                        if isinstance(value, list):
                            record[field] = ", ".join(str(v) for v in value)
                        else:
                            record[field] = value

                    records.append(record)

                # Progress indicator
                if verbose and (idx + 1) % 50 == 0:
                    print(f"      Processed {idx + 1}/{total_queries} queries...")

            except Exception as e:
                failed_queries.append({"query": query_text, "error": str(e)})
                if verbose:
                    print(f"      Warning: Failed query '{query_text}': {e}")
                continue

        if verbose:
            print(f"      ✓ Completed: {total_queries} queries, "
                  f"{len(failed_queries)} failed")

        results_df = pd.DataFrame.from_records(records)

        # Save failed queries if any
        if failed_queries:
            failed_df = pd.DataFrame.from_records(failed_queries)
            failed_path = os.path.join(
                self.output_dir,
                f"{experiment_id}_{query_set_name.lower()}_failed.csv"
            )
            failed_df.to_csv(failed_path, index=False, encoding='utf-8-sig')
            if verbose:
                print(f"      ⚠ Failed queries saved to: {failed_path}")

        return results_df

    def save_results(
        self, df: pd.DataFrame, experiment_id: str, query_set_name: str
    ) -> str:
        """Save results to CSV file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{experiment_id}_{query_set_name.lower()}_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)

        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        return filepath


def load_json_config(config_path: str) -> Dict[str, Any]:
    """Load JSON configuration file"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config


# legacy builder removed


def load_queries(csv_path: str) -> pd.DataFrame:
    """Load query CSV file"""
    df = pd.read_csv(csv_path)
    if "query" not in df.columns:
        raise ValueError(f"Query CSV must have 'query' column: {csv_path}")
    return df


def main():
    parser = argparse.ArgumentParser(
        description="Step03: Fetch OpenSearch results based on JSON configuration"
    )
    parser.add_argument(
        "--single_config",
        required=True,
        help="Path to JSON config with env_file, query_files, output_dir, experiments[]"
    )
    parser.add_argument(
        "--run_only",
        nargs="+",
        help="Run only specified experiment IDs (e.g., exp001 exp002)"
    )
    parser.add_argument(
        "--query_sets",
        nargs="+",
        choices=["head", "tail"],
        default=["head", "tail"],
        help="Query sets to process (default: both)"
    )
    parser.add_argument(
        "--top_k",
        type=int,
        default=20,
        help="Number of results to retrieve per query (default: 20)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Show progress (default: True)"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Step03: Fetch OpenSearch Search Results")
    print("=" * 70)

    # Load configurations (single file only)
    print(f"\n[1] Loading configuration...")
    try:
        cfg = load_json_config(args.single_config)
        print(f"  ✓ Single config loaded: {args.single_config}")
    except Exception as e:
        print(f"  ✗ Failed to load configuration: {e}")
        sys.exit(1)

    # Initialize OpenSearch client
    print(f"\n[2] Connecting to OpenSearch...")
    try:
        env_file = cfg.get("env_file")
        if not env_file or not os.path.exists(env_file):
            raise RuntimeError(f".env file not found: {env_file}")
        client = OpenSearchClient(env_file)
    except Exception as e:
        print(f"  ✗ Failed to connect: {e}")
        sys.exit(1)

    # Load queries
    print(f"\n[3] Loading query files...")
    query_files = cfg.get("query_files", {})
    queries = {}

    for query_set in args.query_sets:
        if query_set not in query_files:
            print(f"  ✗ Warning: {query_set} query file not specified in config")
            continue

        query_file = query_files[query_set]
        try:
            queries[query_set] = load_queries(query_file)
            print(f"  ✓ Loaded {query_set.upper()}: {len(queries[query_set])} queries")
        except Exception as e:
            print(f"  ✗ Failed to load {query_set} queries: {e}")
            sys.exit(1)

    # Initialize result collector
    output_dir = cfg.get("output_dir", "data/search_results")
    collector = SearchResultCollector(output_dir)
    print(f"\n[4] Output directory: {output_dir}")

    # Filter experiments to run
    all_experiments = cfg.get("experiments", [])

    # Apply filters
    experiments_to_run = []
    for exp in all_experiments:
        # Skip if run_only specified and this exp not in list
        if args.run_only and exp["id"] not in args.run_only:
            continue

        experiments_to_run.append(exp)

    print(f"\n[5] Running {len(experiments_to_run)} experiments:")
    for exp in experiments_to_run:
        print(f"  - [{exp['id']}] {exp['name']}: {exp.get('description', 'N/A')}")

    # Execute searches
    print(f"\n[6] Executing searches...")
    print("=" * 70)

    total_experiments = len(experiments_to_run)
    total_files_saved = 0
    skipped_experiments = []

    for exp_idx, experiment in enumerate(experiments_to_run, start=1):
        exp_id = experiment["id"]
        exp_name = experiment["name"]
        index_name = experiment["index_name"]
        query_method = experiment["query_method"]

        print(f"\n[{exp_idx}/{total_experiments}] Experiment: {exp_id}")
        print(f"  Name: {exp_name}")
        print(f"  Description: {experiment.get('description', 'N/A')}")
        print(f"  Index: {index_name}")
        print(f"  Query Method: {query_method.get('id', 'N/A')} ({query_method.get('search_type', 'N/A')})")

        # Minimal index config defaults
        index_config = {
            "name": index_name,
            "fields": {
                "content": "merged_comment",
                "board_name": "BOARD_NAME",
                "keywords": "keywords"
            },
            "source_fields": [
                "BOARD_IDX", "TITLE", "BOARD_NAME", "CONTENT", "merged_comment",
                "view_cnt", "comment_cnt", "agree_cnt", "disagree_cnt", "REG_DATE", "U_ID", "keywords"
            ],
            "embedding_field": "vector_field"
        }
        print(f"  → Index Name: {index_config['name']}")
        print(f"  → Search Type: {query_method.get('search_type', 'N/A')}")

        # Initialize embedding generator if required
        embedding_gen = None
        if query_method.get("search_type") == "semantic" or query_method.get("query_structure", {}).get("type") == "knn":
            try:
                embedding_model = query_method.get("embedding_model")
                embedding_api_url = query_method.get("embedding_api_url")
                if not embedding_api_url or not embedding_model:
                    raise ValueError("Missing embedding_model or embedding_api_url in query config")

                embedding_gen = EmbeddingGenerator(embedding_api_url, embedding_model)
                print(f"  → Embedding Model: {embedding_model}")
            except Exception as e:
                print(f"  ✗ Failed to initialize embedding generator: {e}")
                skipped_experiments.append(exp_id)
                continue

        try:
            for query_set_name, queries_df in queries.items():
                # Collect results
                results_df = collector.collect_results(
                    client=client,
                    experiment=experiment,
                    index_config=index_config,
                    query_method=query_method,
                    queries_df=queries_df,
                    query_set_name=query_set_name.upper(),
                    top_k=args.top_k,
                    verbose=args.verbose,
                    embedding_generator=embedding_gen
                )

                # Save results
                if not results_df.empty:
                    filepath = collector.save_results(
                        results_df,
                        exp_id,
                        query_set_name.upper()
                    )
                    print(f"    ✓ Saved {len(results_df)} results to: {filepath}")
                    total_files_saved += 1
                else:
                    print(f"    ⚠ Warning: No results for {query_set_name.upper()}")

        except NotImplementedError as e:
            print(f"  ⚠ Skipped: {e}")
            skipped_experiments.append(exp_id)
            continue
        except Exception as e:
            print(f"  ✗ Error: {e}")
            skipped_experiments.append(exp_id)
            if not cfg.get("execution", {}).get("continue_on_error", True):
                sys.exit(1)
            continue

    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Total experiments: {len(all_experiments)}")
    print(f"  - Enabled: {len(experiments_to_run)}")
    print(f"  - Completed: {total_experiments - len(skipped_experiments)}")
    print(f"  - Skipped: {len(skipped_experiments)}")
    if skipped_experiments:
        print(f"    Skipped IDs: {', '.join(skipped_experiments)}")
    print(f"Result files saved: {total_files_saved}")
    print(f"Output directory: {output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
