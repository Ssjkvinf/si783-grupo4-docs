import { estado } from '../core/estado.js';
import { fetchAPI, handleAPIError } from '../core/api.js';
import { escapeHTML } from '../core/utilidades.js';
import { formConexion } from './conexiones.js';
import { formCaso } from './casos.js';

// Recorrido guiado: Conectar -> elegir comprobación -> resultado esperado -> ejecutar -> entender -> guardar o repetir.
// Reutiliza /api/execute/quick (política SQL y servicio de ejecución existentes) y las suites existentes.
// La contraseña solo vive en el campo del formulario mientras la pestaña esté abierta: no se guarda en ningún lado.
//
// Tres formas de comprobar (no confundir):
//  - ROW_COUNT    -> cuántas FILAS devuelve la consulta (un COUNT(*) siempre devuelve 1 fila).
//  - SCALAR_VALUE -> el VALOR que devuelve la consulta (p. ej. el número que calcula un COUNT(*)).
//  - EXISTS       -> si devuelve al menos una fila o ninguna.

// Plantillas basadas únicamente en objetos que existen en el entorno de demostración:
//  - DUAL existe en cualquier Oracle.
//  - FRAMEWORK_TEST_ITEMS (ID, NAME, ACTIVE) la crea infra/oracle/init/001_test_schema.sh y sus datos de
//    ejemplo los carga infra/oracle/demo/seed_demo_data.sql (5 productos, 4 activos).
const PLANTILLAS = [
    {
        id: 'conexion',
        titulo: 'Comprobar que la conexión responde',
        sql: 'SELECT 1 FROM DUAL',
        validacion: 'ROW_COUNT',
        esperado: '1',
        nota: 'Funciona en cualquier base Oracle: la consulta devuelve 1 fila. Aquí se comprueba la cantidad de filas, no un valor.'
    },
    {
        id: 'contar',
        titulo: 'Contar los registros de la tabla de demostración',
        sql: 'SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS',
        validacion: 'SCALAR_VALUE',
        esperado: '5',
        nota: 'Compara el NÚMERO que calcula COUNT(*). Con los datos del script de demostración son 5 productos; si su tabla tiene otros datos, cambie el valor esperado.'
    },
    {
        id: 'invalidos',
        titulo: 'Buscar datos inválidos: productos sin nombre',
        sql: 'SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS WHERE TRIM(NAME) IS NULL',
        validacion: 'SCALAR_VALUE',
        esperado: '0',
        nota: 'Se espera el valor 0: ningún registro con nombre vacío. Si apareciera 1 o más, la regla daría FAIL.'
    },
    {
        id: 'existe',
        titulo: '¿Existe el producto con ID 3?',
        sql: 'SELECT ID, NAME FROM FRAMEWORK_TEST_ITEMS WHERE ID = 3',
        validacion: 'EXISTS',
        esperado: 'true',
        nota: 'Con los datos del script de demostración existe un producto con ID 3.'
    },
    {
        id: 'propio',
        titulo: 'Escribir mi propio SELECT',
        sql: '',
        validacion: 'ROW_COUNT',
        esperado: '',
        nota: 'Escriba una consulta SELECT sobre una tabla de su base e indique qué espera obtener.'
    }
];

