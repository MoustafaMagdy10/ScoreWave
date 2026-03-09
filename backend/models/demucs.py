from demucs.pretrained import get_model
from shared.logger import logger


class Demucs:

    def __init__(self, model_name: str = "htdemucs"):
        self.model_name = model_name
        self.model      = None
        self._load_model()


    def _load_model(self) -> None:

        logger.info(f"Loading Demucs model: {self.model_name}...")
        try:
            self.model = get_model(self.model_name)
            self.model.eval()
            logger.info(f"Demucs model '{self.model_name}' loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Demucs model '{self.model_name}': {e}")
            raise


    def health_check(self) -> bool:
        if self.model is None:
            return False
        try:
            # A model with no parameters was never properly loaded
            return sum(1 for _ in self.model.parameters()) > 0
        except Exception:
            return False