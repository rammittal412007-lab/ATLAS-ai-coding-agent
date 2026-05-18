import uuid
from typing import List

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.repos import get_current_user
from app.core.database import get_db
from app.models.models import AgentRun, Repository, Task, User
from app.schemas.schemas import AgentRunRead, TaskCreate, TaskRead
from app.workers.celery_app import run_agent_task

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/tasks")


@router.post("", response_model=TaskRead, status_code=status.HTTP_202_ACCEPTED)
async def create_task(
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    repo_result = await db.execute(
        select(Repository).where(
            Repository.id == body.repository_id,
            Repository.owner_id == user.id,
        )
    )
    repo = repo_result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Repository not ready (status: {repo.status}). Wait for indexing.",
        )

    task = Task(
        id=str(uuid.uuid4()),
        user_id=user.id,
        repository_id=body.repository_id,
        title=body.title,
        description=body.description,
        status="queued",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    run_agent_task.apply_async(
        kwargs={"task_id": task.id, "user_id": user.id},
        queue="default",
    )
    return task


@router.get("", response_model=List[TaskRead])
async def list_tasks(
    repository_id: str = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Task).where(Task.user_id == user.id)
    if repository_id:
        query = query.where(Task.repository_id == repository_id)
    query = query.order_by(Task.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/{task_id}/agent-runs", response_model=List[AgentRunRead])
async def get_agent_runs(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task_res = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    if not task_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Task not found")
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.task_id == task_id)
        .order_by(AgentRun.created_at.asc())
    )
    return result.scalars().all()


@router.post("/{task_id}/retry", response_model=TaskRead)
async def retry_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in ("failed", "cancelled"):
        raise HTTPException(status_code=400, detail="Only failed tasks can be retried")
    task.status = "queued"
    task.retry_count += 1
    task.error_message = None
    await db.commit()
    await db.refresh(task)
    run_agent_task.apply_async(
        kwargs={"task_id": task.id, "user_id": user.id}, queue="default"
    )
    return task


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.celery_task_id:
        from app.workers.celery_app import celery_app
        celery_app.control.revoke(task.celery_task_id, terminate=True)
    await db.delete(task)
    await db.commit()
