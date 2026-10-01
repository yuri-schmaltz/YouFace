"""
Projects endpoints (R2 split).

Routes:
- GET    /projects                                  — list all project folders
- POST   /projects                                  — create a new project folder
- GET    /projects/media/{project_name}/{folder}/{filename:path}
- POST   /projects/{project_name}/open-folder       — open in OS file manager
- DELETE /projects/{project_name}                   — delete project + its jobs

Extracted from youface/api/routes.py (R2 of tech-debt inventory).
All shared helpers come from youface.api.routes.common.
"""
import os
import sys
import json
import subprocess
import shutil
import platform
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from youface.api.database import get_db, JobModel
from youface.api.routes.common import (
    get_user_projects_dir,
    validate_safe_path,
)

router = APIRouter()


@router.get("/projects")
def list_projects() -> List[Dict[str, Any]]:
    """
    Lista todas as pastas de projetos criadas em ~/Vídeos/YouFace_Projects/
    com seus respectivos arquivos de origem, destino, produto final e metadados.
    """
    try:
        projects_dir = get_user_projects_dir()
        projects = []

        if not os.path.exists(projects_dir):
            return []

        for entry in os.scandir(projects_dir):
            if entry.is_dir():
                proj_name = entry.name
                proj_path = entry.path
                meta_path = os.path.join(proj_path, "project.json")
                meta = {}
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                    except Exception:
                        pass

                source_dir = os.path.join(proj_path, "source")
                target_dir = os.path.join(proj_path, "target")
                output_dir = os.path.join(proj_path, "output")

                sources = [f for f in os.listdir(source_dir)] if os.path.exists(source_dir) else []
                targets = [f for f in os.listdir(target_dir)] if os.path.exists(target_dir) else []
                outputs = [f for f in os.listdir(output_dir)] if os.path.exists(output_dir) else []

                has_output = len(outputs) > 0
                status = meta.get("status") or ("completed" if has_output else "queued")

                first_source = sources[0] if sources else None
                first_target = targets[0] if targets else None
                first_output = outputs[0] if outputs else None

                source_url = f"/api/projects/media/{proj_name}/source/{first_source}" if first_source else None
                target_url = f"/api/projects/media/{proj_name}/target/{first_target}" if first_target else None
                output_url = f"/api/projects/media/{proj_name}/output/{first_output}" if first_output else None

                ctime = os.path.getctime(proj_path)
                created_at = meta.get("created_at") or datetime.datetime.fromtimestamp(ctime).isoformat()

                projects.append({
                    "id": meta.get("id") or proj_name,
                    "name": proj_name,
                    "project_dir": proj_path,
                    "created_at": created_at,
                    "status": status,
                    "source_files": sources,
                    "target_files": targets,
                    "output_files": outputs,
                    "source_url": source_url,
                    "target_url": target_url,
                    "output_url": output_url,
                    "processors": meta.get("processors", ["face_swapper"])
                })

        projects.sort(key=lambda p: p["created_at"], reverse=True)
        return projects
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar projetos: {str(e)}")


class ProjectCreateInput(BaseModel):
    name: str
    description: Optional[str] = ""
    output_format: Optional[str] = "mp4"
    output_video_encoder: Optional[str] = "libx264"
    output_video_quality: Optional[str] = "High"
    output_audio_encoder: Optional[str] = "aac"
    output_audio_quality: Optional[int] = 80
    output_audio_volume: Optional[int] = 100
    processors: Optional[List[str]] = ["face_swapper"]


