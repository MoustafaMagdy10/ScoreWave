from fastapi import FastAPI
from shared.logger import logger
from models.demucs import Demucs
from routes.demucs_routes import router as demucs_router
from rich.traceback import install


app = FastAPI()
install(show_locals=True)
logger.info("Starting the Songify API...")

app.include_router(demucs_router, prefix="/api")
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