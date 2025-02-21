from django.urls import path
from . import views

urlpatterns = [

    # path('', views.handle_employee_form, name='handle_employee_form'),
    path('employee_management/', views.handle_employee_form, name='handle_employee_form'),
    path('ok', views.send_employee_emails, name='send_employee_emails'),
    path('search_employee_data/', views.search_employee_data, name='search_employee_data'),
    path('sort_employee_data/', views.sort_employee_data, name='sort_employee_data'),
    path('employee_message_template/', views.employee_message_template, name='employee_message_template'),   
    path('fetch-columns/', views.fetch_columns, name='fetch_columns'),  

]