// Espejo simplificado de app/services/validacion_auto.py, solo para mostrar en vivo qué se va a comparar.
// La decisión real la toma el servidor y se muestra en el resultado.
function detectarComparacion(sql, esperado) {
    const e = (esperado || '').trim().toLowerCase();
    if (!e) return null;
    if (['true', 'sí', 'si', 'yes', 'verdadero', 'false', 'no', 'falso'].includes(e)) {
        return 'si la consulta devuelve alguna fila (usted respondió sí/no)';
    }
    const s = (sql || '').trim().replace(/;$/, '');
    const unico = /^select\s+(distinct\s+)?(count|sum|avg|min|max)\s*\([^,]*\)(\s+(as\s+)?[a-z_][\w$#]*)?\s+from\b/i.test(s)
        && !/\bgroup\s+by\b/i.test(s.replace(/\([^()]*\)/g, ''));
    if (unico) return 'el valor que calcula la consulta (COUNT, SUM, AVG, MIN o MAX)';
    if (/^\d+$/.test(e)) return `la cantidad de filas que devuelve la consulta (${e})`;
    return 'el valor de la única fila que devuelve la consulta';
}

function actualizarDeteccion() {
    const caja = el('inicio-auto-detectado');
    if (el('inicio-validacion').value !== 'AUTO') { caja.innerHTML = ''; return; }
    const d = detectarComparacion(el('inicio-sql').value, el('inicio-esperado-auto').value);
    caja.innerHTML = d
        ? `<i class="bi bi-stars me-1"></i>Se comparará <b>${escapeHTML(d)}</b>. ¿No es lo que quiere? Elija el tipo a mano en la lista.`
        : '<i class="bi bi-info-circle me-1"></i>Escriba lo que espera: un número (filas o valor), sí/no o un texto. La aplicación decide cómo compararlo.';
}

const AVISO_COUNT = 'Atención: su consulta usa COUNT(...). «Cantidad de filas» comprueba cuántas filas devuelve la consulta (un COUNT devuelve siempre 1), no el número que calcula. Para comparar ese número elija «Valor que devuelve la consulta».';

let irASeccion = null;
let alEjecutarFn = null;   // refresca las tarjetas de «Resumen» tras ejecutar (inyectado desde app.js para evitar ciclos de importación)
let ultimaEjecucion = null;
let demo = null;           // { rules: {id, name}, examples: {id, name} } si las suites de demostración ya existen en el proyecto

const el = (id) => document.getElementById(id);

export function initInicio(irA, alEjecutar) {
    irASeccion = irA;
    alEjecutarFn = alEjecutar || null;

    const selPlantilla = el('inicio-plantilla');
    selPlantilla.innerHTML = '<option value="">Elegir una comprobación de ejemplo…</option>' +
        PLANTILLAS.map(p => `<option value="${p.id}">${escapeHTML(p.titulo)}</option>`).join('');
    selPlantilla.addEventListener('change', aplicarPlantilla);

    el('inicio-conexion').addEventListener('change', actualizarAvisoEntorno);
    el('inicio-validacion').addEventListener('change', () => { actualizarCampoEsperado(); actualizarAvisoCount(); actualizarDeteccion(); });
    el('inicio-sql').addEventListener('input', () => { actualizarAvisoCount(); actualizarDeteccion(); });
    el('inicio-esperado-auto').addEventListener('input', actualizarDeteccion);
    el('inicio-btn-usar-valor').addEventListener('click', () => {
        el('inicio-validacion').value = 'SCALAR_VALUE';
        actualizarCampoEsperado(); actualizarAvisoCount();
        el('inicio-esperado-valor').focus();
    });
    el('inicio-btn-nueva-conexion').addEventListener('click', () => formConexion());
    el('inicio-btn-ejecutar').addEventListener('click', ejecutarComprobacion);
    el('inicio-btn-ir-proyectos').addEventListener('click', () => irASeccion && irASeccion('proyectos'));
    el('inicio-btn-cargar-demo').addEventListener('click', cargarSuitesDemo);
    el('inicio-btn-suite-reglas').addEventListener('click', () => ejecutarSuite('rules'));
    el('inicio-btn-suite-ejemplos').addEventListener('click', () => ejecutarSuite('examples'));
    el('inicio-btn-guiada').addEventListener('click', ejecutarDemoGuiada);
    el('inicio-regla').addEventListener('change', mostrarCamposRegla);
    el('inicio-regla-usar').addEventListener('click', usarRegla);
    cargarCatalogoReglas();
    actualizarCampoEsperado();
    actualizarAvisoCount();
    actualizarDeteccion();
}

export async function cargarInicio() {
    const sel = el('inicio-conexion');
    const sinProyecto = el('inicio-sin-proyecto');
    const previa = sel.value;

    if (!estado.proyectoActivoId) {
        sinProyecto.classList.remove('hidden');
        sel.innerHTML = '';
        actualizarAvisoEntorno();
        return;
    }
    sinProyecto.classList.add('hidden');

    try {
        estado.conexiones = await fetchAPI(`/connections/?project_id=${estado.proyectoActivoId}`) || [];
    } catch (e) {
        console.error('No se pudieron cargar las conexiones', e);
        estado.conexiones = [];
    }

    if (estado.conexiones.length === 0) {
        sel.innerHTML = document.body.classList.contains('rol-tester')
            ? '<option value="">Aún no hay conexiones: pida a un administrador que cree una</option>'
            : '<option value="">Aún no hay conexiones: cree una con «Nueva conexión»</option>';
    } else {
        sel.innerHTML = estado.conexiones
            .map(c => `<option value="${c.id}">${escapeHTML(c.name)} (${escapeHTML(c.environment_type)})</option>`).join('');
        if (previa && estado.conexiones.some(c => String(c.id) === previa)) sel.value = previa;
    }
    actualizarAvisoEntorno();
    await detectarSuitesDemo();
}

function conexionSeleccionada() {
    const id = el('inicio-conexion').value;
    return estado.conexiones.find(c => String(c.id) === id) || null;
}

function actualizarAvisoEntorno() {
    const aviso = el('inicio-entorno');
    const c = conexionSeleccionada();
    if (!c) { aviso.innerHTML = ''; return; }
    const textos = {
        TEST: ['bg-success', 'Ambiente TEST: es el ambiente pensado para probar.'],
        STAGING: ['bg-warning text-dark', 'Ambiente STAGING: en este recorrido solo se ejecutan consultas SELECT.'],
        PRODUCTION: ['bg-danger', 'Ambiente PRODUCTION: solo lectura. Verá la cantidad de filas, no su contenido, y no está disponible la comparación por valor.']
    };
    const [clase, texto] = textos[c.environment_type] || ['bg-secondary', c.environment_type];
    aviso.innerHTML = `<span class="badge ${clase} me-2">${escapeHTML(c.environment_type)}</span><span class="small text-muted">${escapeHTML(texto)}</span>`;
}

function aplicarPlantilla() {
    const p = PLANTILLAS.find(x => x.id === el('inicio-plantilla').value);
    const nota = el('inicio-plantilla-nota');
    if (!p) { nota.textContent = ''; return; }
    el('inicio-sql').value = p.sql;
    el('inicio-validacion').value = p.validacion;
    actualizarCampoEsperado();
    if (p.validacion === 'EXISTS') el('inicio-esperado-bool').value = p.esperado;
    else if (p.validacion === 'SCALAR_VALUE') el('inicio-esperado-valor').value = p.esperado;
    else el('inicio-esperado-num').value = p.esperado;
    nota.textContent = p.nota;
    actualizarAvisoCount();
    ocultarResultado();
}

function actualizarCampoEsperado() {
    const v = el('inicio-validacion').value;
    el('inicio-esperado-auto').classList.toggle('hidden', v !== 'AUTO');
    el('inicio-esperado-num').classList.toggle('hidden', v !== 'ROW_COUNT');
    el('inicio-esperado-valor').classList.toggle('hidden', v !== 'SCALAR_VALUE');
    el('inicio-esperado-bool').classList.toggle('hidden', v !== 'EXISTS');
}

// Avisa (sin bloquear) cuando alguien usa COUNT(...) con «cantidad de filas», la confusión más habitual.
function actualizarAvisoCount() {
    const confuso = el('inicio-validacion').value === 'ROW_COUNT' && /\bCOUNT\s*\(/i.test(el('inicio-sql').value);
    el('inicio-aviso-count').classList.toggle('hidden', !confuso);
    el('inicio-aviso-count-texto').textContent = AVISO_COUNT;
}

function valorEsperadoIndicado() {
    const v = el('inicio-validacion').value;
    if (v === 'AUTO') return el('inicio-esperado-auto').value.trim();
    if (v === 'EXISTS') return el('inicio-esperado-bool').value;
    if (v === 'SCALAR_VALUE') return el('inicio-esperado-valor').value.trim();
    return el('inicio-esperado-num').value.trim();
}

function mostrarAlerta(texto) {
    const a = el('inicio-alerta');
    a.textContent = texto;
    a.classList.toggle('hidden', !texto);
}

function ocultarResultado() {
    el('inicio-resultado').classList.add('hidden');
    el('inicio-resultado').innerHTML = '';
    mostrarAlerta('');
}

function datosConexion() {
    const conn = conexionSeleccionada();
    const password = el('inicio-password').value;
    if (!estado.proyectoActivoId) { mostrarAlerta('Primero seleccione o cree un proyecto activo.'); return null; }
    if (!conn) { mostrarAlerta('Elija una conexión o cree una con «Nueva conexión».'); return null; }
    if (!password) { mostrarAlerta('Escriba la contraseña de Oracle. Solo se usa para esta ejecución y no se guarda.'); return null; }
    return { conn, password };
}

async function ejecutarComprobacion() {
    mostrarAlerta('');
    const dc = datosConexion();
    if (!dc) return;
    const sql = el('inicio-sql').value.trim();
    const validacion = el('inicio-validacion').value;
    const esperado = valorEsperadoIndicado();

    if (!sql) return mostrarAlerta('Escriba un SELECT o elija una comprobación de ejemplo.');
    if (esperado === '') return mostrarAlerta('Indique el resultado esperado. Usted decide qué debe devolver la consulta; la aplicación no lo adivina.');
    if (validacion === 'ROW_COUNT' && !/^\d+$/.test(esperado)) return mostrarAlerta('El número de filas esperado debe ser un entero mayor o igual a 0.');

    const btn = el('inicio-btn-ejecutar');
    const texto = el('inicio-btn-ejecutar-texto');
    const spinner = el('inicio-btn-ejecutar-spinner');
    btn.disabled = true; spinner.classList.remove('hidden'); texto.textContent = 'Ejecutando…';

    try {
        const res = await fetchAPI('/execute/quick', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                connection_profile_id: parseInt(dc.conn.id),
                password: dc.password,
                sql_query: sql,
                ...(validacion === 'AUTO' ? {} : { validation_type: validacion }),
                expected_result: esperado
            })
        });
        ultimaEjecucion = res;
        mostrarResultado(res);
        if (alEjecutarFn) alEjecutarFn();
    } catch (err) {
        handleAPIError(err);
    } finally {
        btn.disabled = false; spinner.classList.add('hidden'); texto.textContent = 'Ejecutar comprobación';
    }
}

