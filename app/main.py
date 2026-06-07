# main.py — 週末戰士 FastAPI 後端
from contextlib import asynccontextmanager
from typing import Optional, List
from decimal import Decimal
import io

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
import pandas as pd
from rapidfuzz import fuzz, process

from database import engine, Base, get_db
from models import (
    User, Supplier, Product, PriceList, PriceItem,
    ImportRecord, ImportItem, Inventory
)
from schemas import (
    OKResponse, Token, UserCreate, UserOut,
    SupplierCreate, SupplierOut,
    ProductCreate, ProductUpdate, ProductOut,
    PriceListCreate, PriceListOut, PriceItemOut,
    ImportRecordCreate, ImportRecordOut, ImportItemOut,
    InventoryUpdate, InventoryOut,
)
from auth import authenticate_user, create_access_token, get_current_user, hash_password


# ── 啟動：建立資料表 ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="週末戰士 API",
    description="運動用品進口商管理系統 — 報價/翻譯/記帳/庫存",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 健康檢查 ──────────────────────────────────────────────────
@app.get("/", tags=["health"])
async def root():
    return {"message": "週末戰士 API is running", "version": "1.0.0"}

@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}


# ══════════════════════════════════════════════════════════════
# 認證
# ══════════════════════════════════════════════════════════════
@app.post("/auth/register", response_model=UserOut, tags=["auth"])
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == payload.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@app.post("/auth/login", response_model=Token, tags=["auth"])
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    user = await authenticate_user(db, form.username, form.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


@app.get("/auth/me", response_model=UserOut, tags=["auth"])
async def me(current_user: User = Depends(get_current_user)):
    return current_user


# ══════════════════════════════════════════════════════════════
# 供應商
# ══════════════════════════════════════════════════════════════
@app.get("/suppliers", response_model=List[SupplierOut], tags=["suppliers"])
async def list_suppliers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Supplier).order_by(Supplier.name))
    return result.scalars().all()


