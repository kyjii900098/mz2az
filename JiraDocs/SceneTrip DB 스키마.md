---
title: "SceneTrip DB 스키마"
type: design
status: draft
updated: 2026-07-29
source: ["[[MZ2AZ-111 촬영지 데이터 수집용 스키마]]", "[[SceneTrip 아키텍처 — 기능·API·데이터 전략]]", "[[촬영지 수집 스키마 15컬럼]]"]
related: ["[[프로젝트 결정사항]]", "[[MVP1 데이터 모델 (7·24 화이트보드)]]", "[[데이터 3계층 전략]]"]
---

> [!summary] SceneTrip **1계층(우리 자산 = 직접 수집한 촬영지)** 의 DB 스키마 설계안.
> 수집용 15컬럼 플랫 CSV를 정규화한 구조. 테이블 13개 + 머티리얼라이즈드 뷰 1개.

- 작성: 2026-07-29 (정권호)
- 범위: [[데이터 3계층 전략]] 의 **1계층만.** 2계층(TourAPI·공공데이터)·3계층(Google Places 라이브)은 별도
- 수집 템플릿: [[MZ2AZ-111 촬영지 데이터 수집용 스키마]] — 사람이 채우는 15컬럼 포맷
- 이 문서: 그 CSV가 **적재될 DB 구조**

---

## 0. 현재 수집 데이터 현황 (2026-07-29 기준)

| 파일 | 행수 | 컬럼 | 성격 |
|---|---|---|---|
| `kdramamap_drama_촬영지_2026-07-29.csv` | **20,080** | 15 | 드라마 촬영지 전수 |
| `kdramamap_상위100_성지_2026-07-29.csv` | **5,740** | 18 | 상위 100작 큐레이션 (+`work_rank`, `scene_source`, `scene_source_url`) |
| `kdramamap_작품마스터_2026-07-29.csv` | **477** | 28 | **작품 마스터** (인기도·위키데이터 포함) |
| `촬영지_수집_영화전수.csv` | 6,944 | 16 (+`audience_acc`) | 영화 |
| `촬영지_수집_2026-07-28.csv` | 7,443 | 15 | 통합본 |
| `한국문화정보원_…_20221125.csv` | 15,034 | 14 | 공공데이터 (**cp949 인코딩**) |
| `드라마_해외인기_TOP100.csv` | 100 | 6 | 해외 인기 순위 |

**드라마 촬영지 20,080행 분석:**

- 고유 작품 **476** / 고유 장소명 **14,290**
- **작품 2개 이상이 걸린 장소 2,047개** (조이마당스튜디오 89작, 서강대교 70작, 양주한국병원 58작)
- `title_aliases` 96.8% 채움, **`;` 구분**, 이미 다국어:
  `1%의 어떤 것;1% of Anything;1%の奇跡;1%的可能性;1%ui Eoddungut`
- 좌표 97.0% / `place_naver_url` 100% / `place_image_url` **14.2%**
- `place_type` 중 **`기타` 가 10,273건(51.2%)**

이 수치가 스키마 설계의 근거다. 특히 **2,047개 장소가 여러 작품에 걸려 있다** 는 것이 플랫 테이블을 못 쓰는 결정적 이유다.

---

## 1. 왜 정규화하는가

수집 CSV 한 행은 "장소"가 아니라 **작품 × 장소** 다. 서강대교는 70개 작품에 걸려 있으므로 CSV에 **70행** 이 있고, 그때마다 `title`, `title_aliases`, `title_cast` 가 통째로 반복된다.

```
서강대교 | 작품A | 배우들… | 37.54, 126.93 | 마포구 …
서강대교 | 작품B | 배우들… | 37.54, 126.93 | 마포구 …
…70행
```

- 좌표·주소를 고치려면 **70군데** 를 다 고쳐야 한다 (하나 빠지면 지도에 핀이 두 개 찍힌다)
- 작품 제목 오타를 고치려면 그 작품이 걸린 장소 수만큼 고쳐야 한다
- "아이유가 나온 작품"을 찾으려면 `title_cast` 문자열 안을 뒤져야 해 인덱스를 못 탄다

