import os

script_dir = os.path.dirname(__file__)
router_path = os.path.join(script_dir, "..", "app", "modules", "admin", "router.py")

routes = """
# --- Products & Entitlements ---

@admin_router.get("/products", response_model=list[ProductResponse])
async def list_products(
    admin: Annotated[Member, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProductResponse]:
    \"\"\"List all registered products.\"\"\"
    result = await db.execute(select(Product).order_by(Product.name))
    return [ProductResponse.model_validate(r) for r in result.scalars().all()]

@admin_router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    admin: Annotated[Member, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: ProductCreate,
) -> ProductResponse:
    \"\"\"Create a new product.\"\"\"
    import uuid
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    prod = Product(
        id=uuid.uuid4(),
        name=body.name,
        product_key=body.product_key,
        description=body.description,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(prod)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Product key already exists")
    await log_admin_action(db, admin.id, "product.create", "product", prod.id)
    return ProductResponse.model_validate(prod)

@admin_router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    admin: Annotated[Member, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    product_id: UUID,
):
    \"\"\"Delete a product.\"\"\"
    result = await db.execute(select(Product).where(Product.id == product_id))
    prod = result.scalars().one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(prod)
    await db.commit()
    await log_admin_action(db, admin.id, "product.delete", "product", product_id)

@admin_router.post("/organizations/{org_id}/entitlements", response_model=AdminOrgResponse)
async def grant_entitlement(
    admin: Annotated[Member, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
    body: EntitlementGrantRequest,
) -> AdminOrgResponse:
    \"\"\"Grant an entitlement to an organization.\"\"\"
    # Verify product exists
    result = await db.execute(select(Product).where(Product.product_key == body.product_key))
    if not result.scalars().first():
        raise HTTPException(status_code=400, detail=f"Product key '{body.product_key}' does not exist")
        
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalars().one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    current = list(org.entitlements) if org.entitlements else []
    if body.product_key not in current:
        current.append(body.product_key)
        org.entitlements = current
        org.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        await log_admin_action(db, admin.id, "org.entitlement.grant", "organization", org_id, {"product_key": body.product_key})
        
    # Re-fetch for response
    return await update_organization(admin, db, org_id, AdminOrgUpdate())

@admin_router.delete("/organizations/{org_id}/entitlements/{product_key}", response_model=AdminOrgResponse)
async def revoke_entitlement(
    admin: Annotated[Member, Depends(require_platform_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
    product_key: str,
) -> AdminOrgResponse:
    \"\"\"Revoke an entitlement from an organization.\"\"\"
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalars().one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    current = list(org.entitlements) if org.entitlements else []
    if product_key in current:
        current.remove(product_key)
        org.entitlements = current
        org.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        await log_admin_action(db, admin.id, "org.entitlement.revoke", "organization", org_id, {"product_key": product_key})
        
    return await update_organization(admin, db, org_id, AdminOrgUpdate())
"""

with open(router_path, "a") as f:
    f.write(routes)
print("Routes appended!")
