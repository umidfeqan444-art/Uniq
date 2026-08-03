# -*- coding: utf-8 -*-
"""
Clean copy of import_sellers implementation for quick local testing.
"""
from pathlib import Path
import re

SELLER_FILES_DIR = Path(__file__).parent

# Canonical alias map: friendly supplier key -> filename
ALIAS_MAP = {
    'admin': 'SELLER_random_prices_1dec.txt',
    'zeus': 'SELLER_ZEUS_random_prices_1dec.txt',
}

def _canonical_supplier_name_from_stem(stem: str) -> str:
    """Map various seller file stems to canonical supplier keys (ADMIN/ZEUS) when possible."""
    s = stem.lower()
    if 'zeus' in s:
        return 'ZEUS'
    if 'random' in s or 'admin' in s:
        return 'ADMIN'
    return stem

def _find_seller_files():
    return list(SELLER_FILES_DIR.glob("SELLER*.txt"))

def _normalize_supplier_name_from_path(p: Path) -> str:
    name = p.stem
    if name.upper().startswith("SELLER"):
        name = name[len("SELLER"):]
    return name.lstrip(" _#-").strip()

# Common regexes and parser reused by multiple helpers
_LINE_RE = re.compile(r"^(?P<flag>\S+)\s+(?P<bin>\d{3,6})\s*-\s*(?P<rest>.+)$")
_PCS_PRICE_RE = re.compile(r"\[(?P<pcs>\d+)\s*pcs\.\]\s*(?P<price>[0-9]+(?:\.[0-9]+)?)\$")

def _parse_line(raw: str, supplier_name: str = None):
    m = _LINE_RE.match(raw)
    if not m:
        return {"raw": raw, "supplier_name": supplier_name or "UNKNOWN"}
    flag = m.group("flag").strip()
    bin_code = m.group("bin").strip()
    rest = m.group("rest").strip()
    parts = [p.strip() for p in rest.split(' - ')]
    country = parts[0] if len(parts) > 0 else ""
    bank = parts[1] if len(parts) > 1 else ""
    brand = parts[2] if len(parts) > 2 else ""
    card_type = parts[3] if len(parts) > 3 else ""
    level = parts[4] if len(parts) > 4 else ""
    pcs = 0
    price = 0.0
    pcs_price_match = _PCS_PRICE_RE.search(raw)
    if pcs_price_match:
        try:
            pcs = int(pcs_price_match.group("pcs"))
            price = float(pcs_price_match.group("price"))
            # Remove [X pcs.] Y$ from level field
            level = _PCS_PRICE_RE.sub('', level).strip()
        except Exception:
            pass
    return {
        "raw": raw,
        "supplier_name": supplier_name or "UNKNOWN",
        "flag": flag,
        "bin": bin_code,
        "country": country,
        "bank": bank,
        "brand": brand,
        "type": card_type,
        "level": level,
        "pcs": pcs,
        "price": price,
    }

def get_all_suppliers_from_files():
    # Prefer the two canonical suppliers if their files are present
    found = []
    for key, fname in ALIAS_MAP.items():
        candidate = SELLER_FILES_DIR / fname
        if candidate.exists():
            found.append(key.upper())

    if found:
        return sorted(found)

    # Fallback: list all discovered seller stems
    suppliers = []
    for p in _find_seller_files():
        name = _normalize_supplier_name_from_path(p)
        if name:
            suppliers.append(name)
    return sorted(suppliers)

def get_countries():
    """Return combined country list gathered from all seller files.

    This replaces the previous behavior that returned supplier filenames.
    """
    return get_all_countries()

def get_country_page(page=0, per_page=20):
    """Paginate supplier list (used as "countries" page in UI)."""
    countries = get_countries()
    total = len(countries)
    total_pages = (total + per_page - 1) // per_page

    start_idx = page * per_page
    end_idx = start_idx + per_page

    items = countries[start_idx:end_idx]
    return items, page, total_pages, total

def get_bins_for_country_display(country_name: str):
    files = _find_seller_files()
    target = None
    lookup = country_name.strip().lower()
    for p in files:
        name = _normalize_supplier_name_from_path(p).lower()
        if name == lookup or lookup in name or name in lookup:
            target = p
            break
    if not target:
        return []
    supplier = _normalize_supplier_name_from_path(target)
    items = list(_get_cached_bins_for_file(target, supplier))
    return redistribute_suppliers_evenly(items)

