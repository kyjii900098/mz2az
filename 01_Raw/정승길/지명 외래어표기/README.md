# 지명 외래어표기 — 한국 지명의 영문 표기 이표기 데이터

> 외국인이 영어로 입력한 한국 지명을 실제 장소에 붙이려면, 한 장소가 몇 가지 철자로
> 쓰이는지 알아야 한다. 그 이표기(異表記) 목록을 공개 데이터에서 모은 결과다.
> 작업자: 정승길 (Claude Code 보조) · 수집일 2026-08-08
> 관련 문서: [[01_Raw/정승길/README]]

## 1. 왜 필요한가

대한민국 정부는 2000년에 로마자 표기법을 바꿨다. 그전까지는 **매큔-라이샤워
표기법**(McCune-Reischauer, 이하 MR)을 변형해 썼고, 2000년부터는 **국어의 로마자
표기법**(Revised Romanization, 이하 RR)을 쓴다. 부산이 `Pusan` 에서 `Busan` 으로
바뀐 것이 이 개정 때문이다.

문제는 **바뀐 뒤에도 옛 표기가 사라지지 않았다는 점** 이다. 외국 지도·여행서·논문·
위키백과·구글 검색에는 여전히 `Pusan`, `Cheju`, `Kyongju` 가 남아 있다. SceneTrip 의
사용자는 외국인이므로, 그들이 보고 온 자료에 적힌 철자를 그대로 입력할 가능성이 높다.
검색창에 `Kyongju` 를 친 사용자에게 "결과 없음"을 보여주면 그 사용자는 앱을 닫는다.

그래서 **"한 장소 ↔ 그 장소를 가리키는 모든 영문 철자"** 의 대응표가 필요하다.
이 폴더는 그 표를 공개 데이터로 만든 것이다.

## 2. 어떤 종류의 표기 차이가 있는가

같은 장소가 여러 철자로 쓰이는 이유는 하나가 아니다. 원인별로 나누면 다섯 가지다.

| # | 갈래 | 예 | 이 데이터에 있는가 |
| --- | --- | --- | --- |
| 1 | MR ↔ RR 표기법 개정 | 부산 = `Pusan` / `Busan`, 속초 = `Sokch'o` / `Sokcho` | 있음 (22,942건) |
| 2 | 일제강점기 일본어 표기 | 설악산 = `Setsugaku-zan`, 수원 = `Suigen` | 있음 |
| 3 | 행정구역 접미사 처리 | `Busan` / `Busan-si` / `Busan-gwangyeoksi` | 있음 |
| 4 | 의역 대 음역 | 경복궁 = `Gyeongbokgung` / `Gyeongbok Palace` | 있음 (Wikidata 쪽) |
| 5 | 개칭 이력 | 경원대역 → 가천대역, 안압지 → 월지 | 있음 (Wikidata 쪽) |

1번이 사용자가 말한 "Pusan / Busan 혼재"에 해당하고 분량도 가장 많다. 다만 실제 검색
실패는 4번과 5번에서도 많이 난다. 외국인이 `Gyeongbok Palace` 라고 치는 일은 흔한데,
우리 DB에 `Gyeongbokgung` 만 있으면 못 찾기 때문이다.

## 3. 무엇을 받았는가

두 개의 공개 데이터를 받았고, 둘은 서로 다른 구멍을 메운다.

