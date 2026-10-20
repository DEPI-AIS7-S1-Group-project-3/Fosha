"""Curated hotel and transport recommendations for Egyptian destinations."""
from typing import Any, Dict, List, Optional

RECOMMENDATIONS: Dict[str, Dict[str, Any]] = {
    "Cairo": {
        "hotels": {
            "en": [
                {"area": "Downtown & Nile Corniche", "desc": "Central location, scenic river walks, close to the Egyptian Museum and Tahrir Square (e.g. Steigenberger Hotel El Tahrir, Ramses Hilton)."},
                {"area": "Zamalek Island", "desc": "Upscale, quiet green neighborhood with art galleries, leafy cafes, and boutique hotels (e.g. Marriott Cairo Palace)."},
                {"area": "Giza Pyramids Area", "desc": "Stunning balcony views directly facing the Pyramids and easy morning access to the plateau (e.g. Marriott Mena House, Giza boutique lodges)."}
            ],
            "ar": [
                {"area": "وسط البلد وكورنيش النيل", "desc": "موقع مركزي حيوي على مقربة من المتحف المصري وميدان التحرير والمطاعم التراثية."},
                {"area": "حي الزمالك", "desc": "جزيرة راقية هادئة تضم مساحات خضراء ومطاعم وفنادق تاريخية متميزة."},
                {"area": "منطقة أهرامات الجيزة", "desc": "إطلالات مباشرة ومبهرة على الأهرامات وسهولة الوصول لهضبة الجيزة والمتحف الكبير."}
            ]
        },
        "transport": {
            "en": [
                {"mode": "City Touring", "desc": "Uber and Careem operate widely and affordably throughout Greater Cairo."},
                {"mode": "Day Trips & Pyramids", "desc": "Hire a licensed air-conditioned private car with driver for full-day sightseeing (Pyramids, Saqqara, NMEC)."},
                {"mode": "Inter-city to Luxor/Aswan", "desc": "EgyptAir domestic flight (1 hr) from Cairo Airport (CAI) or Wataniya Sleeper Train from Ramses Station."}
            ],
            "ar": [
                {"mode": "التنقل داخل المدينة", "desc": "تطبيقات النقل الذكي (أوبر وكريم) متوفرة بكثرة وبأسعار مناسبة للتنقل السريع."},
                {"mode": "الجولات اليومية", "desc": "يُفضل استئجار سيارة خاصة مكيفة بسائق ليوم كامل لزيارة الأهرامات وسقارة والمتحف القومي للحضارة."},
                {"mode": "السفر إلى الأقصر وأسوان", "desc": "طيران داخلي (ساعة واحدة) عبر مطار القاهرة، أو قطار النوم (الوطنية) من محطة رمسيس."}
            ]
        }
    },
    "Luxor": {
        "hotels": {
            "en": [
                {"area": "East Bank (Downtown)", "desc": "Walking distance to Luxor Temple, the lively Nile Corniche promenade, and local markets (e.g. Sofitel Winter Palace, Steigenberger Nile Palace)."},
                {"area": "West Bank (Theban Necropolis)", "desc": "Serene countryside retreat among sugarcane fields, eco-guesthouses just minutes from the Valley of the Kings."}
            ],
            "ar": [
                {"area": "البر الشرقي (وسط المدينة)", "desc": "بالقرب من معبد الأقصر، كورنيش النيل، والمطاعم ومحطة القطار (مثل وينتر بالاس التاريخي)."},
                {"area": "البر الغربي", "desc": "أجواء ريفية هادئة ونزل بيئية أصيلة تقع مباشرة بجوار وادي الملوك ومعبد حتشبسوت."}
            ]
        },
        "transport": {
            "en": [
                {"mode": "Nile River Crossing", "desc": "Local public ferry (5-10 EGP) or motorized wooden water-taxis take 5 minutes between East and West banks."},
                {"mode": "West Bank Excursions", "desc": "Pre-arrange an AC taxi/van for the morning circuit (Valley of the Kings, Hatshepsut, Colossi of Memnon)."},
                {"mode": "Sunset Sailing", "desc": "Rent a traditional white-sail Nile felucca for a tranquil 1-2 hour sail to Banana Island."}
            ],
            "ar": [
                {"mode": "العبّارة النيلية", "desc": "المعدية النيلية العامة أو المراكب السريعة تعبر بين البرين الشرقي والغربي في ٥ دقائق."},
                {"mode": "جولات البر الغربي", "desc": "يُنصح بتأجير تاكسي خاص أو ميني باص مكيف لجولة الصباح (وادي الملوك، حتشبسوت، تمثالا ممنون)."},
                {"mode": "فلوكة نيلية", "desc": "استمتع بجولة شراعية تقليدية عند الغروب في النيل وصولًا إلى جزيرة الموز."}
            ]
        }
    },
    "Alexandria": {
        "hotels": {
            "en": [
                {"area": "Corniche & Stanley Bay", "desc": "Breathtaking Mediterranean sea views, close to Stanley Bridge and fine seafood dining (e.g. Four Seasons San Stefano, Romance Hotel)."},
                {"area": "Raml Station & Mansheya", "desc": "Classic belle-époque architecture, within walking distance of the Roman Amphitheatre and Alexandria Library."}
            ],
            "ar": [
                {"area": "الكورنيش وخليج ستانلي", "desc": "إطلالة بانورامية على البحر المتوسط ومطاعم الأسماك الشهيرة (مثل فورسيزونز سان ستيفانو)."},
                {"area": "محطة الرمل والمنشية", "desc": "طابع كلاسيكي تاريخي وقرب من المسرح الروماني ومكتبة الإسكندرية والأسواق الشعبية."}
            ]
        },
        "transport": {
            "en": [
                {"mode": "High-Speed Rail from Cairo", "desc": "The Spanish Talgo Express Train connects Cairo and Alexandria in just 2 hours in air-conditioned comfort."},
                {"mode": "Coastal Travel", "desc": "Uber or the yellow-and-black city taxis along the Corniche from Qaitbay Citadel to Montaza Palace."}
            ],
            "ar": [
                {"mode": "القطار من القاهرة", "desc": "قطار تالجو الإسباني الفاخر يصل الإسكندرية من القاهرة في نحو ساعتين بأعلى مستويات الراحة."},
                {"mode": "التنقل الساحلي", "desc": "تطبيقات أوبر أو التاكسي الأصفر والأسود على طول الكورنيش من قلعة قايتباي حتى حدائق المنتزه."}
            ]
        }
    },
    "Aswan": {
        "hotels": {
            "en": [
                {"area": "Elephantine Island & West Bank", "desc": "Vibrant Nubian guesthouses painted in bright indigo and earth tones, offering home-cooked meals and tranquil river vistas."},
                {"area": "Aswan Corniche", "desc": "Prime spots overlooking the granite rocks and feluccas (e.g. Sofitel Legend Old Cataract, Basma Hotel)."}
            ],
            "ar": [
                {"area": "جزيرة إلفنتين وغرب أسوان", "desc": "بيوت نوبية ملونة بتجربة ضيافة أصيلة ومأكولات طازجة وإطلالات هادئة على جزر النيل."},
                {"area": "كورنيش أسوان", "desc": "موقع رائع يطل على صخور الجرانيت وجزر النيل (مثل فندق أولد كاتاراكت الأسطوري)."}
            ]
        },
        "transport": {
            "en": [
                {"mode": "Island Access", "desc": "Motorized Nile boats are the everyday highway connecting islands to the city mainland."},
                {"mode": "Abu Simbel Excursion", "desc": "Early morning shared tourist shuttle or 40-minute domestic flight from Aswan Airport (ASW)."}
            ],
            "ar": [
                {"mode": "التنقل النهري", "desc": "اللانشات النيلية والمراكب هي الوسيلة الأساسية للتنقل بين الجزر والكورنيش."},
                {"mode": "رحلة أبو سمبل", "desc": "حافلات سياحية مجمعة صباحًا مبكرًا عبر طريق أسوان-أبو سمبل أو طيران داخلي (٤٠ دقيقة)."}
            ]
        }
    },
    "South Sinai": {
        "hotels": {
            "en": [
                {"area": "Naama Bay & Nabq (Sharm)", "desc": "World-class beachfront all-inclusive resorts with private beaches, dive centres, and nightlife."},
                {"area": "Saint Catherine Foothills", "desc": "Quiet mountain eco-lodges perfect for hiking Mount Sinai for the sunrise."}
            ],
            "ar": [
                {"area": "خليج نعمة ونبق (شرم الشيخ)", "desc": "منتجعات شاطئية متكاملة تضم شواطئ رملية ومراكز غوص عالمية."},
                {"area": "سفح جبل سانت كاترين", "desc": "نزل بيئية جبلية ملائمة لتسلق جبل موسى ومشاهدة شروق الشمس."}
            ]
        },
        "transport": {
            "en": [
                {"mode": "Sharm El Sheikh Airport (SSH)", "desc": "Direct domestic and international flights; airport taxis or hotel transfers to your resort."},
                {"mode": "Excursions", "desc": "Organized 4x4 desert tours for Saint Catherine, Blue Hole, and Ras Mohamed National Park."}
            ],
            "ar": [
                {"mode": "مطار شرم الشيخ الدولي", "desc": "رحلات طيران منتظمة وسيارات نقل الفنادق للوصول السريع للمنتجع."},
                {"mode": "الرحلات الجبلية والبحرية", "desc": "حافلات ورحلات دفع رباعي منظمة لمحمية رأس محمد وسانت كاترين."}
            ]
        }
    },
    "Red Sea": {
        "hotels": {
            "en": [
                {"area": "El Gouna", "desc": "Upscale lagoon town with golf courses, turquoise waterways, boutique hotels, and Abu Tig Marina."},
                {"area": "Hurghada Promenade (El Mamsha)", "desc": "Family-friendly beachfront resorts with waterparks and coral reefs."}
            ],
            "ar": [
                {"area": "مدينة الجونة", "desc": "بحيرات شاطئية راقية، فنادق ومارينا اليخوت، ومطاعم عالمية."},
                {"area": "الممشى السياحي بالغردقة", "desc": "منتجعات شاطئية وألعاب مائية ورياضات بحرية مناسبة للعائلات."}
            ]
        },
        "transport": {
            "en": [
                {"mode": "Airport Transfer", "desc": "Hurghada Airport (HRG) is only 15 minutes from downtown and 30 minutes from El Gouna."},
                {"mode": "Marine Travel", "desc": "Daily chartered boats depart for Giftun Island and coral diving excursions."}
            ],
            "ar": [
                {"mode": "المطار", "desc": "مطار الغردقة الدولي يبعد ١٥ دقيقة عن المدينة ونحو نصف ساعة عن الجونة."},
                {"mode": "الرحلات البحرية", "desc": "يخوت بحرية يومية إلى جزيرة جفتون ومواقع الغوص والشعب المرجانية."}
            ]
        }
    }
}


