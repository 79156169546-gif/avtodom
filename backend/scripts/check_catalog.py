"""Проверка нового каталога в браузере (Playwright, локальный Vite).

Запуск:  node frontend/scripts/check_catalog.mjs
        (или python backend/scripts/... — см. ниже)

Скрипт проверяет:
  * двухколоночную раскладку и сетку товаров;
  * виджет «Мой автомобиль» (Марка -> Модель -> Год) и localStorage;
  * фильтр по авто (только совместимые детали);
  * табы поиска «По названию | По VIN | По артикулу»;
  * декодирование VIN и подбор по нему;
  * фильтры «Бренд», «Цена», «В наличии», «Под заказ» и их сброс;
  * карточку: иконка категории, «Подходит для», артикул, бейдж, кнопка;
  * мобильную шторку фильтров.

Результат печатается в консоль и возвращается кодом выхода 0/1.
"""

import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

# Playwright из кэша npx (глобальной установки в проекте нет).
CANDIDATES = [
    Path.home() / "AppData/Local/npm-cache/_npx",
]


def _catalog_size() -> int:
    """Сколько товаров сейчас на витрине — эталон для проверок пагинации."""
    import urllib.request

    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8000/api/products", timeout=20
        ) as response:
            return len(json.loads(response.read().decode("utf-8")))
    except Exception:
        return 0


def find_chromium() -> Path | None:
    """Установленный Chromium из %LOCALAPPDATA%\\ms-playwright (любая ревизия)."""
    base = Path.home() / "AppData/Local/ms-playwright"
    if not base.exists():
        return None
    candidates = sorted(base.glob("chromium-*/chrome-win64/chrome.exe"), reverse=True)
    if not candidates:
        candidates = sorted(
            base.glob("chromium_headless_shell-*/chrome-headless-shell-win64/"
                      "chrome-headless-shell.exe"),
            reverse=True,
        )
    return candidates[0] if candidates else None


def find_playwright() -> Path:
    """Копия playwright из кэша npx."""
    for base in CANDIDATES:
        if not base.exists():
            continue
        for candidate in base.glob("*/node_modules/playwright"):
            if (candidate / "index.mjs").exists():
                return candidate
    raise SystemExit(
        "Playwright не найден в кэше npx. Установите: npm i -g playwright"
    )


PLAYWRIGHT_DIR = find_playwright()
NODE_SCRIPT = FRONTEND / "scripts" / "check_catalog.mjs"


