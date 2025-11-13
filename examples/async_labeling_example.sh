#!/bin/bash
# Async AI Labeling 사용 예시

# 필요한 환경 변수 확인
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY not set"
    echo "Please set it in .env file or export it:"
    echo "  export OPENAI_API_KEY='your-key-here'"
    exit 1
fi

echo "==================================================================="
echo "Async AI Labeling Examples"
echo "==================================================================="

# Example 1: 테스트 모드 (50개만 처리)
echo -e "\n[Example 1] Test mode - 50 documents with 10 concurrent requests"
echo "Command:"
echo "  python process/05.label_with_ai.py \\"
echo "    --input_csv data/pooled_results/pooled_data.csv \\"
echo "    --mode test \\"
echo "    --max_concurrent 10"
echo ""

# Example 2: 빠른 처리 (20개 동시 요청)
echo -e "\n[Example 2] Fast processing - 20 concurrent requests"
echo "Command:"
echo "  python process/05.label_with_ai.py \\"
echo "    --input_csv data/pooled_results/pooled_data.csv \\"
echo "    --model gpt-4o-mini \\"
echo "    --max_concurrent 20"
echo ""

# Example 3: 안정적 처리 (5개 동시 요청)
echo -e "\n[Example 3] Stable processing - 5 concurrent requests (avoid rate limits)"
echo "Command:"
echo "  python process/05.label_with_ai.py \\"
echo "    --input_csv data/pooled_results/pooled_data.csv \\"
echo "    --model gpt-4o-mini \\"
echo "    --max_concurrent 5"
echo ""

# Example 4: 이미 라벨링된 문서 건너뛰기
echo -e "\n[Example 4] Resume - skip already labeled documents"
echo "Command:"
echo "  python process/05.label_with_ai.py \\"
echo "    --input_csv data/pooled_results/pooled_data.csv \\"
echo "    --output_csv data/pooled_results/pooled_data_labeled.csv \\"
echo "    --skip_labeled \\"
echo "    --max_concurrent 10"
echo ""

# Example 5: 커스텀 API URL 사용
echo -e "\n[Example 5] Custom API endpoint"
echo "Command:"
echo "  python process/05.label_with_ai.py \\"
echo "    --input_csv data/pooled_results/pooled_data.csv \\"
echo "    --api_url https://your-api-endpoint.com/v1 \\"
echo "    --model gpt-4o-mini \\"
echo "    --max_concurrent 15"
echo ""

# Example 6: 전체 데이터셋 처리
echo -e "\n[Example 6] Full dataset processing"
echo "Command:"
echo "  python process/05.label_with_ai.py \\"
echo "    --input_csv data/pooled_results/pooled_data.csv \\"
echo "    --mode full \\"
echo "    --max_concurrent 10"
echo ""

echo "==================================================================="
echo "Performance Tips:"
echo "==================================================================="
echo "1. Start with --mode test to verify configuration"
echo "2. Adjust --max_concurrent based on API rate limits:"
echo "   - Official OpenAI: 10 (default)"
echo "   - Self-hosted: 20+ (depending on server)"
echo "   - Rate limited: 3-5"
echo "3. Use --skip_labeled to resume interrupted processing"
echo "4. Monitor for 429 errors - reduce --max_concurrent if they occur"
echo ""
echo "Expected Performance (1000 documents):"
echo "  - Sequential (old): 50-60 minutes"
echo "  - Async (new):      5-8 minutes (10 concurrent)"
echo "  - Speedup:          7-10x faster"
echo "==================================================================="
