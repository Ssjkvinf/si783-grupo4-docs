import { estado } from '../core/estado.js';
import { fetchAPI, handleAPIError } from '../core/api.js';
import { escapeHTML, abrirModalGeneral, modalGeneralAction, modalGeneralId, vacio, esTester, hideModalGeneral } from '../core/utilidades.js';

let abrirTestConexionFn = null;

export function initConexiones(testConexionFn) {
    abrirTestConexionFn = testConexionFn;
}

const AMBIENTES = {
    TEST: { clase: 'amb-test', icono: 'bi-tools', titulo: 'TEST', texto: 'Base de pruebas. Se permiten SELECT y cambios (INSERT, UPDATE, DELETE) que siempre se revierten.' },
    STAGING: { clase: 'amb-staging', icono: 'bi-exclamation-diamond', titulo: 'STAGING', texto: 'Preproducción. Igual que TEST, pero pide confirmación antes de ejecutar cambios.' },
    PRODUCTION: { clase: 'amb-prod', icono: 'bi-shield-lock', titulo: 'PRODUCTION', texto: 'Solo SELECT y sin mostrar filas. Use un usuario Oracle de solo lectura.' }
};

export function formConexion(c = null) {
    const amb = c?.environment_type || 'TEST';
    const opciones = Object.entries(AMBIENTES).map(([valor, a]) => `
        <label class="ambiente-opcion ${a.clase}">
            <input type="radio" name="f-conn-env" value="${valor}" ${amb === valor ? 'checked' : ''}>
            <span class="ambiente-caja"><i class="bi ${a.icono}"></i><b>${a.titulo}</b><small>${a.texto}</small></span>
        </label>`).join('');
    const html = `
        <p class="small text-muted mb-3">Una conexión dice <b>dónde</b> está la base Oracle y <b>con qué usuario</b> entrar. La contraseña nunca se guarda: se pide cada vez que se ejecuta.</p>
        <div class="row g-3">
            <div class="col-12"><label class="form-label" for="f-conn-name">Nombre para reconocerla</label>
                <input type="text" id="f-conn-name" class="form-control" required maxlength="100" placeholder="Oracle de pruebas del equipo" value="${escapeHTML(c?.name||'')}"></div>
            <div class="col-md-8"><label class="form-label" for="f-conn-host">Servidor (host)</label>
                <input type="text" id="f-conn-host" class="form-control" required placeholder="oracle_db o 10.0.0.5" value="${escapeHTML(c?.host||'')}">
                <div class="form-text">Nombre o IP del servidor. Solo letras, números, punto, guion y guion bajo.</div></div>
            <div class="col-md-4"><label class="form-label" for="f-conn-port">Puerto</label>
                <input type="number" id="f-conn-port" class="form-control" required min="1" max="65535" value="${c?.port||1521}">
                <div class="form-text">Oracle usa 1521 por defecto.</div></div>
            <div class="col-md-6"><label class="form-label" for="f-conn-service">Servicio (service name)</label>
                <input type="text" id="f-conn-service" class="form-control" required placeholder="FREEPDB1" value="${escapeHTML(c?.service_name||'')}">
                <div class="form-text">La base dentro del servidor; en Oracle Free suele ser FREEPDB1.</div></div>
            <div class="col-md-6"><label class="form-label" for="f-conn-user">Usuario Oracle</label>
                <input type="text" id="f-conn-user" class="form-control" required placeholder="FRAMEWORK_TEST" value="${escapeHTML(c?.username||'')}"></div>
            <div class="col-12"><label class="form-label">Ambiente</label><div class="ambientes">${opciones}</div></div>
            <div class="col-12"><div class="probar-caja">
                <label class="form-label mb-1" for="f-conn-pwd"><i class="bi bi-plug me-1"></i>Probar al guardar <span class="text-muted fw-normal">(opcional)</span></label>
                <input type="password" id="f-conn-pwd" class="form-control" autocomplete="off" placeholder="Contraseña del usuario Oracle">
                <div class="form-text">Si la escribe, después de guardar se comprueba la conexión. No se guarda.</div>
            </div></div>
        </div>`;
    abrirModalGeneral(c ? "Editar conexión" : "Nueva conexión Oracle", html, c ? "CONN_EDIT" : "CONN_NEW", c?.id);
}

