#!/usr/bin/env python3
"""
Maltego OSINT — точка входа для локальных трансформ.

Команды:
    python project.py list                       # список трансформ + их local-имена
    python project.py local <Имя> <значение>     # локальный запуск (так зовёт Maltego)
    python project.py runserver                  # поднять как TDS-сервер (необязательно)

Локальные имена для Maltego (регистр не важен):
    HoleheEmail       (вход: Email)
    MaigretUsername   (вход: Alias / Phrase / любой ник)
"""
import sys

# Windows: принудительно UTF-8 на выводе, иначе кириллица в Maltego
# превращается в кракозябры (клиент читает stdout в системной cp1251).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from maltego_trx.registry import register_transform_classes
from maltego_trx.server import application
from maltego_trx.handler import handle_run

import transforms

register_transform_classes(transforms)

handle_run(__name__, sys.argv, application)
