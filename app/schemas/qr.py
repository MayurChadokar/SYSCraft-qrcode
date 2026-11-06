from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator

QR_TYPES = Literal["url", "text", "email", "phone", "whatsapp", "wifi", "vcard", "sms", "location", "event", "product", "company", "custom"]

class Customization(BaseModel):
    foreground: str = "#111827"
    background: str = "#ffffff"
    size: int = Field(512, ge=256, le=2048)
    margin: int = Field(4, ge=4, le=16)
    error_correction: Literal["M", "Q", "H"] = "H"
    logo_id: str | None = None
    logo_scale: float = Field(0.18, ge=0.10, le=0.20)
    frame_text: str | None = Field(None, max_length=40)

    @field_validator("foreground", "background")
    @classmethod
    def valid_hex(cls, value: str):
        import re
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("Use a six-digit hex color")
        return value.lower()

class QRCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    qr_type: QR_TYPES
    content: str = Field(min_length=1, max_length=12000)
    customization: Customization = Field(default_factory=Customization)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str):
        if not value.strip():
            raise ValueError("QR content cannot be blank")
        return value

class QRUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=160)

class QRResponse(BaseModel):
    id: int
    name: str
    qr_type: str
    content: str
    customization: dict
    image_url: str
    created_at: datetime

