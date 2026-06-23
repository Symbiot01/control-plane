import asyncio
import os
import sys

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.db.session import engine

async def run():
    async with engine.begin() as conn:
        print("Adding entitlements column to organizations table...")
        # Use IF NOT EXISTS equivalent logic by catching or checking, or just run it and ignore if it exists.
        # Postgres 9.6+ doesn't support IF NOT EXISTS on ADD COLUMN directly without plpgsql block if not 9.6+, wait, postgres 9.6+ does!
        try:
            await conn.execute(text("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS entitlements JSONB NOT NULL DEFAULT '[]'::jsonb;"))
            print("Successfully added entitlements column!")
        except Exception as e:
            print(f"Error (maybe it already exists?): {e}")

if __name__ == "__main__":
    asyncio.run(run())