def get_recommendations(region: Optional[str], days: int, language: str = "en") -> Dict[str, Any]:
    """Return hotel and transport tips for multi-day trips (days >= 2)."""
    if days < 2 or not region:
        return {"hotels": [], "transport": []}

    reg_key = "Cairo" if region in ("Cairo", "Giza", "Greater Cairo") else region
    data = RECOMMENDATIONS.get(reg_key)
    if not data:
        return {"hotels": [], "transport": []}

    lang = "ar" if language == "ar" else "en"
    return {
        "hotels": data["hotels"].get(lang, data["hotels"]["en"]),
        "transport": data["transport"].get(lang, data["transport"]["en"])
    }


def suggest_destinations_for_duration(days: Optional[int], language: str = "en") -> str:
    """Suggest top Egyptian destinations that fit the given time span."""
    ar = language == "ar"
    if days is None:
        if ar:
            return "القاهرة (الأهرامات والتراث)، الإسكندرية (شاطئ المتوسط)، الأقصر (المعابد ووادي الملوك)، أسوان (النيل والقرى النوبية)، أو جنوب سيناء (شرم الشيخ)."
        return "Cairo (Pyramids & Heritage), Alexandria (Mediterranean coast), Luxor (Valley of the Kings & Temples), Aswan (Nile & Nubian villages), or South Sinai (Sharm El Sheikh)."
    
    if days <= 2:
        if ar:
            return "لرحلة قصيرة (يوم أو يومين)، الخيار المثالي هو القاهرة (الأهرامات، المتحف المصري وخان الخليلي) أو الإسكندرية (كورنيش البحر المتوسط، قلعة قايتباي ومكتبة الإسكندرية)."
        return "For a 1-2 day trip, the best destinations are Cairo (Pyramids, NMEC, Egyptian Museum) or Alexandria (Mediterranean Corniche, Qaitbay Citadel & Library)."
    
    if days <= 4:
        if ar:
            return f"لرحلة مدتها {days} أيام، ننصح بزيارة الأقصر (معابد الكرنك والأقصر ومقابر وادي الملوك)، أو أسوان (معبد فيلة والسد العالي والقرية النوبية)، أو منتجعات جنوب سيناء (شرم الشيخ ومحمية رأس محمد)."
        return f"For a {days}-day trip, top destinations with rich itineraries are Luxor (Karnak, Luxor Temple & Valley of the Kings), Aswan (Philae Temple & Nubian Island), or South Sinai (Sharm El Sheikh & Ras Mohamed)."
    
    if ar:
        return f"لرحلة ممتدة ({days} أيام)، نوصي ببرنامج كلاسيكي يجمع بين القاهرة والأقصر، أو قضاء عطلة شاطئية وبحرية متكاملة في البحر الأحمر (الغردقة والجونة)."
    return f"For an extended trip of {days} days, we recommend a grand tour combining Cairo & Luxor, or a coastal resort holiday along the Red Sea (Hurghada & El Gouna)."


