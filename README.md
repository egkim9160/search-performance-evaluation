# Search Performance Evaluation

검색 모델의 성능을 평가하기 위한 데이터 추출 및 분석 프로젝트입니다.

## 프로젝트 구조

```
search-performance-evaluation/
├── module/               # 재사용 가능한 모듈
│   └── db_utils.py      # 데이터베이스 연결 유틸리티
├── process/             # 데이터 처리 스크립트
│   └── 01.fetch_search_logs.py  # 검색 로그 데이터 추출
├── data/                # 데이터 디렉토리 (gitignore)
│   └── raw/            # 원본 데이터
├── .env.example         # 환경변수 설정 예시
├── requirements.txt     # Python 패키지 의존성
└── README.md           # 프로젝트 문서
```

## 설치 및 설정

### 1. Python 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

`.env.example` 파일을 `.env`로 복사하고 데이터베이스 접속 정보를 입력합니다:

```bash
cp .env.example .env
```

`.env` 파일 편집:
```
DB_HOST=your_database_host
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_NAME=medigate
```

## 사용법

### 검색 로그 데이터 추출

MUZZIMA 카테고리의 2024년 이후 검색 로그를 추출합니다:

```bash
python process/01.fetch_search_logs.py
```

옵션:
- `--out_dir`: 출력 디렉토리 지정 (기본값: `data/raw`)
- `--output_file`: 출력 파일명 지정 (기본값: `search_logs.csv`)
- `--min_freq`: 시각화에 포함할 최소 빈도 (기본값: `5`)
- `--max_queries`: 시각화할 최대 쿼리 개수 (기본값: `5000`)
- `--no_plot`: 시각화 생성 건너뛰기

예시:
```bash
# 기본 실행 (상위 5000개 쿼리, cnt >= 5)
python process/01.fetch_search_logs.py

# 상위 10000개 쿼리, 최소 빈도 10
python process/01.fetch_search_logs.py --max_queries 10000 --min_freq 10

# 시각화 없이 데이터만 추출
python process/01.fetch_search_logs.py --no_plot
```

**출력 파일:**
- `data/raw/search_logs.csv`: 검색 로그 데이터 (모든 검색어)
- `data/raw/frequency_distribution.png`: 검색 빈도 분포 시각화
  - 상위 쿼리들의 빈도를 가로축(순위), 세로축(빈도, 로그 스케일)로 표시
  - Head-Tail 패턴을 명확하게 보여주는 단일 플롯
  - 최댓값(Max)을 floating annotation으로 표시

## 데이터베이스 스키마

### SE_LOG 테이블
- `WORD`: 검색어
- `SUB_CATEGORY_CODE`: 서브 카테고리 코드 (예: 'MUZZIMA')
- `LOG_DATE`: 로그 일자
- `cnt`: 검색 횟수 (집계)

## 개발 참고

- 데이터베이스 연결 로직은 `/SPO/Project/RecSys/RecmdSys/module/db_utils.py`를 참고했습니다
- 쿼리 실행 패턴은 `/SPO/Project/RecSys/RecmdSys/process/01.parse_raw_dataset.py`를 참고했습니다
