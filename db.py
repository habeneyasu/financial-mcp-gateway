"""SQLite schema and queries for the financial gateway."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import TypedDict

from config import config

logger = logging.getLogger(__name__)

CUSTOMER_COUNT = 5
USER_COUNT = 10
SEED_PASSWORD = "ChangeMe123!"
_PBKDF2_ITERATIONS = 120_000

TX_STATUSES = ("pending", "completed", "failed", "reversed")
IDEMPOTENCY_STATUSES = ("pending", "completed", "failed")

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active',
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL DEFAULT 'member',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT,
    UNIQUE (id, customer_id)
);

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    account_number TEXT NOT NULL UNIQUE,
    account_type TEXT NOT NULL,
    name TEXT NOT NULL,
    currency TEXT NOT NULL,
    balance_cents INTEGER NOT NULL DEFAULT 0 CHECK (balance_cents >= 0),
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference TEXT NOT NULL UNIQUE,
    source_account_id TEXT NOT NULL,
    destination_account_id TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'failed', 'reversed')),
    failure_code TEXT,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (source_account_id <> destination_account_id),
    CHECK (
        (status = 'failed' AND failure_code IS NOT NULL)
        OR (status <> 'failed' AND failure_code IS NULL)
    ),
    FOREIGN KEY (source_account_id) REFERENCES accounts(id) ON DELETE RESTRICT,
    FOREIGN KEY (destination_account_id) REFERENCES accounts(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    user_id TEXT NOT NULL,
    key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'failed')),
    http_status INTEGER,
    response_body TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL DEFAULT (datetime('now', '+24 hours')),
    PRIMARY KEY (user_id, key),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_users_customer ON users(customer_id);
CREATE INDEX IF NOT EXISTS idx_accounts_customer ON accounts(customer_id);
CREATE INDEX IF NOT EXISTS idx_accounts_account_number ON accounts(account_number);
CREATE INDEX IF NOT EXISTS idx_accounts_currency ON accounts(currency);
CREATE INDEX IF NOT EXISTS idx_transactions_source ON transactions(source_account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_destination ON transactions(destination_account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_reference ON transactions(reference);
CREATE INDEX IF NOT EXISTS idx_idempotency_expires ON idempotency_keys(expires_at);
"""

_CUSTOMER_CONTACTS = (
    ("Alice", "Johnson"),
    ("Bob", "Smith"),
    ("Carol", "Williams"),
    ("David", "Brown"),
    ("Eve", "Davis"),
)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(digest.hex(), digest_hex)


