#!/usr/bin/env python
"""MZ2AZ-141 성지 장소 필터링 — 1단계: 작품별 블로그 코퍼스 수집.

작품마다 '촬영지 / 성지순례 / 무대탐방 …' 키워드로 네이버 블로그를 검색해
본문을 긁어 작품 단위 jsonl 캐시로 떨군다. 재실행하면 이미 받은 작품은 건너뛴다.

v4 의 title 표기가 흔들려서(눈물의여왕 / 눈물의 여왕) 공백·문장부호를 지운
title_key 로 묶어서 크롤링한다 — 205개 표기 → 161편.

PC 통합검색은 조금만 세게 긁어도 403 을 준다. 모바일 검색(m.search.naver.com)을
쓰고, 전역 토큰버킷으로 초당 요청을 묶고, 403 이 뜨면 전 스레드를 재운다.
"""
import csv, json, os, random, re, sys, time, urllib.parse, threading
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup

BASE = os.path.dirname(os.path.abspath(__file__))
VAULT = "/Users/setgee/orca/workspaces/mz2az/141_성지장소필터링-인기도에따라"
V4 = f"{VAULT}/01_Raw/정승길/data/result/촬영지_TOP_v4_MVP1.csv"
CORPUS = f"{BASE}/corpus"
os.makedirs(CORPUS, exist_ok=True)

UAS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
]

QUERIES = ["촬영지", "성지순례", "촬영지 카페", "촬영지 여행", "촬영지 명소", "무대탐방"]
MAX_DOCS = 120
RATE_SEARCH = 3.0   # 검색은 민감 — 초당 3건
RATE_DOC = 14.0     # 본문(PostView)은 관대 — 초당 14건

NAVER_POST = re.compile(r"https?://(?:m\.)?blog\.naver\.com/[A-Za-z0-9_-]+/\d+")
TISTORY = re.compile(r"https?://[a-z0-9][a-z0-9-]*\.tistory\.com/\d+")
PUNCT = re.compile(r"[\s,·:\-–—!?'\"“”‘’()\[\]]+")

_lock = threading.Lock()
_bucket_lock = threading.Lock()
_last = {"search": 0.0, "doc": 0.0}
_pause_until = [0.0]
_done = 0
_total = 0
_local = threading.local()


def title_key(t):
    return PUNCT.sub("", t)


def log(msg):
    print(msg, flush=True)


def sess():
    if getattr(_local, "s", None) is None:
        s = requests.Session()
        s.headers.update({"User-Agent": random.choice(UAS), "Accept-Language": "ko-KR,ko;q=0.9"})
        _local.s = s
    return _local.s


def throttle(lane="search"):
    """레인별 전역 토큰버킷 — 락은 슬롯 계산에만 쓰고 잠은 락 밖에서 잔다."""
    rate = RATE_SEARCH if lane == "search" else RATE_DOC
    while True:
        with _bucket_lock:
            now = time.time()
            if now >= _pause_until[0]:
                slot = max(now, _last[lane] + 1.0 / rate)
                _last[lane] = slot
                nap, done = slot - now, True
            else:
                nap, done = min(_pause_until[0] - now, 10), False
        if nap > 0:
            time.sleep(nap)
        if done:
            return


def cooldown(sec):
    with _bucket_lock:
        _pause_until[0] = max(_pause_until[0], time.time() + sec)


def get(url, tries=4, lane="search"):
    for i in range(tries):
        throttle(lane)
        try:
            r = sess().get(url, timeout=25)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 429, 503):
                cooldown(60 + 60 * i)
                _local.s = None  # 새 세션·새 UA 로 갈아탄다
                continue
            return None
        except Exception:
            time.sleep(1 + 2 * i)
    return None


def search(query):
    """네이버 모바일 검색 → 블로그 글 URL + 검색결과 제목."""
    e = urllib.parse.quote(query)
    urls, titles = [], []
    for where in ("m_blog", "m_view"):
        r = get(f"https://m.search.naver.com/search.naver?where={where}&query={e}")
        if r is None:
            continue
        t = r.text.replace("\\/", "/")
        urls += NAVER_POST.findall(t) + TISTORY.findall(t)
        soup = BeautifulSoup(r.text, "lxml")
        for a in soup.find_all("a", href=True):
            if NAVER_POST.match(a["href"]) or TISTORY.match(a["href"]):
                txt = a.get_text(" ", strip=True).replace("새 창 열림", "")
                if len(txt) > 5:
                    titles.append(txt)
    out, seen = [], set()
    for u in urls:
        u = u.replace("m.blog.naver.com", "blog.naver.com")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out, titles


