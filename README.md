# IPI

Проект для работы с API поставщика Асткол-Альфа.

Сейчас умеет:

- забирать каталог товаров с остатками
- забирать группы товаров
- забирать привязки товаров к группам
- забирать новинки за 30 дней
- собирать единый Excel для дальнейшего маппинга в Ozon, Яндекс и Wildberries
- запускаться в отдельном контейнере на VPS по расписанию
- крутить бесконечный sync-loop без участия руками

Структура:

- `src/api` — код проекта
- `tests` — тесты
- `data` — входные и выходные файлы

Быстрый старт:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip setuptools wheel
python3 -m pip install -e ".[dev]"
```

Переменные окружения:

```bash
export ASTKOL_USER="логин"
export ASTKOL_PASSWORD="пароль"
export MARKETPLACE_PRICE_FIELD="rrc"
export MARKETPLACE_STOCK_FIELD="qty"
export MARKETPLACE_STOCK_RESERVE="0"
```

Если есть только md5-хэш пароля:

```bash
export ASTKOL_USER="логин"
export ASTKOL_PASSWORD_MD5="md5-хэш"
```

Основные команды:

```bash
python3 -m api.main fetch-catalog --output data/catalog.xlsx
python3 -m api.main fetch-groups --output data/groups.xlsx
python3 -m api.main fetch-new --output data/new_items.xlsx
python3 -m api.main build-marketplace-feed --output data/marketplace_feed.xlsx
python3 -m api.main sync-once --output-dir data
python3 -m api.main sync-loop --output-dir data
python3 -m api.main ozon-sync --input data/marketplace_feed.xlsx
python3 -m api.main build-ozon-products-draft --input data/marketplace_feed.xlsx --output data/ozon/products_draft.xlsx
python3 -m api.main ozon-import-products --input data/ozon/products_draft.xlsx
python3 -m api.main ozon-category-tree --output data/ozon/category_tree.json
python3 -m api.main ozon-category-attributes --category-id 123456 --type-id 654321
python3 -m api.main wb-limits --output data/wb/limits.json
python3 -m api.main wb-parent-categories --output data/wb/parent_categories.json
python3 -m api.main wb-subjects --parent-id 1
python3 -m api.main wb-subject-characteristics --subject-id 1
python3 -m api.main build-wb-products-draft --input data/marketplace_feed.xlsx --output data/wb/products_draft.xlsx
python3 -m api.main wb-import-products --input data/wb/products_draft.xlsx
python3 -m api.main build-wb-mapping-draft --feed-input data/marketplace_feed.xlsx --subjects-input data/wb/subjects_5038.json --output data/wb/wb_mapping_draft.xlsx
python3 -m api.main autofill-wb-mapping-draft --input data/wb/wb_mapping_draft.xlsx
python3 -m api.main apply-wb-mapping-to-products-draft --mapping-input data/wb/wb_mapping_draft.xlsx --products-input data/wb/products_draft.xlsx
python3 -m api.main wb-fetch-used-subject-characteristics --products-input data/wb/products_draft.xlsx --output-dir data/wb/characteristics
python3 -m api.main autofill-wb-products-characteristics --products-input data/wb/products_draft.xlsx --characteristics-dir data/wb/characteristics
```

## Контейнер для VPS

Скопируй `.env.example` в `.env`, заполни доступы и запусти:

```bash
cp .env.example .env
docker compose up -d --build
```

Контейнер:

- сам забирает каталог поставщика
- пересобирает `catalog.xlsx`, `groups.xlsx`, `marketplace_feed.xlsx`
- затем вызывает адаптеры маркетплейсов
- повторяет это с интервалом `SYNC_INTERVAL_SECONDS`

Что уже есть по Ozon:

- сборка `prices_payload.json`
- сборка `stocks_payload.json`
- сборка `products_draft.xlsx` для подготовки карточек
- импорт карточек из подготовленного draft через API батчами по 100
- Excel-отчёт `sync_report.xlsx` по ценам и остаткам
- в `sync_report.xlsx` есть отдельные листы по ошибкам: `prices_errors`, `stocks_errors`, `not_found`, `not_created`, `not_moderated`
- dry-run режим по умолчанию
- попытка реальной отправки при `OZON_DRY_RUN=0`
- если `OZON_WAREHOUSE_ID` ещё не задан, всё равно отправляются цены, а остатки пропускаются
- цены режутся на батчи по 1000 товаров
- остатки режутся на батчи по 100 товаров
- цена по умолчанию берётся из `rrc`
- поле цены и поле old_price можно переопределить через env
- остатки можно брать из `qty` или `qty_hr`
- можно задать резерв и лимит по остаткам через env

Как работать с карточками Ozon:

1. Собрать draft:

```bash
python3 -m api.main build-ozon-products-draft --input data/marketplace_feed.xlsx --output data/ozon/products_draft.xlsx
```

2. В `products_draft.xlsx` заполнить:

- `ozon_category_id`
- `ozon_name`
- `attributes_json`

3. Потом импортировать:

```bash
python3 -m api.main ozon-import-products --input data/ozon/products_draft.xlsx
```

Если не знаешь `ozon_category_id`, можно вытащить дерево категорий:

```bash
python3 -m api.main ozon-category-tree --output data/ozon/category_tree.json
```

А потом получить атрибуты категории:

```bash
python3 -m api.main ozon-category-attributes --category-id 123456 --type-id 654321
```

Важно:

- без `ozon_category_id` и `attributes_json` карточка не поедет
- `attributes_json` должен содержать обязательные атрибуты категории Ozon
- это сделано специально, чтобы не заливать в Ozon мусор без правильного маппинга

Для реальной отправки нужно заполнить:

```bash
MARKETPLACE_PRICE_FIELD=rrc
MARKETPLACE_OLD_PRICE_FIELD=
MARKETPLACE_STOCK_FIELD=qty
MARKETPLACE_STOCK_RESERVE=0
MARKETPLACE_STOCK_CAP=0
OZON_CLIENT_ID=
OZON_API_KEY=
OZON_API_BASE_URL=https://api-seller.ozon.ru
OZON_WAREHOUSE_ID=1020000303602000
OZON_CURRENCY_CODE=RUB
OZON_DRY_RUN=0
```

По Wildberries и Яндексу пока заведены безопасные заглушки. Следующий шаг - дописать их по аналогии после доводки Ozon.

Что уже есть по Wildberries:

- проверка лимитов карточек `wb-limits`
- выгрузка родительских категорий `wb-parent-categories`
- выгрузка предметов `wb-subjects`
- выгрузка характеристик предмета `wb-subject-characteristics`
- сборка `products_draft.xlsx` для подготовки карточек
- импорт карточек из подготовленного draft

Как работать с карточками Wildberries:

1. Проверить лимиты:

```bash
python3 -m api.main wb-limits --output data/wb/limits.json
```

2. Найти категорию и предмет:

```bash
python3 -m api.main wb-parent-categories --output data/wb/parent_categories.json
python3 -m api.main wb-subjects --parent-id 1
python3 -m api.main wb-subject-characteristics --subject-id 1
```

3. Собрать draft:

```bash
python3 -m api.main build-wb-products-draft --input data/marketplace_feed.xlsx --output data/wb/products_draft.xlsx
```

Для массового сопоставления категорий удобнее сначала собрать mapping draft:

```bash
python3 -m api.main build-wb-mapping-draft --feed-input data/marketplace_feed.xlsx --subjects-input data/wb/subjects_5038.json --output data/wb/wb_mapping_draft.xlsx
```

В нём будут:

- лист `supplier_to_wb_mapping` — группы поставщика, количество товаров и примеры SKU
- лист `wb_subjects` — все предметы WB из категории `Товары для взрослых`

Потом можно сделать автоподстановку типовых соответствий:

```bash
python3 -m api.main autofill-wb-mapping-draft --input data/wb/wb_mapping_draft.xlsx
```

И перенести найденные `wb_subject_id` в draft карточек:

```bash
python3 -m api.main build-wb-products-draft --input data/marketplace_feed.xlsx --output data/wb/products_draft.xlsx
python3 -m api.main apply-wb-mapping-to-products-draft --mapping-input data/wb/wb_mapping_draft.xlsx --products-input data/wb/products_draft.xlsx
```

Потом массово подтянуть характеристики по уже использованным `subjectID`:

```bash
python3 -m api.main wb-fetch-used-subject-characteristics --products-input data/wb/products_draft.xlsx --output-dir data/wb/characteristics
python3 -m api.main autofill-wb-products-characteristics --products-input data/wb/products_draft.xlsx --characteristics-dir data/wb/characteristics
```

4. Заполнить в draft:

- `wb_parent_id`
- `wb_subject_id`
- `characteristics_json`
- габариты
- вес

5. Импортировать:

```bash
python3 -m api.main wb-import-products --input data/wb/products_draft.xlsx
```

Тест:

```bash
pytest
```
