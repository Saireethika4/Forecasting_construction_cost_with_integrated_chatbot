"""What the chatbot may talk about, and built-in answers that need no AI service."""
import re

REFUSAL = ("I can only help with this construction cost project: estimates, site rates, nearby labour, "
           "the data and model behind them, and general construction questions. "
           "Please ask me something along those lines.")

# Requests that are off-topic even when they mention a construction word, or that try to change the bot's rules
BLOCKED = re.compile(
    r"\b(?:poem|jokes?|songs?|essays?|recipes?|movies?|films?|cricket|football|homework|bitcoin|crypto\w*|stock market"
    r"|iphone|laptops?|smartphones?|dating|horoscope|road trip|holidays?|vacations?|flights?|hotel rooms?|card games?|bridge game|london bridge"
    r"|python|javascript|html|programming|translate|prime minister|president|capital of|tell me a story"
    r"|ignore (?:\w+ ){0,3}(?:instructions?|rules?|prompt)|system prompt|pretend (?:to be|you are)|jailbreak"
    r"|act as (?:a|an) (?!contractor|engineer|estimator))\b"
    r"|(?<!building )\bcode\b"
)

CONSTRUCTION_WORDS = re.compile(
    r"\b(?:construct\w*|build\w*|bridges?|flyovers?|roads?|highways?|tunnels?|retaining walls?|embankment|foundations?|footings?"
    r"|plinth|concrete|cement|steel|rebar|tmt|bricks?|aac|sand|aggregate|mortar|plaster\w*|masonry|roofs?|slabs?|columns?|beams?"
    r"|waterproof\w*|plumb\w*|wiring|electrician|tiles?|tiling|paint\w*|contractors?|masons?|carpenters?|welders?|bar benders?"
    r"|labou?r\w*|workers?|helpers?|scaffold\w*|excavation|curing|blueprint|floor plan|civil engineer\w*|site work|renovat\w*"
    r"|multi-?stor\w*|rera|building code)\b"
)
PROJECT_WORDS = re.compile(
    r"\b(?:dataset|(?:what|which|your) data|data (?:do|does|did) you|ml model|machine learning|xgboost|random forest|r2|r²|accuracy|accurate|train(?:ing)?|predictions?|chatbot|this (?:project|app|site|website|bot)"
    r"|costforge|admin|register\w*|sign ?up|log ?in|password|account|sample (?:records?|listings?)|site factor|openstreetmap"
    r"|cities|material quality|quality levels?|average cost|cost range|price range|factors?\b.*\bcosts?|costs?\b.*\bfactors?"
    r"|who are you|what are you|your name|what can you)\b"
)
MONEY_WORDS = re.compile(r"\b(?:compare|costs?|costing|price[sd]?|pricing|rates?|estimates?|budgets?|expensive|cheap\w*|predict\w*|statistics|stats|how much)\b")
SUBJECT_WORDS = re.compile(
    r"\b(?:city|mumbai|delhi|bangalore|bengaluru|chennai|hyderabad|residential|commercial|apartments?|flats?|houses?|villas?|homes?|offices?"
    r"|malls?|shops?|hotels?|hospitals?|schools?|colleges?|factory|factories|warehouses?|hills?|hilly|mountains?|hill stations?|water bod(?:y|ies)"
    r"|rivers?|lakes?|coast\w*|marine|desert|forest|remote|urban|plains?|sq\.?\s*ft|sqft|sq\.?\s*m|sqm)\b"
)


def is_blocked(message):
    return BLOCKED.search(message) is not None


def is_on_topic(message):
    if CONSTRUCTION_WORDS.search(message) or PROJECT_WORDS.search(message):
        return True
    return bool(MONEY_WORDS.search(message) and SUBJECT_WORDS.search(message))


