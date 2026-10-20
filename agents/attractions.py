"""Attraction facts for the travel agent.
trustworthy FACTS about a place (hours text, prices, visit duration, source) by looking it up by id
"""
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any, Dict, Optional
import json

from rag.config import RAW_DATA_PATH 


@dataclass(frozen=True)
class Attraction:
    id: int
    name: str
    city: str
    region: str
    category: str
    description: str
    opening_hours_text: str  
    price_egyptian_egp: float
    price_foreigner_egp: float
    duration_min: int
    source_url: str
    last_verified: str


@lru_cache(maxsize=1)
def load_attractions() -> Dict[int, Attraction]:
    """Read raw_attractions.json once and return {id: Attraction}."""
    with open(RAW_DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    attractions: Dict[int, Attraction] = {}
    for item in raw:
        attraction = Attraction(
            id=int(item["id"]),
            name=item["name"],
            city=item["city"],
            region=item["region"],
            category=item["category"],
            description=item["description"],
            opening_hours_text=item["opening_hours"],
            price_egyptian_egp=float(item["ticket_price_egyptian_adult_egp"]),
            price_foreigner_egp=float(item["ticket_price_foreigner_adult_egp"]),
            duration_min=int(item["estimated_visit_duration_min"]),
            source_url=item["source_url"],
            last_verified=item["last_verified"],
        )
        attractions[attraction.id] = attraction
    return attractions


def get_attraction(attraction_id: int) -> Optional[Attraction]:
    """Internal helper for our own Python code. Returns None if the id is unknown."""
    return load_attractions().get(attraction_id)


def get_attraction_details(attraction_id: Any) -> Dict[str, Any]:
    """Tool contract (what the LLM will call).

    Always returns a dict with an "ok" flag, so the agent never has to guess
    whether a call worked:
        {"ok": True,  "attraction": {...all fields...}}
        {"ok": False, "error": "human-readable reason"}
    """
    try:
        wanted_id = int(attraction_id)  
    except (TypeError, ValueError):
        return {"ok": False, "error": f"Invalid attraction id: {attraction_id!r}"}

    attraction = get_attraction(wanted_id)
    if attraction is None:
        return {"ok": False, "error": f"No attraction with id {wanted_id}"}
    return {"ok": True, "attraction": asdict(attraction)}


ARABIC_DESCRIPTIONS: Dict[int, str] = {
    1: "متحف رئيسي في ميدان التحرير بالقاهرة يضم مجموعات أثرية كبرى تشمل تماثيل ملكية وبرديات وتوابيت وحلي وقطعاً فريدة من تاريخ مصر القديمة.",
    2: "متحف وطني يقدم الحضارة المصرية عبر العصور ويضم مجموعات بارزة من بينها قاعة المومياوات الملكية الشهيرة في الفسطاط.",
    3: "متحف للتراث القبطي في مجمع الأديان يضم مخطوطات وأيقونات وأعمالاً خشبية منحوتة وجداريات جرى حفظها من الأديرة والكنائس القديمة.",
    4: "متحف في باب الخلق يضم إحدى أكبر مجموعات الآثار والفنون الإسلامية في العالم من خزف ومخطوطات ومعادن وأعمال خشبية نادرة.",
    5: "مجمع أهرامات الجيزة ويضم هرم خوفو الأكبر، آخر عجائب العالم القديم الباقية، وأهرامات خفرع ومنقرع وتمثال أبو الهول.",
    6: "جبانة ملكية قديمة شاسعة تضم معالم من عصور مختلفة، في مقدمتها مجمع الهرم المدرج للملك زوسر ومتحف إيمحتب.",
    7: "حقل أهرامات أثري يرتبط بالملك سنفرو وتطور عمارة الأهرامات المصرية، ويشمل الهرم المنحني والهرم الأحمر.",
    8: "مجمع مدافن أثرية تحت الأرض في سقارة مخصص لمدافن العجول أبيس المقدسة وطقوس الإله بتاح.",
    9: "مجمع معابد ضخم في الأقصر يشتهر بصالة الأعمدة الكبرى المهيبة والمسلات الشاهقة والصروح والبحيرة المقدسة.",
    10: "معبد عريق على كورنيش النيل بالبر الشرقي للأقصر، أضاف إليه أمنحتب الثالث ورمسيس الثاني ويضم صرحاً وأعمدة بارزة.",
    11: "الجبانة الملكية للدولة الحديثة بالبر الغربي للأقصر، وتضم أكثر من ستين مقبرة صخرية بنقوش وألوان جدارية بديعة.",
    12: "معبد جنائزي فريد للملكة حتشبسوت بالبر الغربي يتميز بمدرجاته المعمارية الرائعة ونقوش رحلة بونت الشهيرة.",
    13: "متحف يوضح أسرار وتقنيات التحنيط في مصر القديمة من خلال الأدوات والتوابيت والمومياوات والتمائم والوسائل الشعائرية.",
    14: "منطقة أثرية بالبر الغربي تضم معابد جنائزية ملكية محفورة في صخور الجبل، وأبرزها معبد حتشبسوت.",
    15: "متحف متميز يحتفي بتاريخ النوبة وتراثها، ويضم قاعات عرض وحدائق متحفية ونقوشاً صخرية ونموذجاً لبيت نوبي تقليدي.",
    16: "مجمع معابد مكرس للإلهة إيزيس نُقل إلى جزيرة أجيليكيا لحمايته من الغرق ضمن مشروع إنقاذ آثار النوبة مع اليونسكو.",
    17: "معبدان صخريان استثنائيان بناهما رمسيس الثاني ويشتهران بالتماثيل الضخمة وتعامد الشمس وإنقاذهما التاريخي بنقلهما فوق الجبل.",
    18: "معبد يوناني روماني مزدوج فريد مكرس للإلهين سوبك وحورس، يشتهر بتصميمه المتناظر ونقوشه الجراحية والطبية النادرة.",
    19: "أحد أكثر المعابد اكتمالاً وبقاءً في مصر، كُرّس للإله حورس في العصر البطلمي ويتميز بصروحه الضخمة وأروقته السليمة.",
    20: "متحف ملحق بمعبد كوم أمبو يعرض تماسيح محنطة وتوابيت وأدوات جنائزية مرتبطة بعبادة الإله سوبك التمساح.",
    21: "قلعة حربية تاريخية من القرن الخامس عشر على ساحل البحر بالإسكندرية، شُيّدت في الموقع الأصلي لفنار الإسكندرية القديم.",
    22: "صرح ثقافي ومعرفي بارز يخلد ذكرى مكتبة الإسكندرية القديمة، ويضم متاحف متخصصة وقبة فلكية ومعارض ومكتبات كبرى.",
    23: "مقابر أثرية فريدة تحت الأرض تمزج بين الفنون المصرية واليونانية والرومانية، وتتكون من ثلاثة مستويات منحوتة في الصخر.",
    24: "محمية بحرية طبيعية في أقصى جنوب سيناء تشتهر بأندر الشعاب المرجانية، وأفضل مواقع الغوص عالمياً وغابات المانجروف.",
    25: "أحد أقدم الأديرة المأهولة في العالم عند سفح جبل موسى، ويضم العليقة المقدسة ومكتبة مخطوطات وأيقونات تاريخية نادرة.",
    26: "معلم ترفيهي وتعليمي ضخم يعرض الحياة البحرية بالبحر الأحمر عبر نفق زجاجي تحت الماء وأحواض قروش وحديقة حيوان مصغرة.",
    27: "جزيرة طبيعية ساحرة في مياه البحر الأحمر بالغردقة، تشتهر بشواطئها الرملية ومياهها الفيروزية الصافية والسنوركلنج.",
    28: "قلعة شالي التاريخية المبنية من مادة الكرشيف بقلب واحة سيوة، وتحيط بها بساتين النخيل والزيتون وبحيرات الملح.",
    29: "معبد تاريخي بقرية أغورمي في سيوة، نال شهرة عالمية بزيارة الإسكندر الأكبر عام 331 ق.م لمعرفة نبوءة كهنة الإله آمون.",
    30: "محمية طبيعية ذات مشهد صحراوي فريد بتكويناتها الصخرية الطباشيرية البيضاء وأشكال الفطر الشهيرة ومقصد للتخييم الفلكي.",
}


def arabic_description(attraction_id: int) -> Optional[str]:
    """Arabic description for curated attractions (ids 1..30)."""
    return ARABIC_DESCRIPTIONS.get(attraction_id)