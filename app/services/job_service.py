"""
Job service for JobTrackAI
Handles job-related database operations and business logic
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional
from ..models.job import Job, JobCreate, JobUpdate, JobStatus

logger = logging.getLogger(__name__)

class JobService:
    """Service for job-related operations"""
    
    def __init__(self):
        # TODO: Initialize Supabase client
        self.jobs = {}  # Temporary in-memory storage for development
    
    async def create_job(self, job_data: JobCreate) -> Job:
        """
        Create a new job entry
        """
        try:
            job_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            job = Job(
                id=job_id,
                user_id=job_data.user_id,
                job_title=job_data.job_title,
                company_name=job_data.company_name,
                job_link=job_data.job_link,
                job_description=job_data.job_description,
                status=job_data.status,
                date_added=now,
                last_updated=now
            )
            
            # Store in temporary storage
            self.jobs[job_id] = job
            
            logger.info(f"Created job: {job.job_title} at {job.company_name}")
            return job
            
        except Exception as e:
            logger.error(f"Error creating job: {str(e)}")
            raise
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get a job by ID
        """
        try:
            return self.jobs.get(job_id)
        except Exception as e:
            logger.error(f"Error getting job {job_id}: {str(e)}")
            return None
    
    async def get_user_jobs(self, user_id: str) -> List[Job]:
        """
        Get all jobs for a specific user
        """
        try:
            user_jobs = [job for job in self.jobs.values() if job.user_id == user_id]
            return sorted(user_jobs, key=lambda x: x.date_added, reverse=True)
        except Exception as e:
            logger.error(f"Error getting jobs for user {user_id}: {str(e)}")
            return []
    
    async def update_job(self, job_id: str, job_update: JobUpdate) -> Optional[Job]:
        """
        Update an existing job
        """
        try:
            job = self.jobs.get(job_id)
            if not job:
                logger.warning(f"Job {job_id} not found")
                return None
            
            # Update fields
            if job_update.job_title is not None:
                job.job_title = job_update.job_title
            if job_update.company_name is not None:
                job.company_name = job_update.company_name
            if job_update.job_link is not None:
                job.job_link = job_update.job_link
            if job_update.job_description is not None:
                job.job_description = job_update.job_description
            if job_update.status is not None:
                job.status = job_update.status
            
            job.last_updated = datetime.utcnow()
            
            logger.info(f"Updated job {job_id}: {job.job_title}")
            return job
            
        except Exception as e:
            logger.error(f"Error updating job {job_id}: {str(e)}")
            return None
    
    async def delete_job(self, job_id: str) -> bool:
        """
        Delete a job
        """
        try:
            if job_id in self.jobs:
                del self.jobs[job_id]
                logger.info(f"Deleted job {job_id}")
                return True
            else:
                logger.warning(f"Job {job_id} not found for deletion")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting job {job_id}: {str(e)}")
            return False
    
    async def search_jobs(
        self, 
        user_id: str, 
        query: str = None, 
        status: JobStatus = None,
        company: str = None
    ) -> List[Job]:
        """
        Search jobs with filters
        """
        try:
            user_jobs = await self.get_user_jobs(user_id)
            
            # Apply filters
            if query:
                query_lower = query.lower()
                user_jobs = [
                    job for job in user_jobs
                    if (query_lower in job.job_title.lower() or 
                        query_lower in job.company_name.lower() or
                        (job.job_description and query_lower in job.job_description.lower()))
                ]
            
            if status:
                user_jobs = [job for job in user_jobs if job.status == status]
            
            if company:
                company_lower = company.lower()
                user_jobs = [job for job in user_jobs if company_lower in job.company_name.lower()]
            
            return user_jobs
            
        except Exception as e:
            logger.error(f"Error searching jobs: {str(e)}")
            return []
    
    async def get_job_stats(self, user_id: str) -> dict:
        """
        Get job application statistics for a user
        """
        try:
            user_jobs = await self.get_user_jobs(user_id)
            
            stats = {
                "total_applications": len(user_jobs),
                "by_status": {},
                "by_company": {},
                "recent_applications": 0
            }
            
            # Count by status
            for job in user_jobs:
                status = job.status.value
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
                
                # Count by company
                company = job.company_name
                stats["by_company"][company] = stats["by_company"].get(company, 0) + 1
                
                # Count recent applications (last 30 days)
                days_ago = (datetime.utcnow() - job.date_added).days
                if days_ago <= 30:
                    stats["recent_applications"] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting job stats: {str(e)}")
            return {}
