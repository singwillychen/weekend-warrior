# models.py — SQLAlchemy ORM 資料表定義
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean,
    ForeignKey, Text, Numeric, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from database import Base


class CurrencyEnum(str, enum.Enum):
    TWD = "TWD"
    USD = "USD"
    EUR = "EUR"
    SEK = "SEK"
    NOK = "NOK"
    GBP = "GBP"


# ── 使用者 ────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True)
    hashed_password = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── 供應商 ────────────────────────────────────────────────────
class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    country = Column(String(50), nullable=True)
    currency = Column(SAEnum(CurrencyEnum), default=CurrencyEnum.USD)
    contact_email = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 關聯
    products = relationship("Product", back_populates="supplier")
    price_lists = relationship("PriceList", back_populates="supplier")
    import_records = relationship("ImportRecord", back_populates="supplier")


# ── 產品 ──────────────────────────────────────────────────────
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(100), unique=True, nullable=False, index=True)
    name_en = Column(String(200), nullable=False, index=True)
    name_zh = Column(String(200), nullable=True)           # 中文翻譯
    description_en = Column(Text, nullable=True)
    description_zh = Column(Text, nullable=True)
    category = Column(String(100), nullable=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    unit = Column(String(20), default="pcs")               # 單位
    is_active = Column(Boolean, default=True)
    image_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 關聯
    supplier = relationship("Supplier", back_populates="products")
    price_items = relationship("PriceItem", back_populates="product")
    import_items = relationship("ImportItem", back_populates="product")
    inventory = relationship("Inventory", back_populates="product", uselist=False)


# ── 報價單主檔 ────────────────────────────────────────────────
class PriceList(Base):
    __tablename__ = "price_lists"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    list_date = Column(DateTime(timezone=True), nullable=False)
    currency = Column(SAEnum(CurrencyEnum), default=CurrencyEnum.USD)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 關聯
    supplier = relationship("Supplier", back_populates="price_lists")
    items = relationship("PriceItem", back_populates="price_list", cascade="all, delete-orphan")


# ── 報價單明細 ────────────────────────────────────────────────
class PriceItem(Base):
    __tablename__ = "price_items"

    id = Column(Integer, primary_key=True, index=True)
    price_list_id = Column(Integer, ForeignKey("price_lists.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    unit_price = Column(Numeric(12, 4), nullable=False)   # 原廠報價
    moq = Column(Integer, default=1)                       # 最小訂購量
    notes = Column(String(200), nullable=True)

    # 關聯
    price_list = relationship("PriceList", back_populates="items")
    product = relationship("Product", back_populates="price_items")


# ── 進口記錄主檔 ──────────────────────────────────────────────
class ImportRecord(Base):
    __tablename__ = "import_records"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    invoice_no = Column(String(100), nullable=True, index=True)  # 原廠 Invoice 號碼
    import_declaration_no = Column(String(100), nullable=True)   # 進口報單號碼
    import_date = Column(DateTime(timezone=True), nullable=False)
    currency = Column(SAEnum(CurrencyEnum), default=CurrencyEnum.USD)
    exchange_rate = Column(Numeric(10, 4), default=1.0)          # 進口時匯率
    total_foreign = Column(Numeric(14, 2), default=0)            # 外幣總計
    total_twd = Column(Numeric(14, 2), default=0)                # 台幣總計
    freight_twd = Column(Numeric(14, 2), default=0)              # 運費（台幣）
    customs_twd = Column(Numeric(14, 2), default=0)              # 關稅（台幣）
    other_cost_twd = Column(Numeric(14, 2), default=0)           # 其他費用
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 關聯
    supplier = relationship("Supplier", back_populates="import_records")
    items = relationship("ImportItem", back_populates="import_record", cascade="all, delete-orphan")


# ── 進口記錄明細 ──────────────────────────────────────────────
class ImportItem(Base):
    __tablename__ = "import_items"

    id = Column(Integer, primary_key=True, index=True)
    import_record_id = Column(Integer, ForeignKey("import_records.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    qty = Column(Integer, nullable=False, default=1)
    unit_cost_foreign = Column(Numeric(12, 4), nullable=False)   # 外幣單價
    unit_cost_twd = Column(Numeric(12, 2), nullable=True)        # 換算台幣（含運關雜費分攤）

    # 關聯
    import_record = relationship("ImportRecord", back_populates="items")
    product = relationship("Product", back_populates="import_items")


# ── 庫存 ──────────────────────────────────────────────────────
class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), unique=True, nullable=False)
    qty_on_hand = Column(Integer, default=0)               # 現有庫存
    avg_cost_twd = Column(Numeric(12, 2), default=0)       # 平均進貨成本（台幣）
    selling_price_twd = Column(Numeric(12, 2), default=0)  # 建議售價（台幣）
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 關聯
    product = relationship("Product", back_populates="inventory")