function tablaFilas(res) {
    if (res.rows_hidden) {
        return `<p class="small text-muted mb-0"><i class="bi bi-eye-slash me-1"></i>Ambiente PRODUCTION: por seguridad no se muestran las filas, solo su cantidad (${res.rowcount}).</p>`;
    }
    if (!res.rows.length) return '<p class="small text-muted mb-0">La consulta no devolvió filas.</p>';
    const cab = res.columns.map(c => `<th>${escapeHTML(c)}</th>`).join('');
    const cuerpo = res.rows.map(f => '<tr>' + f.map(v => `<td>${v === null ? '<span class="text-muted">NULL</span>' : escapeHTML(v)}</td>`).join('') + '</tr>').join('');
    const mas = res.rows_truncated ? `<p class="small text-muted mt-1 mb-0">Se muestran las primeras ${res.rows_shown} filas de ${res.rowcount}.</p>` : '';
    return `<div class="table-responsive"><table class="table table-sm table-bordered mb-0"><thead class="table-light"><tr>${cab}</tr></thead><tbody>${cuerpo}</tbody></table></div>${mas}`;
}

function mostrarResultado(res) {
    const estilos = {
        PASS: ['alert-success', 'bi-check-circle-fill', 'PASS: la comprobación pasó'],
        FAIL: ['alert-warning', 'bi-exclamation-triangle-fill', 'FAIL: el resultado no coincide con lo esperado'],
        ERROR: ['alert-danger', 'bi-x-octagon-fill', 'ERROR: la comprobación no pudo evaluarse']
    };
    const [clase, icono, titulo] = estilos[res.status] || estilos.ERROR;
    const contenedor = el('inicio-resultado');

    contenedor.innerHTML = `
        <div class="card resultado resultado-${String(res.status || 'ERROR').toLowerCase()}">
            <div class="card-body">
                <div class="alert ${clase} veredicto d-flex align-items-center mb-3" role="status">
                    <i class="bi ${icono} fs-4 me-3"></i><strong class="fs-5">${escapeHTML(titulo)}</strong>
                </div>
                <dl class="row mb-3">
                    <dt class="col-sm-3">Lo que esperabas</dt><dd class="col-sm-9">${escapeHTML(res.expected_text)}</dd>
                    <dt class="col-sm-3">Lo que se obtuvo</dt><dd class="col-sm-9">${escapeHTML(res.obtained_text)}</dd>
                    <dt class="col-sm-3">Por qué</dt><dd class="col-sm-9">${escapeHTML(res.reason)}</dd>
                    ${res.validation_auto ? `<dt class="col-sm-3">Cómo se comparó</dt><dd class="col-sm-9"><i class="bi bi-stars text-primary me-1"></i>${escapeHTML(res.validation_reason)}</dd>` : ''}
                </dl>
                ${res.status === 'ERROR' ? '' : `<h6 class="text-secondary">Datos devueltos por la consulta</h6>${tablaFilas(res)}`}
                <div class="d-flex flex-wrap gap-2 mt-3">
                    <button class="btn btn-primary" id="inicio-btn-repetir"><i class="bi bi-arrow-repeat me-1"></i>Repetir</button>
                    <button class="btn btn-outline-primary" id="inicio-btn-guardar"><i class="bi bi-bookmark-plus me-1"></i>Guardar como caso de prueba</button>
                    <button class="btn btn-outline-secondary" id="inicio-btn-historial"><i class="bi bi-clock-history me-1"></i>Ver en el historial</button>
                </div>
                <p class="small text-muted mt-3 mb-0">
                    <b>PASS</b>: coincide con lo esperado · <b>FAIL</b>: la consulta se ejecutó pero no coincide · <b>ERROR</b>: no se pudo ejecutar o evaluar.
                </p>
                <details class="mt-3">
                    <summary class="small text-secondary">Detalles técnicos</summary>
                    <ul class="small mt-2 mb-0">
                        <li>Registro de historial: #${res.history_id}</li>
                        <li>Conexión: ${escapeHTML(res.connection_name)} (${escapeHTML(res.environment_type)})</li>
                        <li>Validación: ${escapeHTML(res.validation_type)} · esperado indicado: ${escapeHTML(res.expected_result)}</li>
                        <li>Filas devueltas por la consulta: ${res.rowcount} · Duración: ${res.duration_ms} ms</li>
                        <li>SQL ejecutado: <code>${escapeHTML(res.sql_query)}</code></li>
                        ${res.error_message ? `<li>Mensaje técnico: ${escapeHTML(res.error_message)}</li>` : ''}
                    </ul>
                </details>
            </div>
        </div>`;
    contenedor.classList.remove('hidden');

    el('inicio-btn-repetir').addEventListener('click', ejecutarComprobacion);
    el('inicio-btn-historial').addEventListener('click', () => irASeccion && irASeccion('historial'));
    el('inicio-btn-guardar').addEventListener('click', guardarComoCaso);
    contenedor.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function guardarComoCaso() {
    const u = ultimaEjecucion;
    if (!u) return;
    // El valor esperado es el que la persona indicó ANTES de ejecutar; aquí debe confirmarlo explícitamente.
    formCaso(null, {
        name: '',
        description: 'Creado desde el recorrido guiado de Inicio.',
        sql_query: u.sql_query,
        validation_type: u.validation_type,
        expected_result: u.expected_result,
        confirmar: `Confirmo que el resultado esperado («${u.expected_result}») es el correcto para este caso.`,
        advertencia: u.status === 'PASS' ? null :
            `Esta comprobación terminó en ${u.status}. Antes de guardarla, revise si el valor esperado es el correcto o si el dato tiene un problema.`
    });
}

// ---------------------------------------------------------------------------------------------
// Demostración guiada: el servidor ejecuta tres suites (reglas, FAIL/ERROR, control de cambios) y dice si cada caso dio lo esperado.
// ---------------------------------------------------------------------------------------------

async function ejecutarDemoGuiada() {
    mostrarAlerta('');
    const cont = el('inicio-guiada-resultado');
    const dc = datosConexion();
    if (!dc) { cont.classList.remove('hidden'); cont.innerHTML = `<div class="alert alert-warning mb-0">${escapeHTML(el('inicio-alerta').textContent || 'Complete el paso 1: conexión TEST y contraseña.')}</div>`; return; }
    const btn = el('inicio-btn-guiada');
    btn.disabled = true;
    cont.classList.remove('hidden');
    cont.innerHTML = '<p class="text-muted mb-0"><span class="spinner-border spinner-border-sm me-2"></span>Ejecutando la demostración…</p>';
    try {
        const res = await fetchAPI('/demo/guided', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ connection_profile_id: parseInt(dc.conn.id), password: dc.password })
        });
        mostrarDemoGuiada(res);
        if (alEjecutarFn) alEjecutarFn();
        await detectarSuitesDemo();
    } catch (err) {
        cont.innerHTML = `<div class="alert alert-danger mb-0">${escapeHTML(typeof err.message === 'string' ? err.message : 'No se pudo ejecutar la demostración.')}</div>`;
    } finally {
        btn.disabled = false;
    }
}

