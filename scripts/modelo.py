"""Actualización diaria: lee fuentes, calcula el índice observado, mide el error y recalibra."""
import json, csv, re, sys, pathlib, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from fuentes import noaa_nino, indeci_coen, historico, norm

R = pathlib.Path(__file__).resolve().parents[1]
CFG = json.loads((R / 'config/fuentes.json').read_text(encoding='utf-8'))
NAMES = ['Costa norte','Costa centro','Costa sur','Sierra norte','Sierra centro','Sierra sur','Selva norte','Selva centro','Selva sur']
EF = {'ll':'Lluvias, inundaciones y huaicos','sq':'Déficit hídrico y sequía','ca':'Calor extremo','pe':'Pesca y ecosistema marino','sa':'Salud','ag':'Agricultura','in':'Infraestructura vial'}
SP = {'ll':[.95,.6,.15,.55,.35,.1,.25,.15,.05],'sq':[.05,.1,.2,.15,.3,.9,.45,.45,.45],'ca':[.95,.8,.6,.3,.3,.3,.4,.4,.4],'pe':[1,.9,.5,0,0,0,0,0,0]}
CV = {'ll':[.2,.4,.55,.65,.8,.95,1,1,.6,.3],'sq':[.3,.4,.5,.6,.7,.8,.9,1,.8,.6],'ca':[1,1,.95,.9,.9,.85,.8,.6,.4,.3],'pe':[1,1,1,1,1,.9,.8,.6,.4,.3]}
LR = .3
DEP2Z = {dep: int(z) for z, ds in CFG['zonas'].items() for dep in ds}

def cur(k, d):
    p = min(9, max(0, (d - dt.date(2026, 9, 15)).days / 30.44)); a = int(p); b = min(9, a + 1)
    return CV[k][a] + (CV[k][b] - CV[k][a]) * (p - a)

def hz(k, i, d, sc=1):
    b = lambda x: sc * SP[x][i] * cur(x, d)
    if k == 'sa': return .5 * b('ll') + .5 * b('ca')
    if k == 'ag': return max(.7 * b('ll'), .8 * b('sq'))
    if k == 'in': return .9 * b('ll')
    return b(k)

def pr(k, i, d, st):
    return min(100, max(0, 100 * hz(k, i, d, st.get('sc', 1)) + st['co'].get(f'{k}{i}', 0)))

def pct(v, serie):
    # rango percentil con empates a la mitad: 0 eventos frente a una historia sin eventos = 50 (típico)
    if not serie:
        return None
    menos = sum(1 for x in serie if x < v); igual = sum(1 for x in serie if x == v)
    return round(100 * (menos + 0.5 * igual) / len(serie))

def leer(p, defecto):
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else defecto