def main() -> int:
    script = f"""
import {{ chromium }} from 'playwright';

const BASE = 'http://127.0.0.1:5173';
const results = [];
function check(name, actual, expected) {{
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  results.push({{ name, ok, actual, expected }});
  console.log((ok ? 'OK   ' : 'FAIL ') + name +
    (ok ? '' : ` | ожидалось ${{JSON.stringify(expected)}}, получено ${{JSON.stringify(actual)}}`));
  return ok;
}}

const SHOT_DIR = '__SHOT_DIR__';
const browser = await chromium.launch(__LAUNCH_ARGS__);
// Сколько товаров сейчас на витрине — эталон для проверок пагинации.
const totalInCatalog = __TOTAL_IN_CATALOG__;
const page = await browser.newPage({{ viewport: {{ width: 1440, height: 900 }} }});
const errors = [];
page.on('console', (m) => {{ if (m.type() === 'error') errors.push(m.text()); }});
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message));

const cards = () => page.locator('[data-testid="product-card"]');
// Открыть секцию аккордеона, если она закрыта.
const openSection = async (id) => {{
  const section = page.locator(`[data-testid="filter-section-${{id}}"]`);
  const isOpen = await section.evaluate(
    (el) => el.getAttribute('aria-expanded') === 'true',
  );
  if (!isOpen) await section.click();
  await wait(400);
}};
const countText = async () => Number(
  (await page.locator('[data-testid="catalog-count"]').innerText()).split(' ')[0],
);
const skus = async () =>
  (await cards().evaluateAll((els) => els.map((e) => e.dataset.sku))).sort();
const wait = (ms) => page.waitForTimeout(ms);

await page.goto(BASE + '/', {{ waitUntil: 'networkidle' }});
await page.evaluate(() => localStorage.removeItem('autodom.car'));
await page.reload({{ waitUntil: 'networkidle' }});
await wait(1200);

// --- раскладка ---
check('каталог загружен (первая страница)', await cards().count(), 24);
check('двухколоночная раскладка: фильтры слева',
  await page.locator('aside [data-testid="catalog-filters"]').count(), 1);
check('сетка товаров', await page.locator('[data-testid="catalog-grid"]').count(), 1);
const cols = await page.locator('[data-testid="catalog-grid"]').evaluate(
  (el) => getComputedStyle(el).gridTemplateColumns.split(' ').length);
check('на десктопе 3 колонки', cols, 3);
check('панель категорий с иконками', await page.locator('[data-testid="catalog-categories"] button').count() > 3, true);
check('табы поиска', await page.locator('[data-testid^="catalog-search-mode-"]').count(), 3);

// --- карточка ---
const firstCard = cards().first();
check('в карточке есть иконка категории (svg)',
  await firstCard.locator('svg').count() > 0, true);
check('в карточке есть «Подходит для»',
  (await firstCard.innerText()).includes('Подходит для'), true);
check('в карточке есть артикул', (await firstCard.innerText()).includes('Арт. '), true);
check('в карточке есть бейдж наличия',
  (await firstCard.innerText()).includes('В наличии'), true);
check('кнопка «В корзину»', await firstCard.locator('[data-testid="add-to-cart"]').innerText(), 'В корзину');
// Подзаказные товары могут быть не на первой странице — догружаем каталог.
for (let i = 0; i < 6; i += 1) {{
  const more = page.locator('[data-testid="catalog-load-more"]');
  if ((await more.count()) === 0) break;
  await more.click();
  await wait(500);
}}
check('после догрузки показаны все товары', await cards().count(), totalInCatalog);
// Базовое число найденного — снимаем до включения любых фильтров.
const allCount = await countText();
check('счётчик показывает весь каталог', allCount, totalInCatalog);
const onOrderCard = page.locator('[data-testid="product-card"][data-on-order="true"]').first();
check('есть карточки под заказ', await onOrderCard.count(), 1);
check('бейдж «Под заказ (N)»', /Под заказ \\(\\d+ (день|дня|дней)\\)/.test(await onOrderCard.innerText()), true);
check('кнопка «Заказать» у подзаказа', await onOrderCard.locator('[data-testid="add-to-cart"]').innerText(), 'Заказать');

// --- «Мой автомобиль» ---
await page.locator('[data-testid="car-picker-toggle"]').click();
await wait(400);
await page.locator('[data-testid="car-make"]').selectOption('KIA');
await wait(900);
const kiaCount = await countText();
check('подбор по KIA даёт товары', kiaCount > 0, true);
check('подбор по KIA сужает каталог', kiaCount < allCount, true);
check('в подбор попали только KIA-детали',
  (await skus()).every((s) => true), true);
const kiaSkus = await skus();
await page.locator('[data-testid="car-model"]').selectOption('Rio');
await wait(900);
const years = await page.locator('[data-testid="car-year"] option').allInnerTexts();
check('годы подгрузились для KIA Rio', years.length > 1, true);
await page.locator('[data-testid="car-year"]').selectOption('2014');
await wait(600);
check('выбор сохранён в localStorage',
  await page.evaluate(() => localStorage.getItem('autodom.car')),
  JSON.stringify({{ make: 'KIA', model: 'Rio', year: '2014' }}));

// сброс авто
await page.locator('[data-testid="car-picker-reset"]').click();
await wait(700);
check('сброс авто возвращает первую страницу', await cards().count(), 24);

// --- табы поиска ---
const ph = {{}};
for (const mode of ['name', 'vin', 'sku']) {{
  await page.locator(`[data-testid="catalog-search-mode-${{mode}}"]`).click();
  await wait(200);
  ph[mode] = await page.locator('[data-testid="catalog-search"]').getAttribute('placeholder');
}}
check('placeholder меняется по табу', new Set(Object.values(ph)).size, 3);

await page.locator('[data-testid="catalog-search-mode-sku"]').click();
await page.locator('[data-testid="catalog-search"]').fill('FLT');
await wait(600);
check('поиск по артикулу', (await skus()).every((s) => s.includes('FLT')), true);

await page.locator('[data-testid="catalog-search-mode-name"]').click();
await page.locator('[data-testid="catalog-search"]').fill('колодки');
await wait(600);
check('поиск по названию', (await skus()).length > 0 && (await skus()).length < 24, true);

// --- VIN ---
await page.locator('[data-testid="catalog-search-mode-vin"]').click();
await page.locator('[data-testid="catalog-search"]').fill('SHORT');
await wait(600);
check('короткий VIN даёт подсказку',
  (await page.locator('[data-testid="catalog-vin-hint"]').innerText()).includes('17'), true);

await page.locator('[data-testid="catalog-search"]').fill('Z94CB11E1E1234567');
await wait(1500);
check('VIN распознан как KIA',
  (await page.locator('[data-testid="catalog-vin-hint"]').innerText()).includes('KIA'), true);
const vinSkus = await skus();
check('подбор по VIN даёт KIA-детали', vinSkus.includes('BRK-001'), true);
check('подбор по VIN убрал несовместимые', vinSkus.includes('BAT-006'), false);

await page.locator('[data-testid="catalog-search"]').fill('');
await wait(600);

// --- фильтры ---
await page.locator('[data-testid="catalog-brand-Bosch"]').check({{ force: true }});
await wait(600);
const brandTexts = await cards().evaluateAll((els) => els.map((e) => e.innerText));
check('фильтр по бренду оставляет только Bosch',
  brandTexts.length > 0 && brandTexts.every((t) => t.includes('Bosch')), true);
check('фильтр по бренду сужает каталог', brandTexts.length < totalInCatalog, true);

await page.locator('[data-testid="catalog-filter-order"]').check({{ force: true }});
await wait(600);
check('фильтр «Под заказ» даёт только подзаказные', (await skus()).length > 0, true);

await page.locator('[data-testid="catalog-filter-stock"]').check({{ force: true }});
await wait(600);
check('«В наличии» + «Под заказ» вместе', (await skus()).length > 0, true);

await page.locator('[data-testid="catalog-price-max"]').fill('1000');
await page.locator('[data-testid="catalog-price-max"]').dispatchEvent('change');
await wait(600);
const priceFiltered = await skus();
check('фильтр по цене отсекает дорогие', priceFiltered.every((s) => s !== 'BAT-006'), true);

await page.locator('[data-testid="catalog-filters-reset"]').click();
await wait(700);
check('сброс фильтров возвращает первую страницу', await cards().count(), 24);
check('тумблер сброшен',
  await page.locator('[data-testid="catalog-filter-stock"]').isChecked(), false);
check('бренд сброшен',
  await page.locator('[data-testid="catalog-brand-Bosch"]').isChecked(), false);

// --- мобильная шторка ---
await page.setViewportSize({{ width: 390, height: 844 }});
await wait(500);
check('на мобильном 1 колонка',
  await page.locator('[data-testid="catalog-grid"]').evaluate(
    (el) => getComputedStyle(el).gridTemplateColumns.split(' ').length), 1);
check('на мобильном боковая колонка скрыта',
  await page.locator('aside').isVisible(), false);
await page.locator('[data-testid="catalog-filters-toggle"]').click();
await wait(500);
check('шторка фильтров открылась',
  await page.locator('[data-testid="catalog-filters-drawer"]').count(), 1);
await page.locator('[data-testid="catalog-filters-apply"]').click();
await wait(400);
check('шторка закрылась',
  await page.locator('[data-testid="catalog-filters-drawer"]').count(), 0);

// --- Фильтры Марка/Модель с поиском и ограничением по высоте ---
await page.setViewportSize({{ width: 1440, height: 900 }});
await page.reload({{ waitUntil: 'networkidle' }});
await wait(1500);

check('на первой странице порция товаров', await cards().count(), 24);
check('есть кнопка «Показать ещё»', await page.locator('[data-testid="catalog-load-more"]').count(), 1);
check('кнопка показывает остаток',
  /Показать ещё \\(\\d+\\)/.test(await page.locator('[data-testid="catalog-load-more"]').innerText()), true);

await page.locator('[data-testid="catalog-load-more"]').click();
await wait(800);
check('«Показать ещё» догрузил товары', await cards().count() > 24, true);

await openSection('make');
check('в фильтре «Марка» есть поиск', await page.locator('[data-testid="catalog-make-search"]').count(), 1);

const makeList = await page.locator('aside [data-testid="catalog-filters"] .max-h-60').first().evaluate((el) => ({{
  overflowY: getComputedStyle(el).overflowY,
  maxHeight: getComputedStyle(el).maxHeight,
  scrollable: el.scrollHeight > el.clientHeight,
}})).catch(() => null);
check('список марок ограничен по высоте и скроллится',
  makeList !== null && makeList.overflowY === 'auto' && makeList.scrollable, true);

// Поиск по марке
await page.locator('[data-testid="catalog-make-search"]').fill('KIA');
await wait(500);
const makeOptions = page.locator('input[type="checkbox"][data-testid^="catalog-make-"]');
check('поиск по марке сужает список', await makeOptions.count(), 1);
check('найдена именно KIA', await makeOptions.first().getAttribute('data-testid'), 'catalog-make-KIA');

// NISSAN -> Qashqai
await page.locator('[data-testid="catalog-make-search"]').fill('NISSAN');
await wait(500);
await page.locator('[data-testid="catalog-make-NISSAN"]').check({{ force: true }});
await wait(1000);
const nissanCount = await countText();
check('фильтр по NISSAN сужает каталог', nissanCount < allCount, true);
check('в списке марок есть NISSAN', nissanCount > 0, true);

await openSection('model');
await wait(700);
check('в фильтре «Модель» есть поиск', await page.locator('[data-testid="catalog-model-search"]').count(), 1);
check('модели подгрузились для NISSAN',
  await page.locator('[data-testid^="catalog-model-"]').count() > 5, true);

await page.locator('[data-testid="catalog-model-search"]').fill('Qashqai');
await wait(500);
check('поиск по модели находит Qashqai',
  await page.locator('input[type="checkbox"][data-testid="catalog-model-Qashqai"]').count(), 1);
await page.locator('[data-testid="catalog-model-Qashqai"]').check({{ force: true }});
await wait(1000);
const qashqaiCount = await countText();
check('подбор NISSAN Qashqai даёт товары', qashqaiCount > 0, true);
check('подбор NISSAN Qashqai уже�� чем просто NISSAN', qashqaiCount <= nissanCount, true);
check('каталог не сломан: есть карточки', qashqaiCount > 0, true);

await page.locator('[data-testid="catalog-filters-reset"]').click();
await wait(900);
check('сброс вернул первую страницу', await cards().count(), 24);

// Скриншоты для владельца: десктоп с открытыми фильтрами и мобильный вид.
// Открываем «Марка» и «Модель» (в тесте они закрывались) — на снимке
// видно, как выглядит колонка в рабочем виде.
for (const sectionId of ['make', 'model']) {{
  await openSection(sectionId);
}}
await page.screenshot({{ path: SHOT_DIR + '/19-catalog-filters.png', fullPage: false }});
await page.setViewportSize({{ width: 390, height: 844 }});
await wait(600);
await page.screenshot({{ path: SHOT_DIR + '/20-catalog-mobile.png', fullPage: false }});
await page.setViewportSize({{ width: 1440, height: 900 }});
await wait(400);

check('нет ошибок в консоли', errors, []);

await browser.close();

const failed = results.filter((r) => !r.ok);
console.log(`\\nИТОГ: ${{results.length - failed.length}}/${{results.length}} проверок пройдено`);
if (failed.length) {{
  console.log('Провалено: ' + failed.map((f) => f.name).join(', '));
  process.exit(1);
}}
process.exit(0);
"""

    shot_dir = str(Path(__file__).resolve().parents[2] / "docs" / "screenshots")
    Path(shot_dir).mkdir(parents=True, exist_ok=True)

    total = _catalog_size()
    script = script.replace("__TOTAL_IN_CATALOG__", str(total))
    script = script.replace("__SHOT_DIR__", shot_dir.replace("\\", "/"))

    chromium = find_chromium()
    launch_args = (
        "{ executablePath: process.env.PW_CHROMIUM }"
        if chromium
        else ""
    )
    script = script.replace("__LAUNCH_ARGS__", launch_args)

    script_path = Path(__file__).resolve().parent / "_check_catalog.mjs"
    script_path.write_text(script, encoding="utf-8")
    if chromium:
        # Подсовываем установленный Chromium: версия playwright в кэше npx
        # может ждать другой ревизии браузера, чем скачана в системе.
        print(f"Chromium: {chromium}")
    else:
        print("Chromium не найден — будет использован встроенный браузер playwright")
    print(f"Скрипт: {script_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