@app.post("/suppliers", response_model=SupplierOut, tags=["suppliers"])
async def create_supplier(
    payload: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@app.get("/suppliers/{supplier_id}", response_model=SupplierOut, tags=["suppliers"])
async def get_supplier(supplier_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


# ══════════════════════════════════════════════════════════════
# 產品
# ══════════════════════════════════════════════════════════════
@app.get("/products", response_model=List[ProductOut], tags=["products"])
async def list_products(
    q: Optional[str] = Query(None, description="模糊搜尋 SKU/英文名/中文名"),
    category: Optional[str] = None,
    supplier_id: Optional[int] = None,
    active_only: bool = True,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Product)
    if active_only:
        stmt = stmt.where(Product.is_active == True)
    if category:
        stmt = stmt.where(Product.category == category)
    if supplier_id:
        stmt = stmt.where(Product.supplier_id == supplier_id)

    result = await db.execute(stmt.order_by(Product.sku).offset(offset).limit(limit))
    products = result.scalars().all()

    # 模糊搜尋
    if q:
        candidates = {p.id: f"{p.sku} {p.name_en} {p.name_zh or ''}" for p in products}
        matches = process.extract(q, candidates, scorer=fuzz.WRatio, limit=50, score_cutoff=50)
        matched_ids = {m[2] for m in matches}
        products = [p for p in products if p.id in matched_ids]

    # 附加最新報價和庫存數量
    out = []
    for p in products:
        item = ProductOut.model_validate(p)
        # 最新報價
        pr = await db.execute(
            select(PriceItem, PriceList)
            .join(PriceList)
            .where(PriceItem.product_id == p.id)
            .order_by(desc(PriceList.list_date))
            .limit(1)
        )
        row = pr.first()
        if row:
            item.latest_price = row[0].unit_price
            item.latest_price_currency = row[1].currency.value
        # 庫存
        inv_r = await db.execute(select(Inventory).where(Inventory.product_id == p.id))
        inv = inv_r.scalar_one_or_none()
        if inv:
            item.qty_on_hand = inv.qty_on_hand
        out.append(item)
    return out


@app.post("/products", response_model=ProductOut, tags=["products"])
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Product).where(Product.sku == payload.sku))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"SKU '{payload.sku}' already exists")
    product = Product(**payload.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@app.patch("/products/{product_id}", response_model=ProductOut, tags=["products"])
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    return product


@app.get("/products/{product_id}", response_model=ProductOut, tags=["products"])
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# ── 批次匯入產品（Excel / CSV）────────────────────────────────
@app.post("/products/import", response_model=OKResponse, tags=["products"])
async def import_products(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    content = await file.read()
    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")

    required = {"sku", "name_en"}
    if not required.issubset({c.lower() for c in df.columns}):
        raise HTTPException(status_code=400, detail=f"Missing required columns: {required}")

    df.columns = [c.lower().strip() for c in df.columns]
    created, updated = 0, 0

    for _, row in df.iterrows():
        sku = str(row["sku"]).strip()
        if not sku:
            continue
        res = await db.execute(select(Product).where(Product.sku == sku))
        product = res.scalar_one_or_none()
        if product:
            product.name_en = str(row["name_en"])
            if "name_zh" in row and pd.notna(row["name_zh"]):
                product.name_zh = str(row["name_zh"])
            if "category" in row and pd.notna(row["category"]):
                product.category = str(row["category"])
            updated += 1
        else:
            product = Product(
                sku=sku,
                name_en=str(row["name_en"]),
                name_zh=str(row["name_zh"]) if "name_zh" in row and pd.notna(row.get("name_zh")) else None,
                category=str(row["category"]) if "category" in row and pd.notna(row.get("category")) else None,
            )
            db.add(product)
            created += 1

    await db.commit()
    return OKResponse(message=f"Imported: {created} created, {updated} updated")


# ══════════════════════════════════════════════════════════════
# 報價單
# ══════════════════════════════════════════════════════════════
@app.get("/price-lists", response_model=List[dict], tags=["price-lists"])
async def list_price_lists(
    supplier_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(PriceList, Supplier.name)
        .join(Supplier)
        .order_by(desc(PriceList.list_date))
    )
    if supplier_id:
        stmt = stmt.where(PriceList.supplier_id == supplier_id)
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "id": r[0].id,
            "supplier_id": r[0].supplier_id,
            "supplier_name": r[1],
            "list_date": r[0].list_date,
            "currency": r[0].currency,
            "item_count": 0,
            "created_at": r[0].created_at,
        }
        for r in rows
    ]


@app.post("/price-lists", response_model=dict, tags=["price-lists"])
async def create_price_list(
    payload: PriceListCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    pl = PriceList(
        supplier_id=payload.supplier_id,
        list_date=payload.list_date,
        currency=payload.currency,
        notes=payload.notes,
    )
    db.add(pl)
    await db.flush()

    skipped = []
    for item in payload.items:
        res = await db.execute(select(Product).where(Product.sku == item.sku))
        product = res.scalar_one_or_none()
        if not product:
            skipped.append(item.sku)
            continue
        pi = PriceItem(
            price_list_id=pl.id,
            product_id=product.id,
            unit_price=item.unit_price,
            moq=item.moq,
            notes=item.notes,
        )
        db.add(pi)

    await db.commit()
    return {"id": pl.id, "skipped_skus": skipped, "message": "Price list created"}


@app.get("/price-lists/{list_id}", tags=["price-lists"])
async def get_price_list(list_id: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(PriceList)
        .where(PriceList.id == list_id)
        .options(selectinload(PriceList.items).selectinload(PriceItem.product))
    )
    result = await db.execute(stmt)
    pl = result.scalar_one_or_none()
    if not pl:
        raise HTTPException(status_code=404, detail="Price list not found")

    sup = await db.get(Supplier, pl.supplier_id)
    return {
        "id": pl.id,
        "supplier_id": pl.supplier_id,
        "supplier_name": sup.name if sup else "",
        "list_date": pl.list_date,
        "currency": pl.currency,
        "notes": pl.notes,
        "created_at": pl.created_at,
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "sku": i.product.sku,
                "name_en": i.product.name_en,
                "name_zh": i.product.name_zh,
                "unit_price": i.unit_price,
                "moq": i.moq,
            }
            for i in pl.items
        ],
    }