def _connect() -> sqlite3.Connection:
    path = Path(config.DATABASE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _needs_rebuild(conn: sqlite3.Connection) -> bool:
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if not tables:
        return False
    required = {"customers", "users", "accounts", "transactions", "idempotency_keys"}
    if not required.issubset(tables):
        return True
    if "http_status" not in _columns(conn, "idempotency_keys"):
        return True
    if "reference" not in _columns(conn, "transactions"):
        return True
    customer_cols = _columns(conn, "customers")
    if "first_name" not in customer_cols:
        return True
    if "phone_number" not in customer_cols:
        return True
    account_cols = _columns(conn, "accounts")
    if "account_number" not in account_cols or "account_type" not in account_cols:
        return True
    if "primary_user_id" in account_cols:
        return True
    transaction_cols = _columns(conn, "transactions")
    if "created_by_user_id" in transaction_cols or "amount_cents" in transaction_cols:
        return True
    if "amount" not in transaction_cols:
        return True
    return "name" in customer_cols


def _drop_all(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        """
        DROP TABLE IF EXISTS idempotency_keys;
        DROP TABLE IF EXISTS transactions;
        DROP TABLE IF EXISTS accounts;
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS customers;
        """
    )
    conn.execute("PRAGMA foreign_keys = ON")


def _request_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()


def _seed(conn: sqlite3.Connection) -> None:
    customers = [
        (
            f"cust-{i}",
            _CUSTOMER_CONTACTS[i - 1][0],
            _CUSTOMER_CONTACTS[i - 1][1],
            f"+1555000{i:04d}",
            f"finance{i}@customer.example",
            "active",
        )
        for i in range(1, CUSTOMER_COUNT + 1)
    ]
    conn.executemany(
        """
        INSERT INTO customers (id, first_name, last_name, phone_number, email, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        customers,
    )

    users: list[tuple[str, str, str, str, str, str]] = []
    users_by_customer: dict[str, list[str]] = defaultdict(list)
    for i in range(1, USER_COUNT + 1):
        customer_id = f"cust-{((i - 1) % CUSTOMER_COUNT) + 1}"
        user_id = f"user-{i}"
        role = "admin" if i <= CUSTOMER_COUNT else "member"
        users.append(
            (user_id, customer_id, f"user{i}", hash_password(SEED_PASSWORD), f"user{i}@customer.example", role)
        )
        users_by_customer[customer_id].append(user_id)
    conn.executemany(
        """
        INSERT INTO users (id, customer_id, username, password_hash, email, role)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        users,
    )

    accounts = [
        ("acc-1", "cust-1", "1000000001", "operating", "Operating", "USD", 1_250_000, "open"),
        ("acc-2", "cust-1", "1000000002", "reserve", "Reserve", "USD", 5_000_000, "open"),
        ("acc-3", "cust-2", "2000000001", "operating", "Operating", "USD", 890_000, "open"),
        ("acc-4", "cust-2", "2000000002", "treasury", "Treasury", "EUR", 2_100_000, "open"),
        ("acc-5", "cust-3", "3000000001", "payroll", "Payroll", "GBP", 750_000, "open"),
        ("acc-6", "cust-3", "3000000002", "operating", "Operating", "GBP", 430_000, "open"),
        ("acc-7", "cust-4", "4000000001", "operating", "Operating", "USD", 300_000, "open"),
        ("acc-8", "cust-5", "5000000001", "collections", "Collections", "EUR", 960_000, "open"),
        ("acc-empty", "cust-1", "1000000099", "petty_cash", "Petty cash", "USD", 50, "open"),
    ]
    conn.executemany(
        """
        INSERT INTO accounts (
            id, customer_id, account_number, account_type, name, currency, balance_cents, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        accounts,
    )

    owner_cust1 = users_by_customer["cust-1"][0]
    owner_cust2 = users_by_customer["cust-2"][0]
    owner_cust3 = users_by_customer["cust-3"][0]
    outsider = users_by_customer["cust-5"][0]

    transactions = [
        ("txn_ok_001", "acc-1", "acc-2", 25_000, "USD", "transfer", "completed", None, "Internal USD transfer"),
        ("txn_ok_002", "acc-2", "acc-1", 10_000, "USD", "transfer", "completed", None, "Reserve to operating"),
        ("txn_ok_003", "acc-3", "acc-7", 15_000, "USD", "payment", "completed", None, "Cross-customer USD payment"),
        ("txn_ok_004", "acc-5", "acc-6", 8_000, "GBP", "transfer", "completed", None, "Internal GBP transfer"),
        ("txn_ok_005", "acc-4", "acc-8", 12_000, "EUR", "payout", "completed", None, "EUR collections payout"),
        ("txn_ok_006", "acc-1", "acc-7", 5_000, "USD", "payment", "completed", None, "Vendor payment"),
        ("txn_pending_001", "acc-1", "acc-2", 40_000, "USD", "transfer", "pending", None, "Awaiting approval"),
        ("txn_pending_002", "acc-4", "acc-8", 9_500, "EUR", "payout", "pending", None, "Settlement in flight"),
        ("txn_fail_nsf_001", "acc-empty", "acc-1", 10_000, "USD", "transfer", "failed", "insufficient_balance", "Seed: insufficient balance"),
        ("txn_fail_nsf_002", "acc-7", "acc-1", 9_999_999, "USD", "payment", "failed", "insufficient_balance", "Seed: amount exceeds source"),
        ("txn_fail_unauth_001", "acc-1", "acc-2", 3_000, "USD", "transfer", "failed", "unauthorized", "Seed: source customer not authorized"),
        ("txn_fail_unauth_002", "acc-5", "acc-6", 2_000, "GBP", "transfer", "failed", "unauthorized", "Seed: cross-customer transfer denied"),
        ("txn_fail_dup_001", "acc-1", "acc-2", 25_000, "USD", "transfer", "failed", "duplicate_request", "Seed: replay of txn_ok_001"),
        ("txn_rev_001", "acc-2", "acc-1", 7_500, "USD", "transfer", "reversed", None, "Completed then reversed"),
    ]
    conn.executemany(
        """
        INSERT INTO transactions (
            reference, source_account_id, destination_account_id,
            amount, currency, type, status, failure_code, description
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        transactions,
    )

    idempotency = [
        (
            owner_cust1,
            "transfer-ok-001",
            _request_hash("acc-1>acc-2:25000:USD"),
            "completed",
            200,
            json.dumps({"reference": "txn_ok_001", "status": "completed"}),
        ),
        (
            owner_cust1,
            "transfer-ok-001-replay",
            _request_hash("acc-1>acc-2:25000:USD"),
            "failed",
            409,
            json.dumps({"error": "duplicate_request", "original_reference": "txn_ok_001"}),
        ),
        (
            owner_cust1,
            "transfer-nsf-001",
            _request_hash("acc-empty>acc-1:10000:USD"),
            "failed",
            422,
            json.dumps({"error": "insufficient_balance", "reference": "txn_fail_nsf_001"}),
        ),
        (
            outsider,
            "transfer-unauth-001",
            _request_hash("acc-1>acc-2:3000:USD"),
            "failed",
            403,
            json.dumps({"error": "unauthorized", "reference": "txn_fail_unauth_001"}),
        ),
        (
            owner_cust1,
            "transfer-pending-001",
            _request_hash("acc-1>acc-2:40000:USD"),
            "pending",
            202,
            json.dumps({"reference": "txn_pending_001", "status": "pending"}),
        ),
    ]
    conn.executemany(
        """
        INSERT INTO idempotency_keys
            (user_id, key, request_hash, status, http_status, response_body)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        idempotency,
    )


def record_counts(conn: sqlite3.Connection | None = None) -> dict[str, int]:
    own = False
    if conn is None:
        own = True
        conn = _connect()
    try:
        tables = ("customers", "users", "accounts", "transactions", "idempotency_keys")
        return {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
    finally:
        if own:
            conn.close()


def init_db() -> None:
    with _connect() as conn:
        if _needs_rebuild(conn):
            _drop_all(conn)
        conn.executescript(SCHEMA)
        # Serialize startup when MCP and REST share one SQLite file (e.g. Docker Compose).
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0:
            _seed(conn)
        conn.commit()
        logger.info("database records: %s", record_counts(conn))


def get_customer(customer_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, first_name, last_name, phone_number, email, status, created_by, created_at
            FROM customers
            WHERE id = ?
            """,
            (customer_id,),
        ).fetchone()
    return dict(row) if row else None


def insert_customer(
    *,
    customer_id: str,
    first_name: str,
    last_name: str,
    phone_number: str,
    email: str,
    status: str,
    created_by: str | None,
) -> dict:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO customers (
                id, first_name, last_name, phone_number, email, status, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (customer_id, first_name, last_name, phone_number, email, status, created_by),
        )
    row = get_customer(customer_id)
    if row is None:
        raise RuntimeError(f"customer {customer_id} was not saved")
    return row


def get_user(user_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, customer_id, username, email, role, created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def insert_user(
    *,
    user_id: str,
    customer_id: str,
    username: str,
    password_hash: str,
    email: str,
    role: str,
) -> dict:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (id, customer_id, username, password_hash, email, role)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, customer_id, username, password_hash, email, role),
        )
    row = get_user(user_id)
    if row is None:
        raise RuntimeError(f"user {user_id} was not saved")
    return row


def list_users(
    customer_id: str | None = None,
    limit: int = 100,
) -> tuple[int, list[dict]]:
    limit = max(1, min(limit, 100))
    with _connect() as conn:
        if customer_id:
            total = conn.execute(
                "SELECT COUNT(*) FROM users WHERE customer_id = ?",
                (customer_id,),
            ).fetchone()[0]
            rows = conn.execute(
                """
                SELECT id, customer_id, username, email, role, created_at
                FROM users
                WHERE customer_id = ?
                ORDER BY id
                LIMIT ?
                """,
                (customer_id, limit),
            ).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            rows = conn.execute(
                """
                SELECT id, customer_id, username, email, role, created_at
                FROM users
                ORDER BY id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return total, [dict(row) for row in rows]


def get_idempotency_key(user_id: str, key: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT user_id, key, request_hash, status, http_status, response_body, created_at, expires_at
            FROM idempotency_keys
            WHERE user_id = ? AND key = ?
            """,
            (user_id, key),
        ).fetchone()
    return dict(row) if row else None


def insert_idempotency_key(
    *,
    user_id: str,
    key: str,
    request_hash: str,
    status: str,
    http_status: int | None = None,
    response_body: str | None = None,
) -> dict:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO idempotency_keys (user_id, key, request_hash, status, http_status, response_body)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, key, request_hash, status, http_status, response_body),
        )
    row = get_idempotency_key(user_id, key)
    if row is None:
        raise RuntimeError(f"idempotency key {user_id}/{key} was not saved")
    return row