function mostrarDemoGuiada(res) {
    const insignia = { PASS: 'bg-success', FAIL: 'bg-warning text-dark', ERROR: 'bg-danger' };
    const pasos = res.pasos.map(p => {
        const filas = p.casos.map(c => `
            <tr>
                <td><strong>${escapeHTML(c.case_name)}</strong><div class="small text-muted">${escapeHTML(c.reason)}</div></td>
                <td><span class="badge ${insignia[c.status] || 'bg-secondary'}">${escapeHTML(c.status)}</span></td>
                <td>${c.como_se_esperaba
                    ? '<span class="text-success"><i class="bi bi-check-circle-fill me-1"></i>como se esperaba</span>'
                    : `<span class="text-danger"><i class="bi bi-exclamation-triangle-fill me-1"></i>se esperaba ${escapeHTML(c.estado_esperado_por_el_guion || '—')}</span>`}</td>
            </tr>`).join('');
        return `
            <h6 class="fw-bold mt-3 mb-1">${escapeHTML(p.titulo)}
                <small class="text-muted fw-normal">· ${p.passed} PASS · ${p.failed} FAIL · ${p.errors} ERROR</small></h6>
            <p class="small text-muted mb-2">${escapeHTML(p.descripcion)}</p>
            <div class="table-responsive"><table class="table table-sm table-bordered align-middle mb-0">
                <thead class="table-light"><tr><th>Comprobación</th><th>Resultado</th><th>Según el guion</th></tr></thead><tbody>${filas}</tbody></table></div>`;
    }).join('');
    el('inicio-guiada-resultado').innerHTML = `
        <div class="alert ${res.todo_como_se_esperaba ? 'alert-success' : 'alert-warning'} mb-0">
            <strong>${res.todo_como_se_esperaba ? 'Todo salió como la demostración espera.' : 'Algo salió distinto de lo esperado.'}</strong>
            ${res.todo_como_se_esperaba ? '' : ' Revise que la tabla FRAMEWORK_TEST_ITEMS tenga los datos de ejemplo (5 productos, 4 activos).'}
            <span class="small">Conexión «${escapeHTML(res.conexion)}» (${escapeHTML(res.ambiente)}). Cada ejecución quedó en el historial.</span>
        </div>
        ${pasos}
        <p class="small text-muted mt-3 mb-0">El «ERROR» del DROP es el resultado correcto: la aplicación lo rechaza antes de llegar a Oracle. Bloquear DROP es un control de seguridad; el beneficio principal es repetir comprobaciones y conservar su evidencia.</p>`;
}

