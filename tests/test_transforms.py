"""
Юнит-тесты трансформ на моках (без реальной сети, кроме оффлайн-разбора телефона).
Запуск из корня проекта:  python tests/test_transforms.py
"""
import os
import re
import sys
import importlib
import xml.dom.minidom as X

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from maltego_trx.maltego import MaltegoMsg, MaltegoTransform  # noqa: E402


def _types(xml):
    return re.findall(r'<Entity Type="([^"]+)"', xml)


def _msg(value, settings=None):
    req = MaltegoMsg(LocalArgs=[value])
    settings = settings or {}
    req.getTransformSetting = lambda k: settings.get(k)
    return req


def test_maigret_pivots():
    M = importlib.import_module("transforms.MaigretUsername")
    M._run_maigret = lambda u, t, to, p: {
        "GitHub": {"url_user": "https://github.com/john", "status": {
            "tags": ["coding"], "ids": {"fullname": "John Doe",
                                         "email": "john@gmail.com", "username": "john_d"}}},
        "VK": {"url_user": "https://vk.com/john", "status": {
            "tags": ["social"], "ids": {"phone": "+79991234567",
                                        "location": "Saint Petersburg", "uid": "12345"}}},
    }
    resp = MaltegoTransform()
    M.MaigretUsername.create_entities(_msg("john"), resp)
    out = resp.returnOutput()
    X.parseString(out)
    t = _types(out)
    assert "maltego.EmailAddress" in t
    assert "maltego.Person" in t
    assert "maltego.PhoneNumber" in t
    assert "maltego.Alias" in t
    assert t.count("maltego.URL") == 2
    assert "maltego.Website" in t
    print("ok  maigret pivots")


def test_website_contacts():
    W = importlib.import_module("transforms.WebsiteToContacts")
    W.fetch_text = lambda url, timeout, proxy=None: (
        '<a href="mailto:info@acme.io">m</a> sales@acme.io '
        'phone +1 415-555-2671 logo image@2x.png')
    resp = MaltegoTransform()
    W.WebsiteToContacts.create_entities(_msg("acme.io"), resp)
    out = resp.returnOutput()
    X.parseString(out)
    t = _types(out)
    assert t.count("maltego.EmailAddress") == 2
    assert "maltego.PhoneNumber" in t
    assert "image@2x.png" not in out
    print("ok  website->contacts")


def test_hibp():
    B = importlib.import_module("transforms.EmailToBreaches")
    os.environ.pop("HIBP_API_KEY", None)
    resp = MaltegoTransform()
    B.EmailToBreaches.create_entities(_msg("a@b.com"), resp)
    assert "нет API-ключа" in resp.returnOutput()

    B.query_hibp = lambda email, key, timeout=20: ("ok", [
        {"Name": "Adobe", "Title": "Adobe", "Domain": "adobe.com",
         "BreachDate": "2013-10-04", "PwnCount": 152445165,
         "DataClasses": ["Emails", "Passwords"], "IsVerified": True},
        {"Name": "LinkedIn", "Title": "LinkedIn", "Domain": "linkedin.com",
         "BreachDate": "2012-05-05", "PwnCount": 164611595,
         "DataClasses": ["Emails", "Passwords"], "IsVerified": True},
    ])
    resp = MaltegoTransform()
    B.EmailToBreaches.create_entities(_msg("a@b.com", {"hibp.apikey": "FAKE"}), resp)
    out = resp.returnOutput()
    X.parseString(out)
    assert _types(out).count("maltego.Website") == 2
    assert "adobe.com" in out
    print("ok  hibp")


def test_phone():
    P = importlib.import_module("transforms.PhoneToInfo")
    resp = MaltegoTransform()
    P.PhoneToInfo.create_entities(_msg("+14155552671"), resp)
    out = resp.returnOutput()
    X.parseString(out)
    t = _types(out)
    assert "maltego.Location" in t
    assert t.count("maltego.URL") == 5

    resp = MaltegoTransform()
    P.PhoneToInfo.create_entities(_msg("89991234567"), resp)
    assert "phone.region" in resp.returnOutput()

    resp = MaltegoTransform()
    P.PhoneToInfo.create_entities(_msg("89991234567", {"phone.region": "RU"}), resp)
    assert "+79991234567" in resp.returnOutput()
    print("ok  phone")


if __name__ == "__main__":
    test_maigret_pivots()
    test_website_contacts()
    test_hibp()
    test_phone()
    print("\nALL TESTS PASSED")