def get_all_countries():
    """Return unique country names collected from all SELLER files."""
    countries = set()
    files = _find_seller_files()
    for p in files:
        supplier = _normalize_supplier_name_from_path(p)
        for parsed in _get_cached_bins_for_file(p, supplier):
            country = parsed.get('country', '').strip()
            if country:
                countries.add(country)
    return sorted(countries)

def get_bins_for_country_all(country_name: str):
    """Return bins across all suppliers that match the given country name."""
    lookup = country_name.strip().lower()
    results = []
    files = _find_seller_files()
    for p in files:
        supplier = _normalize_supplier_name_from_path(p)
        for parsed in _get_cached_bins_for_file(p, supplier):
            country = parsed.get('country', '').strip()
            if not country:
                continue
            if country.lower() == lookup or lookup in country.lower() or country.lower() in lookup:
                results.append(parsed)
    return redistribute_suppliers_evenly(results)

def get_bins_for_supplier(supplier_name: str):
    # First, try to find a matching SELLER file by normalized name
    files = _find_seller_files()
    lookup = supplier_name.strip().lower()

    # Use canonical alias map when possible
    alias_map = ALIAS_MAP

    # If alias present, try that file explicitly and attach canonical supplier name
    if lookup in alias_map:
        candidate = SELLER_FILES_DIR / alias_map[lookup]
        if candidate.exists():
            canonical = lookup.upper()
            items = list(_get_cached_bins_for_file(candidate, canonical))
            return redistribute_suppliers_evenly(items)

    # Fallback: try to find a file whose normalized stem matches or contains the supplier_name
    target = None
    for p in files:
        name = _normalize_supplier_name_from_path(p).lower()
        if name == lookup or lookup in name or name in lookup:
            target = p
            break

    if not target:
        return []

    stem = _normalize_supplier_name_from_path(target)
    canonical = _canonical_supplier_name_from_stem(stem)
    items = list(_get_cached_bins_for_file(target, canonical))
    return redistribute_suppliers_evenly(items)

def get_flag_for_country(country_name: str) -> str:
    """
    Return flag emoji for a given country name.

    Priority:
    1) Try to find the flag directly from parsed SELLER files
       (so we always match exactly what is in the data files).
    2) Fallback to a static name→flag map for common aliases.
    3) Fallback to 🌍 if nothing is found.
    """
    if not country_name:
        return "🌍"

    lookup = country_name.strip().lower()
    if not lookup:
        return "🌍"

    # 1) Try to read from SELLER files (uses cache)
    try:
        files = _find_seller_files()
        for p in files:
            supplier = _normalize_supplier_name_from_path(p)
            for parsed in _get_cached_bins_for_file(p, supplier):
                country = parsed.get("country", "").strip()
                if not country:
                    continue
                c_low = country.lower()
                if c_low == lookup or lookup in c_low or c_low in lookup:
                    flag = parsed.get("flag")
                    if flag:
                        return flag
    except Exception as e:
        print(f"get_flag_for_country: error while scanning files: {e}")

    # 2) Fallback static map (lower‑case keys)
    flag_map = {
        "usa": "🇺🇸",
        "united states": "🇺🇸",
        "us": "🇺🇸",
        "uk": "🇬🇧",
        "united kingdom": "🇬🇧",
        "great britain": "🇬🇧",
        "russia": "🇷🇺",
        "russian federation": "🇷🇺",
        "ukraine": "🇺🇦",
        "canada": "🇨🇦",
        "australia": "🇦🇺",
        "germany": "🇩🇪",
        "france": "🇫🇷",
        "italy": "🇮🇹",
        "spain": "🇪🇸",
        "netherlands": "🇳🇱",
        "japan": "🇯🇵",
        "brazil": "🇧🇷",
        "china": "🇨🇳",
        "people's republic of china": "🇨🇳",
        "india": "🇮🇳",
        "mexico": "🇲🇽",
        "south korea": "🇰🇷",
        "sweden": "🇸🇪",
        "norway": "🇳🇴",
        "switzerland": "🇨🇭",
        "belgium": "🇧🇪",
        "denmark": "🇩🇰",
        "finland": "🇫🇮",
        "poland": "🇵🇱",
        "portugal": "🇵🇹",
        "romania": "🇷🇴",
        "turkey": "🇹🇷",
        "greece": "🇬🇷",
        "czech republic": "🇨🇿",
        "hungary": "🇭🇺",
        "austria": "🇦🇹",
        "egypt": "🇪🇬",
        "saudi arabia": "🇸🇦",
        "uae": "🇦🇪",
        "united arab emirates": "🇦🇪",
        "south africa": "🇿🇦",
        "argentina": "🇦🇷",
        "chile": "🇨🇱",
        "colombia": "🇨🇴",
        "indonesia": "🇮🇩",
        "malaysia": "🇲🇾",
        "philippines": "🇵🇭",
        "singapore": "🇸🇬",
        "thailand": "🇹🇭",
        "vietnam": "🇻🇳",
        "israel": "🇮🇱",
        "iran": "🇮🇷",
        "pakistan": "🇵🇰",
        "nigeria": "🇳🇬",
        "morocco": "🇲🇦",
        "maroc": "🇲🇦",
        "algeria": "🇩🇿",
        "kenya": "🇰🇪",
        "ethiopia": "🇪🇹",
        "tunisia": "🇹🇳",
    }

    return flag_map.get(lookup, "🌍")

