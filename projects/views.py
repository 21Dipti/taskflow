import hashlib
from django.core.cache import cache
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Project, Task
from .serializers import ProjectSerializer, TaskSerializer
from .filters import TaskFilter


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = TaskFilter

    def get_queryset(self):
        return Task.objects.filter(project__owner=self.request.user).select_related('project').order_by('-created_at')

    def list(self, request, *args, **kwargs):
        cache_key = self._build_cache_key(request)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=300)
        return response

    def perform_create(self, serializer):
        serializer.save()
        self._invalidate_task_cache()

    def perform_update(self, serializer):
        old_assignee = serializer.instance.assignee_id
        old_status = serializer.instance.status

        task = serializer.save()

        from notifications.tasks import notify_task_reassigned, notify_status_changed
        if task.assignee_id != old_assignee and task.assignee_id is not None:
            notify_task_reassigned.delay(task.id, old_assignee, task.assignee_id)
        if task.status != old_status:
            notify_status_changed.delay(task.id, old_status, task.status)

        self._invalidate_task_cache()

    def perform_destroy(self, instance):
        instance.delete()
        self._invalidate_task_cache()

    def _build_cache_key(self, request):
        params = request.query_params.urlencode()
        raw = f"task_list:{request.user.id}:{params}"
        return f"task_list:{hashlib.md5(raw.encode()).hexdigest()}"

    def _invalidate_task_cache(self):
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern('task_list:*')
        else:
            cache.clear()
