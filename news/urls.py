from django.urls import path

from .views import NewsDetailView, NewsListView

urlpatterns = [
    path("api/news/", NewsListView.as_view(), name="news-list"),
    path("api/news/<int:pk>/", NewsDetailView.as_view(), name="news-detail"),
]
