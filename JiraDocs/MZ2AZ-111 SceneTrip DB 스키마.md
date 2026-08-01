---
title: SceneTrip DB 스키마
type: design
status: draft
updated: 2026-07-31
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

**사람 자체에는 직군을 붙이지 않는다.** 배우/감독 구분은 `content_cast.role_type` 에 있다 — 이유는 해당 절 참조.

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
| `role_type` | TEXT | PK (복합) · `actor` / `director` |
| `sort_order` | INT | `title_cast` 나열 순서 = 비중 |

`role_type` 은 이 사람이 **이 작품에서** 배우였는지 감독이었는지를 담는다. 검색 결과에서 &ldquo;봉준호&rdquo;가 출연진으로 섞여 나오지 않게 하고, 작품 상세에서 출연진과 감독을 다른 줄에 표시하기 위한 값이다.

`person` 이 아니라 여기에 두는 이유는 **겸업 때문** 이다. 하정우·정우성처럼 연출과 연기를 겸하는 인물이 있어 사람마다 값을 하나만 붙이면 한쪽이 지워진다. 하정우를 `actor` 로 넣으면 그가 연출한 작품에서 감독으로 안 잡히고, `director` 로 넣으면 출연작 전부에서 배우로 안 잡힌다. 역할은 사람의 속성이 아니라 **사람과 작품 사이의 속성** 이므로 관계 테이블이 제자리다.

배역명(`role_name`)과는 다른 값이다. `role_type` 은 직군(배우냐 감독이냐)이고, `role_name` 은 맡은 배역(&ldquo;백현우&rdquo;)이다. 후자는 두지 않는다 — 아래 참조.

**현재 수집분은 전량 `actor` 가 된다.** 인물 소스가 `title_cast`(배우 나열) 하나뿐이라 감독 정보가 어느 CSV에도 없다. 감독을 채우려면 별도 수집이 필요하다.

`sort_order` 는 `role_type` 별로 따로 매긴다. 감독과 배우가 한 목록에서 순서를 다투면 의미가 없기 때문이다.

PK가 `(content_id, person_id, role_type)` 로 세 컬럼이 된 것도 겸업 때문이다. 한 작품에서 연출과 주연을 함께 맡는 경우(하정우 『허삼관』)가 있어 `(content_id, person_id)` 만으로는 두 역할이 한 행을 놓고 충돌한다.

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

**인기도 점수는 이 테이블에서 내지 않는다** (§7.2 원칙 ①). 이 로그의 용도는 셋이다 — 나중에 CTR로 승격, 분석·디버깅, 그리고 **별칭 수집** 이다. 사용자가 실제로 친 검색어와 그 뒤에 누른 대상을 짝지어 `content_alias` · `place_alias` 를 보강한다. 수집 CSV의 별칭이 남이 만든 표기라면 이쪽은 **우리 사용자가 실제로 쓰는 표기** 다.

### `saved_place` — 찜 (MVP2)

| 컬럼                  | 타입                       | 비고                                   |
| ------------------- | ------------------------ | ------------------------------------ |
| `user_id`           | BIGINT                   | PK (복합)                              |
| `place_id`          | BIGINT FK → place        | PK (복합)                              |
| `source_content_id` | BIGINT FK → content NULL | 어떤 작품을 보다가 찜했는지 · **작품 인기도의 유일한 통로** |
| `created_at`        | TIMESTAMPTZ              |                                      |

**찜은 `place` 기준이지 `place_content`(성지) 기준이 아니다.** 루트담기가 물리적 장소 단위인 것과 맞춰야 한다 — 같은 장소가 작품 A 성지로도, 작품 B 성지로도 걸려 있을 때 성지 기준으로 찜하면 같은 곳을 두 번 저장하는 꼴이 되고, 루트에 담을 땐 결국 장소 하나로 합쳐져야 하니 그 경계에서 항상 변환 문제가 생긴다.

"왜 찜했는지"는 잃지 않도록 `source_content_id` 로 남긴다 — 저장 대상(장소)과 저장 이유(작품)를 분리한 것이다.

이 칸은 화면 표시용으로 넣었으나, §7.2 에서 **작품 점수를 만드는 유일한 경로** 가 되었다. 찜·루트담기·리뷰가 전부 장소에 달리는 행동이라 작품에 직접 붙는 신호가 없기 때문이다. NULL이면 그 찜은 작품 점수에 기여하지 못하므로, 선택 컬럼이되 **가능한 한 항상 채운다.**

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
| `title_cast` | `person` + `person_i18n` + `content_cast` — `;` 분리, 작품별 1회 · `content_cast.role_type` 은 `actor` 고정 |
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

