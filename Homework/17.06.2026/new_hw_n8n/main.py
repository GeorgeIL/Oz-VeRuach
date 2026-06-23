import datetime
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel, field_validator

from extract_text import extract_file

app = FastAPI()

SENSITIVE_KEYWORDS = [
    "confidential",
    "internal budget",
    "forecast",
    "guidance",
    "budget",
    "expenses",
    "cash flow",
    "cash flow concerns",
    "layoffs",
    "restructuring",
]


class FinancialReport(BaseModel):
    document_type: str = "other"
    company: str | None = None
    ticker: str | None = None
    fiscal_quarter: str | None = None
    fiscal_year: str | None = None
    sentiment: str = "neutral"
    risk_level: str = "medium"
    confidence_score: float = 0.0
    financial_metrics: dict[str, Any] = {}
    entities: dict[str, Any] = {}

    @field_validator("fiscal_year", mode="before")
    @classmethod
    def coerce_fiscal_year(cls, value: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    @field_validator("entities", mode="before")
    @classmethod
    def coerce_entities(cls, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, list):
            return {"items": value}
        return {}


def normalize_document_type(document_type: str) -> str:
    normalized = document_type.strip().lower().replace(" ", "_").replace("-", "_")
    normalized = re.sub(r"[^a-z0-9_]", "", normalized)
    aliases = {
        "earningssummary": "earnings_summary",
        "budgetproposal": "budget_proposal",
        "expensereport": "expense_report",
    }
    return aliases.get(normalized, normalized)


def classify_sensitivity(data: FinancialReport) -> str:
    document_type = normalize_document_type(data.document_type)
    text = str(data).lower()

    if document_type in {"budget_proposal", "expense_report"}:
        return "confidential"

    if any(keyword in text for keyword in SENSITIVE_KEYWORDS):
        return "confidential"

    if document_type == "earnings_summary":
        return "internal"

    return "internal"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/categories")
def categories():
    return {
        "categories": [
            "earnings_summary",
            "budget_proposal",
            "expense_report",
            "other",
        ]
    }


@app.post("/sensitivity")
def sensitivity(data: FinancialReport):
    return {"sensitivity": classify_sensitivity(data)}


@app.post("/enrich")
def enrich(data: FinancialReport):
    document_type = normalize_document_type(data.document_type)
    sentiment = data.sentiment.strip().lower()
    risk_level = data.risk_level.strip().lower()

    department = "Finance"
    if document_type == "budget_proposal":
        department = "Finance Planning"
    elif document_type == "expense_report":
        department = "Accounting"
    elif document_type == "earnings_summary":
        department = "Investor Relations"

    if risk_level == "high" or data.confidence_score < 0.7:
        routing_tag = "needs-review"
    elif sentiment == "negative":
        routing_tag = "finance-review"
    else:
        routing_tag = "auto-approved"

    normalized = FinancialReport(
        document_type=document_type,
        company=data.company,
        ticker=data.ticker,
        fiscal_quarter=data.fiscal_quarter,
        fiscal_year=data.fiscal_year,
        sentiment=sentiment,
        risk_level=risk_level,
        confidence_score=data.confidence_score,
        financial_metrics=data.financial_metrics,
        entities=data.entities,
    )

    return {
        "document_id": str(uuid.uuid4()),
        "department": department,
        "sensitivity": classify_sensitivity(normalized),
        "routing_tag": routing_tag,
        "processed_at": datetime.datetime.utcnow().isoformat(),
    }


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    suffix = Path(file.filename or "upload").suffix.lower()
    allowed = {".pdf", ".docx", ".txt"}

    if suffix not in allowed:
        raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        extracted_text = extract_file(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {
        "extracted_text": extracted_text,
        "filename": file.filename,
    }
