# NSFW Pipeline

Локальный пайплайн для двух задач:

1. MVP: найти интимные зоны на фото и автоматически замазать их.
2. Магазинный пайплайн: после цензуры привести фото к единому формату, добавить watermark и сохранить готовые карточки.

## Что уже умеет

- обрабатывать всю папку изображений
- искать NSFW-зоны через `NudeNet`
- замазывать зоны `blur` / `pixelate` / `block`
- сохранять JSON-отчёт по детекциям
- строить второй этап подготовки карточек:
  - resize
  - white background
  - watermark text
  - watermark image
  - export в `jpg` или `webp`

## Структура

- `data/raw` — исходные фото
- `data/censored` — фото после автоцензуры
- `data/final` — готовые фото для магазина или маркетплейса
- `configs/pipeline.example.json` — пример конфига

## Установка

```bash
cd /workspace/vibecoding/parser/python/nsfw-pipeline
source .venv/bin/activate
python3 -m pip install -U pip setuptools wheel
python3 -m pip install -e ".[dev]"
```

## Этап 1. MVP за 1 день

Положи фото в `data/raw`, потом:

```bash
cd /workspace/vibecoding/parser/python/nsfw-pipeline
source .venv/bin/activate
PYTHONPATH=src python3 -m nsfw_pipeline.main censor-folder \
  --input data/raw \
  --output data/censored \
  --effect blur
```

Будут созданы:

- обработанные изображения в `data/censored`
- отчёт `data/censored/detections_report.json`

## Этап 2. Рабочий пайплайн для магазина

После этапа цензуры:

```bash
cd /workspace/vibecoding/parser/python/nsfw-pipeline
source .venv/bin/activate
PYTHONPATH=src python3 -m nsfw_pipeline.main render-final \
  --input data/censored \
  --output data/final \
  --format webp \
  --max-width 1200 \
  --max-height 1200 \
  --watermark-text "demo-shop.ru"
```

## Команды

### Автоцензура папки

```bash
PYTHONPATH=src python3 -m nsfw_pipeline.main censor-folder \
  --input data/raw \
  --output data/censored \
  --effect blur \
  --blur-kernel 61 \
  --labels FEMALE_BREAST_EXPOSED FEMALE_GENITALIA_EXPOSED MALE_GENITALIA_EXPOSED BUTTOCKS_EXPOSED
```

### Подготовка финальных карточек

```bash
PYTHONPATH=src python3 -m nsfw_pipeline.main render-final \
  --input data/censored \
  --output data/final \
  --format jpg \
  --jpeg-quality 92 \
  --watermark-text "brand"
```

## Примечания

- `NudeNet` нужен только для детекции. Замазку делает наш скрипт через `OpenCV`.
- На первом этапе лучше брать `blur`.
- Для production можно потом заменить `NudeNet` на свой `YOLO`-детектор, не меняя второй этап пайплайна.