def main():
    ahora = dt.datetime.utcnow() - dt.timedelta(hours=5)      # hora de Lima
    d = ahora.date() - dt.timedelta(days=1)                   # último día completo
    st = leer(R / 'docs/state.json', {})
    st.setdefault('sc', 1); st.setdefault('co', {}); st.setdefault('lg', []); st.setdefault('done', [])
    src, chg, obs, enso = [], [], [], None

    try:
        enso = noaa_nino(CFG['noaa_url'])
        src.append(['NOAA CPC (Niño semanal)', 'ok', f"semana {enso['semana']}: Niño 1+2 {enso['nino12_anom']:+.1f} °C, Niño 3.4 {enso['nino34_anom']:+.1f} °C"])
    except Exception as e:
        src.append(['NOAA CPC (Niño semanal)', 'error', str(e)[:120]])

    ep = R / 'data/indeci_eventos.json'
    alm = leer(ep, {'inicio': None, 'ev': {}})
    try:
        nuevos = indeci_coen(CFG['indeci_url'])
        if not nuevos:
            raise ValueError('0 reportes leídos (página dinámica o formato distinto)')
        alm['inicio'] = alm['inicio'] or str(ahora.date())
        alm['ev'].update(nuevos)
        src.append(['INDECI COEN (emergencias)', 'ok', f"{len(nuevos)} leídos, {len(alm['ev'])} acumulados desde {alm['inicio']}"])
    except Exception as e:
        src.append(['INDECI COEN (emergencias)', 'error', str(e)[:120]])

    H = None
    hc = CFG['historico']
    if hc.get('url') and hc.get('col_fecha'):
        try:
            H, mal = historico(hc)
            src.append(['INDECI histórico (línea base)', 'ok', f'{len(H)} filas; {mal} sin fecha válida'])
        except Exception as e:
            src.append(['INDECI histórico (línea base)', 'error', str(e)[:120]])
    else:
        src.append(['INDECI histórico (línea base)', 'pendiente', 'configura historico en config/fuentes.json'])
    src.append(['SENAMHI / ANA', 'pendiente', 'sin descarga automática verificada; usa data/manual_observaciones.csv'])

    w = dt.timedelta(days=6)
    if H is not None and alm['inicio'] and dt.date.fromisoformat(alm['inicio']) <= d - w:
        evs = [(dt.date.fromisoformat(e['f']), DEP2Z.get(e['dep']), e['txt']) for e in alm['ev'].values()]
        hs = [(f, DEP2Z.get(dep), t) for f, dep, t in H]
        for k in CFG['auto']:
            rx = re.compile(CFG['efectos'][k])
            for i in range(9):
                n = sum(1 for f, z, t in evs if z == i and d - w <= f <= d and rx.search(t))
                fh = [f for f, z, t in hs if z == i and rx.search(t)]
                serie = []
                for y in range(min(f.year for f, _, _ in hs), d.year):
                    try: fin = dt.date(y, d.month, d.day)
                    except ValueError: fin = dt.date(y, d.month, 28)
                    serie.append(sum(1 for f in fh if fin - w <= f <= fin))
                o = pct(n, serie)
                if o is not None:
                    obs.append((k, i, o, 'INDECI COEN 7 días vs histórico (percentil)', str(d)))
    else:
        chg.append('Índice observado automático en espera: falta línea base histórica o acumular 7 días de reportes COEN.')

    mp = R / 'data/manual_observaciones.csv'
    if mp.exists():
        for row in csv.DictReader(mp.open(encoding='utf-8')):
            try:
                if row['fuente'].strip():
                    obs.append((row['efecto'], int(row['zona_idx']), float(row['indice']), row['fuente'].strip(), row['fecha']))
            except Exception:
                continue

    for k, i, o, fu, dd in obs:
        clave = f'{dd}|{k}|{i}'
        if clave in st['done']:
            continue
        p = round(pr(k, i, dt.date.fromisoformat(dd), st)); e = round(o - p)
        a = st['co'].get(f'{k}{i}', 0); n = max(-40, min(40, a + LR * e))
        st['co'][f'{k}{i}'] = n
        st['lg'].append({'d': dd, 'k': k, 'i': i, 'p': p, 'o': round(o), 'e': e, 'f': fu})
        st['done'].append(clave)
        chg.append(f'{NAMES[i]} · {EF[k]}: pronóstico {p}, observado {round(o)}; corrección {a:+.1f} → {n:+.1f}')
    if not chg:
        chg.append('Sin observaciones nuevas válidas: los parámetros no cambiaron.')
    st['lg'] = st['lg'][-400:]; st['done'] = st['done'][-2000:]
    st['meta'] = {'actualizado': ahora.strftime('%Y-%m-%d %H:%M'), 'fecha_dato': str(d), 'cambios': chg, 'fuentes': src,
                  'enso': enso, 'params': {'SP': SP, 'CV': CV}}

    hoy = ahora.date()
    t = f"# Informe diario · El Niño Perú · {hoy}\n\nDato hasta: {d}. Estado oficial vigente: editar en docs/index.html tras cada comunicado ENFEN.\n\n## Fuentes\n"
    t += ''.join(f"- {a}: {b} {c}\n" for a, b, c in src) + '\n## Mejoras aplicadas\n' + ''.join(f'- {c}\n' for c in chg)
    t += '\n## Zonas de mayor riesgo hoy (índice 0-100)\n'
    for k in EF:
        top = sorted(((round(pr(k, i, hoy, st)), NAMES[i]) for i in range(9)), reverse=True)[:3]
        t += f"- {EF[k]}: " + '; '.join(f'{n} {v}' for v, n in top) + '\n'
    t += '\nPrototipo de apoyo; no reemplaza los comunicados de ENFEN, SENAMHI e INDECI.\n'
    (R / 'docs/informe.md').write_text(t, encoding='utf-8')
    (R / 'docs/state.json').write_text(json.dumps(st, ensure_ascii=False), encoding='utf-8')
    ep.write_text(json.dumps(alm, ensure_ascii=False), encoding='utf-8')
    print(t)

if __name__ == '__main__':
    main()