요구 구조는 **장소 하나에 여러 작품** + **작품 하나에 여러 장소** 인 N:M 관계이고, 연결 테이블 없이는 표현할 수 없다.

---

## 2. 전체 구조

```
                    ┌─ place_i18n (언어별 이름·주소)
                    │
        place ──────┼─ place_alias (별칭)
          │         │
          │    popularity_score
          │
    place_content ──── place_content_i18n (언어별 관계 설명)
          │
        content ─────┬─ content_i18n (언어별 제목)
          │          └─ content_alias (별칭)
          │
     content_cast
          │
        person ────── person_i18n (언어별 이름)


    search_term  (MV: 위 이름·별칭 전부 펼친 자동완성 색인)
    user_event   (MVP2: 행동 로그)
```

| 분류 | 테이블 |
|---|---|
| **실체(entity)** | `place`, `content`, `person` |
| **연결(junction)** | `place_content`, `content_cast` |
| **번역(i18n)** | `place_i18n`, `content_i18n`, `person_i18n`, `place_content_i18n` |
| **별칭** | `place_alias`, `content_alias` |
| **검색** | `search_term` (MATERIALIZED VIEW) |
| **로그** | `user_event` (MVP2) |

---

## 3. 테이블 정의

### 3.1 `place` — 장소

| 컬럼 | 타입 | 출처 / 설명 |
|---|---|---|
| `id` | BIGSERIAL **PK** | auto increment |
| `category` | TEXT | `place_type` → **코드값** (§8 참조) |
| `geom` | GEOGRAPHY(Point,4326) | `place_latitude` + `place_longitude` |
| `coordinate_status` | TEXT | `geocoded` / `manual` / `missing` (좌표 97%) |
| `naver_map_url` | TEXT NULL | `place_naver_url` (100% 채움) |
| `image_url` | TEXT NULL | `place_image_url` (**14.2%만 채움**) |
| `kakao_place_id` | TEXT NULL | 참고용. **UNIQUE 아님, 필수 아님** (§7) |
| `popularity_score` | NUMERIC DEFAULT 0 | 지도 핀 우선순위. 배치 계산 |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

`category` 를 한글이 아니라 코드로 두는 이유 — 종류가 수십 개뿐이라 행마다 번역할 게 아니라 앱 언어 사전에서 한 번만 번역하면 된다.

### 3.2 `place_i18n` — 장소 (언어별)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `place_id` | BIGINT FK → place | **PK** (복합) |
| `lang` | TEXT | `ko` / `en` / `ja` / `zh-Hant` **PK** (복합) |
| `name` | TEXT | `place_name` |
| `address` | TEXT | `place_address` |
| `trans_status` | TEXT | `machine` / `reviewed` / `human` |

### 3.3 `place_alias` — 장소 별칭

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | BIGSERIAL **PK** | |
| `place_id` | BIGINT FK → place | |
| `alias` | TEXT | 통용명 / 옛이름 / 로마자 |
| `alias_type` | TEXT | `common` / `former` / `romanized` |
| `lang` | TEXT NULL | 로마자는 언어 무관 → NULL |

장소당 **0~3개. 대부분 0개가 정상.**

### 3.4 `content` — 작품

`작품마스터` CSV(477행·28컬럼)가 거의 그대로 대응된다.

