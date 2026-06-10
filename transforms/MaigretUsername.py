"""
MaigretUsername — Maltego local transform.

Вход:  Alias / Phrase / любой ник
Выход: URL на каждый найденный профиль + ПИВОТ-сущности, вытащенные из профилей
       (Email, PhoneNumber, Person, Alias, Location, Website-домена) + сводка.

Движок: maigret (форк Sherlock), запуск как subprocess с JSON-отчётом (-J simple).
"""
import os
import sys
import json
import tempfile
import subprocess
from urllib.parse import urlparse

from maltego_trx.entities import URL, Website, Phrase
from maltego_trx.transform import DiscoverableTransform

from ._common import (
    classify_ids, html_table, COLOR_FOUND, COLOR_INFO,
)


def _run_maigret(username, top_sites, timeout, proxy):
    """Запускает maigret, возвращает dict {sitename: {...}} только по найденным."""
    workdir = tempfile.mkdtemp(prefix="maigret_")
    cmd = [
        sys.executable, "-m", "maigret", username,
        "-J", "simple",
        "-fo", workdir,
        "--no-progressbar", "--no-color", "--no-recursion",
        "--timeout", str(timeout),
        "--top-sites", str(top_sites),
    ]
    if proxy:
        cmd += ["--proxy", proxy]

    hard_limit = timeout * 3 + top_sites
    subprocess.run(cmd, capture_output=True, text=True, timeout=hard_limit)

    # maigret заменяет '/' на '_' в имени файла отчёта — повторяем, иначе не найдём
    safe_name = username.replace("/", "_")
    report = os.path.join(workdir, "report_%s_simple.json" % safe_name)
    if not os.path.exists(report):
        return {}
    with open(report, "r", encoding="utf-8") as fh:
        txt = fh.read().strip()
    return json.loads(txt) if txt else {}


def _domain_of(url):
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:  # noqa: BLE001
        return ""


class MaigretUsername(DiscoverableTransform):
    """Никнейм -> профили + пивот-сущности (maigret)."""

    @classmethod
    def create_entities(cls, request, response):
        username = (request.Value or "").strip()
        if not username:
            response.addEntity(Phrase, "Пустой ник")
            return

        def _setting(key, default):
            val = request.getTransformSetting(key)
            try:
                return int(val) if val not in (None, "") else default
            except (TypeError, ValueError):
                return default

        top_sites = _setting("maigret.topsites", 300)
        timeout = _setting("maigret.timeout", 20)
        proxy = request.getTransformSetting("maigret.proxy") or ""

        try:
            data = _run_maigret(username, top_sites, timeout, proxy)
        except subprocess.TimeoutExpired:
            response.addEntity(Phrase, "maigret: таймаут по нику %s" % username)
            return
        except Exception as exc:  # noqa: BLE001
            response.addEntity(Phrase, "Ошибка maigret: %s" % exc)
            return

        if not data:
            response.addEntity(Phrase, "maigret: профилей для %s не найдено" % username)
            return

        all_ids = {}      # объединённые извлечённые данные со всех профилей
        domains = set()

        for sitename, site in sorted(data.items()):
            url = site.get("url_user") or ""
            status = site.get("status") if isinstance(site.get("status"), dict) else {}
            site_info = site.get("site") if isinstance(site.get("site"), dict) else {}
            tags = status.get("tags") or site_info.get("tags") or []
            ids = status.get("ids") or {}

            ent = response.addEntity(URL, url or sitename)
            ent.setLinkLabel(sitename)
            ent.setLinkColor(COLOR_FOUND)
            ent.setWeight(100)
            ent.addProperty("short-title", "Title", "loose", sitename)
            ent.addProperty("url", "URL", "strict", url)
            ent.addProperty("source.username", "Source username", "loose", username)
            if tags:
                ent.addProperty("maigret.tags", "Tags", "loose", ", ".join(map(str, tags)))
            ent.addDisplayInformation(
                html_table([("Site", sitename), ("URL", url),
                            ("Tags", ", ".join(map(str, tags))),
                            ("Extracted", json.dumps(ids, ensure_ascii=False) if ids else "")]),
                title="maigret",
            )

            # собираем пивот-данные
            for k, v in ids.items():
                all_ids.setdefault(k, [])
                vs = v if isinstance(v, list) else [v]
                all_ids[k].extend(vs)
            d = _domain_of(url)
            if d:
                domains.add(d)

        # ПИВОТ: типизированные сущности из извлечённых данных
        pivots = classify_ids(all_ids)
        for etype, value in pivots:
            pe = response.addEntity(etype, value)
            pe.setLinkLabel("maigret: extracted")
            pe.addProperty("source.username", "Source username", "loose", username)

        # домены профилей -> Website (для инфраструктурных трансформ)
        for d in sorted(domains):
            we = response.addEntity(Website, d)
            we.setLinkColor(COLOR_INFO)
            we.setLinkLabel("profile host")

        response.addEntity(
            Phrase,
            "maigret: %d профил(ей), %d пивот-сущност(ей) для %s"
            % (len(data), len(pivots), username),
        )
