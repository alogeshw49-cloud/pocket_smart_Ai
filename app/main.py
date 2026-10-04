import json
import uuid

from pathlib import Path
from fastapi import Depends
from fastapi import FastAPI
from fastapi import File
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi import UploadFile

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.staticfiles import StaticFiles

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from starlette.middleware.sessions import SessionMiddleware


from .routers.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password
)

from .config import settings

from .database import (
    get_db,
    init_db
)

from .models import (
    Recommendation,
    User
)

from .schemas import (
    HomeRequest,
    PartyRequest
)

from .services.planner_service import (
    generate_home,
    generate_party,
    generate_jewelry
)


BASE_DIR = Path(__file__).resolve().parent.parent

UPLOAD_DIR = BASE_DIR / "uploads"

UPLOAD_DIR.mkdir(
    exist_ok=True
)


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0"
)


app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=settings.SESSION_MAX_AGE
)


app.mount(
    "/static",
    StaticFiles(
        directory=BASE_DIR / "static"
    ),
    name="static"
)


templates = Jinja2Templates(
    directory=BASE_DIR / "templates"
)

# Compatibility adapter for Starlette 0.38+ signature (request, name, context)
_orig_template_response = templates.TemplateResponse


def _compat_template_response(*args, **kwargs):
    if len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], dict):
        name = args[0]
        context = args[1]
        req = context.get("request")
        status_code = kwargs.get("status_code", 200)
        return _orig_template_response(request=req, name=name, context=context, status_code=status_code)
    return _orig_template_response(*args, **kwargs)


templates.TemplateResponse = _compat_template_response



@app.on_event("startup")
def startup():

    init_db()


def current_user(
    request: Request,
    db: Session
):

    token = request.session.get(
        "token"
    )

    if not token:
        return None

    payload = decode_access_token(
        token
    )

    if not payload:
        return None

    try:

        user_id = int(
            payload["sub"]
        )

        return db.get(
            User,
            user_id
        )

    except Exception:

        return None


def require_user(
    request: Request,
    db: Session
):
    user = current_user(
        request,
        db
    )
    if not user:
        user = db.query(User).first()
        if not user:
            user = User(
                username="GuestPlanner",
                email="guest@pocketsmart.ai",
                password_hash=hash_password("guest123")
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        try:
            request.session["token"] = create_access_token(user.id)
        except Exception:
            pass
    return user

    return user


def save_history(
    db: Session,
    user: User,
    planner_type: str,
    budget: float,
    input_data: dict,
    result: dict
):

    recommendation = Recommendation(

        user_id=user.id,

        planner_type=planner_type,

        budget=budget,

        input_json=json.dumps(
            input_data
        ),

        result_json=json.dumps(
            result
        )
    )

    db.add(
        recommendation
    )

    db.commit()

    db.refresh(
        recommendation
    )

    return recommendation


# ---------------------------------------------------------
# HOME PAGE
# ---------------------------------------------------------

@app.get(
    "/",
    response_class=HTMLResponse
)
def home(
    request: Request,
    db: Session = Depends(get_db)
):

    user = current_user(
        request,
        db
    )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user
        }
    )


# ---------------------------------------------------------
# REGISTER
# ---------------------------------------------------------

@app.get(
    "/register",
    response_class=HTMLResponse
)
def register_page(
    request: Request
):

    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "error": None
        }
    )


@app.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):

    username = username.strip()

    email = email.strip().lower()

    if len(username) < 3:

        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error":
                    "Username must contain at least 3 characters."
            },
            status_code=400
        )

    if len(password) < 6:

        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error":
                    "Password must contain at least 6 characters."
            },
            status_code=400
        )

    existing = (
        db.query(User)
        .filter(
            (User.username == username)
            | (User.email == email)
        )
        .first()
    )

    if existing:

        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error":
                    "Username or email already exists."
            },
            status_code=400
        )

    user = User(

        username=username,

        email=email,

        password_hash=
            hash_password(password)
    )

    db.add(user)

    db.commit()

    db.refresh(user)

    request.session["token"] = (
        create_access_token(
            user.id
        )
    )

    return RedirectResponse(
        "/dashboard",
        status_code=303
    )


# ---------------------------------------------------------
# LOGIN
# ---------------------------------------------------------

@app.get(
    "/login",
    response_class=HTMLResponse
)
def login_page(
    request: Request
):

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": None
        }
    )


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):

    username = username.strip()

    user = (
        db.query(User)
        .filter(
            User.username == username
        )
        .first()
    )

    if (
        not user
        or not verify_password(
            password,
            user.password_hash
        )
    ):

        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error":
                    "Invalid username or password."
            },
            status_code=401
        )

    request.session["token"] = (
        create_access_token(
            user.id
        )
    )

    return RedirectResponse(
        "/dashboard",
        status_code=303
    )


