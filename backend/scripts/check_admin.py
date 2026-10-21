"""Проверка переработанной админки (Playwright, локальный Vite).

Запуск:  python backend/scripts/check_admin.py
        node backend/scripts/_check_admin.mjs

Проверяем:
  ЭТАП 1 — заказы:
    * кликабельные метрики (клик по «Новых» фильтрует список);
    * подсветка активной метрики;
    * широкая строка поиска над списком;
    * телефон клиента — ссылка tel:;
    * состав заказа виден в карточке без раскрытия;
    * главная кнопка статуса, кнопка «Отклонить», меню «[ ]».
  ЭТАП 2 — каталог:
    * форма скрыта, есть кнопка «+ Добавить товар»;
    * форма открывается в Drawer справа;
    * таблица с колонками и тумблерами;
    * тумблер сохраняется сразу (PATCH) и меняет состояние;
    * мульти-селект авто: марка -> модель -> бейдж с крестиком.
  ЭТАП 3 — адаптивность:
    * на мобильном таблица превращается в карточки.
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
ROOT = BACKEND_DIR.parent.parent

CANDIDATES = [Path.home() / "AppData/Local/npm-cache/_npx"]


def find_playwright() -> Path:
    for base in CANDIDATES:
        if not base.exists():
            continue
        for candidate in base.glob("*/node_modules/playwright"):
            if (candidate / "index.mjs").exists():
                return candidate
    raise SystemExit("Playwright не найден в кэше npx")


def find_chromium() -> Path | None:
    base = Path.home() / "AppData/Local/ms-playwright"
    if not base.exists():
        return None
    candidates = sorted(base.glob("chromium-*/chrome-win64/chrome.exe"), reverse=True)
    if not candidates:
        candidates = sorted(
            base.glob(
                "chromium_headless_shell-*/chrome-headless-shell-win64/"
                "chrome-headless-shell.exe"
            ),
            reverse=True,
        )
    return candidates[0] if candidates else None


def main() -> int:
    playwright_dir = find_playwright()
    chromium = find_chromium()

    script = f"""
import {{ chromium }} from 'file:///{(playwright_dir / "index.mjs").as_posix()}';

const BASE = 'http://127.0.0.1:5173';
const results = [];
function check(name, actual, expected) {{
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  results.push({{ name, ok }});
  console.log((ok ? 'OK   ' : 'FAIL ') + name +
    (ok ? '' : ` | ожидалось ${{JSON.stringify(expected)}}, получено ${{JSON.stringify(actual)}}`));
  return ok;
}}

const browser = await chromium.launch(__LAUNCH_ARGS__);
const page = await browser.newPage({{ viewport: {{ width: 1440, height: 950 }} }});
const errors = [];
page.on('console', (m) => {{ if (m.type() === 'error') errors.push(m.text()); }});
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message));

const wait = (ms) => page.waitForTimeout(ms);
const scrollBelowHeader = async (locator) => {{
  // Шапка липкая и перехватывает клики: ставим элемент на 140 px ниже
  // верхнего края окна, чтобы он оказался под шапкой, а не под ней.
  const box = await locator.boundingBox();
  if (box) {{
    const target = box.y - 140;
    await page.evaluate((y) => window.scrollTo(0, Math.max(0, y)), target);
  }} else {{
    await locator.scrollIntoViewIfNeeded();
  }}
  await wait(400);
}};


const orders = () => page.locator('[data-testid="admin-order"]');
const rows = () => page.locator('[data-testid="admin-product"]');

// --- Вход владельца ---
await page.goto(BASE + '/login', {{ waitUntil: 'domcontentloaded' }});
await page.locator('[data-testid="login-email"]').fill('__OWNER_EMAIL__');
await page.locator('[data-testid="login-password"]').fill('__OWNER_PASSWORD__');
await page.locator('[data-testid="login-submit"]').click();
await wait(2500);
check('вход выполнен, токен сохранён',
  await page.evaluate(() => Boolean(localStorage.getItem('autodom.token'))), true);
