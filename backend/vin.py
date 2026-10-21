"""Декодирование VIN автомобиля.

VIN — 17-символьный идентификатор по ISO 3779. Нам нужны две части:
  * позиции 1-3 (WMI) — идентификатор производителя;
  * позиция 10 — код года выпуска модели.

Этого достаточно, чтобы понять, к какому автомобилю относится деталь,
и отфильтровать каталог по марке и году. Точная модель из VIN без
специализированной базы не определяется — её клиент уточняет сам.

Таблица WMI покрывает популярные марки; неизвестный префикс — это
нормальная ситуация, а не ошибка: клиенту покажем подсказку выбрать
марку вручную.
"""

from __future__ import annotations

import re
from datetime import datetime

VIN_LENGTH = 17
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")

# Префиксы WMI (первые 3 символа VIN) -> каноническая марка из cars.py.
WMI_MAKES: dict[str, str] = {
    # Lada / VAZ
    "X4": "LADA", "X7": "LADA", "Y6": "LADA", "4A": "LADA",
    "6Y": "LADA", "X9": "LADA", "XW": "LADA",
    # KIA
    "Z94": "KIA", "Z9": "KIA", "KNE": "KIA", "K5T": "KIA",
    "5XY": "KIA", "KNA": "KIA", "K3W": "KIA",
    # Hyundai
    "KM": "HYUNDAI", "5NP": "HYUNDAI", "5YK": "HYUNDAI",
    "94": "HYUNDAI", "T41": "HYUNDAI", "2T": "HYUNDAI",
    # Volkswagen
    "WVW": "VOLKSWAGEN", "1VW": "VOLKSWAGEN", "3VW": "VOLKSWAGEN",
    "XWB": "VOLKSWAGEN", "1V2": "VOLKSWAGEN", "3V1": "VOLKSWAGEN",
    # Audi
    "WAU": "AUDI", "4F": "AUDI", "8D": "AUDI", "8E": "AUDI",
    "8DJ": "AUDI", "8L1": "AUDI", "8P1": "AUDI", "8V1": "AUDI",
    "8X1": "AUDI", "4G": "AUDI",
    # BMW
    "WBA": "BMW", "WBS": "BMW", "4US": "BMW", "3G1": "BMW",
    "WBX": "BMW", "WBY": "BMW", "5WB": "BMW",
    # Toyota
    "JTD": "TOYOTA", "5T": "TOYOTA", "Z30": "TOYOTA", "4T1": "TOYOTA",
    "ZR": "TOYOTA", "MR": "TOYOTA", "JHM": "TOYOTA", "JT2": "TOYOTA",
    # Nissan
    "JN": "NISSAN", "1N4": "NISSAN", "3N1": "NISSAN", "5N1": "NISSAN",
    "5NP": "NISSAN", "SJN": "NISSAN", "JN1": "NISSAN",
    # Renault
    "VF1": "RENAULT", "VF3": "RENAULT", "VF6": "RENAULT", "X44": "RENAULT",
    # Peugeot
    "TMA": "PEUGEOT", "3C1": "PEUGEOT", "3CG": "PEUGEOT", "3CY": "PEUGEOT",
    # Citroen
    "VF7": "CITROEN", "XU7": "CITROEN", "3C6": "CITROEN",
    # Chevrolet
    "1G1": "CHEVROLET", "1GC": "CHEVROLET", "2G1": "CHEVROLET",
    "KL1": "CHEVROLET", "KL5": "CHEVROLET", "3G1": "CHEVROLET",
    # Ford
    "1FT": "FORD", "1FA": "FORD", "WF0": "FORD", "W0L": "FORD",
    "3FA": "FORD", "6F": "FORD",
    # Mazda
    "JM": "MAZDA", "YV1": "MAZDA", "ZY1": "MAZDA", "3FD": "MAZDA",
    # Skoda
    "TMB": "SKODA", "TM2": "SKODA", "TMB1": "SKODA", "TMB5": "SKODA",
    # Opel
    "WSG": "OPEL", "7Z": "OPEL", "X0Y": "OPEL",
    # Volvo
    "YV3": "VOLVO", "4V": "VOLVO",
    # Lexus
    "JTH": "LEXUS", "4A1": "LEXUS",
    # Mercedes-Benz
    "WDD": "MERCEDES-BENZ", "WDC": "MERCEDES-BENZ", "4JG": "MERCEDES-BENZ",
    "1G4": "MERCEDES-BENZ", "W1J": "MERCEDES-BENZ",
    # Subaru
    "JF1": "SUBARU", "4S3": "SUBARU", "5FB": "SUBARU",
    # Suzuki
    "JMA": "SUZUKI", "MMA": "SUZUKI",
    # Mitsubishi
    "JA": "MITSUBISHI", "J4": "MITSUBISHI", "ZS": "MITSUBISHI",
    # Geely
    "LB": "GEELY", "L6T": "GEELY", "L6Y": "GEELY",
    # Chery
    "T11": "CHERY", "LVV": "CHERY", "S21": "CHERY",
    # Great Wall / Haval
    "H0": "GREAT WALL", "T1": "GREAT WALL", "H3": "GREAT WALL",
    # Tank (Haval Group)
    "LSX": "HANG", "J1": "HANG",
    # JAC
    "LJ1": "JAC", "LVV1": "JAC",
    # SsangYong
    "W0W": "SSANGYONG", "KPE": "SSANGYONG",
    # Seat
    "VSS": "SEAT", "5F": "SEAT",
    # Fiat
    "3C1": "FIAT", "198": "FIAT", "1F": "FIAT",
    # Tesla
    "5YJ": "TESLA", "7SA": "TESLA",
    # Dodge
    "1C3": "DODGE", "3C6": "DODGE", "2C3": "DODGE",
    # Infiniti
    "JNK": "INFINITI", "5NK": "INFINITI",
    # ZAZ
    "5Z": "ZAZ", "Y6Z": "ZAZ",
    # Jeep
    "1C4": "JEEP", "ZC4": "JEEP", "2C4": "JEEP",
}

