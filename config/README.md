# 검색 설정 파일 구조

## 파일 구성

### 1. `index_config.json`
**인덱스별 설정**을 정의하는 파일입니다. 각 인덱스의 이름, 필드 매핑, 반환할 소스 필드 등을 지정합니다.

**구조:**
```json
{
  "indexes": {
    "인덱스_ID": {
      "name": "실제 OpenSearch 인덱스명",
      "description": "설명",
      "fields": {
        "content": "merged_comment",
        "keywords": "keywords",
        ...
      },
      "source_fields": ["field1", "field2", ...],
      "embedding_field": "embedding",  // optional
      "embedding_dimension": 768       // optional
    }
  }
}
```

**예시:**
- `baseline`: 기존 인덱스
- `semantic_v1`: Semantic 검색용 인덱스
- `new_dict_v1`: 신규 사전 적용 인덱스

---

### 2. `query_config.json`
**쿼리 방법**을 정의하는 파일입니다. 다양한 검색 방법(lexical, semantic, hybrid)과 쿼리 구조를 지정합니다.

**구조:**
```json
{
  "query_methods": {
    "쿼리방법_ID": {
      "name": "이름",
      "description": "설명",
      "search_type": "lexical | semantic | hybrid",
      "query_structure": {
        "type": "match | multi_match | bool | knn | hybrid",
        ...
      },
      "requires_embedding": true/false
    }
  }
}
```

**예시:**
- `lexical_match`: 기본 match 쿼리
- `lexical_multifield`: Multi-field 검색
- `semantic_knn`: kNN Semantic 검색
- `hybrid_lexical_semantic`: Hybrid 검색

---

### 3. `search_experiments.json`
**실험 조합**을 정의하는 메인 설정 파일입니다. 어떤 인덱스에 어떤 쿼리 방법을 사용할지 조합을 지정합니다.

**구조:**
```json
{
  "env_file": ".env 파일 경로",
  "query_files": {
    "head": "HEAD 쿼리 CSV 경로",
    "tail": "TAIL 쿼리 CSV 경로"
  },
  "output_dir": "결과 저장 디렉토리",
  "experiments": [
    {
      "id": "exp001",
      "name": "실험명",
      "description": "설명",
      "index_id": "index_config.json의 인덱스 ID",
      "query_method_id": "query_config.json의 쿼리방법 ID",
      "enabled": true/false
    }
  ]
}
```

---

## 설정 파일 수정 방법

### 1. 새로운 인덱스 추가

`index_config.json`에 새 인덱스 추가:

```json
{
  "indexes": {
    "my_new_index": {
      "name": "actual-opensearch-index-name",
      "description": "내 새로운 인덱스",
      "fields": {
        "content": "text_field",
        "keywords": "keyword_field"
      },
      "source_fields": ["text_field", "keyword_field"]
    }
  }
}
```

### 2. 새로운 쿼리 방법 추가

`query_config.json`에 새 쿼리 방법 추가:

```json
{
  "query_methods": {
    "my_custom_query": {
      "name": "my_custom_query",
      "description": "내가 만든 쿼리",
      "search_type": "lexical",
      "query_structure": {
        "type": "match",
        "operator": "or"
      }
    }
  }
}
```

### 3. 실험 조합 추가

`search_experiments.json`에 새 실험 추가:

```json
{
  "experiments": [
    {
      "id": "exp011",
      "name": "my_experiment",
      "description": "새로운 실험",
      "index_id": "my_new_index",
      "query_method_id": "my_custom_query",
      "enabled": true
    }
  ]
}
```

---

## 사용 예시

### 모든 활성화된 실험 실행
```bash
python process/03.fetch_opensearch_results.py
```

### 특정 실험만 실행
```bash
python process/03.fetch_opensearch_results.py --run_only exp001 exp002
```

### HEAD 쿼리만 처리
```bash
python process/03.fetch_opensearch_results.py --query_sets head
```

### Top-K 개수 변경
```bash
python process/03.fetch_opensearch_results.py --top_k 50
```

---

## 설정 파일 간의 관계

```
search_experiments.json
  ├─ index_id → index_config.json의 indexes[index_id]
  └─ query_method_id → query_config.json의 query_methods[query_method_id]
```

**실험 실행 시:**
1. `search_experiments.json`에서 실험 목록 로드
2. 각 실험의 `index_id`로 `index_config.json`에서 인덱스 정보 조회
3. 각 실험의 `query_method_id`로 `query_config.json`에서 쿼리 방법 조회
4. 인덱스와 쿼리 방법을 조합하여 OpenSearch 쿼리 실행

---

## 주의사항

1. **인덱스명 확인**: `index_config.json`의 `name` 필드에는 실제 OpenSearch 인덱스명을 정확히 입력해야 합니다.

2. **필드명 매핑**: `fields` 섹션에서 논리적 이름(content, keywords 등)을 실제 인덱스 필드명으로 매핑합니다.

3. **Embedding 관련**: `requires_embedding: true`인 쿼리 방법은 현재 구현되지 않았습니다. 사용하려면 embedding 생성 로직을 추가해야 합니다.

4. **enabled 플래그**: `search_experiments.json`의 각 실험에서 `enabled: false`로 설정하면 해당 실험은 건너뜁니다.

5. **실험 ID**: 각 실험의 `id`는 고유해야 하며, 결과 파일명에 사용됩니다.
