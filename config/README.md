# 검색 설정 (단일 JSON 전용)

## 개요
- 이제 분리형 설정(index_config.json, query_config.json, search_experiments.json)을 사용하지 않습니다.
- 오직 하나의 JSON 파일에 환경(.env 경로), 쿼리 파일 경로, 출력 디렉토리, 그리고 실행할 실험(experiments)을 함께 정의합니다.

## JSON 스키마
```json
{
  "env_file": "/abs/path/to/.env",
  "output_dir": "/abs/path/to/data/search_results",
  "query_files": {
    "head": "/abs/path/to/queries_head_300.csv",
    "tail": "/abs/path/to/queries_longtail_200.csv"
  },
  "experiments": [
    {
      "id": "exp001",
      "name": "muzzima_lexical",
      "description": "MUZZIMA - lexical match",
      "index_name": "community-with-meta_classify-20250716",
      "query_method": {
        "id": "lexical",
        "search_type": "lexical",
        "query_structure": { "type": "match", "operator": "and" }
      }
    },
    {
      "id": "exp002",
      "name": "muzzima_semantic",
      "description": "MUZZIMA - semantic match",
      "index_name": "community-with-meta_classify-20250716",
      "query_method": {
        "id": "semantic",
        "search_type": "semantic",
        "query_structure": { "type": "knn", "k": 20 },
        "embedding_model": "text-embedding-3-large",
        "embedding_api_url": "https://api.openai.com/v1"
      }
    }
  ],
  "execution": {
    "continue_on_error": true
  }
}
```

### 필드 설명
- env_file: OpenSearch 및(OpenAI 등) 인증 값을 읽어올 .env 경로
- output_dir: 검색 결과 CSV 출력 디렉토리
- query_files.head / tail: HEAD/TAIL 쿼리 CSV 경로
- experiments: 실행할 실험 목록
  - index_name: 실제 OpenSearch 인덱스명
  - query_method:
    - lexical 예시: { type: "match" }
    - semantic 예시: { type: "knn" } + embedding_model, embedding_api_url 필수

## 실행 방법
```bash
python process/03.fetch_opensearch_results.py \
  --single_config /SPO/Project/Search_model_evaluation/search-performance-evaluation/config/single_config.json
```

## 기본 매핑(내장 기본값)
- 필드 매핑은 다음과 같은 기본값을 사용합니다(필요 시 코드에서 확장 가능):
  - content: merged_comment
  - board_name: BOARD_NAME
  - keywords: keywords
  - embedding_field: vector_field
- _source에 포함되는 기본 필드:
  - BOARD_IDX, TITLE, BOARD_NAME, CONTENT, merged_comment,
    view_cnt, comment_cnt, agree_cnt, disagree_cnt, REG_DATE, U_ID, keywords
