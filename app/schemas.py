from pydantic import BaseModel, Field


class HomeRequest(BaseModel):
    budget: float = Field(..., gt=0, description="Total budget in currency units")
    room_type: str = Field(default="Living Room", description="Type of room to plan")
    style: str = Field(default="Modern Minimalist", description="Design style / aesthetic")
    room_size_sqft: float = Field(default=250.0, ge=20, description="Approximate room size in sq ft")
    priority: str = Field(default="Balanced", description="Budget priority focus area")
    notes: str = Field(default="", description="Additional preferences or constraints")


class PartyRequest(BaseModel):
    budget: float = Field(..., gt=0, description="Total budget in currency units")
    event_type: str = Field(default="Birthday Party", description="Type of celebration or event")
    guest_count: int = Field(default=20, ge=1, description="Number of guests")
    theme: str = Field(default="Elegant Evening", description="Party theme or vibe")
    venue_type: str = Field(default="Home / Indoor", description="Venue location type")
    priority: str = Field(default="Food & Drinks", description="Primary focus area")
    notes: str = Field(default="", description="Special dietary or guest requests")
