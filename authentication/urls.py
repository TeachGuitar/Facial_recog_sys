from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.signin, name='signin'),
    path('signup', views.signup, name='signup'),
    path('index', views.index, name='index'),
    path('check_username/', views.check_username_availability, name='check_username'),
    path('check_email/', views.check_email_availability, name='check_email'),
    path('signout', views.signout, name='signout'),
    path('activate/<uidb64>/<token>', views.activate, name='activate'),
    path('capture_frame/', views.capture_frame, name='capture_frame'),
    path('video_receive/', views.video_receive, name='video_receive'),
]
