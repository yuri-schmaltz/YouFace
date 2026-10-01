# Playbook de Atualização e Merge do Upstream (YouFace 3.6.1 -> 3.8.2 / 3.8.3)

Este documento orienta como manter o fork `faceYou` sincronizado com as versões mais recentes do YouFace oficial (atualmente `3.8.2` e `3.8.3`), preservando todas as inovações arquiteturais desenvolvidas (API REST FastAPI, Cockpit Web Next.js desacoplado, execução de jobs não-bloqueantes e thread-safety).

---

## 1. Mapeamento das Alterações do Upstream (3.6.1 -> 3.8.2)

Entre a versão `3.6.1` e a `3.8.2`, o YouFace oficial passou por refatorações estruturais significativas:

| Área Upstream | Alteração no 3.8.x | Impacto no faceYou | Ação Necessária |
| :--- | :--- | :--- | :--- |
| **Workflows** | `image_to_image.py` e `image_to_video.py` foram unificados em `to_image.py` e `to_video.py`. | Mínimo na API, pois o job manager abstrai os workflows. | Verificar chamadas diretas a `workflows/` se houver. |
| **Face Analyser** | `face_analyser.py` foi decomposto em `face_creator.py` e `face_tracker.py`. | Médio em `routes.py` (`POST /media/analyze-faces`). | Usar fallback condicional: se existir `face_creator`, importar dele; caso contrário, `face_analyser`. |
| **FFmpeg / FFprobe** | Adicionados `ffprobe.py`, `ffprobe_builder.py` e `frame_store.py`. | Positivo: maior precisão na contagem de frames e detecção de FPS. | Adotar nativamente sem modificações. |
| **Gradio UI** | Mudanças em `youface/uis/`. | Nenhum impacto: a interface Gradio opera isolada do frontend Next.js. | Aceitar upstream automaticamente. |
| **API REST & Frontend** | Não existem no upstream (`youface/api/` e `frontend/`). | Zero colisão de arquivos. | Nossos arquivos permanecem intactos. |

---

## 2. Passo a Passo para Executar o Merge

### Passo 1: Preparar branch limpo para o merge
```bash
git checkout -b merge/upstream-3.8.2
git fetch upstream --tags
```

### Passo 2: Iniciar o Merge da tag 3.8.2
```bash
git merge 3.8.2 -m "chore(upstream): merge YouFace 3.8.2"
```

### Passo 3: Resolução de Conflitos Esperados
Os únicos arquivos que podem ter conflitos pontuais são:
1. `requirements.txt`:
   - *Resolução:* Manter as bibliotecas de IA do upstream e adicionar as dependências da API:
     ```text
     fastapi>=0.110.0
     uvicorn[standard]>=0.28.0
     sqlalchemy>=2.0.28
     python-multipart>=0.0.9
     ```
2. `pyproject.toml` e `youface/metadata.py`:
   - *Resolução:* Atualizar para a versão correspondente `3.8.2-my.1`.
3. `youface/state_manager.py`:
   - *Resolução:* Preservar o `_STATE_LOCK` e o context manager `temporary_state()` introduzidos no faceYou.

### Passo 4: Atualização Condicional em `youface/api/routes.py`
Para garantir retrocompatibilidade com 3.6.1 e 3.8.x:
```python
try:
    from youface.face_analyser import get_many_faces
except ImportError:
    from youface.face_creator import get_many_faces
```

### Passo 5: Verificação dos Testes Automatizados
```bash
pytest tests/test_api_endpoints.py
python run_api.py --help
```

---

## 3. Estratégia de Deploy Pós-Merge
1. Build da imagem Docker unificada:
   ```bash
   docker build -t faceyou:3.8.2 .
   ```
2. Execução com aceleração CUDA:
   ```bash
   docker run --gpus all -p 8000:8000 -v $(pwd)/.jobs:/app/.jobs faceyou:3.8.2
   ```
