# -*- coding: utf-8 -*-
"""GCAT の衛星カタログ → アプリ用 slim JSON（機体諸元）。

  python tools/build_gcat.py            … キャッシュがあれば使う
  python tools/build_gcat.py --refresh  … GCAT から取り直す

出典: GCAT (Jonathan McDowell) https://planet4589.org/space/gcat/
      ライセンス CC BY 4.0（帰属表示すれば自由に複製・再配布できる）

やること:
  1. satcat.tsv（約19MB）と launch.tsv（約14MB）を取得して tools/gcat_cache/ に置く
  2. 軌道上の PAYLOAD だけを抜き、アプリで使う項目に絞る
  3. 打上げ日を YYYY-MM-DD に正規化し、打上げ時刻(UTC・分まで)を lt に入れる
     ★時刻は satcat.tsv に無い（LDate は日付まで）。launch.tsv 側にあるので
       Launch_Tag で突き合わせる。秒は使わない。不確実マーク'?'付きは ltq=1 で残す
  4. 別名から GCAT 内部の分類記号（':RA' ':JP' 等）を落として読める形にする
  5. data/gcat_slim.json に書き出す（約3.5MB / gzip 0.23MB）

将来 Get_GCAT リポジトリに移す時は、このファイルをそのまま持っていけばよい。
"""
import gzip
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_URL = 'https://planet4589.org/space/gcat/tsv/cat/satcat.tsv'
CACHE = os.path.join(ROOT, 'tools', 'gcat_cache', 'satcat.tsv')
DST = os.path.join(ROOT, 'data', 'gcat_slim.json')

# 打上げ「時刻」は satcat.tsv には無い（LDate は日付まで）。launch.tsv 側にあるので
# Launch_Tag で突き合わせて拾う。Launch_Tag は TLE の国際識別子と同じ形（2023-196）。
LAUNCH_URL = 'https://planet4589.org/space/gcat/tsv/launch/launch.tsv'
LAUNCH_CACHE = os.path.join(ROOT, 'tools', 'gcat_cache', 'launch.tsv')

# 軌道上とみなす Status（O=在軌 / OP=運用中 / GRP=構成要素 / AO=減衰中の在軌）
ORBIT_STATUS = ('O', 'OP', 'GRP', 'AO')

MON = {m: i + 1 for i, m in enumerate(
    ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])}