# ── 匯入原廠報價 Excel ────────────────────────────────────────
@app.post("/price-lists/import-excel", response_model=dict, tags=["price-lists"])
async def import_price_list_excel(
    supplier_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    content = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel: {e}")

    df.columns = [c.lower().strip() for c in df.columns]
    if "sku" not in df.columns or "price" not in df.columns:
        raise HTTPException(status_code=400, detail="Excel must have 'sku' and 'price' columns")

    from datetime import datetime, timezone
    pl = PriceList(
        supplier_id=supplier_id,
        list_date=datetime.now(timezone.utc),
        notes=f"Imported from {file.filename}",
    )
    db.add(pl)
    await db.flush()

    created, skipped = 0, []
    for _, row in df.iterrows():
        sku = str(row["sku"]).strip()
        res = await db.execute(select(Product).where(Product.sku == sku))
        product = res.scalar_one_or_none()
        if not product:
            skipped.append(sku)
            continue
        pi = PriceItem(
            price_list_id=pl.id,
            product_id=product.id,
            unit_price=Decimal(str(row["price"])),
            moq=int(row["moq"]) if "moq" in row and pd.notna(row["moq"]) else 1,
        )
        db.add(pi)
        created += 1

    await db.commit()
    return {
        "price_list_id": pl.id,
        "items_created": created,
        "skipped_skus": skipped,
    }


# ══════════════════════════════════════════════════════════════
# 進口記帳
# ══════════════════════════════════════════════════════════════
@app.get("/imports", response_model=List[dict], tags=["imports"])
async def list_imports(
    supplier_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ImportRecord, Supplier.name)
        .join(Supplier)
        .order_by(desc(ImportRecord.import_date))
    )
    if supplier_id:
        stmt = stmt.where(ImportRecord.supplier_id == supplier_id)
    result = await db.execute(stmt)
    return [
        {
            "id": r[0].id,
            "supplier_name": r[1],
            "invoice_no": r[0].invoice_no,
            "import_date": r[0].import_date,
            "currency": r[0].currency,
            "total_foreign": r[0].total_foreign,
            "total_twd": r[0].total_twd,
        }
        for r in result.all()
    ]