def format_clarification_message(
    missing: List[str],
    days: Optional[int] = None,
    budget: Optional[str] = None,
    travelers: Optional[Any] = None,
    language: str = "en",
    all_regions: str = ""
) -> str:
    """Build a natural, welcoming clarification prompt covering days, destination, budget, and travelers."""
    ar = language == "ar"
    parts: List[str] = []

    # 1. Days / Time
    if "days" in missing or days is None:
        parts.append("كم يومًا لديك لهذه الرحلة؟" if ar else "How many days do you have for the trip?")

    # 2. Destination / Region
    if "region" in missing:
        if days:
            suggestion = suggest_destinations_for_duration(days, language)
            if ar:
                parts.append(f"ما المدينة أو المنطقة التي تريد زيارتها؟ {suggestion} (المتاح: {all_regions}).")
            else:
                parts.append(f"Which city or area would you like to visit? {suggestion} (Available destinations: {all_regions}).")
        else:
            if ar:
                parts.append(f"ما المدينة أو المنطقة التي تريد زيارتها؟ المتاح: {all_regions}.")
            else:
                parts.append(f"Which city or area would you like to visit? Available: {all_regions}.")

    # 3. Budget
    if not budget:
        if ar:
            parts.append("ما مستوى الميزانية المفضل لديك؟ (اقتصادي، متوسط، أو فاخر).")
        else:
            parts.append("What is your preferred budget? (Economy, Moderate, or Luxury).")

    # 4. Travelers
    if not travelers:
        if ar:
            parts.append("كم عدد المسافرين معك؟ (مفرد، زوجان، عائلة، أو مجموعة).")
        else:
            parts.append("How many people are travelling? (Solo, Couple, Family, or Group).")

    return " ".join(parts)
