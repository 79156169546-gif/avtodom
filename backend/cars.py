"""Справочник марок и моделей автомобилей.

Нужен для автодополнения в оформлении заказа: клиент начинает вводить
марку — появляется список, начинает вводить модель — появляются модели
выбранной марки.

Справочник статичный (без БД) — это редактируемая константа. Русские
синонимы нужны, чтобы по запросу «киа» находилась Kia, а по «ауди» — Audi.
"""

from __future__ import annotations

# Марка -> список моделей. Порядок моделей сохраняется в списках.
CAR_CATALOG: dict[str, list[str]] = {
    "AUDI": ["A1", "A3", "A4", "A5", "A6", "A7", "A8", "Q2", "Q3", "Q5", "Q7", "Q8", "RS3", "RS4", "RS6", "S3", "S4", "S5", "S6", "S7", "S8", "TT", "e-tron"],
    "BMW": ["1 серия", "2 серия", "3 серия", "4 серия", "5 серия", "6 серия", "7 серия", "8 серия", "X1", "X3", "X5", "X6", "X7", "M2", "M3", "M4", "M5", "Z3", "Z4", "i3", "i4", "iX"],
    "CHERY": ["Tiggo 4", "Tiggo 7", "Tiggo 8", "Tiggo 8 Pro", "Tiggo 8 Pro Max", "Exeed TX", "Exeed EXL", "Omoda 5", "Omoda C5", "Elegza 7"],
    "CHEVROLET": ["Aveo", "Cobalt", "Cruze", "Epica", "Lacetti", "Malibu", "Niva", "Silverado", "Spark", "Tahoe", "Trailblazer"],
    "CITROEN": ["C3", "C4", "C5 Aircross", "Berlingo", "DS3", "DS4", "Jumpy", "Picasso"],
    "DATSUN": ["on-DO", "X-Trail"],
    "DODGE": ["Charger", "Challenger", "Durango", "Journey", "Viper"],
    "FIAT": ["500", "500L", "Doblo", "Ducato", "Fiorino", "Panda", "Punto", "Tipo"],
    "FORD": ["Focus", "Fiesta", "Fusion", "Kuga", "Mondeo", "EcoSport", "Edge", "Explorer", "F-150", "Mustang", "Puma", "Ranger", "Tourneo Custom"],
    "GEELY": ["Atlas", "Atlas Pro", "Coolray", "Emgrand", "Emgrand EV", "Geometry E", "Monjaro", "Preface", "Tugella"],
    "GREAT WALL": ["Hover H3", "Hover H5", "Hover H6", "Hover Haval H9", "Poer", "Wingle 7"],
    "HANG": ["Танк 300", "Танк 500", "Танк 700", "Во(Box)", "Паук"],
    "HONDA": ["Accord", "Civic", "CR-V", "City", "HR-V", "Jazz", "Odyssey", "Pilot", "Ridgeline", "Stream"],
    "HYUNDAI": ["Accent", "Azera", "Creta", "Elantra", "Grandeur", "H1", "H6", "i20", "i30", "i40", "Palisade", "Santa Fe", "Solaris", "Sonata", "Staria", "Tucson", "Venue"],
    "INFINITI": ["FX", "G", "JX", "M", "Q", "QX"],
    "JAC": ["J4", "J6", "J7", "S3", "S5", "T6", "T8"],
    "JEEP": ["Cherokee", "Compass", "Grand Cherokee", "Gladiator", "Renegade", "Wrangler"],
    "KIA": ["Ceed", "Cerato", "K5", "Niro", "Optima", "Proceed", "Rio", "Rio X", "Seltos", "Sorento", "Soul", "Sportage", "Stinger", "Telluride"],
    "LADA": ["2110", "2111", "2112", "Granta", "Kalina", "Largus", "Niva", "Priora", "Samara", "Vesta", "XRAY", "4x4"],
    "LAND ROVER": ["Defender", "Discovery", "Discovery Sport", "Evoque", "Range Rover", "Range Rover Sport"],
    "LEXUS": ["ES", "GS", "IS", "LX", "NX", "RX", "UX"],
    "MAZDA": ["2", "3", "5", "6", "BT-50", "CX-3", "CX-30", "CX-5", "CX-9", "MX-5"],
    "MERCEDES-BENZ": ["A-Class", "B-Class", "C-Class", "E-Class", "S-Class", "CLA", "CLS", "GLE", "GLS", "ML", "G-Class", "V-Class", "Sprinter", "EQE", "EQB"],
    "MITSUBISHI": ["ASX", "Eclipse Cross", "Lancer", "L200", "Outlander", "Outlander Sport", "Pajero", "Space Star", "Xpander"],
    "NISSAN": ["Almera", "Juke", "Kicks", "Leaf", "Micra", "Note", "Pathfinder", "Qashqai", "Sentra", "Serena", "Silvia", "Terrano", "X-Trail"],
    "OPEL": ["Astra", "Corsa", "Crossland", "Grandland", "Insignia", "Mokka", "Vectra", "Zafira", "Zafira Life"],
    "PEUGEOT": ["2008", "208", "301", "308", "407", "408", "508", "Rifter", "Traveller", "Expert"],
    "RENAULT": ["Arkana", "Captur", "Clio", "Duster", "Fluence", "Kadjar", "Kangoo", "Logan", "Megane", "Sandero", "Symbol", "Talisman", "Traffic", "Zoe"],
    "SEAT": ["Alhambra", "Ateca", "Ibiza", "Leon", "Mii", "Toledo"],
    "SKODA": ["Citigo", "Fabia", "Felicia", "Karoq", "Kodiaq", "Octavia", "Rapid", "Scala", "Superb", "Yeti"],
    "SSANGYONG": ["Korando", "Kyron", "Rexton", "Tivoli", "XDEVIL"],
    "SUBARU": ["Forester", "Impreza", "Legacy", "Outback", "XV", "WRX", "Ascent", "Crosstrek", "Solterra"],
    "SUZUKI": ["Baleno", "Celerio", "Dzire", "Grand Vitara", "Ignis", "Jimny", "Kizashi", "S-Cross", "Swift", "SX4"],
    "TESLA": ["Model 3", "Model S", "Model X", "Model Y", "Cybertruck"],
    "TOYOTA": ["Avensis", "Camry", "Carolla", "Corolla Cross", "Crown", "Land Cruiser", "Land Cruiser Prado", "Land Cruiser 300", "Prius", "RAV4", "Sequoia", "Sienna", "Tacoma", "Tundra", "Yaris", "Hilux", "Verso"],
    "VOLKSWAGEN": ["Amarok", "Arteon", "Cross Polo", "Golf", "Golf Plus", "ID.4", "Jetta", "Passat", "Passat CC", "Polo", "Sharan", "Tiguan", "Touran", "Multivan"],
    "VOLVO": ["S40", "S60", "S80", "S90", "V40", "V60", "V90", "XC40", "XC60", "XC90"],
    "ZAZ": ["Sens", "ЗАЗ 1102", "ЗАЗ 1103", "ЗАЗ 1122", "Lanos"],
}

