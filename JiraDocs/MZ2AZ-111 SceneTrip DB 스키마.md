---
title: SceneTrip DB 스키마
type: design
status: draft
updated: 2026-07-30
source:
  - "[[MZ2AZ-111 촬영지 데이터 수집용 스키마]]"
  - "[[촬영지 수집 스키마 15컬럼]]"
related:
  - "[[데이터 3계층 전략]]"
  - "[[MVP1 데이터 모델 (7·24 화이트보드)]]"
---
JIRA:MZ2AZ-138

> [!summary] 수집용 15컬럼 CSV를 적재할 DB 구조. 테이블 14개 + 머티리얼라이즈드 뷰 1개.
> `i18n` = internationalization(국제화). 언어별로 갈리는 값을 담는 테이블.
> ERD·DDL 생성용 DBML은 [[SceneTrip DB 스키마 (DBML)]] 참조.

---

## 1. 구조

```
                    ┌─ place_i18n (언어별 이름·주소)
        place ──────┤
          │         └─ place_alias (별칭)
          │
    place_content ──── place_content_i18n (언어별 장면 설명)
          │
        content ─────┬─ content_i18n (언어별 제목)
          │          └─ content_alias (별칭)
     content_cast
          │
        person ────── person_i18n (언어별 이름)

    search_term  (MV · 자동완성 색인)
    user_event   (MVP2 · 행동 로그)
```

수집 CSV 한 행 = **작품 × 장소** 이므로 그대로 넣으면 작품 정보가 반복 저장된다. 실제로 서강대교는 70개 작품, 조이마당스튜디오는 89개 작품에 걸려 있다. `place_content` 가 이 N:M을 흡수한다.

---

## 2. 테이블

### `place`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `type` | TEXT | `place_type` 을 코드로 변환 |
| `geom` | GEOGRAPHY(Point,4326) | 위도·경도 |
| `naver_place_url` | TEXT NULL | 네이버 지도 **장소 페이지** URL · dedupe 1차 키 |
| `popularity_score` | NUMERIC DEFAULT 0 | 핀 우선순위 |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

`naver_place_url` 은 `https://map.naver.com/p/entry/place/{id}` 형태의 **장소 고유 URL** 이다. 표기가 달라도 같은 장소면 같은 값이 나오므로 dedupe 기준이 된다.

현재 수집된 `place_naver_url` 은 이 형태가 아니다. 20,080행 전부가 `place_address` 를 URL 인코딩한 검색 링크(`/p/search/서울 마포구 …`)라 주소와 정보량이 같고 식별자 역할을 못 한다. **장소 URL은 재수집이 필요하다.**

URL 대신 `{id}` 부분만 `naver_place_id` 로 저장하고 URL은 화면에서 조립하는 방법도 있다. 그쪽이 `UNIQUE` 제약을 걸기에 안정적이다.

### `place_i18n`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `place_id` | BIGINT FK | PK (복합) |
| `lang` | TEXT | PK (복합) · `ko`/`en`/`ja`/`zh-Hant` |
| `name` | TEXT | |
| `address` | TEXT | |
| `description` | TEXT NULL | 장소 자체에 대한 설명 |
| `trans_status` | TEXT | `machine` / `reviewed` / `human` |

`description` 은 작품과 무관한 장소 본연의 설명이다(&ldquo;제주 동쪽 끝의 응회구로 유네스코 세계자연유산&rdquo;). 특정 작품에서의 장면 설명은 `place_content_i18n.relation_description` 에 따로 있다 — 장소 상세 화면에서 전자는 상단 고정, 후자는 작품 목록 안에서 펼쳐진다.

공공데이터(한국문화정보원 15,034행)의 `장소설명` 컬럼이 이 필드의 수집 소스가 된다. 공공누리라 저장·재배포가 자유롭다.

