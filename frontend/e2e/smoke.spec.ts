import { test, expect } from '@playwright/test'

test.describe('App smoke test', () => {
  test('homepage loads without errors', async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', (err) => errors.push(err.message))

    await page.goto('/')
    await expect(page.locator('text=Project Management')).toBeVisible()
    expect(errors).toEqual([])
  })

  test('nav tabs are visible and clickable', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('button', { hasText: 'Projects' })).toBeVisible()
    await expect(page.locator('button', { hasText: 'AI Logs' })).toBeVisible()

    await page.click('button:has-text("AI Logs")')
    await page.click('button:has-text("Projects")')
  })

  test('chat button is visible and opens panel', async ({ page }) => {
    await page.goto('/')
    const chatBtn = page.locator('button[aria-label="Open chat"]')
    await expect(chatBtn).toBeVisible()
    await chatBtn.click()
    // Chat button should disappear once panel is open
    await expect(chatBtn).not.toBeVisible()
  })

  test('no console errors on page load', async ({ page }) => {
    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text())
      }
    })

    await page.goto('/')
    // Wait for any async rendering
    await page.waitForTimeout(2000)
    expect(consoleErrors).toEqual([])
  })
})
