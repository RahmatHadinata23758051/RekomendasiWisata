import re
import logging
import yaml
import os
from typing import List, Optional, Tuple
from src.models.schemas import RawAttractionRecord, NormalizedAttractionRecord

logger = logging.getLogger("scraper.pipeline.normalize")

# Helper to load regions config for city matching
def _load_regions() -> list:
    try:
        config_path = os.path.join("config", "regions.yaml")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f).get("regions", [])
    except Exception as e:
        logger.error(f"Failed to load regions config in normalize: {e}")
    return []

REGIONS = _load_regions()

REGION_MAP = {
    "bandar_lampung": "Kota Bandar Lampung",
    "lampung_barat": "Kabupaten Lampung Barat",
    "lampung_selatan": "Kabupaten Lampung Selatan",
    "lampung_tengah": "Kabupaten Lampung Tengah",
    "lampung_timur": "Kabupaten Lampung Timur",
    "lampung_utara": "Kabupaten Lampung Utara",
    "mesuji": "Kabupaten Mesuji",
    "pesawaran": "Kabupaten Pesawaran",
    "pesisir_barat": "Kabupaten Pesisir Barat",
    "pringsewu": "Kabupaten Pringsewu",
    "tanggamus": "Kabupaten Tanggamus",
    "tulang_bawang": "Kabupaten Tulang Bawang",
    "tulang_bawang_barat": "Kabupaten Tulang Bawang Barat",
    "way_kanan": "Kabupaten Way Kanan",
    "metro": "Kota Metro",
}

def canonicalize_region_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    name_str = str(name).strip()
    cleaned = name_str.lower().replace("-", "_").replace(" ", "_")
    if cleaned in REGION_MAP:
        return REGION_MAP[cleaned]
    for canonical in REGION_MAP.values():
        if canonical.lower() == name_str.lower():
            return canonical
    for canonical in REGION_MAP.values():
        if name_str.lower() in canonical.lower() or canonical.lower() in name_str.lower():
            return canonical
    return name_str


