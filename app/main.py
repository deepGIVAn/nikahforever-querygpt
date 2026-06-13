from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes.query import router as query_router
from app.routes.schema import router as schema_router
from app.routes.suggestions import router as suggest_router

app = FastAPI(
    title="NF QueryGPT API",
    description="Backend API for NikahForever QueryGPT (Natural Language to SQL Assistant)",
    version="1.0.0"
)

# Parse CORS origins from settings
origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]

# Add CORS Middleware to enable communication with Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(query_router)
app.include_router(schema_router)
app.include_router(suggest_router)

@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "NikahForever QueryGPT API is running.",
        "documentation": "/docs"
    }
