# schemas.py — Pydantic 請求/回應模型
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from models import CurrencyEnum


# ── 共用 ──────────────────────────────────────────────────────
class OKResponse(BaseModel):
    ok: bool = True
    message: str = "success"


# ── 使用者 ────────────────────────────────────────────────────
class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str]
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── 供應商 ────────────────────────────────────────────────────
class SupplierCreate(BaseModel):
    name: str
    country: Optional[str] = None
    currency: CurrencyEnum = CurrencyEnum.USD
    contact_email: Optional[str] = None
    notes: Optional[str] = None

class SupplierOut(SupplierCreate):
    id: int
    created_at: datetime
    model_config = {"from_attributes": True}


# ── 產品 ──────────────────────────────────────────────────────
class ProductCreate(BaseModel):
    sku: str
    name_en: str
    name_zh: Optional[str] = None
    description_en: Optional[str] = None
    description_zh: Optional[str] = None
    category: Optional[str] = None
    supplier_id: Optional[int] = None
    unit: str = "pcs"
    image_url: Optional[str] = None

class ProductUpdate(BaseModel):
    name_zh: Optional[str] = None
    description_zh: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None

class ProductOut(ProductCreate):
    id: int
    is_active: bool
    created_at: datetime
    # 最新報價（join 用）
    latest_price: Optional[Decimal] = None
    latest_price_currency: Optional[str] = None
    qty_on_hand: Optional[int] = None
    model_config = {"from_attributes": True}


# ── 報價單 ────────────────────────────────────────────────────
class PriceItemIn(BaseModel):
    sku: str                        # 用 SKU 對應產品
    unit_price: Decimal
    moq: int = 1
    notes: Optional[str] = None

class PriceListCreate(BaseModel):
    supplier_id: int
    list_date: datetime
    currency: CurrencyEnum = CurrencyEnum.USD
    notes: Optional[str] = None
    items: List[PriceItemIn] = []

class PriceItemOut(BaseModel):
    id: int
    product_id: int
    sku: str
    name_en: str
    name_zh: Optional[str]
    unit_price: Decimal
    moq: int
    model_config = {"from_attributes": True}

class PriceListOut(BaseModel):
    id: int
    supplier_id: int
    supplier_name: str
    list_date: datetime
    currency: str
    notes: Optional[str]
    items: List[PriceItemOut] = []
    created_at: datetime
    model_config = {"from_attributes": True}


# ── 進口記錄 ──────────────────────────────────────────────────
class ImportItemIn(BaseModel):
    sku: str
    qty: int
    unit_cost_foreign: Decimal

class ImportRecordCreate(BaseModel):
    supplier_id: int
    invoice_no: Optional[str] = None
    import_declaration_no: Optional[str] = None
    import_date: datetime
    currency: CurrencyEnum = CurrencyEnum.USD
    exchange_rate: Decimal = Decimal("1.0")
    freight_twd: Decimal = Decimal("0")
    customs_twd: Decimal = Decimal("0")
    other_cost_twd: Decimal = Decimal("0")
    notes: Optional[str] = None
    items: List[ImportItemIn] = []

class ImportItemOut(BaseModel):
    id: int
    product_id: int
    sku: str
    name_en: str
    name_zh: Optional[str]
    qty: int
    unit_cost_foreign: Decimal
    unit_cost_twd: Optional[Decimal]
    model_config = {"from_attributes": True}

class ImportRecordOut(BaseModel):
    id: int
    supplier_id: int
    supplier_name: str
    invoice_no: Optional[str]
    import_declaration_no: Optional[str]
    import_date: datetime
    currency: str
    exchange_rate: Decimal
    total_foreign: Decimal
    total_twd: Decimal
    freight_twd: Decimal
    customs_twd: Decimal
    other_cost_twd: Decimal
    notes: Optional[str]
    items: List[ImportItemOut] = []
    created_at: datetime
    model_config = {"from_attributes": True}


# ── 庫存 ──────────────────────────────────────────────────────
class InventoryUpdate(BaseModel):
    selling_price_twd: Optional[Decimal] = None
    qty_adjust: Optional[int] = None    # 正數=入庫，負數=出庫

class InventoryOut(BaseModel):
    id: int
    product_id: int
    sku: str
    name_en: str
    name_zh: Optional[str]
    qty_on_hand: int
    avg_cost_twd: Decimal
    selling_price_twd: Decimal
    margin_pct: Optional[float] = None  # 毛利率
    updated_at: datetime
    model_config = {"from_attributes": True}
