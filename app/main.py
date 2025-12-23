import os
from dotenv import load_dotenv
load_dotenv()  # load .env before importing libraries that read env
from fastapi import FastAPI, UploadFile, Depends, HTTPException, Form, Request
from sqlalchemy.exc import IntegrityError
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine, SessionLocal
from app.models import User, File
from app.auth import hash_password, verify, create_token, SECRET_KEY, ALGORITHM
from jose import jwt
from fastapi import status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials if credentials else None
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
    finally:
        db.close()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
# from s3_service import s3, BUCKET
from fastapi import UploadFile
import cloudinary.uploader
import cloudinary.api
import cloudinary.utils

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
async def register(request: Request, email: str = Form(None), password: str = Form(None)):
    # Accept form data, query params, or JSON body for flexibility
    if not email:
        email = request.query_params.get("email")
    if not password:
        password = request.query_params.get("password")

    # try JSON body if still missing
    if (not email or not password) and request.headers.get("content-type", "").startswith("application/json"):
        try:
            body = await request.json()
            if not email:
                email = body.get("email")
            if not password:
                password = body.get("password")
        except Exception:
            pass

    if not email or not password:
        raise HTTPException(status_code=422, detail=[{"loc": ["body"], "msg": "email and password required"}])

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
async def login(request: Request, email: str = Form(None), password: str = Form(None)):
    # Accept form data, query params, or JSON body
    if not email:
        email = request.query_params.get("email")
    if not password:
        password = request.query_params.get("password")

    if (not email or not password) and request.headers.get("content-type", "").startswith("application/json"):
        try:
            body = await request.json()
            if not email:
                email = body.get("email")
            if not password:
                password = body.get("password")
        except Exception:
            pass

    if not email or not password:
        raise HTTPException(status_code=422, detail=[{"loc": ["body"], "msg": "email and password required"}])

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user or not verify(password, user.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {"token": create_token({"sub": user.email})}
    finally:
        db.close()

@app.post("/upload")
async def upload(file: UploadFile, current_user: User = Depends(get_current_user)):
    # ensure Cloudinary credentials exist
    if not (os.getenv("CLOUDINARY_URL") or (os.getenv("CLOUDINARY_API_KEY") and os.getenv("CLOUDINARY_API_SECRET") and os.getenv("CLOUDINARY_CLOUD_NAME"))):
        raise HTTPException(status_code=500, detail="Cloudinary API credentials not configured. Set CLOUDINARY_URL or CLOUDINARY_API_KEY/CLOUDINARY_API_SECRET/CLOUDINARY_CLOUD_NAME.")

    try:
        # upload with resource_type='auto' so images and other file types are handled
        result = cloudinary.uploader.upload(file.file, resource_type="auto")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cloudinary upload failed: {e}")

    # Persist a simple record in the DB for visibility (owner_id left null)
    try:
        db = SessionLocal()
        public_id = result.get("public_id") or file.filename
        secure_url = result.get("secure_url")
        f = File(filename=public_id, size=float(result.get("bytes") or 0.0), url=secure_url, owner_id=current_user.id)
        db.add(f)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        try:
            db.close()
        except Exception:
            pass

    return {
        "filename": file.filename,
        "url": result.get("secure_url")
    }

@app.get("/ping")
def ping():
    return {"status": "backend ok"}

@app.get("/files")
def list_files(current_user: User = Depends(get_current_user), q: str = None, sort: str = None):
    # list all resource types (images, raw files, etc.) by using 'auto'
    # Prefer returning DB-stored records (most reliable URLs). If DB has none, query Cloudinary.
    try:
        db = SessionLocal()
        query = db.query(File).filter(File.owner_id == current_user.id)
        if q:
            # case-insensitive search on filename
            try:
                query = query.filter(File.filename.ilike(f"%{q}%"))
            except Exception:
                # fallback to simple contains
                query = query.filter(File.filename.contains(q))

        # sorting
        if sort == "size":
            query = query.order_by(File.size.desc())
        elif sort == "oldest":
            query = query.order_by(File.id.asc())
        else:
            query = query.order_by(File.id.desc())

        files = query.all()
        if files:
            out = []
            for f in files:
                out.append({
                    "id": f.id,
                    "name": f.filename,
                    "url": f.url,
                    "size": f.size
                })
            return out
    except Exception as db_e:
        # if DB read fails, continue to try Cloudinary API
        pass
    finally:
        try:
            db.close()
        except Exception:
            pass

    # DB empty or failed — query Cloudinary directly
    try:
        result = cloudinary.api.resources(
            resource_type="auto",
            max_results=50
        )
        resources = result.get("resources", [])
        return [
            {
                "id": None,
                "name": f["public_id"],
                "url": f.get("secure_url"),
                "size": f.get("bytes")
            }
            for f in resources
        ]
    except Exception as e:
        # If Cloudinary listing fails and DB fallback also unavailable, return empty list
        return []
