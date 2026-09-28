import os
import shutil
import uuid
import json
import datetime
import sys
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from facefusion import state_manager
from facefusion.execution import get_available_execution_providers, detect_static_execution_devices
from facefusion.filesystem import resolve_file_paths, get_file_name, create_directory, get_default_path
from facefusion.processors.core import get_processors_modules
from facefusion.jobs import job_manager, job_runner, job_helper
from facefusion.args import collect_step_args
from facefusion.core import process_step
from facefusion.api.database import get_db, JobModel, SessionLocal

router = APIRouter()

# R2: include sub-routers from facefusion.api.routes.* (each is a thin
# domain-specific module). Adding a new domain? Create facefusion/api/routes/<x>.py
# with its own APIRouter() and add an include_router() here.
from facefusion.api.routes import projects as _projects_module  # noqa: E402

router.include_router(_projects_module.router)


def get_user_projects_dir() -> str:
    home = os.path.expanduser("~")
    videos_dir = os.path.join(home, "Vídeos")
    if not os.path.exists(videos_dir):
        videos_dir = os.path.join(home, "Videos")
    if not os.path.exists(videos_dir):
        videos_dir = os.path.join(home, "Videos")
        os.makedirs(videos_dir, exist_ok=True)
    projects_dir = os.path.join(videos_dir, "FaceFusion_Projects")
    os.makedirs(projects_dir, exist_ok=True)
    return os.path.abspath(projects_dir)


def get_allowed_directories() -> List[str]:
    jobs_path = state_manager.get_item("jobs_path") or get_default_path('data')
    temp_path = state_manager.get_item("temp_path") or get_default_path('temp')
    cache_path = get_default_path('cache')
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return [
        os.path.abspath(jobs_path),
        os.path.abspath(temp_path),
        os.path.abspath(cache_path),
        get_user_projects_dir(),
        root_dir
    ]


def validate_safe_path(target_path: str, allowed_dirs: Optional[List[str]] = None) -> str:
    if allowed_dirs is None:
        allowed_dirs = get_allowed_directories()
    abs_target = os.path.abspath(target_path)
    for allowed in allowed_dirs:
        abs_allowed = os.path.abspath(allowed)
        try:
            if os.path.commonpath([abs_target, abs_allowed]) == abs_allowed:
                return abs_target
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail=f"Acesso negado: o arquivo '{target_path}' reside fora dos diretórios autorizados.")



class FaceMapping(BaseModel):
    source_path: str
    target_face_index: int
    reference_frame_number: int


class JobCreateRequest(BaseModel):
    project_name: Optional[str] = None
    source_paths: List[str]
    target_path: str
    face_swapper_weight: Optional[float] = 0.5
    face_mask_blur: Optional[float] = 0.3
    detection_threshold: Optional[float] = 0.5
    smoothing: Optional[int] = 5
    processors: Optional[List[str]] = ["face_swapper"]
    output_format: Optional[str] = "mp4"
    trim_frame_start: Optional[int] = None
    trim_frame_end: Optional[int] = None
    face_swapper_model: Optional[str] = "hyperswap_1a_256"
    face_swapper_pixel_boost: Optional[str] = None
    face_enhancer_model: Optional[str] = "gfpgan_1.4"
    face_enhancer_blend: Optional[int] = 80
    face_enhancer_weight: Optional[float] = 1.0
    frame_enhancer_model: Optional[str] = "span_kendata_x4"
    frame_enhancer_blend: Optional[int] = 80
    # Additional processors options
    face_editor_model: Optional[str] = None
    face_editor_eyebrow_direction: Optional[float] = None
    face_editor_eye_gaze_horizontal: Optional[float] = None
    face_editor_eye_gaze_vertical: Optional[float] = None
    face_editor_eye_open_ratio: Optional[float] = None
    face_editor_lip_open_ratio: Optional[float] = None
    face_editor_mouth_smile: Optional[float] = None
    face_editor_head_pitch: Optional[float] = None
    face_editor_head_yaw: Optional[float] = None
    face_editor_head_roll: Optional[float] = None
    age_modifier_model: Optional[str] = None
    age_modifier_direction: Optional[int] = None
    lip_syncer_model: Optional[str] = None
    lip_syncer_weight: Optional[float] = None
    expression_restorer_model: Optional[str] = None
    expression_restorer_factor: Optional[float] = None
    # Additional 5 processors
    deep_swapper_model: Optional[str] = None
    deep_swapper_morph: Optional[int] = None
    face_debugger_items: Optional[List[str]] = None
    frame_colorizer_model: Optional[str] = None
    frame_colorizer_blend: Optional[int] = None
    frame_colorizer_size: Optional[str] = None
    background_remover_model: Optional[str] = None
    background_remover_color: Optional[List[int]] = None
    output_audio_encoder: Optional[str] = "aac"
    output_audio_quality: Optional[int] = 80
    output_audio_volume: Optional[int] = 100
    output_video_encoder: Optional[str] = "libx264"
    output_video_preset: Optional[str] = "medium"
    # Configurações Avançadas de Detecção e Máscara
    face_mask_types: Optional[List[str]] = None
    face_mask_padding: Optional[List[int]] = None
    face_detector_model: Optional[str] = None
    face_detector_size: Optional[str] = None
    face_detector_angles: Optional[List[int]] = None
    face_landmarker_model: Optional[str] = None
    face_landmarker_score: Optional[float] = None
    face_occluder_model: Optional[str] = None
    face_parser_model: Optional[str] = None
    mappings: Optional[List[FaceMapping]] = None


