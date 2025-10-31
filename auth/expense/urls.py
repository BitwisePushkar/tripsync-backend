from django.urls import path
from .views import (BudgetView,ExpenseCategoryListCreateView,ExpenseCategoryDetailView,BudgetSummaryView)

urlpatterns = [
    path('budget/', BudgetView.as_view(), name='budget'),
    path('categories/', ExpenseCategoryListCreateView.as_view(), name='category-list-create'),
    path('categories/<int:pk>/', ExpenseCategoryDetailView.as_view(), name='category-detail'),
    path('budget/summary/', BudgetSummaryView.as_view(), name='budget-summary'),
]