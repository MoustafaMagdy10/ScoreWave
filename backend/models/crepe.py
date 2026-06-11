import torch
import torchcrepe
from shared.logger import logger


# torchcrepe only has "tiny" and "full" — map the richer capacity strings
_CAPACITY_MAP = {
    "tiny": "tiny",
    "small": "full",
    "medium": "full",
    "large": "full",
    "full": "full",
}


class Crepe:
    """
    Wrapper around the torchcrepe pitch estimation model.
    torchcrepe is a PyTorch port of the original TensorFlow CREPE — same
    accuracy, no Keras/TensorFlow dependency.

    We track readiness with a simple boolean flag set after a test prediction.

    Model capacity options (trade-off: accuracy vs speed):
        tiny | small | medium | large | full
        (small / medium / large all map to torchcrepe's "full" model)
    """

    def __init__(self, model_capacity: str = "medium"):
        self.model_capacity = model_capacity
        self._ready = False
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = _CAPACITY_MAP.get(model_capacity, "full")
        self._load_model()

    def _load_model(self) -> None:
        """
        torchcrepe downloads and caches weights on the first predict() call.
        We force that load now with a silent dummy prediction so the first
        real request doesn't pay the cold-start cost.
        """
        logger.info(
            f"Loading torchcrepe model "
            f"(capacity={self.model_capacity} → model='{self._model}', device={self._device})..."
        )
        try:
            # 1 second of silence at 16 kHz — just enough to trigger weight loading
            dummy_audio = torch.zeros(1, 16000, dtype=torch.float32)

            torchcrepe.predict(
                dummy_audio,
                sample_rate=16000,
                hop_length=160,  # 10 ms at 16 kHz
                fmin=32.7,  # C1 — torchcrepe's default lower bound
                fmax=1975.5,  # B6 — torchcrepe's default upper bound
                model=self._model,
                decoder=torchcrepe.decode.viterbi,
                return_periodicity=True,
                batch_size=512,
                device=self._device,
                pad=True,
            )

            self._ready = True
            logger.info(f"torchcrepe model '{self._model}' loaded successfully.")

        except Exception as e:
            logger.error(f"Failed to load torchcrepe model: {e}")
            raise

    def health_check(self) -> bool:
        """Return True if the model warmed up successfully."""
        return self._ready
