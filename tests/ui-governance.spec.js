const { test, expect } = require('@playwright/test');

const tabs = ['监控', '历史', '策略', '回测'];

const collectConsoleErrors = (page) => {
  const errors = [];
  page.on('console', message => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', error => errors.push(String(error)));
  return errors;
};

const expectNoPageOverflow = async (page) => {
  const geometry = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth
  }));
  expect(geometry.scrollWidth).toBe(geometry.clientWidth);
};

const mockScan = {
  ok: true,
  provider: 'tickflow',
  tradeDate: '2026-08-24',
  funnel: {
    s0: { status: 'pass', text: '开机' },
    s1: { status: 'pass', text: '2只触发' },
    s2: { status: 'ready', text: '2只就绪' }
  },
  details: {
    s0: [{ name: '250日年线', val: '指数站上年线', status: '通过' }],
    s1: [{ name: '大盘跌幅', val: '1.2% >= 1%', status: '通过' }],
    s2: [{ name: '站上均线', val: '站上50日线', status: '通过' }]
  },
  signals: [
    { id: '600519', name: '贵州茅台', reason: '大盘恐慌放量，个股逆势收阳' },
    { id: '300750', name: '宁德时代', reason: '站上均线并出现趋势指标金叉' }
  ],
  warnings: []
};

const prepareLocalMode = async (page) => {
  await page.route('**/api/health', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      ok: true,
      provider: 'tickflow',
      warnings: [],
      providerOrder: ['tickflow', 'mock'],
      configured: {},
      defaultParams: {}
    })
  }));
  await page.route('**/api/a/scan', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(mockScan)
  }));
};

test.describe('UI 治理基线', () => {
  for (const tab of tabs) {
    test(`静态快照 ${tab} 页无整页溢出且控制台干净`, async ({ page }) => {
      const errors = collectConsoleErrors(page);
      await page.goto(`/index.html?mode=static&tab=${encodeURIComponent(tab)}`);
      await expect(page.locator('h1')).toBeVisible();
      await expect(page.getByText('收盘快照 · 只读', { exact: true })).toBeVisible();
      await expectNoPageOverflow(page);
      expect(errors).toEqual([]);
    });
  }

  test('静态快照的策略、历史和回测操作统一只读', async ({ page }) => {
    await page.goto('/index.html?mode=static&tab=策略');
    await expect(page.getByRole('button', { name: /(立即应用|取消应用)/ })).toBeDisabled();
    await expect(page.locator('input[type="checkbox"]').first()).toBeDisabled();
    await page.getByRole('button', { name: '历史' }).click();
    await expect(page.getByRole('button', { name: '清空历史交易记录' })).toBeDisabled();
    await page.getByRole('button', { name: '回测' }).click();
    await expect(page.getByRole('button', { name: '新建回测' })).toBeDisabled();
  });

  test('本地模式完成应用策略与扫描闭环', async ({ page }) => {
    await prepareLocalMode(page);
    await page.goto('/index.html?tab=策略');
    await expect(page.getByText('本地完整版', { exact: true })).toBeVisible();
    const switchStrategy = page.getByRole('button', { name: '切换策略' });
    if (await switchStrategy.isVisible()) await switchStrategy.click();
    await page.getByRole('button', { name: /^稳健均线跟随策略/ }).first().click();
    await page.getByRole('button', { name: '立即应用' }).click();
    await page.getByRole('button', { name: '监控' }).click();
    await expect(page.getByText('待扫描').first()).toBeVisible();
    await page.getByRole('button', { name: '执行扫描' }).click();
    await expect(page.getByText('2 只', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('贵州茅台', { exact: true }).filter({ visible: true })).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test('对话框支持 Esc 关闭并恢复触发点焦点', async ({ page }) => {
    await prepareLocalMode(page);
    await page.goto('/index.html?tab=监控');
    await page.getByRole('button', { name: '执行扫描' }).click();
    const stockButton = page.getByRole('button', { name: '600519' }).first();
    await stockButton.click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toBeHidden();
    await expect(stockButton).toBeFocused();
  });

  test('应用内危险确认可取消且不误删', async ({ page }) => {
    await prepareLocalMode(page);
    await page.goto('/index.html?tab=回测');
    const recordName = page.getByText('强中强2025全年回测', { exact: true });
    const before = await recordName.count();
    if (page.viewportSize().width < 768) {
      await page.locator('article').filter({ hasText: '强中强2025全年回测' }).getByRole('button', { name: '删除', exact: true }).click();
    } else {
      await page.getByRole('button', { name: /删除强中强2025全年回测/ }).click();
    }
    await expect(page.getByRole('dialog', { name: '删除回测记录' })).toBeVisible();
    await page.getByRole('button', { name: '取消' }).click();
    await expect(recordName).toHaveCount(before);
  });
});
