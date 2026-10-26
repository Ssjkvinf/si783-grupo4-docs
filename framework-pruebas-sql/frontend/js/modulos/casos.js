import { estado } from '../core/estado.js';
import { fetchAPI, handleAPIError } from '../core/api.js';
import { escapeHTML, abrirModalGeneral, modalGeneralAction, modalGeneralId, vacio } from '../core/utilidades.js';

let abrirEjecucionFn = null;

export function initCasos(ejecucionFn) {
    abrirEjecucionFn = ejecucionFn;
}

// `prefill` (opcional) rellena un caso NUEVO desde la prueba rápida:
// { name, description, sql_query, validation_type, expected_result, confirmar: 'texto del aviso', advertencia: 'texto' }.
// El valor esperado es siempre el que el usuario indicó antes de ejecutar; nunca el resultado obtenido.
const ETIQUETA_VALIDACION = { ROW_COUNT: 'Cantidad de filas', SCALAR_VALUE: 'Valor', EXISTS: 'Existe sí/no' };

export function formCaso(c = null, prefill = null) {
    const d = c || prefill || {};
    const confirmHtml = prefill?.confirmar ? `
        ${prefill.advertencia ? `<div class="alert alert-warning small">${escapeHTML(prefill.advertencia)}</div>` : ''}
        <div class="form-check mb-2">
            <input class="form-check-input" type="checkbox" id="f-caso-confirm">
            <label class="form-check-label" for="f-caso-confirm">${escapeHTML(prefill.confirmar)}</label>
        </div>` : '';
    const html = `
        <div class="mb-3"><label class="form-label" for="f-caso-name">Nombre</label><input type="text" id="f-caso-name" class="form-control" required placeholder="Ej.: No hay clientes sin correo" value="${escapeHTML(d.name||'')}"></div>
        <div class="mb-3"><label class="form-label" for="f-caso-desc">Descripción <span class="text-muted fw-normal">(opcional)</span></label><textarea id="f-caso-desc" class="form-control" rows="2" placeholder="Qué regla de negocio comprueba">${escapeHTML(d.description||'')}</textarea></div>
        <div class="mb-3"><label class="form-label" for="f-caso-sql">Sentencia SQL</label><textarea class="form-control font-monospace" id="f-caso-sql" rows="4" required placeholder="SELECT COUNT(*) FROM clientes WHERE correo IS NULL">${escapeHTML(d.sql_query||'')}</textarea>
            <div class="form-text">SELECT para comprobar datos. INSERT, UPDATE o DELETE se ejecutan y luego se revierten (solo en TEST y STAGING). DROP, ALTER y similares se rechazan.</div></div>
        <div class="row">
            <div class="col-md-6 mb-3"><label class="form-label">¿Cómo comparar?</label>
                <select class="form-select" id="f-caso-val" required>
                    <option value="AUTO" ${!d.validation_type?'selected':''}>Automático (recomendado): la aplicación decide</option>
                    <option value="ROW_COUNT" ${d.validation_type==='ROW_COUNT'?'selected':''}>ROW_COUNT · cantidad de filas que devuelve la consulta</option>
                    <option value="SCALAR_VALUE" ${d.validation_type==='SCALAR_VALUE'?'selected':''}>SCALAR_VALUE · valor que devuelve la consulta (p. ej. un COUNT)</option>
                    <option value="EXISTS" ${d.validation_type==='EXISTS'?'selected':''}>EXISTS · devuelve filas (true) / ninguna (false)</option>
                </select>
            </div>
            <div class="col-md-6 mb-3"><label class="form-label">Resultado Esperado</label><input type="text" id="f-caso-exp" class="form-control" required value="${escapeHTML(d.expected_result||'')}"></div>
        </div>
        ${confirmHtml}
    `;
    abrirModalGeneral(c ? "Editar Caso" : (prefill ? "Guardar como caso de prueba" : "Nuevo Caso"), html, c ? "CASE_EDIT" : "CASE_NEW", c?.id);

    const selectVal = document.getElementById("f-caso-val");
    const inputExp = document.getElementById("f-caso-exp");

    const updatePlaceholder = () => {
        inputExp.placeholder = selectVal.value === 'AUTO' ? 'Ej.: 5 · 0 · sí · no · un texto' : (selectVal.value === 'EXISTS' ? 'true o false' : (selectVal.value === 'SCALAR_VALUE' ? 'Valor esperado, ej: 0' : 'Número de filas, ej: 1'));
    };
    selectVal.addEventListener('change', updatePlaceholder);
    updatePlaceholder();
}