### `place_image`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `place_id` | BIGINT FK → place | |
| `url` | TEXT | |
| `sort_order` | INT DEFAULT 0 | 표시 순서. `10, 20, 30` 처럼 띄워 넣으면 중간 삽입이 쉽다 |
| `created_at` | TIMESTAMPTZ | |

**장소 사진만 담는다.** 작품과 엮지 않는다. 한 장짜리 컬럼(`place.image_url`)으로 두면 외관·내부·계절별 사진이 늘어나는 순간 `image_url_2` 를 만들게 되므로 테이블로 분리했다.

대표 이미지는 별도 컬럼 없이 `sort_order` 첫 번째로 결정된다.

사용자 리뷰 사진은 이 테이블에 섞지 않고 리뷰에 딸린 별도 테이블(`review_image`)로 둔다 — 생명주기(리뷰 삭제 시 함께 삭제)와 신고·숨김 처리가 다르고, 화면에서도 &ldquo;공식 사진 / 여행자 사진&rdquo;으로 구분해 보여주기 때문이다.

> [!note] `scene_image` — **미결정 메모.** 도입하지 않은 상태이며 DBML·ERD에도 포함하지 않았다.
> 작품별 장면 스틸이 필요해지면 `place_content` 를 부모로 삼는 테이블을 새로 만든다.
>
> ```sql
> scene_image (
>   id               BIGSERIAL PK,
>   place_content_id BIGINT FK → place_content,
>   url              TEXT,
>   sort_order       INT DEFAULT 0,
>   created_at       TIMESTAMPTZ
> )
> ```
>
> `place_id` 는 두지 않는다 — `place_content` 를 조인하면 도달하므로, 두 컬럼이 어긋날 위험이 없다. `place_content` 에 복합키 대신 대리키 `id` 를 둔 이유가 이처럼 자식 테이블이 컬럼 하나로 참조하게 하려는 것이며, `place_content_i18n` 이 이미 같은 방식이다.
>
> 실제 관문은 스키마가 아니라 **저작권** 이다. 스틸컷은 방송사·제작사 저작물이라 무단 저장·게시가 위험하다. 라이선스가 명시된 이미지만 쓰거나 제휴가 필요하므로, 권리 문제가 정리되는 시점에 도입한다.

### `place_alias`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `place_id` | BIGINT FK | |
| `alias` | TEXT | |
| `lang` | TEXT NULL | 문자 범위로 자동 판별 (§ 아래) |

dedupe로 병합된 이름들이 여기 보존된다.

**`lang` 판별 규칙** — `place_alias` · `content_alias` 공통. 적재 시 문자 범위로 기계적으로 채운다.

| 문자 | `lang` |
|---|---|
| 한글 | `ko` |
| 가나 | `ja` |
| 한자 | `zh-Hant` |
| **라틴 문자** | **NULL** |

라틴 문자를 전부 NULL로 두는 것이 핵심이다. `Squid Game`(공식 영문)이든 `Ojingeo Geim`(로마자 음차)이든 `Lovley-Runner`(오타)든 **어느 언어 사용자가 입력해도 매칭되어야** 하므로, 영어인지 로마자인지 구분할 실익이 없다.

별칭 종류를 분류하는 `alias_type` 컬럼은 두지 않는다. 실제 수집 데이터에 공식 번역·직역·로마자·오타·가제가 뒤섞여 있어 4~5개 분류로 담기지 않고(예: `Round Six`, `Lovley-Runner`, `Runaway with Sun-jae on Piggyback`), 자동 판별이 불가능한데 19,434건을 손으로 분류할 수도 없다. `lang` 만으로 검색 요건은 충족된다.

### `content`

| 컬럼                          | 타입                | 비고                                     |
| --------------------------- | ----------------- | -------------------------------------- |
| `id`                        | BIGSERIAL PK      |                                        |
| `category`                  | TEXT              | `drama` / `movie` / `variety` / `kpop` |
| `broadcaster`               | TEXT NULL         |                                        |
| `poster_url`                | TEXT NULL         |                                        |
| `popularity_score`          | NUMERIC DEFAULT 0 | 정렬값. 적재 시 직접 계산해 입력                    |
| `created_at` / `updated_at` | TIMESTAMPTZ       |                                        |