def fetch_doc(url):
    m = re.match(r"https?://blog\.naver\.com/([^/?]+)/(\d+)", url)
    target = url
    if m:
        target = (f"https://blog.naver.com/PostView.naver?blogId={m.group(1)}"
                  f"&logNo={m.group(2)}&redirect=Dlog&widgetTypeCall=true&directAccess=false")
    r = get(target, tries=2, lane="doc")
    if r is None:
        return None
    try:
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "lxml")
        for t in soup(["script", "style", "nav", "footer", "header", "aside"]):
            t.decompose()
        body = (soup.select_one(".se-main-container") or soup.select_one("#postViewArea")
                or soup.select_one(".post-view") or soup.select_one("div.post_ct")
                or soup.select_one(".entry-content") or soup.select_one("article") or soup.body)
        if body is None:
            return None
        # 사진 캡션·alt 도 장소명을 담고 있어 함께 긁는다
        alts = " ".join(i.get("alt", "") for i in body.find_all("img") if i.get("alt"))
        txt = re.sub(r"\n{2,}", "\n", body.get_text("\n", strip=True))
        if alts.strip():
            txt += "\n" + alts
        if len(txt) < 60:
            return None
        tt = soup.find("title")
        return {"url": url, "title": tt.get_text(strip=True) if tt else "", "text": txt[:60000]}
    except Exception:
        return None


def do_title(key, display, category):
    global _done
    safe = re.sub(r"[^\w가-힣]", "_", key)[:60] or "untitled"
    path = f"{CORPUS}/{safe}.jsonl"
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with _lock:
            _done += 1
        return

    kind = "영화" if category == "movie" else "드라마"
    qlist = [f"{display} {q}" for q in QUERIES] + [f"{kind} {display} 촬영지"]
    urls, seen, snippets = [], set(), []
    for q in qlist:
        us, ts = search(q)
        snippets += ts
        for u in us:
            if u not in seen:
                seen.add(u)
                urls.append(u)
    urls = urls[:MAX_DOCS]

    if not urls:  # 차단이든 무결과든 파일을 만들지 않는다 → 다음 실행에서 재시도
        with _lock:
            _done += 1
            log(f"[{_done}/{_total}] {display} — 검색 0건, 보류")
        return

    docs = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for d in ex.map(fetch_doc, urls):
            if d:
                docs.append(d)
    if not docs:
        with _lock:
            _done += 1
            log(f"[{_done}/{_total}] {display} — 본문 0건, 보류")
        return
    docs.append({"url": "__search_snippets__", "title": "검색결과 제목 모음",
                 "text": "\n".join(dict.fromkeys(snippets))})

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    with _lock:
        _done += 1
        log(f"[{_done}/{_total}] {display} — 검색 {len(urls)}건 → 본문 {len(docs) - 1}건")


def load_works():
    rows = list(csv.DictReader(open(V4, encoding="utf-8-sig")))
    works = {}
    for r in rows:
        k = title_key(r["title"])
        w = works.setdefault(k, {"variants": {}, "category": r["title_category"]})
        w["variants"][r["title"]] = w["variants"].get(r["title"], 0) + 1
    for w in works.values():
        w["display"] = max(w["variants"].items(), key=lambda kv: kv[1])[0]
    return works


def main():
    works = load_works()
    items = sorted(works.items())
    global _total, _done
    todo = []
    for k, w in items:
        safe = re.sub(r"[^\w가-힣]", "_", k)[:60] or "untitled"
        if not (os.path.exists(f"{CORPUS}/{safe}.jsonl") and os.path.getsize(f"{CORPUS}/{safe}.jsonl") > 0):
            todo.append((k, w))
    _total = len(items)
    _done = len(items) - len(todo)
    log(f"작품 {_total}편 중 남은 {len(todo)}편 크롤링 시작")
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(lambda kv: do_title(kv[0], kv[1]["display"], kv[1]["category"]), todo))
    log("크롤링 라운드 종료")


if __name__ == "__main__":
    main()
