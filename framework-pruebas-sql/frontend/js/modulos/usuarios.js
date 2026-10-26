import { estado } from '../core/estado.js';
import { fetchAPI, handleAPIError } from '../core/api.js';
import { escapeHTML } from '../core/utilidades.js';

// Sesión, rol y administración de usuarios.
// La interfaz oculta lo que un TESTER no puede hacer (clase .solo-admin), pero quien decide es el servidor (403).

const ROLES = { ADMIN: 'Administrador', TESTER: 'Tester' };
const JSON_HEADERS = { 'Content-Type': 'application/json' };

function iniciales(texto) {
    return (texto || '?').split(/[\s._-]+/).filter(Boolean).slice(0, 2).map(p => p[0].toUpperCase()).join('') || '?';
}

export async function cargarSesion() {
    try {
        estado.usuario = await fetchAPI('/me');
    } catch (e) {
        estado.usuario = { acceso_activado: false, username: null, full_name: 'Modo local', role: 'ADMIN' };
    }
    const u = estado.usuario || {};
    const esAdmin = u.role === 'ADMIN';
    document.body.classList.toggle('rol-tester', !esAdmin);
    document.body.classList.toggle('rol-admin', esAdmin);
    document.body.classList.toggle('sin-acceso', !u.acceso_activado);

    const nombre = u.acceso_activado ? (u.full_name || u.username) : 'Modo local';
    document.getElementById('usuario-avatar').textContent = u.acceso_activado ? iniciales(u.full_name || u.username) : 'L';
    document.getElementById('usuario-nombre').textContent = nombre;
    document.getElementById('usuario-rol').textContent = u.acceso_activado ? ROLES[u.role] || u.role : 'sin control de acceso';
    document.getElementById('usuario-rol').className = 'usuario-rol ' + (esAdmin ? 'rol-badge-admin' : 'rol-badge-tester');

    if (u.acceso_activado && sessionStorage.getItem('sugerir_cambio_clave') === '1') {
        sessionStorage.removeItem('sugerir_cambio_clave');
        const r = await Swal.fire({
            icon: 'info', title: 'Cambie su contraseña inicial',
            html: 'Ingresó con la contraseña configurada en el servidor y no cumple la política (10 caracteres, letras y números). Cámbiela ahora para proteger la cuenta.',
            showCancelButton: true, confirmButtonText: 'Cambiar ahora', cancelButtonText: 'Más tarde'
        });
        if (r.isConfirmed) cambiarMiContrasena();
    }
    return estado.usuario;
}

export async function cambiarMiContrasena() {
    const r = await Swal.fire({
        title: 'Cambiar mi contraseña',
        html: `<div class="text-start">
            <label class="form-label small fw-semibold" for="sw-actual">Contraseña actual</label>
            <input type="password" id="sw-actual" class="form-control mb-2" autocomplete="current-password">
            <label class="form-label small fw-semibold" for="sw-nueva">Nueva contraseña</label>
            <input type="password" id="sw-nueva" class="form-control mb-2" autocomplete="new-password">
            <label class="form-label small fw-semibold" for="sw-nueva2">Repítala</label>
            <input type="password" id="sw-nueva2" class="form-control" autocomplete="new-password">
            <div class="small text-muted mt-2">Al menos 10 caracteres, con letras y números, sin incluir su usuario. Se cerrarán sus otras sesiones.</div>
        </div>`,
        showCancelButton: true, confirmButtonText: 'Guardar', cancelButtonText: 'Cancelar', focusConfirm: false,
        preConfirm: () => {
            const actual = document.getElementById('sw-actual').value;
            const nueva = document.getElementById('sw-nueva').value;
            if (!actual || !nueva) { Swal.showValidationMessage('Complete los campos.'); return false; }
            if (nueva !== document.getElementById('sw-nueva2').value) { Swal.showValidationMessage('Las contraseñas nuevas no coinciden.'); return false; }
            return { actual, nueva };
        }
    });
    if (!r.isConfirmed) return;
    try {
        await fetchAPI('/me/password', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(r.value) });
        Swal.fire({ icon: 'success', title: 'Contraseña actualizada', timer: 1800, showConfirmButton: false });
    } catch (e) { handleAPIError(e); }
}