**수집 원본 지표는 DB에 저장하지 않는다.** `score_total` · `en_views_12m` · `audience_acc` · `rank` · `is_top100` · `wikidata_qid` 는 작품마스터 CSV에 있지만 컬럼으로 두지 않는다.

| 컬럼 | 안 두는 이유 |
|---|---|
| 인기 지표 4종 | 적재 시 `popularity_score` 계산에만 쓰고 버린다. 원본을 같이 저장하면 우리 정렬값과 외부 순위가 공존해 &ldquo;1위인데 왜 목록에선 5번째냐&rdquo;는 혼란이 생기고, 외부 값은 갱신되지 않아 낡는다 |
| `air_period` · `air_status` | **방영 정보는 두지 않는다.** `air_status` 는 476행 전량이 `방영종료` 로 분산이 0이고, 애초에 방영 종료일과 오늘 날짜로 계산되는 파생값이라 저장하면 낡는다 — `김부장`(종료 2026-07-25)처럼 수집 며칠 전에 끝난 작품이 있어, 방영 중에 수집했으면 `방영중` 이 종영 후에도 그대로 남는다. `air_period` 는 `'2021-09-17 ~ 2021-09-17'` 형태의 TEXT 범위여서 정렬·필터에 쓸 수 없고(넷플릭스 단일 공개작 80건은 시작 == 종료), 앱이 읽지 않는다. 원본 값은 작품마스터 CSV에 보존된다 |
| `wikidata_qid` | 다국어 제목을 채울 때 참고하는 값일 뿐 앱이 읽지 않는다. 값 자체는 `01_Raw/김태환/DataCollection/kdramamap_작품마스터_2026-07-29.csv` 에 보존돼 있어 나중에 언어를 추가할 때 그 파일을 다시 보면 된다 |
| `is_featured` | 자동 계산을 덮어쓰는 장치인데 점수를 직접 입력하므로 덮어쓸 대상이 없다. MVP2에서 배치 계산으로 전환할 때 다시 필요해지면 추가한다 |

### `content_i18n`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `content_id` | BIGINT FK | PK (복합) |
| `lang` | TEXT | PK (복합) |
| `title` | TEXT | |
| `description` | TEXT NULL | |
| `trans_status` | TEXT | |

### `content_alias`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `content_id` | BIGINT FK | |
| `alias` | TEXT | `title_aliases` 를 `;` 로 분리 |
| `lang` | TEXT NULL | `place_alias` 와 동일한 판별 규칙 |

`title_aliases` 는 이미 다국어다 (96.8% 채움) — `오징어 게임;Squid Game;イカゲーム;魷魚遊戲;Ojingeo Geim;Round Six;오겜`.

### `person`

| 컬럼 | 타입 |
|---|---|
| `id` | BIGSERIAL PK |
| `created_at` | TIMESTAMPTZ |

### `person_i18n`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `person_id` | BIGINT FK | PK (복합) |
| `lang` | TEXT | PK (복합) |
| `name` | TEXT | 아이유 / IU / アイユー |

인물을 `content_cast` 에 이름 문자열로 직접 넣지 않고 별도 실체로 분리한 이유는 **번역 단위 때문** 이다. 실측상 고유 인물 554명에 출연 관계는 1,209건이다(서인국 9작품, 지창욱 9작품). 이름 번역은 사람 단위로 한 번 하면 되는데 관계 단위로 저장하면 같은 번역을 9번 써야 하고, 한 곳에 오타가 나면 그 작품에서만 검색이 갈라진다.

