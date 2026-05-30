import asyncio
from sqlalchemy import select, update
from app.db.session import AsyncSessionLocal
from app.models.organization import Organization

async def dedupe():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Organization).order_by(Organization.created_at))
        orgs = result.scalars().all()
        
        seen_names = set()
        for org in orgs:
            if org.name in seen_names:
                new_name = f"{org.name}-{org.slug}"
                await db.execute(
                    update(Organization)
                    .where(Organization.id == org.id)
                    .values(name=new_name)
                )
                print(f"Renamed {org.name} to {new_name}")
                seen_names.add(new_name)
            else:
                seen_names.add(org.name)
        
        await db.commit()

if __name__ == "__main__":
    asyncio.run(dedupe())
