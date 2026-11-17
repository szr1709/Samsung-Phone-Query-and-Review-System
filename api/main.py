
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agents.crew import PhoneReviewCrew

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(
    title="Samsung Phone Query and Review API",
    description="AI-powered Samsung phone review API using a two-agent system.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


class ReviewRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        description="Question about a Samsung phone"
    )


class ReviewResponse(BaseModel):
    question: str
    review: str


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


@app.post("/review", response_model=ReviewResponse)
def generate_phone_review(request: ReviewRequest):

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty."
        )

    try:
        crew = PhoneReviewCrew()
        review = crew.run(question)

        return ReviewResponse(
            question=question,
            review=review
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Review generation failed: {str(error)}"
        )
