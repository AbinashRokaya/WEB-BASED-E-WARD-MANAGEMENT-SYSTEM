from fastapi import FastAPI
import uvicorn
from database.db import Base, engine
from route import user_route,admin_route,birth_registration_route,ward_secretary_route
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
origins = [
    "http://localhost:5173",
   
]
Base.metadata.create_all(bind=engine)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return {"message":"Hello World"}


app.include_router(user_route.router)
app.include_router(admin_route.router)    
app.include_router(birth_registration_route.router)
app.include_router(ward_secretary_route.router)

if __name__=="__main__":
    uvicorn.run("main:app",host="localhost",port=8000,reload=True)
    