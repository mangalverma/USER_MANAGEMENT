from fastapi import FastAPI, HTTPException, Depends,BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import List, Optional,Union
from sqlalchemy import create_engine, Column, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
import databases
from uuid import uuid4
from passlib.context import CryptContext
import sqlalchemy
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials


# Database URL
# DATABASE_URL = "sqlite:///./test2.db"



# Environment variables for email configuration
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
# print(EMAIL_ADDRESS,EMAIL_PASSWORD)
# Database and metadata initialization
# database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

# SQLAlchemy setup
Base = declarative_base()
# engine = create_engine(DATABASE_URL)
# Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)


cred = credentials.Certificate(GOOGLE_APPLICATION_CREDENTIALS)
firebase_admin.initialize_app(cred)

db = firestore.Client()


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Define the User model
class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    first_name = Column(String, index=True)
    last_name = Column(String, index=True)
    email = Column(String, nullable=True,index=True,unique=True)
    project_id = Column(Text, nullable=True)
    phone_number = Column(String, nullable=True)
    company_name = Column(String, nullable=True)
    password = Column(String,nullable=True)
    hashtag = Column(String, nullable=True)


# Create the table in the database
# Base.metadata.create_all(bind=engine)

# FastAPI app instance
app = FastAPI()


# Define Pydantic models
class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    project_id: Optional[str] = None
    phone_number: Optional[str] = None
    company_name: Optional[str] = None
    hashtag: Optional[str] = None


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    project_id: Optional[str] = None
    phone_number: Optional[str] = None
    company_name: Optional[str] = None
    hashtag: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: Optional[EmailStr]
    project_id: Optional[str]
    phone_number: Optional[str]
    company_name: Optional[str]
    hashtag: Optional[str]

class Invitation(BaseModel):
    email: EmailStr
    subject: str
    message: str

def send_email(email: str, subject: str, message: str):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = email
        msg['Subject'] = subject

        msg.attach(MIMEText(message, 'plain'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Dependency to get the SQLAlchemy session
# def get_db():
#     db = Session()
#     try:
#         yield db
#     finally:
#         db.close()


# @app.on_event("startup")
# async def startup():
#     await database.connect()


# @app.on_event("shutdown")
# async def shutdown():
#     await database.disconnect()


# Helper function to hash passwords
def hash_password(password: Union[str,'None']) -> Union[str,None]:
    if password==None:
        return None
    return pwd_context.hash(password)


# Endpoint to create a new user
@app.post("/add_users", response_model=UserResponse)
async def create_user(user: UserCreate):
    # existing_user = db.execute(select(User).where(User.email == user.email)).scalar_one_or_none()
    # if existing_user:
    #     raise HTTPException(status_code=400, detail="Email is already registered")

    users_ref = db.collection("users")
    if user.email:
        query = users_ref.where("email", "==", user.email).stream()
        if any(query):
            raise HTTPException(status_code=400, detail="Email is already registered")

    user_id = str(uuid4())
    hashed_password = hash_password(user.password)
    # db_user = User(
    #     id=user_id,
    #     first_name=user.first_name,
    #     last_name=user.last_name,
    #     email=user.email,
    #     password=hashed_password,
    #     project_id=user.project_id,
    #     phone_number=user.phone_number,
    #     company_name=user.company_name,
    #     hashtag=user.hashtag,
    # )
    # db.add(db_user)
    # db.commit()
    # db.refresh(db_user)

    db_user = {
        "id":user_id,
        "first_name":user.first_name,
        "last_name":user.last_name,
        "email":user.email,
        "password":hashed_password,
        "project_id":user.project_id,
        "phone_number":user.phone_number,
        "company_name":user.company_name,
        "hashtag":user.hashtag,
    }
    db.collection("users").document(user_id).set(db_user)

    return db_user


# Endpoint to get user details
@app.get("/get_users", response_model=List[UserResponse])
async def get_users():
    # users = db.execute(select(User)).scalars().all()
    # return users
    users_ref = db.collection("users")
    docs = users_ref.stream()
    users = [doc.to_dict() for doc in docs]
    return users


# Endpoint to update user details
@app.patch("/update_users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, user_update: UserUpdate):
    # db_user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    # if db_user is None:
    #     raise HTTPException(status_code=404, detail="User not found")

    users_ref = db.collection("users").document(user_id)
    doc = users_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
    update_data = user_update.dict(exclude_unset=True)
    if 'password' in update_data:
        update_data['password'] = hash_password(update_data['password'])
    # for key, value in update_data.items():
    #     setattr(db_user, key, value)
    #
    # db.commit()
    # db.refresh(db_user)
    users_ref.update(update_data)
    updated_user = users_ref.get().to_dict()
    return updated_user
    # return db_user


# Endpoint to delete a user
@app.delete("/delete_users/{user_id}")
async def delete_user(user_id: str):
    # db_user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    # if db_user is None:
    #     raise HTTPException(status_code=404, detail="User not found")
    users_ref = db.collection("users").document(user_id)
    doc = users_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    # db.delete(db_user)
    # db.commit()
    users_ref.delete()
    return {"detail": "User deleted successfully"}

@app.post("/send_invite")
async def send_invitation(invitation: Invitation, background_tasks: BackgroundTasks):
    background_tasks.add_task(send_email, invitation.email, invitation.subject, invitation.message)
    return {"detail": "Invitation email has been sent"}


# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
