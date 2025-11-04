# 검색 평가 시스템 사용 가이드

## 전체 워크플로우

```
01.fetch_search_logs.py
  ↓ (검색 로그 수집)
02.prepare_queries_and_fetch_os_results.py
  ↓ (HEAD/TAIL 쿼리 선정)
03.fetch_opensearch_results.py
  ↓ (Lexical/Semantic 검색 실행)
04.pool_search_results.py
  ↓ (Depth-K Pooling으로 결과 통합)
평가 데이터셋 완성!
```

---

## Step 04: 검색 결과 통합 (Depth-K Pooling)

### Depth-K Pooling이란? (TREC 표준 방식)

**핵심 원리:**
- 각 검색 방법에서 **top-K 개씩** 문서를 가져옴
- 모든 문서를 합침 (union)
- 중복 제거

**예시: K=20, 3가지 방법**
```
Lexical top-20:  [doc1, doc2, doc3, ..., doc20]
Semantic top-20: [doc2, doc5, doc21, ..., doc40]
Hybrid top-20:   [doc1, doc2, doc22, ..., doc41]

Pool (합집합):   [doc1, doc2, doc3, doc5, ..., doc41]
                 → 약 20~60개 (중복 제거 후)
```

**왜 이렇게 하나요?**
1. **공평성**: 각 방법이 동등하게 기여 (각 20개씩)
2. **효율성**: 모든 문서를 평가할 필요 없음
3. **표준**: TREC에서 오랫동안 사용된 검증된 방식

---

## 사용 방법

### (권장) HEAD+TAIL 통합 Pooling → 이후 전 단계 단일 세트로 진행

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

출력 예시: `pooled_all_lexical_semantic_k20_YYYYMMDD_HHMMSS.csv`

이 파일을 기준으로 AI 라벨링, 업로드, 평가를 모두 단일 세트로 진행합니다. 평가 단계에서 `--subset`으로 all/head/tail을 분리합니다.

### (구버전) 세트별 개별 Pooling

```bash
python process/04.pool_search_results.py \
  --results \
    data/search_results/exp001_head_20250101_120000.csv \
    data/search_results/exp002_head_20250101_120000.csv \
  --methods lexical semantic \
  --depth_k 20 \
  --query_set HEAD \
  --output_dir data/pooled_results
```

**파라미터 설명:**
- `--results`: 검색 결과 CSV 파일들 (공백으로 구분)
- `--methods`: 각 파일에 해당하는 방법 이름 (공백으로 구분)
- `--depth_k`: 각 방법에서 가져올 문서 개수 (기본: 20)
- `--query_set`: 쿼리 세트 이름 (출력 파일명에 사용)

### 5가지 방법 (Lexical + Semantic + 3개 Hybrid)

```bash
python process/04.pool_search_results.py \
  --results \
    exp001_head.csv \
    exp002_head.csv \
    exp003_head.csv \
    exp004_head.csv \
    exp005_head.csv \
  --methods \
    lexical \
    semantic \
    hybrid_v1 \
    hybrid_v2 \
    hybrid_v3 \
  --depth_k 20 \
  --query_set HEAD
```

---

## 출력 형식

### 파일명
```
pooled_all_lexical_semantic_k20_20250101_120000.csv
```

### CSV 컬럼 구조

```csv
query,doc_id,found_by_methods,num_methods_found,lexical_rank,lexical_score,semantic_rank,semantic_score,merged_comment,...

맥북,doc123,"lexical,semantic",2,1,15.3,5,0.92,나홀로 근무 시 페이...
맥북,doc456,lexical,1,2,14.8,NULL,NULL,통증하고 있는...
맥북,doc789,semantic,1,NULL,NULL,1,0.95,초반에 심적으로...
```

**주요 컬럼:**
- `found_by_methods`: 발견한 방법들 (쉼표로 구분)
- `num_methods_found`: 몇 개 방법에서 발견했는지
- `{method}_rank`: 각 방법에서의 순위 (없으면 NULL)
- `{method}_score`: 각 방법에서의 점수 (없으면 NULL)

---

## Pooling 통계 예시

### 2가지 방법 (Lexical + Semantic)

```
Pooling Statistics:
  Depth-K: 20
  Number of methods: 2
  Total unique documents in pool: 6,000

  Documents found per method:
    lexical: 6,000 (100.0%)    ← 각 쿼리당 20개씩
    semantic: 6,000 (100.0%)   ← 각 쿼리당 20개씩

  Document overlap by number of methods:
    Found by 1 method only: 3,600 (60.0%)  ← 한 방법에서만 발견
    Found by all methods: 2,400 (40.0%)    ← 두 방법 모두 발견

  Unique contributions (found by only one method):
    lexical only: 1,800 (30.0%)   ← Lexical만 발견
    semantic only: 1,800 (30.0%)  ← Semantic만 발견
```

**해석:**
- 각 방법이 6,000개 문서 기여 (300 쿼리 × 20개)
- 40%는 두 방법 모두 발견 (중복)
- 60%는 한 방법만 발견 (고유)
- **→ 두 방법이 서로 보완적!**

### 5가지 방법

