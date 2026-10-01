"""Conectores de fuentes. Nunca inventan datos: si algo falla, lanzan excepción."""
import re, csv, io, unicodedata, datetime as dt
import requests
from bs4 import BeautifulSoup

UA = {'User-Agent': 'Mozilla/5.0 (seguimiento-elnino-peru)'}

def norm(s):
    s = unicodedata.normalize('NFD', s.upper())
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').strip()

def fecha(s):
    try:
        d, m, a = [int(x) for x in s.split('/')]
        return dt.date(a, m, d)
    except Exception:
        return None

def noaa_nino(url):
    """Última semana de índices Niño (NOAA CPC): anomalías de Niño 1+2 y Niño 3.4."""
    t = requests.get(url, headers=UA, timeout=40).text
    filas = [l for l in t.splitlines() if re.match(r'\s*\d{2}[A-Z]{3}\d{4}', l)]
    l = filas[-1]
    f = l.split()[0]
    n = [float(x) for x in re.findall(r'-?\d+\.\d', l[l.index(f) + len(f):])]
    if len(n) < 8:
        raise ValueError('formato inesperado del archivo NOAA')
    return {'semana': f, 'nino12_anom': n[1], 'nino34_anom': n[5]}

TIT = re.compile(r'(\d{1,2}/\d{1,2}/\d{4}).{0,60}?HORAS\s*(?:\([^)]*\))?\s*(.+?)\s*[–—-]\s*([A-ZÁÉÍÓÚÑ ]{3,30})\s*$', re.S)

def indeci_coen(url):
    """Reportes COEN-INDECI publicados en la página de emergencias (título: peligro – departamento)."""
    h = requests.get(url, headers=UA, timeout=40).text
    soup = BeautifulSoup(h, 'html.parser')
    out = {}
    for el in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'a']):
        t = ' '.join(el.get_text(' ').split())
        if 'COEN' not in t.upper():
            continue
        m = TIT.search(t)
        f = fecha(m.group(1)) if m else None
        if not f:
            continue
        ev = {'f': str(f), 'txt': norm(m.group(2)), 'dep': norm(m.group(3))}
        out[f"{ev['f']}|{ev['txt']}|{ev['dep']}"] = ev
    return out

def historico(cfg):
    """Base histórica de emergencias INDECI (CSV público configurado por el usuario)."""
    r = requests.get(cfg['url'], headers=UA, timeout=180)
    rd = csv.DictReader(io.StringIO(r.text), delimiter=cfg.get('sep', ','))
    out, mal = [], 0
    for row in rd:
        f = fecha(row[cfg['col_fecha']].strip().split(' ')[0])
        if not f:
            mal += 1
            continue
        out.append((f, norm(row[cfg['col_dep']]), norm(row[cfg['col_peligro']])))
    return out, mal
