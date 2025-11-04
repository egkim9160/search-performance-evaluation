# 검색 품질 평가 완전 파이프라인

## 전체 워크플로우

```
Step 01: 검색 로그 수집
   ↓
Step 02: HEAD/TAIL 쿼리 선정
   ↓
Step 03: OpenSearch 검색 실행 (Lexical/Semantic)
   ↓
Step 04: Depth-K Pooling (결과 통합)
   ↓
Step 05: Pool을 OpenSearch에 업로드
   ↓
Step 06: AI 기반 Relevance Labeling
   ↓
Step 07: 평가 지표 계산 (nDCG, Recall, MRR)
   ↓
Step 08: 결과 시각화 및 리포트
```

---

## Step 01: 검색 로그 수집

MySQL에서 검색 로그를 가져옵니다.

```bash
python process/01.fetch_search_logs.py \
  --start_date 2024-05-01 \
  --end_date 2025-10-30 \
  --out_dir data/raw
```

**출력:**
- `data/raw/search_logs.csv`
- `data/raw/frequency_distribution.png`

---

## Step 02: HEAD/TAIL 쿼리 선정

검색 로그에서 대표 쿼리를 선정합니다.

```bash
python process/02.prepare_queries_and_fetch_os_results.py \
  --logs_csv data/raw/search_logs.csv \
  --output_dir data/processed \
  --head_sample_k 300 \
  --tail_sample_k 200
```

**출력:**
- `data/processed/queries_head_300.csv`
- `data/processed/queries_longtail_200.csv`

---

## Step 03: OpenSearch 검색 실행

Lexical과 Semantic 검색을 실행합니다.

### 설정 파일 수정

**`config/index_config.json`**
```json
{
  "indexes": {
    "baseline": {
      "name": "community-with-meta_classify-20250716",
      "board_filter": "MUZZIMA",
      "embedding_field": "vector_field"
    }
  }
}
```

**`config/search_experiments.json`**
```json
{
  "experiments": [
    {"id": "exp001", "name": "muzzima_lexical", "enabled": true},
    {"id": "exp002", "name": "muzzima_semantic", "enabled": true}
  ]
}
```

### 실행 (기존 3분할 설정 사용)

```bash
python process/03.fetch_opensearch_results.py \
  --run_only exp001 exp002
```

**출력:**
- `data/search_results/exp001_head_*.csv` (Lexical HEAD)
- `data/search_results/exp001_tail_*.csv` (Lexical TAIL)
- `data/search_results/exp002_head_*.csv` (Semantic HEAD)
- `data/search_results/exp002_tail_*.csv` (Semantic TAIL)

---

## Step 04: Depth-K Pooling (HEAD+TAIL 통합)

Lexical과 Semantic 결과를 합쳐 전체 문서 Pool을 만듭니다. 이후 단계는 이 통합 세트 기준으로 진행됩니다.

```bash
python process/04.pool_search_results.py \
  --results_head \
    data/search_results/exp001_head_*.csv \
    data/search_results/exp002_head_*.csv \
  --results_tail \
    data/search_results/exp001_tail_*.csv \
    data/search_results/exp002_tail_*.csv \
  --methods lexical semantic \
  --depth_k 20 \
  --query_set ALL \
  --output_dir data/pooled_results
```

**출력:**
- `data/pooled_results/pooled_all_lexical_semantic_k20_*.csv`

**통계 예시:**
```
Pooling Statistics:
  Depth-K: 20
  Total unique documents: 6,000

  Documents found per method:
    lexical: 6,000 (100.0%)
    semantic: 6,000 (100.0%)

  Document overlap:
    Found by 1 method only: 3,600 (60.0%)
    Found by all methods: 2,400 (40.0%)
```

---

## Step 05: Pool을 OpenSearch에 업로드 (단일 인덱스)

통합 pooled 결과를 단일 인덱스에 저장합니다.

```bash
python process/05.upload_pool_to_db.py \
  --pooled_csv data/pooled_results/pooled_all_lexical_semantic_k20_*.csv \
  --index_name search_relevance_judgments_all_20251101 \
  --delete_existing
```

