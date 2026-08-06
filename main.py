from fastapi import FastAPI
import uvicorn
from database.db import Base, engine
from route import (user_route,admin_route,birth_registration_route, ward_route,ward_secretary_route,ward_chairperson_route,citizen_route,notice_route,certificate_router,
                   deat_registration_route,migration_registration_route,recommendation_router,complaint_route,data_validation_route,analytics_router,admin_analytics_router,                  tax_router)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os


app = FastAPI()
origins = [
    "http://localhost:5173",
    "https://eward-frontend-dmcz-git-fe-6275eb-rokayaabinash9-5771s-projects.vercel.app"
]
os.makedirs("static/wards", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
# Base.metadata.create_all(bind=engine)
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
app.include_router(ward_chairperson_route.router)
app.include_router(citizen_route.router)
app.include_router(notice_route.router)
app.include_router(ward_route.router)
app.include_router(certificate_router.router)
app.include_router(deat_registration_route.router)
app.include_router(migration_registration_route.router)
app.include_router(recommendation_router.router)
app.include_router(complaint_route.router)
app.include_router(data_validation_route.router)
app.include_router(analytics_router.router)
app.include_router(tax_router.router)
app.include_router(admin_analytics_router.router)


if __name__=="__main__":
    uvicorn.run("main:app",host="localhost",port=8000,reload=True)
    