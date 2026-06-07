from fastapi import FastAPI
from routes.memory_routes import router

app = FastAPI(
    title="Arango Agentic Memory — Phase 1",
    description="Core Memory Engine MVP: store, classify, and retrieve memories via ArangoDB.",
    version="1.0.0",
)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
