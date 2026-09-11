import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.member import Member
from app.modules.admin.models import SuperAdmin
from datetime import datetime

async def main():
    async with AsyncSessionLocal() as db:
        # Get all members
        result = await db.execute(select(Member))
        members = result.scalars().all()
        
        if not members:
            print("No members found in the database.")
            return

        print("Members found:")
        for m in members:
            print(f"- {m.email}")

        now = datetime.utcnow()
        for m in members:
            sa_check = await db.execute(select(SuperAdmin).where(SuperAdmin.member_id == m.id))
            if sa_check.scalars().first() is None:
                new_sa = SuperAdmin(member_id=m.id, created_at=now)
                db.add(new_sa)
                print(f"Made {m.email} a super admin.")
            else:
                print(f"{m.email} is already a super admin.")
        
        await db.commit()
        print("Done!")

asyncio.run(main())
