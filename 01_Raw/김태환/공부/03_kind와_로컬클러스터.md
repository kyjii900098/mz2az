# 3. kind와 SceneTrip 로컬 클러스터

> [[02_쿠버네티스_기본개념]]을 내 맥북에서 실제로 돌려보는 방법.

## kind가 뭔가

**kind = Kubernetes IN Docker.** 이름 그대로다.

쿠버네티스 노드는 원래 서버(머신)다. kind는 **그 노드를 도커 컨테이너로 흉내낸다.**

```
내 맥북
└── Docker Desktop
    └── 컨테이너: scenetrip-control-plane   ← 이게 "노드"다
        └── 그 안에서 또 컨테이너들이 돎    ← Pod들
```

컨테이너 안에서 컨테이너가 도는 구조라 처음엔 헷갈린다. 하지만 이 구조를
이해해야 뒤에 나올 `kind load` 함정을 이해할 수 있다.

### 왜 다른 것 말고 kind인가

로컬 쿠버네티스 선택지는 여러 개다 — Docker Desktop 내장, Minikube, Colima,
Rancher Desktop, k3d. **SceneTrip은 kind만 쓴다.** 이유는:

**클러스터 정의를 코드로 고정할 수 있어서** 다. 노드 수와 포트 매핑이
`platform/kind/cluster.yaml` 에 있으므로 팀원 간 환경 차이가 안 생기고, 깨졌을 때
GUI를 헤매는 대신 지우고 한 줄로 다시 만들 수 있다.

> [!warning] Docker Desktop의 Kubernetes는 끌 것
> Settings → Kubernetes → Enable Kubernetes 체크 해제.
> 켜두면 컨텍스트가 `docker-desktop` 과 `kind-scenetrip` 둘로 늘어나 어디에
> 배포했는지 헷갈리고 메모리도 이중으로 쓴다. Docker Desktop은 **kind 노드를
> 띄우는 런타임으로만** 쓴다.

## SceneTrip 클러스터 구성

`platform/kind/cluster.yaml` 의 실제 내용:

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: scenetrip
nodes:
  - role: control-plane
    extraPortMappings:
      - containerPort: 30080
        hostPort: 8080        # SigNoz UI
      - containerPort: 30081
        hostPort: 8081        # 애플리케이션 API
```

### 포트가 어떻게 뚫리는가

이게 이 문서에서 두 번째로 중요한 개념이다.

```
브라우저 localhost:8080
   ↓  (kind extraPortMappings)
노드 컨테이너의 30080 포트
   ↓  (NodePort Service)
Pod의 8080 포트
   ↓