// ------------------------------------------------------------------------------------ sección Usuarios (ADMIN)
export async function cargarUsuarios() {
    const tbody = document.getElementById('tabla-usuarios');
    const pendientes = document.getElementById('usuarios-pendientes');
    try {
        const usuarios = await fetchAPI('/users');
        const porAprobar = usuarios.filter(u => !u.active && !u.last_login_at);
        const yo = estado.usuario?.username;

        pendientes.innerHTML = porAprobar.length === 0
            ? '<div class="vacio-suave"><i class="bi bi-inbox"></i> No hay solicitudes pendientes.</div>'
            : porAprobar.map(u => `
                <div class="solicitud entrar">
                    <div class="avatar-mini">${escapeHTML(iniciales(u.full_name || u.username))}</div>
                    <div class="flex-grow-1"><b>${escapeHTML(u.full_name || u.username)}</b>
                        <div class="small text-muted">@${escapeHTML(u.username)} · solicitó el ${new Date(u.created_at).toLocaleString()}</div></div>
                    <button class="btn btn-sm btn-success btn-aprobar" data-id="${u.id}"><i class="bi bi-check-lg"></i> Aprobar</button>
                    <button class="btn btn-sm btn-outline-danger btn-rechazar" data-id="${u.id}"><i class="bi bi-x-lg"></i> Rechazar</button>
                </div>`).join('');
        document.getElementById('usuarios-contador').textContent = porAprobar.length;
        document.getElementById('usuarios-contador').classList.toggle('hidden', porAprobar.length === 0);

        tbody.innerHTML = usuarios.map(u => {
            const estadoTxt = u.bloqueado ? '<span class="badge badge-suave-warn"><i class="bi bi-lock"></i> Bloqueado</span>'
                : (u.active ? '<span class="badge badge-suave-ok">Activo</span>' : '<span class="badge badge-suave-gris">Inactivo</span>');
            const esYo = u.username === yo;
            return `<tr>
                <td><div class="d-flex align-items-center gap-2"><div class="avatar-mini">${escapeHTML(iniciales(u.full_name || u.username))}</div>
                    <div><b>${escapeHTML(u.full_name || u.username)}</b>${esYo ? ' <span class="badge bg-light text-dark">usted</span>' : ''}
                    <div class="small text-muted">@${escapeHTML(u.username)}</div></div></div></td>
                <td><select class="form-select form-select-sm sel-rol" data-id="${u.id}" ${esYo ? 'disabled' : ''}>
                    <option value="TESTER" ${u.role === 'TESTER' ? 'selected' : ''}>Tester</option>
                    <option value="ADMIN" ${u.role === 'ADMIN' ? 'selected' : ''}>Administrador</option></select></td>
                <td>${estadoTxt}</td>
                <td class="small text-muted">${u.last_login_at ? new Date(u.last_login_at).toLocaleString() : 'nunca'}</td>
                <td class="text-end pe-3 text-nowrap">
                    ${esYo ? '' : `<button class="btn btn-sm ${u.active ? 'btn-outline-warning' : 'btn-outline-success'} btn-activar" data-id="${u.id}" data-activo="${u.active}" title="${u.active ? 'Desactivar' : 'Activar'}"><i class="bi ${u.active ? 'bi-pause-circle' : 'bi-play-circle'}"></i></button>`}
                    <button class="btn btn-sm btn-outline-secondary btn-clave" data-id="${u.id}" data-user="${escapeHTML(u.username)}" title="Asignar contraseña nueva"><i class="bi bi-key"></i></button>
                    ${esYo ? '' : `<button class="btn btn-sm btn-outline-danger btn-borrar" data-id="${u.id}" data-user="${escapeHTML(u.username)}" title="Eliminar"><i class="bi bi-trash"></i></button>`}
                </td></tr>`;
        }).join('');

        const actualizar = async (id, datos, ok) => {
            try { await fetchAPI(`/users/${id}`, { method: 'PATCH', headers: JSON_HEADERS, body: JSON.stringify(datos) }); toast(ok); }
            catch (e) { handleAPIError(e); }
            cargarUsuarios();
        };
        pendientes.querySelectorAll('.btn-aprobar').forEach(b => b.addEventListener('click', () => actualizar(b.dataset.id, { active: true }, 'Cuenta aprobada')));
        pendientes.querySelectorAll('.btn-rechazar').forEach(b => b.addEventListener('click', () => eliminar(b.dataset.id, 'la solicitud')));
        tbody.querySelectorAll('.sel-rol').forEach(s => s.addEventListener('change', () => actualizar(s.dataset.id, { role: s.value }, 'Rol actualizado')));
        tbody.querySelectorAll('.btn-activar').forEach(b => b.addEventListener('click', () =>
            actualizar(b.dataset.id, { active: b.dataset.activo !== 'true' }, b.dataset.activo === 'true' ? 'Cuenta desactivada' : 'Cuenta activada')));
        tbody.querySelectorAll('.btn-clave').forEach(b => b.addEventListener('click', () => restablecer(b.dataset.id, b.dataset.user)));
        tbody.querySelectorAll('.btn-borrar').forEach(b => b.addEventListener('click', () => eliminar(b.dataset.id, '@' + b.dataset.user)));
    } catch (e) {
        if (e && e.status === 403) {
            pendientes.innerHTML = '';
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Solo un administrador puede ver esta sección.</td></tr>';
        } else handleAPIError(e);
    }
}

