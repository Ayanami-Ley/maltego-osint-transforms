"""
WebsiteToContacts — Maltego local transform (обратный пивот).

Вход:  Website (домен) или URL
Выход: Email и PhoneNumber, найденные на странице, + сводка.

Замыкает петлю: профиль/сайт -> контакты -> их можно гнать в holehe/HIBP.
Тянет страницу httpx'ом (нужна сеть), парсит текст и mailto-ссылки.
"""
import httpx

from maltego_trx.entities import Email, PhoneNumber, Phrase
from maltego_trx.transform import DiscoverableTransform

from ._common import extract_contacts, html_table, COLOR_FOUND

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _normalize_url(value):
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    return "https://" + value


def fetch_text(url, timeout, proxy=None):
    """Возвращает текст страницы (или бросает исключение)."""
    kwargs = {"timeout": httpx.Timeout(timeout), "follow_redirects": True,
              "headers": {"User-Agent": _UA}}
    if proxy:
        kwargs["proxies"] = proxy
    with httpx.Client(**kwargs) as client:
        r = client.get(url)
        return r.text or ""


class WebsiteToContacts(DiscoverableTransform):
    """Сайт/URL -> email и телефоны со страницы."""

    @classmethod
    def create_entities(cls, request, response):
        url = _normalize_url(request.Value)
        if not url:
            response.addEntity(Phrase, "Пустой адрес")
            return

        try:
            timeout = float(request.getTransformSetting("web.timeout") or 15)
        except (TypeError, ValueError):
            timeout = 15.0
        proxy = request.getTransformSetting("web.proxy") or None

        try:
            text = fetch_text(url, timeout, proxy)
        except Exception as exc:  # noqa: BLE001
            response.addEntity(Phrase, "Не удалось загрузить %s: %s" % (url, exc))
            return

        contacts = extract_contacts(text)
        emails, phones = contacts["emails"], contacts["phones"]

        for e in emails:
            ent = response.addEntity(Email, e)
            ent.setLinkLabel("on page")
            ent.setLinkColor(COLOR_FOUND)
            ent.addProperty("source.url", "Source URL", "loose", url)

        for p in phones:
            ent = response.addEntity(PhoneNumber, p)
            ent.setLinkLabel("on page")
            ent.addProperty("source.url", "Source URL", "loose", url)

        summary = response.addEntity(
            Phrase, "Найдено: %d email, %d телефон(ов) на %s" % (len(emails), len(phones), url)
        )
        summary.addDisplayInformation(
            html_table([("URL", url),
                        ("Emails", ", ".join(emails)),
                        ("Phones", ", ".join(phones))]),
            title="WebsiteToContacts",
        )
