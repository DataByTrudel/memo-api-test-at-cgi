from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/")
def root():
    endpoint = os.getenv("SEARCH_ENDPOINT", "not found")
    return {"message": "Hello from memo-api-at-cgi", "search_endpoint": endpoint}
