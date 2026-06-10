"""
Общие хелперы для трансформ: извлечение/классификация данных и оформление.
Это НЕ трансформа (нет одноимённого класса), поэтому register_transform_classes
её игнорирует — просто библиотека.
"""
import re
import html as _html

from maltego_trx.entities import (
    Email, PhoneNumber, Person, Alias, Location, URL, Website, Phrase,
)

# цвета связей (ARGB hex понимается клиентом; при незнании просто игнорится)
COLOR_FOUND = "#27AE60"   # зелёный — найденный аккаунт
COLOR_BREACH = "#E74C3C"  # красный — утечка/риск
COLOR_INFO = "#7F8C8D"    # серый — справочное/footprint

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# телефон в свободном тексте: + и 7..15 цифр с разделителями
PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d\s().\-]{6,17}\d(?!\w)")


def is_email(value):
    return bool(value) and bool(EMAIL_RE.fullmatch(value.strip()))


def html_table(rows):
    """rows: list[(key, value)] -> аккуратная HTML-таблица для detail-панели."""
    cells = "".join(
        "<tr><td style='padding:2px 8px;color:#888'>%s</td>"
        "<td style='padding:2px 8px'>%s</td></tr>"
        % (_html.escape(str(k)), _html.escape(str(v)))
        for k, v in rows if v not in (None, "", [], {})
    )
    return "<table style='border-collapse:collapse'>%s</table>" % cells


# ключи id -> тип сущности Maltego (для пивотинга из результатов maigret)
_NAME_KEYS = {"fullname", "full_name", "name", "real_name", "first_name", "last_name"}
_ALIAS_KEYS = {"username", "login", "nick", "nickname", "screen_name", "handle",
               "uid", "id", "userid", "user_id"}
_LOC_KEYS = {"location", "city", "country", "region", "address", "place"}


def classify_ids(ids):
    """
    Превращает словарь извлечённых id (из maigret) в список (EntityType, value).
    Значение может быть строкой или списком. Возвращает дедуплицированный список.
    """
    out = []
    seen = set()

    def push(etype, val):
        val = str(val).strip()
        if not val:
            return
        key = (etype, val.lower())
        if key not in seen:
            seen.add(key)
            out.append((etype, val))

    for raw_key, raw_val in (ids or {}).items():
        if raw_val is None:
            continue
        values = raw_val if isinstance(raw_val, list) else [raw_val]
        kl = str(raw_key).lower()
        for v in values:
            s = str(v).strip()
            if not s:
                continue
            if "email" in kl or is_email(s):
                push(Email, s)
            elif "phone" in kl or "tel" in kl or "msisdn" in kl:
                push(PhoneNumber, s)
            elif kl in _NAME_KEYS:
                push(Person, s)
            elif kl in _LOC_KEYS:
                push(Location, s)
            elif kl in _ALIAS_KEYS:
                push(Alias, s)
            # незнакомые ключи не тянем как сущности — только в свойства, чтобы не засорять граф
    return out


def extract_contacts(text):
    """Достаёт email'ы и телефоны из произвольного текста/HTML. Возвращает dict."""
    emails = sorted({m.group(0).lower() for m in EMAIL_RE.finditer(text or "")})
    # отсекаем мусорные совпадения вида image@2x, asset-хеши и т.п.
    emails = [e for e in emails if not e.endswith((".png", ".jpg", ".jpeg", ".gif",
                                                    ".webp", ".svg", ".css", ".js"))]
    phones = sorted({re.sub(r"[^\d+]", "", m.group(0)) for m in PHONE_RE.finditer(text or "")})
    phones = [p for p in phones if 8 <= len(p.lstrip("+")) <= 15]
    return {"emails": emails, "phones": phones}
