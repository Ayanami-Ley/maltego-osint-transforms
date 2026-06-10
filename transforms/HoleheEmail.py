"""
HoleheEmail — Maltego local transform.

Вход:  Email (maltego.EmailAddress)
Выход: Website для каждого сервиса, где почта зарегистрирована, + сводка.

Использует holehe (https://github.com/megadose/holehe): проверяет email через
механизмы восстановления пароля на ~120 сайтах БЕЗ отправки писем владельцу.
"""
import trio
import httpx

from maltego_trx.entities import Website, Phrase
from maltego_trx.transform import DiscoverableTransform

try:
    from holehe.core import import_submodules, get_functions, launch_module
    _HOLEHE_ERR = None
except Exception as exc:  # noqa: BLE001
    import_submodules = get_functions = launch_module = None
    _HOLEHE_ERR = str(exc)


async def _scan(email, timeout):
    """Асинхронно прогоняет email по всем модулям holehe, возвращает список dict."""
    modules = import_submodules("holehe.modules")
    websites = get_functions(modules)
    client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))
    out = []
    try:
        async with trio.open_nursery() as nursery:
            for website in websites:
                nursery.start_soon(launch_module, website, email, client, out)
    finally:
        await client.aclose()
    return out


def _is_email(value):
    return bool(value) and "@" in value and "." in value.rsplit("@", 1)[-1]


class HoleheEmail(DiscoverableTransform):
    """Email -> сервисы, на которых зарегистрирована почта (holehe)."""

    @classmethod
    def create_entities(cls, request, response):
        email = (request.Value or "").strip().lower()

        if _HOLEHE_ERR is not None:
            response.addEntity(Phrase, "holehe не импортируется: %s" % _HOLEHE_ERR)
            return
        if not _is_email(email):
            response.addEntity(Phrase, "Это не похоже на email: %s" % email)
            return

        # таймаут одного http-запроса; настраивается в Maltego (Transform Settings)
        try:
            timeout = float(request.getTransformSetting("holehe.timeout") or 15)
        except (TypeError, ValueError):
            timeout = 15.0

        try:
            results = trio.run(_scan, email, timeout)
        except Exception as exc:  # noqa: BLE001
            response.addEntity(Phrase, "Ошибка holehe: %s" % exc)
            return

        found = [r for r in results if r.get("exists")]
        if not found:
            response.addEntity(
                Phrase, "holehe: аккаунтов для %s не найдено (проверено %d сайтов)"
                % (email, len(results))
            )
            return

        for r in sorted(found, key=lambda x: (x.get("domain") or "")):
            domain = r.get("domain") or r.get("name") or "unknown"
            ent = response.addEntity(Website, domain)
            ent.setLinkLabel("holehe")
            ent.setWeight(100)
            ent.addProperty("source.email", "Source email", "loose", email)
            if r.get("emailrecovery"):
                ent.addProperty("holehe.recovery", "Recovery hint",
                                "loose", str(r["emailrecovery"]))
            if r.get("phoneNumber"):
                ent.addProperty("holehe.phone", "Phone hint",
                                "loose", str(r["phoneNumber"]))

        response.addEntity(
            Phrase, "holehe: найдено %d сервис(ов) для %s" % (len(found), email)
        )
