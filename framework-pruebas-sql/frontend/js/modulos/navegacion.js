import { estado } from '../core/estado.js';
import { cargarProyectos } from './proyectos.js';
import { cargarConexiones } from './conexiones.js';
import { cargarCasos } from './casos.js';
import { cargarSuites } from './suites.js';
import { cargarHistorial } from './historial.js';
import { cargarInicio } from './inicio.js';
import { cargarUso } from './uso.js';
import { cargarUsuarios } from './usuarios.js';
import { cargarAnalisis } from './analisis.js';

export function setupSidebarLinks() {
    const linksHtml = `
        <a class="nav-link-custom active" data-section="inicio"><i class="bi bi-rocket-takeoff me-2"></i> Inicio</a>
        <a class="nav-link-custom" data-section="analisis"><i class="bi bi-cpu me-2"></i> Analizar una tabla <span class="nuevo">nuevo</span></a>
        <a class="nav-link-custom" data-section="historial"><i class="bi bi-clock-history me-2"></i> Historial</a>
        <a class="nav-link-custom" data-section="dashboard"><i class="bi bi-speedometer2 me-2"></i> Uso del producto</a>
        <div class="nav-section-label">Módulos avanzados</div>
        <a class="nav-link-custom" data-section="proyectos"><i class="bi bi-folder me-2"></i> Proyectos</a>
        <a class="nav-link-custom" data-section="conexiones"><i class="bi bi-hdd-network me-2"></i> Conexiones Oracle</a>
        <a class="nav-link-custom" data-section="casos"><i class="bi bi-code-square me-2"></i> Casos de Prueba</a>
        <a class="nav-link-custom" data-section="suites"><i class="bi bi-collection me-2"></i> Suites</a>
        <a class="nav-link-custom" data-section="ayuda"><i class="bi bi-question-circle me-2"></i> Ayuda</a>
        <div class="nav-section-label solo-admin">Administración</div>
        <a class="nav-link-custom solo-admin" data-section="usuarios"><i class="bi bi-people me-2"></i> Usuarios y permisos</a>
    `;
    document.querySelectorAll(".sidebar-links-container").forEach(c => {
        const header = c.querySelector('h5');
        c.innerHTML = (header ? header.outerHTML : '') + linksHtml;
    });

    document.querySelectorAll(".nav-link-custom").forEach(link => {
        link.addEventListener("click", (e) => {
            const section = e.target.closest('a').getAttribute("data-section");
            mostrarSeccion(section);
            const offcanvasEl = document.getElementById('offcanvasMenu');
            if (offcanvasEl) {
                const offcanvas = bootstrap.Offcanvas.getInstance(offcanvasEl);
                if (offcanvas) offcanvas.hide();
            }
        });
    });
}

export function mostrarSeccion(section) {
    document.querySelectorAll(".section-container").forEach(el => el.classList.add("hidden"));
    document.querySelectorAll(".nav-link-custom").forEach(el => el.classList.remove("active"));
    document.querySelectorAll(`.nav-link-custom[data-section="${section}"]`).forEach(el => el.classList.add("active"));

    const titleMap = {
        'inicio': 'Inicio', 'dashboard': 'Uso del producto y resultados', 'proyectos': 'Gestión de Proyectos', 'conexiones': 'Conexiones Oracle',
        'casos': 'Casos de Prueba', 'suites': 'Suites de Pruebas', 'historial': 'Historial de Ejecuciones', 'ayuda': 'Guía de Uso',
        'usuarios': 'Usuarios y permisos', 'analisis': 'Analizar una tabla'
    };
    const subtitleMap = {
        'inicio': 'Compruebe consultas SQL y conserve la evidencia', 'dashboard': 'Cuánto y cómo se usa la aplicación, con datos reales',
        'proyectos': 'Agrupan conexiones, casos, suites e historial', 'conexiones': 'Dónde y con qué usuario conectarse (la contraseña nunca se guarda)',
        'casos': 'Comprobaciones guardadas para repetir cuando quiera', 'suites': 'Grupos de casos que se ejecutan juntos con un clic',
        'historial': 'Cada ejecución con lo esperado, lo obtenido y quién la lanzó', 'ayuda': 'Cómo empezar y qué protege la aplicación',
        'usuarios': 'Apruebe solicitudes, asigne roles y proteja las cuentas',
        'analisis': 'Reglas de calidad propuestas a partir de sus datos'
    };
    document.getElementById("titulo-seccion").innerText = titleMap[section] || 'Inicio';
    document.getElementById("subtitulo-seccion").innerText = subtitleMap[section] || '';

    // Las tarjetas antiguas («últimas 100») quedan ocultas: «Uso del producto» ya muestra esas cifras con su periodo, su alcance y su explicación.
    // El elemento se conserva porque dashboard.js todavía lo rellena.
    document.getElementById("kpi-row").classList.add("hidden");

    const requiresProject = ['conexiones', 'casos', 'suites', 'historial', 'analisis'];
    if (requiresProject.includes(section) && !estado.proyectoActivoId) {
        document.getElementById("global-alert").classList.remove("hidden");
        return;
    } else {
        document.getElementById("global-alert").classList.add("hidden");
        const seccion = document.getElementById(`section-${section}`);
        seccion.classList.remove("hidden");
        // Animación de entrada al cambiar de sección (se reinicia en cada cambio).
        seccion.classList.remove("entrar"); void seccion.offsetWidth; seccion.classList.add("entrar");
    }

    if (section === 'inicio') cargarInicio();
    else if (section === 'proyectos') cargarProyectos();
    else if (section === 'conexiones') cargarConexiones();
    else if (section === 'casos') cargarCasos();
    else if (section === 'suites') {
        cargarCasos().then(() => cargarSuites());
    }
    else if (section === 'historial') cargarHistorial();
    else if (section === 'dashboard') cargarUso();
    else if (section === 'usuarios') cargarUsuarios();
    else if (section === 'analisis') cargarAnalisis();
}
