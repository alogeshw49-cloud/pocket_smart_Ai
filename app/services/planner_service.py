import json
import logging
import time
from pathlib import Path
from PIL import Image
from ..config import settings

logger = logging.getLogger(__name__)

_last_quota_error_time = 0.0


def is_quota_limited() -> bool:
    global _last_quota_error_time
    # If 429 quota exhaustion occurred within last 180s, bypass direct API calls to prevent UI delays
    return (time.time() - _last_quota_error_time) < 180.0


def record_quota_error():
    global _last_quota_error_time
    _last_quota_error_time = time.time()


# Initialize GenAI Client if API key is present
def get_genai_client():
    if not settings.GEMINI_API_KEY:
        return None
    try:
        from google import genai
        return genai.Client(api_key=settings.GEMINI_API_KEY)
    except Exception as e:
        logger.warning(f"Could not initialize GenAI client: {e}")
        return None



def _clean_json_response(raw_text: str) -> dict | None:
    """Extract and parse JSON from model output that might contain markdown blocks."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except Exception:
        # Try finding the first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass
    return None


# =====================================================================
# 1. HOME PLANNER
# =====================================================================

def generate_home(data: dict) -> dict:
    budget = float(data.get("budget", 1000.0))
    room_type = data.get("room_type", "Living Room")
    style = data.get("style", "Modern Minimalist")
    room_size_sqft = data.get("room_size_sqft", 250.0)
    priority = data.get("priority", "Balanced")
    notes = data.get("notes", "")

    client = get_genai_client()
    if client and not is_quota_limited():
        try:
            prompt = f"""You are an elite interior designer and financial strategist for PocketSmart AI.
Generate a comprehensive, realistic, and budget-optimized interior design plan for the following project:
- Room Type: {room_type}
- Aesthetic Style: {style}
- Room Size: {room_size_sqft} sq ft
- Total Budget: ${budget:,.2f}
- Primary Focus/Priority: {priority}
- Client Notes/Preferences: {notes or 'None'}

