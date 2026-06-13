# FastAPI + SQLite Developer Guide

**Stack:** FastAPI · SQLAlchemy (async) · aiosqlite · Pydantic v2

---

## 1. Installation

```bash
pip install fastapi uvicorn sqlalchemy aiosqlite
```

---

## 2. Project Structure

```
project/
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI app + lifespan + routes
│   ├── database.py         # Engine, session, Base
│   ├── models.py           # SQLAlchemy ORM models
│   └── schemas.py          # Pydantic request/response schemas
├── app.db                  # SQLite database (auto-created)
└── requirements.txt
```

---

## 3. Database Setup — `database.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///./app.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Set False in production
    connect_args={"check_same_thread": False},
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """Dependency that yields a database session and auto-closes it."""
    async with async_session() as session:
        yield session
```

### Key Points

- `sqlite+aiosqlite` — async driver; never use the sync `sqlite:///` with FastAPI.
- `check_same_thread=False` — required because FastAPI may serve requests across threads.
- `expire_on_commit=False` — prevents lazy-load errors after commit in async context.
- `get_db` uses `yield` so FastAPI's dependency injection handles cleanup automatically.

---

## 4. ORM Models — `models.py`

```python
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationship
    orders = relationship("Order", back_populates="user", lazy="selectin")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total = Column(Float, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, server_default=func.now())

    # Relationship
    user = relationship("User", back_populates="orders", lazy="selectin")
```

### Relationship Loading

Use `lazy="selectin"` for async — it pre-loads related objects in a second query. Avoid `lazy="joined"` or default lazy loading, which will raise errors in async.

---

## 5. Pydantic Schemas — `schemas.py`

```python
from datetime import datetime
from pydantic import BaseModel, EmailStr


# ---------- User ----------

class UserCreate(BaseModel):
    name: str
    email: str  # Use EmailStr if you pip install pydantic[email]


class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Order ----------

class OrderCreate(BaseModel):
    user_id: int
    total: float


class OrderResponse(BaseModel):
    id: int
    user_id: int
    total: float
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

### Why `from_attributes = True`?

Tells Pydantic to read data from SQLAlchemy model attributes (not just dicts). This replaces the old `orm_mode = True` from Pydantic v1.

---

## 6. Application & Routes — `main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import engine, Base, get_db
from app.models import User, Order
from app.schemas import (
    UserCreate, UserUpdate, UserResponse,
    OrderCreate, OrderResponse,
)


# ---------- Lifespan (startup / shutdown) ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup. Replace with Alembic in production."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="My API", lifespan=lifespan)


# ---------- User Routes ----------

@app.post("/users", response_model=UserResponse, status_code=201)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    user = User(**payload.model_dump())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@app.get("/users", response_model=list[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int, payload: UserUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user


@app.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(user)
    await db.commit()


# ---------- Order Routes ----------

@app.post("/orders", response_model=OrderResponse, status_code=201)
async def create_order(payload: OrderCreate, db: AsyncSession = Depends(get_db)):
    # Verify user exists
    result = await db.execute(select(User).where(User.id == payload.user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    order = Order(**payload.model_dump())
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


@app.get("/users/{user_id}/orders", response_model=list[OrderResponse])
async def get_user_orders(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Order).where(Order.user_id == user_id))
    return result.scalars().all()
```

---

## 7. Running the App

```bash
# Development (auto-reload)
uvicorn app.main:app --reload --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

> **Important:** Use `--workers 1` with SQLite. Multiple workers = multiple processes = write conflicts. If you need concurrency, switch to PostgreSQL.

Interactive docs available at: `http://localhost:8000/docs`

---

## 8. Migrations with Alembic

For production, replace `create_all` with proper migrations:

```bash
pip install alembic

# Initialise (one time)
alembic init alembic

# Edit alembic/env.py — set target_metadata = Base.metadata
# Edit alembic.ini — set sqlalchemy.url = sqlite+aiosqlite:///./app.db

# Generate migration
alembic revision --autogenerate -m "initial"

# Apply
alembic upgrade head
```

For async Alembic, update `env.py` to use `run_async_migrations()` — see [Alembic async cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic).

---

## 9. Testing

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DB = "sqlite+aiosqlite:///./test.db"
test_engine = create_async_engine(TEST_DB, connect_args={"check_same_thread": False})
TestSession = async_sessionmaker(bind=test_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSession() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
```

```python
# tests/test_users.py
import pytest

@pytest.mark.anyio
async def test_create_user(client):
    response = await client.post("/users", json={"name": "Jerome", "email": "jerome@test.com"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Jerome"
    assert data["email"] == "jerome@test.com"

@pytest.mark.anyio
async def test_get_user_not_found(client):
    response = await client.get("/users/999")
    assert response.status_code == 404
```

```bash
pip install pytest pytest-asyncio httpx
pytest
```

---

## 10. SQLite Limitations & When to Migrate

| Concern | SQLite | PostgreSQL |
|---------|--------|------------|
| Concurrent writes | Single writer at a time | Full MVCC concurrency |
| Multi-process workers | Not safe | Fully supported |
| JSON / array fields | Limited | Native JSONB, arrays |
| Full-text search | Basic FTS5 | Powerful `tsvector` |
| Deployment | File on disk | Dedicated server |

**Rule of thumb:** SQLite is excellent for prototyping, single-user apps, and read-heavy workloads. Move to PostgreSQL when you need concurrent writes or multi-worker deployments.

**Migration is painless** — change one line:

```python
# Before
DATABASE_URL = "sqlite+aiosqlite:///./app.db"

# After
DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:5432/mydb"
```

Install `asyncpg` and you're done. No model or route changes needed.

---

## 11. Environment Variables (Recommended)

```python
# database.py — production-ready version
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")
```

```bash
pip install python-dotenv
```

```env
# .env
DATABASE_URL=sqlite+aiosqlite:///./app.db
```

---

## Quick Reference

| What | Command / Location |
|------|--------------------|
| Install | `pip install fastapi uvicorn sqlalchemy aiosqlite` |
| Run (dev) | `uvicorn app.main:app --reload` |
| API docs | `http://localhost:8000/docs` |
| DB file | `./app.db` (auto-created) |
| Migrations | Alembic (`alembic upgrade head`) |
| Tests | `pytest` |
