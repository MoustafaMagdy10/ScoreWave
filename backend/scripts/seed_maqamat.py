"""
Seed script: populates the maqamat table with the canonical maqam knowledge base.

Run from the backend/ directory:
    python -m scripts.seed_maqamat

The script is idempotent — it skips maqamat that already exist (matched by
name_latin). Safe to run multiple times.
"""

import asyncio
import sys
from pathlib import Path

# Allow running as a module from backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import async_session_maker, engine, Base  # noqa: E402
from models.maqam import Maqam  # noqa: E402 — registers the table
from shared.logger import logger  # noqa: E402

# ── Canonical maqam data ──────────────────────────────────────────────────────
# scale_cents: cent offsets from tonic within one octave.
# Quarter tones land on multiples of 50 cents (e.g. 150¢ = E-half-flat above D).

MAQAM_DATA = [
    {
        "name_arabic": "بياتي",
        "name_latin": "Bayati",
        "root_note": "D",
        # D  E½♭  F   G   A  B♭   C   D
        "scale_cents": [0, 150, 300, 500, 700, 850, 1050, 1200],
        "mood_arabic": "شوق وحنين وعاطفة",
        "mood_english": "Longing, emotional, melancholic — one of the most expressive maqamat",
        "famous_songs": ["Enta Omri (أنت عمري)", "Longa Riyad", "Ya Msaharni"],
        "jins_structure": "Jins Bayati (D) + Jins Nahawand (G)",
        "has_quarter_tones": True,
        "confidence_threshold": 0.55,
    },
    {
        "name_arabic": "راست",
        "name_latin": "Rast",
        "root_note": "C",
        # C   D   E½♭  F   G   A  B½♭  C
        "scale_cents": [0, 200, 350, 500, 700, 900, 1050, 1200],
        "mood_arabic": "توازن ودفء ونبل",
        "mood_english": "Balanced, warm, noble — often used for anthems and uplifting music",
        "famous_songs": ["Fog El-Nakhal (فوق النخل)", "Ana Wahashtak"],
        "jins_structure": "Jins Rast (C) + Jins Rast (G)",
        "has_quarter_tones": True,
        "confidence_threshold": 0.55,
    },
    {
        "name_arabic": "حجاز",
        "name_latin": "Hijaz",
        "root_note": "D",
        # D   E♭  F#  G   A  B♭  C#  D
        "scale_cents": [0, 100, 400, 500, 700, 800, 1100, 1200],
        "mood_arabic": "غموض وروحانية وغرابة",
        "mood_english": "Mysterious, exotic, spiritual — evokes desert landscapes",
        "famous_songs": ["Lamma Bada Yatathanna (لما بدا يتثنى)", "El Helwa Di"],
        "jins_structure": "Jins Hijaz (D)",
        "has_quarter_tones": False,
        "confidence_threshold": 0.60,
    },
    {
        "name_arabic": "كرد",
        "name_latin": "Kurd",
        "root_note": "D",
        # D   E♭  F   G   A  B♭   C   D
        "scale_cents": [0, 100, 300, 500, 700, 800, 1000, 1200],
        "mood_arabic": "حميمية وتأمل",
        "mood_english": "Intimate, introspective, contemplative",
        "famous_songs": ["Nassam Alayna El-Hawa (نسم علينا الهوا)", "Ala Dal'ouna"],
        "jins_structure": "Jins Kurd (D)",
        "has_quarter_tones": False,
        "confidence_threshold": 0.55,
    },
    {
        "name_arabic": "صبا",
        "name_latin": "Saba",
        "root_note": "D",
        # D   E½♭  F  G♭  A  B♭   C   D
        "scale_cents": [0, 150, 300, 400, 700, 800, 1000, 1200],
        "mood_arabic": "حزن وبكاء وألم",
        "mood_english": "Sorrow, weeping, grief — the most mournful maqam",
        "famous_songs": ["El Atlal (الأطلال)", "Rajaa El Nour"],
        "jins_structure": "Jins Saba (D)",
        "has_quarter_tones": True,
        "confidence_threshold": 0.58,
    },
    {
        "name_arabic": "نهاوند",
        "name_latin": "Nahawand",
        "root_note": "C",
        # C   D   E♭  F   G  A♭   B   C
        "scale_cents": [0, 200, 300, 500, 700, 800, 1100, 1200],
        "mood_arabic": "رومانسية وشوق وعاطفة",
        "mood_english": "Romantic, longing, passionate — closely related to harmonic minor",
        "famous_songs": ["Ghannili Shwayya (غنيلي شويه)", "Qaddak El Mayyas"],
        "jins_structure": "Jins Nahawand (C)",
        "has_quarter_tones": False,
        "confidence_threshold": 0.55,
    },
    {
        "name_arabic": "سيكاه",
        "name_latin": "Sikah",
        "root_note": "E½♭",
        # E½♭  F#  A  B♭  C#  D  E½♭
        "scale_cents": [0, 150, 350, 500, 700, 850, 1050, 1200],
        "mood_arabic": "فرح ومرح وبهجة",
        "mood_english": "Joyful, celebratory, festive — common in Sufi and folk music",
        "famous_songs": ["Zay El Hawa (زي الهوا)", "Leil El Samar"],
        "jins_structure": "Jins Sikah (E½♭) + Jins Rast (A)",
        "has_quarter_tones": True,
        "confidence_threshold": 0.60,
    },
    {
        "name_arabic": "عجم",
        "name_latin": "Ajam",
        "root_note": "B♭",
        # B♭  C   D  E♭  F   G   A  B♭  (major scale from B♭)
        "scale_cents": [0, 200, 400, 500, 700, 900, 1100, 1200],
        "mood_arabic": "قوة وإيجابية وانتصار",
        "mood_english": "Strong, positive, triumphant — essentially a major scale",
        "famous_songs": ["Oum Kalthoum Qasaid", "Wenta Habibi"],
        "jins_structure": "Jins Ajam (B♭)",
        "has_quarter_tones": False,
        "confidence_threshold": 0.50,
    },
]


# ── Runner ────────────────────────────────────────────────────────────────────


async def seed() -> None:
    """Insert all maqamat, skipping duplicates."""
    # Ensure table exists
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        inserted = 0
        skipped = 0

        for data in MAQAM_DATA:
            # Check for existing record by latin name (idempotent)
            from sqlalchemy import select

            result = await session.execute(
                select(Maqam).where(Maqam.name_latin == data["name_latin"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                logger.info(f"  Skipping {data['name_latin']} (already exists)")
                skipped += 1
                continue

            maqam = Maqam(**data)
            session.add(maqam)
            inserted += 1
            logger.info(f"  Inserting {data['name_latin']} ({data['name_arabic']})")

        await session.commit()
        logger.info(f"Seed complete: {inserted} inserted, {skipped} skipped")


if __name__ == "__main__":
    logger.info("=== Seeding maqamat knowledge base ===")
    asyncio.run(seed())
    logger.info("Done.")
