from rest_framework import serializers
from .models import Project, Task


class ProjectSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.id')

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'owner', 'created_at', 'updated_at']


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'project', 'assignee',
            'status', 'due_date', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_project(self, value):
        request = self.context['request']
        if value.owner != request.user:
            raise serializers.ValidationError("You can only add tasks to your own projects.")
        return value
