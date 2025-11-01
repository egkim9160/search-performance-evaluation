# AI 라벨링 후 DB 업로드 가이드

## 📋 워크플로우

CSV 파일에서 먼저 AI 라벨링을 수행한 후 DB에 업로드하는 방식입니다.

### 장점
- ✅ DB 업로드 전에 라벨링 완료
- ✅ 중간 CSV 파일 저장으로 재사용 가능
- ✅ 라벨링 진행 상황 추적 용이
- ✅ DB 부하 감소

---

## 🚀 사용 방법

### Step 05: CSV 파일 AI 라벨링

pooled CSV 파일을 읽어서 relevance를 평가합니다.

#### 전체 라벨링
```bash
python process/05.label_with_ai.py \
  --input_csv data/pooled_results/pooled_head_lexical_semantic_k20_20251101.csv \
  --model gpt-4o-mini
```

**출력:**
- `data/pooled_results/pooled_head_lexical_semantic_k20_20251101_labeled.csv`

#### 테스트 (10개만)
```bash
python process/05.label_with_ai.py \
  --input_csv data/pooled_results/pooled_head_lexical_semantic_k20_20251101.csv \
  --model gpt-4o-mini \
  --limit 10
```

#### 출력 파일 지정
```bash
python process/05.label_with_ai.py \
  --input_csv pooled_head.csv \
  --output_csv labeled_head.csv \
  --model gpt-4o-mini
```

#### 이미 라벨링된 문서 건너뛰기 (기본값)
```bash
python process/05.label_with_ai.py \
  --input_csv pooled_head_labeled.csv \
  --model gpt-4o-mini \
  --skip_labeled  # 기본값이므로 생략 가능
```

라벨링이 중단되어도 다시 실행하면 이어서 진행됩니다!

---

### Step 06: 라벨링된 CSV를 DB에 업로드

라벨링 완료된 CSV를 DB 인덱스에 업로드합니다.

#### 기본 업로드
```bash
python process/06.upload_to_db.py \
  --labeled_csv data/pooled_results/pooled_head_lexical_semantic_k20_20251101_labeled.csv \
  --index_name search_relevance_judgments_head_20251101
```

#### 기존 인덱스 삭제 후 업로드
```bash
python process/06.upload_to_db.py \
  --labeled_csv data/pooled_results/pooled_head_lexical_semantic_k20_20251101_labeled.csv \
  --index_name search_relevance_judgments_head_20251101 \
  --delete_existing
```

---

### Step 07: 메트릭 계산

```bash
python process/07.calculate_metrics.py \
  --index_name search_relevance_judgments_head_20251101 \
  --methods lexical semantic \
  --k_values 5 10 20 \
  --output_dir data/evaluation_results/head
```

---

### Step 08: 시각화

```bash
python process/08.visualize_results.py \
  --results_dir data/evaluation_results/head
```

---

## 📊 전체 예제 (HEAD + TAIL)

### HEAD 쿼리

```bash
# Step 05: 라벨링
python process/05.label_with_ai.py \
  --input_csv data/pooled_results/pooled_head_lexical_semantic_k20_20251101_164720.csv \
  --model gpt-4o-mini

# Step 06: 업로드
python process/06.upload_to_db.py \
  --labeled_csv data/pooled_results/pooled_head_lexical_semantic_k20_20251101_164720_labeled.csv \
  --index_name search_relevance_judgments_head_20251101 \
  --delete_existing

# Step 07: 메트릭 계산
python process/07.calculate_metrics.py \
  --index_name search_relevance_judgments_head_20251101 \
  --output_dir data/evaluation_results/head

# Step 08: 시각화
python process/08.visualize_results.py \
  --results_dir data/evaluation_results/head
```

### TAIL 쿼리

```bash
# Step 05: 라벨링
python process/05.label_with_ai.py \
  --input_csv data/pooled_results/pooled_tail_lexical_semantic_k20_20251101_164720.csv \
  --model gpt-4o-mini

# Step 06: 업로드
python process/06.upload_to_db.py \
  --labeled_csv data/pooled_results/pooled_tail_lexical_semantic_k20_20251101_164720_labeled.csv \
  --index_name search_relevance_judgments_tail_20251101 \
  --delete_existing

# Step 07: 메트릭 계산
python process/07.calculate_metrics.py \
  --index_name search_relevance_judgments_tail_20251101 \
  --output_dir data/evaluation_results/tail

# Step 08: 시각화
python process/08.visualize_results.py \
  --results_dir data/evaluation_results/tail
```

---

## 🔧 옵션 설명

### 05.label_with_ai.py

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--input_csv` | 입력 CSV 파일 (필수) | - |
| `--output_csv` | 출력 CSV 파일 | `{입력}_labeled.csv` |
| `--model` | AI 모델 | `gpt-4o-mini` |
| `--api_url` | OpenAI API URL | `None` (공식 API) |
| `--limit` | 라벨링 개수 제한 | `None` (전체) |
| `--labeled_by` | 라벨러 이름 | `AI-GPT4` |
| `--skip_labeled` | 이미 라벨링된 문서 건너뛰기 | `True` |

### 06.upload_to_db.py

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--labeled_csv` | 라벨링된 CSV 파일 (필수) | - |
| `--index_name` | DB 인덱스 이름 (필수) | - |
| `--env_file` | .env 파일 경로 | `project_root/.env` |
| `--delete_existing` | 기존 인덱스 삭제 | `False` |
| `--verbose` | 진행 상황 표시 | `True` |