| 컬럼 | 타입 | 출처 / 설명 |
|---|---|---|
| `id` | BIGSERIAL **PK** | **우리 PK** |
| `type` | TEXT | `title_category` — `drama`/`movie`/`variety`/`kpop` |
| `broadcaster` | TEXT NULL | 방송사 |
| `air_period` | TEXT NULL | 방영 기간 |
| `air_status` | TEXT NULL | 방영 상태 |
| `poster_url` | TEXT NULL | |
| `kdramamap_url` | TEXT NULL | 수집 출처 |
| **`wikidata_qid`** | TEXT NULL | **다국어 제목 자동 확보 키** (§6) |
| `wiki_lang_count` | INT NULL | 위키 언어 수 |
| `en_wiki_title` | TEXT NULL | |
| `en_views_12m` | INT NULL | 영문 위키 12개월 조회수 |
| `score_global` / `score_interest` / `score_data` | NUMERIC NULL | 인기도 구성 점수 |
| **`score_total`** | NUMERIC NULL | **인기도 종합 (기수집)** |
| `rank` | INT NULL | 순위 |
| `is_top100` | BOOLEAN | 상위 100작 여부 |
| `audience_acc` | BIGINT NULL | 영화 누적 관객수 |
| `is_featured` | BOOLEAN DEFAULT false | 운영자 수동 상단 고정 |
| `popularity_score` | NUMERIC DEFAULT 0 | **최종 정렬값** (§5) |
| `tmdb_id` | INT NULL | 선택. PK 아님 |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

`tmdb_id` 를 PK로 쓰지 않는다 — TMDB에 없는 작품(K-POP·예능)은 등록 자체가 불가능해진다. `wikidata_qid` 도 마찬가지로 참조용이다.

### 3.5 `content_i18n` — 작품 (언어별)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `content_id` | BIGINT FK → content | **PK** (복합) |
| `lang` | TEXT | **PK** (복합) |
| `title` | TEXT | `title` / `title_official` / `title_en` |
| `description` | TEXT NULL | 작품 소개 |
| `trans_status` | TEXT | |

### 3.6 `content_alias` — 작품 별칭

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | BIGSERIAL **PK** | |
| `content_id` | BIGINT FK → content | |
| `alias` | TEXT | `title_aliases` 를 **`;` 로 분리** |
| `alias_type` | TEXT | `abbrev` / `official` / `subtitle` / `romanized` |
| `lang` | TEXT NULL | 로마자·미상은 NULL |

> [!important] `title_aliases` 는 이미 다국어다.
> `1%의 어떤 것;1% of Anything;1%の奇跡;1%的可能性;1%ui Eoddungut`
> 적재 시 **언어를 자동 판별해 `lang` 을 채운다** — 한글/라틴/가나/한자/로마자 표기를 문자 범위로 구분. 그러면 `content_i18n` 의 다국어 제목도 상당 부분 여기서 파생 가능하다.

### 3.7 `person` — 인물

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | BIGSERIAL **PK** | |
| `tmdb_person_id` | INT NULL | 선택 |
| `created_at` | TIMESTAMPTZ | |

### 3.8 `person_i18n` — 인물 (언어별)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `person_id` | BIGINT FK → person | **PK** (복합) |
| `lang` | TEXT | **PK** (복합) |
| `name` | TEXT | 아이유 / IU / アイユー |

### 3.9 `content_cast` — 작품 × 인물 **(연결)**

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `content_id` | BIGINT FK → content | **PK** (복합) |
| `person_id` | BIGINT FK → person | **PK** (복합) |
| `role_name` | TEXT NULL | 배역명 (MVP1은 한국어만) |
| `is_main` | BOOLEAN | 주연 여부. 검색 가중치 |

> **결정(2026-07-29): 작품 단위 출연진으로 한다.** 장면별 출연진은 저장하지 않는다.
> 근거 — 수집 비용이 크고 출처 확인이 어려워 품질이 떨어진다. "아이유 나온 촬영지" 검색은 작품 단위로도 충분하다. 필요해지면 `place_content_cast` 를 추가하면 되고 소급도 가능하다.
> 수집 CSV의 `title_cast` 는 작품 단위로 반복 저장돼 있으므로 **작품별 1회만 적재** 한다.

### 3.10 `place_content` — 장소 × 작품 **(핵심 연결)**