배우 이름은 **기계 번역이 불가능** 하다. 장소명과 달리 관용 표기가 따로 있어 로마자 표기법대로 변환하면 틀린다(변우석 → 규칙상 `Byeon U-seok`, 실제 `Byeon Woo-seok` / 아이유 → 실제 `IU`). 통용 표기를 외부(위키데이터·TMDB 등)에서 수집해야 하며, 그 참조 데이터는 DB 컬럼이 아니라 `01_Raw` 의 CSV로 보관한다.

### `content_cast`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `content_id` | BIGINT FK | PK (복합) |
| `person_id` | BIGINT FK | PK (복합) |
| `sort_order` | INT | `title_cast` 나열 순서 = 비중 |

**작품 단위 출연진만 저장한다.** 장면별 출연진은 저장하지 않는다. `title_cast` 는 CSV에 작품마다 반복되므로 작품별 1회만 적재한다.

`sort_order` 는 `변우석;김혜윤` 의 순서를 그대로 넣는다. 나열 순서가 곧 비중이므로 화면 표시 순서와 검색 가중치에 함께 쓰인다. 주연 여부는 `sort_order <= 2` 로 계산되므로 별도 컬럼(`is_main`)을 두지 않는다.

**배역명(`role_name`)은 두지 않는다.** 수집 CSV에 배역 정보가 없어 전량 NULL이 되고, 채우려면 476작품 × 2~3역을 새로 수집해야 한다. 배역명 검색(&ldquo;우영우&rdquo;, &ldquo;애순&rdquo;)을 지원하기로 결정하면 `search_term` 소스 추가와 배역명 다국어 테이블까지 함께 설계해야 하므로, 그때 세트로 도입한다.

### `place_content`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `place_id` | BIGINT FK | |
| `content_id` | BIGINT FK | |
| `updated_at` | TIMESTAMPTZ | `last_updated` |

`UNIQUE(place_id, content_id)`. 수집 CSV 한 행이 여기에 해당한다. 실제 내용(장면 설명)은 `place_content_i18n` 에 있고 이 테이블은 연결과 갱신 시점만 담는다.

`relation_type`(촬영지/성지 구분)은 두지 않는다. 현재 수집분이 전량 촬영지라 값이 하나뿐이고, 장소에 장면이 딸려 있는 구조 자체로 충분하다.

출처·수집 메타(`source_url` · `scene_source` · `scene_source_url` · `collected_by`)는 두지 않는다. `collected_by` 는 현재 15컬럼 CSV에 아예 없고, 나머지는 앱이 읽지 않으며 값은 `01_Raw` 의 수집 CSV에 보존된다. 장면 설명을 전량 채우기로 했으므로 검증본과 플레이스홀더를 구분하던 `scene_source` 의 역할도 사라졌다.

### `place_content_i18n`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `place_content_id` | BIGINT FK | PK (복합) |
| `lang` | TEXT | PK (복합) |
| `relation_description` | TEXT | `scene_description` |
| `trans_status` | TEXT | |

> [!warning] 현재 수집분에는 실질적으로 비어 있다 — 드라마 전수 20,080행 0% 채움, 상위100 5,740행 중 5,680건이 `"촬영지로 확인됨 — 구체적인 장면 정보 미확인."` 플레이스홀더로 **실제 설명은 60건.** 이 필드를 전량 채우는 것을 전제로 한 설계다.

### `search_term` (MATERIALIZED VIEW)

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `term_norm` | TEXT | 소문자 + 공백·특수문자 제거 |
| `term_display` | TEXT | 표시용 원본 |
| `entity_type` | TEXT | `place` / `content` / `person` |
| `entity_id` | BIGINT | |
| `lang` | TEXT NULL | |
| `weight` | INT | 기본가중치 + `popularity_score`/10 |

`place_i18n` · `place_alias` · `content_i18n` · `content_alias` · `person_i18n` 5곳을 UNION ALL. 적재 후 `REFRESH MATERIALIZED VIEW CONCURRENTLY`.

자동완성이 5개 테이블 조인 없이 이 뷰 하나만 조회하게 하는 것이 목적이다. 예상 10만 행.

### `user_event` (MVP2)

