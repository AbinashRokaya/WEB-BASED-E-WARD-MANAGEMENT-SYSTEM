from sqlalchemy import create_engine  # type: ignore
from sqlalchemy.orm import sessionmaker  # type: ignore
from sqlalchemy.ext.declarative import declarative_base  # type: ignore
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://eward_user:user123@localhost:5432/E_Ward") 

engine = create_engine(DATABASE_URL)

Base = declarative_base()

db_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db=db_session()
    try:
        yield db
    finally:
        db.close()


__all__ = ["Base", "db_session", "get_db", "engine"]