| 컬럼 | 타입 | 출처 / 설명 |
|---|---|---|
| `id` | BIGSERIAL **PK** | |
| `place_id` | BIGINT FK → place | |
| `content_id` | BIGINT FK → content | |
| `relation_type` | TEXT | `filming`(촬영지) / `related`(성지·사옥·공연장) |
| `scene_source` | TEXT NULL | `나무위키` / `영문위키백과` / `미확보` |
| `source_url` | TEXT NULL | `source_url` |
| `scene_source_url` | TEXT NULL | 장면 설명의 출처 (상위100 전용) |
| `image_url` | TEXT NULL | 장면 스틸 |
| `collected_by` | TEXT | 수집자 |
| `updated_at` | TIMESTAMPTZ | `last_updated` |

`UNIQUE(place_id, content_id)`. **수집 CSV 한 행이 여기에 해당.**

`relation_type` 이 필요한 이유 — 사옥·공연장 같은 곳은 뭘 찍은 데가 아니라 팬들이 가는 곳이다. 구분해야 UI 필터도 되고 "여기서 촬영됐습니다"라는 오표기도 막는다.

### 3.11 `place_content_i18n` — 관계 설명 (언어별)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `place_content_id` | BIGINT FK | **PK** (복합) |
| `lang` | TEXT | **PK** (복합) |
| `relation_description` | TEXT | `scene_description` |
| `trans_status` | TEXT | |

> [!warning] **`scene_description` 은 사실상 비어 있다.** (§9 참조)
> 드라마 전수 20,080행에서 채움률 **0%**. 상위100_성지 5,740행은 100% 채움으로 보이지만
> **5,680건(99%)이 `"촬영지로 확인됨 — 구체적인 장면 정보 미확인."` 플레이스홀더** 다.
> 실제 장면 설명이 있는 건 **60건뿐** (나무위키 53 + 영문위키 7).

### 3.12 `search_term` — 자동완성 색인 (MATERIALIZED VIEW)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `term_norm` | TEXT | 소문자 + 공백·특수문자 제거 |
| `term_display` | TEXT | 화면 표시용 원본 |
| `entity_type` | TEXT | `place` / `content` / `person` |
| `entity_id` | BIGINT | 원본 테이블 id |
| `lang` | TEXT NULL | 언어별 우선 노출 |
| `weight` | INT | 기본가중치 + `popularity_score`/10 |

**출처 5곳:** `place_i18n` · `place_alias` · `content_i18n` · `content_alias` · `person_i18n`

수집 배치 후 `REFRESH MATERIALIZED VIEW CONCURRENTLY search_term;`

예상 규모 — 장소 14,290 + 작품 476 + 별칭·다국어 포함해 **약 10만 행**. 인덱스 타면 5ms 내외.

### 3.13 `user_event` — 행동 로그 **(MVP2)**

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | BIGSERIAL **PK** | |
| `user_id` | BIGINT NULL | 비로그인 허용 |
| `session_id` | TEXT | 중복 제거·어뷰징 탐지 |
| `event_type` | TEXT | `impression` / `search` / `click` / `view` / `save` / `route_add` / `review` |
| `entity_type` | TEXT | `place` / `content` |
| `entity_id` | BIGINT | |
| `query` | TEXT NULL | 검색어 |
| `position` | INT NULL | 목록에서 몇 번째 (CTR 보정) |
| `created_at` | TIMESTAMPTZ | |

> [!warning] `impression` 과 `position` 을 반드시 로깅할 것.
> 없으면 부익부 루프(§5.3)를 풀 수 없고 **소급이 불가능하다.**

---

## 4. 인덱스

| 대상 | 종류 | 용도 |
|---|---|---|
| `place.geom` | **GiST** | 내 주변 / 지도 영역 검색 |
| `place.popularity_score DESC, id DESC` | B-tree | 핀 우선순위 (동점 안정화) |
| `content.popularity_score DESC, id DESC` | B-tree | 인기순 정렬 |
| `search_term.term_norm` | B-tree `text_pattern_ops` | 앞글자 일치 |
| `search_term.term_norm` | **GIN** `gin_trgm_ops` | 부분·유사 일치 |
| `place_content(place_id)` / `(content_id)` | B-tree | 양방향 조회 |
| `content_cast(person_id)` | B-tree | 배우 → 작품 역방향 |
| `user_event(entity_type, entity_id, created_at DESC)` | B-tree | 집계 배치 |

