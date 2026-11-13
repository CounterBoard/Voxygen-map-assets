# Voxygen — обработка и публикация карты мира

Репозиторий обслуживает отдельный Worker статических ресурсов карты:

- Worker: `voxygen-map-assets`;
- публичный базовый адрес: `https://voxygen-map-assets.counterboard.workers.dev`;
- каталог публикации: `public/`;
- manifest: `/world-map/manifest.json`.

Исходник карты не хранится в этом репозитории. Основной Worker загружает его в GitHub Release репозитория `CounterBoard/Voxygen-map-storage`, после чего запускает workflow этого репозитория.

## Фактическая последовательность публикации

1. Главный инспектор выбирает квадратное изображение PNG, JPEG или WebP размером не более 90 000 000 байт.
2. Frontend отправляет файл в `POST /api/map` основного Worker, передаёт Telegram Init Data, MIME-тип и `X-Map-Size`, показывает прогресс XHR.
3. Основной Worker проверяет роль главного инспектора, MIME-тип, объявленный размер и наличие тела запроса. Файл потоково передаётся в GitHub Release `world-map` через `FixedLengthStream`.
4. URL исходного Release Asset и MIME-тип сохраняются в D1 `app_settings`. Сама карта и тайлы в D1 не записываются.
5. Основной Worker вызывает GitHub Actions API: workflow `.github/workflows/publish-map.yml`, событие `workflow_dispatch`, ref `main`, inputs `image_url` и `map_version`.
6. Workflow проверяет адрес исходного Release Asset, скачивает его с ограничением 90 000 000 байт и разрешённым HTTPS redirect, не пересылая GitHub token на хост файла.
7. `tools/build_map.py` проверяет версию и изображение, применяет EXIF orientation, требует квадратный растр и генерирует preview и многоуровневые WebP-тайлы Deep Zoom.
8. Workflow публикует каталог `public/` в Cloudflare Worker `voxygen-map-assets` через Wrangler.
9. Frontend опрашивает manifest до 25 минут. Когда `mapVersion` совпадает с ожидаемой версией и preview успешно декодируется, новая карта показывается в приложении.

Загрузка исходника и публикация готовых тайлов — разные этапы. Успешный ответ основного Worker означает, что исходник сохранён и pipeline поставлен в очередь, а не то, что публикация уже завершена.

## Формат Deep Zoom

Текущий manifest расположен по адресу:

`GET /world-map/manifest.json`

Основные поля:

- `schemaVersion` — версия схемы manifest;
- `mapVersion` — уникальная версия карты;
- `source.type` — `deepzoom`;
- `source.width`, `source.height` — размеры исходного растра;
- `source.tileSize` — 512 пикселей;
- `source.minLevel` и `source.maxLevel` — границы уровней пирамиды;
- `source.format` — `webp`;
- `source.coordinateSystem` — фиксированные границы Minecraft-мира;
- `source.tileUrlTemplate` — шаблон URL с `{level}`, `{x}`, `{y}`;
- `source.previewUrl` — URL обзорного изображения;
- `generated.tileCount` — количество созданных тайлов.

Тайлы находятся в версионном каталоге:

`/world-map/versions/<mapVersion>/tiles/<level>/<x>_<y>.webp`

Preview:

`/world-map/versions/<mapVersion>/preview.webp`

Геометрия мира не выводится из размера растра. Используется фиксированная система координат блоков Minecraft: X и Z от -3008 до 3007 включительно. Поэтому исходный растр должен быть квадратным, но его разрешение может отличаться от 6016×6016.

## Генератор

Файл: `tools/build_map.py`

Параметры:

- размер тайла — 512×512 пикселей;
- максимальная сторона исходного растра — 8944 пикселя;
- общий предел растра — 80 000 000 пикселей; для квадратного растра это ограничение соответствует максимальной стороне 8944 пикселя и учитывает защитный лимит Pillow от decompression bomb;
- preview ограничивается стороной 1200 пикселей;
- WebP сохраняется без потерь (`lossless=True`);
- каждый уровень строится из исходного изображения с уменьшением в 2 раза на уровень;
- неполные крайние тайлы сохраняют фактический размер, а не дополняются до 512×512;
- версия ограничена символами ASCII: буквы, цифры, точка, подчёркивание и дефис.

Генератор записывает тайлы в версионный каталог, затем создаёт временный manifest и заменяет им `manifest.json`. Это не даёт manifest ссылаться на тайлы до окончания их локальной генерации.

