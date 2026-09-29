/**
 * Brazilian Portuguese translations.
 * Any key missing here falls back to English (see i18n/index.ts).
 */
const ptBR: Record<string, string> = {
  // App chrome
  "app.title": "YouFace Studio",
  "app.tagline": "Cockpit desacoplado de face-swap",

  // Navigation
  "nav.studio": "Estúdio",
  "nav.projects": "Projetos",
  "nav.diagnostics": "Diagnóstico",
  "nav.language": "Idioma",

  // Common actions
  "action.cancel": "Cancelar",
  "action.save": "Salvar",
  "action.delete": "Excluir",
  "action.refresh": "Atualizar",
  "action.upload": "Enviar",
  "action.download": "Baixar",
  "action.start": "Iniciar",
  "action.retry": "Tentar novamente",

  // Job states
  "job.status.queued": "Na fila",
  "job.status.processing": "Processando",
  "job.status.completed": "Concluído",
  "job.status.failed": "Falhou",
  "job.status.cancelled": "Cancelado",

  // Studio
  "studio.source.label": "Rosto de origem",
  "studio.target.label": "Vídeo de destino",
  "studio.processors.label": "Processadores",
  "studio.advanced.label": "Avançado",

  // Errors
  "error.network": "Erro de rede: {message}",
  "error.unauthorized": "Autenticação necessária. Verifique sua API key.",
  "error.not_found": "Não encontrado: {resource}",
  "error.generic": "Algo deu errado: {message}",
};

export default ptBR;
