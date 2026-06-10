# Maltego Machines

Машины автоматизируют цепочки трансформ в один клик. Они ссылаются на трансформы
по их **Transform ID**, поэтому при добавлении локальных трансформ в Maltego
задавай ровно эти ID:

| Трансформа | Transform ID (обязательно так) | Local-имя | Вход |
|---|---|---|---|
| HoleheEmail | `osint.holehe.email` | `holeheemail` | Email |
| MaigretUsername | `osint.maigret.username` | `maigretusername` | Phrase/Alias |
| WebsiteToContacts | `osint.web.contacts` | `websitetocontacts` | Website/URL |
| EmailToBreaches | `osint.hibp.email` | `emailtobreaches` | Email |
| PhoneToInfo | `osint.phone.info` | `phonetoinfo` | PhoneNumber |

## Как добавить машину

1. В Maltego: вкладка **Machines → Manage Machines → New Machine**.
2. Дай имя, выбери «Macro» (или Blank), вставь содержимое `.machine` файла.
3. Сохрани и запусти на сущности подходящего типа (для `UsernameRecon` — кинь
   `Phrase`/`Alias` с ником и запусти машину).

## Логика

- **UsernameRecon** — последовательная цепочка. `maigret` отдаёт `URL` профилей и
  пивот-сущности (`Email`, `Alias`, `PhoneNumber`, ...). Дальше `holehe` и `HIBP`
  срабатывают автоматически **только** на сущностях `Email` из этого вывода —
  фильтрация по типу входа встроена в Maltego. Получается полный авто-граф.
- **EmailRecon** — две параллельные ветки (`paths`): по одной почте сразу и
  holehe, и HIBP.

> Если переименуешь Transform ID у себя — поправь строки `run("...")` в `.machine`.
