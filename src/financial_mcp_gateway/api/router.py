"""HTTP API with OpenAPI / Swagger UI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from db import init_db
from financial_mcp_gateway.accounts.router import router as accounts_router
from financial_mcp_gateway.customers.router import router as customers_router
from financial_mcp_gateway.idempotency.router import router as idempotency_router
from financial_mcp_gateway.transactions.router import router as transactions_router
from financial_mcp_gateway.users.router import router as users_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Financial Gateway",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(customers_router)
app.include_router(accounts_router)
app.include_router(transactions_router)
app.include_router(users_router)
app.include_router(idempotency_router)
