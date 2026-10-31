from rest_framework.permissions import BasePermission


class IsStoreAdmin(BasePermission):
    """Solo usuarios identificados que sean dueños de una tienda activa."""
    message = "Esta cuenta no administra ninguna tienda activa."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        store = getattr(user, "store", None)
        return bool(store and store.is_active)