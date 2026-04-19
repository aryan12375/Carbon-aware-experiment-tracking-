"""
app/api/v1/endpoints/projects.py
==================================
CRUD for Projects — grouping container for emissions runs.

POST   /projects           — create
GET    /projects           — list all
GET    /projects/{id}      — detail with run count
PATCH  /projects/{id}      — update
DELETE /projects/{id}      — delete (cascades to runs)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.emissions import ProjectCreate, ProjectOut, ProjectUpdate
from app.services.emissions_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, db: AsyncSession = Depends(get_db)) -> ProjectOut:
    try:
        project = await ProjectService.create(db, payload.name, payload.description, payload.team)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    count = await ProjectService.get_run_count(db, project.id)
    return ProjectOut.from_orm_with_count(project, count)


@router.get("", response_model=list[ProjectOut])
async def list_projects(db: AsyncSession = Depends(get_db)) -> list[ProjectOut]:
    projects = await ProjectService.get_all(db)
    result = []
    for p in projects:
        count = await ProjectService.get_run_count(db, p.id)
        result.append(ProjectOut.from_orm_with_count(p, count))
    return result


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)) -> ProjectOut:
    project = await ProjectService.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    count = await ProjectService.get_run_count(db, project_id)
    return ProjectOut.from_orm_with_count(project, count)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: int, payload: ProjectUpdate, db: AsyncSession = Depends(get_db)
) -> ProjectOut:
    project = await ProjectService.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description
    if payload.team is not None:
        project.team = payload.team
    await db.flush()
    count = await ProjectService.get_run_count(db, project_id)
    return ProjectOut.from_orm_with_count(project, count)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)) -> None:
    deleted = await ProjectService.delete(db, project_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
