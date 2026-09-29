/**
 * English (default) translations.
 * All keys MUST be present here — other locales fall back to this one.
 */
const en: Record<string, string> = {
  // App chrome
  "app.title": "YouFace Studio",
  "app.tagline": "Decoupled face-swap cockpit",

  // Navigation
  "nav.studio": "Studio",
  "nav.projects": "Projects",
  "nav.diagnostics": "Diagnostics",
  "nav.language": "Language",

  // Common actions
  "action.cancel": "Cancel",
  "action.save": "Save",
  "action.delete": "Delete",
  "action.refresh": "Refresh",
  "action.upload": "Upload",
  "action.download": "Download",
  "action.start": "Start",
  "action.retry": "Retry",

  // Job states
  "job.status.queued": "Queued",
  "job.status.processing": "Processing",
  "job.status.completed": "Completed",
  "job.status.failed": "Failed",
  "job.status.cancelled": "Cancelled",

  // Studio
  "studio.source.label": "Source face",
  "studio.target.label": "Target video",
  "studio.processors.label": "Processors",
  "studio.advanced.label": "Advanced",

  // Errors
  "error.network": "Network error: {message}",
  "error.unauthorized": "Authentication required. Check your API key.",
  "error.not_found": "Not found: {resource}",
  "error.generic": "Something went wrong: {message}",
};

export default en;
