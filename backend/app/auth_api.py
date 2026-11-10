import os
import re
from datetime import date, datetime
from typing import Optional
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import String, Integer, Date, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from .main import Base, SessionLocal

router=APIRouter(prefix="/api/v2",tags=["account workspace"])

class UserProfile(Base):
    __tablename__="user_profiles"
    user_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    email:Mapped[Optional[str]]=mapped_column(String(320),nullable=True)
    data:Mapped[dict]=mapped_column(JSON,default=dict)
    updated_at:Mapped[datetime]=mapped_column(server_default=func.now(),onupdate=func.now())

class UserResume(Base):
    __tablename__="user_resumes"
    user_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    file_name:Mapped[str]=mapped_column(String(255))
    extracted_text:Mapped[str]=mapped_column(Text)
    skills:Mapped[list]=mapped_column(JSON,default=list)
    updated_at:Mapped[datetime]=mapped_column(server_default=func.now(),onupdate=func.now())

class UserApplication(Base):
    __tablename__="user_applications"
    id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True)
    user_id:Mapped[str]=mapped_column(String(128),index=True)
    company:Mapped[str]=mapped_column(String(200))
    role:Mapped[str]=mapped_column(String(300))
    status:Mapped[str]=mapped_column(String(30),default="Pending")
    platform:Mapped[str]=mapped_column(String(100),default="Manual")
    job_url:Mapped[Optional[str]]=mapped_column(String(2000),nullable=True)
    applied_date:Mapped[Optional[date]]=mapped_column(Date,nullable=True)
    follow_up_date:Mapped[Optional[date]]=mapped_column(Date,nullable=True)
    interview_date:Mapped[Optional[date]]=mapped_column(Date,nullable=True)
    notes:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(server_default=func.now())

class SavedCoverLetter(Base):
    __tablename__="saved_cover_letters"
    id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True)
    user_id:Mapped[str]=mapped_column(String(128),index=True)
    title:Mapped[str]=mapped_column(String(300))
    company:Mapped[str]=mapped_column(String(200),default="")
    role:Mapped[str]=mapped_column(String(300),default="")
    content:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(server_default=func.now())

async def current_user(authorization:Optional[str]=Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401,detail="Please sign in to continue.")
    base=os.getenv("SUPABASE_URL","").rstrip("/")
    key=os.getenv("SUPABASE_ANON_KEY","")
    if not base or not key:
        raise HTTPException(status_code=503,detail="Authentication is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY.")
    token=authorization.split(" ",1)[1].strip()
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response=await client.get(f"{base}/auth/v1/user",headers={"apikey":key,"Authorization":f"Bearer {token}"})
        if response.status_code!=200:
            raise HTTPException(status_code=401,detail="Your session expired. Please sign in again.")
        user=response.json()
        if not user.get("id"): raise HTTPException(status_code=401,detail="Invalid account session.")
        return {"id":user["id"],"email":user.get("email",""),"metadata":user.get("user_metadata",{})}
    except httpx.HTTPError:
        raise HTTPException(status_code=503,detail="Could not validate your account session.")

class ProfileInput(BaseModel):
    data:dict=Field(default_factory=dict)
class ResumeInput(BaseModel):
    file_name:str=Field(min_length=1,max_length=255)
    extracted_text:str=Field(min_length=40,max_length=30000)
    skills:list[str]=Field(default_factory=list,max_length=100)
class ApplicationInput(BaseModel):
    company:str=Field(min_length=1,max_length=200)
    role:str=Field(min_length=1,max_length=300)
    status:str=Field(default="Pending",max_length=30)
    platform:str=Field(default="Manual",max_length=100)
    job_url:Optional[str]=Field(default=None,max_length=2000)
    applied_date:Optional[date]=None
    follow_up_date:Optional[date]=None
    interview_date:Optional[date]=None
    notes:str=Field(default="",max_length=5000)
class CoverLetterInput(BaseModel):
    company:str=Field(default="",max_length=200)
    role:str=Field(min_length=1,max_length=300)
    job_description:str=Field(min_length=80,max_length=12000)
class CoverLetterEdit(BaseModel):
    content:str=Field(min_length=20,max_length=20000)

def app_json(r):
    return {"id":r.id,"company":r.company,"role":r.role,"status":r.status,"platform":r.platform,"job_url":r.job_url,
      "applied_date":r.applied_date.isoformat() if r.applied_date else None,
      "follow_up_date":r.follow_up_date.isoformat() if r.follow_up_date else None,
      "interview_date":r.interview_date.isoformat() if r.interview_date else None,"notes":r.notes,
      "created_at":r.created_at.isoformat() if r.created_at else None}

@router.get("/me")
def get_me(user=Depends(current_user)):
    with SessionLocal() as db:
        p=db.get(UserProfile,user["id"]);r=db.get(UserResume,user["id"])
        return {"user":{"id":user["id"],"email":user["email"]},"profile":p.data if p else {},
          "resume":{"file_name":r.file_name,"extracted_text":r.extracted_text,"skills":r.skills} if r else None}

@router.put("/profile")
def save_profile(payload:ProfileInput,user=Depends(current_user)):
    with SessionLocal() as db:
        p=db.get(UserProfile,user["id"])
        if p is None: p=UserProfile(user_id=user["id"],email=user["email"],data=payload.data);db.add(p)
        else: p.email=user["email"];p.data=payload.data
        db.commit()
        return {"saved":True,"profile":p.data}

@router.put("/resume")
def save_resume(payload:ResumeInput,user=Depends(current_user)):
    with SessionLocal() as db:
        r=db.get(UserResume,user["id"])
        if r is None: r=UserResume(user_id=user["id"],**payload.model_dump());db.add(r)
        else: r.file_name=payload.file_name;r.extracted_text=payload.extracted_text;r.skills=payload.skills
        db.commit()
        return {"saved":True,"file_name":r.file_name,"skills":r.skills,"extracted_text":r.extracted_text}

