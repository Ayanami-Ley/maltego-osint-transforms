"""
PhoneToInfo — Maltego local transform.

Вход:  PhoneNumber
Выход: Location (регион), Phrase (оператор/тип/таймзона), URL footprint-дорки.

Локальный разбор на phonenumbers (порт google libphonenumber, оффлайн) +
генерация поисковых ссылок — это покрывает полезную часть PhoneInfoga без
зависимости от Go-бинаря.
"""
from urllib.parse import quote_plus

import phonenumbers
from phonenumbers import carrier, geocoder, timezone, PhoneNumberType

from maltego_trx.entities import Location, URL, Phrase
from maltego_trx.transform import DiscoverableTransform

from ._common import html_table, COLOR_INFO

_TYPE_NAMES = {
    PhoneNumberType.FIXED_LINE: "fixed line",
    PhoneNumberType.MOBILE: "mobile",
    PhoneNumberType.FIXED_LINE_OR_MOBILE: "fixed line or mobile",
    PhoneNumberType.TOLL_FREE: "toll free",
    PhoneNumberType.PREMIUM_RATE: "premium rate",
    PhoneNumberType.SHARED_COST: "shared cost",
    PhoneNumberType.VOIP: "VoIP",
    PhoneNumberType.PERSONAL_NUMBER: "personal",
    PhoneNumberType.PAGER: "pager",
    PhoneNumberType.UAN: "UAN",
    PhoneNumberType.VOICEMAIL: "voicemail",
    PhoneNumberType.UNKNOWN: "unknown",
}


def _footprint_urls(e164, national):
    q = quote_plus('"%s" OR "%s"' % (e164, national))
    qn = quote_plus(e164)
    return [
        ("Google", "https://www.google.com/search?q=%s" % q),
        ("Yandex", "https://yandex.ru/search/?text=%s" % qn),
        ("Bing", "https://www.bing.com/search?q=%s" % q),
        ("Truecaller", "https://www.truecaller.com/search/global/%s" % quote_plus(e164.lstrip("+"))),
        ("GetContact-ish lookup", "https://duckduckgo.com/?q=%s" % qn),
    ]


class PhoneToInfo(DiscoverableTransform):
    """Телефон -> регион/оператор/тип + footprint-ссылки."""

    @classmethod
    def create_entities(cls, request, response):
        raw = (request.Value or "").strip()
        if not raw:
            response.addEntity(Phrase, "Пустой номер")
            return

        region = (request.getTransformSetting("phone.region") or "").strip().upper() or None

        try:
            num = phonenumbers.parse(raw, region)
        except phonenumbers.NumberParseException as exc:
            response.addEntity(
                Phrase,
                "Не удалось разобрать номер (%s). Если номер без '+', задайте "
                "Transform Setting 'phone.region', напр. RU/US." % exc,
            )
            return

        valid = phonenumbers.is_valid_number(num)
        e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
        intl = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        national = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.NATIONAL)
        geo = geocoder.description_for_number(num, "en")
        carr = carrier.name_for_number(num, "en")
        tzs = list(timezone.time_zones_for_number(num))
        ntype = _TYPE_NAMES.get(phonenumbers.number_type(num), "unknown")

        if not valid:
            response.addEntity(Phrase, "Номер невалиден по libphonenumber: %s" % e164)
            # всё равно отдадим footprint — иногда полезно

        if geo:
            loc = response.addEntity(Location, geo)
            loc.setLinkLabel("region")
            loc.addProperty("source.phone", "Source phone", "loose", e164)

        for label, link in _footprint_urls(e164, national):
            u = response.addEntity(URL, link)
            u.setLinkLabel("footprint: %s" % label)
            u.setLinkColor(COLOR_INFO)
            u.addProperty("short-title", "Title", "loose", "Search %s" % label)
            u.addProperty("url", "URL", "strict", link)

        summary = response.addEntity(
            Phrase,
            "%s | %s | %s%s" % (e164, ntype, carr or geo or "?",
                                "" if valid else " | INVALID"),
        )
        summary.addDisplayInformation(
            html_table([("E.164", e164), ("International", intl), ("National", national),
                        ("Valid", valid), ("Type", ntype), ("Region", geo),
                        ("Carrier", carr), ("Country code", "+%s" % num.country_code),
                        ("Timezones", ", ".join(tzs))]),
            title="phone info",
        )
