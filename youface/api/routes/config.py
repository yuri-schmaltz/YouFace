"""
Config routes: GET/POST /api/config.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from youface import state_manager

router = APIRouter()


@router.get("/config")
def get_current_config() -> Dict[str, Any]:
    """Retorna as configurações e o estado global atual."""
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
    """Atualiza as configurações do estado em memória (não persiste)."""
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
