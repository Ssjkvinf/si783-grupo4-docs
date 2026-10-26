import { estado } from '../core/estado.js';
import { fetchAPI, handleAPIError } from '../core/api.js';
import { escapeHTML, esTester } from '../core/utilidades.js';
import { mostrarResultadoSuite } from './ejecutor.js';

// «Analizar una tabla»: el servidor perfila la tabla (solo SELECT) y propone reglas; aquí se eligen y se guardan como suite.
// La contraseña de Oracle solo vive en el campo de esta pantalla mientras se usa; no se guarda.

const $ = (id) => document.getElementById(id);
let ultimo = null;
let iniciado = false;

export async function cargarAnalisis() {
    if (!iniciado) {
        $('analisis-btn').addEventListener('click', analizar);
        $('analisis-tabla').addEventListener('keydown', (e) => { if (e.key === 'Enter') analizar(); });
        iniciado = true;
    }
    try {
        estado.conexiones = await fetchAPI(`/connections/?project_id=${estado.proyectoActivoId}`) || [];
    } catch (e) { estado.conexiones = []; }
    const sel = $('analisis-conexion');
    const aptas = estado.conexiones.filter(c => c.environment_type !== 'PRODUCTION');
    sel.innerHTML = aptas.length
        ? aptas.map(c => `<option value="${c.id}">${escapeHTML(c.name)} (${c.environment_type})</option>`).join('')
        : `<option value="">${esTester() ? 'No hay conexiones TEST/STAGING: pida una a un administrador' : 'No hay conexiones TEST/STAGING: cree una en «Conexiones Oracle»'}</option>`;
}

function aviso(texto, tipo = 'warning') {
    const a = $('analisis-alerta');
    a.className = `alert alert-${tipo} py-2 small` + (texto ? '' : ' hidden');
    a.textContent = texto || '';
}

async function analizar() {
    const conn = $('analisis-conexion').value;
    const pwd = $('analisis-password').value;
    const tabla = $('analisis-tabla').value.trim();
    if (!conn) return aviso('Elija una conexión de ambiente TEST o STAGING.');
    if (!pwd) return aviso('Escriba la contraseña del usuario Oracle (no se guarda).');
    if (!tabla) return aviso('Escriba el nombre de la tabla, por ejemplo FRAMEWORK_TEST_ITEMS o ESQUEMA.TABLA.');
    aviso('');
    const btn = $('analisis-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Analizando…';
    $('analisis-resultado').innerHTML = `<div class="card"><div class="card-body analizando"><div class="radar"></div>
        <div><b>Leyendo la estructura y los datos de ${escapeHTML(tabla)}…</b><div class="small text-muted">Solo consultas SELECT: no se modifica nada.</div></div></div></div>`;
    try {
        ultimo = await fetchAPI('/analysis/table', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ connection_profile_id: parseInt(conn), password: pwd, tabla }) });
        mostrar(ultimo);
    } catch (e) {
        $('analisis-resultado').innerHTML = '';
        aviso(typeof e.message === 'string' ? e.message : 'No se pudo analizar la tabla.', 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-search me-1"></i> Analizar';
    }
}

function etiquetaColumna(c) {
    const chips = [];
    if (c.clave_primaria) chips.push('<span class="chip-col chip-pk"><i class="bi bi-key-fill"></i> clave primaria</span>');
    if (!c.admite_vacios && !c.clave_primaria) chips.push('<span class="chip-col">obligatoria</span>');
    if (c.vacios > 0) chips.push(`<span class="chip-col chip-warn">${c.vacios} vacíos</span>`);
    if (c.valores) chips.push(`<span class="chip-col chip-val">valores: ${escapeHTML(c.valores.join(', '))}</span>`);
    if (c.minimo !== null && c.minimo !== undefined && !c.valores) chips.push(`<span class="chip-col">de ${escapeHTML(c.minimo)} a ${escapeHTML(c.maximo)}</span>`);
    return chips.join(' ');
}