## Безопасная загрузка исходника

Файл `tools/download_release_asset.py` используется workflow перед генератором.

Он:
- принимает только HTTPS URL Release Asset из `CounterBoard/Voxygen-map-storage`;
- допускает только расширения PNG, JPG/JPEG и WebP;
- запрещает query/fragment, userinfo и произвольные пути;
- допускает только HTTPS redirect на allowlist GitHub asset hosts;
- не передаёт `MAP_SOURCE_GITHUB_TOKEN` на asset host;
- запрещает цепочку дополнительных redirect;
- проверяет `Content-Length`, если он присутствует;
- ограничивает фактически скачанные байты 90 000 000;
- удаляет частичный файл при ошибке и отклоняет пустой ответ.

Само содержимое изображения затем проверяет Pillow в генераторе: фактический формат должен быть PNG, JPEG или WebP; неподдерживаемый/повреждённый файл не может завершить сборку.

## Кэширование и HTTP

Файл `public/_headers` задаёт:

- `/world-map/versions/*`: CORS для чтения, `nosniff`, `Cache-Control: public, max-age=31536000, immutable`;
- `/world-map/manifest.json`: `Cache-Control: no-store` и CORS.

Manifest не кэшируется, чтобы клиент мог обнаружить новую версию. URL тайлов и preview содержат `mapVersion`, поэтому опубликованные ресурсы конкретной версии неизменяемы и могут долго храниться в браузерном/edge cache.

Worker использует Workers Static Assets (`assets.directory = ./public`, `run_worker_first = false`). Файл `src/index.js` является fallback для запросов, которые не соответствуют опубликованному статическому ресурсу; он возвращает 404.

## Будущий формат url-grid

Контракт загрузчика резервирует `source.type = "url-grid"` с 12 строками, 12 столбцами и массивом из 144 URL. Клиент содержит ветку выбора тайлов для этого типа источника, однако текущий генератор создаёт только Deep Zoom, а `futureSources.urlGrid.urls` остаётся пустым. Это не действующий режим публикации.

## Секреты и конфигурация

Secrets репозитория:

- `CLOUDFLARE_API_TOKEN` — право публикации Worker;
- `CLOUDFLARE_ACCOUNT_ID` — Cloudflare Account ID;
- `MAP_SOURCE_GITHUB_TOKEN` — необязательный read token, нужен только если репозиторий исходников приватный.

Secrets основного Worker `voxygen`:

- `GITHUB_TOKEN` — загрузка Release Asset в `Voxygen-map-storage`;
- `MAP_PIPELINE_GITHUB_TOKEN` — запуск workflow в `Voxygen-map-assets`, разрешение Actions: read/write.

Обычные переменные основного Worker:

- `GITHUB_OWNER = CounterBoard`;
- `GITHUB_REPO = Voxygen-map-storage`;
- `GITHUB_RELEASE_TAG = world-map`.

Значения секретов не хранятся в коде и не должны попадать в логи или inputs workflow.

## Проверки

Workflow `.github/workflows/validate-map-pipeline.yml` запускается при push в `main`, при push в feature-ветку проверки геометрии и при pull request в `main`. Он выполняет:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Тесты проверяют:
- фиксированную систему координат мира;
- генерацию manifest на квадратном изображении;
- отказ от неквадратного растра;
- наличие и декодируемость WebP-тайлов;
- ожидаемое количество тайлов и размеры preview;
- отказ от небезопасного идентификатора версии;
- отказ от растра, превышающего общий pixel budget, до преобразования в RGBA;
- allowlist URL/redirect при скачивании Release Asset;
- запрет передачи токена на хост загрузки;
- ограничения объявленного и фактического размера;
- удаление неполного файла при ошибке.

Workflow `.github/workflows/publish-map.yml` — отдельный workflow публикации. Он запускается по `workflow_dispatch` и действительно развёртывает статические ресурсы в Cloudflare. Его успешное выполнение подтверждает завершение конкретного запуска публикации, но не заменяет проверку доступности ресурсов из пользовательского клиента.

## Исходные репозитории

- Основное приложение: https://github.com/CounterBoard/Voxygen
- Pipeline и статические ресурсы: https://github.com/CounterBoard/Voxygen-map-assets
- Исходники карт: https://github.com/CounterBoard/Voxygen-map-storage
- Release исходной карты: https://github.com/CounterBoard/Voxygen-map-storage/releases/tag/world-map