export async function saveCaso() {
    let exp = document.getElementById("f-caso-exp").value.trim();
    const v = document.getElementById("f-caso-val").value;
    if (v === 'EXISTS') {
        exp = exp.toLowerCase();
        if (exp !== 'true' && exp !== 'false') throw {status: 422, message: "Para EXISTS el valor esperado debe ser 'true' o 'false'."};
    }
    if (v === 'ROW_COUNT' && !/^\d+$/.test(exp)) throw {status: 422, message: "Para ROW_COUNT debe ser un entero >= 0 (cantidad de filas)."};
    if (v === 'SCALAR_VALUE' && exp === '') throw {status: 422, message: "Para SCALAR_VALUE indique el valor esperado (use NULL para un valor nulo)."};
    if (v === 'AUTO' && exp === '') throw {status: 422, message: "Indique el resultado esperado: un número, sí/no o un valor."};
    const confirmBox = document.getElementById("f-caso-confirm");
    if (confirmBox && !confirmBox.checked) throw {status: 422, message: "Confirme que el resultado esperado es el correcto antes de guardar el caso."};

    const payload = { project_id: estado.proyectoActivoId, name: document.getElementById("f-caso-name").value, description: document.getElementById("f-caso-desc").value, sql_query: document.getElementById("f-caso-sql").value, validation_type: v, expected_result: exp };
    
    if (modalGeneralAction === "CASE_NEW") {
        await fetchAPI("/test-cases/", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
        Swal.fire({ icon: "success", title: "Caso guardado", text: "Ya puede ejecutarlo o añadirlo a una suite.", timer: 2000, showConfirmButton: false });
    } else {
        await fetchAPI(`/test-cases/${modalGeneralId}`, { method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
        Swal.fire({ icon: "success", title: "Caso actualizado", timer: 1600, showConfirmButton: false });
    }
    cargarCasos();
}

export async function cargarCasos() {
    try {
        estado.casos = await fetchAPI(`/test-cases/?project_id=${estado.proyectoActivoId}`);
        const tbody = document.getElementById("tabla-casos");
        tbody.innerHTML = "";
        if (estado.casos.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6">${vacio('bi-code-square', 'Todavía no hay casos en este proyecto',
                'Un caso es una consulta con el resultado que usted espera. Créelo aquí, guárdelo desde una prueba de Inicio o impórtelo desde Excel.',
                { id: 'casos-vacio-nuevo', texto: 'Nuevo caso' })}</td></tr>`;
            document.getElementById('casos-vacio-nuevo').addEventListener('click', () => formCaso());
            return;
        }
        estado.casos.forEach((c, i) => {
            const tr = document.createElement("tr");
            tr.className = 'fila-entrar';
            tr.style.animationDelay = `${Math.min(i, 12) * 25}ms`;
            tr.innerHTML = `<td class="text-muted small">${c.id}</td><td><strong>${escapeHTML(c.name)}</strong>${c.description ? `<div class="small text-muted text-truncate" style="max-width:260px">${escapeHTML(c.description)}</div>` : ''}</td>
                <td><code class="sql-cell sql-mini" data-idx="${i}" title="Ver la consulta completa">${escapeHTML(c.sql_query)}</code></td>
                <td><span class="badge badge-validacion badge-${String(c.validation_type).toLowerCase()}" title="${c.validation_type}">${ETIQUETA_VALIDACION[c.validation_type] || c.validation_type}</span></td><td><b>${escapeHTML(c.expected_result)}</b></td>
                <td class="text-end pe-4 text-nowrap">
                    <button class="btn btn-sm btn-success btn-exec" data-id="${c.id}" title="Ejecutar"><i class="bi bi-play-fill"></i></button>
                    <button class="btn btn-sm btn-outline-secondary btn-edit" data-id="${c.id}" title="Editar"><i class="bi bi-pencil"></i></button>
                    <button class="btn btn-sm btn-outline-danger btn-del" data-id="${c.id}" title="Eliminar"><i class="bi bi-trash"></i></button>
                </td>`;
            tbody.appendChild(tr);
        });
        tbody.querySelectorAll('.sql-cell').forEach(c => c.addEventListener('click', () => {
            const caso = estado.casos[c.dataset.idx];
            Swal.fire({ title: escapeHTML(caso.name), html: `<pre class="sql-bloque text-start">${escapeHTML(caso.sql_query)}</pre>`, width: 800, confirmButtonText: 'Cerrar' });
        }));
        tbody.querySelectorAll('.btn-exec').forEach(b => b.addEventListener('click', () => {
            if (abrirEjecucionFn) abrirEjecucionFn('CASE', b.dataset.id);
        }));
        tbody.querySelectorAll('.btn-edit').forEach(b => b.addEventListener('click', () => formCaso(estado.casos.find(x => x.id == b.dataset.id))));
        tbody.querySelectorAll('.btn-del').forEach(b => b.addEventListener('click', () => eliminarCaso(b.dataset.id)));
    } catch(e) { handleAPIError(e); }
}

export async function eliminarCaso(id) {
    const caso = estado.casos.find(x => x.id == id);
    const res = await Swal.fire({ title: `¿Eliminar el caso «${escapeHTML(caso?.name || '')}»?`, text: 'Si el caso ya tiene ejecuciones en el historial no se puede eliminar: así se conserva la evidencia.',
        icon: 'warning', showCancelButton: true, confirmButtonText: 'Eliminar', cancelButtonText: 'Cancelar', confirmButtonColor: '#ef4444' });
    if (res.isConfirmed) {
        try { await fetchAPI(`/test-cases/${id}`, { method: 'DELETE' }); cargarCasos(); } catch(e) { handleAPIError(e); }
    }
}
