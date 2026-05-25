import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.database import get_db
from app.extractor import get_extractor
from app.invoice_service import (
    add_extraction_log,
    apply_extracted_data,
    determine_status,
    get_user_invoice,
    invoice_to_detail,
    replace_items,
)
from app.models import Invoice, InvoiceStatus, User
from app.schemas import InvoiceDetail, InvoiceSummary, InvoiceUpdate
from app.storage import delete_file, save_upload

router = APIRouter(prefix="/api/invoices", tags=["invoices"])
logger = logging.getLogger(__name__)

async def _extract_and_save_invoice(db: Session, invoice: Invoice) -> None:
    extractor = get_extractor()
    try:
        logger.info(
            "Invoice extraction started invoice_id=%s file_name=%s extractor=%s",
            invoice.id,
            invoice.file_name,
            extractor.__class__.__name__,
        )
        extracted = await extractor.extract(invoice.stored_file_path, invoice.file_name)
        apply_extracted_data(invoice, extracted)
        replace_items(invoice, extracted.items)
        invoice.status = determine_status(extracted)
        add_extraction_log(
            db,
            invoice,
            invoice.status,
            raw_ai_response=extracted.model_dump(mode="json"),
        )
        logger.info(
            "Invoice extraction completed invoice_id=%s status=%s item_count=%s",
            invoice.id,
            invoice.status,
            len(extracted.items),
        )
    except Exception as exc:
        invoice.status = InvoiceStatus.failed
        add_extraction_log(db, invoice, InvoiceStatus.failed, error_message=str(exc))
        logger.exception("Invoice extraction failed invoice_id=%s file_name=%s", invoice.id, invoice.file_name)


@router.post("/upload", response_model=InvoiceDetail, status_code=status.HTTP_201_CREATED)
async def upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> InvoiceDetail:
    logger.info(
        "Invoice upload started user_id=%s file_name=%s content_type=%s",
        user.id,
        file.filename,
        file.content_type,
    )
    stored_path, file_url = await save_upload(file)
    invoice = Invoice(
        user_id=user.id,
        file_name=file.filename or "invoice",
        file_url=file_url,
        stored_file_path=stored_path,
        status=InvoiceStatus.uploaded,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    logger.info("Invoice record created invoice_id=%s user_id=%s", invoice.id, user.id)

    invoice.status = InvoiceStatus.processing
    db.commit()

    await _extract_and_save_invoice(db, invoice)
    db.commit()
    invoice = get_user_invoice(db, user, invoice.id)
    if invoice is None:
        logger.error("Uploaded invoice disappeared after extraction invoice_id=%s user_id=%s", invoice.id, user.id)
        raise HTTPException(status_code=404, detail="Invoice not found")
    logger.info("Invoice upload completed invoice_id=%s status=%s", invoice.id, invoice.status)
    return invoice_to_detail(invoice)


@router.get("", response_model=list[InvoiceSummary])
def list_invoices(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[InvoiceSummary]:
    logger.info("Invoice list requested user_id=%s", user.id)
    statement = (
        select(Invoice)
        .where(Invoice.user_id == user.id)
        .order_by(Invoice.created_at.desc())
    )
    invoices = list(db.scalars(statement).all())
    logger.info("Invoice list returned user_id=%s count=%s", user.id, len(invoices))
    return invoices


@router.get("/{invoice_id}", response_model=InvoiceDetail)
def get_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> InvoiceDetail:
    invoice = get_user_invoice(db, user, invoice_id)
    if invoice is None:
        logger.warning("Invoice detail not found invoice_id=%s user_id=%s", invoice_id, user.id)
        raise HTTPException(status_code=404, detail="Invoice not found")
    logger.info("Invoice detail returned invoice_id=%s user_id=%s", invoice_id, user.id)
    return invoice_to_detail(invoice)


@router.put("/{invoice_id}", response_model=InvoiceDetail)
def update_invoice(
    invoice_id: str,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> InvoiceDetail:
    invoice = get_user_invoice(db, user, invoice_id)
    if invoice is None:
        logger.warning("Invoice update not found invoice_id=%s user_id=%s", invoice_id, user.id)
        raise HTTPException(status_code=404, detail="Invoice not found")

    logger.info("Invoice update started invoice_id=%s user_id=%s status=%s", invoice_id, user.id, payload.status)
    apply_extracted_data(invoice, payload)
    replace_items(invoice, payload.items)
    invoice.status = payload.status or InvoiceStatus.completed
    db.commit()
    db.refresh(invoice)
    invoice = get_user_invoice(db, user, invoice.id)
    if invoice is None:
        logger.error("Updated invoice disappeared invoice_id=%s user_id=%s", invoice_id, user.id)
        raise HTTPException(status_code=404, detail="Invoice not found")
    logger.info("Invoice update completed invoice_id=%s user_id=%s status=%s", invoice.id, user.id, invoice.status)
    return invoice_to_detail(invoice)

@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    invoice = get_user_invoice(db, user, invoice_id)
    if invoice is None:
        logger.warning("Invoice delete not found invoice_id=%s user_id=%s", invoice_id, user.id)
        raise HTTPException(status_code=404, detail="Invoice not found")
    logger.info("Invoice delete started invoice_id=%s user_id=%s", invoice_id, user.id)
    stored_path = invoice.stored_file_path
    db.delete(invoice)
    db.commit()
    delete_file(stored_path)
    logger.info("Invoice delete completed invoice_id=%s user_id=%s", invoice_id, user.id)