---

## 💡 팁

### 1. 라벨링 중단 시 재개

라벨링 중에 중단되어도 괜찮습니다. 다시 실행하면 이미 라벨링된 문서는 건너뛰고 이어서 진행합니다.

```bash
# 처음 실행 (50개 라벨링 후 중단)
python process/05.label_with_ai.py --input_csv pooled.csv

# 다시 실행 (나머지 진행)
python process/05.label_with_ai.py --input_csv pooled_labeled.csv
```

### 2. 단계별 테스트

```bash
# 1단계: 10개만 테스트
python process/05.label_with_ai.py \
  --input_csv pooled.csv --limit 10

# 2단계: 업로드 테스트
python process/06.upload_to_db.py \
  --labeled_csv pooled_labeled.csv \
  --index_name test_index_20251101

# 3단계: 메트릭 확인
python process/07.calculate_metrics.py \
  --index_name test_index_20251101 \
  --output_dir data/test_results
```

### 3. 병렬 처리

여러 CSV 파일을 동시에 처리하려면:

```bash
# 터미널 1
python process/05.label_with_ai.py --input_csv pooled_head.csv &

# 터미널 2
python process/05.label_with_ai.py --input_csv pooled_tail.csv &
```

---

## 📝 예상 소요 시간

| 단계 | 문서 수 | 소요 시간 |
|------|---------|----------|
| Step 05 (HEAD) | 11,449 | 1-2시간 |
| Step 05 (TAIL) | 4,804 | 30분-1시간 |
| Step 06 (HEAD) | 11,449 | 2-5분 |
| Step 06 (TAIL) | 4,804 | 1-3분 |
| Step 07 | - | 1-3분 |
| Step 08 | - | 1-2분 |
| **전체** | - | **약 2-3.5시간** |

---

## 🔍 출력 예시

### Step 05 출력
```
======================================================================
Step05: AI-based Relevance Labeling (CSV)
======================================================================

[0] Initializing AI labeler...
  Model: gpt-4o-mini
  API: Official OpenAI API
  Labeled by: AI-GPT4
  ✓ Labeler initialized

[1] Loading CSV file...
  ✓ Loaded 11,449 documents
  Already labeled: 0
  To label: 11,449

[2] Starting AI labeling...
  Total to process: 11,449
  Labeling: 100%|████████████| 11449/11449 [1:45:23<00:00, 1.81it/s]

[3] Saving labeled CSV...
  ✓ Saved to: pooled_head_labeled.csv

[4] Labeling statistics:
  Processed: 11,449
  Successfully labeled: 11,396
  Failed: 53
  Total labeled in file: 11,396/11,449

  Relevance distribution:
    0 (Not relevant): 4,521 (39.7%)
    1 (Partially relevant): 4,682 (41.1%)
    2 (Very relevant): 2,193 (19.2%)
```

### Step 06 출력
```
======================================================================
Step06: Upload Labeled CSV to DB
======================================================================

[1] Connecting to DB...
  ✓ Connected to cluster: opensearch
    Version: 3.1.0

[2] Deleting existing index: search_relevance_judgments_head_20251101
  ✓ Index deleted

[3] Creating relevance judgment index...
  ✓ Index created: search_relevance_judgments_head_20251101

[4] Uploading labeled CSV...
  Loading labeled CSV: pooled_head_labeled.csv
  Total records: 11,449
  Labeled records: 11,396 (99.5%)

  Uploading 11,449 documents to DB...

  ✓ Upload completed:
    - Successfully indexed: 11,449
    - Failed: 0

[5] Index statistics:
  Total documents: 11,449
  Unique queries: 300
  Labeled documents: 11,396

  Relevance distribution:
    0 (Not relevant): 4,521 (39.7%)
    1 (Partially relevant): 4,682 (41.1%)
    2 (Very relevant): 2,193 (19.2%)
```

---

## ⚠️ 주의사항

1. **OPENAI_API_KEY 필수**
   - `.env` 파일에 설정되어 있어야 합니다.

2. **비용 발생**
   - gpt-4o-mini: 약 11,000개 문서 라벨링 시 ~$5-10 예상

3. **중간 저장**
   - 라벨링된 CSV는 백업하세요!
   - 다시 라벨링하지 않아도 됩니다.

4. **네트워크 연결**
   - OpenAI API 호출: 안정적인 인터넷 필요
   - DB 연결: VPN 등 확인

---

## 🆚 기존 방식과 비교

### 기존 방식 (DB에서 라벨링)
```
Pooling → DB 업로드 → DB에서 라벨링 → 메트릭 계산
```

**단점:**
- DB에 unlabeled 데이터 저장
- 라벨링 중단 시 복구 어려움
- DB 의존성

### 새로운 방식 (CSV에서 라벨링)
```
Pooling → CSV 라벨링 → DB 업로드 (labeled) → 메트릭 계산
```

**장점:**
- CSV로 중간 결과 저장
- 라벨링 중단 후 재개 가능
- DB에는 완성된 데이터만 저장

---

**✅ CSV 라벨링 방식을 사용하세요!**