def list_idempotency_keys(
    user_id: str | None = None,
    limit: int = 100,
) -> tuple[int, list[dict]]:
    limit = max(1, min(limit, 100))
    with _connect() as conn:
        if user_id:
            total = conn.execute(
                "SELECT COUNT(*) FROM idempotency_keys WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
            rows = conn.execute(
                """
                SELECT user_id, key, request_hash, status, http_status, response_body, created_at, expires_at
                FROM idempotency_keys
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) FROM idempotency_keys").fetchone()[0]
            rows = conn.execute(
                """
                SELECT user_id, key, request_hash, status, http_status, response_body, created_at, expires_at
                FROM idempotency_keys
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return total, [dict(row) for row in rows]


def insert_account(
    *,
    account_id: str,
    customer_id: str,
    account_number: str,
    account_type: str,
    name: str,
    currency: str,
    balance_cents: int,
    status: str,
) -> dict:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO accounts (
                id, customer_id, account_number, account_type, name, currency, balance_cents, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                customer_id,
                account_number,
                account_type,
                name,
                currency,
                balance_cents,
                status,
            ),
        )
    row = get_account(account_id)
    if row is None:
        raise RuntimeError(f"account {account_id} was not saved")
    return row

def get_account(account_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                a.id,
                a.customer_id,
                c.first_name AS customer_first_name,
                c.last_name AS customer_last_name,
                a.account_number,
                a.account_type,
                a.name,
                a.currency,
                a.balance_cents,
                a.status,
                a.created_at,
                (
                    SELECT COUNT(*) FROM transactions t
                    WHERE t.source_account_id = a.id OR t.destination_account_id = a.id
                ) AS transaction_count
            FROM accounts a
            JOIN customers c ON c.id = a.customer_id
            WHERE a.id = ?
            """,
            (account_id,),
        ).fetchone()
    return dict(row) if row else None


def get_transaction_by_reference(reference: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                t.id,
                t.reference,
                t.source_account_id,
                t.destination_account_id,
                t.amount,
                t.currency,
                t.type,
                t.status,
                t.failure_code,
                t.description,
                t.created_at
            FROM transactions t
            WHERE t.reference = ?
            """,
            (reference,),
        ).fetchone()
    return dict(row) if row else None


def insert_transaction(
    *,
    reference: str,
    source_account_id: str,
    destination_account_id: str,
    amount: int,
    currency: str,
    transaction_type: str,
    description: str,
    status: str,
) -> dict:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO transactions (
                reference, source_account_id, destination_account_id,
                amount, currency, type, description, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reference,
                source_account_id,
                destination_account_id,
                amount,
                currency,
                transaction_type,
                description,
                status,
            ),
        )
    row = get_transaction_by_reference(reference)
    if row is None:
        raise RuntimeError(f"transaction {reference} was not saved")
    return row


