from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from app.models import InvoiceStatus

class PartyData(BaseModel):
    name: str | None = None
    address: str | None = None
    vat_pan_number: str | None = None
    
class InvoiceItemData(BaseModel):
    description: str | None = None
    quantity: Decimal | None = None
    rate: Decimal | None = None
    amount: Decimal | None = None

class ExtractedInvoiceData(BaseModel):
    invoice_number: str | None = None
    invoice_date: date | None = None
    seller: PartyData = Field(default_factory=PartyData)
    buyer: PartyData = Field(default_factory=PartyData)
    items: list[InvoiceItemData] = Field(default_factory=list)
    subtotal: Decimal | None = None
    discount: Decimal | None = None
    vat_amount: Decimal | None = None
    total_amount: Decimal | None = None
    currency: str | None = None
    remarks: str | None = None

class InvoiceItemResponse(InvoiceItemData):
    id: str
    model_config = ConfigDict(from_attributes=True)

class InvoiceSummary(BaseModel):
    id: str
    file_name: str
    file_url: str
    invoice_number: str | None
    invoice_date: date | None
    seller_name: str | None
    buyer_name: str | None
    vat_amount: Decimal | None
    total_amount: Decimal | None
    currency: str | None
    status: InvoiceStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class InvoiceDetail(InvoiceSummary):
    seller: PartyData
    buyer: PartyData
    subtotal: Decimal | None
    discount: Decimal | None
    remarks: str | None
    items: list[InvoiceItemResponse]

class InvoiceUpdate(BaseModel):
    invoice_number: str | None = None
    invoice_date: date | None = None
    seller: PartyData = Field(default_factory=PartyData)
    buyer: PartyData = Field(default_factory=PartyData)
    items: list[InvoiceItemData] = Field(default_factory=list)
    subtotal: Decimal | None = None
    discount: Decimal | None = None
    vat_amount: Decimal | None = None
    total_amount: Decimal | None = None
    currency: str | None = None
    remarks: str | None = None
    status: InvoiceStatus | None = None
