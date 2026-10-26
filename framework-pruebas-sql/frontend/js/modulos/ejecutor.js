import { estado } from '../core/estado.js';
import { fetchAPI, handleAPIError, API_URL } from '../core/api.js';
import { actualizarDatosProyectoActivo } from './dashboard.js';
import { escapeHTML } from '../core/utilidades.js';
import { insigniaEstado, mostrarDetalleEjecucion } from './historial.js';

const ICONO_CAMBIO = { nuevo_fallo: 'bi-arrow-down-right-circle-fill', corregido: 'bi-arrow-up-right-circle-fill', igual: 'bi-dash-circle', primera_vez: 'bi-stars', cambio: 'bi-arrow-left-right' };

let modalPwdInst = null;
let execAction = null;
let execTargetId = null;

export function getModalPwdInst() {
    if (!modalPwdInst) {
        modalPwdInst = new bootstrap.Modal(document.getElementById("modalPassword"));
    }
    return modalPwdInst;
}

export function abrirTestConexion(connId) {
    execAction = "TEST_CONN"; execTargetId = connId;
    const conn = estado.conexiones.find(c => c.id == connId);
    document.getElementById("pwd-conn-select-container").classList.add("hidden");
    document.getElementById("pwd-password").value = "";
    document.getElementById("modalPasswordText").innerText = `Probar la conexión «${conn ? conn.name : '#' + connId}»: escriba la contraseña del usuario Oracle. Solo se usa para esta prueba.`;
    getModalPwdInst().show();
}

export async function abrirEjecucion(type, targetId) {
    if (estado.conexiones.length === 0) {
        Swal.fire({ icon: "info", title: "Falta una conexión", text: document.body.classList.contains('rol-tester')
            ? "Este proyecto aún no tiene conexiones Oracle. Pida a un administrador que cree una."
            : "Cree primero una conexión Oracle en «Conexiones Oracle»." });
        return;
    }
    execAction = type; execTargetId = targetId;
    const sel = document.getElementById("pwd-connection-id");
    sel.innerHTML = "";
    estado.conexiones.forEach(c => { const opt = document.createElement("option"); opt.value = c.id; opt.textContent = `${c.name} (${c.environment_type})`; sel.appendChild(opt); });
    document.getElementById("pwd-conn-select-container").classList.remove("hidden");
    document.getElementById("pwd-password").value = "";
    const lista = type === 'SUITE' ? estado.suites : estado.casos;
    const item = (lista || []).find(x => x.id == targetId);
    const nombre = item ? `«${item.name}»` : `#${targetId}`;
    document.getElementById("modalPasswordText").innerText = type === 'SUITE'
        ? `Ejecutar la suite ${nombre}: se ejecutan todos sus casos y cada resultado queda en el historial.`
        : `Ejecutar el caso ${nombre} y comparar con el resultado esperado.`;
    getModalPwdInst().show();
}

async function confirmarAmbiente(conn) {
    if (conn.environment_type === 'STAGING') {
        const r = await Swal.fire({ icon: 'warning', title: 'Ambiente STAGING',
            html: 'Si hay INSERT, UPDATE o DELETE se ejecutarán y luego <b>se revertirán</b> (rollback). ¿Continuar?',
            showCancelButton: true, confirmButtonText: 'Sí, ejecutar', cancelButtonText: 'Cancelar' });
        return r.isConfirmed ? 'STAGING_OK' : null;
    }
    if (conn.environment_type === 'PRODUCTION') {
        const r = await Swal.fire({ icon: 'warning', title: 'Ambiente PRODUCTION',
            html: 'Solo se permiten consultas SELECT y no se mostrarán las filas. Cualquier cambio será rechazado. ¿Continuar?',
            showCancelButton: true, confirmButtonText: 'Sí, solo lectura', cancelButtonText: 'Cancelar', confirmButtonColor: '#ef4444' });
        return r.isConfirmed ? 'OK' : null;
    }
    return 'OK';
}