SigNoz UI
```

3단 연결이다. 이 매핑이 미리 되어 있어서 **`kubectl port-forward` 가 필요 없다.**

> [!danger] extraPortMappings는 클러스터 생성 시점에만 정할 수 있다
> 나중에 포트를 추가하려면 **클러스터를 다시 만들어야 한다.** 그래서 클러스터를
> 손으로 만들면 안 되고 `just cluster-up` 을 써야 한다. 손으로 만들면 포트 매핑이
> 조용히 빠져서 "왜 localhost로 접속이 안 되지"가 된다.

> [!warning] 같은 포트로 port-forward를 겹쳐 열지 말 것
> 노드 컨테이너가 이미 호스트 8080을 잡고 있다. `kubectl port-forward` 로 8080을
> 또 열면 리스너가 둘 생기고 어느 쪽이 응답할지 OS 바인딩 우선순위에 달린다.
> "설정을 고쳤는데 반영이 안 되는" 것처럼 보이는 혼란이 생긴다.

> [!note] 한 장비에 kind 클러스터는 하나만
> 8080·8081을 노드 컨테이너가 점유한다. 다른 프로젝트 클러스터가 떠 있으면
> 먼저 내려야 한다.

## kind load — 가장 많이 하는 실수

**kind 노드는 호스트 Docker와 별도의 이미지 스토어를 쓴다.**

```
내 맥의 Docker 이미지 스토어          kind 노드 안의 이미지 스토어
├── scene-api:dev  ← docker build     ├── nginx
└── nginx                             └── (scene-api가 없음!)
```

`docker build` 는 왼쪽만 갱신한다. 노드는 오른쪽을 본다. 그래서 배포해도 이미지를
못 찾는다. **`kind load` 가 이미지를 왼쪽에서 오른쪽으로 복사한다.**

```bash
docker build -t scene-api:dev services/scene-api
kind load docker-image scene-api:dev --name scenetrip   # ← 이걸 빼먹음
kubectl rollout restart deployment/scene-api -n scenetrip
```

> [!danger] 이게 왜 무서운가
> 이미지가 아예 없으면 `ErrImageNeverPull` 로 멈추니까 금방 안다. 그런데 **한 번
> 적재한 뒤 코드를 고치고 다시 빌드만 하면**, 노드엔 옛 이미지가 그대로 있어서
> 파드가 정상적으로 뜬다. 오류가 안 나고 **조용히 옛 코드가 계속 돈다.**
> "고쳤는데 반영이 안 되네"의 대부분이 이것이다.

SceneTrip은 이걸 레시피로 감쌌다. 손으로 하지 말고 이걸 쓴다.

```bash
just image scene-api      # build + kind load
just update scene-api     # build + kind load + 롤링 재시작
```

이미지 태그(`:dev`)는 그대로 둔다. 태그가 같아도 `kind load` 가 노드의 이미지를
교체했으므로 새 파드는 새 이미지를 쓴다. 태그를 매번 바꾸면 노드에 옛 이미지만 쌓인다.

## Helm — 쿠버네티스의 패키지 매니저

SigNoz 하나 설치하려면 YAML이 수십 개 필요하다. Deployment, Service, ConfigMap,
PVC, StatefulSet... 이걸 손으로 다 쓸 수 없다.

**Helm은 그 YAML 묶음을 템플릿으로 패키징한 것** 이다. `brew` 나 `npm` 같은 것.

| 용어 | 의미 |
| --- | --- |
| **Chart (차트)** | 패키지 자체. YAML 템플릿 묶음 |
| **Values** | 차트에 넣는 설정값 (`values.yaml`) |
| **Release (릴리스)** | 차트를 클러스터에 설치한 **한 번의 설치 인스턴스**. 이름이 붙음 |

```bash
helm list -n signoz          # 설치된 릴리스 목록
helm status signoz -n signoz # 상태
helm uninstall signoz -n signoz
```

`helm list` 의 `STATUS` 가 `deployed` 면 정상. `pending-install` 이면 아직 설치 중
(마이그레이션 Job이 도는 중일 수 있으니 3~4분은 기다려 볼 것).

> [!warning] helm uninstall은 PVC를 안 지운다
> 데이터는 남는다. 재설치하면 기존 데이터가 그대로 붙는다. 완전히 지우려면
> PVC와 네임스페이스까지 따로 지워야 한다.

## 실제 사용 흐름

### 최초 1회

```bash
just cluster-up      # 클러스터 생성 + SigNoz 설치, 3~4분
```

**멱등(idempotent)** 하다 — 이미 있으면 건너뛴다. 여러 번 실행해도 안전하다.
이 단어는 인프라 도구에서 계속 나온다. "몇 번을 해도 결과가 같다"는 뜻.

### 상태 확인

```bash
just cluster-doctor            # 도구·클러스터·SigNoz·워크로드를 한 화면에
kubectl config current-context # kind-scenetrip
kubectl get nodes              # Ready
```

### 정리

```bash
just cluster-down              # 전부 삭제 (확인 절차 있음)
# 또는
kind delete cluster --name scenetrip
```

> [!danger] 클러스터를 지우면 수집한 로그·트레이스와 DB 데이터가 전부 사라진다
> 되돌릴 수 없다. 매일 끄고 켜는 용도로는 클러스터 삭제가 아니라 **scale 0** 을
> 쓴다. [[04_관측성과_SigNoz]] 참고.

### 고장났을 때

kind에서는 **지우고 다시 만드는 게 정상적인 복구 절차** 다. 명령 한 줄이다.

```bash
just cluster-down && just cluster-up
```

> [!note] Docker Desktop의 "Reset Kubernetes Cluster"는 쓰지 말 것
> 그 메뉴는 Docker Desktop 내장 Kubernetes를 초기화할 뿐, kind 클러스터엔 아무
> 영향이 없다.

## 자주 만나는 오류

| 오류 | 원인 | 확인/해결 |
| --- | --- | --- |
| `The connection to the server was refused` | Docker Desktop 꺼짐 / 클러스터 없음 | `kind get clusters`, `docker ps` |
| 컨텍스트가 `kind-scenetrip`이 아님 | 다른 클러스터를 보고 있음 | `kubectl config use-context kind-scenetrip` |
| 노드가 `NotReady` | 노드 컨테이너 문제 | 기다려보고 안 되면 클러스터 재생성 |
| Pod가 `Pending` | 리소스 부족 / PVC 미바인딩 | `kubectl describe pod` 의 Events |
| `ErrImageNeverPull` | **`kind load` 안 함** | `just image <모듈>` |
| 디스크가 꽉 참 | 옛 이미지 누적 | `docker system df` → `docker system prune` |

---

이전: [[02_쿠버네티스_기본개념]] · 다음: [[04_관측성과_SigNoz]]