// ---------------------------------------------------------------------------------------------
// Asistente de reglas: el servidor (/api/rules/*) convierte una regla común en SELECT + validación + esperado.
// El SQL se genera y se valida en el servidor; aquí solo se muestran los campos y la vista previa.
// ---------------------------------------------------------------------------------------------

let reglas = [];
let reglaConstruida = null;
let temporizadorRegla = null;

async function cargarCatalogoReglas() {
    const sel = el('inicio-regla');
    try {
        reglas = await fetchAPI('/rules/templates') || [];
    } catch (e) {
        reglas = [];
    }
    if (!reglas.length) {
        sel.innerHTML = '<option value="">El asistente no está disponible; use un ejemplo o escriba su SELECT</option>';
        return;
    }
    sel.innerHTML = '<option value="">Elija una regla…</option>' +
        reglas.map(r => `<option value="${escapeHTML(r.id)}">${escapeHTML(r.titulo)}</option>`).join('');
}

function reglaSeleccionada() {
    return reglas.find(r => r.id === el('inicio-regla').value) || null;
}

function mostrarCamposRegla() {
    const r = reglaSeleccionada();
    const campos = el('inicio-regla-campos');
    reglaConstruida = null;
    el('inicio-regla-usar').disabled = true;
    el('inicio-regla-vista').classList.add('hidden');
    el('inicio-regla-error').classList.add('hidden');
    if (!r) { el('inicio-regla-desc').textContent = ''; campos.innerHTML = ''; return; }
    el('inicio-regla-desc').textContent = r.descripcion;
    campos.innerHTML = r.parametros.map(p => `
        <div class="col-md-4">
            <label class="form-label small mb-0">${escapeHTML(p.etiqueta)}</label>
            <input type="text" class="form-control form-control-sm" data-regla-param="${escapeHTML(p.nombre)}"
                   value="${escapeHTML(p.ejemplo)}" placeholder="${escapeHTML(p.ayuda || '')}" autocomplete="off">
        </div>`).join('');
    campos.querySelectorAll('[data-regla-param]').forEach(i => i.addEventListener('input', programarVistaPrevia));
    construirRegla();
}