Return ONLY a valid JSON object matching exactly this structure:
{{
  "title": "Short descriptive title of the room design concept",
  "summary": "2-3 sentences explaining the overarching vision, color palette, and smart budget strategy.",
  "total_budget": {budget},
  "estimated_total": (float, <= {budget} with a small safety buffer),
  "savings_buffer": (float, total_budget - estimated_total),
  "currency": "$",
  "categories": [
    {{
      "name": "Category name (e.g. Core Furniture & Seating, Ambient & Task Lighting, Textiles & Rugs, Wall Styling & Art)",
      "allocated_budget": (float),
      "percentage": (percentage of budget, e.g. 45),
      "items": [
        {{
          "name": "Item name (e.g. Bouclé Accent Armchair, Low-Profile Oak Media Console)",
          "estimated_cost": (float),
          "priority": "Must Have" or "Recommended" or "Luxury Upgrade",
          "description": "Specific styling guidance and materials to look for.",
          "smart_tip": "Where to buy, budget-friendly dupe advice, or thrifting tip."
        }}
      ]
    }}
  ],
  "ai_tips": [
    "Smart money-saving tip 1",
    "Design hack 2",
    "Lighting/spatial optimization tip 3"
  ],
  "timeline_or_phases": [
    "Phase 1: Measurement, decluttering & color palette selection",
    "Phase 2: Sourcing core anchor furniture pieces",
    "Phase 3: Layering ambient lighting and textured textiles",
    "Phase 4: Styling accents, artwork and botanical elements"
  ]
}}
Do NOT include markdown formatting outside the JSON."""

            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt
            )
            parsed = _clean_json_response(response.text)
            if parsed and "categories" in parsed and parsed["categories"]:
                return parsed
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                record_quota_error()
            logger.error(f"Gemini generate_home failed, falling back to algorithmic planner: {e}")

    # Fallback Algorithmic Planner
    c1_pct, c2_pct, c3_pct, c4_pct = 0.45, 0.20, 0.20, 0.10
    total_est = round(budget * 0.95, 2)
    buffer = round(budget - total_est, 2)

    cat1_budget = round(total_est * c1_pct, 2)
    cat2_budget = round(total_est * c2_pct, 2)
    cat3_budget = round(total_est * c3_pct, 2)
    cat4_budget = round(total_est * c4_pct, 2)

    return {
        "title": f"{style} {room_type} Design Plan",
        "summary": f"A balanced, high-impact {style.lower()} concept tailored for a {room_size_sqft} sq ft {room_type.lower()}, prioritizing durable focal pieces with budget-conscious aesthetic accents.",
        "total_budget": budget,
        "estimated_total": total_est,
        "savings_buffer": buffer,
        "currency": "$",
        "categories": [
            {
                "name": "Core Anchor Furniture",
                "allocated_budget": cat1_budget,
                "percentage": 45,
                "items": [
                    {
                        "name": f"Primary {room_type} Centerpiece (Sofa / Bed / Table)",
                        "estimated_cost": round(cat1_budget * 0.70, 2),
                        "priority": "Must Have",
                        "description": f"Durable, neutral-toned focal piece in {style.lower()} silhouette with stain-resistant fabric or solid wood framing.",
                        "smart_tip": "Invest here for longevity; look for solid hardwood frames and timeless neutral tones."
                    },
                    {
                        "name": "Complementary Accent Seating / Storage",
                        "estimated_cost": round(cat1_budget * 0.30, 2),
                        "priority": "Recommended",
                        "description": "Slim-profile accent piece that enhances circulation and provides functional surface area.",
                        "smart_tip": "Shop mid-season sales or outlet stores for design-forward accent chairs."
                    }
                ]
            },
            {
                "name": "Lighting & Electrical Ambiance",
                "allocated_budget": cat2_budget,
                "percentage": 20,
                "items": [
                    {
                        "name": "Sculptural Floor / Pendant Fixture",
                        "estimated_cost": round(cat2_budget * 0.60, 2),
                        "priority": "Recommended",
                        "description": f"Statement light source matching {style.lower()} finishes with warm 2700K illumination.",
                        "smart_tip": "A striking lighting fixture acts as functional jewelry for the ceiling and elevates budget furniture."
                    },
                    {
                        "name": "Dimmable Task / Ambient Table Lamps",
                        "estimated_cost": round(cat2_budget * 0.40, 2),
                        "priority": "Must Have",
                        "description": "Pair of accent lamps to eliminate harsh overhead glare and create multi-layered evening ambiance.",
                        "smart_tip": "Use smart warm-dimming LED bulbs to transform room moods seamlessly."
                    }
                ]
            },
            {
                "name": "Rugs, Curtains & Soft Textiles",
                "allocated_budget": cat3_budget,
                "percentage": 20,
                "items": [
                    {
                        "name": f"Textured Area Rug ({'8x10' if room_size_sqft >= 200 else '5x8'})",
                        "estimated_cost": round(cat3_budget * 0.65, 2),
                        "priority": "Must Have",
                        "description": "High-durability low-pile or flatweave rug grounding the seating arrangement.",
                        "smart_tip": "Ensure the front legs of all furniture sit on the rug to visually expand the room."
                    },
                    {
                        "name": "Floor-to-Ceiling Drapery Panels",
                        "estimated_cost": round(cat3_budget * 0.35, 2),
                        "priority": "Recommended",
                        "description": "Linen-blend curtains hung high and wide to visually double the perceived ceiling height.",
                        "smart_tip": "Mount the curtain rod 4-6 inches above the window frame for an instant luxury feel."
                    }
                ]
            },
            {
                "name": "Wall Art, Mirrors & Botanical Accents",
                "allocated_budget": cat4_budget,
                "percentage": 10,
                "items": [
                    {
                        "name": "Large Framed Statement Canvas or Gallery Set",
                        "estimated_cost": round(cat4_budget * 0.60, 2),
                        "priority": "Recommended",
                        "description": f"Artwork embracing the {style.lower()} color story to anchor blank walls.",
                        "smart_tip": "Print oversized downloadable digital art and frame in budget IKEA Ribba or Ribba dupes."
                    },
                    {
                        "name": "Indoor Plants & Organic Ceramic Planters",
                        "estimated_cost": round(cat4_budget * 0.40, 2),
                        "priority": "Must Have",
                        "description": "Low-maintenance architectural greenery (Monstera, Fiddle Leaf, or Snake Plant).",
                        "smart_tip": "Foliage injects immediate life and oxygen into interior photography and everyday living."
                    }
                ]
            }
        ],
        "ai_tips": [
            f"Stick to the 60-30-10 color rule for {style}: 60% dominant neutral, 30% secondary texture, 10% bold accent.",
            "Avoid matching furniture sets; mix materials (wood, matte black metal, linen) for a custom designer look.",
            "Always anchor lighting at 3 distinct heights: ceiling overhead, eye-level sconce/lamp, and low accent."
        ],
        "timeline_or_phases": [
            "Week 1: Paint walls, deep clean, and order large rug + anchor furniture.",
            "Week 2: Assemble anchor piece, install light fixtures, and hang drapery rods.",
            "Week 3: Arrange accent seating, position lighting, and layer soft cushions.",
            "Week 4: Finalize gallery wall, position live greenery, and style surfaces."
        ]
    }


# =====================================================================
# 2. PARTY PLANNER
# =====================================================================

def generate_party(data: dict) -> dict:
    budget = float(data.get("budget", 800.0))
    event_type = data.get("event_type", "Birthday Party")
    guest_count = int(data.get("guest_count", 20))
    theme = data.get("theme", "Casual Elegance")
    venue_type = data.get("venue_type", "Home / Indoor")
    priority = data.get("priority", "Food & Drinks")
    notes = data.get("notes", "")

    per_person = round(budget / max(1, guest_count), 2)

    client = get_genai_client()
    if client and not is_quota_limited():
        try:
            prompt = f"""You are a master event producer and budget architect for PocketSmart AI.
