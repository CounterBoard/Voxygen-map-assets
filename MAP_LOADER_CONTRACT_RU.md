# Контракт загрузчика карты Voxygen

Manifest: GET /world-map/manifest.json

Текущий источник:
- source.type = "deepzoom"
- source.width / source.height — исходные размеры
- source.tileSize — 512
- source.minLevel / source.maxLevel — уровни пирамиды
- source.tileUrlTemplate — шаблон с {level}, {x}, {y}
- source.previewUrl — обзорное изображение

Будущий источник:
- source.type = "url-grid"
- source.rows = 12
- source.columns = 12
- source.urls = массив из 144 публичных URL, построчно слева направо и сверху вниз (абсолютные или относительно manifest origin)
- source.previewUrl — небольшое обзорное изображение, которое показывается до загрузки плиток

Клиент обязан:
1. сначала показать preview;
2. загружать только тайлы, пересекающие видимую область;
3. отменять/игнорировать запросы тайлов вне актуального viewport;
4. кэшировать immutable URL;
5. при смене manifest version очищать только ссылки на старую версию, не удаляя browser cache;
6. выбирать реализацию по source.type.
