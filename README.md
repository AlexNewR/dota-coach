# Живой коуч Dota 2 (мид)

VAC-safe подсказки во время матча: фарм, предметы и смерти. Учится на **про-миде** Lone Druid, Io, Keeper of the Light и Earth Spirit.

## Откуда статистика

1. **Основной источник — Parse API поверх [Dota2ProTracker](https://dota2protracker.com)**  
   Ключ `PARSE_API_KEY` лежит только в локальном `.env` (файл в `.gitignore`). Коллектор вызывает `get_heroes` / `get_matches` на parse.bot и берёт mid (позиция 2) для Lone Druid, Io и KotL.
2. **Запасной контур** — HTML страницы героя D2PT, затем OpenDota для поминутныx рядов, затем снимок mid-билдов.

Нейросеть — классификатор следующего предмета (MLP на NumPy) по purchase-таймингам про-мидера. Фарм и смерти сравниваются с перцентилями/нормой, это не «кликай сюда».

## Герои и роль

- Роль: **мид** (`lane_role = 2`)
- Lone Druid (80), Io (91), Keeper of the Light (90), Earth Spirit (107)
- Билды с D2PT / OpenDota NN: KotL — urn/vessel/travels/octarine; LD — treads/maelstrom/mjollnir/aghs/diffusal; Io mid — bottle/wand/aghs/bkb; ES — bottle/urn/blink/bkb

## Установка

Нужен Python 3.11+.

```powershell
cd "C:\Users\alwexn\Desktop\dota train"
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
```

В Steam у Dota 2:

- параметры запуска: `-gamestateintegration`
- видео: **Borderless Windowed**

```powershell
python scripts\install_gsi.py
python scripts\collect_data.py
python scripts\train_items.py
python scripts\run_coach.py
```

Оверлей: http://127.0.0.1:3000/

Без живой Dota проверка контура:

```powershell
python scripts\run_demo.py
```

`collect_data.py --no-opendota` — только ProTracker (или снимок), без OpenDota.

NN-датасет (OpenDota, **только mid** + фильтр даты/ранга):

```powershell
python scripts\collect_data.py --opendota-primary --per-hero 400 --max-age-days 540 --min-rank 70
python scripts\train_items.py
```

Сборка для другого ПК и облачное обновление (GitHub Releases):

```powershell
python scripts\publish_update.py --version 0.2.0
```

На другом ПК один раз распакуй `DotaCoach.zip` и запусти `ЗАПУСК.bat`. Дальше коуч сам проверяет latest release и обновляется. Репозиторий должен быть **public**.

- только `lane_role = 2` (без саппорт/офф/сейф fallback)
- `--max-age-days` — окно по `start_time` (для LD/Io mid шире по умолчанию)
- `--min-rank` — pub Divine+ (70); league/pro принимаются отдельно
- env: `OPENDOTA_MAX_AGE_DAYS`, `OPENDOTA_MIN_RANK`, `OPENDOTA_PER_HERO`

## Что умеет в лайве

GSI отдаёт только **твоего** героя. Коуч не видит позиции врагов и не водит мышь.

- Фарм: LH ниже p25 про-мидера дольше 45 секунд
- Предметы: следующий слот как у D2PT / если купил не то
- Смерть: слишком рано относительно нормы, золото в кармане, нет TP

Подсказки не чаще чем раз в 15–30 секунд.

## Структура

- `src/dota_coach/gsi/` — GSI и установка конфига
- `src/dota_coach/data/` — ProTracker, OpenDota fallback, синтетика
- `src/dota_coach/models/` — фарм, смерти, item-NN
- `src/dota_coach/coach/` — когда показывать hint
- `src/dota_coach/overlay/static/` — оверлей
