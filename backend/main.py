from fastapi import FastAPI
from shared.logger import logger
from models.demucs import Demucs
from routes.demucs_router import router as demucs_router
from routes.crepe_router import router as crepe_router
from routes.basic_pitch_router import router as basic_pitch_router
from routes.pipeline_router import router as pipeline_router
from rich.traceback import install


app = FastAPI()
install(show_locals=True)
logger.info("Starting the Songify API...")

app.include_router(demucs_router, prefix="/api")
app.include_router(crepe_router, prefix="/api")
app.include_router(basic_pitch_router, prefix="/api")
app.include_router(pipeline_router, prefix="/api")
@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/model")
def get_model():
    model = Demucs()
    return {"model": model.health_check()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)