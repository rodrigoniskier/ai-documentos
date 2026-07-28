import path from 'node:path';
import {chromium, type Locator, type Page} from 'playwright-core';

import {config} from './config.js';
import type {Shot} from './types.js';

async function selectFirstUsefulOption(element: Locator): Promise<boolean> {
  if (!(await element.count())) return false;
  const options = await element.locator('option').evaluateAll((items) =>
    items.map((item) => ({value: (item as HTMLOptionElement).value, text: item.textContent || ''})),
  );
  const candidate = options.find((option) => option.value && !/selecione|^-+$|^\s*$/i.test(option.text));
  if (!candidate) return false;
  await element.selectOption(candidate.value);
  return true;
}

async function screenshot(page: Page, destination: string): Promise<void> {
  await page.screenshot({path: destination, fullPage: false});
}

export async function captureDemo(destinationDir: string): Promise<Record<Shot, string>> {
  const browser = await chromium.launch({
    executablePath: config.chromeExecutable,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });
  const page = await browser.newPage({viewport: {width: 1080, height: 1920}, deviceScaleFactor: 1});
  const shots: Record<Shot, string> = {
    inicio: '01-inicio.png',
    periodo: '02-periodo.png',
    componente: '03-componente.png',
    tipo: '04-tipo.png',
    formulario: '05-formulario.png',
  };

  try {
    await page.goto(config.demoUrl, {waitUntil: 'networkidle', timeout: 90000});
    await page.waitForTimeout(1200);
    await screenshot(page, path.join(destinationDir, shots.inicio));

    const selects = page.locator('select');
    if ((await selects.count()) > 0) {
      const firstSelect = selects.nth(0);
      await firstSelect.scrollIntoViewIfNeeded().catch(() => undefined);
      await selectFirstUsefulOption(firstSelect);
      await page.waitForTimeout(1200);
    }
    await screenshot(page, path.join(destinationDir, shots.periodo));

    if ((await selects.count()) > 1) {
      const secondSelect = selects.nth(1);
      await secondSelect.scrollIntoViewIfNeeded().catch(() => undefined);
      await selectFirstUsefulOption(secondSelect);
      await page.waitForTimeout(1200);
    }
    await screenshot(page, path.join(destinationDir, shots.componente));

    const typeLabel = page.getByText('Resposta Única', {exact: true}).first();
    if (await typeLabel.count()) {
      await typeLabel.scrollIntoViewIfNeeded().catch(() => undefined);
      await typeLabel.click({timeout: 5000}).catch(() => undefined);
      await page.waitForTimeout(800);
    } else {
      const firstRadio = page.locator('input[type="radio"]').first();
      if (await firstRadio.count()) await firstRadio.check().catch(() => undefined);
    }
    await screenshot(page, path.join(destinationDir, shots.tipo));

    const advance = page.getByText(/Avançar para o Formulário/i).first();
    if (await advance.count()) {
      await advance.click({timeout: 8000}).catch(() => undefined);
      await page.waitForLoadState('networkidle', {timeout: 30000}).catch(() => undefined);
      await page.waitForTimeout(1200);
    }
    await screenshot(page, path.join(destinationDir, shots.formulario));
  } finally {
    await browser.close();
  }

  return shots;
}
