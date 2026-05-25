from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.models import Invoice, InvoiceExtractionLog, InvoiceItem, InvoiceStatus, User
from app.schemas import ExtractedInvoiceData, InvoiceDetail, InvoiceItemResponse, InvoiceUpdate, PartyData

def invoice_to_detail(invoice: Invoice) -> InvoiceDetail:
    """SQLAlchemy Model → API Response Schema"""
    return InvoiceDetail(
        id=invoice.id,
        file_name=invoice.file_name,
        file_url=invoice.file_url,
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.invoice_date,
        seller_name=invoice.seller_name,
        buyer_name=invoice.buyer_name,
        subtotal=invoice.subtotal,
        discount=invoice.discount,
        vat_amount=invoice.vat_amount,
        total_amount=invoice.total_amount,
        currency=invoice.currency,
        status=invoice.status,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
        remarks=invoice.remarks,
        seller=PartyData(
            name=invoice.seller_name,
            address=invoice.seller_address,
            vat_pan_number=invoice.seller_vat_pan_number,
        ),
        buyer=PartyData(
            name=invoice.buyer_name,
            address=invoice.buyer_address,
            vat_pan_number=invoice.buyer_vat_pan_number,
        ),
        items=[InvoiceItemResponse.model_validate(item) for item in invoice.items],
    )

def get_user_invoice(db: Session, user: User, invoice_id: str) -> Invoice | None:
    statement = (
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.user_id == user.id) #users can only access their own invoices
        .options(selectinload(Invoice.items), selectinload(Invoice.logs))
    )
    return db.scalars(statement).first()

def apply_extracted_data(invoice: Invoice, data: ExtractedInvoiceData | InvoiceUpdate) -> None:
    """extracted data from LLM to SQLAlchemy Model."""
    invoice.invoice_number = data.invoice_number
    invoice.invoice_date = data.invoice_date
    invoice.seller_name = data.seller.name
    invoice.seller_address = data.seller.address
    invoice.seller_vat_pan_number = data.seller.vat_pan_number
    invoice.buyer_name = data.buyer.name
    invoice.buyer_address = data.buyer.address
    invoice.buyer_vat_pan_number = data.buyer.vat_pan_number
    invoice.subtotal = data.subtotal
    invoice.discount = data.discount
    invoice.vat_amount = data.vat_amount
    invoice.total_amount = data.total_amount
    invoice.currency = data.currency
    invoice.remarks = data.remarks

def replace_items(invoice: Invoice, items: list) -> None:
    invoice.items.clear()
    for item in items:
        invoice.items.append(
            InvoiceItem(
                description=item.description,
                quantity=item.quantity,
                rate=item.rate,
                amount=item.amount,
            )
        )

def determine_status(data: ExtractedInvoiceData) -> InvoiceStatus:
    required_values = [
        data.invoice_number,
        data.invoice_date,
        data.seller.name,
        data.buyer.name,
        data.total_amount,
    ]
    return InvoiceStatus.completed if all(required_values) else InvoiceStatus.needs_review

def add_extraction_log(
    db: Session,
    invoice: Invoice,
    status: InvoiceStatus,
    raw_ai_response: dict | None = None,
    error_message: str | None = None,
) -> None:
    db.add(
        InvoiceExtractionLog(
            invoice_id=invoice.id,
            status=status,
            raw_ai_response=raw_ai_response,
            error_message=error_message,
        )
    )