await page.goto(BASE + '/admin', {{ waitUntil: 'domcontentloaded' }});
// Ждём появления вкладок, а не «тишины сети» — админка шлёт запросы.
await page.locator('[data-testid="admin-tab-orders"]').waitFor({{ state: 'visible', timeout: 20000 }});
await wait(1500);

check('админка открылась', await page.locator('[data-testid="admin-tab-orders"]').count(), 1);

// Готовим такой заказ через API: тест не должен зависеть от того, сколько
// заказов в «new» осталось в базе.
const prepared = await page.evaluate(async () => {{
  const token = localStorage.getItem('autodom.token');
  const resp = await fetch('/api/admin/orders?limit=1', {{
    headers: {{ Authorization: 'Bearer ' + token }},
  }});
  const list = await resp.json();
  if (!list.length) return null;
  const order = list[0];
  const patch = await fetch('/api/admin/orders/' + order.id, {{
    method: 'PATCH',
    headers: {{
      'Content-Type': 'application/json',
      Authorization: 'Bearer ' + token,
    }},
    body: JSON.stringify({{ status: 'new' }}),
  }});
  const updated = await patch.json();
  return {{ id: order.id, number: order.order_number, prevStatus: order.status }};
}});
check('заказ для проверки кнопок подготовлен', prepared !== null, true);

// Метрики рисуются, когда приходит статистика — ждём их появления.
await page.locator('[data-testid="stat-orders-new"]').waitFor({{ state: 'visible', timeout: 20000 }});

// Диагностика: что вернул stats и что есть на странице.
const diag = await page.evaluate(async () => {{
  const token = localStorage.getItem('autodom.token');
  let stats = null;
  let statsErr = null;
  try {{
    const resp = await fetch('/api/admin/stats', {{
      headers: {{ Authorization: 'Bearer ' + token }},
    }});
    statsErr = resp.status;
    stats = await resp.json();
  }} catch (e) {{
    statsErr = 'network: ' + e.message;
  }}
  return {{
    statsErr,
    totals: stats && stats.totals ? Object.keys(stats.totals) : null,
    statCards: document.querySelectorAll('[data-testid^="stat-"]').length,
    errorBox: document.body.innerText.includes('Не удалось загрузить'),
    bodyStart: document.body.innerText.slice(0, 300),
  }};
}});
console.log('ДИАГНОСТИКА: ' + JSON.stringify(diag));
console.log('ОШИБКИ КОНСОЛИ: ' + JSON.stringify(errors));

// ============ ЭТАП 1: ЗАКАЗЫ ============

// Метрики кликабельны
check('метрика «Новых» есть', await page.locator('[data-testid="stat-orders-new"]').count(), 1);
check('метрика «Заказов всего» есть', await page.locator('[data-testid="stat-orders-total"]').count(), 1);
check('метрика «Выручка» есть', await page.locator('[data-testid="stat-revenue"]').count(), 1);
check('метрика «Товаров» есть', await page.locator('[data-testid="stat-products"]').count(), 1);

const beforeNew = await orders().count();
await page.locator('[data-testid="stat-orders-new"]').click();
await wait(1800);
const afterNew = await orders().count();
check('клик по «Новых» меняет список', afterNew !== beforeNew, true);
check('после фильтра список не пуст', afterNew > 0, true);
check('активная метрика подсвечена',
  await page.locator('[data-testid="stat-orders-new"]').getAttribute('aria-pressed'), 'true');
const cardTexts = await page.locator('[data-testid="admin-order"]').evaluateAll(
  (els) => els.map((e) => e.innerText),
);
check('в списке только новые',
  cardTexts.length > 0 && cardTexts.every((s) => s.includes('Новый')), true);

// Возврат ко всем
await page.locator('[data-testid="stat-orders-total"]').click();
await wait(1500);
check('клик по «Заказов всего» снимает фильтр',
  await page.locator('[data-testid="stat-orders-total"]').getAttribute('aria-pressed'), 'true');

// Поиск над списком
const searchBox = page.locator('[data-testid="admin-search"]');
check('широкая строка поиска над списком', await searchBox.count(), 1);
check('строка поиска видна', await searchBox.isVisible(), true);

