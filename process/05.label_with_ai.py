#!/usr/bin/env python3
"""
Step05: Label CSV with AI before uploading to OpenSearch
Performs relevance labeling on pooled CSV file directly
"""
import os
import sys
import argparse
import json
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai package is required. Install with: pip install openai")
    sys.exit(1)


# Ensure project root is on sys.path
try:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
except Exception:
    PROJECT_ROOT = Path.cwd()


RELEVANCE_PROMPT_TEMPLATE = """당신은 검색 품질 평가 전문가입니다. 주어진 검색어(쿼리)와 문서의 관련성을 평가해주세요.

**평가 기준:**
- 2 (매우 관련): 문서가 검색어에 대한 직접적이고 완전한 답변을 제공
- 1 (부분 관련): 문서가 검색어와 일부 관련이 있으나 완전한 답변은 아님
- 0 (무관): 문서가 검색어와 전혀 관련이 없음

**검색어:**
{query}

**문서 제목:**
{title}

**문서 내용:**
{content}

**지시사항:**
1. 검색어와 문서의 관련성을 신중히 평가하세요
2. 반드시 JSON 형식으로만 응답하세요
3. 평가 이유를 간단히 설명하세요

**응답 형식 (JSON만):**
{{
  "relevance": 0 또는 1 또는 2,
  "reason": "평가 이유 (한 문장)"
}}
"""


