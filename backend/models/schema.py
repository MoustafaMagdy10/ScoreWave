from pydantic import BaseModel


class StemPaths(BaseModel):
    vocals:    str
    no_vocals: str   # bass + drums + other mixed — fed into CREPE next step
    drums:     str
    bass:      str
    other:     str


class SeparationResponse(BaseModel):
    stems: StemPaths