| 데이터 | 출처 | 라이선스 | 받은 것 | 스크립트 |
| --- | --- | --- | --- | --- |
| 지명 이표기 | [GeoNames](https://download.geonames.org/export/dump/) KR 덤프 | CC BY 4.0 | 지명 144,735곳, 이표기 중 로마자 50,467건 (35,705곳) | `collect_geonames_variants.py` |
| 장소 별칭 | [Wikidata](https://query.wikidata.org/) SPARQL | CC0 | 장소 3,400곳, 영문 별칭 4,956건 | `collect_wikidata_aliases.py` |

GeoNames 는 **자연지명과 행정지명에 강하다.** 산·하천·섬·읍면동까지 MR 표기가 반달표
(`ŏ`, `ŭ`)와 어깻점(`'`)을 살린 채로 들어 있다. 반면 궁·박물관 같은 관광 시설의
별칭은 거의 없다.

Wikidata 는 그 반대다. **관광 시설과 개칭 이력에 강하다.** 경복궁 항목에는
`Gyeongbok Palace`, `Gyeongbokgung Palace`, `Kyŏngbok Palace` 가 모두 별칭으로 달려
있고, 역 이름이 바뀐 경우 옛 이름이 남아 있다. 촬영지는 대부분 관광 시설이므로
SceneTrip 에는 이쪽이 오히려 더 중요할 수 있다.

두 소스를 합쳐야 하는 이유가 여기 있다. 하나만 쓰면 절반이 빈다.

## 4. 실제로 어떻게 생겼는가

GeoNames 에서 뽑은 대표 사례다. 오른쪽 열이 전부 같은 장소를 가리키는 다른 철자다.

| 한글 | 현행 표기(RR) | 이표기 |
| --- | --- | --- |
| 부산 | Busan | Pusan, Fusan, Fuzan, Fousan, Husan, Busan-si, Busan-gwangyeoksi |
| 광주 | Gwangju | Kwangju, Kwangju-jikhalsi, Gwangju-si |
| 대구 | Daegu | Taegu, Daegu-si, Daegu-gwangyeoksi |
| 설악산 | Seoraksan | Sŏraksan, Sŏrak-san, Soraku San, Setsugaku-zan, Setsugaku-san |
| 한라산 | Hallasan | Halla Mountain, Han-ra-san, Hanna San, Kanra-san, Mount Auckland |
| 전주 | Jeonju | Chŏnju, Chunju, Jeon Ju, Chenju, Tjyen-tjyou |
| 춘천 | Chuncheon | Ch'unch'ŏn, Shunsen, Chhun-chhen |
| 강릉 | Gangneung | Kangnŭng, Kang-neung, Gangreung, Kōryō |
| 속초 | Sokcho | Sokch'o, Sogcho |
| 통영 | Tongyeong | T'ongyŏng, Chungmoo, Ch'ungmu |
| 독도 | Dokdo | Tok-to, Dog Do |
| 보성 | Boseong | Posung, Hōjō, Boseong-guncheong |

`Gangneung` 의 이표기에 `Gangreung` 이 있는 것을 눈여겨볼 만하다. 이건 MR 도 RR 도
아닌 **그냥 흔한 오기(誤記)** 인데, 실제로 통용되니까 데이터에 들어와 있다. 검색
매칭 관점에서는 이런 항목이 가장 값지다. 규칙으로는 만들어 낼 수 없고 실사용 기록에서만
나오기 때문이다.

## 5. 파일 배치

```
01_Raw/정승길/지명 외래어표기/
├── README.md                      ← 이 파일
├── collect_geonames_variants.py   ← GeoNames 수집·정리
├── collect_wikidata_aliases.py    ← Wikidata 수집·정리
└── data/
    ├── romanization_variants.csv  ← 결과물 1. 이표기 표 (50,467행)
    ├── wikidata_aliases.csv       ← 결과물 2. 별칭 표 (4,956행)
    ├── geonames_kr_raw.tsv        ← 원본 덤프 (git 제외)
    └── geonames_kr_altnames_raw.tsv ← 원본 덤프 (git 제외)
```

원본 덤프 두 개는 합쳐서 33MB 라 볼트 `.gitignore` 에 넣었다. 스크립트를 다시 돌리면
자동으로 내려받으므로 git 이력에 둘 이유가 없다고 판단했다. **Dropbox 로는 동기화되지만
다른 기기에서 `git clone` 만 하면 이 두 파일이 없다.** 그때는 스크립트를 한 번 돌리면
된다.

### `romanization_variants.csv` 의 열

| 열 | 뜻 |
| --- | --- |
| `geonameid` | GeoNames 의 장소 고유 번호. 같은 장소를 묶는 열쇠다 |
| `official_rr` | GeoNames 가 대표로 삼는 현행 표기 |
| `hangul` | 한글 표기 (있는 경우만) |
| `feature_class` / `feature_code` | 장소 종류. `P`=거주지, `T`=산, `H`=수계, `S`=시설, `A`=행정구역 |
| `latitude` / `longitude` | 좌표. 동명이지(同名異地)를 좌표로 갈라낼 때 쓴다 |
| `variant` | 이표기 하나 |
| `variant_type` | 어느 갈래로 보이는지 — `MR` / `spacing_hyphen` / `other_variant` |
| `is_historic` | GeoNames 가 역사적 명칭으로 표시한 것 |
| `same_name_diff_spelling` | 반달표·하이픈만 빼면 현행 표기와 같아지는 경우 |

`variant_type` 은 스크립트가 글자 모양으로 어림잡은 값이다. 반달표나 어깻점이 있으면
MR 로 본다. **정확한 분류가 아니므로 통계에 쓰지 말고 훑어볼 때만 참고한다.**

## 6. 주의할 점

이 데이터를 그대로 검색 인덱스에 넣기 전에 걸러야 할 것이 넷 있다.

1. **동명이지가 섞인다.** `Sinchon` 만 해도 전국에 수십 곳이다. 이표기로 검색어를
   넓히면 오히려 엉뚱한 곳이 걸릴 수 있다. 좌표나 상위 행정구역으로 후보를 좁혀야 한다.
2. **한글 열이 비거나 로마자로 채워진 행이 있다.** GeoNames 의 `ko` 언어 이표기에
   로마자가 들어가 있는 경우가 있어서, 위 예시 표에도 한글 대신 `Kyŏngju-gun` 같은
   값이 나온 항목이 있었다. 한글이 꼭 필요하면 다른 소스로 채워야 한다.
3. **일제강점기 일본어 표기를 그대로 노출하면 안 된다.** `Suigen`(수원),
   `Keishū`(경주) 같은 값은 검색 매칭용으로만 쓰고 화면에 보여주지 않는다.
   NGA 조사에서 한국 지명의 약 1% 가 실제로는 쓰이지 않는 일본어 지명이라는 지적도 있었다.
4. **촬영지 POI 는 여전히 부족하다.** 감천문화마을·북촌은 마을 단위로 잡히지만, 개별
   카페나 촬영 세트는 어느 소스에도 없다. 그건 4장에서 정리한 대로 별도 수집이 필요하다.

## 7. 아직 안 받은 것

찾긴 했지만 이번에 받지 않은 소스다. 필요해지면 여기서부터 시작하면 된다.

| 소스 | 무엇이 있는가 | 왜 미뤘는가 |
| --- | --- | --- |
| [NGA GEOnet Names Server](https://geonames.nga.mil/) | 미국 정부 공인 지명 DB. 승인 표기와 변형 표기를 `name_type` 열로 구분해 준다 | GeoNames 가 사실상 이 DB 에서 파생됐고, 다운로드 링크가 동적 페이지라 자동화에 손이 더 든다 |
| [한국관광공사 TourAPI 영문](https://www.data.go.kr/data/15101753/openapi.do) | 관광지 약 8만 건의 공식 영문 명칭 | API 키 발급이 필요하다. 이표기가 아니라 정답 표기 한 개만 주므로 4장 갈래를 메우진 못한다 |
| [행정안전부 영문도로명주소DB](https://www.data.go.kr/data/15050414/fileData.do) | 도로명·행정구역의 공식 영문 표기 전체 | 이표기가 아니라 정답 표기만 준다. 주소 정규화가 필요해지면 그때 받는다 |
| [국립국어원 어문규범 용례 API](https://www.data.go.kr/data/15112892/openapi.do) | 로마자 표기 규범의 공식 용례 | 규범 판정용이라 실사용 변형은 없다. 표기 규칙을 코드로 옮길 때 근거로 쓸 만하다 |
| OpenStreetMap `alt_name` / `old_name` 태그 | 지역민이 직접 단 별칭·옛 이름 | 값지지만 Overpass 질의와 정제에 별도 작업이 든다 |

이 중 SceneTrip 에 가장 먼저 필요해질 것은 TourAPI 다. 촬영지가 관광지와 많이 겹치는데,
지금 두 소스로는 관광지의 공식 영문 명칭조차 절반쯤만 채워지기 때문이다.

## 8. 다시 받으려면

```bash
cd "01_Raw/정승길/지명 외래어표기"
python3 collect_geonames_variants.py   # data/ 에 원본이 있으면 내려받기를 건너뛴다
python3 collect_wikidata_aliases.py
```

두 스크립트 모두 외부 라이브러리 없이 파이썬 표준 라이브러리만 쓴다. GeoNames 덤프는
날마다 갱신되므로, 다시 받으려면 `data/` 의 `*_raw.tsv` 를 지우고 돌리면 된다.
Wikidata 는 질의 서버가 가끔 502 를 내는데 스크립트가 세 번까지 다시 시도한다.
