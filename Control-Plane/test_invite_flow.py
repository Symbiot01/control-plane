import asyncio
from uuid import uuid4
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.member import Member
from app.modules.admin.models import SuperAdmin
from app.schemas.invite import OrganizationInviteCreate
from app.modules.admin.router import create_organization_invite

async def test_invite_creation():
    async with AsyncSessionLocal() as db:
        # Find a super admin
        result = await db.execute(select(SuperAdmin))
        super_admin = result.scalars().first()
        
        if not super_admin:
            # Let's create a fake member and make them super admin for testing
            print("No super admin found, creating a test one...")
            member = Member(
                id=uuid4(), 
                email="test_super_admin@example.com", 
                firebase_uid="fake_uid_123"
            )
            db.add(member)
            await db.flush()
            super_admin = SuperAdmin(member_id=member.id)
            db.add(super_admin)
            await db.commit()
            
        # Get the actual Member object for the super admin
        member_result = await db.execute(select(Member).where(Member.id == super_admin.member_id))
        admin_member = member_result.scalars().one()
        
        print(f"Using Admin Member: {admin_member.email}")
        
        # Create the invite request body
        req_body = OrganizationInviteCreate(
            name="New Founder",
            email="new_founder@example.com",
            organization_id=None,
            plan_id=None,
            initial_credits=15000,
            role="owner",
            expiration_hours=72
        )
        
        print(f"\n--- Testing Invite Creation Endpoint Logic ---")
        # Call the endpoint logic directly (passing the dependencies manually)
        response = await create_organization_invite(admin_member, db, req_body)
        
        print(f"\n✅ SUCCESS!")
        print(f"Generated Invite ID: {response.id}")
        print(f"Invitee Email: {response.email}")
        print(f"Status: {response.status}")
        print(f"Invite URL: {response.invite_url}")

if __name__ == "__main__":
    asyncio.run(test_invite_creation())
