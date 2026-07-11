from dotenv import load_dotenv

load_dotenv()  # must run before any import below reads GOOGLE_* env vars

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.models.responses import ErrorResponse, HealthResponse
from app.routers.classify import load_audio_classifier, load_image_classifier, router as classify_router
from app.routers.document import load_vision_client, router as document_router
from app.routers.honeypot import router as honeypot_router
from app.routers.complaint import init_db as init_complaint_db, router as complaint_router
from app.routers.digital_arrest import router as digital_arrest_router
from app.routers.vault import router as vault_router
from app.routers.phishing import load_phishing_blocklist, router as phishing_router
from app.routers.social_profile import router as social_profile_router
from app.routers.network_intel import init_db as init_network_intel_db, router as network_intel_router
from app.routers.blocklist import init_db as init_blocklist_db, router as blocklist_router
from app.routers.compliance import init_db as init_compliance_db, router as compliance_router
from app.routers.asset_tracker import init_db as init_asset_tracker_db, router as asset_tracker_router
from app.routers.moonshots import router as moonshots_router
from app.routers.romance_scam import router as romance_scam_router
from app.routers.investment_scam import router as investment_scam_router
from app.routers.lottery_scam import router as lottery_scam_router
from app.routers.courier_scam import router as courier_scam_router
from app.routers.bec_scam import router as bec_scam_router
from app.routers.matrimonial_scam import router as matrimonial_scam_router
from app.routers.gov_scheme import router as gov_scheme_router
from app.routers.qr_scam import router as qr_scam_router
from app.routers.exam_scam import router as exam_scam_router
from app.routers.ecommerce_scam import router as ecommerce_scam_router
from app.routers.ussd_scam import router as ussd_scam_router
from app.routers.recruitment_scam import router as recruitment_scam_router
from app.routers.challan_scam import router as challan_scam_router
from app.routers.customercare_scam import router as customercare_scam_router
from app.routers.kyc_scam import router as kyc_scam_router
from app.routers.rental_scam import router as rental_scam_router
from app.routers.reward_scam import router as reward_scam_router
from app.routers.utility_scam import router as utility_scam_router
from app.routers.job_scam import router as job_scam_router
from app.routers.loan_scam import router as loan_scam_router
from app.routers.sextortion import router as sextortion_router
from app.routers.segments import init_db as init_segments_db, router as segments_router
from app.routers.vulnerable import init_db as init_vulnerable_db, router as vulnerable_router
from app.routers.surfaces import router as surfaces_router
from app.routers.business import init_db as init_business_db, router as business_router
from app.routers.education import router as education_router
from app.routers.campaign_timeline import init_db as init_campaign_timeline_db, router as campaign_timeline_router
from app.services.honeypot_pipeline import load_tts_client, load_whisper_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ponytail: sync loads block briefly at startup — fine for demo
    load_image_classifier()
    load_audio_classifier()
    load_vision_client()
    load_whisper_model()
    load_tts_client()
    load_phishing_blocklist()
    init_network_intel_db()
    init_blocklist_db()
    init_compliance_db()
    init_asset_tracker_db()
    init_segments_db()
    init_vulnerable_db()
    init_business_db()
    init_campaign_timeline_db()
    init_complaint_db()
    yield


app = FastAPI(title="Kavach API", version="0.1.0", lifespan=lifespan)

# Dev servers (5173 Vite default, 5174 its documented fallback — port drift
# bit us once, a leftover process held 5173) plus the deployed Firebase
# Hosting origins for marketing and the app. Still no wildcard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "https://kavach-501620-app.web.app",
        "https://kavach-marketing.web.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(classify_router)
app.include_router(document_router)
app.include_router(honeypot_router)
app.include_router(phishing_router)
app.include_router(social_profile_router)
app.include_router(complaint_router)
app.include_router(digital_arrest_router)
app.include_router(vault_router)
app.include_router(network_intel_router)
app.include_router(blocklist_router)
app.include_router(compliance_router)
app.include_router(asset_tracker_router)
app.include_router(moonshots_router)
app.include_router(romance_scam_router)
app.include_router(investment_scam_router)
app.include_router(lottery_scam_router)
app.include_router(courier_scam_router)
app.include_router(bec_scam_router)
app.include_router(matrimonial_scam_router)
app.include_router(gov_scheme_router)
app.include_router(qr_scam_router)
app.include_router(exam_scam_router)
app.include_router(ecommerce_scam_router)
app.include_router(ussd_scam_router)
app.include_router(recruitment_scam_router)
app.include_router(challan_scam_router)
app.include_router(customercare_scam_router)
app.include_router(kyc_scam_router)
app.include_router(rental_scam_router)
app.include_router(reward_scam_router)
app.include_router(utility_scam_router)
app.include_router(job_scam_router)
app.include_router(loan_scam_router)
app.include_router(sextortion_router)
app.include_router(segments_router)
app.include_router(vulnerable_router)
app.include_router(surfaces_router)
app.include_router(business_router)
app.include_router(education_router)
app.include_router(campaign_timeline_router)


def _error_response(status_code: int, error: str, detail: Any = None) -> JSONResponse:
    """Build a guaranteed-JSON error response. Every error in this codebase flows through here."""
    content: dict[str, Any] = {"error": error, "status_code": status_code}
    if detail is not None:
        content["detail"] = detail
    return JSONResponse(status_code=status_code, content=content)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _error_response(exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Pydantic v2 model_validator errors include a ValueError object in ctx["error"],
    # which json.dumps cannot serialize. Convert to str to keep the response valid JSON.
    errors = exc.errors()
    for err in errors:
        ctx = err.get("ctx", {})
        if isinstance(ctx.get("error"), Exception):
            ctx["error"] = str(ctx["error"])
    return _error_response(422, "Validation error", errors)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return _error_response(500, "Internal server error", str(exc))


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness check."""
    return HealthResponse(status="ok")


# ponytail: test-only route — gate behind DEBUG env var before production
@app.get("/debug/crash", response_model=ErrorResponse)
async def crash() -> None:
    """Intentionally raises to verify the global exception handler returns JSON."""
    raise RuntimeError("Intentional crash for testing")