# Русские синонимы марок: как пишут -> марка из справочника.
CAR_ALIASES: dict[str, str] = {
    "ауди": "AUDI",
    "ауді": "AUDI",
    "бмв": "BMW",
    "бэмвэ": "BMW",
    "вмв": "BMW",
    "ваз": "LADA",
    "лада": "LADA",
    "форд": "FORD",
    "шкода": "SKODA",
    "фольксваген": "VOLKSWAGEN",
    "вольксваген": "VOLKSWAGEN",
    "мерседес": "MERCEDES-BENZ",
    "мерседес-бенц": "MERCEDES-BENZ",
    "хёндэ": "HYUNDAI",
    "хендай": "HYUNDAI",
    "хундай": "HYUNDAI",
    "хендэ": "HYUNDAI",
    "киа": "KIA",
    "кия": "KIA",
    "нисса": "NISSAN",
    "нисан": "NISSAN",
    "тойота": "TOYOTA",
    "тоёта": "TOYOTA",
    "тесла": "TESLA",
    "вольво": "VOLVO",
    "опель": "OPEL",
    "пежо": "PEUGEOT",
    "рено": "RENAULT",
    "шкодa": "SKODA",
    "skoda": "SKODA",
    "порше": "PORSCHE",
    "нексия": "NEXIA",
    "субару": "SUBARU",
    "сузуки": "SUZUKI",
    "митсубиси": "MITSUBISHI",
    "мицубиси": "MITSUBISHI",
    "хавал": "HAVAL",
    # Общие слова: клиент пишет «авто» — показываем массовые марки.
    "авто": "LADA",
    "автомобиль": "LADA",
    "машина": "LADA",
    "жигули": "LADA",
}

CAR_MAKES: list[str] = sorted(CAR_CATALOG.keys())


def normalize_query(value: str) -> str:
    """Приводит ввод к виду для поиска: без пробелов, в верхнем регистре."""
    return "".join(value.split()).upper()


def search_makes(query: str, limit: int = 12) -> list[str]:
    """Марки, подходящие под запрос (по началу названия или по синониму)."""
    cleaned = normalize_query(query)
    if not cleaned:
        return CAR_MAKES[:limit]

    exact: list[str] = []
    by_prefix: list[str] = []
    by_contains: list[str] = []

    for make in CAR_MAKES:
        if make == cleaned:
            exact.append(make)
        elif make.startswith(cleaned):
            by_prefix.append(make)
        elif cleaned in make:
            by_contains.append(make)

    for alias, make in CAR_ALIASES.items():
        if alias.upper().startswith(cleaned) and make not in by_prefix:
            by_prefix.append(make)

    result: list[str] = []
    for make in exact + by_prefix + by_contains:
        if make not in result:
            result.append(make)
    return result[:limit]


def search_models(make: str, query: str, limit: int = 20) -> list[str]:
    """Модели выбранной марки, подходящие под запрос."""
    models = CAR_CATALOG.get(make.upper(), [])
    cleaned = normalize_query(query)
    if not cleaned:
        return models[:limit]

    exact: list[str] = []
    by_prefix: list[str] = []
    by_contains: list[str] = []
    for model in models:
        normalized = normalize_query(model)
        if normalized == cleaned:
            exact.append(model)
        elif normalized.startswith(cleaned):
            by_prefix.append(model)
        elif cleaned in normalized:
            by_contains.append(model)

    result: list[str] = []
    for model in exact + by_prefix + by_contains:
        if model not in result:
            result.append(model)
    return result[:limit]


def resolve_make(value: str | None) -> str | None:
    """Приводит введённую марку к канонической (для сохранения в заказе)."""
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    upper = cleaned.upper()
    if upper in CAR_CATALOG:
        return upper
    alias = CAR_ALIASES.get(cleaned.lower())
    if alias:
        return alias
    return cleaned