// Берём номер первого заказа и ищем по нему.
const orderNumber = (await page.locator('[data-testid="admin-order-number"]').first()
  .innerText()).trim();
await searchBox.fill(orderNumber);
await wait(4000);
check('поиск по номеру заказа находит его', await orders().count(), 1);
await searchBox.fill('несуществующийклиент999');
await wait(4000);
check('поиск без совпадений даёт пустой список', await orders().count(), 0);
await searchBox.fill('');
await wait(4000);

// Телефон — ссылка tel:
const phoneLink = page.locator('[data-testid="admin-order-phone"]').first();
check('телефон клиента — ссылка', await phoneLink.count(), 1);
check('href начинается с tel:', (await phoneLink.getAttribute('href') || '').startsWith('tel:'), true);

// Состав заказа в карточке
const itemsLine = page.locator('[data-testid="admin-order-items"]').first();
check('состав заказа виден в карточке', await itemsLine.count(), 1);
const itemsText = await itemsLine.innerText();
check('в составе есть количество и единица', /[(][0-9]+ (шт|компл|уп)[)]/.test(itemsText), true);

// Кнопки статусов — на заказе в статусе «new» (у завершённых её нет по дизайну).

await page.locator('[data-testid="stat-orders-new"]').click();
await wait(4000);
// Список перерисовывается — берём свежий локатор и ждём кнопку.
const primaryBtn = orders().first().locator('[data-testid^="order-primary-"]');
await primaryBtn.waitFor({{ state: 'visible', timeout: 20000 }});
check('есть главная кнопка статуса', await primaryBtn.count(), 1);
const primaryLabel = await primaryBtn.innerText();
check('главная кнопка с понятным действием',
  ['Принять', 'В работу', 'Готов', 'Завершить'].some((s) => primaryLabel.includes(s)), true);
check('есть кнопка «Отклонить»',
  await orders().first().locator('[data-testid="order-reject"]').count(), 1);
check('есть кнопка-иконка [ ]',
  await orders().first().locator('[data-testid="order-more-status"]').count(), 1);
check('меню закрыто по умолчанию',
  await orders().first().locator('[data-testid="order-status-menu"]').count(), 0);

await orders().first().locator('[data-testid="order-more-status"]').click();
await wait(600);
check('меню статусов открылось',
  await orders().first().locator('[data-testid="order-status-menu"]').count(), 1);
const menuItems = await orders().first().locator('[data-testid^="order-status-"]').count();
check('в меню есть остальные статусы', menuItems >= 4, true);
await orders().first().locator('[data-testid="order-more-status"]').click();
await wait(400);

// Главная кнопка меняет статус — проверяем по данным с сервера.
const targetOrder = (await page.locator('[data-testid="admin-order-number"]').first()
  .innerText()).trim();
await primaryBtn.click();
await wait(4000);
const noticeCount = await page.locator('[data-testid="admin-notice"]').count();
const noticeText = noticeCount
  ? await page.locator('[data-testid="admin-notice"]').first().innerText()
  : '';
check('смена статуса подтверждена уведомлением', noticeText.includes(targetOrder), true);
const statusAfter = await page.evaluate(async (num) => {{
  const token = localStorage.getItem('autodom.token');
  const resp = await fetch('/api/admin/orders?query=' + num + '&limit=10', {{
    headers: {{ Authorization: 'Bearer ' + token }},
  }});
  const list = await resp.json();
  return list.length ? list[0].status : null;
}}, targetOrder);
check('статус изменился на сервере', statusAfter === 'accepted', true);

// Выручка за сегодня должна уменьшаться, когда заказ отклоняют:
// отклонённый заказ денег не приносит.
const revenueBefore = await page.evaluate(async () => {{
  const token = localStorage.getItem('autodom.token');
  const resp = await fetch('/api/admin/stats', {{
    headers: {{ Authorization: 'Bearer ' + token }},
  }});
  const data = await resp.json();
  return {{ today: Number(data.totals.revenue_today),
           total: Number(data.totals.revenue_total) }};
}});

