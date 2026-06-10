"""
EmailToBreaches — Maltego local transform.

Вход:  Email
Выход: Website (домен утечки, пивотится дальше) на каждую утечку + сводка.

Движок: Have I Been Pwned API v3 (https://haveibeenpwned.com/API/v3).
ВАЖНО: нужен платный API-ключ. Передаётся через Transform Setting `hibp.apikey`
или переменную окружения HIBP_API_KEY.
"""
import os
from urllib.parse import quote

import httpx

from maltego_trx.entities import Website, Phrase
from maltego_trx.transform import DiscoverableTransform

from ._common import html_table, COLOR_BREACH

_API = "https://haveibeenpwned.com/api/v3/breachedaccount/%s?truncateResponse=false"
_UA = "maltego-osint-transform"


def query_hibp(email, api_key, timeout=20):
    """
    Запрос к HIBP. Возвращает (status, data):
      status: 'ok' | 'clean' | 'unauthorized' | 'ratelimited' | 'error'
      data:   список breach-dict для 'ok', иначе строка-пояснение.
    """
    url = _API % quote(email, safe="")
    headers = {"hibp-api-key": api_key, "user-agent": _UA}
    try:
        r = httpx.get(url, headers=headers, timeout=httpx.Timeout(timeout))
    except Exception as exc:  # noqa: BLE001
        return "error", str(exc)

    if r.status_code == 200:
        return "ok", r.json()
    if r.status_code == 404:
        return "clean", "утечек не найдено"
    if r.status_code == 401:
        return "unauthorized", "неверный или отсутствующий API-ключ"
    if r.status_code == 429:
        return "ratelimited", "rate limit, retry-after=%s" % r.headers.get("retry-after", "?")
    return "error", "HTTP %s" % r.status_code


class EmailToBreaches(DiscoverableTransform):
    """Email -> утечки по базе Have I Been Pwned."""

    @classmethod
    def create_entities(cls, request, response):
        email = (request.Value or "").strip().lower()
        if "@" not in email:
            response.addEntity(Phrase, "Это не похоже на email: %s" % email)
            return

        api_key = (request.getTransformSetting("hibp.apikey")
                   or os.environ.get("HIBP_API_KEY") or "").strip()
        if not api_key:
            response.addEntity(
                Phrase,
                "HIBP: нет API-ключа. Задайте Transform Setting 'hibp.apikey' "
                "или переменную окружения HIBP_API_KEY.",
            )
            return

        try:
            timeout = float(request.getTransformSetting("hibp.timeout") or 20)
        except (TypeError, ValueError):
            timeout = 20.0

        status, data = query_hibp(email, api_key, timeout)

        if status == "clean":
            response.addEntity(Phrase, "HIBP: для %s утечек не найдено" % email)
            return
        if status != "ok":
            response.addEntity(Phrase, "HIBP (%s): %s" % (status, data))
            return

        for b in data:
            domain = (b.get("Domain") or "").strip()
            title = b.get("Title") or b.get("Name") or "breach"
            value = domain or title
            ent = response.addEntity(Website, value)
            ent.setLinkLabel("breach: %s" % title)
            ent.setLinkColor(COLOR_BREACH)
            ent.setWeight(100)
            ent.addProperty("hibp.name", "Breach", "loose", b.get("Name", ""))
            ent.addProperty("hibp.date", "Breach date", "loose", b.get("BreachDate", ""))
            ent.addProperty("hibp.count", "Pwned count", "loose", str(b.get("PwnCount", "")))
            ent.addProperty("hibp.data", "Data classes", "loose",
                            ", ".join(b.get("DataClasses", []) or []))
            ent.addProperty("source.email", "Source email", "loose", email)
            ent.addDisplayInformation(
                html_table([("Breach", title),
                            ("Domain", domain),
                            ("Date", b.get("BreachDate", "")),
                            ("Pwned count", b.get("PwnCount", "")),
                            ("Data", ", ".join(b.get("DataClasses", []) or [])),
                            ("Verified", b.get("IsVerified", ""))]),
                title="HIBP",
            )

        response.addEntity(
            Phrase, "HIBP: %s засвечен в %d утечк(ах)" % (email, len(data))
        )
