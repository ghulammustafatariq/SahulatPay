"""KYC service — Cloudinary upload, OCR.space, Face++, Fernet, DeepSeek."""
from __future__ import annotations

import asyncio
import base64
import io
from typing import Optional
from uuid import UUID

import cloudinary
import cloudinary.uploader
import cloudinary.utils
import httpx
from cryptography.fernet import Fernet, InvalidToken

from config import settings


# ── Cloudinary init (lazy — configured once) ─────────────────────────────────
def _configure_cloudinary():
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )


# ── Upload KYC image to Cloudinary (private) ─────────────────────────────────
async def upload_kyc_document(
    file_bytes: bytes,
    user_id: UUID,
    doc_type: str,          # cnic_front | cnic_back | liveness_selfie | business_doc
) -> str:
    """Uploads to Cloudinary as private. Returns public_id (stored in DB)."""
    _configure_cloudinary()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: cloudinary.uploader.upload(
            io.BytesIO(file_bytes),
            folder=f"kyc/{user_id}/",
            public_id=doc_type,
            type="private",
            overwrite=True,
            resource_type="image",
        )
    )
    return result["public_id"]


def get_signed_url(public_id: str, expires_seconds: int = 900) -> str:
    """Generate 15-minute admin-only signed URL for a private KYC document."""
    _configure_cloudinary()
    import time
    url, _ = cloudinary.utils.cloudinary_url(
        public_id,
        resource_type="image",
        type="private",
        expires_at=int(time.time()) + expires_seconds,
        sign_url=True,
    )
    return url


# ── OCR.space — extract text from image bytes ────────────────────────────────
async def ocr_extract_text(file_bytes: bytes) -> str:
    """Send image to OCR.space, return raw extracted text."""
    if not settings.OCR_API_KEY:
        return ""
    b64 = base64.b64encode(file_bytes).decode()
    payload = {
        "base64Image": f"data:image/jpeg;base64,{b64}",
        "apikey":      settings.OCR_API_KEY,
        "language":    "eng",
        "OCREngine":   "2",
        "isTable":     "false",
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("https://api.ocr.space/parse/image", data=payload)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("ParsedResults") or []
            if results:
                return results[0].get("ParsedText", "")
    except Exception as e:
        print(f"[kyc_service] OCR error: {e}")
    return ""


# ── DeepSeek — clean + extract CNIC fields from raw OCR text ─────────────────
async def deepseek_extract_cnic(raw_ocr: str) -> dict:
    """Returns dict: {cnic_number, full_name, dob, address, father_name}"""
    if not settings.DEEPSEEK_API_KEY or not raw_ocr.strip():
        return {}
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )
        prompt = (
            "You are a Pakistan CNIC parser. Extract from this OCR text and return ONLY valid JSON "
            "(no markdown, no explanation) with keys: cnic_number (format XXXXX-XXXXXXX-X), "
            "full_name, father_name, dob (YYYY-MM-DD), address. If a field is not found use null.\n\n"
            f"OCR Text:\n{raw_ocr}"
        )
        resp = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0,
        )
        import json
        text = resp.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        print(f"[kyc_service] DeepSeek CNIC extract error: {e}")
        return {}


# ── Fernet AES-256 encryption ─────────────────────────────────────────────────
def encrypt_value(plaintext: str) -> str:
    if not settings.ENCRYPTION_KEY:
        return plaintext
    try:
        f = Fernet(settings.ENCRYPTION_KEY.encode())
        return f.encrypt(plaintext.encode()).decode()
    except Exception:
        return plaintext


def decrypt_value(ciphertext: str) -> str:
    if not settings.ENCRYPTION_KEY:
        return ciphertext
    try:
        f = Fernet(settings.ENCRYPTION_KEY.encode())
        return f.decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception):
        return ciphertext


# ── Face++ — compare two images ───────────────────────────────────────────────
async def facepp_compare(img1_bytes: bytes, img2_bytes: bytes) -> float:
    """Returns confidence score 0.0–100.0. Higher = more similar."""
    if not settings.FACE_API_KEY:
        return 0.0
    b64_1 = base64.b64encode(img1_bytes).decode()
    b64_2 = base64.b64encode(img2_bytes).decode()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api-us.faceplusplus.com/facepp/v3/compare",
                data={
                    "api_key":        settings.FACE_API_KEY,
                    "api_secret":     settings.FACE_API_SECRET,
                    "image_base64_1": b64_1,
                    "image_base64_2": img2_bytes and b64_2,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if "error_message" in data:
                print(f"[kyc_service] Face++ error: {data['error_message']}")
                return 0.0
            return float(data.get("confidence", 0.0))
    except Exception as e:
        print(f"[kyc_service] Face++ request error: {e}")
        return 0.0


# ── DeepSeek — analyse business documents ─────────────────────────────────────
async def deepseek_analyse_business(ocr_texts: list[str], business_name: str) -> str:
    """Returns AI analysis string for business document review."""
    if not settings.DEEPSEEK_API_KEY:
        return "Pending manual review."
    combined = "\n---\n".join(ocr_texts)
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )
        resp = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[{
                "role": "user",
                "content": (
                    f"You are a compliance officer reviewing business registration documents for '{business_name}'. "
                    f"Extracted text from documents:\n{combined}\n\n"
                    "In 3-4 sentences: (1) Are the documents legitimate? (2) What business type is this? "
                    "(3) Any concerns or missing information? Be concise and factual."
                ),
            }],
            max_tokens=300,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[kyc_service] DeepSeek business analysis error: {e}")
        return "AI analysis unavailable. Pending manual review."
