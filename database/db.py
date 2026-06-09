from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
from dotenv import load_dotenv

load_dotenv()
# DATABASE_URL = "postgresql://postgres:password@localhost:5432/my_fastapi_db"
DATABASE_URL = os.getenv("DATABASE_URL") 

engine=create_engine(DATABASE_URL)

Base=declarative_base()

db_session=sessionmaker(bind=engine,autoflush=False,autocommit=False)


def get_db():
    db=db_session()
    try:
        yield db
    finally:
        db.close()