```
Pooling Statistics:
  Depth-K: 20
  Number of methods: 5
  Total unique documents in pool: 18,000

  Documents found per method:
    lexical: 6,000 (33.3%)
    semantic: 6,000 (33.3%)
    hybrid_v1: 6,000 (33.3%)
    hybrid_v2: 6,000 (33.3%)
    hybrid_v3: 6,000 (33.3%)

  Document overlap by number of methods:
    Found by 1 method only: 5,400 (30.0%)
    Found by 2 methods: 4,500 (25.0%)
    Found by 3 methods: 3,600 (20.0%)
    Found by 4 methods: 2,700 (15.0%)
    Found by all methods: 1,800 (10.0%)

  Unique contributions (found by only one method):
    lexical only: 1,200 (6.7%)
    semantic only: 1,500 (8.3%)
    hybrid_v1 only: 1,000 (5.6%)
    hybrid_v2 only: 900 (5.0%)
    hybrid_v3 only: 800 (4.4%)
```

**해석:**
- 각 방법이 6,000개 기여 (300 쿼리 × 20개)
- 총 30,000개에서 중복 제거 → 18,000개
- 10%만 모든 방법에서 발견 (핵심 문서)
- 30%는 한 방법만 발견 (고유 기여)

---

## 일부만 중복되는 경우?

**질문:** "5개 방법 중 3개에서만 발견된 문서는?"

**답:** 모두 pool에 포함됩니다!

```
doc_A: lexical, semantic, hybrid_v1에서 발견
  → num_methods_found = 3
  → found_by_methods = "lexical,semantic,hybrid_v1"
  → lexical_rank = 5, semantic_rank = 12, hybrid_v1_rank = 8
  → hybrid_v2_rank = NULL, hybrid_v3_rank = NULL

doc_B: hybrid_v2, hybrid_v3에서만 발견
  → num_methods_found = 2
  → found_by_methods = "hybrid_v2,hybrid_v3"
  → lexical_rank = NULL, semantic_rank = NULL, hybrid_v1_rank = NULL
  → hybrid_v2_rank = 3, hybrid_v3_rank = 7
```

**모든 조합이 가능하고, 모두 추적됩니다!**

---

## 전체 파이프라인 예시

```bash
# 1. 검색 로그 수집
python process/01.fetch_search_logs.py \
  --start_date 2024-05-01 \
  --end_date 2025-10-30

# 2. 쿼리 선정
python process/02.prepare_queries_and_fetch_os_results.py \
  --logs_csv data/raw/search_logs.csv

# 3. Lexical + Semantic 검색 실행
python process/03.fetch_opensearch_results.py \
  --run_only exp001 exp002

# 4. HEAD+TAIL 통합 Pooling (Depth-20)
python process/04.pool_search_results.py \
  --results_head \
    data/search_results/exp001_head_*.csv \
    data/search_results/exp002_head_*.csv \
  --results_tail \
    data/search_results/exp001_tail_*.csv \
    data/search_results/exp002_tail_*.csv \
  --methods lexical semantic \
  --depth_k 20 \
  --query_set ALL
```

---

## 왜 Balanced가 아니라 Depth-K인가요?

### ❌ 잘못된 Balanced 방식 (이전 버전)
```
목표: 총 20개 문서
- Lexical에서 10개 + Semantic에서 10개
- 중복 제거 후 부족하면 더 채움
```

**문제점:**
- Lexical 10개, Semantic 10개 → 불공평!
- 5개 방법이면? 각 4개씩? → 너무 적음!
- 중복이 많으면? → 의미 없음

### ✅ 올바른 Depth-K 방식 (현재)
```
목표: 각 방법에서 K개씩
- Lexical top-20
- Semantic top-20
- 중복 제거 → 최종 pool 크기는 자연스럽게 결정
```

**장점:**
- 각 방법이 동등하게 기여 (각 K개)
- 방법이 늘어나도 공평 (각 K개)
- 중복률이 자연스럽게 측정됨
- TREC 표준 방식 (검증됨)

---

## Depth-K 값 선택 가이드

| Depth-K | 쿼리 300개 기준 | 설명 |
|---------|----------------|------|
| **20** (권장) | 6,000개/방법 | 표준, 균형 잡힌 pool |
| 10 | 3,000개/방법 | 빠른 평가, 작은 pool |
| 50 | 15,000개/방법 | 깊은 평가, 큰 pool |
| 100 | 30,000개/방법 | 매우 깊은 평가 (labeling 부담) |

**일반적으로 K=20이 적당합니다:**
- TREC에서 오랫동안 사용
- Pool 크기와 labeling 비용의 균형
- 대부분의 관련 문서 포함

---

## 다음 단계: Relevance Labeling

Pool이 준비되면 각 문서의 관련도를 평가합니다:

```csv
query,doc_id,relevance,found_by_methods,...
맥북,doc123,2,"lexical,semantic",...  ← 매우 관련
맥북,doc456,1,lexical,...             ← 부분 관련
맥북,doc789,0,semantic,...            ← 무관
```

**Relevance Scale:**
- 2: 매우 관련 (쿼리에 정확히 답변)
- 1: 부분 관련 (일부 관련 정보)
- 0: 무관

이후 nDCG, MRR, Recall 등을 계산하여 검색 성능을 평가합니다.