**필요 확장:** `postgis`, `pg_trgm`

---

## 5. 인기도

### 5.1 콜드스타트가 이미 해결돼 있다

`작품마스터` 에 **`score_global` · `score_interest` · `score_data` · `score_total` · `rank` · `is_top100` · `en_views_12m`** 가 이미 계산돼 있다. 사용자 행동 데이터 없이도 MVP1 인기순 정렬이 바로 가능하다.

### 5.2 MVP1 공식

```sql
UPDATE content c SET popularity_score =
    COALESCE(c.score_total, 0)
  + (SELECT COUNT(*) FROM place_content WHERE content_id = c.id) * 0.5
  + CASE WHEN c.is_featured THEN 1000 ELSE 0 END;
```

`is_featured` 가 필요한 이유 — `작품마스터` 는 드라마 위주라 K-POP·예능·영화는 `score_total` 이 비어 자동 점수가 0이 된다. 밀어야 할 콘텐츠를 사람이 보정할 장치가 없으면 데모에서 이상한 순서가 나온다. 영화는 `audience_acc`(누적 관객수)를 정규화해 대체 지표로 쓸 수 있다.

**장소 인기도** 는 연결된 작품들의 인기도 합에서 시작한다. 줌 아웃 상태에서 핀 14,290개를 다 뿌릴 수 없으므로 필수다.

### 5.3 MVP2 — 행동 기반 전환

```
score = 30 · log(1+루트담기)
      + 15 · log(1+찜)
      +  8 · log(1+상세조회)
      +  5 · CTR × log(1+노출)
      +  2 · log(1+검색)

각 항 × 0.5^(경과일 / 30)          ← 시간 감쇠
```

설계 근거 세 가지:

1. **스케일 정규화** — 검색수·클릭수·찜수는 자릿수가 다르다(예: 12,400 / 1,830 / 67). 그냥 더하면 검색수가 전부 먹고 가장 신뢰도 높은 찜이 묻힌다 → `log(1+x)`
2. **부익부 루프 차단** — 클릭수를 그대로 쓰면 `상위 노출 → 클릭 증가 → 더 상위 노출` 로 1등이 영원히 1등이 된다 → 클릭수 대신 **CTR(클릭÷노출)** + 시간 감쇠
3. **신호 강도 차등** — 사용자가 치른 비용 순으로 가중

| 행동 | 사용자 비용 | 신뢰도 | 어뷰징 난이도 |
|---|---|---|---|
| 검색 노출 | 0 | 매우 낮음 | 아주 쉬움 |
| 검색 클릭 | 탭 1번 | 낮음 | 쉬움 |
| 상세 조회 | 관심 | 중간 | 쉬움 |
| 찜 | 로그인 + 의사결정 | 높음 | 어려움 |
| **루트에 담기** | 실제 여행 계획에 넣음 | **매우 높음** | 매우 어려움 |
| 리뷰 작성 | 시간 투자 | 최상 | 매우 어려움 |

가중치는 **코드에 박지 말고 설정으로 뺀다.** 데모 후 반드시 조정하게 되는데 배포 없이 바꿀 수 있어야 한다.

### 5.4 실무 주의

- **동점 처리** — `ORDER BY popularity_score DESC, id DESC`. tie-breaker가 없으면 페이지네이션에서 항목이 중복/누락된다
- **집계는 배치로** — 조회할 때마다 `user_event` 를 `COUNT(*)` 하면 죽는다. 하루 한 번 배치로 `popularity_score` 에 써넣는다
- **중복 제거** — 같은 사람이 같은 장소를 10번 봐도 1~2회로 캡. `(session_id, entity_id, 날짜)` 단위

---

## 6. 다국어

**대상: `ko` / `en` / `ja` / `zh-Hant`(대만·번체, 예정)**

컬럼 방식(`name_en`, `name_ja`, `name_zh_hant`…)을 쓰지 않고 **번역 테이블을 분리** 한다.

