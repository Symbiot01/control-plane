import { chromium } from 'playwright';
import { exec } from 'child_process';

const server = exec('npm run dev');
setTimeout(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log('BROWSER ERROR:', msg.text());
    }
  });
  page.on('pageerror', err => {
    console.log('PAGE ERROR:', err.message);
  });
  try {
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });
  } catch (e) {}
  await browser.close();
  server.kill();
  process.exit(0);
}, 3000);
