from basic_pitch.inference import Model
from basic_pitch import ICASSP_2022_MODEL_PATH
from shared.logger import logger


class BasicPitch:
    """
    Wrapper around Spotify's Basic Pitch audio-to-MIDI transcription model.

    Basic Pitch is a lightweight neural network for polyphonic note transcription
    and multipitch estimation. It converts audio (WAV, MP3, FLAC, etc.) to MIDI.

    Uses the ICASSP 2022 model (the official pretrained model from Spotify).
    Uses ONNX runtime for better compatibility with Python 3.12.
    """

    def __init__(self):
        self.model = None
        self._ready = False
        self._load_model()

    def _load_model(self) -> None:
        logger.info("Loading Basic Pitch model (ICASSP 2022 ONNX)...")
        try:
            onnx_path = str(ICASSP_2022_MODEL_PATH).replace("nmp", "nmp.onnx")
            self.model = Model(onnx_path)
            self._ready = True
            logger.info("Basic Pitch model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Basic Pitch model: {e}")
            raise

    def health_check(self) -> bool:
        return self._ready
