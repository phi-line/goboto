import sys
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(message)s")
handler.setFormatter(formatter)

logger.addHandler(handler)