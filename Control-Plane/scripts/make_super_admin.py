import asyncio
import sys
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.member import Member
from app.modules.admin.models import SuperAdmin

async def make_super_admin(email: str):
    async with AsyncSessionLocal() as db:
        # Find the member by email
        result = await db.execute(select(Member).where(Member.email == email))
        member = result.scalars().one_or_none()
        
        if not member:
            print(f"❌ Error: No user found with email '{email}'. Did you sign up yet?")
            return
            
        # Check if they are already a super admin
        admin_result = await db.execute(select(SuperAdmin).where(SuperAdmin.member_id == member.id))
        if admin_result.scalars().first():
            print(f"✅ {email} is already a Super Admin!")
            return
            
        # Promote them
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        new_admin = SuperAdmin(
            id=uuid.uuid4(),
            member_id=member.id,
            created_at=now
        )
        db.add(new_admin)
        await db.commit()
        
        print(f"🎉 Success! '{email}' has been promoted to Super Admin.")
        print("Refresh your browser to access the Admin Dashboard!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/make_super_admin.py <your_email>")
        sys.exit(1)
        
    email = sys.argv[1]
    asyncio.run(make_super_admin(email))
