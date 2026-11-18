"""Built-in labelled samples for extraction accuracy demo."""

from datetime import date, timedelta

TODAY = date.today()
TOMORROW = (TODAY + timedelta(days=1)).isoformat()
DAY_AFTER = (TODAY + timedelta(days=2)).isoformat()

EVAL_SAMPLES = [
    {
        "text": "Kal 3 mason chahiye, Chengalpattu mein, 800 per day",
        "expected": {"skill": "mason", "count": 3, "location": "Chengalpattu", "wage_per_day": 800},
    },
    {
        "text": "Need 2 painters tomorrow in Chennai, 900 per day",
        "expected": {"skill": "painter", "count": 2, "location": "Chennai", "wage_per_day": 900},
    },
    {
        "text": "Pipe wala 1 venum Tambaram la, 750 / day, naalai",
        "expected": {"skill": "plumber", "count": 1, "location": "Tambaram", "wage_per_day": 750},
    },
    {
        "text": "Electrician 2 chahiye Guindy mein kal 1000 rupaye",
        "expected": {"skill": "electrician", "count": 2, "location": "Guindy", "wage_per_day": 1000},
    },
    {
        "text": "4 helper / mazdoor needed Porur tomorrow Rs 600",
        "expected": {"skill": "helper", "count": 4, "location": "Porur", "wage_per_day": 600},
    },
    {
        "text": "Carpenter 1 wanted OMR, 1100 per day, day after tomorrow",
        "expected": {"skill": "carpenter", "count": 1, "location": "Omr", "wage_per_day": 1100},
    },
    {
        "text": "Raj mistri 5 log Chengalpattu, kal, 850 din",
        "expected": {"skill": "mason", "count": 5, "location": "Chengalpattu", "wage_per_day": 850},
    },
    {
        "text": "Colour wala 2 Chennai ECR, tomorrow, 950",
        "expected": {"skill": "painter", "count": 2, "location": "Chennai", "wage_per_day": 950},
    },
    {
        "text": "Wireman one needed Velachery aaj 1200",
        "expected": {"skill": "electrician", "count": 1, "location": "Velachery", "wage_per_day": 1200},
    },
    {
        "text": "Mestri 3 venum Chengalpattu, 800, kal",
        "expected": {"skill": "mason", "count": 3, "location": "Chengalpattu", "wage_per_day": 800},
    },
    {
        "text": "Plumber 2 chahiye Tambaram mein parso 700",
        "expected": {"skill": "plumber", "count": 2, "location": "Tambaram", "wage_per_day": 700},
    },
    {
        "text": "Need helper 6 people Chennai Guindy tomorrow 550 per day",
        "expected": {"skill": "helper", "count": 6, "location": "Chennai", "wage_per_day": 550},
    },
    {
        "text": "Wood wala carpenter 2 Porur kal 1000",
        "expected": {"skill": "carpenter", "count": 2, "location": "Porur", "wage_per_day": 1000},
    },
    {
        "text": "Painter 1 needed Chengalpattu, 850/day tomorrow",
        "expected": {"skill": "painter", "count": 1, "location": "Chengalpattu", "wage_per_day": 850},
    },
    {
        "text": "2 electrician OMR mein kal 1100 per day",
        "expected": {"skill": "electrician", "count": 2, "location": "Omr", "wage_per_day": 1100},
    },
    {
        "text": "Mason chahiye 4, Chennai, Rs 900, kal",
        "expected": {"skill": "mason", "count": 4, "location": "Chennai", "wage_per_day": 900},
    },
    {
        "text": "Naalai 3 helper Velachery, 650 rupees",
        "expected": {"skill": "helper", "count": 3, "location": "Velachery", "wage_per_day": 650},
    },
    {
        "text": "Plumber one Guindy tomorrow 800 per day",
        "expected": {"skill": "plumber", "count": 1, "location": "Guindy", "wage_per_day": 800},
    },
    {
        "text": "Raj mistri aur helper nahi — sirf 2 carpenter Tambaram 950 kal",
        "expected": {"skill": "carpenter", "count": 2, "location": "Tambaram", "wage_per_day": 950},
    },
    {
        "text": "Need 3 mestri Chengalpattu tomorrow wage 820",
        "expected": {"skill": "mason", "count": 3, "location": "Chengalpattu", "wage_per_day": 820},
    },
]


def field_matches(field: str, predicted, expected) -> bool:
    if predicted is None:
        return False
    if field == "location":
        return str(expected).lower() in str(predicted).lower() or str(predicted).lower() in str(expected).lower()
    if field == "skill":
        return str(predicted).lower() == str(expected).lower()
    return predicted == expected
