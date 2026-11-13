from fastapi import APIRouter

router=APIRouter()

categories = [
    {"id": 1, "name": "Hardware"},
    {"id": 2, "name": "Software"},
    {"id": 3, "name": "Network"},
]

@router.get("/categories")
def get_categories():
    return categories