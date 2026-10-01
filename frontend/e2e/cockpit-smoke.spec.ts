import { test, expect } from "@playwright/test";

/**
 * Smoke E2E for the YouFace cockpit.
 *
 * Verifica o boot mínimo do cockpit sem precisar de GPU, modelos ou
 * arquivos reais. Se este teste passar, o build/serve e o roteamento
 * básico do Next.js estão funcionando.
 *
 * Para rodar localmente:
 *   1. Em um terminal: `cd .. && python run_api.py`
 *   2. Em outro: `cd frontend && npm run start` (porta 3000)
 *   3. `cd frontend && npx playwright test`
 */
test.describe("Cockpit smoke", () => {
  test("home page boots and shows engine status", async ({ page }) => {
    await page.goto("/");

    // O cockpit renderiza o título/branding
    await expect(page).toHaveTitle(/YouFace|YouFace/i, { timeout: 15_000 });

    // O status bar mostra "Engine:" (Online ou Offline)
    await expect(page.locator("text=Engine:").first()).toBeVisible({ timeout: 10_000 });

    // O ConnectionModeBadge aparece (Jobs: Conectando.../SSE/Polling/Offline)
    await expect(page.locator("text=/Jobs:/").first()).toBeVisible({ timeout: 5_000 });
  });

  test("navigates to projects tab without crash", async ({ page }) => {
    await page.goto("/");
    // Espera o cockpit estar interativo
    await page.waitForLoadState("networkidle", { timeout: 15_000 });

    // Tenta clicar no tab "Projetos" (se existir)
    const projectsTab = page.getByText(/Projetos|Projects/).first();
    if (await projectsTab.isVisible().catch(() => false)) {
      await projectsTab.click();
      // Sem crash = passou
      await expect(page).toHaveURL(/\/$/);
    }
  });

  test("config.json is served and apiUrl is parseable", async ({ page }) => {
    const response = await page.goto("/config.json");
    expect(response?.status()).toBe(200);
    const body = await response!.json();
    expect(body).toHaveProperty("apiUrl");
    // apiUrl pode ser "" (caminho relativo) ou URL absoluta
    expect(typeof body.apiUrl).toBe("string");
    expect(body).toHaveProperty("apiPathPrefix");
    expect(body.apiPathPrefix).toMatch(/^\/api/);
  });
});
