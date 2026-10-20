import { estado } from '../core/estado.js';
import { fetchAPI, handleAPIError } from '../core/api.js';
import { escapeHTML, abrirModalGeneral, modalGeneralAction, modalGeneralId } from '../core/utilidades.js';

let abrirEjecucionFn = null;

export function initCasos(ejecucionFn) {
    abrirEjecucionFn = ejecucionFn;
}

// `prefill` (opcional) rellena un caso NUEVO desde la prueba rápida:
// { name, description, sql_query, validation_type, expected_result, confirmar: 'texto del aviso', advertencia: 'texto' }.
// El valor esperado es siempre el que el usuario indicó antes de ejecutar; nunca el resultado obtenido.
export function formCaso(c = null, prefill = null) {
    const d = c || prefill || {};
    const confirmHtml = prefill?.confirmar ? `
        ${prefill.advertencia ? `<div class="alert alert-warning small">${escapeHTML(prefill.advertencia)}</div>` : ''}
        <div class="form-check mb-2">
            <input class="form-check-input" type="checkbox" id="f-caso-confirm">
            <label class="form-check-label" for="f-caso-confirm">${escapeHTML(prefill.confirmar)}</label>
        </div>` : '';
    const html = `
        <div class="mb-3"><label class="form-label">Nombre</label><input type="text" id="f-caso-name" class="form-control" required value="${escapeHTML(d.name||'')}"></div>
        <div class="mb-3"><label class="form-label">Descripción</label><textarea id="f-caso-desc" class="form-control">${escapeHTML(d.description||'')}</textarea></div>
        <div class="mb-3"><label class="form-label">Sentencia SQL</label><textarea class="form-control font-monospace text-primary" id="f-caso-sql" rows="3" required>${escapeHTML(d.sql_query||'')}</textarea></div>
        <div class="row">
            <div class="col-md-6 mb-3"><label class="form-label">Tipo Validación</label>
                <select class="form-select" id="f-caso-val" required>
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
        inputExp.placeholder = selectVal.value === 'EXISTS' ? 'true o false' : (selectVal.value === 'SCALAR_VALUE' ? 'Valor esperado, ej: 0' : 'Número de filas, ej: 1');
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
    const confirmBox = document.getElementById("f-caso-confirm");
    if (confirmBox && !confirmBox.checked) throw {status: 422, message: "Confirme que el resultado esperado es el correcto antes de guardar el caso."};

    const payload = { project_id: estado.proyectoActivoId, name: document.getElementById("f-caso-name").value, description: document.getElementById("f-caso-desc").value, sql_query: document.getElementById("f-caso-sql").value, validation_type: v, expected_result: exp };
    
    if (modalGeneralAction === "CASE_NEW") {
        await fetchAPI("/test-cases/", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
        Swal.fire("Éxito", "Caso creado.", "success");
    } else {
        await fetchAPI(`/test-cases/${modalGeneralId}`, { method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
        Swal.fire("Éxito", "Caso actualizado.", "success");
    }
    cargarCasos();
}

export async function cargarCasos() {
    try {
        estado.casos = await fetchAPI(`/test-cases/?project_id=${estado.proyectoActivoId}`);
        const tbody = document.getElementById("tabla-casos");
        tbody.innerHTML = "";
        estado.casos.forEach(c => {
            const tr = document.createElement("tr");
            tr.innerHTML = `<td>${c.id}</td><td><strong>${escapeHTML(c.name)}</strong></td>
                <td class="text-truncate-custom font-monospace text-primary small sql-cell" data-sql="${escapeHTML(c.sql_query)}">${escapeHTML(c.sql_query)}</td>
                <td><span class="badge bg-secondary">${c.validation_type}</span></td><td>${escapeHTML(c.expected_result)}</td>
                <td class="text-end pe-4">
                    <button class="btn btn-sm btn-outline-success btn-exec" data-id="${c.id}"><i class="bi bi-play-fill"></i></button>
                    <button class="btn btn-sm btn-outline-secondary btn-edit" data-id="${c.id}"><i class="bi bi-pencil"></i></button>
                    <button class="btn btn-sm btn-outline-danger btn-del" data-id="${c.id}"><i class="bi bi-trash"></i></button>
                </td>`;
            tbody.appendChild(tr);
        });
        tbody.querySelectorAll('.sql-cell').forEach(c => c.addEventListener('click', (e) => {
            Swal.fire({title: "SQL Completo", html: `<pre class="text-start bg-light p-3 border rounded"><code>${e.target.getAttribute('data-sql')}</code></pre>`, width: '800px'});
        }));
        tbody.querySelectorAll('.btn-exec').forEach(b => b.addEventListener('click', () => {
            if (abrirEjecucionFn) abrirEjecucionFn('CASE', b.dataset.id);
        }));
        tbody.querySelectorAll('.btn-edit').forEach(b => b.addEventListener('click', () => formCaso(estado.casos.find(x => x.id == b.dataset.id))));
        tbody.querySelectorAll('.btn-del').forEach(b => b.addEventListener('click', () => eliminarCaso(b.dataset.id)));
    } catch(e) { handleAPIError(e); }
}

export async function eliminarCaso(id) {
    const res = await Swal.fire({ title: '¿Eliminar caso?', icon: 'warning', showCancelButton: true, confirmButtonText: 'Eliminar' });
    if (res.isConfirmed) {
        try { await fetchAPI(`/test-cases/${id}`, { method: 'DELETE' }); cargarCasos(); } catch(e) { handleAPIError(e); }
    }
}