function mostrar(d) {
    const cols = d.columnas.map(c => `<tr>
        <td><b>${escapeHTML(c.nombre)}</b></td><td class="small text-muted">${escapeHTML(c.tipo)}</td>
        <td class="small">${c.distintos ?? '—'}</td><td>${etiquetaColumna(c)}</td></tr>`).join('');
    const props = d.propuestas.map((p, i) => `
        <label class="propuesta ${p.recomendada ? 'recomendada' : ''}">
            <input type="checkbox" class="form-check-input sel-propuesta" data-idx="${i}" ${p.recomendada ? 'checked' : ''}>
            <div class="flex-grow-1">
                <div class="d-flex flex-wrap align-items-center gap-2"><b>${escapeHTML(p.nombre)}</b>
                    ${p.recomendada ? '<span class="badge badge-suave-ok">recomendada</span>' : '<span class="badge badge-suave-gris">opcional</span>'}</div>
                <div class="small text-muted">${escapeHTML(p.motivo)}</div>
                <details class="small mt-1"><summary>Ver la consulta</summary><code class="d-block mt-1">${escapeHTML(p.sql)}</code>
                    <span class="text-muted">Se espera: ${escapeHTML(p.expected_result)}</span></details>
            </div>
        </label>`).join('');
    $('analisis-resultado').innerHTML = `
        <div class="row g-3 mb-3 entrar">
            <div class="col-6 col-md-3"><div class="cifra"><span>Filas</span><b>${d.filas}</b></div></div>
            <div class="col-6 col-md-3"><div class="cifra"><span>Columnas</span><b>${d.columnas.length}</b></div></div>
            <div class="col-6 col-md-3"><div class="cifra"><span>Reglas propuestas</span><b>${d.propuestas.length}</b></div></div>
            <div class="col-6 col-md-3"><div class="cifra"><span>Consultas SELECT</span><b>${d.consultas_ejecutadas}</b></div></div>
        </div>
        <div class="row g-3">
            <div class="col-lg-5">
                <div class="card h-100"><div class="card-header card-header-titulo"><h6 class="m-0"><i class="bi bi-table me-1"></i>${escapeHTML(d.tabla)}: cómo están hoy los datos</h6></div>
                    <div class="table-responsive"><table class="table table-sm align-middle mb-0">
                        <thead><tr><th>Columna</th><th>Tipo</th><th>Distintos</th><th>Observado</th></tr></thead><tbody>${cols}</tbody></table></div>
                    ${d.columnas_omitidas.length ? `<div class="card-footer small text-muted">Omitidas: ${escapeHTML(d.columnas_omitidas.join(', '))}</div>` : ''}
                </div>
            </div>
            <div class="col-lg-7">
                <div class="card h-100"><div class="card-header card-header-titulo d-flex flex-wrap justify-content-between align-items-center gap-2">
                        <h6 class="m-0"><i class="bi bi-magic me-1"></i>Reglas propuestas</h6>
                        <div class="small"><a href="#" id="analisis-todas">todas</a> · <a href="#" id="analisis-recomendadas">solo recomendadas</a> · <a href="#" id="analisis-ninguna">ninguna</a></div></div>
                    <div class="card-body">
                        <div class="alert alert-info small py-2"><i class="bi bi-info-circle me-1"></i>${escapeHTML(d.aviso)}</div>
                        <div class="lista-propuestas">${props || '<div class="text-muted small">No hay reglas que proponer para esta tabla.</div>'}</div>
                        <div class="guardar-suite mt-3">
                            <label class="form-label small mb-0" for="analisis-nombre-suite">Nombre de la suite</label>
                            <div class="d-flex flex-wrap gap-2">
                                <input id="analisis-nombre-suite" class="form-control flex-grow-1" maxlength="120" value="Calidad de ${escapeHTML(d.tabla)}" style="min-width:200px">
                                <button class="btn btn-outline-primary" id="analisis-guardar"><i class="bi bi-bookmark-plus me-1"></i>Guardar</button>
                                <button class="btn btn-primary btn-brillo" id="analisis-guardar-ejecutar"><i class="bi bi-play-fill me-1"></i>Guardar y ejecutar</button>
                            </div>
                            <div class="small text-muted mt-1" id="analisis-contador"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>`;
    const marcar = (fn) => (e) => { e.preventDefault(); document.querySelectorAll('.sel-propuesta').forEach(c => { c.checked = fn(d.propuestas[c.dataset.idx]); }); contar(); };
    $('analisis-todas').addEventListener('click', marcar(() => true));
    $('analisis-recomendadas').addEventListener('click', marcar(p => p.recomendada));
    $('analisis-ninguna').addEventListener('click', marcar(() => false));
    document.querySelectorAll('.sel-propuesta').forEach(c => c.addEventListener('change', contar));
    $('analisis-guardar').addEventListener('click', () => guardar(false));
    $('analisis-guardar-ejecutar').addEventListener('click', () => guardar(true));
    contar();
}

function elegidas() {
    return [...document.querySelectorAll('.sel-propuesta:checked')].map(c => ultimo.propuestas[c.dataset.idx]);
}

function contar() {
    const n = elegidas().length;
    $('analisis-contador').textContent = n ? `Se crearán ${n} casos en una suite nueva.` : 'Elija al menos una regla.';
    $('analisis-guardar').disabled = $('analisis-guardar-ejecutar').disabled = n === 0;
}

async function guardar(ejecutar) {
    const props = elegidas();
    const nombre = $('analisis-nombre-suite').value.trim();
    if (!nombre) { Swal.fire({ icon: 'info', title: 'Ponga un nombre a la suite' }); return; }
    try {
        const r = await fetchAPI('/analysis/save-suite', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_id: ultimo.project_id, nombre_suite: nombre, propuestas: props.map(p => ({ regla: p.regla, params: p.params })) }) });
        if (!ejecutar) {
            Swal.fire({ icon: 'success', title: 'Suite guardada', html: `Se creó <b>${escapeHTML(r.suite_name)}</b> con ${r.casos.length} casos. Puede ejecutarla cuando quiera desde «Suites».` });
            return;
        }
        const pwd = $('analisis-password').value;
        if (!pwd) { Swal.fire({ icon: 'info', title: 'Suite guardada', text: 'Escriba la contraseña para ejecutarla, o hágalo desde «Suites».' }); return; }
        Swal.fire({ title: 'Ejecutando la suite…', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
        const res = await fetchAPI(`/execute/suite/${r.suite_id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ connection_profile_id: parseInt($('analisis-conexion').value), password: pwd }) });
        mostrarResultadoSuite(res);
    } catch (e) { handleAPIError(e); }
}