| 컬럼 방식 | 번역 테이블 방식 |
|---|---|
| 언어 추가 = 테이블 3개에 컬럼 4~5개 ALTER | 언어 추가 = **행 추가.** 스키마 변경 0 |
| 미번역분 조회가 어려움 | `lang='ja'` 없는 행으로 즉시 조회 |
| 대부분 NULL이라 낭비 | 있는 것만 저장 |
| 번역 품질 상태 관리 불가 | `trans_status` 로 관리 |

번역 대상은 장소명만이 아니다. 주소, 그리고 가장 긴 `relation_description` 까지 전부다.

원본 테이블에는 **언어중립 데이터만** 남긴다 — 좌표, 카테고리 코드, URL, ID, 점수. 한국어도 예외 없이 `lang='ko'` 행으로 넣는다.

**번역 비용이 예상보다 훨씬 싸다.** 두 가지 이유:

1. **`title_aliases` 가 이미 다국어** — 96.8% 채움. 작품 제목의 영·일·중은 별도 번역이 거의 불필요
2. **`wikidata_qid` 보유** — Wikidata는 한 항목에 수십 개 언어 레이블을 갖고 있다. QID 하나로 `ja`, `zh-Hant` 제목을 **API 한 번에** 끌어올 수 있다

남는 실제 번역 대상은 **장소명·주소·장면 설명** 이다. 장소명은 로마자 표기 규칙으로 상당 부분 자동화되고, 주소는 도로명주소 영문 API가 있다.

**언어 코드 주의:** 대만은 `zh-TW` 보다 **`zh-Hant`(번체)** 를 권장. 홍콩(zh-HK)도 번체라 함께 커버되고, 중국 본토 `zh-Hans`(간체)와는 글자가 달라 반드시 구분해야 한다.

**로마자 별칭은 언어 무관하게 항상 검색되게** 한다 — 일본인도 "Seongsan"으로 칠 수 있다.

**운영:** LLM 초벌 번역 → `trans_status='machine'` → 인기 장소부터 사람이 검수해 `reviewed` 로 승격.

---

## 7. 중복 장소 방지

**결정(2026-07-29): `kakao_place_id` 는 두되 UNIQUE 제약도, 필수 수집도 걸지 않는다.**

컬럼 자체는 비워두는 비용이 0이고 다음 용도가 있다:

- 카카오맵 SDK 연동 (핀 탭 → 장소 상세·길찾기)
- 도로명 변경·장소 이전 시 좌표·주소 자동 갱신
- 수집 자동화 시 dedupe 기준

나중에 주소·좌표로 카카오 API를 돌려 소급 채우기가 가능하다 (`user_event` 로깅과 달리 되돌릴 수 있는 결정).

**다만 적재 시 dedupe는 반드시 필요하다.** 고유 장소명이 14,290개인데 이건 **문자열 기준** 이라, 표기가 다른 동일 장소가 그 안에 섞여 있다. 적재 시 다음 순서로 판정한다:

1. `place_naver_url` 이 같으면 동일 장소 (100% 채움이라 1차 기준으로 강력)
2. 좌표 반경 50m + 이름 유사도(trigram) 0.6 이상이면 동일 후보 → 검토 큐
3. 둘 다 아니면 신규

```sql
-- 신규 장소 추가 전 근접 확인
SELECT p.id, i.name, i.address,
       ROUND(ST_Distance(p.geom, ST_MakePoint(:lng, :lat)::geography)) AS dist_m
FROM place p
JOIN place_i18n i ON i.place_id = p.id AND i.lang = 'ko'
WHERE ST_DWithin(p.geom, ST_MakePoint(:lng, :lat)::geography, 100)
ORDER BY dist_m;
```

---

## 8. 수집 CSV → 테이블 매핑

### 8.1 표준 15컬럼 (드라마 전수 · 영화 · 통합본)