def list_transactions(
    account_id: str | None = None,
    limit: int = 10,
) -> tuple[int, list[dict]]:
    limit = max(1, min(limit, 100))
    with _connect() as conn:
        if account_id:
            total = conn.execute(
                """
                SELECT COUNT(*) FROM transactions
                WHERE source_account_id = ? OR destination_account_id = ?
                """,
                (account_id, account_id),
            ).fetchone()[0]
            rows = conn.execute(
                """
                SELECT
                    t.id,
                    t.reference,
                    t.status,
                    t.failure_code,
                    t.currency,
                    t.source_account_id,
                    src.name AS source_account_name,
                    src.currency AS source_currency,
                    t.destination_account_id,
                    dst.name AS destination_account_name,
                    dst.currency AS destination_currency,
                    CASE
                        WHEN t.source_account_id = ? THEN 'outbound'
                        ELSE 'inbound'
                    END AS direction,
                    t.amount,
                    t.type,
                    t.description,
                    t.created_at
                FROM transactions t
                JOIN accounts src ON src.id = t.source_account_id
                JOIN accounts dst ON dst.id = t.destination_account_id
                WHERE t.source_account_id = ? OR t.destination_account_id = ?
                ORDER BY t.id DESC
                LIMIT ?
                """,
                (account_id, account_id, account_id, limit),
            ).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
            rows = conn.execute(
                """
                SELECT
                    t.id,
                    t.reference,
                    t.source_account_id,
                    t.destination_account_id,
                    t.amount,
                    t.currency,
                    t.type,
                    t.status,
                    t.failure_code,
                    t.description,
                    t.created_at
                FROM transactions t
                ORDER BY t.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return total, [dict(row) for row in rows]


class TransactionStats(TypedDict):
    total: int
    by_status: dict[str, int]


def transaction_stats() -> TransactionStats:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        by_status = {
            row["status"]: row["count"]
            for row in conn.execute(
                "SELECT status, COUNT(*) AS count FROM transactions GROUP BY status"
            ).fetchall()
        }
    return {"total": total, "by_status": by_status}