Design a spectacular party budget allocation and planning roadmap for:
- Event Type: {event_type}
- Guest Count: {guest_count} people (~${per_person:.2f}/person budget)
- Theme/Vibe: {theme}
- Venue: {venue_type}
- Total Budget: ${budget:,.2f}
- Core Priority: {priority}
- Client Notes: {notes or 'None'}

Return ONLY a valid JSON object matching exactly this structure:
{{
  "title": "Creative Event Name / Concept",
  "summary": "2-3 sentences describing the guest experience, flow of the event, and smart budget distribution.",
  "total_budget": {budget},
  "estimated_total": (float, <= {budget}),
  "savings_buffer": (float, total_budget - estimated_total),
  "currency": "$",
  "categories": [
    {{
      "name": "Category name (e.g. Catering & Specialty Bites, Bar & Signature Drinks, Decor & Ambiance, Music & Guest Experience)",
      "allocated_budget": (float),
      "percentage": (percentage of budget),
      "items": [
        {{
          "name": "Item or Service name",
          "estimated_cost": (float),
          "priority": "Must Have" or "Recommended" or "Luxury Upgrade",
          "description": "Specific quantities, flavor profiles, or styling advice.",
          "smart_tip": "Cost-saving bulk trick, DIY recipe, or sourcing tip."
        }}
      ]
    }}
  ],
  "ai_tips": [
    "Party flow tip 1",
    "Budget beverage or catering hack 2",
    "Music/lighting atmosphere tip 3"
  ],
  "timeline_or_phases": [
    "2 Weeks Before: Invitations, RSVP tracking, playlist curation",
    "3 Days Before: Bulk grocery and beverage procurement",
    "1 Day Before: Food prep, styling bar setup, charging audio gear",
    "Party Day (H-3 Hours): Ice, fresh florals, warm lighting & temperature check"
  ]
}}
Do NOT include markdown formatting outside the JSON."""

            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt
            )
            parsed = _clean_json_response(response.text)
            if parsed and "categories" in parsed and parsed["categories"]:
                return parsed
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                record_quota_error()
            logger.error(f"Gemini generate_party failed, falling back to algorithmic planner: {e}")

    # Fallback Algorithmic Planner
    total_est = round(budget * 0.94, 2)
    buffer = round(budget - total_est, 2)

    cat1_budget = round(total_est * 0.45, 2)  # Food & Catering
    cat2_budget = round(total_est * 0.25, 2)  # Beverages & Bar
    cat3_budget = round(total_est * 0.18, 2)  # Decor & Atmosphere
    cat4_budget = round(total_est * 0.12, 2)  # Entertainment & Amenities

    return {
        "title": f"{theme} {event_type}",
        "summary": f"An unforgettable {event_type.lower()} curated for {guest_count} guests (${per_person}/guest). Focused on self-serve grazing stations, bespoke signature drinks, and moody ambient lighting that maximize vibe without catering markup.",
        "total_budget": budget,
        "estimated_total": total_est,
        "savings_buffer": buffer,
        "currency": "$",
        "categories": [
            {
                "name": "Artisanal Catering & Grazing Station",
                "allocated_budget": cat1_budget,
                "percentage": 45,
                "items": [
                    {
                        "name": f"Curated Charcuterie & Mezze Grazing Table (for {guest_count})",
                        "estimated_cost": round(cat1_budget * 0.60, 2),
                        "priority": "Must Have",
                        "description": "Abundant display of aged cheeses, cured meats, artisan crackers, grapes, figs, nuts, and marinated olives.",
                        "smart_tip": "Buy cheeses and nuts in bulk at warehouse clubs like Costco/Sam's Club for 50% savings."
                    },
                    {
                        "name": "Hot Specialty Sliders / Skewers & Warm Hors d'oeuvres",
                        "estimated_cost": round(cat1_budget * 0.40, 2),
                        "priority": "Must Have",
                        "description": "Satisfying savory handhelds (e.g., pulled brisket sliders, caprese skewers, glazed chicken bites).",
                        "smart_tip": "Prep skewers in advance; bake in batches so food stays piping hot throughout the evening."
                    }
                ]
            },
            {
                "name": "Beverages & Signature Cocktail Bar",
                "allocated_budget": cat2_budget,
                "percentage": 25,
                "items": [
                    {
                        "name": "Signature Batch Cocktail / Mocktail Station",
                        "estimated_cost": round(cat2_budget * 0.60, 2),
                        "priority": "Must Have",
                        "description": "Large beverage dispenser with a handcrafted punch (e.g. Rosemary Grapefruit Spritz or Spiced Sangria) with botanical garnishes.",
                        "smart_tip": "Batch cocktails prevent long bar queues and drastically cut per-drink liquor costs."
                    },
                    {
                        "name": "Chilled Sparkling Wine, Craft Beers & Seltzers + Garnishes",
                        "estimated_cost": round(cat2_budget * 0.40, 2),
                        "priority": "Recommended",
                        "description": "Crisp Prosecco/Cava, craft IPA assortment, and sparkling mineral waters with fresh citrus slices.",
                        "smart_tip": "Prosecco or Cava delivers Champagne aesthetics at a fraction of the cost."
                    }
                ]
            },
            {
                "name": "Themed Decor, Florals & Tabletop Styling",
                "allocated_budget": cat3_budget,
                "percentage": 18,
                "items": [
                    {
                        "name": "Botanical Runners & Accent Votive Candles",
                        "estimated_cost": round(cat3_budget * 0.60, 2),
                        "priority": "Must Have",
                        "description": "Fresh eucalyptus branches running down tables interspersed with warm tea lights and pillar candles.",
                        "smart_tip": "Trader Joe's or local farmers markets offer lush greenery bunches at unbeatable prices."
                    },
                    {
                        "name": "Premium Compostable Dinnerware & Linen Napkins",
                        "estimated_cost": round(cat3_budget * 0.40, 2),
                        "priority": "Recommended",
                        "description": "Heavyweight bamboo plates, gold-accent cutlery, and heavyweight linen-feel paper napkins.",
                        "smart_tip": "Palm leaf or bamboo plates feel upscale and eliminate cleanup stress."
                    }
                ]
            },
            {
                "name": "Music, Photo Corner & Guest Experience",
                "allocated_budget": cat4_budget,
                "percentage": 12,
                "items": [
                    {
                        "name": "Custom DIY Backlit Photo Vignette",
                        "estimated_cost": round(cat4_budget * 0.60, 2),
                        "priority": "Recommended",
                        "description": "Warm fairy curtain lights, simple fabric drape, and themed mini instant camera or smartphone tripod.",
                        "smart_tip": "A designated photo area with flattering warm lighting encourages social media sharing."
                    },
                    {
                        "name": "High-Fidelity Curated Sound & Ambiance",
                        "estimated_cost": round(cat4_budget * 0.40, 2),
                        "priority": "Must Have",
                        "description": "Continuous 4-hour curated playlist transitioning from lounge beats to energetic celebration tempos.",
                        "smart_tip": "Crossfade songs by 6 seconds in Spotify settings for a seamless DJ-like music flow."
                    }
                ]
            }
        ],
        "ai_tips": [
            "Calculate 1.5 drinks per person for the first hour, and 1 drink per person for each subsequent hour.",
            "Dim the main overhead lights 30 minutes before arrival and illuminate with 10+ soft candlelight points.",
            "Keep food stations separated from the drink station to encourage natural guest mingling."
        ],
        "timeline_or_phases": [
            "T-10 Days: Finalize headcounts and order specialty napkins and batch cocktail ingredients.",
            "T-2 Days: Build Spotify playlist, chill sparkling wines, and buy dry groceries.",
            "T-1 Day: Pre-slice cheeses, bake sliders/bites base, and set up bar table.",
            "Event Day (2h before): Assemble grazing board, light candles, and cue opening playlist."
        ]
    }


# =====================================================================
# 3. JEWELRY & STYLING PLANNER
# =====================================================================

def generate_jewelry(data: dict, image_path: Path | None = None) -> dict:
    budget = float(data.get("budget", 500.0))
    occasion = data.get("occasion", "Wedding")
    style = data.get("style", "Elegant & Timeless")
    outfit_color = data.get("outfit_color", "")
    notes = data.get("notes", "")

    client = get_genai_client()
    if client and not is_quota_limited():
        try:
            prompt = f"""You are a celebrity fashion stylist and luxury jewelry advisor for PocketSmart AI.
