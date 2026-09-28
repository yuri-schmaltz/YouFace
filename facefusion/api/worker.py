import time
import threading
from sqlalchemy import asc
from facefusion.api.database import SessionLocal, JobModel
from facefusion.jobs import job_runner
from facefusion.core import process_step
from facefusion import state_manager, logger


_worker_stop_event = threading.Event()
_current_running_job_id = None
_current_job_lock = threading.Lock()


def get_current_job_id():
    with _current_job_lock:
        return _current_running_job_id


def set_current_job_id(job_id):
    global _current_running_job_id
    with _current_job_lock:
        _current_running_job_id = job_id


def cancel_running_job(job_id: str) -> bool:
    """
    Sinaliza ao process_manager do FaceFusion para abortar o job atualmente em execução.
    """
    with _current_job_lock:
        if _current_running_job_id == job_id:
            from facefusion import process_manager
            process_manager.stop()
            logger.warning(f"[Worker] Sinal de cancelamento enviado para o job {job_id}.", __name__)
            return True
    return False


def start_worker():
    global _worker_stop_event
    _worker_stop_event.clear()
    thread = threading.Thread(target=worker_loop, daemon=True)
    thread.start()


def stop_worker():
    global _worker_stop_event
    logger.info("[Worker] Sinalizando encerramento para o worker loop...", __name__)
    _worker_stop_event.set()


def worker_loop():
    logger.info("[Worker] Inicializando fila sequencial no segundo plano...", __name__)
    
    # Garantir que JOBS_PATH e o state_manager estejam devidamente carregados nesta thread
    try:
        from facefusion import state_manager
        from facefusion.program import create_program
        from facefusion.args import apply_args
        from facefusion.jobs import job_manager
        from facefusion.filesystem import get_default_path

        program = create_program()
        args = vars(program.parse_args(['run']))
        apply_args(args, state_manager.init_item)
        
        jobs_path = state_manager.get_item('jobs_path') or get_default_path('data')
        job_manager.init_jobs(jobs_path)
        logger.info(f"[Worker] Caminho de jobs inicializado: {jobs_path}", __name__)
    except Exception as e:
        logger.error(f"[Worker] Erro crítico ao inicializar parâmetros: {str(e)}", __name__)

    # Recuperação de jobs travados em 'processing' devido a desligamento ou reinício
    try:
        db = SessionLocal()
        stuck_jobs = db.query(JobModel).filter_by(status="processing").all()
        for stuck_job in stuck_jobs:
            logger.error(f"[Worker] Recuperando job travado {stuck_job.id} para status 'failed'.", __name__)
            stuck_job.status = "failed"
            stuck_job.progress = 0
            stuck_job.error_message = "O servidor foi reiniciado enquanto esta tarefa estava sendo processada."
        db.commit()
        db.close()
    except Exception as e:
        logger.error(f"[Worker] Erro ao recuperar jobs travados: {str(e)}", __name__)

    logger.info("[Worker] Loop de escuta de tarefas iniciado.", __name__)
    while not _worker_stop_event.is_set():
        try:
            db = SessionLocal()
            # Buscar o job mais antigo na fila
            job = db.query(JobModel).filter_by(status="queued").order_by(asc(JobModel.created_at)).first()
            
            if job:
                job_id = job.id
                logger.info(f"[Worker] Selecionado job para processamento: {job_id}", __name__)
                
                # Atualizar estado para processando
                job.status = "processing"
                job.progress = 15
                db.commit()
                db.close()
                
                try:
                    set_current_job_id(job_id)
                    from facefusion.logger import set_job_context
                    set_job_context(job_id)

                    # Garantir que o comando está configurado para executar
                    state_manager.set_item('command', 'job-run')
                    
                    # Chamar o pipeline de execução nativo do FaceFusion
                    success = job_runner.run_job(job_id, process_step)
                    
                    db = SessionLocal()
                    job_to_update = db.query(JobModel).filter_by(id=job_id).first()
                    if job_to_update:
                        # Se já foi marcado como cancelado, não sobrescrever para completed
                        if job_to_update.status == "failed" and "Cancelado" in (job_to_update.error_message or ""):
                            logger.warning(f"[Worker] Job {job_id} foi cancelado pelo usuário.", __name__)
                        elif success:
                            job_to_update.status = "completed"
                            job_to_update.progress = 100
                            logger.info(f"[Worker] Job {job_id} concluído com sucesso.", __name__)
                        else:
                            job_to_update.status = "failed"
                            job_to_update.progress = 0
                            job_to_update.error_message = "Erro de execução nos passos do FaceFusion."
                            logger.info(f"[Worker] Job {job_id} falhou nos passos de execução.", __name__)
                        db.commit()
                        
                        # Sincronizar status com project.json na pasta Vídeos
                        if job_to_update.output_path:
                            try:
                                import json
                                proj_dir = os.path.dirname(os.path.dirname(job_to_update.output_path))
                                meta_path = os.path.join(proj_dir, "project.json")
                                if os.path.exists(meta_path):
                                    with open(meta_path, "r", encoding="utf-8") as pf:
                                        meta = json.load(pf)
                                    meta["status"] = job_to_update.status
                                    if job_to_update.error_message:
                                        meta["error_message"] = job_to_update.error_message
                                    with open(meta_path, "w", encoding="utf-8") as pf:
                                        json.dump(meta, pf, indent=2, ensure_ascii=False)
                            except Exception:
                                pass
                    db.close()
                    
                except Exception as e:
                    import traceback
                    error_trace = traceback.format_exc()
                    logger.error(f"[Worker] Falha ao rodar o job {job_id}: {str(e)}\n{error_trace}", __name__)
                    
                    db = SessionLocal()
                    job_to_update = db.query(JobModel).filter_by(id=job_id).first()
                    if job_to_update:
                        if not (job_to_update.status == "failed" and "Cancelado" in (job_to_update.error_message or "")):
                            job_to_update.status = "failed"
                            job_to_update.progress = 0
                            job_to_update.error_message = f"Exceção: {str(e)}\n{error_trace}"
                            db.commit()
                            
                            # Sincronizar status com project.json na pasta Vídeos
                            if job_to_update.output_path:
                                try:
                                    import json
                                    proj_dir = os.path.dirname(os.path.dirname(job_to_update.output_path))
                                    meta_path = os.path.join(proj_dir, "project.json")
                                    if os.path.exists(meta_path):
                                        with open(meta_path, "r", encoding="utf-8") as pf:
                                            meta = json.load(pf)
                                        meta["status"] = job_to_update.status
                                        meta["error_message"] = job_to_update.error_message
                                        with open(meta_path, "w", encoding="utf-8") as pf:
                                            json.dump(meta, pf, indent=2, ensure_ascii=False)
                                except Exception:
                                    pass
                    db.close()
                finally:
                    set_current_job_id(None)
                    from facefusion.logger import set_job_context
                    set_job_context('')
            else:
                db.close()
                _worker_stop_event.wait(1)
        except Exception as e:
            logger.error(f"[Worker] Erro no loop de execução do worker: {str(e)}", __name__)
            _worker_stop_event.wait(2)