def _download(url, dst):
    """planet4589.org の証明書は Python(OpenSSL)の検証に通らないことがある
       （"Basic Constraints of CA cert not marked critical"）。Windowsの証明書ストアを
       使う curl.exe なら通るので、失敗したら curl に切り替える。
       GitHub Actions(Linux) では素直に urllib が通るので、この分岐は使われない。"""
    req = urllib.request.Request(url, headers={'User-Agent': 'OPsLABMaps/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=300) as r, open(dst, 'wb') as f:
            f.write(r.read())
        return
    except urllib.error.URLError as e:
        if 'CERTIFICATE_VERIFY_FAILED' not in str(e):
            raise
        print('  urllib は証明書検証で失敗 → curl に切り替え')
    import shutil
    import subprocess
    curl = shutil.which('curl')
    if not curl:
        raise RuntimeError('curl が見つからないため取得できませんでした')
    # Windowsのcurlはschannel経由で失効確認に失敗する(CRYPT_E_NO_REVOCATION_CHECK)。
    # --ssl-no-revoke は失効確認だけを省く指定で、証明書の検証自体は行われる。
    subprocess.run([curl, '-fsSL', '--ssl-no-revoke', '-o', dst, url], check=True)


def fetch(refresh=False):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    if refresh or not os.path.exists(CACHE):
        print('取得中: %s' % SRC_URL)
        _download(SRC_URL, CACHE)
    print('元データ: %s (%.1f MB)' % (CACHE, os.path.getsize(CACHE) / 1048576))
    return CACHE


def fetch_launch(refresh=False):
    os.makedirs(os.path.dirname(LAUNCH_CACHE), exist_ok=True)
    if refresh or not os.path.exists(LAUNCH_CACHE):
        print('取得中: %s' % LAUNCH_URL)
        _download(LAUNCH_URL, LAUNCH_CACHE)
    print('元データ: %s (%.1f MB)' % (LAUNCH_CACHE, os.path.getsize(LAUNCH_CACHE) / 1048576))
    return LAUNCH_CACHE


def norm_time(v):
    """'2023 Dec 15 0405:54?' → ('04:05', 1) / '2025 Jun  2 2357' → ('23:57', 0)
       時刻を持たない（'2026 Jul 11'）なら ('', 0)。
       ★秒は使わない＝表示は分まで。末尾の '?' は不確実マークなのでフラグで残す。"""
    v = (v or '').strip()
    q = 1 if '?' in v else 0
    v = v.replace('?', '').strip()
    m = re.match(r'^\d{4}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+(\d{2})(\d{2})', v)
    if not m:
        return '', 0
    hh, mm = int(m.group(1)), int(m.group(2))
    if hh > 23 or mm > 59:
        return '', 0
    return '%02d:%02d' % (hh, mm), q


def build_launch_times(path):
    """Launch_Tag → ('HH:MM', 不確実フラグ)。時刻を持たない打上げは入れない。"""
    hdr, out = None, {}
    for line in open(path, encoding='utf-8', errors='replace'):
        if line.startswith('#Launch_Tag'):
            hdr = line.lstrip('#').rstrip('\n').split('\t')
            continue
        if line.startswith('#') or not line.strip() or hdr is None:
            continue
        r = dict(zip(hdr, line.rstrip('\n').split('\t')))
        tag = (r.get('Launch_Tag') or '').strip()
        if not tag:
            continue
        hm, q = norm_time(r.get('Launch_Date'))
        if hm:
            out[tag] = (hm, q)
    return out


def norm_date(v):
    """'2023 Dec 15' → '2023-12-15' / '2023 Dec' → '2023-12' / '2023' → '2023'。
       不確実マーク '?' は落とす。読めなければ空。"""
    v = (v or '').replace('?', '').strip()
    if not v:
        return ''
    m = re.match(r'^(\d{4})(?:\s+([A-Z][a-z]{2}))?(?:\s+(\d{1,2}))?', v)
    if not m:
        return ''
    y, mo, d = m.group(1), m.group(2), m.group(3)
    if mo and mo in MON:
        return ('%s-%02d-%02d' % (y, MON[mo], int(d))) if d else ('%s-%02d' % (y, MON[mo]))
    return y


def clean_alt(v):
    """別名の掃除。GCAT内部の分類記号(':RA' ':JP' ':NA2' 等)を落とし、
       空要素を捨てて ' / ' で繋ぐ。'USA 239,Navstar 67' → 'USA 239 / Navstar 67'。"""
    parts = [re.sub(r':[A-Za-z]+\d*\s*$', '', p).strip() for p in (v or '').split(',')]
    parts = [p for p in parts if p]
    return ' / '.join(dict.fromkeys(parts))      # 重複は落とし、順序は保つ


def g(r, k):
    v = (r.get(k) or '').strip()
    return '' if v in ('-', '?', '') else v


def num(r, k):
    try:
        f = float(g(r, k))
        return f if f > 0 else None
    except Exception:
        return None


def build(path, ltimes=None):
    ltimes = ltimes or {}
    hdr, out = None, {}
    for line in open(path, encoding='utf-8', errors='replace'):
        if line.startswith('#JCAT'):
            hdr = line.rstrip('\n').split('\t')
            continue
        if line.startswith('#') or not line.strip() or hdr is None:
            continue
        r = dict(zip(hdr, line.rstrip('\n').split('\t')))
        if not (r.get('Type') or '').strip().startswith('P'):        # PAYLOAD のみ
            continue
        if (r.get('Status') or '').strip() not in ORBIT_STATUS:      # 軌道上のみ
            continue
        n = g(r, 'Satcat').lstrip('0')                               # NORAD番号(ゼロ埋めなし)
        if not n:
            continue
        d = {}
        for key, col in [('m', 'Mass'), ('dm', 'DryMass'), ('len', 'Length'),
                         ('dia', 'Diameter'), ('span', 'Span')]:
            v = num(r, col)
            if v is not None:
                d[key] = v
        if (r.get('MassFlag') or '').strip() == '?':
            d['mq'] = 1                                              # 質量は推定値
        for key, col in [('sh', 'Shape'), ('mfr', 'Manufacturer'), ('bus', 'Bus'),
                         ('own', 'Owner'), ('st', 'State'), ('pl', 'PLName'),
                         ('orb', 'OpOrbit')]:
            v = g(r, col)
            if v:
                d[key] = v
        ld = norm_date(g(r, 'LDate'))
        if ld:
            d['ld'] = ld
            # 打上げ時刻（UTC・分まで）。日付が YYYY-MM-DD まで確定している時だけ付ける
            # ＝月までしか分からない衛星に時刻を付けても意味がないため。
            lt = ltimes.get(g(r, 'Launch_Tag'))
            if lt and len(ld) == 10:
                d['lt'] = lt[0]
                if lt[1]:
                    d['ltq'] = 1                                     # 打上げ時刻は不確実
        alt = clean_alt(g(r, 'AltNames'))
        if alt:
            d['alt'] = alt
        out[n] = d
    return out


def main():
    refresh = '--refresh' in sys.argv
    ltimes = build_launch_times(fetch_launch(refresh))
    print('打上げ時刻: %d件（時刻を持つ打上げ）' % len(ltimes))
    out = build(fetch(refresh), ltimes)
    s = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    with open(DST, 'w', encoding='utf-8', newline='') as f:
        f.write(s)
    nlt = sum(1 for v in out.values() if 'lt' in v)
    print('出力: %s' % DST)
    print('  %d件 / %.2f MB (gzip %.2f MB)'
          % (len(out), len(s.encode('utf-8')) / 1048576,
             len(gzip.compress(s.encode('utf-8'))) / 1048576))
    print('  うち打上げ時刻あり: %d件 (%.1f%%)' % (nlt, 100.0 * nlt / max(1, len(out))))


if __name__ == '__main__':
    main()
