import os
import argparse
from dataclasses import dataclass
from typing import Tuple

import pandas as pd


DEFAULT_LOGS_CSV = \
    "/SPO/Project/Search_model_evaluation/251030_logging_collection/data/raw.full/search_logs.csv"
DEFAULT_OUTPUT_DIR = \
    "/SPO/Project/Search_model_evaluation/251030_logging_collection/data/processed"


@dataclass
class QuerySampleSpec:
    head_top_n: int = 500
    head_sample_k: int = 300
    tail_start_rank: int = 1500
    tail_min_count: int = 3
    tail_min_words: int = 3
    tail_sample_k: int = 200
    random_seed: int = 42


def load_logs(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # Normalize column names
    cols = {c.lower(): c for c in df.columns}
    # Resolve query column
    query_col = None
    for candidate in ("query", "word", "keyword", "term", "search_term", "search_word"):
        if candidate in cols:
            query_col = cols[candidate]
            break
    if query_col is None:
        raise ValueError("CSV에 질의 컬럼이 필요합니다: query/word/keyword/term 등")
    count_col = None
    for candidate in ("search_count", "count", "cnt", "n"):
        if candidate in cols:
            count_col = cols[candidate]
            break
    if count_col is None:
        if "search_count" in df.columns:
            count_col = "search_count"
        else:
            raise ValueError("CSV에 검색량 컬럼이 필요합니다: search_count 또는 count 계열")

    # Clean
    df = df[[query_col, count_col]].rename(columns={query_col: "query", count_col: "search_count"})
    df["query"] = df["query"].astype(str).str.strip()
    df = df[df["query"] != ""]
    # Aggregate just in case
    df = df.groupby("query", as_index=False)["search_count"].sum()
    # Rank by count desc
    df = df.sort_values(["search_count", "query"], ascending=[False, True]).reset_index(drop=True)
    df["rank"] = df.index + 1
    return df


def word_count(text: str) -> int:
    return len(str(text).split())


def sample_head_and_tail(df: pd.DataFrame, spec: QuerySampleSpec) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = pd.Series(range(1)).sample(random_state=spec.random_seed)  # force seed init
    head_pool = df.head(spec.head_top_n)
    head_sample = head_pool.sample(n=min(spec.head_sample_k, len(head_pool)), random_state=spec.random_seed, replace=False)

    tail_pool = df[df["rank"] >= spec.tail_start_rank]
    tail_pool = tail_pool[(tail_pool["search_count"] >= spec.tail_min_count) & (tail_pool["query"].map(word_count) >= spec.tail_min_words)]
    tail_sample = tail_pool.sample(n=min(spec.tail_sample_k, len(tail_pool)), random_state=spec.random_seed, replace=False)

    head_sample = head_sample.sort_values("rank").reset_index(drop=True)
    tail_sample = tail_sample.sort_values("rank").reset_index(drop=True)
    return head_sample, tail_sample


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Step02: 쿼리 선정 (HEAD/TAIL 샘플링)")
    parser.add_argument("--logs_csv", default=DEFAULT_LOGS_CSV, help="검색 로그 CSV 파일 경로")
    parser.add_argument("--output_dir", default=DEFAULT_OUTPUT_DIR, help="출력 디렉토리")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드")
    parser.add_argument("--head_top_n", type=int, default=500, help="HEAD 풀 크기 (상위 N개)")
    parser.add_argument("--head_sample_k", type=int, default=300, help="HEAD 샘플링 개수")
    parser.add_argument("--tail_start_rank", type=int, default=1500, help="TAIL 시작 순위")
    parser.add_argument("--tail_min_count", type=int, default=3, help="TAIL 최소 검색 횟수")
    parser.add_argument("--tail_min_words", type=int, default=3, help="TAIL 최소 단어 수")
    parser.add_argument("--tail_sample_k", type=int, default=200, help="TAIL 샘플링 개수")
    args = parser.parse_args()

    ensure_dir(args.output_dir)

    print("=" * 60)
    print("Step02: Query Selection (HEAD/TAIL Sampling)")
    print("=" * 60)

    spec = QuerySampleSpec(
        head_top_n=args.head_top_n,
        head_sample_k=args.head_sample_k,
        tail_start_rank=args.tail_start_rank,
        tail_min_count=args.tail_min_count,
        tail_min_words=args.tail_min_words,
        tail_sample_k=args.tail_sample_k,
        random_seed=args.seed,
    )

    print(f"\n[1] Loading search logs from: {args.logs_csv}")
    logs_df = load_logs(args.logs_csv)
    print(f"  - Total queries: {len(logs_df):,}")
    print(f"  - Total search count: {logs_df['search_count'].sum():,}")

    print(f"\n[2] Sampling HEAD and TAIL queries...")
    head_df, tail_df = sample_head_and_tail(logs_df, spec)
    print(f"  - HEAD queries sampled: {len(head_df)}")
    print(f"  - TAIL queries sampled: {len(tail_df)}")

    head_out = os.path.join(args.output_dir, "queries_head_300.csv")
    tail_out = os.path.join(args.output_dir, "queries_longtail_200.csv")

    print(f"\n[3] Saving query sets...")
    head_df.to_csv(head_out, index=False, encoding='utf-8-sig')
    tail_df.to_csv(tail_out, index=False, encoding='utf-8-sig')
    print(f"  - HEAD queries saved to: {head_out}")
    print(f"  - TAIL queries saved to: {tail_out}")

    print("\n" + "=" * 60)
    print("Query selection completed successfully!")
    print("=" * 60)
    print(f"Total selected queries: {len(head_df) + len(tail_df)}")
    print(f"  - HEAD: {len(head_df)}")
    print(f"  - TAIL: {len(tail_df)}")
    print("=" * 60)


if __name__ == "__main__":
    main()


