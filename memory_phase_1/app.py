from fastapi import FastAPI
from routes.memory_routes import router as memory_router
from routes.intelligence_routes import router as intelligence_router

app = FastAPI(
    title="Arango Agentic Memory — Phase 3",
    description="Core Memory Engine with Reflection and Summarization Layer.",
    version="3.0.0",
)

app.include_router(memory_router)
app.include_router(intelligence_router)


@app.get("/health")
def health():
    return {"status": "ok"}
