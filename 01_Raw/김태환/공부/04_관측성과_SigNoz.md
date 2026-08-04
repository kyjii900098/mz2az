# 4. 관측성(Observability)과 SigNoz

> 클러스터에 앱을 올렸다([[03_kind와_로컬클러스터]]). 그런데 장애가 났는데 원인을 모른다.

## 관측성이 푸는 문제

서버 한 대에 앱 하나면 `ssh` 로 들어가서 로그 파일을 `tail` 하면 된다.
쿠버네티스에선 이게 안 된다.

- Pod가 여러 개고 계속 죽었다 살아난다 (죽으면 로그도 같이 사라짐)
- 서비스가 6개면 요청 하나가 6개를 거쳐 간다 — **어디서 느려졌는지 모름**
- 로그가 어느 Pod에 있는지 찾는 것부터 일

**관측성은 "시스템 밖에서 나오는 데이터만 보고 안에서 무슨 일이 일어나는지
알 수 있는가"** 다. 모니터링이 "미리 정한 것을 감시"라면, 관측성은 "예상 못 한
질문에도 답할 수 있는 상태"다.

## 세 가지 신호 (Three Pillars)

| 신호 | 무엇 | 답하는 질문 | 예 |
| --- | --- | --- | --- |
| **로그(Log)** | 시점별 이벤트 기록 | "무슨 일이 있었나?" | `ERROR 결제 실패: timeout` |
| **메트릭(Metric)** | 시간에 따른 수치 | "얼마나?" | CPU 80%, 초당 요청 120건 |
| **트레이스(Trace)** | 요청 하나의 전체 여정 | "어디서 느려졌나?" | API 200ms → DB 1800ms |

셋을 따로 보면 반쪽이고, **연결해서 봐야** 힘이 난다.

```
메트릭에서 에러율 급증 발견
  → 그 시각의 트레이스를 봄 → 특정 구간이 느림
    → 그 트레이스의 trace_id로 로그를 검색 → 원인 로그 발견
```

### 트레이스와 스팬 — 처음 보면 낯선 개념

**트레이스(Trace)** 는 요청 하나가 시스템을 통과한 전체 기록이다.
**스팬(Span)** 은 그 안의 개별 작업 단위다.

```
Trace (trace_id: abc123)  총 2100ms
├── Span: HTTP GET /api/scenes        2100ms
    ├── Span: 인증 검사                  20ms
    ├── Span: DB 쿼리                  1800ms  ← 범인
    └── Span: 응답 직렬화                 30ms
```

`trace_id` 는 요청이 서비스를 넘어가도 따라간다. 그래서 백엔드 3개를 거친 요청도
하나의 트레이스로 이어 볼 수 있다. **이게 마이크로서비스 디버깅의 핵심 도구다.**

## OpenTelemetry (OTel)

관측성 데이터를 **만들고 보내는 표준** 이다. 특정 회사 제품이 아니라 CNCF 표준.

### 왜 표준이 필요한가

옛날엔 관측 도구마다 전용 SDK를 앱에 심어야 했다. Datadog을 쓰다가 New Relic으로
바꾸려면 **앱 코드를 전부 고쳐야** 했다. OTel은 이 계층을 표준화해서, 앱은 OTel로만
내보내고 백엔드는 자유롭게 갈아끼울 수 있게 했다.

```
내 앱 ──OTel SDK/에이전트──> OTLP 프로토콜 ──> [ SigNoz / Datadog / Jaeger ... ]
                                              ↑ 여기만 바꾸면 됨
```

### 알아둘 용어

| 용어 | 의미 |
| --- | --- |
| **OTLP** | OpenTelemetry가 데이터를 보내는 전송 프로토콜 |
| **포트 4317** | OTLP over gRPC (기본) |
| **포트 4318** | OTLP over HTTP |
| **Collector** | 데이터를 받아 처리·전달하는 중계기 |
| **자동 계측(auto-instrumentation)** | **코드를 안 고치고** 에이전트만 붙여서 계측 |
| **`service.name`** | 이 데이터가 어느 서비스에서 왔는지 나타내는 이름. 검색의 1차 키 |

**자동 계측** 이 실용적으로 중요하다. Java면 JAR 에이전트를 붙이기만 하면
HTTP 요청, DB 쿼리, 로그가 자동으로 수집된다.

```bash
JAVA_TOOL_OPTIONS="-javaagent:$HOME/otel/opentelemetry-javaagent.jar" \
OTEL_SERVICE_NAME=scenetrip-scene-api \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
OTEL_LOGS_EXPORTER=otlp \
OTEL_TRACES_EXPORTER=otlp \
OTEL_METRICS_EXPORTER=otlp \
<앱 실행 명령>
```

Python(AI 에이전트)이면:

```bash
pip install opentelemetry-distro opentelemetry-exporter-otlp
opentelemetry-bootstrap --action=install

OTEL_SERVICE_NAME=scenetrip-trip-planner \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
OTEL_LOGS_EXPORTER=otlp \
opentelemetry-instrument python main.py
```