export function mostrarResultadoSuite(res) {
    const todoBien = res.failed === 0 && res.errors === 0;
    const total = res.total_tests || 1;
    const barra = (n, clase) => n ? `<div class="seg-${clase}" style="width:${(100 * n / total).toFixed(1)}%"></div>` : '';
    const filas = (res.case_results || []).map(r => `
        <div class="fila-resultado ${r.change === 'nuevo_fallo' ? 'fila-nuevo-fallo' : ''}">
            ${insigniaEstado(r.status)}
            <div class="flex-grow-1"><b>${escapeHTML(r.case_name)}</b>
                <div class="small text-muted">esperado: ${escapeHTML(r.expected_text)} · obtenido: ${escapeHTML(r.obtained_text)}</div>
                ${r.status !== 'PASS' ? `<div class="small">${escapeHTML(r.reason)}</div>` : ''}
                ${r.change ? `<div class="cambio cambio-${r.change}"><i class="bi ${ICONO_CAMBIO[r.change] || 'bi-dash'}"></i> ${escapeHTML(r.change_text)}${r.previous_status ? ` (antes: ${escapeHTML(r.previous_status)})` : ''}</div>` : ''}</div>
        </div>`).join('');
    const comparacion = (res.new_failures || res.fixed)
        ? `<div class="aviso-comparacion">${res.new_failures ? `<span class="cambio cambio-nuevo_fallo"><i class="bi bi-arrow-down-right-circle-fill"></i> ${res.new_failures} fallo(s) nuevo(s)</span>` : ''}
            ${res.fixed ? `<span class="cambio cambio-corregido"><i class="bi bi-arrow-up-right-circle-fill"></i> ${res.fixed} corregido(s)</span>` : ''}
            <span class="small text-muted">frente a la ejecución anterior de cada caso</span></div>` : '';
    const descargas = res.run_id ? `<div class="d-flex flex-wrap gap-2 mt-3">
            <a class="btn btn-sm btn-outline-primary" href="${API_URL}/history/runs/${encodeURIComponent(res.run_id)}/report" download><i class="bi bi-file-earmark-richtext me-1"></i>Descargar reporte</a>
            <a class="btn btn-sm btn-outline-success" href="${API_URL}/excel/results/export?run_id=${encodeURIComponent(res.run_id)}" download><i class="bi bi-file-earmark-excel me-1"></i>Excel de esta corrida</a></div>` : '';
    Swal.fire({
        width: 720, confirmButtonText: 'Cerrar',
        html: `<div class="text-start">
            <div class="veredicto-mini veredicto-${todoBien ? 'pass' : (res.errors ? 'error' : 'fail')}">
                <i class="bi ${todoBien ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill'}"></i>
                <div><b>${escapeHTML(res.suite_name)}</b> · ${todoBien ? 'todos los casos pasaron' : 'hay casos que revisar'}</div></div>
            <div class="resumen-suite">
                <span class="estado-pill estado-pass">${res.passed} PASS</span>
                <span class="estado-pill estado-fail">${res.failed} FAIL</span>
                <span class="estado-pill estado-error">${res.errors} ERROR</span>
                <span class="small text-muted ms-auto">${res.total_tests} casos · ${Math.round(res.total_duration_ms)} ms</span>
            </div>
            <div class="barra-resultados">${barra(res.passed, 'pass')}${barra(res.failed, 'fail')}${barra(res.errors, 'error')}</div>
            ${comparacion}
            <div class="lista-resultados">${filas}</div>
            <div class="small text-muted mt-2">Cada caso quedó guardado en el Historial.</div>
            ${descargas}
        </div>`
    });
}

export async function procesarPasswordSubmit(e) {
    e.preventDefault();
    const pwd = document.getElementById("pwd-password").value;
    const btn = document.getElementById("pwd-submit-btn");
    const spinner = document.getElementById("pwd-submit-spinner");
    const text = document.getElementById("pwd-submit-text");
    const connId = document.getElementById("pwd-connection-id").value;

    let isStagingConfirmed = false;
    if (execAction !== "TEST_CONN") {
        const conn = estado.conexiones.find(c => c.id == connId);
        if (conn) {
            getModalPwdInst().hide();
            const ok = await confirmarAmbiente(conn);
            if (!ok) { document.getElementById("pwd-password").value = ""; return; }
            isStagingConfirmed = ok === 'STAGING_OK';
        }
    }

    btn.disabled = true; spinner.classList.remove("hidden"); text.innerText = "Ejecutando...";
    try {
        if (execAction === "TEST_CONN") {
            await fetchAPI(`/connections/${execTargetId}/test`, { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({password: pwd}) });
            getModalPwdInst().hide();
            Swal.fire({ icon: "success", title: "Conexión correcta", text: "La aplicación pudo conectarse a Oracle con ese usuario.", timer: 2200, showConfirmButton: false });
        } else if (execAction === "CASE") {
            Swal.fire({ title: 'Ejecutando…', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
            const res = await fetchAPI(`/execute/test-case/${execTargetId}`, { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({connection_profile_id: parseInt(connId), password: pwd, confirm_staging_dml: isStagingConfirmed}) });
            mostrarDetalleEjecucion(res);
            actualizarDatosProyectoActivo();
        } else if (execAction === "SUITE") {
            Swal.fire({ title: 'Ejecutando la suite…', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
            const res = await fetchAPI(`/execute/suite/${execTargetId}`, { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({connection_profile_id: parseInt(connId), password: pwd, confirm_staging_dml: isStagingConfirmed}) });
            mostrarResultadoSuite(res);
            actualizarDatosProyectoActivo();
        }
    } catch(err) {
        getModalPwdInst().hide();
        handleAPIError(err);
    } finally {
        document.getElementById("pwd-password").value = "";
        btn.disabled = false; spinner.classList.add("hidden"); text.innerText = "Ejecutar";
    }
}
