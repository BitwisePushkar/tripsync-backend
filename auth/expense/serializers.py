from rest_framework import serializers
from .models import Budget, ExpenseCategory

class BudgetSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)     
    class Meta:
        model = Budget
        fields = ['user_id', 'email', 'total', 'created_at', 'updated_at']
        read_only_fields = ['user_id', 'email', 'created_at', 'updated_at']   
    def validate_total(self, value):
        if not (2000 <= value <= 1000000):
            raise serializers.ValidationError("Budget must be between ₹2,000 and ₹10,00,000")
        return value

class ExpenseCategorySerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    budget_id = serializers.IntegerField(source='budget.id', read_only=True)
    percentage = serializers.SerializerMethodField(read_only=True)    
    class Meta:
        model = ExpenseCategory
        fields = ['id', 'user_id', 'email', 'budget_id', 'category', 'allocated', 'percentage', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user_id', 'email', 'budget_id', 'percentage', 'created_at', 'updated_at']    
    def get_percentage(self, obj):
        if obj.budget and obj.budget.total:
            return round((obj.allocated / obj.budget.total) * 100, 2)
        return 0   
    def validate_allocated(self, value):
        if value <= 0:
            raise serializers.ValidationError("Allocated amount must be greater than 0")
        return value

    def validate(self, data):
        user = self.context['request'].user
        if 'allocated' in data:
            allocated = data['allocated']
        elif self.instance:
            allocated = self.instance.allocated
        else:
            raise serializers.ValidationError({"allocated": "This field is required"})
        try:
            budget = Budget.objects.get(user=user)
        except Budget.DoesNotExist:
            raise serializers.ValidationError("Budget not found")
        categories = ExpenseCategory.objects.filter(user=user)
        if self.instance:
            categories = categories.exclude(pk=self.instance.pk)       
        total_allocated = sum(c.allocated for c in categories)
        new_total = total_allocated + allocated
        if new_total > budget.total:
            remaining = budget.total - total_allocated
            raise serializers.ValidationError("Allocated amount exceeds remaining budget. ")
        return data

class ExpenseCategoryListSerializer(serializers.ModelSerializer):
    percentage = serializers.SerializerMethodField()       
    class Meta:
        model = ExpenseCategory
        fields = ['id', 'category', 'allocated', 'percentage']     
    def get_percentage(self, obj):
        if obj.budget and obj.budget.total:
            return round((obj.allocated / obj.budget.total) * 100, 2)
        return 0