> [!warning] 에이전트 버전을 고정할 것
> `latest` 로 받으면 안 된다. Java 에이전트 2.14.0은 Spring Boot 4에서 모든 HTTP
> 응답 본문을 0바이트로 만들고(상태 코드는 정상이라 더 헷갈림) logback 계측이
> 기동 자체를 실패시킨 사례가 실측으로 확인됐다.

## SigNoz

**OpenTelemetry 데이터를 저장하고 보여주는 오픈소스 백엔드 + UI** 다.
로그·메트릭·트레이스를 한 곳에서 다룬다. Datadog의 오픈소스 대안 격.

### 구성 요소

가벼운 도구가 아니다. Pod 6개가 상주하고 PVC 18GiB를 잡는다.

| Pod | 역할 |
| --- | --- |
| `signoz-0` | UI + 쿼리 서비스 |
| `signoz-ingester-*` | **OTel Collector — 데이터가 들어오는 입구** |
| `chi-signoz-telemetrystore-clickhouse-*` | **ClickHouse — 로그·트레이스 실제 저장소** |
| `signoz-telemetrystore-clickhouse-operator-*` | ClickHouse 관리자 |
| `signoz-telemetrykeeper-zookeeper-0` | 코디네이션 |
| `signoz-metastore-postgres-0` | 대시보드·설정 메타데이터 |
| `signoz-telemetrystore-migrator-*` | 스키마 마이그레이션 (Job) |

> [!note] 정상인데 오해하기 쉬운 두 가지
> - **migrator가 `Completed` 인 것은 정상이다.** 스키마를 올리고 끝나는 Job이라 종료된다.
> - **`signoz-0` 의 RESTARTS가 2~3회인 것도 정상이다.** PostgreSQL·ClickHouse가
>   준비되기 전에 먼저 떠서 생기는 backoff이며, 의존 서비스가 뜨면 안정화된다.

ClickHouse는 **컬럼형 DB** 다. 로그처럼 대량으로 쌓이는 데이터를 빠르게 집계하는
데 특화되어 있어서 관측성 도구가 많이 쓴다.

### 설치 — foundryctl

SigNoz는 `foundryctl` 이라는 CLI로 설치한다. `casting.yaml` 에 "무엇을 어디에
배포할지"를 선언하면 Helm values를 만들고 배포까지 해준다.

```yaml
apiVersion: v1alpha1
kind: Installation
metadata:
  name: signoz
spec:
  deployment:        # ← 이 레벨이 반드시 필요
    flavor: helm
    mode: kubernetes
```

> [!danger] 함정 1 — 공식 웹 문서의 예시가 틀렸다
> `spec.deployment` 중간 레벨이 빠진 예시가 실려 있어서 그대로 복사하면
> `deployment '{Platform: Mode: Flavor: _:{}}' is not supported` 오류가 난다.
> 값이 틀린 게 아니라 **위치가 틀린 것.** `foundryctl gen examples` 로 정답 예시를
> 직접 뽑는 게 웹 문서보다 정확하다.

> [!danger] 함정 2 — 옛 설치 방법이 인터넷에 널려 있다
> `install.sh` 나 `git clone` 후 번들 파일로 설치하는 방식은 **v0.130.0부터 폐기** 됐다.
> 검색해서 나오는 블로그 대부분이 구버전이다.

SceneTrip에선 `just cluster-up` 이 이 과정을 대신한다. 손으로 할 일이 없다.

> [!danger] 함정 3 — 설치 직후 관리자 계정을 반드시 만들 것
> 계정(=조직)이 없으면 collector가 파이프라인 설정을 못 받아 **OTLP 수신기 자체가
> 안 열린다.** 앱 쪽에는 `Connection refused` 로만 보여서 원인 찾기가 어렵다.
> 비밀번호는 12자 이상 + 대문자 + 소문자 + 숫자 + 기호. 로컬 전용이니 실제로 쓰는
> 비밀번호를 재사용하지 말 것.

## 앱을 SigNoz에 연결하기

> [!important] SigNoz는 스스로 로그를 만들지 않는다
> **앱이 OTLP로 보내야** 화면에 나타난다. "UI는 뜨는데 로그가 하나도 없음"은
> 고장이 아니라 아직 아무도 안 보내고 있는 것이다.

엔드포인트가 **앱이 어디서 도느냐** 에 따라 다르다. 이걸 헷갈리면 안 된다.

| 앱 위치 | OTLP 엔드포인트 | 추가 작업 |
| --- | --- | --- |
| **클러스터 안** (Pod) | `http://signoz-ingester.signoz.svc.cluster.local:4317` | 없음 |
| **맥에서 직접 실행** | `http://localhost:4317` | **port-forward 필요** |

```bash
# 로컬 앱에서 보낼 때만 필요. 별도 터미널을 계속 켜둬야 함
kubectl port-forward -n signoz svc/signoz-ingester 4317:4317 4318:4318
```

