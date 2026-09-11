import asyncio
from sqlalchemy import select, text
from app.db.session import AsyncSessionLocal
from app.models.member import Member
from app.modules.admin.models import SuperAdmin

async def main():
    async with AsyncSessionLocal() as db:
        print("--- Super Admins ---")
        result = await db.execute(select(SuperAdmin))
        sas = result.scalars().all()
        for sa in sas:
            print(f"SA id: {sa.id}, member_id: {sa.member_id}, created: {sa.created_at}")

        print("--- Members ---")
        result = await db.execute(select(Member).where(Member.email == 'admin@admin.com'))
        admin = result.scalars().first()
        if admin:
            print(f"admin@admin.com -> id: {admin.id}, active: {admin.is_active}")
        else:
            print("admin@admin.com not found in members!")

asyncio.run(main())
