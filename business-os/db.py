"""Single Mongo client shared by every module.
All collection handles live here so routers never create their own clients.
Provides both sync (pymongo) and async (motor) clients.
Falls back to mongomock (in-memory) when MONGO_URL is not set."""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

_log = logging.getLogger("db")

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Resolve the Mongo connection (real client or in-memory fallback)
mongo_url = os.environ.get("MONGO_URL", "").strip()

if mongo_url:
    from pymongo import MongoClient
    import motor.motor_asyncio
    mongo = MongoClient(mongo_url, maxPoolSize=50, minPoolSize=5, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
    db = mongo[os.environ.get("DB_NAME", "smartdecision")]
    async_mongo = motor.motor_asyncio.AsyncIOMotorClient(mongo_url, maxPoolSize=100, serverSelectionTimeoutMS=5000)
    async_db = async_mongo[os.environ.get("DB_NAME", "smartdecision")]
    _log.info("Connected to MongoDB at %s", mongo_url)
else:
    try:
        import mongomock
        mongo = mongomock.MongoClient()
        db = mongo["smartdecision"]
        async_mongo = None
        async_db = None
        _log.warning("Using mongomock (in-memory) — set MONGO_URL for production MongoDB")
    except ImportError:
        mongo = None
        db = None
        async_mongo = None
        async_db = None
        _log.warning("No MongoDB configured and mongomock not available")


# Get a sync collection handle (None if DB absent)
def _col(name):
    return db[name] if db is not None else None

# Get an async collection handle, wrapping sync when needed
def _async_col(name):
    if async_db is not None:
        return async_db[name]
    if db is not None:
        return _MongomockAsyncAdapter(db[name])
    return None


class _MongomockAsyncAdapter:
    """Wraps a sync pymongo/mongomock collection to work with await syntax."""
    def __init__(self, sync_col):
        self._col = sync_col

    async def find_one(self, *args, **kwargs):
        return self._col.find_one(*args, **kwargs)

    async def insert_one(self, doc, **kwargs):
        return self._col.insert_one(doc, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._col.update_one(*args, **kwargs)

    async def find(self, *args, **kwargs):
        cursor = self._col.find(*args, **kwargs)
        return _AsyncCursorWrapper(cursor)

    async def count_documents(self, *args, **kwargs):
        return self._col.count_documents(*args, **kwargs)

    async def aggregate(self, *args, **kwargs):
        cursor = self._col.aggregate(*args, **kwargs)
        return _AsyncCursorWrapper(cursor)

    async def delete_one(self, *args, **kwargs):
        return self._col.delete_one(*args, **kwargs)

    async def delete_many(self, *args, **kwargs):
        return self._col.delete_many(*args, **kwargs)

    async def update_many(self, *args, **kwargs):
        return self._col.update_many(*args, **kwargs)

    async def create_index(self, *args, **kwargs):
        return self._col.create_index(*args, **kwargs)


# Adapt a sync cursor to the async iteration protocol
class _AsyncCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._cursor)
        except StopIteration:
            raise StopAsyncIteration

    async def to_list(self, length=None):
        return list(self._cursor)

# Handles to every Mongo collection (sync)
users_col = _col("users")
threads_col = _col("goal_threads")
events_col = _col("substrate_events")
telemetry_col = _col("telemetry_events")
ledger_col = _col("credit_ledger")
stats_col = _col("stats")
traffic_col = _col("traffic_sessions")
geo_col = _col("geo_cache")
orders_col = _col("payment_orders")
feedback_col = _col("feedback")
orgs_col = _col("organizations")
members_col = _col("org_members")
invites_col = _col("org_invites")
decisions_col = _col("decisions")
plans_col = _col("org_plans")
journeys_col = _col("journeys")
shares_col = _col("shares")
tasks_col = _col("tasks")
subscriptions_col = _col("subscriptions")
token_usage_col = _col("token_usage")
user_patterns_col = _col("user_patterns")
conversation_memory_col = _col("conversation_memory")
rate_limits_col = _col("rate_limits")
org_memory_col = _col("organization_memory")    # Ch.18 Autopsy Engine + Ch.26 Org Memory
executives_col = _col("executives")             # Ch.22 Executive DNA
executive_messages_col = _col("executive_messages")   # Ch.23 Hierarchy & Communication
executive_decisions_col = _col("executive_decisions") # Ch.20 Executive Decisions
resource_requests_col = _col("resource_requests")     # Ch.24 Internal Economy
projects_col = _col("projects")                       # Ch.36 Project Planning
automation_templates_col = _col("automation_templates")  # Ch.38 Department Automation
exec_tasks_col = _col("exec_tasks")                   # Ch.40 Executive task queue (approval → execution)
genesis_pipelines_col = _col("genesis_pipelines")     # Genesis session state (survives restarts)
evidence_col = _col("evidence")                       # Ch.44 Verification evidence (the proof engine)
learning_col = _col("learning_events")                # Ch.47 Verified organizational learning
playbooks_col = _col("playbooks")                     # Playbook Engine state
habits_col = _col("habits")                           # Habit Tracker
weekly_reviews_col = _col("weekly_reviews")           # Weekly Review
sessions_col = _col("sessions")                       # JWT session tokens

# Handles to every Mongo collection (async)
async_users_col = _async_col("users")
async_threads_col = _async_col("goal_threads")
async_events_col = _async_col("substrate_events")
async_telemetry_col = _async_col("telemetry_events")
async_ledger_col = _async_col("credit_ledger")
async_stats_col = _async_col("stats")
async_traffic_col = _async_col("traffic_sessions")
async_geo_col = _async_col("geo_cache")
async_orders_col = _async_col("payment_orders")
async_feedback_col = _async_col("feedback")
async_orgs_col = _async_col("organizations")
async_members_col = _async_col("org_members")
async_invites_col = _async_col("org_invites")
async_decisions_col = _async_col("decisions")
async_plans_col = _async_col("org_plans")
async_journeys_col = _async_col("journeys")
async_shares_col = _async_col("shares")
async_tasks_col = _async_col("tasks")
async_subscriptions_col = _async_col("subscriptions")
async_token_usage_col = _async_col("token_usage")
async_user_patterns_col = _async_col("user_patterns")
async_conversation_memory_col = _async_col("conversation_memory")
async_rate_limits_col = _async_col("rate_limits")
async_sessions_col = _async_col("sessions")