| 컬럼            | 타입           | 비고                                                                           |
| ------------- | ------------ | ---------------------------------------------------------------------------- |
| `id`          | BIGSERIAL PK |                                                                              |
| `user_id`     | BIGINT NULL  | 비로그인 허용                                                                      |
| `session_id`  | TEXT         | 중복 제거                                                                        |
| `event_type`  | TEXT         | `impression` / `search` / `click` / `save` / `route_add` / `review`          |
| `entity_type` | TEXT NULL    | `place` / `content` / `person` · 대상 없는 이벤트는 NULL (`search`)                  |
| `entity_id`   | BIGINT NULL  |                                                                              |
| `query`       | TEXT NULL    |                                                                              |
| `position`    | INT NULL     | 목록 순번 · CTR 보정                                                               |
| `created_at`  | TIMESTAMPTZ  |                                                                              |

`impression` 과 `position` 은 소급 수집이 불가능하므로 로깅 시작 시점부터 포함해야 한다.

### `saved_place` — 찜 (MVP2)

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `user_id` | BIGINT | PK (복합) |
| `place_id` | BIGINT FK → place | PK (복합) |
| `source_content_id` | BIGINT FK → content NULL | 어떤 작품을 보다가 찜했는지 (선택) |
| `created_at` | TIMESTAMPTZ | |

**찜은 `place` 기준이지 `place_content`(성지) 기준이 아니다.** 루트담기가 물리적 장소 단위인 것과 맞춰야 한다 — 같은 장소가 작품 A 성지로도, 작품 B 성지로도 걸려 있을 때 성지 기준으로 찜하면 같은 곳을 두 번 저장하는 꼴이 되고, 루트에 담을 땐 결국 장소 하나로 합쳐져야 하니 그 경계에서 항상 변환 문제가 생긴다.

"왜 찜했는지"는 잃지 않도록 `source_content_id` 로 남긴다 — 저장 대상(장소)과 저장 이유(작품)를 분리한 것이다.

`user_event` 와 별도 테이블인 이유 — `user_event` 는 append-only 로그(분석용)이고, 찜은 토글·해제가 필요한 **현재 상태** 라 별도의 상태 테이블이 필요하다. `created_at` 은 위 인기도 감쇠 계산에도 그대로 쓰인다.

---

## 3. 인덱스

| 대상 | 종류 | 용도 |
|---|---|---|
| `place.geom` | GiST | 반경·영역 검색 |
| `place.popularity_score DESC, id DESC` | B-tree | 핀 우선순위 |
| `content.popularity_score DESC, id DESC` | B-tree | 인기순 정렬 |
| `search_term.term_norm` | B-tree `text_pattern_ops` | 앞글자 일치 |
| `search_term.term_norm` | GIN `gin_trgm_ops` | 부분·유사 일치 |
| `place_content(place_id)` / `(content_id)` | B-tree | 양방향 조회 |
| `content_cast(person_id)` | B-tree | 배우 → 작품 |
| `user_event(entity_type, entity_id, created_at DESC)` | B-tree | 집계 배치 |

정렬 인덱스의 `id DESC` 는 동점 시 순서를 고정한다. 없으면 페이지네이션에서 항목이 중복·누락된다.

**확장:** `postgis`, `pg_trgm`

---

## 4. 수집 CSV → 테이블

### 표준 15컬럼

| CSV 컬럼 | 이동처 |
|---|---|
| `id` | 폐기 (재채번) |
| `title` | `content_i18n.title` (`lang='ko'`) |
| `title_aliases` | `content_alias` — `;` 분리 + 언어 판별 |
| `title_category` | `content.category` |
| `title_cast` | `person` + `person_i18n` + `content_cast` — `;` 분리, 작품별 1회 |
| `place_name` | `place_i18n.name` (`lang='ko'`) |
| `place_type` | `place.type` (코드 변환) |
| `place_address` | `place_i18n.address` (`lang='ko'`) · **dedupe 키** |
| `place_latitude` / `place_longitude` | `place.geom` |
| `place_image_url` | `place_image.url` |
| `place_naver_url` | `place.naver_place_url` — 현재 값은 주소 인코딩본이므로 장소 URL로 재수집 |
| `scene_description` | `place_content_i18n.relation_description` |
| `source_url` | 저장하지 않음 (`01_Raw` CSV에 보존) |
| `last_updated` | `place_content.updated_at` |
| `audience_acc` (영화) | 저장하지 않음 — 적재 시 `popularity_score` 계산에만 사용 |

