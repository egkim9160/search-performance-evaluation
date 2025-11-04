#!/bin/bash
#
# 검색 평가 파이프라인 (라벨링 → 업로드 → 평가)
# 사용법: bash run_pipeline.sh
#

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Directories
PROJECT_ROOT="/SPO/Project/Search_model_evaluation/search-performance-evaluation"
DATA_DIR="/SPO/Project/Search_model_evaluation/251103_pipeline_verification/data"
RESULTS_DIR_DEFAULT="${DATA_DIR}/search_results"
RESULTS_DIR_FALLBACK="/SPO/Project/Search_model_evaluation/251030_logging_collection/data/search_results"
POOLED_DIR="${DATA_DIR}/pooled_results"
EVAL_DIR="./evaluation_results"  # 현재 디렉토리에 저장

mkdir -p "${POOLED_DIR}"

# Step 03: Fetch OpenSearch results
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}[Step 03] OpenSearch 결과 수집${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

CONFIG_FILE="/SPO/Project/Search_model_evaluation/search-performance-evaluation/config/single_config.json"
echo "구성 파일: $CONFIG_FILE"

python ${PROJECT_ROOT}/process/03.fetch_opensearch_results.py \
  --single_config "$CONFIG_FILE"

# Step 04: Depth-K Pooling (HEAD+TAIL 통합)
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}[Step 04] Pooling (HEAD+TAIL 통합)${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# Resolve results dir
RESULTS_DIR="$RESULTS_DIR_DEFAULT"
if [ ! -d "$RESULTS_DIR" ] || [ -z "$(ls -1 ${RESULTS_DIR}/*_head_*.csv 2>/dev/null | head -1)" ]; then
  RESULTS_DIR="$RESULTS_DIR_FALLBACK"
fi

echo "검색 결과 디렉토리: $RESULTS_DIR"

# Pick files per method (exclude *_failed.csv)
HEAD_LEX=$(ls -t ${RESULTS_DIR}/exp001_head_*.csv 2>/dev/null | grep -v '_failed\.csv' | head -1 || true)
TAIL_LEX=$(ls -t ${RESULTS_DIR}/exp001_tail_*.csv 2>/dev/null | grep -v '_failed\.csv' | head -1 || true)
HEAD_SEM=$(ls -t ${RESULTS_DIR}/exp002_head_*.csv 2>/dev/null | grep -v '_failed\.csv' | head -1 || true)
TAIL_SEM=$(ls -t ${RESULTS_DIR}/exp002_tail_*.csv 2>/dev/null | grep -v '_failed\.csv' | head -1 || true)

# Build dynamic method/file lists
METHODS=()
RESULTS_HEAD=()
RESULTS_TAIL=()
RESULTS_DUMMY=()

if [ -n "$HEAD_LEX" ] && [ -n "$TAIL_LEX" ]; then
  METHODS+=(lexical)
  RESULTS_HEAD+=("$HEAD_LEX")
  RESULTS_TAIL+=("$TAIL_LEX")
  RESULTS_DUMMY+=("$HEAD_LEX")
fi

if [ -n "$HEAD_SEM" ] && [ -n "$TAIL_SEM" ]; then
  METHODS+=(semantic)
  RESULTS_HEAD+=("$HEAD_SEM")
  RESULTS_TAIL+=("$TAIL_SEM")
  RESULTS_DUMMY+=("$HEAD_SEM")
fi

if [ ${#METHODS[@]} -eq 0 ]; then
  echo -e "${RED}✗ 사용할 수 있는 HEAD/TAIL 결과 CSV를 찾지 못했습니다.${NC}"
  echo "  확인: ${RESULTS_DIR}/exp001_*(head|tail)_*.csv, exp002_*(head|tail)_*.csv (단, *_failed.csv 제외)"
  exit 1
fi

echo "  HEAD:"
for f in "${RESULTS_HEAD[@]}"; do echo "    - $(basename "$f")"; done
echo "  TAIL:"
for f in "${RESULTS_TAIL[@]}"; do echo "    - $(basename "$f")"; done

# Call pooler (pass --results to satisfy required arg; not used when head/tail given)
python ${PROJECT_ROOT}/process/04.pool_search_results.py \
  --results "${RESULTS_DUMMY[@]}" \
  --results_head "${RESULTS_HEAD[@]}" \
  --results_tail "${RESULTS_TAIL[@]}" \
  --methods "${METHODS[@]}" \
  --depth_k 20 \
  --query_set ALL \
  --output_dir "$POOLED_DIR"

# Pooled file (ALL: head+tail 통합)
# 메서드 문자열(예: "lexical" 또는 "lexical_semantic")을 동적으로 생성
METHOD_STR=$(IFS=_; echo "${METHODS[*]}")
if [ -z "$METHOD_STR" ]; then
  METHOD_STR="lexical_semantic"
fi

POOLED_ALL=$(ls -t ${POOLED_DIR}/pooled_all_${METHOD_STR}_k20_*.csv 2>/dev/null | head -1)

# Index name (단일 인덱스에 업로드)
DATE_TAG=$(date +%Y%m%d)
INDEX_ALL="search_relevance_judgments_all_${DATE_TAG}"

# Print header
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}검색 평가 파이프라인${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# Check pooled file
echo -e "${YELLOW}[0] Pooled 파일 확인...${NC}"
echo ""

if [ -z "$POOLED_ALL" ]; then
    echo -e "${RED}✗ 통합 Pooled 파일(ALL)을 찾을 수 없습니다!${NC}"
    echo "  Step 04를 (head, tail 결과를 합쳐) 먼저 실행하세요."
    exit 1
fi

echo "  ALL: $(basename $POOLED_ALL)"
echo ""

# =============================================================================
# Step 05: AI Labeling
# =============================================================================
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}[Step 05] AI 라벨링${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# Labeling mode: full, test, skip
# Set LABELING_MODE environment variable to override (default: test)
LABELING_MODE=${LABELING_MODE:-test}

echo -e "${YELLOW}ALL(HEAD+TAIL) 라벨링 (모드: ${LABELING_MODE})...${NC}"
python ${PROJECT_ROOT}/process/05.label_with_ai.py \
    --input_csv "$POOLED_ALL" \
    --model gpt-4o-mini \
    --mode "$LABELING_MODE"

LABELED_ALL="${POOLED_ALL%.csv}_labeled.csv"

if [ ! -f "$LABELED_ALL" ]; then
    echo -e "${RED}✗ 라벨링된 CSV 파일이 없습니다!${NC}"
    echo "  Step 05 실행 중 오류가 발생했습니다."
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Step 05 완료${NC}"
echo ""
echo -e "${GREEN}라벨링된 파일:${NC}"
echo "  ALL: $(basename $LABELED_ALL)"
echo ""

# =============================================================================
# Step 06: Upload to DB
# =============================================================================
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}[Step 06] DB 업로드${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

echo -e "${YELLOW}ALL(HEAD+TAIL) 업로드...${NC}"
python ${PROJECT_ROOT}/process/06.upload_to_db.py \
    --labeled_csv "$LABELED_ALL" \
    --index_name "$INDEX_ALL" \
    --delete_existing

echo ""
echo -e "${GREEN}✓ Step 06 완료${NC}"
echo ""

# =============================================================================
# Step 07: Calculate Metrics
# =============================================================================
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}[Step 07] 평가 지표 계산${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

mkdir -p "${EVAL_DIR}/head"
mkdir -p "${EVAL_DIR}/tail"
mkdir -p "${EVAL_DIR}/all"

echo -e "${YELLOW}HEAD 쿼리 평가...${NC}"
python ${PROJECT_ROOT}/process/07.calculate_metrics.py \
    --index_name "$INDEX_ALL" \
    --methods "${METHODS[@]}" \
    --k_values 5 10 20 \
    --subset head \
    --output_dir "${EVAL_DIR}"

echo ""

echo -e "${YELLOW}TAIL 쿼리 평가...${NC}"
python ${PROJECT_ROOT}/process/07.calculate_metrics.py \
    --index_name "$INDEX_ALL" \
    --methods "${METHODS[@]}" \
    --k_values 5 10 20 \
    --subset tail \
    --output_dir "${EVAL_DIR}"

echo ""

echo -e "${YELLOW}전체 (HEAD + TAIL) 평가...${NC}"
python ${PROJECT_ROOT}/process/07.calculate_metrics.py \
    --index_name "$INDEX_ALL" \
    --methods "${METHODS[@]}" \
    --k_values 5 10 20 \
    --subset all \
    --output_dir "${EVAL_DIR}"

echo ""
echo -e "${GREEN}✓ Step 07 완료${NC}"
echo ""

# =============================================================================
# Step 08: Visualize Results
# =============================================================================
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}[Step 08] 결과 시각화${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# Visualize HEAD results
echo -e "${YELLOW}HEAD 쿼리 시각화...${NC}"
python ${PROJECT_ROOT}/process/08.visualize_results.py \
    --results_dir "${EVAL_DIR}/head" \
    --k_values 5 10 20

echo ""

# Visualize TAIL results
echo -e "${YELLOW}TAIL 쿼리 시각화...${NC}"
python ${PROJECT_ROOT}/process/08.visualize_results.py \
    --results_dir "${EVAL_DIR}/tail" \
    --k_values 5 10 20

echo ""

# Visualize ALL results
echo -e "${YELLOW}전체 (HEAD + TAIL) 시각화...${NC}"
python ${PROJECT_ROOT}/process/08.visualize_results.py \
    --results_dir "${EVAL_DIR}/all" \
    --k_values 5 10 20

echo ""
echo -e "${GREEN}✓ Step 08 완료${NC}"
echo ""

# =============================================================================
# Summary
# =============================================================================
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}파이프라인 완료!${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo -e "${GREEN}생성된 결과물:${NC}"
echo ""
echo "  📁 Labeled CSV:"
echo "     ${LABELED_ALL}"
echo ""
echo "  📁 Evaluation Results:"
echo "     ${EVAL_DIR}/head/  (HEAD 쿼리)"
echo "     ${EVAL_DIR}/tail/  (TAIL 쿼리)"
echo "     ${EVAL_DIR}/all/   (전체: HEAD + TAIL) ⭐"
echo ""
echo "  📊 주요 파일:"
echo "     - aggregated_metrics.csv (평가 지표)"
echo "     - method_comparison.png (방법 비교)"
echo "     - metrics_heatmap.png (히트맵)"
echo "     - ndcg_by_k.png (nDCG 차트)"
echo "     - EVALUATION_REPORT.md (리포트)"
echo ""
echo -e "${GREEN}다음 단계:${NC}"
echo "  1. 전체 평가 리포트 확인 (추천):"
echo "     cat ${EVAL_DIR}/all/EVALUATION_REPORT.md"
echo ""
echo "  2. HEAD/TAIL 개별 리포트:"
echo "     cat ${EVAL_DIR}/head/EVALUATION_REPORT.md"
echo "     cat ${EVAL_DIR}/tail/EVALUATION_REPORT.md"
echo ""
echo "  3. 시각화 결과 확인:"
echo "     ls -lh ${EVAL_DIR}/all/*.png"
echo ""
echo "  4. 상세 메트릭 확인:"
echo "     cat ${EVAL_DIR}/all/aggregated_metrics.csv"
echo ""
echo -e "${BLUE}======================================================================${NC}"