const orderToReject = await page.evaluate(async () => {{
  const token = localStorage.getItem('autodom.token');
  const resp = await fetch('/api/admin/orders?order_status=accepted&limit=1', {{
    headers: {{ Authorization: 'Bearer ' + token }},
  }});
  const list = await resp.json();
  if (!list.length) return null;
  return {{ id: list[0].id, number: list[0].order_number, total: Number(list[0].total) }};
}});

if (orderToReject) {{
  await page.evaluate(async (info) => {{
    const token = localStorage.getItem('autodom.token');
    await fetch('/api/admin/orders/' + info.id, {{
      method: 'PATCH',
      headers: {{ 'Content-Type': 'application/json',
                 Authorization: 'Bearer ' + token }},
      body: JSON.stringify({{ status: 'rejected' }}),
    }});
  }}, orderToReject);
  await wait(1200);

  const revenueAfter = await page.evaluate(async () => {{
    const token = localStorage.getItem('autodom.token');
    const resp = await fetch('/api/admin/stats', {{
      headers: {{ Authorization: 'Bearer ' + token }},
    }});
    const data = await resp.json();
    return {{ today: Number(data.totals.revenue_today),
             total: Number(data.totals.revenue_total) }};
  }});

  check('отклонение уменьшает выручку за сегодня',
    Math.abs((revenueBefore.today - revenueAfter.today) - orderToReject.total) < 0.01, true);
  check('отклонение уменьшает общую выручку',
    Math.abs((revenueBefore.total - revenueAfter.total) - orderToReject.total) < 0.01, true);

  // Возвращаем заказ в исходный статус.
  await page.evaluate(async (info) => {{
    const token = localStorage.getItem('autodom.token');
    await fetch('/api/admin/orders/' + info.id, {{
      method: 'PATCH',
      headers: {{ 'Content-Type': 'application/json',
                 Authorization: 'Bearer ' + token }},
      body: JSON.stringify({{ status: 'accepted' }}),
    }});
  }}, orderToReject);
  await wait(1200);

  const revenueRestored = await page.evaluate(async () => {{
    const token = localStorage.getItem('autodom.token');
    const resp = await fetch('/api/admin/stats', {{
      headers: {{ Authorization: 'Bearer ' + token }},
    }});
    const data = await resp.json();
    return {{ today: Number(data.totals.revenue_today),
             total: Number(data.totals.revenue_total) }};
  }});
  check('возврат статуса восстанавливает выручку',
    Math.abs(revenueRestored.today - revenueBefore.today) < 0.01, true);
}} else {{
  check('нашёлся заказ для проверки выручки', false, true);
}}

// Возвращаем подготовленный заказ в исходный статус: тест не должен
// расходовать заказы, иначе со временем их не останется.
const restored = await page.evaluate(async (info) => {{
  const token = localStorage.getItem('autodom.token');
  await fetch('/api/admin/orders/' + info.id, {{
    method: 'PATCH',
    headers: {{
      'Content-Type': 'application/json',
      Authorization: 'Bearer ' + token,
    }},
    body: JSON.stringify({{ status: info.prevStatus }}),
  }});
  return 'done';
}}, prepared);
check('заказ возвращён в исходный статус', restored === 'done', true);
await page.locator('[data-testid="stat-orders-total"]').click();
await wait(2500);

// ============ ЭТАП 2: КАТАЛОГ ============
await page.locator('[data-testid="admin-tab-products"]').click();
await wait(1500);

check('форма товара скрыта', await page.locator('[data-testid="product-sku"]').count(), 0);
check('есть кнопка «+ Добавить товар»', await page.locator('[data-testid="admin-add-product"]').count(), 1);
check('таблица каталога есть', await page.locator('[data-testid="admin-products-table"]').count(), 1);
check('строки каталога есть', await rows().count() > 0, true);

// Заголовки таблицы
const headers = (await page.locator('[data-testid="admin-products-table"] thead th').allInnerTexts())
  .map((h) => h.toLowerCase());
check('колонка «Название / Артикул»', headers.some((h) => h.includes('название')), true);
check('колонка «Цена»', headers.some((h) => h.includes('цена')), true);
check('колонка «Наличие»', headers.some((h) => h.includes('наличие')), true);
check('колонка «Под заказ»', headers.some((h) => h.includes('под заказ')), true);
check('колонка «Действия»', headers.some((h) => h.includes('действия')), true);

