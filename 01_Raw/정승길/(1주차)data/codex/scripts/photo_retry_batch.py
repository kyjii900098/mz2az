#!/usr/bin/env python3
"""구글 매칭됐지만 사진이 빈 장소들의 사진 재조회 배치.
Place Details(photos 필드) → 첫 사진 media(skipHttpRedirect)로 CDN URL 확보.
출력: 조합작업/TOP120완성/사진재시도_결과.csv
"""
import csv, json, time
from pathlib import Path
import urllib.request, urllib.error

DATA = Path(__file__).resolve().parents[2]
INP = DATA/'조합작업'/'TOP120완성'/'사진재시도_대상.csv'
OUT = DATA/'조합작업'/'TOP120완성'/'사진재시도_결과.csv'

def load_key():
    for line in open(Path.home()/'.secrets'):
        line=line.strip()
        if '=' in line and ('GOOGLE' in line.upper() or 'PLACE' in line.upper()):
            return line.split('=',1)[1].strip().strip('"\'')
    raise SystemExit('key not found')
KEY=load_key()

def gapi(url, mask=None):
    headers={'X-Goog-Api-Key':KEY}
    if mask: headers['X-Goog-FieldMask']=mask
    req=urllib.request.Request(url, headers=headers)
    for a in range(3):
        try: return json.load(urllib.request.urlopen(req, timeout=20))
        except urllib.error.HTTPError as e:
            if e.code in (403,429,500,503) and a<2: time.sleep(2*(a+1)); continue
            raise
        except Exception:
            if a<2: time.sleep(2*(a+1)); continue
            raise

rows=list(csv.reader(open(INP,encoding='utf-8-sig')))[1:]
out=[['place_name','place_address','photo_url','status']]
ok=0; nophoto=0; err=0
for i,(name,addr,pid) in enumerate(rows,1):
    status='no_photo'; purl=''
    try:
        d=gapi(f'https://places.googleapis.com/v1/places/{pid}', 'photos')
        photos=d.get('photos',[])
        if photos:
            pm=gapi(f"https://places.googleapis.com/v1/{photos[0]['name']}/media?maxWidthPx=800&skipHttpRedirect=true")
            purl=pm.get('photoUri','')
            status='ok' if purl else 'media_fail'
    except Exception as e:
        status=f'err:{type(e).__name__}'
    if status=='ok': ok+=1
    elif status=='no_photo': nophoto+=1
    else: err+=1
    out.append([name,addr,purl,status])
    if i%50==0:
        with open(OUT,'w',encoding='utf-8-sig',newline='') as f: csv.writer(f).writerows(out)
        print(f'{i}/{len(rows)} ok={ok} nophoto={nophoto} err={err}', flush=True)
    time.sleep(0.25)
with open(OUT,'w',encoding='utf-8-sig',newline='') as f: csv.writer(f).writerows(out)
print(f'완료: {len(rows)}곳 | 사진확보 {ok} | 사진없음 {nophoto} | 오류 {err}', flush=True)
