import uvicorn

from habittracker.server import create_application

app = create_application()

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