# Код года выпуска (позиция 10). Буквы A-Y = 1980-2000, цифры 1-9 = 2001-2009.
# Цикл повторяется каждые 30 лет.
_YEAR_LETTERS = "ABCDEFGHJKLMNPRSTVWXY"


def _year_from_code(code: str, now_year: int) -> int | None:
    """Код года из позиции 10 -> календарный год."""
    code = code.upper()
    if code in _YEAR_LETTERS:
        base = 1980 + _YEAR_LETTERS.index(code)
    elif code.isdigit() and code != "0":
        base = 2000 + int(code)
    else:
        return None

    # Выбираем самый свежий год, который ещё не «в будущем».
    candidates = [base]
    while candidates[-1] - base < 60:
        candidates.append(candidates[-1] + 30)
    valid = [year for year in candidates if year <= now_year + 1]
    return valid[-1] if valid else candidates[0]


def decode_vin(vin: str | None, now: datetime | None = None) -> dict[str, object]:
    """Разобрать VIN.

    Возвращает словарь:
      valid     — формат VIN корректен
      reason    — человекочитаемая причина, если valid == False
      make      — каноническая марка (может быть None)
      year      — год выпуска (может быть None)
      wmi       — первые 3 символа VIN
    """
    now = now or datetime.now()
    raw = (vin or "").strip().upper()

    if not raw:
        return {
            "valid": False,
            "reason": "Введите VIN — 17 символов из подложки или бардачка.",
            "make": None,
            "year": None,
            "wmi": None,
        }

    if len(raw) != VIN_LENGTH:
        return {
            "valid": False,
            "reason": f"В VIN должно быть {VIN_LENGTH} символов, а введено {len(raw)}.",
            "make": None,
            "year": None,
            "wmi": None,
        }

    if not VIN_RE.match(raw):
        return {
            "valid": False,
            "reason": "VIN содержит недопустимые символы (в нём нет букв I, O и Q).",
            "make": None,
            "year": None,
            "wmi": raw[:3],
        }

    wmi = raw[:3]
    make = WMI_MAKES.get(wmi)
    year = _year_from_code(raw[9], now.year)

    reason = ""
    if not make:
        reason = "Марку по VIN определить не удалось — выберите её вручную."
    elif not year:
        reason = "Год выпуска по VIN определить не удалось — укажите его вручную."

    return {
        "valid": True,
        "reason": reason,
        "make": make,
        "year": year,
        "wmi": wmi,
    }
