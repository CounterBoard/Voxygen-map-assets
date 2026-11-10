# Voxygen — автоматическая публикация карты

Это не набор тайлов для ручной загрузки. Здесь находятся только скрипт и workflow:
один исходный файл карты передаётся в GitHub Actions, тайлы генерируются автоматически,
затем готовая статика публикуется в Cloudflare Worker `voxygen-map-assets`.

## Как это будет работать после интеграции с основным Worker

1. Администратор загружает один файл карты в Voxygen.
2. Основной Worker сохраняет исходник как Release Asset в GitHub.
3. Основной Worker вызывает `workflow_dispatch` этого репозитория, передавая URL файла и версию карты.
4. GitHub Actions скачивает файл, запускает `tools/build_map.py` и публикует `public/` через Wrangler.
5. Voxygen читает `/world-map/manifest.json`, затем загружает нужные тайлы по мере просмотра и масштабирования.

## Однократная настройка GitHub

В репозитории открой Settings → Secrets and variables → Actions → New repository secret:

- `CLOUDFLARE_API_TOKEN` — API token Cloudflare для публикации Workers;
- `CLOUDFLARE_ACCOUNT_ID` — Cloudflare Account ID.

Для токена требуется право редактирования Workers Scripts в нужном аккаунте. Не помещайте токен в код, workflow inputs или публичные файлы.

Для автоматического запуска из основного Worker токен `GITHUB_TOKEN`, используемый им для загрузки Release Asset, должен также иметь право `Actions: write` для этого репозитория. Если текущий токен не имеет такого права, понадобится отдельный secret/credential в основном Worker.

## Ручной тест конвейера

Откройте вкладку Actions → Process and publish world map → Run workflow. Передайте:
- `image_url`: публичный URL Release Asset с исходной картой;
- `map_version`: уникальный идентификатор, например `map-20261110-2300`.

После успешного запуска Cloudflare создаст Worker `voxygen-map-assets` (если его ещё нет) и опубликует manifest по адресу:
`https://voxygen-map-assets.<ваш-subdomain>.workers.dev/world-map/manifest.json`

`<ваш-subdomain>` нужно заменить на фактический Cloudflare account subdomain.

## Текущий и будущий форматы

Сейчас manifest описывает `source.type = "deepzoom"` и URL-шаблон тайлов. В manifest предусмотрено место для будущего источника `url-grid` с 12 строками, 12 столбцами и 144 публичными URL. После появления этих URL приложение сможет выбирать подходящий адаптер источника без изменения загрузки исходной карты.

## Важно: интеграция ещё не завершена

Этот репозиторийный пакет реализует автоматическую обработку и публикацию. Чтобы загрузка одной карты из Voxygen запускала его без ручного захода в Actions, нужно внести небольшой вызов GitHub Actions `workflow_dispatch` в существующий основной Worker после успешной загрузки Release Asset. Кроме того, приложение должно переключиться с прежнего единого изображения на загрузчик, читающий manifest и Deep Zoom тайлы. Эти два изменения нельзя считать уже выполненными.
