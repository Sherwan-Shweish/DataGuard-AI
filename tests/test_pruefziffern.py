"""IBAN (ISO 13616), USt-IdNr. (ISO 7064 MOD 11,10), PLZ, E-Mail – Grenzfälle und Gegentest mit python-stdnum."""

from __future__ import annotations

import random
import re

import pytest
from stdnum import iban as stdnum_iban  # nur im Test – keine Laufzeitabhängigkeit
from stdnum.de import vat as stdnum_de_vat

from src import pruefziffern as pz
from src.suite import KONTROLLE_UST

GUELTIGE_IBAN = ["DE59500400000611223344", "DE89370400440532013000", "AT611904300234573201", "NL91ABNA0417164300",
                 "CH9300762011623852957", "FR1420041010050500013M02606", "GB29NWBK60161331926819",
                 "BE68539007547034", "PL61109010140000071219812874", "IT60X0542811101000000123456"]


@pytest.mark.parametrize("iban", GUELTIGE_IBAN)
def test_gueltige_iban(iban):
    assert pz.iban_gueltig(iban) and pz.iban_gueltig(" ".join(re.findall(".{1,4}", iban)))


@pytest.mark.parametrize("iban,grund", [
    ("DE58500400000611223344", "pruefziffer"), ("DE5950040000061122334", "laenge"),
    ("XY59500400000611223344", "land"), ("DE59500400000611223345", "pruefziffer"), ("", "leer"),
])
def test_ungueltige_iban(iban, grund):
    assert not pz.iban_gueltig(iban)
    if grund == "laenge":
        assert pz.iban_laendercode_bekannt(iban) and not pz.iban_laenge_gueltig(iban)
    if grund == "land":
        assert not pz.iban_laendercode_bekannt(iban)


def test_iban_bilden_und_blz():
    iban = pz.iban_bilden("DE", "500400000611223344")
    assert iban == "DE59500400000611223344" and pz.iban_de_blz(iban) == "50040000"


def test_iban_gegentest_stdnum():
    r = random.Random(7)
    for _ in range(300):
        bban = "".join(str(r.randint(0, 9)) for _ in range(18))
        iban = pz.iban_bilden("DE", bban)
        kaputt = iban[:-1] + str((int(iban[-1]) + 1) % 10)
        assert pz.iban_gueltig(iban) == stdnum_iban.is_valid(iban) is True
        assert pz.iban_gueltig(kaputt) == stdnum_iban.is_valid(kaputt) is False


def test_iban_maskierung():
    assert pz.iban_maskieren("DE59500400000611223344") == "DE59 •••• 3344"
    assert pz.iban_maskieren("") == ""


# Wörtlich aus FlowAudit-AI 1.2.1, src/einvoice_parser.py (ust_id_de_gueltig) – Referenz für den Gleichheitstest.
_UST_ID_DE_FLOWAUDIT = re.compile(r"DE\d{9}")


def _flowaudit_ust_id_de_gueltig(ust_id: str) -> bool:
    uid = ust_id.replace(" ", "").upper()
    if not _UST_ID_DE_FLOWAUDIT.fullmatch(uid) or uid[2] == "0":
        return False
    produkt = 10
    for ziffer in uid[2:10]:
        summe = (int(ziffer) + produkt) % 10 or 10
        produkt = (2 * summe) % 11
    return (11 - produkt) % 10 == int(uid[10])


def test_ust_de_wie_flowaudit():
    """Nachbau statt Import: gleiche Ergebnisse auf 20.000 Zufallsnummern und den Kontrollwerten der Suite."""
    r = random.Random(42)
    for _ in range(20_000):
        nr = "DE" + "".join(str(r.randint(0, 9)) for _ in range(9))
        assert pz.ust_id_de_gueltig(nr) == _flowaudit_ust_id_de_gueltig(nr), nr
    for nr in KONTROLLE_UST.values():
        assert pz.ust_id_de_gueltig(nr) and _flowaudit_ust_id_de_gueltig(nr)


def test_ust_de_gegentest_stdnum():
    r = random.Random(3)
    for _ in range(2_000):
        acht = str(r.randint(1, 9)) + "".join(str(r.randint(0, 9)) for _ in range(7))
        for pruef in "0123456789":
            nr = f"DE{acht}{pruef}"
            assert pz.ust_id_de_gueltig(nr) == stdnum_de_vat.is_valid(nr), nr


@pytest.mark.parametrize("nr,gueltig", [
    ("DE214365872", True), ("DE214365873", False), ("DE012345678", False), ("DE21436587", False),
    ("DE2143658721", False), ("ATU12345678", True), ("NL123456789B01", True), ("NL123456789", False),
    ("FR12345678901", True), ("IT12345678901", True), ("PL1234567890", True), ("ESB1234567A", True),
    ("XX123456789", False),
])
def test_ust_format(nr, gueltig):
    assert (pz.ust_format_gueltig(nr) and (not nr.startswith("DE") or pz.ust_id_de_gueltig(nr))) is gueltig


def test_ust_land():
    assert pz.ust_land("ATU12345678") == "AT" and pz.ust_land("EL123456789") == "GR" and pz.ust_land("ZZ1") is None


@pytest.mark.parametrize("plz,land,erwartet", [
    ("65189", "DE", True), ("6518", "DE", False), ("D-65189", "DE", False), ("1010", "AT", True),
    ("3011 AB", "NL", True), ("50-001", "PL", True), ("301 00", "CZ", True), ("12345", "XY", None),
])
def test_plz(plz, land, erwartet):
    assert pz.plz_gueltig(plz, land) is erwartet


@pytest.mark.parametrize("email,ok", [("info@firma.example", True), ("a.b-c@x.de", True),
                                      ("info@@firma.example", False),
                                      ("info firma.example", False), ("info@firma", False), ("info@firma.de.", False)])
def test_email(email, ok):
    assert pz.email_gueltig(email) is ok


def test_bic_und_telefon():
    assert pz.bic_gueltig("COBADEFFXXX") and pz.bic_gueltig("COBADEFF") and not pz.bic_gueltig("COBA-EFFXXX")
    assert pz.telefon_gueltig("+49 611 1234567") and not pz.telefon_gueltig("0611 1234567")
    assert pz.telefon_ziffern("0611/1234567") == pz.telefon_ziffern("+49 611 1234567") == "496111234567"
