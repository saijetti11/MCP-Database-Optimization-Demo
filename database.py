from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import sys
from dotenv import load_dotenv

from models import Base

# Load environment variables from .env file
load_dotenv()

# Get DATABASE_URL from .env file
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:1234@localhost:5432/mcp_db"
)

# Print to stderr to not interfere with MCP protocol
print(f"📊 Using database: {DATABASE_URL}", file=sys.stderr)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)


def init_db():

    Base.metadata.create_all(bind=engine)