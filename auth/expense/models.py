from django.db import models
from account.models import User

class Budget(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='budget', primary_key=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"{self.user.email} - Budget: {self.total}"   
    class Meta:
        ordering = ['-created_at']

class ExpenseCategory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expense_categories')
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='categories')
    category = models.CharField(max_length=50, choices=[('Food & Dining', 'Food & Dining'),('Transport', 'Transport'),('Entertainment', 'Entertainment'),('Friend', 'Friend'),('Accomodation', 'Accomodation'),('Shopping', 'Shopping'),('other', 'Other'),])
    allocated = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"{self.user.email} - {self.category}: {self.allocated}"
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'category']