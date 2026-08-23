const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.js',
  timeout: 30_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:8765',
    colorScheme: 'dark',
    trace: 'retain-on-failure',
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {}
  },
  projects: [
    { name: 'mobile-390', use: { viewport: { width: 390, height: 844 } } },
    { name: 'tablet-768', use: { viewport: { width: 768, height: 1024 } } },
    { name: 'desktop-1024', use: { viewport: { width: 1024, height: 768 } } },
    { name: 'desktop-1440', use: { viewport: { width: 1440, height: 900 } } }
  ],
  webServer: {
    command: 'python3 -m http.server 8765 --bind 127.0.0.1 >/dev/null 2>&1',
    url: 'http://127.0.0.1:8765/index.html',
    reuseExistingServer: false,
    timeout: 30_000
  }
});