| 데이터            | 이름 기준 고유 | 주소 기준 고유 | 중복 그룹     |
| -------------- | -------- | -------- | --------- |
| 드라마 전수 20,080행 | 14,290   | 13,145   | **1,414** |
| 상위100 5,740행   | 4,744    | 4,520    | **343**   |
|                |          |          |           |

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

`popularity_score` 는 두 단계로 만들어진다.

| 단계 | 근거 |
|---|---|
| **초기** | 외부 지표를 적재 시 계산해 입력 (§7.1) |
| **데이터 쌓인 후** | 사용자의 실제 행동으로 배치 재계산 (§7.2) |

---

### 7.1 초기 — 적재 시 직접 입력

외부 지표(`score_total` · `en_views_12m` · `audience_acc`)를 DB에 저장하지 않으므로, 수집·적재 단계에서 이 값들을 참고해 계산한 결과를 `popularity_score` 에 바로 넣는다. 사용자 행동 데이터가 없는 시점에서는 이것으로 인기순 정렬이 성립한다.

계산 기준은 적재 스크립트에 두며, 드라마는 `score_total`, 영화는 `audience_acc`, 지표가 없는 K-POP·예능은 수집자가 직접 값을 부여한다.

`place.popularity_score` 도 같은 방식으로, 연결된 작품 인기도의 합에서 시작한다. 장소가 14,000개 이상이라 줌 아웃 시 핀 솎아내기에 필요하다.

> [!question] 확인 필요 — 이 단계의 계산 기준은 §7.2 를 확정한 뒤 다시 본다.

---

### 7.2 데이터 쌓인 후 — 사용자 행동으로 계산

#### 원칙

**① 점수는 로그가 아니라 상태 테이블에서 낸다.**
`user_event`(append-only 로그)가 아니라 `saved_place` 같은 상태 테이블의 현재 행을 센다. 로그로 세면 두 가지를 따로 막아야 한다 — 찜·해제를 반복하는 어뷰징(로그에는 매번 남는다)과 해제의 점수 반영이다. 상태를 세면 둘 다 애초에 발생하지 않는다. `saved_place` 는 (`user_id`, `place_id`)가 PK라 몇 번을 토글해도 최종 1건이고, 해제하면 행이 사라져 점수도 함께 빠진다.

**② 모든 신호에 감쇠를 건다.**
감쇠 없는 신호를 하나라도 섞으면 그 신호만 누적 총량이 되어 나머지를 압도한다.

**③ 점수는 더해가지 않는다.**
배치가 매번 전체를 재계산해 덮어쓴다. 시간이 입력값이라 "행동 발생 시 +N" 방식으로는 유지할 수 없다.

#### 신호

| 신호 | 출처 | 가중치 | 도입 시점 |
|---|---|---|---|
| 찜 | `saved_place` 행 수 | | 지금 |
| 루트담기 | `route_item` 행 수 | | 테이블 설계 후 |
| 리뷰 | `review` 행 수 | | 테이블 설계 후 |
| CTR | `user_event` · 노출 대비 클릭 | | 데이터 축적 후 |

> [!question] 확인 필요 — 가중치 미정. 신호가 찜 하나뿐인 동안은 비율 자체가 성립하지 않으므로, 두 번째 신호가 들어오는 시점에 함께 정한다.

**쓰지 않는 신호**

| 신호 | 이유 |
|---|---|
| 클릭 (생짜 개수) | 상위 노출 → 클릭 → 상위 노출의 순환이 생긴다. CTR로 대체 |
| 노출 (`impression`) | 그 자체는 점수가 아니다. CTR의 분모로만 쓴다 |
| 검색 (`search`) | 대상이 없는 이벤트(`entity_id` NULL)라 특정 작품·장소에 귀속되지 않는다. 검색 로그는 별칭 수집에 쓴다 (§2 `user_event`) |

`impression` 과 `position` 은 지금 점수에 쓰지 않지만 **첫날부터 로깅한다.** 소급 수집이 불가능하다.

#### 점수 구성

```
작품 점수 = 그 작품 때문에 생긴 찜        (감쇠 적용)
장소 점수 = 그 장소를 직접 한 찜          (감쇠 적용)
          + α × 그 장소에 걸린 작품의 점수
```

