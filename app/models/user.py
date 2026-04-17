from datetime import datetime

from autonomous.auth.user import User
from autonomous.model.autoattr import StringAttr

ROLES = ["viewer", "editor", "admin"]


class AppUser(User):
    """Extends autonomous.auth.user.User to add `viewer` + `editor` roles.

    Why this subclass: upstream User.authenticate() hard-codes role="user" on
    every login, which would clobber admin-promoted accounts. We override to
    preserve existing roles on repeat logins and to bootstrap the first user
    as admin.
    """

    role = StringAttr(choices=ROLES, default="viewer")

    @classmethod
    def authenticate(cls, user_info: dict, token: str | None = None) -> "AppUser":
        email = (user_info.get("email") or "").strip()
        name = (user_info.get("name") or email).strip()
        if not email:
            raise ValueError("Google userinfo is missing an email")

        user = cls.find(email=email)
        is_new = user is None
        if is_new:
            user = cls(email=email, name=name)

        user.name = name
        user.email = email
        user.provider = "google"
        user.token = token or ""
        user.last_login = datetime.now()
        user.state = "authenticated"

        if is_new and cls.objects(role="admin").count() == 0:
            user.role = "admin"
        elif is_new:
            user.role = "viewer"
        # else: preserve existing role

        user.save()
        return user

    @property
    def is_viewer(self) -> bool:
        return self.role in ("viewer", "editor", "admin")

    @property
    def is_editor(self) -> bool:
        return self.role in ("editor", "admin")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def __repr__(self):
        return f"<AppUser {self.pk} {self.email} {self.role}>"
