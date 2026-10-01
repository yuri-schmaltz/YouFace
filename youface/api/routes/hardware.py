"""
Hardware routes: provider enumeration, device detection, telemetry, processor list.
"""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException

from youface.execution import get_available_execution_providers, detect_static_execution_devices

router = APIRouter()


@router.get("/hardware/providers")
def get_hardware_providers() -> List[str]:
    """Todos os provedores de execução (CPU/CUDA/DirectML/etc) disponíveis."""
    try:
        providers = get_available_execution_providers()
        return [str(p) for p in providers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler provedores de hardware: {str(e)}")


@router.get("/hardware/devices")
def get_hardware_devices() -> List[Dict[str, Any]]:
    """Detalhes de GPUs NVIDIA detectadas (memória, temperatura, uso)."""
    try:
        devices = detect_static_execution_devices()
        return [dict(device) for device in devices]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao detectar dispositivos NVIDIA: {str(e)}")


@router.get("/hardware/telemetry")
def get_hardware_telemetry() -> Dict[str, Any]:
    """Telemetria completa de CPU/GPU/RAM/VRAM em tempo real."""
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
            "vram_usage_percent": 0.0,
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
                "cores": psutil.cpu_count(logical=True),
            },
            "ram": {
                "total_gb": round(vm.total / (1024**3), 1),
                "used_gb": round(vm.used / (1024**3), 1),
                "free_gb": round(vm.available / (1024**3), 1),
                "usage_percent": round(vm.percent, 1),
            },
            "gpu": gpu_data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao coletar telemetria de hardware: {str(e)}")


@router.get("/processors/list")
def get_available_processors() -> List[str]:
    """Lista os 11 processadores nativos do YouFace."""
    try:
        from youface.processors.core import get_processors_modules
        processors = get_processors_modules()
        return [p.__name__ for p in processors]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar processadores: {str(e)}")
