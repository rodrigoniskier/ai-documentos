import path from 'node:path';

import {chromium, type Locator, type Page} from 'playwright-core';

import {config} from './config.js';
import type {DemoCapture, Shot} from './types.js';

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

async function installPointer(page: Page): Promise<void> {
  await page.evaluate(() => {
    const pointer = document.createElement('div');
    pointer.id = 'rn-demo-pointer';
    pointer.style.cssText = [
      'position:fixed', 'left:40px', 'top:40px', 'width:34px', 'height:34px',
      'border:5px solid #ffd21f', 'border-radius:50%', 'box-shadow:0 0 0 7px rgba(11,78,162,.28)',
      'z-index:2147483647', 'pointer-events:none', 'transition:left .45s ease,top .45s ease,transform .18s ease',
      'transform:translate(-50%,-50%)',
    ].join(';');
    document.body.appendChild(pointer);
  });
}

async function pointTo(page: Page, locator: Locator, click = false): Promise<void> {
  if (!(await locator.count())) return;
  await locator.scrollIntoViewIfNeeded().catch(() => undefined);
  const box = await locator.boundingBox();
  if (!box) return;
  await page.evaluate(({x, y, click}) => {
    const pointer = document.getElementById('rn-demo-pointer') as HTMLDivElement | null;
    if (!pointer) return;
    pointer.style.left = `${x}px`;
    pointer.style.top = `${y}px`;
    if (click) {
      pointer.style.transform = 'translate(-50%,-50%) scale(.72)';
      setTimeout(() => { pointer.style.transform = 'translate(-50%,-50%) scale(1)'; }, 180);
    }
  }, {x: box.x + box.width / 2, y: box.y + box.height / 2, click});
  await page.waitForTimeout(click ? 500 : 850);
}

async function fillVisibleFields(page: Page): Promise<void> {
  const textareas = page.locator('textarea:visible');
  const textareaValues = [
    'Durante uma resposta inflamatória aguda, qual alteração vascular favorece a saída de proteínas plasmáticas para o tecido?',
    'O aumento transitório da permeabilidade vascular nas vênulas pós-capilares.',
    'A redução permanente do fluxo sanguíneo arterial.',
    'A inibição completa da migração leucocitária.',
    'A ausência de mediadores químicos no foco inflamatório.',
  ];
  const textareaCount = Math.min(await textareas.count(), textareaValues.length);
  for (let index = 0; index < textareaCount; index += 1) {
    const field = textareas.nth(index);
    await pointTo(page, field, true);
    await field.fill(textareaValues[index] || 'Conteúdo demonstrativo').catch(() => undefined);
    await page.waitForTimeout(650);
  }

  const textInputs = page.locator('input[type="text"]:visible');
  const inputValues = ['Inflamação aguda', 'Patologia', 'Dificuldade intermediária', 'Questão demonstrativa'];
  const inputCount = Math.min(await textInputs.count(), inputValues.length);
  for (let index = 0; index < inputCount; index += 1) {
    const field = textInputs.nth(index);
    const current = await field.inputValue().catch(() => '');
    if (current) continue;
    await pointTo(page, field, true);
    await field.fill(inputValues[index] || 'Demonstração').catch(() => undefined);
    await page.waitForTimeout(500);
  }
}

export async function captureDemo(destinationDir: string): Promise<DemoCapture> {
  const browser = await chromium.launch({
    executablePath: config.chromeExecutable,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });
  const context = await browser.newContext({
    viewport: {width: 1440, height: 900},
    deviceScaleFactor: 1,
    recordVideo: {dir: destinationDir, size: {width: 1440, height: 900}},
  });
  const page = await context.newPage();
  const recordedVideo = page.video();
  const shots: Record<Shot, string> = {
    inicio: '01-inicio.png',
    periodo: '02-periodo.png',
    componente: '03-componente.png',
    tipo: '04-tipo.png',
    formulario: '05-formulario.png',
  };
  const videoName = '06-demonstracao.webm';

  try {
    await page.goto(config.demoUrl, {waitUntil: 'networkidle', timeout: 90000});
    await installPointer(page);
    await page.waitForTimeout(1800);
    await screenshot(page, path.join(destinationDir, shots.inicio));

    const selects = page.locator('select');
    if ((await selects.count()) > 0) {
      const firstSelect = selects.nth(0);
      await pointTo(page, firstSelect, true);
      await selectFirstUsefulOption(firstSelect);
      await page.waitForTimeout(1700);
    }
    await screenshot(page, path.join(destinationDir, shots.periodo));

    if ((await selects.count()) > 1) {
      const secondSelect = selects.nth(1);
      await pointTo(page, secondSelect, true);
      await selectFirstUsefulOption(secondSelect);
      await page.waitForTimeout(1800);
    }
    await screenshot(page, path.join(destinationDir, shots.componente));

    const typeLabel = page.getByText('Resposta Única', {exact: true}).first();
    if (await typeLabel.count()) {
      await pointTo(page, typeLabel, true);
      await typeLabel.click({timeout: 5000}).catch(() => undefined);
      await page.waitForTimeout(1300);
    } else {
      const firstRadio = page.locator('input[type="radio"]').first();
      if (await firstRadio.count()) {
        await pointTo(page, firstRadio, true);
        await firstRadio.check().catch(() => undefined);
      }
    }
    await screenshot(page, path.join(destinationDir, shots.tipo));

    const advance = page.getByText(/Avançar para o Formulário/i).first();
    if (await advance.count()) {
      await pointTo(page, advance, true);
      await advance.click({timeout: 8000}).catch(() => undefined);
      await page.waitForLoadState('networkidle', {timeout: 30000}).catch(() => undefined);
      await page.waitForTimeout(1800);
      await installPointer(page).catch(() => undefined);
      await fillVisibleFields(page);
    }
    await screenshot(page, path.join(destinationDir, shots.formulario));
    await page.waitForTimeout(2200);
  } finally {
    await page.close().catch(() => undefined);
    await context.close().catch(() => undefined);
    if (recordedVideo) await recordedVideo.saveAs(path.join(destinationDir, videoName)).catch(() => undefined);
    await browser.close();
  }

  return {shots, video: videoName};
}