### 상위100_성지 추가 3컬럼

`work_rank` · `scene_source` · `scene_source_url` 모두 저장하지 않는다. 순위는 `popularity_score` 로 대체되고, 출처는 `01_Raw` CSV에 남는다.

### 작품마스터 28컬럼

`content` / `content_i18n` 으로 적재. 단 아래는 컬럼으로 저장하지 않는다.

| CSV 컬럼 | 처리 |
|---|---|
| `score_total` · `score_global` · `score_interest` · `score_data` · `en_views_12m` · `rank` · `is_top100` | 적재 시 `popularity_score` 계산에만 사용하고 버린다 |
| `location_count` · `location_geocoded` · `region_count` · `top_region` | `place_content` 집계로 나오는 파생값 |
| `air_period` · `air_status` | 저장하지 않음 (§2 `content` 참조) |

**적재 순서:** 작품마스터 → `content` 를 먼저 만들고, 촬영지 CSV는 `title` 로 매칭해 `place` + `place_content` 만 추가한다. 그래야 작품 정보가 20,080번 중복 적재되지 않는다.

### 공공데이터 (한국문화정보원 15,034행)

**cp949 인코딩.** utf-8로 읽으면 깨진다.
`장소설명` · `영업시간` · `브레이크타임` · `휴무일` · `전화번호` 는 15컬럼에 없는 정보이고 공공누리라 저장이 자유롭다. 도입 시 `place` 에 컬럼 추가. MVP1 범위 밖.

---

## 5. dedupe (중복 장소 병합)

같은 장소를 수집자마다 다르게 적어 여러 행이 된다. 실측:

| 데이터 | 이름 기준 고유 | 주소 기준 고유 | 중복 그룹 |
|---|---|---|---|
| 드라마 전수 20,080행 | 14,290 | 13,145 | **1,414** |
| 상위100 5,740행 | 4,744 | 4,520 | **343** |

```
같은 주소인데 이름이 다른 예:
['상암DMC디지털큐브', '상암동DMC디지털큐브', '디지털큐브', '더차이 상암 디지털큐브점', '상암산로']
['남산', '남산타워']
```

병합하지 않으면 같은 자리에 핀이 여러 개 찍히고, 작품 연결·찜·인기도가 조각난다.

**판정 규칙**

| 순서 | 조건 | 처리 |
|---|---|---|
| 1 | `naver_place_url` 동일 | 자동 병합 (확정) |
| 2 | `place_address` 정규화 후 동일 | 자동 병합 |
| 3 | 주소는 다르나 좌표 50m 이내 + 이름 유사도 0.6↑ | 검토 큐 → 사람이 판단 |
| 4 | 그 외 | 신규 |

1번이 채워지면 2·3번은 거의 쓸 일이 없다. 장소 URL이 없는 행에만 적용한다.

주소 기준(2번)은 완전하지 않다. `['마포대교 옆', '여의도한강공원', '크루즈옆']` 처럼 주소만 같고 실제로는 다른 지점이 묶일 수 있다. 반대로 `남산` / `남산타워` 는 같은 곳인데 주소 표기가 달라 3번으로 넘어간다. **장소 URL은 이 두 오류를 모두 없앤다.**

**대표 이름은 최빈 표기를 쓰고, 병합된 나머지 이름은 `place_alias` 로 보존한다.** 그래야 어느 표기로 검색해도 같은 핀이 나온다.

