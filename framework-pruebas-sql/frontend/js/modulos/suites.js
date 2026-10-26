import { estado } from '../core/estado.js';
import { fetchAPI, handleAPIError, API_URL } from '../core/api.js';
import { escapeHTML, abrirModalGeneral, modalGeneralAction, modalGeneralId, vacio } from '../core/utilidades.js';

let abrirEjecucionFn = null;

export function initSuites(ejecucionFn) {
    abrirEjecucionFn = ejecucionFn;
}

export function formSuite(s = null) {
    const html = `
        <p class="small text-muted">Una suite agrupa casos que se ejecutan juntos con un clic (por ejemplo, «Reglas de la tabla de clientes»). Después de crearla, añádale casos desde su tarjeta.</p>
        <div class="mb-3"><label class="form-label" for="f-suite-name">Nombre</label><input type="text" id="f-suite-name" class="form-control" required maxlength="100" placeholder="Reglas de calidad de clientes" value="${escapeHTML(s?.name||'')}"></div>
        <div class="mb-3"><label class="form-label" for="f-suite-desc">Descripción</label><textarea id="f-suite-desc" class="form-control" placeholder="Qué comprueba y cuándo conviene ejecutarla">${escapeHTML(s?.description||'')}</textarea></div>
    `;
    abrirModalGeneral(s ? "Editar suite" : "Nueva suite", html, s ? "SUITE_EDIT" : "SUITE_NEW", s?.id);
}