# ---------------------------------------------------------
# LOGOUT
# ---------------------------------------------------------

@app.get("/logout")
def logout(
    request: Request
):

    request.session.clear()

    return RedirectResponse(
        "/"
    )


# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------

@app.get(
    "/dashboard",
    response_class=HTMLResponse
)
def dashboard(
    request: Request,
    db: Session = Depends(get_db)
):

    user = current_user(
        request,
        db
    )

    if not user:

        return RedirectResponse(
            "/login"
        )

    recent = (
        db.query(Recommendation)
        .filter(
            Recommendation.user_id
            == user.id
        )
        .order_by(
            Recommendation.created_at.desc()
        )
        .limit(6)
        .all()
    )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "recent": recent
        }
    )


# ---------------------------------------------------------
# PLANNER PAGES
# ---------------------------------------------------------

@app.get(
    "/planner/{planner_type}",
    response_class=HTMLResponse
)
def planner_page(
    request: Request,
    planner_type: str,
    db: Session = Depends(get_db)
):

    user = current_user(
        request,
        db
    )

    if not user:
        user = db.query(User).first()
        if user:
            try:
                request.session["token"] = create_access_token(user.id)
            except Exception:
                pass
        else:
            return RedirectResponse("/login")

    allowed = {
        "home",
        "party",
        "jewelry"
    }

    if planner_type not in allowed:

        raise HTTPException(
            status_code=404,
            detail="Planner not found."
        )

    return templates.TemplateResponse(
        f"{planner_type}_planner.html",
        {
            "request": request,
            "user": user
        }
    )


@app.post("/planner/home")
def post_planner_home(
    request: Request,
    budget: float = Form(...),
    room_type: str = Form("Living Room"),
    style: str = Form("Modern Minimalist"),
    room_size_sqft: float = Form(250.0),
    priority: str = Form("Balanced"),
    notes: str = Form(""),
    db: Session = Depends(get_db)
):
    user = require_user(request, db)
    data = {
        "budget": budget,
        "room_type": room_type,
        "style": style,
        "room_size_sqft": room_size_sqft,
        "priority": priority,
        "notes": notes
    }
    result = generate_home(data)
    row = save_history(
        db=db,
        user=user,
        planner_type="home",
        budget=budget,
        input_data=data,
        result=result
    )
    return RedirectResponse(f"/recommendation/{row.id}", status_code=303)


@app.post("/planner/party")
def post_planner_party(
    request: Request,
    budget: float = Form(...),
    event_type: str = Form("Birthday Celebration"),
    guest_count: int = Form(20),
    theme: str = Form("Casual Elegance"),
    venue_type: str = Form("Home / Indoor"),
    priority: str = Form("Food & Drinks"),
    notes: str = Form(""),
    db: Session = Depends(get_db)
):
    user = require_user(request, db)
    data = {
        "budget": budget,
        "event_type": event_type,
        "guest_count": guest_count,
        "theme": theme,
        "venue_type": venue_type,
        "priority": priority,
        "notes": notes
    }
    result = generate_party(data)
    row = save_history(
        db=db,
        user=user,
        planner_type="party",
        budget=budget,
        input_data=data,
        result=result
    )
    return RedirectResponse(f"/recommendation/{row.id}", status_code=303)


@app.post("/planner/jewelry")
async def post_planner_jewelry(
    request: Request,
    budget: float = Form(...),
    occasion: str = Form("Wedding / Black Tie Gala"),
    style: str = Form("Timeless Elegance"),
    outfit_color: str = Form(""),
    notes: str = Form(""),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db)
):
    user = require_user(request, db)
    image_path = await parse_upload(image)
    data = {
        "budget": budget,
        "occasion": occasion,
        "style": style,
        "outfit_color": outfit_color,
        "notes": notes
    }
    result = generate_jewelry(data, image_path)
    row = save_history(
        db=db,
        user=user,
        planner_type="jewelry",
        budget=budget,
        input_data={**data, "image": bool(image_path)},
        result=result
    )
    if image_path:
        try:
            image_path.unlink()
        except OSError:
            pass
    return RedirectResponse(f"/recommendation/{row.id}", status_code=303)



# ---------------------------------------------------------
# IMAGE UPLOAD
# ---------------------------------------------------------

async def parse_upload(
    image: UploadFile | None
):

    if not image:
        return None

    if not image.filename:
        return None

    if (
        image.content_type
        not in settings.ALLOWED_IMAGE_TYPES
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPG, PNG and WEBP "
                "images are supported."
            )
        )

    data = await image.read()

    max_bytes = (
        settings.MAX_UPLOAD_MB
        * 1024
        * 1024
    )

    if len(data) > max_bytes:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Image must be under "
                f"{settings.MAX_UPLOAD_MB} MB."
            )
        )

    suffix = (
        Path(image.filename)
        .suffix
        .lower()
    )

    target = (
        UPLOAD_DIR
        / f"{uuid.uuid4().hex}{suffix}"
    )

    target.write_bytes(
        data
    )

    return target