카카오 place_id는 사용하지 않는다 (네이버 지도 SDK 사용).

---

## 6. 다국어

**`ko` / `en` / `ja` / `zh-Hant`** — 대만·홍콩은 번체이므로 `zh-TW` 가 아니라 `zh-Hant`. 중국 본토 `zh-Hans`(간체)와 글자가 다르다.

언어별 컬럼(`name_en`, `name_ja` …)을 쓰지 않고 i18n 테이블로 분리한다. 언어 추가가 **행 추가** 로 끝나고, 미번역분을 `lang` 유무로 바로 찾을 수 있다.

원본 테이블에는 언어중립 값만 남긴다 — 좌표, 카테고리 코드, ID, 점수. 한국어도 `lang='ko'` 행으로 넣는다.

번역 대상 중 작품 제목은 `title_aliases`(96.8% 채움)와 `wikidata_qid` 로 상당 부분 자동 확보된다. 실제 번역이 필요한 것은 **장소명 · 주소 · 장면 설명** 이다.

로마자 별칭은 `lang` 을 NULL로 두어 어느 언어에서든 검색되게 한다.

---

## 7. 인기도

**MVP1 — 적재 시 직접 입력.** 외부 지표(`score_total` · `en_views_12m` · `audience_acc`)를 DB에 저장하지 않으므로, 수집·적재 단계에서 이 값들을 참고해 계산한 결과를 `popularity_score` 에 바로 넣는다. 사용자 행동 데이터가 없는 MVP1에서는 이것으로 인기순 정렬이 성립한다.

계산 기준은 적재 스크립트에 두며, 드라마는 `score_total`, 영화는 `audience_acc`, 지표가 없는 K-POP·예능은 수집자가 직접 값을 부여한다.

`place.popularity_score` 도 같은 방식으로, 연결된 작품 인기도의 합에서 시작한다. 장소가 14,000개 이상이라 줌 아웃 시 핀 솎아내기에 필요하다.

**MVP2 — "요즘 인기" (작품)** — `user_event` 를 시간 감쇠(decay)로 집계해 전환한다. 감쇠 반감기는 스키마가 아니라 배치 쿼리의 상수이므로 값은 튜닝 가능하다(제안: 작품 14일).

```sql
UPDATE content c SET popularity_score = sub.score
FROM (
  SELECT entity_id AS content_id,
         SUM(
           CASE event_type
             WHEN 'route_add' THEN 30
             WHEN 'save'      THEN 15
             WHEN 'search'    THEN 2
           END
           * POWER(0.5, EXTRACT(EPOCH FROM (now() - created_at)) / 86400.0 / 14)
                                                                -- ↑ 반감기 14일
         ) AS score
  FROM user_event
  WHERE entity_type = 'content'
  GROUP BY entity_id
) sub
WHERE c.id = sub.content_id;
```

행동마다 가중치가 다른 것은 사용자가 치른 비용 순이다 — 루트담기(30) > 찜(15) > 검색(2). 클릭수 대신 CTR을 쓰면(노출 대비 클릭) 상위 노출이 클릭을 부르는 순환을 끊을 수 있다.

> [!question] 확인 필요 — `click` 가중치가 비어 있다. `view` 를 없애면서 함께 삭제했으므로, 가중치 재검토 시 `click` 항목을 다시 넣어야 한다.

#### 감쇠(decay)가 작동하는 방식

**저장된 점수가 저절로 줄어드는 것이 아니다.** 배치를 돌릴 때마다 `user_event` 원본에서 처음부터 다시 계산하고, 그 시점에 각 이벤트를 나이만큼 할인한다. 시간 자체가 입력값이므로 &ldquo;이벤트 발생 시 더하기&rdquo; 방식으로는 유지할 수 없고, 주기적 전체 재계산이 유일한 방법이다.

찜(가중치 15) 3건이 2주 간격으로 쌓인 작품을 7/30에 계산하면:

