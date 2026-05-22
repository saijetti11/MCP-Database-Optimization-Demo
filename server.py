# server.py

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from database import SessionLocal, engine
from models import Base
from models import Employee


# =========================================================
# LIFESPAN  — runs once on startup / shutdown
# =========================================================

@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """
    Create ONE shared DB session for the lifetime of the server.
    All optimized tools reuse this session instead of opening a new one.
    """

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    # =====================================================
    # SEED DATABASE IF EMPTY
    # =====================================================

    existing = db.query(Employee).count()

    if existing == 0:

        employees = [
            Employee(name="Sai", department="AI"),
            Employee(name="John", department="Backend"),
            Employee(name="Alice", department="DevOps"),
        ]

        db.add_all(employees)
        db.commit()

        print("✅ Sample employees inserted")

    else:
        print("✅ Database already seeded")


    try:
        yield {
            "db": db,
            "created_at": datetime.now().isoformat()
        }
    finally:
        db.close()


# =========================================================
# MCP SERVER
# =========================================================

mcp = FastMCP(
    "DB Optimization Demo",
    lifespan=lifespan
)