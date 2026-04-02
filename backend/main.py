import logging
import uvicorn
from dotenv import load_dotenv

# Load .env before any module reads os.getenv() at import time.
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(name)s  %(message)s",
)

from habittracker.server import create_application

app = create_application()

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
