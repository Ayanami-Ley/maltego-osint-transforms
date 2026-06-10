# Maltego OSINT Transforms

Набор **локальных трансформ** для Maltego (на `maltego-trx`) для разведки по
никнеймам, почтам, телефонам и сайтам. С автопивотингом (нашёл профиль → сразу
вытащил из него почты/телефоны/имена) и Maltego-машинами для запуска цепочек в
один клик.

Всё работает **локально**: код выполняется на твоей машине, со своим Python и
своим IP. Никакого сервера, TDS или регистрации не нужно.

---

## Содержание

1. [Что внутри](#1-что-внутри)
2. [Как это работает (пивотинг)](#2-как-это-работает-пивотинг)
3. [Установка](#3-установка)
4. [Подключение трансформ в Maltego](#4-подключение-трансформ-в-maltego)
5. [Настройки (Transform Settings)](#5-настройки-transform-settings)
6. [Машины (запуск цепочек в один клик)](#6-машины)
7. [Примеры рабочих сценариев](#7-примеры-рабочих-сценариев)
8. [Тесты](#8-тесты)
9. [Траблшутинг](#9-траблшутинг)
10. [Структура проекта](#10-структура-проекта)
11. [Этика и легальность](#11-этика-и-легальность)

---

## 1. Что внутри

| Класс | Transform ID | Local-имя | Вход → Выход | Движок |
|---|---|---|---|---|
| `MaigretUsername` | `osint.maigret.username` | `maigretusername` | ник → URL профилей **+ пивот-сущности** | [maigret](https://github.com/soxoj/maigret) (форк Sherlock, 3000+ сайтов) |
| `HoleheEmail` | `osint.holehe.email` | `holeheemail` | Email → Website сервисов | [holehe](https://github.com/megadose/holehe) (~120 сайтов, проверка через recovery, **писем владельцу не шлёт**) |
| `WebsiteToContacts` | `osint.web.contacts` | `websitetocontacts` | Website/URL → Email, PhoneNumber | парсинг страницы (httpx + regex) |
| `EmailToBreaches` | `osint.hibp.email` | `emailtobreaches` | Email → Website утечек | [Have I Been Pwned API v3](https://haveibeenpwned.com/API/v3) (**нужен API-ключ**) |
| `PhoneToInfo` | `osint.phone.info` | `phonetoinfo` | PhoneNumber → Location, footprint-URL | `phonenumbers` (порт google libphonenumber, оффлайн) |

> **Про PhoneInfoga.** Это Go-бинарь, тащить его в локальную Python-трансформу
> непортируемо. Полезную часть (разбор номера: регион, оператор, тип линии,
> таймзоны + генерация поисковых footprint-ссылок) я реализовал на `phonenumbers` —
> оффлайн и надёжно. Если когда-нибудь нужен именно бинарь PhoneInfoga, в
> `PhoneToInfo.py` несложно добавить shell-out к нему как опцию.

---

## 2. Как это работает (пивотинг)

Сила Maltego — в том, чтобы тянуть граф от узла к узлу. Поэтому трансформы не
просто выдают «плоский» результат, а создают **сущности, по которым можно идти дальше**:

- `MaigretUsername` из извлечённых maigret данных (`ids` на странице профиля)
  достаёт и эмитит как отдельные сущности: `Email`, `PhoneNumber`, `Person`,
  `Alias` (другие ники/ID), `Location`, а также `Website` доменов профилей.
  → Найденную почту сразу гонишь в `holehe` или `EmailToBreaches`.
- `WebsiteToContacts` — обратное направление: со страницы профиля/сайта вытаскивает
  почты и телефоны. → Замыкает петлю `ник → профиль → контакты → утечки`.

Цвета связей в графе: **зелёный** — найденный аккаунт, **красный** — утечка/риск,
**серый** — справочное/footprint. У сущностей в detail-панели — аккуратная
HTML-табличка с деталями (`addDisplayInformation`).

---

## 3. Установка

Нужен **Python 3.9+** и сам **Maltego** (хватит бесплатной Community Edition).

**Linux / macOS:**
```bash
cd maltego-osint
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):** команда называется `python`, не `python3`.
```powershell
cd maltego-osint
python -m venv venv
venv\Scripts\activate
venv\Scripts\python.exe -m pip install -r requirements.txt
```
Если PowerShell не даёт активировать venv — `Set-ExecutionPolicy -Scope Process -Bypass`,
потом снова `venv\Scripts\activate`. Ставить зависимости лучше через
`venv\Scripts\python.exe -m pip`, чтобы они гарантированно попали в тот Python, который
будет дёргать Maltego (см. раздел 9).

Проверка, что трансформы видны (должно показать 5 local-имён):

```
python project.py list
```

Проверка запуска руками (так же дёргает Maltego):

```
python project.py local phonetoinfo "+14155552671"      # оффлайн, ответит сразу
python project.py local maigretusername durov            # пойдёт в сеть
```

В ответ — XML `<MaltegoMessage>...`. Если он есть, пайплайн рабочий.

> **Запиши абсолютный путь к python внутри venv** — он понадобится Maltego:
> - Linux/macOS: `/полный/путь/maltego-osint/venv/bin/python`
> - Windows: `C:\...\maltego-osint\venv\Scripts\python.exe`

---

## 4. Подключение трансформ в Maltego

`Transforms → Manage Transforms → New Local Transform`. Заводишь **пять** трансформ
по таблице из раздела 1. Для каждой:

| Поле | Значение |
|---|---|
| **Transform ID** | строго как в таблице (`osint.maigret.username` и т.д.) — **важно для машин** |
| **Display name** | любое читаемое имя |
| **Input entity type** | см. ниже |
| **Command** | абсолютный путь к python из venv |
| **Parameters** | `project.py local <local-имя>` |
| **Working directory** | абсолютный путь к папке `maltego-osint` |

Типы входных сущностей:

| Трансформа | Input entity type |
|---|---|
| `MaigretUsername` | `maltego.Phrase` (и/или `maltego.Alias`) |
| `HoleheEmail` | `maltego.EmailAddress` |
| `WebsiteToContacts` | `maltego.Website` (и/или `maltego.URL`) |
| `EmailToBreaches` | `maltego.EmailAddress` |
| `PhoneToInfo` | `maltego.PhoneNumber` |

> Значение сущности Maltego подставляет **последним аргументом сам** — в Parameters
> его писать НЕ нужно, только `project.py local <local-имя>`.

---

## 5. Настройки (Transform Settings)

В локальном режиме параметры заданы дефолтами прямо в коде; читаются также из
Transform Settings / переменных окружения, где это указано.

| Ключ | Дефолт | Где | Что |
|---|---|---|---|
| `maigret.topsites` | 300 | MaigretUsername | сколько сайтов из топа проверять (больше = полнее, но дольше) |
| `maigret.timeout` | 20 | MaigretUsername | таймаут на сайт, сек |
| `maigret.proxy` | — | MaigretUsername | `socks5://127.0.0.1:9050` (Tor) или `http://host:port` |
| `holehe.timeout` | 15 | HoleheEmail | таймаут http-запроса, сек |
| `web.timeout` | 15 | WebsiteToContacts | таймаут загрузки страницы, сек |
| `web.proxy` | — | WebsiteToContacts | прокси для запроса |
| `hibp.apikey` | — | EmailToBreaches | **API-ключ HIBP** (или ENV `HIBP_API_KEY`) |
| `hibp.timeout` | 20 | EmailToBreaches | таймаут запроса к HIBP |
| `phone.region` | — | PhoneToInfo | код страны (RU/US/...) для номеров без `+` |

Чтобы поменять дефолт без UI — правь значение прямо в соответствующем
`transforms/*.py` (значения собраны вверху методов). Если хочешь крутилки в UI
Maltego — поднимай проект как TDS-сервер (`python project.py runserver`), тогда
`getTransformSetting` начнёт читать настройки из конфигурации трансформы.

**API-ключ HIBP** берётся на https://haveibeenpwned.com/API/Key (платно).
Без ключа `EmailToBreaches` вернёт понятное сообщение, а не упадёт.

---

## 6. Машины

В папке `machines/` — две Maltego Machine (+ свой `machines/README.md`):

- **UsernameRecon** (`machines/UsernameRecon.machine`) — последовательная цепочка:
  `maigret` (ник → профили + извлечённые email) → `holehe` (где зареганы почты) →
  `HIBP` (утечки по ним). Следующая трансформа автоматически срабатывает только на
  сущностях подходящего типа из предыдущего вывода.
- **EmailRecon** (`machines/EmailRecon.machine`) — по одному email параллельно
  запускает `holehe` и `HIBP`.

Как добавить: `Machines → Manage Machines → New Machine`, выбрать тип «Macro»,
вставить содержимое `.machine` файла, сохранить и запустить на сущности нужного типа.

> Машины ссылаются на трансформы по **Transform ID**, поэтому ID при заведении
> локальных трансформ задавай ровно как в таблице. Переименуешь — поправь строки
> `run("...")` в `.machine`.

---

## 7. Примеры рабочих сценариев

**Полный пробив по нику.** Кидаешь `Phrase` с ником → запускаешь машину
`UsernameRecon`. Граф сам разворачивается: профили по соцсеткам, из них — почты и
телефоны, по почтам — где ещё зареганы и в каких утечках светились.

**Точечно по почте.** `EmailAddress` → `HoleheEmail` (сервисы) и `EmailToBreaches`
(утечки), или сразу машина `EmailRecon`.

**От сайта к контактам.** `Website`/`URL` → `WebsiteToContacts` → почты/телефоны →
их обратно в holehe/HIBP.

**Телефон.** `PhoneNumber` → `PhoneToInfo` → регион (`Location`), оператор/тип в
сводке и готовые поисковые ссылки (`URL`) для ручного дожима.

---

## 8. Тесты

`tests/test_transforms.py` — юнит-тесты на моках (парсинг вывода maigret и HIBP,
извлечение контактов со страницы, оффлайн-разбор телефона, ветки ошибок).

```bash
python tests/test_transforms.py
# -> ALL TESTS PASSED
```

Сети не требуют (кроме оффлайн-разбора телефона, который и так локальный).

---

## 9. Траблшутинг

Ниже — реальные проблемы, которые встречаются при настройке (особенно на Windows),
с причиной и фиксом.

### Установка и venv (Windows)

**`python3 : Имя "python3" не распознано...`**
На Windows команда называется `python`, а не `python3`. Используй:
```powershell
python -m venv venv
```
Если и `python` не находится — пробуй лаунчер `py -3 -m venv venv`. Если оба ругаются —
Python не в PATH: переустанови с python.org с галочкой **«Add python.exe to PATH»**.

**PowerShell не даёт активировать venv** (ошибка про «выполнение сценариев отключено»)
Разово разреши для текущей сессии и активируй заново:
```powershell
Set-ExecutionPolicy -Scope Process -Bypass
venv\Scripts\activate
```
После активации в начале строки появится `(venv)`.

**`ModuleNotFoundError: No module named 'maltego_trx'`** (в Maltego, exit code 1)
Зависимости встали не в тот Python, который дёргает Maltego. Ставь их **именно в venv**
и проверь импорт:
```powershell
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -c "import maltego_trx; print('OK')"
```
Должно напечатать `OK`. В Command у трансформы должен стоять этот же
`...\venv\Scripts\python.exe`, а не глобальный питон.

### Регистрация и запуск

**`INFO: Ignoring File: "_common" does not contain a class of the same name`**
Это **не ошибка**, а нормальный INFO-лог. `_common.py` — файл с хелперами, а не
трансформа, поэтому он пропускается. Так и должно быть. Главное — что в
`python project.py list` видны все 5 local-имён.

**`can't open file 'C:\Users\...\project.py': No such file or directory`** (exit code 2)
У трансформы **не задан или неверный Working directory**. Python ищет `project.py`
не там. Открой `Manage Transforms → Edit` у этой трансформы и проверь:
- **Working directory:** `C:\Users\<ты>\Desktop\maltego-osint`
- **Command:** `C:\Users\<ты>\Desktop\maltego-osint\venv\Scripts\python.exe`
- **Parameters:** `project.py local <local-имя>`

Частая причина: при заведении пятёрки трансформ у одной-двух поля заполнились не
полностью. Пробегись по всем пяти и сверь.

**`python project.py list` не показывает трансформу**
Имя файла должно строго совпадать с именем класса (`MaigretUsername.py` ↔
`class MaigretUsername`) — требование `maltego-trx`.

### Результаты

**Кракозябры в выводе** (`holehe: ��������� ��� ...`)
Кодировка: вывод в UTF-8, а Windows-клиент читал его как cp1251. **Уже починено** —
в `project.py` принудительно выставлен UTF-8 на stdout/stderr. Если вдруг используешь
старую версию файла, либо обнови `project.py`, либо задай переменную окружения и
перезапусти Maltego:
```powershell
setx PYTHONUTF8 1
```

**`HIBP: нет API-ключа`**
Ожидаемо: HIBP API платный. Возьми ключ на https://haveibeenpwned.com/API/Key, затем:
```powershell
setx HIBP_API_KEY "твой_ключ"
```
и **перезапусти Maltego** (`setx` подхватывается только новыми процессами). Не нужен
пробив по утечкам — просто не запускай `EmailToBreaches`, на остальные 4 трансформы
это не влияет.

**holehe пишет «не найдено», хотя почта рабочая**
Часть сайтов отвечает rate-limit'ом, и holehe помечает их как «не определено». Это
норма, попробуй позже или с прокси.

**maigret долго / мало находит**
Крути `maigret.topsites` и `maigret.timeout`. Полный прогон по большой базе сайтов
медленный по своей природе.

**WebsiteToContacts «не удалось загрузить»**
Сайт недоступен, блочит ботов или это SPA (контент рисуется JS — статический HTML
пустой). Трансформа парсит только статический HTML; для footprint лучше брать страницы
«Контакты» обычных сайтов. При необходимости задай `web.proxy`.

### Общий приём для дебага

Maltego проглатывает stderr. Любую трансформу можно запустить руками из терминала и
увидеть настоящую ошибку или результат:
```powershell
python project.py local maigretusername durov
python project.py local phonetoinfo "+14155552671"
```

---

## 10. Структура проекта

```
maltego-osint/
├── project.py                  # раннер maltego-trx (list / local / runserver)
├── requirements.txt
├── README.md
├── transforms/
│   ├── __init__.py             # регистрация всех трансформ
│   ├── _common.py              # хелперы: классификация id, HTML, regex, цвета
│   ├── MaigretUsername.py      # ник -> профили + пивот-сущности
│   ├── HoleheEmail.py          # email -> сервисы
│   ├── WebsiteToContacts.py    # сайт/URL -> email/телефоны
│   ├── EmailToBreaches.py      # email -> утечки (HIBP)
│   └── PhoneToInfo.py          # телефон -> регион/оператор + footprint
├── machines/
│   ├── README.md
│   ├── UsernameRecon.machine   # ник -> maigret -> holehe + HIBP (цепочка)
│   └── EmailRecon.machine      # email -> holehe + HIBP (параллельно)
└── tests/
    └── test_transforms.py
```

---

## 11. Этика и легальность

Все движки — публичные инструменты, предназначенные для **легальной** разведки по
открытым источникам: пентест с разрешением, проверка собственных утечек,
расследования с правовым основанием. holehe не отправляет писем владельцу почты,
HIBP отдаёт только факт присутствия в утечках. Ответственность за то, по кому и
зачем ты это запускаешь, — на тебе.
