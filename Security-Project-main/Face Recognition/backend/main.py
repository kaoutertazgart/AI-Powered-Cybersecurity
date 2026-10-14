"""
main.py — FastAPI entry point
Run: uvicorn main:app --reload
Docs: http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from database import create_tables
from routers import auth, students

app = FastAPI(
    title=settings.APP_NAME,
    description="Student face recognition — authentication & enrollment (ArcFace)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    create_tables()
    print("✅  Database tables created / verified.")


app.include_router(auth.router)
app.include_router(students.router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

