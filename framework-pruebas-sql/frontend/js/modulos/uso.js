import { estado } from '../core/estado.js';
import { fetchAPI } from '../core/api.js';
import { escapeHTML } from '../core/utilidades.js';

// Dashboard de utilización: todas las cifras salen de GET /api/usage/summary, que las calcula con datos guardados
// en la base interna (execution_history, test_cases, test_suites, usage_events). Aquí no se calcula ni se inventa nada.

const el = (id) => document.getElementById(id);
let irASeccion = null;

export function initUso(irA) {
    irASeccion = irA;
    el('uso-dias').addEventListener('change', cargarUso);
    el('uso-alcance').addEventListener('change', cargarUso);
}

const fmt = (n) => (n === null || n === undefined) ? '—' : Number(n).toLocaleString('es-PE');
const pct = (n) => (n === null || n === undefined) ? '—' : `${n}%`;

function tarjeta(titulo, valor, definicion, clase = 'primary') {
    return `<div class="col-6 col-lg-4 col-xl-2 mb-3">
        <div class="card p-3 h-100 border-start border-${clase} border-4">
            <div class="small text-muted">${escapeHTML(titulo)}</div>
            <div class="fs-3 fw-bold">${valor}</div>
            <div class="uso-def">${escapeHTML(definicion)}</div>
        </div></div>`;
}