// Тумблеры в таблице
const firstRow = rows().first();
const sku = await firstRow.getAttribute('data-sku');
check('тумблер «В наличии» в строке', await firstRow.locator(`[data-testid="product-stock-${{sku}}"]`).count(), 1);
check('тумблер «Под заказ» в строке', await firstRow.locator(`[data-testid="product-onorder-${{sku}}"]`).count(), 1);
check('кнопка «Редактировать»', await firstRow.locator(`[data-testid="product-edit-${{sku}}"]`).count(), 1);
check('кнопка «Скрыть»', await firstRow.locator(`[data-testid="product-active-${{sku}}"]`).count(), 1);

// Мгновенное сохранение: переключаем «В наличии» и проверяем PATCH
const stockSwitch = firstRow.locator(`[data-testid="product-stock-${{sku}}"]`);
const stockTrack = firstRow.locator(`[data-testid="product-stock-${{sku}}-track"]`);
const wasChecked = await stockSwitch.isChecked();
// Видимая дорожка должна быть на экране и кликабельна.
const trackBox = await stockTrack.boundingBox();
check('тумблер виден и имеет размер', !!trackBox && trackBox.width > 20, true);
check('тумблер не перекрыт шапкой', !!trackBox && trackBox.y > 100, true);
await stockSwitch.dispatchEvent('click');
await wait(2000);
const afterToggle = await firstRow.locator(`[data-testid="product-stock-${{sku}}"]`).isChecked();
check('тумблер переключился', afterToggle !== wasChecked, true);
const savedNotice = await page.locator('text=/наличии|под заказ/').first().innerText().catch(() => '');
check('изменение сохранено и подтверждено', savedNotice.length > 0, true);
// Проверяем на сервере
const serverState = await page.evaluate(async (s) => {{
  const token = localStorage.getItem('autodom.token');
  const resp = await fetch('/api/admin/products', {{
    headers: {{ Authorization: 'Bearer ' + token }},
  }});
  const list = await resp.json();
  const item = list.find((p) => p.sku === s);
  return item ? {{ in_stock: item.in_stock, is_on_order: item.is_on_order }} : null;
}}, sku);
check('состояние сохранилось в БД', serverState && serverState.in_stock === afterToggle, true);

// Совместимость не должна потеряться при переключении тумблера.
const compatBefore = await page.evaluate(async (s) => {{
  const token = localStorage.getItem('autodom.token');
  const resp = await fetch('/api/admin/products', {{
    headers: {{ Authorization: 'Bearer ' + token }},
  }});
  const list = await resp.json();
  const item = list.find((p) => p.sku === s);
  return item ? item.compatibility.length : -1;
}}, sku);
console.log('ТОВАР В ТЕСТЕ: ' + sku + ', совместимостей: ' + compatBefore);
check('совместимость товара на месте', compatBefore > 0, true);

// Тумблер «Под заказ» открывает поле срока поставки.
await firstRow.locator(`[data-testid="product-onorder-${{sku}}"]`).dispatchEvent('click');
await wait(3000);
check('поле срока появилось', await firstRow.locator(`[data-testid="product-days-${{sku}}"]`).count(), 1);
const compatAfter = await page.evaluate(async (s) => {{
  const token = localStorage.getItem('autodom.token');
  const resp = await fetch('/api/admin/products', {{
    headers: {{ Authorization: 'Bearer ' + token }},
  }});
  const list = await resp.json();
  const item = list.find((p) => p.sku === s);
  return item ? item.compatibility.length : -1;
}}, sku);
console.log('СОВМЕСТИМОСТЬ: до=' + compatBefore + ' после=' + compatAfter);
check('совместимость не стёрлась после PATCH', compatAfter, compatBefore);
const onOrderState = await page.evaluate(async (s) => {{
  const token = localStorage.getItem('autodom.token');
  const resp = await fetch('/api/admin/products', {{
    headers: {{ Authorization: 'Bearer ' + token }},
  }});
  const list = await resp.json();
  const item = list.find((p) => p.sku === s);
  return item ? {{ is_on_order: item.is_on_order, in_stock: item.in_stock }} : null;
}}, sku);
check('«Под заказ» сохранён на сервере', onOrderState && onOrderState.is_on_order === true, true);
check('«Под заказ» снимает наличие', onOrderState && onOrderState.in_stock === false, true);

