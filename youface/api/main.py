import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from youface.app_context import set_app_context
set_app_context('cli')

from youface import conda
conda.setup()

from youface import state_manager
from youface.program import create_program
from youface.args import apply_args
from youface.jobs import job_manager

# Inicializar o state_manager com os argumentos padrão
program = create_program()
known_args, _ = program.parse_known_args(['run'])
apply_args(vars(known_args), state_manager.init_item)

# Inicializar o logger para capturar os logs dos workers e pipeline
from youface import logger
logger.init(state_manager.get_item('log_level') or 'info')

# Inicializar a fila de jobs
jobs_path = state_manager.get_item('jobs_path') or '.jobs'
job_manager.init_jobs(jobs_path)

from youface import metadata
from youface.api.database import init_db
from youface.api.worker import start_worker, stop_worker
from youface.api.routes import router as api_router
from contextlib import asynccontextmanager


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db()
        start_worker()
        yield
        stop_worker()

    app_version = metadata.get('version') or "3.7.0-my.1"

    app = FastAPI(
        title="YouFace API",
        description="RESTful API for the modernized YouFace decoupled architecture",
        version=app_version,
        lifespan=lifespan
    )


    @app.middleware("http")
    async def log_correlation_middleware(request, call_next):
        import uuid
        from youface.logger import set_session_context
        session_id = request.headers.get("X-Session-ID") or request.headers.get("X-Correlation-ID") or f"sess-{uuid.uuid4().hex[:8]}"
        set_session_context(session_id)
        try:
            response = await call_next(request)
            response.headers["X-Session-ID"] = session_id
            return response
        finally:
            set_session_context('')

    # Configuração de CORS para permitir acesso seguro do frontend Next.js local em qualquer porta
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Middleware custom: rate limiting, security headers, body size cap
    from youface.api.middleware import RateLimiter, SecurityHeaders, MaxBodySize, TenantMiddleware
    # Ordem importa: MaxBodySize primeiro (rejeita cedo), depois SecurityHeaders,
    # depois RateLimiter. Middlewares são executados em ordem reversa ao redor
    # da request, então esta ordem resulta em: rate limit check first, then
    # security headers added on response, then size cap on the way in.
    app.add_middleware(MaxBodySize, max_bytes=200 * 1024 * 1024)
    app.add_middleware(SecurityHeaders)
    app.add_middleware(RateLimiter, requests_per_window=60, window_seconds=60)
    # Tenant identification runs LAST (outermost) so it sees the final
    # response and can decorate it with X-RateLimit-* headers. It does not
    # reject any request by itself — quota enforcement is explicit at the
    # endpoint that costs minutes (job create, train start).
    app.add_middleware(TenantMiddleware)

    # Bearer auth gate. Disabled unless YOUFACE_API_TOKEN env var is set.
    # See youface/api/auth.py for the full design.
    from youface.api.auth import BearerAuthMiddleware
    app.add_middleware(BearerAuthMiddleware)

    # Inclusão do roteador de endpoints.
    # Manteve compat: tanto /api quanto /api/v1 funcionam. A partir da
    # próxima major release, /api será deprecado e o prefixo único será /api/v1.
    app.include_router(api_router, prefix="/api")
    app.include_router(api_router, prefix="/api/v1")

    # Servir os arquivos estáticos do frontend Next.js exportado se existir
    import os
    import sys
    from fastapi.staticfiles import StaticFiles
    
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(backend_dir, "..", ".."))
    frontend_out_dir = os.path.join(root_dir, "frontend", "out")
    
    is_testing = "pytest" in sys.modules or "unittest" in sys.modules
    
    if os.path.exists(frontend_out_dir) and not is_testing:
        app.mount("/", StaticFiles(directory=frontend_out_dir, html=True), name="frontend")
    else:
        @app.get("/")
        def read_root():
            return {
                "app": "YouFace API",
                "version": app_version,
                "status": "online"
            }

    return app


app = create_app()


def find_free_port(start_port: int = 8000, max_attempts: int = 100) -> int:
    import socket
    for p in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError(f"Nenhuma porta livre encontrada a partir de {start_port}")


def write_frontend_config(port: int) -> None:
    import os
    import json
    from youface import logger
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(backend_dir, "..", ".."))
    frontend_public_dir = os.path.join(root_dir, "frontend", "public")
    frontend_out_dir = os.path.join(root_dir, "frontend", "out")

    # Caminho relativo — o frontend passa a usar `/api/...` na mesma origem,
    # o que destrava LAN, proxy reverso e HTTPS compartilhado.
    # Mantemos compatibilidade com resolvers antigos gravando tambem a URL
    # absoluta em `apiUrlAbsolute` (lida de forma opcional pelo frontend).
    config_data = {
        "apiUrl": "",
        "apiUrlAbsolute": f"http://localhost:{port}",
        "apiPathPrefix": "/api",
    }

    if os.path.exists(frontend_public_dir):
        config_path = os.path.join(frontend_public_dir, "config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
            logger.info(f"[API] Gravado config.json do frontend em: {config_path}", __name__)
        except Exception as e:
            logger.error(f"[API] Erro ao gravar config.json em public: {str(e)}", __name__)

    if os.path.exists(frontend_out_dir):
        config_path = os.path.join(frontend_out_dir, "config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
            logger.info(f"[API] Gravado config.json do frontend em: {config_path}", __name__)
        except Exception as e:
            logger.error(f"[API] Erro ao gravar config.json em out: {str(e)}", __name__)


if __name__ == "__main__":
    # Carregar configuração padrão ou via variáveis de ambiente
    host = "127.0.0.1"
    try:
        port = find_free_port(8000)
    except Exception:
        port = 8000
        
    write_frontend_config(port)
    uvicorn.run("youface.api.main:app", host=host, port=port, reload=True)
