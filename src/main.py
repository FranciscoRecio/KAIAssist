from fastapi import FastAPI
from src.config.settings import Settings
from src.api.routes import twilio

app = FastAPI(title="KAI Assist", description="AI-powered call center assistant")
settings = Settings()

# Include routers
app.include_router(twilio.router, prefix="/api/twilio", tags=["twilio"])

@app.get("/")
async def root():
    return {"message": "KAI Assist API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 