| 이벤트 | 며칠 전 | `0.5^(일수/14)` | 점수 |
|---|---|---|---|
| 7/30 찜 | 0일 | 1.0 | 15.00 |
| 7/16 찜 | 14일 | 0.5 | 7.50 |
| 7/02 찜 | 28일 | 0.25 | 3.75 |
| | | **합계** | **26.25** |

14일 뒤 새 이벤트가 하나도 없으면 같은 계산이 **13.125** 가 된다. 아무 일도 없었는데 정확히 절반 — 이것이 반감기 14일의 의미다.

**급상승은 눌리지 않는다.** 감쇠는 과거 이벤트에만 걸리고 새 이벤트는 할인율 0%로 들어온다. 점수 20이던 작품에 찜 50개가 몰리면:

| | 계산 | 점수 |
|---|---|---|
| 기존 누적분 | 20 × 0.95 | 19 |
| 신규 찜 50개 | 50 × 15 × **1.0** | 750 |
| | **합계** | **769** |

감쇠가 깎은 것은 1점이고 새 활동이 750점을 올렸다. 규모가 달라 감쇠가 급상승과 경쟁하지 못한다.

**감쇠의 실제 효과는 점수를 &ldquo;누적 총량&rdquo;이 아니라 &ldquo;현재 속도&rdquo;로 바꾸는 것이다.** 활동이 일정하면 유입과 감쇠가 같아지는 지점에서 멈춘다 — 대략 `하루 활동량 × 20`.

| 상태 | 하루 활동 | 평형 점수 |
|---|---|---|
| 방영 중 · 하루 찜 10개 | 150점 | 약 3,100 |
| 종영 후 · 하루 찜 1개 | 15점 | 약 310 |

감쇠가 없으면 점수가 누적 총량이 되어, 4년치가 쌓인 옛 대작이 지금 아무도 찾지 않아도 영구 1위가 되고 신작은 따라잡을 수 없다.

**배치 주기는 하루 1회면 충분하다.** 반감기 14일에서 1시간의 감쇠는 0.2%, 하루는 4.8%다. 시간당 재계산해도 순위가 바뀌지 않는다. 신작 반영이 느리다고 판단되면 주기가 아니라 **반감기를 줄인다**(7일이면 민감, 30일이면 안정). 배치 쿼리의 상수라 스키마 변경 없이 조정된다.

**MVP2 — "요즘 인기" (장소)** — 장소는 직접 신호만으로는 부족하다. 서강대교처럼 89개 작품에 걸린 장소는 실제로는 인기가 높아도, 사용자가 "서강대교"를 직접 검색·클릭하는 일은 드물고 작품 화면에서 성지 목록으로만 스치듯 지나갈 수 있다. 그래서 **직접 신호 + 연결된 작품의 인기도 일부**를 더한다.

```sql
UPDATE place p SET popularity_score =
    COALESCE(direct.score, 0)
  + 0.3 * COALESCE(inherited.score, 0)   -- α=0.3 · 연결된 작품 인기도 전이 비율
FROM
  (SELECT entity_id AS place_id,
          SUM(... 위와 동일한 decay 가중합, entity_type='place' ...) AS score
   FROM user_event WHERE entity_type = 'place' GROUP BY entity_id) direct
  FULL OUTER JOIN
  (SELECT pc.place_id, SUM(c.popularity_score) AS score
   FROM place_content pc JOIN content c ON c.id = pc.content_id
   GROUP BY pc.place_id) inherited
  ON direct.place_id = inherited.place_id
WHERE p.id = COALESCE(direct.place_id, inherited.place_id);
```

반감기는 장소가 더 길게(제안: 30일) — 작품은 방영 종료 후 화제성이 빠르게 식지만, 장소는 방영이 끝나도 관광지로서 인기가 오래 유지되기 때문이다. α(전이 비율)도 코드가 아닌 설정값으로 두고 실사용 데이터로 튜닝한다.