function toast(texto) {
    Swal.fire({ toast: true, position: 'top-end', icon: 'success', title: texto, timer: 1800, showConfirmButton: false });
}

async function eliminar(id, quien) {
    const r = await Swal.fire({ icon: 'warning', title: `¿Eliminar ${quien}?`, text: 'El historial conserva el nombre de usuario en las ejecuciones que hizo.',
        showCancelButton: true, confirmButtonText: 'Eliminar', cancelButtonText: 'Cancelar', confirmButtonColor: '#ef4444' });
    if (!r.isConfirmed) return;
    try { await fetchAPI(`/users/${id}`, { method: 'DELETE' }); toast('Eliminado'); } catch (e) { handleAPIError(e); }
    cargarUsuarios();
}

async function restablecer(id, username) {
    const r = await Swal.fire({
        title: `Contraseña nueva para @${escapeHTML(username)}`, input: 'password', inputLabel: 'Al menos 10 caracteres, con letras y números',
        inputAttributes: { autocomplete: 'new-password' }, showCancelButton: true, confirmButtonText: 'Asignar', cancelButtonText: 'Cancelar',
        inputValidator: v => (!v ? 'Escriba la contraseña.' : undefined)
    });
    if (!r.isConfirmed) return;
    try {
        await fetchAPI(`/users/${id}/reset-password`, { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ nueva: r.value }) });
        toast('Contraseña asignada; se cerraron sus sesiones');
    } catch (e) { handleAPIError(e); }
    cargarUsuarios();
}

export async function nuevoUsuario() {
    const r = await Swal.fire({
        title: 'Nuevo usuario',
        html: `<div class="text-start">
            <label class="form-label small fw-semibold" for="sw-nombre">Nombre completo</label>
            <input id="sw-nombre" class="form-control mb-2" maxlength="120">
            <label class="form-label small fw-semibold" for="sw-usuario">Usuario</label>
            <input id="sw-usuario" class="form-control mb-2" maxlength="50" placeholder="ana.perez">
            <label class="form-label small fw-semibold" for="sw-clave">Contraseña inicial</label>
            <input id="sw-clave" type="password" class="form-control mb-2" autocomplete="new-password">
            <label class="form-label small fw-semibold" for="sw-rol">Rol</label>
            <select id="sw-rol" class="form-select"><option value="TESTER">Tester: crea y ejecuta casos y suites</option>
                <option value="ADMIN">Administrador: además gestiona usuarios, proyectos y conexiones</option></select>
        </div>`,
        showCancelButton: true, confirmButtonText: 'Crear', cancelButtonText: 'Cancelar', focusConfirm: false,
        preConfirm: () => ({
            full_name: document.getElementById('sw-nombre').value.trim(),
            username: document.getElementById('sw-usuario').value.trim(),
            password: document.getElementById('sw-clave').value,
            role: document.getElementById('sw-rol').value
        })
    });
    if (!r.isConfirmed) return;
    try {
        await fetchAPI('/users', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(r.value) });
        toast('Usuario creado');
    } catch (e) { handleAPIError(e); }
    cargarUsuarios();
}
