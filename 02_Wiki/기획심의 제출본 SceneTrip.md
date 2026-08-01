---
title: 기획심의 제출본 SceneTrip
summary: 06-19 제출본. 12쪽. 프로젝트명은 「(SceneTrip) K-콘텐츠 속 그 장면, 그 장소를 실제 촬영지와 맞춤형 여행 코스로 연결하는 외국인 대상 팬덤 여행 앱」.
type: artifact
status: draft
date: 2026-06-19
act: 2
mentor:
  - 정문창
  - 김상규
  - 방한민
topic:
  - 기획서
  - MVP범위
adopted: yes
source:
  - "[[01_Raw/Project/01_기획심의 준비/최종_mz2az]]"
  - "[[01_Raw/Project/01_기획심의 준비/기획서초안_태환]]"
  - "[[01_Raw/Project/01_기획심의 준비/기획서초안__]]"
related:
  - K-Loca 브라우저 확장 컨셉
  - 기획 발표 후 심사위원 지적 8건
  - 비주얼 맵이라는 워딩
---

> [!summary] 06-19 제출본. 12쪽. 프로젝트명은 「(SceneTrip) K-콘텐츠 속 그 장면, 그 장소를 실제 촬영지와 맞춤형 여행 코스로 연결하는 외국인 대상 팬덤 여행 앱」.

### 상세 내용

**초안 계보** — `기획서초안__` → `기획서초안_태환`(둘 다 (Scene Trip) K-콘텐츠 성지순례 정보제공 및 코스 추천 서비스, React+FastAPI 웹앱 컨셉) 과 별개로 `기획서초안_승길`([[K-Loca 브라우저 확장 컨셉]])이 있었고, 이 둘이 합쳐져 최종본이 됐다. 태환 초안의 팀 구성표에 정승길 역할이 "Chrome Extension UI"로 적혀 있는 것이 병합 중이던 흔적이다.

**최종 제출본의 뼈대**

| 항목 | 내용 |
| --- | --- |
| 기술 키워드 | LLM/RAG, Geospatial Search, Location-aware LLM Agent, Context-aware Recommendation, POI Recommendation, Itinerary Planning, LLM-based Information Extraction, Geocoding, PostGIS, Map/Route API, Human-in-the-loop Data Validation |
| 분류 | ①인공지능 - ②신뢰·산업 AI |
| 주요 기능 | ① 콘텐츠별 성지 정보 제공 ② AI기반 여행 일정 추천 ③ 루트공유 및 커뮤니티 |
| 시장 규모 | TAM 1,637만 / SAM 331만 / SOM 100만 |
| 역할 | 정승길 프론트, 정권호 백엔드·DB, 김태환 데이터·RAG·Agent |
| 멘토 | 정문창(기획·BM), 김상규(AI), 방한민(인프라) |

**AI 활용 전략 3종** — 성지 데이터 자동 구축 파이프라인(수집→LLM 정제→검증 Agent→성지 DB, 3회 실패 시 관리자 검수 큐), 여행 일정 자동 생성(여행 前), 위치 기반 실시간 성지 추천(여행 中).

**MVP 범위 제한** — "MVP는 촬영지 검색, 지도 기반 정보 제공, AI 여행 코스 추천, 루트 공유 및 방문 인증 기능으로 제한. 광고, 결제, 고도화된 개인화 추천 등은 후속 확장 기능으로 분리. **서울, 부산, 경주로 지역범위 제한.**" 이 마지막 문장만 원본에서 빨간 글씨로 강조돼 있다.

> [!question] 원본에 남은 오류
> ① 본문의 "2024년 1,673만 명"이 인포그래픽·TAM의 1,637만 명과 어긋난다. ② 추진 일정표의 기획 행이 6·8·10월로 한 달씩 건너뛰어 p1 서술과 맞지 않는다. 둘 다 원본 그대로 전사본에 남겨 두었다.