export async function saveSuite() {
    const payload = { project_id: estado.proyectoActivoId, name: document.getElementById("f-suite-name").value, description: document.getElementById("f-suite-desc").value };
    if (modalGeneralAction === "SUITE_NEW") {
        await fetchAPI("/suites/", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
        Swal.fire({ icon: "success", title: "Suite creada", text: "Ahora añádale casos desde su tarjeta.", timer: 2200, showConfirmButton: false });
    } else {
        await fetchAPI(`/suites/${modalGeneralId}`, { method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
        Swal.fire({ icon: "success", title: "Suite actualizada", timer: 1600, showConfirmButton: false });
    }
    cargarSuites();
}

// Últimas corridas de la suite como barras (verde = todos pasaron, ámbar/rojo = hubo fallos) y enlace al reporte de la última.
async function cargarTendencia(suiteId) {
    const caja = document.getElementById(`tendencia-${suiteId}`);
    if (!caja) return;
    try {
        const corridas = await fetchAPI(`/history/runs?suite_id=${suiteId}&limit=8`);
        if (!corridas || corridas.length === 0) { caja.innerHTML = '<span class="small text-muted"><i class="bi bi-hourglass"></i> Aún no se ha ejecutado.</span>'; return; }
        const barras = corridas.slice().reverse().map(c => {
            const clase = c.errors ? 'error' : (c.failed ? 'fail' : 'pass');
            const alto = 30 + Math.round(70 * c.passed / Math.max(c.total, 1));
            return `<span class="tend-barra tend-${clase}" style="height:${alto}%" title="${escapeHTML(new Date(c.fecha + (String(c.fecha).match(/[zZ]|[+-]\d\d:?\d\d$/) ? '' : 'Z')).toLocaleString())}: ${c.passed}/${c.total} PASS"></span>`;
        }).join('');
        const u = corridas[0];
        caja.innerHTML = `<div class="tend-barras" aria-label="Últimas corridas">${barras}</div>
            <div class="small"><b>Última:</b> ${u.passed}/${u.total} PASS${u.failed ? `, ${u.failed} FAIL` : ''}${u.errors ? `, ${u.errors} ERROR` : ''}
            · <a href="${API_URL}/history/runs/${encodeURIComponent(u.run_id)}/report" download>reporte</a></div>`;
    } catch (e) { caja.innerHTML = ''; }
}

export async function cargarSuites() {
    try {
        estado.suites = await fetchAPI(`/suites/?project_id=${estado.proyectoActivoId}`);
        const cont = document.getElementById("contenedor-suites");
        cont.innerHTML = "";
        if (estado.suites.length === 0) {
            cont.innerHTML = `<div class="col-12"><div class="card">${vacio('bi-collection', 'Todavía no hay suites',
                'Una suite junta varios casos para ejecutarlos con un clic. Cree una aquí o cargue las de demostración desde Inicio.',
                { id: 'suites-vacio-nueva', texto: 'Nueva suite' })}</div></div>`;
            document.getElementById('suites-vacio-nueva').addEventListener('click', () => formSuite());
            return;
        }

        estado.suites.forEach((s, i) => {
            const arr = s.test_cases || [];
            const casesHtml = arr.map((c, n) => `<li class="caso-en-suite">
                <span class="num-caso">${n + 1}</span><span class="flex-grow-1 text-truncate" title="${escapeHTML(c.name)}">${escapeHTML(c.name)}</span>
                <button class="btn btn-sm btn-link text-danger p-0 btn-retirar-caso" data-suite="${s.id}" data-case="${c.id}" title="Quitar de la suite"><i class="bi bi-x-circle"></i></button></li>`).join("");

            const col = document.createElement("div"); col.className = "col-md-6 col-xl-4 mb-4";
            col.innerHTML = `
                <div class="card suite-card h-100 fila-entrar" style="animation-delay:${Math.min(i, 8) * 50}ms">
                    <div class="suite-card-cabecera">
                        <div class="suite-icono"><i class="bi bi-collection-play"></i></div>
                        <div class="flex-grow-1 overflow-hidden">
                            <div class="fw-bold text-truncate" title="${escapeHTML(s.name)}">${escapeHTML(s.name)}</div>
                            <div class="small text-muted">${arr.length} ${arr.length === 1 ? 'caso' : 'casos'}</div>
                        </div>
                        <button class="btn btn-sm btn-light btn-edit" data-id="${s.id}" title="Editar"><i class="bi bi-pencil"></i></button>
                        <button class="btn btn-sm btn-light text-danger btn-del" data-id="${s.id}" title="Eliminar"><i class="bi bi-trash"></i></button>
                    </div>
                    <div class="card-body pt-2">
                        ${s.description ? `<p class="small text-muted">${escapeHTML(s.description)}</p>` : ''}
                        <div class="tendencia" id="tendencia-${s.id}"></div>
                        <ul class="lista-casos">${casesHtml || '<li class="small text-muted">Sin casos todavía: añada uno abajo.</li>'}</ul>
                        <div class="d-flex gap-2">
                            <select class="form-select form-select-sm sel-asoc" data-suite="${s.id}" aria-label="Caso para añadir"><option value="">Añadir un caso…</option></select>
                            <button class="btn btn-sm btn-outline-primary btn-asoc" data-suite="${s.id}"><i class="bi bi-plus-lg"></i></button>
                        </div>
                    </div>
                    <div class="card-footer d-flex justify-content-end"><button class="btn btn-primary btn-sm btn-brillo btn-exec" data-id="${s.id}" ${arr.length ? '' : 'disabled'}><i class="bi bi-play-fill"></i> Ejecutar suite</button></div>
                </div>`;
            cont.appendChild(col);

            const sel = col.querySelector('.sel-asoc');
            estado.casos.forEach(c => {
                if (!arr.some(xc => xc.id === c.id)) {
                    const opt = document.createElement("option"); opt.value = c.id; opt.textContent = c.name; sel.appendChild(opt);
                }
            });
        });

        estado.suites.forEach(s => cargarTendencia(s.id));

        cont.querySelectorAll('.btn-retirar-caso').forEach(b => b.addEventListener('click', async (e) => {
            const btn = e.target.closest('button');
            try { await fetchAPI(`/suites/${btn.dataset.suite}/test-cases/${btn.dataset.case}`, { method: 'DELETE' }); cargarSuites(); } catch(err) { handleAPIError(err); }
        }));
        cont.querySelectorAll('.btn-asoc').forEach(b => b.addEventListener('click', async (e) => {
            const suiteId = e.target.closest('button').dataset.suite;
            const caseId = cont.querySelector(`.sel-asoc[data-suite="${suiteId}"]`).value;
            if (!caseId) return;
            try { await fetchAPI(`/suites/${suiteId}/test-cases/${caseId}`, { method: 'POST' }); cargarSuites(); } catch(err) { handleAPIError(err); }
        }));
        cont.querySelectorAll('.btn-edit').forEach(b => b.addEventListener('click', () => formSuite(estado.suites.find(x => x.id == b.dataset.id))));
        cont.querySelectorAll('.btn-del').forEach(b => b.addEventListener('click', async (e) => {
            const id = e.target.closest('button').dataset.id;
            const suite = estado.suites.find(x => x.id == id);
            const res = await Swal.fire({ title: `¿Eliminar la suite «${escapeHTML(suite?.name || '')}»?`, text: 'Los casos no se borran. Si la suite ya se ejecutó, no se puede eliminar para conservar la evidencia del historial.',
                icon: 'warning', showCancelButton: true, confirmButtonText: 'Eliminar', cancelButtonText: 'Cancelar', confirmButtonColor: '#ef4444' });
            if (res.isConfirmed) { try { await fetchAPI(`/suites/${id}`, { method: 'DELETE' }); cargarSuites(); } catch(err) { handleAPIError(err); } }
        }));
        cont.querySelectorAll('.btn-exec').forEach(b => b.addEventListener('click', () => {
            if (abrirEjecucionFn) abrirEjecucionFn('SUITE', b.dataset.id);
        }));
    } catch(e) { handleAPIError(e); }
}