**OpenSearch 인덱스 구조:**
```json
{
  "mappings": {
    "properties": {
      "query": {"type": "keyword"},
      "doc_id": {"type": "keyword"},
      "query_set": {"type": "keyword"},
      "found_by_methods": {"type": "keyword"},
      "num_methods_found": {"type": "integer"},
      
      "lexical_rank": {"type": "integer"},
      "lexical_score": {"type": "float"},
      "semantic_rank": {"type": "integer"},
      "semantic_score": {"type": "float"},
      
      "TITLE": {"type": "text"},
      "CONTENT": {"type": "text"},
      "merged_comment": {"type": "text"},
      
      "relevance": {"type": "integer"},
      "labeled_by": {"type": "keyword"},
      "labeled_at": {"type": "date"},
      "notes": {"type": "text"}
    }
  }
}
```

**출력:**
```
Summary
======================================================================
Index: search_relevance_judgments_head_20251101
Uploaded: 6,000 documents
Labeled: 0/6,000 (0.0%)
======================================================================
```

---

## Step 06: AI 기반 Relevance Labeling (단일 세트)

GPT-4를 사용하여 자동으로 관련도를 평가합니다. (OpenAI 공식 API 사용)

```bash
python process/06.label_relevance.py \
  --index_name search_relevance_judgments_all_20251101 \
  --model gpt-4o-mini
```

**Labeling 프로세스:**
1. OpenSearch에서 unlabeled 문서 조회
2. 각 문서에 대해 GPT-4 호출
3. Relevance (0/1/2) 판정
4. OpenSearch 인덱스에 업데이트

**출력:**
```
Summary
======================================================================
Processed: 6,000
Successfully labeled: 5,950
Failed: 50
Labeling coverage: 5,950/6,000 (99.2%)

Relevance distribution:
  2 (Very relevant): 1,200 (20.2%)
  1 (Partially relevant): 2,400 (40.3%)
  0 (Not relevant): 2,350 (39.5%)
======================================================================
```

---

## Step 07: 평가 지표 계산 (all/head/tail 제공)

nDCG, Recall, MRR 등을 계산합니다.

```bash
# ALL
python process/07.calculate_metrics.py \
  --index_name search_relevance_judgments_all_20251101 \
  --methods lexical semantic \
  --k_values 5 10 20 \
  --subset all \
  --output_dir data/evaluation_results

# HEAD only
python process/07.calculate_metrics.py \
  --index_name search_relevance_judgments_all_20251101 \
  --methods lexical semantic \
  --subset head \
  --output_dir data/evaluation_results

# TAIL only
python process/07.calculate_metrics.py \
  --index_name search_relevance_judgments_all_20251101 \
  --methods lexical semantic \
  --subset tail \
  --output_dir data/evaluation_results
```

**계산되는 지표:**
- **nDCG@K** (Normalized Discounted Cumulative Gain)
- **Recall@K** (재현율)
- **Precision@K** (정밀도)
- **MRR** (Mean Reciprocal Rank)
- **MAP** (Mean Average Precision)

**출력:**
```
Aggregated Metrics (Mean across queries):
----------------------------------------------------------------------
              ndcg@5  ndcg@10  ndcg@20  recall@5  recall@10  recall@20    mrr     map
lexical       0.4521   0.5234   0.5892    0.3421     0.5234     0.7123  0.5234  0.4891
semantic      0.4892   0.5621   0.6234    0.3892     0.5621     0.7456  0.5621  0.5234

Method Comparison:
----------------------------------------------------------------------

NDCG@20:
  🥇 semantic           : 0.6234
  🥈 lexical            : 0.5892

RECALL@20:
  🥇 semantic           : 0.7456
  🥈 lexical            : 0.7123

MRR:
  🥇 semantic           : 0.5621
  🥈 lexical            : 0.5234
```

**파일 출력:**
- `data/evaluation_results/head/per_query_metrics_lexical.csv`
- `data/evaluation_results/head/per_query_metrics_semantic.csv`
- `data/evaluation_results/head/aggregated_metrics.csv`

---

## Step 08: 결과 시각화

평가 결과를 차트와 리포트로 생성합니다.

```bash
python process/08.visualize_results.py \
  --results_dir data/evaluation_results/head \
  --output_dir data/evaluation_results/head \
  --k_values 5 10 20
```

**생성되는 시각화:**

1. **`method_comparison.png`** - 주요 지표 비교 (Bar chart)
2. **`metrics_heatmap.png`** - 전체 지표 히트맵
3. **`ndcg_by_k.png`** - K값에 따른 nDCG 변화
4. **`recall_by_k.png`** - K값에 따른 Recall 변화
5. **`distribution_ndcg@20.png`** - nDCG 분포 (Violin plot)
6. **`distribution_recall@20.png`** - Recall 분포
7. **`EVALUATION_REPORT.md`** - Markdown 리포트

