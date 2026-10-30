import { estado } from '../core/estado.js';
import { fetchAPI, handleAPIError } from '../core/api.js';
import { escapeHTML, abrirModalGeneral, modalGeneralAction, modalGeneralId, vacio, esTester } from '../core/utilidades.js';

let updateGlobalProjectsFn = null;

export function initProyectos(updateFn) {
    updateGlobalProjectsFn = updateFn;
}

export function formProyecto(p = null) {
    const html = `
        <p class="small text-muted">Un proyecto agrupa las conexiones, casos, suites e historial de un sistema o equipo (por ejemplo, «Facturación»).</p>
        <div class="mb-3"><label class="form-label" for="f-proj-name">Nombre</label><input type="text" id="f-proj-name" class="form-control" required placeholder="Facturación" value="${escapeHTML(p?.name||'')}"></div>
        <div class="mb-3"><label class="form-label" for="f-proj-desc">Descripción <span class="text-muted fw-normal">(opcional)</span></label><textarea id="f-proj-desc" class="form-control">${escapeHTML(p?.description||'')}</textarea></div>
    `;
    abrirModalGeneral(p ? "Editar Proyecto" : "Nuevo Proyecto", html, p ? "PROJ_EDIT" : "PROJ_NEW", p?.id);
}

export async function saveProyecto() {
    const payload = { name: document.getElementById("f-proj-name").value, description: document.getElementById("f-proj-desc").value };
    if (modalGeneralAction === "PROJ_NEW") {
        await fetchAPI("/projects/", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
        Swal.fire({ icon: "success", title: "Proyecto creado", timer: 1600, showConfirmButton: false });
    } else {
        await fetchAPI(`/projects/${modalGeneralId}`, { method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
        Swal.fire({ icon: "success", title: "Proyecto actualizado", timer: 1600, showConfirmButton: false });
    }
    if (updateGlobalProjectsFn) await updateGlobalProjectsFn();
    if (!document.getElementById("section-proyectos").classList.contains("hidden")) cargarProyectos();
}

export function cargarProyectos() {
    const tbody = document.getElementById("tabla-proyectos");
    tbody.innerHTML = "";
    if (estado.proyectos.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4">${vacio('bi-folder-plus', 'Todavía no hay proyectos',
            esTester() ? 'Pida a un administrador que cree un proyecto.' : 'Un proyecto agrupa conexiones, casos, suites e historial. Cree el primero.',
            esTester() ? null : { id: 'proyectos-vacio-nuevo', texto: 'Nuevo proyecto' })}</td></tr>`;
        document.getElementById('proyectos-vacio-nuevo')?.addEventListener('click', () => formProyecto());
        return;
    }
    estado.proyectos.forEach((p, i) => {
        const tr = document.createElement("tr");
        tr.className = 'fila-entrar';
        tr.style.animationDelay = `${Math.min(i, 12) * 25}ms`;
        const activo = p.id === estado.proyectoActivoId ? ' <span class="badge badge-suave-ok ms-1">activo</span>' : '';
        tr.innerHTML = `<td class="text-muted small">${p.id}</td><td><strong>${escapeHTML(p.name)}</strong>${activo}</td><td class="text-muted">${escapeHTML(p.description)}</td>
            <td class="text-end pe-4">
                <button class="btn btn-sm btn-outline-secondary btn-edit solo-admin" data-id="${p.id}"><i class="bi bi-pencil"></i></button>
                <button class="btn btn-sm btn-outline-danger btn-del solo-admin" data-id="${p.id}"><i class="bi bi-trash"></i></button>
            </td>`;
        tbody.appendChild(tr);
    });
    tbody.querySelectorAll('.btn-edit').forEach(b => b.addEventListener('click', () => formProyecto(estado.proyectos.find(x => x.id == b.dataset.id))));
    tbody.querySelectorAll('.btn-del').forEach(b => b.addEventListener('click', () => eliminarProyecto(b.dataset.id)));
}

export async function eliminarProyecto(id) {
    const proyecto = estado.proyectos.find(x => x.id == id);
    const res = await Swal.fire({ title: `¿Eliminar el proyecto «${escapeHTML(proyecto?.name || '')}»?`, text: 'Solo se puede eliminar si no tiene conexiones, casos, suites ni historial.',
        icon: 'warning', showCancelButton: true, confirmButtonText: 'Eliminar', cancelButtonText: 'Cancelar', confirmButtonColor: '#ef4444' });
    if (res.isConfirmed) {
        try {
            await fetchAPI(`/projects/${id}`, { method: 'DELETE' });
            Swal.fire({ icon: "success", title: "Proyecto eliminado", timer: 1600, showConfirmButton: false });
            if (updateGlobalProjectsFn) await updateGlobalProjectsFn();
            cargarProyectos();
        } catch(e) { handleAPIError(e); }
    }
}
