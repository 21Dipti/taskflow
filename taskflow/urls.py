from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .middleware import get_metrics


@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request):
    return Response({
        'message': 'Welcome to TaskFlow API',
        'endpoints': {
            'signup': '/api/auth/signup/',
            'login': '/api/auth/login/',
            'token_refresh': '/api/auth/token/refresh/',
            'projects': '/api/projects/',
            'tasks': '/api/tasks/',
            'notifications': '/api/notifications/',
            'health': '/health/',
            'metrics': '/metrics/',
        }
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return Response({'status': 'ok'})


@api_view(['GET'])
@permission_classes([AllowAny])
def metrics_view(request):
    return Response(get_metrics())


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/', include('projects.urls')),
    path('api/', include('notifications.urls')),
    path('', TemplateView.as_view(template_name='index.html'), name='frontend'),
    path('api/', api_root, name='api-root'),
    path('health/', health_check, name='health'),
    path('metrics/', metrics_view, name='metrics'),
]