**리포트 예시:**
```markdown
# Search Evaluation Results Summary

## Overall Comparison

### Key Metrics

| Method | NDCG@10 | NDCG@20 | RECALL@10 | RECALL@20 | MRR | MAP |
|--------|---------|---------|-----------|-----------|-----|-----|
| lexical | 0.5234 | 0.5892 | 0.5234 | 0.7123 | 0.5234 | 0.4891 |
| semantic | 0.5621 | 0.6234 | 0.5621 | 0.7456 | 0.5621 | 0.5234 |

## Best Method per Metric

- **NDCG@10**: semantic (0.5621)
- **NDCG@20**: semantic (0.6234)
- **RECALL@20**: semantic (0.7456)
- **MRR**: semantic (0.5621)

## Performance Differences (vs. Baseline)

### NDCG@20

- ✅ **semantic**: 0.6234 (+0.0342, +5.8%)
```

---

## 전체 파이프라인 실행 (한번에)

```bash
#!/bin/bash

# Step 1: 검색 로그 수집
python process/01.fetch_search_logs.py \
  --start_date 2024-05-01 \
  --end_date 2025-10-30

# Step 2: 쿼리 선정
python process/02.prepare_queries_and_fetch_os_results.py \
  --logs_csv data/raw/search_logs.csv

# Step 3: 검색 실행
python process/03.fetch_opensearch_results.py \
  --run_only exp001 exp002

# Step 4: Pooling (HEAD)
python process/04.pool_search_results.py \
  --results \
    data/search_results/exp001_head_*.csv \
    data/search_results/exp002_head_*.csv \
  --methods lexical semantic \
  --depth_k 20 \
  --query_set HEAD

# Step 5: OpenSearch 업로드
python process/05.upload_pool_to_db.py \
  --pooled_csv data/pooled_results/pooled_head_*.csv \
  --index_name search_relevance_judgments_head_20251101 \
  --delete_existing

# Step 6: Relevance Labeling
python process/06.label_relevance.py \
  --index_name search_relevance_judgments_head_20251101

# Step 7: 평가 지표 계산
python process/07.calculate_metrics.py \
  --index_name search_relevance_judgments_head_20251101 \
  --output_dir data/evaluation_results/head

# Step 8: 시각화
python process/08.visualize_results.py \
  --results_dir data/evaluation_results/head
```

---

## 평가 지표 해석

### nDCG@K (Normalized Discounted Cumulative Gain)
- **범위**: 0.0 ~ 1.0
- **의미**: 상위 K개 결과의 품질 (순서 고려)
- **해석**:
  - 1.0 = 완벽 (모든 관련 문서가 상위에)
  - 0.5 ~ 0.7 = 양호
  - < 0.5 = 개선 필요

### Recall@K
- **범위**: 0.0 ~ 1.0
- **의미**: 전체 관련 문서 중 상위 K개에 포함된 비율
- **해석**:
  - 0.7 = 관련 문서의 70%를 찾음
  - 높을수록 좋음

### MRR (Mean Reciprocal Rank)
- **범위**: 0.0 ~ 1.0
- **의미**: 첫 번째 관련 문서가 나타나는 순위의 역수
- **해석**:
  - 1.0 = 첫 번째 결과가 관련 문서
  - 0.5 = 평균 2번째에 첫 관련 문서
  - 0.1 = 평균 10번째에 첫 관련 문서

---

## 문제 해결

### OpenSearch 연결 실패
```
✗ OpenSearch connection failed
```
→ `.env` 파일의 OpenSearch 설정 확인
  - OPENSEARCH_HOST
  - OPENSEARCH_ID (또는 OPENSEARCH_USER)
  - OPENSEARCH_PW (또는 OPENSEARCH_PASSWORD)

### Labeling 실패
```
✗ Labeling failed: Missing OPENAI_API_KEY
```
→ `.env` 파일에 `OPENAI_API_KEY` 추가

### 지표 계산 실패
```
✗ No results found for semantic
```
→ OpenSearch 인덱스에 `semantic_rank` 필드가 있는지 확인
→ Step 5에서 올바른 pooled CSV 사용했는지 확인
→ Step 6에서 라벨링이 완료되었는지 확인

---

## 참고 자료

- [TREC Evaluation](https://trec.nist.gov/)
- [nDCG 설명](https://en.wikipedia.org/wiki/Discounted_cumulative_gain)
- [정보 검색 평가](https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-ranked-retrieval-results-1.html)