function programarVistaPrevia() {
    clearTimeout(temporizadorRegla);
    temporizadorRegla = setTimeout(construirRegla, 300);
}

async function construirRegla() {
    const r = reglaSeleccionada();
    if (!r) return;
    const params = {};
    el('inicio-regla-campos').querySelectorAll('[data-regla-param]').forEach(i => { params[i.dataset.reglaParam] = i.value.trim(); });
    const err = el('inicio-regla-error');
    try {
        const res = await fetchAPI('/rules/build', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rule_id: r.id, params })
        });
        reglaConstruida = res;
        err.classList.add('hidden');
        el('inicio-regla-sql').textContent = res.sql;
        el('inicio-regla-explica').innerHTML = `<b>Se comprobará:</b> ${escapeHTML(res.explicacion)}`;
        el('inicio-regla-vista').classList.remove('hidden');
        el('inicio-regla-usar').disabled = false;
    } catch (e) {
        reglaConstruida = null;
        el('inicio-regla-vista').classList.add('hidden');
        el('inicio-regla-usar').disabled = true;
        err.textContent = (e && typeof e.message === 'string') ? e.message : 'Revise los datos de la regla.';
        err.classList.remove('hidden');
    }
}

function usarRegla() {
    const b = reglaConstruida;
    if (!b) return;
    el('inicio-sql').value = b.sql;
    el('inicio-validacion').value = b.validation_type;
    actualizarCampoEsperado();
    if (b.validation_type === 'EXISTS') el('inicio-esperado-bool').value = b.expected_result;
    else if (b.validation_type === 'SCALAR_VALUE') el('inicio-esperado-valor').value = b.expected_result;
    else el('inicio-esperado-num').value = b.expected_result;
    el('inicio-plantilla').value = '';
    el('inicio-plantilla-nota').textContent = 'Regla del asistente: ' + b.explicacion + ' Puede ejecutarla tal cual o ajustar la consulta.';
    actualizarAvisoCount();
    ocultarResultado();
    el('inicio-btn-ejecutar').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// ---------------------------------------------------------------------------------------------
// Suite de demostración: se configura una vez y se repite sin reconstruir los casos.
// ---------------------------------------------------------------------------------------------

const NOMBRES_DEMO = {
    rules: 'Demo: reglas de calidad de FRAMEWORK_TEST_ITEMS',
    examples: 'Demo: ejemplos de FAIL y ERROR (intencionales)'
};

function mostrarBotonesSuites() {
    const listo = !!demo;
    el('inicio-demo-cargar').classList.toggle('hidden', listo);
    el('inicio-demo-listo').classList.toggle('hidden', !listo);
}

async function detectarSuitesDemo() {
    try {
        const suites = await fetchAPI(`/suites/?project_id=${estado.proyectoActivoId}`) || [];
        const rules = suites.find(s => s.name === NOMBRES_DEMO.rules);
        const examples = suites.find(s => s.name === NOMBRES_DEMO.examples);
        demo = (rules && examples) ? { rules: { id: rules.id, name: rules.name }, examples: { id: examples.id, name: examples.name } } : null;
    } catch (e) {
        demo = null;
    }
    mostrarBotonesSuites();
}

async function cargarSuitesDemo() {
    if (!estado.proyectoActivoId) return mostrarAlerta('Primero seleccione o cree un proyecto activo.');
    try {
        const r = await fetchAPI('/demo/scenario', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_id: estado.proyectoActivoId })
        });
        demo = { rules: { id: r.rules_suite.suite_id, name: r.rules_suite.suite_name },
                 examples: { id: r.examples_suite.suite_id, name: r.examples_suite.suite_name } };
        mostrarBotonesSuites();
        Swal.fire('Suites cargadas', 'Se crearon (o ya existían) los casos y las dos suites de demostración. Ahora puede ejecutarlas.', 'success');
    } catch (err) {
        handleAPIError(err);
    }
}

