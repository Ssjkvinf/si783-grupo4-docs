export const API_URL = window.location.origin.includes("localhost") || window.location.origin.includes("127.0.0.1") ? "/api" : window.location.origin + "/api";

// Títulos en lenguaje claro según el código HTTP (el detalle viene del servidor).
const TITULOS = {
    0: 'No hay conexión con el servidor',
    400: 'No se pudo hacer',
    403: 'No tiene permiso',
    404: 'No se encontró',
    409: 'No se puede hacer en este momento',
    422: 'Revise los datos',
    423: 'Cuenta bloqueada',
    429: 'Demasiados intentos',
    500: 'Error del servidor',
    503: 'Servicio no disponible'
};
const CAMPOS = {
    name: 'Nombre', description: 'Descripción', sql_query: 'Consulta SQL', expected_result: 'Resultado esperado',
    validation_type: 'Cómo comparar', host: 'Servidor', port: 'Puerto', service_name: 'Servicio', username: 'Usuario',
    password: 'Contraseña', environment_type: 'Ambiente', connection_profile_id: 'Conexión', project_id: 'Proyecto', full_name: 'Nombre completo'
};

export function handleAPIError(e) {
    let msg = "Ocurrió un problema con la petición.";
    if (typeof e.message === 'string') msg = escapeHTML(e.message);
    else if (Array.isArray(e.message)) {
        msg = "<ul class='text-start mb-0'>" + e.message.map(err => {
            const campo = err.loc?.[err.loc.length - 1];
            return `<li><b>${escapeHTML(CAMPOS[campo] || campo || 'Campo')}</b>: ${escapeHTML(String(err.msg || '').replace(/^Value error, /, ''))}</li>`;
        }).join('') + "</ul>";
    } else if (typeof e.message === 'object') {
        msg = escapeHTML(JSON.stringify(e.message));
    }
    const status = e.status ?? 0;
    const titulo = TITULOS[status] || (status >= 500 ? TITULOS[500] : 'Algo salió mal');
    Swal.fire({ title: titulo, html: msg, icon: status === 403 || status === 409 ? "warning" : "error", confirmButtonText: 'Entendido' });
}

export async function fetchAPI(endpoint, options = {}) {
    let res;
    try {
        res = await fetch(API_URL + endpoint, options);
    } catch (err) {
        throw { status: 0, message: 'No se pudo contactar con el servidor. Revise su conexión a internet o si la aplicación está en marcha.' };
    }
    if (!res.ok) {
        if (res.status === 401) {
            window.location.href = '/login';
            return;
        }
        let errorMsg = 'Error en el servidor';
        try { const errorData = await res.json(); errorMsg = errorData.detail || errorMsg; } catch (e) {}
        throw { status: res.status, message: errorMsg };
    }
    if (res.status === 204) return null;
    return await res.json();
}

function escapeHTML(str) {
    if (!str) return '';
    return str.toString().replace(/[&<>'"]/g,
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag]));
}
