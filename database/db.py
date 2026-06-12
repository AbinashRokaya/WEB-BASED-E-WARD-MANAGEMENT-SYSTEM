from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://eward_user:user123@localhost:5432/e_ward"
)

engine = create_engine(DATABASE_URL)

Base = declarative_base()

db_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = db_session()
    try:
        yield db
    finally:
        db.close()