@router.get("/applications")
def list_apps(user=Depends(current_user)):
    with SessionLocal() as db:
        rows=db.query(UserApplication).filter_by(user_id=user["id"]).order_by(UserApplication.created_at.desc()).all()
        return {"applications":[app_json(r) for r in rows]}

@router.post("/applications")
def create_app(payload:ApplicationInput,user=Depends(current_user)):
    if payload.status not in {"Saved","Applied","Pending","Responded","Interview","Rejected","Offer","Withdrawn"}:
        raise HTTPException(status_code=422,detail="Unsupported application status.")
    with SessionLocal() as db:
        r=UserApplication(user_id=user["id"],**payload.model_dump());db.add(r);db.commit();db.refresh(r)
        return app_json(r)

@router.put("/applications/{app_id}")
def update_app(app_id:int,payload:ApplicationInput,user=Depends(current_user)):
    with SessionLocal() as db:
        r=db.query(UserApplication).filter_by(id=app_id,user_id=user["id"]).first()
        if not r: raise HTTPException(status_code=404,detail="Application not found.")
        for k,v in payload.model_dump().items(): setattr(r,k,v)
        db.commit();db.refresh(r)
        return app_json(r)

@router.delete("/applications/{app_id}")
def delete_app(app_id:int,user=Depends(current_user)):
    with SessionLocal() as db:
        r=db.query(UserApplication).filter_by(id=app_id,user_id=user["id"]).first()
        if not r: raise HTTPException(status_code=404,detail="Application not found.")
        db.delete(r);db.commit()
        return {"deleted":True}

@router.post("/cover-letters/generate")
def generate_letter(payload:CoverLetterInput,user=Depends(current_user)):
    with SessionLocal() as db:
        resume=db.get(UserResume,user["id"]);profile=db.get(UserProfile,user["id"])
        if not resume:
            raise HTTPException(status_code=400,detail="Upload and save your resume before creating a cover letter.")
        p=profile.data if profile else {}
        name=" ".join(x for x in [p.get("first_name","").strip(),p.get("last_name","").strip()] if x)
        name=name or (p.get("full_name") or user.get("metadata",{}).get("full_name") or "").strip() or "Your Name"
        contact=[p.get("email") or user.get("email",""),p.get("phone",""),p.get("linkedin_url",""),p.get("portfolio_url","")]
        contact_line=" | ".join(x.strip() for x in contact if isinstance(x,str) and x.strip())
        location=(p.get("location") or "").strip()
        skills=resume.skills or []
        jd=payload.job_description.lower()
        matching=[skill for skill in skills if skill.lower() in jd]
        relevant=matching[:6] if matching else skills[:5]
        if relevant:
            skill_phrase=", ".join(relevant)
            opening=(f"I am applying for the {payload.role} position"
                     +(f" at {payload.company}" if payload.company.strip() else "")
                     +f". My resume reflects hands-on experience with {skill_phrase}, which are relevant to this opportunity.")
        else:
            opening=(f"I am applying for the {payload.role} position"
                     +(f" at {payload.company}" if payload.company.strip() else "")
                     +". My professional background and project experience are described in the resume I have included.")
        summary=re.sub(r"\\s+"," ",str(p.get("experience_summary",""))).strip()
        if summary:
            experience=("My experience includes "+summary.rstrip(".")+"." )
        else:
            experience=("My resume provides further detail about the projects, responsibilities and results behind my technical background.")
        if matching:
            alignment=("I was particularly interested in the role's requirements around "+", ".join(matching[:5])+
                       ". These areas connect with skills already represented in my background, and I would welcome the chance to discuss specific examples.")
        else:
            alignment=("I have reviewed the responsibilities and qualifications in the job description. I would welcome the opportunity to explain how my experience and approach could support the team's needs.")
        closing=("Thank you for considering my application. I would appreciate the opportunity to discuss the role and how I could contribute.")
        header=[name]
        if location: header.append(location)
        if contact_line: header.append(contact_line)
        content="\\n".join(header)+"\\n\\nDear Hiring Manager,\\n\\n"+opening+"\\n\\n"+experience+"\\n\\n"+alignment+"\\n\\n"+closing+"\\n\\nSincerely,\\n"+name
        row=SavedCoverLetter(user_id=user["id"],title=f"{payload.role} — {payload.company.strip() or 'Cover Letter'}",
                             company=payload.company.strip(),role=payload.role,content=content)
        db.add(row);db.commit();db.refresh(row)
        return {"id":row.id,"title":row.title,"content":row.content,
                "notice":"Draft created using resume skills and the required job description. Review every detail before sending."}

@router.get("/cover-letters")
def list_letters(user=Depends(current_user)):
    with SessionLocal() as db:
        rows=db.query(SavedCoverLetter).filter_by(user_id=user["id"]).order_by(SavedCoverLetter.created_at.desc()).all()
        return {"cover_letters":[{"id":r.id,"title":r.title,"company":r.company,"role":r.role,"content":r.content} for r in rows]}

@router.put("/cover-letters/{letter_id}")
def update_letter(letter_id:int,payload:CoverLetterEdit,user=Depends(current_user)):
    with SessionLocal() as db:
        row=db.query(SavedCoverLetter).filter_by(id=letter_id,user_id=user["id"]).first()
        if not row: raise HTTPException(status_code=404,detail="Cover letter not found.")
        row.content=payload.content;db.commit();db.refresh(row)
        return {"saved":True,"id":row.id,"content":row.content}
