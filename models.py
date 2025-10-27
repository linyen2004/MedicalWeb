# -*- coding: utf-8 -*-
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    blood_type = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    weight = Column(Integer, nullable=True)

    histories = relationship("History", back_populates="patient", cascade="all, delete-orphan")
    logs = relationship("Log", back_populates="patient", cascade="all, delete-orphan")
    requests = relationship("HomecareRequest", back_populates="patient", cascade="all, delete-orphan")
    emergencies = relationship("EmergencyEvent", back_populates="patient", cascade="all, delete-orphan")

class Doctor(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class History(Base):
    __tablename__ = "histories"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    patient = relationship("Patient", back_populates="histories")

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.now)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    patient = relationship("Patient", back_populates="logs")

class HomecareRequest(Base):
    __tablename__ = "homecare_requests"
    id = Column(Integer, primary_key=True, index=True)
    reason = Column(Text)
    status = Column(String, default="pending")
    requested_at = Column(DateTime, default=datetime.now)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    patient = relationship("Patient", back_populates="requests")

class EmergencyEvent(Base):
    __tablename__ = "emergency_events"
    id = Column(Integer, primary_key=True, index=True)
    event = Column(Text)
    status = Column(String, default="處理中")   # ✅ 重新輸入中文
    time = Column(DateTime, default=datetime.now)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    patient = relationship("Patient", back_populates="emergencies")