@router.post("/projects")
def create_project_endpoint(request: ProjectCreateInput) -> Dict[str, Any]:
    """
    Cria uma nova estrutura de projeto com subpastas e grava as configurações em project.json em ~/Vídeos/YouFace_Projects/.
    """
    try:
        projects_dir = get_user_projects_dir()
        raw_name = request.name.strip()
        if not raw_name:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
            raw_name = f"Projeto_{now_str}"
        
        safe_name = "".join(c if c.isalnum() or c in ("-", "_", " ") else "_" for c in raw_name).strip()
        safe_name = safe_name.replace(" ", "_")
        
        proj_dir = os.path.join(projects_dir, safe_name)
        if os.path.exists(proj_dir):
            now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = f"{safe_name}_{now_str}"
            proj_dir = os.path.join(projects_dir, safe_name)
            
        source_dir = os.path.join(proj_dir, "source")
        target_dir = os.path.join(proj_dir, "target")
        output_dir = os.path.join(proj_dir, "output")
        
        os.makedirs(source_dir, exist_ok=True)
        os.makedirs(target_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)
        
        meta = {
            "id": f"proj-{uuid.uuid4().hex[:8]}",
            "name": safe_name,
            "description": request.description or "",
            "created_at": datetime.datetime.now().isoformat(),
            "status": "created",
            "processors": request.processors or ["face_swapper"],
            "output_format": request.output_format or "mp4",
            "output_video_encoder": request.output_video_encoder or "libx264",
            "output_video_quality": request.output_video_quality or "High",
            "output_audio_encoder": request.output_audio_encoder or "aac",
            "output_audio_quality": request.output_audio_quality or 80,
            "output_audio_volume": request.output_audio_volume or 100,
            "source_files": [],
            "target_files": [],
            "output_files": []
        }
        
        with open(os.path.join(proj_dir, "project.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
            
        return {
            "status": "success",
            "project": {
                **meta,
                "project_dir": proj_dir,
                "source_url": None,
                "target_url": None,
                "output_url": None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar projeto: {str(e)}")




@router.get("/projects/media/{project_name}/{folder}/{filename:path}")
def get_project_media(project_name: str, folder: str, filename: str):
    """
    Retorna com segurança os arquivos de mídia (source, target, output) pertencentes a um projeto na pasta Vídeos.
    """
    if folder not in ("source", "target", "output"):
        raise HTTPException(status_code=400, detail="Pasta de projeto inválida.")

    proj_dir = os.path.join(get_user_projects_dir(), project_name)
    file_path = validate_safe_path(os.path.join(proj_dir, folder, filename))

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Arquivo de mídia não encontrado no projeto.")

    return FileResponse(file_path)


@router.post("/api/projects/{project_name}/open-folder")
@router.post("/projects/{project_name}/open-folder")
def open_project_folder(project_name: str) -> Dict[str, Any]:
    """
    Abre o diretório do projeto no explorador de arquivos gráfico do sistema operacional (ex: Dolphin / Nautilus).
    """
    proj_dir = os.path.join(get_user_projects_dir(), project_name)
    validate_safe_path(proj_dir)

    if not os.path.exists(proj_dir):
        raise HTTPException(status_code=404, detail="Pasta do projeto não encontrada no disco.")

    try:
        import subprocess
        if sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", proj_dir])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", proj_dir])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", proj_dir])
        return {"status": "success", "message": f"Pasta do projeto '{project_name}' aberta no explorador de arquivos."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao abrir pasta do projeto: {str(e)}")


@router.delete("/projects/{project_name}")
def delete_project(project_name: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Exclui a pasta completa do projeto em ~/Vídeos/YouFace_Projects/ e remove jobs associados.
    """
    proj_dir = os.path.join(get_user_projects_dir(), project_name)
    validate_safe_path(proj_dir)

    if not os.path.exists(proj_dir):
        raise HTTPException(status_code=404, detail="Pasta do projeto não encontrada no disco.")

    try:
        import shutil
        shutil.rmtree(proj_dir)
        # Excluir jobs associados do banco
        jobs = db.query(JobModel).filter_by(project_name=project_name).all()
        for j in jobs:
            db.delete(j)
        db.commit()
        return {"status": "success", "message": f"Projeto '{project_name}' excluído com sucesso."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao excluir projeto: {str(e)}")