async function ejecutarSuite(cual) {
    mostrarAlerta('');
    const dc = datosConexion();
    if (!dc || !demo) return;
    const suite = demo[cual];
    const cont = el('inicio-suite-resultado');
    cont.classList.remove('hidden');
    cont.innerHTML = '<p class="text-muted mb-0"><span class="spinner-border spinner-border-sm me-2"></span>Ejecutando la suite…</p>';
    try {
        const res = await fetchAPI(`/execute/suite/${suite.id}`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ connection_profile_id: parseInt(dc.conn.id), password: dc.password })
        });
        mostrarResultadoSuite(res, cual);
        if (alEjecutarFn) alEjecutarFn();
    } catch (err) {
        cont.classList.add('hidden');
        handleAPIError(err);
    }
}

function mostrarResultadoSuite(res, cual) {
    const cont = el('inicio-suite-resultado');
    const insignia = { PASS: 'bg-success', FAIL: 'bg-warning text-dark', ERROR: 'bg-danger' };
    const filas = (res.case_results || []).map(r => `
        <tr>
            <td><strong>${escapeHTML(r.case_name)}</strong></td>
            <td>${escapeHTML(r.expected_text)}</td>
            <td>${escapeHTML(r.obtained_text)}</td>
            <td><span class="badge ${insignia[r.status] || 'bg-secondary'}">${escapeHTML(r.status)}</span></td>
            <td class="small">${escapeHTML(r.reason)}</td>
        </tr>`).join('');
    const todoBien = res.failed === 0 && res.errors === 0;
    cont.innerHTML = `
        <div class="alert ${todoBien ? 'alert-success' : 'alert-warning'} mb-3">
            <strong>${escapeHTML(res.suite_name)}</strong>:
            ${res.passed} PASS · ${res.failed} FAIL · ${res.errors} ERROR (de ${res.total_tests} reglas, ${res.total_duration_ms} ms)
        </div>
        <div class="table-responsive">
            <table class="table table-sm table-bordered align-middle mb-3">
                <thead class="table-light"><tr><th>Regla</th><th>Se esperaba</th><th>Se obtuvo</th><th>Estado</th><th>Por qué</th></tr></thead>
                <tbody>${filas}</tbody>
            </table>
        </div>
        <div class="d-flex flex-wrap gap-2">
            <button class="btn btn-primary" id="inicio-btn-suite-repetir"><i class="bi bi-arrow-repeat me-1"></i>Ejecutar de nuevo</button>
            <button class="btn btn-outline-secondary" id="inicio-btn-suite-historial"><i class="bi bi-clock-history me-1"></i>Ver en el historial</button>
        </div>
        <p class="small text-muted mt-3 mb-0">Cada ejecución queda en el historial con su fecha, lo esperado y lo obtenido. Los casos ya están guardados: repetirla no exige volver a escribirlos.</p>`;
    el('inicio-btn-suite-repetir').addEventListener('click', () => ejecutarSuite(cual));
    el('inicio-btn-suite-historial').addEventListener('click', () => irASeccion && irASeccion('historial'));
    cont.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