export async function saveConexion() {
    const payload = {
        project_id: estado.proyectoActivoId,
        name: document.getElementById("f-conn-name").value.trim(),
        engine: "oracle",
        host: document.getElementById("f-conn-host").value.trim(),
        port: parseInt(document.getElementById("f-conn-port").value),
        service_name: document.getElementById("f-conn-service").value.trim(),
        username: document.getElementById("f-conn-user").value.trim(),
        environment_type: document.querySelector('input[name="f-conn-env"]:checked').value
    };
    const pwd = document.getElementById("f-conn-pwd").value;
    let perfil;
    if (modalGeneralAction === "CONN_NEW") {
        perfil = await fetchAPI("/connections/", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
    } else {
        perfil = await fetchAPI(`/connections/${modalGeneralId}`, { method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
    }
    document.getElementById("f-conn-pwd").value = "";
    hideModalGeneral();
    await cargarConexiones();
    if (pwd && perfil) {
        Swal.fire({ title: 'Probando la conexión…', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
        try {
            await fetchAPI(`/connections/${perfil.id}/test`, { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({ password: pwd }) });
            Swal.fire({ icon: "success", title: "Guardada y probada", text: "La aplicación se conectó a Oracle correctamente." });
        } catch (e) {
            Swal.fire({ icon: "warning", title: "Guardada, pero no se pudo conectar",
                text: (typeof e.message === 'string' ? e.message : 'Revise servidor, puerto, servicio, usuario y contraseña.') });
        }
    } else {
        Swal.fire({ icon: "success", title: modalGeneralAction === "CONN_NEW" ? "Conexión creada" : "Conexión actualizada", timer: 1600, showConfirmButton: false });
    }
}

export async function cargarConexiones() {
    try {
        estado.conexiones = await fetchAPI(`/connections/?project_id=${estado.proyectoActivoId}`);
        const tbody = document.getElementById("tabla-conexiones");
        tbody.innerHTML = "";
        if (estado.conexiones.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6">${vacio('bi-hdd-network', 'Este proyecto aún no tiene conexiones Oracle',
                esTester() ? 'Pida a un administrador que registre la conexión a la base de pruebas.' : 'Registre dónde está la base Oracle y con qué usuario entrar. La contraseña no se guarda.',
                esTester() ? null : { id: 'conexiones-vacio-nueva', texto: 'Nueva conexión' })}</td></tr>`;
            document.getElementById('conexiones-vacio-nueva')?.addEventListener('click', () => formConexion());
            return;
        }
        estado.conexiones.forEach((c, i) => {
            const a = AMBIENTES[c.environment_type] || AMBIENTES.TEST;
            const tr = document.createElement("tr");
            tr.className = 'fila-entrar';
            tr.style.animationDelay = `${Math.min(i, 12) * 25}ms`;
            tr.innerHTML = `<td class="text-muted small">${c.id}</td>
                <td><strong>${escapeHTML(c.name)}</strong> <span class="badge amb-badge ${a.clase} ms-1" title="${escapeHTML(a.texto)}"><i class="bi ${a.icono}"></i> ${c.environment_type}</span></td>
                <td><code>${escapeHTML(c.host)}:${c.port}</code></td>
                <td>${escapeHTML(c.service_name)}</td><td>${escapeHTML(c.username)}</td>
                <td class="text-end pe-4 text-nowrap">
                    <button class="btn btn-sm btn-outline-primary btn-test" data-id="${c.id}" title="Probar la conexión"><i class="bi bi-plug"></i> Probar</button>
                    <button class="btn btn-sm btn-outline-secondary btn-edit solo-admin" data-id="${c.id}" title="Editar"><i class="bi bi-pencil"></i></button>
                    <button class="btn btn-sm btn-outline-danger btn-del solo-admin" data-id="${c.id}" title="Eliminar"><i class="bi bi-trash"></i></button>
                </td>`;
            tbody.appendChild(tr);
        });
        tbody.querySelectorAll('.btn-test').forEach(b => b.addEventListener('click', () => {
            if (abrirTestConexionFn) abrirTestConexionFn(b.dataset.id);
        }));
        tbody.querySelectorAll('.btn-edit').forEach(b => b.addEventListener('click', () => formConexion(estado.conexiones.find(x => x.id == b.dataset.id))));
        tbody.querySelectorAll('.btn-del').forEach(b => b.addEventListener('click', () => eliminarConexion(b.dataset.id)));
    } catch(e) { handleAPIError(e); }
}

export async function eliminarConexion(id) {
    const conn = estado.conexiones.find(x => x.id == id);
    const res = await Swal.fire({ title: `¿Eliminar la conexión «${escapeHTML(conn?.name || '')}»?`, text: 'Si ya se usó en ejecuciones guardadas, no se podrá eliminar para conservar la evidencia.',
        icon: 'warning', showCancelButton: true, confirmButtonText: 'Eliminar', cancelButtonText: 'Cancelar', confirmButtonColor: '#ef4444' });
    if (res.isConfirmed) {
        try { await fetchAPI(`/connections/${id}`, { method: 'DELETE' }); cargarConexiones(); } catch(e) { handleAPIError(e); }
    }
}
