---
source: "[[목업_초안_아키텍처_연결도_김태환.html]]"
source_path: 01_Raw/Project/목업/아키텍처_연결도_김태환.html
author: 김태환
date_est: 2026-07-28
type: raw-transcription
method: html-extraction
visual_review: complete
visual_review_date: 2026-07-29
---

> [!info] 전사 방식
> 이 html에는 **이미지가 하나도 없다.** 구조도 전체가 CSS 박스와 텍스트로 그려져 있어 DOM 텍스트만으로 손실 없이 옮길 수 있다.
> 부제: *"지도와 RAG가 각 계층에서 어떻게 쓰이는지 — 전체 구조도 + 실제 데이터 흐름 3가지"*

# Frontend · Backend · AI 는 이렇게 연결됩니다

## 1. 전체 구조도 (Layered Architecture)

### FRONTEND · Flutter 앱 (iOS/Android/Web)

| 블록 | 설명 |
| --- | --- |
| 지도 화면 | 성지 핀·내 위치·경로 동선 렌더링, 지도 SDK |
| 작품검색 | 작품·성지 리스트, 상세 |
| AI 가이드 챗봇 | 위치 기반 실시간 대화 UI |
| 경로여정 · 커뮤니티 | 경로마켓·여정만들기·팬포럼 |

↓ `REST / HTTPS (JSON)` · `위치 스트림 · 인증 토큰`

### BACKEND · SpringBoot (비즈니스 로직 · 신뢰 경계)

| 블록 | 설명 |
| --- | --- |
| API Gateway · 인증 | 요청 검증·라우팅, 유저 세션 |
| **Entitlement (권한)** | 패스/구매 경로 보유 여부 판정 → **차등 RAG의 기준** |
| 결제 · 패스 관리 | 경로 건당구매·패스권 결제 |
| CRUD 서비스 | 유저·경로·커뮤니티·후기 |

↓ `내부 API (REST/gRPC)` · `요청 + 권한 컨텍스트(tier, 허용 work/route id)`

### AI SERVICE · Python / LangChain (김태환 담당 영역)

| 블록 | 설명 |
| --- | --- |
| Location-aware Agent | 도구 호출: `search_spots` · `get_route` · `rag_lookup` · `recommend_nearby` |
| RAG Engine | 권한 필터 + 벡터 검색 + 근거(citation) 생성 |
| 추천 · 경로 엔진 | POI 추천 · Itinerary Planning |
| 수집·추출 파이프라인 | (배치) 성지 DB 자동 구축 |

↓ `SQL · 지리쿼리 · 벡터검색`

### DATA

| 블록 | 설명 |
| --- | --- |
| PostgreSQL + PostGIS | 성지·좌표·경로 — 반경/근접 지리 검색 |
| pgvector | 성지·씬·후기 임베딩 — RAG 시맨틱 검색 |
| 원문·출처 저장소 | 수집 원본·URL (근거 추적) |

↓ `외부 API 호출`

### EXTERNAL SERVICES

| 블록 | 설명 |
| --- | --- |
| Map / Route API | 지도 타일·도보/대중교통 경로 (Agent가 길안내에 호출) |
| Geocoding API | 주소→좌표 (수집 파이프라인) |
| LLM Providers | Claude · Gemini · QWen (추출·응답·요약) |
| 콘텐츠 소스 | YouTube · 블로그 · SNS (수집 대상) |

---

## 2. 실제 데이터 흐름 (핵심 시나리오 3)

### Flow 1 · 촬영지 검색 → 지도에 성지 핀 표시  〈지도 사용〉

> 사용자가 작품을 고르면 실제 촬영 성지가 지도 위 핀으로 뜨는 흐름.

| STEP | 주체 | 내용 |
| --- | --- | --- |
| 1 | Frontend | 작품 선택 + **내 위치(GPS)** 와 함께 요청 전송 |
| 2 | Backend | 인증 확인 후 성지 조회 요청 중계 |
| 3 | PostGIS | **지리 쿼리** 로 해당 작품 성지 + 좌표 반환 |
| 4 | Frontend | 받은 좌표를 **지도 SDK** 로 핀·내 위치 렌더링 |

