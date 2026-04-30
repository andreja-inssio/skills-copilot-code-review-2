"""
Announcements endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional, List
from datetime import date
from bson import ObjectId
from bson.errors import InvalidId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def _doc_to_dict(doc: dict) -> dict:
    """Convert a MongoDB document to a serializable dict."""
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


def _require_teacher(teacher_username: str) -> dict:
    """Validate the teacher exists; raise 401 if not."""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")
    return teacher


def _parse_object_id(announcement_id: str) -> ObjectId:
    try:
        return ObjectId(announcement_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=400, detail="Invalid announcement ID")


def _validate_dates(expiration_date: str, start_date: Optional[str]) -> None:
    try:
        date.fromisoformat(expiration_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid expiration_date format (expected YYYY-MM-DD)")
    if start_date:
        try:
            date.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format (expected YYYY-MM-DD)")


@router.get("", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """
    Get all currently active announcements.

    An announcement is active when:
    - Its expiration_date is today or in the future, AND
    - Its start_date (if set) is today or in the past.
    """
    today = date.today().isoformat()
    result = []
    for doc in announcements_collection.find():
        if doc.get("expiration_date", "") < today:
            continue
        start = doc.get("start_date")
        if start and start > today:
            continue
        result.append(_doc_to_dict(doc))
    return result


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(
    teacher_username: str = Query(...)
) -> List[Dict[str, Any]]:
    """
    Get all announcements including expired ones.
    Requires teacher authentication.
    """
    _require_teacher(teacher_username)
    result = [_doc_to_dict(doc) for doc in announcements_collection.find()]
    result.sort(key=lambda x: x.get("expiration_date", ""))
    return result


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    message: str,
    expiration_date: str,
    teacher_username: str = Query(...),
    start_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new announcement.
    Requires teacher authentication.
    expiration_date is required; start_date is optional.
    """
    _require_teacher(teacher_username)
    _validate_dates(expiration_date, start_date)

    doc: Dict[str, Any] = {
        "message": message,
        "expiration_date": expiration_date,
        "created_by": teacher_username,
    }
    if start_date:
        doc["start_date"] = start_date

    insert_result = announcements_collection.insert_one(doc)
    created = announcements_collection.find_one({"_id": insert_result.inserted_id})
    return _doc_to_dict(created)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    message: str,
    expiration_date: str,
    teacher_username: str = Query(...),
    start_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update an existing announcement.
    Requires teacher authentication.
    """
    _require_teacher(teacher_username)
    obj_id = _parse_object_id(announcement_id)
    _validate_dates(expiration_date, start_date)

    set_fields: Dict[str, Any] = {
        "message": message,
        "expiration_date": expiration_date,
    }
    unset_fields: Dict[str, Any] = {}

    if start_date:
        set_fields["start_date"] = start_date
    else:
        unset_fields["start_date"] = ""

    update_op: Dict[str, Any] = {"$set": set_fields}
    if unset_fields:
        update_op["$unset"] = unset_fields

    result = announcements_collection.update_one({"_id": obj_id}, update_op)
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    updated = announcements_collection.find_one({"_id": obj_id})
    return _doc_to_dict(updated)


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: str = Query(...)
) -> Dict[str, str]:
    """
    Delete an announcement.
    Requires teacher authentication.
    """
    _require_teacher(teacher_username)
    obj_id = _parse_object_id(announcement_id)

    result = announcements_collection.delete_one({"_id": obj_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted"}
