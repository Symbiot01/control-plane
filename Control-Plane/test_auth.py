import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.member import Member
from app.modules.admin.models import SuperAdmin

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Member).where(Member.email == 'admin@admin.com'))
        member = result.scalars().first()
        
        admin_result = await db.execute(select(SuperAdmin).where(SuperAdmin.member_id == member.id))
        sa = admin_result.scalars().first()
        if sa:
            print(f"User is superadmin! ID: {sa.id}")
            level_of_access = "super_admin"
        else:
            print("User is NOT superadmin!")
            level_of_access = "guest"
            
        print(f"Final level of access: {level_of_access}")

asyncio.run(main())
