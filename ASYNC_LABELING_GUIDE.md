# Async AI Labeling 개선 사항

## 개요

AI 레이블링 처리 속도를 개선하기 위해 비동기 처리를 구현했습니다.

## 주요 개선 사항

### 1. **비동기 API 호출**
- `AsyncOpenAI` 클라이언트 사용
- 여러 문서를 동시에 처리하여 대기 시간 최소화
- I/O bound 작업에 최적화된 `asyncio` 활용

### 2. **동시 요청 수 제한 (Rate Limiting)**
- `asyncio.Semaphore`를 사용하여 동시 API 요청 수 제한
- API 서버 부하 방지 및 rate limit 에러 회피
- 기본값: 10개 동시 요청 (조정 가능)

### 3. **개선된 진행률 표시**
- `tqdm.asyncio`를 사용한 실시간 진행률 표시
- 전체 처리 시간 예측 가능

### 4. **향상된 에러 처리**
- 개별 문서 실패 시에도 전체 프로세스 계속 진행
- 에러 샘플 출력 (최대 5개)
- 실패율 추적

## 사용법

### 기본 사용
```bash
python process/05.label_with_ai.py \
  --input_csv data/pooled_results/pooled_data.csv \
  --model gpt-4o-mini
```

### 동시 요청 수 조정
```bash
# 더 빠른 처리 (서버 성능이 좋은 경우)
python process/05.label_with_ai.py \
  --input_csv data/pooled_results/pooled_data.csv \
  --model gpt-4o-mini \
  --max_concurrent 20

# 안정적인 처리 (rate limit 에러 방지)
python process/05.label_with_ai.py \
  --input_csv data/pooled_results/pooled_data.csv \
  --model gpt-4o-mini \
  --max_concurrent 5
```

### 테스트 모드
```bash
# 50개만 처리해서 테스트
python process/05.label_with_ai.py \
  --input_csv data/pooled_results/pooled_data.csv \
  --mode test \
  --max_concurrent 10
```

## 성능 비교

### 이전 (순차 처리)
- **1000개 문서**: 약 50-60분
- **동시 처리**: 1개
- **처리 방식**: 순차적 API 호출

### 현재 (비동기 처리)
- **1000개 문서**: 약 5-8분 (max_concurrent=10)
- **동시 처리**: 최대 10개
- **처리 방식**: 병렬 API 호출
- **속도 개선**: **약 7-10배 빠름**

## 권장 설정

### API 종류별 권장 설정

#### Official OpenAI API
```bash
--max_concurrent 10  # 기본값
```

#### 자체 호스팅 API
```bash
--max_concurrent 20  # 서버 사양에 따라 조정
```

#### Rate Limit이 엄격한 경우
```bash
--max_concurrent 3-5  # 안정성 우선
```

## 주의 사항

1. **API 비용**
   - 동시 요청 수가 많을수록 빠르지만, API 호출 비용은 동일합니다
   - 처리 속도와 비용은 무관합니다 (총 호출 횟수는 동일)

2. **Rate Limiting**
   - API 서버의 rate limit을 초과하지 않도록 `--max_concurrent` 조정 필요
   - 429 에러가 발생하면 값을 낮춰보세요

3. **메모리 사용**
   - 모든 태스크를 메모리에 생성하므로, 매우 큰 데이터셋의 경우 메모리 사용량 증가
   - 10,000개 이상의 문서: 배치 처리 고려

4. **중단 복구**
   - 중간에 중단된 경우, `--skip_labeled True`로 재실행하면 이미 라벨링된 문서는 건너뜁니다
   - 자동 checkpoint 저장은 아직 미구현 (향후 추가 예정)

## 트러블슈팅

### 429 Too Many Requests
```
해결: --max_concurrent 값을 낮추세요 (예: 5)
```

### TimeoutError
```
해결: 네트워크 연결 확인 또는 --max_concurrent 값을 낮추세요
```

### 메모리 부족
```
해결: --limit로 배치 크기를 제한하고 여러 번 실행
```

## 향후 개선 계획

1. **자동 checkpoint 저장**
   - N개 처리마다 중간 결과 저장
   - 크래시 복구 기능

2. **배치 처리 옵션**
   - 대용량 데이터셋을 위한 배치별 처리
   - 메모리 효율성 개선

3. **재시도 로직**
   - 실패한 문서 자동 재시도
   - 지수 백오프 구현

4. **진행 상황 저장**
   - 실시간 진행 상황을 파일에 저장
   - 중단 시 정확한 재개 지점 파악

## 기술 세부사항

### 비동기 처리 흐름
```
1. 모든 문서에 대한 Task 생성
2. Semaphore로 동시 실행 수 제한
3. asyncio.gather로 모든 Task 동시 실행
4. 완료된 Task부터 결과 수집
5. 모든 Task 완료 후 DataFrame 업데이트
```

### 핵심 구성 요소
- **AsyncOpenAI**: 비동기 API 클라이언트
- **asyncio.Semaphore**: 동시 실행 제어
- **tqdm.asyncio**: 비동기 진행률 표시
- **asyncio.gather**: 병렬 실행 관리