@router.get("/hardware/providers")
def get_hardware_providers() -> List[str]:
    """
    Retorna todos os provedores de execução (hardware acceleration) disponíveis na máquina.
    """
    try:
        providers = get_available_execution_providers()
        return [str(p) for p in providers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler provedores de hardware: {str(e)}")


@router.get("/hardware/devices")
def get_hardware_devices() -> List[Dict[str, Any]]:
    """
    Retorna detalhes de temperatura, memória e uso dos dispositivos NVIDIA (GPUs) detectados.
    """
    try:
        devices = detect_static_execution_devices()
        return [dict(device) for device in devices]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao detectar dispositivos NVIDIA: {str(e)}")


@router.get("/hardware/telemetry")
def get_hardware_telemetry() -> Dict[str, Any]:
    """
    Retorna telemetria completa de uso de CPU, GPU, RAM e VRAM em tempo real.
    """
    try:
        import psutil
        cpu_pct = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()

        gpu_data = {
            "name": "GPU",
            "temperature_c": None,
            "usage_percent": None,
            "vram_total_gb": 0.0,
            "vram_used_gb": 0.0,
            "vram_free_gb": 0.0,
            "vram_usage_percent": 0.0
        }

        devices = detect_static_execution_devices()
        if devices:
            d = devices[0]
            gpu_data["name"] = d.get("product", {}).get("name", "NVIDIA GPU")
            gpu_data["temperature_c"] = d.get("temperature", {}).get("gpu", {}).get("value")
            gpu_data["usage_percent"] = d.get("utilization", {}).get("gpu", {}).get("value")

            vm_total = d.get("video_memory", {}).get("total", {}).get("value", 0)
            vm_free = d.get("video_memory", {}).get("free", {}).get("value", 0)
            vm_used = max(0, vm_total - vm_free)

            gpu_data["vram_total_gb"] = round(vm_total / 1024.0, 1)
            gpu_data["vram_used_gb"] = round(vm_used / 1024.0, 1)
            gpu_data["vram_free_gb"] = round(vm_free / 1024.0, 1)
            if vm_total > 0:
                gpu_data["vram_usage_percent"] = round((vm_used / vm_total) * 100.0, 1)

        return {
            "cpu": {
                "usage_percent": round(cpu_pct, 1),
                "cores": psutil.cpu_count(logical=True)
            },
            "ram": {
                "total_gb": round(vm.total / (1024**3), 1),
                "used_gb": round(vm.used / (1024**3), 1),
                "free_gb": round(vm.available / (1024**3), 1),
                "usage_percent": round(vm.percent, 1)
            },
            "gpu": gpu_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao coletar telemetria de hardware: {str(e)}")


@router.get("/processors/list")
def get_available_processors() -> List[str]:
    """
    Retorna a lista de processadores de frame disponíveis no sistema.
    """
    try:
        processors_paths = resolve_file_paths("facefusion/processors/modules")
        names = [get_file_name(path) for path in processors_paths]
        return [name for name in names if name is not None]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao varrer processadores: {str(e)}")


@router.get("/config")
def get_current_config() -> Dict[str, Any]:
    """
    Retorna as configurações e o estado global atual da aplicação em execução.
    """
    try:
        return {
            "temp_path": state_manager.get_item("temp_path"),
            "jobs_path": state_manager.get_item("jobs_path"),
            "log_level": state_manager.get_item("log_level"),
            "execution_providers": state_manager.get_item("execution_providers"),
            "execution_thread_count": state_manager.get_item("execution_thread_count"),
            "video_memory_strategy": state_manager.get_item("video_memory_strategy"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler configuração do estado: {str(e)}")


class ConfigUpdateRequest(BaseModel):
    temp_path: Optional[str] = None
    jobs_path: Optional[str] = None
    log_level: Optional[str] = None
    execution_providers: Optional[List[str]] = None
    execution_thread_count: Optional[int] = None
    video_memory_strategy: Optional[str] = None


@router.post("/config")
def update_config(request: ConfigUpdateRequest) -> Dict[str, Any]:
    """
    Atualiza as configurações do estado em memória.
    """
    try:
        if request.temp_path is not None:
            state_manager.set_item("temp_path", request.temp_path)
        if request.jobs_path is not None:
            state_manager.set_item("jobs_path", request.jobs_path)
        if request.log_level is not None:
            state_manager.set_item("log_level", request.log_level)
        if request.execution_providers is not None:
            state_manager.set_item("execution_providers", request.execution_providers)
        if request.execution_thread_count is not None:
            state_manager.set_item("execution_thread_count", request.execution_thread_count)
        if request.video_memory_strategy is not None:
            state_manager.set_item("video_memory_strategy", request.video_memory_strategy)
        return {"status": "success", "config": get_current_config()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar configuração: {str(e)}")


# ---------------------------------------------------------
# GERENCIADOR DE DOWNLOAD DE MODELOS DE IA
# ---------------------------------------------------------
model_download_state = {
    "status": "idle",  # "idle" | "downloading" | "completed" | "error" | "cancelled"
    "scope": "full",
    "current_model": "",
    "downloaded": 0,
    "total": 0,
    "percent": 0.0,
    "error": None
}
download_thread = None

class DownloadModelsRequest(BaseModel):
    download_scope: Optional[str] = "full"
    download_provider: Optional[str] = "github"


def _calculate_models_disk_info() -> Dict[str, Any]:
    models_dir = os.path.abspath(".assets/models")
    if not os.path.exists(models_dir):
        return {"count": 0, "size_gb": 0.0}
    
    total_bytes = 0
    onnx_count = 0
    try:
        for root, _, files in os.walk(models_dir):
            for f in files:
                fp = os.path.join(root, f)
                total_bytes += os.path.getsize(fp)
                if f.endswith(".onnx"):
                    onnx_count += 1
        return {
            "count": onnx_count,
            "size_gb": round(total_bytes / (1024 ** 3), 2)
        }
    except Exception:
        return {"count": 0, "size_gb": 0.0}


def _run_models_download(scope: str, provider: str):
    global model_download_state
    try:
        model_download_state["status"] = "downloading"
        model_download_state["scope"] = scope
        model_download_state["error"] = None
        
        from facefusion import state_manager
        providers = [provider, "huggingface" if provider == "github" else "github"]
        state_manager.init_item("download_providers", providers)
        state_manager.set_item("download_providers", providers)
        state_manager.init_item("download_scope", scope)
        state_manager.set_item("download_scope", scope)
        
        from facefusion.filesystem import get_file_name, resolve_file_paths
        from facefusion.processors.core import get_processors_modules
        from facefusion.download import conditional_download_hashes, conditional_download_sources
        
        available_processors = [ get_file_name(file_path) for file_path in resolve_file_paths("facefusion/processors/modules") ]
        processor_modules = get_processors_modules(available_processors)
        common_modules = []
        for processor_module in processor_modules:
            for common_module in processor_module.get_common_modules():
                if common_module not in common_modules:
                    common_modules.append(common_module)

        model_list = []
        for module in common_modules + processor_modules:
            if hasattr(module, "create_static_model_set"):
                model_set = module.create_static_model_set(scope)
                for model_key, model_data in model_set.items():
                    model_list.append((model_key, model_data))

        model_download_state["total"] = len(model_list)
        model_download_state["downloaded"] = 0
        
        for idx, (model_key, model_data) in enumerate(model_list):
            if model_download_state["status"] == "cancelled":
                break
            model_download_state["current_model"] = model_key
            model_download_state["downloaded"] = idx
            model_download_state["percent"] = round((idx / max(len(model_list), 1)) * 100, 1)
            
            hashes = model_data.get("hashes")
            sources = model_data.get("sources")
            if hashes and sources:
                conditional_download_hashes(hashes)
                conditional_download_sources(sources)

        if model_download_state["status"] != "cancelled":
            model_download_state["downloaded"] = len(model_list)
            model_download_state["percent"] = 100.0
            model_download_state["status"] = "completed"
            model_download_state["current_model"] = "Todos os modelos baixados com sucesso!"
    except Exception as e:
        model_download_state["status"] = "error"
        model_download_state["error"] = str(e)


@router.get("/models/status")
def get_models_status() -> Dict[str, Any]:
    """
    Retorna o status do download de modelos e o uso de disco em .assets/models/.
    """
    disk_info = _calculate_models_disk_info()
    return {
        **model_download_state,
        "disk": disk_info
    }


@router.post("/models/download")
def start_models_download(request: DownloadModelsRequest) -> Dict[str, Any]:
    """
    Inicia o download de todos os modelos em segundo plano.
    """
    global download_thread, model_download_state
    if model_download_state["status"] == "downloading":
        return {"status": "already_running", "message": "Download de modelos já está em andamento."}
    
    scope = request.download_scope or "full"
    provider = request.download_provider or "github"
    model_download_state["status"] = "downloading"
    model_download_state["scope"] = scope
    model_download_state["percent"] = 0.0
    model_download_state["downloaded"] = 0
    model_download_state["error"] = None
    
    import threading
    download_thread = threading.Thread(target=_run_models_download, args=(scope, provider), daemon=True)
    download_thread.start()
    
    return {"status": "started", "message": f"Download de modelos ({scope}) iniciado em segundo plano."}


@router.post("/models/cancel")
def cancel_models_download() -> Dict[str, Any]:
    """
    Cancela o download de modelos em andamento.
    """
    global model_download_state
    if model_download_state["status"] == "downloading":
        model_download_state["status"] = "cancelled"
        model_download_state["current_model"] = "Download cancelado pelo usuário."
        return {"status": "cancelled", "message": "Download de modelos cancelado."}
    return {"status": "idle", "message": "Nenhum download em andamento."}


@router.post("/media/upload")
def upload_media(file: UploadFile = File(...)):
    """
    Faz o upload de uma imagem ou vídeo para a pasta temporária de jobs.
    """
    try:
        jobs_path = state_manager.get_item("jobs_path") or get_default_path('data')
        uploads_dir = os.path.join(jobs_path, "uploads")
        create_directory(uploads_dir)
        
        filename = file.filename or "file"
        file_ext = os.path.splitext(filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(uploads_dir, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {
            "file_path": os.path.abspath(file_path),
            "filename": filename,
            "unique_filename": unique_filename,
            "url": f"/api/media/upload/{unique_filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no upload da mídia: {str(e)}")


@router.get("/media/upload/{filename:path}")
def get_upload_file(filename: str):
    """
    Retorna um arquivo de mídia enviado para a pasta temporária ou recortes de análise.
    """
    jobs_path = state_manager.get_item("jobs_path") or get_default_path('data')
    uploads_dir = os.path.abspath(os.path.join(jobs_path, "uploads"))
    file_path = os.path.abspath(os.path.join(uploads_dir, filename))
    
    # Previne path traversal
    safe_path = validate_safe_path(file_path, [uploads_dir])
        
    if os.path.exists(safe_path):
        return FileResponse(safe_path)
    raise HTTPException(status_code=404, detail="Arquivo de mídia não encontrado")


@router.get("/media/output/{filename:path}")
def get_output_file(filename: str):
    """
    Retorna o arquivo final gerado pelo processamento.
    """
    jobs_path = state_manager.get_item("jobs_path") or get_default_path('data')
    outputs_dir = os.path.abspath(os.path.join(jobs_path, "outputs"))
    file_path = os.path.abspath(os.path.join(outputs_dir, filename))
    
    # Previne path traversal
    safe_path = validate_safe_path(file_path, [outputs_dir])
        
    if os.path.exists(safe_path):
        return FileResponse(safe_path)
    raise HTTPException(status_code=404, detail="Arquivo de mídia não encontrado")


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Retorna a lista de todas as tarefas (jobs) cadastradas no sistema, lidas a partir do banco de dados relacional.
    """
    try:
        jobs = db.query(JobModel).order_by(desc(JobModel.created_at)).all()
        jobs_list = []
        for job in jobs:
            source = ""
            if job.source_paths:
                try:
                    source_list = json.loads(job.source_paths)
                    if source_list:
                        source = f"/api/media/upload/{os.path.basename(source_list[0])}"
                except Exception:
                    pass

            target = ""
            if job.target_path:
                target = f"/api/media/upload/{os.path.basename(job.target_path)}"

            output = ""
            if job.output_path:
                if job.project_name:
                    output = f"/api/projects/media/{job.project_name}/output/{os.path.basename(job.output_path)}"
                else:
                    output = f"/api/media/output/{os.path.basename(job.output_path)}"

            jobs_list.append({
                "id": job.id,
                "project_name": job.project_name,
                "status": job.status,
                "progress": job.progress,
                "date_created": job.created_at,
                "date_updated": job.updated_at,
                "source": source,
                "target": target,
                "output": output,
                "error_message": job.error_message,
                "step": job.step
            })
        return jobs_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar jobs: {str(e)}")


@router.get("/jobs/stream")
async def stream_jobs():
    """
    Server-Sent Events (SSE) endpoint que envia atualizações da lista de jobs
    em tempo real para o cockpit, reduzindo overhead de polling HTTP contínuo.
    """
    import asyncio
    from fastapi.responses import StreamingResponse

    async def event_generator():
        last_hash = ""
        while True:
            try:
                db = SessionLocal()
                jobs = db.query(JobModel).order_by(desc(JobModel.created_at)).limit(50).all()
                data = [
                    {
                        "id": j.id,
                        "project_name": j.project_name,
                        "status": j.status,
                        "progress": j.progress,
                        "step": j.step,
                        "error_message": j.error_message,
                        "output_path": j.output_path,
                        "outputUrl": (
                            f"/api/projects/media/{j.project_name}/output/{os.path.basename(j.output_path)}"
                            if j.project_name and j.output_path and os.path.exists(j.output_path)
                            else (f"/api/media/output/{os.path.basename(j.output_path)}" if j.output_path and os.path.exists(j.output_path) else None)
                        ),
                        "created_at": j.created_at.isoformat() if j.created_at else None,
                        "updated_at": j.updated_at.isoformat() if j.updated_at else None
                    }
                    for j in jobs
                ]
                db.close()
                current_hash = f"{len(data)}:" + ";".join(f"{item['id']}-{item['status']}-{item['progress']}-{item['step']}" for item in data)
                if current_hash != last_hash:
                    last_hash = current_hash
                    yield f"data: {json.dumps(data)}\n\n"
            except Exception as e:
                yield f": heartbeat {str(e)}\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retorna o status e os detalhes de uma tarefa específica.
    """
    job = db.query(JobModel).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    
    source = ""
    if job.source_paths:
        try:
            source_list = json.loads(job.source_paths)
            if source_list:
                source = f"/api/media/upload/{os.path.basename(source_list[0])}"
        except Exception:
            pass
            
    target = ""
    if job.target_path:
        target = f"/api/media/upload/{os.path.basename(job.target_path)}"
        
    output = ""
    if job.output_path and job.status == "completed":
        output = f"/api/media/output/{os.path.basename(job.output_path)}"

    return {
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "date_created": job.created_at.isoformat(),
        "date_updated": job.updated_at.isoformat(),
        "source": source,
        "target": target,
        "output": output,
        "error_message": job.error_message,
        "step": job.step
    }


def apply_processor_args(step_args: Dict[str, Any], request: JobCreateRequest) -> None:
    if request.face_swapper_model is not None:
        step_args["face_swapper_model"] = request.face_swapper_model
    if request.face_swapper_pixel_boost is not None:
        step_args["face_swapper_pixel_boost"] = request.face_swapper_pixel_boost
    if request.face_swapper_weight is not None:
        step_args["face_swapper_weight"] = request.face_swapper_weight
    if request.face_mask_blur is not None:
        step_args["face_mask_blur"] = request.face_mask_blur
    if request.detection_threshold is not None:
        step_args["face_detector_score"] = request.detection_threshold
        step_args["face_landmarker_score"] = request.detection_threshold
    if request.trim_frame_start is not None:
        step_args["trim_frame_start"] = request.trim_frame_start
    if request.trim_frame_end is not None:
        step_args["trim_frame_end"] = request.trim_frame_end
    if request.face_enhancer_model is not None:
        step_args["face_enhancer_model"] = request.face_enhancer_model
    if request.face_enhancer_blend is not None:
        step_args["face_enhancer_blend"] = request.face_enhancer_blend
    if request.face_enhancer_weight is not None:
        step_args["face_enhancer_weight"] = request.face_enhancer_weight
    if request.frame_enhancer_model is not None:
        step_args["frame_enhancer_model"] = request.frame_enhancer_model
    if request.frame_enhancer_blend is not None:
        step_args["frame_enhancer_blend"] = request.frame_enhancer_blend
    if request.face_editor_model is not None:
        step_args["face_editor_model"] = request.face_editor_model
    if request.face_editor_eyebrow_direction is not None:
        step_args["face_editor_eyebrow_direction"] = request.face_editor_eyebrow_direction
    if request.face_editor_eye_gaze_horizontal is not None:
        step_args["face_editor_eye_gaze_horizontal"] = request.face_editor_eye_gaze_horizontal
    if request.face_editor_eye_gaze_vertical is not None:
        step_args["face_editor_eye_gaze_vertical"] = request.face_editor_eye_gaze_vertical
    if request.face_editor_eye_open_ratio is not None:
        step_args["face_editor_eye_open_ratio"] = request.face_editor_eye_open_ratio
    if request.face_editor_lip_open_ratio is not None:
        step_args["face_editor_lip_open_ratio"] = request.face_editor_lip_open_ratio
    if request.face_editor_mouth_smile is not None:
        step_args["face_editor_mouth_smile"] = request.face_editor_mouth_smile
    if request.face_editor_head_pitch is not None:
        step_args["face_editor_head_pitch"] = request.face_editor_head_pitch
    if request.face_editor_head_yaw is not None:
        step_args["face_editor_head_yaw"] = request.face_editor_head_yaw
    if request.face_editor_head_roll is not None:
        step_args["face_editor_head_roll"] = request.face_editor_head_roll
    if request.age_modifier_model is not None:
        step_args["age_modifier_model"] = request.age_modifier_model
    if request.age_modifier_direction is not None:
        step_args["age_modifier_direction"] = request.age_modifier_direction
    if request.lip_syncer_model is not None:
        step_args["lip_syncer_model"] = request.lip_syncer_model
    if request.lip_syncer_weight is not None:
        step_args["lip_syncer_weight"] = request.lip_syncer_weight
    if request.expression_restorer_model is not None:
        step_args["expression_restorer_model"] = request.expression_restorer_model
    if request.expression_restorer_factor is not None:
        step_args["expression_restorer_factor"] = request.expression_restorer_factor
    if request.deep_swapper_model is not None:
        step_args["deep_swapper_model"] = request.deep_swapper_model
    if request.deep_swapper_morph is not None:
        step_args["deep_swapper_morph"] = request.deep_swapper_morph
    if request.face_debugger_items is not None:
        step_args["face_debugger_items"] = request.face_debugger_items
    if request.frame_colorizer_model is not None:
        step_args["frame_colorizer_model"] = request.frame_colorizer_model
    if request.frame_colorizer_blend is not None:
        step_args["frame_colorizer_blend"] = request.frame_colorizer_blend
    if request.frame_colorizer_size is not None:
        step_args["frame_colorizer_size"] = request.frame_colorizer_size
    if request.background_remover_model is not None:
        step_args["background_remover_model"] = request.background_remover_model
    if request.background_remover_color is not None:
        step_args["background_remover_color"] = request.background_remover_color
    if request.output_audio_encoder is not None:
        step_args["output_audio_encoder"] = request.output_audio_encoder
    if request.output_audio_quality is not None:
        step_args["output_audio_quality"] = request.output_audio_quality
    if request.output_audio_volume is not None:
        step_args["output_audio_volume"] = request.output_audio_volume
    if request.output_video_encoder is not None:
        step_args["output_video_encoder"] = request.output_video_encoder
    if request.output_video_preset is not None:
        step_args["output_video_preset"] = request.output_video_preset
    # Configurações Avançadas de Detecção e Máscara
    if request.face_mask_types is not None:
        step_args["face_mask_types"] = request.face_mask_types
    if request.face_mask_padding is not None:
        step_args["face_mask_padding"] = request.face_mask_padding
    if request.face_detector_model is not None:
        step_args["face_detector_model"] = request.face_detector_model
    if request.face_detector_size is not None:
        step_args["face_detector_size"] = request.face_detector_size
    if request.face_detector_angles is not None:
        step_args["face_detector_angles"] = request.face_detector_angles
    if request.face_landmarker_model is not None:
        step_args["face_landmarker_model"] = request.face_landmarker_model
    if request.face_landmarker_score is not None:
        step_args["face_landmarker_score"] = request.face_landmarker_score
    if request.face_occluder_model is not None:
        step_args["face_occluder_model"] = request.face_occluder_model
    if request.face_parser_model is not None:
        step_args["face_parser_model"] = request.face_parser_model


@router.post("/jobs")
def create_job(request: JobCreateRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Cria uma nova tarefa de Face Swap na fila persistente do banco de dados e no disco.
    Suporta mapeamento de múltiplos rostos ou fluxo padrão de face única/tudo.
    """
    try:
        jobs_path = state_manager.get_item("jobs_path") or get_default_path('data')
        uploads_dir = os.path.abspath(os.path.join(jobs_path, "uploads"))
        outputs_dir = os.path.join(jobs_path, "outputs")
        create_directory(outputs_dir)

        # Resolução automática de caminhos de mídia com validação segura
        resolved_source_paths = []
        for path in request.source_paths:
            if path.startswith("/api/media/upload/"):
                filename = os.path.basename(path)
                resolved_source_paths.append(validate_safe_path(os.path.join(uploads_dir, filename)))
            else:
                resolved_source_paths.append(validate_safe_path(path))
                
        resolved_target_path = request.target_path
        if request.target_path.startswith("/api/media/upload/"):
            filename = os.path.basename(request.target_path)
            resolved_target_path = validate_safe_path(os.path.join(uploads_dir, filename))
        else:
            resolved_target_path = validate_safe_path(request.target_path)

        from facefusion.filesystem import is_image, is_video
        
        # Validar existências e tipos de mídias de origem
        for p in resolved_source_paths:
            if not os.path.exists(p):
                raise HTTPException(status_code=400, detail=f"Arquivo de origem não encontrado no disco: {p}")
            if not (is_image(p) or is_video(p)):
                raise HTTPException(status_code=400, detail=f"Arquivo de origem com formato inválido ou corrompido: {p}")
                
        # Validar mídia de destino
        if not os.path.exists(resolved_target_path):
            raise HTTPException(status_code=400, detail=f"Arquivo de destino não encontrado no disco: {resolved_target_path}")
        if not (is_image(resolved_target_path) or is_video(resolved_target_path)):
            raise HTTPException(status_code=400, detail=f"Arquivo de destino com formato inválido ou corrompido: {resolved_target_path}")

        target_ext = os.path.splitext(resolved_target_path)[1] or ".mp4"
        job_id = f"job-{uuid.uuid4().hex[:8]}"

        # Estrutura de Projeto em ~/Vídeos/FaceFusion_Projects/<nome_do_projeto>/
        import re, shutil
        if request.project_name and request.project_name.strip():
            safe_project_name = re.sub(r'[^a-zA-Z0-9_\- ]+', '_', request.project_name.strip())
        else:
            safe_project_name = f"Projeto_{datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')}"

        projects_dir = get_user_projects_dir()
        proj_dir = os.path.join(projects_dir, safe_project_name)
        source_dir = os.path.join(proj_dir, "source")
        target_dir = os.path.join(proj_dir, "target")
        output_dir = os.path.join(proj_dir, "output")
        os.makedirs(source_dir, exist_ok=True)
        os.makedirs(target_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        # Copiar fontes para a subpasta source/ do projeto
        project_source_paths = []
        for p in resolved_source_paths:
            src_fname = os.path.basename(p)
            dest_src = os.path.join(source_dir, src_fname)
            if not os.path.exists(dest_src) or os.path.abspath(p) != os.path.abspath(dest_src):
                shutil.copy2(p, dest_src)
            project_source_paths.append(dest_src)

        # Copiar destino para a subpasta target/ do projeto
        tgt_fname = os.path.basename(resolved_target_path)
        dest_tgt = os.path.join(target_dir, tgt_fname)
        if not os.path.exists(dest_tgt) or os.path.abspath(resolved_target_path) != os.path.abspath(dest_tgt):
            shutil.copy2(resolved_target_path, dest_tgt)
        project_target_path = dest_tgt

        # Caminho final da renderização na pasta output/
        if is_video(resolved_target_path) and request.output_format:
            output_ext = f".{request.output_format.lower().lstrip('.')}"
        else:
            output_ext = target_ext
        output_filename = f"resultado{output_ext}"
        output_path = os.path.abspath(os.path.join(output_dir, output_filename))

        # Criar project.json de metadados
        project_meta = {
            "id": job_id,
            "name": safe_project_name,
            "created_at": datetime.datetime.now().isoformat(),
            "status": "queued",
            "source_files": [os.path.basename(p) for p in project_source_paths],
            "target_file": tgt_fname,
            "output_file": output_filename,
            "output_path": output_path,
            "project_dir": proj_dir,
            "processors": request.processors,
            "output_format": request.output_format,
            "output_audio_encoder": request.output_audio_encoder,
            "output_audio_quality": request.output_audio_quality,
            "output_audio_volume": request.output_audio_volume,
            "output_video_encoder": request.output_video_encoder,
            "output_video_preset": request.output_video_preset
        }
        with open(os.path.join(proj_dir, "project.json"), "w", encoding="utf-8") as pf:
            json.dump(project_meta, pf, indent=2, ensure_ascii=False)

        # 1. Criar os arquivos de job no disco
        if not job_manager.create_job(job_id):
            raise HTTPException(status_code=500, detail="Falha ao criar arquivo de job.")

        if request.mappings:
            # Fluxo de Mapeamento de múltiplos rostos (passos sequenciais interligados)
            for idx, mapping in enumerate(request.mappings):
                resolved_mapping_source = mapping.source_path
                if mapping.source_path.startswith("/api/media/upload/"):
                    resolved_mapping_source = os.path.join(uploads_dir, os.path.basename(mapping.source_path))
                resolved_mapping_source = validate_safe_path(resolved_mapping_source)

                if not os.path.exists(resolved_mapping_source):
                    raise HTTPException(status_code=400, detail=f"Arquivo de origem mapeado não encontrado no disco: {resolved_mapping_source}")
                if not (is_image(resolved_mapping_source) or is_video(resolved_mapping_source)):
                    raise HTTPException(status_code=400, detail=f"Arquivo de origem mapeado com formato inválido ou corrompido: {resolved_mapping_source}")

                # Copiar também para source_dir se ainda não estiver
                map_fname = os.path.basename(resolved_mapping_source)
                map_dest_src = os.path.join(source_dir, map_fname)
                if not os.path.exists(map_dest_src) or os.path.abspath(resolved_mapping_source) != os.path.abspath(map_dest_src):
                    shutil.copy2(resolved_mapping_source, map_dest_src)

                step_args = collect_step_args()
                step_args["source_paths"] = [map_dest_src]
                
                # Interligar passos sequencialmente
                if idx == 0:
                    step_args["target_path"] = project_target_path
                else:
                    step_args["target_path"] = job_helper.get_step_output_path(job_id, idx - 1, output_path)

                step_args["output_path"] = output_path
                step_args["processors"] = request.processors
                step_args["face_selector_mode"] = "reference"
                step_args["reference_face_position"] = mapping.target_face_index
                step_args["reference_frame_number"] = mapping.reference_frame_number
                step_args["reference_target_path"] = project_target_path

                apply_processor_args(step_args, request)

                if not job_manager.add_step(job_id, step_args):
                    raise HTTPException(status_code=500, detail=f"Falha ao adicionar passo {idx} ao job.")
        else:
            # Fluxo padrão de face única/tudo
            step_args = collect_step_args()
            step_args["source_paths"] = project_source_paths
            step_args["target_path"] = project_target_path
            step_args["output_path"] = output_path
            step_args["processors"] = request.processors

            apply_processor_args(step_args, request)

            if not job_manager.add_step(job_id, step_args):
                raise HTTPException(status_code=500, detail="Falha ao adicionar step ao job.")

        if not job_manager.submit_job(job_id):
            raise HTTPException(status_code=500, detail="Falha ao enviar job para fila.")

        # 2. Registrar no banco de dados SQLite
        db_job = JobModel(
            id=job_id,
            status="queued",
            progress=0,
            project_name=safe_project_name,
            source_paths=json.dumps(project_source_paths),
            target_path=project_target_path,
            output_path=output_path,
            face_swapper_weight=request.face_swapper_weight,
            face_mask_blur=request.face_mask_blur,
            detection_threshold=request.detection_threshold,
            smoothing=request.smoothing,
            processors=json.dumps(request.processors)
        )
        db.add(db_job)
        db.commit()

        return {
            "job_id": job_id,
            "project_name": safe_project_name,
            "status": "queued",
            "output_path": output_path,
            "output_url": f"/api/projects/media/{safe_project_name}/output/{output_filename}"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao criar job: {str(e)}")


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Exclui uma tarefa do banco de dados, seus arquivos de job no disco e a mídia de saída se gerada.
    Impede a exclusão direta se a tarefa estiver em processamento ativo (necessário cancelar antes).
    """
    job = db.query(JobModel).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    
    if job.status == "processing":
        raise HTTPException(
            status_code=400,
            detail="Não é possível excluir uma tarefa em processamento ativo. Cancele-a antes de excluir."
        )

    try:
        # Excluir arquivos de job no disco
        job_manager.delete_job(job_id)
        
        # Excluir arquivos físicos de mídia se existirem
        if job.output_path and os.path.exists(job.output_path):
            try:
                os.remove(job.output_path)
            except Exception:
                pass
            
        # Excluir do banco
        db.delete(job)
        db.commit()
        
        return {"status": "success", "message": f"Job {job_id} excluído com sucesso."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao excluir job: {str(e)}")


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Cancela uma tarefa em fila ou em processamento ativo com segurança.
    """
    job = db.query(JobModel).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
        
    if job.status in ("completed", "failed"):
        return {"status": "info", "message": f"A tarefa {job_id} já está finalizada ({job.status})."}
        
    if job.status == "queued":
        job.status = "failed"
        job.progress = 0
        job.error_message = "Cancelado pelo usuário na fila."
        db.commit()
        return {"status": "success", "message": f"Tarefa {job_id} cancelada na fila."}
        
    if job.status == "processing":
        from facefusion.api.worker import cancel_running_job
        cancel_running_job(job_id)
        job.status = "failed"
        job.progress = 0
        job.error_message = "Cancelado pelo usuário durante o processamento."
        db.commit()
        return {"status": "success", "message": f"Sinal de cancelamento enviado para a tarefa {job_id}."}

    return {"status": "unknown", "message": f"Status desconhecido da tarefa: {job.status}"}


@router.post("/media/cleanup")
def cleanup_temporary_media(max_age_seconds: int = 3600) -> Dict[str, Any]:
    """
    Exclui arquivos temporários de crops e previews efêmeros para evitar esgotamento de disco.

    Args:
        max_age_seconds: idade máxima (em segundos) para considerar um arquivo
                         "temporário". Default 1h — alinhado com o ciclo típico
                         de preview/analyze do cockpit. Use 0 para limpar
                         tudo (legado).
    """
    import time
    try:
        jobs_path = state_manager.get_item("jobs_path") or get_default_path('data')
        uploads_dir = os.path.abspath(os.path.join(jobs_path, "uploads"))
        crops_dir = os.path.join(uploads_dir, "crops")
        cleaned_count = 0
        skipped_recent = 0
        now = time.time()
        if os.path.exists(crops_dir):
            for fname in os.listdir(crops_dir):
                fpath = os.path.join(crops_dir, fname)
                try:
                    if not os.path.isfile(fpath):
                        continue
                    if max_age_seconds > 0:
                        age = now - os.path.getmtime(fpath)
                        if age < max_age_seconds:
                            skipped_recent += 1
                            continue
                    os.remove(fpath)
                    cleaned_count += 1
                except Exception:
                    pass
        msg = f"{cleaned_count} arquivos removidos"
        if skipped_recent:
            msg += f", {skipped_recent} mantidos (< {max_age_seconds}s)"
        return {"status": "success", "message": msg, "removed": cleaned_count, "kept": skipped_recent}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na limpeza de mídia temporária: {str(e)}")


@router.get("/diagnostic/export")
def export_diagnostic(background_tasks: BackgroundTasks):
    """
    Gera um pacote ZIP contendo logs e configurações higienizados (sem PII ou segredos),
    e remove automaticamente o arquivo temporário após o download.
    """
    import tempfile
    import zipfile
    import platform
    try:
        from facefusion.filesystem import get_default_path
        from facefusion import state_manager
        
        # 1. Obter caminhos
        cache_dir = get_default_path('cache')
        log_file_path = os.path.join(cache_dir, 'facefusion.log')
        config_path = state_manager.get_item('config_path') or 'facefusion.ini'
        
        # 2. Criar arquivo zip temporário
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        temp_zip_name = temp_zip.name
        temp_zip.close()
        
        def sanitize_text(text: str) -> str:
            import re
            # Mascarar caminhos de usuário no Linux
            text = re.sub(r'/home/[a-zA-Z0-9_-]+', '/home/user', text)
            # Mascarar caminhos de usuário no macOS
            text = re.sub(r'/Users/[a-zA-Z0-9_-]+', '/Users/user', text)
            # Mascarar caminhos de usuário no Windows
            text = re.sub(r'[cC]:\\Users\\[a-zA-Z0-9_-]+', 'C:\\Users\\user', text)
            # Mascarar possíveis tokens/senhas
            text = re.sub(r'(?i)(token|password|secret|key)["\s:=]+[a-zA-Z0-9_=-]+', r'\1: [MASKED]', text)
            return text

        with zipfile.ZipFile(temp_zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Adicionar log higienizado se existir
            if os.path.exists(log_file_path):
                try:
                    with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        log_content = f.read()
                    sanitized_log = sanitize_text(log_content)
                    zipf.writestr('facefusion.log', sanitized_log)
                except Exception as ex:
                    zipf.writestr('log_error.txt', f"Erro ao ler log: {str(ex)}")
            else:
                zipf.writestr('facefusion.log', 'Nenhum log gerado ainda.')
                
            # Adicionar ini de configuração higienizado
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                        config_content = f.read()
                    sanitized_config = sanitize_text(config_content)
                    zipf.writestr('facefusion.ini', sanitized_config)
                except Exception as ex:
                    zipf.writestr('config_error.txt', f"Erro ao ler config: {str(ex)}")
                    
            # Adicionar dados do sistema/hardware
            system_info = {
                "os": platform.system(),
                "os_release": platform.release(),
                "os_version": platform.version(),
                "machine": platform.machine(),
                "python_version": platform.python_version(),
                "execution_providers": state_manager.get_item('execution_providers') or [],
                "video_memory_strategy": state_manager.get_item('video_memory_strategy') or 'balanced',
            }
            zipf.writestr('system_info.json', json.dumps(system_info, indent=4))
            
        # Agendar remoção do zip temporário após o streaming para o cliente
        background_tasks.add_task(os.remove, temp_zip_name)

        return FileResponse(
            temp_zip_name,
            background=background_tasks,
            media_type="application/zip",
            filename="facefusion_diagnostic.zip"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar diagnóstico: {str(e)}")


class PreviewRequest(BaseModel):
    source_paths: List[str]
    target_path: str
    processors: Optional[List[str]] = ["face_swapper"]
    frame_number: Optional[int] = 0
    timestamp: Optional[float] = None
    face_swapper_weight: Optional[float] = 0.5
    face_mask_blur: Optional[float] = 0.3
    detection_threshold: Optional[float] = 0.5
    face_swapper_model: Optional[str] = "hyperswap_1a_256"
    face_swapper_pixel_boost: Optional[str] = None
    face_enhancer_model: Optional[str] = "gfpgan_1.4"
    face_enhancer_blend: Optional[int] = 80
    face_enhancer_weight: Optional[float] = 1.0
    frame_enhancer_model: Optional[str] = "span_kendata_x4"
    frame_enhancer_blend: Optional[int] = 80
    # Additional processors options
    face_editor_model: Optional[str] = None
    face_editor_eyebrow_direction: Optional[float] = None
    face_editor_eye_gaze_horizontal: Optional[float] = None
    face_editor_eye_gaze_vertical: Optional[float] = None
    face_editor_eye_open_ratio: Optional[float] = None
    face_editor_lip_open_ratio: Optional[float] = None
    face_editor_mouth_smile: Optional[float] = None
    face_editor_head_pitch: Optional[float] = None
    face_editor_head_yaw: Optional[float] = None
    face_editor_head_roll: Optional[float] = None
    age_modifier_model: Optional[str] = None
    age_modifier_direction: Optional[int] = None
    lip_syncer_model: Optional[str] = None
    lip_syncer_weight: Optional[float] = None
    expression_restorer_model: Optional[str] = None
    expression_restorer_factor: Optional[float] = None
    deep_swapper_model: Optional[str] = None
    deep_swapper_morph: Optional[int] = None
    face_debugger_items: Optional[List[str]] = None
    frame_colorizer_model: Optional[str] = None
    frame_colorizer_blend: Optional[int] = None
    frame_colorizer_size: Optional[str] = None
    background_remover_model: Optional[str] = None
    background_remover_color: Optional[List[int]] = None
    # Configurações Avançadas de Detecção e Máscara
    face_mask_types: Optional[List[str]] = None
    face_mask_padding: Optional[List[int]] = None
    face_detector_model: Optional[str] = None
    face_detector_size: Optional[str] = None
    face_detector_angles: Optional[List[int]] = None
    face_landmarker_model: Optional[str] = None
    face_landmarker_score: Optional[float] = None
    face_occluder_model: Optional[str] = None
    face_parser_model: Optional[str] = None


@router.post("/preview")
def generate_preview(request: PreviewRequest):
    """
    Gera um preview instantâneo aplicando os processadores selecionados em um único frame
    da mídia de destino, sem criar um job completo. Reutiliza a lógica nativa de preview
    do FaceFusion (mesma do Gradio UI).
    """
    import cv2
    import numpy
    import tempfile

    try:
        from facefusion.vision import read_static_image, read_static_images, read_video_frame, extract_vision_mask, merge_vision_mask, restrict_frame, unpack_resolution, detect_video_fps
        from facefusion.audio import create_empty_audio_frame
        from facefusion.processors.core import get_processors_modules
        from facefusion.filesystem import is_image, is_video, get_default_path
        from facefusion import state_manager as sm, logger as ff_logger

        # Resolver caminhos
        jobs_path = sm.get_item("jobs_path") or get_default_path('data')
        uploads_dir = os.path.abspath(os.path.join(jobs_path, "uploads"))

        resolved_source_paths = []
        for path in request.source_paths:
            if path.startswith("/api/media/upload/"):
                filename = os.path.basename(path)
                resolved_source_paths.append(validate_safe_path(os.path.join(uploads_dir, filename)))
            else:
                resolved_source_paths.append(validate_safe_path(path))

        resolved_target_path = request.target_path
        if request.target_path.startswith("/api/media/upload/"):
            filename = os.path.basename(request.target_path)
            resolved_target_path = validate_safe_path(os.path.join(uploads_dir, filename))
        else:
            resolved_target_path = validate_safe_path(request.target_path)

        # Validar que os arquivos existem e são válidos
        for sp in resolved_source_paths:
            if not os.path.exists(sp):
                raise HTTPException(status_code=400, detail=f"Arquivo source não encontrado: {sp}")
            if not (is_image(sp) or is_video(sp)):
                raise HTTPException(status_code=400, detail=f"Arquivo source com formato inválido ou corrompido: {sp}")
        if not os.path.exists(resolved_target_path):
            raise HTTPException(status_code=400, detail=f"Arquivo target não encontrado: {resolved_target_path}")
        if not (is_image(resolved_target_path) or is_video(resolved_target_path)):
            raise HTTPException(status_code=400, detail=f"Arquivo target com formato inválido ou corrompido: {resolved_target_path}")

        # Montar overrides thread-safe para o preview
        overrides = {
            'source_paths': resolved_source_paths,
            'target_path': resolved_target_path,
            'processors': request.processors or ["face_swapper"],
            'face_selector_mode': 'many',
        }
        if request.face_swapper_model is not None:
            overrides['face_swapper_model'] = request.face_swapper_model
        if request.face_swapper_pixel_boost is not None:
            overrides['face_swapper_pixel_boost'] = request.face_swapper_pixel_boost
        if request.face_swapper_weight is not None:
            overrides['face_swapper_weight'] = request.face_swapper_weight
        if request.face_mask_blur is not None:
            overrides['face_mask_blur'] = request.face_mask_blur
        if request.detection_threshold is not None:
            overrides['face_detector_score'] = request.detection_threshold
            overrides['face_landmarker_score'] = request.detection_threshold
        if request.face_enhancer_model is not None:
            overrides['face_enhancer_model'] = request.face_enhancer_model
        if request.face_enhancer_blend is not None:
            overrides['face_enhancer_blend'] = request.face_enhancer_blend
        if request.face_enhancer_weight is not None:
            overrides['face_enhancer_weight'] = request.face_enhancer_weight
        if request.frame_enhancer_model is not None:
            overrides['frame_enhancer_model'] = request.frame_enhancer_model
        if request.frame_enhancer_blend is not None:
            overrides['frame_enhancer_blend'] = request.frame_enhancer_blend
        if request.face_editor_model is not None:
            overrides['face_editor_model'] = request.face_editor_model
        if request.face_editor_eyebrow_direction is not None:
            overrides['face_editor_eyebrow_direction'] = request.face_editor_eyebrow_direction
        if request.face_editor_eye_gaze_horizontal is not None:
            overrides['face_editor_eye_gaze_horizontal'] = request.face_editor_eye_gaze_horizontal
        if request.face_editor_eye_gaze_vertical is not None:
            overrides['face_editor_eye_gaze_vertical'] = request.face_editor_eye_gaze_vertical
        if request.face_editor_eye_open_ratio is not None:
            overrides['face_editor_eye_open_ratio'] = request.face_editor_eye_open_ratio
        if request.face_editor_lip_open_ratio is not None:
            overrides['face_editor_lip_open_ratio'] = request.face_editor_lip_open_ratio
        if request.face_editor_mouth_smile is not None:
            overrides['face_editor_mouth_smile'] = request.face_editor_mouth_smile
        if request.face_editor_head_pitch is not None:
            overrides['face_editor_head_pitch'] = request.face_editor_head_pitch
        if request.face_editor_head_yaw is not None:
            overrides['face_editor_head_yaw'] = request.face_editor_head_yaw
        if request.face_editor_head_roll is not None:
            overrides['face_editor_head_roll'] = request.face_editor_head_roll
        if request.age_modifier_model is not None:
            overrides['age_modifier_model'] = request.age_modifier_model
        if request.age_modifier_direction is not None:
            overrides['age_modifier_direction'] = request.age_modifier_direction
        if request.lip_syncer_model is not None:
            overrides['lip_syncer_model'] = request.lip_syncer_model
        if request.lip_syncer_weight is not None:
            overrides['lip_syncer_weight'] = request.lip_syncer_weight
        if request.expression_restorer_model is not None:
            overrides['expression_restorer_model'] = request.expression_restorer_model
        if request.expression_restorer_factor is not None:
            overrides['expression_restorer_factor'] = request.expression_restorer_factor
        if request.deep_swapper_model is not None:
            overrides['deep_swapper_model'] = request.deep_swapper_model
        if request.deep_swapper_morph is not None:
            overrides['deep_swapper_morph'] = request.deep_swapper_morph
        if request.face_debugger_items is not None:
            overrides['face_debugger_items'] = request.face_debugger_items
        if request.frame_colorizer_model is not None:
            overrides['frame_colorizer_model'] = request.frame_colorizer_model
        if request.frame_colorizer_blend is not None:
            overrides['frame_colorizer_blend'] = request.frame_colorizer_blend
        if request.frame_colorizer_size is not None:
            overrides['frame_colorizer_size'] = request.frame_colorizer_size
        if request.background_remover_model is not None:
            overrides['background_remover_model'] = request.background_remover_model
        if request.background_remover_color is not None:
            overrides['background_remover_color'] = request.background_remover_color
        # Configurações Avançadas de Detecção e Máscara
        if request.face_mask_types is not None:
            overrides['face_mask_types'] = request.face_mask_types
        if request.face_mask_padding is not None:
            overrides['face_mask_padding'] = request.face_mask_padding
        if request.face_detector_model is not None:
            overrides['face_detector_model'] = request.face_detector_model
        if request.face_detector_size is not None:
            overrides['face_detector_size'] = request.face_detector_size
        if request.face_detector_angles is not None:
            overrides['face_detector_angles'] = request.face_detector_angles
        if request.face_landmarker_model is not None:
            overrides['face_landmarker_model'] = request.face_landmarker_model
        if request.face_landmarker_score is not None:
            overrides['face_landmarker_score'] = request.face_landmarker_score
        if request.face_occluder_model is not None:
            overrides['face_occluder_model'] = request.face_occluder_model
        if request.face_parser_model is not None:
            overrides['face_parser_model'] = request.face_parser_model

        with sm.temporary_state(overrides):
            processors = request.processors or []
            for processor_module in get_processors_modules(processors):
                if not processor_module.pre_check():
                    raise HTTPException(status_code=400, detail=f"Falha ao carregar ou baixar o modelo do processador: {processor_module.__name__}")

            # Ler frames de origem
            source_vision_frames = read_static_images(resolved_source_paths)
            source_audio_frame = create_empty_audio_frame()
            source_voice_frame = create_empty_audio_frame()

            # Ler frame de destino
            if is_image(resolved_target_path):
                reference_vision_frame = read_static_image(resolved_target_path)
                target_vision_frame = read_static_image(resolved_target_path, 'rgba')
            elif is_video(resolved_target_path):
                # Determinar o frame_number de acordo com timestamp ou frame_number fornecido
                if request.timestamp is not None:
                    fps = detect_video_fps(resolved_target_path) or 30.0
                    frame_number = int(request.timestamp * fps)
                else:
                    frame_number = request.frame_number or 0
                reference_vision_frame = read_video_frame(resolved_target_path, frame_number)
                target_vision_frame = read_video_frame(resolved_target_path, frame_number)
                if target_vision_frame is None:
                    raise HTTPException(status_code=400, detail="Não foi possível ler o frame do vídeo.")
                # Converter para RGBA se necessário
                if len(target_vision_frame.shape) == 3 and target_vision_frame.shape[2] == 3:
                    target_vision_frame = cv2.cvtColor(target_vision_frame, cv2.COLOR_BGR2BGRA)
            else:
                raise HTTPException(status_code=400, detail="Formato de target não suportado.")

            if target_vision_frame is None:
                raise HTTPException(status_code=400, detail="Frame de destino está vazio.")

            # Redimensionar temporariamente para otimizar velocidade de preview
            preview_resolution = '1024x1024'
            target_vision_frame = restrict_frame(target_vision_frame, unpack_resolution(preview_resolution))
            temp_vision_mask = extract_vision_mask(target_vision_frame)
            target_vision_frame = merge_vision_mask(target_vision_frame, temp_vision_mask)
            restricted_target_vision_frames = [ target_vision_frame[:, :, :3] ]
            temp_vision_frame = target_vision_frame.copy()

            for processor_module in get_processors_modules(processors):
                ff_logger.disable()
                if processor_module.pre_process('preview'):
                    ff_logger.enable()
                    temp_vision_frame, temp_vision_mask = processor_module.process_frame(
                    {
                        'reference_vision_frame': reference_vision_frame,
                        'source_audio_frame': source_audio_frame,
                        'source_voice_frame': source_voice_frame,
                        'source_vision_frames': source_vision_frames,
                        'target_vision_frames': restricted_target_vision_frames,
                        'temp_vision_frame': temp_vision_frame[:, :, :3],
                        'temp_vision_mask': temp_vision_mask
                    })
                ff_logger.enable()

            fill_color = sm.get_item('background_remover_fill_color')
            alpha = fill_color[-1] if fill_color else 0
            temp_vision_mask = temp_vision_mask.clip(alpha, 255)
            output_frame = merge_vision_mask(temp_vision_frame, temp_vision_mask)
            output_frame = cv2.resize(output_frame, target_vision_frame.shape[1::-1])

            # Converter para imagem JPEG BGR se necessário
            if len(output_frame.shape) == 3 and output_frame.shape[2] == 4:
                output_frame = cv2.cvtColor(output_frame, cv2.COLOR_BGRA2BGR)

            # Salvar como JPEG temporário
            outputs_dir = os.path.join(jobs_path, "outputs")
            os.makedirs(outputs_dir, exist_ok=True)
            preview_filename = f"preview_{uuid.uuid4().hex[:8]}.jpg"
            preview_path = os.path.join(outputs_dir, preview_filename)
            cv2.imwrite(preview_path, output_frame, [cv2.IMWRITE_JPEG_QUALITY, 92])

            return {
                "preview_url": f"/api/media/output/{preview_filename}",
                "status": "success"
            }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao gerar preview: {str(e)}")


class FaceAnalyzeRequest(BaseModel):
    file_path: str
    frame_number: Optional[int] = 0
    timestamp: Optional[float] = None


@router.post("/media/analyze-faces")
def analyze_faces(request: FaceAnalyzeRequest):
    """
    Detecta e classifica todos os rostos em um determinado frame/imagem.
    Retorna coordenadas, gênero, idade, raça e uma miniatura recortada.
    """
    try:
        from facefusion import state_manager as sm
        from facefusion.filesystem import is_image, is_video, get_default_path
        from facefusion.vision import read_static_image, read_video_frame, detect_video_fps
        from facefusion.face_selector import sort_and_filter_faces
        try:
            from facefusion.face_analyser import get_many_faces
        except ImportError:
            from facefusion.face_creator import get_many_faces
        from facefusion import face_detector, face_landmarker, face_recognizer, face_classifier
        import cv2
        import numpy as np

        # 1. Resolver caminhos
        jobs_path = sm.get_item("jobs_path") or get_default_path('data')
        uploads_dir = os.path.abspath(os.path.join(jobs_path, "uploads"))
        crops_dir = os.path.join(uploads_dir, "crops")
        os.makedirs(crops_dir, exist_ok=True)
        
        if request.file_path.startswith("/api/media/upload/"):
            filename = os.path.basename(request.file_path)
            resolved_path = validate_safe_path(os.path.join(uploads_dir, filename))
        else:
            resolved_path = validate_safe_path(request.file_path)
            
        if not os.path.exists(resolved_path):
            raise HTTPException(status_code=400, detail=f"Arquivo não encontrado: {resolved_path}")

        # 2. Executar pre_checks para garantir modelos baixados
        face_detector.pre_check()
        face_landmarker.pre_check()
        face_recognizer.pre_check()
        face_classifier.pre_check()

        # 3. Ler frame
        if is_image(resolved_path):
            frame = read_static_image(resolved_path)
        elif is_video(resolved_path):
            if request.timestamp is not None:
                fps = detect_video_fps(resolved_path) or 30.0
                frame_number = int(request.timestamp * fps)
            else:
                frame_number = request.frame_number or 0
            frame = read_video_frame(resolved_path, frame_number)
        else:
            raise HTTPException(status_code=400, detail="Formato de mídia não suportado para análise.")

        if frame is None:
            raise HTTPException(status_code=400, detail="Não foi possível ler o frame da mídia.")

        # 4. Detectar e classificar os rostos de forma thread-safe
        with sm.temporary_state({'face_selector_order': 'large-small'}):
            detected_faces = get_many_faces([frame])
            sorted_faces = sort_and_filter_faces([], detected_faces)

        # 5. Salvar recortes e estruturar retorno
        results = []
        for idx, face in enumerate(sorted_faces):
            h, w = frame.shape[:2]
            # Coordenadas: left, top, right, bottom
            x_min = max(0, int(face.bounding_box[0]))
            y_min = max(0, int(face.bounding_box[1]))
            x_max = min(w, int(face.bounding_box[2]))
            y_max = min(h, int(face.bounding_box[3]))
            
            crop_url = None
            if x_max > x_min and y_max > y_min:
                crop = frame[y_min:y_max, x_min:x_max]
                crop_filename = f"crop_{uuid.uuid4().hex[:12]}.jpg"
                crop_path = os.path.join(crops_dir, crop_filename)
                
                # Converter de RGBA/BGR para BGR caso necessário antes de gravar
                if len(crop.shape) == 3 and crop.shape[2] == 4:
                    crop_bgr = cv2.cvtColor(crop, cv2.COLOR_BGRA2BGR)
                else:
                    crop_bgr = crop
                    
                cv2.imwrite(crop_path, crop_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
                crop_url = f"/api/media/upload/crops/{crop_filename}"

            # Formatar a idade como string legível
            age_str = f"{face.age.start}-{face.age.stop - 1}" if hasattr(face.age, "start") else str(face.age)

            results.append({
                "index": idx,
                "bounding_box": [x_min, y_min, x_max, y_max],
                "gender": face.gender,
                "age": age_str,
                "race": face.race,
                "crop_url": crop_url
            })

        return {"faces": results}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao analisar rostos: {str(e)}")


class VideoDiagnosticRequest(BaseModel):
    video_path: str
    max_scenes: Optional[int] = 30
    threshold_content: Optional[float] = 27.0


@router.post("/video/diagnose")
def diagnose_video(request: VideoDiagnosticRequest) -> Dict[str, Any]:
    """
    Executa varredura profunda e pré-análise inteligente do vídeo alvo.
    Detecta cortes de cena (takes), rostos, dimensões fisionômicas, ruído analógico/VHS
    e perda de tracking para recomendar configurações personalizadas.
    """
    import cv2
    import numpy as np
    import uuid
    import time
    from facefusion import state_manager as sm
    from facefusion.filesystem import get_default_path
    try:
        from facefusion.face_creator import get_many_faces
    except ImportError:
        from facefusion.face_analyser import get_many_faces
    from facefusion.face_selector import sort_and_filter_faces

    jobs_path = sm.get_item("jobs_path") or get_default_path('data')
    uploads_dir = os.path.abspath(os.path.join(jobs_path, "uploads"))
    thumbs_dir = os.path.join(uploads_dir, "scene_thumbs")
    os.makedirs(thumbs_dir, exist_ok=True)

    if request.video_path.startswith("/api/media/upload/"):
        filename = os.path.basename(request.video_path)
        resolved_path = validate_safe_path(os.path.join(uploads_dir, filename))
    else:
        resolved_path = validate_safe_path(request.video_path)

    if not os.path.exists(resolved_path):
        raise HTTPException(status_code=404, detail=f"Vídeo não encontrado: {resolved_path}")

    cap = cv2.VideoCapture(resolved_path)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Não foi possível abrir o arquivo de vídeo para análise.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
    video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
    total_duration = total_frames / fps if fps > 0 else 0.0

    # 1. Segmentação Rápida de Cenas (Takes)
    # Tenta usar scenedetect, com fallback robusto para histograma HSV do OpenCV
    scenes_raw = []
    try:
        from scenedetect import detect, ContentDetector
        detector = ContentDetector(threshold=request.threshold_content or 27.0)
        detected = detect(resolved_path, detector)
        for s in detected:
            scenes_raw.append((s[0].get_seconds(), s[1].get_seconds()))
    except Exception:
        scenes_raw = []

    # Se scenedetect não achou ou falhou, divide em blocos temporais proporcionais
    if not scenes_raw:
        step_sec = max(4.0, min(15.0, total_duration / (request.max_scenes or 20)))
        t = 0.0
        while t < total_duration:
            next_t = min(total_duration, t + step_sec)
            scenes_raw.append((t, next_t))
            t = next_t

    if request.max_scenes and len(scenes_raw) > request.max_scenes:
        # Priorizar cenas distribuídas uniformemente
        stride = max(1, len(scenes_raw) // request.max_scenes)
        scenes_raw = scenes_raw[::stride][:request.max_scenes]

    scenes_diagnostics = []
    vhs_noise_flags = []
    distant_shot_flags = []
    flicker_risk_count = 0

    # 2. Diagnóstico por Tomada (Per-Take Analysis)
    for idx, (start_s, end_s) in enumerate(scenes_raw):
        duration = end_s - start_s
        mid_time = start_s + (duration * 0.5)
        frame_idx = int(mid_time * fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        # Medição de Ruído / Nitidez (Variance of Laplacian)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Salvar thumbnail leve da cena
        thumb_filename = f"scene_{uuid.uuid4().hex[:10]}.jpg"
        thumb_path = os.path.join(thumbs_dir, thumb_filename)
        thumb_img = cv2.resize(frame, (320, 180))
        cv2.imwrite(thumb_path, thumb_img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        thumb_url = f"/api/media/upload/scene_thumbs/{thumb_filename}"

        # Detecção Facial no keyframe do take
        detected_faces = []
        try:
            with sm.temporary_state({'face_selector_order': 'large-small'}):
                faces = get_many_faces([frame])
                detected_faces = sort_and_filter_faces([], faces)
        except Exception:
            detected_faces = []

        faces_count = len(detected_faces)
        primary_w = 0
        primary_h = 0
        primary_score = 0.0
        shot_type = "no_face"
        tracking_stability = "stable"

        if detected_faces:
            best_face = detected_faces[0]
            bb = best_face.bounding_box
            primary_w = max(0, int(bb[2] - bb[0]))
            primary_h = max(0, int(bb[3] - bb[1]))
            primary_score = float(getattr(best_face, 'score', 0.85))

            # Classificação do Enquadramento da Face
            # Proporção da altura da face em relação à altura total do vídeo
            face_ratio = primary_h / float(video_height) if video_height > 0 else 0.1

            if face_ratio >= 0.35:
                shot_type = "extreme_close_up"
            elif face_ratio >= 0.18:
                shot_type = "close_up"
            elif face_ratio >= 0.07:
                shot_type = "medium_shot"
            else:
                shot_type = "long_shot"

        # Detecção de ruído VHS e risco de perda de tracking
        is_low_detail = laplacian_var < 110.0
        is_distant = (shot_type == "long_shot") or (primary_h > 0 and primary_h < 75)

        if is_low_detail:
            noise_level = "high"
            vhs_noise_flags.append(True)
        elif laplacian_var < 250.0:
            noise_level = "medium"
        else:
            noise_level = "low"

        if is_distant:
            distant_shot_flags.append(True)

        if is_distant and (is_low_detail or primary_score < 0.65):
            tracking_stability = "high_risk"
            flicker_risk_count += 1
        elif is_distant or primary_score < 0.70:
            tracking_stability = "flickering_risk"
            flicker_risk_count += 1
        else:
            tracking_stability = "stable"

        # Recomendação específica para este Take
        if tracking_stability == "high_risk":
            rec_detector = "retinaface"
            rec_size = "640x640"
            rec_thresh = 0.35
            rec_dist = 0.50
            rec_smoothing = 8
            rec_angles = [0]
            rec_landmarker = 0.35
        elif tracking_stability == "flickering_risk":
            rec_detector = "retinaface"
            rec_size = "640x640"
            rec_thresh = 0.45
            rec_dist = 0.42
            rec_smoothing = 6
            rec_angles = [0]
            rec_landmarker = 0.40
        else:
            rec_detector = "yolo_face"
            rec_size = "640x640"
            rec_thresh = 0.65
            rec_dist = 0.35
            rec_smoothing = 5
            rec_angles = [0]
            rec_landmarker = 0.50

        scenes_diagnostics.append({
            "scene_index": idx + 1,
            "start_time": round(start_s, 2),
            "end_time": round(end_s, 2),
            "duration": round(duration, 2),
            "keyframe_time": round(mid_time, 2),
            "keyframe_thumb_url": thumb_url,
            "faces_detected_count": faces_count,
            "primary_face_box_size": {"width": primary_w, "height": primary_h},
            "shot_type": shot_type,
            "noise_blur_level": noise_level,
            "laplacian_var": round(laplacian_var, 1),
            "face_detector_score": round(primary_score, 2),
            "tracking_stability": tracking_stability,
            "primary_angle": 0,
            "recommended_config": {
                "face_detector_model": rec_detector,
                "face_detector_size": rec_size,
                "detection_threshold": rec_thresh,
                "reference_face_distance": rec_dist,
                "smoothing": rec_smoothing,
                "face_detector_angles": rec_angles,
                "face_landmarker_score": rec_landmarker
            }
        })

    cap.release()

    # 3. Consolidação da Recomendação Global Ideal
    has_vhs_noise = len(vhs_noise_flags) > 0
    has_distant = len(distant_shot_flags) > 0
    rationale = []

    if has_distant and has_vhs_noise:
        global_detector = "retinaface"
        global_threshold = 0.35
        global_distance = 0.48
        global_smoothing = 8
        global_landmarker = 0.40
        rationale.append("Identificadas micro-faces em planos abertos combinadas com ruído analógico de fita (VHS).")
        rationale.append("Recomendado RetinaFace com limiar de detecção reduzido para 0.35 para evitar alternância (flickering).")
        rationale.append("Tolerância biométrica (Face Distance) ampliada para 0.48 para manter o tracking ativo em tomadas distantes.")
        rationale.append("Suavização temporal ajustada para 8 para amortecer transições entre takes.")
    elif has_distant:
        global_detector = "retinaface"
        global_threshold = 0.45
        global_distance = 0.42
        global_smoothing = 6
        global_landmarker = 0.45
        rationale.append("Detectados takes distantes (planos médios e abertos).")
        rationale.append("Recomendado RetinaFace com limiar de 0.45 para estabilidade contínua.")
    elif has_vhs_noise:
        global_detector = "yolo_face"
        global_threshold = 0.50
        global_distance = 0.38
        global_smoothing = 7
        global_landmarker = 0.45
        rationale.append("Gravação com textura/ruído analógico detectada.")
        rationale.append("Suavização elevada para 7 para mitigar oscilações de grão da imagem.")
    else:
        global_detector = "yolo_face"
        global_threshold = 0.65
        global_distance = 0.35
        global_smoothing = 5
        global_landmarker = 0.50
        rationale.append("Vídeo nítido em alta definição com enquadramentos favoráveis.")
        rationale.append("Parâmetros de alta precisão mantidos (YOLO-Face, Threshold 0.65).")

    return {
        "video_path": resolved_path,
        "total_duration": round(total_duration, 2),
        "total_scenes": len(scenes_diagnostics),
        "vhs_noise_detected": has_vhs_noise,
        "distant_shots_detected": has_distant,
        "critical_flicker_scenes_count": flicker_risk_count,
        "overall_recommendation": {
            "face_detector_model": global_detector,
            "face_detector_size": "640x640",
            "detection_threshold": global_threshold,
            "reference_face_distance": global_distance,
            "smoothing": global_smoothing,
            "face_detector_angles": [0],
            "face_landmarker_score": global_landmarker,
            "rationale": rationale
        },
        "scenes": scenes_diagnostics
    }
