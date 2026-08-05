
bazel이 뭐냐? 

모노레포를 위한 빌드 도구다.
그런데 빌드만 하는게 아니라 유용한 도구가 포함되어 있다.

근데 왜 이거 써야함?
증분 빌드때문에 쓴다.

증분 빌드가 뭔데?
필요한 것(변경된 것)만 빌드시킨다.

예를 들면 백엔드 작업하고 푸쉬했는데 프론트가 작업 끝나고 푸쉬해서 그걸 받아서
내 로컬에서 빌드하고 테스트해보려고 하는데, 변경된 것은 프론트 뿐이니 프론트만 하면된다.
이렇게 필요한 빌드만 하도록 하는것이 증분 빌드가 된다.

또 하나의 목적이 있는데 격리성(Hermeticity)보장이라는 점이다.
그런데 그냥 대충 도커처럼 어느 컴퓨터에서도 동일한 결과를 보장하기 위한 것이라고만 이해하고 넘어가도 될 것 같다.

그럼 증분 빌드를 어떻게 하는거냐?
그래서 bazel은 의존성 그래프를 내부적으로 그린다.
그런데 이 그래프를 그리기 위해서 우리는 BUILD.bazel 이라는 파일에서 각 노드와 의존성을 정의해준다.
이 그래프 정보들을 통해 bazel이 그래프를 구성할 수 있는 것이다.

각 노드들은 추적하는 대상파일들이 있고 그래프를 통해 추적한 파일들의 해시값을 통해 변경을 확인할 수 있다.



간단한 문법을 알아보자
```
# 문법 기본 구조
레시피_이름(
    name = "이_점의_이름",      # 1. 점(Node)의 이름표
    srcs = ["소스파일.java"],   # 2. 이 점이 만드는 데 필요한 내 폴더 안의 파일들
    deps = [":다른_점_이름"],   # 3. 이 점이 만들어지기 위해 먼저 완성이 필요한 다른 점(선/Edge)
)
```

레시피 이름은 정해져 있다.


```

java_binary(
    name = "bin",                 # 점 B 생성! 라벨: //services/scene-api:bin
    srcs = ["Main.java"],
    deps = [
        "//libs/java/common:my_utils",  # ★ 점 B 에서 점 A 로 화살표를 잇는다!
    ],
)

//services/scene-api : bin
  ▲ ─────────────────   ▲
  │          │          └─ 3. BUILD.bazel 파일 안에 적힌 name = "bin" (점 이름)
  │          └──────────── 2. 프로젝트 루트 기준 폴더 경로 (패키지)
  └─────────────────────── 1. "저장소 맨 꼭대기(루트)부터 시작해라"
```

- **`//services/scene-api:bin`** → 프로젝트 최상위 폴더에서 `services/scene-api/` 로 들어가서 `BUILD.bazel` 을 연 다음, 거기 적힌 `name = "bin"` 타깃을 찾아라!
    
- **`:bin`** (앞의 경로 생략) → **지금 내가 있는 이 `BUILD.bazel` 파일 안**에 적힌 `name = "bin"` 타깃을 찾아라!
    
- **`//services/scene-api/...`** → `services/scene-api` 폴더와 그 밑에 있는 **모든 하위 폴더의 모든 타깃**!


스프링 빌드할때 예시 코드

```
java_library(
    name = "user_service",
    srcs = [
        "UserService.java",
        "UserRepository.java",
        "UserDto.java",
    ],
)

java_library( 
	name = "scene-api-lib", 
	srcs = glob(["src/main/java/**/*.java"]), # ← glob 이 자동으로 훑음! 
)
```

이렇게 해두면:

- 개발자가 IDE(IntelliJ 등)에서 `UserService.java`, `OrderService.java` 같은 **새 자바 파일을 10개 만들어도 `BUILD.bazel` 을 일일이 수정할 필요가 없습니다.**


name, src등의 속성은 레시피마다 다르다


테스트레인과 태그가 클로드랑 이야기하다보면 뜰때가 있어서 용어정리를 하자면

```
java_test(
    name = "user_service_test",
    srcs = ["UserServiceTest.java"],
    tags = ["unit", "fast"],  # ← '단위 테스트', '빠름' 태그 부착!
)

java_test(
    name = "payment_integration_test",
    srcs = ["PaymentIntegrationTest.java"],
    tags = ["integration", "heavy", "requires-db"],  # ← '통합 테스트', '무겁고 DB 필요함'
)
```

이렇게 테스트에다가 tags가 붙는다

테스트레인은 
레인은 fast, intergration, heavy 레인으로 나뉘고 뒤로갈수록 시간이 오래걸리는 테스트다.
각각 태그는 "unit", "intergration", "e2e"
unit은 아주 간단한 검사
intergration은 db나 도커를 띄워서 검사

쿠버네티스는 일단 kind를 쓰는데 이거는 쿠버네티스 클러스터를 로컬에서 컨테이너로 띄울 수 있는 도구다. 
포트포워딩 이야기도 나오는데  이건 kind라는 클러스터 포트로 들어오는 요청들을 각 컨테이너에 전달하는 규칙을 정하는것임.


contracts 폴더의 명세를 통해서 generator같은 것이 api주소를 사용할 수 있는 코드 파일을 생성해서 사용하도록 구조가 짜여있다. 그래서 이것도 의존성이 묶여있어서 이 파일이 바뀌면 의존성이 얽힌 파일들은 다시 빌드해야한다고 판단한다.


ci가 깃에서도 돌고, 로컬에서도 체크할수있도록 구조가 만들어져 있다

ci와 check도 차이가 있는데 check은 가벼운검사, ci는 완전검사 느낌

일단 AGENTS.md, CLAUDE.md에 대부분의 규칙과 순서들이 지시되어 있다. 그래서 일단 어느정도 순서만 알고 에이전트가 순서를 지켜줄 탠데 뭔가 빠진게 있는거같으면 시키자. 그래서 어느정도 구조를 알아야한다. 확률론적 모델이기때문에 어쩔수가 없다.