function tabla(titulo, definicion, cabeceras, filas, vacio) {
    const cuerpo = filas.length
        ? filas.map(f => `<tr>${f.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')
        : `<tr><td colspan="${cabeceras.length}" class="text-muted text-center">${escapeHTML(vacio)}</td></tr>`;
    return `<div class="card mb-3"><div class="card-header bg-white"><h6 class="m-0 fw-bold text-secondary">${escapeHTML(titulo)}</h6>
            <div class="uso-def">${escapeHTML(definicion)}</div></div>
        <div class="table-responsive"><table class="table table-sm align-middle mb-0">
            <thead class="table-light"><tr>${cabeceras.map(c => `<th>${escapeHTML(c)}</th>`).join('')}</tr></thead>
            <tbody>${cuerpo}</tbody></table></div></div>`;
}

const insignia = (estadoTxt) => {
    const c = estadoTxt === 'PASS' ? 'bg-success' : (estadoTxt === 'FAIL' ? 'bg-warning text-dark' : 'bg-danger');
    return `<span class="badge ${c}">${escapeHTML(estadoTxt)}</span>`;
};

function graficoPorFecha(d) {
    const max = Math.max(1, ...d.por_fecha.map(x => x.total));
    const barras = d.por_fecha.map(x => {
        const alto = (v) => (v / max) * 100;
        const titulo = `${x.fecha}: ${x.total} ejecuciones (PASS ${x.pass}, FAIL ${x.fail}, ERROR ${x.error})`;
        return `<div class="uso-col" title="${escapeHTML(titulo)}" aria-label="${escapeHTML(titulo)}">
            <div class="uso-pila">
                <div class="uso-seg bg-danger" style="height:${alto(x.error)}%"></div>
                <div class="uso-seg bg-warning" style="height:${alto(x.fail)}%"></div>
                <div class="uso-seg bg-success" style="height:${alto(x.pass)}%"></div>
            </div></div>`;
    }).join('');
    const n = d.por_fecha.length;
    return `<div class="uso-barras">${barras}</div>
        <div class="d-flex justify-content-between small text-muted mt-1">
            <span>${escapeHTML(d.por_fecha[0].fecha)}</span><span>${escapeHTML(d.por_fecha[Math.floor(n / 2)].fecha)}</span><span>${escapeHTML(d.por_fecha[n - 1].fecha)}</span></div>
        <div class="small mt-2"><span class="badge bg-success">PASS</span> <span class="badge bg-warning text-dark">FAIL</span> <span class="badge bg-danger">ERROR</span>
            <span class="text-muted ms-2">Altura máxima = ${fmt(max)} ejecuciones en un día.</span></div>`;
}

function barraResultados(t) {
    const total = t.total_ejecuciones;
    if (!total) return '';
    const seg = (v, c) => v ? `<div class="bg-${c}" style="width:${(100 * v / total).toFixed(1)}%" title="${v}"></div>` : '';
    return `<div class="uso-resultados">${seg(t.pass, 'success')}${seg(t.fail, 'warning')}${seg(t.error, 'danger')}</div>
        <div class="small mt-1"><span class="text-success fw-bold">PASS ${fmt(t.pass)}</span> · <span class="text-warning fw-bold">FAIL ${fmt(t.fail)}</span> · <span class="text-danger fw-bold">ERROR ${fmt(t.error)}</span></div>`;
}

function renderizar(d) {
    const def = d.definiciones, t = d.tarjetas;
    let html = `<p class="small text-muted">Alcance: <b>${escapeHTML(d.alcance.proyecto)}</b> · Periodo: <b>${escapeHTML(d.periodo.desde)}</b> a <b>${escapeHTML(d.periodo.hasta)}</b> (${d.periodo.dias} días, ${escapeHTML(d.periodo.zona)}).
        Datos guardados en la base interna de la aplicación.</p>`;

    if (!d.hay_datos) {
        html += `<div class="alert alert-info d-flex flex-wrap align-items-center gap-3" role="status">
            <div><i class="bi bi-info-circle-fill me-2"></i><b>Sin ejecuciones en este periodo.</b> ${escapeHTML(d.mensaje_vacio)}</div>
            <button class="btn btn-sm btn-primary" id="uso-ir-inicio"><i class="bi bi-rocket-takeoff me-1"></i>Ir a Inicio</button></div>`;
    } else {
        html += `<div class="row">
            ${tarjeta('Ejecuciones', fmt(t.total_ejecuciones), def.total_ejecuciones)}
            ${tarjeta('Corridas de suite', fmt(t.corridas_de_suite), def.corridas_de_suite, 'info')}
            ${tarjeta('Tasa de PASS', pct(t.tasa_pass), def.tasa_pass, 'success')}
            ${tarjeta('Casos distintos', fmt(t.casos_distintos), def.casos_distintos, 'secondary')}
            ${tarjeta('Proyectos activos', fmt(t.proyectos_activos), def.proyectos_activos, 'secondary')}
            ${tarjeta('Duración media', t.duracion_media_ms === null ? '—' : `${fmt(t.duracion_media_ms)} ms`, 'Tiempo medio de ejecución por registro, medido por la aplicación.', 'warning')}
        </div>
        <div class="row">
            <div class="col-lg-8 mb-3"><div class="card h-100"><div class="card-header bg-white"><h6 class="m-0 fw-bold text-secondary">Ejecuciones por fecha</h6>
                <div class="uso-def">${escapeHTML(def.por_fecha)}</div></div><div class="card-body">${graficoPorFecha(d)}</div></div></div>
            <div class="col-lg-4 mb-3"><div class="card h-100"><div class="card-header bg-white"><h6 class="m-0 fw-bold text-secondary">Resultados</h6>
                <div class="uso-def">PASS: coincide con lo esperado · FAIL: se ejecutó pero no coincide · ERROR: no se pudo ejecutar o evaluar.</div></div>
                <div class="card-body">${barraResultados(t)}</div></div></div>
        </div>`;

        html += `<div class="row"><div class="col-lg-6">${tabla('Casos más ejecutados', def.top_casos,
            ['Caso', 'Ejec.', 'PASS', 'FAIL', 'ERROR', 'Último'],
            d.top_casos.map(c => [escapeHTML(c.nombre), fmt(c.ejecuciones), fmt(c.pass), fmt(c.fail), fmt(c.error), insignia(c.ultimo_estado)]),
            'Sin casos ejecutados.')}</div>
            <div class="col-lg-6">${tabla('Suites más usadas', def.top_suites, ['Suite', 'Corridas', 'Ejec.', '% PASS'],
            d.top_suites.map(s => [escapeHTML(s.nombre), fmt(s.corridas), fmt(s.ejecuciones), pct(s.pct_pass)]),
            'Ninguna suite se ejecutó en este periodo.')}</div></div>
            <div class="row"><div class="col-lg-6">${tabla('Origen de las ejecuciones', def.por_origen, ['Origen', 'Ejecuciones'],
            d.por_origen.map(o => [escapeHTML(o.descripcion), fmt(o.ejecuciones)]), 'Sin datos.')}</div>
            <div class="col-lg-6">${tabla('Proyectos con actividad', def.proyectos_activos, ['Proyecto', 'Ejecuciones'],
            d.proyectos.map(p => [escapeHTML(p.nombre), fmt(p.ejecuciones)]), 'Sin datos.')}</div></div>`;
    }

    html += `<div class="row"><div class="col-lg-6">${tabla('Altas en el periodo', def.altas, ['Elemento', 'Creados', 'Total actual'],
        [['Casos', fmt(d.altas.casos), fmt(d.totales_actuales.casos)], ['Suites', fmt(d.altas.suites), fmt(d.totales_actuales.suites)],
         ['Conexiones', fmt(d.altas.conexiones), fmt(d.totales_actuales.conexiones)]], '')}</div>
        <div class="col-lg-6">${tabla('Otras acciones (Excel, demostración)', def.eventos, ['Acción', 'Veces'],
        d.eventos.map(e => [escapeHTML(e.descripcion), fmt(e.cantidad)]), 'Aún no se importó ni exportó ningún Excel en este periodo.')}</div></div>`;

    html += `<details class="small text-muted mb-3"><summary>Cómo leer estas cifras y sus límites</summary>
        <ul class="mt-2">${Object.entries(def).map(([k, v]) => `<li>${escapeHTML(v)}</li>`).join('')}</ul>
        <p class="mb-1"><b>Límites:</b></p><ul>${d.limitaciones.map(l => `<li>${escapeHTML(l)}</li>`).join('')}</ul>
        ${d.historico.total ? `<p>Histórico total en este alcance: ${fmt(d.historico.total)} ejecuciones (primera: ${escapeHTML(d.historico.primera_ejecucion)}; última: ${escapeHTML(d.historico.ultima_ejecucion)}).</p>` : ''}
        ${d.truncado ? '<p class="text-danger">Se alcanzó el máximo de filas analizadas: las cifras son parciales.</p>' : ''}</details>`;
    return html;
}

export async function cargarUso() {
    const cont = el('uso-contenido');
    cont.innerHTML = '<p class="text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Calculando…</p>';
    const dias = parseInt(el('uso-dias').value);
    const soloProyecto = el('uso-alcance').value === 'proyecto';
    let url = `/usage/summary?days=${dias}`;
    if (soloProyecto && estado.proyectoActivoId) url += `&project_id=${estado.proyectoActivoId}`;
    try {
        const datos = await fetchAPI(url);
        cont.innerHTML = renderizar(datos);
        const btn = el('uso-ir-inicio');
        if (btn) btn.addEventListener('click', () => irASeccion && irASeccion('inicio'));
    } catch (e) {
        cont.innerHTML = `<div class="alert alert-danger" role="alert">No se pudieron calcular las métricas de uso: ${escapeHTML(e.message || 'error del servidor')}.
            <button class="btn btn-sm btn-outline-danger ms-2" id="uso-reintentar">Reintentar</button></div>`;
        el('uso-reintentar').addEventListener('click', cargarUso);
    }
}
