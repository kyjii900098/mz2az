---
title: SceneTrip DB 스키마 (DBML)
type: design
status: draft
updated: 2026-07-31
source:
  - "[[MZ2AZ-111 SceneTrip DB 스키마]]"
---

> [!summary] [[MZ2AZ-111 SceneTrip DB 스키마]] 의 DBML 표현. 아래 블록을 [dbdiagram.io](https://dbdiagram.io) 에 붙여넣으면 ERD가 나온다.
> `Export to PostgreSQL` 로 DDL도 바로 뽑을 수 있다.

## ERD

![[scenetrip.svg]]

작게 보이면 [[scenetrip.svg]] 로 파일을 직접 열면 된다 — 벡터라 확대해도 깨지지 않는다. 아래 DBML 블록을 dbdiagram.io에 다시 붙여넣으면 갱신본을 받을 수 있다(`Export to SVG` → `assets/scenetrip.svg` 덮어쓰기).

컬럼의 의미·설계 근거는 [[MZ2AZ-111 SceneTrip DB 스키마]] 를 볼 것. 이 문서는 도식·DDL 생성용이다.

## DBML

```dbml
// ─────────────────────────────────────────────
//  SceneTrip — 1계층(직접 수집 촬영지) 스키마
// ─────────────────────────────────────────────

Enum lang {
  ko
  en
  ja
  "zh-Hant" [note: '번체. 대만·홍콩. 간체(zh-Hans)와 구분']
}

Enum content_category {
  drama
  movie
  variety
  kpop
}

Enum role_type {
  actor
  director
}

Enum trans_status {
  machine
  reviewed
  human
}

// search_term 과 user_event 는 값이 같아도 별개 Enum이다.
// 서로 참조하지 않고 늘어날 방향이 다르다 —
// search 쪽은 region·role(검색 대상), event 쪽은 route·review(행동 대상).
Enum search_entity_type {
  place
  content
  person
}

Enum event_entity_type {
  place
  content
  person
}

Enum event_type {
  impression
  search
  click
  save
  route_add
  review
}


// ───────────── 장소 ─────────────

Table place {
  id bigserial [pk]
  type varchar [note: 'place_type 코드값']
  geom geography [not null, note: 'Point,4326 · 위경도']
  naver_place_url varchar [unique, note: 'map.naver.com/p/entry/place/{id} · dedupe 1차 키']
  popularity_score decimal [default: 0, note: '핀 우선순위 · 배치 계산']
  created_at timestamptz
  updated_at timestamptz

  Indexes {
    geom [type: gist]
    (popularity_score, id) [note: '실제로는 DESC, DESC']
  }

  Note: '언어중립 값만 보관. 이름·주소는 place_i18n'
}

Table place_i18n {
  place_id bigint
  lang lang
  name varchar [not null]
  address varchar
  description text [note: '장소 자체의 설명. 작품별 장면 설명은 place_content_i18n']
  trans_status trans_status

  Indexes {
    (place_id, lang) [pk]
  }
}

Table place_image {
  id bigserial [pk]
  place_id bigint [not null]
  url varchar [not null]
  sort_order int [default: 0, note: '10,20,30 처럼 띄워 넣어 중간 삽입 대비']
  created_at timestamptz

  Indexes {
    (place_id, sort_order)
  }

  Note: '''
  장소 사진만. 작품(place_content)과 엮지 않음.
  대표 이미지 = sort_order 첫 번째 (별도 컬럼 없음).
  리뷰 사진은 review_image 로 분리 (생명주기·신고처리·화면 구분이 다름).
  '''
}

Table place_alias {
  id bigserial [pk]
  place_id bigint [not null]
  alias varchar [not null]
  lang lang [null, note: '한글ko/가나ja/한자zh-Hant/라틴NULL — 문자 범위로 자동 판별']

  Note: 'dedupe로 병합된 표기들을 보존. alias_type 은 두지 않음 (실데이터가 분류에 안 담김)'
}


// ───────────── 작품 ─────────────

Table content {
  id bigserial [pk]
  category content_category [not null]
  broadcaster varchar
  poster_url varchar
  popularity_score decimal [default: 0, note: '정렬값. 적재 시 직접 계산해 입력']
  created_at timestamptz
  updated_at timestamptz

  Indexes {
    (popularity_score, id) [note: '실제로는 DESC, DESC']
  }

  Note: '''
  수집 원본 지표는 컬럼으로 두지 않는다.
  - score_total, en_views_12m, audience_acc, rank, is_top100
      → 적재 시 popularity_score 계산에만 쓰고 버림
  - wikidata_qid → 앱이 읽지 않음. 값은 01_Raw 작품마스터 CSV에 보존됨
  - is_featured  → 점수를 직접 입력하므로 덮어쓸 자동 계산이 없음
  - air_period, air_status → 방영 정보는 두지 않음. air_status 는 476행 전량
      '방영종료'(분산 0) + 날짜 파생값이라 낡고, air_period 는 앱이 읽지 않음
  '''
}

Table content_i18n {
  content_id bigint
  lang lang
  title varchar [not null]
  description text
  trans_status trans_status

  Indexes {
    (content_id, lang) [pk]
  }
}

Table content_alias {
  id bigserial [pk]
  content_id bigint [not null]
  alias varchar [not null]
  lang lang [null, note: 'place_alias 와 동일 판별 규칙']

  Note: 'title_aliases 를 ; 로 분리 (96.8% 채움, 이미 다국어). alias_type 은 두지 않음'
}


// ───────────── 인물 ─────────────

Table person {
  id bigserial [pk]
  created_at timestamptz

  Note: '사람 자체에는 직군을 붙이지 않음. 배우/감독 구분은 content_cast.role_type'
}

Table person_i18n {
  person_id bigint
  lang lang
  name varchar [not null]

  Indexes {
    (person_id, lang) [pk]
  }
}

Table content_cast {
  content_id bigint
  person_id bigint
  role_type role_type [not null, note: '이 작품에서의 직군 — 배우/감독']
  sort_order int [note: 'title_cast 나열 순서 = 비중. role_type 별로 따로 매김']

  Indexes {
    (content_id, person_id, role_type) [pk]
    person_id [note: '배우 → 작품 역방향']
  }

  Note: '''
  작품 단위 출연진만. 장면별 출연진은 저장하지 않음.
  is_main 은 sort_order <= 2 로 계산되므로 두지 않음.

  role_type 을 person 이 아니라 여기 둔 이유 — 겸업(하정우·정우성 등).
  역할은 사람의 속성이 아니라 사람과 작품 사이의 속성.
  PK에 role_type 이 들어간 것도 한 작품에서 연출·주연을 겸하는 경우 때문.
  현재 수집분은 전량 actor (감독 정보가 CSV에 없음. 별도 수집 필요).

  role_name(배역명)은 수집 데이터에 없어 전량 NULL이 되므로 두지 않음 —
  role_type(직군)과는 다른 값. 배역명 검색을 지원할 때
  search_term 소스·다국어 테이블과 함께 설계.
  '''
}


// ───────────── 장소 × 작품 (핵심 연결) ─────────────

Table place_content {
  id bigserial [pk]
  place_id bigint [not null]
  content_id bigint [not null]
  updated_at timestamptz

  Indexes {
    (place_id, content_id) [unique]
    place_id
    content_id
  }

  Note: '''
  수집 CSV 한 행이 여기에 해당. N:M을 흡수.
  출처·수집 메타(source_url, scene_source, scene_source_url, collected_by)는 두지 않음 —
  앱이 읽지 않고 값은 01_Raw 수집 CSV에 보존됨.
  '''
}

Table place_content_i18n {
  place_content_id bigint
  lang lang
  relation_description text
  trans_status trans_status

  Indexes {
    (place_content_id, lang) [pk]
  }

  Note: '현재 수집분은 실질적으로 비어 있음(실제 설명 60건). 전량 채우는 것을 전제한 설계'
}


// ───────────── 검색 · 로그 ─────────────

Table search_term {
  term_norm varchar [note: '소문자 + 공백·특수문자 제거']
  term_display varchar
  entity_type search_entity_type
  entity_id bigint
  lang lang [null]
  weight int [note: '기본가중치 + popularity_score/10']

  Indexes {
    term_norm [type: btree, note: 'text_pattern_ops · 앞글자 일치']
    term_norm [type: gin, note: 'gin_trgm_ops · 부분·유사 일치']
  }

  Note: '''
  MATERIALIZED VIEW (테이블 아님).
  place_i18n · place_alias · content_i18n · content_alias · person_i18n 5곳 UNION ALL.
  entity_id 는 다형 참조라 FK 없음.
  적재 후 REFRESH MATERIALIZED VIEW CONCURRENTLY.
  '''
}

Table user_event {
  id bigserial [pk]
  user_id bigint [null, note: '비로그인 허용']
  session_id varchar
  event_type event_type
  entity_type event_entity_type [null, note: '대상 없는 이벤트는 NULL (search)']
  entity_id bigint [null]
  query varchar [null, note: 'search 전용']
  position int [null, note: '목록 순번 · CTR 보정']
  created_at timestamptz

  Indexes {
    (entity_type, entity_id, created_at) [note: '집계 배치']
  }

  Note: 'MVP2. impression·position 은 소급 수집 불가 — 처음부터 포함할 것'
}

Table saved_place {
  user_id bigint
  place_id bigint
  source_content_id bigint [null, note: '어떤 작품 보다가 찜했는지 (선택)']
  created_at timestamptz

  Indexes {
    (user_id, place_id) [pk]
  }

  Note: '''
  찜(MVP2). place 기준 — place_content(성지) 기준이 아님.
  route_add 가 물리적 장소 단위라 찜도 맞춰야 같은 장소 중복 저장을 피함.
  user_event 와 별도: 이쪽은 토글 가능한 현재 상태, user_event 는 append-only 로그.
  '''
}


// ───────────── 관계 ─────────────

Ref: place_i18n.place_id > place.id
Ref: place_alias.place_id > place.id
Ref: place_image.place_id > place.id

Ref: content_i18n.content_id > content.id
Ref: content_alias.content_id > content.id

Ref: person_i18n.person_id > person.id

Ref: content_cast.content_id > content.id
Ref: content_cast.person_id > person.id

Ref: place_content.place_id > place.id
Ref: place_content.content_id > content.id
Ref: place_content_i18n.place_content_id > place_content.id

Ref: saved_place.place_id > place.id
Ref: saved_place.source_content_id > content.id


// ───────────── 그룹 ─────────────

TableGroup "핵심" {
  place
  content
  person
  place_content
  content_cast
  place_image
}

TableGroup "다국어" {
  place_i18n
  content_i18n
  person_i18n
  place_content_i18n
}

TableGroup "별칭" {
  place_alias
  content_alias
}

TableGroup "검색·로그" {
  search_term
  user_event
  saved_place
}
```

---

## DBML로 옮기면서 생긴 차이

| 항목 | 문서 | DBML |
|---|---|---|
| `geom` | `GEOGRAPHY(Point,4326)` | `geography` — DBML이 괄호·쉼표 타입을 파싱 못 해 note로 뺌 |
| 정렬 인덱스 | `popularity_score DESC, id DESC` | DBML에 `DESC` 문법이 없어 note로 표기. **DDL 생성 후 직접 붙일 것** |
| `search_term` | MATERIALIZED VIEW | DBML에 뷰 개념이 없어 Table로 표현. **DDL 그대로 쓰면 안 됨** |
| GIN/GiST | 인덱스 종류 | DBML `[type: gin]` 지원. 단 연산자 클래스(`gin_trgm_ops`)는 미지원 → note |
| `entity_type` | `search_term` · `user_event` 각각 `TEXT` (독립) | Enum으로 표현하되 `search_entity_type` / `event_entity_type` 로 **분리**. 값은 같지만 두 칸은 서로 참조하지 않고 늘어날 방향이 다르다(검색 쪽 `region`·`role`, 로그 쪽 `route`·`review`). 하나로 공유하면 한쪽에 값을 추가할 때 다른 쪽에도 허용되고, PostgreSQL Enum은 값 제거가 어렵다 |

`Export to PostgreSQL` 로 뽑은 DDL은 위 3가지를 손봐야 실행된다.

## 아직 DBML에 없는 것 (결정 대기)

| 항목                     | 상태                                                                              |
| ---------------------- | ------------------------------------------------------------------------------- |
| `search_term.subtitle` | 동명이인(&ldquo;한강&rdquo;이 장소·작품 둘 다) 구별용으로 제안했으나 추가 확정 안 됨                         |
| `user_event.surface`   | 어느 화면(검색/지도/상세)에서 난 이벤트인지 구분용으로 제안했으나 추가 확정 안 됨                                 |
| `scene_image`          | 작품별 장면 스틸 — [[MZ2AZ-111 SceneTrip DB 스키마]] §`place_image` 아래 메모 참조. 저작권 문제로 미도입 |
| `route` / `route_item` | 루트(코스) 기능. MVP1 8/10~8/14 주차 예정이나 아직 미설계                                        |
| 사용자 테이블 (`app_user` 등) | `saved_place.user_id` · `user_event.user_id` 가 참조할 대상이 스키마에 없음                  |