# First match wins, so specific questions come before broad ones
ANSWERS = [
    (r"who are you|what are you|your name|what (?:is|does) this (?:project|app|site|website)|about this (?:project|app|site|website)",
     "I'm the CostForge assistant. This project estimates construction costs in India, compares rates by site, and helps you find nearby labour. I only answer questions about the project and construction."),
    (r"(?:reset|forgot|change|lost).*password|password.*(?:reset|forgot|change)",
     "There's no self-service password reset yet, so please contact the site admin about your account."),
    (r"(?:how|where).*(?:register|sign ?up|create.*account)|(?:register|sign ?up).*how",
     "Choose **Register** at the top of the site and fill in the form. An admin then activates your account, and you can log in."),
    (r"(?:can't|cannot|can not|unable|how|not able).*log ?in|pending.*approval|account.*(?:waiting|pending|deactivated)",
     "Log in with your email and password from **User Login**. New accounts can't log in until an admin activates them, so if yours says pending, please wait for approval."),
    (r"(?:how|where|can i|want to).*(?:list|add|register).*(?:labou?r|worker|myself|contractor|mason)|list as labou?r",
     "Workers and contractors can use **List as Labour** at the top of the public site. It needs consent to show contact details, and the listing appears after admin approval."),
    (r"sample (?:records?|listings?)|(?:real|fake|genuine).*(?:workers?|contacts?|listings?|numbers?)|(?:workers?|contacts?|listings?|numbers?).*(?:real|fake|genuine)",
     "Listings marked **Sample** are placeholders that demonstrate the search, so please don't contact them. Other listings come from workers or the admin. OpenStreetMap results are public listings that aren't verified."),
    (r"(?:how|where).*(?:find|search|hire|get).*(?:labou?r|workers?|masons?|contractors?)|how.*labou?r search",
     "Open **Find Labour**, type a place or use your current location, then choose a trade and distance. Results are sorted by distance and show contact details. You can also ask me, for example, \"masons near Hyderabad\"."),
    (r"how.*(?:accurate|reliable)|accuracy|can i trust|r2|r²",
     "On held-out projects in the dataset, the model's error is about 0.4%. That is flattering, because the dataset follows a fixed pattern by city and quality, so expect larger errors on real projects. Type factors and site rates are indicative assumptions, so confirm figures with quotes."),
    (r"(?:what|which).*(?:data|dataset)|(?:data|dataset).*(?:come|from|use|contain|have)|how many projects",
     "The model uses 5,000 residential and commercial building projects in Bangalore, Chennai, Delhi, Hyderabad and Mumbai. You can browse them on the **Dataset** page. It has no bridges, roads or tunnels, so those use the rate table."),
    (r"(?:what|which).*(?:model|algorithm)|random forest|xgboost|machine learning|how.*(?:predict|train|model) .*work|how does .*(?:prediction|model)",
     "The **Training** page trains Random Forest, plus XGBoost where installed, and keeps the more accurate one. It learns material and labour cost per sq.ft from area, floors, city, quality and building type. Bridges, roads, tunnels and walls use the rate table instead."),
    (r"(?:how|when|why).*train|retrain",
     "Open **Training** and choose **Train Models Now**. It takes a few seconds and updates the model used for predictions. You don't need to retrain unless you want fresh charts or the data changes."),
    (r"site factor|type (?:and|&) site factor|what.*multiplier",
     "The type and site factor scales the model's estimate for what you're building and where. For example, an apartment on plain ground is ×1.10. It comes from the rate table, is an indicative assumption, and can be edited by the admin."),
    (r"how.*(?:use|make|get).*(?:estimate|prediction)|how.*(?:estimate|calculate) .*(?:work|calculated)|how (?:do|can) i (?:estimate|predict)",
     "Open **Prediction**, choose what you're building, enter its size and site, and calculate. Buildings also ask for floors and city. You can also say **start prediction** here and I'll guide you."),
    (r"\bcuring\b|\bcure\b",
     "Keep concrete continuously moist after it sets. IS 456 calls for at least 7 days with ordinary Portland cement and at least 10 days with mineral admixtures or in hot, dry weather. Longer curing improves strength and durability."),
    (r"\bm\s?-?\s?(?:15|20|25|30)\b|concrete grade|grade of concrete",
     "The number in a concrete grade is its characteristic strength in N/mm² at 28 days, so M20 means 20 N/mm². IS 456 sets M20 as the minimum for reinforced concrete. Your structural engineer should choose the grade for your design and exposure."),
    (r"(?:which|what|best|good).*(?:\btmt\b|rebar|steel)|fe\s?\d{3}",
     "TMT bars are commonly used as reinforcement, and the number in a grade such as Fe 500 is the yield strength in N/mm². The grade, bar sizes and spacing should come from your structural drawings."),
    (r"(?:aac|\bbricks?\b).*(?:vs|versus|or|better|compare)|(?:vs|versus|better|compare).*(?:aac|\bbricks?\b)|(?:which|what).*(?:bricks?|blocks?)",
     "AAC blocks are lighter, insulate better and lay faster, while clay bricks are widely available and handle moisture and impact well. The better choice depends on local prices, load and climate, so compare the delivered cost per sq.ft of wall."),
    (r"(?:which|what|type|types|best|kind).*(?:foundation|footing)|(?:foundation|footing).*(?:type|which|need)",
     "Common types are isolated footings, raft foundations and piles. The right one depends on soil, loads and water level, so get a soil test and a structural engineer's design first. Hill and water sites often need more complex foundations, which is one reason they cost more."),
    (r"waterproof",
     "Prioritise roofs, bathrooms, basements and external joints, which are the usual leak points. Good detailing, well-compacted concrete and a suitable membrane or coating work together, and fixing leaks later usually costs more than doing it during construction."),
    (r"monsoon|rain|weather|season",
     "Rain slows excavation, concreting and finishing. Plan foundations for dry months, protect stored cement and steel, keep the site drained, and allow extra time in the schedule. Hill and coastal sites usually lose more working days."),
    (r"(?:reduce|save|lower|cut|minimi[sz]e|optimi[sz]e).*(?:cost|budget|money|expens)|(?:cost|budget).*(?:saving|reduc|tips)|(?:cheaper|less expensive) (?:way|to build)",
     "The biggest savings come early: a simple layout, repeated floor plans, firm drawings before work starts, and several quotes for materials and labour. Avoid mid-project design changes and buy major materials in bulk. Don't cut structural quality, since repairs cost far more."),
    (r"(?:how long|time|duration).*(?:build|construct|take)",
     "Duration depends on size, design, site and funding, so ask your contractor for a schedule. Hill, water and remote sites usually take longer because of access and shorter working seasons."),
    (r"permit|permission|approval.*(?:build|construct)|\brera\b|building (?:code|plan approval)",
     "Rules vary by state and local authority. Check building plan approval, land use and any environmental clearances with your local authority and a licensed professional. This project doesn't cover legal approvals."),
]
ANSWERS = [(re.compile(pattern), answer) for pattern, answer in ANSWERS]


def find_answer(message):
    for pattern, answer in ANSWERS:
        if pattern.search(message):
            return answer
    return None
