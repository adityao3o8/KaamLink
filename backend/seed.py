"""Seed workers + 200 historical jobs for KaamLink demo."""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from app.database import SessionLocal, init_db
from app.models import HistoricalJob, Worker
from app.services.embeddings import dumps_embedding, embed_text

AREAS = ["Chengalpattu", "Chennai", "Tambaram", "Guindy", "Porur", "OMR", "ECR", "Velachery"]
SKILLS = ["mason", "painter", "plumber", "electrician", "helper", "carpenter"]
LANG_OPTIONS = ["Hindi", "Tamil", "English", "Tamil,Hindi", "Hindi,English", "Tamil,English"]

FIRST = [
    "Ravi", "Suresh", "Murugan", "Anbu", "Karthik", "Imran", "Vijay", "Prakash",
    "Selvam", "Dinesh", "Arun", "Bala", "Ganesh", "Hari", "Jegan", "Kumar",
    "Lokesh", "Mani", "Naveen", "Palani",
]
LAST = [
    "Kumar", "Raj", "Singh", "Das", "Nadar", "Pillai", "Yadav", "Sharma",
    "Reddy", "Iyer", "Khan", "Mishra", "Patel", "Verma", "Nair",
]

SLANG = {
    "mason": ["raj mistri", "mestri", "brick mestri"],
    "painter": ["colour wala", "paint mestri", "wall colour expert"],
    "plumber": ["pipe wala", "plumbing mestri", "tap-pipe expert"],
    "electrician": ["wireman", "current wala", "electrical mestri"],
    "helper": ["mazdoor", "site helper", "loading helper"],
    "carpenter": ["wood wala", "furniture mistri", "door-window carpenter"],
}

BASE_WAGE = {
    "mason": 800,
    "painter": 750,
    "plumber": 850,
    "electrician": 950,
    "helper": 600,
    "carpenter": 900,
}


def availability_for(days: int = 14) -> list[str]:
    today = date.today()
    must = {0, 1, 2}
    skip = set(random.sample(range(3, days), k=min(3, days - 3)))
    return [
        (today + timedelta(days=i)).isoformat()
        for i in range(days)
        if i in must or i not in skip
    ]


def make_profile(name: str, skill: str, years: int, area: str, wage: int, slang: str) -> str:
    return (
        f"{name} is a {skill} ({slang}) with {years} years experience around {area}. "
        f"Expected wage about {wage} per day. Speaks site Hindi/Tamil mix."
    )


def seed_historical(db, n: int = 200) -> int:
    db.query(HistoricalJob).delete()
    random.seed(7)
    rows = []
    today = date.today()
    for i in range(n):
        skill = SKILLS[i % len(SKILLS)]
        area = AREAS[i % len(AREAS)]
        base = BASE_WAGE[skill]
        wage = base + random.randint(-120, 180)
        rows.append(
            HistoricalJob(
                skill=skill,
                area=area,
                wage=max(400, wage),
                date=(today - timedelta(days=random.randint(1, 180))).isoformat(),
            )
        )
    db.add_all(rows)
    print(f"Seeded {len(rows)} historical jobs.")
    return len(rows)


def seed(reset: bool = True):
    init_db()
    db = SessionLocal()
    try:
        if reset:
            db.query(Worker).delete()
            db.commit()

        existing = db.query(Worker).count()
        if existing >= 40 and not reset:
            print(f"Already have {existing} workers, skip workers.")
        else:
            random.seed(42)
            workers = []
            for i in range(40):
                skill = SKILLS[i % len(SKILLS)]
                name = f"{FIRST[i % len(FIRST)]} {LAST[i % len(LAST)]}"
                if i >= 20:
                    name = f"{FIRST[(i * 3) % len(FIRST)]} {LAST[(i * 5) % len(LAST)]}"
                area = AREAS[i % len(AREAS)]
                years = random.randint(1, 18)
                wage = random.choice([550, 600, 650, 700, 750, 800, 850, 900, 950, 1000, 1100])
                reliability = round(random.uniform(3.0, 5.0), 2)
                languages = LANG_OPTIONS[i % len(LANG_OPTIONS)]
                slang = random.choice(SLANG[skill])
                phone = f"9{random.randint(100000000, 999999999)}"
                profile = make_profile(name, skill, years, area, wage, slang)
                emb = embed_text(profile)
                workers.append(
                    Worker(
                        name=name,
                        phone=phone,
                        skill=skill,
                        experience_years=years,
                        area=area,
                        languages=languages,
                        expected_wage=wage,
                        availability=json.dumps(availability_for()),
                        reliability=reliability,
                        profile_text=profile,
                        embedding=dumps_embedding(emb),
                    )
                )
            db.add_all(workers)
            db.commit()
            print(f"Seeded {len(workers)} workers.")
            for skill in SKILLS:
                c = db.query(Worker).filter(Worker.skill == skill).count()
                print(f"  {skill}: {c}")

        seed_historical(db, n=200)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed(reset=True)
