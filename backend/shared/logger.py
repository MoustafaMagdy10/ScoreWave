import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="\n%(asctime)s - %(name)s - %(levelname)s - %(message)s\n",
)

logger = logging.getLogger("songify")