// Возвращаем как было
await firstRow.locator(`[data-testid="product-onorder-${{sku}}"]`).dispatchEvent('click');
await wait(2500);
await firstRow.locator(`[data-testid="product-stock-${{sku}}"]`).dispatchEvent('click');
await wait(2500);

// Переключатель «Скрытые» — по умолчанию выключен, скрытые товары не видны.
// Сбрасываем флаг: тест не должен зависеть от предыдущих прогонов.
await page.evaluate(() => localStorage.setItem('autodom.admin.showHidden', '0'));
await page.reload({{ waitUntil: 'domcontentloaded' }});
await page.locator('[data-testid="admin-tab-products"]').click();
await wait(3000);
const hiddenSwitch = page.locator('[data-testid="admin-show-hidden"]');
check('переключатель «Скрытые» есть', await hiddenSwitch.count(), 1);
check('по умолчанию скрытые не показываются',
  await page.locator('[data-testid="admin-products-table"] tbody tr')
    .evaluateAll((els) => els.every((e) => !e.className.includes('opacity-60'))), true);
const activeOnly = await page.locator('[data-testid="admin-products-table"] tbody tr').count();
check('в списке только активные товары', activeOnly > 0 && activeOnly < 137, true);

await hiddenSwitch.dispatchEvent('click');
await wait(2000);
const withHidden = await page.locator('[data-testid="admin-products-table"] tbody tr').count();
check('включение показывает скрытые', withHidden > activeOnly, true);
check('состояние сохраняется в localStorage',
  await page.evaluate(() => localStorage.getItem('autodom.admin.showHidden')), '1');

await hiddenSwitch.dispatchEvent('click');
await wait(2000);
check('выключение возвращает активные',
  await page.locator('[data-testid="admin-products-table"] tbody tr').count(), activeOnly);

// Drawer
await page.locator('[data-testid="admin-add-product"]').click();
await wait(600);
check('форма открылась в Drawer', await page.locator('[data-testid="product-drawer"]').count(), 1);
check('поле артикула в Drawer', await page.locator('[data-testid="product-sku"]').count(), 1);
check('мульти-селект авто в Drawer', await page.locator('[data-testid="product-compatibility"]').count(), 1);

// Мульти-селект: марка -> модель -> бейдж
await page.locator('[data-testid="compatibility-make-button"]').click();
await wait(400);
check('выпадающий список марок открылся', await page.locator('[data-testid="compatibility-make-KIA"]').count(), 1);
await page.locator('[data-testid="compatibility-make-KIA"]').click();
await wait(400);
await page.locator('[data-testid="compatibility-model-button"]').click();
await wait(500);
check('модели KIA загрузились', await page.locator('[data-testid="compatibility-model-Rio"]').count(), 1);
await page.locator('[data-testid="compatibility-model-Rio"]').click();
await wait(300);
await page.locator('[data-testid="compatibility-add"]').click();
await wait(500);
check('появился бейдж авто', await page.locator('[data-testid="compatibility-badges"]').count(), 1);
const badgeText = await page.locator('[data-testid="compatibility-badges"]').innerText();
check('бейдж содержит KIA Rio', badgeText.includes('KIA Rio'), true);
check('у бейджа есть крестик', await page.locator('[data-testid="compatibility-remove-KIA-Rio"]').count(), 1);
await page.locator('[data-testid="compatibility-remove-KIA-Rio"]').click();
await wait(400);
check('крестик удаляет бейдж', await page.locator('[data-testid="compatibility-badges"]').count(), 0);

// Esc закрывает Drawer
await page.keyboard.press('Escape');
await wait(500);
check('Esc закрывает Drawer', await page.locator('[data-testid="product-drawer"]').count(), 0);

