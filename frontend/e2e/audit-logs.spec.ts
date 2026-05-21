import { test, expect } from '@playwright/test'

/**
 * Regression coverage for the audit-log wiring fix:
 *
 * Before the fix, every audit log file contained only a SESSION_START event
 * with no agent_name, so the AI Logs page rendered "Unknown agent".
 *
 * After the fix, on_chat_model_start fires for the Gemini chat model and
 * AGENT_TASK_START / AGENT_TASK_END are written with agent_name="project_creator".
 */
test('AI Logs page shows project_creator after a chat turn', async ({ page }, testInfo) => {
  test.setTimeout(90_000)

  await page.goto('/')
  await page.screenshot({ path: testInfo.outputPath('01-home.png'), fullPage: true })

  // Open the chat panel
  await page.locator('button[aria-label="Open chat"]').click()

  // Type a benign message — no tool calls expected, just an LLM turn.
  const chatInput = page.getByPlaceholder('Type a message...')
  await chatInput.fill('Say hi back in one short sentence.')
  await page.getByRole('button', { name: 'Send' }).click()

  // Wait for the agent's reply to render. ChatPanel adds an assistant bubble
  // with the prose-invert class when done. Generous timeout for Gemini latency.
  await expect(
    page.locator('.prose.prose-invert').first(),
  ).toBeVisible({ timeout: 60_000 })

  await page.screenshot({ path: testInfo.outputPath('02-chat-reply.png'), fullPage: true })

  // Close the chat panel so its overlay doesn't intercept the tab click.
  await page.getByRole('button', { name: 'Close' }).click()

  // Switch to the AI Logs tab.
  await page.getByRole('button', { name: 'AI Logs' }).click()

  // The page should now render at least one session in the left panel.
  await expect(page.locator('aside')).toContainText('Sessions', { timeout: 10_000 })

  // Click the first session (most recent).
  const firstSession = page.locator('aside button').first()
  await firstSession.waitFor({ state: 'visible' })
  await firstSession.click()

  // The right panel header should now display the real agent name,
  // NOT the "Unknown agent" fallback.
  const header = page.locator('section').filter({ has: page.locator('text=tokens') }).first()

  await page.screenshot({ path: testInfo.outputPath('03-logs-page.png'), fullPage: true })

  // Hard assertion: the regression we fixed.
  await expect(page.locator('text=Unknown agent')).toHaveCount(0)
  await expect(page.getByText('project_creator').first()).toBeVisible()

  // Also assert the event timeline rendered something past SESSION_START.
  await expect(page.locator('text=AGENT_TASK_START').first()).toBeVisible()
})
