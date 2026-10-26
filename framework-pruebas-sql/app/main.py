import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env antes de cualquier otra importación
load_dotenv()

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.database import engine, Base, SessionLocal
from app.models import project, connection, test_case, suite, history, usage, user
from app.api import projects, connections, test_cases, suites, executions, demo, usage as api_usage, excel as api_excel, history as api_history, rules as api_rules, users as api_users, analysis as api_analysis
from app.security.acceso import usuario_actual
from app.security.auth import leer_token
# La creación del esquema y el Proyecto general se delega a las migraciones de Alembic (alembic upgrade head).

app = FastAPI(
    title="Framework de Pruebas SQL",
    description="API para ejecución, validación y trazabilidad de pruebas en bases de datos relacionales (Oracle MVP).",
    version="2.0.0"
)

# Configuración CORS centralizada mediante variable de entorno
cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost,http://localhost:3000,http://127.0.0.1,http://127.0.0.1:3000")
origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]

# Si permitimos "*", las credenciales deben desactivarse por seguridad y compatibilidad
allow_creds = "*" not in origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

RUTAS_PUBLICAS = {"/", "/health", "/login", "/api/login", "/api/logout", "/api/register"}

CABECERAS_SEGURIDAD = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


@app.middleware("http")
async def cookie_auth_middleware(request: Request, call_next):
    """
    Primera barrera: sin una cookie de sesión firmada y vigente, /api/* responde 401 y las páginas redirigen a /login.
    La segunda barrera (cuenta activa, sesión no anulada y rol) la aplica la dependencia `usuario_actual` en cada router.
    """
    response = await _controlar_acceso(request, call_next)
    for clave, valor in CABECERAS_SEGURIDAD.items():
        response.headers.setdefault(clave, valor)
    # La interfaz se revalida en cada carga (ETag/Last-Modified): tras un despliegue nadie se queda con JavaScript viejo.
    if request.url.path.startswith("/ui") or request.url.path == "/login":
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


async def _controlar_acceso(request: Request, call_next):
    # Solo aplicar protección si está habilitada en entorno
    if not os.getenv("APP_ACCESS_ENABLED", "").lower() == "true":
        return await call_next(request)

    # El primer administrador se crea con estas variables: sin ellas (o sin secreto de sesión) el servicio no atiende.
    expected_username = os.getenv("APP_ACCESS_USERNAME", "").strip()
    expected_password = os.getenv("APP_ACCESS_PASSWORD", "").strip()
    session_secret = os.getenv("APP_SESSION_SECRET", "").strip()
    if not expected_username or not expected_password or not session_secret:
        return JSONResponse(status_code=503, content={"detail": "Service Unavailable: Incomplete configuration"})

    path = request.url.path

    # Rutas públicas
    if path in RUTAS_PUBLICAS:
        return await call_next(request)

    # Rutas de frontend de assets (css, js, imágenes) permitidas sin auth para cargar el login
    if path.startswith("/ui/css/") or path.startswith("/ui/js/"):
        return await call_next(request)

    if not leer_token(request.cookies.get("session_token")):
        if path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        else:
            return RedirectResponse(url="/login", status_code=303)

    return await call_next(request)


@app.get("/login", include_in_schema=False)
def get_login_page():
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
    login_html = os.path.join(frontend_path, "login.html")
    if os.path.exists(login_html):
        return FileResponse(login_html)
    return JSONResponse(status_code=404, content={"detail": "login.html not found"})

@app.get("/health", tags=["Salud"])
def health_check():
    return {"status": "ok", "message": "El motor del Framework SQL está en línea.", "version": "2.0.0"}

# Registro de routers de la API v2.
# Todas las rutas exigen un usuario con sesión válida; proyectos y conexiones se modifican solo con rol ADMIN
# (lo controla cada ruta de escritura con `requiere_admin`).
con_sesion = [Depends(usuario_actual)]
app.include_router(api_users.router, prefix="/api", tags=["Usuarios y acceso"])
app.include_router(projects.router, prefix="/api", tags=["Proyectos"], dependencies=con_sesion)
app.include_router(connections.router, prefix="/api", tags=["Perfiles de Conexión"], dependencies=con_sesion)
app.include_router(test_cases.router, prefix="/api", tags=["Casos de Prueba"], dependencies=con_sesion)
app.include_router(suites.router, prefix="/api", tags=["Suites de Pruebas"], dependencies=con_sesion)
app.include_router(executions.router, prefix="/api", tags=["Motor de Ejecución"], dependencies=con_sesion)
app.include_router(api_history.router, prefix="/api", tags=["Historial de Ejecuciones"], dependencies=con_sesion)
app.include_router(demo.router, prefix="/api", tags=["Escenario de demostración"], dependencies=con_sesion)
app.include_router(api_usage.router, prefix="/api", tags=["Uso del producto"], dependencies=con_sesion)
app.include_router(api_excel.router, prefix="/api", tags=["Excel"], dependencies=con_sesion)
app.include_router(api_rules.router, prefix="/api", tags=["Asistente de reglas"], dependencies=con_sesion)
app.include_router(api_analysis.router, prefix="/api", tags=["Analizar una tabla"], dependencies=con_sesion)

# Montar frontend en /ui/
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/ui", StaticFiles(directory=frontend_path, html=True), name="ui")

@app.get("/", include_in_schema=False)
def read_root():
    return RedirectResponse(url="/ui/")
