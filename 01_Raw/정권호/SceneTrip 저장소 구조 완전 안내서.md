# SceneTrip 저장소 구조 완전 안내서

> 이 저장소가 **어떻게 생겼고, 왜 그렇게 생겼고, 문서들이 서로 어떻게 물려 있는지** 를
> 처음부터 끝까지 설명한다. 특히 **Bazel** 은 이 문서의 절반을 차지한다.
> 모르는 단어가 나오면 그 자리에서 [[#부록 A — 용어 사전]] 으로 점프할 수 있게 링크를 걸어 뒀다.
> 기준 시점: 2026-08-05 · 기준 파일: `~/backup/SceneTrip` 스냅샷 + 현재 작업 저장소
> 둘이 다른 부분은 [[#부록 C — 백업본과 현재 저장소의 차이]] 에 정리했다.

명령을 **어떤 순서로 치는지** 는 자매 문서인 [[개발 순서와 just 명령어 안내서]] 가 다룬다.
이 문서는 그 명령들이 **무엇을 건드리는지** 를 다룬다. 둘은 겹치지 않는다.

---

## 목차

**1부 — 큰 그림**

- [[#0. 저장소 전체를 한 장으로]]
- [[#1. 이 저장소가 보통과 다른 점 세 가지]]
- [[#2. 지금 이 저장소의 실제 상태 — 아직 뼈대다]]

**2부 — 디렉터리 전부 훑기**

- [[#3. 최상위 지도]]
- [[#4. 코드가 사는 곳 — services · apps · agents · libs]]
- [[#5. 약속이 사는 곳 — contracts]]
- [[#6. 인프라가 사는 곳 — platform]]
- [[#7. 테스트가 사는 곳 — tests]]
- [[#8. 도구가 사는 곳 — tools]]
- [[#9. 문서가 사는 곳 — docs]]
- [[#10. 나머지 — third_party · .github · 점으로 시작하는 파일들]]

**3부 — Bazel 완전 해부** ← 제일 안 와닿는 부분

- [[#11. Bazel 은 대체 무엇을 하는 물건인가]]
- [[#12. 워크스페이스 · 패키지 · 타깃 · 라벨]]
- [[#13. BUILD.bazel 을 실제로 읽어 보자]]
- [[#14. srcs · deps · data · visibility]]
- [[#15. Bazel 의 전부는 그래프다]]
- [[#16. 격리 — Bazel 이 까다롭게 구는 진짜 이유]]
- [[#17. MODULE.bazel — 바깥 세계에서 뭘 가져오는가]]
- [[#18. .bazelrc 와 config — 플래그를 이름으로 부르기]]
- [[#19. 태그와 테스트 레인]]
- [[#20. 타깃 이름 규칙 — 읽지 않고도 맞히기]]
- [[#21. 그래프에 질문하는 법]]
- [[#22. buildifier 와 Gazelle]]
- [[#23. bazel- 로 시작하는 심볼릭 링크]]
- [[#24. Bazel 증상별 원인 사전]]
- [[#25. 지금 이 저장소의 Bazel 진도표]]

**4부 — just 와 명령 계층**

- [[#26. 4층 구조]]
- [[#27. 레시피 문법 최소한]]
- [[#28. check 와 ci 는 어떻게 다른가]]

**5부 — 문서들의 연결 관계**

- [[#29. 문서 지도]]
- [[#30. 규칙이 충돌할 때의 우선순위 사슬]]
- [[#31. 문서마다 한 줄 역할과 읽는 시점]]
- [[#32. 상황별 읽기 순서]]
- [[#33. 문서가 코드에 강제되는 지점]]

**6부 — 흐름으로 다시 보기**

- [[#34. 기능 하나가 태어나서 배포되기까지]]
- [[#35. 새 언어 하나가 들어올 때]]

**부록**

- [[#부록 A — 용어 사전]]
- [[#부록 B — 헷갈리는 짝 정리]]
- [[#부록 C — 백업본과 현재 저장소의 차이]]
- [[#부록 D — 바깥 링크 모음]]

---

# 1부 — 큰 그림

## 0. 저장소 전체를 한 장으로

이 저장소는 **회사 하나가 통째로 들어 있는 서랍장** 이라고 보면 된다.
기획서, 설계, 서버 코드, 앱 코드, AI 코드, 인프라 설정, 테스트, 운영 매뉴얼까지
전부 한 서랍장 안에 칸을 나눠 들어간다. 이런 걸 [[#모노레포|모노레포]] 라고 부른다.

```
                     ┌──────────────────────────────┐
   사람 / AI  ─────►  │           just               │  명령 창구 (주문표)
                     └──────────────┬───────────────┘
                                    │
                     ┌──────────────▼───────────────┐
                     │           Bazel              │  빌드·테스트 기계
                     └──────────────┬───────────────┘
                                    │ 읽는다
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
   ┌────▼─────┐              ┌──────▼──────┐            ┌───────▼───────┐
   │ 코드     │              │  약속       │            │  인프라       │
   │ services │◄─── 참조 ────│  contracts  │            │  platform     │
   │ apps     │              │  (proto,    │            │  (terraform,  │
   │ agents   │              │   openapi,  │            │   k8s, helm,  │
   │ libs     │              │   schemas)  │            │   kind)       │
   └──────────┘              └─────────────┘            └───────────────┘
        ▲                           ▲                           ▲
        └───────────────┬───────────┴───────────────────────────┘
                        │  전부 설명하는 것
                  ┌─────▼──────┐
                  │   docs     │  기획·설계·운영·QA·AI 문서
                  └────────────┘
```

문장 하나로 줄이면 이렇다.

**`just` 로 명령하고, Bazel 이 짓고, 코드는 `contracts/` 의 약속으로만 서로 대화하고,
그 전부를 `docs/` 가 설명한다.**

## 1. 이 저장소가 보통과 다른 점 세 가지

### (1) 언어가 여러 개인데 빌드 도구는 하나다

백엔드는 Java(Spring Boot), AI 는 Python, iOS 는 Swift, Android 는 Kotlin 이다.
보통이면 각각 Gradle, pip, Xcode, Gradle 을 따로 쓴다. 이 저장소는 그러지 않는다.
**전부 Bazel 하나로 짓는다.** 이유는 [[#11. Bazel 은 대체 무엇을 하는 물건인가]] 에 있고,
결정의 기록은 저장소 안 `docs/architecture/adr/0001-...md` 다.

### (2) 명령의 입구가 하나다

`bazel build ...` 를 직접 치는 일은 없다. 문서에도, 스크립트에도, CI 설정에도
날것의 `bazel` 은 등장하지 않는다. 전부 `just <이름>` 이다.

왜 이렇게까지 하냐면 — 이 저장소는 **AI 에이전트가 개발의 상당 부분을 수행하는 것을
전제** 하고 만들어졌기 때문이다. AI 는 "이 서비스는 `make test`, 저 앱은 `pnpm test:ci`"
같은 걸 추론해 낼 수 없다. `just --list` 하나로 할 수 있는 일이 전부 나열되면
사람도 AI 도 헤매지 않는다.

### (3) 문서가 장식이 아니라 부품이다

- `AGENTS.md` 는 **계약서** 다. 저장소의 규칙 정본.
- `CLAUDE.md` 는 **작업 절차서** 다. 그 규칙 안에서 어떻게 움직일지.
- 각 디렉터리의 `README.md` 는 **그 칸의 안내판** 이다. 비어 있는 칸에도 안내판은 있다.
- `contracts/` 는 **문서가 아니라 빌드 입력** 이다. 여기 적힌 명세로부터 실제 코드가 나온다.

이 셋의 관계가 이 저장소를 이해하는 핵심이고, [[#5부 — 문서들의 연결 관계|5부]] 에서 따로 다룬다.

## 2. 지금 이 저장소의 실제 상태 — 아직 뼈대다

**이걸 모르면 저장소를 읽다가 반드시 혼란스러워진다.**

파일이 100개 남짓인데 그 대부분이 `README.md` 다. `services/` 안에는 서비스가 없고,
`apps/` 안에는 앱이 없다. 실제 애플리케이션 코드는 **아직 한 줄도 없다.**

```
현재 = 잘 지어진 빈 건물 + 아주 상세한 입주 규칙

  ✓ 방 배치도(디렉터리)        완성
  ✓ 입주 규칙(AGENTS/CLAUDE)   완성
  ✓ 관리실(just 레시피 90여 개) 완성
  ✓ 전기·수도 배관(Bazel 설정)  기초만
  ✗ 입주자(실제 코드)          없음
```

그래서 이런 현상이 자연스럽다.

- `just test` 를 돌리면 "테스트 대상 없음" 이 뜬다 → 실패가 아니라 **경고** 로 처리된다.
  (`tools/scripts/bazel-test.sh` 가 Bazel 종료 코드 4 를 일부러 0 으로 바꾼다)
- `just lint` 를 돌리면 `미구현: 아직 적용할 린터가 없습니다` 가 뜬다 → 소스가 없으니 당연하다.
- `MODULE.bazel` 에 Java/Swift/Kotlin/Python 규칙이 **주석으로만** 들어 있다 →
  "아무도 안 쓰는 규칙으로 파일을 채우지 않는다" 는 방침이다.

지금 실제로 도는 Bazel 타깃은 딱 넷이다. 자세히는 [[#25. 지금 이 저장소의 Bazel 진도표]].

---

# 2부 — 디렉터리 전부 훑기

## 3. 최상위 지도

```
SceneTrip/
├── AGENTS.md            저장소 계약서 — 규칙의 정본 (영문)
├── CLAUDE.md            AI 작업 절차서 (영문)
├── README.md            현관문. 여기서 시작한다 (한글)
│
├── justfile             모든 명령의 입구
├── MODULE.bazel         외부 의존성 선언
├── MODULE.bazel.lock    위 선언을 못 박은 결과 (기계가 씀, 사람이 안 씀)
├── BUILD.bazel          루트 패키지 — 저장소 전역 도구 타깃만
├── .bazelrc             Bazel 플래그 모음
├── .bazelversion        Bazel 버전 고정 (8.0.0)
├── .bazelignore         Bazel 이 아예 안 볼 폴더
├── .gitignore           git 이 무시할 것
├── .editorconfig        에디터 공통 설정(들여쓰기 등)
│
├── services/            백엔드 서버들
├── apps/                iOS / Android 앱들
├── agents/              AI 에이전트들
├── libs/                둘 이상이 쓰는 공유 코드
│
├── contracts/           인터페이스 정본 ★ 가장 중요한 칸
├── platform/            인프라 (terraform, k8s, helm, kind, docker)
├── tests/               모듈을 가로지르는 테스트만
├── tools/               빌드·개발 도구 (bazel, just, scripts, templates, ci)
├── docs/                모든 산문 문서
├── third_party/         남의 코드를 통째로 들여올 때
└── .github/             CI 워크플로 + 이슈/PR 템플릿
```

**최상위 폴더를 새로 만드는 것은 금지다.** 새 파일의 자리는 `AGENTS.md` §2 의
"배치 결정표" 로 정한다. 이건 취향이 아니라 규칙이다 — 자리가 흔들리면 사람도 AI 도
찾지 못한다.

## 4. 코드가 사는 곳 — services · apps · agents · libs

### 네 칸의 역할

- **`services/<이름>/`** — 독립 배포되는 백엔드 서버. Spring Boot(Java).
  자기 데이터를 소유한다.
- **`apps/<이름>/`** — 사용자가 보는 앱. iOS 는 Swift, Android 는 Kotlin.
  **둘은 코드를 공유하지 않는다.**
- **`agents/<이름>/`** — LLM 기반 구성요소. Python. 프롬프트·도구·오케스트레이션을 가진다.
- **`libs/<언어>/<이름>/`** — 둘 이상의 모듈이 import 하는 코드.
  `libs/java`, `libs/python`, `libs/swift`, `libs/kotlin`, `libs/proto`.

### 모듈 하나의 모양은 항상 같다

```
services/scene-api/
├── BUILD.bazel     필수 — 이 폴더의 조립 설명서
├── README.md       필수 — 목적, 포트, 쓰는 계약, 의존성
├── CLAUDE.md       선택 — 이 모듈에서만 통하는 규칙 (루트보다 우선)
├── src/            구현
├── tests/          이 모듈만 검증하는 테스트
└── deploy/         이 모듈 소유의 k8s/helm 조각
```

이 모양은 손으로 만들지 않는다. `just new-service <이름>` 이
`tools/templates/module/` 의 템플릿을 찍어 낸다. **그래서 모든 모듈이 처음부터
같은 모양** 이고, 라벨을 읽지 않고도 맞힐 수 있다.

### 모듈끼리 대화하는 규칙 — 이게 제일 중요하다

```
  ✗ 금지                                ✓ 허용
  ─────────────────────                 ─────────────────────
  service A 가 service B 의             A 가 B 의 계약(contracts/)을 보고
  src/ 를 직접 import                   네트워크로 호출

  iOS 와 Android 가 공통 코드           둘 다 contracts/ 의 같은 명세로부터
  레이어를 만들어 공유                   각자 클라이언트를 생성

  앱이 API 호출 코드를 손으로 작성       contracts/openapi 로부터 생성

  에이전트가 DB 에 직접 접속            에이전트가 서비스를 호출

  같은 유틸을 두 모듈에 복사             libs/<언어>/ 로 올리고 둘 다 참조
```

마지막 줄이 특히 중요하다. **복제는 해결책이 아니라 신호다.**
두 번째 모듈이 같은 코드를 필요로 하는 순간, 그건 `libs/` 로 올려야 한다는 뜻이다.

## 5. 약속이 사는 곳 — contracts

이 저장소에서 **가장 먼저 이해해야 할 칸** 이다.

```
contracts/
├── proto/      gRPC 서비스와 메시지 정의    (.proto)
├── openapi/    REST API 명세               (.yaml)
├── asyncapi/   이벤트·스트림 명세           (.yaml)
└── schemas/    JSON Schema / Avro — AI 에이전트 도구 스키마 포함
```

### 계약 우선(contract-first)이란

통신 형식이 바뀔 때 순서가 정해져 있다.

```
1. contracts/ 를 먼저 고친다
2. just gen  (혹은 그냥 just build — 생성은 빌드 시점에 일어난다)
3. 생성된 스텁에 맞춰 구현한다
```

**역순은 없다.** 구현이 계약과 다르면 그건 구현 쪽의 결함이다.

왜 이렇게 하냐면, SceneTrip 은 같은 API 를 **서버 · iOS · Android 셋** 이 동시에 본다.
명세가 하나면 셋이 어긋날 수가 없다. 사람이 세 번 맞춰 쓰는 게 아니라 기계가 세 벌을 뽑는다.

```
        contracts/openapi/scene-api-v1.yaml   ← 사람이 쓰는 유일한 파일
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   spring 생성기    swift5 생성기    kotlin 생성기
        │               │               │
        ▼               ▼               ▼
   서버 인터페이스   iOS 클라이언트   Android 클라이언트
   (이걸 구현하면    (앱이 그대로     (앱이 그대로
    계약 위반이       가져다 씀)       가져다 씀)
    컴파일 오류)
```

### 생성물은 커밋하지 않는다

생성된 코드는 **Bazel 빌드 산출물** 이다. 저장소에 들어가지 않는다.
`AGENTS.md` §2 배치표에도 "생성된 스텁 → **nowhere**" 라고 적혀 있다.
필요하면 언제든 다시 뽑을 수 있는 것을 저장소에 두면, 명세와 생성물이 어긋나는
순간이 반드시 온다.

### 호환성 규칙

- 파괴적 변경은 **새 버전 디렉터리** 를 만든다. `scene/v1` → `scene/v2`. 제자리 수정 금지.
- protobuf 필드 번호는 지우거나 재사용하지 않는다. `reserved` 로 막는다.
- 모든 계약 변경은 `just test-contract` 로 검증한다.

## 6. 인프라가 사는 곳 — platform

```
platform/
├── kind/           로컬 Kubernetes 클러스터 정의 (cluster.yaml)
├── terraform/      클라우드 리소스 — 네트워크, DB, 클러스터, IAM
├── kubernetes/     매니페스트. <모듈>/ 폴더 + 공용 구성요소
├── helm/           이 저장소가 소유하는 차트
├── environments/   dev / staging / prod 의 값만
└── docker/         로컬 개발 보조 컨테이너
```

### 세 가지 철칙

**시크릿은 이 트리에 없다.** 값은 시크릿 매니저에서 오고, 커밋하는 건
`*.tfvars.example` 같은 자리표시자뿐이다.

**환경은 코드가 아니라 값으로 갈린다.** dev 든 prod 든 같은 코드가 돌고
`environments/<env>/` 의 값만 다르다. `if env == "prod"` 같은 분기를 만들지 않는다.

**상태를 바꾸는 명령은 전부 확인 절차가 있다.** `just tf-apply` 는 실행 전에
대상 환경을 출력하고 y/n 을 묻는다.

### 로컬 클러스터의 모양

```
Docker Desktop  (컨테이너 런타임으로만 씀. 내장 Kubernetes 는 끈다)
└── kind 클러스터 "scenetrip"        컨텍스트: kind-scenetrip
    ├── 네임스페이스 scenetrip        우리 서비스·앱·에이전트
    └── 네임스페이스 signoz           SigNoz (관측 도구 묶음)

호스트 8080 → NodePort 30080 → SigNoz UI
호스트 8081 → NodePort 30081 → 애플리케이션 API
```

포트 매핑은 `platform/kind/cluster.yaml` 이 **클러스터를 만드는 시점에만** 정할 수 있다.
그래서 `port-forward` 가 필요 없고, 동시에 포트를 추가하려면 클러스터를 다시 만들어야 한다.
(다시 만들면 그동안 쌓인 로그·트레이스·DB 데이터가 사라진다)

### 안전장치 하나 — 이건 그림으로 볼 만하다

`tools/scripts/_lib.sh` 에 이런 함수가 있다.

```
require_kind_context()
   현재 kubectl 컨텍스트가 "kind-scenetrip" 이 아니면 → 즉시 실행 거부
```

알림이 아니라 **차단** 이다. 이유가 주석에 적혀 있는데 인용할 만하다 —
사람이 매번 기억해야 하는 규칙은 규칙이 아니고, 한눈판 사이의 `kubectl apply` 한 번이
운영 클러스터 컨텍스트로 나가면 그게 그대로 장애다.

## 7. 테스트가 사는 곳 — tests

**`tests/` 에는 배포 단위 둘 이상에 걸친 테스트만 둔다.**
모듈 하나만 검증하는 테스트는 그 모듈 안 `tests/` 에 코드 옆에 둔다. 이 구분이 전부다.

```
tests/
├── contract/     생산자·소비자가 contracts/ 를 지키는지   just test-contract   빠름
├── integration/  여러 모듈 + 실제 의존성                  just test-integration 중간
├── e2e/          사용자 표면을 관통하는 전체 스택          just test-e2e        느림
└── load/         부하 상태의 처리량·지연                   just test-load       수동
```

어느 레인에서 도는지는 **Bazel 태그** 가 정한다. 자세히는 [[#19. 태그와 테스트 레인]].
태그를 잘못 달면 두 가지 중 하나가 일어난다 — 빠른 레인이 느려지거나,
그 테스트가 **영영 실행되지 않는다.** 후자가 더 무섭다. 조용히 아무도 모른다.

## 8. 도구가 사는 곳 — tools

```
tools/
├── bazel/
│   ├── defs/        재사용 매크로(.bzl) — 같은 규칙을 세 번 복사하기 전에 여기로
│   └── toolchains/  격리된 툴체인 선언
├── just/            루트 justfile 이 import 하는 명령 모듈 9개
├── scripts/         just 레시피가 호출하는 셸 스크립트 30여 개
├── templates/       just new-* 가 찍어 내는 템플릿
└── ci/              CI 전용 보조 로직
```

이 칸의 규칙 두 개만 기억하면 된다.

- **justfile 은 명령을, 스크립트는 로직을 담는다.** 레시피 안의 셸이 5줄을 넘으면
  `scripts/` 로 옮긴다.
- **같은 Bazel 패턴이 세 번 나오면 매크로다.** `bazel/defs/` 로 올린다.

자세한 계층 구조는 [[#26. 4층 구조]] 에서.

## 9. 문서가 사는 곳 — docs

```
docs/
├── product/       비전, PRD, 요구사항, 페르소나, 로드맵
├── architecture/  시스템 설계, 다이어그램, 데이터 모델
│   └── adr/       아키텍처 결정 기록 ★ 추가만 하고 고쳐 쓰지 않는다
├── api/           API "사용법" (명세는 contracts/ 에 있다)
├── engineering/   온보딩, Bazel 가이드, just 가이드, 컨벤션
├── installs/      로컬 환경 설치 (kind, SigNoz)
├── education/     강의 자료 (35슬라이드 HTML 덱)
├── qa/            테스트 전략, 커버리지 정책
├── ops/           런북, SLO, 온콜, 장애 회고
├── ai/            에이전트 설계, 프롬프트, 평가 방법·결과
└── project/       계획, 현황, 결정 로그, 회고
    └── plans/     코드보다 먼저 쓰는 구현 계획
```

### 언어 정책

**한글이 기본이다.** 문서, justfile 주석, 스크립트 메시지, README 전부 한글이다.
**`AGENTS.md` 와 `CLAUDE.md` 만 영문** 인데, 이 둘은 AI 도구가 직접 읽어 따르는
운영 지침이라 모호함을 줄이려고 영문으로 고정했다.
코드 식별자(타깃 이름, 레시피 이름, 경로, 변수)는 언제나 영문이다.

### ADR 은 왜 특별한가

ADR(Architecture Decision Record)은 **추가만 한다.** 결정을 바꾸려면
기존 것을 고치는 게 아니라 새 ADR 을 쓰고 옛 것의 상태를 `superseded` 로 바꾼다.

```
proposed  →  accepted  →  superseded | deprecated
```

역사를 고쳐 쓰지 않는 이유는 간단하다. 나중에 읽는 사람에게 필요한 건
"지금 뭘 쓰는가" 가 아니라 **"왜 그때 그걸 안 골랐는가"** 이기 때문이다.
그래서 ADR 에는 기각한 대안과 그 이유를 반드시 남긴다.

현재 ADR 두 개:

- **0001** — Bazel 을 유일한 빌드 시스템으로, just 를 유일한 명령 창구로.
- **0002** — 제품 스택을 Spring · Python · iOS/Android 네이티브로 확정.
  (0001 의 배경에 적혀 있던 "Go/TypeScript" 라는 **가정** 을 정정한 문서다.
  0001 을 대체하지는 않는다 — 두 법칙은 그대로 유지)

## 10. 나머지 — third_party · .github · 점으로 시작하는 파일들

### third_party/

남의 코드를 통째로 들여올 때만 쓴다. `MODULE.bazel` 에 버전을 고정해 받는 게 우선이고,
대안이 없을 때만 벤더링한다. 들여온 디렉터리마다 `PROVENANCE.md` 를 두고
출처 URL, 정확한 커밋, 라이선스, 로컬 수정 사항 전부를 적는다.
그리고 **가져온 코드는 제자리에서 고치지 않는다** — 빌드 규칙에서 패치를 적용해야
업그레이드가 기계적으로 유지된다.

### .github/

`workflows/ci.yml` 하나가 핵심인데, **의도적으로 얇다.**

```yaml
- 체크아웃
- just 설치
- bazelisk 설치
- Bazel 캐시 복원
- run: just ci-full        ← 파이프라인 로직은 여기 없다
```

파이프라인의 실제 내용은 `tools/just/ci.just` 에 있다.
그래서 **CI 가 하는 일을 노트북에서 그대로 재현할 수 있다.** 이게 이 구조의 목적이다.

### 점으로 시작하는 파일들

- **`.bazelversion`** — 내용이 `8.0.0` 한 줄이다. [[#bazelisk|bazelisk]] 가 이 파일을 읽고
  그 버전의 Bazel 을 알아서 받아 쓴다. 모두가 같은 버전을 쓰게 하는 장치.
- **`.bazelrc`** — Bazel 플래그 모음. [[#18. .bazelrc 와 config — 플래그를 이름으로 부르기]]
- **`.bazelignore`** — Bazel 이 아예 들여다보지 않을 폴더. `node_modules`, `.git`, `.venv`.
- **`.gitignore`** — `/bazel-*` 심볼릭 링크, `.env`, 각종 키 파일, 언어별 산출물.
  `.env.example` 은 **예외적으로 커밋한다** (`!.env.example`).
- **`.editorconfig`** — 에디터마다 들여쓰기가 달라지지 않게 하는 공통 설정.

---

# 3부 — Bazel 완전 해부

여기가 이 문서의 본론이다. 천천히 간다.

## 11. Bazel 은 대체 무엇을 하는 물건인가

### 한 문장

**[[#Bazel|Bazel]] 은 "무엇으로 무엇을 만드는가" 를 전부 적어 두고, 바뀐 것만 다시 만드는 기계다.**

### 보통의 빌드 도구와 뭐가 다른가

보통의 빌드 도구(Gradle, npm, pip)는 **언어별 요리사** 다.
Java 요리사, JS 요리사가 각자 주방을 갖고 각자 재료를 사 온다.
언어가 넷이면 주방이 넷이고, 캐시도 넷이고, CI 잡도 넷이다.

Bazel 은 **한 개의 공장** 이다. 언어가 넷이어도 공장은 하나다.
공장 안에 Java 라인, Swift 라인이 있을 뿐이다.

```
  언어별 도구                          Bazel
  ─────────────                       ─────────────
  Gradle  ──► 서버 산출물              ┌─────────────────────┐
  pip     ──► AI 산출물                │       Bazel         │
  Xcode   ──► iOS 산출물          ──►  │  하나의 의존성 그래프 │ ──► 전부
  Gradle  ──► Android 산출물           └─────────────────────┘

  · 캐시 4개, 서로 모름                 · 캐시 1개, 전부 공유
  · "이거 고치면 뭐가 영향받지?"        · 그래프에 물어보면 답이 나온다
    → 아무도 모름
```

### Bazel 이 특별히 잘하는 것 두 가지

**(1) 안 바뀐 건 다시 안 만든다.**
Bazel 은 모든 입력 파일의 [[#해시|해시]](지문)를 기억한다. 입력 지문이 같으면
결과도 같을 수밖에 없으니, 만들지 않고 캐시에서 꺼낸다.
파일 하나를 고쳤을 때 그 파일에 **의존하는 것만** 다시 지어진다.

**(2) 무엇이 영향받는지 계산할 수 있다.**
"이 파일을 고치면 어떤 테스트를 돌려야 하나?" 에 정확한 답이 나온다.
`tools/scripts/affected-targets.sh` 가 실제로 이걸 한다 —
바뀐 파일 목록을 Bazel 에 넣고 "이것들에 의존하는 테스트 전부" 를 받아 온다.

### 대신 감수하는 것

- **학습 곡선이 있다.** 파일을 추가하면 `BUILD.bazel` 도 같이 고쳐야 한다.
  "폴더에 넣으면 알아서 잡힌다" 가 통하지 않는다.
- **언어를 늘리려면 규칙을 써야 한다.** 설치 명령 한 줄로 안 된다.
- **IDE 연동에 어댑터가 필요할 수 있다.** 네이티브 레이아웃을 전제하는 도구들이 있다.

이 비용은 ADR 0001 에 "의도한 마찰이며, 이 결정의 요점이다" 라고 명시돼 있다.

## 12. 워크스페이스 · 패키지 · 타깃 · 라벨

Bazel 을 이해하려면 이 네 단어의 관계를 그림으로 잡아야 한다.

```
워크스페이스 (= 저장소 전체. MODULE.bazel 이 있는 곳이 루트)
│
├── contracts/openapi/          ← BUILD.bazel 이 있다 → 이 폴더가 "패키지"
│   ├── BUILD.bazel
│   ├── scene-api-v1.yaml
│   └── [타깃] :scene_api_spring
│
├── tests/contract/             ← BUILD.bazel 이 있다 → 또 하나의 "패키지"
│   ├── BUILD.bazel
│   └── [타깃] :scene_api_swift
│       [타깃] :scene_api_kotlin
│       [타깃] :scene_api_contract_test
│
└── docs/                       ← BUILD.bazel 이 없다 → 패키지가 아니다
                                  (Bazel 입장에서 그냥 파일 더미)
```

- **워크스페이스** — 저장소 하나. `MODULE.bazel` 이 있는 폴더가 루트다.
- **패키지** — `BUILD.bazel` 파일이 있는 폴더. **파일이 있어야 패키지가 된다.**
- **타깃** — `BUILD.bazel` 안에 선언된 항목 하나. "만들 수 있는 것" 하나.
- **[[#라벨|라벨]]** — 타깃을 가리키는 주소.

### 라벨 문법 해부

```
   //services/scene-api:bin
   ▲  ▲                 ▲
   │  │                 └─ 타깃 이름. BUILD.bazel 안의 name = "bin"
   │  └─ 패키지 경로. 저장소 루트부터의 디렉터리
   └─ "이 저장소 루트부터" 라는 뜻
```

변형들:

```
//services/scene-api:bin      정확히 그 타깃 하나
//services/scene-api          :scene-api 의 줄임 (폴더명과 타깃명이 같을 때)
:bin                          같은 BUILD 파일 안에서 쓰는 상대 주소
//services/scene-api/...      그 폴더 아래 전부  ("..." 는 재귀 와일드카드)
//...                         저장소 전체 (justfile 의 ALL 변수가 이 값이다)
@bazel_skylib//rules:build_test.bzl    다른 저장소(외부 의존성)의 것
▲
└─ "@" 로 시작하면 바깥 저장소
```

이 문법을 알면 `just build //contracts/...` 같은 명령이 무슨 뜻인지 바로 읽힌다.

## 13. BUILD.bazel 을 실제로 읽어 보자

말로만 하면 안 와닿으니 이 저장소의 진짜 파일 두 개를 줄별로 뜯는다.

### 예제 1 — 루트 `BUILD.bazel` (가장 단순)

```python
# ① 다른 곳에서 규칙을 가져온다
load("@buildifier_prebuilt//:rules.bzl", "buildifier")

# ② 이 패키지 타깃들의 기본 공개 범위
package(default_visibility = ["//visibility:public"])

# ③ 타깃 하나
buildifier(
    name = "buildifier",
    exclude_patterns = ["./bazel-*/**"],
    lint_mode = "fix",
    mode = "fix",
)

# ④ 또 하나
buildifier(
    name = "buildifier_check",
    exclude_patterns = ["./bazel-*/**"],
    lint_mode = "warn",
    mode = "diff",
)
```

읽는 법:

- **①** `load` 는 import 다. `@buildifier_prebuilt` 라는 외부 저장소에서
  `buildifier` 라는 **규칙(rule)** 을 가져온다. 규칙은 "만드는 방법의 종류" 다.
  `MODULE.bazel` 에 그 저장소를 선언해 뒀기 때문에 `@` 로 부를 수 있다.
- **②** `package(...)` 는 이 파일 전체에 적용되는 기본값. 여기선 "누구나 참조 가능".
- **③** 타깃이다. 라벨은 `//:buildifier`. `just fmt` 가 이걸 실행한다
  (`bazel run //:buildifier`).
- **④** 라벨은 `//:buildifier_check`. `mode = "diff"` 라 **고치지 않고 어긋나면 실패한다.**
  `just fmt-check` 와 `just lint` 가 이걸 부르므로 `just check` 와 CI 를 거쳐 간다.

같은 규칙에서 옵션만 다르게 준 타깃 두 개 — "고치는 것" 과 "검사하는 것" 이
따로 있는 이 패턴은 저장소 전체에서 반복된다.

### 예제 2 — `contracts/openapi/BUILD.bazel` (실제로 코드를 만드는 타깃)

```python
load("@openapi_tools_generator_bazel//:defs.bzl", "openapi_generator")

package(default_visibility = ["//visibility:public"])

# 다른 패키지가 이 파일 자체를 참조할 수 있게 연다
exports_files(["scene-api-v1.yaml"])

# scene-api 의 Spring 서버 인터페이스
openapi_generator(
    name = "scene_api_spring",
    generator = "spring",
    spec = "scene-api-v1.yaml",
)
```

여기서 중요한 통찰이 하나 있다.

**이 타깃이 곧 명세의 검사기다.**
생성기는 코드를 뽑기 전에 명세를 파싱·검증한다. 그러니 `$ref` 가 깨졌거나 문법이 틀리면
**빌드가 실패한다.** 그리고 `just check` 는 `bazel build //...` 를 돌린다.
따로 "명세 검사기" 를 붙이지 않았는데도 명세 검사가 게이트에 자동으로 포함된다.

### 예제 3 — `tests/contract/BUILD.bazel` (테스트 타깃)

```python
load("@bazel_skylib//rules:build_test.bzl", "build_test")
load("@openapi_tools_generator_bazel//:defs.bzl", "openapi_generator")

package(default_visibility = ["//visibility:private"])

openapi_generator(
    name = "scene_api_swift",
    generator = "swift5",
    spec = "//contracts/openapi:scene-api-v1.yaml",   # ← 다른 패키지의 파일을 라벨로 참조
)

openapi_generator(
    name = "scene_api_kotlin",
    generator = "kotlin",
    spec = "//contracts/openapi:scene-api-v1.yaml",
)

build_test(
    name = "scene_api_contract_test",
    tags = ["unit"],                                  # ← 이 태그가 레인을 정한다
    targets = [
        ":scene_api_kotlin",
        ":scene_api_swift",
        "//contracts/openapi:scene_api_spring",
    ],
)
```

배울 점 셋:

**(1) 파일을 라벨로 참조한다.** `spec = "//contracts/openapi:scene-api-v1.yaml"`.
상대 경로(`../../contracts/...`)가 아니다. Bazel 은 파일도 타깃으로 다룬다.
그래서 저쪽 패키지가 `exports_files` 로 열어 줘야 참조가 된다.

**(2) `BUILD.bazel` 이 없으면 그 폴더는 존재하지 않는 셈이다.**
이 파일의 주석에 그 이유가 적혀 있다 — `BUILD.bazel` 이 없으면 Bazel 은
`//tests/contract/...` 를 "대상 없음" 이 아니라 **에러** 로 처리한다.
그러면 `just test-contract` 가 그냥 죽는다. 계약을 검증하라고 문서에 적어 놓고
정작 그 명령이 실행되지 않는 상태가 되는 것이다.

**(3) 태그가 레인을 정한다.** `tags = ["unit"]` 덕분에 이 테스트는
`just test-contract` 뿐 아니라 빠른 레인(`just test`)과 `just check` 에서도 함께 돈다.

## 14. srcs · deps · data · visibility

타깃에 붙는 속성 중 계속 마주칠 넷.

```
어떤_규칙(
    name = "무엇",          이 타깃의 이름. 라벨의 : 뒤가 된다
    srcs = [...],           재료 — 이 타깃을 만드는 소스 파일들
    deps = [...],           부품 — 이 타깃이 의존하는 다른 타깃들
    data = [...],           동봉물 — 실행할 때 옆에 있어야 하는 파일들
    visibility = [...],     누가 이걸 참조할 수 있나
    tags = [...],           분류표 — 어느 레인에서 돌지 등
)
```

### srcs — 여기가 제일 자주 사고 난다

**소스 파일을 추가하면 `srcs` 에도 넣어야 한다. 같은 편집에서.**
안 넣으면 어떻게 되냐면 — 컴파일 에러가 아니라 "그 파일이 없는 것처럼" 빌드된다.
`AGENTS.md` §3 이 "파일을 추가하면 같은 변경에서 `srcs` 를 갱신한다" 를 규칙으로
못 박아 둔 이유다.

증상이 특이하다. **"분명히 파일을 만들었는데 없다고 나온다"** 면
코드를 보기 전에 `BUILD.bazel` 의 `srcs`/`data` 를 먼저 본다.

### deps — 모듈 경계가 강제되는 지점

`deps` 에 적을 수 있는 것은 `libs/` 와 `contracts/` 다.
다른 서비스의 내부를 `deps` 에 적었다면 그건 **잘못된 import** 다.
"규칙이 그렇다" 가 아니라, 그렇게 하면 서비스가 독립 배포될 수 없기 때문이다.

### data — 실행 시점에 필요한 것

에이전트의 프롬프트 파일이 대표적이다. 프롬프트는 코드 안 문자열이 아니라
`prompts/` 폴더의 파일이고, Bazel `data` 로 참조된다.
`srcs` 는 "만들 때 필요한 것", `data` 는 "실행할 때 옆에 있어야 하는 것" 이다.

### visibility — 문을 열고 닫는 것

```
//visibility:public     아무나 참조 가능
//visibility:private    같은 패키지 안에서만
```

`tests/contract/BUILD.bazel` 이 `private` 인 게 좋은 예다.
계약 테스트용 생성 타깃을 다른 데서 가져다 쓰라고 만든 게 아니니 닫아 둔 것이다.

## 15. Bazel 의 전부는 그래프다

이 절만 이해하면 Bazel 의 나머지는 전부 따라온다.

Bazel 은 타깃과 타깃 사이의 의존을 **방향이 있는 그래프** 로 들고 있다.

```
   //contracts/openapi:scene-api-v1.yaml   (파일)
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
    :spring   :swift    :kotlin        (생성 타깃)
        │         │         │
        └────┬────┴────┬────┘
             ▼         ▼
      :scene_api_contract_test          (테스트 타깃)
```

이 그래프 하나로 아래가 전부 나온다.

**증분 빌드** — `scene-api-v1.yaml` 을 고치면 아래로 흐르는 것만 다시 만든다.
안 고쳤으면 아무것도 안 만든다.

**캐시** — 각 노드의 입력 지문이 같으면 결과를 다시 쓰지 않고 꺼낸다.
그래서 CI 가 `~/.cache/bazel` 을 캐시해 두는 것이다(`.github/workflows/ci.yml`).

**영향 범위 계산** — 화살표를 거꾸로 타면 "이걸 고치면 뭐가 영향받나" 가 나온다.
`just rdeps <타깃>` 이 그것이다.

**병렬 실행** — 서로 의존하지 않는 노드는 동시에 만들 수 있다. Bazel 이 알아서 한다.

**여기서 나오는 결론:** 그래프가 정확해야 위의 넷이 전부 성립한다.
`BUILD.bazel` 을 정확하게 쓰라는 잔소리는 결국 **그래프를 거짓말하지 말라** 는 뜻이다.
`srcs` 를 빠뜨리면 Bazel 은 "이 파일은 이 타깃과 무관하다" 고 믿고,
그 파일을 고쳐도 다시 만들지 않는다. 캐시가 틀린 답을 준다.

## 16. 격리 — Bazel 이 까다롭게 구는 진짜 이유

[[#격리|격리(hermeticity)]]는 **"같은 입력이면 언제 어디서 돌려도 같은 결과"** 를 뜻한다.
Bazel 의 캐시와 원격 실행은 전부 이 전제 위에 서 있다.
전제가 깨지면 캐시가 거짓말을 하고, 그게 제일 찾기 어려운 버그가 된다.

그래서 네 가지가 금지다.

```
✗ 호스트 툴체인 금지
    "내 맥에 깔린 JDK" 를 쓰지 않는다. 컴파일러·인터프리터·SDK 는
    MODULE.bazel 이 선언하고 Bazel 이 직접 받는다.
    → 머신에 뭔가 깔려 있어서 빌드가 성공하고 있다면,
      그 툴체인이 tools/bazel/toolchains/ 에 빠진 것이다.

✗ 빌드 시점 네트워크 금지
    빌드 중에 뭔가를 다운로드하면 안 된다. 외부 의존성은 전부
    MODULE.bazel 에 고정되고 MODULE.bazel.lock 에 못 박힌다.

✗ 절대 경로 금지
    /Users/... , $HOME , 머신마다 다른 경로 전부 금지.
    스크립트는 REPO_ROOT 기준 상대 경로만 쓴다.

✗ 시각·난수 금지
    출력에 타임스탬프나 랜덤이 들어가면 같은 입력에 다른 결과가 나온다.
```

`.bazelrc` 의 `build --incompatible_strict_action_env` 가 이걸 거드는 플래그다 —
빌드 액션에 넘기는 환경변수를 고정해서 호스트 환경 차이를 무시한다.

**격리는 조용히 깨진다.** 그래서 `CLAUDE.md` §4 가 굳이 한 번 더 반복해 적어 뒀다.

## 17. MODULE.bazel — 바깥 세계에서 뭘 가져오는가

### 이 파일이 유일한 창구다

외부 의존성을 선언하는 곳은 `MODULE.bazel` **하나뿐** 이다.
옛날 방식인 `WORKSPACE` 는 쓰지 않는다. 이 새 방식을 [[#bzlmod|bzlmod]] 라고 부른다.

```python
module(
    name = "scenetrip",
    version = "0.1.0",
    compatibility_level = 1,
)

bazel_dep(name = "bazel_skylib", version = "1.8.1")
bazel_dep(name = "platforms", version = "1.0.0")
bazel_dep(name = "rules_pkg", version = "1.0.1")
bazel_dep(name = "buildifier_prebuilt", version = "6.4.0", dev_dependency = True)
bazel_dep(name = "openapi_tools_generator_bazel", version = "0.2.3")
```

- `bazel_dep` 한 줄 = 외부 모듈 하나를 이름과 버전으로 가져온다.
  가져오면 `@이름//...` 라벨로 참조할 수 있게 된다.
- `dev_dependency = True` 는 "이 저장소를 개발할 때만 필요하고,
  누가 우리를 의존할 땐 안 따라간다" 는 뜻.
- 버전은 [registry.bazel.build](https://registry.bazel.build) 에서 확인한다.

### use_extension — 규칙만으로 안 될 때

```python
openapi_gen = use_extension("@openapi_tools_generator_bazel//:extension.bzl", "openapi_gen")
openapi_gen.client(
    sha256 = "1cf0c80de12c0fdc8594289c19e414b402108ef10b8dd0bfda1953151341ab5d",
    version = "7.2.0",
)
use_repo(openapi_gen, "openapi_tools_generator_bazel_cli")
```

이건 "확장" 이다. OpenAPI 생성기 본체는 자바 CLI JAR 파일인데,
그걸 **버전과 SHA256 지문까지 못 박아** 받아 온다.
지문을 고정했으니 같은 입력이면 같은 코드가 나온다 — 이게 [[#격리|격리]] 를 지키는 방식이다.

### 잠금 파일

`MODULE.bazel.lock` (약 400줄)은 **기계가 쓰고 기계가 읽는 파일** 이다.
"선언한 버전들을 실제로 해석했더니 정확히 이 조합이더라" 를 못 박아 둔다.

```
MODULE.bazel 을 고쳤다
        │
        ▼
just deps-update        (내부적으로 bazel mod tidy)
        │
        ▼
MODULE.bazel.lock 이 바뀐다
        │
        ▼
같은 커밋에 함께 넣는다   ← 이걸 빠뜨리면 다른 사람 머신에서 다른 버전이 잡힌다
```

### 지금은 대부분이 주석이다

`MODULE.bazel` 에서 Java, Swift, Kotlin, Python, protobuf, OCI 이미지 규칙은
전부 **주석 블록** 으로 들어 있다. 실수가 아니라 방침이다 —

> 언어별 규칙 세트는 그 언어의 첫 모듈이 들어올 때 추가한다.
> 아무도 의존하지 않는 규칙으로 이 파일을 채우지 않는다.

주석에는 확인해 둔 버전 후보까지 적혀 있어서, 첫 Spring 서비스를 만들 때
그 블록의 주석만 풀면 된다.

### 버전은 어떻게 통일되나

```
.bazelversion  →  "8.0.0"
       ▲
       │ 읽는다
   bazelisk        ← 우리가 실제로 설치하는 것. "bazel" 이라는 이름으로 깔린다
       │
       ▼
   그 버전의 진짜 Bazel 을 받아서 실행
```

즉 우리는 Bazel 을 설치하지 않는다. **bazelisk 를 설치하고,
그게 `.bazelversion` 을 보고 알아서 맞춘다.** 그래서 "내 맥은 되는데 CI 는 안 돼" 가
Bazel 버전 때문일 일이 없다.

## 18. .bazelrc 와 config — 플래그를 이름으로 부르기

Bazel 은 플래그가 수백 개다. 매번 손으로 붙이면 사람마다 달라지고, 로컬과 CI 가 어긋난다.
그래서 `.bazelrc` 에 **이름표를 붙여** 둔다.

```
# 언제나 적용되는 것
build --verbose_failures
build --incompatible_strict_action_env
build --symlink_prefix=bazel-

test --test_output=errors
test --build_tests_only

# 이름표가 붙은 묶음
build:debug   --compilation_mode=dbg
build:release --compilation_mode=opt
build:release --stamp

build:ci --announce_rc
build:ci --show_timestamps
build:ci --keep_going
test:ci  --flaky_test_attempts=2
```

`build:release` 처럼 콜론 뒤에 이름이 붙은 줄은 `--config=release` 를 줬을 때만 켜진다.

```
just build-release   →   bazel build --config=release //...
                                     └─ .bazelrc 의 build:release 줄들이 켜진다
```

핵심 원칙: **명령줄에 임시 플래그를 붙이지 말고 여기에 config 를 추가한다.**
그래야 로컬과 CI 가 구조적으로 같은 플래그를 쓴다.

파일 맨 끝에 이 줄이 있다.

```
try-import %workspace%/.bazelrc.user
```

`.bazelrc.user` 는 개인용 파일이고 gitignore 대상이다. `try-` 라서 없어도 에러가 아니다.
**빌드 성공이 이 파일에 의존해서는 안 된다** — 그러면 나만 되는 빌드가 된다.

파일 안에 원격 캐시 설정도 주석으로 준비돼 있다. 공용 캐시가 생기면 주석만 풀면 된다.

## 19. 태그와 테스트 레인

[[#태그|태그]]는 타깃에 붙이는 분류표다. `just` 가 이걸로 그래프를 잘라 낸다.

```
tags = ["unit"]              빠르고 격리됨 → just test 에서 돈다
tags = ["integration"]       컨테이너·DB 필요 → just test-integration
tags = ["e2e"]               전체 스택 → just test-e2e
tags = ["slow"]              30초 초과 → 빠른 레인에서 제외
tags = ["manual"]            //... 와일드카드에 절대 안 잡힘 (배포·푸시·파괴적 작업)
tags = ["requires-network"]  비격리 → 샌드박스·원격 실행에서 제외
```

레인이 어떻게 갈리는지는 `tools/just/test.just` 를 보면 그대로 보인다.

```
just test              →  --test_tag_filters=-integration,-e2e,-slow,-manual
                                             └ 마이너스는 "제외"
just test-integration  →  --test_tag_filters=integration
just test-e2e          →  --test_tag_filters=e2e   (대상은 //tests/e2e/...)
just test-load         →  --test_tag_filters=manual  ← 게이트에 절대 안 들어간다
```

### 태그를 잘못 달면

```
느린 테스트에 slow 를 안 붙임      →  빠른 레인이 느려진다. 다들 안 돌리게 된다.
통합 테스트에 integration 안 붙임  →  빠른 레인에서 DB 없이 돌다가 깨진다.
단위 테스트에 manual 을 붙임       →  ★ 아무 레인에도 안 잡혀 영영 안 돈다.
```

세 번째가 최악이다. 초록불인데 아무것도 검증하지 않는 상태.
그래서 `tests/README.md` 가 "태그를 의도적으로 붙일 것" 이라고 강조한다.

### 빈 레인은 실패가 아니다

레인은 전부 `tools/scripts/bazel-test.sh` 를 거친다.

```bash
"${BAZEL:-bazel}" test "$@"
code=$?
if [ "$code" -eq 4 ]; then           # 4 = "일치하는 테스트 대상 없음"
  warn "일치하는 테스트 대상이 없습니다: $*"
  exit 0                              # 경고로 낮춘다
fi
exit "$code"                          # 진짜 실패는 그대로 통과시킨다
```

모듈을 만들어 가는 중에 레인이 비어 있는 건 정상이라는 판단이다.
**하지만 진짜 테스트 실패는 그대로 게이트를 막는다.** 이 구분이 중요하다.

## 20. 타깃 이름 규칙 — 읽지 않고도 맞히기

이름을 통일해 두면 `BUILD.bazel` 을 열어 보지 않고도 라벨을 조립할 수 있다.
사람에게도 편하지만, 진짜 이유는 **AI 가 파일을 안 읽고 명령을 만들 수 있게** 하는 것이다.

| 타깃 이름 | 뜻 |
| --- | --- |
| `:<모듈명>` | 그 모듈의 주 라이브러리·바이너리 (폴더 이름과 같다) |
| `:bin` | 실행 진입점 |
| `:unit_test` | 빠르고 격리된 테스트 |
| `:integration_test` | 픽스처·컨테이너가 필요한 테스트 (`integration` 태그) |
| `:image` | OCI 컨테이너 이미지 |
| `:push` | 이미지 푸시 (항상 `manual` 태그) |
| `:lint` | 모듈 전용 린트 |
| `:<이름>_proto` / `:<이름>_<언어>_proto` | proto 라이브러리와 언어 바인딩 |

그래서 `services/scene-api` 라는 서비스가 생겼다면, 파일을 안 봐도 이렇게 칠 수 있다.

```
just build //services/scene-api/...
just test  //services/scene-api:unit_test
just run   //services/scene-api:bin
```

이 규칙은 `tools/templates/module/BUILD.bazel.tmpl` 에 주석으로 박혀 있어서,
새 모듈은 처음부터 이 이름들을 갖고 태어난다.

## 21. 그래프에 질문하는 법

Bazel 의 숨은 기능. `tools/just/bazel.just` 에 레시피로 감싸져 있다.

```
just targets                 이 저장소의 모든 바이너리·라이브러리 타깃 목록
just test-targets            모든 테스트 타깃 목록
just query 'deps(//X:Y)'     X:Y 가 의존하는 것 전부  (아래로)
just rdeps //X:Y             X:Y 에 의존하는 것 전부  (위로 — 영향 범위)
just why //A:a //B:b         A 가 B 에 의존하게 된 경로를 그래프로
```

언제 쓰냐면:

- **"이거 고치면 뭐가 깨지지?"** → `just rdeps`
- **"왜 이 라이브러리가 여기까지 딸려 오지?"** → `just why`
- **"이 저장소에 뭐가 있지?"** → `just targets`

`just why` 는 특히 좋다. 의도치 않은 의존이 생겼을 때 "누가 끌어왔는지" 를
추측 대신 답으로 알려 준다.

## 22. buildifier 와 Gazelle

### buildifier — BUILD 파일 전용 포매터·린터

`BUILD.bazel` 과 `.bzl` 파일은 파이썬처럼 생겼지만 파이썬이 아니다([[#Starlark|Starlark]]).
그래서 전용 도구를 쓴다.

```
just fmt        →  bazel run //:buildifier         제자리에서 고친다
just fmt-check  →  bazel run //:buildifier_check   어긋나면 실패한다
just lint       →  bazel run //:buildifier_check   + 언어별 린터
```

`just check` 가 `fmt-check lint build test` 순서라 BUILD 파일 포맷도 게이트에 포함된다.

### Gazelle — BUILD 파일 자동 생성기 (지금은 없다)

Gazelle 은 소스를 스캔해 `BUILD.bazel` 을 자동으로 써 주는 도구다.
백업본 저장소에는 있었지만 **현재 저장소에서는 빠졌다.** 이유가 `MODULE.bazel` 에 적혀 있다.

- Gazelle 은 Go·proto 만 내장 지원이고, 다른 언어는 **언어별 확장을 따로 붙이는** 구조다.
- 우리 스택(Java/Swift/Kotlin/Python)은 확장을 넷 다 붙여야 하는데,
  그러면 관리 대상이 넷 늘어난다.
- Gazelle 바이너리 자체가 Go 로 만들어져 있어 `rules_go` 를 함께 끌고 온다.
  저장소에 Go 코드가 한 줄도 없는데 Go 규칙이 들어오는 셈이다.

그래서 결론은 **"쓸 수 없다" 가 아니라 "지금 붙일 때가 아니다"** 다.
당분간 `BUILD.bazel` 은 손으로 쓴다. [[#20. 타깃 이름 규칙 — 읽지 않고도 맞히기|이름 규칙]] 을
지키면 손으로 써도 라벨은 여전히 예측 가능하다.

## 23. bazel- 로 시작하는 심볼릭 링크

빌드를 한 번 돌리면 저장소 루트에 이런 게 생긴다.

```
bazel-out/      bazel-bin/      bazel-testlogs/      bazel-<저장소이름>/
```

전부 **심볼릭 링크** 다. 실제 산출물은 저장소 밖(`~/.cache/bazel` 아래)에 있고,
이건 그리로 가는 바로가기다.

- `.bazelrc` 의 `build --symlink_prefix=bazel-` 이 이 접두사를 정한다.
- `.gitignore` 의 `/bazel-*` 가 커밋을 막는다.
- 루트 `BUILD.bazel` 과 `.bazelignore` 가 도구들이 이걸 훑지 않게 제외한다.

**절대 커밋하지 않는다.** `AGENTS.md` §9 의 금지 목록에 명시돼 있다.

## 24. Bazel 증상별 원인 사전

실제로 자주 겪는 것들만.

**"분명히 파일을 만들었는데 없다고 나온다"**
→ `BUILD.bazel` 의 `srcs` 또는 `data` 에 안 넣었다. 코드를 보기 전에 BUILD 를 본다.

**"`//tests/contract/...` 를 못 찾는다고 에러가 난다"**
→ 그 폴더에 `BUILD.bazel` 이 없다. 파일이 없으면 Bazel 에게 그 폴더는 패키지가 아니다.
"대상 없음(경고)" 이 아니라 **에러** 로 처리된다.

**"테스트 대상 없음(경고)이 뜬다"**
→ 정상이다. 아직 그 레인에 테스트가 없다. `bazel-test.sh` 가 경고로 낮춘 것이다.

**"로컬은 초록인데 CI 는 빨강이다"**
→ 이 저장소 설계상 이건 **레시피의 버그** 다. 로컬에서 `just ci` 를 돌려 재현한다.
CI 는 `just ci-full` 을 부를 뿐이라 다른 명령을 돌리고 있지 않다.

**"내 맥에서만 빌드가 된다"**
→ [[#격리|격리]] 위반이다. 호스트에 깔린 도구를 쓰고 있거나 절대 경로가 섞였다.
빠진 툴체인을 `tools/bazel/toolchains/` 에 등록해야 한다.

**"뭔가 계속 이상하다"**
→ `just clean` (산출물 삭제). 그래도 이상하면 `just clean-all`
(분석 캐시까지 날림, 느림, 확인 절차 있음). 이건 최후 수단이다.

**"의존성을 추가했는데 못 찾는다"**
→ `MODULE.bazel` 만 고치고 `just deps-update` 를 안 돌렸다.
그리고 바뀐 `MODULE.bazel.lock` 을 같은 커밋에 넣어야 한다.

**"`glob` 이 비어서 에러가 난다"**
→ `.bazelrc` 의 `--incompatible_disallow_empty_glob` 때문이다.
빈 결과를 허용하려면 `glob([...], allow_empty = True)` 라고 명시해야 한다.
템플릿의 `filegroup` 이 그렇게 돼 있다.

## 25. 지금 이 저장소의 Bazel 진도표

**실제로 존재하는 Bazel 타깃 전부 (현재 저장소 기준):**

```
//:buildifier                              BUILD 파일 포맷 고치기
//:buildifier_check                        BUILD 파일 포맷 검사
//contracts/openapi:scene_api_spring       명세 → Spring 서버 인터페이스
//tests/contract:scene_api_swift           명세 → iOS 클라이언트
//tests/contract:scene_api_kotlin          명세 → Android 클라이언트
//tests/contract:scene_api_contract_test   위 셋이 다 생성되는지 검사 (tags=["unit"])
```

**아직 없는 것:**

```
✗ 언어 규칙 (rules_java, rules_swift, rules_kotlin, rules_python)
     → MODULE.bazel 에 주석으로 대기 중. 첫 모듈이 들어올 때 주석 해제.
✗ 툴체인 등록          → tools/bazel/toolchains/ 는 README 만 있다
✗ 재사용 매크로         → tools/bazel/defs/ 도 README 만 있다
✗ 컨테이너 이미지 규칙  → rules_oci 주석 대기
✗ proto 규칙            → contracts/proto 는 아직 비어 있다
✗ BUILD 자동 생성       → Gazelle 은 의도적으로 뺐다
✗ 원격 캐시             → .bazelrc 에 설정 블록만 주석으로 준비
```

**그래서 지금 `just build` 를 돌리면** 실제로 도는 일은
"OpenAPI 명세를 파싱해서 세 언어 코드가 나오는지 확인" 정도다.
그것만으로도 명세가 깨지면 게이트가 막힌다는 점이 이 설계의 영리한 부분이다.

---

# 4부 — just 와 명령 계층

## 26. 4층 구조

명령 하나가 실제로 실행되기까지 네 층을 지난다.

```
  ┌─────────────────────────────────────────────────────────┐
  │ 1층   justfile                    루트. 변수 정의 + import  │
  │       - BAZEL, ALL(//...), REPO_ROOT                      │
  │       - tools/just/*.just 9개를 import                    │
  │       - check, ci, versions 만 직접 정의                   │
  └────────────────────────┬────────────────────────────────┘
                           │
  ┌────────────────────────▼────────────────────────────────┐
  │ 2층   tools/just/*.just            영역별 레시피            │
  │       bazel · dev · test · docs · infra · k8s · ci ·      │
  │       agent · scaffold                                    │
  │       레시피 본문은 짧게. 5줄 넘으면 3층으로 민다.            │
  └────────────────────────┬────────────────────────────────┘
                           │
  ┌────────────────────────▼────────────────────────────────┐
  │ 3층   tools/scripts/*.sh           실제 로직 30여 개        │
  │       전부 _lib.sh 를 source → log/warn/die/REPO_ROOT     │
  │       전부 set -euo pipefail, 전부 멱등                    │
  └────────────────────────┬────────────────────────────────┘
                           │
  ┌────────────────────────▼────────────────────────────────┐
  │ 4층   bazel / kubectl / helm / terraform                  │
  │       실제 도구. 사람이 직접 부르지 않는다.                  │
  └─────────────────────────────────────────────────────────┘
```

### 왜 굳이 네 층인가

**2층이 있는 이유** — 저장소가 커져도 `just --list` 를 훑을 수 있게. 영역별로 파일이 갈린다.

**3층이 있는 이유** — justfile 문법 안에서 긴 셸을 쓰면 이스케이프 지옥이 된다.
그리고 스크립트는 테스트하고 `shellcheck` 를 돌릴 수 있다.

**4층을 직접 안 부르는 이유** — 플래그 표면이 넓고 미묘하게 틀리기 쉽다.
감싸 두면 레인별 올바른 플래그를 **한 번만** 정의하고 모두가 똑같이 쓴다.
ADR 0001 의 "Bazel 만 쓰고 래퍼를 두지 않기" 기각 사유가 정확히 이것이다.

### 실제 예로 따라가기

```
사람:      just test-contract
             │
2층:       tools/just/test.just
           ./tools/scripts/bazel-test.sh //tests/contract/...
             │
3층:       bazel-test.sh
           bazel test //tests/contract/... ; 종료코드 4면 경고로 낮춤
             │
4층:       bazel
           tests/contract/BUILD.bazel 의 build_test 실행
             │
결과:      명세가 세 언어로 다 생성되는지 확인
```

## 27. 레시피 문법 최소한

`.just` 파일을 읽을 때 필요한 것만.

```just
# 이 주석이 just --list 에 설명으로 나온다   ← 레시피 바로 위 마지막 주석 줄
[group('build')]                              ← --list 에서 묶이는 그룹
build *targets=ALL:                           ← 이름 *가변인자=기본값
    {{BAZEL}} build {{targets}}               ← 본문 (탭/스페이스 들여쓰기)
```

- `{{변수}}` — 변수 치환. `BAZEL`, `ALL`, `REPO_ROOT` 는 루트 justfile 이 정의한다.
- `*targets=ALL` — 안 주면 `//...` 이 들어간다. 그래서 `just build` 는 전체 빌드.
- `[confirm("문구")]` — 실행 전에 y/n 을 묻는다. 공용 상태를 바꾸는 레시피는 전부 이걸 단다.
- `recipe: dep1 dep2` — 콜론 뒤는 선행 레시피. `check: fmt-check lint build test` 처럼.
- `@` 로 시작하는 줄 — 명령 자체를 출력하지 않고 결과만 보여 준다.

**설명 주석 함정 하나:** just 는 레시피 바로 위 **마지막 주석 줄** 만 설명으로 쓴다.
여러 줄을 쓸 거면 요약 문장을 맨 아래에 둬야 목록에 제대로 나온다.
(`tools/just/README.md` 가 이걸 콕 집어 적어 뒀다)

## 28. check 와 ci 는 어떻게 다른가

```
just check :  fmt-check → lint → build → test
              ─────────────────────────────────
              PR 올리기 전 게이트. 빠르다. 매번 돌린다.

just ci    :  gen-check → fmt-check → lint → build → test → test-integration
              ────────────────────────────────────────────────────────────
              CI 가 하는 걸 그대로. 앞에 gen-check, 뒤에 통합 테스트가 더 붙는다.
```

`gen-check` 가 하는 일이 재밌다.

```bash
gen-check: gen
    @git diff --exit-code -- . || {
        echo "생성물이 최신이 아닙니다 — 'just gen' 을 실행하고 결과를 커밋하세요";
        exit 1;
    }
```

`just gen` 을 돌린 다음 **git diff 가 비어 있는지** 본다.
diff 가 생겼다는 건 "커밋된 생성물이 낡았다" 는 뜻이니 실패시킨다.
사람이 잊어도 기계가 잡는다.

**CI 워크플로가 실제로 부르는 건 `just ci-full` 이다.**

```
ci-full: gen-check fmt-check lint
    ./tools/scripts/bazel-test.sh //... --config=ci
```

`--config=ci` 로 [[#18. .bazelrc 와 config — 플래그를 이름으로 부르기|.bazelrc 의 ci 묶음]] 이
켜진다 — 타임스탬프 출력, `--keep_going`(하나 깨져도 계속 가서 최대한 많은 신호를 모음),
불안정 테스트 2회 재시도.

---

# 5부 — 문서들의 연결 관계

여기가 질문의 핵심이었던 "안내 문서들이 어떻게 연결돼 있는가" 다.

## 29. 문서 지도

```
                          README.md
                       (현관 — 한글)
                             │
                 ┌───────────┼────────────┐
                 │           │            │
                 ▼           ▼            ▼
          AGENTS.md      docs/       docs/installs/
         (계약 — 영문)   (전체 인덱스)   (환경 설치)
                 │
                 │  "이 규칙 안에서 어떻게 움직이나"
                 ▼
          CLAUDE.md
        (절차 — 영문)
                 │
                 │  "이 모듈에서는 다르다"
                 ▼
    <모듈>/CLAUDE.md      ← agents/ 모듈은 템플릿이 자동 생성
                 │
                 ▼
     <모듈>/README.md      목적·포트·계약·의존성

  ─────────────────────────────────────────────────────────

  AGENTS.md 가 인용되는 곳 (규칙이 실제로 쓰이는 지점)

    §2  배치 결정표    ←── README.md · docs/README.md · 모든 디렉터리 README
    §3  모듈 해부      ←── services/apps/agents README · 템플릿
    §4.1 타깃 이름     ←── BUILD.bazel.tmpl · tools/bazel/README.md
    §4.2 태그          ←── tests/README.md · docs/qa/README.md · tests/contract/BUILD.bazel
    §4.3 격리          ←── MODULE.bazel 주석 · CLAUDE.md §4
    §5  just 규칙      ←── justfile 머리말 · tools/just/README.md
    §8  문서 배치      ←── docs/README.md · CLAUDE.md §10
    §9  보안           ←── platform/README.md · .gitignore

  ─────────────────────────────────────────────────────────

  ADR 이 근거를 대는 곳

    ADR 0001 (Bazel + just)  ──► justfile · .bazelrc · AGENTS.md 의 두 불변식
    ADR 0002 (스택 확정)      ──► MODULE.bazel · scaffold.just · libs/ 하위 폴더
```

## 30. 규칙이 충돌할 때의 우선순위 사슬

`CLAUDE.md` §1 에 명시된 순서다.

```
사용자의 명시적 지시
      >  <모듈>/CLAUDE.md          (그 모듈 안에서만)
         >  루트 CLAUDE.md          (작업 절차)
            >  AGENTS.md            (저장소 계약)
               >  도구의 기본 동작
```

읽는 법: **아래로 갈수록 일반적이고, 위로 갈수록 구체적이다.**
구체적인 게 이긴다. 그래서 에이전트 모듈이 자기 폴더에 `CLAUDE.md` 를 두면
그 안에서는 루트보다 그게 우선이다.

`AGENTS.md` 와 `docs/engineering/` 이 어긋나면 **AGENTS.md 가 이기고 문서를 고친다.**
(docs/engineering/README.md 가 직접 그렇게 적어 뒀다)

## 31. 문서마다 한 줄 역할과 읽는 시점

**루트**

- `README.md` — 현관. 처음 온 사람이 여기서 시작한다. 설치 가이드로 보낸다.
- `AGENTS.md` — 규칙의 정본. 세션에 한 번 읽는다. 규칙이 헷갈릴 때 되돌아온다.
- `CLAUDE.md` — 작업 절차 체크리스트. 코드 고칠 때 옆에 둔다.

**칸마다의 안내판** — `services/`, `apps/`, `agents/`, `libs/`, `contracts/`,
`platform/`, `tests/`, `tools/`, `third_party/` 각각의 `README.md`.
**그 칸에 뭘 넣고 뭘 넣으면 안 되는지** 를 적어 둔다. 새 파일 자리를 정할 때 읽는다.

**docs/ 안**

- `docs/README.md` — 문서 전체 인덱스. 새 문서를 쓰기 전에 자리를 정하러 온다.
- `docs/engineering/onboarding.md` — 첫날 문서. 세팅부터 첫 변경까지.
- `docs/architecture/adr/` — 왜 이렇게 됐는지. 결정에 의문이 생기면 온다.
- `docs/project/plans/` — 코드보다 먼저 쓰는 구현 계획. 티켓 하나에 문서 하나.
- `docs/installs/` — 로컬 환경 설치. **순서대로 읽어야 한다** (SigNoz 는 k8s 를 전제).
- `docs/education/` — 35슬라이드 강의 덱. `just slides` 로 연다.
- 나머지(`product`, `api`, `qa`, `ops`, `ai`) — 해당 일을 할 때 온다.

**tools/ 안**

- `tools/just/README.md` — 레시피를 추가할 때 읽는다. 4가지 규칙이 적혀 있다.
- `tools/scripts/README.md` — 스크립트를 쓸 때. `pending:` 자리표시자 개념 설명.
- `tools/templates/README.md` — 모듈 관례를 바꿀 때. 템플릿도 같이 고쳐야 한다.

## 32. 상황별 읽기 순서

**저장소를 처음 열었다**

```
README.md
  → docs/engineering/onboarding.md
    → AGENTS.md §1·§2  (뭐가 어디 있는지)
      → just --list     (뭘 할 수 있는지)
```

**코드를 처음 고친다**

```
CLAUDE.md §1 (세션 시작 프로토콜)
  → 건드릴 모듈의 README.md
    → 그 모듈에 CLAUDE.md 가 있으면 그것도
      → AGENTS.md §4 (Bazel 규칙)
```

**API 를 바꾼다**

```
contracts/README.md   (계약 우선 3단계)
  → contracts/<종류>/README.md
    → docs/api/README.md   (사용법 문서도 같이 고쳐야 하나 확인)
```

**왜 이렇게 만들었는지 궁금하다**

```
docs/architecture/adr/  ← 결정의 이유는 전부 여기
  → 관련 docs/project/plans/  ← 그때 어떻게 하기로 했나
```

**로컬에서 서버를 띄워 보고 싶다**

```
docs/installs/k8s_install.md
  → docs/installs/signoz_install.md   (순서 지킬 것)
    → platform/kind/README.md          (포트 매핑이 왜 그런지)
      → just cluster-up
```

## 33. 문서가 코드에 강제되는 지점

문서가 그냥 글로 남지 않고 **기계가 검사하는 지점** 이 몇 군데 있다.

```
docs-index-check.sh    →  docs/ 아래 모든 디렉터리에 README.md 가 있나,
                          인덱스에 없는 고아 문서가 없나
docs-lint.sh           →  마크다운 스타일, 죽은 링크
gen-check              →  생성물이 최신인가 (git diff 로)
buildifier_check       →  BUILD 파일 포맷·린트
prompt-lint.sh         →  프롬프트 파일의 프런트매터·필수 변수·길이
workflow-lint.sh       →  GitHub Actions 워크플로 파일 자체
security-scan.sh       →  의존성 감사 + 시크릿 탐지 (CI 별도 잡)
```

그리고 사람이 지켜야 하는 대신 **차단되는** 것도 있다.

```
require_kind_context()  →  kubectl 컨텍스트가 kind-scenetrip 이 아니면 실행 거부
[confirm]               →  클라우드·공용 상태를 바꾸는 레시피 전부
tags = ["manual"]       →  //... 와일드카드에 배포·푸시 타깃이 안 걸리게
```

**설계 철학이 여기서 드러난다.** 사람이 매번 기억해야 하는 규칙은 규칙이 아니라고 보고,
가능한 건 기계가 막게 만들어 뒀다.

---

# 6부 — 흐름으로 다시 보기

## 34. 기능 하나가 태어나서 배포되기까지

지금까지 나온 칸이 전부 등장하는 한 바퀴다.

```
① 기획         docs/product/prd/<기능>.md
               문제·범위·성공 지표·하지 않을 것

② 계획         docs/project/plans/<기능>.md
               모듈 2개 이상 / 계약 변경 / 의존성 추가 / 100줄 초과
               넷 중 하나라도 걸리면 코드보다 먼저 쓴다

③ 결정         docs/architecture/adr/NNNN-....md
               오래 영향을 남기는 결정이면 ADR 로 승격

④ 계약         contracts/openapi/scene-api-v1.yaml  ← 먼저 고친다
               just gen / just build 로 스텁이 나온다

⑤ 테스트       services/scene-api/tests/...  (모듈 안)
               just test <타깃> — 의도한 이유로 실패하는지 확인

⑥ 구현         services/scene-api/src/...
               + BUILD.bazel 을 같은 편집에서 갱신 ★

⑦ 게이트       just check
               fmt-check → lint → build → test

⑧ 문서         services/scene-api/README.md 갱신
               영향받은 docs/ 페이지 갱신

⑨ 커밋         feat(scene-api): ...
               타입(스코프): 명령형 요약

⑩ CI           .github/workflows/ci.yml → just ci-full

⑪ 이미지       just image scene-api      (빌드 + kind 노드에 적재)

⑫ 배포         just deploy scene-api local
               platform/kubernetes/scene-api/ 를 적용하고 롤아웃 대기

⑬ 관측         just signoz
               SigNoz UI 에서 service.name = scenetrip-scene-api 로 필터

⑭ 운영         docs/ops/runbooks/scene-api.md
               운영에 올라가기 전에 런북이 있어야 한다
```

④→⑥ 순서가 뒤집히면 안 된다는 게 계약 우선의 전부다.
⑥ 의 별표가 Bazel 에서 제일 자주 빠뜨리는 지점이다.

## 35. 새 언어 하나가 들어올 때

첫 Spring 서비스를 만든다고 하면 이 순서다.

```
1. MODULE.bazel 의 Java 주석 블록을 푼다
   (rules_java, rules_jvm_external — 버전은 풀 때 registry 에서 재확인)

2. just deps-update           → MODULE.bazel.lock 갱신

3. tools/bazel/toolchains/ 에 JDK 툴체인 등록
   ★ 여기가 격리의 갈림길. 등록 안 하면 "내 맥에 깔린 JDK" 를 쓰게 된다.

4. just new-service scene-api  → 템플릿으로 모듈 골격 생성

5. services/scene-api/BUILD.bazel 의 자리표시자 filegroup 을
   진짜 java_library / java_binary / java_test 로 교체

6. tools/scripts/format.sh · lint.sh 에 자바 도구 연결
   (지금은 "미구현:" 을 출력하는 자리표시자다)

7. contracts/openapi 의 spring 생성 타깃을 deps 로 물린다
   → 컨트롤러가 그 인터페이스를 구현하면 계약 위반이 컴파일 오류가 된다

8. just check 로 게이트 확인
```

같은 언어의 **두 번째** 모듈부터는 1~3, 6 이 생략된다.
그래서 첫 모듈이 제일 비싸고, 그 비용을 ADR 0001 이 미리 인정해 뒀다.

---

# 부록 A — 용어 사전

여기 있는 항목은 문서 위쪽에서 `[[#용어]]` 로 링크해 두었다.

### 모노레포

여러 프로젝트를 저장소 하나에 두는 방식. 반대는 프로젝트마다 저장소를 따로 두는 폴리레포.
장점은 한 번의 변경으로 여러 모듈을 같이 고칠 수 있고 버전 어긋남이 없다는 것.
비용은 도구가 감당해야 할 규모가 커진다는 것 — 그래서 Bazel 을 쓴다.

### Bazel

구글이 만든 빌드·테스트 시스템. 언어에 상관없이 "무엇으로 무엇을 만드는가" 를
[[#의존성 그래프|그래프]] 로 표현하고, 바뀐 것만 다시 만든다.
공식 문서: [bazel.build](https://bazel.build/)

### bazelisk

Bazel 의 **버전 관리 래퍼**. `.bazelversion` 파일을 읽고 그 버전의 Bazel 을 자동으로
받아서 실행한다. 우리는 bazelisk 를 `bazel` 이라는 이름으로 설치해서 쓴다.
[github.com/bazelbuild/bazelisk](https://github.com/bazelbuild/bazelisk)

### just

명령 실행기. `justfile` 에 이름 붙인 명령(레시피)을 모아 두고 `just <이름>` 으로 부른다.
Make 와 비슷하지만 "파일을 만드는 것" 이 아니라 "작업을 실행하는 것" 에 맞춰져 있고,
인자 전달·그룹·`--list` 발견성이 좋다.
[github.com/casey/just](https://github.com/casey/just)

### 워크스페이스

Bazel 이 다루는 저장소 하나. `MODULE.bazel` 이 있는 폴더가 루트다.

### 패키지

`BUILD.bazel` 파일이 있는 폴더. 파일이 없으면 Bazel 에게 그 폴더는 패키지가 아니다.

### 타깃

`BUILD.bazel` 안에 선언된 항목 하나. "만들 수 있는 것" 하나.
라이브러리, 바이너리, 테스트, 이미지, 파일 묶음 전부 타깃이다.

### 라벨

타깃의 주소. `//패키지경로:타깃이름` 형식.
자세히는 [[#12. 워크스페이스 · 패키지 · 타깃 · 라벨]].

### 규칙 (rule)

"이런 것은 이렇게 만든다" 는 정의. `java_library`, `openapi_generator`, `build_test` 같은 것.
`load()` 로 가져와서 쓴다.

### 매크로 (macro)

규칙 여러 개를 묶어 한 번에 선언하게 해 주는 함수. `tools/bazel/defs/` 에 둔다.
같은 패턴이 세 번 나오면 매크로로 만든다.

### Starlark

`BUILD.bazel` 과 `.bzl` 파일이 쓰는 언어. 파이썬을 아주 많이 닮았지만
파일 입출력·네트워크·while 이 없는 **결정적인** 부분집합이다.
[[#격리|격리]] 를 지키려고 일부러 능력을 뺐다.

### 의존성 그래프

"A 를 만들려면 B 가 필요하다" 의 화살표 모음.
Bazel 의 증분 빌드·캐시·영향 범위 계산이 전부 여기서 나온다.
[[#15. Bazel 의 전부는 그래프다]]

### 격리 (hermeticity)

**같은 입력이면 언제 어디서 돌려도 같은 결과가 나오는 성질.**
호스트 도구 금지, 빌드 시점 네트워크 금지, 절대 경로 금지, 시각·난수 금지.
[[#16. 격리 — Bazel 이 까다롭게 구는 진짜 이유]]

### 해시

파일 내용을 짧은 문자열로 요약한 값. 내용이 1비트만 달라도 값이 완전히 달라진다.
Bazel 은 입력들의 해시로 "이거 전에 만든 적 있나" 를 판단한다. 지문이라고 생각하면 된다.

### 캐시

한 번 만든 결과를 저장해 두고 재사용하는 것. Bazel 은 로컬 캐시(`~/.cache/bazel`)를 쓰고,
공용 원격 캐시도 붙일 수 있다(`.bazelrc` 에 설정이 주석으로 준비돼 있다).

### 태그

타깃에 붙이는 분류표. 어느 테스트 레인에서 돌지, 와일드카드에 걸릴지를 결정한다.
[[#19. 태그와 테스트 레인]]

### 레인 (test lane)

테스트를 속도·필요 환경에 따라 나눈 묶음. 빠른(unit) · 통합 · e2e · 부하.
`just test`, `just test-integration`, `just test-e2e`, `just test-load`.

### bzlmod

Bazel 의 현재 의존성 관리 방식. `MODULE.bazel` 에 `bazel_dep` 으로 선언한다.
옛 방식인 `WORKSPACE` 는 이 저장소에서 쓰지 않는다.

### 툴체인

컴파일러·인터프리터·SDK 같은 "만드는 도구" 묶음.
Bazel 이 직접 받아서 버전을 고정한다. `tools/bazel/toolchains/` 에 등록한다.

### 계약 (contract)

모듈 사이의 통신 형식 정의. proto / OpenAPI / AsyncAPI / JSON Schema.
`contracts/` 에 손으로 쓰고, 거기서 코드가 생성된다.

### 스캐폴딩

새 모듈의 골격을 템플릿으로 찍어 내는 것. `just new-service` 등이 한다.

### 게이트

통과해야 다음으로 갈 수 있는 검사. 이 저장소의 게이트는 `just check` 다.

### 멱등 (idempotent)

여러 번 실행해도 결과가 같은 성질. `just cluster-up`, `just setup` 같은 것들이 그렇다.
이 저장소의 모든 스크립트가 지켜야 하는 성질이다.

### ADR

Architecture Decision Record. 결정 하나당 문서 하나.
**추가만 하고 고쳐 쓰지 않는다.** 기각한 대안과 그 이유를 반드시 남긴다.

### kind

Kubernetes IN Docker. Kubernetes 클러스터를 도커 컨테이너 안에 띄우는 도구.
클러스터가 **코드(`cluster.yaml`)** 라서 깨지면 지우고 한 줄로 다시 만든다.
[kind.sigs.k8s.io](https://kind.sigs.k8s.io/)

### SigNoz

오픈소스 관측(observability) 도구. 로그·메트릭·트레이스를 한곳에서 본다.
로컬에서는 `localhost:8080`. [signoz.io](https://signoz.io/)

### OpenTelemetry

애플리케이션이 로그·메트릭·트레이스를 내보내는 표준 규격.
SigNoz 는 이 규격으로 데이터를 받는다. [opentelemetry.io](https://opentelemetry.io/)

---

# 부록 B — 헷갈리는 짝 정리

**`contracts/` vs `docs/api/`**
`contracts/` 는 API 를 **정의** 하고 빌드 입력이 된다(기계가 읽는다).
`docs/api/` 는 API 를 **어떻게 쓰는지** 설명한다(사람이 읽는다). 명세는 docs 에 없다.

**`tests/` vs 모듈 안 `tests/`**
`tests/` 는 배포 단위 **둘 이상** 에 걸친 테스트만.
모듈 하나만 검증하면 그 모듈 안 `tests/` 에 코드 옆에 둔다.

**`platform/kind/` vs `tools/just/k8s.just` vs `tools/just/infra.just`**
`platform/kind/` 는 클러스터의 **정의**(cluster.yaml).
`k8s.just` 는 **로컬** 클러스터를 다루는 명령.
`infra.just` 는 **노트북 밖** — 레지스트리, terraform, 클라우드.

**`libs/` vs `third_party/`**
`libs/` 는 **우리가 쓴** 공유 코드. `third_party/` 는 **남의 코드를 통째로** 들여온 것.
남의 코드는 `MODULE.bazel` 로 버전 고정해 받는 게 우선이고, 벤더링은 최후 수단이다.

**`just check` vs `just ci`**
`check` 는 PR 전 로컬 게이트(빠름).
`ci` 는 CI 가 하는 걸 그대로(gen-check + 통합 테스트가 더 붙음).

**`just gen` vs `just deps-update`**
`gen` 은 **생성물**(스텁·클라이언트·목) 재생성.
`deps-update` 는 **외부 의존성 잠금 파일**(MODULE.bazel.lock) 갱신.

**`AGENTS.md` vs `CLAUDE.md`**
`AGENTS.md` 는 **무엇이 규칙인가**(구조·Bazel·just·품질 기준).
`CLAUDE.md` 는 **그 안에서 어떻게 움직이는가**(작업 루프·검증·응답 방식).

**`srcs` vs `data`**
`srcs` 는 **만들 때** 필요한 파일. `data` 는 **실행할 때** 옆에 있어야 하는 파일.
프롬프트 파일이 대표적인 `data` 다.

---

# 부록 C — 백업본과 현재 저장소의 차이

`~/backup/SceneTrip` 스냅샷과 현재 작업 저장소를 비교한 결과다.
구조와 규칙은 사실상 같고, 아래가 달라졌다. **원인은 대부분 ADR 0002(스택 확정)다.**

**언어가 바뀌었다**

```
백업본:  Go · TypeScript · Python        libs/go · libs/ts · libs/python
현재:    Java · Swift · Kotlin · Python  libs/java · libs/swift · libs/kotlin
                                          libs/python · libs/proto
```

**스캐폴딩 레시피가 갈라졌다**

```
백업본:  just new-app <이름> ts
현재:    just new-app-ios <이름>       (Swift)
         just new-app-android <이름>   (Kotlin)
         just new-service <이름>        (기본 java)
```

**Gazelle 이 빠졌다**
백업본에는 `//:gazelle` 타깃과 `rules_go`/`gazelle` 의존성이 있었다.
현재는 없고 `BUILD.bazel` 을 손으로 쓴다. 이유는 [[#22. buildifier 와 Gazelle]].
그래서 현재 `just gen` 은 `bazel run //:gazelle` 없이 `generate.sh` 만 부른다.

**실제 Bazel 타깃이 생겼다**
현재 저장소에는 `contracts/openapi/BUILD.bazel` 과 `tests/contract/BUILD.bazel` 이 있고
`scene-api-v1.yaml` 이라는 진짜 명세가 들어와 있다. 백업본에는 없다.

**문서가 늘었다**

```
+ docs/architecture/adr/0002-product-stack-spring-python-native-mobile.md
+ docs/engineering/onboarding.md
+ docs/project/plans/README.md
+ docs/project/plans/scene-api-search-map.md   (MZ2AZ-149)
+ tools/templates/contract/openapi.yaml.tmpl
```

**ci-full 이 안전해졌다**
백업본은 `bazel test //... --config=ci` 를 직접 불렀다.
현재는 `bazel-test.sh` 를 거쳐서, 테스트가 아직 없어도 CI 가 종료 코드 4 로 죽지 않는다.

**의존성 버전이 올라갔다**
`bazel_skylib` 1.7.1 → 1.8.1, `platforms` 0.0.10 → 1.0.0,
`openapi_tools_generator_bazel` 0.2.3 신규.

---

# 부록 D — 바깥 링크 모음

**빌드**

- [Bazel 공식 문서](https://bazel.build/)
- [Bazel 개념 — 워크스페이스·패키지·타깃](https://bazel.build/concepts/build-ref)
- [라벨 문법](https://bazel.build/concepts/labels)
- [BUILD 파일 작성법](https://bazel.build/concepts/build-files)
- [bzlmod (MODULE.bazel)](https://bazel.build/external/module)
- [Bazel 중앙 레지스트리](https://registry.bazel.build) — 의존성 버전 확인용
- [Starlark 언어](https://bazel.build/rules/language)
- [bazelisk](https://github.com/bazelbuild/bazelisk)
- [buildifier](https://github.com/bazelbuild/buildtools/tree/master/buildifier)

**명령**

- [just 매뉴얼](https://just.systems/man/en/)
- [just 저장소](https://github.com/casey/just)

**계약**

- [OpenAPI 명세](https://spec.openapis.org/oas/latest.html)
- [OpenAPI Generator](https://openapi-generator.tech/)
- [Protocol Buffers](https://protobuf.dev/)
- [AsyncAPI](https://www.asyncapi.com/)
- [JSON Schema](https://json-schema.org/)

**인프라·관측**

- [kind](https://kind.sigs.k8s.io/)
- [Kubernetes 문서](https://kubernetes.io/docs/home/)
- [Helm](https://helm.sh/)
- [SigNoz](https://signoz.io/)
- [OpenTelemetry](https://opentelemetry.io/)

**방법론**

- [Architecture Decision Records](https://adr.github.io/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)

---

## 한 장 요약

```
서랍장 하나에 회사 전체가 들어 있다 (모노레포)
    ↓
명령은 just 하나로 들어간다 (레시피 90여 개, just --list 로 전부 보임)
    ↓
빌드·테스트는 Bazel 하나가 한다 (언어가 넷이어도 그래프는 하나)
    ↓
모듈끼리는 contracts/ 의 약속으로만 대화한다 (명세 하나 → 코드 세 벌)
    ↓
규칙은 AGENTS.md 에, 절차는 CLAUDE.md 에, 이유는 ADR 에 남는다
    ↓
게이트는 just check 하나. 초록이 아니면 넘기지 않는다.
```

**Bazel 만 세 줄로 다시**

1. `BUILD.bazel` 은 그 폴더의 조립 설명서다. 파일을 추가하면 `srcs` 도 같이 고친다.
2. 라벨 `//경로:이름` 이 주소다. `//...` 은 전부라는 뜻이다.
3. 캐시와 증분 빌드는 [[#격리|격리]] 위에 서 있다. 호스트 도구·네트워크·절대 경로·난수 금지.
