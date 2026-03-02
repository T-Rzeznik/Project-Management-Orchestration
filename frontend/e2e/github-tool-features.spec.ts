import { test, expect } from '@playwright/test'

/**
 * E2E tests for the new GitHub tool features:
 * - file_tree in read_github_repo result
 * - manifest_contents in read_github_repo result
 * - Updated tool step summary showing file count
 *
 * These tests mock the /api/chat endpoint so they don't need
 * a real Gemini API key or live GitHub access.
 */

const MOCK_CHAT_RESPONSE = {
  assistant_message: 'I analyzed the repository. It is a TypeScript project using React.',
  input_tokens: 100,
  output_tokens: 200,
  project_created: null,
  tool_steps: [
    {
      tool_name: 'read_github_repo',
      tool_label: 'Read GitHub Repository',
      args: { github_url: 'https://github.com/owner/myapp' },
      summary: 'Fetched owner/myapp (4 files)',
      detail: {
        owner: 'owner',
        repo: 'myapp',
        name: 'myapp',
        description: 'A sample app with no README',
        stars: 42,
        primary_language: 'TypeScript',
        open_issues_count: 3,
        languages: { TypeScript: 9000, CSS: 1000 },
        contributors: ['alice', 'bob'],
        readme_content: '',
        recent_issues: [],
        topics: ['react', 'typescript'],
        html_url: 'https://github.com/owner/myapp',
        file_tree: [
          'src/index.ts',
          'src/App.tsx',
          'src/components/Header.tsx',
          'package.json',
        ],
        manifest_contents: {
          'package.json': '{"name":"myapp","dependencies":{"react":"^18.0.0"}}',
        },
      },
      duration_ms: 350,
    },
  ],
}

test.describe('GitHub tool: file tree & manifest features', () => {
  test('chat shows tool step with file count in summary', async ({ page }) => {
    // Intercept the /api/chat endpoint and return mock data
    await page.route('**/api/chat', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE),
      })
    })

    await page.goto('/')

    // Open the chat panel
    const chatBtn = page.locator('button[aria-label="Open chat"]')
    await chatBtn.click()

    // Type a message and send
    const input = page.locator('input[placeholder="Type a message..."]')
    await input.fill('https://github.com/owner/myapp')
    await page.locator('button[aria-label="Send"]').click()

    // Wait for the assistant response to appear
    await expect(page.locator('text=I analyzed the repository')).toBeVisible({
      timeout: 10_000,
    })

    // The tool step summary should show the file count
    await expect(page.locator('text=Fetched owner/myapp (4 files)')).toBeVisible()
  })

  test('tool step detail contains file_tree when expanded', async ({ page }) => {
    await page.route('**/api/chat', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE),
      })
    })

    await page.goto('/')

    // Open chat, send message
    await page.locator('button[aria-label="Open chat"]').click()
    const input = page.locator('input[placeholder="Type a message..."]')
    await input.fill('https://github.com/owner/myapp')
    await page.locator('button[aria-label="Send"]').click()

    // Wait for tool step to appear
    await expect(page.locator('text=Read GitHub Repository')).toBeVisible({
      timeout: 10_000,
    })

    // Expand the tool step
    await page.locator('button:has-text("Read GitHub Repository")').click()

    // The detail section should contain file_tree entries
    const detailBlock = page.locator('pre', { hasText: 'file_tree' })
    await expect(detailBlock).toBeVisible()
    await expect(detailBlock).toContainText('src/index.ts')
    await expect(detailBlock).toContainText('src/App.tsx')
    await expect(detailBlock).toContainText('package.json')
  })

  test('tool step detail contains manifest_contents when expanded', async ({ page }) => {
    await page.route('**/api/chat', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE),
      })
    })

    await page.goto('/')

    // Open chat, send message
    await page.locator('button[aria-label="Open chat"]').click()
    const input = page.locator('input[placeholder="Type a message..."]')
    await input.fill('https://github.com/owner/myapp')
    await page.locator('button[aria-label="Send"]').click()

    await expect(page.locator('text=Read GitHub Repository')).toBeVisible({
      timeout: 10_000,
    })

    // Expand the tool step
    await page.locator('button:has-text("Read GitHub Repository")').click()

    // The detail section should contain manifest_contents
    const detailBlock = page.locator('pre', { hasText: 'manifest_contents' })
    await expect(detailBlock).toBeVisible()
    await expect(detailBlock).toContainText('package.json')
    await expect(detailBlock).toContainText('react')
  })

  test('empty readme_content is visible in detail', async ({ page }) => {
    await page.route('**/api/chat', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHAT_RESPONSE),
      })
    })

    await page.goto('/')

    // Open chat, send message
    await page.locator('button[aria-label="Open chat"]').click()
    const input = page.locator('input[placeholder="Type a message..."]')
    await input.fill('https://github.com/owner/myapp')
    await page.locator('button[aria-label="Send"]').click()

    await expect(page.locator('text=Read GitHub Repository')).toBeVisible({
      timeout: 10_000,
    })

    // Expand the tool step
    await page.locator('button:has-text("Read GitHub Repository")').click()

    // readme_content should be an empty string in the JSON
    const resultBlock = page.locator('pre', { hasText: 'readme_content' })
    await expect(resultBlock).toBeVisible()
    await expect(resultBlock).toContainText('"readme_content": ""')
  })
})
