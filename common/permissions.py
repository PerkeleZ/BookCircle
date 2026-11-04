from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsModerator(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_moderator)


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_admin)


class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.owner_id == request.user.id


class ReadOnlyOrAuthenticated(BasePermission):
    """Чтение — всем, изменения — только вошедшим."""
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or bool(request.user.is_authenticated)
