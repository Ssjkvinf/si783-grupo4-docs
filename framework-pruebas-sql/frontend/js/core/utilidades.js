export function escapeHTML(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Estado vacío con guía: qué es esta pantalla y cuál es el siguiente paso (botón opcional, con id para engancharlo).
export function vacio(icono, titulo, texto, boton = null) {
    const btn = boton ? `<button type="button" class="btn btn-primary btn-sm mt-2 ${boton.clase || ''}" id="${boton.id}"><i class="bi ${boton.icono || 'bi-plus-lg'} me-1"></i>${escapeHTML(boton.texto)}</button>` : '';
    return `<div class="vacio"><i class="bi ${icono}"></i><b>${escapeHTML(titulo)}</b><span>${escapeHTML(texto)}</span>${btn}</div>`;
}

export function esTester() {
    return document.body.classList.contains('rol-tester');
}

export let modalGeneralAction = null;
export let modalGeneralId = null;
let modalGeneralInst = null;

export function getModalGeneralInst() {
    if (!modalGeneralInst) {
        modalGeneralInst = new bootstrap.Modal(document.getElementById("modalGeneral"));
    }
    return modalGeneralInst;
}

export function abrirModalGeneral(title, html, actionType, id = null) {
    document.getElementById("modalGeneralTitle").innerText = title;
    document.getElementById("modalGeneralBody").innerHTML = html;
    modalGeneralAction = actionType;
    modalGeneralId = id;
    document.getElementById("modalGeneralSubmit").disabled = false;
    getModalGeneralInst().show();
}

export function hideModalGeneral() {
    getModalGeneralInst().hide();
}