| CSV 컬럼 | 이동처 |
|---|---|
| `id` | ❌ 폐기 (id 재채번) |
| `title` | → `content_i18n.title` (`lang='ko'`) |
| `title_aliases` | → `content_alias` (**`;` 분리 + 언어 자동 판별**) |
| `title_category` | → `content.type` |
| `title_cast` | → `person` + `person_i18n` + `content_cast` (**`;` 분리, 작품별 1회**) |
| `place_name` | → `place_i18n.name` (`lang='ko'`) |
| `place_type` | → `place.category` (**코드로 변환**, §8.3) |
| `place_address` | → `place_i18n.address` (`lang='ko'`) |
| `place_latitude` / `place_longitude` | → `place.geom` |
| `place_image_url` | → `place.image_url` |
| `place_naver_url` | → `place.naver_map_url` (+ **dedupe 1차 키**) |
| `scene_description` | → `place_content_i18n.relation_description` |
| `source_url` | → `place_content.source_url` |
| `last_updated` | → `place_content.updated_at` |
| `audience_acc` (영화 전용) | → `content.audience_acc` |

### 8.2 상위100_성지 추가 3컬럼

| CSV 컬럼 | 이동처 |
|---|---|
| `work_rank` | → `content.rank` |
| `scene_source` | → `place_content.scene_source` |
| `scene_source_url` | → `place_content.scene_source_url` |

### 8.3 작품마스터 28컬럼 → `content`

`work_id`, `title`, `title_official`, `title_en`, `title_aliases`, `title_category`, `title_cast`, `broadcaster`, `air_period`, `air_status`, `wikidata_qid`, `wiki_lang_count`, `en_wiki_title`, `en_views_12m`, `score_global`, `score_interest`, `score_data`, `score_total`, `rank`, `is_top100`, `poster_url`, `description`, `kdramamap_url`, `last_updated` → `content` / `content_i18n`

`location_count`, `location_geocoded`, `region_count`, `top_region` 은 **저장하지 않는다** — `place_content` 에서 집계로 나오는 파생값이라 중복 저장하면 어긋난다.

> **적재 순서:** `작품마스터` 를 먼저 넣어 `content` 를 만들고, 촬영지 CSV들은 `title` 로 매칭해 `place` + `place_content` 만 추가한다. 이렇게 해야 작품 정보가 20,080번 중복 적재되지 않는다.

### 8.4 `place_type` 코드 정리 필요

현재 값 분포(드라마 전수 기준): `기타` **10,273(51.2%)**, `거리` 2,045, `빌딩` 1,150, `공원` 686, `카페` 571, `다리` 554, `음식점` 525, `대학교` 470, `숙박` 408, `스튜디오` 374, `주거` 372, `학교` 273, `병원` 269, `해변` 227, `교회` 155, `편의점` 140, `역` 126, `시장` 124, `터미널` 119, `박물관` 108, `호수` 105, `미술관` 98, `마을` 94, `항구` 89, `마트` 88 …

> [!question] 확인 필요
> **`기타` 가 절반이 넘는다.** 카테고리 필터·아이콘·핀 색상이 사실상 작동하지 않는다는 뜻이다.
> ① 코드 체계를 상위 10~15개로 재정의하고 ② `기타` 를 주소·장소명 키워드로 재분류하는 작업이 필요하다.
> 이건 스키마가 아니라 **데이터 정제 작업** 이므로 별도 티켓으로 뺄 것.

### 8.5 공공데이터 (한국문화정보원 15,034행)

**cp949 인코딩** — utf-8로 읽으면 깨진다. 적재 스크립트에서 명시할 것.

컬럼: `연번` `미디어타입` `제목` `장소명` `장소타입` `장소설명` `영업시간` `브레이크타임` `휴무일` `주소` `위도` `경도` `전화번호` `최종작성일`

**`장소설명`·`영업시간`·`브레이크타임`·`휴무일`·`전화번호` 는 우리 15컬럼에 없는 정보** 다. 공공누리라 **저장·재배포가 자유** 로우므로 ([[데이터 3계층 전략]] 2계층), Google Places로 라이브 호출해야 하는 항목을 일부 대체할 수 있다. 다만 2022-11 기준 데이터라 최신성 확인이 필요하다.

