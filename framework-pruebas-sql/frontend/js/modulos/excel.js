import { estado } from '../core/estado.js';
import { API_URL, handleAPIError } from '../core/api.js';
import { escapeHTML } from '../core/utilidades.js';
import { cargarCasos } from './casos.js';

// Integración con Excel: plantilla, importar casos (con validación previa) y exportar casos o resultados.
// El servidor valida todo (app/services/excel_io.py); aquí solo se envía el archivo y se muestra el informe.

async function descargar(ruta, nombreAlternativo) {
    const res = await fetch(API_URL + ruta);
    if (!res.ok) {
        let msg = 'No se pudo generar el archivo.';
        try { msg = (await res.json()).detail || msg; } catch (e) { /* respuesta sin JSON */ }
        throw { status: res.status, message: msg };
    }
    const m = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') || '');
    const nombre = m ? m[1] : nombreAlternativo;
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement('a');
    a.href = url; a.download = nombre;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    return nombre;
}

export async function descargarPlantilla() {
    try { await descargar('/excel/template', 'plantilla_casos.xlsx'); } catch (e) { handleAPIError(e); }
}

export async function exportarCasos() {
    if (!estado.proyectoActivoId) return Swal.fire('Atención', 'Seleccione un proyecto activo.', 'warning');
    try { await descargar(`/excel/cases/export?project_id=${estado.proyectoActivoId}`, 'casos.xlsx'); } catch (e) { handleAPIError(e); }
}

export async function exportarResultados() {
    const p = new URLSearchParams();
    if (estado.proyectoActivoId) p.set('project_id', estado.proyectoActivoId);
    const status = document.getElementById('filtro-hist-status')?.value;
    const suite = document.getElementById('filtro-hist-suite')?.value;
    if (status) p.set('status', status);
    if (suite) p.set('suite_id', suite);
    try { await descargar(`/excel/results/export?${p.toString()}`, 'resultados.xlsx'); } catch (e) { handleAPIError(e); }
}

async function enviar(archivo, modo, soloValidar) {
    const res = await fetch(`${API_URL}/excel/cases/import?project_id=${estado.proyectoActivoId}&mode=${modo}&dry_run=${soloValidar}`, {
        method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: archivo
    });
    let cuerpo = null;
    try { cuerpo = await res.json(); } catch (e) { /* sin JSON */ }
    if (!res.ok) throw { status: res.status, message: (cuerpo && cuerpo.detail) || 'No se pudo procesar el archivo.' };
    return cuerpo;
}

function tablaErrores(errores) {
    const filas = errores.slice(0, 50).map(e => `<tr><td>${e.fila}</td><td>${escapeHTML(e.campo)}</td><td>${escapeHTML(e.mensaje)}</td></tr>`).join('');
    const mas = errores.length > 50 ? `<p class="small text-muted">…y ${errores.length - 50} más.</p>` : '';
    return `<div class="text-start" style="max-height:280px; overflow-y:auto"><table class="table table-sm"><thead><tr><th>Fila</th><th>Campo</th><th>Problema</th></tr></thead><tbody>${filas}</tbody></table>${mas}</div>`;
}

export async function importarExcel() {
    if (!estado.proyectoActivoId) return Swal.fire('Atención', 'Seleccione un proyecto activo.', 'warning');
    const paso1 = await Swal.fire({
        title: 'Importar casos desde Excel',
        html: `<div class="text-start small">
            <p>Use la plantilla (botón «Plantilla»). Primero se <b>valida</b> sin guardar nada; si hay un solo error no se importa nada.</p>
            <input type="file" id="excel-archivo" class="form-control mb-2" accept=".xlsx">
            <label class="form-label mb-0">Si un caso ya existe (mismo nombre):</label>
            <select id="excel-modo" class="form-select"><option value="skip">Omitirlo</option><option value="update">Actualizarlo</option></select></div>`,
        showCancelButton: true, confirmButtonText: 'Validar', cancelButtonText: 'Cancelar',
        preConfirm: () => {
            const f = document.getElementById('excel-archivo').files[0];
            if (!f) { Swal.showValidationMessage('Elija un archivo .xlsx'); return false; }
            if (!f.name.toLowerCase().endsWith('.xlsx')) { Swal.showValidationMessage('Solo se admiten archivos .xlsx'); return false; }
            if (f.size > 2 * 1024 * 1024) { Swal.showValidationMessage('El archivo supera los 2 MB'); return false; }
            return { archivo: f, modo: document.getElementById('excel-modo').value };
        }
    });
    if (!paso1.isConfirmed) return;
    const { archivo, modo } = paso1.value;

    let validacion;
    try { validacion = await enviar(archivo, modo, true); } catch (e) { return handleAPIError(e); }
    if (!validacion.ok) {
        return Swal.fire({ icon: 'error', title: 'El archivo tiene errores: no se importó nada', width: 760, html: tablaErrores(validacion.errores) });
    }
    const paso2 = await Swal.fire({
        icon: 'question', title: 'Validación correcta',
        html: `<p>Se crearán <b>${validacion.n_crear}</b> caso(s), se actualizarán <b>${validacion.n_actualizar}</b> y se omitirán <b>${validacion.n_omitidos}</b> (ya existen).</p>`,
        showCancelButton: true, confirmButtonText: 'Importar ahora', cancelButtonText: 'Cancelar'
    });
    if (!paso2.isConfirmed) return;
    try {
        const r = await enviar(archivo, modo, false);
        await Swal.fire({ icon: 'success', title: 'Importación completada', text: r.mensaje + (r.suites_creadas ? ` Suites nuevas: ${r.suites_creadas}.` : '') });
        cargarCasos();
    } catch (e) { handleAPIError(e); }
}