class RelevanceLabeler:
    """AI-based relevance labeling for CSV"""
    
    def __init__(self, api_url: Optional[str], model: str, labeled_by: str = "AI-GPT4"):
        """Initialize labeler with OpenAI API"""
        self.model = model
        self.labeled_by = labeled_by
        
        # Use official OpenAI API if api_url is None
        client_params = {
            "api_key": os.getenv("OPENAI_API_KEY"),
            "timeout": 120,
            "max_retries": 2,
        }
        
        if api_url:
            client_params["base_url"] = api_url
        
        self.client = OpenAI(**client_params)
        
        print(f"  Model: {self.model}")
        print(f"  API: {'Official OpenAI API' if not api_url else api_url}")
        print(f"  Labeled by: {self.labeled_by}")
    
    def label_document(self, query: str, title: str, content: str) -> Dict:
        """
        Label single document
        
        Returns:
            dict with 'relevance' (int) and 'reason' (str), or None if failed
        """
        # Convert to string and handle NaN/None
        title_str = str(title) if pd.notna(title) and title else "(제목 없음)"
        content_str = str(content) if pd.notna(content) and content else "(내용 없음)"
        
        # Truncate content to 2000 characters
        if content_str != "(내용 없음)":
            content_str = content_str[:2000]
        
        prompt = RELEVANCE_PROMPT_TEMPLATE.format(
            query=query,
            title=title_str,
            content=content_str
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a search quality expert. Always respond in valid JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            if "relevance" not in result:
                raise ValueError("Missing 'relevance' field")
            
            relevance = int(result["relevance"])
            if relevance not in [0, 1, 2]:
                raise ValueError(f"Invalid relevance value: {relevance}")
            
            return {
                "relevance": relevance,
                "reason": result.get("reason", "")
            }
        
        except Exception as e:
            return None
    
    def label_csv(
        self,
        input_csv: str,
        output_csv: str,
        limit: Optional[int] = None,
        skip_labeled: bool = True
    ) -> Dict:
        """
        Label documents in CSV file
        
        Args:
            input_csv: Input CSV file path
            output_csv: Output CSV file path
            limit: Limit number of documents to label (for testing)
            skip_labeled: Skip already labeled documents
        
        Returns:
            dict with statistics
        """
        print(f"\n[1] Loading CSV file...")
        df = pd.read_csv(input_csv)
        print(f"  ✓ Loaded {len(df):,} documents")
        
        # Check if relevance columns exist
        if 'relevance' not in df.columns:
            df['relevance'] = None
            df['labeled_by'] = None
            df['labeled_at'] = None
            df['notes'] = None
        
        # Determine which documents to label
        if skip_labeled:
            to_label = df[df['relevance'].isna()].copy()
            print(f"  Already labeled: {(~df['relevance'].isna()).sum():,}")
            print(f"  To label: {len(to_label):,}")
        else:
            to_label = df.copy()
            print(f"  Total to label: {len(to_label):,}")
        
        if limit:
            to_label = to_label.head(limit)
            print(f"  Limited to: {len(to_label):,} documents")
        
        if len(to_label) == 0:
            print(f"\n  ℹ No documents to label")
            return {"total": 0, "labeled": 0, "failed": 0}
        
        print(f"\n[2] Starting AI labeling...")
        print(f"  Total to process: {len(to_label):,}")
        
        labeled_count = 0
        failed_count = 0
        
        # Progress bar
        for idx, row in tqdm(to_label.iterrows(), total=len(to_label), desc="  Labeling"):
            try:
                # Choose content (prefer merged_comment, fallback to CONTENT)
                # Handle NaN values from pandas
                merged_comment = row.get("merged_comment")
                content_field = row.get("CONTENT")
                
                # Use merged_comment if available and not NaN, otherwise use CONTENT
                if pd.notna(merged_comment) and merged_comment:
                    content = merged_comment
                elif pd.notna(content_field) and content_field:
                    content = content_field
                else:
                    content = ""
                
                # Get title safely
                title = row.get("TITLE", "")
                if pd.isna(title):
                    title = ""
                
                # Label document
                result = self.label_document(
                    query=row["query"],
                    title=title,
                    content=content
                )
                
                if result:
                    # Update DataFrame
                    df.loc[idx, 'relevance'] = result["relevance"]
                    df.loc[idx, 'notes'] = result["reason"]
                    df.loc[idx, 'labeled_by'] = self.labeled_by
                    df.loc[idx, 'labeled_at'] = datetime.now().isoformat()
                    
                    labeled_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                failed_count += 1
                if failed_count <= 5:
                    print(f"\n    Warning: Error labeling row {idx}: {e}")
        
        print(f"\n[3] Saving labeled CSV...")
        df.to_csv(output_csv, index=False, encoding='utf-8-sig')
        print(f"  ✓ Saved to: {output_csv}")
        
        # Statistics
        stats = {
            "total": len(to_label),
            "labeled": labeled_count,
            "failed": failed_count,
            "total_labeled_in_file": (~df['relevance'].isna()).sum()
        }
        
        print(f"\n[4] Labeling statistics:")
        print(f"  Processed: {stats['total']:,}")
        print(f"  Successfully labeled: {stats['labeled']:,}")
        print(f"  Failed: {stats['failed']:,}")
        print(f"  Total labeled in file: {stats['total_labeled_in_file']:,}/{len(df):,}")
        
        # Relevance distribution
        relevance_dist = df['relevance'].value_counts().sort_index()
        if len(relevance_dist) > 0:
            print(f"\n  Relevance distribution:")
            for rel, count in relevance_dist.items():
                if pd.notna(rel):
                    label = {2: "Very relevant", 1: "Partially relevant", 0: "Not relevant"}.get(int(rel), "Unknown")
                    pct = count / stats['total_labeled_in_file'] * 100
                    print(f"    {int(rel)} ({label}): {count:,} ({pct:.1f}%)")
        
        return stats


def main():
    parser = argparse.ArgumentParser(
        description="Step05: Label CSV with AI before uploading to OpenSearch"
    )
    parser.add_argument(
        "--input_csv",
        required=True,
        help="Input pooled CSV file"
    )
    parser.add_argument(
        "--output_csv",
        help="Output labeled CSV file (default: input_csv with _labeled suffix)"
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="AI model to use (default: gpt-4o-mini)"
    )
    parser.add_argument(
        "--api_url",
        default=None,
        help="OpenAI API URL (default: None = use official OpenAI API)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of documents to label (for testing)"
    )
    parser.add_argument(
        "--labeled_by",
        default="AI-GPT4",
        help="Labeler name (default: AI-GPT4)"
    )
    parser.add_argument(
        "--skip_labeled",
        action="store_true",
        default=True,
        help="Skip already labeled documents (default: True)"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "test", "skip"],
        default="full",
        help="Labeling mode: full (all docs), test (50 docs), skip (use existing labeled file)"
    )
    args = parser.parse_args()
    
    # Apply mode settings
    if args.mode == "test" and not args.limit:
        args.limit = 50
    elif args.mode == "skip":
        args.limit = 0  # Skip labeling entirely
    
    # Set output file
    if not args.output_csv:
        input_path = Path(args.input_csv)
        args.output_csv = str(input_path.parent / f"{input_path.stem}_labeled{input_path.suffix}")
    
    print("=" * 70)
    print("Step05: AI-based Relevance Labeling (CSV)")
    print("=" * 70)
    
    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n  ✗ Error: OPENAI_API_KEY not found in environment variables")
        print("  Please set OPENAI_API_KEY in .env file")
        sys.exit(1)
    
    # Initialize labeler
    print(f"\n[0] Initializing AI labeler...")
    try:
        labeler = RelevanceLabeler(
            api_url=args.api_url,
            model=args.model,
            labeled_by=args.labeled_by
        )
        print("  ✓ Labeler initialized")
    except Exception as e:
        print(f"  ✗ Failed to initialize labeler: {e}")
        sys.exit(1)
    
    # Label CSV
    try:
        # Check if skip mode and labeled file already exists
        if args.mode == "skip":
            if not Path(args.output_csv).exists():
                print(f"\n  ✗ Skip mode requested but labeled file does not exist: {args.output_csv}")
                print(f"  Please run labeling first or use --mode full/test")
                sys.exit(1)
            else:
                print(f"\n  ℹ Skip mode: Using existing labeled file")
                print(f"  File: {args.output_csv}")
                # Create dummy stats
                df = pd.read_csv(args.output_csv)
                stats = {
                    "total": 0,
                    "labeled": 0,
                    "failed": 0,
                    "total_labeled_in_file": (~df['relevance'].isna()).sum() if 'relevance' in df.columns else 0
                }
        else:
            stats = labeler.label_csv(
                input_csv=args.input_csv,
                output_csv=args.output_csv,
                limit=args.limit,
                skip_labeled=args.skip_labeled
            )
    except Exception as e:
        print(f"\n  ✗ Labeling failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Input: {args.input_csv}")
    print(f"Output: {args.output_csv}")
    print(f"Processed: {stats['total']:,}")
    print(f"Successfully labeled: {stats['labeled']:,}")
    print(f"Failed: {stats['failed']:,}")
    print(f"Success rate: {stats['labeled']/max(stats['total'], 1)*100:.1f}%")
    print("=" * 70)
    print("\nNext step:")
    print(f"python process/06.upload_labeled_csv_to_opensearch.py \\")
    print(f"  --labeled_csv {args.output_csv} \\")
    print(f"  --index_name search_relevance_judgments_YYYYMMDD")
    print("=" * 70)


if __name__ == "__main__":
    main()

