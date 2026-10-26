import { estado } from '../core/estado.js';
import { fetchAPI, handleAPIError, API_URL } from '../core/api.js';
import { escapeHTML } from '../core/utilidades.js';

const ORIGEN = { UI: 'Interfaz (Casos/Suites)', INICIO: 'Inicio (prueba rápida)', CLI: 'Línea de comandos', GITHUB_ACTIONS: 'GitHub Actions' };
const ESTADO = {
    PASS: { clase: 'pass', icono: 'bi-check-circle-fill', texto: 'Pasó: coincide con lo esperado' },
    FAIL: { clase: 'fail', icono: 'bi-exclamation-triangle-fill', texto: 'Falló: se ejecutó, pero no coincide' },
    ERROR: { clase: 'error', icono: 'bi-x-octagon-fill', texto: 'Error: no se pudo ejecutar o evaluar' }
};

// Las fechas de la base vienen en UTC; algunas sin zona horaria.
export function fechaLocal(iso) {
    if (!iso) return '';
    const texto = /[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + 'Z';
    return new Date(texto).toLocaleString();
}

// El resultado obtenido se guarda serializado (p. ej. "Filas afectadas: 0" con comillas); se muestra sin ellas.
function sinComillas(texto) {
    if (!texto) return '';
    const t = String(texto);
    return t.length > 1 && t.startsWith('"') && t.endsWith('"') ? t.slice(1, -1) : t;
}

export function insigniaEstado(status) {
    const e = ESTADO[status] || ESTADO.ERROR;
    return `<span class="estado-pill estado-${e.clase}"><i class="bi ${e.icono}"></i> ${escapeHTML(status)}</span>`;
}

function rellenarSelect(sel, items, vacio) {
    const actual = sel.value;
    sel.innerHTML = `<option value="">${vacio}</option>` + items.map(i => `<option value="${i.id}">${escapeHTML(i.name)}</option>`).join('');
    if ([...sel.options].some(o => o.value === actual)) sel.value = actual;
}

async function cargarFiltros() {
    if (!estado.proyectoActivoId) return;
    try {
        const [casos, suites] = await Promise.all([
            fetchAPI(`/test-cases/?project_id=${estado.proyectoActivoId}`),
            fetchAPI(`/suites/?project_id=${estado.proyectoActivoId}`)
        ]);
        estado.casos = casos || [];
        estado.suites = suites || [];
        rellenarSelect(document.getElementById('filtro-hist-case'), estado.casos, 'Todos los casos');
        rellenarSelect(document.getElementById('filtro-hist-suite'), estado.suites, 'Todas las suites');
    } catch (e) { /* los filtros son opcionales: el historial se muestra igual */ }
}

export async function cargarHistorial() {
    await cargarFiltros();
    const status = document.getElementById("filtro-hist-status").value;
    const suiteId = document.getElementById("filtro-hist-suite").value;
    const caseId = document.getElementById("filtro-hist-case").value;
    const por = document.getElementById("filtro-hist-por").value.trim();

    let url = `/history/?skip=${estado.histSkip}&limit=${estado.histLimit}`;
    if (estado.proyectoActivoId) url += `&project_id=${estado.proyectoActivoId}`;
    if (status) url += `&status=${status}`;
    if (suiteId) url += `&suite_id=${suiteId}`;
    if (caseId) url += `&test_case_id=${caseId}`;
    if (por) url += `&executed_by=${encodeURIComponent(por)}`;

    try {
        const hist = await fetchAPI(url);
        const tbody = document.getElementById("tabla-historial");
        tbody.innerHTML = "";

        document.getElementById("btn-hist-prev").disabled = estado.histSkip === 0;
        document.getElementById("btn-hist-next").disabled = hist.length < estado.histLimit;
        document.getElementById("historial-pag-info").innerText = hist.length
            ? `Mostrando ${estado.histSkip + 1}–${estado.histSkip + hist.length}` : 'Sin resultados';

        if (hist.length === 0) {
            const hayFiltros = status || suiteId || caseId || por;
            tbody.innerHTML = `<tr><td colspan="7"><div class="vacio">
                <i class="bi bi-clock-history"></i>
                <b>${hayFiltros ? 'Ninguna ejecución coincide con los filtros' : 'Todavía no hay ejecuciones en este proyecto'}</b>
                <span>${hayFiltros ? 'Pruebe quitando algún filtro.' : 'Haga una comprobación desde Inicio o ejecute un caso o una suite: cada ejecución aparece aquí con su evidencia.'}</span>
            </div></td></tr>`;
            return;
        }

        hist.forEach((h, i) => {
            const que = h.case_name ? escapeHTML(h.case_name) : (h.test_case_id === null ? '<i>Prueba rápida</i>' : `Caso #${h.test_case_id}`);
            const suite = h.suite_id !== null ? `<span class="chip-suite"><i class="bi bi-collection"></i> ${escapeHTML(h.suite_name || 'Suite #' + h.suite_id)}</span>` : '';
            const tr = document.createElement("tr");
            tr.className = 'fila-entrar';
            tr.style.animationDelay = `${Math.min(i, 12) * 25}ms`;
            tr.innerHTML = `<td class="small text-muted text-nowrap">${fechaLocal(h.executed_at)}<div class="text-muted">#${h.id}</div></td>
                <td><div class="fw-semibold">${que}</div>${suite}</td>
                <td>${insigniaEstado(h.status)}</td>
                <td class="small"><div class="text-truncate" style="max-width:260px" title="${escapeHTML(h.expected_result)} → ${escapeHTML(h.actual_result)}">
                    <span class="text-muted">esperado</span> ${escapeHTML(h.expected_result)}
                    <span class="text-muted">· obtenido</span> ${escapeHTML(sinComillas(h.actual_result) || h.error_message || '')}</div></td>
                <td class="small text-nowrap">${h.duration_ms} ms</td>
                <td>${h.executed_by ? `<span class="por-usuario"><i class="bi bi-person-circle"></i> ${escapeHTML(h.executed_by)}</span>` : '<small class="text-muted">sin usuario</small>'}</td>
                <td class="text-end pe-4"><button class="btn btn-sm btn-outline-primary btn-det" data-idx="${i}" title="Ver detalle"><i class="bi bi-eye"></i></button></td>`;
            tbody.appendChild(tr);
        });

        tbody.querySelectorAll('.btn-det').forEach(b => b.addEventListener('click', () => mostrarDetalleEjecucion(hist[b.dataset.idx])));
    } catch(e) { handleAPIError(e); }
}

export function mostrarDetalleEjecucion(h) {
    const e = ESTADO[h.status] || ESTADO.ERROR;
    const filaSiHay = (etiqueta, valor) => valor ? `<dt>${etiqueta}</dt><dd>${valor}</dd>` : '';
    Swal.fire({
        width: 760,
        showConfirmButton: true, confirmButtonText: 'Cerrar',
        html: `<div class="detalle-ejecucion text-start">
            <div class="veredicto-mini veredicto-${e.clase}"><i class="bi ${e.icono}"></i><div><b>${escapeHTML(h.status)}</b> · ${e.texto}</div></div>
            <div class="comparacion">
                <div><span>Se esperaba</span><b>${escapeHTML(h.expected_result)}</b></div>
                <i class="bi bi-arrow-right"></i>
                <div><span>Se obtuvo</span><b>${escapeHTML(sinComillas(h.actual_result) || (h.status === 'ERROR' ? 'nada: no se pudo ejecutar' : '—'))}</b></div>
            </div>
            <dl class="detalle-lista">
                ${filaSiHay('Qué se ejecutó', h.case_name ? escapeHTML(h.case_name) : (h.test_case_id === null ? 'Prueba rápida desde Inicio' : 'Caso #' + h.test_case_id))}
                ${filaSiHay('Suite', h.suite_id !== null ? escapeHTML(h.suite_name || 'Suite #' + h.suite_id) : '')}
                ${filaSiHay('Conexión', escapeHTML(h.connection_name || ''))}
                ${filaSiHay('Cuándo', fechaLocal(h.executed_at))}
                ${filaSiHay('Quién', escapeHTML(h.executed_by || 'sin usuario registrado'))}
                ${filaSiHay('Desde', escapeHTML(ORIGEN[h.trigger_source] || h.trigger_source || 'origen no registrado'))}
                ${filaSiHay('Cómo se comparó', escapeHTML(h.validation_type || ''))}
                ${filaSiHay('Duración', h.duration_ms + ' ms')}
                ${filaSiHay('Cambios revertidos', ['INSERT', 'UPDATE', 'DELETE'].includes(h.statement_type) ? (h.rollback_applied ? 'Sí: se aplicó rollback, la base quedó como estaba' : 'No') : '')}
                ${filaSiHay('Error', h.error_message ? `<span class="text-danger">${escapeHTML(h.error_message)}</span>` : '')}
                ${filaSiHay('Error de rollback', h.rollback_error ? `<span class="text-danger">${escapeHTML(h.rollback_error)}</span>` : '')}
            </dl>
            <div id="detalle-anterior"></div>
            <div class="small text-muted mb-1">SQL ejecutado</div>
            <pre class="sql-bloque">${escapeHTML(h.executed_sql)}</pre>
            <div class="d-flex flex-wrap align-items-center gap-2">
                <span class="small text-muted">Registro #${h.id}${h.run_id ? ' · corrida ' + escapeHTML(h.run_id.slice(0, 8)) : ''}</span>
                ${h.run_id ? `<a class="btn btn-sm btn-outline-primary ms-auto" href="${API_URL}/history/runs/${encodeURIComponent(h.run_id)}/report" download><i class="bi bi-file-earmark-richtext me-1"></i>Reporte de la corrida</a>` : ''}
            </div>
        </div>`
    });
    if (h.test_case_id) mostrarVezAnterior(h);
}

// «Frente a la vez anterior»: busca la ejecución previa del mismo caso y dice si empeoró o se arregló.
async function mostrarVezAnterior(h) {
    try {
        const lista = await fetchAPI(`/history/?test_case_id=${h.test_case_id}&limit=100`);
        const previo = (lista || []).find(x => x.id < h.id);
        const caja = document.getElementById('detalle-anterior');
        if (!caja) return;
        let texto, clase;
        if (!previo) { texto = 'Es la primera ejecución de este caso.'; clase = 'primera_vez'; }
        else if (previo.status === h.status) { texto = `Igual que la vez anterior (${fechaLocal(previo.executed_at)}).`; clase = 'igual'; }
        else if (previo.status === 'PASS') { texto = `Antes pasaba (${fechaLocal(previo.executed_at)}) y ahora no: algo cambió en los datos o en la consulta.`; clase = 'nuevo_fallo'; }
        else if (h.status === 'PASS') { texto = `Antes daba ${previo.status} (${fechaLocal(previo.executed_at)}) y ahora pasa.`; clase = 'corregido'; }
        else { texto = `Antes daba ${previo.status}; ahora ${h.status}.`; clase = 'cambio'; }
        caja.innerHTML = `<div class="cambio cambio-${clase} mb-3"><i class="bi bi-clock-history"></i> <b>Frente a la vez anterior:</b> ${escapeHTML(texto)}</div>`;
    } catch (e) { /* opcional */ }
}
