import asyncio
import os
import sys

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.db.session import engine

async def run():
    async with engine.begin() as conn:
        print("Creating products table...")
        sql1 = """
        CREATE TABLE IF NOT EXISTS products (
            id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            product_key TEXT UNIQUE NOT NULL,
            description TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );
        """
        sql2 = """
        CREATE INDEX IF NOT EXISTS idx_products_key ON products(product_key);
        """
        await conn.execute(text(sql1))
        await conn.execute(text(sql2))
        print("Successfully created products table!")

if __name__ == "__main__":
    asyncio.run(run())
