import base64
import asyncio
import json
import logging
import mimetypes
from pathlib import Path
import httpx

from app.config import get_settings
from app.schemas import ExtractedInvoiceData, InvoiceItemData, PartyData
logger = logging.getLogger(__name__)
MIME_TYPE_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

def detect_mime_type(file_name: str, file_path: str) -> str:
    guessed = mimetypes.guess_type(file_name)[0] or mimetypes.guess_type(file_path)[0]
    if guessed and guessed != "application/octet-stream":
        return guessed
    return MIME_TYPE_BY_EXTENSION.get(Path(file_name).suffix.lower()) or MIME_TYPE_BY_EXTENSION.get(Path(file_path).suffix.lower()) or "application/octet-stream"

class InvoiceExtractor:
    async def extract(self, file_path: str, file_name: str) -> ExtractedInvoiceData:
        raise NotImplementedError

class MockInvoiceExtractor(InvoiceExtractor):
    async def extract(self, file_path: str, file_name: str) -> ExtractedInvoiceData:
        logger.info("Mock extraction started file_name=%s", file_name)
        stem = Path(file_name).stem.replace("_", " ").replace("-", " ").strip()
        extracted = ExtractedInvoiceData(
            invoice_number=None,
            invoice_date=None,
            seller=PartyData(name=None, address=None, vat_pan_number=None),
            buyer=PartyData(name=None, address=None, vat_pan_number=None),
            items=[
                InvoiceItemData(
                    description=f"Review extracted line item from {stem or 'uploaded invoice'}",
                    quantity=None,
                    rate=None,
                    amount=None,
                )
            ],
            subtotal=None,
            discount=None,
            vat_amount=None,
            total_amount=None,
            currency=None,
            remarks="Mock extraction result. Configure an LLM provider to populate real invoice fields.",
        )
        logger.info("Mock extraction completed file_name=%s item_count=%s", file_name, len(extracted.items))
        return extracted

class GeminiInvoiceExtractor(InvoiceExtractor):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def extract(self, file_path: str, file_name: str) -> ExtractedInvoiceData:
        file_bytes = Path(file_path).read_bytes()
        mime_type = detect_mime_type(file_name, file_path)
        logger.info(
            "Gemini extraction started file_name=%s model=%s mime_type=%s file_size=%s",
            file_name,
            self.model,
            mime_type,
            len(file_bytes),
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": self._prompt()},
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": base64.b64encode(file_bytes).decode("ascii"),
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        response = await self._post_with_retry(url, payload)

        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        extracted = ExtractedInvoiceData.model_validate(self._parse_json(text))
        logger.info("Gemini extraction completed file_name=%s item_count=%s", file_name, len(extracted.items))
        return extracted

    async def _post_with_retry(self, url: str, payload: dict) -> httpx.Response:
        retry_statuses = {429, 500, 502, 503, 504}
        headers = {"x-goog-api-key": self.api_key}
        async with httpx.AsyncClient(timeout=60) as client:
            for attempt in range(1, 4):
                try:
                    response = await client.post(url, headers=headers, json=payload)
                except httpx.RequestError as exc:
                    if attempt == 3:
                        raise RuntimeError(f"Gemini request failed after retries: {exc.__class__.__name__}") from exc
                    logger.warning("Gemini request error attempt=%s error=%s", attempt, exc.__class__.__name__)
                    await asyncio.sleep(attempt * 1.5)
                    continue

                if response.status_code in retry_statuses and attempt < 3:
                    logger.warning("Gemini transient error status=%s attempt=%s", response.status_code, attempt)
                    await asyncio.sleep(attempt * 1.5)
                    continue

                if response.is_error:
                    detail = response.text[:500].replace("\n", " ")
                    raise RuntimeError(f"Gemini extraction failed status={response.status_code} detail={detail}")

                return response

        raise RuntimeError("Gemini extraction failed without a response")

    @staticmethod
    def _parse_json(text: str) -> dict:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.removeprefix("json").strip()
        return json.loads(cleaned)

    @staticmethod
    def _prompt() -> str:
        return """
Extract invoice data from the attached invoice file.
Return only valid JSON matching this exact shape. Use null for missing or uncertain fields.
Do not guess values that are not visible in the invoice.

{
  "invoice_number": null,
  "invoice_date": null,
  "seller": {"name": null, "address": null, "vat_pan_number": null},
  "buyer": {"name": null, "address": null, "vat_pan_number": null},
  "items": [
    {"description": null, "quantity": null, "rate": null, "amount": null}
  ],
  "subtotal": null,
  "discount": null,
  "vat_amount": null,
  "total_amount": null,
  "currency": null,
  "remarks": null
}

Dates must use YYYY-MM-DD format when visible.
Numbers must not include currency symbols or thousands separators.
""".strip()

def get_extractor() -> InvoiceExtractor:
    settings = get_settings()
    if settings.llm_provider.lower() == "gemini" and settings.gemini_api_key:
        logger.info("Using Gemini invoice extractor model=%s", settings.gemini_model)
        return GeminiInvoiceExtractor(settings.gemini_api_key, settings.gemini_model)
    logger.warning("Using mock invoice extractor provider=%s gemini_key_configured=%s", settings.llm_provider, bool(settings.gemini_api_key))
    return MockInvoiceExtractor()