Analyze the user's styling request and provide a high-end jewelry curation and budget breakdown:
- Occasion: {occasion}
- Style Aesthetic: {style}
- Outfit Color / Description: {outfit_color or 'Not specified'}
- Total Jewelry Budget: ${budget:,.2f}
- Extra Notes: {notes or 'None'}

Return ONLY a valid JSON object matching exactly this structure:
{{
  "title": "Styling & Jewelry Curation Concept",
  "summary": "2-3 sentences analyzing how the jewelry complements the neckline, color, and occasion with high aesthetic polish.",
  "total_budget": {budget},
  "estimated_total": (float, <= {budget}),
  "savings_buffer": (float, total_budget - estimated_total),
  "currency": "$",
  "outfit_analysis": "Detailed assessment of the outfit color harmony and recommended metals.",
  "metal_recommendation": "e.g. 14k-18k Yellow Gold, Platinum, Rose Gold, or Silver Vermeil",
  "gemstone_or_finish": "e.g. Freshwater Baroque Pearls, Moissanite, Lab Emeralds, or Polished High-Sheen Metal",
  "styling_verdict": "One golden styling rule for this look.",
  "categories": [
    {{
      "name": "Category name (e.g. Primary Focal Piece, Harmonizing Secondary Jewelry, Accent Rings & Bangles, Finishing Accessories)",
      "allocated_budget": (float),
      "percentage": (percentage of budget),
      "items": [
        {{
          "name": "Jewelry piece name",
          "estimated_cost": (float),
          "priority": "Must Have" or "Recommended" or "Luxury Upgrade",
          "description": "Specific cut, setting, dimensions, and styling notes.",
          "smart_tip": "Metal purity advice, lab-grown vs natural tip, or ethical sourcing recommendation."
        }}
      ]
    }}
  ],
  "ai_tips": [
    "Neckline jewelry pairing rule",
    "Metal longevity and allergy guidance",
    "Day-to-night styling transition hack"
  ],
  "timeline_or_phases": [
    "Step 1: Choose the single hero piece (Earrings vs Necklace) based on the garment neckline",
    "Step 2: Balance wrist and hand accents on the non-dominant or clutch hand",
    "Step 3: Test jewelry under event lighting and ensure clasps are secure"
  ]
}}
Do NOT include markdown formatting outside the JSON."""

            contents = [prompt]
            if image_path and image_path.exists():
                try:
                    pil_img = Image.open(image_path)
                    contents.append(pil_img)
                    prompt += "\n\nCRITICAL: An image of the outfit/garment is attached above. Inspect the fabric color, silhouette, neckline, and texture closely, and tailor the jewelry recommendation precisely to match!"
                except Exception as img_err:
                    logger.warning(f"Could not load image for Gemini: {img_err}")

            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=contents
            )
            parsed = _clean_json_response(response.text)
            if parsed and "categories" in parsed and parsed["categories"]:
                return parsed
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                record_quota_error()
            logger.error(f"Gemini generate_jewelry failed, falling back to algorithmic planner: {e}")

    # Fallback Algorithmic Planner
    total_est = round(budget * 0.95, 2)
    buffer = round(budget - total_est, 2)

    cat1_budget = round(total_est * 0.50, 2)  # Hero piece (Earrings or Necklace)
    cat2_budget = round(total_est * 0.30, 2)  # Secondary piece
    cat3_budget = round(total_est * 0.20, 2)  # Rings & Delicate details

    metal_rec = "14K Solid Yellow Gold or Vermeil" if "warm" in outfit_color.lower() or "red" in outfit_color.lower() or "cream" in outfit_color.lower() or "gold" in outfit_color.lower() else "White Gold, Platinum, or Rhodium-Plated Sterling Silver"

    return {
        "title": f"{style} {occasion} Jewelry Ensemble",
        "summary": f"A regal, light-catching jewelry curation designed for {occasion.lower()}. Harmonizes {outfit_color or 'your chosen outfit'} with radiant {metal_rec.lower()}, focusing budget on one breathtaking hero piece to keep the look effortless.",
        "total_budget": budget,
        "estimated_total": total_est,
        "savings_buffer": buffer,
        "currency": "$",
        "outfit_analysis": f"For {outfit_color or 'this ensemble'} worn to a {occasion.lower()}, metallic warmth and sparkling accents elevate the silhouette without competing with fabric detailing.",
        "metal_recommendation": metal_rec,
        "gemstone_or_finish": "Lab-Grown Diamond Solitaires, Akoya Pearls, or Mirror-Polish Lustre",
        "styling_verdict": "Highlight either the neckline OR the ears with statement scale—never compete both at equal volume.",
        "categories": [
            {
                "name": "Statement Hero Piece",
                "allocated_budget": cat1_budget,
                "percentage": 50,
                "items": [
                    {
                        "name": f"Architectural Chandelier or Drop Earrings ({metal_rec})",
                        "estimated_cost": round(cat1_budget * 0.70, 2),
                        "priority": "Must Have",
                        "description": "Elongated drop design framing the jawline, featuring bezel-set sparkling crystals or cultured freshwater pearls.",
                        "smart_tip": "Opt for lab-created stones or moissanite to achieve 3-carat sparkle on a smart budget."
                    },
                    {
                        "name": "Delicate Floating Pendant or Collar Chain",
                        "estimated_cost": round(cat1_budget * 0.30, 2),
                        "priority": "Recommended",
                        "description": "Whisper-thin 16-inch diamond-cut chain resting perfectly in the collarbone hollow.",
                        "smart_tip": "A dainty chain lets the earrings lead while still catching candlelight when speaking."
                    }
                ]
            },
            {
                "name": "Wrist & Clutch Hand Adornment",
                "allocated_budget": cat2_budget,
                "percentage": 30,
                "items": [
                    {
                        "name": "Hinged Oval Tennis Bangle or Paperclip Bracelet",
                        "estimated_cost": round(cat2_budget * 0.65, 2),
                        "priority": "Must Have",
                        "description": "Sleek, close-fitting hinged cuff in high-polish finish that stays securely in place without snagging gown fabric.",
                        "smart_tip": "Choose an oval rather than circular bangle so stones stay upright on top of the wrist."
                    },
                    {
                        "name": "Textured Stacking Bracelet",
                        "estimated_cost": round(cat2_budget * 0.35, 2),
                        "priority": "Recommended",
                        "description": "Rope-twist or herringbone slender chain adding dimension to the main bracelet.",
                        "smart_tip": "Mixing textures in the exact same metal alloy looks bespoke and curated."
                    }
                ]
            },
            {
                "name": "Cocktail Ring & Subtle Accents",
                "allocated_budget": cat3_budget,
                "percentage": 20,
                "items": [
                    {
                        "name": "Solitaire Cushion-Cut Cocktail Ring",
                        "estimated_cost": round(cat3_budget * 0.70, 2),
                        "priority": "Recommended",
                        "description": "Split-shank signet or elevated prong setting worn on the index or middle finger of your non-drink hand.",
                        "smart_tip": "Sterling silver base with heavy 2.5-micron gold vermeil gives real solid gold look for a fifth the price."
                    },
                    {
                        "name": "Minimalist Huggie Ear Cuffs (No Piercing Needed)",
                        "estimated_cost": round(cat3_budget * 0.30, 2),
                        "priority": "Recommended",
                        "description": "Subtle clip-on huggie cuff nestled in the upper cartilage for a touch of modern edge.",
                        "smart_tip": "Ear cuffs add contemporary youthfulness to traditional formal attire."
                    }
                ]
            }
        ],
        "ai_tips": [
            "If your dress has a high neck or halter, skip the necklace entirely and upgrade the earrings and cuff bracelet.",
            "Wipe jewelry down with a micro-fiber cloth before walking out to remove dulling fingerprints and lotions.",
            "Apply perfume and hairspray at least 15 minutes BEFORE putting on fine jewelry or pearls."
        ],
        "timeline_or_phases": [
            "T-7 Days: Try on entire jewelry set with your outfit, shoes, and intended hairstyle.",
            "T-2 Days: Check clasps, safety latches, and polish metals with jewelry cloth.",
            "Event Day: Fasten jewelry after makeup and hair styling are 100% complete."
        ]
    }
