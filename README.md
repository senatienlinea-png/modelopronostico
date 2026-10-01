# Modelo de pronóstico de efectos de El Niño en Perú (actualización diaria)

Cada día a las 06:00 (Lima) GitHub Actions ejecuta `scripts/modelo.py`, que:
1. Lee las fuentes (NOAA CPC, reportes COEN de INDECI, línea base histórica de INDECI).
2. Calcula el **índice observado** (percentil del conteo semanal de reportes frente a su historia, 0-100).
3. Mide el error contra el pronóstico de ayer y **recalibra** la corrección de cada zona y efecto.
4. Publica `docs/state.json` (datos), `docs/informe.md` (informe del día) y las mejoras aplicadas.

## Puesta en marcha
1. Crea un repositorio en GitHub y sube todo este contenido.
2. Settings → Pages → Deploy from branch → `main` / carpeta `/docs`. El tablero queda en la URL de Pages.
3. Settings → Actions → General → Workflow permissions → *Read and write*.
4. Abre en datosabiertos.gob.pe la base histórica de emergencias de INDECI, copia la URL del CSV y completa `historico` en `config/fuentes.json` (`url`, `sep`, `col_fecha`, `col_dep`, `col_peligro`, con los nombres reales de las columnas).
5. Actions → *actualizacion-diaria* → Run workflow, y revisa en el log el estado de cada fuente.

## Estado por efecto
| Efecto | Índice observado automático |
|---|---|
| Lluvias, inundaciones y huaicos | Sí, con INDECI (requiere paso 4 y 7 días de acumulación) |
| Sequía, calor | Solo si INDECI reporta eventos equivalentes; SENAMHI/ANA pendiente |
| Pesca, salud, agricultura, infraestructura | No. Son derivados; ingresa datos en `data/manual_observaciones.csv` (fecha,efecto,zona_idx,indice,fuente) |

## Límites conocidos (verificar en la primera ejecución)
- Los datos de SENAMHI se descargan tras una verificación anti-bot (Cloudflare Turnstile), por lo que no se automatizan aquí. Alternativas: solicitud formal de datos a SENAMHI o carga manual.
- La lectura de INDECI depende de que `portal.indeci.gob.pe/emergencias/` entregue los reportes en el HTML; si el log dice "0 reportes", hay que ajustar el conector.
- Departamento → zona (`config/fuentes.json`) es una aproximación; varios departamentos abarcan más de una zona.
- El comunicado ENFEN y el estado oficial se actualizan a mano tras cada publicación (próxima: 15/10/2026).