> [!note] 클러스터 내부 주소가 왜 저렇게 생겼나
> `<서비스이름>.<네임스페이스>.svc.cluster.local` 이 쿠버네티스 내부 DNS 규칙이다.
> 클러스터 안에서는 이 이름으로 서로를 찾는다. [[02_쿠버네티스_기본개념]]의 Service 참고.

### 서비스 이름 규칙

**`scenetrip-<모듈 디렉터리 이름>`** 으로 통일한다. 저장소 디렉터리와 1:1로 맞추면
로그 화면의 서비스 이름만 보고 어느 코드인지 바로 찾을 수 있다.

| 모듈 | `service.name` |
| --- | --- |
| `services/scene-api` | `scenetrip-scene-api` |
| `apps/web` | `scenetrip-web` |
| `agents/trip-planner` | `scenetrip-trip-planner` |

## 로그 검색

UI 좌측 메뉴 → **Logs → Logs Explorer**

### 연산자

| 분류 | 연산자 |
| --- | --- |
| 비교 | `=`, `!=` |
| 목록 | `IN`, `NOT IN` |
| 텍스트 | `CONTAINS` |
| 존재 | `EXISTS` |

`AND` / `OR` 로 조합한다.

```text
service.name = scenetrip-scene-api AND severity_text = ERROR
service.name IN (scenetrip-scene-api, scenetrip-trip-planner)
body CONTAINS "timeout"
trace_id EXISTS
trace_id = abc123...          ← 요청 하나가 남긴 로그만 시간순으로
```

### 보기 모드

| 모드 | 용도 |
| --- | --- |
| **List** | 개별 로그를 시간순으로 |
| **Time Series** | 로그 **개수의 시간 추이** 그래프 |
| **Table** | 그룹별 집계 |

장애 대응 순서: **Time Series로 급증 시점을 찾고 → List로 그 구간의 실제 로그를 읽는다.**

### 로그 상세의 Context 탭

로그 한 줄을 클릭하면 4개 탭이 나온다. 이 중 **Context 탭이 가장 유용하다** —
그 로그의 앞뒤 로그를 보여준다. 에러 하나를 붙잡았으면 여기부터 열 것. 직전에
무슨 일이 있었는지가 대부분 거기 있다.

## 로그를 잘 남기는 규칙

검색은 남긴 만큼만 된다.

- **구조화 로그를 쓸 것** — 문자열을 이어 붙이지 말고 키·값 속성으로.
  `CONTAINS` 전문 검색보다 `=` 속성 필터가 훨씬 빠르고 정확하다.
- **`trace_id` 가 함께 나가게 할 것** — OTel 에이전트를 붙이면 대체로 자동 주입된다.
  이게 없으면 로그와 트레이스가 끊긴다.
- **심각도를 정확히 쓸 것** — 전부 INFO로 남기면 `severity_text` 필터가 무력화된다.
- **민감 정보를 남기지 말 것** — 한번 수집되면 ClickHouse에 그대로 남는다.
  토큰·비밀번호·개인정보·좌표 원본 금지.

> [!danger] AI 에이전트의 폴백은 반드시 로그를 남길 것
> 모델 호출이 실패했을 때 조용히 기본값으로 넘어가면, 사용자는 품질 저하를 겪는데
> 로그에는 아무것도 안 남는다. **무음 실패(silent failure)는 금지.**
> ```text
> service.name = scenetrip-trip-planner AND body CONTAINS "fallback"
> ```
> 위 조회에서 아무것도 안 나오는데 사용자 불만은 있는 상황이 가장 위험하다 —
> 폴백이 로그를 안 남기고 있다는 뜻이다.

## 매일 쓰는 흐름

```bash
# 아침 — 깨우기
kubectl scale statefulset,deployment --all --replicas=1 -n signoz

# 브라우저에서 http://localhost:8080

# 저녁 — 재우기 (데이터는 유지, 리소스만 회수)
kubectl scale statefulset,deployment --all --replicas=0 -n signoz
```

`helm uninstall` 이 아니라 **scale 0** 을 쓴다. 재설치 없이 바로 되살아난다.

### 상태 확인 한 줄

```bash
helm list -n signoz && kubectl get pods -n signoz
```

`STATUS` 가 `deployed` 이고 Pod가 모두 `Running`(migrator만 `Completed`)이면 정상.

## 로그가 안 보일 때 — 확인 순서

1. 앱에 OTel 에이전트가 실제로 붙었는지 (기동 로그에 OTel 배너)
2. **로컬 앱이라면 ingester port-forward를 열었는지** ← 가장 흔한 원인
3. `OTEL_LOGS_EXPORTER=otlp` 를 켰는지 ← **트레이스만 켜고 로그를 빼먹는 실수가 잦다**
4. 클러스터 안 앱이라면 엔드포인트가 `signoz-ingester.signoz.svc.cluster.local:4317` 인지

```bash
kubectl logs -n signoz -l app.kubernetes.io/name=signoz-otel-collector --tail=50
```

---

이전: [[03_kind와_로컬클러스터]] · 다음: [[05_명령어_치트시트]]