> 지도는 **Frontend가 그리고**, 핀 좌표 데이터는 **PostGIS의 성지 DB** 에서 옵니다. AI는 이 단계에 관여하지 않음(빠른 조회).

### Flow 2 · 실시간 AI 가이드 질문 — "여기 어떻게 가요?"  〈RAG + 권한 + 지도〉

> RAG와 지도(Route API), 그리고 구매 권한(Entitlement)이 한 번에 맞물리는 핵심 흐름.

| STEP | 주체 | 내용 |
| --- | --- | --- |
| 1 | Frontend | 질문 + **현재 위치·활성 경로** 전송 |
| 2 | Backend | **Entitlement 판정** — tier·허용 work/route id를 붙여 AI에 전달 |
| 3 | AI | **Agent** 의도 파악 → 필요한 **도구 호출** 결정 |
| 4 | AI | **RAG** — **권한 필터** 로 허용 청크만 벡터 검색 → 근거 확보 |
| 5 | Route API | `get_route` 로 도보/대중교통 실측 동선 계산 |
| 6 | Frontend | 근거 포함 답변 + 지도 핀/동선 갱신 |

> 같은 질문이라도 **무료 유저** 는 요약형 답변+구매 유도, **해당 경로 구매/패스** 유저는 상세 씬·팁까지 — 차이는 STEP 4의 **RAG 검색 범위(권한 필터)** 에서 갈립니다.

### Flow 3 · 성지 데이터 자동 구축 (배치 · 서비스 이전 준비)  〈배치 파이프라인〉

> 앱 요청과 무관하게 오프라인에서 성지 DB와 RAG 인덱스를 미리 채워두는 흐름.

| STEP | 주체 | 내용 |
| --- | --- | --- |
| 1 | 콘텐츠 소스 | YouTube 자막·블로그·기사 **수집** (출처 URL 보관) |
| 2 | AI | **추출** — LLM으로 작품·씬·장소·주소 구조화 추출 |
| 3 | Geocoding | 주소 → **좌표** 변환, 중복 병합 |
| 4 | AI | **HITL** — 저신뢰 건 **사람 검수** 후 승인 |
| 5 | Data | **PostGIS 적재** + 임베딩 → **pgvector 인덱싱** |

> 이 배치가 **Flow 1의 지도 핀** 과 **Flow 2의 RAG 근거** 의 원천 데이터를 만듭니다. 실시간 흐름(1·2)과 분리해 앱 응답 지연을 없앰.

---

## 3. 지도와 RAG는 정확히 어디에 쓰이나

**지도(Map)는 4곳에서 쓰인다** (문서 소제목은 "3곳"이나 항목은 4개다 — 원문 그대로)

1. **Frontend 렌더링** — 지도 SDK로 성지 핀·내 위치·경로 동선 표시 (Flow 1·2)
2. **PostGIS 지리 검색** — "내 반경 N km 성지", 근접 정렬 등 위치 쿼리 (Data 계층)
3. **Route API 길안내** — AI Agent가 도보/대중교통 실측 동선 계산에 호출 (Flow 2)
4. **Geocoding** — 수집 파이프라인에서 주소를 좌표로 변환 (Flow 3)

**RAG는 이렇게 쓰인다**

1. **근거 기반 응답** — AI 가이드가 성지 DB·검증 후기를 검색해 환각 없이 답변 (Flow 2)
2. **권한 필터 검색** — Backend가 준 tier로 **허용된 work/route 청크만** 검색 → 차등 서비스
3. **인용(citation) 반환** — 답변에 출처를 붙여 목업의 "검증 데이터 기반" 카드 구현
4. **작품 요약·추천 근거** — 작품 상세·추천 이유 생성에도 활용

> **한 줄 정리** — Frontend는 **보여주고(지도·챗봇)**, Backend는 **지키고(인증·결제·권한)**, AI Service는 **생각합니다(RAG·Agent·추출)**. 지도는 표현+지리검색+길안내에, RAG는 AI 응답의 근거와 권한별 차등에 쓰입니다.

> [!question] 확인 필요 — 원문 수치 불일치
> "지도(Map)는 **3곳** 에서 쓰입니다" 라고 써 놓고 항목은 **4개** 를 나열했다. 원본 그대로 두었다.
