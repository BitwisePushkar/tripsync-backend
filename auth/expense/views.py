from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from django.shortcuts import get_object_or_404
from .models import Budget, ExpenseCategory
from .serializers import (BudgetSerializer,ExpenseCategorySerializer,ExpenseCategoryListSerializer)

class BudgetView(APIView):
    permission_classes = [IsAuthenticated]
    def get_object(self, user):
        try:
            return Budget.objects.get(user=user)
        except Budget.DoesNotExist:
            return None
    @extend_schema(
        summary="Get user's budget",
        description="Retrieve the budget for the authenticated user",
        responses={
            200: BudgetSerializer,
            404: OpenApiTypes.OBJECT
        }
    )
    def get(self, request):
        budget = self.get_object(request.user)
        if budget is None:
            return Response({"error": "No budget found."},status=status.HTTP_404_NOT_FOUND)
        serializer = BudgetSerializer(budget)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Create budget",
        description="Create a new budget for the authenticated user.",
        request=BudgetSerializer,
        responses={
            201: BudgetSerializer,
            400: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Create Budget Example',
                value={'total': 50000.00},
                request_only=True
            )
        ]
    )
    def post(self, request):
        if Budget.objects.filter(user=request.user).exists():
            return Response({"error": "Budget already exists."},status=status.HTTP_400_BAD_REQUEST)       
        serializer = BudgetSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Update budget",
        description="Update budget fields",
        request=BudgetSerializer,
        responses={
            200: BudgetSerializer,
            404: OpenApiTypes.OBJECT
        }
    )
    def patch(self, request):
        budget = self.get_object(request.user)
        if budget is None:
            return Response(
                {"error": "No budget found."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = BudgetSerializer(budget, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Delete budget",
        description="Delete the user's budget",
        responses={
            204: None,
            404: OpenApiTypes.OBJECT
        }
    )
    def delete(self, request):
        budget = self.get_object(request.user)
        if budget is None:
            return Response({"error": "No budget found."},status=status.HTTP_404_NOT_FOUND)
        budget.delete()
        return Response({"message": "Budget deleted successfully"},status=status.HTTP_204_NO_CONTENT)

class ExpenseCategoryListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="List all expense categories",
        description="Retrieve all expense categories for the authenticated user",
        responses={200: ExpenseCategoryListSerializer(many=True)}
    )
    def get(self, request):
        categories = ExpenseCategory.objects.filter(user=request.user)
        serializer = ExpenseCategoryListSerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Create expense category",
        description="Create a new expense category. Budget must exist before creating categories.",
        request=ExpenseCategorySerializer,
        responses={
            201: ExpenseCategorySerializer,
            400: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Create Food Category',
                value={
                    'category': 'Food & Dining',
                    'allocated': 10000.00
                },
                request_only=True
            ),
            OpenApiExample(
                'Create Transport Category',
                value={
                    'category': 'Transport',
                    'allocated': 5000.00
                },
                request_only=True
            )
        ]
    )
    def post(self, request):
        try:
            budget = Budget.objects.get(user=request.user)
        except Budget.DoesNotExist:
            return Response({"error": "Please create a budget first."},status=status.HTTP_400_BAD_REQUEST)
        category = request.data.get('category')
        if ExpenseCategory.objects.filter(user=request.user, category=category).exists():
            return Response({"error": "Category already exists."},status=status.HTTP_400_BAD_REQUEST)
        serializer = ExpenseCategorySerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user, budget=budget)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ExpenseCategoryDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get_object(self, user, pk):
        return get_object_or_404(ExpenseCategory, user=user, pk=pk)
    @extend_schema(
        summary="Get category detail",
        description="Retrieve detailed information about a specific expense category",
        responses={200: ExpenseCategorySerializer}
    )
    def get(self, request, pk):
        category = self.get_object(request.user, pk)
        serializer = ExpenseCategorySerializer(category)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Update category",
        description="Update category fields",
        request=ExpenseCategorySerializer,
        responses={200: ExpenseCategorySerializer}
    )
    def patch(self, request, pk):
        category = self.get_object(request.user, pk)
        serializer = ExpenseCategorySerializer(category, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Delete category",
        description="Delete an expense category",
        responses={204: OpenApiTypes.OBJECT}
    )
    def delete(self, request, pk):
        category = self.get_object(request.user, pk)
        category.delete()
        return Response(
            {"message": "Category deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )

class BudgetSummaryView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="Get budget summary",
        description="Get a comprehensive summary including total budget, total allocated amount, remaining budget, total number of categories, and all categories with their details",
        responses={
            200: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Summary Response',
                value={
                    'total': 50000.00,
                    'total_allocated': 25000.00,
                    'remaining_budget': 25000.00,
                    'total_categories': 2,
                    'categories': [
                        {
                            'id': 1,
                            'category': 'Food & Dining',
                            'allocated': 10000.00
                        },
                        {
                            'id': 2,
                            'category': 'Transport',
                            'allocated': 15000.00
                        }
                    ]
                },
                response_only=True
            )
        ]
    )
    def get(self, request):
        try:
            budget = Budget.objects.get(user=request.user)
        except Budget.DoesNotExist:
            return Response({"error": "No budget found."},status=status.HTTP_404_NOT_FOUND)
        
        categories = ExpenseCategory.objects.filter(user=request.user)
        total_allocated = sum(cat.allocated for cat in categories)
        remaining_budget = budget.total - total_allocated
        total_categories = categories.count()
        percentage_allocated = round((total_allocated / budget.total) * 100, 2) if budget.total else 0
        percentage_remaining = round((remaining_budget / budget.total) * 100, 2) if budget.total else 0        
        serializer = ExpenseCategoryListSerializer(categories, many=True)         
        return Response({"total": float(budget.total),"total_allocated": float(total_allocated),"remaining_budget": float(remaining_budget),"percentage_allocated": percentage_allocated,"percentage_remaining": percentage_remaining,"total_categories": total_categories,"categories": serializer.data}, status=status.HTTP_200_OK)