import os
from dotenv import load_dotenv
load_dotenv()  # load .env before importing libraries that read env
from fastapi import FastAPI, UploadFile, Depends, HTTPException, Form
from sqlalchemy.exc import IntegrityError
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine, SessionLocal
from app.models import User, File
from app.auth import hash_password, verify, create_token
# from s3_service import s3, BUCKET
from fastapi import UploadFile
import cloudinary.uploader
import cloudinary.api

Base.metadata.create_all(bind=engine)
app = FastAPI()

# Configure CORS origins from env (comma-separated). Defaults to localhost dev origins.
allow_origins = os.getenv("ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
allow_origins = [o.strip() for o in allow_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/register")
def register(email: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    try:
        # check existing user
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        user = User(email=email, password=hash_password(password))
        db.add(user)
        db.commit()
        return {"message": "Registered"}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Registration failed: {e}")
    finally:
        db.close()

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user or not verify(password, user.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {"token": create_token({"sub": user.email})}
    finally:
        db.close()

@app.post("/upload")
async def upload(file: UploadFile):
    # ensure Cloudinary credentials exist
    if not (os.getenv("CLOUDINARY_URL") or (os.getenv("CLOUDINARY_API_KEY") and os.getenv("CLOUDINARY_API_SECRET") and os.getenv("CLOUDINARY_CLOUD_NAME"))):
        raise HTTPException(status_code=500, detail="Cloudinary API credentials not configured. Set CLOUDINARY_URL or CLOUDINARY_API_KEY/CLOUDINARY_API_SECRET/CLOUDINARY_CLOUD_NAME.")

    try:
        result = cloudinary.uploader.upload(file.file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cloudinary upload failed: {e}")

    return {
        "filename": file.filename,
        "url": result.get("secure_url")
    }

@app.get("/ping")
def ping():
    return {"status": "backend ok"}

@app.get("/files")
def list_files():
    result = cloudinary.api.resources(
        resource_type="raw",   # file thường
        max_results=50
    )

    return [
        {
            "name": f["public_id"],
            "url": f["secure_url"],
            "size": f["bytes"]
        }
        for f in result.get("resources", [])
    ]