찜·루트담기·리뷰는 **전부 장소에 달리는 행동이다.** 작품을 찜하거나 루트에 담는 기능은 없다. 그래서 작품 점수는 `saved_place.source_content_id`("어느 작품을 보다가 찜했는지")를 통해서만 만들어진다 — **이 칸이 작품 점수의 유일한 통로다.**

두 점수는 서로 비교되지 않는다(장소는 장소끼리, 작품은 작품끼리 정렬). 같은 찜 1건이 양쪽에 각각 반영되어도 부풀 것이 없다.

**계산 순서는 작품 → 장소로 고정한다.** 장소 → 작품 → 장소로 순환이 생기므로, 배치 안에서 작품 점수를 먼저 확정한 뒤 장소가 그 값을 참조해야 결과가 안정된다.

배치 쿼리는 가중치와 α 가 확정된 뒤 여기에 붙인다.

#### 감쇠가 작동하는 방식

**저장된 점수가 저절로 줄어드는 것이 아니다.** 배치를 돌릴 때마다 원본에서 처음부터 다시 계산하고, 그 시점에 각 건을 나이만큼 할인한다. 시간 자체가 입력값이므로 주기적 전체 재계산이 유일한 방법이다.

찜 3건이 2주 간격으로 쌓인 작품을 7/30에 계산하면 (반감기 14일 · 찜 1건 15점 가정):

| 찜 | 며칠 전 | `0.5^(일수/14)` | 점수 |
|---|---|---|---|
| 7/30 | 0일 | 1.0 | 15.00 |
| 7/16 | 14일 | 0.5 | 7.50 |
| 7/02 | 28일 | 0.25 | 3.75 |
| | | **합계** | **26.25** |

14일 뒤 새 찜이 하나도 없으면 같은 계산이 **13.125** 가 된다. 아무 일도 없었는데 정확히 절반 — 이것이 반감기 14일의 의미다.

**급상승은 눌리지 않는다.** 감쇠는 과거에만 걸리고 새 찜은 할인율 0%로 들어온다. 점수 20이던 작품에 찜 50건이 몰리면 기존 누적분은 19로 1점 줄고 신규분이 750점 들어온다. 규모가 달라 감쇠가 급상승과 경쟁하지 못한다.

**감쇠의 실제 효과는 점수를 &ldquo;누적 총량&rdquo;이 아니라 &ldquo;현재 속도&rdquo;로 바꾸는 것이다.** 활동이 일정하면 유입과 감쇠가 같아지는 지점에서 멈춘다 — 대략 `하루 활동량 × 20`.

| 상태 | 하루 활동 | 평형 점수 |
|---|---|---|
| 방영 중 · 하루 찜 10건 | 150점 | 약 3,100 |
| 종영 후 · 하루 찜 1건 | 15점 | 약 310 |

감쇠가 없으면 점수가 누적 총량이 되어, 4년치가 쌓인 옛 대작이 지금 아무도 찾지 않아도 영구 1위가 되고 신작은 따라잡을 수 없다.

**배치 주기는 하루 1회면 충분하다.** 반감기 14일에서 1시간의 감쇠는 0.2%, 하루는 4.8%다. 시간당 재계산해도 순위가 바뀌지 않는다. 신작 반영이 느리다고 판단되면 주기가 아니라 **반감기를 줄인다**(7일이면 민감, 30일이면 안정). 배치 쿼리의 상수라 스키마 변경 없이 조정된다.

#### 미결

> [!question] 확인 필요 — α 합산 방식. 여러 작품에 걸린 장소를 어떻게 볼 것인가.
> 현재 설계는 연결된 작품 점수를 **전부 더한다.** 서강대교·조이마당스튜디오는 각각 89개 작품에 걸려 있어, 작품당 100점이면 α=0.3에서 2,670점을 물려받는다. 작품 1개인 청운고는 30점이다. 직접 찜으로는 뒤집을 수 없는 격차다.
> 촬영지로 자주 쓰이는 것은 관광 매력이 아니라 촬영 허가의 문제이므로, 합계로 두면 인기 순위가 아니라 **촬영 편의 순위** 가 된다.
> 후보 — 전부 합산 / 가장 인기 있는 작품 하나만 / 상위 N개 합.

> [!question] 확인 필요 — 반감기. 작품 14일 · 장소 30일로 제안돼 있으나, α로 물려받은 점수는 **이미 작품 반감기로 감쇠된 값** 이다. 장소 점수 안에 두 개의 반감기가 섞인다.
