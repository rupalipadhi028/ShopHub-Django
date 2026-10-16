from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminOrReadOnly(BasePermission):
    """Allow public catalog reads and reserve catalog writes for staff users."""

    def has_permission(self, request, view):
        return bool(request.method in SAFE_METHODS or request.user and request.user.is_staff)


class IsOwnerOrReadOnly(BasePermission):
    """Allow authenticated users to read reviews, but edit only their own."""

    def has_permission(self, request, view):
        return bool(request.method in SAFE_METHODS or request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return bool(request.method in SAFE_METHODS or obj.user_id == request.user.id)
