"""
Reporte de una corrida: página HTML autónoma (sin JavaScript ni recursos externos) con el resultado de cada caso, la comparación
con la vez anterior y los datos de trazabilidad. Se descarga y se puede imprimir o guardar como PDF desde el navegador.

Todo el texto que viene de la base se escapa (html.escape). En PRODUCTION el resultado obtenido ya se guardó sin filas.
"""
from datetime import timezone
from html import escape
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.history import ExecutionHistory
from app.services import comparacion

ESTILO = """
body{font-family:Segoe UI,system-ui,sans-serif;color:#0f172a;margin:0;background:#f4f6fb}
.hoja{max-width:1000px;margin:24px auto;background:#fff;border-radius:16px;padding:32px;box-shadow:0 8px 24px -12px rgba(15,23,42,.2)}
h1{margin:0 0 4px;font-size:24px}.sub{color:#64748b;margin:0 0 20px}
.banda{border-radius:12px;padding:14px 18px;color:#fff;font-weight:700;margin-bottom:18px}
.ok{background:linear-gradient(100deg,#10b981,#34d399)}.mal{background:linear-gradient(100deg,#f59e0b,#ef4444)}
.cifras{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}.cifra{flex:1;min-width:120px;border:1px solid #e2e8f0;border-radius:12px;padding:10px 14px}
.cifra span{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#64748b}.cifra b{font-size:22px}
table{width:100%;border-collapse:collapse;font-size:13px}th{background:#f8fafc;text-align:left;font-size:11px;text-transform:uppercase;color:#64748b;padding:8px}
td{border-top:1px solid #eef2f7;padding:8px;vertical-align:top}
.p{display:inline-block;border-radius:999px;padding:2px 8px;font-weight:700;font-size:11px}
.PASS{background:#ecfdf5;color:#047857}.FAIL{background:#fffbeb;color:#b45309}.ERROR{background:#fef2f2;color:#b91c1c}
.nuevo_fallo{color:#b91c1c;font-weight:700}.corregido{color:#047857;font-weight:700}.otro{color:#64748b}
code{background:#f1f5f9;border-radius:6px;padding:2px 5px;font-size:12px;word-break:break-word}
.meta{display:grid;grid-template-columns:180px 1fr;gap:4px 12px;font-size:13px;margin-bottom:18px}.meta dt{color:#64748b}.meta dd{margin:0}
.pie{color:#64748b;font-size:12px;margin-top:18px}
@media print{body{background:#fff}.hoja{box-shadow:none;margin:0;max-width:none}}
"""


def _fecha(dt) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def filas_de_corrida(db: Session, run_id: str) -> List[ExecutionHistory]:
    return db.query(ExecutionHistory).filter(ExecutionHistory.run_id == run_id).order_by(ExecutionHistory.id.asc()).all()


def generar_html(db: Session, run_id: str) -> Optional[str]:
    filas = filas_de_corrida(db, run_id)
    if not filas:
        return None
    primera = filas[0]
    total = len(filas)
    cuenta = {e: sum(1 for f in filas if f.status == e) for e in ("PASS", "FAIL", "ERROR")}
    titulo = primera.suite_name or (primera.case_name if total == 1 else None) or ("Prueba rápida" if primera.test_case_id is None else "Ejecución")

    filas_html, nuevos, corregidos = [], 0, 0
    for f in filas:
        previo = comparacion.anterior(db, f.test_case_id, primera.id)
        cambio = comparacion.clasificar(previo.status if previo else None, f.status)
        nuevos += cambio == "nuevo_fallo"
        corregidos += cambio == "corregido"
        clase = cambio if cambio in ("nuevo_fallo", "corregido") else "otro"
        antes = f'<span class="p {escape(previo.status)}">{escape(previo.status)}</span> ' if previo else ""
        error = f'<br><span style="color:#b91c1c">{escape(f.error_message)}</span>' if f.error_message else ""
        filas_html.append(
            f"<tr><td><b>{escape(f.case_name or 'Prueba rápida')}</b><br><code>{escape(f.executed_sql or '')}</code></td>"
            f"<td><span class='p {escape(f.status)}'>{escape(f.status)}</span></td>"
            f"<td>{escape(str(f.expected_result or ''))}</td>"
            f"<td>{escape(str(f.actual_result or ''))}{error}</td>"
            f"<td>{antes}<span class='{clase}'>{escape(comparacion.CAMBIOS[cambio])}</span></td>"
            f"<td>{f.duration_ms} ms</td></tr>")

    todo_bien = cuenta["FAIL"] == 0 and cuenta["ERROR"] == 0
    banda = ("Todos los casos pasaron" if todo_bien else f"{cuenta['FAIL'] + cuenta['ERROR']} de {total} casos necesitan revisión")
    if nuevos:
        banda += f" · {nuevos} fallo(s) nuevo(s) respecto de la vez anterior"
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reporte · {escape(titulo)}</title><style>{ESTILO}</style></head>
<body><div class="hoja">
<h1>Reporte de ejecución: {escape(titulo)}</h1>
<p class="sub">SQL QA Framework · corrida {escape(run_id[:8])}</p>
<div class="banda {'ok' if todo_bien else 'mal'}">{escape(banda)}</div>
<div class="cifras">
<div class="cifra"><span>Casos</span><b>{total}</b></div>
<div class="cifra"><span>PASS</span><b style="color:#047857">{cuenta['PASS']}</b></div>
<div class="cifra"><span>FAIL</span><b style="color:#b45309">{cuenta['FAIL']}</b></div>
<div class="cifra"><span>ERROR</span><b style="color:#b91c1c">{cuenta['ERROR']}</b></div>
<div class="cifra"><span>Nuevos fallos</span><b>{nuevos}</b></div>
<div class="cifra"><span>Corregidos</span><b>{corregidos}</b></div>
</div>
<dl class="meta">
<dt>Fecha</dt><dd>{_fecha(primera.executed_at)}</dd>
<dt>Conexión</dt><dd>{escape(primera.connection_name or '—')}</dd>
<dt>Ejecutado por</dt><dd>{escape(primera.executed_by or 'sin usuario registrado')}</dd>
<dt>Origen</dt><dd>{escape(primera.trigger_source or 'no registrado')}</dd>
<dt>Duración total</dt><dd>{round(sum(f.duration_ms or 0 for f in filas), 2)} ms</dd>
</dl>
<div style="overflow-x:auto"><table><thead><tr><th>Caso y consulta</th><th>Resultado</th><th>Esperado</th><th>Obtenido</th><th>Frente a la vez anterior</th><th>Duración</th></tr></thead>
<tbody>{''.join(filas_html)}</tbody></table></div>
<p class="pie">PASS: coincide con lo esperado · FAIL: se ejecutó pero no coincide · ERROR: no se pudo ejecutar o evaluar.
Un PASS indica que la regla configurada se cumple, no que toda la base esté correcta. Generado desde el historial guardado.</p>
</div></body></html>"""
