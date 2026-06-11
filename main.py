from fastapi import FastAPI
import uvicorn
# from database.db import Base, engine
from route import user_route

app = FastAPI()


# Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return {"message":"Hello World"}
@app.post("/users")
def create_user(user: dict):
    return {
        "message": "User created",#arp
        "user": user
    }

app.include_router(user_route.router)   

if __name__=="__main__":
    uvicorn.run("main:app",host="localhost",port=8000,reload=True)
    