→ 도입한다면 `place` 에 `business_hours`, `phone`, `closed_days` 컬럼을 추가하고 출처를 `data_source` 로 표기. **MVP1 범위 밖으로 두고 별도 판단.**

---

## 9. ⚠️ 스키마와 별개의 최대 리스크 — `scene_description`

| 파일 | `scene_description` 상태 |
|---|---|
| 드라마 전수 20,080행 | **0% 채움** |
| 상위100_성지 5,740행 | 100% 채움이지만 **5,680건(99%)이 플레이스홀더** |
| | `"촬영지로 확인됨 — 구체적인 장면 정보 미확인."` |
| **실제 장면 설명** | **60건** (나무위키 53 + 영문위키 7) |

**"이 장소가 그 작품에서 어떤 장면이었나"가 SceneTrip의 핵심 가치인데, 그게 25,820행 중 60건뿐이다.**

지금 데이터는 정확히 말하면 *"어떤 작품이 어디서 찍었다"* 목록이고, *"거기서 무슨 일이 있었나"* 는 없다. 사용자가 핀을 눌렀을 때 보여줄 게 제목과 주소밖에 없다는 뜻이다.

스키마는 이 문제를 못 푼다 — `place_content_i18n.relation_description` 자리는 이미 있고 비어 있을 뿐이다. **수집 전략의 문제** 이므로 별도 논의가 필요하다. 선택지:

1. **범위 축소** — 상위 100작 × 주요 장소만 장면 설명을 채우고 나머지는 목록으로 제공
2. **LLM 생성** — 작품·장소·회차 정보로 생성. 단 **환각 리스크가 크고** 출처 표기가 불가능
3. **크라우드소싱** — 사용자 기여. MVP1 일정엔 불가능
4. **위키 확대 수집** — 나무위키·위키백과 파싱 범위를 넓힘. 현재 60건이 나온 경로

`scene_source` 컬럼을 스키마에 넣어둔 이유가 이거다. **어떤 설명이 검증된 것이고 어떤 게 플레이스홀더인지 DB 레벨에서 구분** 되어야 화면에서 걸러낼 수 있다.

---

## 10. 남은 작업

- [ ] 수집 템플릿에 `place_aliases`, `relation_type` 컬럼 추가 ([[MZ2AZ-111 촬영지 데이터 수집용 스키마]])
- [ ] 적재 스크립트 — 작품마스터 → `content` 선적재 후 촬영지 CSV 매칭 (§8.3)
- [ ] `place_type` 코드 체계 재정의 + `기타` 51% 재분류 (§8.4) — **별도 티켓**
- [ ] `relation_type` 판정 규칙 (사옥·공연장·스튜디오 → `related`)
- [ ] dedupe 로직 — `place_naver_url` 1차, 좌표+유사도 2차 (§7)
- [ ] **`scene_description` 수집 전략 결정 (§9)** — 최우선
- [ ] 데모 전 `user_event` 로깅 활성화 (`impression`·`position` 포함)

---

## 별칭 수집 규칙 (수집자 전달용)

| 넣는다 | 예시 |
|---|---|
| 줄임말 | 케이팝 데몬 헌터스 → `케데헌` |
| 영문 정식 제목 | 오징어 게임 → `Squid Game` |
| 로마자 표기 | `Ojingeo Geim` (외국인 대상이라 중요) |
| 부제·원제 | 도깨비 → `쓸쓸하고 찬란하神-도깨비` |

| 넣지 않는다 | 이유 |
|---|---|
| 조합형 (`도깨비 방파제`) | (작품 수 × 장소 수)만큼 늘어나 관리 불가. 검색은 토큰 분리로 잡힘 — `도깨비` 는 content에, `방파제` 는 place에 매칭돼 AND 스코어링으로 수렴한다 |
| 오타 (`이태원 클래스`) | 검색 엔진이 처리할 일 |
| 배우 이름 | `content_cast` 로 따로 들어감 |

**구분자는 `;`** — 기존 `title_aliases` 규칙과 통일.
