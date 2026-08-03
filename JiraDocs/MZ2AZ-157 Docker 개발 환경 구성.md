---
title: "Docker 개발 환경 구성"
type: jiradoc
status: 진행 중
updated: 2026-08-04
---

JIRA:MZ2AZ-178
JIRA:MZ2AZ-179

| 티켓 | 제목 | 담당 | 상태 |
| --- | --- | --- | --- |
| [MZ2AZ-178](https://mz2az.atlassian.net/browse/MZ2AZ-178) | Docker Compose로 프로젝트 전체 컨테이너 정의 | 정권호 | ✅ 완료 |
| [MZ2AZ-179](https://mz2az.atlassian.net/browse/MZ2AZ-179) | 팀원별 로컬 환경 구성 가이드 | 정권호 | ✅ 완료 |

> [!summary]
> 팀원 세 명이 각자 노트북에서 같은 개발 환경을 띄울 수 있도록 도커 구성을 만들고 설치 가이드를 정리했다.
> 백엔드 서버(Spring Boot)와 데이터베이스(PostgreSQL + PostGIS)를 컨테이너 두 개로 정의했고, 명령 한 줄로 둘을 함께 띄운다.
> **프론트 담당자는 Docker Desktop 만 설치하면 된다** — Java 를 깔지 않아도 서버가 뜬다.
> 근거 회의: [[(2주차)2026년 8월 3일 Sprint Planning]] — 3-1 기술 스택에서 *"환경: Docker + Docker Compose, 프로젝트 전체 단위로 컨테이너화"* 로 확정했다.
> 코드 위치: `github.com/mz2az/SceneTrip` (로컬 경로 `~/SceneTrip`)

---

## MZ2AZ-178 Docker Compose로 프로젝트 전체 컨테이너 정의

**파일** — 결과물은 볼트가 아니라 코드 저장소(`mz2az/SceneTrip`)에 있다. 근거 회의록은 [[(2주차)2026년 8월 3일 Sprint Planning]] 이다.

### 만든 것

| 경로 | 역할 |
| --- | --- |
| `docker-compose.yml` | 컨테이너 두 개(DB·백엔드)를 한 번에 켜고 끄는 정의 |
| `.env.example` | 접속 계정·포트 같은 환경별 설정값의 견본 |
| `.gitignore` | 실제 설정값이 든 `.env` 와 빌드 산출물을 깃에서 제외 |
| `backend/Dockerfile` | 백엔드 서버를 이미지로 굽는 방법 |
| `backend/build.gradle.kts` | 라이브러리 목록과 자바 버전 |
| `backend/src/main/resources/application.yml` | 서버 설정 (DB 주소 등) |
| `backend/src/main/resources/db/migration/V1__enable_extensions.sql` | PostGIS 확장을 켜는 첫 마이그레이션 |
| `backend/src/main/java/.../common/PingController.java` | 세팅 확인용 엔드포인트 |
| `README.md` | 저장소 구조와 3줄 실행법 |

### 컨테이너 구성

| 서비스 | 이미지 | 포트 | 역할 |
| --- | --- | --- | --- |
| `db` | `imresamu/postgis:17-3.5` | 5432 | PostgreSQL 17.6 + PostGIS 3.5.3 |
| `backend` | `backend/Dockerfile` 로 직접 빌드 | 8080 | Spring Boot 4.1 서버 |

두 컨테이너는 compose 가 만든 내부 네트워크로 연결된다. 그래서 백엔드는 DB 주소를 `localhost` 가 아니라 서비스 이름인 `db` 로 부른다.

### 확정한 스택

| 항목 | 값 | 비고 |
| --- | --- | --- |
| 프레임워크 | Spring Boot **4.1.0** | |
| 자바 | **21** (Temurin 21.0.11) | LTS |
| 빌드 도구 | **Gradle 9.5.1**, Kotlin DSL | `build.gradle.kts` |
| DB | PostgreSQL **17.6** + PostGIS **3.5.3** | |
| 마이그레이션 | **Flyway** | |
| 도커 | Engine 29.6.2 · Compose v5.3.1 | Docker Desktop |

### 결정과 이유

**① DB 이미지로 공식 `postgis/postgis` 를 쓰지 않았다.**
공식 이미지는 **arm64(애플 실리콘) 빌드를 내지 않는다.** 태그를 전부 확인했는데 arm64 를 지원하는 것이 하나도 없었다. 팀 노트북이 M 시리즈 맥이면 그 이미지는 에뮬레이션으로 돌아 DB 가 눈에 띄게 느려진다. `imresamu/postgis` 는 PostGIS 도커 이미지 메인테이너가 내는 멀티아키텍처 빌드라 arm64 와 amd64 를 모두 지원한다. 실제로 컨테이너 안에서 `aarch64` 로 도는 것을 확인했다.

**② DB 에 준비 상태 검사(healthcheck)를 붙였다.**
DB 컨테이너가 "실행 중"인 것과 "접속을 받을 준비가 된" 것은 다르다. 이 검사가 없으면 백엔드가 준비되기 전에 접속을 시도했다가 죽는다. compose 가 DB 의 준비 완료를 확인한 뒤에 백엔드를 띄우도록 순서를 걸었다.

**③ 백엔드 이미지를 2단계로 굽는다.**
1단계에서는 JDK(자바 개발 도구)가 든 이미지로 실행 파일(jar)을 만들고, 2단계에서는 JRE(자바 실행기)만 있는 가벼운 이미지에 그 jar 만 옮긴다. 빌드 도구를 최종 이미지에서 빼기 위함이다. 결과 이미지는 **580MB** 다. 또 이 방식 덕분에 **팀원 노트북에 자바가 없어도 서버가 뜬다.**

**④ 라이브러리 캐시를 빌드끼리 공유한다.**
`Dockerfile` 에 `--mount=type=cache` 를 걸었다. 이게 없으면 소스를 한 줄만 고쳐도 라이브러리를 전부 다시 내려받는다.

**⑤ 설정값을 `.env` 로 분리하고 깃에서 제외했다.**
지금 들어 있는 값은 로컬 개발용 계정뿐이라 굳이 숨길 것이 없다. 그런데 곧 네이버 지도 키와 TMDB 키가 들어온다. 그때 가서 규칙을 바꾸면 이미 깃 기록에 키가 남으므로, 처음부터 분리해 두었다.

**⑥ JPA 가 테이블을 만들지 못하게 막았다.**
`application.yml` 에 `ddl-auto: validate` 를 넣었다. 이 설정은 엔티티(자바 클래스)와 실제 테이블이 다르면 서버를 아예 띄우지 않는다. JPA 에게 테이블을 만들게 하면 팀원 세 명의 DB 가 조금씩 다르게 갈라지고, [[MZ2AZ-111 SceneTrip DB 스키마]] 로 설계해 둔 구조가 무의미해진다. **스키마의 정답은 Flyway SQL 하나로 둔다.**

> [!note] Flyway 가 하는 일
> Flyway 는 **DB 구조 변경을 버전으로 관리하는 도구** 다. `backend/src/main/resources/db/migration/` 안의 SQL 파일을 번호 순서대로 실행한다.
> 서버가 뜰 때 Flyway 가 `flyway_schema_history` 표를 보고 어디까지 적용했는지 확인한 뒤, 아직 안 돌린 파일만 실행한다. 그래서 팀원은 `git pull` 하고 컨테이너를 다시 띄우기만 하면 스키마가 최신이 된다.
> - 파일 이름은 `V{번호}__{설명}.sql` 이고 밑줄이 **두 개** 다. 하나면 인식하지 못한다.
> - **이미 적용된 파일은 고치면 안 된다.** Flyway 가 파일 내용의 검사값을 저장해 두고, 내용이 바뀌면 서버 기동을 거부한다. 잘못 짰으면 다음 번호로 새 파일을 만들어 바로잡는다.

### PostGIS 는 별도 DB 가 아니라 PostgreSQL 확장이다

이미지 이름이 `postgis` 라서 다른 데이터베이스처럼 보이지만, 안에서 도는 것은 그냥 PostgreSQL 17.6 이다. 확장을 쓰려면 두 단계가 필요하고, 둘은 서로 다른 층위의 작업이다.

| 단계 | 하는 일 | 어디서 | 누가 처리하나 |
| --- | --- | --- | --- |
| 1. 설치 | PostGIS 실행 파일을 서버에 깐다 | 운영체제 | **도커 이미지** 가 미리 해 둠 |
| 2. 활성화 | 특정 데이터베이스에서 기능을 켠다 | SQL (`CREATE EXTENSION`) | **Flyway `V1`** |

공식 `postgres:17` 이미지에는 1단계가 되어 있지 않다. 그 이미지를 쓰면 컨테이너를 띄울 때마다 안에 들어가 설치해야 하고, 컨테이너를 지우면 사라진다. 그래서 1단계까지 끝나 있는 `postgis` 이미지를 쓴다.

2단계를 Flyway 에 남긴 이유는 **활성화가 데이터베이스마다 따로** 이기 때문이다. 이미지가 기본 데이터베이스에는 자동으로 켜 주지만, 나중에 AWS RDS 로 옮기면 그쪽은 켜 주지 않는다. Flyway 에 적어 두면 어느 환경에서든 똑같이 동작한다.

### 검증 결과

실제로 띄워서 아래를 모두 확인했다.

| 확인 항목 | 결과 |
| --- | --- |
| 컨테이너 기동 | `db` 정상(healthy) · `backend` 정상 |
| 백엔드 응답 `GET /api/ping` | `{"status":"ok","service":"scenetrip-backend", ...}` |
| DB 연결 `GET /actuator/health` | `db: UP` (PostgreSQL) |
| Flyway 적용 | `flyway_schema_history` 에 `V1 enable extensions · success=t` |
| PostGIS 활성화 | `3.5 USE_GEOS=1 USE_PROJ=1 USE_STATS=1` |
| 아키텍처 | `PostgreSQL 17.6 on aarch64` — 에뮬레이션 아님 |
| 시간대 | 응답 시각이 `+09:00` |
| 로컬 테스트 | `./gradlew test` 통과 |

> [!question] 확인 필요 — pgvector 가 이 이미지에 없다
> `pg_available_extensions` 를 조회했더니 `vector` 가 없었다. 아키텍처 문서([[아키텍처 5계층 구조]])의 RAG 검색은 pgvector 를 전제로 한다.
> MVP1 범위에는 벡터 검색이 없으므로 지금은 문제가 되지 않는다. **MVP2 에서 RAG 를 붙일 때** 확장이 더 들어 있는 태그(`imresamu/postgis:17-3.5-bundle0`)로 바꿀지, 우리 이미지를 직접 만들지 정해야 한다.
>
> **지도 검색과는 무관하다.** 좌표·거리·영역은 PostGIS 가 처리하고 pgvector 는 문장의 의미를 다루는 별개의 확장이다. 화면 기준 촬영지 검색은 지금 구성으로 전부 된다.

---

## MZ2AZ-179 팀원별 로컬 환경 구성 가이드

**파일** — 이 문서가 가이드 본문이다. 저장소 안의 `README.md` 에는 3줄 요약만 두었다.

> [!tip] 이 절만 보면 된다
> 아래 순서대로 하면 각자 노트북에서 백엔드 서버와 DB 가 뜬다. 막히면 맨 아래 문제 해결 표를 볼 것.

### 역할별로 필요한 것

| 담당 | Docker Desktop | JDK 21 | 이유 |
| --- | --- | --- | --- |
| 정승길 (프론트) | 필요 | 불필요 | 서버를 쓰기만 하므로 컨테이너로 띄우면 된다 |
| 김태환 (데이터·AI) | 필요 | 불필요 | 위와 같다 |
| 정권호 (백엔드) | 필요 | 필요 | 코드를 고치며 IDE 에서 바로 실행해야 한다 |

### 1단계 · 설치

터미널(Terminal.app)을 **직접 열어서** 아래를 실행한다.

```bash
# 프론트·AI 담당은 이 줄만
brew install --cask docker-desktop

# 백엔드 담당은 자바까지
brew install --cask docker-desktop temurin@21
```

> [!warning] Claude Code 나 편집기 터미널에서 실행하면 실패한다
> 위 명령은 관리자 권한이 필요한데(`/usr/local/bin`, `/Library/Java` 에 파일을 넣는다), 진짜 터미널이 아니면 비밀번호를 물어보지 못하고 `sudo: a terminal is required to read the password` 로 끝난다. **반드시 Terminal.app 에서 실행할 것.**

설치가 끝나면 **Docker Desktop 앱을 한 번 실행한다.** 첫 실행에서 약관 동의와 권한 승인을 물어본다. 상단 메뉴 막대에 고래 아이콘이 뜨면 준비된 것이다.

> [!note] 왜 앱을 꼭 실행해야 하나
> `brew` 는 명령어만 깔아 준다. 컨테이너를 실제로 돌리는 프로그램(도커 데몬)과 `docker compose` 명령은 앱이 처음 켜질 때 설치된다. 앱을 안 켜면 `docker compose` 가 `unknown command` 로 나온다.

### 2단계 · 코드 받기

```bash
git clone https://github.com/mz2az/SceneTrip.git
cd SceneTrip
cp .env.example .env
```

`.env` 는 각자 노트북에만 두는 설정 파일이라 깃에 올라가지 않는다. 그래서 클론한 뒤 직접 한 번 복사해야 한다.

### 3단계 · 실행

```bash
docker compose up -d --build
```

`docker-compose.yml` 이 있는 `SceneTrip` 폴더 안에서 실행해야 한다. 이 명령은 현재 폴더에서 그 파일을 찾기 때문이다.

처음 한 번은 이미지를 내려받고 서버를 빌드하느라 **3~5분** 걸린다. 두 번째부터는 수십 초로 줄어든다.

### 4단계 · 됐는지 확인

```bash
curl http://localhost:8080/api/ping
```

아래처럼 나오면 성공이다.

```json
{"status":"ok","service":"scenetrip-backend","time":"2026-08-04T00:37:40+09:00"}
```

DB 까지 붙었는지는 이쪽으로 확인한다. `"db":{"status":"UP"}` 이 보이면 된다.

```bash
curl http://localhost:8080/actuator/health
```

### 자주 쓰는 명령

| 하고 싶은 것 | 명령 |
| --- | --- |
| 띄우기 | `docker compose up -d` |
| 코드 고친 뒤 다시 띄우기 | `docker compose up -d --build` |
| 끄기 (데이터는 남음) | `docker compose down` |
| 끄고 DB 데이터까지 지우기 | `docker compose down -v` |
| 상태 보기 | `docker compose ps` |
| 서버 로그 실시간 보기 | `docker compose logs -f backend` |
| DB 에 SQL 로 접속 | `docker exec -it scenetrip-db psql -U scenetrip -d scenetrip` |

### 백엔드 담당자의 개발 방식

컨테이너로 전부 띄우면 코드를 고칠 때마다 이미지를 다시 구워야 해서 느리다. 그래서 **DB 만 컨테이너로 띄우고 서버는 IDE 에서 직접 실행** 한다.

```bash
docker compose up -d db      # DB 만 띄운다
cd backend
./gradlew bootRun            # 또는 IDE 에서 ScenetripApplication 실행
```

이때 서버는 `application.yml` 의 기본값을 써서 `localhost:5432` 로 DB 를 찾는다. 컨테이너로 띄울 때는 compose 가 주소를 `db:5432` 로 덮어쓴다. 그래서 두 방식 모두 설정을 고치지 않고 돌아간다.

테스트도 같은 방식이다. `ScenetripApplicationTests` 는 실제 DB 에 붙으므로 **DB 컨테이너가 떠 있어야 통과한다.**

```bash
docker compose up -d db
cd backend && ./gradlew test
```

### 문제 해결

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| `docker: unknown command: docker compose` | Docker Desktop 앱을 한 번도 실행하지 않았다 | 앱을 실행하고 고래 아이콘을 확인한다 |
| `Cannot connect to the Docker daemon` | 도커가 꺼져 있다 | Docker Desktop 을 실행한다 |
| `sudo: a terminal is required to read the password` | 진짜 터미널이 아닌 곳에서 설치를 실행했다 | Terminal.app 에서 다시 실행한다 |
| `port is already allocated` | 5432 나 8080 을 다른 프로그램이 이미 쓰고 있다 | `.env` 에서 `POSTGRES_PORT=5433` 처럼 바꾼다 |
| `no configuration file provided` | `SceneTrip` 폴더 밖에서 명령을 실행했다 | `cd ~/SceneTrip` 후 다시 실행한다 |
| 백엔드가 떴다가 바로 죽는다 | DB 접속 실패가 가장 흔하다 | `docker compose logs backend` 로 원인을 본다 |
| `Migration checksum mismatch` | 이미 적용된 Flyway SQL 파일을 고쳤다 | 파일을 되돌리고, 변경은 새 번호 파일로 만든다 |

---

## 새 서비스를 컨테이너로 추가하기

> [!info] 이 절은 사람과 코딩 에이전트가 같이 읽는 지침이다
> 각자 만드는 것(Flutter 앱, 데이터 파이프라인, AI 서비스)을 같은 방식으로 컨테이너에 얹기 위한 규칙이다.
> 에이전트에게 시킬 때는 **"`JiraDocs/MZ2AZ-157 Docker 개발 환경 구성.md` 의 '새 서비스를 컨테이너로 추가하기' 절을 그대로 따라서 `{서비스 이름}` 을 추가해라"** 라고 지시한다.
> 이미 돌아가는 `backend` 와 `db` 가 이 규칙을 그대로 따르고 있으니, 판단이 서지 않으면 **`backend/Dockerfile` 과 `docker-compose.yml` 의 `backend` 블록을 본보기로 삼는다.**

### 먼저 판단할 것 — 이걸 정말 컨테이너로 만들어야 하나

모든 작업물을 컨테이너에 넣을 필요는 없다. 아래 기준으로 먼저 가른다.

| 성격 | 컨테이너로? | 예 |
| --- | --- | --- |
| 계속 떠 있고 다른 서비스가 네트워크로 호출한다 | **그렇다** | 백엔드 API, AI 추론 서버, DB |
| 개발자 기기에서 직접 실행해야 한다 | **아니다** | Flutter 모바일 앱 (에뮬레이터·실기기 필요) |
| 가끔 한 번씩 돌리는 작업이다 | 컨테이너로 만들되 **기본 기동에서 제외** | 데이터 적재 배치, 크롤러 |
| 결과가 정적 파일이고 팀에 공유하고 싶다 | 그렇다 | Flutter **웹** 빌드 결과 |

가끔 돌리는 작업은 compose 의 `profiles` 로 묶어 둔다. 그러면 `docker compose up` 에는 안 뜨고, 필요할 때만 `docker compose --profile batch up loader` 로 부른다. 배치 작업이 매번 같이 떠서 자원을 먹는 것을 막기 위함이다.

### 반드시 지킬 규칙

| # | 규칙 | 이유 |
| --- | --- | --- |
| 1 | 새 서비스는 저장소 최상위에 자기 폴더를 갖는다. **폴더 이름과 compose 서비스 이름을 같게** 쓴다 | 이름이 어긋나면 남이 파일을 찾지 못한다 |
| 2 | 빌드 방법은 그 폴더의 `Dockerfile` 에만 쓴다. 루트 compose 에는 `build: context: ./{폴더}` 만 적는다 | 루트 파일이 비대해지면 아무도 못 고친다 |
| 3 | **다른 사람의 서비스 정의를 수정하지 않는다.** 자기 블록만 새로 추가한다 | JiraDocs 의 섹션 소유권 규칙과 같다 |
| 4 | 컨테이너끼리는 **서비스 이름** 으로 부른다 (`db`, `backend`). `localhost` 를 쓰지 않는다 | 컨테이너 안에서 `localhost` 는 자기 자신이라 접속이 실패한다 |
| 5 | 바뀔 수 있는 값(포트·계정·외부 API 키)을 코드나 compose 에 직접 쓰지 않는다. `.env` 로 빼고 **`.env.example` 에 견본을 반드시 추가** 한다 | `.env` 는 깃에 없다. 견본을 안 넣으면 남이 클론했을 때 뜨지 않는다 |
| 6 | 호스트 포트는 `"${이름_PORT:-기본값}:내부포트"` 형태로 쓴다 | 팀원 노트북마다 이미 쓰는 포트가 다르다 |
| 7 | DB 가 준비돼야 도는 서비스는 `depends_on` 에 `condition: service_healthy` 를 건다 | 준비 전에 붙으면 그대로 죽는다 |
| 8 | Dockerfile 을 **빌드 단계와 실행 단계로 나눈다.** 최종 이미지에 빌드 도구를 남기지 않는다 | 이미지가 몇 배로 커지고 공격 면이 넓어진다 |
| 9 | 실행 단계는 root 가 아닌 전용 계정으로 돌린다 | 컨테이너가 뚫렸을 때 피해를 줄인다 |
| 10 | 의존성 설치 결과는 `--mount=type=cache` 로 재사용한다 | 없으면 소스 한 줄 고칠 때마다 전부 다시 받는다 |
| 11 | 소스가 아닌 것(빌드 산출물·캐시·`.env`)은 `.dockerignore` 로 제외한다 | 빌드가 느려지고 비밀값이 이미지에 섞인다 |
| 12 | 베이스 이미지가 **arm64 를 지원하는지 확인** 한다 | 팀 노트북이 애플 실리콘이다. 안 되면 에뮬레이션으로 느려진다 |

12번은 이 티켓에서 실제로 걸렸던 문제다. 공식 `postgis/postgis` 가 arm64 빌드를 내지 않아 다른 이미지로 바꿨다. 확인 방법은 아래와 같다.

```bash
docker pull {이미지}
docker image inspect --format '{{.Os}}/{{.Architecture}}' {이미지}
# linux/arm64 가 나와야 한다. linux/amd64 면 에뮬레이션이므로 대안을 찾는다.
```

### 절차

| 단계 | 할 일 |
| --- | --- |
| 1 | `{서비스}/Dockerfile` 을 만든다 (아래 골격 참고) |
| 2 | `{서비스}/.dockerignore` 를 만든다 |
| 3 | 루트 `docker-compose.yml` 의 `services:` 아래에 블록을 **추가** 한다 |
| 4 | 새로 쓴 환경변수를 `.env.example` 에 추가한다 |
| 5 | 아래 검증을 모두 통과시킨다 |
| 6 | 루트 `README.md` 의 저장소 구조 표에 한 줄 추가한다 |

### 골격

Dockerfile 은 언어와 상관없이 이 모양을 지킨다.

```dockerfile
# 1단계: 빌드 — 컴파일러·패키지 관리자가 있는 이미지에서 실행물을 만든다.
FROM {빌드용 이미지} AS build
WORKDIR /workspace
COPY {의존성 정의 파일} ./
COPY {소스} ./
RUN --mount=type=cache,target={그 언어의 캐시 경로} \
	{빌드 명령}

# 2단계: 실행 — 실행에 필요한 최소한만 있는 이미지로 옮긴다.
FROM {실행용 이미지}
WORKDIR /app
RUN useradd --system --create-home --uid 10001 app
COPY --from=build /workspace/{결과물} ./
USER app
EXPOSE {포트}
ENTRYPOINT [{실행 명령}]
```

compose 블록은 이 모양을 지킨다.

```yaml
  {서비스이름}:
    build:
      context: ./{폴더}
    container_name: scenetrip-{서비스이름}
    environment:
      TZ: Asia/Seoul
      # 백엔드를 부른다면 주소는 localhost 가 아니라 backend 다.
      API_BASE_URL: http://backend:8080
    ports:
      - "${그이름_PORT:-포트}:내부포트"
    depends_on:          # DB 나 백엔드가 먼저 떠야 한다면
      db:
        condition: service_healthy
    restart: unless-stopped
```

언어별로 다른 부분은 아래 정도만 채우면 된다.

| 언어 | 빌드용 이미지 | 실행용 이미지 | 캐시 경로 |
| --- | --- | --- | --- |
| Java (참고: `backend/Dockerfile`) | `eclipse-temurin:21-jdk` | `eclipse-temurin:21-jre` | `/root/.gradle` |
| Python | `python:3.12-slim` | `python:3.12-slim` | `/root/.cache/pip` |
| Flutter 웹 | Flutter 공식 이미지 | `nginx:alpine` | 이미지 문서 참조 |

### 검증 — 아래를 모두 통과해야 끝난 것이다

```bash
cd ~/SceneTrip

# 1. compose 파일 문법과 변수 치환이 맞는지 본다.
docker compose config --quiet          # 아무것도 출력되지 않아야 통과

# 2. 새 서비스만 띄운다.
docker compose up -d --build {서비스}

# 3. 상태를 본다. Exited 나 Restarting 이면 실패다.
docker compose ps

# 4. 로그에 오류가 없는지 본다.
docker compose logs {서비스}

# 5. 기존 서비스를 깨뜨리지 않았는지 확인한다. 이 응답이 그대로 나와야 한다.
curl http://localhost:8080/api/ping
```

마지막 항목을 빠뜨리지 말 것. 루트 compose 는 팀 공용 파일이라 자기 서비스만 확인하고 끝내면 남의 환경을 깨뜨린 채로 올리게 된다.

### 자주 나오는 실수

| 실수 | 증상 | 바로잡기 |
| --- | --- | --- |
| 다른 컨테이너를 `localhost` 로 부름 | `Connection refused` | 서비스 이름으로 바꾼다 (`http://backend:8080`) |
| 포트를 숫자로 고정 | 다른 팀원이 `port is already allocated` | `${이름_PORT:-기본값}` 으로 바꾼다 |
| `.env.example` 을 갱신하지 않음 | 남이 클론하면 안 뜬다 | 새 변수를 견본에 추가한다 |
| `.env` 를 커밋 | 나중에 API 키가 깃 기록에 남는다 | 커밋 전에 `git status` 로 확인한다 |
| 남의 서비스 블록을 고침 | 남의 환경이 깨진다 | 자기 블록만 추가한다 |
| arm64 미지원 이미지 사용 | 눈에 띄게 느림 | `docker image inspect` 로 확인 후 대안을 찾는다 |

---

## 다음 작업

| 할 일 | 관련 |
| --- | --- |
| 실제 테이블 DDL 을 `V2` 마이그레이션으로 작성 | [[MZ2AZ-111 SceneTrip DB 스키마 (DBML)]] |
| V6 CSV 데이터 적재 | 데이터 확정 후 |
| API 명세서 작성 — 프론트가 기다리는 산출물 | [[(2주차)2026년 8월 3일 Sprint Planning]] 2-3 |
| `app/` 에 Flutter 프로젝트 추가 | MZ2AZ-160 |