def clean_whitespace(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    return " ".join(text.split()).strip()

def normalize_place_name(name: str) -> str:
    """
    Cleans name for display.
    """
    return clean_whitespace(name) or ""

def normalize_name_for_matching(name: str) -> str:
    """
    Normalizes place name to a canonical form used for fuzzy matching.
    Removes common Indonesian tourism prefixes and punctuation.
    """
    name_clean = name.lower()
    
    # Remove HTML entities or weird punctuation
    name_clean = re.sub(r"[^\w\s]", " ", name_clean)
    
    # Remove common tourism prefixes/suffixes in Indonesian/English
    stopwords = [
        "tempat", "wisata", "destinasi", "objek", "pantai", "beach", "curup", "air terjun", 
        "waterfall", "gunung", "mount", "bukit", "hill", "pulau", "island", "danau", "lake", 
        "taman", "park", "hutan", "forest", "desa", "kampung", "situs", "museum", "cagar", 
        "waterpark", "kebun", "zoo", "gua", "cave", "bendungan", "waduk", "pemandian", 
        "sumber air panas", "camping ground", "spot", "sunrise", "sunset", "kabupaten", 
        "kota", "kecamatan", "kelurahan", "lampung"
    ]
    
    # Sort stopwords by length descending to prevent partial replacements of longer terms
    stopwords.sort(key=len, reverse=True)
    
    for word in stopwords:
        # Match word bounds or spaces
        name_clean = re.sub(rf"\b{word}\b", " ", name_clean)
        
    # Standardize spaces
    return clean_whitespace(name_clean) or name.lower().strip()

def parse_coordinate(coord: Optional[float]) -> Optional[float]:
    if coord is None:
        return None
    try:
        val = float(coord)
        if -90.0 <= val <= 90.0 or -180.0 <= val <= 180.0:
            return val
    except (ValueError, TypeError):
        pass
    return None

def is_within_lampung(lat: Optional[float], lon: Optional[float]) -> bool:
    """
    Checks if coordinates are within the bounding box of Lampung Province.
    """
    if lat is None or lon is None:
        return False
    # Lampung bounds: Lat [-6.5, -3.5], Lon [103.0, 106.5]
    return -6.5 <= lat <= -3.5 and 103.0 <= lon <= 106.5

def extract_city_regency(
    address: Optional[str],
    default_city: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None
) -> Optional[str]:
    """
    Identifies which Lampung city/regency the address or coordinates belong to.
    """
    # 1. Try address matching first (longest search keyword first to prevent false-matches like Tulang Bawang Barat -> Tulang Bawang)
    if address:
        addr_lower = address.lower()
        sorted_regions = sorted(REGIONS, key=lambda x: max(len(x["name"]), len(x["query"])), reverse=True)
        for reg in sorted_regions:
            reg_name = reg["name"].lower()
            reg_query = reg["query"].lower()
            if reg_query in addr_lower or reg_name in addr_lower:
                return reg["name"]

    # 2. Try coordinates bounding box match
    if lat is not None and lon is not None:
        for reg in REGIONS:
            bbox = reg.get("bbox")
            if bbox and len(bbox) == 4:
                min_lon, min_lat, max_lon, max_lat = bbox
                if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
                    return reg["name"]

    return default_city

def normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    # Strip non-numeric characters except +
    cleaned = re.sub(r"[^\d+]", "", phone)
    
    # Standardize indonesian format: 08xx -> +628xx
    if cleaned.startswith("0"):
        cleaned = "+62" + cleaned[1:]
    elif cleaned.startswith("62") and not cleaned.startswith("+"):
        cleaned = "+" + cleaned
        
    return cleaned

def normalize_website(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    url_clean = url.strip().lower()
    if not url_clean.startswith(("http://", "https://")):
        url_clean = "https://" + url_clean
    # Strip trailing slash
    if url_clean.endswith("/"):
        url_clean = url_clean[:-1]
    return url_clean

def parse_indonesian_price(price_str: Optional[str]) -> Optional[float]:
    """
    Extracts numeric price value from Indonesian currency strings.
    E.g. "Rp 15.000" -> 15000.0, "Rp10k" -> 10000.0, "Free" -> 0.0, "Gratis" -> 0.0
    """
    if not price_str:
        return None
        
    p_str = price_str.lower().strip()
    
    # Check if the text literally represents zero or free
    if p_str in ["0", "rp 0", "rp. 0", "rp0"] or any(free_word in p_str for free_word in ["free", "gratis", "cuma-cuma"]):
        return 0.0
        
    # Convert 'k' notation (e.g. 15k -> 15000)
    k_match = re.search(r"(\d+(?:\.\d+)?)\s*k\b", p_str)
    if k_match:
        try:
            return float(k_match.group(1)) * 1000
        except ValueError:
            pass

    # Extract digits, ignoring dots as thousand separators
    # E.g. "rp. 15.000,00" or "Rp 15.000"
    # Find all sequences of numbers, dots, and commas
    digits_match = re.findall(r"[\d\.,]+", p_str)
    if digits_match:
        # Grab the longest match which is likely the price
        price_num_str = max(digits_match, key=len)
        
        # Clean price_num_str
        # If it contains both dots and commas, comma is probably decimal and dot is thousand separator
        if "." in price_num_str and "," in price_num_str:
            parts = price_num_str.split(",")
            integer_part = parts[0].replace(".", "")
            decimal_part = parts[1]
            price_num_str = f"{integer_part}.{decimal_part}"
        elif "," in price_num_str:
            # If only comma, it might be thousand separator or decimal
            # In IDR, comma is usually decimal (e.g., 15000,00) or thousand (rarely, unless English style).
            # Let's count decimal digits: if exactly 2, treat as decimal.
            parts = price_num_str.split(",")
            if len(parts) == 2 and len(parts[1]) == 2:
                price_num_str = parts[0].replace(".", "") + "." + parts[1]
            else:
                price_num_str = price_num_str.replace(",", "")
        elif "." in price_num_str:
            # In Indonesian, dot is thousand separator. E.g. 15.000
            # If there's a dot, we check if it looks like a thousand separator: e.g. "15.000" -> 15000
            # If it's a decimal dot (e.g. "15.5"), it's short.
            parts = price_num_str.split(".")
            if len(parts) > 1 and len(parts[-1]) == 3:
                price_num_str = price_num_str.replace(".", "")
                
        try:
            return float(price_num_str)
        except ValueError:
            pass
            
    return None

def classify_record(
    name: str,
    categories: List[str],
    lat: Optional[float],
    lon: Optional[float],
    description: Optional[str] = None,
    review_count: Optional[int] = None,
    search_keyword: Optional[str] = None
) -> Tuple[str, str, float, List[str]]:
    """
    Classifies a record into accepted, rejected, or manual_review based on categories and name.
    Returns: (classification, reason, confidence, signals)
    """
    # 1. Coordinate check
    if lat is not None and lon is not None:
        if not is_within_lampung(lat, lon):
            return "manual_review", f"Koordinat ({lat}, {lon}) di luar target Lampung", 0.5, ["outside_bounds"]
    
    if not categories:
        return "manual_review", "Lokasi tanpa kategori", 0.5, ["missing_categories"]
        
    primary_cat = categories[0].strip().title()
    name_lower = name.lower()

    # Reject strong business/accommodation terms in the name unless category is strongly accepted
    rejected_name_kws = [
        "hotel", "homestay", "guest house", "guesthouse", "villa", "penginapan", "resort", "warung", "cafe", 
        "coffee", "kopi", "bengkel", "sekolah", "sdn", "smp", "sma", "paud", "tk", "toko", "cell", "mart", 
        "spbu", "pertamina", "salon", "laundry", "apotek", "klinik", "kost", "kos-kosan"
    ]

    # Specific strict check for category "Taman" or "Park"
    if primary_cat.lower() in ["taman", "park"]:
        signals = []
        tourist_name_kws = [
            "wisata", "rekreasi", "hiburan", "mini", "bermain", "water", "safari", 
            "keluarga", "flora", "fauna", "satwa", "hewan", "kupu-kupu", "bunga", 
            "theme park", "amusement", "leisure", "agrowisata", "edukasi", "sakura", 
            "outbound", "culinary", "kuliner", "selfie", "foto", "kelinci", "rusa", "hutan"
        ]
        
        # Check name
        for kw in tourist_name_kws:
            if re.search(rf"\b{kw}\b", name_lower):
                signals.append(f"name_keyword:{kw}")
                
        # Check description
        if description:
            desc_lower = description.lower()
            for kw in tourist_name_kws:
                if re.search(rf"\b{kw}\b", desc_lower):
                    signals.append(f"desc_keyword:{kw}")
                    
        # Check secondary categories
        for cat in categories[1:]:
            cat_lower = cat.lower()
            if any(ac.lower() in cat_lower for ac in ["tujuan wisata", "taman hiburan", "pusat rekreasi", "cagar alam", "kebun binatang", "agrowisata"]):
                signals.append(f"secondary_category:{cat}")
                
        # Check review count
        if review_count is not None and review_count >= 15:
            signals.append(f"high_reviews:{review_count}")
            
        # Check search keyword
        if search_keyword:
            sk_lower = search_keyword.lower()
            for kw in ["taman wisata", "wisata keluarga", "taman bermain", "taman kota"]:
                if kw in sk_lower:
                    signals.append(f"search_keyword:{kw}")
                    
        if signals:
            return "accepted", f"Kategori 'Taman' disetujui dengan sinyal: {', '.join(signals)}", 0.9, signals
            
        # Check if local/neighborhood park keywords
        local_park_kws = ["perumahan", "perum", "rt ", "rw ", "dharma wanita", "griya", "residence", "cluster", "komplek", "asrama", "kantor", "pkk", "kelurahan", "kecamatan"]
        for kw in local_park_kws:
            if kw in name_lower:
                return "manual_review", f"Taman lingkungan/perumahan lokal: '{name}'", 0.5, ["local_park_keyword"]
                
        return "manual_review", "Kategori 'Taman' tanpa sinyal wisata khusus", 0.5, []

    # Specific check for "Rumah Wisata" (often translated homestays)
    if primary_cat.lower() in ["rumah wisata"]:
        # If it doesn't have wisata keywords in name, reject it as lodging
        has_wisata_kw = any(w in name_lower for w in ["wisata", "pantai", "situs", "candi", "budaya"])
        if not has_wisata_kw:
            return "rejected", "Kategori utama 'Rumah wisata' teridentifikasi sebagai penginapan/akomodasi", 1.0, ["category_rejected"]

    accepted_cats = [
        "Tujuan Wisata", "Pantai", "Air Terjun", "Museum", "Taman Rekreasi Air", 
        "Taman Hiburan", "Pusat Rekreasi", "Bumi Perkemahan", "Area Mendaki", "Tempat Bersejarah", 
        "Cagar Alam", "Kebun Binatang", "Agrowisata", "Desa Wisata", "Tourist Attraction", 
        "National Park", "Nature Preserve"
    ]
    
    rejected_cats = [
        "Hotel", "Penginapan", "Restoran", "Kafe", "Biro Perjalanan", "Agen Perjalanan", 
        "Rental Mobil", "Agen Sewa Mobil", "Kantor Perusahaan", "Sekolah", "Taman Kanak-kanak", 
        "Toko", "Pusat Perbelanjaan", "Dealer", "Bengkel", "SPBU", "Perumahan", "Lodge",
        "Coffee Shop", "Guest House", "Homestay", "Villa", "Rumah wisata"
    ]
    
    manual_cats = [
        "Tempat Ibadah", "Taman Lingkungan", "Lapangan", "Monumen Kecil", "Spot Foto Informal",
        "Masjid", "Gereja", "Pura", "Vihara", "Klenteng", "Mosque", "Church", "Temple"
    ]

    # Check accepted categories list
    if any(ac.lower() in primary_cat.lower() for ac in accepted_cats):
        for rk in ["hotel", "homestay", "villa", "bengkel", "spbu", "paud", "sekolah"]:
            if f" {rk} " in f" {name_lower} " or name_lower.startswith(rk):
                return "rejected", f"Nama mengandung unsur bisnis/non-wisata: '{name}'", 0.8, ["name_rejected_keyword"]
        return "accepted", f"Kategori utama '{primary_cat}' disetujui", 1.0, ["category_accepted"]

    # Check rejected categories list
    if any(rc.lower() in primary_cat.lower() for rc in rejected_cats):
        return "rejected", f"Kategori utama '{primary_cat}' ditolak", 1.0, ["category_rejected"]

    # Check manual categories list
    if any(mc.lower() in primary_cat.lower() for mc in manual_cats):
        return "manual_review", f"Kategori utama '{primary_cat}' memerlukan review manual", 0.5, ["category_manual"]

    # Check secondary categories for any accepted ones
    for cat in categories[1:]:
        cat_title = cat.strip().title()
        if any(ac.lower() in cat_title.lower() for ac in accepted_cats):
            return "accepted", f"Kategori tambahan '{cat_title}' disetujui", 0.9, ["secondary_category_accepted"]

    # Name-based checks
    for kw in rejected_name_kws:
        if re.search(rf"\b{kw}\b", name_lower):
            return "rejected", f"Nama mengandung keyword bisnis '{kw}'", 0.9, ["name_rejected_keyword"]

    accepted_name_kws = ["wisata", "pantai", "curup", "air terjun", "pulau", "bukit", "gunung", "candi", "situs", "taman", "waterpark"]
    for kw in accepted_name_kws:
        if re.search(rf"\b{kw}\b", name_lower):
            return "accepted", f"Nama mengandung keyword wisata '{kw}'", 0.8, ["name_accepted_keyword"]

    # Default to manual review
    return "manual_review", f"Kategori '{primary_cat}' tidak terklasifikasi secara otomatis", 0.5, []

def map_canonical_categories(name: str, categories: List[str]) -> Tuple[str, List[str]]:
    """
    Maps raw categories and name to canonical category tags.
    """
    tags = set()
    name_lower = name.lower()
    cats_text = " ".join(categories).lower() + " " + name_lower

    if "pantai" in cats_text or "beach" in cats_text:
        tags.add("beach")
        tags.add("nature")
    if "pulau" in cats_text or "island" in cats_text:
        tags.add("island")
        tags.add("nature")
    if "gunung" in cats_text or "mount" in cats_text:
        tags.add("mountain")
        tags.add("nature")
    if "bukit" in cats_text or "hill" in cats_text:
        tags.add("hill")
        tags.add("nature")
    if "air terjun" in cats_text or "waterfall" in cats_text or "curup" in cats_text:
        tags.add("waterfall")
        tags.add("nature")
    if "danau" in cats_text or "lake" in cats_text:
        tags.add("lake")
        tags.add("nature")
    if "sungai" in cats_text or "river" in cats_text:
        tags.add("river")
        tags.add("nature")
    if "hutan" in cats_text or "forest" in cats_text or "mangrove" in cats_text:
        tags.add("forest")
        tags.add("nature")
    if "camping" in cats_text or "kemah" in cats_text:
        tags.add("camping")
        tags.add("nature")
    if "museum" in cats_text:
        tags.add("museum")
        tags.add("culture")
    if "sejarah" in cats_text or "historic" in cats_text or "candi" in cats_text or "situs" in cats_text or "monumen" in cats_text:
        tags.add("history")
        tags.add("culture")
    if "religi" in cats_text or "masjid" in cats_text or "church" in cats_text or "temple" in cats_text or "makam" in cats_text:
        tags.add("religious")
        tags.add("culture")
    if "edukasi" in cats_text or "education" in cats_text:
        tags.add("education")
    if "taman" in cats_text or "park" in cats_text:
        tags.add("park")
    if "waterpark" in cats_text or "water park" in cats_text or "kolam" in cats_text:
        tags.add("waterpark")
        tags.add("recreation")
    if "agro" in cats_text or "kebun" in cats_text or "sawah" in cats_text:
        tags.add("agrotourism")
        tags.add("nature")
    if "keluarga" in cats_text or "family" in cats_text or "hiburan" in cats_text or "bermain" in cats_text:
        tags.add("family")
        tags.add("recreation")
    if "rekreasi" in cats_text or "recreation" in cats_text or "zoo" in cats_text or "binatang" in cats_text:
        tags.add("recreation")

    if any(w in cats_text for w in ["alam", "nature"]):
        tags.add("nature")
    if any(w in cats_text for w in ["budaya", "culture", "adat", "seni"]):
        tags.add("culture")

    if not tags:
        if "wisata" in name_lower or "attraction" in cats_text:
            tags.add("recreation")
        else:
            tags.add("other")

    priority = [
        "waterfall", "beach", "island", "mountain", "hill", "lake", "river", "forest", 
        "camping", "museum", "history", "religious", "waterpark", "agrotourism", 
        "education", "family", "recreation", "park", "culture", "nature", "other"
    ]
    
    primary = "other"
    for p in priority:
        if p in tags:
            primary = p
            break
            
    return primary, list(tags)

def normalize_record(raw: RawAttractionRecord) -> NormalizedAttractionRecord:
    lat = parse_coordinate(raw.latitude)
    lon = parse_coordinate(raw.longitude)
    
    city_regency = extract_city_regency(raw.raw_address, raw.query_region, lat, lon)
    city_regency = canonicalize_region_name(city_regency) or "Kota Bandar Lampung"
    name = normalize_place_name(raw.raw_name)
    normalized_name = normalize_name_for_matching(name)
    
    cats = []
    if raw.raw_categories:
        for c in raw.raw_categories:
            clean_c = clean_whitespace(c.replace("_", " ").lower())
            if clean_c:
                cats.append(clean_c)
                
    # Format phone and website
    phone = normalize_phone(raw.phone) if raw.phone else None
    website = normalize_website(raw.website) if raw.website else (normalize_website(raw.source_url) if raw.source_url else None)
    
    # Format opening hours
    opening_hours = None
    if raw.opening_hours:
        parts = []
        for oh in raw.opening_hours:
            day = oh.get("day", "")
            hours = oh.get("hours", "")
            if day or hours:
                parts.append(f"{day}: {hours}")
        opening_hours = "; ".join(parts)
        
    # Format facilities from additionalInfo
    facilities = []
    if raw.facilities:
        for key, items in raw.facilities.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        for item_name, val in item.items():
                            if val:
                                facilities.append(f"{key}: {item_name}")
            elif isinstance(items, dict):
                for item_name, val in items.items():
                    if val:
                        facilities.append(f"{key}: {item_name}")
                        
    # Run classification with extra signals
    classification, reason, confidence, signals = classify_record(
        name, cats, lat, lon,
        description=raw.description,
        review_count=raw.review_count,
        search_keyword=raw.query_keyword
    )
    
    # Business status
    business_status = "OPERATIONAL"
    if raw.permanently_closed:
        business_status = "CLOSED_PERMANENTLY"
    elif raw.temporarily_closed:
        business_status = "CLOSED_TEMPORARILY"
        
    return NormalizedAttractionRecord(
        source_record_id=raw.source_record_id,
        source=raw.source,
        source_place_id=raw.source_place_id,
        name=name,
        normalized_name=normalized_name,
        address=clean_whitespace(raw.raw_address),
        city_regency=city_regency,
        district=raw.district,
        village=None,
        latitude=lat,
        longitude=lon,
        categories=cats,
        rating=raw.rating,
        review_count=raw.review_count,
        phone=phone,
        website=website,
        price_min=None,
        price_max=None,
        currency=None,
        price_notes=None,
        opening_hours=opening_hours,
        business_status=business_status,
        facilities=facilities,
        source_url=raw.source_url,
        collected_at=raw.collected_at,
        classification=classification,
        classification_confidence=confidence,
        classification_signals=signals,
        classification_reason=reason,
        raw_payload_path=raw.raw_payload_path,
        query_region=raw.query_region
    )