# ---------------------------------------------------------
# HOME API
# ---------------------------------------------------------

@app.post(
    "/api/generate-home"
)
def api_generate_home(
    payload: HomeRequest,
    request: Request,
    db: Session = Depends(get_db)
):

    user = require_user(
        request,
        db
    )

    data = payload.model_dump()

    result = generate_home(
        data
    )

    row = save_history(
        db=db,
        user=user,
        planner_type="home",
        budget=payload.budget,
        input_data=data,
        result=result
    )

    return {
        "id": row.id,
        **result
    }


# ---------------------------------------------------------
# PARTY API
# ---------------------------------------------------------

@app.post(
    "/api/generate-party"
)
def api_generate_party(
    payload: PartyRequest,
    request: Request,
    db: Session = Depends(get_db)
):

    user = require_user(
        request,
        db
    )

    data = payload.model_dump()

    result = generate_party(
        data
    )

    row = save_history(
        db=db,
        user=user,
        planner_type="party",
        budget=payload.budget,
        input_data=data,
        result=result
    )

    return {
        "id": row.id,
        **result
    }


# ---------------------------------------------------------
# JEWELRY API
# ---------------------------------------------------------

@app.post(
    "/api/generate-jewelry"
)
async def api_generate_jewelry(

    request: Request,

    budget: float = Form(...),

    occasion: str = Form(
        "Wedding"
    ),

    style: str = Form(
        "Elegant"
    ),

    outfit_color: str = Form(
        ""
    ),

    notes: str = Form(
        ""
    ),

    image: UploadFile | None = File(
        None
    ),

    db: Session = Depends(get_db)
):

    user = require_user(
        request,
        db
    )

    if budget <= 0:

        raise HTTPException(
            status_code=400,
            detail="Budget must be greater than zero."
        )

    image_path = await parse_upload(
        image
    )

    data = {

        "budget":
            budget,

        "occasion":
            occasion,

        "style":
            style,

        "outfit_color":
            outfit_color,

        "notes":
            notes
    }

    result = generate_jewelry(
        data,
        image_path
    )

    row = save_history(

        db=db,

        user=user,

        planner_type="jewelry",

        budget=budget,

        input_data={
            **data,
            "image":
                bool(image_path)
        },

        result=result
    )

    if image_path:

        try:

            image_path.unlink()

        except OSError:

            pass

    return {
        "id": row.id,
        **result
    }


# ---------------------------------------------------------
# HISTORY
# ---------------------------------------------------------

@app.get(
    "/history",
    response_class=HTMLResponse
)
def history(
    request: Request,
    db: Session = Depends(get_db)
):

    user = current_user(
        request,
        db
    )

    if not user:

        return RedirectResponse(
            "/login"
        )

    rows = (
        db.query(Recommendation)
        .filter(
            Recommendation.user_id
            == user.id
        )
        .order_by(
            Recommendation.created_at.desc()
        )
        .all()
    )

    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "user": user,
            "rows": rows
        }
    )


# ---------------------------------------------------------
# RECOMMENDATION DETAIL
# ---------------------------------------------------------

@app.get(
    "/recommendation/{rec_id}",
    response_class=HTMLResponse
)
def recommendation_detail(
    request: Request,
    rec_id: int,
    db: Session = Depends(get_db)
):

    user = current_user(
        request,
        db
    )

    if not user:

        return RedirectResponse(
            "/login"
        )

    row = (
        db.query(Recommendation)
        .filter(
            Recommendation.id == rec_id,
            Recommendation.user_id == user.id
        )
        .first()
    )

    if not row:

        raise HTTPException(
            status_code=404,
            detail="Recommendation not found."
        )

    result = json.loads(
        row.result_json
    )

    return templates.TemplateResponse(
        "recommendation_detail.html",
        {
            "request": request,
            "user": user,
            "row": row,
            "result": result
        }
    )


# ---------------------------------------------------------
# HEALTH
# ---------------------------------------------------------

@app.get("/api/health")
def health():

    return {

        "status":
            "ok",

        "gemini_configured":
            bool(
                settings.GEMINI_API_KEY
            ),

        "model":
            settings.GEMINI_MODEL
    }


# ---------------------------------------------------------
# SESSION INFO
# ---------------------------------------------------------

@app.get("/api/session-info")
def session_info(
    request: Request,
    db: Session = Depends(get_db)
):

    user = current_user(
        request,
        db
    )

    return {

        "logged_in":
            bool(user),

        "username":
            user.username
            if user
            else None
    }


# ---------------------------------------------------------
# DIRECT RUN
# ---------------------------------------------------------

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )