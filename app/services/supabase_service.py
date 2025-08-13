"""
Supabase service for JobTrackAI
Handles database operations and connection management
"""

import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from supabase import create_client, Client
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from app.models.job import JobCreate, JobUpdate, JobStatus

logger = logging.getLogger(__name__)

class SupabaseService:
    """Service for Supabase database operations"""
    
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
        self.supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.database_url = os.getenv("DATABASE_URL")
        
        # Try Supabase client first, fallback to direct PostgreSQL
        if self.supabase_url and self.supabase_anon_key:
            try:
                self.client: Client = create_client(self.supabase_url, self.supabase_anon_key)
                logger.info("Supabase client initialized successfully")
                self.use_direct_connection = False
            except Exception as e:
                logger.warning(f"Supabase client failed, falling back to direct connection: {e}")
                self.use_direct_connection = True
        else:
            self.use_direct_connection = True
        
        if self.use_direct_connection and not self.database_url:
            raise ValueError("Either SUPABASE_URL/ANON_KEY or DATABASE_URL must be set in environment variables")
        
        if self.use_direct_connection:
            logger.info("Using direct PostgreSQL connection")
        else:
            logger.info("Using Supabase client")

    # =====================
    # Users
    # =====================
    async def get_user_by_phone(self, phone_e164: str) -> Optional[Dict[str, Any]]:
        """Fetch a user row by phone in E.164 format."""
        try:
            if not self.use_direct_connection:
                result = (
                    self.client
                    .table("users")
                    .select("id, phone_e164, display_name, metadata, created_at, updated_at")
                    .eq("phone_e164", phone_e164)
                    .single()
                    .execute()
                )
                return result.data if result.data else None
            else:
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(
                            """
                            SELECT id, phone_e164, display_name, metadata, created_at, updated_at
                            FROM users
                            WHERE phone_e164 = %s
                            LIMIT 1
                            """,
                            (phone_e164,)
                        )
                        row = cur.fetchone()
                        return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error fetching user by phone: {e}")
            if not self.use_direct_connection and self.database_url and "Invalid API key" in str(e):
                self.use_direct_connection = True
                return await self.get_user_by_phone(phone_e164)
            return None

    async def create_user(self, *, phone_e164: str, display_name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Create a new user row."""
        try:
            if not self.use_direct_connection:
                payload = {
                    "phone_e164": phone_e164,
                    "display_name": display_name,
                    "metadata": metadata or {},
                }
                result = self.client.table("users").insert(payload).execute()
                return result.data[0] if result.data else None
            else:
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(
                            """
                            INSERT INTO users (phone_e164, display_name, metadata)
                            VALUES (%s, %s, %s::jsonb)
                            ON CONFLICT (phone_e164) DO UPDATE SET
                                display_name = COALESCE(EXCLUDED.display_name, users.display_name),
                                updated_at = NOW()
                            RETURNING id, phone_e164, display_name, metadata, created_at, updated_at
                            """,
                            (phone_e164, display_name, Json(metadata or {}))
                        )
                        row = cur.fetchone()
                        return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            if not self.use_direct_connection and self.database_url and "Invalid API key" in str(e):
                self.use_direct_connection = True
                return await self.create_user(phone_e164=phone_e164, display_name=display_name, metadata=metadata)
            return None

    async def get_or_create_user_by_phone(self, phone_e164: str, *, display_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Idempotently fetch or create a user for this phone number."""
        user = await self.get_user_by_phone(phone_e164)
        if user:
            # Optionally backfill display_name
            if display_name and not user.get("display_name"):
                try:
                    if not self.use_direct_connection:
                        upd = self.client.table("users").update({"display_name": display_name}).eq("id", user["id"]).execute()
                        if upd.data:
                            user = upd.data[0]
                    else:
                        with psycopg2.connect(self.database_url) as conn:
                            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                                cur.execute(
                                    """
                                    UPDATE users SET display_name = %s, updated_at = NOW()
                                    WHERE id = %s::uuid
                                    RETURNING id, phone_e164, display_name, metadata, created_at, updated_at
                                    """,
                                    (display_name, user["id"])
                                )
                                row = cur.fetchone()
                                if row:
                                    user = dict(row)
                except Exception:
                    pass
            return user
        return await self.create_user(phone_e164=phone_e164, display_name=display_name)

    # =====================
    # Conversations & Messages (Context Memory)
    # =====================
    async def get_conversation_metadata(self, conversation_id: str) -> Dict[str, Any]:
        """Fetch conversation metadata"""
        try:
            if not self.use_direct_connection:
                result = (
                    self.client
                    .table("conversations")
                    .select("metadata")
                    .eq("id", conversation_id)
                    .single()
                    .execute()
                )
                return result.data.get("metadata", {}) if result.data else {}
            else:
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(
                            """
                            SELECT metadata FROM conversations WHERE id = %s::uuid
                            """,
                            (conversation_id,)
                        )
                        row = cur.fetchone()
                        return dict(row).get("metadata", {}) if row else {}
        except Exception as e:
            logger.error(f"Error fetching conversation metadata: {e}")
            if not self.use_direct_connection and self.database_url and "Invalid API key" in str(e):
                self.use_direct_connection = True
                return await self.get_conversation_metadata(conversation_id)
            return {}

    async def update_conversation_metadata(self, conversation_id: str, metadata: Dict[str, Any]) -> bool:
        """Update conversation metadata JSONB"""
        try:
            if not self.use_direct_connection:
                result = (
                    self.client
                    .table("conversations")
                    .update({"metadata": metadata})
                    .eq("id", conversation_id)
                    .execute()
                )
                return bool(result.data)
            else:
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(
                            """
                            UPDATE conversations SET metadata = %s::jsonb, updated_at = NOW() WHERE id = %s::uuid
                            RETURNING id
                            """,
                            (Json(metadata), conversation_id)
                        )
                        row = cur.fetchone()
                        return bool(row)
        except Exception as e:
            logger.error(f"Error updating conversation metadata: {e}")
            if not self.use_direct_connection and self.database_url and "Invalid API key" in str(e):
                self.use_direct_connection = True
                return await self.update_conversation_metadata(conversation_id, metadata)
            return False
    async def create_conversation(self, user_id: str, title: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Create a new conversation row"""
        try:
            if not self.use_direct_connection:
                payload = {
                    "user_id": user_id,
                    "title": title,
                    "metadata": metadata or {}
                }
                result = self.client.table("conversations").insert(payload).execute()
                return result.data[0] if result.data else None
            else:
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(
                            """
                            INSERT INTO conversations (user_id, title, metadata)
                            VALUES (%s::uuid, %s, %s::jsonb)
                            RETURNING id, user_id, title, metadata, created_at, updated_at, last_message_at
                            """,
                            (user_id, title, Json(metadata or {}))
                        )
                        row = cur.fetchone()
                        return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error creating conversation: {e}")
            # Fallback to direct DB if REST key invalid
            if not self.use_direct_connection and self.database_url and "Invalid API key" in str(e):
                self.use_direct_connection = True
                return await self.create_conversation(user_id, title, metadata)
            return None

    async def get_or_create_recent_conversation(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Return most recent conversation for user, or create a new one if none."""
        try:
            if not self.use_direct_connection:
                result = (
                    self.client
                    .table("conversations")
                    .select("*")
                    .eq("user_id", user_id)
                    .order("last_message_at", desc=True)
                    .order("updated_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if result.data:
                    return result.data[0]
                return await self.create_conversation(user_id)
            else:
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(
                            """
                            SELECT id, user_id, title, metadata, created_at, updated_at, last_message_at
                            FROM conversations
                            WHERE user_id = %s::uuid
                            ORDER BY last_message_at DESC NULLS LAST, updated_at DESC
                            LIMIT 1
                            """,
                            (user_id,)
                        )
                        row = cur.fetchone()
                        if row:
                            return dict(row)
                        return await self.create_conversation(user_id)
        except Exception as e:
            logger.error(f"Error getting/creating recent conversation: {e}")
            return await self.create_conversation(user_id)

    async def add_message(self, conversation_id: str, user_id: str, role: str, content: str, tool_calls: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Insert a message into messages table"""
        try:
            if not self.use_direct_connection:
                payload = {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "role": role,
                    "content": content,
                    "tool_calls": tool_calls or None
                }
                result = self.client.table("messages").insert(payload).execute()
                # Update conversation recency
                try:
                    now_iso = datetime.now(timezone.utc).isoformat()
                    self.client.table("conversations").update({"last_message_at": now_iso, "updated_at": now_iso}).eq("id", conversation_id).execute()
                except Exception:
                    pass
                return result.data[0] if result.data else None
            else:
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(
                            """
                            INSERT INTO messages (conversation_id, user_id, role, content, tool_calls)
                            VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb)
                            RETURNING id, conversation_id, user_id, role, content, tool_calls, created_at
                            """,
                            (conversation_id, user_id, role, content, Json(tool_calls) if tool_calls is not None else None)
                        )
                        row = cur.fetchone()
                        # Update conversation recency
                        try:
                            cur.execute(
                                """
                                UPDATE conversations
                                SET last_message_at = NOW(), updated_at = NOW()
                                WHERE id = %s::uuid
                                RETURNING id
                                """,
                                (conversation_id,)
                            )
                            conn.commit()
                        except Exception:
                            conn.rollback()
                        return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            if not self.use_direct_connection and self.database_url and "Invalid API key" in str(e):
                self.use_direct_connection = True
                return await self.add_message(conversation_id, user_id, role, content, tool_calls)
            return None

    async def get_recent_messages(self, conversation_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch recent messages for context"""
        try:
            if not self.use_direct_connection:
                result = (
                    self.client
                    .table("messages")
                    .select("role, content, created_at, id")
                    .eq("conversation_id", conversation_id)
                    .order("created_at", desc=True)
                    .order("id", desc=True)
                    .limit(limit)
                    .execute()
                )
                return list(reversed(result.data)) if result.data else []
            else:
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(
                            """
                            SELECT role, content, created_at, id
                            FROM messages
                            WHERE conversation_id = %s::uuid
                            ORDER BY created_at DESC, id DESC
                            LIMIT %s
                            """,
                            (conversation_id, limit)
                        )
                        rows = cur.fetchall()
                        data = [dict(r) for r in rows] if rows else []
                        return list(reversed(data))
        except Exception as e:
            logger.error(f"Error fetching recent messages: {e}")
            if not self.use_direct_connection and self.database_url and "Invalid API key" in str(e):
                self.use_direct_connection = True
                return await self.get_recent_messages(conversation_id, limit)
            return []
    
    async def create_job(self, job_data: JobCreate, user_id: str) -> Optional[Dict[str, Any]]:
        """Create a new job entry"""
        try:
            if not self.use_direct_connection:
                data = {
                    "user_id": user_id,
                    "job_title": job_data.job_title,
                    "company_name": job_data.company_name,
                    "job_link": job_data.job_link,
                    "job_description": job_data.job_description,
                    "status": job_data.status.value if job_data.status else "applied"
                }
                result = self.client.table("jobs").insert(data).execute()
                if result.data:
                    logger.info(f"Created job: {job_data.job_title} at {job_data.company_name}")
                    return result.data[0]
                else:
                    logger.error("No data returned from job creation")
                    return None
            else:
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(
                            """
                            INSERT INTO jobs (user_id, job_title, company_name, job_link, job_description, status)
                            VALUES (%s::uuid, %s, %s, %s, %s, %s)
                            RETURNING id, user_id, job_title, company_name, job_link, job_description, status, date_added, last_updated
                            """,
                            (
                                user_id,
                                job_data.job_title,
                                job_data.company_name,
                                job_data.job_link,
                                job_data.job_description,
                                job_data.status.value if job_data.status else "applied"
                            )
                        )
                        row = cur.fetchone()
                        return dict(row) if row else None
                
        except Exception as e:
            logger.error(f"Error creating job: {str(e)}")
            if not self.use_direct_connection and self.database_url and "Invalid API key" in str(e):
                self.use_direct_connection = True
                return await self.create_job(job_data, user_id)
            return None
    
    async def update_job_status(self, job_id: str, status: JobStatus, user_id: str) -> Optional[Dict[str, Any]]:
        """Update job status"""
        try:
            if not self.use_direct_connection:
                data = {
                    "status": status.value,
                    "last_updated": "now()"
                }
                result = self.client.table("jobs").update(data).eq("id", job_id).eq("user_id", user_id).execute()
                if result.data:
                    logger.info(f"Updated job {job_id} status to {status.value}")
                    return result.data[0]
                else:
                    logger.error(f"No job found with id {job_id} for user {user_id}")
                    return None
            else:
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(
                            """
                            UPDATE jobs
                            SET status = %s, last_updated = NOW()
                            WHERE id = %s::uuid AND user_id = %s::uuid
                            RETURNING id, user_id, job_title, company_name, job_link, job_description, status, date_added, last_updated
                            """,
                            (status.value, job_id, user_id)
                        )
                        row = cur.fetchone()
                        return dict(row) if row else None
                
        except Exception as e:
            logger.error(f"Error updating job status: {str(e)}")
            if not self.use_direct_connection and self.database_url and "Invalid API key" in str(e):
                self.use_direct_connection = True
                return await self.update_job_status(job_id, status, user_id)
            return None
    
    async def get_user_jobs(self, user_id: str, status: Optional[JobStatus] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get jobs for a user, optionally filtered by status and limited."""
        try:
            if not self.use_direct_connection:
                query = self.client.table("jobs").select("*").eq("user_id", user_id)
                if status:
                    query = query.eq("status", status.value)
                query = query.order("date_added", desc=True)
                if limit:
                    query = query.limit(limit)
                result = query.execute()
                if result.data:
                    logger.info(f"Retrieved {len(result.data)} jobs for user {user_id}")
                    return result.data
                else:
                    logger.info(f"No jobs found for user {user_id}")
                    return []
            else:
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        if status:
                            cur.execute(
                                """
                                SELECT id, user_id, job_title, company_name, job_link, job_description, status, date_added, last_updated
                                FROM jobs
                                WHERE user_id = %s::uuid AND status = %s
                                ORDER BY date_added DESC
                                """ + (" LIMIT %s" if limit else ""),
                                (user_id, status.value) + ((limit,) if limit else tuple())
                            )
                        else:
                            cur.execute(
                                """
                                SELECT id, user_id, job_title, company_name, job_link, job_description, status, date_added, last_updated
                                FROM jobs
                                WHERE user_id = %s::uuid
                                ORDER BY date_added DESC
                                """ + (" LIMIT %s" if limit else ""),
                                (user_id,) + ((limit,) if limit else tuple())
                            )
                        rows = cur.fetchall()
                        data = [dict(r) for r in rows] if rows else []
                        logger.info(f"Retrieved {len(data)} jobs for user {user_id} (direct DB)")
                        return data
        except Exception as e:
            logger.error(f"Error retrieving jobs: {str(e)}")
            return []
    
    async def get_job_by_id(self, job_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific job by ID"""
        try:
            result = self.client.table("jobs").select("*").eq("id", job_id).eq("user_id", user_id).execute()
            
            if result.data:
                return result.data[0]
            else:
                logger.info(f"No job found with id {job_id} for user {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving job: {str(e)}")
            return None
    
    async def delete_job(self, job_id: str, user_id: str) -> bool:
        """Delete a specific job by ID"""
        try:
            if not self.use_direct_connection:
                result = self.client.table("jobs").delete().eq("id", job_id).eq("user_id", user_id).execute()
                return bool(result.data)
            else:
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "DELETE FROM jobs WHERE id = %s::uuid AND user_id = %s::uuid",
                            (job_id, user_id)
                        )
                        return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting job {job_id}: {str(e)}")
            return False
    
    async def delete_jobs_by_status(self, user_id: str, status: str) -> tuple[int, list[str]]:
        """Delete all jobs with a specific status for a user.
        Returns: (count_deleted, list_of_deleted_job_titles)
        """
        try:
            # First get the jobs to be deleted for confirmation
            jobs_to_delete = await self.search_jobs(user_id=user_id, status_filter=status)
            if not jobs_to_delete:
                return 0, []
            
            job_titles = [f"{j['job_title']} at {j['company_name']}" for j in jobs_to_delete]
            job_ids = [j['id'] for j in jobs_to_delete]
            
            if not self.use_direct_connection:
                # Delete in Supabase
                for job_id in job_ids:
                    result = self.client.table("jobs").delete().eq("id", job_id).eq("user_id", user_id).execute()
                return len(job_ids), job_titles
            else:
                # Delete via direct connection
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "DELETE FROM jobs WHERE user_id = %s::uuid AND status = %s",
                            (user_id, status)
                        )
                        return cur.rowcount, job_titles
                        
        except Exception as e:
            logger.error(f"Error deleting jobs with status {status}: {str(e)}")
            return 0, []
    
    async def search_jobs(self, user_id: str, company_name: Optional[str] = None, job_title: Optional[str] = None, 
                         status_filter: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search jobs by company name, job title, or status."""
        try:
            if not self.use_direct_connection:
                query = self.client.table("jobs").select("*").eq("user_id", user_id)
                if company_name:
                    query = query.ilike("company_name", f"%{company_name}%")
                if job_title:
                    query = query.ilike("job_title", f"%{job_title}%")
                if status_filter:
                    query = query.eq("status", status_filter)
                query = query.order("date_added", desc=True)
                if limit:
                    query = query.limit(limit)
                result = query.execute()
                if result.data:
                    logger.info(f"Found {len(result.data)} jobs matching search criteria")
                    return result.data
                else:
                    logger.info("No jobs found matching search criteria")
                    return []
            else:
                with psycopg2.connect(self.database_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        params = [user_id]
                        where_clauses = ["user_id = %s::uuid"]
                        if company_name:
                            where_clauses.append("company_name ILIKE %s")
                            params.append(f"%{company_name}%")
                        if job_title:
                            where_clauses.append("job_title ILIKE %s")
                            params.append(f"%{job_title}%")
                        if status_filter:
                            where_clauses.append("status = %s")
                            params.append(status_filter)
                        sql = (
                            "SELECT id, user_id, job_title, company_name, job_link, job_description, status, date_added, last_updated "
                            "FROM jobs WHERE " + " AND ".join(where_clauses) + " ORDER BY date_added DESC"
                        )
                        if limit:
                            sql += " LIMIT %s"
                            params.append(limit)
                        cur.execute(sql, tuple(params))
                        rows = cur.fetchall()
                        data = [dict(r) for r in rows] if rows else []
                        logger.info(f"Found {len(data)} jobs matching search criteria (direct DB)")
                        return data
        except Exception as e:
            logger.error(f"Error searching jobs: {str(e)}")
            return []
    
    async def delete_job(self, job_id: str, user_id: str) -> bool:
        """Delete a job entry"""
        try:
            result = self.client.table("jobs").delete().eq("id", job_id).eq("user_id", user_id).execute()
            
            if result.data:
                logger.info(f"Deleted job {job_id}")
                return True
            else:
                logger.error(f"No job found with id {job_id} for user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting job: {str(e)}")
            return False
    
    async def get_job_stats(self, user_id: str) -> Dict[str, int]:
        """Get job statistics for a user"""
        try:
            result = self.client.table("jobs").select("status").eq("user_id", user_id).execute()
            
            if not result.data:
                return {}
            
            stats = {}
            for job in result.data:
                status = job.get("status", "unknown")
                stats[status] = stats.get(status, 0) + 1
            
            logger.info(f"Retrieved job stats for user {user_id}: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error retrieving job stats: {str(e)}")
            return {}
