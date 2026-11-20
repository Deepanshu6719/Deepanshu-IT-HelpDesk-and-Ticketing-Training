
from models.user import User


def has_role(current_user: User, role_name: str) -> bool:
    return any(
        assignment.role.name == role_name
        for assignment in current_user.role_assignments
    )