# Кеш для поставщиков
_SUPPLIERS_CACHE = ["ADMIN", "ZEUS", "tec_9", "topseller", "jessePinkman", "Operator", "macho"]
_SUPPLIERS_COUNT = len(_SUPPLIERS_CACHE)

# ─── Кэш файлов в памяти ───────────────────────────────────────────────────
# { canonical_key -> [parsed_bin, ...] }
_FILE_CACHE: dict = {}
_FILE_MTIME: dict = {}  # { path_str -> mtime } для инвалидации при изменении файла

def _get_cached_bins_for_file(path, supplier_name: str) -> list:
    """Читает файл один раз и кэширует результат. Перечитывает если файл изменился."""
    import os
    path_str = str(path)
    try:
        mtime = os.path.getmtime(path_str)
    except OSError:
        return []

    if path_str in _FILE_CACHE and _FILE_MTIME.get(path_str) == mtime:
        return _FILE_CACHE[path_str]

    items = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parsed = _parse_line(line, supplier_name=supplier_name)
                items.append(parsed)
    except Exception as e:
        print(f"_get_cached_bins_for_file: error reading {path}: {e}")

    _FILE_CACHE[path_str] = items
    _FILE_MTIME[path_str] = mtime
    return items

def invalidate_cache(path=None):
    """Сбрасывает кэш (весь или для конкретного файла) — вызывать после decrease_pcs_in_file."""
    if path is None:
        _FILE_CACHE.clear()
        _FILE_MTIME.clear()
    else:
        path_str = str(path)
        _FILE_CACHE.pop(path_str, None)
        _FILE_MTIME.pop(path_str, None)

def decrease_pcs_in_file(bin_code: str):
    """Уменьшает pcs на 1 для указанного BIN во всех SELLER файлах. Если pcs становится 0, строка удаляется."""
    files = _find_seller_files()
    for p in files:
        try:
            with open(p, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            new_lines = []
            changed = False
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    new_lines.append(line)
                    continue
                m = _LINE_RE.match(stripped)
                if m:
                    rest = m.group("rest")
                    # Проверяем что BIN совпадает
                    if m.group("bin").strip() == bin_code:
                        pcs_m = _PCS_PRICE_RE.search(stripped)
                        if pcs_m:
                            old_pcs = int(pcs_m.group("pcs"))
                            new_pcs = old_pcs - 1
                            if new_pcs <= 0:
                                # Убираем строку полностью
                                changed = True
                                continue
                            else:
                                # Заменяем число pcs
                                old_tag = pcs_m.group(0)  # e.g. "[627 pcs.] 12.0$"
                                new_tag = old_tag.replace(f"[{old_pcs} pcs.]", f"[{new_pcs} pcs.]", 1)
                                new_line = line.replace(old_tag, new_tag, 1)
                                new_lines.append(new_line)
                                changed = True
                                continue
                new_lines.append(line)
            if changed:
                with open(p, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                invalidate_cache(p)  # сбрасываем кэш для этого файла
        except Exception as e:
            print(f"decrease_pcs_in_file: error processing {p}: {e}")


def redistribute_suppliers_evenly(bins_list):
    """
    Быстро распределяет BIN'ы между поставщиками
    """
    if not bins_list:
        return bins_list
    
    # Используем кешированные данные
    for i, bin_item in enumerate(bins_list):
        bin_item['supplier_name'] = _SUPPLIERS_CACHE[i % _SUPPLIERS_COUNT]
    
    return bins_list