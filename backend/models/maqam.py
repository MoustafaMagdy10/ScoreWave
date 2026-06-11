"""
SQLAlchemy model for the Maqam knowledge base.

Each row represents a single maqam (Arabic/Turkish/Persian modal scale)
with its full cultural, musical, and technical metadata.
"""

from sqlalchemy import Boolean, Column, Float, Integer, JSON, String, Text

from core.database import Base


class Maqam(Base):
    """Maqam knowledge-base entry."""

    __tablename__ = "maqamat"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ── Names ─────────────────────────────────────────────────────────────────
    name_arabic = Column(String(64), nullable=False, unique=True)
    name_latin = Column(String(64), nullable=False, unique=True)  # e.g. "Bayati"

    # ── Root / tonic ──────────────────────────────────────────────────────────
    root_note = Column(String(8), nullable=False)  # e.g. "D", "E½"

    # ── Scale definition ──────────────────────────────────────────────────────
    # Stored as JSON list of floats: cents offsets from tonic within one octave
    # Compatible with 24-TET: quarter tones land on multiples of 50 cents.
    # Example: [0, 150, 300, 500, 700, 850, 1050, 1200]
    scale_cents = Column(JSON, nullable=False)

    # ── Cultural metadata ─────────────────────────────────────────────────────
    mood_arabic = Column(Text, nullable=True)
    mood_english = Column(Text, nullable=True)

    # JSON list of well-known songs in this maqam.  E.g. ["Enta Omri", "Longa Riyad"]
    famous_songs = Column(JSON, nullable=True)

    # Description of the jins (tetrachord) structure.
    # E.g. "Jins Bayati + Jins Nahawand"
    jins_structure = Column(String(128), nullable=True)

    # ── Technical flags ───────────────────────────────────────────────────────
    has_quarter_tones = Column(Boolean, nullable=False, default=False)

    # Minimum confidence from the detector to accept this maqam as a match.
    confidence_threshold = Column(Float, nullable=False, default=0.55)

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict of this maqam."""
        return {
            "id": self.id,
            "name_arabic": self.name_arabic,
            "name_latin": self.name_latin,
            "root_note": self.root_note,
            "scale_cents": self.scale_cents,
            "mood_english": self.mood_english,
            "mood_arabic": self.mood_arabic,
            "famous_songs": self.famous_songs or [],
            "jins_structure": self.jins_structure,
            "has_quarter_tones": self.has_quarter_tones,
            "confidence_threshold": self.confidence_threshold,
        }

    def __repr__(self) -> str:
        return f"<Maqam(name_latin={self.name_latin!r}, root={self.root_note!r})>"