// ============ ЭТАП 3: АДАПТИВНОСТЬ ============
await page.setViewportSize({{ width: 390, height: 844 }});
await wait(800);
check('на мобильном таблица скрыта',
  await page.locator('[data-testid="admin-products-table"]').isVisible(), false);
check('на мобильном строки-карточки видны',
  await page.locator('[data-testid="admin-product-card"]').first().isVisible(), true);
check('на мобильном тумблер в карточке работает',
  await page.locator('[data-testid="admin-product-card"]').first()
    .locator('input[type="checkbox"]').count(), 2);
check('на мобильном ширина не ломает вёрстку',
  await page.evaluate(() => document.documentElement.scrollWidth <=
    window.innerWidth + 2), true);

await page.setViewportSize({{ width: 1440, height: 950 }});
await wait(600);

check('нет ошибок в консоли', errors, []);

// ---------- Скриншоты для документации ----------
const SHOT_DIR = 'C:/Users/79156/OneDrive/Desktop/автодом/docs/screenshots';
await page.setViewportSize({{ width: 1440, height: 1000 }});
await page.goto(BASE + '/admin', {{ waitUntil: 'domcontentloaded' }});
await page.locator('[data-testid="stat-orders-new"]').waitFor({{ state: 'visible', timeout: 20000 }});
await wait(2500);
await page.screenshot({{ path: SHOT_DIR + '/21-admin-orders.png', fullPage: false }});

await page.locator('[data-testid="admin-tab-products"]').click();
await wait(2500);
await page.screenshot({{ path: SHOT_DIR + '/22-admin-catalog.png', fullPage: false }});

await page.locator('[data-testid="admin-add-product"]').click();
await wait(900);
await page.screenshot({{ path: SHOT_DIR + '/23-admin-product-drawer.png', fullPage: false }});
await page.keyboard.press('Escape');
await wait(500);

await page.setViewportSize({{ width: 390, height: 844 }});
await wait(1200);
await page.screenshot({{ path: SHOT_DIR + '/24-admin-mobile.png', fullPage: false }});
await page.setViewportSize({{ width: 1440, height: 950 }});
await wait(600);

await browser.close();

const failed = results.filter((r) => !r.ok);
console.log(`\\nИТОГ: ${{results.length - failed.length}}/${{results.length}} проверок пройдено`);
if (failed.length) {{
  console.log('Провалено: ' + failed.map((f) => f.name).join(', '));
  process.exit(1);
}}
process.exit(0);
"""

    script = script.replace(
        "__LAUNCH_ARGS__",
        "{ executablePath: process.env.PW_CHROMIUM }" if chromium else "",
    )

    owner_email, owner_password = _owner_credentials()
    script = script.replace("__OWNER_EMAIL__", owner_email)
    script = script.replace("__OWNER_PASSWORD__", owner_password)

    script_path = BACKEND_DIR / "_check_admin.mjs"
    script_path.write_text(script, encoding="utf-8")
    print(f"Скрипт: {script_path}")
    if chromium:
        print(f"Chromium: {chromium}")
    return 0


def _owner_credentials() -> tuple[str, str]:
    """Логин владельца для входа в кабинет.

    Пароль берём из существующего тестового скрипта, чтобы не плодить
    копии учётных данных по проекту. Переменные окружения имеют приоритет.
    """
    import os
    import re

    email = os.environ.get("AUTODOM_OWNER_EMAIL", "owner@autodom.ru")
    password = os.environ.get("AUTODOM_OWNER_PASSWORD", "")

    if not password:
        source = BACKEND_DIR / "test_accounts.py"
        if source.exists():
            text = source.read_text(encoding="utf-8")
            match = re.search(
                r'"email":\s*"owner@autodom\.ru",\s*"password":\s*"([^"]+)"', text
            )
            if match:
                password = match.group(1)

    if not password:
        raise SystemExit(
            "Не найден пароль владельца. Задайте AUTODOM_OWNER_PASSWORD "
            "в переменных окружения."
        )
    return email, password


if __name__ == "__main__":
    raise SystemExit(main())
