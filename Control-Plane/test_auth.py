import asyncio
from app.db.session import async_session_maker
from app.modules.auth.router import get_or_create_member

async def main():
    async with async_session_maker() as db:
        try:
            member = await get_or_create_member(
                db, 
                firebase_uid="test_uid_new_123",
                email="test_new_123@example.com",
                display_name="Test Name"
            )
            print(f"Created member: {member.id}")
            
            # Now let's try to simulate what happens in auth_exchange
            from app.models.organization_member import OrganizationMember
            from sqlalchemy import select
            result = await db.execute(
                select(OrganizationMember)
                .where(OrganizationMember.member_id == member.id)
                .limit(1)
            )
            row = result.scalars().first()
            if row:
                org_id = str(row.organization_id)
                level_of_access = row.role
            else:
                org_id = None
                level_of_access = "guest"
            print(f"Org ID: {org_id}, Access: {level_of_access}")
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