@app.post("/imports", response_model=dict, tags=["imports"])
async def create_import(
    payload: ImportRecordCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rec = ImportRecord(
        supplier_id=payload.supplier_id,
        invoice_no=payload.invoice_no,
        import_declaration_no=payload.import_declaration_no,
        import_date=payload.import_date,
        currency=payload.currency,
        exchange_rate=payload.exchange_rate,
        freight_twd=payload.freight_twd,
        customs_twd=payload.customs_twd,
        other_cost_twd=payload.other_cost_twd,
        notes=payload.notes,
    )
    db.add(rec)
    await db.flush()

    total_foreign = Decimal("0")
    total_qty_value = Decimal("0")
    items_data = []

    for item in payload.items:
        res = await db.execute(select(Product).where(Product.sku == item.sku))
        product = res.scalar_one_or_none()
        if not product:
            continue
        line_foreign = item.unit_cost_foreign * item.qty
        total_foreign += line_foreign
        total_qty_value += item.unit_cost_foreign * item.qty
        items_data.append((product.id, item.qty, item.unit_cost_foreign))

    # 額外成本分攤（按比例）
    extra_twd = payload.freight_twd + payload.customs_twd + payload.other_cost_twd
    total_twd = total_foreign * payload.exchange_rate + extra_twd

    rec.total_foreign = total_foreign
    rec.total_twd = total_twd

    for product_id, qty, unit_cost_f in items_data:
        ratio = (unit_cost_f * qty / total_foreign) if total_foreign > 0 else Decimal("0")
        extra_alloc = extra_twd * ratio
        unit_cost_twd = (unit_cost_f * payload.exchange_rate + extra_alloc / qty) if qty > 0 else Decimal("0")
        ii = ImportItem(
            import_record_id=rec.id,
            product_id=product_id,
            qty=qty,
            unit_cost_foreign=unit_cost_f,
            unit_cost_twd=unit_cost_twd,
        )
        db.add(ii)

        # 更新庫存（移動平均成本法）
        inv_r = await db.execute(select(Inventory).where(Inventory.product_id == product_id))
        inv = inv_r.scalar_one_or_none()
        if inv:
            old_total = inv.avg_cost_twd * inv.qty_on_hand
            new_total = unit_cost_twd * qty
            inv.qty_on_hand += qty
            inv.avg_cost_twd = (old_total + new_total) / inv.qty_on_hand if inv.qty_on_hand > 0 else unit_cost_twd
        else:
            db.add(Inventory(
                product_id=product_id,
                qty_on_hand=qty,
                avg_cost_twd=unit_cost_twd,
            ))

    await db.commit()
    return {"import_record_id": rec.id, "total_twd": float(total_twd)}


@app.get("/imports/{record_id}", tags=["imports"])
async def get_import(record_id: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(ImportRecord)
        .where(ImportRecord.id == record_id)
        .options(selectinload(ImportRecord.items).selectinload(ImportItem.product))
    )
    result = await db.execute(stmt)
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Import record not found")

    sup = await db.get(Supplier, rec.supplier_id)
    return {
        "id": rec.id,
        "supplier_name": sup.name if sup else "",
        "invoice_no": rec.invoice_no,
        "import_declaration_no": rec.import_declaration_no,
        "import_date": rec.import_date,
        "currency": rec.currency,
        "exchange_rate": rec.exchange_rate,
        "total_foreign": rec.total_foreign,
        "total_twd": rec.total_twd,
        "freight_twd": rec.freight_twd,
        "customs_twd": rec.customs_twd,
        "other_cost_twd": rec.other_cost_twd,
        "notes": rec.notes,
        "items": [
            {
                "product_id": i.product_id,
                "sku": i.product.sku,
                "name_en": i.product.name_en,
                "name_zh": i.product.name_zh,
                "qty": i.qty,
                "unit_cost_foreign": i.unit_cost_foreign,
                "unit_cost_twd": i.unit_cost_twd,
            }
            for i in rec.items
        ],
    }


# ══════════════════════════════════════════════════════════════
# 庫存
# ══════════════════════════════════════════════════════════════
@app.get("/inventory", response_model=List[dict], tags=["inventory"])
async def list_inventory(
    q: Optional[str] = None,
    low_stock: Optional[int] = Query(None, description="低於此數量視為低庫存"),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Inventory, Product)
        .join(Product)
        .order_by(Product.sku)
    )
    if low_stock is not None:
        stmt = stmt.where(Inventory.qty_on_hand <= low_stock)
    result = await db.execute(stmt)
    rows = result.all()

    out = []
    for inv, prod in rows:
        if q:
            score = fuzz.WRatio(q, f"{prod.sku} {prod.name_en} {prod.name_zh or ''}")
            if score < 50:
                continue
        margin = None
        if inv.selling_price_twd and inv.avg_cost_twd and inv.avg_cost_twd > 0:
            margin = float((inv.selling_price_twd - inv.avg_cost_twd) / inv.selling_price_twd * 100)
        out.append({
            "product_id": prod.id,
            "sku": prod.sku,
            "name_en": prod.name_en,
            "name_zh": prod.name_zh,
            "qty_on_hand": inv.qty_on_hand,
            "avg_cost_twd": inv.avg_cost_twd,
            "selling_price_twd": inv.selling_price_twd,
            "margin_pct": round(margin, 1) if margin else None,
            "updated_at": inv.updated_at,
        })
    return out


@app.patch("/inventory/{product_id}", response_model=dict, tags=["inventory"])
async def update_inventory(
    product_id: int,
    payload: InventoryUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    inv_r = await db.execute(select(Inventory).where(Inventory.product_id == product_id))
    inv = inv_r.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory record not found")

    if payload.selling_price_twd is not None:
        inv.selling_price_twd = payload.selling_price_twd
    if payload.qty_adjust is not None:
        new_qty = inv.qty_on_hand + payload.qty_adjust
        if new_qty < 0:
            raise HTTPException(status_code=400, detail="Insufficient stock")
        inv.qty_on_hand = new_qty

    await db.commit()
    await db.refresh(inv)
    return {"product_id": product_id, "qty_on_hand": inv.qty_on_hand, "selling_price_twd": inv.selling_price_twd}
